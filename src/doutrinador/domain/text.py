from __future__ import annotations

import re
import unicodedata


STOP_WORDS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "entre", "essa", "esse", "esta", "este", "isso", "na", "nas",
    "no", "nos", "o", "os", "ou", "para", "pela", "pelo", "por", "que",
    "qual", "quais", "se", "sem", "ser", "sobre", "sua", "suas", "um", "uma",
}


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in value if not unicodedata.combining(char))


def tokens(text: str) -> list[str]:
    return [
        token for token in re.findall(r"[a-z0-9]+", normalize(text))
        if len(token) > 2 and token not in STOP_WORDS
    ]
