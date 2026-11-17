"""Utilidades de normalización de skills y redacción de PII."""
import re
import unicodedata

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
_DOC_ID = re.compile(r"\b(?:c\.?c\.?|cédula|cedula|nit|pasaporte)\s*[:#]?\s*[\d.\-]{5,}\b", re.I)


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9+#./ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def split_skills(raw: str | None) -> list[str]:
    """Divide por comas ignorando las que están entre paréntesis: 'Programming (Python, C++)'."""
    if not raw or not isinstance(raw, str):
        return []
    out, depth, buf = [], 0, ""
    for ch in raw:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch in ",;\n" and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    out.append(buf)
    seen, result = set(), []
    for item in out:
        item = item.strip(" .-•\t")
        if 1 < len(item) <= 80 and normalize(item) not in seen:
            seen.add(normalize(item))
            result.append(item)
    return result


def redact_pii(text: str) -> str:
    """Minimización (Ley 1581): se eliminan identificadores antes de enviar texto a terceros."""
    text = _EMAIL.sub("[EMAIL]", text)
    text = _DOC_ID.sub("[DOCUMENTO]", text)
    return _PHONE.sub("[TELEFONO]", text)


# ---------------------------------------------------------------------------
# Utilidades de Iteración 4 (normalización ES/EN usada por la extracción y el matching)
# ---------------------------------------------------------------------------
_WS = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    if text.isascii():
        return text
    t = text.replace("’", "'").replace("–", "-").replace("—", "-").replace("�", "'")
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")


def norm(text: str) -> str:
    """Minúsculas, sin tildes, espacios colapsados y puntuación de borde removida."""
    if not text:
        return ""
    t = strip_accents(str(text)).lower()
    t = t.replace("’", "'").replace("–", "-").replace("—", "-")
    t = re.sub(r"[\*#•·▪►●]+", " ", t)
    t = _WS.sub(" ", t).strip(" .,:;-_/|()[]{}\"'")
    return t


def clean_display(text: str) -> str:
    return _WS.sub(" ", str(text or "")).strip(" .,:;-_*#")


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9\+\#\.]+", norm(text))


def fix_mojibake(text: str) -> str:
    """Repara caracteres de reemplazo comunes de los CSV (p. ej. 'you�ll')."""
    if not isinstance(text, str):
        return ""
    return text.replace("�", "'")
