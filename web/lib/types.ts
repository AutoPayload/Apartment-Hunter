export type Tier = "A" | "B" | "none" | "reject";
export type Status = "new" | "notified" | "interested" | "reviewed" | "discarded";

export interface Listing {
  id: number;
  site: string;
  listing_id: string;
  url: string;
  title: string;
  description: string;
  location_text: string;
  zone: string | null;
  price_raw: string;
  currency: "CRC" | "USD" | null;
  price_crc: number | null;
  size_m2: number | null;
  bedrooms: number | null;
  phone: string | null;
  photos: string[];
  extraction: { parking?: string; unit_type?: string; source?: string } | null;
  tier: Tier | null;
  score: number;
  reasons: string[];
  duplicate_of: number | null;
  status: Status;
  first_seen: string;
  last_seen: string;
  posted_at: string | null;
  days_on_market: number | null;
  first_price_crc: number | null;
  price_drop_crc: number | null;
  dup_count: number | null;
}

export const SITE_LABELS: Record<string, string> = {
  encuentra24: "Encuentra24",
  casas24: "Casas24",
  anuntico: "Anuntico",
  inhauscr: "InHaus CR",
  alquilacr: "AlquilaCR",
};

export const ZONES = [
  "Curridabat",
  "Zapote",
  "San Francisco de Dos Ríos",
  "Tres Ríos",
  "San Antonio de Desamparados",
  "Montes de Oca",
];

export const STATUSES: Status[] = ["new", "notified", "interested", "reviewed", "discarded"];

export const STATUS_LABELS: Record<Status, string> = {
  new: "Nuevo",
  notified: "Notificado",
  interested: "Me interesa",
  reviewed: "Revisado",
  discarded: "Descartado",
};
