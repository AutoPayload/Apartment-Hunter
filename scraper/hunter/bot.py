"""Telegram button handler. Long-polls for Interested / Discard taps and updates Supabase."""

from __future__ import annotations

import logging
import time

import httpx

from .store import Store

log = logging.getLogger(__name__)

STATUS_LABELS = {"interested": "👍 Marcado: me interesa", "discarded": "🗑 Descartado"}


def handle_callback(store: Store, data: str) -> str | None:
    """Apply a callback like 'st:42:interested'. Returns the label to show, or None if invalid."""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "st" or parts[2] not in STATUS_LABELS or not parts[1].isdigit():
        return None
    store.set_status(int(parts[1]), parts[2])  # type: ignore[arg-type]
    return STATUS_LABELS[parts[2]]


def run_bot(store: Store, token: str, chat_id: str) -> None:
    api = f"https://api.telegram.org/bot{token}"
    http = httpx.Client(timeout=40)
    offset = 0
    log.info("bot: polling for button taps")
    while True:
        try:
            resp = http.get(f"{api}/getUpdates", params={"timeout": 30, "offset": offset,
                                                         "allowed_updates": '["callback_query"]'})
            updates = resp.json().get("result", [])
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("bot: poll failed: %s", exc)
            time.sleep(5)
            continue
        for upd in updates:
            offset = upd["update_id"] + 1
            cq = upd.get("callback_query")
            if not cq:
                continue
            msg = cq.get("message") or {}
            if str((msg.get("chat") or {}).get("id")) != str(chat_id):
                continue  # only your own chat may change statuses
            try:
                label = handle_callback(store, cq.get("data", ""))
            except Exception as exc:
                log.exception("bot: status update failed")
                label = None
                http.post(f"{api}/answerCallbackQuery",
                          json={"callback_query_id": cq["id"], "text": f"Error: {exc}"[:190]})
                continue
            http.post(f"{api}/answerCallbackQuery",
                      json={"callback_query_id": cq["id"], "text": label or "Acción desconocida"})
            if label and msg:
                # Replace the status buttons with the chosen status, keeping any link buttons.
                kb = (msg.get("reply_markup") or {}).get("inline_keyboard", [])
                links = [row for row in kb if all("url" in b for b in row)]
                http.post(f"{api}/editMessageReplyMarkup", json={
                    "chat_id": msg["chat"]["id"], "message_id": msg["message_id"],
                    "reply_markup": {"inline_keyboard": [[{"text": label, "callback_data": "noop"}], *links]},
                })
