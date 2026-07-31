"""Deterministische beurt-validatie — port van BedrijfspandAI validateModelTurn.js"""

import json

BEURTTYPEN = {"naamstap", "dialoog", "taak", "edge", "ziel_principe", "skill", "tool", "afronding"}
DEKKINGSLABELS = {"GEDEKT", "AFGELEID", "GEEN-DEKKING"}
SPREKERS = {"interviewer", "ondernemer"}
AUTONOMIENIVEAUS = {"autonoom", "eerst-vragen", "nooit"}
TOOLSOORTEN = {"huidig", "suggestie"}

NAAMSTAP_VELDEN = {"turn", "type", "naam"}
DIALOOG_VELDEN = {"turn", "type", "spreker", "tekst"}
AFRONDING_VELDEN = {"turn", "type"}
DATA_BEURT_VELDEN = {"turn", "type", "data"}

TAAK_DATA_VELDEN = {
    "id", "naam", "beschrijving", "trigger", "afhankelijk_van",
    "autonomie", "escalatie", "faalgevolg", "dekking", "source_turns",
}
EDGE_DATA_VELDEN = {"van", "naar", "soort", "dekking", "source_turns"}
ZIEL_PRINCIPE_DATA_VELDEN = {"titel", "tekst", "reden", "dekking", "source_turns"}
SKILL_DATA_VELDEN = {"naam", "domein", "dekking", "source_turns"}
TOOL_DATA_VELDEN = {"naam", "taak_id", "soort", "redenering", "dekking", "source_turns"}


def _onbekende_velden(obj, toegestaan, errors, context):
    onbekend = [k for k in obj if k not in toegestaan]
    if onbekend:
        errors.append({"category": "onbekend-veld", "message": f"{context}: onbekend veld/velden {', '.join(onbekend)}"})


def _niet_lege_string(waarde):
    return isinstance(waarde, str) and len(waarde) > 0


def _valideer_source_turns(data, errors, context):
    st = data.get("source_turns")
    if not isinstance(st, list) or len(st) == 0:
        errors.append({"category": "ongeldige-source-turns", "message": f"{context}: source_turns ontbreekt of is leeg"})
        return
    if not all(isinstance(n, int) and n >= 1 for n in st):
        errors.append({"category": "ongeldige-source-turns", "message": f"{context}: source_turns moet positieve gehele beurtnummers bevatten"})


def _valideer_dekking(data, errors, context):
    if data.get("dekking") not in DEKKINGSLABELS:
        errors.append({"category": "ongeldig-label", "message": f"{context}: dekking \"{data.get('dekking')}\" is geen geldig label"})


def _valideer_data(beurt, errors, context):
    data = beurt.get("data")
    if not isinstance(data, dict):
        errors.append({"category": "ontbrekend-veld", "message": f"{context}: data ontbreekt"})
        return None
    return data


def _valideer_naamstap(beurt, errors):
    context = f"naamstap beurt {beurt.get('turn')}"
    _onbekende_velden(beurt, NAAMSTAP_VELDEN, errors, context)
    if not _niet_lege_string(beurt.get("naam")):
        errors.append({"category": "ontbrekend-veld", "message": "naamstap: naam ontbreekt of is leeg"})


def _valideer_afronding(beurt, errors):
    _onbekende_velden(beurt, AFRONDING_VELDEN, errors, f"afronding beurt {beurt.get('turn')}")


def _valideer_dialoog(beurt, errors):
    context = f"dialoog beurt {beurt.get('turn')}"
    _onbekende_velden(beurt, DIALOOG_VELDEN, errors, context)
    if beurt.get("spreker") not in SPREKERS:
        errors.append({"category": "ontbrekend-veld", "message": f"{context}: spreker moet \"interviewer\" of \"ondernemer\" zijn"})
    if not _niet_lege_string(beurt.get("tekst")):
        errors.append({"category": "ontbrekend-veld", "message": f"{context}: tekst ontbreekt of is leeg"})


def _valideer_taak(beurt, errors):
    context = f"taak beurt {beurt.get('turn')}"
    _onbekende_velden(beurt, DATA_BEURT_VELDEN, errors, context)
    data = _valideer_data(beurt, errors, context)
    if not data:
        return
    _onbekende_velden(data, TAAK_DATA_VELDEN, errors, context)
    if not _niet_lege_string(data.get("id")):
        errors.append({"category": "ontbrekend-veld", "message": f"{context}: data.id ontbreekt"})
    if not _niet_lege_string(data.get("naam")):
        errors.append({"category": "ontbrekend-veld", "message": f"{context}: data.naam ontbreekt"})
    if data.get("autonomie") is not None and data["autonomie"] not in AUTONOMIENIVEAUS:
        errors.append({"category": "ongeldig-label", "message": f"{context}: autonomie \"{data['autonomie']}\" is geen geldig niveau"})
    _valideer_dekking(data, errors, context)
    _valideer_source_turns(data, errors, context)


def _valideer_edge(beurt, errors):
    context = f"edge beurt {beurt.get('turn')}"
    _onbekende_velden(beurt, DATA_BEURT_VELDEN, errors, context)
    data = _valideer_data(beurt, errors, context)
    if not data:
        return
    _onbekende_velden(data, EDGE_DATA_VELDEN, errors, context)
    if not _niet_lege_string(data.get("van")):
        errors.append({"category": "ontbrekend-veld", "message": f"{context}: data.van ontbreekt"})
    if not _niet_lege_string(data.get("naar")):
        errors.append({"category": "ontbrekend-veld", "message": f"{context}: data.naar ontbreekt"})
    _valideer_dekking(data, errors, context)
    _valideer_source_turns(data, errors, context)


def _valideer_ziel_principe(beurt, errors):
    context = f"ziel_principe beurt {beurt.get('turn')}"
    _onbekende_velden(beurt, DATA_BEURT_VELDEN, errors, context)
    data = _valideer_data(beurt, errors, context)
    if not data:
        return
    _onbekende_velden(data, ZIEL_PRINCIPE_DATA_VELDEN, errors, context)
    if not _niet_lege_string(data.get("tekst")):
        errors.append({"category": "ontbrekend-veld", "message": f"{context}: data.tekst ontbreekt"})
    _valideer_dekking(data, errors, context)
    _valideer_source_turns(data, errors, context)


def _valideer_skill(beurt, errors):
    context = f"skill beurt {beurt.get('turn')}"
    _onbekende_velden(beurt, DATA_BEURT_VELDEN, errors, context)
    data = _valideer_data(beurt, errors, context)
    if not data:
        return
    _onbekende_velden(data, SKILL_DATA_VELDEN, errors, context)
    if not _niet_lege_string(data.get("naam")):
        errors.append({"category": "ontbrekend-veld", "message": f"{context}: data.naam ontbreekt"})
    _valideer_dekking(data, errors, context)
    _valideer_source_turns(data, errors, context)


def _valideer_tool(beurt, errors):
    context = f"tool beurt {beurt.get('turn')}"
    _onbekende_velden(beurt, DATA_BEURT_VELDEN, errors, context)
    data = _valideer_data(beurt, errors, context)
    if not data:
        return
    _onbekende_velden(data, TOOL_DATA_VELDEN, errors, context)
    if not _niet_lege_string(data.get("naam")):
        errors.append({"category": "ontbrekend-veld", "message": f"{context}: data.naam ontbreekt"})
    if data.get("soort") not in TOOLSOORTEN:
        errors.append({"category": "ontbrekend-veld", "message": f"{context}: soort moet \"huidig\" of \"suggestie\" zijn"})
    _valideer_dekking(data, errors, context)
    _valideer_source_turns(data, errors, context)


_VALIDATORS = {
    "naamstap": _valideer_naamstap,
    "dialoog": _valideer_dialoog,
    "taak": _valideer_taak,
    "edge": _valideer_edge,
    "ziel_principe": _valideer_ziel_principe,
    "skill": _valideer_skill,
    "tool": _valideer_tool,
    "afronding": _valideer_afronding,
}


def parse_model_response(raw):
    """Valideert een ruw modelantwoord (string) tegen het beurt-protocol.
    Geeft {"valid": bool, "errors": list, "turns": list|None} terug."""
    try:
        beurten = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [{"category": "ongeldige-json", "message": f"antwoord is geen geldige JSON: {e}"}]}

    if not isinstance(beurten, list) or len(beurten) == 0:
        return {"valid": False, "errors": [{"category": "geen-beurten", "message": "antwoord moet een niet-lege array van beurten zijn"}]}

    errors = []
    for beurt in beurten:
        if not isinstance(beurt, dict):
            errors.append({"category": "ongeldige-beurt", "message": "beurt is geen object"})
            continue
        turn = beurt.get("turn")
        if not isinstance(turn, int) or turn < 1:
            errors.append({"category": "ongeldig-beurtnummer", "message": f"beurtnummer \"{turn}\" is geen positief geheel getal"})
        beurt_type = beurt.get("type")
        if beurt_type not in BEURTTYPEN:
            errors.append({"category": "onbekend-beurttype", "message": f"beurttype \"{beurt_type}\" is onbekend"})
            continue
        _VALIDATORS[beurt_type](beurt, errors)

    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True, "errors": [], "turns": beurten}
