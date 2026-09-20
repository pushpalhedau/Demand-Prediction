"use client";

import { useQuery } from "@tanstack/react-query";
import { geoContains, geoMercator, geoPath } from "d3-geo";
import type { Feature, MultiPoint } from "geojson";
import { useMemo, useRef, useState, type PointerEvent } from "react";
import { PanelSkeleton } from "@/components/data/chart-card";
import { attainmentColor } from "@/lib/attainment";
import {
  BOUNDARY_CODES,
  bestBoundaries,
  countryHint,
  canonicalKey,
  indexRegions,
  normalizeRegion,
  type RegionCollection,
  type RegionFeature,
} from "@/lib/region-map";
import { useFormat, usePresentation } from "@/lib/session";
import type { StoreRow } from "@/lib/types";

const LOADERS: Record<string, () => Promise<{ default: unknown }>> = {
  US: () => import("@/data/regions/US.json"),
  DE: () => import("@/data/regions/DE.json"),
  AE: () => import("@/data/regions/AE.json"),
};

const loadBoundaries = async (code: string) => (await LOADERS[code]?.())?.default as RegionCollection | undefined;

const WIDTH = 1000;
const PAD = 36;

type Hover = { kind: "store"; id: string } | { kind: "region"; key: string } | null;

const bubbleRadius = (units: number, maxUnits: number) => 5 + 17 * Math.sqrt(units / maxUnits);

interface Layout {
  height: number;
  bubbles: Map<string, { x: number; y: number; r: number }>;
  regions: { key: string; feature: RegionFeature; path: string; label: [number, number]; operating: boolean }[];
  project: (lng: number, lat: number) => [number, number] | null;
}

/** Fit the map to the regions the group trades in (and every rooftop), at a fixed width; the height follows. */
function layoutMap(boundaries: RegionCollection | null, stores: StoreRow[], operatingKeys: Set<string>): Layout {
  const points: [number, number][] = stores.map((s) => [s.longitude as number, s.latitude as number]);
  const index = boundaries ? indexRegions(boundaries.features) : null;
  const seen = new Set<RegionFeature>();
  const operating: RegionFeature[] = [];
  for (const key of operatingKeys) {
    const f = index?.get(key);
    if (f && !seen.has(f)) {
      seen.add(f);
      operating.push(f);
    }
  }
  const pointsFeature: Feature<MultiPoint> = { type: "Feature", properties: {}, geometry: { type: "MultiPoint", coordinates: points } };
  const focus = { type: "FeatureCollection" as const, features: [...operating, pointsFeature] };

  const projection = geoMercator();
  const distinct = new Set(points.map((p) => p.join(","))).size;
  if (distinct < 2 && operating.length === 0) {
    projection.center(points[0] ?? [0, 0]).scale(30000).translate([WIDTH / 2, 260]);
  } else {
    projection.fitWidth(WIDTH - PAD * 2, focus);
    const [tx, ty] = projection.translate();
    projection.translate([tx + PAD, ty + PAD]);
  }
  const path = geoPath(projection);
  const y1 = path.bounds(focus)[1][1];
  const height = distinct < 2 && operating.length === 0 ? 520 : Math.max(Math.round(y1 + PAD), 300);

  const maxUnits = Math.max(...stores.map((s) => s.units_sold), 1);
  const bubbles = new Map<string, { x: number; y: number; r: number }>();
  for (const s of stores) {
    const at = projection([s.longitude as number, s.latitude as number]);
    if (at) bubbles.set(s.dealer_id, { x: at[0], y: at[1], r: bubbleRadius(s.units_sold, maxUnits) });
  }

  // Put each region's name where it is inside the region and clear of every bubble and of the other names.
  const placed: { x0: number; x1: number; y0: number; y1: number }[] = [];
  const clear = (box: { x0: number; x1: number; y0: number; y1: number }) => {
    for (const b of bubbles.values()) {
      const nx = Math.min(Math.max(b.x, box.x0), box.x1);
      const ny = Math.min(Math.max(b.y, box.y0), box.y1);
      if ((b.x - nx) ** 2 + (b.y - ny) ** 2 < (b.r + 4) ** 2) return false;
    }
    return placed.every((p) => box.x1 < p.x0 || box.x0 > p.x1 || box.y1 < p.y0 || box.y0 > p.y1);
  };
  const labelAt = (feature: RegionFeature): [number, number] => {
    const [cx, cy] = path.centroid(feature);
    const w = feature.properties.name.length * 10.4;
    const candidates: [number, number][] = [];
    for (let dy = -120; dy <= 120; dy += 20) for (let dx = -160; dx <= 160; dx += 20) candidates.push([dx, dy]);
    candidates.sort((a, b) => Math.hypot(a[0], a[1]) - Math.hypot(b[0], b[1]));
    // First choice: inside the region. Small regions (Ajman, say) cannot fit a name, so the fallback sits just outside.
    for (const mustBeInside of [true, false]) {
      for (const [dx, dy] of candidates) {
        const x = cx + dx;
        const y = cy + dy;
        const box = { x0: x - w / 2, x1: x + w / 2, y0: y - 14, y1: y + 5 };
        const inside =
          !mustBeInside ||
          [[x - w / 2, y - 6], [x + w / 2, y - 6], [x, y]].every((pt) => {
            const lonLat = projection.invert?.(pt as [number, number]);
            return lonLat ? geoContains(feature, lonLat) : true;
          });
        if (inside && clear(box)) {
          placed.push(box);
          return [x, y];
        }
      }
    }
    return [cx, cy];
  };

  const regions = (boundaries?.features ?? []).map((feature) => ({
    key: normalizeRegion(feature.properties.name),
    feature,
    path: path(feature) ?? "",
    operating: seen.has(feature),
    label: seen.has(feature) ? labelAt(feature) : ([0, 0] as [number, number]),
  }));
  return { height, bubbles, regions, project: (lng, lat) => projection([lng, lat]) };
}

/**
 * A real map of the group's footprint: region boundaries with every rooftop on them. Bubble size is units sold, bubble
 * colour is pace against target, and a region's shading is its share of the group's units. Drawn with the theme's own
 * colours, so it follows light and dark mode; no map tiles or external service is used.
 */
export function RegionMap({ stores, country }: { stores: StoreRow[]; country: string | null | undefined }) {
  const { t } = usePresentation();
  const fmt = useFormat();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<Hover>(null);
  const [pos, setPos] = useState({ x: 0, y: 0, flip: false });

  const regionNames = useMemo(() => [...new Set(stores.map((s) => s.region).filter((r): r is string => Boolean(r)))].sort(), [stores]);
  const hint = countryHint(country);
  const boundaries = useQuery({
    queryKey: ["region-boundaries", hint, regionNames],
    staleTime: Infinity,
    queryFn: async () => {
      const codes = hint ? [hint] : [...BOUNDARY_CODES];
      const loaded = (await Promise.all(codes.map(loadBoundaries))).filter((c): c is RegionCollection => Boolean(c));
      const best = bestBoundaries(loaded, regionNames);
      if (best || !hint) return best;
      // The country setting pointed at a set that recognises none of the regions: try the others.
      const rest = (await Promise.all(BOUNDARY_CODES.filter((c) => c !== hint).map(loadBoundaries))).filter((c): c is RegionCollection => Boolean(c));
      return bestBoundaries(rest, regionNames);
    },
  });

  const maxUnits = Math.max(...stores.map((s) => s.units_sold), 1);
  const operatingKeys = useMemo(() => new Set(regionNames.map(normalizeRegion)), [regionNames]);
  const layout = useMemo(
    () => (boundaries.isPending ? null : layoutMap(boundaries.data ?? null, stores, operatingKeys)),
    [boundaries.isPending, boundaries.data, stores, operatingKeys],
  );

  const regionIndex = useMemo(() => (boundaries.data ? indexRegions(boundaries.data.features) : null), [boundaries.data]);
  const totals = useMemo(() => {
    const by = new Map<string, { stores: number; units: number; paceWeight: number; paceUnits: number; label: string }>();
    for (const s of stores) {
      if (!s.region) continue;
      const key = canonicalKey(regionIndex, s.region);
      const row = by.get(key) ?? { stores: 0, units: 0, paceWeight: 0, paceUnits: 0, label: s.region };
      row.stores += 1;
      row.units += s.units_sold;
      if (s.attainment_pct !== null) {
        row.paceWeight += s.attainment_pct * s.units_sold;
        row.paceUnits += s.units_sold;
      }
      by.set(key, row);
    }
    return by;
  }, [stores, regionIndex]);
  const maxRegionUnits = Math.max(...[...totals.values()].map((r) => r.units), 1);

  if (!layout) return <PanelSkeleton height={420} />;

  const place = (event: PointerEvent) => {
    const box = wrapRef.current?.getBoundingClientRect();
    if (box) setPos({ x: event.clientX - box.left, y: event.clientY - box.top, flip: event.clientX - box.left > box.width - 260 });
  };
  const ordered = [...stores].sort((a, b) => b.units_sold - a.units_sold);
  const hoveredStore = hover?.kind === "store" ? stores.find((s) => s.dealer_id === hover.id) : undefined;
  const hoveredRegion = hover?.kind === "region" ? totals.get(hover.key) : undefined;
  const regionShade = (key: string) => {
    const r = totals.get(key);
    return r ? Math.round(22 + 38 * (r.units / maxRegionUnits)) : 0;
  };
  const yoy = (v: number | null) => (v === null ? t("val.na") : fmt.pct(v, 1, true));

  return (
    <div ref={wrapRef} className="relative" onPointerMove={place} onPointerLeave={() => setHover(null)}>
      <svg
        viewBox={`0 0 ${WIDTH} ${layout.height}`}
        role="img"
        aria-label={t("rg.map.aria")}
        className="mx-auto w-full rounded-lg border"
        style={{ background: "color-mix(in oklab, var(--primary) 5%, var(--background))", maxHeight: 720 }}
      >
        <rect width={WIDTH} height={layout.height} fill="transparent" onPointerEnter={() => setHover(null)} />
        <g strokeLinejoin="round">
          {layout.regions.map((r) => (
            <path
              key={r.key}
              d={r.path}
              fill={r.operating ? `color-mix(in oklab, var(--chart-1) ${regionShade(r.key)}%, var(--card))` : "var(--card)"}
              stroke={
                hover?.kind === "region" && hover.key === r.key
                  ? "var(--foreground)"
                  : r.operating
                    ? "color-mix(in oklab, var(--chart-1) 55%, var(--border))"
                    : "var(--border)"
              }
              strokeWidth={hover?.kind === "region" && hover.key === r.key ? 1.6 : 1}
              onPointerEnter={(e) => {
                place(e);
                setHover(r.operating ? { kind: "region", key: r.key } : null);
              }}
            />
          ))}
        </g>
        <g pointerEvents="none">
          {layout.regions
            .filter((r) => r.operating)
            .map((r) => (
              <text
                key={r.key}
                x={r.label[0]}
                y={r.label[1]}
                textAnchor="middle"
                className="fill-muted-foreground text-[14px] font-medium tracking-[0.06em] uppercase"
                style={{ paintOrder: "stroke", stroke: "var(--card)", strokeWidth: 3, strokeLinejoin: "round" }}
              >
                {r.feature.properties.name}
              </text>
            ))}
        </g>
        <g>
          {ordered.map((s) => {
            const at = layout.project(s.longitude as number, s.latitude as number);
            if (!at) return null;
            const active = hover?.kind === "store" && hover.id === s.dealer_id;
            return (
              <circle
                key={s.dealer_id}
                cx={at[0]}
                cy={at[1]}
                r={bubbleRadius(s.units_sold, maxUnits)}
                fill={attainmentColor(s.attainment_pct)}
                fillOpacity={0.88}
                stroke={active ? "var(--foreground)" : "var(--background)"}
                strokeWidth={active ? 2.2 : 1.5}
                tabIndex={0}
                role="img"
                aria-label={`${s.dealer_name}: ${fmt.num(s.units_sold)}`}
                onPointerEnter={(e) => {
                  place(e);
                  setHover({ kind: "store", id: s.dealer_id });
                }}
                onFocus={() => setHover({ kind: "store", id: s.dealer_id })}
                onBlur={() => setHover(null)}
              />
            );
          })}
        </g>
      </svg>

      {(hoveredStore || hoveredRegion) && (
        <div
          className="bg-background pointer-events-none absolute z-10 grid gap-1 rounded-lg border px-3 py-2 text-xs shadow-xl"
          style={{ left: pos.flip ? pos.x - 16 : pos.x + 16, top: Math.max(pos.y - 12, 0), transform: pos.flip ? "translateX(-100%)" : undefined }}
        >
          {hoveredStore ? (
            <>
              <p className="text-sm font-medium">{hoveredStore.dealer_name}</p>
              <p className="text-muted-foreground">
                {hoveredStore.brand} · {hoveredStore.city}, {hoveredStore.region}
              </p>
              <p className="tabular">
                {fmt.num(hoveredStore.units_sold)} {t("ov.trend.units").toLowerCase()} · {fmt.money(hoveredStore.revenue)}
              </p>
              <p className="tabular">
                {hoveredStore.attainment_pct === null ? t("rg.no_target") : t("rg.of_target", { v: fmt.pct(hoveredStore.attainment_pct, 0) })} · {yoy(hoveredStore.yoy_units_pct)} {t("rg.yoy")}
              </p>
            </>
          ) : (
            hoveredRegion && (
              <>
                <p className="text-sm font-medium">{hoveredRegion.label}</p>
                <p className="tabular">{t("rg.map.region_meta", { n: hoveredRegion.stores, units: fmt.num(hoveredRegion.units) })}</p>
                {hoveredRegion.paceUnits > 0 && (
                  <p className="tabular">{t("rg.map.avg_pace", { v: fmt.pct(hoveredRegion.paceWeight / hoveredRegion.paceUnits, 0) })}</p>
                )}
              </>
            )
          )}
        </div>
      )}
    </div>
  );
}
