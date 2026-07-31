"""Telegram-bot: stuurt output naar ons team na afronding interview."""

import json
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}"


def stuur_bericht(token, chat_id, tekst, parse_mode="HTML"):
    url = f"{TELEGRAM_API.format(token=token)}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": tekst,
        "parse_mode": parse_mode,
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()


def stuur_document(token, chat_id, bestandsnaam, inhoud, caption=""):
    url = f"{TELEGRAM_API.format(token=token)}/sendDocument"
    files = {"document": (bestandsnaam, inhoud.encode("utf-8"), "application/octet-stream")}
    data = {"chat_id": chat_id, "caption": caption}
    resp = requests.post(url, data=data, files=files, timeout=30)
    resp.raise_for_status()
    return resp.json()


def stuur_interview_output(token, chat_id, bestanden, naam):
    """Stuur alle 8 bestanden naar ons team via Telegram."""
    stuur_bericht(token, chat_id, f"<b>Interview afgerond: {naam}</b>\n\n8 bestanden volgen hieronder.")

    for bestandsnaam, inhoud in bestanden.items():
        stuur_document(token, chat_id, bestandsnaam, inhoud)

    stuur_bericht(token, chat_id, f"Alle {len(bestanden)} bestanden verzonden voor <b>{naam}</b>.")


def get_bot_info(token):
    url = f"{TELEGRAM_API.format(token=token)}/getMe"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()
