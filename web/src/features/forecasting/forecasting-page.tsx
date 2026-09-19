"use client";

import { useQuery } from "@tanstack/react-query";
import { SlidersHorizontal } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, LineChart, ReferenceDot, ReferenceLine, XAxis, YAxis } from "recharts";
import { ChartFrame } from "@/components/charts/chart-frame";
import { FORECAST_STROKE, ForecastGradient, XMarker } from "@/components/charts/forecast-marks";
import { bridge, joinSeries, type Row } from "@/components/charts/series";
import { valueTip } from "@/components/charts/tooltip";
import { PanelSkeleton } from "@/components/data/chart-card";
import { Insight } from "@/components/data/insight";
import { MetricStrip, MetricStripSkeleton, type Metric } from "@/components/data/metric-strip";
import { PageHeading } from "@/components/data/page-heading";
import { RichText } from "@/components/data/rich-text";
import { Section } from "@/components/data/section";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Button } from "@/components/ui/button";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { ApiError, api } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { dayName, formatMonth, monthName } from "@/lib/format";
import { useDashboardQuery } from "@/lib/query";
import { useFormat, useMe, usePresentation } from "@/lib/session";
import type { ForecastOptions, ForecastReport, Lever } from "@/lib/types";

type Target = "units_sold" | "total_revenue_incl_tax";
const ALL_BRANDS = "__all__";

/** Level monthly payment on a loan at an APR: the same formula the what-if model uses. */
function monthlyPayment(apr: number, loan: number, months: number): number {
  const r = apr / 100 / 12;
  return r <= 0 ? loan / months : (loan * r) / (1 - (1 + r) ** -months);
}

export function ForecastingPage() {
  const { t } = usePresentation();
  const fmt = useFormat();
  const { data: me } = useMe();
  const { filters, apiParams } = useFilters();

  const [target, setTarget] = useState<Target>("units_sold");
  const [horizon, setHorizon] = useState<3 | 6 | 12>(3);
  const [brandPick, setBrandPick] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Record<string, number>>({});
  const [pending, setPending] = useState<Record<string, number>>({});
  const brand = brandPick ?? (filters.brand || "");

  const options = useDashboardQuery<ForecastOptions>("fc-options", "/api/forecasting/options");
  const report = useQuery<ForecastReport>({
    queryKey: ["fc-report", apiParams, target, horizon, brand, overrides],
    queryFn: () =>
      api<ForecastReport>("/api/forecasting/report", {
        method: "POST",
        params: apiParams,
        body: { target, horizon_months: horizon, brand: brand || null, overrides: Object.keys(overrides).length ? overrides : null },
      }),
    staleTime: 5 * 60_000,
  });

  const isUnits = target === "units_sold";
  const word = isUnits ? t("cmp.word.units") : t("cmp.word.revenue");
  const value = (v: number) => (isUnits ? fmt.compact(v) : fmt.money(v));
  const leverLabel = (l: Lever) =>
    ({
      crude_oil_price_usd: `${t("fc.lever.crude")} (USD/${t("fc.barrel")})`,
      petrol_price_per_litre: `${t("fc.lever.petrol")} (${me?.organisation.currency ?? ""}/${t("fc.litre")})`,
      diesel_price_per_litre: `${t("fc.lever.diesel")} (${me?.organisation.currency ?? ""}/${t("fc.litre")})`,
      auto_loan_apr_pct: `${t("fc.lever.apr")} (%)`,
    })[l.key] ?? l.key;

  const scope = [
    brand || null,
    filters.category ? `${filters.category} ${t("fc.segment")}` : null,
    filters.region ? `${filters.region} ${t("fc.stores")}` : null,
    filters.fuel ? `${filters.fuel} ${t("fc.only")}` : null,
  ].filter(Boolean);

  const ok = report.data?.status === "ok" ? report.data : null;
  const h = ok?.headline;
  const headline = h
    ? t(h.yoy_pct === null ? "fc.head.noyoy" : "fc.head", { total: value(h.expected), word, n: horizon, pct: fmt.pct(h.yoy_pct, 0, true) })
    : t("fc.title");

  return (
    <div className="space-y-8">
      <PageHeading eyebrow={t("fc.title")} headline={headline} />

      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("fc.forecast")}>
          <Select value={target} onValueChange={(v) => setTarget(v as Target)}>
            <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="units_sold">{t("fc.units_sold")}</SelectItem>
              <SelectItem value="total_revenue_incl_tax">{t("sa.fc.revenue")}</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label={t("fc.looking_ahead")}>
          <Select value={String(horizon)} onValueChange={(v) => setHorizon(Number(v) as 3 | 6 | 12)}>
            <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
            <SelectContent>
              {[3, 6, 12].map((m) => (
                <SelectItem key={m} value={String(m)}>{t("fc.months", { n: m })}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label={t("filter.brand")}>
          <Select value={brand || ALL_BRANDS} onValueChange={(v) => setBrandPick(v === ALL_BRANDS ? "" : v)}>
            <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_BRANDS}>{t("fc.all_brands")}</SelectItem>
              {(options.data?.brands ?? []).map((b) => (
                <SelectItem key={b} value={b}>{b}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        {scope.length > 0 && <p className="text-muted-foreground pb-2 text-xs">{t("fc.scope")}: {scope.join(" · ")}</p>}
      </div>

      {options.data && options.data.levers.length > 0 && (
        <Collapsible defaultOpen={Object.keys(overrides).length > 0} className="border-y">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="h-12 w-full justify-start gap-2 rounded-none px-0 font-medium hover:bg-transparent">
              <SlidersHorizontal className="size-4" /> {t("fc.whatif.title")}
              {Object.keys(overrides).length > 0 && <span className="text-primary ml-2 text-xs">{t("fc.whatif.active")}</span>}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-5 pt-1 pb-5">
            <p className="text-muted-foreground text-sm">{t("fc.whatif.caption")}</p>
            <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
              {options.data.levers.map((l) => {
                const current = pending[l.key] ?? overrides[l.key] ?? l.current;
                const loan = options.data?.average_loan ?? 0;
                const pay = monthlyPayment(current, loan, 60);
                const base = monthlyPayment(l.current, loan, 60);
                return (
                  <div key={l.key} className="space-y-3">
                    <div className="flex items-baseline justify-between gap-2">
                      <Label className="text-sm">{leverLabel(l)}</Label>
                      <span className="tabular text-sm font-medium">{fmt.num(current, l.step < 1 ? 2 : 0)}</span>
                    </div>
                    <Slider min={l.min} max={l.max} step={l.step} value={[current]} onValueChange={([v]) => setPending((p) => ({ ...p, [l.key]: v ?? l.current }))} />
                    {l.key === "auto_loan_apr_pct" && loan > 0 && (
                      <p className="text-muted-foreground text-xs">
                        {t("fc.payment", { pay: fmt.money(pay), loan: fmt.money(loan), delta: `${pay >= base ? "+" : "−"}${fmt.money(Math.abs(pay - base))}` })}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() => {
                  const merged = { ...overrides, ...pending };
                  const changed = Object.fromEntries(Object.entries(merged).filter(([k, v]) => Math.abs(v - (options.data?.levers.find((l) => l.key === k)?.current ?? v)) > 1e-6));
                  setOverrides(changed);
                  setPending({});
                }}
              >
                {t("fc.apply")}
              </Button>
              <Button size="sm" variant="outline" onClick={() => { setOverrides({}); setPending({}); }}>
                {t("fc.reset")}
              </Button>
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}

      {report.isPending ? (
        <div className="space-y-8" aria-busy>
          <MetricStripSkeleton />
          <PanelSkeleton height={440} />
          <p className="text-muted-foreground text-center text-sm">{t("fc.training")}</p>
        </div>
      ) : report.isError ? (
        <ErrorState message={report.error.message} reference={report.error instanceof ApiError ? report.error.reference : undefined} />
      ) : ok ? (
        <Result data={ok} target={target} horizon={horizon} />
      ) : (
        <EmptyState title={t(`fc.status.${report.data.status}`)}>{report.data.status === "no_data" ? t("fc.status.no_data_hint") : undefined}</EmptyState>
      )}
    </div>
  );
}

function Result({ data: d, target, horizon }: { data: ForecastReport; target: Target; horizon: number }) {
  const { t, lang } = usePresentation();
  const fmt = useFormat();
  const isUnits = target === "units_sold";
  const h = d.headline!;
  const word = isUnits ? t("cmp.word.units") : t("cmp.word.revenue");
  const value = (v: number) => (isUnits ? fmt.compact(v) : fmt.money(v));
  const exact = (v: number) => (isUnits ? fmt.num(v) : fmt.money(v, false));
  const busiest = d.busiest_month ? monthName(d.busiest_month, lang) : null;

  const chart = useMemo(() => {
    if (!d.history || !d.forecast) return null;
    const history = d.history.map((p) => ({ x: p.x, y: p.y }));
    const last = history[history.length - 1];
    const join = (key: "expected" | "low" | "high") => bridge(history, d.forecast!.map((f) => ({ x: f.x, y: f[key] })));
    const rows = joinSeries({ actual: history, expected: join("expected"), low: join("low"), high: join("high") }).map((r) => ({ ...r, band: typeof r.low === "number" && typeof r.high === "number" ? [r.low, r.high] : null }) as unknown as Row & { band: number[] | null });
    const end = d.forecast[d.forecast.length - 1];
    return { rows, last, end, divider: d.forecast[0]?.x };
  }, [d]);

  const config = {
    actual: { label: t("fc.booked"), color: "var(--chart-1)" },
    expected: { label: t("fc.expected"), color: "var(--brand-to)" },
    low: { label: t("fc.conservative"), color: "var(--muted-foreground)" },
    high: { label: t("fc.optimistic"), color: "var(--muted-foreground)" },
    band: { label: t("fc.range"), color: "var(--brand-from)" },
  } satisfies ChartConfig;

  const metrics: Metric[] = [
    {
      label: t("fc.kpi.expected", { word, n: horizon }),
      value: value(h.expected),
      delta: h.yoy_pct === null ? null : { text: t("fc.vs_last_year", { pct: fmt.pct(h.yoy_pct, 0, true) }), tone: h.yoy_pct >= 0 ? "positive" : "negative" },
      spark: d.history?.map((p) => p.y),
    },
    { label: t("fc.kpi.range"), value: `${value(h.low)} – ${value(h.high)}`, note: t("fc.kpi.range_help", { pct: h.confidence_pct }) },
    {
      label: t("fc.kpi.runrate"),
      value: value(h.run_rate),
      delta: h.run_rate_delta_pct === null ? null : { text: t("fc.vs_trailing", { pct: fmt.pct(h.run_rate_delta_pct, 0, true) }), tone: h.run_rate_delta_pct >= 0 ? "positive" : "negative" },
    },
  ];

  return (
    <div className="space-y-8">
      {d.what_if?.active && (
        <p className="bg-accent text-accent-foreground rounded-md px-3 py-2 text-sm">
          <RichText text={t("fc.whatif.impact", { word, pct: fmt.pct(d.what_if.net_pct, 1, true), value: value(d.what_if.value_shift) })} />
        </p>
      )}
      <MetricStrip metrics={metrics} />

      {chart && (
        <ChartFrame
          headline={t("fc.chart.head", { n: horizon, pct: h.confidence_pct })}
          description={
            <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="flex items-center gap-1.5"><span className="bg-chart-1 h-0.5 w-4 rounded-full" />{t("fc.booked")}</span>
              <span className="flex items-center gap-1.5"><span className="brand-gradient h-0.5 w-4 rounded-full" />{t("fc.expected")}</span>
              <span className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-[2px]" style={{ background: "color-mix(in oklch, var(--brand-from) 22%, transparent)" }} />{t("fc.range")}</span>
            </span>
          }
          csv={{
            filename: "demand_forecast.csv",
            headers: [t("ov.export.month"), t("fc.booked"), t("fc.expected"), t("fc.conservative"), t("fc.optimistic")],
            rows: chart.rows.map((r) => [r.x, r.actual, r.expected, r.low, r.high]),
          }}
        >
          {(height) => (
            <ChartContainer config={config} className="w-full" style={{ height: height + 40 }}>
              <ComposedChart data={chart.rows} margin={{ left: 0, right: 132, top: 16 }}>
                <ForecastGradient />
                <CartesianGrid vertical={false} strokeOpacity={0.6} />
                <XAxis dataKey="x" tickFormatter={(v: string) => formatMonth(v, lang)} tickLine={false} axisLine={false} tickMargin={10} minTickGap={24} />
                <YAxis tickFormatter={(v: number) => value(v)} tickLine={false} axisLine={false} width={isUnits ? 52 : 88} domain={["auto", "auto"]} />
                <ChartTooltip
                  cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }}
                  content={<ChartTooltipContent labelFormatter={(_, p) => formatMonth(String(p?.[0]?.payload?.x ?? ""), lang)} formatter={valueTip(config, (v) => exact(v))} />}
                />
                {chart.divider && <ReferenceLine x={chart.divider} stroke="var(--muted-foreground)" strokeDasharray="3 3" strokeOpacity={0.6} />}
                <Area dataKey="band" stroke="none" fill="var(--color-band)" fillOpacity={0.14} legendType="none" tooltipType="none" />
                <Line dataKey="actual" stroke="var(--color-actual)" strokeWidth={2.25} dot={{ r: 2.5 }} connectNulls />
                <Line dataKey="high" stroke="var(--muted-foreground)" strokeOpacity={0.7} strokeWidth={1.25} strokeDasharray="2 4" dot={false} connectNulls />
                <Line dataKey="low" stroke="var(--muted-foreground)" strokeOpacity={0.7} strokeWidth={1.25} strokeDasharray="2 4" dot={false} connectNulls />
                <Line dataKey="expected" stroke={FORECAST_STROKE} strokeWidth={3} strokeLinecap="round" dot={{ r: 3, fill: "var(--brand-to)", strokeWidth: 0 }} connectNulls />
                {chart.last && <ReferenceDot x={chart.last.x} y={chart.last.y} ifOverflow="visible" shape={(p: { cx?: number; cy?: number }) => <XMarker cx={p.cx} cy={p.cy} />} />}
                {chart.end && (
                  <>
                    <ReferenceDot x={chart.end.x} y={chart.end.high} r={0} ifOverflow="visible" label={{ value: `${t("fc.optimistic")} · ${value(h.high)}`, position: "right", fill: "var(--muted-foreground)", fontSize: 11 }} />
                    <ReferenceDot x={chart.end.x} y={chart.end.expected} r={0} ifOverflow="visible" label={{ value: `${t("fc.expected")} · ${value(h.expected)}`, position: "right", fill: "var(--foreground)", fontSize: 12, fontWeight: 600 }} />
                    <ReferenceDot x={chart.end.x} y={chart.end.low} r={0} ifOverflow="visible" label={{ value: `${t("fc.conservative")} · ${value(h.low)}`, position: "right", fill: "var(--muted-foreground)", fontSize: 11 }} />
                  </>
                )}
              </ComposedChart>
            </ChartContainer>
          )}
        </ChartFrame>
      )}

      <div className="grid gap-x-10 gap-y-8 lg:grid-cols-2">
        {d.seasonality?.monthly ? (
          <Section title={t("fc.season.month")}>
            <ChartContainer config={{ effect: { label: t("fc.effect"), color: "var(--chart-1)" } }} className="h-[240px] w-full">
              <LineChart data={d.seasonality.monthly.map((m) => ({ ...m, label: monthName(m.month, lang) }))} margin={{ left: 0, right: 12, top: 8 }}>
                <CartesianGrid vertical={false} strokeOpacity={0.6} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
                <YAxis tickFormatter={(v: number) => fmt.num(v, 1)} tickLine={false} axisLine={false} width={44} />
                <ReferenceLine y={0} stroke="var(--muted-foreground)" />
                <ChartTooltip cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }} content={<ChartTooltipContent hideLabel formatter={valueTip({ effect: { label: t("fc.effect") } }, (v) => fmt.num(v, 2))} />} />
                <Line dataKey="effect" stroke="var(--color-effect)" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ChartContainer>
          </Section>
        ) : (
          <EmptyState title={t("fc.season.none")} />
        )}
        {d.seasonality?.weekly ? (
          <Section title={t("fc.season.week")}>
            <ChartContainer config={{ effect: { label: t("fc.effect"), color: "var(--chart-2)" } }} className="h-[240px] w-full">
              <BarChart data={d.seasonality.weekly.map((w) => ({ ...w, label: dayName(w.day, lang) }))} margin={{ left: 0, right: 12, top: 8 }}>
                <CartesianGrid vertical={false} strokeOpacity={0.6} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
                <YAxis tickFormatter={(v: number) => fmt.num(v, 1)} tickLine={false} axisLine={false} width={44} />
                <ReferenceLine y={0} stroke="var(--muted-foreground)" />
                <ChartTooltip cursor={{ fill: "var(--muted)", opacity: 0.5 }} content={<ChartTooltipContent hideLabel formatter={valueTip({ effect: { label: t("fc.effect") } }, (v) => fmt.num(v, 2))} />} />
                <Bar dataKey="effect" fill="var(--color-effect)" radius={3} />
              </BarChart>
            </ChartContainer>
          </Section>
        ) : (
          <EmptyState title={t("fc.season.none")} />
        )}
      </div>

      <Section title={t("fc.plan.tag")}>
        <Insight
          rank={1}
          tag={t("fc.plan.tag")}
          accent="var(--primary)"
          title={t(isUnits ? "fc.plan.title.units" : "fc.plan.title.revenue", { total: value(h.expected), n: horizon })}
          detail={<RichText text={`${busiest ? t("fc.plan.busiest", { month: busiest }) : ""}${h.yoy_pct === null ? "" : ` ${t("fc.plan.yoy", { pct: fmt.pct(h.yoy_pct, 0, true) })}`}`.trim()} />}
          value={value(h.expected)}
          valueCaption={t("fc.expected")}
          valueTone="neutral"
          meta={<span className="text-muted-foreground text-xs">{t("fc.kpi.range_help", { pct: h.confidence_pct })}</span>}
        />
      </Section>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-muted-foreground text-xs">{label}</Label>
      {children}
    </div>
  );
}
