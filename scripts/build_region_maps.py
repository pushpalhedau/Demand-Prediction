"""
Build the small region-boundary files the Store Performance map draws (web/src/data/regions/<CC>.json).

Source: Natural Earth 1:10m "Admin 1 - States, Provinces" (public domain, naturalearthdata.com). Download once:
    https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson

    pip install shapely            # dev-only, not a runtime dependency
    python scripts/build_region_maps.py --src path/to/ne_10m_admin_1_states_provinces.geojson

Each output is a GeoJSON FeatureCollection whose features carry `name` and `aliases` (other spellings the platform's data
may use), simplified and rounded so a country is tens of KB. To support another country, add it to COUNTRIES.
"""
import argparse
import json
from pathlib import Path

from shapely.geometry import MultiPolygon, mapping, shape
from shapely.geometry.polygon import orient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "src" / "data" / "regions"

# iso_a2 -> (simplify tolerance in degrees, names to drop, extra spellings by Natural Earth name)
COUNTRIES = {
    "US": (0.03, set(), {}),
    "DE": (0.012, set(), {
        "Baden-Württemberg": ["Baden-Wurttemberg"], "Bayern": ["Bavaria"], "Hessen": ["Hesse"],
        "Niedersachsen": ["Lower Saxony"], "Nordrhein-Westfalen": ["North Rhine-Westphalia", "NRW"],
        "Rheinland-Pfalz": ["Rhineland-Palatinate"], "Sachsen": ["Saxony"], "Sachsen-Anhalt": ["Saxony-Anhalt"],
        "Thüringen": ["Thuringia"], "Mecklenburg-Vorpommern": ["Mecklenburg-Western Pomerania"],
    }),
    "AE": (0.004, {"Neutral Zone"}, {
        "Dubay": ["Dubai"], "Fujayrah": ["Fujairah", "Al Fujayrah"], "Ras Al Khaymah": ["Ras Al Khaimah", "Ras al-Khaimah"],
        "Umm Al Qaywayn": ["Umm Al Quwain", "Umm al-Quwain"], "Ajman": ["Ajman", "Ajmān"],
    }),
}


def _clockwise(geom):
    """d3-geo (which draws the map) reads polygons as spherical shapes and needs exterior rings clockwise, the opposite of
    the GeoJSON standard. Left as-is, every region is drawn as 'the whole world except this region'."""
    if geom.geom_type == "Polygon":
        return orient(geom, sign=-1.0)
    if geom.geom_type == "MultiPolygon":
        return MultiPolygon([orient(p, sign=-1.0) for p in geom.geoms])
    return geom


def _signed_area(ring):
    return sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1] for i in range(len(ring) - 1))


def _drop_slivers(geometry, min_area=2e-4):
    """After rounding, specks smaller than ~2 km2 can flip direction; they are invisible at map scale, so drop them."""
    if geometry["type"] == "Polygon":
        return geometry if _signed_area(geometry["coordinates"][0]) < -min_area else None
    polygons = [p for p in geometry["coordinates"] if _signed_area(p[0]) < -min_area]
    return {"type": "MultiPolygon", "coordinates": polygons} if polygons else None


def _round(coords, digits=3):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], digits), round(coords[1], digits)]
    return [_round(c, digits) for c in coords]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    args = ap.parse_args()
    data = json.loads(Path(args.src).read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    for code, (tolerance, drop, extra) in COUNTRIES.items():
        features = []
        for f in data["features"]:
            props = f["properties"]
            if props.get("iso_a2") != code or props["name"] in drop:
                continue
            geom = shape(f["geometry"]).simplify(tolerance, preserve_topology=True)
            if geom.is_empty:
                continue
            name = props["name"]
            aliases = {name, props.get("name_en") or name, *(extra.get(name, []))}
            for alt in (props.get("name_alt") or "").split("|"):
                if alt.strip():
                    aliases.add(alt.strip())
            g = mapping(_clockwise(geom))
            geometry = _drop_slivers({"type": g["type"], "coordinates": _round(g["coordinates"])})
            if geometry:
                features.append({"type": "Feature", "properties": {"name": name, "aliases": sorted(aliases)}, "geometry": geometry})
        path = OUT / f"{code}.json"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":"), ensure_ascii=False),
                        encoding="utf-8")
        print(f"{code}: {len(features)} regions, {path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
