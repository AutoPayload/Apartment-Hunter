-- Dashboard view: days on market and last price change per listing.

create or replace view public.listings_view
with (security_invoker = true) as
select
  l.*,
  (extract(epoch from (l.last_seen - l.first_seen)) / 86400)::int as days_on_market,
  ph.first_price_crc,
  case when ph.first_price_crc is not null and l.price_crc < ph.first_price_crc
       then ph.first_price_crc - l.price_crc end as price_drop_crc,
  d.dup_count
from public.listings l
left join lateral (
  select price_crc as first_price_crc
  from public.price_history h
  where h.listing_id = l.id
  order by h.seen_at asc
  limit 1
) ph on true
left join lateral (
  select count(*)::int as dup_count
  from public.listings d
  where d.duplicate_of = l.id
) d on true;
