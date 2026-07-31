#!/usr/bin/env bash
# Stop alles wat ./start.sh heeft gestart: tunnel, server en Hermes.

set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"

UITVOER="${DAKAN_UITVOER:-$PWD/output}"

for onderdeel in tunnel server hermes; do
  bestand="$UITVOER/$onderdeel.pid"
  if [ -f "$bestand" ] && kill -0 "$(cat "$bestand")" 2>/dev/null; then
    kill "$(cat "$bestand")" && echo "$onderdeel gestopt."
    rm -f "$bestand"
  else
    echo "$onderdeel draaide niet."
    rm -f "$bestand"
  fi
done
