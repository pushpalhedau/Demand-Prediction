"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { EChart, GRID_LINE, INK, INK_MUTED, PALETTE, type ChartOption } from "@/components/charts/EChart";
import { ErrorNotice, KpiCard, Section, Skeleton } from "@/components/ui/primitives";
import { ApiError, api } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { formatMonth } from "@/lib/format";
import { useFormat, usePresentation } from "@/lib/session";
import type { Glance as GlanceData, Point } from "@/lib/types";

const values = (points: Point[] | undefined) => (points ?? []).map((p) => p.y);

export function Glance() {
  const { t, tv, lang } = usePresentation();
  const fmt = useFormat();
  const { apiParams } = useFilters();
  const { data, error, isPending } = useQuery({
    queryKey: ["overview", "glance", apiParams],
    queryFn: () => api<GlanceData>("/api/overview/glance", { params: apiParams }),
  });

  const trend = useMemo<ChartOption | null>(() => {
    const tr = data?.trend;
    if (!tr?.revenue?.length) return null;
    const rev = tr.revenue;
    const proj = tr.revenue_projection ?? [];
    const months = [...rev, ...proj].map((p) => formatMonth(p.x, lang));
    const pad = (n: number) => Array<null>(n).fill(null);
    const lastRevenue = rev[rev.length - 1]?.y ?? null;
    const projLabel = t("ov.trend.projection");
    return {
      grid: { left: 8, right: 8, top: 36, bottom: 8, containLabel: true },
      legend: { top: 0, textStyle: { color: INK_MUTED }, data: [t("ov.trend.revenue"), t("ov.trend.units")] },
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: months, axisLine: { lineStyle: { color: GRID_LINE } }, axisLabel: { color: INK_MUTED } },
      yAxis: [
        {
          type: "value",
          axisLabel: { color: INK_MUTED, formatter: (v: number) => fmt.money(v) },
          splitLine: { lineStyle: { color: GRID_LINE } },
        },
        { type: "value", axisLabel: { color: INK_MUTED }, splitLine: { show: false } },
      ],
      series: [
        {
          name: t("ov.trend.units"),
          type: "bar",
          yAxisIndex: 1,
          data: [...values(tr.units), ...pad(proj.length)],
          itemStyle: { color: "rgba(6,182,212,0.22)" },
        },
        {
          name: t("ov.trend.units"),
          type: "bar",
          yAxisIndex: 1,
          data: [...pad(rev.length), ...values(tr.units_projection)],
          itemStyle: { color: "rgba(6,182,212,0.09)" },
          tooltip: { valueFormatter: (v: number) => `${fmt.num(v)} (${projLabel})` },
        },
        {
          name: t("ov.trend.revenue"),
          type: "line",
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 3, color: PALETTE[0] },
          itemStyle: { color: PALETTE[0] },
          data: [...values(rev), ...pad(proj.length)],
          tooltip: { valueFormatter: (v: number) => fmt.money(v, false) },
          markArea: proj.length
            ? {
                silent: true,
                itemStyle: { color: "rgba(99,102,241,0.06)" },
                label: { color: INK_MUTED, position: "insideTopLeft" },
                data: [[{ name: projLabel, xAxis: months[rev.length - 1] ?? "" }, { xAxis: months[months.length - 1] ?? "" }]],
              }
            : undefined,
        },
        {
          name: t("ov.trend.revenue_proj"),
          type: "line",
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2.5, type: "dotted", color: PALETTE[0] },
          itemStyle: { color: PALETTE[0] },
          data: [...pad(rev.length - 1), lastRevenue, ...values(proj)],
          tooltip: { valueFormatter: (v: number) => `${fmt.money(v, false)} (${projLabel})` },
        },
      ],
    };
  }, [data, fmt, lang, t]);

  const category = useMemo<ChartOption | null>(() => {
    if (!data?.by_category.length) return null;
    return {
      tooltip: { trigger: "item", valueFormatter: (v: number) => `${fmt.num(v)} ${t("ov.trend.units")}` },
      legend: { orient: "vertical", right: 0, top: "middle", textStyle: { color: INK_MUTED } },
      series: [
        {
          type: "pie",
          radius: ["48%", "78%"],
          center: ["38%", "50%"],
          label: { show: false },
          itemStyle: { borderColor: "#0b0f19", borderWidth: 2 },
          data: data.by_category.map((c) => ({ name: tv(c.vehicle_category), value: c.sales })),
        },
      ],
    };
  }, [data, fmt, t, tv]);

  const fuel = useMemo<ChartOption | null>(() => {
    if (!data?.by_fuel.length) return null;
    const sorted = [...data.by_fuel].sort((a, b) => b.sales - a.sales);
    return {
      grid: { left: 8, right: 8, top: 16, bottom: 8, containLabel: true },
      tooltip: { trigger: "item", valueFormatter: (v: number) => `${fmt.num(v)} ${t("ov.trend.units")}` },
      xAxis: { type: "category", data: sorted.map((f) => tv(f.fuel_type)), axisLabel: { color: INK_MUTED } },
      yAxis: { type: "value", splitLine: { lineStyle: { color: GRID_LINE } }, axisLabel: { color: INK_MUTED } },
      series: [
        {
          type: "bar",
          data: sorted.map((f, i) => ({ value: f.sales, itemStyle: { color: PALETTE[i % PALETTE.length] } })),
        },
      ],
    };
  }, [data, fmt, t, tv]);

  const stores = useMemo<ChartOption | null>(() => {
    if (!data?.stores.length) return null;
    const rows = [...data.stores].sort((a, b) => a.units - b.units);
    return {
      grid: { left: 8, right: 130, top: 24, bottom: 8, containLabel: true },
      tooltip: {
        trigger: "item",
        formatter: (p: { dataIndex: number }) => {
          const s = rows[p.dataIndex];
          return s ? `${s.dealer_name} — ${s.city}<br/>${fmt.num(s.units)} ${t("ov.trend.units")} · ${fmt.money(s.revenue)}` : "";
        },
      },
      xAxis: { type: "value", show: false },
      yAxis: { type: "category", data: rows.map((s) => s.dealer_name), axisLabel: { color: INK } },
      series: [
        {
          type: "bar",
          barWidth: 14,
          data: rows.map((s) => s.units),
          itemStyle: { color: PALETTE[0], borderRadius: [0, 4, 4, 0] },
          label: {
            show: true,
            position: "right",
            color: INK,
            formatter: (p: { dataIndex: number }) => {
              const s = rows[p.dataIndex];
              return s ? `${fmt.num(s.units)} · ${fmt.money(s.revenue)}` : "";
            },
          },
          markLine:
            data.store_average_units !== null
              ? {
                  silent: true,
                  symbol: "none",
                  lineStyle: { color: INK, type: "dashed" },
                  label: { color: INK, formatter: t("ov.store.group_avg", { v: fmt.num(data.store_average_units) }) },
                  data: [{ xAxis: data.store_average_units }],
                }
              : undefined,
        },
      ],
    };
  }, [data, fmt, t]);

  if (error) {
    return <ErrorNotice message={error.message} reference={error instanceof ApiError ? error.reference : undefined} />;
  }
  if (isPending) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
    );
  }

  const k = data.kpis;
  const yoy = (d: number | null) => (d === null ? t("val.na") : t("val.yoy_pct", { v: fmt.pct(d, 1, true).replace(/\s?%$/, "") }));
  const yoyPts = (d: number | null) => (d === null ? null : t("val.yoy_pts", { v: fmt.pct(d, 1, true).replace(/\s?%$/, "") }));
  const up = (d: number | null) => (d === null || d >= 0 ? "good" : "bad");
  const attainmentNote =
    k.target_attainment_pct === null
      ? t("ov.kpi.no_targets")
      : [
          k.target_attainment_delta !== null ? yoyPts(k.target_attainment_delta) : null,
          t("ov.kpi.attainment_sub", { actual: fmt.num(k.ttm_units), target: fmt.num(k.annual_target) }),
        ]
          .filter(Boolean)
          .join(" · ");

  return (
    <div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard label={t("ov.kpi.units")} value={t("val.units", { v: fmt.num(k.total_sales) })} note={yoy(k.total_sales_delta)} tone={up(k.total_sales_delta)} />
        <KpiCard label={t("ov.kpi.revenue")} value={fmt.money(k.total_revenue)} note={yoy(k.total_revenue_delta)} tone={up(k.total_revenue_delta)} />
        <KpiCard
          label={t("ov.kpi.attainment")}
          value={k.target_attainment_pct === null ? t("val.na") : fmt.pct(k.target_attainment_pct, 0)}
          note={attainmentNote}
          tone={k.target_attainment_pct !== null && k.target_attainment_pct >= 92 ? "good" : "bad"}
        />
        <KpiCard
          label={t("ov.kpi.penetration")}
          value={fmt.pct(k.finance_lease_penetration, 0)}
          note={yoyPts(k.finance_lease_penetration_delta)}
          tone={up(k.finance_lease_penetration_delta)}
        />
      </div>

      <div className="mt-8">
        <Section title={t("ov.trend.title")} caption={t("ov.trend.caption")}>
          {trend && <EChart option={trend} height={340} label={t("ov.trend.title")} />}
        </Section>
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        <Section title={t("ov.mix.category")}>{category && <EChart option={category} height={300} label={t("ov.mix.category")} />}</Section>
        <Section title={t("ov.mix.fuel")}>{fuel && <EChart option={fuel} height={300} label={t("ov.mix.fuel")} />}</Section>
      </div>

      <div className="mt-8">
        <Section title={t("ov.store.title")} caption={t("ov.store.caption")}>
          {stores && <EChart option={stores} height={Math.max(300, 34 * (data.stores.length + 1))} label={t("ov.store.title")} />}
        </Section>
      </div>
    </div>
  );
}
