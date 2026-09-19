import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";

/** A titled block on a page, divided from the one above by a hairline (no card box). */
export function Panel({
  title,
  description,
  action,
  children,
  footer,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <section className="min-w-0 border-t pt-5">
      {(title || description || action) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            {title && <h2 className="font-heading text-[17px] leading-tight font-semibold tracking-[-0.01em]">{title}</h2>}
            {description && <p className="text-muted-foreground max-w-3xl text-sm leading-relaxed">{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
      {footer && <p className="text-muted-foreground mt-4 text-xs leading-relaxed">{footer}</p>}
    </section>
  );
}

export function PanelSkeleton({ height = 300 }: { height?: number }) {
  return <Skeleton className="w-full rounded-lg" style={{ height }} />;
}
