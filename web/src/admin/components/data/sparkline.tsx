/** A tiny trend line for a metric: no axes, the last point marked. Pure SVG, so it stays crisp at any density. */
export function Sparkline({ values, width = 92, height = 30, label }: { values: number[]; width?: number; height?: number; label?: string }) {
  if (values.length < 2) return null;
  const pad = 3;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const x = (i: number) => pad + (i / (values.length - 1)) * (width - pad * 2);
  const y = (v: number) => height - pad - ((v - min) / span) * (height - pad * 2);
  const points = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  const last = values.length - 1;
  const area = `M${x(0)},${height} L${points.join(" L")} L${x(last)},${height} Z`;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label} className="shrink-0 overflow-visible">
      <path d={area} fill="var(--chart-1)" fillOpacity={0.1} />
      <polyline points={points.join(" ")} fill="none" stroke="var(--chart-1)" strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(last)} cy={y(values[last]!)} r={2.6} fill="var(--card)" stroke="var(--chart-1)" strokeWidth={1.6} />
    </svg>
  );
}
