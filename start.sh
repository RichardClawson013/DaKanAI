#!/usr/bin/env bash
# Start DaKanAI compleet: Hermes, de interviewserver, de tunnel, en de site.
#
# Het adres van de tunnel verandert bij elke herstart. Dit script zet dat nieuwe
# adres zelf in de interviewpagina en publiceert die, zodat niemand dat met de
# hand hoeft te doen.
#
# Gebruik:  ./start.sh
# Stoppen:  ./stop.sh

set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

UITVOER="${DAKAN_UITVOER:-$PWD/output}"
mkdir -p "$UITVOER"

set -a
source .env
set +a
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-$API_KEY}"

wacht_op() {  # wacht_op <url> <seconden>
  local url="$1" limiet="$2" verstreken=0
  until curl -s -m 3 -o /dev/null "$url"; do
    sleep 2
    verstreken=$((verstreken + 2))
    [ "$verstreken" -ge "$limiet" ] && return 1
  done
}

draait() {  # draait <pid-bestand>
  [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null
}

# ── 1. Hermes: de motor die het gesprek voert ────────────────────────────────
if draait "$UITVOER/hermes.pid"; then
  echo "Hermes draait al."
else
  nohup "$HOME/.local/bin/hermes" gateway > "$UITVOER/hermes-gateway.log" 2>&1 &
  echo $! > "$UITVOER/hermes.pid"
  if wacht_op "http://127.0.0.1:8642/health" 60; then
    echo "Hermes gestart."
  else
    echo "FOUT: Hermes komt niet op. Zie $UITVOER/hermes-gateway.log" >&2
    exit 1
  fi
fi

# ── 2. De interviewserver ────────────────────────────────────────────────────
if draait "$UITVOER/server.pid"; then
  echo "Server draait al."
else
  nohup .venv/bin/python -m server.app > "$UITVOER/server.log" 2>&1 &
  echo $! > "$UITVOER/server.pid"
  if wacht_op "http://127.0.0.1:${PORT:-8787}/gezond" 30; then
    echo "Server gestart op poort ${PORT:-8787}."
  else
    echo "FOUT: de server komt niet op. Zie $UITVOER/server.log" >&2
    exit 1
  fi
fi

# ── 3. De tunnel, zodat de site buiten deze pc bij de server kan ─────────────
if draait "$UITVOER/tunnel.pid" && [ -s "$UITVOER/tunnel-url.txt" ] \
   && curl -s -m 5 -o /dev/null "$(cat "$UITVOER/tunnel-url.txt")/gezond"; then
  ADRES=$(cat "$UITVOER/tunnel-url.txt")
  echo "Tunnel draait al: $ADRES"
else
  nohup "$HOME/.local/bin/cloudflared" tunnel --url "http://localhost:${PORT:-8787}" \
    > "$UITVOER/tunnel.log" 2>&1 &
  echo $! > "$UITVOER/tunnel.pid"
  ADRES=""
  for _ in $(seq 1 30); do
    ADRES=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" "$UITVOER/tunnel.log" | head -1 || true)
    [ -n "$ADRES" ] && break
    sleep 2
  done
  if [ -z "$ADRES" ]; then
    echo "FOUT: geen tunnel-adres gevonden. Zie $UITVOER/tunnel.log" >&2
    exit 1
  fi
  echo "$ADRES" > "$UITVOER/tunnel-url.txt"
  echo "Tunnel gestart: $ADRES"
fi

# ── 4. Het nieuwe adres in de pagina zetten en publiceren ────────────────────
HUIDIG=$(grep -oE 'https://[a-z0-9.-]+\.trycloudflare\.com' index.html | head -1 || true)
if [ "$HUIDIG" = "$ADRES" ]; then
  echo "De site wijst al naar dit adres."
else
  sed -i "s|https://[a-z0-9.-]*\.trycloudflare\.com|$ADRES|g" index.html
  cp index.html web/index.html
  if git diff --quiet -- index.html web/index.html; then
    echo "Pagina ongewijzigd."
  else
    git add index.html web/index.html
    git commit -q -m "chore: interviewpagina wijst naar het huidige tunnel-adres"
    if git push -q origin HEAD 2>/dev/null; then
      echo "Site bijgewerkt en gepubliceerd."
    else
      echo "LET OP: pagina lokaal bijgewerkt, publiceren mislukt (geen verbinding?)." >&2
    fi
  fi
fi

echo
echo "Interview hier:    http://127.0.0.1:${PORT:-8787}/"
echo "Interview publiek: $ADRES"
echo "Monitor:           ./start-monitor.sh"
