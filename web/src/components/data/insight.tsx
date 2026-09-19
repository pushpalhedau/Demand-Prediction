import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Three-step confidence read-out. */
export function ConfidenceMeter({ level, label }: { level: "High" | "Medium" | "Low"; label: string }) {
  const filled = { High: 3, Medium: 2, Low: 1 }[level];
  return (
    <span className="text-muted-foreground inline-flex items-center gap-2 text-xs">
      <span className="flex items-end gap-0.5" aria-hidden>
        {[1, 2, 3].map((i) => (
          <span key={i} className={cn("w-1 rounded-[1px]", i <= filled ? "bg-foreground" : "bg-border")} style={{ height: 4 + i * 3 }} />
        ))}
      </span>
      {label}
    </span>
  );
}

/**
 * One finding worth acting on: what kind it is, the headline, the reasoning, when it matters and how sure we are,
 * with its estimated value on the right. Used wherever the product advises rather than reports.
 */
export function Insight({
  rank,
  tag,
  accent,
  title,
  detail,
  meta,
  value,
  valueCaption,
  valueTone = "positive",
}: {
  rank?: number;
  tag: string;
  accent: string;
  title?: ReactNode;
  detail: ReactNode;
  meta?: ReactNode;
  value?: string;
  valueCaption?: string;
  valueTone?: "positive" | "negative" | "neutral";
}) {
  return (
    <article className="grid grid-cols-[2rem_minmax(0,1fr)] gap-x-4 gap-y-3 border-t py-5 first:border-t-0 sm:grid-cols-[2rem_minmax(0,1fr)_auto]">
      {rank === undefined ? <span /> : <span className="font-heading tabular text-muted-foreground/60 pt-0.5 text-lg leading-none font-semibold">{String(rank).padStart(2, "0")}</span>}
      <div className="min-w-0 space-y-2">
        <p className="flex items-center gap-2 text-[11px] font-semibold tracking-[0.08em] uppercase">
          <span className="size-1.5 rounded-full" style={{ background: accent }} aria-hidden />
          <span style={{ color: accent }}>{tag}</span>
        </p>
        {title && <h3 className="font-heading text-[15px] leading-snug font-semibold tracking-[-0.005em] text-balance">{title}</h3>}
        <div className="text-muted-foreground max-w-3xl text-sm leading-relaxed">{detail}</div>
        {meta && <div className="flex flex-wrap items-center gap-x-5 gap-y-1">{meta}</div>}
      </div>
      {value && (
        <div className="col-start-2 sm:col-start-3 sm:text-right">
          <p className={cn("font-heading tabular text-xl leading-none font-semibold tracking-[-0.02em]", { "text-success": valueTone === "positive", "text-destructive": valueTone === "negative" })}>{value}</p>
          {valueCaption && <p className="text-muted-foreground mt-1 text-xs">{valueCaption}</p>}
        </div>
      )}
    </article>
  );
}
