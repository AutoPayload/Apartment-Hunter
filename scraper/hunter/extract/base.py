"""Extractor interface: read a listing, return classified facts (never a pass/fail decision)."""

from __future__ import annotations

from typing import Protocol

from ..models import Extraction, Listing

FIELDS = ("parking", "unit_type", "pets", "security", "utilities_included", "furnished", "pool_gym")


class Extractor(Protocol):
    def extract(self, listing: Listing) -> Extraction: ...


class SameListingJudge(Protocol):
    def same_listing(self, a: str, b: str) -> float | None:
        """Probability that two listing texts describe the same apartment (None if unavailable)."""
        ...
