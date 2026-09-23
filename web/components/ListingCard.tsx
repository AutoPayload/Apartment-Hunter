import { ago, crc, whatsappLink } from "@/lib/format";
import { SITE_LABELS, type Listing } from "@/lib/types";

import { StatusButtons } from "./StatusButtons";

const TIER_STYLE: Record<string, string> = {
  A: "bg-emerald-600 text-white",
  B: "bg-amber-500 text-black",
  none: "bg-zinc-400 text-black",
  reject: "bg-zinc-600 text-white",
};

const PARKING: Record<string, string> = { yes: "🚗 Parqueo", no: "Sin parqueo", unknown: "🚗 ¿Parqueo?" };

export function ListingCard({ l }: { l: Listing }) {
  const photo = l.photos?.[0];
  const wa = whatsappLink(l.phone, l.url);
  const facts = [
    l.bedrooms == null ? null : l.bedrooms === 0 ? "Estudio" : `${l.bedrooms} hab`,
    l.size_m2 ? `${Math.round(l.size_m2)} m²` : null,
    PARKING[l.extraction?.parking ?? "unknown"],
  ].filter(Boolean);

  return (
    <article className="flex flex-col overflow-hidden rounded-xl border border-line bg-card sm:flex-row">
      <a href={l.url} target="_blank" rel="noreferrer" className="block shrink-0 sm:w-56">
        {photo ? (
          <img src={photo} alt="" loading="lazy" className="h-48 w-full bg-line object-cover sm:h-full" />
        ) : (
          <div className="flex h-48 w-full items-center justify-center bg-line text-muted sm:h-full">Sin foto</div>
        )}
      </a>
      <div className="flex min-w-0 flex-1 flex-col gap-2 p-4">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {l.tier && <span className={`rounded px-1.5 py-0.5 font-bold ${TIER_STYLE[l.tier]}`}>Tier {l.tier}</span>}
          <span className="font-semibold tabular-nums">{l.score} pts</span>
          <span className="text-muted">
            {SITE_LABELS[l.site] ?? l.site} · {ago(l.first_seen)}
            {l.days_on_market ? ` · ${l.days_on_market} ${l.days_on_market === 1 ? "día" : "días"} publicado` : ""}
          </span>
          {l.dup_count ? <span className="text-muted">· también en {l.dup_count} sitio(s)</span> : null}
        </div>
        <h2 className="text-base leading-snug font-semibold">
          <a href={l.url} target="_blank" rel="noreferrer" className="hover:underline">
            {l.title || "(sin título)"}
          </a>
        </h2>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-xl font-bold tabular-nums">{crc(l.price_crc)}</span>
          {l.currency === "USD" && <span className="text-sm text-muted">{l.price_raw}</span>}
          {l.price_drop_crc ? (
            <span className="text-sm font-medium text-emerald-600">
              ↓ {crc(l.price_drop_crc)} (antes {crc(l.first_price_crc)})
            </span>
          ) : null}
        </div>
        <p className="text-sm text-muted">
          📍 {l.zone ?? l.location_text ?? "?"} {facts.length ? `· ${facts.join(" · ")}` : ""}
        </p>
        {l.reasons?.length ? (
          <ul className="flex flex-wrap gap-1.5">
            {l.reasons.map((r) => (
              <li key={r} className="rounded-full border border-line px-2 py-0.5 text-xs">
                {r}
              </li>
            ))}
          </ul>
        ) : null}
        {l.description && <p className="line-clamp-2 text-sm text-muted">{l.description}</p>}
        <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-1">
          <StatusButtons id={l.id} status={l.status} />
          <div className="flex gap-3 text-sm">
            {wa && (
              <a href={wa} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">
                WhatsApp
              </a>
            )}
            <a href={l.url} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">
              Ver anuncio ↗
            </a>
          </div>
        </div>
      </div>
    </article>
  );
}
