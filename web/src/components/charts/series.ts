import type { Point } from "@/lib/types";

/** CSS colour for the n-th data series (theme-aware: the tokens change with light/dark). */
export const seriesColor = (index: number): string => `var(--chart-${(index % 8) + 1})`;

export type Row = { x: string } & Record<string, number | string | null>;

/**
 * Join several dated series into one row per date, for Recharts. Missing values stay null so lines break
 * instead of drawing to zero.
 */
export function joinSeries(series: Record<string, Point[] | undefined>): Row[] {
  const rows = new Map<string, Row>();
  for (const [key, points] of Object.entries(series)) {
    for (const p of points ?? []) {
      const row = rows.get(p.x) ?? ({ x: p.x } as Row);
      row[key] = p.y;
      rows.set(p.x, row);
    }
  }
  return [...rows.values()].sort((a, b) => a.x.localeCompare(b.x));
}

/** Make a forecast line start where the actuals end, so the two segments join. */
export function bridge(actual: Point[] | undefined, projection: Point[] | undefined): Point[] {
  const last = actual?.[actual.length - 1];
  return last ? [last, ...(projection ?? [])] : (projection ?? []);
}
