from datetime import datetime, timedelta, timezone

from hunter.adapters import get_adapter
from hunter.bot import handle_callback
from hunter.dedupe import average_hash, hamming
from hunter.extract.keywords import KeywordExtractor
from hunter.health import check_site
from hunter.notify import ConsoleNotifier
from hunter.pipeline import Deps, run_site
from hunter.store import MemoryStore


def deps_for(store, notifier, pages):
    """pages: site -> list of HTML strings returned on successive runs."""
    calls = {}

    def collect(adapter):
        i = calls.get(adapter.name, 0)
        calls[adapter.name] = i + 1
        seq = pages.get(adapter.name, [""])
        return adapter.parse(seq[min(i, len(seq) - 1)], adapter.urls()[0])

    return Deps(store=store, extractor=KeywordExtractor(), notifier=notifier, usd_crc_rate=505, collect=collect)


def test_new_listing_alerts_once(fixture_html):
    store, notifier = MemoryStore(), ConsoleNotifier(quiet=True)
    deps = deps_for(store, notifier, {"encuentra24": [fixture_html("encuentra24.html")]})
    adapter = get_adapter("encuentra24")

    first = run_site(adapter, deps)
    assert first.fetched == 5 and first.new == 5
    assert first.alerted == ["encuentra24:31000001"]

    second = run_site(adapter, deps)
    assert second.new == 0 and second.alerted == []
    assert [s for s in notifier.sent if s[0] == "new"] == [("new", "encuentra24:31000001")]
    row = next(r for r in store.rows.values() if r["listing_id"] == "31000001")
    assert row["status"] == "notified"


def test_price_drop_into_tier_a_alerts(fixture_html):
    html = fixture_html("encuentra24.html")
    cheaper = html.replace("$700", "$640")  # Zapote: 353,500 (B) -> 323,200 (A)
    store, notifier = MemoryStore(), ConsoleNotifier(quiet=True)
    deps = deps_for(store, notifier, {"encuentra24": [html, cheaper]})
    adapter = get_adapter("encuentra24")
    run_site(adapter, deps)
    result = run_site(adapter, deps)
    assert result.price_drops == ["encuentra24:31000002"]
    assert ("price_drop", "encuentra24:31000002") in notifier.sent
    assert (2, 323200) in store.history
    assert store.rows[2]["status"] == "notified"


def test_cross_site_duplicate_not_alerted_twice(fixture_html):
    store, notifier = MemoryStore(), ConsoleNotifier(quiet=True)
    deps = deps_for(store, notifier, {
        "encuentra24": [fixture_html("encuentra24.html")], "casas24": [fixture_html("casas24.html")],
    })
    run_site(get_adapter("encuentra24"), deps)
    result = run_site(get_adapter("casas24"), deps)
    assert result.duplicates == ["casas24:900111"]
    assert "casas24:900111" not in result.alerted
    assert "casas24:900222" in result.alerted


def test_fetch_error_is_logged_not_raised():
    store = MemoryStore()

    def broken(adapter):
        raise ConnectionError("down")

    deps = Deps(store=store, extractor=KeywordExtractor(), notifier=ConsoleNotifier(quiet=True),
                usd_crc_rate=505, collect=broken)
    result = run_site(get_adapter("anuntico"), deps)
    assert "down" in result.error
    assert store.runs[-1].count == 0 and store.runs[-1].error


def test_health_alerts_once_after_n_empty_runs():
    store = MemoryStore()
    t0 = datetime.now(timezone.utc)
    store.log_run("anuntico", t0, 4, 1, None)
    for i in range(1, 3):
        store.log_run("anuntico", t0 + timedelta(minutes=i), 0, 0, None)
    assert check_site(store, "anuntico", 3) is None
    store.log_run("anuntico", t0 + timedelta(minutes=3), 0, 0, "HTTP 403")
    msg = check_site(store, "anuntico", 3)
    assert msg and "403" in msg
    store.log_run("anuntico", t0 + timedelta(minutes=4), 0, 0, None)
    assert check_site(store, "anuntico", 3) is None  # not repeated


def test_digest_lists_tier_b(fixture_html):
    store = MemoryStore()
    deps = deps_for(store, ConsoleNotifier(quiet=True), {"alquilacr": [fixture_html("alquilacr.html")]})
    run_site(get_adapter("alquilacr"), deps)
    rows = store.digest(datetime.now(timezone.utc) - timedelta(hours=24))
    assert [r["listing_id"] for r in rows] == ["4521"]


def test_bot_callback_sets_status(fixture_html):
    store = MemoryStore()
    run_site(get_adapter("encuentra24"),
             deps_for(store, ConsoleNotifier(quiet=True), {"encuentra24": [fixture_html("encuentra24.html")]}))
    assert handle_callback(store, "st:1:discarded")
    assert store.rows[1]["status"] == "discarded"
    assert handle_callback(store, "st:1:hacked") is None
    assert handle_callback(store, "garbage") is None


def test_average_hash_is_stable():
    import io

    from PIL import Image

    def png(color_left, color_right):
        img = Image.new("RGB", (64, 64), color_left)
        img.paste(Image.new("RGB", (32, 64), color_right), (32, 0))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

    a, b = average_hash(png("white", "black")), average_hash(png("white", "black"))
    c = average_hash(png("black", "white"))
    assert hamming(a, b) == 0 and hamming(a, c) > 30
    assert average_hash(b"not an image") is None
