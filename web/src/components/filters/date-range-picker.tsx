"use client";

import { format, parseISO } from "date-fns";
import { de, enUS } from "date-fns/locale";
import { CalendarDays } from "lucide-react";
import { useState } from "react";
import type { DateRange } from "react-day-picker";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { usePresentation } from "@/lib/session";

const ISO = "yyyy-MM-dd";

/** Date range as ISO strings ("" = unbounded). Limited to the dates the account actually has data for. */
export function DateRangePicker({
  from,
  to,
  min,
  max,
  onChange,
}: {
  from: string;
  to: string;
  min?: string | null;
  max?: string | null;
  onChange: (range: { from: string; to: string }) => void;
}) {
  const { lang, t } = usePresentation();
  const [open, setOpen] = useState(false);
  const locale = lang === "de" ? de : enUS;
  const pattern = lang === "de" ? "dd.MM.yyyy" : "MMM d, yyyy";

  const start = from ? parseISO(from) : min ? parseISO(min) : undefined;
  const end = to ? parseISO(to) : max ? parseISO(max) : undefined;
  const custom = Boolean(from || to);
  const label =
    start && end ? `${format(start, pattern, { locale })} – ${format(end, pattern, { locale })}` : t("filter.period");

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" className="h-9 justify-start gap-2 font-normal" aria-label={t("filter.period")}>
          <CalendarDays className="text-muted-foreground size-4" />
          <span className={custom ? "" : "text-muted-foreground"}>{label}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto p-0">
        <Calendar
          mode="range"
          locale={locale}
          numberOfMonths={2}
          captionLayout="dropdown"
          defaultMonth={start}
          startMonth={min ? parseISO(min) : undefined}
          endMonth={max ? parseISO(max) : undefined}
          disabled={[...(min ? [{ before: parseISO(min) }] : []), ...(max ? [{ after: parseISO(max) }] : [])]}
          selected={start && end ? ({ from: start, to: end } as DateRange) : undefined}
          onSelect={(range) => {
            if (!range?.from) return;
            const next = { from: format(range.from, ISO), to: format(range.to ?? range.from, ISO) };
            onChange(next);
            if (range.to) setOpen(false);
          }}
        />
        {custom && (
          <div className="flex justify-end border-t p-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                onChange({ from: "", to: "" });
                setOpen(false);
              }}
            >
              {t("app.reset_filters")}
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
