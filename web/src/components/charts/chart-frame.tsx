"use client";

import { Download, Maximize2 } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { downloadCsv } from "@/lib/csv";
import { usePresentation } from "@/lib/session";

export interface CsvExport {
  filename: string;
  headers: string[];
  rows: unknown[][];
}

/**
 * A chart with an insight headline (what to conclude, not what it is called), a key, and a toolbar to export the data
 * or expand it. `children` receives the height to draw at, so the expanded view is a real, larger chart.
 */
export function ChartFrame({
  headline,
  description,
  csv,
  children,
}: {
  headline: string;
  description?: ReactNode;
  csv?: CsvExport;
  children: (height: number) => ReactNode;
}) {
  const { t } = usePresentation();
  return (
    <section className="min-w-0 border-t pt-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="space-y-1.5">
          <h2 className="font-heading max-w-3xl text-[17px] leading-snug font-semibold tracking-[-0.01em] text-balance">{headline}</h2>
          {description && <div className="text-muted-foreground text-xs">{description}</div>}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {csv && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="size-8" aria-label={t("app.export_csv")} onClick={() => downloadCsv(csv.filename, csv.headers, csv.rows)}>
                  <Download className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>{t("app.export_csv")}</TooltipContent>
            </Tooltip>
          )}
          <Dialog>
            <Tooltip>
              <TooltipTrigger asChild>
                <DialogTrigger asChild>
                  <Button variant="ghost" size="icon" className="size-8" aria-label={t("chart.expand")}>
                    <Maximize2 className="size-4" />
                  </Button>
                </DialogTrigger>
              </TooltipTrigger>
              <TooltipContent>{t("chart.expand")}</TooltipContent>
            </Tooltip>
            <DialogContent className="max-w-[min(1200px,94vw)] sm:max-w-[min(1200px,94vw)]">
              <DialogHeader>
                <DialogTitle className="font-heading text-lg leading-snug">{headline}</DialogTitle>
                <DialogDescription asChild>{description ? <div>{description}</div> : <span className="sr-only">{headline}</span>}</DialogDescription>
              </DialogHeader>
              {children(520)}
            </DialogContent>
          </Dialog>
        </div>
      </div>
      {children(340)}
    </section>
  );
}
