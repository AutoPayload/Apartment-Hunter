"""Offline, rule-based extractor. Used when Jev is not configured, fails, or is unsure."""

from __future__ import annotations

import re

from ..models import Extraction, Listing
from ..zones import fold, match_zone

# (field, value, patterns). Earlier rules win, so negatives come before positives.
_RULES: list[tuple[str, str, list[str]]] = [
    ("parking", "no", [
        r"sin (parqueo|estacionamiento|cochera|garaje)", r"no (incluye|tiene|cuenta con|hay|ofrece) (parqueo|estacionamiento|cochera|garaje)",
        r"parqueo (publico|en (la )?(calle|via))", r"no (apto|apta) para (carro|vehiculo)",
    ]),
    ("parking", "yes", [
        r"\bparqueos?\b", r"\bestacionamientos?\b", r"\bcochera\b", r"\bgaraje\b", r"\bgarage\b",
        r"espacio para (un |1 |dos |2 )?(carro|vehiculo|auto)", r"\bparking\b",
    ]),
    ("unit_type", "room", [
        r"(alquil[oa]|se alquila|renta) (una )?(habitacion|cuarto)\b", r"\b(habitacion|cuarto) (en casa|para (estudiante|senorita|caballero|persona sola))",
        r"\bcompartid[oa]s?\b", r"\broommates?\b", r"\bshared room\b",
    ]),
    ("unit_type", "studio", [r"\bestudio\b", r"\bstudio\b", r"\bmonoambiente\b", r"\bloft\b", r"\bapartaestudio\b"]),
    ("unit_type", "apartment", [r"\bapartamentos?\b", r"\bapto\b", r"\bapartment\b", r"\bdepartamento\b", r"\bcondominio\b"]),
    ("unit_type", "house", [r"^(se alquila |alquilo |alquiler (de )?)?casa\b", r"\bcasa (de|en) \w+"]),
    ("pets", "no", [r"no (se )?(aceptan|acepta|permiten|permite) mascotas", r"\bsin mascotas\b", r"\bno mascotas\b", r"\bno pets\b"]),
    ("pets", "yes", [r"(acepta|aceptan|permite|permiten) mascotas", r"pet ?friendly", r"mascotas (permitidas|bienvenidas)", r"\bpets? (allowed|ok)\b"]),
    ("security", "yes", [
        r"seguridad (24|privada|las 24)", r"\bvigilancia\b", r"\bguarda\b", r"acceso controlado", r"porton electrico",
        r"condominio (cerrado|con seguridad)", r"residencial cerrado", r"\bgated\b", r"circuito cerrado", r"\bcamaras\b",
    ]),
    ("utilities_included", "no", [r"servicios (no incluidos|aparte|por aparte)", r"no incluye (agua|luz|servicios)"]),
    ("utilities_included", "yes", [
        r"servicios incluidos", r"incluye (agua|luz|internet|servicios|cuota|mantenimiento)", r"(agua|luz|internet) incluid[oa]s?",
        r"(mantenimiento|cuota( de condominio)?) incluid[oa]", r"todo incluido",
    ]),
    ("furnished", "no", [r"sin (amueblar|muebles|amoblar)", r"\bno amueblado\b", r"\bunfurnished\b"]),
    ("furnished", "yes", [r"\bamueblad[oa]\b", r"\bamoblad[oa]\b", r"\bfurnished\b", r"semi ?amueblad[oa]"]),
    ("pool_gym", "yes", [r"\bpiscina\b", r"\bgimnasio\b", r"\bgym\b", r"\bpool\b"]),
]
_COMPILED = [(f, v, [re.compile(p) for p in pats]) for f, v, pats in _RULES]


class KeywordExtractor:
    source = "keywords"

    def extract(self, listing: Listing) -> Extraction:
        title = fold(listing.title)
        text = fold(listing.text)
        values: dict[str, str] = {}
        for field, value, patterns in _COMPILED:
            if field in values:
                continue
            # Unit type is decided by the title first, since descriptions mention other units.
            haystacks = (title, text) if field == "unit_type" else (text,)
            if any(p.search(h) for h in haystacks for p in patterns):
                values[field] = value
        return Extraction(
            **values,
            zone=listing.zone or match_zone(listing.location_text, listing.title, listing.description),
            confidence={k: 0.7 for k in values},
            source=self.source,
        )
