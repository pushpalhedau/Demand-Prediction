"use client";

import { useMemo, type ReactNode } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, ReferenceDot, XAxis, YAxis } from "recharts";
import { ChartFrame } from "@/components/charts/chart-frame";
import { FORECAST_STROKE, ForecastGradient, XMarker } from "@/components/charts/forecast-marks";
import { bridge, joinSeries } from "@/components/charts/series";
import { valueTip } from "@/components/charts/tooltip";
import { MetricStrip, type Metric } from "@/components/data/metric-strip";
import { PageHeading } from "@/components/data/page-heading";
import { PanelSkeleton } from "@/components/data/chart-card";
import { RankedBars } from "@/components/data/ranked-bars";
import { Section } from "@/components/data/section";
import { ErrorState } from "@/components/data/states";
import { Skeleton } from "@/components/ui/skeleton";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { ApiError } from "@/lib/api";
import { formatMonth } from "@/lib/format";
import { useFormat, usePresentation } from "@/lib/session";
import type { Glance as GlanceData, Point } from "@/lib/types";
import { useGlance } from "./queries";

const sum = (points: Point[]) => points.reduce((total, p) => total + (p.y ?? 0), 0);
const last = <T,>(items: T[], n: number) => items.slice(Math.max(0, items.length - n));

export function Glance({ nav }: { nav: ReactNode }) {
  const query = useGlance();
  const { t } = usePresentation();
  const fmt = useFormat();

  if (query.isError) {
    return (
      <div className="space-y-6">
        {nav}
        <ErrorState message={query.error.message} reference={query.error instanceof ApiError ? query.error.reference : undefined} />
      </div>
    );
  }
  if (!query.data) {
    return (
      <div className="space-y-6">
        {nav}
        <Skeleton className="h-24 w-full max-w-3xl" />
        <Skeleton className="h-32 w-full" />
        <PanelSkeleton height={380} />
      </div>
    );
  }

  const data = query.data;
  const k = data.kpis;
  const revDelta = k.total_revenue_delta;
  const headline =
    (revDelta === null
      ? t("ov.head.nodelta", { rev: fmt.money(k.total_revenue), units: fmt.num(k.total_sales) })
      : Math.abs(revDelta) < 0.05
        ? t("ov.head.flat", { units: fmt.num(k.total_sales) })
        : t(revDelta > 0 ? "ov.head.ahead" : "ov.head.behind", { pct: fmt.pct(Math.abs(revDelta), 1), units: fmt.num(k.total_sales) })) +
    (k.target_attainment_pct === null ? "" : ` ${t("ov.head.plan", { pct: fmt.pct(k.target_attainment_pct, 0) })}`);

  return (
    <div className="space-y-8">
      {nav}
      <PageHeading eyebrow={t("ov.title")} headline={headline} />
      <Metrics data={data} />
      <Trend data={data} />
      <div className="grid gap-x-10 gap-y-8 lg:grid-cols-2">
        <Mix title={t("ov.mix.category")} rows={data.by_category.map((c) => ({ name: c.vehicle_category, value: c.sales }))} translate />
        <Mix title={t("ov.mix.fuel")} rows={data.by_fuel.map((f) => ({ name: f.fuel_type, value: f.sales }))} translate />
      </div>
      <Stores data={data} />
    </div>
  );
}

function Metrics({ data }: { data: GlanceData }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  const k = data.kpis;
  const pts = (d: number | null) => (d === null ? null : { text: `${fmt.pct(d, 1, true).replace(/\s?%$/, "")} ${t("ov.pts")}`, tone: d >= 0 ? ("positive" as const) : ("negative" as const) });
  const rel = (d: number | null) => (d === null ? null : { text: fmt.pct(d, 1, true), tone: d >= 0 ? ("positive" as const) : ("negative" as const) });
  const vs = t("ov.vs_last_year");

  const metrics: Metric[] = [
    { label: t("ov.kpi.units"), value: fmt.num(k.total_sales), delta: rel(k.total_sales_delta), note: vs, spark: last(data.trend.units ?? [], 12).map((p) => p.y ?? 0) },
    { label: t("ov.kpi.revenue"), value: fmt.money(k.total_revenue), delta: rel(k.total_revenue_delta), note: vs, spark: last(data.trend.revenue ?? [], 12).map((p) => p.y ?? 0) },
    k.target_attainment_pct === null
      ? { label: t("ov.kpi.attainment"), value: t("val.na"), note: t("ov.kpi.no_targets") }
      : {
          label: t("ov.kpi.attainment"),
          value: fmt.pct(k.target_attainment_pct, 0),
          delta: pts(k.target_attainment_delta),
          note: t("ov.kpi.attainment_sub", { actual: fmt.num(k.ttm_units), target: fmt.num(k.annual_target) }),
          bullet: { value: k.target_attainment_pct, target: 100, targetLabel: t("ov.target") },
        },
    { label: t("ov.kpi.penetration"), value: fmt.pct(k.finance_lease_penetration, 0), delta: pts(k.finance_lease_penetration_delta), note: vs },
  ];
  return <MetricStrip metrics={metrics} />;
}

function Trend({ data }: { data: GlanceData }) {
  const { t, lang } = usePresentation();
  const fmt = useFormat();
  const tr = data.trend;

  const model = useMemo(() => {
    const rev = tr.revenue ?? [];
    if (!rev.length) return null;
    const proj = tr.revenue_projection ?? [];
    const rows = joinSeries({ revenue: rev, revenueProj: bridge(rev, proj), units: tr.units, unitsProj: tr.units_projection });
    const peak = rev.reduce((best, p) => ((p.y ?? 0) > (best.y ?? 0) ? p : best), rev[0]!);
    const handover = rev[rev.length - 1]!;
    const end = proj[proj.length - 1];
    const lastSix = sum(last(rev, 6));
    const nextSix = sum(proj.slice(0, 6));
    return { rows, peak, handover, end, outlook: lastSix ? (nextSix / lastSix - 1) * 100 : null };
  }, [tr]);

  if (!model) return null;
  const config = {
    revenue: { label: t("ov.trend.revenue"), color: "var(--chart-1)" },
    revenueProj: { label: t("ov.trend.revenue_proj"), color: "var(--brand-to)" },
    units: { label: t("ov.trend.units"), color: "var(--muted-foreground)" },
    unitsProj: { label: `${t("ov.trend.units")} (${t("ov.trend.projection")})`, color: "var(--muted-foreground)" },
  } satisfies ChartConfig;

  const headline =
    model.outlook === null
      ? t("ov.trend.title")
      : t("ov.chart.head", { month: formatMonth(model.peak.x, lang), peak: fmt.money(model.peak.y), pct: fmt.pct(model.outlook, 1, true) });

  const key = (
    <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
      <span className="flex items-center gap-1.5"><span className="bg-chart-1 h-0.5 w-4 rounded-full" />{t("ov.trend.revenue")}</span>
      <span className="flex items-center gap-1.5"><span className="brand-gradient h-0.5 w-4 rounded-full" />{t("ov.trend.revenue_proj")}</span>
      <span className="flex items-center gap-1.5"><span className="bg-muted-foreground/30 h-2.5 w-2 rounded-[1px]" />{t("ov.trend.units")}</span>
    </span>
  );

  return (
    <ChartFrame
      headline={headline}
      description={key}
      csv={{
        filename: "revenue_and_units_trend.csv",
        headers: [t("ov.export.month"), t("ov.trend.revenue"), t("ov.trend.revenue_proj"), t("ov.trend.units"), `${t("ov.trend.units")} (${t("ov.trend.projection")})`],
        rows: model.rows.map((r) => [r.x, r.revenue, r.revenueProj, r.units, r.unitsProj]),
      }}
    >
      {(height) => (
        <ChartContainer config={config} className="w-full" style={{ height }}>
          <ComposedChart data={model.rows} margin={{ left: 0, right: 84, top: 22, bottom: 0 }}>
            <ForecastGradient />
            <CartesianGrid vertical={false} strokeOpacity={0.6} />
            <XAxis dataKey="x" tickFormatter={(v: string) => formatMonth(v, lang)} tickLine={false} axisLine={false} minTickGap={40} tickMargin={10} />
            <YAxis yAxisId="rev" tickFormatter={(v: number) => fmt.money(v)} tickLine={false} axisLine={false} width={88} tickCount={5} />
            <YAxis yAxisId="units" orientation="right" hide />
            <ChartTooltip
              cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }}
              content={
                <ChartTooltipContent
                  labelFormatter={(_, p) => formatMonth(String(p?.[0]?.payload?.x ?? ""), lang)}
                  formatter={valueTip(config, (v, key) => (key.startsWith("revenue") ? fmt.money(v, false) : fmt.num(v)))}
                />
              }
            />
            <Bar yAxisId="units" dataKey="units" fill="var(--color-units)" fillOpacity={0.16} radius={[1.5, 1.5, 0, 0]} />
            <Bar yAxisId="units" dataKey="unitsProj" fill="var(--color-unitsProj)" fillOpacity={0.07} radius={[1.5, 1.5, 0, 0]} />
            <Line yAxisId="rev" dataKey="revenue" type="monotone" stroke="var(--color-revenue)" strokeWidth={2.25} dot={false} activeDot={{ r: 4 }} connectNulls />
            <Line yAxisId="rev" dataKey="revenueProj" type="monotone" stroke={FORECAST_STROKE} strokeWidth={2.75} strokeLinecap="round" dot={false} activeDot={{ r: 4 }} connectNulls />
            <ReferenceDot
              yAxisId="rev"
              x={model.peak.x}
              y={model.peak.y ?? 0}
              r={4}
              fill="var(--card)"
              stroke="var(--chart-1)"
              strokeWidth={2}
              ifOverflow="visible"
              label={{ value: t("ov.peak", { month: formatMonth(model.peak.x, lang) }), position: "top", fill: "var(--foreground)", fontSize: 11, fontWeight: 600 }}
            />
            <ReferenceDot yAxisId="rev" x={model.handover.x} y={model.handover.y ?? 0} ifOverflow="visible" shape={(p: { cx?: number; cy?: number }) => <XMarker cx={p.cx} cy={p.cy} />} />
            {model.end && (
              <ReferenceDot
                yAxisId="rev"
                x={model.end.x}
                y={model.end.y ?? 0}
                r={3.5}
                fill="var(--brand-to)"
                stroke="var(--card)"
                strokeWidth={1.5}
                ifOverflow="visible"
                label={{ value: fmt.money(model.end.y), position: "right", fill: "var(--foreground)", fontSize: 12, fontWeight: 600 }}
              />
            )}
          </ComposedChart>
        </ChartContainer>
      )}
    </ChartFrame>
  );
}

function Mix({ title, rows, translate }: { title: string; rows: { name: string; value: number }[]; translate?: boolean }) {
  const { t, tv } = usePresentation();
  const fmt = useFormat();
  const total = rows.reduce((s, r) => s + r.value, 0) || 1;
  const sorted = [...rows].sort((a, b) => b.value - a.value);
  return (
    <Section title={title}>
      <RankedBars
        rows={sorted.map((r) => ({
          key: r.name,
          label: translate ? tv(r.name) : r.name,
          value: r.value,
          display: t("val.units", { v: fmt.num(r.value) }),
          secondary: fmt.pct((r.value / total) * 100, 1),
        }))}
      />
    </Section>
  );
}

function Stores({ data }: { data: GlanceData }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  const rows = [...data.stores].sort((a, b) => b.units - a.units);
  return (
    <Section title={t("ov.store.title")} description={t("ov.store.caption")}>
      <RankedBars
        reference={data.store_average_units === null ? undefined : { value: data.store_average_units, label: t("ov.store.group_avg", { v: fmt.num(data.store_average_units) }) }}
        rows={rows.map((s) => ({ key: `${s.dealer_name}-${s.city}`, label: s.dealer_name, sublabel: s.city, value: s.units, display: t("val.units", { v: fmt.num(s.units) }), secondary: fmt.money(s.revenue) }))}
      />
      {data.store_average_units !== null && (
        <p className="text-muted-foreground mt-3 flex items-center gap-2 text-xs">
          <span className="bg-foreground/70 h-3 w-px" aria-hidden />
          {t("ov.store.group_avg", { v: fmt.num(data.store_average_units) })}
        </p>
      )}
    </Section>
  );
}
