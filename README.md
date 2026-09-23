# Apartment Hunter

Finds rental apartments in Costa Rica that match your rules and pings you on Telegram
within minutes of them being posted.

```
Collect ─▶ Normalize ─▶ Dedupe ─▶ Classify (Jev) ─▶ Score ─▶ Notify ─▶ Review
5 sites     ₡/$, m²,     same site   parking, unit     your rules   Telegram   Next.js
page 1      rooms, tel   + cross-    type, zone, pets  in code,     alert /    dashboard
newest      zone         site        security, ...     not the AI   digest     on Vercel
```

| Part | Where | What |
|---|---|---|
| `scraper/` | Hostinger VPS (Docker) | Python package `hunter`: adapters, pipeline, Telegram bot, scheduler |
| `supabase/migrations/` | Supabase | `listings`, `price_history`, `scrape_runs`, `listings_view` |
| `web/` | Vercel | Review dashboard: cards, filters, status buttons |
| `deploy/` | VPS | Dockerfile + docker-compose (scheduler + bot) |

Sites: **Encuentra24, Casas24, Anuntico, InHaus CR, AlquilaCR**.

> ⚠️ **The site adapters have not been checked against the live sites yet.** They were written
> without network access to them, from each site's likely markup, JSON-LD and URL patterns, and
> are tested only against synthetic fixtures. Run `hunter probe` for each site once (step 5) and fix
> any that parse 0 listings.

---

## Rules (`scraper/hunter/scoring.py`)

| Result | When |
|---|---|
| **Reject** | a room or shared space, **or** no parking |
| **Tier A**: instant Telegram alert | ≤ ₡350,000 **and** a target zone **and** parking confirmed |
| **Tier B**: daily digest (08:00) | ₡350k–₡380k in a target zone, **or** Tier A price with parking unknown (ask the landlord), **or** no price |
| **Bonus points** | 24/7 security / gated (+10), pets (+8), utilities or condo fee included (+8), pool/gym (+5), furnished (+3), cheaper (up to +10) |

Target zones (`scraper/hunter/zones.py`): Curridabat (Granadilla, Tirrases, Pinares…), Zapote,
San Francisco de Dos Ríos, Tres Ríos (La Unión), San Antonio de Desamparados, Montes de Oca
(San Pedro, Los Yoses, Sabanilla…).

USD prices are converted with `USD_CRC_RATE` before any rule runs.

Also handled:
- **Price drops:** a listing you've already seen that gets ≥2% cheaper is re-scored; if it becomes Tier A you get a 📉 alert.
- **Cross-site duplicates:** the same apartment on two sites alerts only once. It's matched by near-identical first photo, exact price + bedrooms + m², a Jev "same unit?" check, or very similar text. The dashboard shows "también en N sitio(s)".
- **Health:** a site returning 0 listings 3 runs in a row triggers one ⚠️ Telegram message. This usually means the layout changed.

## AI step: Jev (TypeSafe AI)

Jev is a "System One" model. It answers typed questions (`Choice`, `Noul` yes/no, `Score`) in one
pass and returns a confidence for each answer. It doesn't generate text, so:

- **Code** extracts numbers: price and currency → CRC, m², bedrooms, phone, posted date (`normalize.py`).
- **Jev** classifies: parking, unit type, pets, security, utilities included, furnished, pool/gym, zone
  (`extract/jev.py`), and cross-site "same apartment?" (`Noul`).
- Answers below `JEV_MIN_CONFIDENCE` (0.6) become `unknown`. Keyword rules (`extract/keywords.py`)
  fill whatever Jev leaves unknown and replace Jev completely if `TYPESAFE_API_KEY` is empty or the API fails.
- Jev only runs on **new** listings, and it never decides pass/fail. `scoring.py` does that.

---

## Setup

### 1. Supabase
Apply the migrations: `supabase db push`, or paste `supabase/migrations/0001_listings.sql` and then
`0002_views.sql` into the SQL editor. RLS is on with no policies, so only the service-role key
(scraper and dashboard server) can read or write.

### 2. Telegram
1. Talk to **@BotFather** → `/newbot` → copy the token.
2. Send your bot any message, then get your chat id (e.g. from **@userinfobot**).

### 3. Config
```bash
cp .env.example .env   # fill in Supabase, Telegram, TYPESAFE_API_KEY, USD_CRC_RATE
```

### 4. Try it locally
```bash
cd scraper
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
pytest                                                       # 79 tests, offline
hunter run --all --dry-run --no-ai --fixtures tests/fixtures # whole pipeline on fixtures
hunter test-alert                                            # checks Telegram credentials
```

### 5. Check each site (once, from the VPS or your laptop)
```bash
hunter probe --site encuentra24     # saves probes/encuentra24.html and prints what was parsed
```
If a site parses 0 listings, or the wrong things:
1. Open the site in the browser with DevTools → **Network**. If results come from an XHR JSON
   endpoint, that's the most stable source: put it in `search_urls` and override `parse()`.
2. Otherwise open `probes/<site>.html`, find the listing card element, and update that adapter's
   `Selectors(...)` and `detail_url_pattern` in `scraper/hunter/adapters/<site>.py`.
3. Set up your own filtered, **newest-first** search in the browser (province, price, sort) and paste
   the URL into `.env` as `HUNTER_URLS_<SITE>=...`. No code change needed.
4. Check `/robots.txt`. `hunter` respects it and waits `REQUEST_DELAY_SECONDS` between requests
   to the same host. If a site fights scraping, drop it: four reliable sources beat five fragile ones.

If a site needs JavaScript, set `needs_js = True` on its adapter and build the image with
`--build-arg WITH_PLAYWRIGHT=1`.

### 6. Run on the VPS
```bash
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml logs -f
```
- `scheduler`: each site every 20 min, staggered (4 min apart); health hourly; digest at 08:00 CR.
- `bot`: handles the 👍 / 🗑 buttons on alerts and writes the status to Supabase.

One-off commands: `docker compose -f deploy/docker-compose.yml run --rm scheduler probe --site anuntico`.

Prefer host cron or n8n? Skip `scheduler` and call the same commands, for example:
```cron
*/20 * * * *  cd /opt/apartment-hunter && docker compose -f deploy/docker-compose.yml run --rm scheduler run --site encuentra24
4-59/20 * * * * ... run --site casas24     # and so on, offset per site
0 14 * * *    ... digest                   # 08:00 Costa Rica = 14:00 UTC (if the VPS clock is UTC)
15 * * * *    ... health
```

### 7. Dashboard on Vercel
Import the repo in Vercel and set **Root Directory = `web`**. Environment variables:
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DASHBOARD_PASSWORD`. Then put the URL in `.env` as
`DASHBOARD_URL` so the digest links to it.

Locally: `cd web && cp .env.example .env.local && npm install && npm run dev`.

---

## Adding a site
1. Create `scraper/hunter/adapters/<site>.py` with an `Adapter` subclass: `name`, `search_urls`,
   `detail_url_pattern`, and `Selectors`. Parsing tries JSON-LD first, then your card selectors,
   then any link matching `detail_url_pattern`.
2. Register it in `adapters/__init__.py`. Add a label in `notify/telegram.py` and `web/lib/types.ts`.
3. Save a page as `scraper/tests/fixtures/<site>.html` and add it to `tests/test_adapters.py`.

## Commands
```
hunter run --site X | --all [--dry-run] [--fixtures DIR] [--no-ai] [--no-details]
hunter probe --site X [--url URL]
hunter digest [--hours 24] [--dry-run]
hunter health [--dry-run]
hunter bot
hunter schedule [--interval 20] [--digest-hour 8]
hunter test-alert
```
