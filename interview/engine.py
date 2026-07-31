"""Interview-engine: het brein. Stuurt het gesprek, valideert, herstelt, compileert."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import paden
from .system_prompt import INTERVIEW_SYSTEEM_PROMPT, WELKOMSBERICHT
from .validator import parse_model_response
from .interview_status import bepaal_vraag_status, WAARSCHUWINGSTEKST, AFSLUITTEKST
from .compiler import compile_transcript
from . import events

MAX_RETRIES = 3


def _call_llm(messages, api_key, model, provider="anthropic"):
    """Stuur berichten naar het LLM. Provider-agnostisch."""
    if provider == "anthropic":
        return _call_anthropic(messages, api_key, model)
    elif provider == "google":
        return _call_google(messages, api_key, model)
    elif provider == "openrouter":
        return _call_openrouter(messages, api_key, model)
    elif provider == "hermes":
        return _call_hermes(messages, api_key, model)
    else:
        raise ValueError(f"onbekende provider: {provider}")


def _call_anthropic(messages, api_key, model):
    system_msg = None
    chat_messages = []
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
        else:
            chat_messages.append(m)

    body = {"model": model, "max_tokens": 8192, "messages": chat_messages}
    if system_msg:
        body["system"] = system_msg

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=body,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"]


def _call_google(messages, api_key, model):
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    contents = []
    for m in messages:
        if m["role"] == "system":
            continue
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    body = {"contents": contents}
    if system_parts:
        body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    resp = requests.post(url, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_openrouter(messages, api_key, model):
    body = {"model": model, "messages": messages, "max_tokens": 8192}
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_hermes(messages, api_key, model):
    """Praat met Hermes, de agent die hier op de pc draait.

    Hermes voert het gesprek en praat zelf verder met OpenRouter. Hij spreekt
    hetzelfde formaat als OpenRouter, alleen op een ander adres. Het gesprek
    zelf houden wij bij: het transcript is het product, dat hoort niet in het
    geheugen van een ander programma te leven.
    """
    url = os.environ.get("HERMES_URL", "http://127.0.0.1:8642") + "/v1/chat/completions"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"model": model, "messages": messages},
        timeout=600,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


class InterviewSession:
    """Eén interview-sessie met één ondernemer."""

    def __init__(self, api_key, model, provider="anthropic"):
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.transcript = []
        self.wisselingen = []  # LLM-gespreksgeschiedenis
        self.afgerond = False
        self.interview_id = f"interview-{int(time.time())}"

        # Start met welkomsbericht (vast, beurt 1)
        welkomst = {"turn": 1, "type": "dialoog", "spreker": "interviewer", "tekst": WELKOMSBERICHT}
        self.transcript.append(welkomst)
        self.wisselingen.append({"role": "system", "content": INTERVIEW_SYSTEEM_PROMPT})
        self.wisselingen.append({"role": "assistant", "content": json.dumps([welkomst], ensure_ascii=False)})

    def ondernemer_zegt(self, tekst):
        """Verwerk een bericht van de ondernemer. Geeft de modelrespons terug als lijst beurten."""
        beurt = {
            "turn": len(self.transcript) + 1,
            "type": "dialoog",
            "spreker": "ondernemer",
            "tekst": tekst,
        }
        self.transcript.append(beurt)
        self.wisselingen.append({"role": "user", "content": tekst})
        events.ondernemer_bericht(tekst, beurt["turn"])

        return self._vraag_model()

    def _vraag_model(self):
        """Vraag het model om de volgende beurt(en). Valideert en herstelt."""
        status = bepaal_vraag_status(self.transcript)
        events.status_check(status)

        if status == "noodrem":
            afsluit_beurt = {"turn": len(self.transcript) + 1, "type": "afronding"}
            self.transcript.append(afsluit_beurt)
            self.afgerond = True
            return [afsluit_beurt]

        extra_context = ""
        if status == "waarschuwing":
            extra_context = f"\n\n[SYSTEEM: {WAARSCHUWINGSTEKST}]"
        elif status == "destilleren":
            extra_context = "\n\n[SYSTEEM: destilleer nu je beste lezing en leg die voor aan de ondernemer.]"
        elif status == "afsluiten":
            extra_context = f"\n\n[SYSTEEM: {AFSLUITTEKST}]"

        messages = list(self.wisselingen)
        if extra_context:
            messages.append({"role": "user", "content": extra_context})

        for poging in range(MAX_RETRIES):
            events.llm_aanroep(self.provider, self.model)
            t0 = time.time()
            try:
                raw = _call_llm(messages, self.api_key, self.model, self.provider)
                events.llm_antwoord(time.time() - t0, len(raw))
            except Exception as e:
                events.llm_fout(str(e), poging + 1)
                if poging < MAX_RETRIES - 1:
                    continue
                # Na max retries: gracieus herstellen
                herstel = {
                    "turn": len(self.transcript) + 1,
                    "type": "dialoog",
                    "spreker": "interviewer",
                    "tekst": "Sorry, er ging even iets mis aan mijn kant. Kun je dat laatste nog een keer herhalen?",
                }
                self.transcript.append(herstel)
                self.wisselingen.append({"role": "assistant", "content": json.dumps([herstel], ensure_ascii=False)})
                events.herstel(herstel["tekst"])
                return [herstel]

            # Strip markdown code blocks als het model ze toevoegt
            cleaned = raw.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            result = parse_model_response(cleaned)

            if result["valid"]:
                beurten = result["turns"]
                types = [b.get("type", "?") for b in beurten]
                events.validatie_ok(len(beurten), types)

                for b in beurten:
                    self.transcript.append(b)
                    if b.get("type") == "naamstap":
                        events.naamstap(b.get("naam", "?"))
                self.wisselingen.append({"role": "assistant", "content": cleaned})

                if any(b.get("type") == "afronding" for b in beurten):
                    self.afgerond = True
                    self._compileer()

                return beurten

            # Ongeldig — foutmelding naar het model voor retry
            fout_tekst = "; ".join(e["message"] for e in result["errors"][:5])
            fouten_kort = [e["message"] for e in result["errors"][:5]]
            events.validatie_fout(fouten_kort, poging + 1)
            events.retry(poging + 1, fout_tekst[:120])
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"[SYSTEEM: je vorige antwoord bevatte fouten: {fout_tekst}. "
                           f"Corrigeer en geef het opnieuw als geldige JSON-array van beurten.]",
            })

        # Alle pogingen mislukt — gracieus herstellen
        herstel = {
            "turn": len(self.transcript) + 1,
            "type": "dialoog",
            "spreker": "interviewer",
            "tekst": "Even een momentje — ik moet mijn gedachten ordenen. Kun je dat laatste nog een keer vertellen?",
        }
        self.transcript.append(herstel)
        self.wisselingen.append({"role": "assistant", "content": json.dumps([herstel], ensure_ascii=False)})
        events.herstel(herstel["tekst"])
        return [herstel]

    def _compileer(self):
        """Compileer het transcript naar 8 bestanden."""
        events.compilatie_start()
        meta = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "interview_id": self.interview_id,
            "provider": self.provider,
            "model": self.model,
            "turns_total": len(self.transcript),
        }

        bestanden = compile_transcript(self.transcript, meta)

        # Opslaan op schijf
        naam = next((b["naam"] for b in self.transcript if b.get("type") == "naamstap"), "onbekend")
        output_dir = paden.uitvoermap() / naam.lower()
        output_dir.mkdir(parents=True, exist_ok=True)

        for bestandsnaam, inhoud in bestanden.items():
            (output_dir / bestandsnaam).write_text(inhoud, encoding="utf-8")

        self.output_dir = output_dir
        self.bestanden = bestanden
        events.compilatie_klaar(len(bestanden), str(output_dir))
        return bestanden

    def get_dialoog_tekst(self, beurten):
        """Haal alleen de interviewer-tekst uit beurten voor weergave."""
        teksten = []
        for b in beurten:
            if b.get("type") == "dialoog" and b.get("spreker") == "interviewer":
                teksten.append(b["tekst"])
        return "\n\n".join(teksten)
