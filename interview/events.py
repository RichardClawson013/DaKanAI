"""Event-logger: schrijft gestructureerde events naar JSONL voor de monitor."""

import json
import time
from pathlib import Path

from . import paden


def _eventlog():
    return paden.eventlog()


def _schrijf(event_type: str, **data):
    _eventlog().parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": time.time(), "type": event_type, **data}
    with open(_eventlog(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def server_gestart(poort: int, provider: str, model: str):
    _schrijf("server_start", poort=poort, provider=provider, model=model)


def sessie_gestart(interview_id: str, code_hash: str):
    _schrijf("sessie_start", interview_id=interview_id, code=code_hash)


def ondernemer_bericht(tekst: str, beurt_nr: int):
    _schrijf("ondernemer", tekst=tekst[:120], beurt=beurt_nr)


def llm_aanroep(provider: str, model: str):
    _schrijf("llm_aanroep", provider=provider, model=model)


def llm_antwoord(duur_sec: float, lengte: int):
    _schrijf("llm_antwoord", duur=round(duur_sec, 1), lengte=lengte)


def llm_fout(fout: str, poging: int):
    _schrijf("llm_fout", fout=fout[:200], poging=poging)


def validatie_ok(aantal_beurten: int, types: list[str]):
    _schrijf("validatie_ok", beurten=aantal_beurten, types=types)


def validatie_fout(fouten: list[str], poging: int):
    _schrijf("validatie_fout", fouten=fouten[:5], poging=poging)


def retry(poging: int, reden: str):
    _schrijf("retry", poging=poging, reden=reden[:200])


def herstel(tekst: str):
    _schrijf("herstel", tekst=tekst[:120])


def naamstap(naam: str):
    _schrijf("naamstap", naam=naam)


def status_check(status: str):
    _schrijf("status_check", status=status)


def compilatie_start():
    _schrijf("compilatie_start")


def compilatie_klaar(bestanden: int, output_dir: str):
    _schrijf("compilatie_klaar", bestanden=bestanden, output_dir=output_dir)


def telegram_verstuurd(naam: str):
    _schrijf("telegram_verstuurd", naam=naam)


def telegram_fout(fout: str):
    _schrijf("telegram_fout", fout=fout[:200])


def sessie_afgerond(interview_id: str, totaal_beurten: int):
    _schrijf("sessie_afgerond", interview_id=interview_id, beurten=totaal_beurten)
