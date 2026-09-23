"""Casas24 (casas24.com/costa-rica-es).

UNVERIFIED: written without access to the live site. Run `hunter probe --site casas24`
and adjust. Set HUNTER_URLS_CASAS24 to your pre-filtered newest-first search URL.
"""

from __future__ import annotations

from .base import Adapter, Selectors


class Casas24(Adapter):
    name = "casas24"
    base_url = "https://www.casas24.com"
    search_urls = [
        "https://www.casas24.com/costa-rica-es/alquiler/apartamentos/san-jose?orden=recientes",
    ]
    # Detail pages: a path segment containing a numeric id (e.g. ...-apartamento-curridabat-900111).
    detail_url_pattern = r"casas24\.com/costa-rica-es/[^?#]+/[^/?#]*\d{4,}[^/?#]*/?(?:[?#]|$)"
    id_pattern = r"(\d{4,})/?(?:[?#]|$)"
    selectors = Selectors(
        card=".property-card, .listing-card, .card-property, article[class*=propert], li[class*=propert], article",
        title="[class*=title], h2, h3",
        price="[class*=price], [class*=precio]",
        location="[class*=location], [class*=address], [class*=ubicacion]",
    )
