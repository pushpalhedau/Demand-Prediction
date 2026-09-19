import type { ReactNode } from "react";

/** A page section divided from the one above by a hairline, not boxed in a card. */
export function Section({ title, description, action, children }: { title: string; description?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="min-w-0 border-t pt-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="font-heading text-[17px] leading-tight font-semibold tracking-[-0.01em]">{title}</h2>
          {description && <p className="text-muted-foreground max-w-3xl text-sm leading-relaxed">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
