import { describe, expect, it } from "vitest";
import type { Article } from "@/lib/types";
import { actionable, signalWord, themeDrivers } from "./signals";

const article = (over: Partial<Article>): Article => ({
  title: "t", url: null, domain: null, published_date: "2026-01-01", theme: "fuel_prices", demand_direction: "up",
  demand_change_pct: 1, impact_score: 1, affected_category: null, signal_summary: null, ...over,
});

describe("signalWord", () => {
  it("calls small moves flat and larger ones a tailwind or headwind", () => {
    expect(signalWord(0.5)).toBe("flat");
    expect(signalWord(-0.75)).toBe("flat");
    expect(signalWord(1.2)).toBe("tailwind");
    expect(signalWord(-1.2)).toBe("headwind");
  });
});

describe("themeDrivers", () => {
  it("averages the demand change per theme and ignores unscored articles", () => {
    const rows = themeDrivers([
      article({ theme: "a", demand_change_pct: 2 }),
      article({ theme: "a", demand_change_pct: 4 }),
      article({ theme: "b", demand_change_pct: -1 }),
      article({ theme: "c", demand_change_pct: null }),
    ]);
    expect(rows).toEqual([{ theme: "a", mean: 3 }, { theme: "b", mean: -1 }]);
  });
});

describe("actionable", () => {
  it("drops neutral articles and ranks by impact times size", () => {
    const top = actionable([
      article({ title: "small", impact_score: 1, demand_change_pct: 1 }),
      article({ title: "big", impact_score: 3, demand_change_pct: -2 }),
      article({ title: "neutral", demand_direction: "neutral", impact_score: 9, demand_change_pct: 9 }),
    ]);
    expect(top.map((a) => a.title)).toEqual(["big", "small"]);
  });
});
