"""Proveedor Claude (Anthropic) con el SDK oficial, como en V5."""
from app.core.config import get_settings
from app.modules.extraction.providers.base import SYSTEM_PROMPT


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        self.model = get_settings().anthropic_model

    def available(self) -> bool:
        return get_settings().anthropic_api_key is not None

    def call(self, text: str) -> str:
        import anthropic

        s = get_settings()
        client = anthropic.Anthropic(api_key=s.anthropic_api_key.get_secret_value(), timeout=s.ai_timeout_seconds,
                                     max_retries=1)
        msg = client.messages.create(model=self.model, max_tokens=2000, system=SYSTEM_PROMPT,
                                     messages=[{"role": "user", "content": f"<cv>\n{text}\n</cv>"}])
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
