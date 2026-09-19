"use client";

import { X } from "lucide-react";
import type { ReactNode } from "react";
import { useFilters, type Filters } from "@/lib/filters";
import { formatDate } from "@/lib/format";
import { useMe, usePresentation } from "@/lib/session";

/**
 * Every dashboard opens the same way: what this is, the one-sentence answer, and where the numbers come from
 * (data date, currency) with the active scope as removable chips.
 */
export function PageHeading({ eyebrow, headline, meta = [], actions }: { eyebrow: string; headline: string; meta?: string[]; actions?: ReactNode }) {
  const { t, lang } = usePresentation();
  const { data: me } = useMe();
  const { filters, update } = useFilters();

  const chips: { label: string; clear: Partial<Filters> }[] = [];
  const add = (label: string, clear: Partial<Filters>) => chips.push({ label, clear });
  if (filters.from || filters.to) add(`${filters.from || "…"} → ${filters.to || "…"}`, { from: "", to: "" });
  if (filters.region) add(filters.region, { region: "" });
  if (filters.city) add(filters.city, { city: "" });
  if (filters.brand) add(filters.brand, { brand: "" });
  if (filters.category) add(filters.category, { category: "" });
  if (filters.fuel) add(filters.fuel, { fuel: "" });

  const asOf = me?.data_range.to ? t("ov.meta.asof", { date: formatDate(me.data_range.to, lang) }) : null;
  const facts = [asOf, me?.organisation.currency, ...meta].filter(Boolean) as string[];

  return (
    <header className="space-y-3">
      <p className="text-muted-foreground text-[11px] font-semibold tracking-[0.1em] uppercase">{eyebrow}</p>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <h1 className="font-heading max-w-3xl min-w-[16rem] flex-1 text-[1.65rem] leading-[1.2] font-semibold tracking-[-0.02em] text-balance sm:text-3xl">{headline}</h1>
        {actions && <div className="flex shrink-0 items-center gap-2 pt-1">{actions}</div>}
      </div>
      <div className="text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-2 text-xs">
        {facts.map((f, i) => (
          <span key={f} className="flex items-center gap-2">
            {i > 0 && <span aria-hidden className="bg-border size-[3px] rounded-full" />}
            {f}
          </span>
        ))}
        {chips.length > 0 && <span aria-hidden className="bg-border h-3 w-px" />}
        {chips.map((c) => (
          <button
            key={c.label}
            type="button"
            onClick={() => update(c.clear)}
            className="bg-secondary text-secondary-foreground hover:bg-accent inline-flex items-center gap-1 rounded-sm px-2 py-1 font-medium transition-colors"
            aria-label={`${t("scope.remove")}: ${c.label}`}
          >
            {c.label}
            <X className="size-3" aria-hidden />
          </button>
        ))}
      </div>
    </header>
  );
}
