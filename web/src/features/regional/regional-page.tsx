"use client";

import { Award, TriangleAlert } from "lucide-react";
import { Bar, BarChart, CartesianGrid, LabelList, Scatter, ScatterChart, XAxis, YAxis, ZAxis } from "recharts";
import { Panel, PanelSkeleton } from "@/components/data/chart-card";
import { DataTable, type Column } from "@/components/data/data-table";
import { KpiCard, KpiSkeletonRow } from "@/components/data/kpi-card";
import { PageHeader } from "@/components/data/page-header";
import { QueryBoundary } from "@/components/data/query-boundary";
import { EmptyState } from "@/components/data/states";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart";
import { attainmentColor } from "@/lib/attainment";
import { useDashboardQuery } from "@/lib/query";
import { useFormat, usePresentation } from "@/lib/session";
import type { Scorecard, StoreRow } from "@/lib/types";

const chartConfig = { units: { label: "Units", color: "var(--chart-1)" } } satisfies ChartConfig;

function Legend() {
  const { t } = usePresentation();
  return (
    <div className="text-muted-foreground flex items-center gap-2 text-xs">
      <span>{t("rg.pace.behind")}</span>
      <span
        className="h-2 w-28 rounded-full"
        style={{ background: `linear-gradient(90deg, ${attainmentColor(84)}, ${attainmentColor(95)}, ${attainmentColor(104)})` }}
        aria-hidden
      />
      <span>{t("rg.pace.ahead")}</span>
    </div>
  );
}

export function RegionalPage() {
  const { t } = usePresentation();
  const query = useDashboardQuery<Scorecard>("regional", "/api/regional/scorecard");
  return (
    <>
      <PageHeader title={t("tab.regional")} description={t("rg.subtitle")} />
      <QueryBoundary query={query} skeleton={<div className="space-y-6"><KpiSkeletonRow count={3} /><PanelSkeleton height={420} /></div>}>
        {(data) => (data.rows.length ? <Content data={data} /> : <EmptyState title={t("rg.empty")} />)}
      </QueryBoundary>
    </>
  );
}

function Content({ data }: { data: Scorecard }) {
  const { t, tv } = usePresentation();
  const fmt = useFormat();
  const rows = data.rows;
  const withTarget = rows.filter((r) => r.attainment_pct !== null);
  const behind = withTarget.filter((r) => (r.attainment_pct ?? 100) < data.behind_plan_pct).length;
  const totalUnits = rows.reduce((sum, r) => sum + r.units_sold, 0);

  const located = rows.filter((r) => r.latitude !== null && r.longitude !== null && r.units_sold > 0);
  const label = (r: StoreRow) => r.dealer_name;
  const ranking = [...rows].sort((a, b) => b.units_sold - a.units_sold).map((r) => ({ ...r, label: label(r), fill: attainmentColor(r.attainment_pct) }));

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

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <KpiCard label={t("rg.kpi.rooftops")} value={fmt.num(rows.length)} />
        <KpiCard label={t("rg.kpi.units")} value={fmt.num(totalUnits)} />
        <KpiCard
          label={t("rg.kpi.behind")}
          value={t("rg.kpi.behind_value", { n: behind, total: withTarget.length })}
          note={t("rg.kpi.behind_help", { pct: data.behind_plan_pct })}
          tone={behind > 0 ? "negative" : "positive"}
        />
      </div>

      {located.length > 0 && (
        <Panel title={t("rg.map.title")} description={t("rg.map.caption")} action={<Legend />}>
          <ChartContainer config={chartConfig} className="h-[420px] w-full">
            <ScatterChart margin={{ top: 16, right: 24, bottom: 16, left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" dataKey="longitude" name="Longitude" domain={["dataMin - 0.3", "dataMax + 0.3"]} hide />
              <YAxis type="number" dataKey="latitude" name="Latitude" domain={["dataMin - 0.3", "dataMax + 0.3"]} hide />
              <ZAxis type="number" dataKey="units_sold" range={[90, 900]} />
              <ChartTooltip
                cursor={false}
                content={({ active, payload }) => {
                  const r = payload?.[0]?.payload as StoreRow | undefined;
                  if (!active || !r) return null;
                  return (
                    <div className="bg-background grid gap-1 rounded-lg border px-3 py-2 text-xs shadow-xl">
                      <p className="text-sm font-medium">{r.dealer_name}</p>
                      <p className="text-muted-foreground">
                        {r.brand} · {r.city}, {r.region}
                      </p>
                      <p className="tabular">
                        {fmt.num(r.units_sold)} {t("ov.trend.units").toLowerCase()} · {fmt.money(r.revenue)}
                      </p>
                      <p className="tabular">
                        {r.attainment_pct === null ? t("rg.no_target") : t("rg.of_target", { v: fmt.pct(r.attainment_pct, 0) })} · {yoy(r.yoy_units_pct)} {t("rg.yoy")}
                      </p>
                    </div>
                  );
                }}
              />
              <Scatter
                data={located}
                shape={(props: { cx?: number; cy?: number; size?: number; payload?: StoreRow }) => (
                  <circle
                    cx={props.cx}
                    cy={props.cy}
                    r={Math.sqrt((props.size ?? 100) / Math.PI)}
                    fill={attainmentColor(props.payload?.attainment_pct)}
                    fillOpacity={0.8}
                    stroke="var(--background)"
                    strokeWidth={1.5}
                  />
                )}
              />
            </ScatterChart>
          </ChartContainer>
        </Panel>
      )}

      <Panel title={t("rg.rank.title")} action={<Legend />}>
        <ChartContainer config={chartConfig} className="w-full" style={{ height: Math.max(320, 26 * ranking.length + 24) }}>
          <BarChart data={ranking} layout="vertical" margin={{ left: 0, right: 56, top: 4 }}>
            <CartesianGrid horizontal={false} />
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
                    <p className="tabular">{fmt.num(r.units_sold)} {t("ov.trend.units").toLowerCase()} · {r.attainment_pct === null ? t("rg.no_target") : t("rg.of_target", { v: fmt.pct(r.attainment_pct, 0) })}</p>
                  </div>
                );
              }}
            />
            <Bar dataKey="units_sold" radius={4} barSize={14}>
              <LabelList dataKey="units_sold" position="right" fontSize={12} className="fill-foreground" formatter={(v: unknown) => fmt.num(Number(v))} />
            </Bar>
          </BarChart>
        </ChartContainer>
      </Panel>

      <Panel title={t("rg.score.title")}>
        <DataTable columns={columns} rows={rows} rowKey={(r) => r.dealer_id} initialSort={{ key: "units", dir: "desc" }} />
      </Panel>

      {weakest && strongest && (
        <div className="grid gap-4 md:grid-cols-2">
          <Alert>
            <Award className="text-success" />
            <AlertTitle>{t("rg.strong", { name: strongest.dealer_name })}</AlertTitle>
            <AlertDescription>
              {t("rg.summary", { units: fmt.num(strongest.units_sold), pace: fmt.pct(strongest.attainment_pct, 0), yoy: yoy(strongest.yoy_units_pct) })}
            </AlertDescription>
          </Alert>
          <Alert>
            <TriangleAlert className="text-warning" />
            <AlertTitle>{t("rg.weak", { name: weakest.dealer_name })}</AlertTitle>
            <AlertDescription>
              {t("rg.summary", { units: fmt.num(weakest.units_sold), pace: fmt.pct(weakest.attainment_pct, 0), yoy: yoy(weakest.yoy_units_pct) })}
              {alsoDown.length > 0 && ` ${t("rg.also_down", { names: alsoDown.map((r) => r.dealer_name).join(", ") })}`}
            </AlertDescription>
          </Alert>
        </div>
      )}
    </div>
  );
}
