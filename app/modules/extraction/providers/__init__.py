"""Registro de proveedores. Para añadir uno nuevo basta implementar `available()` y `call()`."""
from app.core.config import get_settings
from app.modules.extraction.providers.anthropic_provider import AnthropicProvider
from app.modules.extraction.providers.gemini_provider import GeminiProvider

REGISTRY = {"anthropic": AnthropicProvider, "gemini": GeminiProvider}


def configured() -> list[str]:
    return [name for name, cls in REGISTRY.items() if cls().available()]


def select_provider(preferred: str = "auto"):
    """Devuelve el proveedor externo a usar o None (modo local)."""
    env_choice = get_settings().ai_provider
    if env_choice == "local":
        return None
    order = []
    for choice in (env_choice, preferred):
        if choice in REGISTRY and choice not in order:
            order.append(choice)
    order += [n for n in REGISTRY if n not in order]
    for name in order:
        p = REGISTRY[name]()
        if p.available():
            return p
    return None
