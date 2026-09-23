"""InHaus CR (inhauscr.com), a real-estate agency site (likely WordPress with a property theme).

UNVERIFIED: written without access to the live site. Theme markup such as Houzez or
RealHomes is covered by the selectors below. Run `hunter probe --site inhauscr` and adjust.
"""

from __future__ import annotations

from .base import Adapter, DetailSelectors, Selectors


class InHausCR(Adapter):
    name = "inhauscr"
    base_url = "https://www.inhauscr.com"
    search_urls = [
        "https://www.inhauscr.com/?s=&status=alquiler&type=apartamento&orderby=date&order=DESC",
    ]
    detail_url_pattern = r"inhauscr\.com/(?:propiedad|property|propiedades|listing|inmueble)/([^/?#]+)"
    selectors = Selectors(
        card=".item-listing-wrap, .rh_list_card, .property-item, .listing-item, article.property, article",
        link=".item-title a, .rh_list_card__details h3 a, h2 a, h3 a, a[href]",
        title=".item-title, .rh_list_card__details h3, h2, h3",
        price=".item-price, .price, .rh_price__price, [class*=price]",
        location=".item-address, .address, .rh_address, [class*=address], [class*=location]",
        description=".item-description, .rh_list_card__excerpt, [class*=excerpt], p",
    )
    detail_selectors = DetailSelectors(
        description="#property-description-wrap, .property-description, .rh_content, .entry-content",
        price=".item-price, .price, [class*=price]",
        location=".address, .item-address, [class*=address]",
        gallery=".property-gallery img, .rh_property__gallery img, [class*=gallery] img",
    )
