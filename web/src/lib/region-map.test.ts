import { describe, expect, it } from "vitest";
import AE from "@/data/regions/AE.json";
import DE from "@/data/regions/DE.json";
import US from "@/data/regions/US.json";
import { bestBoundaries, canonicalKey, countryHint, indexRegions, matchScore, normalizeRegion, type RegionCollection } from "./region-map";

const sets = { US: US as unknown as RegionCollection, DE: DE as unknown as RegionCollection, AE: AE as unknown as RegionCollection };

// The region names the three demo datasets actually use.
const usRegions = ["Texas", "Florida", "Georgia", "Ohio", "North Carolina", "Tennessee"];
const deRegions = ["Baden-Württemberg", "Bayern", "Hessen", "Niedersachsen", "Nordrhein-Westfalen", "Rheinland-Pfalz"];
const aeRegions = ["Abu Dhabi", "Ajman", "Dubai", "Fujairah", "Ras Al Khaimah", "Sharjah"];

describe("region names", () => {
  it("ignores accents, case and punctuation", () => {
    expect(normalizeRegion("Baden-Württemberg")).toBe(normalizeRegion("BADEN WURTTEMBERG"));
    expect(normalizeRegion("Ras Al Khaimah")).toBe("rasalkhaimah");
  });

  it("knows the alternative spellings the data uses", () => {
    const index = indexRegions(sets.AE.features);
    expect(index.get(normalizeRegion("Dubai"))?.properties.name).toBe("Dubay");
    expect(index.get(normalizeRegion("Fujairah"))).toBeDefined();
    expect(indexRegions(sets.DE.features).get(normalizeRegion("Bavaria"))?.properties.name).toBe("Bayern");
  });
});

describe("region totals", () => {
  it("files every spelling of a region under one key, so no region loses its volume", () => {
    const index = indexRegions(sets.AE.features);
    expect(canonicalKey(index, "Dubai")).toBe(canonicalKey(index, "Dubay"));
    expect(canonicalKey(index, "Ras Al Khaimah")).toBe(normalizeRegion("Ras Al Khaymah"));
    expect(canonicalKey(index, "Fujairah")).toBe(normalizeRegion("Fujayrah"));
    expect(canonicalKey(null, "Atlantis")).toBe("atlantis");
  });
});

describe("choosing the boundary set", () => {
  it.each([
    ["US", usRegions],
    ["DE", deRegions],
    ["AE", aeRegions],
  ])("recognises every %s region in its own set", (code, regions) => {
    expect(matchScore(sets[code as keyof typeof sets], regions)).toBe(regions.length);
  });

  it("picks the right country from the regions alone", () => {
    const all = Object.values(sets);
    expect(bestBoundaries(all, usRegions)).toBe(sets.US);
    expect(bestBoundaries(all, deRegions)).toBe(sets.DE);
    expect(bestBoundaries(all, aeRegions)).toBe(sets.AE);
  });

  it("returns nothing for regions no set knows, so the map falls back to plain positions", () => {
    expect(bestBoundaries(Object.values(sets), ["Atlantis", "Narnia"])).toBeNull();
    expect(bestBoundaries(Object.values(sets), [])).toBeNull();
  });

  it("uses the account's country setting as a first guess", () => {
    expect(countryHint("United States")).toBe("US");
    expect(countryHint("Deutschland")).toBe("DE");
    expect(countryHint("United Arab Emirates")).toBe("AE");
    expect(countryHint("Wakanda")).toBeNull();
    expect(countryHint(null)).toBeNull();
  });
});

describe("boundary files", () => {
  it("are valid polygons with names and aliases", () => {
    for (const set of Object.values(sets)) {
      expect(set.features.length).toBeGreaterThan(5);
      for (const f of set.features) {
        expect(["Polygon", "MultiPolygon"]).toContain(f.geometry.type);
        expect(f.properties.name).toBeTruthy();
        expect(f.properties.aliases).toContain(f.properties.name);
      }
    }
  });

  it("wind exterior rings clockwise, which d3-geo needs (the opposite of GeoJSON: otherwise a region draws as the whole world minus itself)", () => {
    const signedArea = (ring: number[][]) => ring.slice(0, -1).reduce((sum, [x, y], i) => sum + x! * ring[i + 1]![1]! - ring[i + 1]![0]! * y!, 0);
    for (const set of Object.values(sets)) {
      for (const f of set.features) {
        const polygons = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
        for (const polygon of polygons) expect(signedArea(polygon[0]!)).toBeLessThan(0);
      }
    }
  });
});
