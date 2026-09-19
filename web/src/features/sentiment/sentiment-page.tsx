"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { useState } from "react";
import { PanelSkeleton } from "@/components/data/chart-card";
import { PageHeading } from "@/components/data/page-heading";
import { QueryBoundary } from "@/components/data/query-boundary";
import { RichText } from "@/components/data/rich-text";
import { ErrorState } from "@/components/data/states";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { useFormat, usePresentation } from "@/lib/session";
import type { PipelineStatus, SentimentOverview } from "@/lib/types";
import { DemandWatch } from "./demand-watch";
import { ForecastCheckPanel } from "./forecast-check";
import { BottomLine, Headline } from "./headline";
import { signalWord } from "./signals";

export function SentimentPage() {
  const { t } = usePresentation();
  const fmt = useFormat();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["sentiment"], queryFn: () => api<SentimentOverview>("/api/sentiment/overview"), staleTime: 5 * 60_000 });
  const [timespan, setTimespan] = useState("30d");
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [view, setView] = useState<"watch" | "forecast">("watch");

  const refresh = useMutation({
    mutationFn: () => api<PipelineStatus>("/api/sentiment/refresh", { method: "POST", body: { timespan } }),
    onSuccess: async (result) => {
      setStatus(result);
      await queryClient.invalidateQueries({ queryKey: ["sentiment"] });
    },
  });

  const data = query.data;
  const hasSignals = Boolean(data && data.stats.total_articles > 0 && data.articles.length > 0);
  const headline = data && hasSignals
    ? t(`sa.head.${signalWord(data.stats.net_demand_signal_pct)}`, { pct: fmt.pct(data.stats.net_demand_signal_pct, 1, true) })
    : t("sa.head.empty");

  const controls = (
    <>
      <Select value={timespan} onValueChange={setTimespan}>
        <SelectTrigger size="sm" className="w-40" aria-label={t("sa.window")}><SelectValue /></SelectTrigger>
        <SelectContent>
          {Object.entries(data?.timespans ?? { "Last 30 days": "30d" }).map(([label, value]) => (
            <SelectItem key={value} value={value}>{label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button size="sm" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
        {refresh.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />} {t("sa.refresh")}
      </Button>
    </>
  );

  return (
    <div className="space-y-8">
      <PageHeading eyebrow={t("sa.title")} headline={headline} actions={controls} />
      {refresh.isPending && <p className="text-muted-foreground text-sm">{t("sa.fetching")}</p>}
      {refresh.isError && <ErrorState message={refresh.error.message} />}
      {status && <PipelineNotice status={status} />}

      <QueryBoundary query={query} skeleton={<PanelSkeleton height={420} />}>
        {(d) =>
          d.stats.total_articles === 0 || d.articles.length === 0 ? (
            <p className="text-muted-foreground max-w-xl text-sm leading-relaxed">
              <RichText text={t("sa.empty")} />
            </p>
          ) : (
            <div className="space-y-8">
              <Headline stats={d.stats} runrate={d.monthly_runrate} />
              <BottomLine stats={d.stats} articles={d.articles} runrate={d.monthly_runrate} />
              <Tabs value={view} onValueChange={(v) => setView(v as "watch" | "forecast")}>
                <TabsList variant="line" className="h-auto gap-6 border-b p-0" aria-label={t("sa.title")}>
                  <TabsTrigger value="watch" className="flex-none px-0 pb-2.5">{t("sa.tab_watch")}</TabsTrigger>
                  <TabsTrigger value="forecast" className="flex-none px-0 pb-2.5">{t("sa.tab_fc")}</TabsTrigger>
                </TabsList>
              </Tabs>
              {view === "watch" ? <DemandWatch stats={d.stats} articles={d.articles} /> : <ForecastCheckPanel />}
            </div>
          )
        }
      </QueryBoundary>
    </div>
  );
}

function PipelineNotice({ status }: { status: PipelineStatus }) {
  const { t } = usePresentation();
  const errors = status.errors ?? [];
  // A fallback to the secondary news source is expected behaviour, not a failure.
  const notes = errors.filter((e) => e.includes("Google News RSS"));
  const hard = errors.filter((e) => !e.includes("Google News RSS"));
  const summary = t("sa.status.summary", {
    fetched: status.fetch?.fetched_from_gdelt ?? 0,
    source: status.fetch?.source ?? "news",
    added: status.fetch?.inserted ?? 0,
    scored: status.analyze?.articles_found ?? 0,
    mode: (status.mode ?? "").toUpperCase(),
  });
  return (
    <Alert variant={hard.length ? "destructive" : "default"}>
      <AlertTitle>{hard.length ? t("sa.status.warn", { msg: hard.join("; ") }) : t("sa.status.done")}</AlertTitle>
      <AlertDescription>
        {summary}
        {notes.map((n) => (
          <span key={n} className="mt-1 block">{n}</span>
        ))}
      </AlertDescription>
    </Alert>
  );
}
