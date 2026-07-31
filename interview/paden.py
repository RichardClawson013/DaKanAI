"""Eén plek die bepaalt waar DaKanAI zijn spullen vindt en neerzet.

Alle paden worden afgeleid van waar dit bestand staat. Daardoor kan er nergens
in de code een thuismap van een specifieke gebruiker terechtkomen: verplaats je
het project, dan verhuist alles mee.

Wie de uitvoer ergens anders wil hebben, zet `DAKAN_UITVOER`.
"""

import os
from pathlib import Path

# interview/paden.py -> interview/ -> de projectmap
PROJECT = Path(__file__).resolve().parent.parent


def uitvoermap():
    """De map waar interviews hun bestanden neerzetten."""
    eigen = os.environ.get("DAKAN_UITVOER")
    return Path(eigen) if eigen else PROJECT / "output"


def eventlog():
    """Het bestand waar de monitor uit meeleest."""
    return uitvoermap() / "monitor.jsonl"


def codes_pad():
    """Het bestand met de toegangscodes."""
    eigen = os.environ.get("CODES_PATH")
    return Path(eigen) if eigen else PROJECT / "codes.json"


def webpagina():
    """De map met de interviewpagina."""
    return PROJECT
