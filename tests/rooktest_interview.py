"""Rooktest: één volledig interview van begin tot eind, via de echte server.

Dit is de enige test die telt voor de vraag of de fabriek werkt: er gaat een
ondernemer in en er komen acht bestanden uit. Alles gaat over de echte HTTP-weg
die ook een bezoeker aflegt, met Hermes als motor.

De ondernemer wordt nagespeeld door een goedkoop model. Die kent het protocol
niet — die praat gewoon zoals een schilder praat.

Draaien:  .venv/bin/python tests/rooktest_interview.py
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

PROJECT = Path(__file__).resolve().parent.parent
SERVER = os.environ.get("DAKAN_SERVER", "http://127.0.0.1:8787")
ONDERNEMER_MODEL = "anthropic/claude-haiku-4.5"
MAX_BEURTEN = int(os.environ.get("MAX_BEURTEN", "120"))

PERSONA = """Je bent Marloes Verhoeven, 44, eigenaar van Verhoeven Schilderwerk in Zwolle.
Drie schilders in dienst, jij doet de offertes, planning en klantcontact.
Je bent nuchter, praat kort, en gebruikt geen enkel technisch of AI-jargon.

Wat er speelt (verzin gerust details erbij, blijf consistent):
- Aanvragen komen per mail en via het formulier op de site. Veel te veel, en er
  zitten ook aanbiedingen van leveranciers tussen.
- Offertes maak je in Excel. Per klus schat je het aantal vierkante meters.
- Bij klussen boven de 200 vierkante meter wil je altijd eerst zelf gaan kijken
  voordat er een prijs uitgaat. Kleinere klussen mag iemand anders inschatten.
- Je plant je ploegen per week in. Bij regen schuift alles.
- Kleuradvies aan klanten doe je altijd zelf, dat geef je nooit uit handen.
- Klachten handel je zelf af, daar wil je niemand tussen.
- Je weet niet welk boekhoudpakket je vaste kracht Ricardo gebruikt; dat moet je
  navragen.

Antwoord als Marloes, in gewone spreektaal, 1 tot 4 zinnen. Geen opsommingen,
geen kopjes. Word je iets gevraagd dat je echt niet weet, zeg dat dan gewoon.
Vindt de interviewer dat hij genoeg heeft en vraagt hij of hij mag afronden,
zeg dan ja tenzij je echt nog iets kwijt wil."""


def ondernemer_antwoord(api_key, geschiedenis):
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": ONDERNEMER_MODEL,
            "messages": [{"role": "system", "content": PERSONA}] + geschiedenis,
            "max_tokens": 300,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def eerste_code():
    codes = json.loads((PROJECT / "codes.json").read_text())
    return codes[0] if isinstance(codes, list) else list(codes)[0]


def main():
    api_key = os.environ.get("API_KEY")
    if not api_key:
        sys.exit("API_KEY ontbreekt — draai eerst: set -a; source .env; set +a")

    code = eerste_code()
    start = requests.post(f"{SERVER}/interview/start", json={"code": code}, timeout=60)
    start.raise_for_status()
    welkomst = start.json()["tekst"]
    print(f"sessie: {start.json()['sessie_id']}", flush=True)

    geschiedenis = [{"role": "user", "content": welkomst}]
    vastgelegd = {}
    t0 = time.time()

    for ronde in range(1, MAX_BEURTEN + 1):
        antwoord = ondernemer_antwoord(api_key, geschiedenis)
        geschiedenis.append({"role": "assistant", "content": antwoord})

        resp = requests.post(
            f"{SERVER}/interview/bericht",
            json={"code": code, "tekst": antwoord},
            timeout=900,
        )
        resp.raise_for_status()
        data = resp.json()

        for beurt in data.get("beurten", []):
            soort = beurt.get("type", "?")
            vastgelegd[soort] = vastgelegd.get(soort, 0) + 1

        gegevens = sum(v for k, v in vastgelegd.items() if k not in ("dialoog", "afronding"))
        print(f"ronde {ronde:3d} | {int(time.time()-t0):4d}s | vastgelegd: {gegevens} | {vastgelegd}", flush=True)

        if data.get("afgerond"):
            bestanden = data.get("bestanden") or {}
            print(f"\nAFGEROND na {ronde} rondes, {int(time.time()-t0)}s", flush=True)
            print(f"BESTANDEN: {len(bestanden)}", flush=True)
            for naam in bestanden:
                print(f"  - {naam} ({len(bestanden[naam])} tekens)", flush=True)
            if len(bestanden) == 8:
                print("\nGESLAAGD: acht bestanden opgeleverd.")
                return 0
            print(f"\nGEZAKT: {len(bestanden)} bestanden in plaats van 8.")
            return 1

        geschiedenis.append({"role": "user", "content": data.get("tekst") or "(geen vraag)"})

    print(f"\nGEZAKT: na {MAX_BEURTEN} rondes nog niet afgerond. Vastgelegd: {vastgelegd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
