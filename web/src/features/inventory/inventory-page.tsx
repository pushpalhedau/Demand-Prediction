"use client";

import { CircleCheck, Download } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, Scatter, ScatterChart, XAxis, YAxis, ZAxis } from "recharts";
import { Panel, PanelSkeleton } from "@/components/data/chart-card";
import { DataTable, type Column } from "@/components/data/data-table";
import { KpiCard, KpiSkeletonRow } from "@/components/data/kpi-card";
import { PageHeader } from "@/components/data/page-header";
import { QueryBoundary } from "@/components/data/query-boundary";
import { EmptyState } from "@/components/data/states";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, type ChartConfig } from "@/components/ui/chart";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { downloadCsv } from "@/lib/csv";
import { useDashboardQuery } from "@/lib/query";
import { useFormat, usePresentation } from "@/lib/session";
import type { StockHealth } from "@/lib/types";

type Health = Required<Pick<StockHealth, "kpis" | "aging" | "stock_vs_demand" | "reorder" | "aged" | "thresholds">> & Pick<StockHealth, "coverage">;

const POSITION_COLOR = { healthy: "var(--success)", below_reorder: "var(--warning)", overstocked: "var(--destructive)" } as const;
const AGING_COLORS = ["var(--success)", "var(--chart-1)", "var(--warning)", "var(--destructive)"];

export function InventoryPage() {
  const { t } = usePresentation();
  const [agedDays, setAgedDays] = useState(90);
  const query = useDashboardQuery<StockHealth>("inv-health", "/api/inventory/stock-health", { params: { aged_days: agedDays } });
  return (
    <>
      <PageHeader
        title={t("tab.inventory")}
        description={t("inv.subtitle")}
        actions={
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground text-xs">{t("inv.aged_threshold")}</span>
            <Select value={String(agedDays)} onValueChange={(v) => setAgedDays(Number(v))}>
              <SelectTrigger size="sm" className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                {(query.data?.thresholds ?? [45, 60, 75, 90, 120]).map((d) => (
                  <SelectItem key={d} value={String(d)}>{t("inv.days", { n: d })}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        }
      />
      <QueryBoundary query={query} skeleton={<div className="space-y-6"><KpiSkeletonRow /><PanelSkeleton height={340} /></div>}>
        {(d) => (d.status === "ok" ? <Content data={d as Health} /> : <EmptyState title={t("inv.empty")} />)}
      </QueryBoundary>
    </>
  );
}

function Content({ data }: { data: Health }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  const k = data.kpis;
  const healthy = k.net_days_supply >= k.healthy_low && k.net_days_supply <= k.healthy_high;
  const supplyNote =
    k.net_days_supply < k.healthy_low
      ? t("inv.kpi.below", { n: fmt.num(k.healthy_low - k.net_days_supply) })
      : k.net_days_supply > k.healthy_high
        ? t("inv.kpi.above", { n: fmt.num(k.net_days_supply - k.healthy_high) })
        : t("inv.kpi.inside", { low: k.healthy_low, high: k.healthy_high });

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label={t("inv.kpi.units")} value={fmt.num(k.units)} note={t("inv.kpi.pipeline", { transit: fmt.num(k.in_transit), order: fmt.num(k.on_order) })} />
        <KpiCard label={t("inv.kpi.supply")} value={t("inv.days", { n: fmt.num(k.net_days_supply) })} note={supplyNote} tone={healthy ? "positive" : "negative"} />
        <KpiCard label={t("inv.kpi.cost")} value={fmt.money(k.cost_value)} note={t("inv.kpi.carry", { carry: fmt.money(k.carry_per_month), floor: fmt.money(k.floorplan_per_month) })} />
        <KpiCard
          label={t("inv.kpi.aged", { n: k.aged_days })}
          value={t("inv.units", { n: fmt.num(k.aged_units) })}
          note={t("inv.kpi.aged_note", { capital: fmt.money(k.aged_capital), burn: fmt.money(k.aged_burn_per_month) })}
          tone="negative"
        />
      </div>

      <Coverage coverage={data.coverage} />

      <div className="grid gap-6 xl:grid-cols-2">
        <AgingLadder aging={data.aging} />
        <StockVsDemand data={data.stock_vs_demand} />
      </div>

      <Reorder rows={data.reorder} />
      <AgedStock rows={data.aged} days={k.aged_days} />
    </div>
  );
}

function Coverage({ coverage }: { coverage: Health["coverage"] }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  if (!coverage) return <EmptyState title={t("inv.cov.none")} />;
  const config = { units: { label: t("inv.cov.demand"), color: "var(--chart-1)" } } satisfies ChartConfig;
  const rows = coverage.demand.map((d) => ({ label: t("inv.cov.next", { n: d.days }), units: d.units }));
  const top = Math.max(coverage.with_pipeline, ...coverage.demand.map((d) => d.units)) * 1.18;
  return (
    <Panel title={t("inv.cov.title")} description={t("inv.cov.caption")}>
      <ChartContainer config={config} className="h-[320px] w-full">
        <BarChart data={rows} margin={{ left: 4, right: 12, top: 24 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
          <YAxis domain={[0, top]} tickFormatter={(v: number) => fmt.compact(v)} tickLine={false} axisLine={false} width={52} />
          <ChartTooltip
            cursor={{ fill: "var(--muted)", opacity: 0.5 }}
            content={({ active, payload }) => {
              const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
              return active && r ? (
                <div className="bg-background rounded-lg border px-3 py-2 text-xs shadow-xl">
                  <span className="font-medium">{r.label}</span> <span className="tabular ml-2">{t("inv.cov.tip", { n: fmt.num(r.units) })}</span>
                </div>
              ) : null;
            }}
          />
          <ReferenceLine y={coverage.on_hand} stroke="var(--success)" strokeWidth={2} label={{ value: t("inv.cov.now", { n: fmt.num(coverage.on_hand) }), position: "insideTopLeft", fill: "var(--success)", fontSize: 11 }} />
          <ReferenceLine y={coverage.with_pipeline} stroke="var(--foreground)" strokeDasharray="5 4" label={{ value: t("inv.cov.pipeline", { n: fmt.num(coverage.with_pipeline) }), position: "insideTopLeft", fill: "var(--foreground)", fontSize: 11 }} />
          <Bar dataKey="units" fill="var(--color-units)" radius={[4, 4, 0, 0]} maxBarSize={88} />
        </BarChart>
      </ChartContainer>
    </Panel>
  );
}

function AgingLadder({ aging }: { aging: Health["aging"] }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  const [metric, setMetric] = useState<"units" | "capital">("units");
  const rows = aging.map((a, i) => ({ ...a, value: metric === "units" ? a.units : a.capital_amt, fill: AGING_COLORS[i % AGING_COLORS.length] }));
  const config = { value: { label: metric === "units" ? t("ov.trend.units") : t("inv.capital"), color: "var(--chart-1)" } } satisfies ChartConfig;
  return (
    <Panel
      title={t("inv.aging.title")}
      action={
        <ToggleGroup type="single" variant="outline" size="sm" value={metric} onValueChange={(v) => v && setMetric(v as "units" | "capital")} aria-label={t("inv.aging.title")}>
          <ToggleGroupItem value="units">{t("ov.trend.units")}</ToggleGroupItem>
          <ToggleGroupItem value="capital">{t("inv.capital")}</ToggleGroupItem>
        </ToggleGroup>
      }
    >
      <ChartContainer config={config} className="h-[300px] w-full">
        <BarChart data={rows} margin={{ left: 4, right: 12, top: 16 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="bucket" tickLine={false} axisLine={false} tickMargin={8} />
          <YAxis tickFormatter={(v: number) => (metric === "units" ? fmt.compact(v) : fmt.money(v))} tickLine={false} axisLine={false} width={metric === "units" ? 52 : 84} />
          <ChartTooltip
            cursor={{ fill: "var(--muted)", opacity: 0.5 }}
            content={({ active, payload }) => {
              const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
              return active && r ? (
                <div className="bg-background grid gap-0.5 rounded-lg border px-3 py-2 text-xs shadow-xl">
                  <p className="text-sm font-medium">{r.bucket}</p>
                  <p className="tabular">{t("inv.units", { n: fmt.num(r.units) })} · {fmt.money(r.capital_amt)}</p>
                  <p className="text-muted-foreground">{t("inv.aging.lines", { n: r.lines })}</p>
                </div>
              ) : null;
            }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={72}>
            {rows.map((r) => <Cell key={r.bucket} fill={r.fill} />)}
          </Bar>
        </BarChart>
      </ChartContainer>
    </Panel>
  );
}

function StockVsDemand({ data }: { data: Health["stock_vs_demand"] }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  const config = {
    healthy: { label: t("inv.pos.healthy"), color: POSITION_COLOR.healthy },
    below_reorder: { label: t("inv.pos.below"), color: POSITION_COLOR.below_reorder },
    overstocked: { label: t("inv.pos.over"), color: POSITION_COLOR.overstocked },
    stockout: { label: t("inv.pos.out"), color: "var(--destructive)" },
  } satisfies ChartConfig;
  const xmax = Math.max(1, ...data.points.map((p) => p.demand_forecast_30d), ...data.stocked_out.map((s) => s.demand_forecast_30d));
  const byPosition = (pos: keyof typeof POSITION_COLOR) => data.points.filter((p) => p.position === pos);
  const tip = (title: string, lines: string[]) => (
    <div className="bg-background grid gap-0.5 rounded-lg border px-3 py-2 text-xs shadow-xl">
      <p className="text-sm font-medium">{title}</p>
      {lines.map((l) => <p key={l} className="text-muted-foreground tabular">{l}</p>)}
    </div>
  );
  return (
    <Panel title={t("inv.svd.title")} footer={t("inv.svd.note", { low: data.healthy_low, high: data.healthy_high })}>
      <ChartContainer config={config} className="h-[300px] w-full">
        <ScatterChart margin={{ left: 4, right: 16, top: 12, bottom: 8 }}>
          <CartesianGrid />
          <XAxis type="number" dataKey="demand_forecast_30d" name={t("inv.svd.x")} domain={[0, xmax]} tickLine={false} axisLine={false} tickFormatter={(v: number) => fmt.num(v)} label={{ value: t("inv.svd.x"), position: "insideBottom", offset: -4, fontSize: 11, fill: "var(--muted-foreground)" }} height={44} />
          <YAxis type="number" dataKey="current_stock" name={t("inv.svd.y")} tickLine={false} axisLine={false} width={44} />
          <ZAxis type="number" dataKey="inventory_value_amt" range={[30, 260]} />
          {[data.healthy_low, data.healthy_high].map((days, i) => (
            <ReferenceLine key={days} segment={[{ x: 0, y: 0 }, { x: xmax, y: (xmax * days) / 30 }]} stroke="var(--muted-foreground)" strokeDasharray={i === 0 ? "2 4" : "6 4"} ifOverflow="hidden" />
          ))}
          <ChartTooltip
            cursor={{ strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              const r = payload?.[0]?.payload as { brand: string; model: string; dealer_name: string; days_of_supply?: number; demand_forecast_30d: number; current_stock?: number } | undefined;
              if (!active || !r) return null;
              return tip(`${r.brand} ${r.model}`, [r.dealer_name, `${t("inv.svd.x")}: ${fmt.num(r.demand_forecast_30d)}`, r.current_stock === undefined ? t("inv.pos.out") : `${t("inv.svd.y")}: ${fmt.num(r.current_stock)} · ${t("inv.days", { n: fmt.num(r.days_of_supply ?? 0) })}`]);
            }}
          />
          <ChartLegend content={<ChartLegendContent />} />
          <Scatter name="healthy" data={byPosition("healthy")} fill="var(--color-healthy)" fillOpacity={0.75} />
          <Scatter name="below_reorder" data={byPosition("below_reorder")} fill="var(--color-below_reorder)" fillOpacity={0.8} />
          <Scatter name="overstocked" data={byPosition("overstocked")} fill="var(--color-overstocked)" fillOpacity={0.8} />
          <Scatter name="stockout" data={data.stocked_out.map((s) => ({ ...s, current_stock: 0 }))} fill="var(--color-stockout)" shape="cross" legendType="cross" />
        </ScatterChart>
      </ChartContainer>
    </Panel>
  );
}

function Reorder({ rows }: { rows: Health["reorder"] }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  type Row = Health["reorder"][number];
  const cover = (r: Row) =>
    r.coverage.kind === "inbound"
      ? t("inv.cover.inbound", { n: r.coverage.units ?? 0 })
      : r.coverage.kind === "dealer_trade"
        ? t("inv.cover.trade", { store: r.coverage.store ?? "", n: r.coverage.units ?? 0 })
        : t("inv.cover.factory");
  const columns: Column<Row>[] = [
    { key: "dealer", header: t("inv.col.dealer"), cell: (r) => <span className="font-medium">{r.dealer}</span>, sort: (r) => r.dealer },
    { key: "vehicle", header: t("inv.col.vehicle"), cell: (r) => r.vehicle, sort: (r) => r.vehicle },
    { key: "hand", header: t("inv.col.on_hand"), align: "right", cell: (r) => fmt.num(r.on_hand), sort: (r) => r.on_hand },
    { key: "inbound", header: t("inv.col.inbound"), align: "right", cell: (r) => fmt.num(r.inbound), sort: (r) => r.inbound },
    { key: "point", header: t("inv.col.reorder_pt"), align: "right", cell: (r) => fmt.num(r.reorder_point), sort: (r) => r.reorder_point },
    { key: "short", header: t("inv.col.short"), align: "right", cell: (r) => fmt.num(r.net_short), sort: (r) => r.net_short },
    { key: "lead", header: t("inv.col.lead"), align: "right", cell: (r) => t("inv.days_short", { n: r.lead_time_days }), sort: (r) => r.lead_time_days },
    { key: "gp", header: t("inv.col.gp"), align: "right", cell: (r) => fmt.money(r.gp_at_risk, false), sort: (r) => r.gp_at_risk },
    { key: "cover", header: t("inv.col.coverage"), cell: cover },
    {
      key: "urgency",
      header: t("inv.col.urgency"),
      cell: (r) => (
        <div className="flex w-28 items-center gap-2">
          <Progress value={r.urgency} className="h-1.5" />
          <span className="tabular text-xs">{fmt.num(r.urgency)}</span>
        </div>
      ),
      sort: (r) => r.urgency,
    },
  ];
  return (
    <Panel
      title={t("inv.reorder.title")}
      action={rows.length > 0 && <ExportButton onClick={() => downloadCsv("reorder_priorities.csv", columns.map((c) => c.header), rows.map((r) => [r.dealer, r.vehicle, r.on_hand, r.inbound, r.reorder_point, r.net_short, r.lead_time_days, r.gp_at_risk, cover(r), r.urgency]))} />}
    >
      {rows.length ? <DataTable columns={columns} rows={rows} rowKey={(r, i) => `${r.dealer}-${r.vehicle}-${i}`} initialSort={{ key: "urgency", dir: "desc" }} /> : <NoneNote text={t("inv.reorder.none")} />}
    </Panel>
  );
}

function AgedStock({ rows, days }: { rows: Health["aged"]; days: number }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  type Row = Health["aged"][number];
  const action = (r: Row) => (r.action.kind === "dealer_trade" ? t("inv.act.trade", { store: r.action.store ?? "" }) : t(`inv.act.${r.action.kind}`));
  const columns: Column<Row>[] = [
    { key: "dealer", header: t("inv.col.dealer"), cell: (r) => <span className="font-medium">{r.dealer}</span>, sort: (r) => r.dealer },
    { key: "vehicle", header: t("inv.col.vehicle"), cell: (r) => r.vehicle, sort: (r) => r.vehicle },
    { key: "units", header: t("inv.col.units"), align: "right", cell: (r) => fmt.num(r.units), sort: (r) => r.units },
    { key: "lot", header: t("inv.col.on_lot"), align: "right", cell: (r) => fmt.num(r.days_on_lot), sort: (r) => r.days_on_lot },
    { key: "dos", header: t("inv.col.dos"), align: "right", cell: (r) => fmt.num(r.days_of_supply), sort: (r) => r.days_of_supply },
    { key: "capital", header: t("inv.capital"), align: "right", cell: (r) => fmt.money(r.capital), sort: (r) => r.capital },
    { key: "burn", header: t("inv.col.burn"), align: "right", cell: (r) => fmt.money(r.monthly_burn, false), sort: (r) => r.monthly_burn },
    { key: "action", header: t("inv.col.action"), cell: action },
  ];
  return (
    <Panel
      title={t("inv.aged.title", { n: days })}
      action={rows.length > 0 && <ExportButton onClick={() => downloadCsv("aged_inventory_actions.csv", columns.map((c) => c.header), rows.map((r) => [r.dealer, r.vehicle, r.units, r.days_on_lot, r.days_of_supply, r.capital, r.monthly_burn, action(r)]))} />}
    >
      {rows.length ? <DataTable columns={columns} rows={rows} rowKey={(r, i) => `${r.dealer}-${r.vehicle}-${i}`} initialSort={{ key: "capital", dir: "desc" }} /> : <NoneNote text={t("inv.aged.none", { n: days })} />}
    </Panel>
  );
}

function ExportButton({ onClick }: { onClick: () => void }) {
  const { t } = usePresentation();
  return (
    <Button variant="outline" size="sm" onClick={onClick}>
      <Download /> {t("app.export_csv")}
    </Button>
  );
}

function NoneNote({ text }: { text: string }) {
  return (
    <Alert>
      <CircleCheck className="text-success" />
      <AlertDescription>{text}</AlertDescription>
    </Alert>
  );
}
