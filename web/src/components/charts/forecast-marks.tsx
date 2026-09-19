/**
 * PredictaX's chart grammar, taken from the logo's X: actuals are a solid line; where the forecast takes over, an X marks
 * the hand-over and the line shifts from blue to green as it looks ahead. Blue to green always means "the future".
 */
export const FORECAST_GRADIENT_ID = "px-forecast-gradient";

/** Put inside a Recharts chart. Objects with `stroke="url(#px-forecast-gradient)"` pick it up. */
export function ForecastGradient() {
  return (
    <defs>
      <linearGradient id={FORECAST_GRADIENT_ID} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="var(--brand-from)" />
        <stop offset="100%" stopColor="var(--brand-to)" />
      </linearGradient>
    </defs>
  );
}

export const FORECAST_STROKE = `url(#${FORECAST_GRADIENT_ID})`;

/** The hand-over marker: two short crossing strokes, one per brand colour. Use as a ReferenceDot `shape`. */
export function XMarker({ cx, cy }: { cx?: number; cy?: number }) {
  if (cx === undefined || cy === undefined) return null;
  const d = 5.5;
  return (
    <g transform={`translate(${cx},${cy})`} aria-hidden>
      <circle r={9} fill="var(--card)" fillOpacity={0.85} />
      <path d={`M${-d},${d} L${d},${-d}`} stroke="var(--brand-to)" strokeWidth={2.6} strokeLinecap="round" />
      <path d={`M${-d},${-d} L${d},${d}`} stroke="var(--brand-from)" strokeWidth={2.6} strokeLinecap="round" />
    </g>
  );
}
