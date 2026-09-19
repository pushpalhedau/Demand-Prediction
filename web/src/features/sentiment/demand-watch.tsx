"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, XAxis, YAxis } from "recharts";
import { Panel } from "@/components/data/chart-card";
import { Insight } from "@/components/data/insight";
import { ErrorState } from "@/components/data/states";
import { Button } from "@/components/ui/button";
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart";
import { useFilters } from "@/lib/filters";
import { api } from "@/lib/api";
import { hasTranslation } from "@/lib/i18n";
import { safeUrl } from "@/lib/safe";
import { useFormat, usePresentation } from "@/lib/session";
import type { Article, SentimentOverview } from "@/lib/types";
import { actionable, direction, latest, themeDrivers } from "./signals";

const COLOR = { up: "var(--success)", down: "var(--destructive)", neutral: "var(--muted-foreground)" } as const;

export function DemandWatch({ stats, articles }: { stats: SentimentOverview["stats"]; articles: Article[] }) {
  const { t, tv, lang } = usePresentation();
  const { apiParams } = useFilters();
  const themeName = (key: string | null) => (key && hasTranslation(lang, `sa.theme.${key}`) ? t(`sa.theme.${key}`) : (key ?? "—"));

  const drivers = useMemo(
    () => themeDrivers(articles).map((d) => ({ name: themeName(d.theme), value: d.mean })).sort((a, b) => a.value - b.value),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [articles, lang],
  );
  const segments = useMemo(
    () => Object.entries(stats.segment_changes ?? {}).filter(([k]) => k !== "All").map(([k, v]) => ({ name: tv(k), value: v })).sort((a, b) => a.value - b.value),
    [stats, tv],
  );
  const quiet = articles.every((a) => direction(a) === "neutral");
  const signals = actionable(articles);

  const briefing = useMutation({ mutationFn: () => api<{ text: string }>("/api/sentiment/briefing", { method: "POST", params: apiParams }) });

  return (
    <div className="space-y-6">
      {!quiet && <Diverging title={t("sa.drivers.title")} rows={drivers} />}
      {segments.length > 0 && Math.max(...segments.map((s) => Math.abs(s.value))) >= 0.05 && (
        <Diverging title={t("sa.segment.title")} description={t("sa.segment.caption")} rows={segments} />
      )}

      <Panel title={signals.length ? t("sa.signals.title") : t("sa.latest.title")} description={signals.length ? undefined : t("sa.latest.caption")}>
        <div>
          {(signals.length ? signals : latest(articles)).map((a, i) => (
            <SignalRow key={`${a.url ?? a.title}-${i}`} rank={i + 1} article={a} themeName={themeName} />
          ))}
        </div>
      </Panel>

      <Panel title={t("sa.read.title")}>
        <div className="space-y-4">
          <Button variant="outline" onClick={() => briefing.mutate()} disabled={briefing.isPending}>
            {briefing.isPending && <Loader2 className="animate-spin" />} {t("sa.read.button")}
          </Button>
          {briefing.isPending && <p className="text-muted-foreground text-sm">{t("sa.read.spinner")}</p>}
          {briefing.isError && <ErrorState message={briefing.error.message} />}
          {briefing.data && <p className="bg-muted/40 rounded-lg p-4 text-sm leading-relaxed whitespace-pre-wrap">{briefing.data.text}</p>}
        </div>
      </Panel>
    </div>
  );
}

function SignalRow({ rank, article: a, themeName: nameOf }: { rank: number; article: Article; themeName: (k: string | null) => string }) {
  const { t, tv, lang } = usePresentation();
  const fmt = useFormat();
  const dir = direction(a);
  const seg = a.affected_category ?? "All";
  const exposureKey = `sa.exp.${a.theme}`;
  const exposure = hasTranslation(lang, exposureKey) ? t(exposureKey) : seg === "All" ? t("sa.card.exposure_all") : t("sa.card.exposure_seg", { seg: tv(seg) });
  const href = safeUrl(a.url);
  const title = (a.title ?? t("sa.card.untitled")).slice(0, 150);
  return (
    <Insight
      rank={rank}
      tag={nameOf(a.theme)}
      accent={COLOR[dir]}
      title={href ? <a href={href} target="_blank" rel="noopener noreferrer" className="hover:underline">{title}</a> : title}
      detail={a.signal_summary ?? `${tv(seg)}: ${exposure}`}
      value={typeof a.demand_change_pct === "number" ? fmt.pct(a.demand_change_pct, 1, true) : undefined}
      valueCaption={t("sa.card.impact")}
      valueTone={dir === "up" ? "positive" : dir === "down" ? "negative" : "neutral"}
      meta={
        <span className="text-muted-foreground text-xs">
          {[a.domain, a.published_date, `${tv(seg)}: ${exposure}`].filter(Boolean).join(" · ")}
        </span>
      }
    />
  );
}

function Diverging({ title, description, rows }: { title: string; description?: string; rows: { name: string; value: number }[] }) {
  const fmt = useFormat();
  const span = Math.max(0.5, ...rows.map((r) => Math.abs(r.value))) * 1.3;
  const config = { value: { label: title, color: "var(--chart-1)" } } satisfies ChartConfig;
  return (
    <Panel title={title} description={description}>
      <ChartContainer config={config} className="w-full" style={{ height: Math.max(180, 44 * rows.length) }}>
        <BarChart data={rows} layout="vertical" margin={{ left: 0, right: 48, top: 4 }}>
          <CartesianGrid horizontal={false} />
          <XAxis type="number" domain={[-span, span]} hide />
          <YAxis dataKey="name" type="category" tickLine={false} axisLine={false} width={190} interval={0} tick={{ fontSize: 12 }} />
          <ReferenceLine x={0} stroke="var(--muted-foreground)" />
          <ChartTooltip
            cursor={{ fill: "var(--muted)", opacity: 0.5 }}
            content={({ active, payload }) => {
              const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
              return active && r ? (
                <div className="bg-background rounded-lg border px-3 py-2 text-xs shadow-xl">
                  <span className="font-medium">{r.name}</span> <span className="tabular ml-2">{fmt.pct(r.value, 1, true)}</span>
                </div>
              ) : null;
            }}
          />
          <Bar dataKey="value" radius={3} barSize={18}>
            {rows.map((r) => <Cell key={r.name} fill={r.value >= 0 ? "var(--success)" : "var(--destructive)"} />)}
            <LabelList dataKey="value" position="right" fontSize={12} className="fill-foreground" formatter={(v: unknown) => fmt.pct(Number(v), 1, true)} />
          </Bar>
        </BarChart>
      </ChartContainer>
    </Panel>
  );
}
