"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";
import { Panel, PanelSkeleton } from "@/components/data/chart-card";
import { PageHeader } from "@/components/data/page-header";
import { QueryBoundary } from "@/components/data/query-boundary";
import { EmptyState } from "@/components/data/states";
import { RichText } from "@/components/data/rich-text";
import { valueTip } from "@/components/charts/tooltip";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Label } from "@/components/ui/label";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useFilters } from "@/lib/filters";
import { monthName } from "@/lib/format";
import { useDashboardQuery } from "@/lib/query";
import { useFormat, usePresentation } from "@/lib/session";
import type { Dimension, Drivers, Measure, Tracking } from "@/lib/types";

export function ComparisonPage() {
  const { t } = usePresentation();
  const [measure, setMeasure] = useState<Measure>("units");
  return (
    <>
      <PageHeader
        title={t("tab.comparison")}
        description={t("cmp.subtitle")}
        actions={
          <ToggleGroup type="single" variant="outline" size="sm" value={measure} onValueChange={(v) => v && setMeasure(v as Measure)} aria-label={t("cmp.measure")}>
            <ToggleGroupItem value="units">{t("sa.fc.units")}</ToggleGroupItem>
            <ToggleGroupItem value="revenue">{t("sa.fc.revenue")}</ToggleGroupItem>
          </ToggleGroup>
        }
      />
      <TrackingPanel measure={measure} />
      <DriversPanel measure={measure} />
    </>
  );
}

function TrackingPanel({ measure }: { measure: Measure }) {
  const { t, lang } = usePresentation();
  const fmt = useFormat();
  const query = useDashboardQuery<Tracking>("cmp-tracking", "/api/comparison/tracking", { params: { measure } });
  const value = (v: number) => (measure === "units" ? fmt.num(v) : fmt.money(v, false));

  return (
    <QueryBoundary query={query} skeleton={<PanelSkeleton height={420} />}>
      {(d) => {
        if (d.status !== "ok" || !d.rows || !d.year) {
          return <EmptyState title={d.status === "no_sales" ? t("cmp.no_sales") : t("cmp.no_history")} />;
        }
        const year = d.year;
        const config = {
          last_year: { label: String(year - 1), color: "var(--chart-4)" },
          booked: { label: t("cmp.booked", { year }), color: "var(--chart-1)" },
          forecast: { label: t("cmp.forecast", { year }), color: "var(--chart-3)" },
        } satisfies ChartConfig;
        const rows = d.rows.map((r) => ({ ...r, label: monthName(r.month, lang) }));
        const measureWord = measure === "units" ? t("cmp.word.units") : t("cmp.word.revenue");
        const headline =
          d.projected_total === undefined
            ? null
            : t(d.has_forecast ? "cmp.head.projected" : d.complete_year ? "cmp.head.full" : "cmp.head.todate", {
                total: measure === "units" ? fmt.compact(d.projected_total) : fmt.money(d.projected_total),
                word: measureWord,
                year,
              });

        return (
          <div className="space-y-4">
            {d.comparable === false && (
              <Alert>
                <AlertDescription>{t("cmp.not_comparable", { label: d.windows?.cur_label ?? "" })}</AlertDescription>
              </Alert>
            )}
            <Panel
              title={t("cmp.trend.title", { year, word: measureWord })}
              description={d.has_forecast ? t("cmp.trend.caption_fc", { year }) : t("cmp.trend.caption")}
              action={
                headline && (
                  <p className="text-right text-sm font-medium">
                    {headline}
                    {d.projected_yoy_pct != null && (
                      <span className={d.projected_yoy_pct < 0 ? "text-destructive" : "text-success"}>
                        {" · "}
                        {fmt.pct(d.projected_yoy_pct, 1, true)} {t("cmp.vs", { year: year - 1 })}
                      </span>
                    )}
                  </p>
                )
              }
            >
              <ChartContainer config={config} className="h-[340px] w-full">
                <LineChart data={rows} margin={{ left: 4, right: 12, top: 8 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
                  <YAxis tickFormatter={(v: number) => (measure === "units" ? fmt.compact(v) : fmt.money(v))} tickLine={false} axisLine={false} width={measure === "units" ? 52 : 84} />
                  <ChartTooltip content={<ChartTooltipContent formatter={valueTip(config, (v) => value(v))} />} />
                  <ChartLegend content={<ChartLegendContent />} />
                  <Line dataKey="last_year" stroke="var(--color-last_year)" strokeWidth={2} strokeDasharray="2 4" dot={{ r: 3 }} connectNulls />
                  <Line dataKey="booked" stroke="var(--color-booked)" strokeWidth={2.5} dot={{ r: 3.5 }} connectNulls />
                  {d.has_forecast && <Line dataKey="forecast" stroke="var(--color-forecast)" strokeWidth={2.25} strokeDasharray="6 4" dot={{ r: 3 }} connectNulls />}
                </LineChart>
              </ChartContainer>
            </Panel>
          </div>
        );
      }}
    </QueryBoundary>
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
    <Panel
      title={t("cmp.drivers.title", { dim: dimensionLabel.toLowerCase() })}
      description={t("cmp.drivers.caption")}
      action={
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={effective}
          disabled={brandLocked}
          onValueChange={(v) => v && setDimension(v as Dimension)}
          aria-label={t("cmp.break_down")}
        >
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
                  <CartesianGrid horizontal={false} />
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
                <ul className="space-y-2 border-t pt-4 text-sm leading-relaxed">
                  {d.sentences.map((line, i) => (
                    <li key={i} className="text-muted-foreground flex gap-2">
                      <span aria-hidden className="bg-muted-foreground/50 mt-2 size-1 shrink-0 rounded-full" />
                      <span>
                        <RichText text={line} />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        }}
      </QueryBoundary>
    </Panel>
  );
}
