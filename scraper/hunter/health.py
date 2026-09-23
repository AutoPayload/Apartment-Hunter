"""Layout-change detector: a site that returns 0 listings N runs in a row is probably broken."""

from __future__ import annotations

from .store import Store


def check_site(store: Store, site: str, empty_runs: int) -> str | None:
    """Message if the site just became broken (so you're told once, not every hour)."""
    runs = store.recent_runs(site, empty_runs + 1)
    if len(runs) < empty_runs:
        return None
    latest = runs[:empty_runs]
    if not all(r.count == 0 for r in latest):
        return None
    before = runs[empty_runs] if len(runs) > empty_runs else None
    if before is not None and before.count == 0:
        return None  # already reported
    last_error = next((r.error for r in latest if r.error), None)
    msg = f"{site}: 0 anuncios en las últimas {empty_runs} corridas. Posible cambio de diseño del sitio."
    if last_error:
        msg += f" Último error: {last_error[:200].rstrip('.')}."
    return msg + f" Revisar con: hunter probe --site {site}"
