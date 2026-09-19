import type { Article } from "@/lib/types";

/** Net signal (in %) beyond which the news counts as a tailwind or headwind rather than flat. */
export const SIGNAL_THRESHOLD = 0.75;

export type SignalWord = "tailwind" | "headwind" | "flat";

export function signalWord(net: number): SignalWord {
  return net > SIGNAL_THRESHOLD ? "tailwind" : net < -SIGNAL_THRESHOLD ? "headwind" : "flat";
}

export const direction = (a: Article): "up" | "down" | "neutral" => a.demand_direction ?? "neutral";

/** Mean demand change per news theme, largest movers first. */
export function themeDrivers(articles: Article[]): { theme: string; mean: number }[] {
  const sums = new Map<string, { total: number; n: number }>();
  for (const a of articles) {
    if (a.theme && typeof a.demand_change_pct === "number") {
      const s = sums.get(a.theme) ?? { total: 0, n: 0 };
      s.total += a.demand_change_pct;
      s.n += 1;
      sums.set(a.theme, s);
    }
  }
  return [...sums].map(([theme, s]) => ({ theme, mean: s.total / s.n }));
}

/** Articles worth acting on, ranked by impact × size of the demand change. */
export function actionable(articles: Article[], limit = 8): Article[] {
  const rank = (a: Article) => (a.impact_score ?? 0) * Math.abs(a.demand_change_pct ?? 0);
  return articles
    .filter((a) => direction(a) !== "neutral")
    .sort((a, b) => rank(b) - rank(a))
    .slice(0, limit);
}

export function latest(articles: Article[], limit = 5): Article[] {
  return [...articles].sort((a, b) => (b.published_date ?? "").localeCompare(a.published_date ?? "")).slice(0, limit);
}
