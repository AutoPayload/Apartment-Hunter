"""Anuntico (anuntico.com), a general classifieds site with many private landlords.

UNVERIFIED: written without access to the live site. Run `hunter probe --site anuntico`
and adjust. Set HUNTER_URLS_ANUNTICO to your pre-filtered newest-first search URL.
"""

from __future__ import annotations

from .base import Adapter, Selectors


class Anuntico(Adapter):
    name = "anuntico"
    base_url = "https://www.anuntico.com"
    search_urls = [
        "https://www.anuntico.com/c/Alquiler-de-Apartamentos/San-Jose/",
        "https://www.anuntico.com/c/Alquiler-de-Apartamentos/Cartago/",
    ]
    # Ads look like /ad/<id>/<slug>.html or /<slug>-<id>.html
    detail_url_pattern = r"anuntico\.com/(?:ad/(\d{5,})|[^?#]*?-(\d{5,})\.html)"
    selectors = Selectors(
        card=".ad-item, .anuncio, .listing-item, .item-anuncio, li.ad, article",
        title=".ad-title, .titulo, h2, h3, a",
        price=".ad-price, .precio, [class*=price]",
        location=".ad-location, .ubicacion, [class*=location], [class*=provincia]",
        description=".ad-description, .descripcion, p",
        date=".ad-date, .fecha, time",
    )

