import { Filters, type FilterValues } from "@/components/Filters";
import { ListingCard } from "@/components/ListingCard";
import { db } from "@/lib/supabase";
import type { Listing } from "@/lib/types";

export const dynamic = "force-dynamic";

type Params = { [key: string]: string | string[] | undefined };

function str(p: Params, key: string, fallback = ""): string {
  const v = p[key];
  return typeof v === "string" ? v : fallback;
}

export default async function Home({ searchParams }: { searchParams: Promise<Params> }) {
  const p = await searchParams;
  const v: FilterValues = {
    status: str(p, "status", "open"),
    tier: str(p, "tier", "AB"),
    site: str(p, "site"),
    zone: str(p, "zone"),
    max: str(p, "max"),
    sort: str(p, "sort", "score"),
  };

  let q = db().from("listings_view").select("*").is("duplicate_of", null).limit(200);
  if (v.status === "open") q = q.in("status", ["new", "notified", "interested"]);
  else if (v.status !== "all") q = q.eq("status", v.status);
  if (v.tier === "AB") q = q.in("tier", ["A", "B"]);
  else if (v.tier !== "all") q = q.eq("tier", v.tier);
  if (v.site) q = q.eq("site", v.site);
  if (v.zone) q = q.eq("zone", v.zone);
  if (v.max && Number(v.max) > 0) q = q.lte("price_crc", Number(v.max));
  if (v.sort === "price") q = q.order("price_crc", { ascending: true, nullsFirst: false });
  else if (v.sort === "new") q = q.order("first_seen", { ascending: false });
  else q = q.order("score", { ascending: false }).order("first_seen", { ascending: false });

  const { data, error } = await q;
  const listings = (data ?? []) as Listing[];

  return (
    <main className="mx-auto max-w-5xl px-4 py-6">
      <header className="mb-5 flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Apartment Hunter</h1>
        <p className="text-sm text-muted">
          {listings.length} {listings.length === 1 ? "anuncio" : "anuncios"}
        </p>
      </header>
      <div className="mb-5">
        <Filters v={v} />
      </div>
      {error && (
        <p className="mb-4 rounded-lg border border-red-400 p-3 text-sm text-red-600">
          Error de Supabase: {error.message}
        </p>
      )}
      <section className="flex flex-col gap-4">
        {listings.map((l) => (
          <ListingCard key={l.id} l={l} />
        ))}
        {!error && listings.length === 0 && (
          <p className="rounded-lg border border-dashed border-line p-8 text-center text-muted">
            Nada pendiente con estos filtros.
          </p>
        )}
      </section>
    </main>
  );
}
