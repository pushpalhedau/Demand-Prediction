"use client";

import { useMemo, type ReactNode } from "react";
import { CartesianGrid, Line, LineChart, ReferenceDot, ReferenceLine, XAxis, YAxis } from "recharts";
import { ChartFrame } from "@/components/charts/chart-frame";
import { FORECAST_STROKE, ForecastGradient, XMarker } from "@/components/charts/forecast-marks";
import { bridge, joinSeries } from "@/components/charts/series";
import { valueTip } from "@/components/charts/tooltip";
import { PanelSkeleton } from "@/components/data/chart-card";
import { ConfidenceMeter, Insight } from "@/components/data/insight";
import { MetricStrip, type Metric } from "@/components/data/metric-strip";
import { PageHeading } from "@/components/data/page-heading";
import { Section } from "@/components/data/section";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Skeleton } from "@/components/ui/skeleton";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { ApiError } from "@/lib/api";
import { formatMonth } from "@/lib/format";
import { useFormat, usePresentation } from "@/lib/session";
import { useRecommendations } from "./queries";

export function Recommendations({ nav }: { nav: ReactNode }) {
  const query = useRecommendations();
  const { t, lang } = usePresentation();
  const fmt = useFormat();
  const data = query.data;

  const chart = useMemo(() => {
    const history = data?.landing.history ?? [];
    const projection = data?.landing.projection ?? [];
    if (!history.length || !projection.length) return null;
    const rows = joinSeries({ actual: history, projected: bridge(history, projection) });
    const target = data?.landing.annual_target ?? 0;
    return { rows, handover: history[history.length - 1]!, monthlyTarget: target ? target / 12 : null };
  }, [data]);

  if (query.isError) {
    return (
      <div className="space-y-6">
        {nav}
        <ErrorState message={t("ov.rec.unavailable")} reference={query.error instanceof ApiError ? query.error.reference : undefined} />
      </div>
    );
  }
  if (!data) {
    return (
      <div className="space-y-6">
        {nav}
        <Skeleton className="h-24 w-full max-w-3xl" />
        <Skeleton className="h-32 w-full" />
        <PanelSkeleton height={320} />
      </div>
    );
  }

  const { landing, plays } = data;
  const att = landing.attainment_pct ?? null;
  const gap = landing.unit_gap ?? 0;
  const short = gap > 0;
  const atStake = plays.reduce((sum, p) => sum + p.impact_amt, 0);
  const headline = att === null ? t("ov.rec.head_noplan", { n: plays.length, value: fmt.money(atStake) }) : t("ov.rec.head", { n: plays.length, value: fmt.money(atStake), pct: fmt.num(att) });

  const metrics: Metric[] = [
    att === null
      ? { label: t("ov.rec.landing"), value: t("val.na"), note: t("ov.kpi.no_targets") }
      : {
          label: t("ov.rec.landing"),
          value: t("ov.rec.landing_pct", { v: fmt.num(att) }),
          delta: { text: `${short ? "−" : "+"}${fmt.num(Math.abs(gap))} ${t("ov.trend.units").toLowerCase()}`, tone: short ? "negative" : "positive" },
          note: t("ov.rec.landing_money", { money: fmt.money(Math.abs(gap) * data.gross_per_unit) }),
          bullet: { value: att, target: 100, targetLabel: t("ov.target") },
        },
    { label: t("ov.rec.value_total"), value: fmt.money(atStake), note: t("ov.rec.value_sub", { n: plays.length }) },
    att === null || !short
      ? { label: t("ov.rec.extra_needed"), value: t("ov.rec.extra_none"), delta: { text: t("ov.rec.on_track"), tone: "positive" } }
      : { label: t("ov.rec.extra_needed"), value: t("ov.rec.extra_val", { v: fmt.num(landing.gap_per_store_month ?? 0) }), note: t("ov.rec.extra_sub") },
  ];

  const config = {
    actual: { label: t("ov.rec.chart.actual"), color: "var(--chart-4)" },
    projected: { label: t("ov.rec.chart.projected"), color: "var(--brand-to)" },
  } satisfies ChartConfig;

  return (
    <div className="space-y-8">
      {nav}
      <PageHeading eyebrow={t("ov.tab_recs")} headline={headline} />
      <MetricStrip metrics={metrics} />

      <Section title={t("ov.rec.next.title")} description={t("ov.rec.next.caption")}>
        {plays.length ? (
          <div>
            {plays.map((p, i) => (
              <Insight
                key={`${p.title}-${i}`}
                rank={i + 1}
                tag={p.category}
                accent={p.accent}
                title={p.title}
                detail={p.detail}
                value={fmt.money(p.impact_amt)}
                valueCaption={t("ov.rec.est_value")}
                meta={
                  <>
                    <ConfidenceMeter level={p.confidence} label={t("ov.rec.confidence", { level: t(`conf.${p.confidence}`) })} />
                    <span className="text-muted-foreground text-xs">{p.horizon}</span>
                  </>
                }
              />
            ))}
          </div>
        ) : (
          <EmptyState title={t("ov.rec.on_track")}>{t("ov.rec.none")}</EmptyState>
        )}
      </Section>

      {chart && (
        <ChartFrame
          headline={att === null ? t("ov.rec.chart.title") : t("ov.rec.chart.head", { pct: fmt.num(att) })}
          description={t("ov.rec.chart.caption")}
          csv={{
            filename: "where_the_year_lands.csv",
            headers: [t("ov.export.month"), t("ov.rec.chart.actual"), t("ov.rec.chart.projected")],
            rows: chart.rows.map((r) => [r.x, r.actual, r.projected]),
          }}
        >
          {(height) => (
            <ChartContainer config={config} className="w-full" style={{ height }}>
              <LineChart data={chart.rows} margin={{ left: 0, right: 16, top: 12 }}>
                <ForecastGradient />
                <CartesianGrid vertical={false} strokeOpacity={0.6} />
                <XAxis dataKey="x" tickFormatter={(v: string) => formatMonth(v, lang)} tickLine={false} axisLine={false} minTickGap={40} tickMargin={10} />
                <YAxis tickFormatter={(v: number) => fmt.num(v)} tickLine={false} axisLine={false} width={52} domain={["auto", "auto"]} />
                <ChartTooltip
                  cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }}
                  content={<ChartTooltipContent labelFormatter={(_, p) => formatMonth(String(p?.[0]?.payload?.x ?? ""), lang)} formatter={valueTip(config, (v) => `${fmt.num(v)} ${t("ov.trend.units").toLowerCase()}`)} />}
                />
                {chart.monthlyTarget && (
                  <ReferenceLine
                    y={chart.monthlyTarget}
                    stroke="var(--foreground)"
                    strokeOpacity={0.55}
                    strokeDasharray="4 4"
                    label={{ value: t("ov.rec.chart.plan_pace", { v: fmt.num(chart.monthlyTarget) }), position: "insideTopRight", fill: "var(--foreground)", fontSize: 11, fontWeight: 600 }}
                  />
                )}
                <Line dataKey="actual" type="monotone" stroke="var(--color-actual)" strokeWidth={2.25} dot={false} activeDot={{ r: 4 }} />
                <Line dataKey="projected" type="monotone" stroke={FORECAST_STROKE} strokeWidth={2.75} strokeLinecap="round" dot={false} activeDot={{ r: 4 }} connectNulls />
                <ReferenceDot x={chart.handover.x} y={chart.handover.y ?? 0} ifOverflow="visible" shape={(p: { cx?: number; cy?: number }) => <XMarker cx={p.cx} cy={p.cy} />} />
              </LineChart>
            </ChartContainer>
          )}
        </ChartFrame>
      )}
    </div>
  );
}
