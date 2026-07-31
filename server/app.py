"""HTTP-server: verbindt de webpagina met de interview-engine."""

import json
import os
import time
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory

from .codes import laad_codes, is_geldige_code
from .telegram_bot import stuur_interview_output
from interview.engine import InterviewSession
from interview import events, paden

CODES_PATH = str(paden.codes_pad())
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Rate limiting: max 30 verzoeken per IP per minuut
_rate_limit = {}
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 30

# Actieve sessies per toegangscode
_sessies = {}


def _rate_check(ip):
    now = time.time()
    if ip not in _rate_limit:
        _rate_limit[ip] = []
    _rate_limit[ip] = [t for t in _rate_limit[ip] if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit[ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_limit[ip].append(now)
    return True


def maak_app():
    app = Flask(__name__)

    provider_key = os.environ.get("API_KEY", "")
    hermes_key = os.environ.get("HERMES_API_KEY", "")
    model = os.environ.get("MODEL", "")
    provider = os.environ.get("PROVIDER", "anthropic")
    api_key = hermes_key if provider == "hermes" else provider_key
    telegram_token = os.environ.get("TELEGRAM_TOKEN", "")
    allowed_origin = os.environ.get("ALLOWED_ORIGIN", "*")

    @app.after_request
    def cors(response):
        response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.route("/", methods=["GET"])
    def pagina():
        """De interviewpagina zelf. Zo is de interface hier op de pc bereikbaar."""
        return send_from_directory(str(paden.webpagina()), "index.html")

    @app.route("/gezond", methods=["GET"])
    def gezond():
        return jsonify({"status": "ok"})

    @app.route("/interview/start", methods=["POST", "OPTIONS"])
    def interview_start():
        if request.method == "OPTIONS":
            return "", 204

        ip = request.remote_addr or "onbekend"
        if not _rate_check(ip):
            return jsonify({"error": "te veel aanvragen, probeer later opnieuw"}), 429

        data = request.get_json(silent=True) or {}
        code = data.get("code", "")

        try:
            codes = laad_codes(CODES_PATH)
        except Exception:
            return jsonify({"error": "toegangscodes konden niet gelezen worden"}), 500

        if not is_geldige_code(code, codes):
            return jsonify({"error": "ongeldige toegangscode"}), 401

        if not api_key or not model:
            return jsonify({"error": "server niet geconfigureerd (API_KEY of MODEL ontbreekt)"}), 500

        sessie = InterviewSession(api_key, model, provider)
        sessie_id = sessie.interview_id
        _sessies[code] = sessie
        events.sessie_gestart(sessie_id, code[:4] + "****")

        # Welkomstbericht als eerste beurt
        welkomst = sessie.transcript[0]
        return jsonify({
            "sessie_id": sessie_id,
            "beurten": [welkomst],
            "tekst": welkomst["tekst"],
        })

    @app.route("/interview/bericht", methods=["POST", "OPTIONS"])
    def interview_bericht():
        if request.method == "OPTIONS":
            return "", 204

        ip = request.remote_addr or "onbekend"
        if not _rate_check(ip):
            return jsonify({"error": "te veel aanvragen, probeer later opnieuw"}), 429

        data = request.get_json(silent=True) or {}
        code = data.get("code", "")
        tekst = data.get("tekst", "").strip()

        if not tekst:
            return jsonify({"error": "tekst ontbreekt"}), 400

        sessie = _sessies.get(code)
        if not sessie:
            return jsonify({"error": "geen actieve sessie — start eerst met /interview/start"}), 404

        beurten = sessie.ondernemer_zegt(tekst)

        # Alleen interviewer-tekst teruggeven voor weergave
        interviewer_tekst = sessie.get_dialoog_tekst(beurten)

        response_data = {
            "beurten": beurten,
            "tekst": interviewer_tekst,
            "afgerond": sessie.afgerond,
        }

        if sessie.afgerond:
            # Stuur output via Telegram
            if telegram_token and TELEGRAM_CHAT_ID:
                try:
                    naam = next((b["naam"] for b in sessie.transcript if b.get("type") == "naamstap"), "onbekend")
                    stuur_interview_output(telegram_token, TELEGRAM_CHAT_ID, sessie.bestanden, naam)
                    events.telegram_verstuurd(naam)
                except Exception as e:
                    events.telegram_fout(str(e))
                    response_data["telegram_fout"] = str(e)

            response_data["bestanden"] = sessie.bestanden
            events.sessie_afgerond(sessie.interview_id, len(sessie.transcript))
            del _sessies[code]

        return jsonify(response_data)

    return app


def main():
    app = maak_app()
    port = int(os.environ.get("PORT", "8787"))
    events.server_gestart(port, os.environ.get("PROVIDER", "?"), os.environ.get("MODEL", "?"))
    print(f"DaKanAI server draait op poort {port}")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
