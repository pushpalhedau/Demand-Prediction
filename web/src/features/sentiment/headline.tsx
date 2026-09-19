"use client";

import { PolarAngleAxis, RadialBar, RadialBarChart } from "recharts";
import { Insight } from "@/components/data/insight";
import { Section } from "@/components/data/section";
import { ChartContainer } from "@/components/ui/chart";
import { hasTranslation } from "@/lib/i18n";
import { useFormat, usePresentation } from "@/lib/session";
import type { Article, SentimentOverview } from "@/lib/types";
import { RichText } from "@/components/data/rich-text";
import { direction, signalWord, themeDrivers } from "./signals";

type Stats = SentimentOverview["stats"];

const TONE = { tailwind: "var(--success)", headwind: "var(--destructive)", flat: "var(--muted-foreground)" } as const;
const GAUGE_LIMIT = 6;

export function Headline({ stats, runrate }: { stats: Stats; runrate: number }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  const net = stats.net_demand_signal_pct;
  const word = signalWord(net);
  const color = TONE[word];
  const units = Math.round((runrate * net) / 100);
  // Map [-6, 6] onto the gauge's 0–100 arc, so "flat" sits at the top.
  const arc = ((Math.max(-GAUGE_LIMIT, Math.min(GAUGE_LIMIT, net)) + GAUGE_LIMIT) / (2 * GAUGE_LIMIT)) * 100;

  return (
    <div className="bg-card rounded-lg border p-5">
      <div className="grid items-center gap-6 md:grid-cols-[3fr_2fr]">
        <div className="space-y-1">
          <p className="text-muted-foreground text-[11px] font-medium tracking-[0.08em] uppercase">{t("sa.headline.label")}</p>
          <p className="font-heading tabular text-5xl font-semibold tracking-[-0.03em]" style={{ color }}>{fmt.pct(net, 1, true)}</p>
          <p className="text-sm">
            {t(`sa.word.${word}`)}
            {runrate > 0 && <span className="text-muted-foreground"> · {t("sa.headline.units", { v: fmt.num(units, 0) })}</span>}
          </p>
        </div>
        <div>
          <ChartContainer config={{ value: { label: t("sa.headline.label"), color } }} className="mx-auto h-[130px] w-full max-w-[260px]">
            <RadialBarChart data={[{ value: arc }]} startAngle={180} endAngle={0} innerRadius="75%" outerRadius="105%" cy="88%">
              <PolarAngleAxis type="number" domain={[0, 100]} tick={false} axisLine={false} />
              <RadialBar dataKey="value" background={{ fill: "var(--muted)" }} cornerRadius={8} fill={color} />
            </RadialBarChart>
          </ChartContainer>
          <p className="text-muted-foreground -mt-1 text-center text-xs">{t("sa.gauge.scale")}</p>
        </div>
      </div>
    </div>
  );
}

/** The always-visible plain-language conclusion, composed deterministically from the current signals. */
export function BottomLine({ stats, articles, runrate }: { stats: Stats; articles: Article[]; runrate: number }) {
  const { lang, t, tv } = usePresentation();
  const fmt = useFormat();
  const net = stats.net_demand_signal_pct;
  const themeName = (key: string) => (hasTranslation(lang, `sa.theme.${key}`) ? t(`sa.theme.${key}`) : key);
  const pct = (v: number) => fmt.pct(v, 1, true);

  const upCount = articles.filter((a) => direction(a) === "up").length;
  const downCount = articles.filter((a) => direction(a) === "down").length;
  const withSignal = upCount + downCount;
  const drivers = themeDrivers(articles).filter((d) => Math.abs(d.mean) >= 0.1).sort((a, b) => Math.abs(b.mean) - Math.abs(a.mean));
  const segments = Object.entries(stats.segment_changes ?? {})
    .filter(([k, v]) => k !== "All" && Math.abs(v) >= 0.05)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 2);

  let tone: keyof typeof TONE = "flat";
  let body: string;
  if (withSignal === 0) {
    body = t("sa.bl.none");
  } else if (Math.abs(net) < 0.5) {
    const names = (dir: "up" | "down", fallback: string) => {
      const found = [...new Set(articles.filter((a) => direction(a) === dir && a.theme).map((a) => themeName(a.theme!)))].sort().slice(0, 2);
      // German capitalises nouns mid-sentence, so theme names are only lower-cased in English.
      return found.length ? (lang === "de" ? found.join(", ") : found.join(", ").toLowerCase()) : t(fallback);
    };
    body = t("sa.bl.mixed", { up_n: upCount, up_theme: names("up", "sa.bl.supportive_news"), dn_n: downCount, dn_theme: names("down", "sa.bl.headwind_news") });
  } else {
    tone = net < 0 ? "headwind" : "tailwind";
    const parts = [
      t("sa.bl.net", {
        word: t(net < 0 ? "sa.word.headwind" : "sa.word.tailwind"),
        pct: pct(net),
        units: runrate ? t("sa.bl.units_hint", { v: fmt.num(Math.round((runrate * net) / 100), 0) }) : "",
      }),
    ];
    const lead = drivers[0];
    if (lead) {
      const exposureKey = `sa.exp.${lead.theme}`;
      parts.push(`${t("sa.bl.driver", { label: themeName(lead.theme) })} ${hasTranslation(lang, exposureKey) ? `— ${t(exposureKey)}.` : `(${pct(lead.mean)}).`}`);
    }
    if (segments.length) parts.push(`${t("sa.bl.exposed")}${segments.map(([s, v]) => `${tv(s)} (${pct(v)})`).join(", ")}.`);
    const first = segments[0];
    if (net < 0) parts.push(`<b>${t("sa.bl.week")}</b> ${t("sa.bl.week_down", { seg: first && first[1] < 0 ? tv(first[0]) : t("sa.bl.seg_affected") })}`);
    else parts.push(`<b>${t("sa.bl.week")}</b> ${t("sa.bl.week_up", { seg: first && first[1] > 0 ? tv(first[0]) : t("sa.bl.seg_favour") })}`);
    body = parts.join(" ");
  }

  return (
    <Section title={t("sa.bottom_line")}>
      <Insight
        tag={t(`sa.word.${tone}`)}
        accent={TONE[tone]}
        detail={<RichText text={body} />}
      />
    </Section>
  );
}
