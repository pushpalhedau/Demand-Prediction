import type { ReactNode } from "react";

/** Every admin screen opens the same way: what this is, and the one-sentence context under it. */
export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description?: string; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
      <div className="space-y-1.5">
        <p className="text-muted-foreground text-[11px] font-semibold tracking-[0.1em] uppercase">{eyebrow}</p>
        <h1 className="font-heading text-[1.65rem] leading-[1.2] font-semibold tracking-[-0.02em] text-balance sm:text-3xl">{title}</h1>
        {description && <p className="text-muted-foreground max-w-2xl text-sm leading-relaxed">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2 pt-1">{actions}</div>}
    </header>
  );
}
