"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceDot, ReferenceLine, XAxis, YAxis } from "recharts";
import { ChartFrame } from "@/components/charts/chart-frame";
import { FORECAST_STROKE, ForecastGradient, XMarker } from "@/components/charts/forecast-marks";
import { valueTip } from "@/components/charts/tooltip";
import { PanelSkeleton } from "@/components/data/chart-card";
import { MetricStrip, MetricStripSkeleton, type Metric } from "@/components/data/metric-strip";
import { PageHeading } from "@/components/data/page-heading";
import { Section } from "@/components/data/section";
import { QueryBoundary } from "@/components/data/query-boundary";
import { RichText } from "@/components/data/rich-text";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Checkbox } from "@/components/ui/checkbox";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Label } from "@/components/ui/label";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ApiError } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { monthName } from "@/lib/format";
import { useDashboardQuery } from "@/lib/query";
import { useFormat, usePresentation } from "@/lib/session";
import type { Dimension, Drivers, Measure, Tracking } from "@/lib/types";

export function ComparisonPage() {
  const { t } = usePresentation();
  const [measure, setMeasure] = useState<Measure>("units");
  const query = useDashboardQuery<Tracking>("cmp-tracking", "/api/comparison/tracking", { params: { measure } });

  const toggle = (
    <ToggleGroup type="single" variant="outline" size="sm" value={measure} onValueChange={(v) => v && setMeasure(v as Measure)} aria-label={t("cmp.measure")}>
      <ToggleGroupItem value="units">{t("sa.fc.units")}</ToggleGroupItem>
      <ToggleGroupItem value="revenue">{t("sa.fc.revenue")}</ToggleGroupItem>
    </ToggleGroup>
  );

  if (query.isError) {
    return (
      <div className="space-y-6">
        <PageHeading eyebrow={t("tab.comparison")} headline={t("tab.comparison")} actions={toggle} />
        <ErrorState message={query.error.message} reference={query.error instanceof ApiError ? query.error.reference : undefined} />
      </div>
    );
  }
  if (!query.data) {
    return (
      <div className="space-y-8">
        <PageHeading eyebrow={t("tab.comparison")} headline={t("cmp.subtitle")} actions={toggle} />
        <MetricStripSkeleton />
        <PanelSkeleton height={420} />
      </div>
    );
  }
  const d = query.data;
  if (d.status !== "ok" || !d.rows || !d.year) {
    return (
      <div className="space-y-8">
        <PageHeading eyebrow={t("tab.comparison")} headline={d.status === "no_sales" ? t("cmp.no_sales") : t("cmp.no_history")} actions={toggle} />
      </div>
    );
  }
  return (
    <div className="space-y-8">
      <Tracked data={d} measure={measure} toggle={toggle} />
      <DriversPanel measure={measure} />
    </div>
  );
}

function Tracked({ data: d, measure, toggle }: { data: Tracking; measure: Measure; toggle: React.ReactNode }) {
  const { t, lang } = usePresentation();
  const fmt = useFormat();
  const year = d.year!;
  const rows = d.rows!.map((r) => ({ ...r, label: monthName(r.month, lang) }));
  const isUnits = measure === "units";
  const total = (v: number) => (isUnits ? fmt.num(v) : fmt.money(v));
  const exact = (v: number) => (isUnits ? fmt.num(v) : fmt.money(v, false));
  const word = isUnits ? t("cmp.word.units") : t("cmp.word.revenue");
  const booked = rows.reduce((sum, r) => sum + (r.booked ?? 0), 0);
  const pct = d.projected_yoy_pct;

  const headline =
    pct == null || d.projected_total === undefined
      ? t("cmp.head.plain", { total: total(booked), word, year })
      : t(d.has_forecast ? "cmp.head.proj" : "cmp.head.done", { year, total: total(d.projected_total), word, pct: fmt.pct(pct, 1, true), prev: year - 1 });

  const metrics: Metric[] = [
    { label: d.has_forecast ? t("cmp.m.projected", { year }) : d.complete_year ? t("cmp.m.total", { year }) : t("cmp.m.todate", { year }), value: total(d.has_forecast || d.complete_year ? (d.projected_total ?? booked) : booked), note: word },
    { label: t("cmp.m.last", { year: year - 1 }), value: total(d.last_year_total ?? 0), note: word },
    { label: t("cmp.m.change"), value: pct == null ? t("val.na") : fmt.pct(pct, 1, true), delta: pct == null ? null : { text: `${year} ${t("cmp.vs", { year: year - 1 })}`, tone: pct >= 0 ? "positive" : "negative" } },
  ];

  const config = {
    last_year: { label: String(year - 1), color: "var(--chart-4)" },
    booked: { label: t("cmp.booked", { year }), color: "var(--chart-1)" },
    forecast: { label: t("cmp.forecast", { year }), color: "var(--brand-to)" },
  } satisfies ChartConfig;
  const lastBooked = [...rows].reverse().find((r) => r.booked != null);

  return (
    <>
      <PageHeading eyebrow={t("tab.comparison")} headline={headline} actions={toggle} />
      {d.comparable === false && <p className="text-foreground bg-warning/15 rounded-md px-3 py-2 text-sm">{t("cmp.not_comparable", { label: d.windows?.cur_label ?? "" })}</p>}
      <MetricStrip metrics={metrics} />
      <ChartFrame
        headline={t("cmp.chart.head", { year, prev: year - 1 })}
        description={
          <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="flex items-center gap-1.5"><span className="bg-chart-4 h-0.5 w-4 rounded-full" />{year - 1}</span>
            <span className="flex items-center gap-1.5"><span className="bg-chart-1 h-0.5 w-4 rounded-full" />{t("cmp.booked", { year })}</span>
            {d.has_forecast && <span className="flex items-center gap-1.5"><span className="brand-gradient h-0.5 w-4 rounded-full" />{t("cmp.forecast", { year })}</span>}
          </span>
        }
        csv={{ filename: `${measure}_year_over_year.csv`, headers: [t("ov.export.month"), String(year - 1), t("cmp.booked", { year }), t("cmp.forecast", { year })], rows: rows.map((r) => [r.label, r.last_year, r.booked, r.forecast]) }}
      >
        {(height) => (
          <ChartContainer config={config} className="w-full" style={{ height }}>
            <LineChart data={rows} margin={{ left: 0, right: 16, top: 12 }}>
              <ForecastGradient />
              <CartesianGrid vertical={false} strokeOpacity={0.6} />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={10} />
              <YAxis tickFormatter={(v: number) => (isUnits ? fmt.compact(v) : fmt.money(v))} tickLine={false} axisLine={false} width={isUnits ? 52 : 88} />
              <ChartTooltip cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }} content={<ChartTooltipContent formatter={valueTip(config, (v) => exact(v))} />} />
              <Line dataKey="last_year" stroke="var(--color-last_year)" strokeWidth={2} strokeDasharray="2 4" dot={{ r: 2.5 }} connectNulls />
              <Line dataKey="booked" stroke="var(--color-booked)" strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
              {d.has_forecast && <Line dataKey="forecast" stroke={FORECAST_STROKE} strokeWidth={2.75} strokeLinecap="round" dot={{ r: 2.5, fill: "var(--brand-to)", strokeWidth: 0 }} connectNulls />}
              {d.has_forecast && lastBooked && <ReferenceDot x={lastBooked.label} y={lastBooked.booked ?? 0} ifOverflow="visible" shape={(p: { cx?: number; cy?: number }) => <XMarker cx={p.cx} cy={p.cy} />} />}
            </LineChart>
          </ChartContainer>
        )}
      </ChartFrame>
    </>
  );
}

function DriversPanel({ measure }: { measure: Measure }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  const { filters } = useFilters();
  const [dimension, setDimension] = useState<Dimension>("store");
  const [onlySignificant, setOnlySignificant] = useState(true);
  const brandLocked = Boolean(filters.brand);
  const effective: Dimension = brandLocked ? "store" : dimension;

  const query = useDashboardQuery<Drivers>("cmp-drivers", "/api/comparison/drivers", {
    params: { measure, dimension: effective, only_significant: onlySignificant ? "true" : "false" },
    serverText: true,
  });
  const dimensionLabel = { store: t("cmp.dim.store"), brand: t("cmp.dim.brand"), category: t("cmp.dim.category") }[effective];
  const formatValue = (v: number) => (measure === "units" ? fmt.compact(v) : fmt.money(v));
  const signed = (v: number) => `${v >= 0 ? "+" : "−"}${formatValue(Math.abs(v))}`;

  return (
    <Section
      title={t("cmp.drivers.title", { dim: dimensionLabel.toLowerCase() })}
      description={t("cmp.drivers.caption")}
      action={
        <ToggleGroup type="single" variant="outline" size="sm" value={effective} disabled={brandLocked} onValueChange={(v) => v && setDimension(v as Dimension)} aria-label={t("cmp.break_down")}>
          <ToggleGroupItem value="store">{t("cmp.dim.store")}</ToggleGroupItem>
          <ToggleGroupItem value="brand">{t("cmp.dim.brand")}</ToggleGroupItem>
          <ToggleGroupItem value="category">{t("cmp.dim.category")}</ToggleGroupItem>
        </ToggleGroup>
      }
    >
      <QueryBoundary query={query} skeleton={<PanelSkeleton height={340} />}>
        {(d) => {
          if (d.status !== "ok" || !d.rows) return <EmptyState title={t("cmp.no_prior")} />;
          const config = { specific: { label: d.specific_label ?? "", color: "var(--chart-1)" } } satisfies ChartConfig;
          const rows = d.rows.map((r) => ({ ...r, label: `${r.significant ? "★ " : ""}${r.name}`, fill: r.specific >= 0 ? "var(--success)" : "var(--destructive)" }));
          const showFilter = (d.n_significant ?? 0) >= 3;
          return (
            <div className="space-y-5">
              {showFilter && (
                <div className="flex items-center gap-2">
                  <Checkbox id="only-sig" checked={onlySignificant} onCheckedChange={(v) => setOnlySignificant(v === true)} />
                  <Label htmlFor="only-sig" className="text-sm font-normal">
                    {t("cmp.only_sig", { n: d.n_significant ?? 0, dim: dimensionLabel.toLowerCase() })}
                  </Label>
                </div>
              )}
              <ChartContainer config={config} className="w-full" style={{ height: Math.max(260, 32 * rows.length + 60) }}>
                <BarChart data={rows} layout="vertical" margin={{ left: 0, right: 24, top: 8 }}>
                  <CartesianGrid horizontal={false} strokeOpacity={0.6} />
                  <XAxis type="number" tickFormatter={(v: number) => formatValue(v)} tickLine={false} axisLine={false} />
                  <YAxis dataKey="label" type="category" tickLine={false} axisLine={false} width={200} interval={0} tick={{ fontSize: 12 }} />
                  <ReferenceLine x={0} stroke="var(--muted-foreground)" />
                  <ChartTooltip
                    cursor={{ fill: "var(--muted)", opacity: 0.5 }}
                    content={
                      <ChartTooltipContent
                        hideLabel
                        formatter={(_, __, item) => {
                          const r = item.payload as (typeof rows)[number];
                          return (
                            <div className="grid gap-1">
                              <p className="font-medium">{r.name}</p>
                              <p className="text-muted-foreground">
                                {d.specific_label}: <span className="text-foreground tabular">{signed(r.specific)}</span>
                              </p>
                              <p className="text-muted-foreground">
                                {t("cmp.total_change")}: <span className="text-foreground tabular">{signed(r.total)}</span>
                              </p>
                            </div>
                          );
                        }}
                      />
                    }
                  />
                  <Bar dataKey="specific" radius={3} barSize={16}>
                    {rows.map((r) => (
                      <Cell key={r.name} fill={r.fill} fillOpacity={r.significant || !showFilter ? 1 : 0.55} />
                    ))}
                  </Bar>
                </BarChart>
              </ChartContainer>
              <p className="text-muted-foreground text-xs">
                {t("cmp.axis", { label: d.specific_label ?? "", word: measure === "units" ? t("cmp.word.units") : t("cmp.word.revenue") })}
                {(d.n_significant ?? 0) > 0 && ` ${t("cmp.star", { dim: dimensionLabel.toLowerCase() })}`}
              </p>
              {d.sentences && d.sentences.length > 0 && (
                <ol className="divide-y border-t">
                  {d.sentences.map((line, i) => (
                    <li key={i} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-x-4 py-4">
                      <span className="font-heading tabular text-muted-foreground/60 text-lg leading-none font-semibold">{String(i + 1).padStart(2, "0")}</span>
                      <p className="text-muted-foreground max-w-3xl text-sm leading-relaxed">
                        <RichText text={line} />
                      </p>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          );
        }}
      </QueryBoundary>
    </Section>
  );
}
