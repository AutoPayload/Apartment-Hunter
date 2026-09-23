"use client";

import { useTransition } from "react";

import { setStatus } from "@/app/actions";
import { STATUS_LABELS, type Status } from "@/lib/types";

const ACTIONS: { status: Status; label: string; className: string }[] = [
  { status: "interested", label: "👍 Me interesa", className: "border-accent text-accent" },
  { status: "reviewed", label: "✓ Revisado", className: "border-line text-ink" },
  { status: "discarded", label: "🗑 Descartar", className: "border-line text-muted" },
];

export function StatusButtons({ id, status }: { id: number; status: Status }) {
  const [pending, startTransition] = useTransition();
  return (
    <div className="flex flex-wrap items-center gap-2">
      {ACTIONS.map((a) => (
        <button
          key={a.status}
          disabled={pending || status === a.status}
          onClick={() => startTransition(() => setStatus(id, a.status))}
          className={`rounded-md border px-2.5 py-1 text-xs font-medium transition disabled:opacity-40 ${a.className}`}
        >
          {a.label}
        </button>
      ))}
      <span className="text-xs text-muted">{pending ? "Guardando…" : STATUS_LABELS[status]}</span>
    </div>
  );
}
