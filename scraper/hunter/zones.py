"""Target zones and the spellings used for them in listings."""

from __future__ import annotations

import re
import unicodedata

# Canonical zone -> aliases (matched accent- and case-insensitively, on word boundaries).
TARGET_ZONES: dict[str, list[str]] = {
    "Curridabat": [
        "curridabat", "granadilla", "tirrases", "sanchez", "freses", "pinares",
        "lomas de ayarco", "ayarco", "jose maria zeledon",
    ],
    "Zapote": ["zapote"],
    "San Francisco de Dos Ríos": ["san francisco de dos rios", "sfdr", "dos rios"],
    "Tres Ríos": ["tres rios", "la union", "concepcion de tres rios", "san juan de la union", "san diego de la union"],
    "San Antonio de Desamparados": ["san antonio de desamparados", "san antonio desamparados"],
    "Montes de Oca": [
        "montes de oca", "san pedro de montes de oca", "san pedro", "los yoses", "sabanilla",
        "mercedes de montes de oca", "betania", "san rafael de montes de oca", "lourdes",
        "barrio dent", "la granja",
    ],
}

OTHER_ZONE = "other"


def fold(text: str) -> str:
    """Lowercase and strip accents so 'Ríos' and 'rios' compare equal."""
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (zone, re.compile(r"\b" + re.escape(alias) + r"\b"))
    for zone, aliases in TARGET_ZONES.items()
    # Longest aliases first so "san pedro de montes de oca" beats "san pedro".
    for alias in sorted(aliases, key=len, reverse=True)
]


def match_zone(*texts: str) -> str | None:
    """Return the first target zone mentioned in the given texts, checked in order."""
    for text in texts:
        folded = fold(text)
        if not folded:
            continue
        for zone, pattern in _PATTERNS:
            if pattern.search(folded):
                return zone
    return None


def is_target(zone: str | None) -> bool:
    return zone in TARGET_ZONES
