"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/data/page-header";
import { QueryBoundary } from "@/components/data/query-boundary";
import { PanelSkeleton } from "@/components/data/chart-card";
import { EmptyState, ErrorState } from "@/components/data/states";
import { RichText } from "@/components/data/rich-text";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { usePresentation } from "@/lib/session";
import type { PipelineStatus, SentimentOverview } from "@/lib/types";
import { BottomLine, Headline } from "./headline";
import { DemandWatch } from "./demand-watch";
import { ForecastCheckPanel } from "./forecast-check";

export function SentimentPage() {
  const { t } = usePresentation();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["sentiment"], queryFn: () => api<SentimentOverview>("/api/sentiment/overview"), staleTime: 5 * 60_000 });
  const [timespan, setTimespan] = useState("30d");
  const [status, setStatus] = useState<PipelineStatus | null>(null);

  const refresh = useMutation({
    mutationFn: () => api<PipelineStatus>("/api/sentiment/refresh", { method: "POST", body: { timespan } }),
    onSuccess: async (result) => {
      setStatus(result);
      await queryClient.invalidateQueries({ queryKey: ["sentiment"] });
    },
  });

  return (
    <>
      <PageHeader
        title={t("sa.title")}
        actions={
          <>
            <Select value={timespan} onValueChange={setTimespan}>
              <SelectTrigger size="sm" className="w-40" aria-label={t("sa.window")}><SelectValue /></SelectTrigger>
              <SelectContent>
                {Object.entries(query.data?.timespans ?? { "Last 30 days": "30d" }).map(([label, value]) => (
                  <SelectItem key={value} value={value}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button size="sm" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
              {refresh.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />} {t("sa.refresh")}
            </Button>
          </>
        }
      />

      {refresh.isPending && <p className="text-muted-foreground text-sm">{t("sa.fetching")}</p>}
      {refresh.isError && <ErrorState message={refresh.error.message} />}
      {status && <PipelineNotice status={status} />}

      <QueryBoundary query={query} skeleton={<PanelSkeleton height={420} />}>
        {(data) =>
          data.stats.total_articles === 0 || data.articles.length === 0 ? (
            <EmptyState title={t("sa.title")}>
              <RichText text={t("sa.empty")} />
            </EmptyState>
          ) : (
            <div className="space-y-6">
              <Headline stats={data.stats} runrate={data.monthly_runrate} />
              <BottomLine stats={data.stats} articles={data.articles} runrate={data.monthly_runrate} />
              <Tabs defaultValue="watch" className="gap-6">
                <TabsList>
                  <TabsTrigger value="watch">{t("sa.tab_watch")}</TabsTrigger>
                  <TabsTrigger value="forecast">{t("sa.tab_fc")}</TabsTrigger>
                </TabsList>
                <TabsContent value="watch"><DemandWatch stats={data.stats} articles={data.articles} /></TabsContent>
                <TabsContent value="forecast"><ForecastCheckPanel /></TabsContent>
              </Tabs>
            </div>
          )
        }
      </QueryBoundary>
    </>
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
