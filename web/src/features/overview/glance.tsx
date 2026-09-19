"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, ComposedChart, LabelList, Line, Pie, PieChart, ReferenceArea, ReferenceLine, XAxis, YAxis } from "recharts";
import { bridge, joinSeries, seriesColor } from "@/components/charts/series";
import { valueTip } from "@/components/charts/tooltip";
import { Panel, PanelSkeleton } from "@/components/data/chart-card";
import { KpiCard, KpiSkeletonRow } from "@/components/data/kpi-card";
import { ErrorState } from "@/components/data/states";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { ApiError, api } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { formatMonth } from "@/lib/format";
import { useFormat, usePresentation } from "@/lib/session";
import type { Glance as GlanceData } from "@/lib/types";

export function Glance() {
  const { t, tv, lang } = usePresentation();
  const fmt = useFormat();
  const { apiParams } = useFilters();
  const { data, error, isPending } = useQuery({
    queryKey: ["overview", "glance", apiParams],
    queryFn: () => api<GlanceData>("/api/overview/glance", { params: apiParams }),
  });

  const trend = useMemo(() => {
    const tr = data?.trend;
    if (!tr?.revenue?.length) return null;
    const rows = joinSeries({
      revenue: tr.revenue,
      revenueProj: bridge(tr.revenue, tr.revenue_projection),
      units: tr.units,
      unitsProj: tr.units_projection,
    });
    const config = {
      revenue: { label: t("ov.trend.revenue"), color: "var(--chart-1)" },
      revenueProj: { label: t("ov.trend.revenue_proj"), color: "var(--chart-1)" },
      units: { label: t("ov.trend.units"), color: "var(--chart-2)" },
      unitsProj: { label: `${t("ov.trend.units")} (${t("ov.trend.projection")})`, color: "var(--chart-2)" },
    } satisfies ChartConfig;
    return { rows, config, from: tr.revenue[tr.revenue.length - 1]?.x, to: rows[rows.length - 1]?.x };
  }, [data, t]);

  const category = useMemo(() => {
    const rows = (data?.by_category ?? []).map((c, i) => ({ name: tv(c.vehicle_category), sales: c.sales, fill: seriesColor(i) }));
    const config: ChartConfig = Object.fromEntries(rows.map((r) => [r.name, { label: r.name, color: r.fill }]));
    return { rows, config };
  }, [data, tv]);

  const fuel = useMemo(() => {
    const rows = [...(data?.by_fuel ?? [])]
      .sort((a, b) => b.sales - a.sales)
      .map((f, i) => ({ name: tv(f.fuel_type), sales: f.sales, fill: seriesColor(i) }));
    return { rows, config: { sales: { label: t("ov.trend.units") } } satisfies ChartConfig };
  }, [data, t, tv]);

  if (error) return <ErrorState message={error.message} reference={error instanceof ApiError ? error.reference : undefined} />;
  if (isPending) {
    return (
      <div className="space-y-6">
        <KpiSkeletonRow />
        <PanelSkeleton height={380} />
      </div>
    );
  }

  const k = data.kpis;
  const yoy = (d: number | null) => (d === null ? t("val.na") : t("val.yoy_pct", { v: fmt.pct(d, 1, true).replace(/\s?%$/, "") }));
  const yoyPts = (d: number | null) => (d === null ? null : t("val.yoy_pts", { v: fmt.pct(d, 1, true).replace(/\s?%$/, "") }));
  const tone = (d: number | null) => (d === null || d >= 0 ? "positive" : "negative");
  const attainmentNote =
    k.target_attainment_pct === null
      ? t("ov.kpi.no_targets")
      : [
          yoyPts(k.target_attainment_delta),
          t("ov.kpi.attainment_sub", { actual: fmt.num(k.ttm_units), target: fmt.num(k.annual_target) }),
        ]
          .filter(Boolean)
          .join(" · ");

  const storeRows = [...data.stores].sort((a, b) => b.units - a.units);
  const storeConfig = { units: { label: t("ov.trend.units"), color: "var(--chart-1)" } } satisfies ChartConfig;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label={t("ov.kpi.units")} value={t("val.units", { v: fmt.num(k.total_sales) })} note={yoy(k.total_sales_delta)} tone={tone(k.total_sales_delta)} trend />
        <KpiCard label={t("ov.kpi.revenue")} value={fmt.money(k.total_revenue)} note={yoy(k.total_revenue_delta)} tone={tone(k.total_revenue_delta)} trend />
        <KpiCard
          label={t("ov.kpi.attainment")}
          value={k.target_attainment_pct === null ? t("val.na") : fmt.pct(k.target_attainment_pct, 0)}
          note={attainmentNote}
          tone={k.target_attainment_pct === null ? "neutral" : k.target_attainment_pct >= 92 ? "positive" : "negative"}
        />
        <KpiCard
          label={t("ov.kpi.penetration")}
          value={fmt.pct(k.finance_lease_penetration, 0)}
          note={yoyPts(k.finance_lease_penetration_delta)}
          tone={tone(k.finance_lease_penetration_delta)}
          trend
        />
      </div>

      {trend && (
        <Panel title={t("ov.trend.title")} description={t("ov.trend.caption")}>
          <ChartContainer config={trend.config} className="h-[340px] w-full">
            <ComposedChart data={trend.rows} margin={{ left: 4, right: 4, top: 8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="x" tickFormatter={(v: string) => formatMonth(v, lang)} tickLine={false} axisLine={false} minTickGap={36} tickMargin={8} />
              <YAxis yAxisId="rev" tickFormatter={(v: number) => fmt.money(v)} tickLine={false} axisLine={false} width={92} />
              <YAxis yAxisId="units" orientation="right" tickFormatter={(v: number) => fmt.num(v)} tickLine={false} axisLine={false} width={48} />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    labelFormatter={(_, p) => formatMonth(String(p?.[0]?.payload?.x ?? ""), lang)}
                    formatter={valueTip(trend.config, (v, key) => (key.startsWith("revenue") ? fmt.money(v, false) : fmt.num(v)))}
                  />
                }
              />
              <ChartLegend content={<ChartLegendContent />} />
              {trend.from && trend.to && trend.from !== trend.to && (
                <ReferenceArea yAxisId="rev" x1={trend.from} x2={trend.to} fill="var(--muted)" fillOpacity={0.5} ifOverflow="visible" />
              )}
              <Bar yAxisId="units" dataKey="units" fill="var(--color-units)" fillOpacity={0.35} radius={[2, 2, 0, 0]} />
              <Bar yAxisId="units" dataKey="unitsProj" fill="var(--color-unitsProj)" fillOpacity={0.15} radius={[2, 2, 0, 0]} legendType="none" />
              <Line yAxisId="rev" dataKey="revenue" type="monotone" stroke="var(--color-revenue)" strokeWidth={2.25} dot={false} connectNulls />
              <Line yAxisId="rev" dataKey="revenueProj" type="monotone" stroke="var(--color-revenueProj)" strokeWidth={2} strokeDasharray="5 4" dot={false} legendType="none" connectNulls />
            </ComposedChart>
          </ChartContainer>
        </Panel>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title={t("ov.mix.category")}>
          <ChartContainer config={category.config} className="mx-auto h-[300px] w-full">
            <PieChart>
              <ChartTooltip content={<ChartTooltipContent hideLabel nameKey="name" formatter={valueTip(category.config, (v) => `${fmt.num(v)} ${t("ov.trend.units")}`)} />} />
              <Pie data={category.rows} dataKey="sales" nameKey="name" innerRadius={62} outerRadius={104} strokeWidth={2} paddingAngle={1} />
              <ChartLegend content={<ChartLegendContent nameKey="name" />} />
            </PieChart>
          </ChartContainer>
        </Panel>

        <Panel title={t("ov.mix.fuel")}>
          <ChartContainer config={fuel.config} className="h-[300px] w-full">
            <BarChart data={fuel.rows} margin={{ top: 8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} />
              <YAxis tickFormatter={(v: number) => fmt.num(v)} tickLine={false} axisLine={false} width={56} />
              <ChartTooltip cursor={{ fill: "var(--muted)", opacity: 0.5 }} content={<ChartTooltipContent hideLabel formatter={valueTip(fuel.config, (v) => `${fmt.num(v)} ${t("ov.trend.units")}`)} />} />
              <Bar dataKey="sales" radius={[4, 4, 0, 0]} maxBarSize={72} />
            </BarChart>
          </ChartContainer>
        </Panel>
      </div>

      <Panel title={t("ov.store.title")} description={t("ov.store.caption")}>
        <ChartContainer config={storeConfig} className="w-full" style={{ height: Math.max(220, 52 * storeRows.length + 30) }}>
          <BarChart data={storeRows} layout="vertical" margin={{ left: 0, right: 96, top: 16 }}>
            <CartesianGrid horizontal={false} />
            <XAxis type="number" hide domain={[0, "dataMax"]} />
            <YAxis dataKey="dealer_name" type="category" tickLine={false} axisLine={false} width={190} />
            <ChartTooltip
              cursor={{ fill: "var(--muted)", opacity: 0.5 }}
              content={
                <ChartTooltipContent
                  labelFormatter={(_, p) => {
                    const s = p?.[0]?.payload as { dealer_name: string; city: string } | undefined;
                    return s ? `${s.dealer_name} — ${s.city}` : "";
                  }}
                  formatter={valueTip(storeConfig, (v) => `${fmt.num(v)} ${t("ov.trend.units")}`)}
                />
              }
            />
            {data.store_average_units !== null && (
              <ReferenceLine
                x={data.store_average_units}
                stroke="var(--muted-foreground)"
                strokeDasharray="4 4"
                label={{ value: t("ov.store.group_avg", { v: fmt.num(data.store_average_units) }), position: "top", fill: "var(--muted-foreground)", fontSize: 11 }}
              />
            )}
            <Bar dataKey="units" fill="var(--color-units)" radius={4} barSize={18}>
              <LabelList
                dataKey="units"
                position="right"
                className="fill-foreground"
                fontSize={12}
                formatter={(v: unknown) => fmt.num(Number(v))}
              />
            </Bar>
          </BarChart>
        </ChartContainer>
      </Panel>
    </div>
  );
}
