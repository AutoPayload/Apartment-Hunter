import { SITE_LABELS, STATUS_LABELS, STATUSES, ZONES } from "@/lib/types";

export type FilterValues = {
  status: string;
  tier: string;
  site: string;
  zone: string;
  max: string;
  sort: string;
};

const select = "rounded-md border border-line bg-card px-2 py-1.5 text-sm";

export function Filters({ v }: { v: FilterValues }) {
  return (
    <form method="get" className="flex flex-wrap items-end gap-2">
      <label className="flex flex-col gap-1 text-xs text-muted">
        Estado
        <select name="status" defaultValue={v.status} className={select}>
          <option value="open">Pendientes</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
          <option value="all">Todos</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">
        Tier
        <select name="tier" defaultValue={v.tier} className={select}>
          <option value="AB">A + B</option>
          <option value="A">A</option>
          <option value="B">B</option>
          <option value="all">Todos</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">
        Sitio
        <select name="site" defaultValue={v.site} className={select}>
          <option value="">Todos</option>
          {Object.entries(SITE_LABELS).map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">
        Zona
        <select name="zone" defaultValue={v.zone} className={select}>
          <option value="">Todas</option>
          {ZONES.map((z) => (
            <option key={z} value={z}>
              {z}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">
        Máx ₡
        <input
          name="max"
          type="number"
          step={5000}
          defaultValue={v.max}
          placeholder="380000"
          className={`${select} w-28`}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">
        Orden
        <select name="sort" defaultValue={v.sort} className={select}>
          <option value="score">Puntaje</option>
          <option value="new">Más nuevos</option>
          <option value="price">Precio</option>
        </select>
      </label>
      <button className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white dark:text-black">Filtrar</button>
    </form>
  );
}
