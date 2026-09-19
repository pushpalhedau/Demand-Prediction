import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export type Tone = "positive" | "negative" | "neutral";

/** A headline figure. `trend` renders the note as a signed delta with direction; otherwise it is plain supporting text. */
export function KpiCard({
  label,
  value,
  note,
  tone = "neutral",
  trend = false,
  icon,
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  tone?: Tone;
  trend?: boolean;
  icon?: ReactNode;
}) {
  const Arrow = tone === "positive" ? ArrowUpRight : tone === "negative" ? ArrowDownRight : Minus;
  return (
    <Card className="gap-3 py-5">
      <CardHeader className="flex flex-row items-center justify-between gap-2 px-5">
        <CardDescription className="text-xs font-medium tracking-wide uppercase">{label}</CardDescription>
        {icon && <span className="text-muted-foreground">{icon}</span>}
      </CardHeader>
      <CardContent className="space-y-1 px-5">
        <div className="tabular text-2xl leading-none font-semibold tracking-tight lg:text-[1.7rem]">{value}</div>
        {note && (
          <p
            className={cn("flex items-center gap-1 text-xs", {
              "text-success": tone === "positive",
              "text-destructive": tone === "negative",
              "text-muted-foreground": tone === "neutral",
            })}
          >
            {trend && <Arrow className="size-3.5 shrink-0" aria-hidden />}
            <span>{note}</span>
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export function KpiSkeletonRow({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} className="h-[112px] rounded-xl" />
      ))}
    </div>
  );
}
