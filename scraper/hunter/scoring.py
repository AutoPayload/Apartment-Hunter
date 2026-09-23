"""Your rules. The AI only supplies facts; pass/fail is decided here, in plain code.

Edit the constants below to change what counts as a match.
"""

from __future__ import annotations

from .models import Extraction, Listing, ScoreResult
from .zones import is_target

TIER_A_MAX_CRC = 350_000   # instant alert at or below this (parking included)
TIER_B_MAX_CRC = 380_000   # daily digest up to this

BASE_SCORE = {"A": 70, "B": 45}
BONUS = {
    "security": (10, "Seguridad 24/7 o acceso controlado"),
    "pets": (8, "Acepta mascotas"),
    "utilities_included": (8, "Servicios o cuota incluidos"),
    "pool_gym": (5, "Piscina o gimnasio"),
    "furnished": (3, "Amueblado"),
}


def _fmt(crc: int) -> str:
    return f"₡{crc:,.0f}".replace(",", ".")


def score(listing: Listing, ex: Extraction) -> ScoreResult:
    reasons: list[str] = []

    # --- hard rejects ---
    if ex.unit_type == "room":
        return ScoreResult(tier="reject", score=0, reasons=["Habitación / espacio compartido"])
    if ex.parking == "no":
        return ScoreResult(tier="reject", score=0, reasons=["Sin parqueo"])

    price = listing.price_crc
    zone = ex.zone or listing.zone
    in_zone = is_target(zone)

    if price is None:
        # Can't place it without a price, so it goes to the digest to check by hand.
        tier = "B" if in_zone else "none"
        reasons.append("Precio no indicado")
    elif price > TIER_B_MAX_CRC:
        return ScoreResult(tier="none", score=0, reasons=[f"Precio {_fmt(price)} > {_fmt(TIER_B_MAX_CRC)}"])
    elif not in_zone:
        return ScoreResult(tier="none", score=0, reasons=[f"Fuera de zonas objetivo ({zone or 'zona desconocida'})"])
    elif price <= TIER_A_MAX_CRC and ex.parking == "yes":
        tier = "A"
        reasons.append(f"{_fmt(price)} con parqueo en {zone}")
    elif price <= TIER_A_MAX_CRC:
        tier = "B"
        reasons.append(f"{_fmt(price)} en {zone}; parqueo sin confirmar (preguntar)")
    else:
        tier = "B"
        parking = "con parqueo" if ex.parking == "yes" else "parqueo sin confirmar"
        reasons.append(f"{_fmt(price)} en {zone} ({parking})")

    if listing.currency == "USD" and listing.price is not None:
        reasons.append(f"Publicado en USD (${listing.price:,.0f})")

    points = BASE_SCORE.get(tier, 0)
    for field, (bonus, label) in BONUS.items():
        if getattr(ex, field) == "yes":
            points += bonus
            reasons.append(label)
    if ex.unit_type == "studio":
        reasons.append("Estudio")
    if price is not None:
        # Cheaper is better: up to +10 for being well under the Tier A ceiling.
        points += max(0, min(10, (TIER_A_MAX_CRC - price) // 10_000))
    return ScoreResult(tier=tier, score=min(points, 100), reasons=reasons)
