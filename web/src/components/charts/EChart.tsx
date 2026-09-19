"use client";

import { BarChart, LineChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
  CanvasRenderer,
]);

export const PALETTE = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#14b8a6", "#f97316"];
export const INK = "#f3f4f6";
export const INK_MUTED = "#9ca3af";
export const GRID_LINE = "rgba(255,255,255,0.06)";

export type ChartOption = echarts.EChartsCoreOption;

/** A themed, resizing ECharts canvas. Pass a complete option; it is diffed on change. */
export function EChart({ option, height, label }: { option: ChartOption; height: number; label: string }) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!host.current) return;
    const instance = echarts.init(host.current, undefined, { renderer: "canvas" });
    chart.current = instance;
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(host.current);
    return () => {
      observer.disconnect();
      instance.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(
      {
        backgroundColor: "transparent",
        color: PALETTE,
        textStyle: { fontFamily: "inherit", color: INK_MUTED },
        tooltip: {
          backgroundColor: "#111827",
          borderColor: "rgba(255,255,255,0.12)",
          textStyle: { color: INK },
        },
        ...option,
      },
      { notMerge: true },
    );
  }, [option]);

  return <div ref={host} role="img" aria-label={label} style={{ height, width: "100%" }} />;
}
