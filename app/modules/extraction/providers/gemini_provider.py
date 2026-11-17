"""Proveedor Google Gemini por API REST (sin SDK adicional). Mismo contrato y verificación que Claude."""
import httpx

from app.core.config import get_settings
from app.modules.extraction.providers.base import SYSTEM_PROMPT

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider:
    name = "gemini"

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.model = get_settings().gemini_model
        self._transport = transport  # inyectable en pruebas

    def available(self) -> bool:
        return get_settings().gemini_api_key is not None

    def call(self, text: str) -> str:
        s = get_settings()
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": f"<cv>\n{text}\n</cv>"}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0, "maxOutputTokens": 2000},
        }
        with httpx.Client(timeout=s.ai_timeout_seconds, transport=self._transport) as client:
            r = client.post(ENDPOINT.format(model=self.model), json=body,
                            headers={"x-goog-api-key": s.gemini_api_key.get_secret_value()})
            r.raise_for_status()
            data = r.json()
        parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)
