"""Shared data shapes. Every adapter returns `Listing`; later stages fill in the rest."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Tri = Literal["yes", "no", "unknown"]
UnitType = Literal["apartment", "studio", "room", "house", "unknown"]
Tier = Literal["A", "B", "none", "reject"]
Status = Literal["new", "notified", "interested", "reviewed", "discarded"]


class Listing(BaseModel):
    """One listing as scraped from a search page (plus normalized fields)."""

    site: str
    listing_id: str
    url: str
    title: str = ""
    price_raw: str = ""
    description: str = ""
    location_text: str = ""
    photos: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None

    # Filled by normalize.normalize()
    price: float | None = None
    currency: Literal["CRC", "USD"] | None = None
    price_crc: int | None = None
    size_m2: float | None = None
    bedrooms: int | None = None
    phone: str | None = None
    zone: str | None = None

    @property
    def key(self) -> str:
        return f"{self.site}:{self.listing_id}"

    @property
    def text(self) -> str:
        """Everything a classifier should read about the listing."""
        parts = [self.title, self.location_text, self.price_raw, self.description]
        return "\n".join(p for p in parts if p)


class Extraction(BaseModel):
    """Classified facts about a listing. Values below the confidence cutoff are "unknown"."""

    parking: Tri = "unknown"
    unit_type: UnitType = "unknown"
    zone: str | None = None
    pets: Tri = "unknown"
    security: Tri = "unknown"
    utilities_included: Tri = "unknown"
    furnished: Tri = "unknown"
    pool_gym: Tri = "unknown"
    confidence: dict[str, float] = Field(default_factory=dict)
    source: str = "keywords"


class ScoreResult(BaseModel):
    tier: Tier
    score: int
    reasons: list[str]


class StoredListing(BaseModel):
    """A listing row as read back from the store (subset used by the pipeline)."""

    id: int
    site: str
    listing_id: str
    url: str
    title: str = ""
    price_crc: int | None = None
    zone: str | None = None
    bedrooms: int | None = None
    size_m2: float | None = None
    photos: list[str] = Field(default_factory=list)
    description: str = ""
    tier: Tier | None = None
    status: Status = "new"
    duplicate_of: int | None = None
    photo_hash: str | None = None
