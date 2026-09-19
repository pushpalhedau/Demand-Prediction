"use client";

import { useQuery } from "@tanstack/react-query";
import { FilterX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { usePresentation } from "@/lib/session";
import type { FilterOptions } from "@/lib/types";
import { DateRangePicker } from "./date-range-picker";

const ALL = "__all__";

function FilterSelect({
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
    <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? "" : v)}>
      <SelectTrigger size="sm" className="h-9 min-w-[7.5rem] gap-2" aria-label={label}>
        <span className="text-muted-foreground text-xs">{label}</span>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{t("filter.all")}</SelectItem>
        {options.map((o) => (
          <SelectItem key={o} value={o}>
            {render ? render(o) : o}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

/** The global filters, applied to every dashboard. Options come from the account's own data. */
export function FilterToolbar({
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
    <div className="flex flex-wrap items-center gap-2" role="search" aria-label={t("app.filters")}>
      <DateRangePicker
        from={filters.from}
        to={filters.to}
        min={dataRange.from}
        max={dataRange.to}
        onChange={(r) => update(r)}
      />
      <FilterSelect label={regionLabel ?? t("filter.state")} value={filters.region} onChange={(v) => update({ region: v })} options={o?.regions ?? []} />
      <FilterSelect label={t("filter.city")} value={filters.city} onChange={(v) => update({ city: v })} options={cityOptions} />
      <FilterSelect label={t("filter.brand")} value={filters.brand} onChange={(v) => update({ brand: v })} options={o?.brands ?? []} />
      <FilterSelect label={t("filter.category")} value={filters.category} onChange={(v) => update({ category: v })} options={o?.categories ?? []} render={tv} />
      <FilterSelect label={t("filter.fuel")} value={filters.fuel} onChange={(v) => update({ fuel: v })} options={o?.fuel_types ?? []} render={tv} />
      {active && (
        <Button variant="ghost" size="sm" onClick={reset} className="text-muted-foreground h-9 gap-1.5">
          <FilterX className="size-4" /> {t("app.reset_filters")}
        </Button>
      )}
    </div>
  );
}
