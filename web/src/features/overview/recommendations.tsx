"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";
import { bridge, joinSeries } from "@/components/charts/series";
import { valueTip } from "@/components/charts/tooltip";
import { Panel, PanelSkeleton } from "@/components/data/chart-card";
import { KpiCard, KpiSkeletonRow } from "@/components/data/kpi-card";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { ApiError, api } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { formatMonth } from "@/lib/format";
import { useFormat, usePresentation } from "@/lib/session";
import type { Recommendations as RecommendationsData } from "@/lib/types";

const CONFIDENCE_VARIANT = { High: "default", Medium: "secondary", Low: "outline" } as const;

export function Recommendations() {
  const { t, lang } = usePresentation();
  const fmt = useFormat();
  const { apiParams } = useFilters();
  // The plays' wording is generated server-side in the viewer's language, so language is part of the cache key.
  const { data, error, isPending } = useQuery({
    queryKey: ["overview", "recommendations", apiParams, lang],
    queryFn: () => api<RecommendationsData>("/api/overview/recommendations", { params: apiParams }),
  });

  const chart = useMemo(() => {
    const history = data?.landing.history ?? [];
    const projection = data?.landing.projection ?? [];
    if (!history.length || !projection.length) return null;
    const config = {
      actual: { label: t("ov.rec.chart.actual"), color: "var(--chart-4)" },
      projected: { label: t("ov.rec.chart.projected"), color: "var(--chart-1)" },
    } satisfies ChartConfig;
    const rows = joinSeries({ actual: history, projected: bridge(history, projection) });
    const target = data?.landing.annual_target ?? 0;
    return { config, rows, monthlyTarget: target ? target / 12 : null };
  }, [data, t]);

  if (error) return <ErrorState message={t("ov.rec.unavailable")} reference={error instanceof ApiError ? error.reference : undefined} />;
  if (isPending) {
    return (
      <div className="space-y-6">
        <KpiSkeletonRow count={3} />
        <PanelSkeleton height={320} />
      </div>
    );
  }

  const { landing, plays } = data;
  const att = landing.attainment_pct ?? null;
  const gap = landing.unit_gap ?? 0;
  const short = gap > 0;
  const atStake = plays.reduce((sum, p) => sum + p.impact_amt, 0);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        {att === null ? (
          <KpiCard label={t("ov.rec.landing")} value={t("val.na")} note={t("ov.kpi.no_targets")} />
        ) : (
          <KpiCard
            label={t("ov.rec.landing")}
            value={t("ov.rec.landing_pct", { v: fmt.num(att) })}
            note={t("ov.rec.landing_delta", { sign: short ? "−" : "+", units: fmt.num(Math.abs(gap)), money: fmt.money(Math.abs(gap) * data.gross_per_unit) })}
            tone={short ? "negative" : "positive"}
          />
        )}
        <KpiCard label={t("ov.rec.value_total")} value={fmt.money(atStake)} note={t("ov.rec.value_sub", { n: plays.length })} />
        {att === null || !short ? (
          <KpiCard label={t("ov.rec.extra_needed")} value={t("ov.rec.extra_none")} note={t("ov.rec.on_track")} tone="positive" />
        ) : (
          <KpiCard label={t("ov.rec.extra_needed")} value={t("ov.rec.extra_val", { v: fmt.num(landing.gap_per_store_month ?? 0) })} note={t("ov.rec.extra_sub")} tone="negative" />
        )}
      </div>

      <Panel title={t("ov.rec.next.title")} description={t("ov.rec.next.caption")}>
        {plays.length ? (
          <ol className="space-y-3">
            {plays.map((play, i) => (
              <li key={`${play.title}-${i}`}>
                <Card className="border-l-4 py-0 shadow-none" style={{ borderLeftColor: play.accent }}>
                  <CardContent className="space-y-2 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-semibold tracking-wide uppercase" style={{ color: play.accent }}>
                        {play.category}
                      </span>
                      <div className="flex items-center gap-2">
                        <Badge variant={CONFIDENCE_VARIANT[play.confidence]}>{t("ov.rec.confidence", { level: t(`conf.${play.confidence}`) })}</Badge>
                        <span className="text-muted-foreground text-xs">{play.horizon}</span>
                      </div>
                    </div>
                    <h3 className="text-sm leading-snug font-semibold">
                      {i + 1}. {play.title}
                    </h3>
                    <p className="text-muted-foreground text-sm leading-relaxed">{play.detail}</p>
                    <p className="text-success tabular text-base font-semibold">
                      {fmt.money(play.impact_amt)} <span className="text-muted-foreground text-xs font-normal">{t("ov.rec.est_value")}</span>
                    </p>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState title={t("ov.rec.on_track")}>{t("ov.rec.none")}</EmptyState>
        )}
      </Panel>

      {chart && (
        <Panel title={t("ov.rec.chart.title")} description={t("ov.rec.chart.caption")}>
          <ChartContainer config={chart.config} className="h-[300px] w-full">
            <LineChart data={chart.rows} margin={{ left: 4, right: 12, top: 8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="x" tickFormatter={(v: string) => formatMonth(v, lang)} tickLine={false} axisLine={false} minTickGap={36} tickMargin={8} />
              <YAxis tickFormatter={(v: number) => fmt.num(v)} tickLine={false} axisLine={false} width={56} domain={["auto", "auto"]} />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    labelFormatter={(_, p) => formatMonth(String(p?.[0]?.payload?.x ?? ""), lang)}
                    formatter={valueTip(chart.config, (v) => `${fmt.num(v)} ${t("ov.trend.units")}`)}
                  />
                }
              />
              <ChartLegend content={<ChartLegendContent />} />
              {chart.monthlyTarget && (
                <ReferenceLine
                  y={chart.monthlyTarget}
                  stroke="var(--chart-3)"
                  strokeDasharray="5 4"
                  label={{ value: t("ov.rec.chart.plan_pace", { v: fmt.num(chart.monthlyTarget) }), position: "insideTopRight", fill: "var(--muted-foreground)", fontSize: 11 }}
                />
              )}
              <Line dataKey="actual" type="monotone" stroke="var(--color-actual)" strokeWidth={2} dot={false} />
              <Line dataKey="projected" type="monotone" stroke="var(--color-projected)" strokeWidth={2.25} strokeDasharray="5 4" dot={false} />
            </LineChart>
          </ChartContainer>
        </Panel>
      )}
    </div>
  );
}
