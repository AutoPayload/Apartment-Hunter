"""Telegram notifications: instant alerts, price drops, daily digest, health warnings."""

from __future__ import annotations

import html
import logging
from typing import Any

import httpx

from ..models import Extraction, Listing, ScoreResult
from ..normalize import whatsapp_link

log = logging.getLogger(__name__)

SITE_LABELS = {
    "encuentra24": "Encuentra24", "casas24": "Casas24", "anuntico": "Anuntico",
    "inhauscr": "InHaus CR", "alquilacr": "AlquilaCR",
}
WA_MESSAGE = "Hola, vi su anuncio del apartamento ({url}). ¿Sigue disponible? ¿Incluye parqueo?"


def crc(value: int | None) -> str:
    return "precio ?" if value is None else f"₡{value:,.0f}".replace(",", ".")


def format_alert(listing: Listing, ex: Extraction, sc: ScoreResult, kind: str = "new",
                 old_price: int | None = None) -> str:
    e = html.escape
    head = {"new": f"🏠 <b>Tier {sc.tier}</b> · {sc.score} pts", "price_drop": "📉 <b>Bajó de precio</b>"}[kind]
    price = crc(listing.price_crc)
    if kind == "price_drop" and old_price:
        price = f"<s>{crc(old_price)}</s> → {price}"
    lines = [
        head,
        f"<b>{e(listing.title[:120])}</b>",
        f"💰 {price}" + (f" (${listing.price:,.0f})" if listing.currency == "USD" and listing.price else ""),
        f"📍 {e(ex.zone or listing.zone or listing.location_text or '?')}",
    ]
    facts = []
    if listing.bedrooms is not None:
        facts.append("estudio" if listing.bedrooms == 0 else f"{listing.bedrooms} hab")
    if listing.size_m2:
        facts.append(f"{listing.size_m2:.0f} m²")
    facts.append({"yes": "🚗 parqueo", "no": "sin parqueo", "unknown": "🚗 ¿parqueo?"}[ex.parking])
    lines.append(" · ".join(facts))
    lines.append("✅ " + e("; ".join(sc.reasons)))
    lines.append(f"🔗 <a href=\"{e(listing.url)}\">{SITE_LABELS.get(listing.site, listing.site)}</a>")
    return "\n".join(lines)


def buttons(listing_id: int, listing: Listing) -> dict[str, Any]:
    row = [
        {"text": "👍 Me interesa", "callback_data": f"st:{listing_id}:interested"},
        {"text": "🗑 Descartar", "callback_data": f"st:{listing_id}:discarded"},
    ]
    keyboard = [row]
    wa = whatsapp_link(listing.phone, WA_MESSAGE.format(url=listing.url))
    if wa:
        keyboard.append([{"text": "💬 WhatsApp al anunciante", "url": wa}])
    return {"inline_keyboard": keyboard}


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, dashboard_url: str = ""):
        if not token or not chat_id:
            raise SystemExit("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set (or use --dry-run).")
        self.api = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id
        self.dashboard_url = dashboard_url
        self.http = httpx.Client(timeout=20)

    def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self.http.post(f"{self.api}/{method}", json=payload)
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {data.get('description')}")
        return data

    def send_text(self, text: str, reply_markup: dict | None = None) -> None:
        payload: dict[str, Any] = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": True}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        self._call("sendMessage", payload)

    def alert(self, stored_id: int, listing: Listing, ex: Extraction, sc: ScoreResult, kind: str = "new",
              old_price: int | None = None) -> None:
        text = format_alert(listing, ex, sc, kind, old_price)
        markup = buttons(stored_id, listing)
        if listing.photos:
            try:
                self._call("sendPhoto", {"chat_id": self.chat_id, "photo": listing.photos[0],
                                         "caption": text[:1024], "parse_mode": "HTML", "reply_markup": markup})
                return
            except Exception as exc:  # bad image URL etc. -> plain message
                log.info("sendPhoto failed, sending text: %s", exc)
        self.send_text(text, markup)

    def digest(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        e = html.escape
        lines = [f"📋 <b>Resumen diario</b>: {len(rows)} opciones Tier B"]
        for r in rows[:30]:
            reason = (r.get("reasons") or [""])[0]
            lines.append(
                f"• <a href=\"{e(r['url'])}\">{e((r.get('title') or '')[:60])}</a>: "
                f"{crc(r.get('price_crc'))}, {e(r.get('zone') or '?')}. {e(reason)}"
            )
        if self.dashboard_url:
            lines.append(f"\n<a href=\"{e(self.dashboard_url)}?tier=B\">Abrir panel</a>")
        self.send_text("\n".join(lines))

    def health(self, message: str) -> None:
        self.send_text(f"⚠️ {html.escape(message)}")


class ConsoleNotifier:
    """Prints instead of sending. Used by --dry-run and tests (keeps a record in `sent`)."""

    def __init__(self, quiet: bool = False):
        self.sent: list[tuple[str, Any]] = []
        self.quiet = quiet

    def _out(self, text: str) -> None:
        if not self.quiet:
            print(text + "\n" + "-" * 60)

    def alert(self, stored_id, listing, ex, sc, kind="new", old_price=None) -> None:
        self.sent.append((kind, listing.key))
        self._out(format_alert(listing, ex, sc, kind, old_price))

    def digest(self, rows) -> None:
        self.sent.append(("digest", len(rows)))
        self._out(f"DIGEST: {len(rows)} rows")

    def health(self, message: str) -> None:
        self.sent.append(("health", message))
        self._out(f"HEALTH: {message}")
