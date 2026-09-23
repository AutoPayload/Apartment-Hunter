"""AlquilaCR (alquilacr.com), a rentals-only site.

UNVERIFIED: written without access to the live site. Run `hunter probe --site alquilacr`
and adjust. Set HUNTER_URLS_ALQUILACR to your pre-filtered newest-first search URL.
"""

from __future__ import annotations

from .base import Adapter, Selectors


class AlquilaCR(Adapter):
    name = "alquilacr"
    base_url = "https://www.alquilacr.com"
    search_urls = [
        "https://www.alquilacr.com/alquiler/apartamentos/san-jose/?orden=nuevos",
    ]
    detail_url_pattern = r"alquilacr\.com/(?:propiedad|property|anuncio|inmueble)/[^/?#]+"
    id_pattern = r"-(\d{3,})/?(?:[?#]|$)"
    selectors = Selectors(
        card=".property-item, .listing-item, .item-listing-wrap, .card, article",
        title="[class*=title], h2, h3",
        price="[class*=price], [class*=precio]",
        location="[class*=location], [class*=address], [class*=ubicacion]",
    )
