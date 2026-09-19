"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { EChart, GRID_LINE, INK_MUTED, PALETTE, type ChartOption } from "@/components/charts/EChart";
import { Card, ErrorNotice, KpiCard, Notice, Section, Skeleton } from "@/components/ui/primitives";
import { ApiError, api } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { formatMonth } from "@/lib/format";
import { useFormat, usePresentation } from "@/lib/session";
import type { Recommendations as RecommendationsData } from "@/lib/types";

const CONFIDENCE_DOT: Record<string, string> = { High: "#10b981", Medium: "#f59e0b", Low: "#9ca3af" };

export function Recommendations() {
  const { t, lang } = usePresentation();
  const fmt = useFormat();
  const { apiParams } = useFilters();
  // The plays' wording is generated server-side in the viewer's language, so language is part of the cache key.
  const { data, error, isPending } = useQuery({
    queryKey: ["overview", "recommendations", apiParams, lang],
    queryFn: () => api<RecommendationsData>("/api/overview/recommendations", { params: apiParams }),
  });

  const chart = useMemo<ChartOption | null>(() => {
    const history = data?.landing.history ?? [];
    const projection = data?.landing.projection ?? [];
    if (!history.length || !projection.length) return null;
    const labels = [...history, ...projection].map((p) => formatMonth(p.x, lang));
    const pad = (n: number) => Array<null>(n).fill(null);
    const target = data?.landing.annual_target ?? 0;
    const monthlyTarget = target ? target / 12 : null;
    const lastActual = history[history.length - 1]?.y ?? null;
    return {
      grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
      legend: { top: 0, right: 0, textStyle: { color: INK_MUTED } },
      tooltip: { trigger: "axis", valueFormatter: (v: number) => `${fmt.num(v)} ${t("ov.trend.units")}` },
      xAxis: { type: "category", data: labels, axisLabel: { color: INK_MUTED }, axisLine: { lineStyle: { color: GRID_LINE } } },
      yAxis: {
        type: "value",
        name: t("ov.rec.chart.yaxis"),
        nameTextStyle: { color: INK_MUTED },
        scale: true,
        axisLabel: { color: INK_MUTED },
        splitLine: { lineStyle: { color: GRID_LINE } },
      },
      series: [
        {
          name: t("ov.rec.chart.actual"),
          type: "line",
          showSymbol: false,
          lineStyle: { width: 2, color: "#9ca3af" },
          itemStyle: { color: "#9ca3af" },
          data: [...history.map((p) => p.y), ...pad(projection.length)],
        },
        {
          name: t("ov.rec.chart.projected"),
          type: "line",
          showSymbol: false,
          lineStyle: { width: 2.5, type: "dotted", color: PALETTE[0] },
          itemStyle: { color: PALETTE[0] },
          data: [...pad(history.length - 1), lastActual, ...projection.map((p) => p.y)],
          markLine: monthlyTarget
            ? {
                silent: true,
                symbol: "none",
                lineStyle: { color: "#f59e0b", type: "dashed" },
                label: { color: "#f59e0b", position: "insideEndTop", formatter: t("ov.rec.chart.plan_pace", { v: fmt.num(monthlyTarget) }) },
                data: [{ yAxis: monthlyTarget }],
              }
            : undefined,
        },
      ],
    };
  }, [data, fmt, lang, t]);

  if (error) {
    return <ErrorNotice message={t("ov.rec.unavailable")} reference={error instanceof ApiError ? error.reference : undefined} />;
  }
  if (isPending) return <Skeleton className="h-64" />;

  const { landing, plays } = data;
  const att = landing.attainment_pct ?? null;
  const gap = landing.unit_gap ?? 0;
  const perStore = landing.gap_per_store_month ?? 0;
  const short = gap > 0;
  const atStake = plays.reduce((sum, p) => sum + p.impact_amt, 0);

  return (
    <div>
      <div className="grid gap-4 md:grid-cols-3">
        {att === null ? (
          <KpiCard label={t("ov.rec.landing")} value={t("val.na")} note={t("ov.kpi.no_targets")} tone="bad" />
        ) : (
          <KpiCard
            label={t("ov.rec.landing")}
            value={t("ov.rec.landing_pct", { v: fmt.num(att) })}
            note={t("ov.rec.landing_delta", {
              sign: short ? "−" : "+",
              units: fmt.num(Math.abs(gap)),
              money: fmt.money(Math.abs(gap) * data.gross_per_unit),
            })}
            tone={short ? "bad" : "good"}
          />
        )}
        <KpiCard
          label={t("ov.rec.value_total")}
          value={fmt.money(atStake)}
          note={t("ov.rec.value_sub", { n: plays.length })}
          tone="good"
        />
        {att === null || !short ? (
          <KpiCard label={t("ov.rec.extra_needed")} value={t("ov.rec.extra_none")} note={t("ov.rec.on_track")} tone="good" />
        ) : (
          <KpiCard
            label={t("ov.rec.extra_needed")}
            value={t("ov.rec.extra_val", { v: fmt.num(perStore) })}
            note={t("ov.rec.extra_sub")}
            tone="bad"
          />
        )}
      </div>

      <div className="mt-8">
        <Section title={t("ov.rec.next.title")} caption={t("ov.rec.next.caption")}>
          {plays.length ? (
            <ol className="space-y-3">
              {plays.map((play, i) => (
                <li key={`${play.title}-${i}`}>
                  <Card className="border-l-[3px] p-4" style={{ borderLeftColor: play.accent }}>
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-xs font-bold uppercase tracking-wider" style={{ color: play.accent }}>
                        {play.category}
                      </span>
                      <span className="text-xs text-muted">
                        <span style={{ color: CONFIDENCE_DOT[play.confidence] ?? "#9ca3af" }}>●</span>{" "}
                        {t("ov.rec.confidence", { level: t(`conf.${play.confidence}`) })} · {play.horizon}
                      </span>
                    </div>
                    <h3 className="mt-2 font-semibold">
                      {i + 1}. {play.title}
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-muted">{play.detail}</p>
                    <p className="mt-3 text-lg font-bold text-good">
                      {fmt.money(play.impact_amt)}{" "}
                      <span className="text-xs font-normal text-muted">{t("ov.rec.est_value")}</span>
                    </p>
                  </Card>
                </li>
              ))}
            </ol>
          ) : (
            <Notice>{t("ov.rec.none")}</Notice>
          )}
        </Section>
      </div>

      <div className="mt-8">
        <Section title={t("ov.rec.chart.title")} caption={t("ov.rec.chart.caption")}>
          {chart && <EChart option={chart} height={280} label={t("ov.rec.chart.title")} />}
        </Section>
      </div>
    </div>
  );
}
