/**
 * Colour for "pace against the store's own annual target". Targets carry a +5% stretch, so about 95% is holding last
 * year's volume: that is the neutral midpoint; below ~90% shades toward red, at or above target toward green.
 * The hue means the same thing on the footprint chart and the ranking.
 */
const LOW = 84;
const HIGH = 104;

export function attainmentColor(pct: number | null | undefined): string {
  const value = Math.min(Math.max(pct ?? 100, LOW), HIGH);
  const t = (value - LOW) / (HIGH - LOW);
  if (t < 0.5) return `color-mix(in oklch, var(--destructive), var(--warning) ${Math.round((t / 0.5) * 100)}%)`;
  return `color-mix(in oklch, var(--warning), var(--success) ${Math.round(((t - 0.5) / 0.5) * 100)}%)`;
}
