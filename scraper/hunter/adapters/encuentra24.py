"""Encuentra24 (encuentra24.com/costa-rica-es), probably the biggest source.

UNVERIFIED: written without access to the live site. Run `hunter probe --site encuentra24`
on the VPS and adjust the selectors / URL below. In DevTools > Network check whether the
results come from an XHR JSON endpoint; if so, set `search_urls` to it and override `parse`.
"""

from __future__ import annotations

from .base import Adapter, DetailSelectors, Selectors


class Encuentra24(Adapter):
    name = "encuentra24"
    base_url = "https://www.encuentra24.com"
    # Apartments for rent, newest first, max ₡380k. Paste your own filtered URL into
    # HUNTER_URLS_ENCUENTRA24 if this one doesn't filter the way you want.
    search_urls = [
        "https://www.encuentra24.com/costa-rica-es/bienes-raices-alquiler-apartamentos/san-jose"
        "?q=f_price.-380000|f_currency.crc&sort=f_added&dir=desc",
        "https://www.encuentra24.com/costa-rica-es/bienes-raices-alquiler-apartamentos/cartago"
        "?q=f_price.-380000|f_currency.crc&sort=f_added&dir=desc",
    ]
    detail_url_pattern = r"encuentra24\.com/costa-rica-es/bienes-raices-alquiler-[^/?#]+/[^?#]*?(\d{6,})(?:[/?#]|$)"
    selectors = Selectors(
        card="div.d3-ad-tile, article.ann-box-teaser, [data-adid], .ann-box",
        link="a.d3-ad-tile__description, a[href*='bienes-raices-alquiler'], a[href]",
        title=".d3-ad-tile__title, .ann-box-title, h2, h3",
        price=".d3-ad-tile__price, .ann-price, [class*=price]",
        location=".d3-ad-tile__location, .ann-box-location, [class*=location]",
        description=".d3-ad-tile__short-description, .ann-box-desc, [class*=description]",
        image="img",
        date=".d3-ad-tile__date, .ann-box-date, time",
    )
    detail_selectors = DetailSelectors(
        description=".d3-property__description, .ad-description, .d3-ad-detail__description, [itemprop=description]",
        price=".d3-property-headline__price, .ad-price, [class*=price]",
        location=".d3-property-headline__location, .ad-location, [class*=location]",
        gallery=".d3-gallery img, .ad-gallery img, [class*=gallery] img",
    )
