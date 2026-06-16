"""
preprocessing/fetch_dealer_rankings.py

Fetches real Google Maps review counts for all 50 UAE dealers using Serper.dev.
Review count (user_ratings_total) is the only publicly available per-dealer
activity signal — it accumulates proportionally to sales volume and footfall.

Output → realdata-datasets/dealer_rankings_google.csv
  Columns include:
    google_rating        : live Google Maps star rating
    user_ratings_total   : cumulative review count (primary ranking signal)
    reviews_per_year     : review count / years since established (age-normalised)
    brand_rank           : rank within same brand (1 = top seller of that brand)
    brand_sales_weight   : share of brand's transactions to assign this dealer (0–1)

FREE SETUP - takes about 3 minutes, no credit card
  1. Go to https://serper.dev
  2. Click "Get Started Free" - sign up with email only
  3. Dashboard -> copy your API Key
  4. Add to .env:   SERPER_API_KEY=<your_key>
  5. Run:           python preprocessing/fetch_dealer_rankings.py

Free tier: 2,500 requests/month (this script uses ~100-150 for all 50 dealers)
No credit card. No expiry.

No extra packages needed — uses only `requests` (already in requirements.txt).
"""

import os
import re
import math
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_MAPS_URL = "https://google.serper.dev/maps"

DEALERS_CSV  = "realdata-datasets/dealers.csv"
OUTPUT_CSV   = "realdata-datasets/dealer_rankings_google.csv"
CURRENT_YEAR = 2026

# Max distance (km) between expected GPS and Google result — rejects false matches
MAX_DIST_KM = 3.0


# ── Geo helpers ──────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two GPS points."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def confidence_label(dist_km: float) -> str:
    if dist_km < 0:      return "not_found"
    if dist_km <= 0.3:   return "high"
    if dist_km <= 1.5:   return "medium"
    return "low"


# ── Serper search ────────────────────────────────────────────────────────────

def serper_maps_search(query: str, lat: float, lon: float) -> list:
    """
    Calls Serper.dev /maps endpoint and returns a list of place dicts.
    Each dict may contain: title, address, latitude, longitude, rating, ratingCount.
    """
    headers = {
        "X-API-KEY":    SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "q":  query,
        "ll": f"@{lat},{lon},15z",   # location hint (zoom 15 ≈ city level)
        "hl": "en",
        "gl": "ae",                  # country = UAE
    }
    try:
        resp = requests.post(SERPER_MAPS_URL, headers=headers, json=payload, timeout=12)
        resp.raise_for_status()
        return resp.json().get("places", [])
    except requests.RequestException as exc:
        print(f"    ⚠  Serper request failed: {exc}")
        return []


def parse_review_count(place: dict) -> int:
    """
    Extract review count from a Serper place result.
    Serper uses 'ratingCount' but may also surface it in a 'reviews' field
    or as a formatted string like '(1,234)'.
    """
    # Direct numeric fields
    for key in ("ratingCount", "reviewsCount", "reviews", "userRatingsTotal"):
        val = place.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return int(val)

    # String fields that might contain a count, e.g. "1,234 reviews" or "(567)"
    for key in ("ratingCount", "reviews", "reviewsText"):
        val = place.get(key, "")
        if isinstance(val, str):
            match = re.search(r"([\d,]+)", val)
            if match:
                return int(match.group(1).replace(",", ""))

    return 0


def find_dealer(name: str, brand: str, city: str, lat: float, lon: float) -> dict:
    """
    Tries multiple query strategies to find the best matching Google Maps place
    for a dealer within MAX_DIST_KM of its known GPS coordinates.
    Returns the matched place dict, augmented with _distance_km and _query_used,
    or an empty dict if nothing is found within the distance threshold.
    """
    queries = [
        name,                                    # "Al-Futtaim Motors - Dubai Festival City"
        f"{name} {brand}",                       # "Al-Futtaim Motors - Dubai Festival City Toyota"
        f"{brand} dealer {city} UAE",            # "Toyota dealer Dubai UAE"
        f"{name.split('-')[0].strip()} {city}",  # "Al-Futtaim Motors Dubai"
    ]

    for query in queries:
        places = serper_maps_search(query, lat, lon)

        for place in places:
            r_lat = place.get("latitude")
            r_lon = place.get("longitude")

            if r_lat is None or r_lon is None:
                continue

            dist_km = haversine_km(lat, lon, float(r_lat), float(r_lon))

            if dist_km <= MAX_DIST_KM:
                place["_distance_km"] = round(dist_km, 2)
                place["_query_used"]  = query
                return place

        time.sleep(0.15)   # stay well under Serper's rate limit

    return {}


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    if not SERPER_API_KEY:
        print("""
  ERROR: SERPER_API_KEY not found in .env

  Steps (free, no credit card, ~3 min):
    1. https://serper.dev -> "Get Started Free"
    2. Sign up with email -> verify -> Dashboard
    3. Copy your API Key
    4. Add to .env:  SERPER_API_KEY=<your_key>

  Free tier: 2,500 requests/month
  This script uses ~100-150 requests for all 50 dealers
""")
        return

    df = pd.read_csv(DEALERS_CSV)
    results = []

    print(f"Fetching Google Maps data for {len(df)} dealers via Serper.dev...\n")
    header = f"{'ID':<10} {'Dealer':<48} {'Reviews':>8}  {'Rating':>6}  {'Dist':>6}  Conf"
    print(header)
    print("-" * 90)

    for _, row in df.iterrows():
        dealer_id        = row["dealer_id"]
        name             = row["dealer_name"]
        brand            = row["brand"]
        city             = row["city"]
        lat              = float(row["latitude"])
        lon              = float(row["longitude"])
        established_year = int(row.get("established_year", 2000))

        place = find_dealer(name, brand, city, lat, lon)

        if place:
            ratings_total = parse_review_count(place)
            rating        = place.get("rating")
            dist_km       = place.get("_distance_km", -1)
            confidence    = confidence_label(dist_km)
            google_name   = place.get("title", "")
            place_id      = place.get("placeId", place.get("place_id", ""))
            query_used    = place.get("_query_used", "")
        else:
            ratings_total = 0
            rating        = None
            dist_km       = -1
            confidence    = "not_found"
            google_name   = ""
            place_id      = ""
            query_used    = ""

        years_active   = max(1, CURRENT_YEAR - established_year)
        reviews_per_yr = round(ratings_total / years_active, 1)

        rating_str = f"{rating} ★" if rating else "  —  "
        dist_str   = f"{dist_km}km" if dist_km >= 0 else "  —  "
        mark       = "OK" if confidence not in ("not_found", "low") else ("~" if confidence == "low" else "!!")

        print(
            f"{dealer_id:<10} {name:<48} {ratings_total:>8,}  "
            f"{rating_str:>6}  {dist_str:>6}  {mark} {confidence}"
        )

        results.append({
            "dealer_id":          dealer_id,
            "dealer_name":        name,
            "brand":              brand,
            "region":             row["region"],
            "city":               city,
            "established_year":   established_year,
            "years_active":       years_active,
            "synthetic_tier":     row["tier"],
            "google_place_id":    place_id,
            "google_name":        google_name,
            "google_rating":      rating,
            "user_ratings_total": ratings_total,
            "reviews_per_year":   reviews_per_yr,
            "distance_km":        dist_km,
            "match_confidence":   confidence,
            "query_used":         query_used,
        })

        time.sleep(0.2)

    out = pd.DataFrame(results)

    # ── Rank within brand by raw review count (primary signal) ───────────────
    out["brand_rank"] = (
        out.groupby("brand")["user_ratings_total"]
           .rank(method="dense", ascending=False)
           .astype(int)
    )

    # ── Age-normalised rank (reviews per year since established) ─────────────
    out["brand_rank_per_year"] = (
        out.groupby("brand")["reviews_per_year"]
           .rank(method="dense", ascending=False)
           .astype(int)
    )

    # ── Normalised weight per brand (sums to 1.0 per brand) ──────────────────
    brand_totals = out.groupby("brand")["user_ratings_total"].transform("sum")
    out["brand_sales_weight"] = (
        out["user_ratings_total"] / brand_totals.replace(0, 1)
    ).round(4)

    out = out.sort_values(["brand", "brand_rank"]).reset_index(drop=True)
    out.to_csv(OUTPUT_CSV, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    found   = (out["match_confidence"] != "not_found").sum()
    high_cf = (out["match_confidence"] == "high").sum()
    med_cf  = (out["match_confidence"] == "medium").sum()

    print("\n" + "=" * 90)
    print(f"Saved  →  {OUTPUT_CSV}")
    print(f"Matched:  {found}/{len(out)}   (high: {high_cf}  medium: {med_cf}  low: {found - high_cf - med_cf})\n")

    print("Top 15 dealers by Google Maps review count:")
    top = out.nlargest(15, "user_ratings_total")[
        ["dealer_name", "brand", "user_ratings_total", "reviews_per_year",
         "google_rating", "brand_rank", "match_confidence"]
    ]
    print(top.to_string(index=False))

    unmatched = out[out["match_confidence"] == "not_found"]["dealer_name"].tolist()
    if unmatched:
        print(f"\n⚠  Not found ({len(unmatched)}) — check names/GPS or add manually:")
        for d in unmatched:
            print(f"   • {d}")

    low_cf = out[out["match_confidence"] == "low"]["dealer_name"].tolist()
    if low_cf:
        print(f"\n⚠  Low confidence matches ({len(low_cf)}) — verify manually:")
        for d in low_cf:
            print(f"   • {d}")


if __name__ == "__main__":
    main()
