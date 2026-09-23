-- Apartment Hunter core schema. Replaces the "apartment-alert-log" file in Drive.
-- Apply with: supabase db push   (or paste into the SQL editor)

create table if not exists public.listings (
  id            bigint generated always as identity primary key,
  site          text        not null,
  listing_id    text        not null,
  url           text        not null,
  title         text        not null default '',
  description   text        not null default '',
  location_text text        not null default '',
  zone          text,
  price_raw     text        not null default '',
  currency      text        check (currency in ('CRC', 'USD')),
  price_crc     integer,
  size_m2       numeric,
  bedrooms      smallint,
  phone         text,
  photos        jsonb       not null default '[]'::jsonb,
  photo_hash    text,
  posted_at     timestamptz,
  extraction    jsonb,                       -- Jev / keyword facts + confidences
  tier          text        check (tier in ('A', 'B', 'none', 'reject')),
  score         smallint    not null default 0,
  reasons       jsonb       not null default '[]'::jsonb,
  duplicate_of  bigint      references public.listings (id) on delete set null,
  status        text        not null default 'new'
                check (status in ('new', 'notified', 'interested', 'reviewed', 'discarded')),
  notified_at   timestamptz,
  first_seen    timestamptz not null default now(),
  last_seen     timestamptz not null default now(),
  unique (site, listing_id)
);

create index if not exists listings_tier_status_idx on public.listings (tier, status, first_seen desc);
create index if not exists listings_dupe_idx on public.listings (zone, price_crc) where duplicate_of is null;
create index if not exists listings_last_seen_idx on public.listings (last_seen desc);

create table if not exists public.price_history (
  id          bigint generated always as identity primary key,
  listing_id  bigint      not null references public.listings (id) on delete cascade,
  price_crc   integer     not null,
  seen_at     timestamptz not null default now()
);
create index if not exists price_history_listing_idx on public.price_history (listing_id, seen_at);

create table if not exists public.scrape_runs (
  id          bigint generated always as identity primary key,
  site        text        not null,
  started_at  timestamptz not null default now(),
  count       integer     not null default 0,
  new_count   integer     not null default 0,
  error       text
);
create index if not exists scrape_runs_site_idx on public.scrape_runs (site, started_at desc);

-- Personal project: only the service role (scraper, dashboard server) touches these tables.
-- RLS on with no policies = anon/authenticated keys can't read or write anything.
alter table public.listings      enable row level security;
alter table public.price_history enable row level security;
alter table public.scrape_runs   enable row level security;
