import clsx from "clsx";
import type { CSSProperties, ReactNode } from "react";

export function Section({ title, caption, children }: { title: string; caption?: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      {caption && <p className="mt-1 max-w-3xl text-sm text-muted">{caption}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function Card({ children, className, style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <div className={clsx("rounded-xl border border-line bg-panel p-5", className)} style={style}>
      {children}
    </div>
  );
}

export function KpiCard({
  label,
  value,
  note,
  tone = "neutral",
}: {
  label: string;
  value: string;
  note?: string | null;
  tone?: "good" | "bad" | "neutral";
}) {
  return (
    <Card>
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-2 text-3xl font-semibold tabular-nums text-ink">{value}</p>
      {note && (
        <p
          className={clsx("mt-1.5 text-sm", {
            "text-good": tone === "good",
            "text-bad": tone === "bad",
            "text-muted": tone === "neutral",
          })}
        >
          {note}
        </p>
      )}
    </Card>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-xl bg-panel", className)} aria-hidden />;
}

export function ErrorNotice({ message, reference }: { message: string; reference?: string }) {
  return (
    <div role="alert" className="rounded-xl border border-bad/40 bg-bad/10 p-4 text-sm text-ink">
      {message}
      {reference && <span className="ml-2 text-muted">Reference: {reference}</span>}
    </div>
  );
}

export function Notice({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-line bg-panel p-4 text-sm text-muted">{children}</div>;
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <div role="tablist" className="inline-flex gap-1 rounded-lg border border-line bg-panel p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={tab.id === value}
          onClick={() => onChange(tab.id)}
          className={clsx(
            "rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
            tab.id === value ? "bg-brand text-white" : "text-muted hover:text-ink",
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
