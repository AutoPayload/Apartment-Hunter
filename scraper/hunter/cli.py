"""Command line entry point.

  hunter run --site encuentra24          one site (cron calls this, staggered per site)
  hunter run --all --dry-run             no Supabase writes, alerts printed instead of sent
  hunter run --all --dry-run --fixtures tests/fixtures   fully offline
  hunter probe --site anuntico           save page 1 to probes/ and show what was parsed
  hunter digest                          Tier B summary for the last 24 h
  hunter health                          warn about sites returning 0 listings
  hunter bot                             handle Telegram button taps (long-running)
  hunter schedule                        run everything on a timer (long-running, used by Docker)
  hunter test-alert                      send a sample alert to check Telegram setup
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .adapters import ADAPTERS, get_adapter
from .config import get_settings
from .extract import KeywordExtractor, build_extractor
from .health import check_site
from .http import PoliteClient
from .models import Extraction, Listing, ScoreResult
from .notify import ConsoleNotifier, TelegramNotifier
from .normalize import normalize
from .pipeline import Deps, run_site
from .store import MemoryStore, SupabaseStore

PROBE_DIR = Path.cwd() / "probes"


def _sites(args) -> list[str]:
    if args.all or not args.site:
        return list(ADAPTERS)
    return args.site


def cmd_run(args) -> int:
    s = get_settings()
    store = MemoryStore() if args.dry_run else SupabaseStore(s.supabase_url, s.supabase_key)
    notifier = ConsoleNotifier() if args.dry_run else TelegramNotifier(s.telegram_token, s.telegram_chat_id,
                                                                      s.dashboard_url)
    extractor = KeywordExtractor() if args.no_ai else build_extractor(s)
    client = PoliteClient(s.user_agent, delay=s.request_delay)

    if args.fixtures:
        fixture_dir = Path(args.fixtures)

        def collect(adapter):
            path = fixture_dir / f"{adapter.name}.html"
            if not path.exists():
                return []
            return adapter.parse(path.read_text(encoding="utf-8"), adapter.urls()[0])

        enrich = None
        photo = None
    else:
        def collect(adapter):
            return adapter.fetch(client)

        def enrich(adapter, listing):
            return adapter.enrich(client, listing)

        from .dedupe import photo_hash

        def photo(listing):
            return photo_hash(client, listing)

    deps = Deps(store=store, extractor=extractor, notifier=notifier, usd_crc_rate=s.usd_crc_rate,
                collect=collect, enrich=None if args.no_details else enrich, photo_hash=photo)
    failed = False
    try:
        for site in _sites(args):
            r = run_site(get_adapter(site), deps)
            failed |= r.error is not None
            print(f"[{site}] fetched={r.fetched} new={r.new} alerts={len(r.alerted)} "
                  f"price_drops={len(r.price_drops)} duplicates={len(r.duplicates)}"
                  + (f" ERROR={r.error}" if r.error else ""))
            if args.dry_run and isinstance(store, MemoryStore):
                for row in store.rows.values():
                    if row["site"] == site:
                        print(f"   {row['tier']:>6} {row['score']:>3} {row['price_crc'] or '-':>9} "
                              f"{(row['zone'] or '-')[:22]:<22} {row['title'][:60]}")
    finally:
        client.close()
    return 1 if failed else 0


def cmd_probe(args) -> int:
    s = get_settings()
    adapter = get_adapter(args.site)
    url = args.url or adapter.urls()[0]
    PROBE_DIR.mkdir(exist_ok=True)
    with PoliteClient(s.user_agent, delay=s.request_delay) as client:
        if not client.allowed(url):
            print(f"robots.txt disallows {url}. Pick another URL or drop the site.")
            return 1
        html = adapter.fetch_html(client, url)
    out = PROBE_DIR / f"{adapter.name}.html"
    out.write_text(html, encoding="utf-8")
    listings = [normalize(item, s.usd_crc_rate) for item in adapter.parse(html, url)]
    print(f"Saved {len(html):,} bytes to {out}")
    print(f"Parsed {len(listings)} listings from {url}")
    for item in listings[:10]:
        print(f"  {item.listing_id:<14} {item.price_crc or '-':>9} {item.zone or '-':<22} {item.title[:50]}")
        print(f"  {'':<14} {item.url}")
    if not listings:
        print("0 listings: open the saved HTML, find the listing cards and update the adapter's "
              "selectors / detail_url_pattern (or check DevTools > Network for a JSON API).")
    return 0 if listings else 1


def cmd_digest(args) -> int:
    s = get_settings()
    store = SupabaseStore(s.supabase_url, s.supabase_key)
    rows = store.digest(datetime.now(timezone.utc) - timedelta(hours=args.hours))
    notifier = ConsoleNotifier() if args.dry_run else TelegramNotifier(s.telegram_token, s.telegram_chat_id,
                                                                      s.dashboard_url)
    notifier.digest(rows)
    print(f"digest: {len(rows)} listings")
    return 0


def cmd_health(args) -> int:
    s = get_settings()
    store = SupabaseStore(s.supabase_url, s.supabase_key)
    notifier = ConsoleNotifier() if args.dry_run else TelegramNotifier(s.telegram_token, s.telegram_chat_id)
    problems = 0
    for site in ADAPTERS:
        msg = check_site(store, site, s.health_empty_runs)
        if msg:
            problems += 1
            notifier.health(msg)
    print(f"health: {problems} site(s) need attention")
    return 0


def cmd_bot(args) -> int:
    from .bot import run_bot

    s = get_settings()
    run_bot(SupabaseStore(s.supabase_url, s.supabase_key), s.telegram_token, s.telegram_chat_id)
    return 0


def cmd_schedule(args) -> int:
    from .scheduler import schedule_loop

    schedule_loop(args.interval, args.digest_hour)
    return 0


def cmd_test_alert(args) -> int:
    s = get_settings()
    listing = normalize(Listing(site="encuentra24", listing_id="demo", url="https://www.encuentra24.com/",
                                title="Apartamento de prueba en Curridabat", price_raw="₡340.000",
                                description="2 habitaciones, parqueo, seguridad 24/7. Tel 8888-8888"),
                        s.usd_crc_rate)
    ex = Extraction(parking="yes", unit_type="apartment", zone="Curridabat", security="yes")
    TelegramNotifier(s.telegram_token, s.telegram_chat_id).alert(
        0, listing, ex, ScoreResult(tier="A", score=85, reasons=["Mensaje de prueba"]))
    print("sent")
    return 0


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="hunter", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="scrape, score and notify")
    r.add_argument("--site", action="append", choices=list(ADAPTERS))
    r.add_argument("--all", action="store_true")
    r.add_argument("--dry-run", action="store_true", help="in-memory store, print alerts")
    r.add_argument("--fixtures", help="read <dir>/<site>.html instead of the network")
    r.add_argument("--no-ai", action="store_true", help="keyword extractor only")
    r.add_argument("--no-details", action="store_true", help="skip detail-page fetches")
    r.set_defaults(func=cmd_run)

    pr = sub.add_parser("probe", help="fetch page 1, save it, show parsed listings")
    pr.add_argument("--site", required=True, choices=list(ADAPTERS))
    pr.add_argument("--url")
    pr.set_defaults(func=cmd_probe)

    d = sub.add_parser("digest", help="send the Tier B daily digest")
    d.add_argument("--hours", type=int, default=24)
    d.add_argument("--dry-run", action="store_true")
    d.set_defaults(func=cmd_digest)

    h = sub.add_parser("health", help="alert on sites returning 0 listings")
    h.add_argument("--dry-run", action="store_true")
    h.set_defaults(func=cmd_health)

    sub.add_parser("bot", help="handle Telegram buttons").set_defaults(func=cmd_bot)

    sc = sub.add_parser("schedule", help="long-running loop: staggered runs, health, digest")
    sc.add_argument("--interval", type=int, default=20, help="minutes between runs of each site")
    sc.add_argument("--digest-hour", type=int, default=8, help="Costa Rica local hour for the digest")
    sc.set_defaults(func=cmd_schedule)
    sub.add_parser("test-alert", help="send a sample Telegram alert").set_defaults(func=cmd_test_alert)

    args = p.parse_args(argv)
    sys.exit(args.func(args))
