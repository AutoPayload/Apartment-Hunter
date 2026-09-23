"""Adapter base class. A site adapter is mostly configuration: URLs, a URL pattern, selectors.

Parsing tries, in order:
  1. JSON-LD listing objects embedded in the page (most stable when present),
  2. card selectors (`Selectors`),
  3. a link fallback: every <a> whose href matches `detail_url_pattern`.
Results from 2 and 3 are merged into 1 by URL, so partial data from each still helps.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from selectolax.parser import HTMLParser

from ..models import Listing
from ..normalize import parse_posted
from . import generic as g

if TYPE_CHECKING:
    from ..http import PoliteClient

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Selectors:
    """CSS selectors. Each field may list comma-separated alternatives; the first that matches wins."""

    card: str = ""
    link: str = "a[href]"
    title: str = "h2, h3, [class*=title]"
    price: str = "[class*=price], [class*=precio]"
    location: str = "[class*=location], [class*=ubicacion], [class*=address]"
    description: str = "[class*=description], [class*=descripcion], p"
    image: str = "img"
    date: str = "time, [class*=date], [class*=fecha]"


@dataclass(frozen=True)
class DetailSelectors:
    description: str = "[class*=description], [class*=descripcion], [itemprop=description]"
    price: str = "[class*=price], [class*=precio]"
    location: str = "[class*=location], [class*=ubicacion], [class*=address]"
    gallery: str = "[class*=gallery] img, [class*=slider] img, [class*=carousel] img"


class Adapter:
    name: str = ""
    base_url: str = ""
    # Pre-filtered, newest-first search URLs. Only page 1 is fetched. Override without code
    # changes with env HUNTER_URLS_<NAME>="url1 url2".
    search_urls: list[str] = []
    # Regex matching a listing detail URL; group 1 (if any) is the listing id.
    detail_url_pattern: str = ""
    # Optional regex for the listing id when it differs from detail_url_pattern's group 1.
    # Falls back to the last URL path segment.
    id_pattern: str = ""
    selectors: Selectors = Selectors()
    detail_selectors: DetailSelectors = DetailSelectors()
    needs_js: bool = False

    def urls(self) -> list[str]:
        env = os.getenv(f"HUNTER_URLS_{self.name.upper()}", "").split()
        return env or list(self.search_urls)

    # ---- fetching ----

    def fetch_html(self, client: "PoliteClient", url: str) -> str:
        if self.needs_js:
            from .playwright_fetch import render

            return render(url, client.user_agent)
        return client.get_text(url)

    def fetch(self, client: "PoliteClient") -> list[Listing]:
        seen: dict[str, Listing] = {}
        for url in self.urls():
            html = self.fetch_html(client, url)
            for listing in self.parse(html, url):
                seen.setdefault(listing.listing_id, listing)
        return list(seen.values())

    # ---- parsing ----

    def _url_re(self) -> re.Pattern[str] | None:
        return re.compile(self.detail_url_pattern) if self.detail_url_pattern else None

    def parse(self, html: str, page_url: str) -> list[Listing]:
        tree = HTMLParser(html)
        url_re = self._url_re()
        entries: dict[str, dict] = {}

        def merge(entry: dict) -> None:
            url = entry.get("url")
            if not url or (url_re and not url_re.search(url)):
                return
            existing = entries.setdefault(url, {"url": url})
            for key, value in entry.items():
                if value and not existing.get(key):
                    existing[key] = value

        for entry in g.ld_listings(tree, page_url, url_re):
            merge(entry)
        for entry in self.parse_cards(tree, page_url):
            merge(entry)
        if not entries and url_re:
            for entry in self.parse_links(tree, page_url, url_re):
                merge(entry)

        listings = []
        for entry in entries.values():
            listing = self.to_listing(entry)
            if listing:
                listings.append(listing)
        return listings

    def parse_cards(self, tree: HTMLParser, base: str) -> list[dict]:
        s = self.selectors
        out = []
        for card in g.all_matches(tree, s.card):
            link = card if card.tag == "a" else g.first(card, s.link)
            href = link.attributes.get("href") if link is not None else None
            url = g.absolute(base, href)
            if not url:
                continue
            date_node = g.first(card, s.date)
            out.append(
                {
                    "url": url,
                    "title": g.text_of(g.first(card, s.title)) or g.text_of(link),
                    "price_raw": g.text_of(g.first(card, s.price)),
                    "location_text": g.text_of(g.first(card, s.location)),
                    "description": g.text_of(g.first(card, s.description)),
                    "photos": [p for p in [g.image_url(g.first(card, s.image), base)] if p],
                    "posted": (date_node.attributes.get("datetime") if date_node else None)
                    or g.text_of(date_node),
                }
            )
        return out

    def parse_links(self, tree: HTMLParser, base: str, url_re: re.Pattern[str]) -> list[dict]:
        out = []
        for a in tree.css("a[href]"):
            url = g.absolute(base, a.attributes.get("href"))
            if url_re.search(url):
                img = a.css_first("img")
                out.append(
                    {
                        "url": url,
                        "title": g.text_of(a) or (img.attributes.get("alt", "") if img else ""),
                        "photos": [p for p in [g.image_url(img, base)] if p],
                    }
                )
        return out

    def to_listing(self, entry: dict) -> Listing | None:
        url = entry["url"]
        title = entry.get("title") or ""
        if not title and not entry.get("price_raw"):
            return None
        return Listing(
            site=self.name,
            listing_id=g.id_from_url(url, self.id_pattern or self.detail_url_pattern),
            url=url,
            title=title,
            price_raw=str(entry.get("price_raw") or ""),
            description=entry.get("description") or "",
            location_text=entry.get("location_text") or "",
            photos=entry.get("photos") or [],
            posted_at=parse_posted(str(entry.get("posted") or "")),
        )

    # ---- detail pages (only fetched for new listings) ----

    def enrich(self, client: "PoliteClient", listing: Listing) -> Listing:
        try:
            html = self.fetch_html(client, listing.url)
        except Exception as exc:  # detail pages are a bonus; never fail the run for them
            log.warning("%s: detail fetch failed for %s: %s", self.name, listing.url, exc)
            return listing
        return self.parse_detail(html, listing)

    def parse_detail(self, html: str, listing: Listing) -> Listing:
        tree = HTMLParser(html)
        ds = self.detail_selectors
        ld = g.ld_listings(tree, listing.url)
        ld_entry = next((e for e in ld if e["url"] == listing.url), ld[0] if ld else {})

        description = (
            g.text_of(g.first(tree.body or tree.root, ds.description))
            or ld_entry.get("description", "")
            or g.meta(tree, "og:description", "description")
        )
        if len(description) > len(listing.description):
            listing.description = description
        if not listing.price_raw:
            listing.price_raw = ld_entry.get("price_raw") or g.text_of(g.first(tree.root, ds.price))
        if not listing.location_text:
            listing.location_text = ld_entry.get("location_text") or g.text_of(g.first(tree.root, ds.location))
        if not listing.title:
            listing.title = g.meta(tree, "og:title") or g.text_of(tree.css_first("h1"))

        photos = list(listing.photos)
        for url in ld_entry.get("photos", []) + [g.meta(tree, "og:image")] + [
            g.image_url(n, listing.url) for n in g.all_matches(tree, ds.gallery)
        ]:
            if url and url not in photos:
                photos.append(url)
        listing.photos = photos[:12]

        phones = g.phone_links(tree)
        if phones and not listing.phone:
            listing.phone = phones[0]
        if listing.posted_at is None:
            listing.posted_at = parse_posted(ld_entry.get("posted", "") or g.meta(tree, "article:published_time"))
        return listing
