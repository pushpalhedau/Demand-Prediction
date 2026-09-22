import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Sparkline } from "./sparkline";

export type Tone = "positive" | "negative" | "neutral";

export interface Metric {
  label: string;
  value: ReactNode;
  /** Change against a comparison period, shown as a chip. */
  delta?: { text: string; tone: Tone } | null;
  note?: ReactNode;
  /** Recent history, drawn as a sparkline. */
  spark?: number[];
  /** Progress toward a target: `value` and `target` are on the same scale (target is drawn as a tick). */
  bullet?: { value: number; target: number; targetLabel: string };
}

function DeltaChip({ text, tone }: { text: string; tone: Tone }) {
  const Icon = tone === "negative" ? ArrowDownRight : ArrowUpRight;
  return (
    <span
      className={cn("tabular inline-flex items-center gap-0.5 rounded-sm px-1.5 py-0.5 text-xs font-medium", {
        "bg-success/12 text-success": tone === "positive",
        "bg-destructive/12 text-destructive": tone === "negative",
        "bg-muted text-muted-foreground": tone === "neutral",
      })}
    >
      {tone !== "neutral" && <Icon className="size-3" aria-hidden />}
      {text}
    </span>
  );
}

function Bullet({ value, target, targetLabel }: NonNullable<Metric["bullet"]>) {
  const max = Math.max(target * 1.25, value * 1.05);
  const pct = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  return (
    <div role="img" aria-label={`${targetLabel}: ${target}`}>
      <div className="bg-muted relative h-1.5 rounded-full">
        <div className="bg-primary absolute inset-y-0 left-0 rounded-full" style={{ width: pct(value) }} />
        <div className="bg-foreground absolute -inset-y-1 w-px" style={{ left: pct(target) }} />
      </div>
      <div className="text-muted-foreground relative mt-1 h-3 text-[10px] tracking-wide uppercase">
        <span className="absolute -translate-x-1/2" style={{ left: pct(target) }}>{targetLabel}</span>
      </div>
    </div>
  );
}

/**
 * The headline figures of a page as one connected band: label, value, change with context, and either a sparkline
 * or progress toward target. Hairlines (a 1px grid gap) separate cells at any width.
 */
export function MetricStrip({ metrics }: { metrics: Metric[] }) {
  return (
    <div className="bg-border grid gap-px overflow-hidden rounded-lg border sm:grid-cols-2 xl:grid-cols-[repeat(var(--cols),minmax(0,1fr))]" style={{ ["--cols" as string]: metrics.length }}>
      {metrics.map((m) => (
        <div key={m.label} className="bg-card flex min-w-0 flex-col gap-3 p-5">
          <p className="text-muted-foreground text-[11px] font-medium tracking-[0.08em] uppercase">{m.label}</p>
          <div className="flex min-h-9 items-center justify-between gap-3">
            <div className="font-heading tabular text-[1.6rem] leading-none font-semibold tracking-[-0.02em] whitespace-nowrap">{m.value}</div>
            {m.spark && <Sparkline values={m.spark} width={76} label={m.label} />}
          </div>
          <div className="mt-auto space-y-2">
            {m.bullet && <Bullet {...m.bullet} />}
            <div className="flex min-h-5 flex-wrap items-center gap-x-2 gap-y-1">
              {m.delta && <DeltaChip {...m.delta} />}
              {m.note && <span className="text-muted-foreground text-xs">{m.note}</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function MetricStripSkeleton() {
  return <div className="bg-muted h-[132px] animate-pulse rounded-lg" aria-hidden />;
}
