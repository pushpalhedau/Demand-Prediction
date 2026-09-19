import type { ReactNode } from "react";

export interface RankedRow {
  key: string;
  label: string;
  sublabel?: string;
  value: number;
  /** Shown right-aligned after the bar. */
  display: ReactNode;
  secondary?: ReactNode;
}

/**
 * A ranked list with an in-row bar, right-aligned figures and an optional reference tick (e.g. the group average).
 * Reads faster and aligns better than a chart when the point is "who is biggest and by how much".
 */
export function RankedBars({ rows, reference }: { rows: RankedRow[]; reference?: { value: number; label: string } }) {
  const max = Math.max(1, ...rows.map((r) => r.value), reference?.value ?? 0) * 1.02;
  const at = (v: number) => `${(v / max) * 100}%`;
  return (
    <ol className="divide-y">
      {rows.map((r) => (
        <li key={r.key} className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)_auto] items-center gap-x-4 py-2.5 sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)_auto]">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{r.label}</p>
            {r.sublabel && <p className="text-muted-foreground truncate text-xs">{r.sublabel}</p>}
          </div>
          <div className="bg-muted relative h-2 rounded-[2px]">
            <div className="bg-chart-1 absolute inset-y-0 left-0 rounded-[2px]" style={{ width: at(r.value) }} />
            {reference && <div className="bg-foreground/70 absolute -inset-y-1 w-px" style={{ left: at(reference.value) }} title={reference.label} />}
          </div>
          <div className="tabular min-w-[5.5rem] text-right text-sm">
            <span className="font-medium">{r.display}</span>
            {r.secondary && <span className="text-muted-foreground block text-xs">{r.secondary}</span>}
          </div>
        </li>
      ))}
    </ol>
  );
}
