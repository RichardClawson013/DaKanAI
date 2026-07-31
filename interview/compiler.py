"""Compiler: transcript -> 8 bestanden — port van BedrijfspandAI compiler/"""

import json
from html import escape as html_escape


def _canonical_json(value):
    def sort_deep(v):
        if isinstance(v, list):
            return [sort_deep(x) for x in v]
        if isinstance(v, dict):
            return {k: sort_deep(v[k]) for k in sorted(v)}
        return v
    return json.dumps(sort_deep(value), indent=2, ensure_ascii=False) + "\n"


def parse_transcript(transcript):
    if not isinstance(transcript, list) or len(transcript) == 0:
        raise ValueError("transcript moet een niet-lege array zijn")

    naamstap = next((b for b in transcript if b.get("type") == "naamstap"), None)
    if not naamstap:
        raise ValueError('transcript moet een beurt met type "naamstap" bevatten')

    parsed = {
        "naam": naamstap["naam"],
        "taken": [],
        "edges": [],
        "ziel_principes": [],
        "skills": [],
        "tools": [],
    }

    for beurt in transcript:
        t = beurt.get("type")
        if t in ("naamstap", "dialoog", "afronding"):
            continue
        elif t == "taak":
            parsed["taken"].append(beurt["data"])
        elif t == "edge":
            parsed["edges"].append(beurt["data"])
        elif t == "ziel_principe":
            parsed["ziel_principes"].append(beurt["data"])
        elif t == "skill":
            parsed["skills"].append(beurt["data"])
        elif t == "tool":
            parsed["tools"].append(beurt["data"])
        else:
            raise ValueError(f"onbekend beurttype: {t}")

    return parsed


def _dekkingsregel(data):
    st = data.get("source_turns", [])
    meervoud = "en" if len(st) > 1 else ""
    return f"**Dekking:** {data['dekking']} — beurt{meervoud} {', '.join(str(n) for n in st)}"


def build_manifest(parsed, meta):
    return {
        "schema_version": "1.0",
        "generated": meta["generated"],
        "werknemer": {"naam": parsed["naam"]},
        "interview": {
            "id": meta["interview_id"],
            "turns_total": meta["turns_total"],
            "provider": meta["provider"],
            "model": meta["model"],
        },
        "tasks": parsed["taken"],
        "edges": parsed["edges"],
    }


def build_ziel(parsed):
    naam = parsed["naam"]
    regels = [f"# Ziel van {naam}", ""]
    principes = parsed["ziel_principes"]
    if not principes:
        regels += ["_Geen principes vastgelegd in dit interview._", ""]
    for i, p in enumerate(principes):
        regels += [f"## {p.get('titel', f'Principe {i+1}')}", ""]
        regels += [p["tekst"], ""]
        if p.get("reden"):
            regels += [f"**Reden:** {p['reden']}", ""]
        regels += [_dekkingsregel(p), ""]
    return "\n".join(regels).rstrip() + "\n"


def build_agents(parsed):
    naam = parsed["naam"]
    taken = parsed["taken"]
    labels = [("autonoom", "Doet zelfstandig"), ("eerst-vragen", "Vraagt eerst"), ("nooit", "Raakt nooit aan")]
    regels = [f"# Operationeel profiel — {naam}", ""]

    for niveau, label in labels:
        op_niveau = [t for t in taken if t.get("autonomie") == niveau]
        regels += [f"## {label}", ""]
        if not op_niveau:
            regels += ["_Geen taken op dit niveau._", ""]
        else:
            for t in op_niveau:
                regels.append(f"- **{t['naam']}** ({t['dekking']}, beurt {', '.join(str(n) for n in t['source_turns'])})")
            regels.append("")

    onbepaald = [t for t in taken if not t.get("autonomie")]
    if onbepaald:
        regels += ["## Nog niet bepaald", ""]
        for t in onbepaald:
            regels.append(f"- **{t['naam']}** — autonomieniveau nog niet vastgesteld")
        regels.append("")

    regels += ["## Escalatieregels", ""]
    met_escalatie = [t for t in taken if t.get("escalatie")]
    if not met_escalatie:
        regels += ["_Geen escalatieregels vastgelegd._", ""]
    else:
        for t in met_escalatie:
            for r in t["escalatie"]:
                regels.append(f"- **{t['naam']}** — als {r['als']}, dan {r['dan']}")
        regels.append("")

    return "\n".join(regels).rstrip() + "\n"


def build_skills(parsed):
    naam = parsed["naam"]
    skills = parsed["skills"]
    regels = [f"# Vaardigheden — {naam}", ""]
    if not skills:
        regels += ["_Geen vaardigheden vastgelegd in dit interview._", ""]
        return "\n".join(regels).rstrip() + "\n"

    per_domein = {}
    for s in skills:
        domein = s.get("domein", "Algemeen")
        per_domein.setdefault(domein, []).append(s)

    for domein in sorted(per_domein):
        regels += [f"## {domein}", ""]
        for s in per_domein[domein]:
            regels.append(f"- **{s['naam']}** ({s['dekking']}, beurt {', '.join(str(n) for n in s['source_turns'])})")
        regels.append("")

    return "\n".join(regels).rstrip() + "\n"


def build_tools(parsed):
    naam = parsed["naam"]
    tools = parsed["tools"]
    regels = [f"# Gereedschap — {naam}", ""]

    def tool_regel(t):
        voor_taak = f" (voor {t['taak_id']})" if t.get("taak_id") else ""
        redenering = f": {t['redenering']}" if t.get("redenering") else ""
        return f"- **{t['naam']}**{voor_taak} — {t['dekking']}{redenering}, beurt {', '.join(str(n) for n in t['source_turns'])}"

    huidig = [t for t in tools if t.get("soort") == "huidig"]
    suggesties = [t for t in tools if t.get("soort") == "suggestie"]

    regels += ["## Huidig gebruikt", ""]
    if not huidig:
        regels += ["_Geen huidig gereedschap vastgelegd._", ""]
    else:
        regels += [tool_regel(t) for t in huidig] + [""]

    regels += ["## AI-toolsuggesties", ""]
    if not suggesties:
        regels += ["_Geen suggesties._", ""]
    else:
        regels += [tool_regel(t) for t in suggesties] + [""]

    return "\n".join(regels).rstrip() + "\n"


def build_rapport(parsed):
    naam = parsed["naam"]
    taken = parsed["taken"]
    principes = parsed["ziel_principes"]
    ne = html_escape(naam)
    slug = html_escape(naam.lower())

    def principe_item(p):
        titel = html_escape(p.get("titel", "Principe"))
        tekst = html_escape(p["tekst"])
        dekking = html_escape(p["dekking"])
        beurten = ", ".join(str(n) for n in p["source_turns"])
        return f'        <li><strong>{titel}:</strong> {tekst} <em>({dekking}, beurt {beurten})</em></li>'

    def taak_item(t):
        tn = html_escape(t["naam"])
        fg = f' — <em>faalgevolg: {html_escape(t["faalgevolg"])}</em>' if t.get("faalgevolg") else ""
        return f"          <li>{tn}{fg}</li>"

    principes_html = "\n".join(principe_item(p) for p in principes) if principes else "        <li><em>Geen principes vastgelegd.</em></li>"

    labels = [("autonoom", "Doet zelfstandig"), ("eerst-vragen", "Vraagt eerst"), ("nooit", "Raakt nooit aan")]
    taak_secties = []
    for niveau, label in labels:
        items = [t for t in taken if t.get("autonomie") == niveau]
        lijst = "\n".join(taak_item(t) for t in items) if items else "          <li><em>Geen taken op dit niveau.</em></li>"
        taak_secties.append(f"""    <section>
      <h2>{html_escape(label)}</h2>
      <ul>
{lijst}
      </ul>
    </section>""")

    return f"""<!doctype html>
<html lang="nl">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Maak kennis met {ne}</title>
    <style>
      :root {{
        --color-bg: oklch(11% 0.03 300);
        --color-surface: oklch(20% 0.032 300);
        --color-border: oklch(32% 0.03 300);
        --color-text: oklch(92% 0.015 90);
        --color-text-muted: oklch(68% 0.02 290);
        --color-gold: oklch(80% 0.13 86);
        --color-orange: oklch(58% 0.16 42);
        --font-serif: "Iowan Old Style", "Palatino Linotype", "URW Palladio", Palatino, P052, ui-serif, Georgia, serif;
        --font-sans: ui-sans-serif, "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background: var(--color-bg);
        color: var(--color-text);
        font-family: var(--font-sans);
        line-height: 1.6;
      }}
      main {{ max-width: 42rem; margin: 0 auto; padding: 3rem 1.5rem 4rem; }}
      h1, h2 {{ font-family: var(--font-serif); font-weight: 600; line-height: 1.2; margin: 0 0 1rem; }}
      h1 {{ font-size: clamp(1.8rem, 1.4rem + 1.6vw, 2.5rem); color: var(--color-gold); }}
      h2 {{ font-size: 1.25rem; }}
      section {{
        background: var(--color-surface);
        border: 1px solid var(--color-border);
        border-radius: 14px;
        padding: 1.5rem;
        margin-bottom: 1rem;
      }}
      ul {{ margin: 0; padding-left: 1.2rem; }}
      li {{ margin-bottom: 0.5rem; }}
      em {{ color: var(--color-text-muted); font-style: normal; }}
      footer {{ color: var(--color-text-muted); font-size: 0.85rem; margin-top: 2rem; }}
    </style>
  </head>
  <body>
    <main>
      <h1>Maak kennis met {ne}.</h1>
      <section>
        <h2>Wie {ne} is</h2>
        <ul>
{principes_html}
        </ul>
      </section>
{chr(10).join(taak_secties)}
      <footer>
        <p>Leeswijzer: zie ook ziel_{slug}.md, agents_{slug}.md, skills_{slug}.md, tools_{slug}.md en wereldmodel_{slug}.json.</p>
      </footer>
    </main>
  </body>
</html>
"""


def build_open_onderwerpen(parsed):
    naam = parsed["naam"]
    taken = parsed["taken"]
    edges = parsed["edges"]
    open_taken = [t for t in taken if t.get("dekking") == "GEEN-DEKKING"]
    open_edges = [e for e in edges if e.get("dekking") == "GEEN-DEKKING"]

    regels = [f"# Open onderwerpen — trainingsagenda voor {naam}", ""]

    if not open_taken and not open_edges:
        regels.append("_Geen open onderwerpen. Alles is GEDEKT of AFGELEID vastgelegd._")
        return "\n".join(regels).rstrip() + "\n"

    regels += [
        f"Dit zijn de onderwerpen die tijdens het interview bewust open zijn gelaten "
        f"(GEEN-DEKKING) — de trainingsagenda voor {naam} zodra deze operationeel is.",
        "",
    ]

    def vind_afhankelijkheden(taak_id):
        verbonden = set()
        for e in edges:
            if e.get("van") == taak_id:
                verbonden.add(e["naar"])
            if e.get("naar") == taak_id:
                verbonden.add(e["van"])
        for t in taken:
            if taak_id in (t.get("afhankelijk_van") or []):
                verbonden.add(t["id"])
        if not verbonden:
            return "niets bekends — geen andere taak of edge verwijst hiernaar."
        return ", ".join(sorted(verbonden))

    if open_taken:
        regels += ["## Open taken", ""]
        for t in open_taken:
            regels += [
                f"### {t['naam']}", "",
                f"- **Waar:** beurt {', '.join(str(n) for n in t['source_turns'])}",
                "- **Waarom open:** bewust open gelaten tijdens het interview — geen bronverwijzing of afgeleide redenering vastgelegd.",
                f"- **Wat hangt hiervan af:** {vind_afhankelijkheden(t['id'])}",
                "",
            ]

    if open_edges:
        regels += ["## Open afhankelijkheden", ""]
        for e in open_edges:
            regels += [
                f"### {e['van']} → {e['naar']}", "",
                f"- **Waar:** beurt {', '.join(str(n) for n in e['source_turns'])}",
                "- **Waarom open:** bewust open gelaten tijdens het interview — geen bronverwijzing of afgeleide redenering vastgelegd.",
                "",
            ]

    return "\n".join(regels).rstrip() + "\n"


def compile_transcript(transcript, meta):
    parsed = parse_transcript(transcript)
    naam_slug = parsed["naam"].lower()

    manifest = build_manifest(parsed, meta)

    return {
        f"wereldmodel_{naam_slug}.json": _canonical_json(manifest),
        f"ziel_{naam_slug}.md": build_ziel(parsed),
        f"agents_{naam_slug}.md": build_agents(parsed),
        f"skills_{naam_slug}.md": build_skills(parsed),
        f"tools_{naam_slug}.md": build_tools(parsed),
        f"rapport_{naam_slug}.html": build_rapport(parsed),
        f"open_onderwerpen_trainingbot_{naam_slug}.md": build_open_onderwerpen(parsed),
        "transcript.json": _canonical_json(transcript),
    }
