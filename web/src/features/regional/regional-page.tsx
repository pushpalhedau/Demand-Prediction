"use client";

import { Bar, BarChart, CartesianGrid, LabelList, XAxis, YAxis } from "recharts";
import { ChartFrame } from "@/components/charts/chart-frame";
import { RegionMap } from "@/components/charts/region-map";
import { PanelSkeleton } from "@/components/data/chart-card";
import { DataTable, type Column } from "@/components/data/data-table";
import { Insight } from "@/components/data/insight";
import { MetricStrip, MetricStripSkeleton } from "@/components/data/metric-strip";
import { PageHeading } from "@/components/data/page-heading";
import { QueryBoundary } from "@/components/data/query-boundary";
import { Section } from "@/components/data/section";
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart";
import { attainmentColor } from "@/lib/attainment";
import { useDashboardQuery } from "@/lib/query";
import { useFormat, useMe, usePresentation } from "@/lib/session";
import type { Scorecard, StoreRow } from "@/lib/types";

const chartConfig = { units: { label: "Units", color: "var(--chart-1)" } } satisfies ChartConfig;

function Legend() {
  const { t } = usePresentation();
  return (
    <span className="text-muted-foreground inline-flex items-center gap-2 text-xs">
      <span>{t("rg.pace.behind")}</span>
      <span
        className="h-1.5 w-24 rounded-full"
        style={{ background: `linear-gradient(90deg, ${attainmentColor(84)}, ${attainmentColor(95)}, ${attainmentColor(104)})` }}
        aria-hidden
      />
      <span>{t("rg.pace.ahead")}</span>
    </span>
  );
}

export function RegionalPage() {
  const { t } = usePresentation();
  const query = useDashboardQuery<Scorecard>("regional", "/api/regional/scorecard");
  return (
    <QueryBoundary
      query={query}
      skeleton={
        <div className="space-y-8">
          <PanelSkeleton height={110} />
          <MetricStripSkeleton />
          <PanelSkeleton height={420} />
        </div>
      }
    >
      {(data) => (data.rows.length ? <Content data={data} /> : <PageHeading eyebrow={t("tab.regional")} headline={t("rg.empty")} />)}
    </QueryBoundary>
  );
}

function Content({ data }: { data: Scorecard }) {
  const { t, tv } = usePresentation();
  const fmt = useFormat();
  const { data: me } = useMe();
  const rows = data.rows;
  const withTarget = rows.filter((r) => r.attainment_pct !== null);
  const behind = withTarget.filter((r) => (r.attainment_pct ?? 100) < data.behind_plan_pct).length;
  const totalUnits = rows.reduce((sum, r) => sum + r.units_sold, 0);

  const located = rows.filter((r) => r.latitude !== null && r.longitude !== null && r.units_sold > 0);
  const ranking = [...rows].sort((a, b) => b.units_sold - a.units_sold).map((r) => ({ ...r, label: r.dealer_name, fill: attainmentColor(r.attainment_pct) }));

  const ranked = [...withTarget].sort((a, b) => (a.attainment_pct ?? 0) - (b.attainment_pct ?? 0));
  const weakest = ranked[0];
  const strongest = ranked[ranked.length - 1];
  const alsoDown = weakest ? ranked.filter((r) => (r.yoy_units_pct ?? 0) < 0 && r.dealer_id !== weakest.dealer_id).slice(0, 3) : [];

  const yoy = (v: number | null) => (v === null ? t("val.na") : fmt.pct(v, 1, true));
  const columns: Column<StoreRow>[] = [
    { key: "store", header: t("rg.col.store"), cell: (r) => <span className="font-medium">{r.dealer_name}</span>, sort: (r) => r.dealer_name },
    { key: "brand", header: t("rg.col.franchise"), cell: (r) => r.brand, sort: (r) => r.brand },
    { key: "region", header: t("rg.col.region"), cell: (r) => r.region ?? "–", sort: (r) => r.region },
    { key: "units", header: t("rg.col.units"), align: "right", cell: (r) => fmt.num(r.units_sold), sort: (r) => r.units_sold },
    { key: "revenue", header: t("rg.col.revenue"), align: "right", cell: (r) => fmt.money(r.revenue), sort: (r) => r.revenue },
    {
      key: "yoy",
      header: t("rg.col.yoy"),
      align: "right",
      cell: (r) => <span className={(r.yoy_units_pct ?? 0) < 0 ? "text-destructive" : undefined}>{yoy(r.yoy_units_pct)}</span>,
      sort: (r) => r.yoy_units_pct,
    },
    {
      key: "pace",
      header: t("rg.col.pace"),
      align: "right",
      cell: (r) =>
        r.attainment_pct === null ? (
          "–"
        ) : (
          <span className="inline-flex items-center gap-2">
            <span className="size-2 rounded-full" style={{ background: attainmentColor(r.attainment_pct) }} aria-hidden />
            {fmt.pct(r.attainment_pct, 0)}
          </span>
        ),
      sort: (r) => r.attainment_pct,
    },
    { key: "gross", header: t("rg.col.gross"), align: "right", cell: (r) => fmt.money(r.est_gross), sort: (r) => r.est_gross },
    { key: "close", header: t("rg.col.close"), align: "right", cell: (r) => (r.close_rate === null ? "–" : fmt.pct(r.close_rate * 100, 0)), sort: (r) => r.close_rate },
    { key: "days", header: t("rg.col.days"), align: "right", cell: (r) => (r.avg_days_to_close === null ? "–" : fmt.num(r.avg_days_to_close, 0)), sort: (r) => r.avg_days_to_close },
    { key: "top", header: t("rg.col.top"), cell: (r) => (r.top_category ? tv(r.top_category) : "–"), sort: (r) => r.top_category },
  ];

  const headline =
    weakest && strongest
      ? t(behind > 0 ? "rg.head.behind" : "rg.head.ok", { n: behind, total: withTarget.length, best: strongest.dealer_name, pct: fmt.pct(strongest.attainment_pct, 0) })
      : t("rg.head.none", { n: rows.length, units: fmt.num(totalUnits) });

  const meta = (r: StoreRow) => <span className="text-muted-foreground text-xs">{[r.brand, r.region].filter(Boolean).join(" · ")}</span>;
  const summary = (r: StoreRow) => t("rg.summary", { units: fmt.num(r.units_sold), pace: fmt.pct(r.attainment_pct, 0), yoy: yoy(r.yoy_units_pct) });

  return (
    <div className="space-y-8">
      <PageHeading eyebrow={t("tab.regional")} headline={headline} />
      <MetricStrip
        metrics={[
          { label: t("rg.kpi.rooftops"), value: fmt.num(rows.length) },
          { label: t("rg.kpi.units"), value: fmt.num(totalUnits) },
          {
            label: t("rg.kpi.behind"),
            value: t("rg.kpi.behind_value", { n: behind, total: withTarget.length }),
            delta: behind > 0 ? { text: t("rg.kpi.behind_flag", { n: behind }), tone: "negative" } : { text: t("ov.rec.on_track"), tone: "positive" },
            note: t("rg.kpi.behind_help", { pct: data.behind_plan_pct }),
          },
        ]}
      />

      {weakest && strongest && (
        <Section title={t("rg.read.title")}>
          <div>
            <Insight
              rank={1}
              tag={t("rg.tag.weak")}
              accent="var(--warning)"
              title={weakest.dealer_name}
              detail={`${summary(weakest)}${alsoDown.length > 0 ? ` ${t("rg.also_down", { names: alsoDown.map((r) => r.dealer_name).join(", ") })}` : ""}`}
              value={fmt.pct(weakest.attainment_pct, 0)}
              valueCaption={t("rg.value.pace")}
              valueTone="negative"
              meta={meta(weakest)}
            />
            <Insight
              rank={2}
              tag={t("rg.tag.strong")}
              accent="var(--success)"
              title={strongest.dealer_name}
              detail={summary(strongest)}
              value={fmt.pct(strongest.attainment_pct, 0)}
              valueCaption={t("rg.value.pace")}
              meta={meta(strongest)}
            />
          </div>
        </Section>
      )}

      {located.length > 0 && (
        <ChartFrame
          headline={t("rg.map.title")}
          description={
            <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
              {t("rg.map.caption")}
              <Legend />
            </span>
          }
        >
          {() => <RegionMap stores={located} country={me?.organisation.country} />}
        </ChartFrame>
      )}

      <ChartFrame
        headline={t("rg.rank.title")}
        description={<Legend />}
        csv={{ filename: "stores_by_units.csv", headers: [t("rg.col.store"), t("rg.col.units"), t("rg.col.pace")], rows: ranking.map((r) => [r.dealer_name, r.units_sold, r.attainment_pct]) }}
      >
        {(height) => (
          <ChartContainer config={chartConfig} className="w-full" style={{ height: Math.max(height - 20, 26 * ranking.length + 24) }}>
            <BarChart data={ranking} layout="vertical" margin={{ left: 0, right: 56, top: 4 }}>
              <CartesianGrid horizontal={false} strokeOpacity={0.6} />
              <XAxis type="number" hide />
              <YAxis dataKey="label" type="category" tickLine={false} axisLine={false} width={200} interval={0} tick={{ fontSize: 12 }} />
              <ChartTooltip
                cursor={{ fill: "var(--muted)", opacity: 0.5 }}
                content={({ active, payload }) => {
                  const r = payload?.[0]?.payload as (StoreRow & { label: string }) | undefined;
                  if (!active || !r) return null;
                  return (
                    <div className="bg-background grid gap-0.5 rounded-lg border px-3 py-2 text-xs shadow-xl">
                      <p className="text-sm font-medium">{r.label}</p>
                      <p className="tabular">
                        {fmt.num(r.units_sold)} {t("ov.trend.units").toLowerCase()} · {r.attainment_pct === null ? t("rg.no_target") : t("rg.of_target", { v: fmt.pct(r.attainment_pct, 0) })}
                      </p>
                    </div>
                  );
                }}
              />
              <Bar dataKey="units_sold" radius={3} barSize={14}>
                <LabelList dataKey="units_sold" position="right" fontSize={12} className="fill-foreground" formatter={(v: unknown) => fmt.num(Number(v))} />
              </Bar>
            </BarChart>
          </ChartContainer>
        )}
      </ChartFrame>

      <Section title={t("rg.score.title")}>
        <DataTable columns={columns} rows={rows} rowKey={(r) => r.dealer_id} initialSort={{ key: "units", dir: "desc" }} />
      </Section>
    </div>
  );
}
