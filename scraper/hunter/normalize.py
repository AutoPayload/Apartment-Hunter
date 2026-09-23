"""Turn messy scraped text into numbers: price, currency, size, bedrooms, phone, dates."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .models import Listing
from .zones import fold, match_zone

# Below this amount a price with no currency marker is assumed to be USD.
USD_GUESS_CEILING = 10_000

_CRC_MARK = r"(?:₡|¢|crc|colones|col\.)"
_USD_MARK = r"(?:us\$|usd|u\$s|\$|dolares|dólares)"
_NUM = r"\d{1,3}(?:[.,\u00a0 ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_MULT = r"(?:\s*(mil|k|millones|millon|millón|m(?![²2a-z])))?"

_PRICE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("CRC", re.compile(_CRC_MARK + r"\s*(" + _NUM + r")" + _MULT, re.I)),
    ("USD", re.compile(_USD_MARK + r"\s*(" + _NUM + r")" + _MULT, re.I)),
    ("CRC", re.compile(r"(" + _NUM + r")" + _MULT + r"\s*" + _CRC_MARK, re.I)),
    ("USD", re.compile(r"(" + _NUM + r")" + _MULT + r"\s*" + _USD_MARK, re.I)),
]
_BARE_PRICE = re.compile(r"(" + _NUM + r")" + _MULT, re.I)


def parse_number(raw: str) -> float | None:
    """Parse '350.000', '350,000', '1.200.000', '1,250.50', '650' into a float."""
    s = re.sub(r"\s", "", raw or "")
    if not s:
        return None
    if "." in s and "," in s:
        # Whichever separator comes last is the decimal one.
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        s = s.replace(thou, "").replace(dec, ".")
    elif "." in s or "," in s:
        sep = "." if "." in s else ","
        parts = s.split(sep)
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            s = "".join(parts)  # thousands grouping
        elif len(parts) == 2:
            s = parts[0] + "." + parts[1]  # decimal
        else:
            s = "".join(parts)
    try:
        return float(s)
    except ValueError:
        return None


def _apply_multiplier(value: float, mult: str | None) -> float:
    m = (mult or "").lower()
    if m in ("mil", "k"):
        return value * 1_000
    if m in ("millones", "millon", "millón", "m"):
        return value * 1_000_000
    return value


def parse_price(text: str, allow_bare: bool = True) -> tuple[float, str] | None:
    """Find the first price in text. Returns (amount, "CRC"|"USD") or None.

    With allow_bare, a number with no currency marker counts too (use only on a price field).
    """
    if not text:
        return None
    best: tuple[int, float, str] | None = None
    for currency, pattern in _PRICE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        value = parse_number(m.group(1))
        if value is None or value <= 0:
            continue
        value = _apply_multiplier(value, m.group(2))
        if best is None or m.start() < best[0]:
            best = (m.start(), value, currency)
    if best:
        return best[1], best[2]
    m = _BARE_PRICE.search(text) if allow_bare else None
    if m:
        value = parse_number(m.group(1))
        if value:
            value = _apply_multiplier(value, m.group(2))
            return value, ("USD" if value < USD_GUESS_CEILING else "CRC")
    return None


def to_crc(amount: float, currency: str, usd_crc_rate: float) -> int:
    return int(round(amount * usd_crc_rate if currency == "USD" else amount))


_BEDROOMS = re.compile(
    r"(\d{1,2})\s*(?:habitaciones|habitacion|hab\.?|cuartos?|dormitorios?|recamaras?|bedrooms?|beds?)\b"
)
_BEDROOM_WORDS = {"una": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4}
_BEDROOMS_WORD = re.compile(r"\b(una|un|dos|tres|cuatro)\s+(?:habitaciones|habitacion|cuartos?|dormitorios?)\b")
_SIZE = re.compile(r"(\d{2,4}(?:[.,]\d+)?)\s*(?:m2|m²|mts2|mts|mt2|metros cuadrados|metros)\b")
_PHONE = re.compile(r"(?:\+?506[\s-]?)?\b([245678]\d{3})[\s-]?(\d{4})\b")


def parse_bedrooms(text: str) -> int | None:
    t = fold(text)
    if re.search(r"\b(estudio|studio|monoambiente|loft)\b", t) and not _BEDROOMS.search(t):
        return 0
    m = _BEDROOMS.search(t)
    if m:
        return int(m.group(1))
    m = _BEDROOMS_WORD.search(t)
    return _BEDROOM_WORDS[m.group(1)] if m else None


def parse_size(text: str) -> float | None:
    m = _SIZE.search(fold(text))
    return parse_number(m.group(1)) if m else None


def parse_phone(text: str) -> str | None:
    """Return a Costa Rican number as 8 digits, preferring mobiles (6/7/8...)."""
    found = [a + b for a, b in _PHONE.findall(text or "")]
    mobiles = [p for p in found if p[0] in "678"]
    return (mobiles or found or [None])[0]


def whatsapp_link(phone: str | None, message: str = "") -> str | None:
    if not phone:
        return None
    from urllib.parse import quote

    link = f"https://wa.me/506{phone}"
    return f"{link}?text={quote(message)}" if message else link


_RELATIVE = re.compile(r"hace\s+(\d+|un|una)\s*(minutos?|min|horas?|h|dias?|semanas?|mes(?:es)?)")
_DMY = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?:[t ](\d{2}):(\d{2})(?::(\d{2}))?)?")


def parse_posted(text: str, now: datetime | None = None) -> datetime | None:
    """Parse 'hace 3 horas', 'ayer', 'hoy', '2026-09-20', '20/09/2026'."""
    now = now or datetime.now(timezone.utc)
    t = fold(text)
    if not t:
        return None
    m = _ISO.search(t)
    if m:
        y, mo, d, hh, mm, ss = m.groups()
        return datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0), tzinfo=timezone.utc)
    m = _RELATIVE.search(t)
    if m:
        n = 1 if m.group(1) in ("un", "una") else int(m.group(1))
        unit = m.group(2)
        if unit.startswith("min"):
            delta = timedelta(minutes=n)
        elif unit.startswith("h"):
            delta = timedelta(hours=n)
        elif unit.startswith("d"):
            delta = timedelta(days=n)
        elif unit.startswith("s"):
            delta = timedelta(weeks=n)
        else:
            delta = timedelta(days=30 * n)
        return now - delta
    if re.search(r"\bhoy\b", t):
        return now
    if re.search(r"\bayer\b", t):
        return now - timedelta(days=1)
    m = _DMY.search(t)
    if m:
        d, mo, y = (int(g) for g in m.groups())
        y = y + 2000 if y < 100 else y
        try:
            return datetime(y, mo, d, tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize(listing: Listing, usd_crc_rate: float) -> Listing:
    """Fill the numeric/derived fields of a listing in place and return it."""
    listing.title = clean_text(listing.title)
    listing.location_text = clean_text(listing.location_text)
    listing.description = clean_text(listing.description)
    listing.price_raw = clean_text(listing.price_raw)

    parsed = parse_price(listing.price_raw) or parse_price(
        f"{listing.title} {listing.description}", allow_bare=False
    )
    if parsed:
        listing.price, listing.currency = parsed
        listing.price_crc = to_crc(listing.price, listing.currency, usd_crc_rate)

    body = f"{listing.title} {listing.description}"
    listing.bedrooms = listing.bedrooms if listing.bedrooms is not None else parse_bedrooms(body)
    listing.size_m2 = listing.size_m2 or parse_size(body)
    listing.phone = listing.phone or parse_phone(listing.description)
    listing.zone = listing.zone or match_zone(listing.location_text, listing.title, listing.description)
    return listing
