"""One run for one site: collect -> normalize -> dedupe -> classify -> score -> store -> notify."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

from . import dedupe
from .adapters.base import Adapter
from .extract.base import Extractor
from .models import Extraction, Listing, ScoreResult
from .normalize import normalize
from .scoring import score
from .store import Store

log = logging.getLogger(__name__)

# A seen listing whose price falls by at least this fraction is re-scored and may re-alert.
PRICE_DROP_MIN = 0.02


class Notifier(Protocol):
    def alert(self, stored_id: int, listing: Listing, ex: Extraction, sc: ScoreResult, kind: str = "new",
              old_price: int | None = None) -> None: ...
    def digest(self, rows: list[dict]) -> None: ...
    def health(self, message: str) -> None: ...


@dataclass
class RunResult:
    site: str
    fetched: int = 0
    new: int = 0
    alerted: list[str] = field(default_factory=list)
    price_drops: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class Deps:
    store: Store
    extractor: Extractor
    notifier: Notifier
    usd_crc_rate: float
    # Returns the raw listings for an adapter (network, or a fixture file in tests / dry runs).
    collect: Callable[[Adapter], list[Listing]]
    # Fetches the detail page for a new listing (None disables detail fetching).
    enrich: Callable[[Adapter, Listing], Listing] | None = None
    photo_hash: Callable[[Listing], str | None] | None = None
    max_details: int = 15


def run_site(adapter: Adapter, deps: Deps) -> RunResult:
    started = datetime.now(timezone.utc)
    result = RunResult(site=adapter.name)
    try:
        _run(adapter, deps, result)
    except Exception as exc:
        log.exception("%s: run failed", adapter.name)
        result.error = f"{type(exc).__name__}: {exc}"[:500]
    deps.store.log_run(adapter.name, started, result.fetched, result.new, result.error)
    return result


def _run(adapter: Adapter, deps: Deps, result: RunResult) -> None:
    listings = [normalize(item, deps.usd_crc_rate) for item in deps.collect(adapter)]
    result.fetched = len(listings)
    existing = deps.store.lookup(adapter.name, [item.listing_id for item in listings])
    judge = deps.extractor if hasattr(deps.extractor, "same_listing") else None

    seen_ids: list[int] = []
    for listing in listings:
        prev = existing.get(listing.listing_id)
        if prev is None:
            continue
        seen_ids.append(prev.id)
        if (
            prev.price_crc and listing.price_crc
            and listing.price_crc <= prev.price_crc * (1 - PRICE_DROP_MIN)
            and prev.duplicate_of is None
        ):
            _price_drop(listing, prev, deps, result)
    deps.store.touch(seen_ids)

    new = [item for item in listings if item.listing_id not in existing]
    result.new = len(new)
    for i, listing in enumerate(new):
        if deps.enrich and i < deps.max_details:
            listing = normalize(deps.enrich(adapter, listing), deps.usd_crc_rate)
        ex = deps.extractor.extract(listing)
        if ex.zone and not listing.zone:
            listing.zone = ex.zone
        sc = score(listing, ex)

        dup_id = None
        phash = None
        if sc.tier in ("A", "B"):
            # Only worth the photo download / Jev call for listings we'd tell you about.
            phash = deps.photo_hash(listing) if deps.photo_hash else None
            dup = dedupe.find_duplicate(listing, phash, deps.store, judge)
            if dup:
                dup_id = dup.id
                result.duplicates.append(listing.key)
                sc.reasons.append(f"Duplicado de {dup.site} #{dup.id}")

        stored_id = deps.store.insert(listing, ex, sc, phash, dup_id)
        if sc.tier == "A" and dup_id is None:
            deps.notifier.alert(stored_id, listing, ex, sc)
            deps.store.mark_notified(stored_id)
            result.alerted.append(listing.key)


def _price_drop(listing: Listing, prev, deps: Deps, result: RunResult) -> None:
    ex = Extraction(**prev.extraction) if prev.extraction else deps.extractor.extract(listing)
    sc = score(listing, ex)
    deps.store.update_price(prev.id, listing.price_crc, listing.price_raw, sc)
    result.price_drops.append(listing.key)
    # Alert when the drop makes it an A (or it already was one and you haven't discarded it).
    if sc.tier == "A" and prev.status not in ("discarded", "reviewed"):
        deps.notifier.alert(prev.id, listing, ex, sc, kind="price_drop", old_price=prev.price_crc)
        deps.store.mark_notified(prev.id)
        result.alerted.append(listing.key)
