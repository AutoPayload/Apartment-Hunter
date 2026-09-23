"""Jev (TypeSafe AI System One) extractor.

Jev answers typed questions in one pass (`Choice`, `Noul`, `Score`) and returns a confidence
for each answer. It does not write text or numbers, so prices, sizes and phones stay in
normalize.py. Here it only classifies. Answers below `min_confidence` become "unknown", and
the keyword extractor fills anything Jev leaves unknown.
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import Extraction, Listing
from ..zones import OTHER_ZONE, TARGET_ZONES
from .base import FIELDS
from .keywords import KeywordExtractor

log = logging.getLogger(__name__)

_TRI = {
    "yes": "The listing clearly says so.",
    "no": "The listing clearly says the opposite.",
    "unknown": "The listing does not mention it or is ambiguous.",
}


def _questions() -> dict[str, Any]:
    from typesafe_sdk import Choice

    def tri(instructions: str) -> Any:
        return Choice(instructions=instructions, criteria=_TRI)

    return {
        "parking": tri("Does the rental include at least one private parking space for a car (parqueo, cochera, estacionamiento)?"),
        "unit_type": Choice(
            instructions="What is being rented?",
            criteria={
                "apartment": "A whole apartment with its own kitchen and bathroom (apartamento, condominio).",
                "studio": "A whole studio / monoambiente / loft / apartaestudio.",
                "room": "A single room or a shared space inside a house or apartment.",
                "house": "A whole house.",
                "unknown": "Cannot tell.",
            },
        ),
        "pets": tri("Are pets allowed?"),
        "security": tri("Does the building or condo have 24/7 security, a guard, or gated / controlled access?"),
        "utilities_included": tri("Are utilities (water, electricity, internet) or the condo maintenance fee included in the rent?"),
        "furnished": tri("Is the unit furnished (amueblado)?"),
        "pool_gym": tri("Does the property have a pool or a gym?"),
        "zone": Choice(
            instructions="Which area of Costa Rica is the property in?",
            criteria={
                **{zone: "Includes: " + ", ".join(aliases) for zone, aliases in TARGET_ZONES.items()},
                OTHER_ZONE: "Anywhere else, or not stated.",
            },
        ),
    }


class JevExtractor:
    source = "jev"

    def __init__(self, api_key: str, min_confidence: float = 0.6, client: Any = None, model: str | None = None):
        self.min_confidence = min_confidence
        self.fallback = KeywordExtractor()
        if client is None:
            from typesafe_sdk import TypeSafeClient

            client = TypeSafeClient(api_key=api_key, model=model)
        self.client = client
        self._questions = _questions()

    def extract(self, listing: Listing) -> Extraction:
        rules = self.fallback.extract(listing)
        try:
            response = self.client.system_one(
                state={
                    "title": listing.title,
                    "location": listing.location_text,
                    "price": listing.price_raw,
                    "description": listing.description[:4000],
                },
                questions=self._questions,
            )
        except Exception as exc:  # network, quota, validation: fall back, never crash the run
            log.warning("Jev failed for %s, using keywords: %s", listing.key, exc)
            return rules

        values: dict[str, Any] = {}
        confidence: dict[str, float] = {}
        for name in (*FIELDS, "zone"):
            answer = response.choices.get(name)
            if answer is None:
                continue
            confidence[name] = round(float(answer.confidence), 3)
            if answer.confidence >= self.min_confidence and answer.choice != "unknown":
                values[name] = answer.choice

        # Keyword rules fill whatever Jev left unknown (e.g. explicit "sin parqueo").
        for name in FIELDS:
            if name not in values and getattr(rules, name) != "unknown":
                values[name] = getattr(rules, name)
                confidence.setdefault(name, rules.confidence.get(name, 0.0))

        zone = listing.zone or rules.zone
        if not zone and values.get("zone") in TARGET_ZONES:
            zone = values["zone"]
        values.pop("zone", None)
        return Extraction(**values, zone=zone, confidence=confidence, source=self.source)

    def same_listing(self, a: str, b: str) -> float | None:
        from typesafe_sdk import Noul

        try:
            response = self.client.system_one(
                state={"listing_a": a[:2000], "listing_b": b[:2000]},
                questions={
                    "same": Noul(
                        instructions="Do listing_a and listing_b advertise the same physical apartment?",
                        criteria={
                            "true": "Same unit: matching building/area, size, rooms and price, possibly worded differently.",
                            "false": "Different units, even if in the same building or area.",
                        },
                    )
                },
            )
            return float(response.nouls["same"].noul)
        except Exception as exc:
            log.warning("Jev duplicate check failed: %s", exc)
            return None
