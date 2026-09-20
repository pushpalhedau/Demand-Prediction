import type { Feature, FeatureCollection, MultiPolygon, Polygon } from "geojson";

export interface RegionProps {
  name: string;
  aliases: string[];
}
export type RegionFeature = Feature<Polygon | MultiPolygon, RegionProps>;
export type RegionCollection = FeatureCollection<Polygon | MultiPolygon, RegionProps>;

/** "Baden-Württemberg", "Baden Wurttemberg" and "BADEN-WURTTEMBERG" are one region. */
export function normalizeRegion(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

/** Every spelling of every region (its name and aliases) pointing at the region. */
export function indexRegions(features: RegionFeature[]): Map<string, RegionFeature> {
  const index = new Map<string, RegionFeature>();
  for (const f of features) {
    for (const spelling of [f.properties.name, ...f.properties.aliases]) index.set(normalizeRegion(spelling), f);
  }
  return index;
}

/** The key a region's totals live under: the matched boundary's own name, so "Dubai" and "Dubay" are one region. */
export function canonicalKey(index: Map<string, RegionFeature> | null, name: string): string {
  const feature = index?.get(normalizeRegion(name));
  return normalizeRegion(feature ? feature.properties.name : name);
}

/** How many of the data's region names a boundary set recognises: used to pick the right country's map. */
export function matchScore(collection: RegionCollection, regionNames: string[]): number {
  const index = indexRegions(collection.features);
  return new Set(regionNames.filter((r) => index.has(normalizeRegion(r))).map(normalizeRegion)).size;
}

/** The best-matching boundary set, or null when none recognises any of the regions. */
export function bestBoundaries(candidates: RegionCollection[], regionNames: string[]): RegionCollection | null {
  let best: RegionCollection | null = null;
  let bestScore = 0;
  for (const c of candidates) {
    const score = matchScore(c, regionNames);
    if (score > bestScore) {
      best = c;
      bestScore = score;
    }
  }
  return best;
}

/** Country name as the account settings write it -> the boundary file to try first. */
const COUNTRY_HINTS: Record<string, string> = {
  unitedstates: "US",
  unitedstatesofamerica: "US",
  usa: "US",
  us: "US",
  america: "US",
  germany: "DE",
  deutschland: "DE",
  de: "DE",
  unitedarabemirates: "AE",
  uae: "AE",
  ae: "AE",
};

export function countryHint(country: string | null | undefined): string | null {
  return country ? (COUNTRY_HINTS[normalizeRegion(country)] ?? null) : null;
}

export const BOUNDARY_CODES = ["US", "DE", "AE"] as const;
