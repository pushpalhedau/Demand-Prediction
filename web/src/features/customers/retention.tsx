"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Download } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, XAxis, YAxis } from "recharts";
import { ChartFrame } from "@/components/charts/chart-frame";
import { Panel, PanelSkeleton } from "@/components/data/chart-card";
import { DataTable, type Column } from "@/components/data/data-table";
import { MetricStrip, MetricStripSkeleton } from "@/components/data/metric-strip";
import { PageHeading } from "@/components/data/page-heading";
import { QueryBoundary } from "@/components/data/query-boundary";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart";
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { useDashboardQuery } from "@/lib/query";
import { useFormat, usePresentation } from "@/lib/session";
import type { QueuePage, QueueRow, Retention as RetentionData } from "@/lib/types";

const PAGE_SIZE = 20;
const ALL_STORES = "__all__";
const BAND_COLOR: Record<string, string> = {
  Active: "var(--success)",
  "In cycle — due back": "var(--chart-1)",
  "Going quiet": "var(--warning)",
  "Likely lost": "var(--destructive)",
};

export function Retention({ nav }: { nav: ReactNode }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  const query = useDashboardQuery<RetentionData>("cu-retention", "/api/customers/retention");
  return (
    <QueryBoundary
      query={query}
      skeleton={
        <div className="space-y-8">
          {nav}
          <PanelSkeleton height={110} />
          <MetricStripSkeleton />
          <PanelSkeleton height={420} />
        </div>
      }
    >
      {(d) => {
        if (d.status !== "ok") {
          return (
            <div className="space-y-8">
              {nav}
              <PageHeading eyebrow={t("tab.customers")} headline={t("cu.no_customers")} />
            </div>
          );
        }
        const bands = d.book ?? [];
        const book = bands.filter((b) => b.customers > 0).map((b) => ({ ...b, fill: BAND_COLOR[b.band] ?? "var(--chart-1)" }));
        const dueBack = bands.find((b) => b.band === "In cycle — due back")?.customers ?? 0;
        const bookConfig = { customers: { label: t("cu.buyers"), color: "var(--chart-1)" } } satisfies ChartConfig;
        return (
          <div className="space-y-8">
            {nav}
            <PageHeading eyebrow={t("tab.customers")} headline={t("cu.head", { flagged: fmt.num(d.queue_total), repeat: fmt.pct(d.repeat_rate_pct, 0) })} />
            <MetricStrip
              metrics={[
                { label: t("cu.kpi.buyers"), value: fmt.num(d.buyers), note: t("cu.kpi.buyers_help", { n: fmt.num(d.records) }) },
                { label: t("cu.kpi.repeat"), value: fmt.pct(d.repeat_rate_pct, 0), note: t("cu.kpi.repeat_help") },
                { label: t("cu.kpi.share"), value: fmt.pct(d.repeat_share_pct, 0), note: t("cu.kpi.share_help") },
                { label: t("cu.kpi.flagged"), value: fmt.num(d.queue_total), note: t("cu.kpi.flagged_help") },
              ]}
            />

            <ActionQueue stores={d.queue_stores ?? []} reasons={d.queue_reasons ?? {}} />

            {book.length > 0 && (
              <ChartFrame
                headline={t("cu.book.head", { n: fmt.num(dueBack) })}
                description={t("cu.book.caption")}
                csv={{ filename: "customer_book.csv", headers: [t("cu.book.title"), t("cu.buyers"), t("cu.lifetime")], rows: book.map((b) => [b.band, b.customers, b.lifetime_value]) }}
              >
                {(height) => (
                  <ChartContainer config={bookConfig} className="w-full" style={{ height: Math.max(220, height - 90) }}>
                    <BarChart data={book} layout="vertical" margin={{ left: 0, right: 150, top: 4 }}>
                      <CartesianGrid horizontal={false} strokeOpacity={0.6} />
                      <XAxis type="number" tickFormatter={(v: number) => fmt.compact(v)} tickLine={false} axisLine={false} />
                      <YAxis dataKey="band" type="category" tickLine={false} axisLine={false} width={150} />
                      <ChartTooltip
                        cursor={{ fill: "var(--muted)", opacity: 0.5 }}
                        content={({ active, payload }) => {
                          const r = payload?.[0]?.payload as (typeof book)[number] | undefined;
                          if (!active || !r) return null;
                          return (
                            <div className="bg-background grid gap-0.5 rounded-lg border px-3 py-2 text-xs shadow-xl">
                              <p className="text-sm font-medium">{r.band}</p>
                              <p className="text-muted-foreground">{t(`cu.band.${r.band}`)}</p>
                              <p className="tabular">
                                {fmt.num(r.customers)} · {fmt.money(r.lifetime_value)} {t("cu.lifetime")}
                              </p>
                            </div>
                          );
                        }}
                      />
                      <Bar dataKey="customers" radius={3} barSize={22}>
                        {book.map((b) => (
                          <Cell key={b.band} fill={b.fill} />
                        ))}
                        <LabelList dataKey="customers" position="right" fontSize={12} className="fill-foreground" formatter={(v: unknown) => fmt.compact(Number(v))} />
                      </Bar>
                    </BarChart>
                  </ChartContainer>
                )}
              </ChartFrame>
            )}

            {d.segments && d.segments.length > 0 && (
              <Accordion type="single" collapsible className="border-t">
                <AccordionItem value="segments" className="border-0">
                  <AccordionTrigger className="font-heading py-5 text-[17px] font-semibold hover:no-underline">{t("cu.segments.title")}</AccordionTrigger>
                  <AccordionContent>
                    <DataTable
                      rows={d.segments}
                      rowKey={(r) => r.segment}
                      columns={[
                        { key: "segment", header: t("cu.seg.segment"), cell: (r) => <span className="font-medium">{r.segment}</span> },
                        { key: "customers", header: t("cu.seg.customers"), align: "right", cell: (r) => fmt.num(r.customers), sort: (r) => r.customers },
                        { key: "share", header: t("cu.seg.share"), align: "right", cell: (r) => fmt.pct(r.share_pct, 1), sort: (r) => r.share_pct },
                        { key: "rev", header: t("cu.seg.revenue"), align: "right", cell: (r) => fmt.money(r.lifetime_revenue), sort: (r) => r.lifetime_revenue },
                        { key: "deal", header: t("cu.seg.deal"), align: "right", cell: (r) => fmt.money(r.avg_deal_value), sort: (r) => r.avg_deal_value },
                        { key: "repeat", header: t("cu.seg.repeat"), align: "right", cell: (r) => fmt.pct(r.repeat_rate_pct, 0), sort: (r) => r.repeat_rate_pct },
                        { key: "lease", header: t("cu.seg.lease"), align: "right", cell: (r) => fmt.pct(r.lease_pct, 0), sort: (r) => r.lease_pct },
                        { key: "income", header: t("cu.seg.income"), align: "right", cell: (r) => fmt.money(r.median_income), sort: (r) => r.median_income },
                        { key: "credit", header: t("cu.seg.credit"), align: "right", cell: (r) => fmt.num(r.avg_credit), sort: (r) => r.avg_credit },
                        { key: "since", header: t("cu.seg.since"), align: "right", cell: (r) => (r.months_since_deal === null ? "–" : fmt.num(r.months_since_deal, 0)), sort: (r) => r.months_since_deal },
                      ] satisfies Column<NonNullable<RetentionData["segments"]>[number]>[]}
                    />
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            )}
          </div>
        );
      }}
    </QueryBoundary>
  );
}

function ActionQueue({ stores, reasons }: { stores: string[]; reasons: Record<string, number> }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  const { apiParams } = useFilters();
  const reasonNames = Object.keys(reasons).sort();
  const [store, setStore] = useState("");
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(0);
  const selected = reasonNames.filter((r) => !excluded.has(r));

  const params = new URLSearchParams(apiParams);
  if (store) params.set("store", store);
  // Every reason ticked means "no reason filter"; only send the list when the user narrowed it.
  if (excluded.size > 0) selected.forEach((r) => params.append("reason", r));

  const queue = useQuery<QueuePage>({
    queryKey: ["cu-queue", apiParams, store, [...excluded].sort(), page],
    queryFn: () => {
      const q = new URLSearchParams(params);
      q.set("page", String(page));
      q.set("page_size", String(PAGE_SIZE));
      return api<QueuePage>(`/api/customers/queue?${q.toString()}`);
    },
    placeholderData: (previous) => previous,
  });

  const pages = Math.max(1, Math.ceil((queue.data?.total ?? 0) / PAGE_SIZE));
  const columns: Column<QueueRow>[] = [
    { key: "name", header: t("cu.q.customer"), cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: "store", header: t("cu.q.store"), cell: (r) => r.store ?? "–" },
    { key: "reason", header: t("cu.q.reason"), cell: (r) => <Badge variant="secondary" className="font-normal">{r.reason}</Badge> },
    { key: "play", header: t("cu.q.play"), cell: (r) => r.play },
    { key: "when", header: t("cu.q.contact"), cell: (r) => (r.when_days === null ? t("cu.now") : t("cu.in_days", { n: fmt.num(r.when_days) })) },
    { key: "vehicle", header: t("cu.q.vehicle"), cell: (r) => r.vehicle ?? "–" },
    { key: "since", header: t("cu.q.since"), align: "right", cell: (r) => (r.months_since_last_deal === null ? "–" : fmt.num(r.months_since_last_deal, 0)) },
    { key: "gross", header: t("cu.q.gross"), align: "right", cell: (r) => fmt.money(r.opportunity_amt, false) },
    { key: "email", header: t("cu.q.email"), cell: (r) => (r.email_opt_in ? t("cu.yes") : t("cu.no")) },
  ];

  return (
    <Panel
      title={t("cu.queue.title")}
      description={t("cu.queue.caption")}
      action={
        <Button asChild variant="outline" size="sm">
          <a href={`/api/customers/queue.csv?${params.toString()}`} download>
            <Download /> {t("app.export_csv")}
          </a>
        </Button>
      }
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Select value={store || ALL_STORES} onValueChange={(v) => { setStore(v === ALL_STORES ? "" : v); setPage(0); }}>
          <SelectTrigger size="sm" className="w-64" aria-label={t("cu.q.store")}><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_STORES}>{t("cu.all_stores")}</SelectItem>
            {stores.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="gap-2">
              {t("cu.q.reason")} <Badge variant="secondary">{selected.length}/{reasonNames.length}</Badge> <ChevronDown className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-64">
            <DropdownMenuLabel>{t("cu.q.reason")}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {reasonNames.map((r) => (
              <DropdownMenuCheckboxItem
                key={r}
                checked={!excluded.has(r)}
                onSelect={(e) => e.preventDefault()}
                onCheckedChange={(on) => {
                  setExcluded((prev) => {
                    const next = new Set(prev);
                    if (on) next.delete(r);
                    else next.add(r);
                    return next;
                  });
                  setPage(0);
                }}
              >
                {r} <span className="text-muted-foreground ml-auto pl-3 text-xs tabular">{fmt.num(reasons[r])}</span>
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <p className="text-muted-foreground ml-auto text-sm tabular">{t("cu.queue.count", { n: fmt.num(queue.data?.total ?? 0) })}</p>
      </div>

      {queue.isError ? (
        <ErrorState message={queue.error.message} />
      ) : queue.data && queue.data.rows.length > 0 ? (
        <>
          <DataTable columns={columns} rows={queue.data.rows} rowKey={(r, i) => `${r.name}-${i}`} />
          <div className="mt-4 flex items-center justify-between">
            <p className="text-muted-foreground text-sm tabular">{t("cu.page", { page: page + 1, pages })}</p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>{t("cu.prev")}</Button>
              <Button variant="outline" size="sm" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>{t("cu.next")}</Button>
            </div>
          </div>
        </>
      ) : queue.isPending ? (
        <PanelSkeleton height={360} />
      ) : (
        <EmptyState title={t("cu.queue.none")} />
      )}
    </Panel>
  );
}
