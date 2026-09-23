"""Persistence. `SupabaseStore` for real runs; `MemoryStore` for tests and --dry-run."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from .models import Extraction, Listing, ScoreResult, Status


@dataclass
class Existing:
    id: int
    price_crc: int | None
    tier: str | None
    status: str
    extraction: dict[str, Any] | None
    duplicate_of: int | None


@dataclass
class Candidate:
    """An earlier listing that might be the same apartment."""

    id: int
    site: str
    title: str
    description: str
    price_crc: int | None
    zone: str | None
    bedrooms: int | None
    photo_hash: str | None
    size_m2: float | None = None


@dataclass
class Run:
    site: str
    started_at: datetime
    count: int
    new_count: int
    error: str | None


class Store(Protocol):
    def lookup(self, site: str, listing_ids: list[str]) -> dict[str, Existing]: ...
    def insert(self, listing: Listing, ex: Extraction, sc: ScoreResult, photo_hash: str | None,
               duplicate_of: int | None) -> int: ...
    def touch(self, ids: list[int]) -> None: ...
    def update_price(self, id: int, price_crc: int, price_raw: str, sc: ScoreResult) -> None: ...
    def mark_notified(self, id: int) -> None: ...
    def set_status(self, id: int, status: Status) -> None: ...
    def duplicate_candidates(self, listing: Listing, tolerance: float = 0.05) -> list[Candidate]: ...
    def digest(self, since: datetime) -> list[dict[str, Any]]: ...
    def log_run(self, site: str, started_at: datetime, count: int, new_count: int, error: str | None) -> None: ...
    def recent_runs(self, site: str, limit: int) -> list[Run]: ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row(listing: Listing, ex: Extraction, sc: ScoreResult, photo_hash: str | None,
         duplicate_of: int | None) -> dict[str, Any]:
    return {
        "site": listing.site,
        "listing_id": listing.listing_id,
        "url": listing.url,
        "title": listing.title,
        "description": listing.description,
        "location_text": listing.location_text,
        "zone": ex.zone or listing.zone,
        "price_raw": listing.price_raw,
        "currency": listing.currency,
        "price_crc": listing.price_crc,
        "size_m2": listing.size_m2,
        "bedrooms": listing.bedrooms,
        "phone": listing.phone,
        "photos": listing.photos,
        "photo_hash": photo_hash,
        "posted_at": listing.posted_at.isoformat() if listing.posted_at else None,
        "extraction": ex.model_dump(),
        "tier": sc.tier,
        "score": sc.score,
        "reasons": sc.reasons,
        "duplicate_of": duplicate_of,
    }


class SupabaseStore:
    def __init__(self, url: str, key: str):
        if not url or not key:
            raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set (or use --dry-run).")
        from supabase import create_client

        self.db = create_client(url, key)

    def lookup(self, site: str, listing_ids: list[str]) -> dict[str, Existing]:
        if not listing_ids:
            return {}
        rows = (
            self.db.table("listings")
            .select("id, listing_id, price_crc, tier, status, extraction, duplicate_of")
            .eq("site", site)
            .in_("listing_id", listing_ids)
            .execute()
            .data
        )
        return {
            r["listing_id"]: Existing(r["id"], r["price_crc"], r["tier"], r["status"], r["extraction"], r["duplicate_of"])
            for r in rows
        }

    def insert(self, listing, ex, sc, photo_hash, duplicate_of) -> int:
        row = _row(listing, ex, sc, photo_hash, duplicate_of)
        data = self.db.table("listings").upsert(row, on_conflict="site,listing_id").execute().data
        new_id = data[0]["id"]
        if listing.price_crc is not None:
            self.db.table("price_history").insert({"listing_id": new_id, "price_crc": listing.price_crc}).execute()
        return new_id

    def touch(self, ids: list[int]) -> None:
        if ids:
            self.db.table("listings").update({"last_seen": _now().isoformat()}).in_("id", ids).execute()

    def update_price(self, id: int, price_crc: int, price_raw: str, sc: ScoreResult) -> None:
        self.db.table("listings").update(
            {"price_crc": price_crc, "price_raw": price_raw, "tier": sc.tier, "score": sc.score,
             "reasons": sc.reasons, "last_seen": _now().isoformat()}
        ).eq("id", id).execute()
        self.db.table("price_history").insert({"listing_id": id, "price_crc": price_crc}).execute()

    def mark_notified(self, id: int) -> None:
        self.db.table("listings").update({"status": "notified", "notified_at": _now().isoformat()}).eq(
            "id", id).eq("status", "new").execute()

    def set_status(self, id: int, status: Status) -> None:
        self.db.table("listings").update({"status": status}).eq("id", id).execute()

    def duplicate_candidates(self, listing: Listing, tolerance: float = 0.05) -> list[Candidate]:
        if listing.price_crc is None:
            return []
        lo, hi = int(listing.price_crc * (1 - tolerance)), int(listing.price_crc * (1 + tolerance))
        q = (
            self.db.table("listings")
            .select("id, site, title, description, price_crc, zone, bedrooms, photo_hash, size_m2")
            .neq("site", listing.site)
            .is_("duplicate_of", "null")
            .gte("price_crc", lo)
            .lte("price_crc", hi)
            .gte("first_seen", (_now() - timedelta(days=60)).isoformat())
            .limit(25)
        )
        if listing.zone:
            q = q.eq("zone", listing.zone)
        return [Candidate(**r) for r in q.execute().data]

    def digest(self, since: datetime) -> list[dict[str, Any]]:
        return (
            self.db.table("listings")
            .select("id, site, url, title, price_crc, zone, score, reasons, phone, photos, first_seen")
            .eq("tier", "B")
            .eq("status", "new")
            .is_("duplicate_of", "null")
            .gte("first_seen", since.isoformat())
            .order("score", desc=True)
            .execute()
            .data
        )

    def log_run(self, site, started_at, count, new_count, error) -> None:
        self.db.table("scrape_runs").insert(
            {"site": site, "started_at": started_at.isoformat(), "count": count, "new_count": new_count,
             "error": error}
        ).execute()

    def recent_runs(self, site: str, limit: int) -> list[Run]:
        rows = (
            self.db.table("scrape_runs").select("site, started_at, count, new_count, error")
            .eq("site", site).order("started_at", desc=True).limit(limit).execute().data
        )
        return [Run(r["site"], datetime.fromisoformat(r["started_at"]), r["count"], r["new_count"], r["error"])
                for r in rows]


@dataclass
class MemoryStore:
    rows: dict[int, dict[str, Any]] = field(default_factory=dict)
    history: list[tuple[int, int]] = field(default_factory=list)
    runs: list[Run] = field(default_factory=list)

    def _find(self, site: str, listing_id: str) -> dict[str, Any] | None:
        return next((r for r in self.rows.values() if r["site"] == site and r["listing_id"] == listing_id), None)

    def lookup(self, site, listing_ids):
        out = {}
        for lid in listing_ids:
            r = self._find(site, lid)
            if r:
                out[lid] = Existing(r["id"], r["price_crc"], r["tier"], r["status"], r["extraction"], r["duplicate_of"])
        return out

    def insert(self, listing, ex, sc, photo_hash, duplicate_of) -> int:
        existing = self._find(listing.site, listing.listing_id)
        new_id = existing["id"] if existing else len(self.rows) + 1
        now = _now()
        self.rows[new_id] = {**_row(listing, ex, sc, photo_hash, duplicate_of), "id": new_id,
                             "status": "new", "first_seen": now, "last_seen": now}
        if listing.price_crc is not None:
            self.history.append((new_id, listing.price_crc))
        return new_id

    def touch(self, ids):
        for i in ids:
            self.rows[i]["last_seen"] = _now()

    def update_price(self, id, price_crc, price_raw, sc):
        self.rows[id].update(price_crc=price_crc, price_raw=price_raw, tier=sc.tier, score=sc.score,
                             reasons=sc.reasons, last_seen=_now())
        self.history.append((id, price_crc))

    def mark_notified(self, id):
        if self.rows[id]["status"] == "new":
            self.rows[id]["status"] = "notified"

    def set_status(self, id, status):
        self.rows[id]["status"] = status

    def duplicate_candidates(self, listing, tolerance=0.05):
        if listing.price_crc is None:
            return []
        lo, hi = listing.price_crc * (1 - tolerance), listing.price_crc * (1 + tolerance)
        return [
            Candidate(r["id"], r["site"], r["title"], r["description"], r["price_crc"], r["zone"], r["bedrooms"],
                      r["photo_hash"], r["size_m2"])
            for r in self.rows.values()
            if r["site"] != listing.site and r["duplicate_of"] is None and r["price_crc"] is not None
            and lo <= r["price_crc"] <= hi and (not listing.zone or r["zone"] == listing.zone)
        ]

    def digest(self, since):
        rows = [r for r in self.rows.values()
                if r["tier"] == "B" and r["status"] == "new" and r["duplicate_of"] is None and r["first_seen"] >= since]
        return sorted(rows, key=lambda r: -r["score"])

    def log_run(self, site, started_at, count, new_count, error):
        self.runs.append(Run(site, started_at, count, new_count, error))

    def recent_runs(self, site, limit):
        return [r for r in reversed(self.runs) if r.site == site][:limit]
