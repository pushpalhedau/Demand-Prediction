"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { usePresentation } from "@/lib/session";
import type { FilterOptions } from "@/lib/types";

function Select({
  label,
  value,
  onChange,
  options,
  render,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
  render?: (v: string) => string;
}) {
  const { t } = usePresentation();
  return (
    <label className="block text-xs font-medium text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 block w-full rounded-lg border border-line bg-canvas px-2.5 py-2 text-sm text-ink"
      >
        <option value="">{t("filter.all")}</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {render ? render(o) : o}
          </option>
        ))}
      </select>
    </label>
  );
}

function DateField({
  label,
  value,
  onChange,
  min,
  max,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  min?: string | null;
  max?: string | null;
}) {
  return (
    <label className="block text-xs font-medium text-muted">
      {label}
      <input
        type="date"
        min={min ?? undefined}
        max={max ?? undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 block w-full rounded-lg border border-line bg-canvas px-2.5 py-1.5 text-sm text-ink"
      />
    </label>
  );
}

/** The global filters. Options come from the account's own data; the city list follows the chosen region. */
export function FilterBar({
  regionLabel,
  dataRange,
}: {
  regionLabel: string | null;
  dataRange: { from: string | null; to: string | null };
}) {
  const { t, tv } = usePresentation();
  const { filters, update, reset, active } = useFilters();

  const options = useQuery({ queryKey: ["filters"], queryFn: () => api<FilterOptions>("/api/workspace/filters") });
  const cities = useQuery({
    queryKey: ["cities", filters.region],
    queryFn: () => api<string[]>("/api/workspace/cities", { params: { region: filters.region } }),
    enabled: Boolean(filters.region),
  });

  const o = options.data;
  const cityOptions = filters.region ? (cities.data ?? []) : (o?.cities ?? []);

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">{t("app.filters")}</h3>
      <div className="grid grid-cols-2 gap-3">
        <DateField label={t("filter.date_from")} value={filters.from} onChange={(v) => update({ from: v })} min={dataRange.from} max={dataRange.to} />
        <DateField label={t("filter.date_to")} value={filters.to} onChange={(v) => update({ to: v })} min={dataRange.from} max={dataRange.to} />
      </div>
      <Select
        label={regionLabel ?? t("filter.state")}
        value={filters.region}
        onChange={(v) => update({ region: v })}
        options={o?.regions ?? []}
      />
      <Select label={t("filter.city")} value={filters.city} onChange={(v) => update({ city: v })} options={cityOptions} />
      <Select label={t("filter.brand")} value={filters.brand} onChange={(v) => update({ brand: v })} options={o?.brands ?? []} />
      <Select
        label={t("filter.category")}
        value={filters.category}
        onChange={(v) => update({ category: v })}
        options={o?.categories ?? []}
        render={tv}
      />
      <Select
        label={t("filter.fuel")}
        value={filters.fuel}
        onChange={(v) => update({ fuel: v })}
        options={o?.fuel_types ?? []}
        render={tv}
      />
      {active && (
        <button onClick={reset} className="text-sm text-accent hover:underline">
          {t("app.reset_filters")}
        </button>
      )}
    </div>
  );
}
