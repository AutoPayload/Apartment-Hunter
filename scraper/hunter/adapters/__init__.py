"""Site adapters. Add a site: write a module with an Adapter subclass and register it here."""

from __future__ import annotations

from .alquilacr import AlquilaCR
from .anuntico import Anuntico
from .base import Adapter
from .casas24 import Casas24
from .encuentra24 import Encuentra24
from .inhauscr import InHausCR

ADAPTERS: dict[str, type[Adapter]] = {
    cls.name: cls for cls in (Encuentra24, Casas24, Anuntico, InHausCR, AlquilaCR)
}


def get_adapter(name: str) -> Adapter:
    try:
        return ADAPTERS[name]()
    except KeyError:
        raise SystemExit(f"Unknown site {name!r}. Known: {', '.join(ADAPTERS)}") from None
