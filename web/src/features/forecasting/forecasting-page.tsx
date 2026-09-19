"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleCheck, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";
import { bridge, joinSeries } from "@/components/charts/series";
import { valueTip } from "@/components/charts/tooltip";
import { Panel, PanelSkeleton } from "@/components/data/chart-card";
import { KpiCard, KpiSkeletonRow } from "@/components/data/kpi-card";
import { PageHeader } from "@/components/data/page-header";
import { EmptyState, ErrorState } from "@/components/data/states";
import { RichText } from "@/components/data/rich-text";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
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

/** Level monthly payment on a loan at an APR — the same formula the what-if model uses. */
function monthlyPayment(apr: number, loan: number, months: number): number {
  const r = apr / 100 / 12;
  return r <= 0 ? loan / months : (loan * r) / (1 - (1 + r) ** -months);
}

export function ForecastingPage() {
  const { t, lang } = usePresentation();
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

  const chart = useMemo(() => {
    const d = report.data;
    if (d?.status !== "ok" || !d.history || !d.forecast) return null;
    const history = d.history.map((p) => ({ x: p.x, y: p.y }));
    const last = history[history.length - 1];
    const join = (key: "expected" | "low" | "high") => bridge(history, d.forecast!.map((f) => ({ x: f.x, y: f[key] })));
    const rows = joinSeries({ actual: history, expected: join("expected"), low: join("low"), high: join("high") }).map((r) => ({
      ...r,
      band: typeof r.low === "number" && typeof r.high === "number" ? [r.low, r.high] : null,
    }));
    const config = {
      actual: { label: t("fc.booked"), color: "var(--chart-4)" },
      expected: { label: t("fc.expected"), color: "var(--chart-1)" },
      low: { label: t("fc.conservative"), color: "var(--destructive)" },
      high: { label: t("fc.optimistic"), color: "var(--success)" },
      band: { label: t("fc.range"), color: "var(--chart-1)" },
    } satisfies ChartConfig;
    return { rows, config, divider: d.forecast[0]?.x, lastBooked: last?.x };
  }, [report.data, t]);

  return (
    <>
      <PageHeader title={t("fc.title")} description={t("fc.subtitle")} />

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
        <Collapsible defaultOpen={Object.keys(overrides).length > 0} className="rounded-xl border">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="h-12 w-full justify-start gap-2 rounded-xl px-5 font-medium">
              <SlidersHorizontal className="size-4" /> {t("fc.whatif.title")}
              {Object.keys(overrides).length > 0 && <span className="text-primary ml-2 text-xs">{t("fc.whatif.active")}</span>}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-5 border-t px-5 py-5">
            <p className="text-muted-foreground text-sm">{t("fc.whatif.caption")}</p>
            <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
              {options.data.levers.map((l) => {
                const current = pending[l.key] ?? overrides[l.key] ?? l.current;
                const loan = options.data?.average_loan ?? 0;
                return (
                  <div key={l.key} className="space-y-3">
                    <div className="flex items-baseline justify-between gap-2">
                      <Label className="text-sm">{leverLabel(l)}</Label>
                      <span className="tabular text-sm font-medium">{fmt.num(current, l.step < 1 ? 2 : 0)}</span>
                    </div>
                    <Slider
                      min={l.min}
                      max={l.max}
                      step={l.step}
                      value={[current]}
                      onValueChange={([v]) => setPending((p) => ({ ...p, [l.key]: v ?? l.current }))}
                    />
                    {l.key === "auto_loan_apr_pct" && loan > 0 && (
                      <p className="text-muted-foreground text-xs">
                        {t("fc.payment", {
                          pay: fmt.money(monthlyPayment(current, loan, 60)),
                          loan: fmt.money(loan),
                          delta: `${monthlyPayment(current, loan, 60) >= monthlyPayment(l.current, loan, 60) ? "+" : "−"}${fmt.money(Math.abs(monthlyPayment(current, loan, 60) - monthlyPayment(l.current, loan, 60)))}`,
                        })}
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
                  const changed = Object.fromEntries(
                    Object.entries(merged).filter(([k, v]) => Math.abs(v - (options.data?.levers.find((l) => l.key === k)?.current ?? v)) > 1e-6),
                  );
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
        <div className="space-y-6" aria-busy>
          <KpiSkeletonRow count={3} />
          <PanelSkeleton height={440} />
          <p className="text-muted-foreground text-center text-sm">{t("fc.training")}</p>
        </div>
      ) : report.isError ? (
        <ErrorState message={report.error.message} reference={report.error instanceof ApiError ? report.error.reference : undefined} />
      ) : report.data.status !== "ok" ? (
        <EmptyState title={t(`fc.status.${report.data.status}`)}>{report.data.status === "no_data" ? t("fc.status.no_data_hint") : undefined}</EmptyState>
      ) : (
        (() => {
          const d = report.data;
          const h = d.headline!;
          const word = isUnits ? t("cmp.word.units") : t("cmp.word.revenue");
          const busiest = d.busiest_month ? monthName(d.busiest_month, lang) : null;
          const plan = t(isUnits ? "fc.plan.units" : "fc.plan.revenue", { total: value(h.expected), n: horizon });
          return (
            <div className="space-y-6">
              {d.what_if?.active && (
                <Alert>
                  <AlertDescription>
                    <RichText text={t("fc.whatif.impact", { word, pct: fmt.pct(d.what_if.net_pct, 1, true), value: value(d.what_if.value_shift) })} />
                  </AlertDescription>
                </Alert>
              )}

              <div className="grid gap-4 md:grid-cols-3">
                <KpiCard
                  label={t("fc.kpi.expected", { word, n: horizon })}
                  value={value(h.expected)}
                  note={h.yoy_pct === null ? undefined : t("fc.vs_last_year", { pct: fmt.pct(h.yoy_pct, 0, true) })}
                  tone={h.yoy_pct === null ? "neutral" : h.yoy_pct >= 0 ? "positive" : "negative"}
                  trend
                />
                <KpiCard label={t("fc.kpi.range")} value={`${value(h.low)} – ${value(h.high)}`} note={t("fc.kpi.range_help", { pct: h.confidence_pct })} />
                <KpiCard
                  label={t("fc.kpi.runrate")}
                  value={value(h.run_rate)}
                  note={h.run_rate_delta_pct === null ? undefined : t("fc.vs_trailing", { pct: fmt.pct(h.run_rate_delta_pct, 0, true) })}
                  tone={h.run_rate_delta_pct === null ? "neutral" : h.run_rate_delta_pct >= 0 ? "positive" : "negative"}
                  trend
                />
              </div>

              {chart && (
                <Panel title={t("fc.chart.title")} description={t("fc.chart.caption", { pct: h.confidence_pct })}>
                  <ChartContainer config={chart.config} className="h-[400px] w-full">
                    <ComposedChart data={chart.rows} margin={{ left: 4, right: 12, top: 12 }}>
                      <CartesianGrid vertical={false} />
                      <XAxis dataKey="x" tickFormatter={(v: string) => formatMonth(v, lang)} tickLine={false} axisLine={false} tickMargin={8} minTickGap={24} />
                      <YAxis tickFormatter={(v: number) => value(v)} tickLine={false} axisLine={false} width={isUnits ? 52 : 84} domain={["auto", "auto"]} />
                      <ChartTooltip
                        content={
                          <ChartTooltipContent
                            labelFormatter={(_, p) => formatMonth(String(p?.[0]?.payload?.x ?? ""), lang)}
                            formatter={valueTip(chart.config, (v) => (isUnits ? fmt.num(v) : fmt.money(v, false)))}
                          />
                        }
                      />
                      <ChartLegend content={<ChartLegendContent />} />
                      {chart.divider && <ReferenceLine x={chart.divider} stroke="var(--muted-foreground)" strokeDasharray="3 3" label={{ value: `${t("fc.forecast_starts")} →`, position: "insideTopLeft", fill: "var(--muted-foreground)", fontSize: 11 }} />}
                      <Area dataKey="band" stroke="none" fill="var(--color-band)" fillOpacity={0.12} legendType="none" tooltipType="none" />
                      <Line dataKey="actual" stroke="var(--color-actual)" strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
                      <Line dataKey="high" stroke="var(--color-high)" strokeWidth={1.5} strokeDasharray="2 4" dot={false} connectNulls />
                      <Line dataKey="low" stroke="var(--color-low)" strokeWidth={1.5} strokeDasharray="2 4" dot={false} connectNulls />
                      <Line dataKey="expected" stroke="var(--color-expected)" strokeWidth={3} dot={{ r: 3.5 }} connectNulls />
                    </ComposedChart>
                  </ChartContainer>
                </Panel>
              )}

              <div className="grid gap-6 lg:grid-cols-2">
                {d.seasonality?.monthly ? (
                  <Panel title={t("fc.season.month")}>
                    <ChartContainer config={{ effect: { label: t("fc.effect"), color: "var(--chart-1)" } }} className="h-[240px] w-full">
                      <LineChart data={d.seasonality.monthly.map((m) => ({ ...m, label: monthName(m.month, lang) }))} margin={{ left: 4, right: 12, top: 8 }}>
                        <CartesianGrid vertical={false} />
                        <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
                        <YAxis tickFormatter={(v: number) => fmt.num(v, 1)} tickLine={false} axisLine={false} width={44} />
                        <ReferenceLine y={0} stroke="var(--muted-foreground)" />
                        <ChartTooltip content={<ChartTooltipContent hideLabel formatter={valueTip({ effect: { label: t("fc.effect") } }, (v) => fmt.num(v, 2))} />} />
                        <Line dataKey="effect" stroke="var(--color-effect)" strokeWidth={2.5} dot={{ r: 3 }} />
                      </LineChart>
                    </ChartContainer>
                  </Panel>
                ) : (
                  <EmptyState title={t("fc.season.none")} />
                )}
                {d.seasonality?.weekly ? (
                  <Panel title={t("fc.season.week")}>
                    <ChartContainer config={{ effect: { label: t("fc.effect"), color: "var(--chart-2)" } }} className="h-[240px] w-full">
                      <BarChart data={d.seasonality.weekly.map((w) => ({ ...w, label: dayName(w.day, lang) }))} margin={{ left: 4, right: 12, top: 8 }}>
                        <CartesianGrid vertical={false} />
                        <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
                        <YAxis tickFormatter={(v: number) => fmt.num(v, 1)} tickLine={false} axisLine={false} width={44} />
                        <ReferenceLine y={0} stroke="var(--muted-foreground)" />
                        <ChartTooltip cursor={{ fill: "var(--muted)", opacity: 0.5 }} content={<ChartTooltipContent hideLabel formatter={valueTip({ effect: { label: t("fc.effect") } }, (v) => fmt.num(v, 2))} />} />
                        <Bar dataKey="effect" fill="var(--color-effect)" radius={3} />
                      </BarChart>
                    </ChartContainer>
                  </Panel>
                ) : (
                  <EmptyState title={t("fc.season.none")} />
                )}
              </div>

              <Alert>
                <CircleCheck className="text-success" />
                <AlertDescription>
                  <RichText
                    text={`${plan}${busiest ? ` ${t("fc.plan.busiest", { month: busiest })}` : ""}${h.yoy_pct === null ? "" : ` ${t("fc.plan.yoy", { pct: fmt.pct(h.yoy_pct, 0, true) })}`}`}
                  />
                </AlertDescription>
              </Alert>
            </div>
          );
        })()
      )}
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-muted-foreground text-xs">{label}</Label>
      {children}
    </div>
  );
}
