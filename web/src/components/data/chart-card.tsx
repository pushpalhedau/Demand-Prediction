import type { ReactNode } from "react";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/** A titled panel that holds a chart, table or any other analysis block. */
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
    <Card className="gap-4 py-5">
      {(title || description || action) && (
        <CardHeader className="px-5">
          {title && <CardTitle className="text-base">{title}</CardTitle>}
          {description && <CardDescription className="leading-relaxed">{description}</CardDescription>}
          {action && <CardAction>{action}</CardAction>}
        </CardHeader>
      )}
      <CardContent className="px-5">{children}</CardContent>
      {footer && <div className="text-muted-foreground border-t px-5 pt-4 text-xs">{footer}</div>}
    </Card>
  );
}

export function PanelSkeleton({ height = 300 }: { height?: number }) {
  return <Skeleton className="w-full rounded-xl" style={{ height }} />;
}
