import type { ComponentProps } from "react";
import type { ChartConfig, ChartTooltipContent } from "@/components/ui/chart";

type TipFormatter = NonNullable<ComponentProps<typeof ChartTooltipContent>["formatter"]>;

/**
 * Tooltip rows with our own number formatting (currency, units, percent…). shadcn's default row prints
 * `toLocaleString()`, which ignores the account's currency and the UI language.
 */
export function valueTip(config: ChartConfig, format: (value: number, key: string) => string): TipFormatter {
  return function tooltipRow(value, name, item) {
    const key = String(item.dataKey ?? name);
    const label = config[key]?.label ?? config[String(name)]?.label ?? String(name);
    const color = (item.payload as { fill?: string } | undefined)?.fill ?? item.color;
    return (
      <>
        <span className="size-2.5 shrink-0 rounded-[2px]" style={{ background: color }} aria-hidden />
        <div className="flex flex-1 items-center justify-between gap-6 leading-none">
          <span className="text-muted-foreground">{label}</span>
          <span className="text-foreground font-mono font-medium tabular-nums">{format(Number(value), key)}</span>
        </div>
      </>
    );
  };
}
