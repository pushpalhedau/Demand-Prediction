"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";
import { valueTip } from "@/components/charts/tooltip";
import { Panel } from "@/components/data/chart-card";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Button } from "@/components/ui/button";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { formatMonth } from "@/lib/format";
import { useFormat, usePresentation } from "@/lib/session";
import type { ForecastCheck } from "@/lib/types";

type Target = "units_sold" | "total_revenue_incl_tax";

/** Does adding news signals improve the forecast? Trains a baseline and a news-aware model and lays them over the actuals. */
export function ForecastCheckPanel() {
  const { t, lang } = usePresentation();
  const fmt = useFormat();
  const { apiParams } = useFilters();
  const [horizon, setHorizon] = useState(90);
  const [target, setTarget] = useState<Target>("units_sold");

  const run = useMutation({
    mutationFn: () => api<ForecastCheck>("/api/sentiment/forecast-check", { method: "POST", params: apiParams, body: { target, horizon_days: horizon } }),
  });
  const isUnits = target === "units_sold";
  const config = {
    actual: { label: t("sa.fc.actual"), color: "var(--chart-4)" },
    standard: { label: t("sa.fc.standard"), color: "var(--chart-1)" },
    news_aware: { label: t("sa.fc.news_aware"), color: "var(--chart-5)" },
  } satisfies ChartConfig;

  return (
    <Panel title={t("sa.fc.title")}>
      <div className="space-y-6">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label className="text-muted-foreground text-xs">{t("sa.fc.horizon")}</Label>
            <Select value={String(horizon)} onValueChange={(v) => setHorizon(Number(v))}>
              <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
              <SelectContent>{[30, 60, 90, 180].map((d) => <SelectItem key={d} value={String(d)}>{t("inv.days", { n: d })}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-muted-foreground text-xs">{t("sa.fc.measure")}</Label>
            <Select value={target} onValueChange={(v) => setTarget(v as Target)}>
              <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="units_sold">{t("sa.fc.units")}</SelectItem>
                <SelectItem value="total_revenue_incl_tax">{t("sa.fc.revenue")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending && <Loader2 className="animate-spin" />} {t("sa.fc.run")}
          </Button>
        </div>

        {run.isPending && <p className="text-muted-foreground text-sm">{t("sa.fc.training")}</p>}
        {run.isError && <ErrorState message={run.error.message} />}
        {!run.data && !run.isPending && !run.isError && <EmptyState title={t("sa.fc.prompt")} />}
        {run.data?.status === "baseline_failed" && <ErrorState message={t("sa.fc.base_failed", { e: run.data.message ?? "" })} />}
        {run.data?.status === "ok" && run.data.rows && (
          <ChartContainer config={config} className="h-[360px] w-full">
            <LineChart data={run.data.rows} margin={{ left: 4, right: 12, top: 8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="x" tickFormatter={(v: string) => formatMonth(v, lang)} tickLine={false} axisLine={false} tickMargin={8} minTickGap={24} />
              <YAxis tickFormatter={(v: number) => (isUnits ? fmt.compact(v) : fmt.money(v))} tickLine={false} axisLine={false} width={isUnits ? 52 : 84} domain={["auto", "auto"]} />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    labelFormatter={(_, p) => formatMonth(String(p?.[0]?.payload?.x ?? ""), lang)}
                    formatter={valueTip(config, (v) => (isUnits ? fmt.num(v) : fmt.money(v, false)))}
                  />
                }
              />
              <ChartLegend content={<ChartLegendContent />} />
              {run.data.forecast_starts && <ReferenceLine x={run.data.forecast_starts} stroke="var(--muted-foreground)" strokeDasharray="4 4" />}
              <Line dataKey="actual" stroke="var(--color-actual)" strokeWidth={2} dot={{ r: 3 }} connectNulls />
              <Line dataKey="standard" stroke="var(--color-standard)" strokeWidth={2.5} dot={false} />
              <Line dataKey="news_aware" stroke="var(--color-news_aware)" strokeWidth={2.5} strokeDasharray="2 4" dot={false} connectNulls />
            </LineChart>
          </ChartContainer>
        )}
      </div>
    </Panel>
  );
}
