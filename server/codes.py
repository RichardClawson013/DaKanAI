"""Toegangscode-validatie — timing-safe vergelijking."""

import hashlib
import hmac
import json
from pathlib import Path


def laad_codes(codes_path):
    inhoud = Path(codes_path).read_text(encoding="utf-8")
    codes = json.loads(inhoud)
    if not isinstance(codes, list):
        raise ValueError(f"{codes_path} moet een JSON-array van toegangscodes bevatten")
    return codes


def is_geldige_code(code, codes):
    if not isinstance(code, str) or len(code) == 0:
        return False

    code_hash = hashlib.sha256(code.encode("utf-8")).digest()
    for bekende_code in codes:
        bekende_hash = hashlib.sha256(bekende_code.encode("utf-8")).digest()
        if hmac.compare_digest(code_hash, bekende_hash):
            return True
    return False
