"""Cross-site duplicate detection: the same apartment posted on several sites alerts only once.

Candidates are earlier listings from other sites with a similar price (±5%) in the same zone.
A candidate counts as the same apartment when any of these holds:
  1. their first photos are near-identical (average hash, Hamming distance <= 6),
  2. Jev says they're the same unit with probability >= 0.8,
  3. same exact price, bedrooms and size (m²), which is strong enough on its own,
  4. without Jev: bedrooms match and the titles/descriptions are very similar.
"""

from __future__ import annotations

import io
import logging
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from .extract.base import SameListingJudge
from .models import Listing
from .store import Candidate, Store

if TYPE_CHECKING:
    from .http import PoliteClient

log = logging.getLogger(__name__)

HASH_MAX_DISTANCE = 6
JEV_MIN_SAME = 0.8
TEXT_MIN_RATIO = 0.85


def average_hash(image_bytes: bytes, size: int = 8) -> str | None:
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((size, size))
    except Exception:
        return None
    pixels = list(img.tobytes())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p > avg else "0" for p in pixels)
    return f"{int(bits, 2):0{size * size // 4}x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def photo_hash(client: "PoliteClient", listing: Listing) -> str | None:
    if not listing.photos:
        return None
    try:
        return average_hash(client.get(listing.photos[0], check_robots=False).content)
    except Exception as exc:
        log.debug("photo fetch failed for %s: %s", listing.key, exc)
        return None


def _summary(title: str, description: str) -> str:
    return f"{title}\n{description[:600]}".lower()


def find_duplicate(listing: Listing, phash: str | None, store: Store,
                   judge: SameListingJudge | None = None) -> Candidate | None:
    for cand in store.duplicate_candidates(listing):
        if listing.bedrooms is not None and cand.bedrooms is not None and listing.bedrooms != cand.bedrooms:
            continue
        if phash and cand.photo_hash and hamming(phash, cand.photo_hash) <= HASH_MAX_DISTANCE:
            return cand
        if (
            listing.price_crc == cand.price_crc and listing.bedrooms is not None
            and listing.bedrooms == cand.bedrooms and listing.size_m2 and cand.size_m2
            and abs(listing.size_m2 - cand.size_m2) <= 1
        ):
            return cand
        a = _summary(listing.title, listing.description)
        b = _summary(cand.title, cand.description)
        if judge is not None:
            p = judge.same_listing(a, b)
            if p is not None:
                if p >= JEV_MIN_SAME:
                    return cand
                continue
        if listing.bedrooms is not None and SequenceMatcher(None, a, b).ratio() >= TEXT_MIN_RATIO:
            return cand
    return None
