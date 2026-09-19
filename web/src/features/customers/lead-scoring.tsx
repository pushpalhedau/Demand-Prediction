"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, PolarAngleAxis, RadialBar, RadialBarChart, ReferenceLine, XAxis, YAxis } from "recharts";
import { Panel, PanelSkeleton } from "@/components/data/chart-card";
import { QueryBoundary } from "@/components/data/query-boundary";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { api } from "@/lib/api";
import { useFormat, useMe, usePresentation } from "@/lib/session";
import type { LeadForm, LeadScore, NumericRange } from "@/lib/types";

type Relationship = "new" | "service" | "repeat";

interface Draft {
  store: string;
  age: number;
  occupation: string;
  income: number;
  credit: number;
  category: string;
  fuel: string;
  channel: string;
  relationship: Relationship;
  discount: number;
  price: number;
}

function initialDraft(form: LeadForm): Draft | null {
  if (!form.model || form.stores.length === 0) return null;
  const { options, stats } = form.model;
  return {
    store: form.stores[0]?.store ?? "",
    age: Math.round(stats.age.p50),
    occupation: options.occupation[0] ?? "",
    income: Math.round(stats.annual_income.p50),
    credit: Math.round(stats.credit_score.p50),
    category: options.vehicle_category[0] ?? "",
    fuel: options.fuel_type[0] ?? "",
    channel: options.marketing_channel[0] ?? "",
    relationship: "new",
    discount: 6,
    price: Math.round(stats.base_price.p50),
  };
}

const range = (r: NumericRange) => ({ min: Math.floor(r.lo), max: Math.ceil(Math.max(r.hi, r.lo + 1)) });

export function LeadScoring() {
  const { t } = usePresentation();
  const query = useQuery({ queryKey: ["cu-lead-form"], queryFn: () => api<LeadForm>("/api/customers/lead-form"), staleTime: 10 * 60_000 });
  return (
    <QueryBoundary query={query} skeleton={<PanelSkeleton height={420} />}>
      {(form) => (form.model ? <LeadFormView form={form} /> : <EmptyState title={t("cu.lead.untrained")} />)}
    </QueryBoundary>
  );
}

function LeadFormView({ form }: { form: LeadForm }) {
  const { t, tv } = usePresentation();
  const fmt = useFormat();
  const { data: me } = useMe();
  const model = form.model!;
  const [draft, setDraft] = useState<Draft>(() => initialDraft(form)!);
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }));
  const currency = me?.organisation.currency ?? "";
  const store = form.stores.find((s) => s.store === draft.store) ?? form.stores[0]!;

  const score = useMutation({
    mutationFn: () =>
      api<LeadScore>("/api/customers/score-lead", {
        method: "POST",
        body: {
          region: store.region,
          age: draft.age,
          occupation: draft.occupation,
          annual_income: draft.income,
          credit_score: draft.credit,
          vehicle_category: draft.category,
          fuel_type: draft.fuel,
          marketing_channel: draft.channel,
          relationship: draft.relationship,
          discount_pct: draft.discount,
          base_price: draft.price,
        },
      }),
  });

  const pick = (label: string, value: string, options: string[], onChange: (v: string) => void, render: (v: string) => string = (v) => v) => (
    <div className="space-y-1.5">
      <Label className="text-muted-foreground text-xs">{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
        <SelectContent>{options.map((o) => <SelectItem key={o} value={o}>{render(o)}</SelectItem>)}</SelectContent>
      </Select>
    </div>
  );
  const slide = (label: string, value: number, min: number, max: number, step: number, onChange: (v: number) => void, suffix = "") => (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <Label className="text-muted-foreground text-xs">{label}</Label>
        <span className="tabular text-sm font-medium">{fmt.num(value, step < 1 ? 1 : 0)}{suffix}</span>
      </div>
      <Slider min={min} max={max} step={step} value={[value]} onValueChange={([v]) => onChange(v ?? value)} />
    </div>
  );
  const money = (label: string, value: number, onChange: (v: number) => void) => (
    <div className="space-y-1.5">
      <Label className="text-muted-foreground text-xs">{label} ({currency})</Label>
      <Input type="number" inputMode="numeric" min={0} value={value} onChange={(e) => onChange(Number(e.target.value))} className="tabular" />
    </div>
  );

  const age = range(model.stats.age);
  const credit = range(model.stats.credit_score);
  const relationshipLabel = { new: t("cu.rel.new"), service: t("cu.rel.service"), repeat: t("cu.rel.repeat") };

  return (
    <div className="space-y-6">
      <Panel title={t("cu.lead.title")} description={t("cu.lead.caption")}>
        <div className="space-y-6">
          {pick(
            t("cu.lead.store"),
            draft.store,
            form.stores.map((s) => s.store),
            (v) => set("store", v),
            (v) => {
              const s = form.stores.find((x) => x.store === v);
              return s ? `${s.store} — ${s.city}, ${s.region}` : v;
            },
          )}
          <div className="grid gap-x-8 gap-y-6 md:grid-cols-2 xl:grid-cols-3">
            <div className="space-y-6">
              {slide(t("cu.lead.age"), draft.age, age.min, age.max, 1, (v) => set("age", v))}
              {pick(t("cu.lead.occupation"), draft.occupation, model.options.occupation, (v) => set("occupation", v))}
              {money(t("cu.lead.income"), draft.income, (v) => set("income", v))}
            </div>
            <div className="space-y-6">
              {slide(t("cu.lead.credit"), draft.credit, credit.min, credit.max, 1, (v) => set("credit", v))}
              {pick(t("cu.lead.category"), draft.category, model.options.vehicle_category, (v) => set("category", v), tv)}
              {pick(t("cu.lead.fuel"), draft.fuel, model.options.fuel_type, (v) => set("fuel", v), tv)}
            </div>
            <div className="space-y-6">
              {pick(t("cu.lead.channel"), draft.channel, model.options.marketing_channel, (v) => set("channel", v))}
              {pick(t("cu.lead.relationship"), draft.relationship, form.relationships, (v) => set("relationship", v as Relationship), (v) => relationshipLabel[v as Relationship])}
              {slide(t("cu.lead.discount"), draft.discount, 0, 20, 0.5, (v) => set("discount", v), "%")}
              {money(t("cu.lead.price"), draft.price, (v) => set("price", v))}
            </div>
          </div>
          <Button onClick={() => score.mutate()} disabled={score.isPending}>
            {score.isPending && <Loader2 className="animate-spin" />} {t("cu.lead.score")}
          </Button>
        </div>
      </Panel>

      {score.isError && <ErrorState message={score.error.message} />}
      {score.data && <Result result={score.data} store={store.store} channel={draft.channel} />}
    </div>
  );
}

function zone(p: number): "hot" | "warm" | "cold" {
  return p >= 0.7 ? "hot" : p >= 0.45 ? "warm" : "cold";
}

function Result({ result, store, channel }: { result: LeadScore; store: string; channel: string }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  const p = result.close_probability;
  const z = zone(p);
  const color = { hot: "var(--success)", warm: "var(--warning)", cold: "var(--destructive)" }[z];
  const explanations = [...(result.explanations ?? [])]
    .slice(0, 6)
    .sort((a, b) => a.score - b.score)
    .map((e) => ({ ...e, label: e.feature.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) }));
  const configEx = { score: { label: t("cu.res.push"), color: "var(--chart-1)" } } satisfies ChartConfig;
  const internetChannel = ["Online Ad", "Social Media", "Search Engine"].includes(channel);

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <Panel title={t("cu.res.prob")} footer={t(`cu.zone.${z}`)}>
          <div className="relative">
            <ChartContainer config={{ value: { label: t("cu.res.prob"), color } }} className="mx-auto h-[190px] w-full">
              <RadialBarChart data={[{ value: p * 100 }]} startAngle={180} endAngle={0} innerRadius="72%" outerRadius="100%" cy="82%">
                <PolarAngleAxis type="number" domain={[0, 100]} tick={false} axisLine={false} />
                <RadialBar dataKey="value" background={{ fill: "var(--muted)" }} cornerRadius={8} fill={color} />
              </RadialBarChart>
            </ChartContainer>
            <p className="font-heading tabular absolute inset-x-0 bottom-3 text-center text-4xl font-semibold" style={{ color }}>{fmt.pct(p * 100, 0)}</p>
          </div>
        </Panel>

        <Panel title={t("cu.res.moving")} description={result.explainer_used === "shap" ? t("cu.res.shap") : t("cu.res.quick")}>
          {explanations.length ? (
            <ChartContainer config={configEx} className="w-full" style={{ height: 40 * explanations.length + 30 }}>
              <BarChart data={explanations} layout="vertical" margin={{ left: 0, right: 16, top: 4 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" tickLine={false} axisLine={false} tickFormatter={(v: number) => fmt.num(v, 2)} />
                <YAxis dataKey="label" type="category" tickLine={false} axisLine={false} width={150} />
                <ReferenceLine x={0} stroke="var(--muted-foreground)" />
                <ChartTooltip
                  cursor={{ fill: "var(--muted)", opacity: 0.5 }}
                  content={({ active, payload }) => {
                    const r = payload?.[0]?.payload as (typeof explanations)[number] | undefined;
                    if (!active || !r) return null;
                    return <div className="bg-background rounded-lg border px-3 py-2 text-xs shadow-xl"><span className="font-medium">{r.label}</span> <span className="tabular ml-2">{fmt.num(r.score, 3)}</span></div>;
                  }}
                />
                <Bar dataKey="score" radius={3} barSize={16}>
                  {explanations.map((e) => <Cell key={e.feature} fill={e.direction === "positive" ? "var(--success)" : "var(--destructive)"} />)}
                </Bar>
              </BarChart>
            </ChartContainer>
          ) : (
            <EmptyState title={t("cu.res.none")} />
          )}
        </Panel>
      </div>

      <Alert variant={z === "cold" ? "destructive" : "default"}>
        <AlertTitle>{t(`cu.rec.${z}.title`)}</AlertTitle>
        <AlertDescription>{t(`cu.rec.${z}.body`, { store })}{z === "cold" && internetChannel ? ` ${t("cu.rec.cold.internet")}` : ""}</AlertDescription>
      </Alert>
    </div>
  );
}
