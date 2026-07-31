#!/usr/bin/env python3
"""DaKanAI Live Monitor — toont in realtime wat de interview-engine doet."""

import json
import time
import os
from datetime import datetime
from pathlib import Path
from collections import deque

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.align import Align
from rich import box

import os

_PROJECT = Path(__file__).resolve().parent
_UITVOER = Path(os.environ.get("DAKAN_UITVOER") or (_PROJECT / "output"))
EVENT_LOG = _UITVOER / "monitor.jsonl"

# Huisstijl kleuren (uit BedrijfspandAI)
GOUD = "#c9a832"
ORANJE = "#b85a2a"
PAARS = "#483f58"
TEKST = "#ece8df"
GEDEMPT = "#a09aad"
DONKER = "#2d2839"

# Iconen per event-type
ICONEN = {
    "server_start":       ("●", "green"),
    "sessie_start":       ("►", GOUD),
    "ondernemer":         ("◇", "cyan"),
    "llm_aanroep":        ("◆", GOUD),
    "llm_antwoord":       ("✓", "green"),
    "llm_fout":           ("✗", "red"),
    "validatie_ok":       ("✓", "green"),
    "validatie_fout":     ("✗", ORANJE),
    "retry":              ("↻", ORANJE),
    "herstel":            ("⚑", "yellow"),
    "naamstap":           ("★", GOUD),
    "status_check":       ("…", GEDEMPT),
    "compilatie_start":   ("⚙", GOUD),
    "compilatie_klaar":   ("✓", "green"),
    "telegram_verstuurd": ("✈", "green"),
    "telegram_fout":      ("✗", "red"),
    "sessie_afgerond":    ("■", GOUD),
}

# Beschrijvingen per event-type
def beschrijf(ev):
    t = ev["type"]
    if t == "server_start":
        return f"Server gestart op poort {ev.get('poort', '?')}  —  {ev.get('provider', '?')} / {ev.get('model', '?')}"
    if t == "sessie_start":
        return f"Nieuw interview gestart  (code: {ev.get('code', '?')})"
    if t == "ondernemer":
        return f"Ondernemer (beurt {ev.get('beurt', '?')}): \"{ev.get('tekst', '')}\""
    if t == "llm_aanroep":
        return f"LLM aanroep  →  {ev.get('provider', '?')} / {ev.get('model', '?')}"
    if t == "llm_antwoord":
        return f"LLM antwoord  ({ev.get('lengte', 0)} tekens, {ev.get('duur', 0)}s)"
    if t == "llm_fout":
        return f"LLM FOUT (poging {ev.get('poging', '?')}): {ev.get('fout', '')}"
    if t == "validatie_ok":
        types = ", ".join(ev.get("types", []))
        return f"Validator OK  ({ev.get('beurten', 0)} beurten: {types})"
    if t == "validatie_fout":
        fouten = "; ".join(ev.get("fouten", []))
        return f"Validator FOUT (poging {ev.get('poging', '?')}): {fouten}"
    if t == "retry":
        return f"Retry poging {ev.get('poging', '?')}  —  {ev.get('reden', '')}"
    if t == "herstel":
        return f"Gracieus herstel: \"{ev.get('tekst', '')}\""
    if t == "naamstap":
        return f"Ondernemer geïdentificeerd: {ev.get('naam', '?')}"
    if t == "status_check":
        return f"Status: {ev.get('status', '?')}"
    if t == "compilatie_start":
        return "Compilatie gestart — transcript → 8 bestanden"
    if t == "compilatie_klaar":
        return f"Compilatie klaar — {ev.get('bestanden', 0)} bestanden → {ev.get('output_dir', '?')}"
    if t == "telegram_verstuurd":
        return f"Telegram verstuurd naar ons team  ({ev.get('naam', '?')})"
    if t == "telegram_fout":
        return f"Telegram FOUT: {ev.get('fout', '')}"
    if t == "sessie_afgerond":
        return f"Interview afgerond  ({ev.get('beurten', 0)} beurten)"
    return json.dumps(ev)


def maak_header():
    logo = Text()
    logo.append("  D a K a n A I  ", style=f"bold {GOUD}")
    logo.append("\n")
    logo.append("  Live Interview Monitor", style=GEDEMPT)
    return Panel(
        Align.center(logo),
        border_style=GOUD,
        box=box.DOUBLE,
        padding=(1, 0),
    )


def maak_status(sessie_info):
    tabel = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
        expand=True,
    )
    tabel.add_column(style=GEDEMPT, width=16)
    tabel.add_column(style=TEKST)
    tabel.add_column(style=GEDEMPT, width=16)
    tabel.add_column(style=TEKST)

    tabel.add_row(
        "Server",
        Text("● Draait", style="green") if sessie_info.get("server") else Text("○ Wacht...", style=GEDEMPT),
        "Provider",
        sessie_info.get("provider", "—"),
    )
    tabel.add_row(
        "Model",
        sessie_info.get("model", "—"),
        "Ondernemer",
        Text(sessie_info.get("naam", "— wacht —"), style=GOUD) if sessie_info.get("naam") else Text("— wacht —", style=GEDEMPT),
    )
    tabel.add_row(
        "Sessie",
        sessie_info.get("sessie_id", "—"),
        "Beurten",
        str(sessie_info.get("beurten", 0)),
    )

    return Panel(
        tabel,
        title=Text(" Status ", style=f"bold {GOUD}"),
        border_style=PAARS,
        box=box.ROUNDED,
    )


def maak_eventlog(events_lijst):
    tabel = Table(
        show_header=False,
        box=None,
        padding=(0, 1),
        expand=True,
    )
    tabel.add_column(style=GEDEMPT, width=10, no_wrap=True)
    tabel.add_column(width=2, no_wrap=True)
    tabel.add_column(ratio=1)

    for ev in events_lijst:
        ts = datetime.fromtimestamp(ev.get("ts", 0)).strftime("%H:%M:%S")
        icoon, kleur = ICONEN.get(ev["type"], ("·", GEDEMPT))
        tekst = beschrijf(ev)

        tabel.add_row(
            ts,
            Text(icoon, style=kleur),
            Text(tekst, style=TEKST if kleur in ("green", GOUD) else kleur),
        )

    if not events_lijst:
        tabel.add_row("", "", Text("Wacht op events...", style=GEDEMPT))

    return Panel(
        tabel,
        title=Text(" Events ", style=f"bold {GOUD}"),
        border_style=PAARS,
        box=box.ROUNDED,
    )


def main():
    console = Console()
    console.clear()

    events_buffer = deque(maxlen=50)
    sessie_info = {
        "server": False,
        "provider": "—",
        "model": "—",
        "naam": None,
        "sessie_id": "—",
        "beurten": 0,
    }

    # Lees bestaande events als het bestand al bestaat
    gelezen_pos = 0
    if EVENT_LOG.exists():
        with open(EVENT_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    events_buffer.append(ev)
                    _update_sessie_info(sessie_info, ev)
                except json.JSONDecodeError:
                    pass
            gelezen_pos = f.tell()

    def render():
        layout = Layout()
        layout.split_column(
            Layout(maak_header(), size=6),
            Layout(maak_status(sessie_info), size=7),
            Layout(maak_eventlog(list(events_buffer))),
        )
        return layout

    with Live(render(), console=console, refresh_per_second=2, screen=True) as live:
        while True:
            nieuw = False

            if EVENT_LOG.exists():
                with open(EVENT_LOG, "r", encoding="utf-8") as f:
                    f.seek(gelezen_pos)
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            ev = json.loads(line)
                            events_buffer.append(ev)
                            _update_sessie_info(sessie_info, ev)
                            nieuw = True
                        except json.JSONDecodeError:
                            pass
                    gelezen_pos = f.tell()

            if nieuw:
                live.update(render())

            time.sleep(0.5)


def _update_sessie_info(info, ev):
    t = ev["type"]
    if t == "server_start":
        info["server"] = True
        info["provider"] = ev.get("provider", "—")
        info["model"] = ev.get("model", "—")
    elif t == "sessie_start":
        info["sessie_id"] = ev.get("interview_id", "—")
        info["naam"] = None
        info["beurten"] = 1
    elif t == "naamstap":
        info["naam"] = ev.get("naam", "?")
    elif t == "ondernemer":
        info["beurten"] = ev.get("beurt", info["beurten"])
    elif t == "sessie_afgerond":
        info["beurten"] = ev.get("beurten", info["beurten"])


if __name__ == "__main__":
    main()
