"""Site-independent HTML helpers: JSON-LD, OpenGraph, selector-driven cards, link fallback."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser, Node

LISTING_TYPES = {
    "offer", "product", "residence", "apartment", "house", "singlefamilyresidence",
    "accommodation", "realestatelisting", "place", "room",
}


def text_of(node: Node | None) -> str:
    return re.sub(r"\s+", " ", node.text(separator=" ")).strip() if node else ""


def first(node: Node, selectors: str | None) -> Node | None:
    """Return the first match among comma-separated alternative selectors, in the order given."""
    if not selectors:
        return None
    for sel in (s.strip() for s in selectors.split(",")):
        if sel:
            found = node.css_first(sel)
            if found is not None:
                return found
    return None


def all_matches(node: Node | HTMLParser, selectors: str | None) -> list[Node]:
    """All matches for the first alternative selector that matches anything."""
    if not selectors:
        return []
    for sel in (s.strip() for s in selectors.split(",")):
        if sel:
            found = node.css(sel)
            if found:
                return found
    return []


def absolute(base: str, href: str | None) -> str:
    if not href:
        return ""
    url = urljoin(base, href.strip())
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def image_url(node: Node | None, base: str) -> str:
    if node is None:
        return ""
    attrs = node.attributes
    for key in ("data-src", "data-lazy-src", "data-original", "src", "data-bg"):
        val = attrs.get(key)
        if val and not val.startswith("data:"):
            return absolute(base, val)
    srcset = attrs.get("data-srcset") or attrs.get("srcset")
    if srcset:
        return absolute(base, srcset.split(",")[0].split()[0])
    style = attrs.get("style") or ""
    m = re.search(r"url\(['\"]?([^'\")]+)", style)
    return absolute(base, m.group(1)) if m else ""


def id_from_url(url: str, pattern: str | None) -> str:
    if pattern:
        m = re.search(pattern, url)
        found = next((grp for grp in (m.groups() if m else ()) if grp), None)
        if found:
            return found
    path = urlsplit(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1]
    return slug or hashlib.sha1(url.encode()).hexdigest()[:16]


# ---------- JSON-LD ----------

def _walk_ld(obj: Any) -> Iterable[dict]:
    if isinstance(obj, list):
        for item in obj:
            yield from _walk_ld(item)
    elif isinstance(obj, dict):
        yield obj
        for key in ("@graph", "itemListElement", "item", "mainEntity", "offers", "itemOffered"):
            if key in obj:
                yield from _walk_ld(obj[key])


def json_ld(tree: HTMLParser) -> list[dict]:
    out: list[dict] = []
    for script in tree.css('script[type="application/ld+json"]'):
        raw = script.text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Some sites emit several objects or trailing commas; skip what we can't read.
            continue
        out.extend(_walk_ld(data))
    return out


def _types(obj: dict) -> set[str]:
    t = obj.get("@type", [])
    return {x.lower() for x in (t if isinstance(t, list) else [t]) if isinstance(x, str)}


def _ld_price(obj: dict) -> str:
    offers = obj.get("offers")
    offer = offers[0] if isinstance(offers, list) and offers else offers
    src = offer if isinstance(offer, dict) else obj
    price = src.get("price") or (src.get("priceSpecification") or {}).get("price")
    if price in (None, ""):
        return ""
    currency = src.get("priceCurrency") or (src.get("priceSpecification") or {}).get("priceCurrency") or ""
    return f"{currency} {price}".strip()


def _ld_location(obj: dict) -> str:
    addr = obj.get("address")
    if not addr:
        loc = obj.get("location") or (obj.get("itemOffered") or {}).get("address")
        addr = loc.get("address") if isinstance(loc, dict) and "address" in loc else loc
    if isinstance(addr, dict):
        keys = ("streetAddress", "addressLocality", "addressRegion")
        return ", ".join(str(addr[k]) for k in keys if addr.get(k))
    return str(addr) if isinstance(addr, str) else ""


def _ld_images(obj: dict, base: str) -> list[str]:
    img = obj.get("image")
    items = img if isinstance(img, list) else [img]
    urls = []
    for it in items:
        if isinstance(it, dict):
            it = it.get("url") or it.get("contentUrl")
        if isinstance(it, str) and it:
            urls.append(absolute(base, it))
    return urls


def ld_listings(tree: HTMLParser, base: str, url_filter: re.Pattern[str] | None = None) -> list[dict]:
    """Listing-like JSON-LD objects as plain dicts with our field names."""
    results: dict[str, dict] = {}
    for obj in json_ld(tree):
        if not (_types(obj) & LISTING_TYPES):
            continue
        url = absolute(base, obj.get("url") or obj.get("@id") or "")
        if not url or (url_filter and not url_filter.search(url)):
            continue
        entry = results.setdefault(url, {"url": url})
        entry.setdefault("title", obj.get("name") or "")
        entry.setdefault("description", obj.get("description") or "")
        if not entry.get("price_raw"):
            entry["price_raw"] = _ld_price(obj)
        if not entry.get("location_text"):
            entry["location_text"] = _ld_location(obj)
        if not entry.get("photos"):
            entry["photos"] = _ld_images(obj, base)
        entry.setdefault("posted", obj.get("datePosted") or obj.get("datePublished") or "")
    return list(results.values())


# ---------- OpenGraph / detail pages ----------

def meta(tree: HTMLParser, *names: str) -> str:
    for name in names:
        node = tree.css_first(f'meta[property="{name}"]') or tree.css_first(f'meta[name="{name}"]')
        if node is not None and node.attributes.get("content"):
            return node.attributes["content"].strip()
    return ""


def phone_links(tree: HTMLParser) -> list[str]:
    """Numbers from tel: and WhatsApp links, which detail pages often hide phones behind."""
    out = []
    for a in tree.css('a[href^="tel:"], a[href*="wa.me/"], a[href*="api.whatsapp.com"]'):
        href = (a.attributes.get("href") or "").replace("%20", "")
        href = re.sub(r"[\s\-()+]", "", href)
        m = re.search(r"(?:506)?([245678]\d{7})(?!\d)", href)
        if m:
            out.append(m.group(1))
    return out
