"""
preprocessing/patch_dealer_rankings.py

Second-pass retry for dealers that were not_found or had suspicious matches
(0 reviews where a real dealer should have many, or absurdly high counts
indicating a wrong place was matched).

Runs targeted alternative queries for each problem dealer, then writes
the corrections back into dealer_rankings_google.csv.

Run AFTER fetch_dealer_rankings.py:
  python preprocessing/patch_dealer_rankings.py
"""

import os
import sys
import io
import re
import math
import time
import requests
import pandas as pd
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
load_dotenv()

SERPER_API_KEY  = os.getenv("SERPER_API_KEY", "")
SERPER_MAPS_URL = "https://google.serper.dev/maps"
RANKINGS_CSV    = "realdata-datasets/dealer_rankings_google.csv"
MAX_DIST_KM     = 3.0

# ---------------------------------------------------------------------------
# Dealers that need targeted retry — manually curated alternative queries
# and tighter GPS anchors based on known UAE dealer network.
# ---------------------------------------------------------------------------
RETRY_TARGETS = {
    # dealer_id : list of (query, lat, lon) to attempt in order
    "DLR0014": [  # Arabian Automobiles - Ajman
        ("Arabian Automobiles Ajman Nissan", 25.415186, 55.520321),
        ("Nissan dealer Ajman UAE",           25.415186, 55.520321),
        ("Arabian Automobiles Company Ajman", 25.415186, 55.520321),
    ],
    "DLR0012": [  # Arabian Automobiles - Abu Dhabi
        ("Arabian Automobiles Abu Dhabi Nissan",   24.458367, 54.384948),
        ("Arabian Automobiles Company Abu Dhabi",  24.458367, 54.384948),
        ("Nissan showroom Abu Dhabi Electra",      24.458367, 54.384948),
    ],
    "DLR0025": [  # Al Habtoor Motors - Abu Dhabi
        ("Al Habtoor Motors Abu Dhabi Mitsubishi", 24.444665, 54.379231),
        ("Al Habtoor Motors Abu Dhabi",            24.444665, 54.379231),
        ("Mitsubishi dealer Abu Dhabi UAE",        24.444665, 54.379231),
    ],
    "DLR0028": [  # Juma Al Majid - Abu Dhabi Hyundai
        ("JMEA Hyundai Abu Dhabi",                 24.450345, 54.376136),
        ("Juma Al Majid Hyundai Abu Dhabi",        24.450345, 54.376136),
        ("Hyundai showroom Abu Dhabi UAE",         24.450345, 54.376136),
    ],
    "DLR0029": [  # Kia UAE - Dubai Motor City
        ("Kia Motors Motor City Dubai",            25.035997, 55.237508),
        ("Kia showroom Dubai Motor City",          25.035997, 55.237508),
        ("Kia dealer Motor City UAE",              25.035997, 55.237508),
    ],
    "DLR0030": [  # Kia UAE - Abu Dhabi
        ("Kia Motors Abu Dhabi UAE",               24.446851, 54.381052),
        ("Kia showroom Abu Dhabi",                 24.446851, 54.381052),
        ("Kia dealer Abu Dhabi UAE",               24.446851, 54.381052),
    ],
    "DLR0031": [  # Kia UAE - Sharjah
        ("Kia Motors Sharjah UAE",                 25.346923, 55.422079),
        ("Kia showroom Sharjah",                   25.346923, 55.422079),
        ("Kia dealer Sharjah UAE",                 25.346923, 55.422079),
    ],
    "DLR0040": [  # Al Nabooda - Abu Dhabi Volkswagen
        ("Al Nabooda Automobiles Abu Dhabi VW",    24.456612, 54.383874),
        ("Al Nabooda Automobiles Abu Dhabi",       24.456612, 54.383874),
        ("Volkswagen dealer Abu Dhabi UAE",        24.456612, 54.383874),
    ],
    "DLR0041": [  # Premier Motors - Abu Dhabi Land Rover
        ("Premier Motors Land Rover Abu Dhabi",    24.460934, 54.383915),
        ("Premier Motors Abu Dhabi",               24.460934, 54.383915),
        ("Land Rover dealer Abu Dhabi UAE",        24.460934, 54.383915),
    ],
    "DLR0042": [  # Al Masaood - Abu Dhabi Nissan
        ("Al Masaood Automobiles Abu Dhabi Nissan", 24.461506, 54.381324),
        ("Al Masaood Automobiles Abu Dhabi",        24.461506, 54.381324),
        ("Nissan dealer Abu Dhabi Mussafah",        24.461506, 54.381324),
    ],
    "DLR0049": [  # Juma Al Majid - Ajman Hyundai
        ("JMEA Hyundai Ajman",                     25.399868, 55.508891),
        ("Juma Al Majid Hyundai Ajman",            25.399868, 55.508891),
        ("Hyundai dealer Ajman UAE",               25.399868, 55.508891),
    ],
    # --- Suspicious wrong-match corrections ---
    # DLR0001 matched 50 reviews (Al-Futtaim Dubai Festival City should be much higher)
    "DLR0001": [
        ("Al-Futtaim Toyota Dubai Festival City",  25.23054, 55.353925),
        ("Toyota showroom Dubai Festival City",    25.23054, 55.353925),
        ("Al Futtaim Motors Festival City Dubai",  25.23054, 55.353925),
    ],
    # DLR0035 matched 39,847 reviews — almost certainly a mall, not a Ford dealer
    "DLR0035": [
        ("International Traders Ford Dubai",       25.21161, 55.279191),
        ("Ford dealer Sheikh Zayed Road Dubai",    25.21161, 55.279191),
        ("International Traders Cars Dubai",       25.21161, 55.279191),
    ],
    # DLR0019 matched 1 review — Gargash Abu Dhabi is a flagship, should have many
    "DLR0019": [
        ("Gargash Enterprises Mercedes Abu Dhabi", 24.457257, 54.378392),
        ("Gargash Motors Mercedes-Benz Abu Dhabi", 24.457257, 54.378392),
        ("Mercedes-Benz dealer Abu Dhabi UAE",     24.457257, 54.378392),
    ],
    # DLR0033 matched 1.5 stars / 2 reviews — likely wrong place
    "DLR0033": [
        ("Al Ghandi Auto Abu Dhabi Chevrolet",    24.448179, 54.375597),
        ("Al Ghandi Automobiles Abu Dhabi",       24.448179, 54.375597),
        ("Chevrolet dealer Abu Dhabi UAE",        24.448179, 54.375597),
    ],
}


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def confidence_label(dist_km):
    if dist_km < 0:     return "not_found"
    if dist_km <= 0.3:  return "high"
    if dist_km <= 1.5:  return "medium"
    return "low"


def parse_review_count(place):
    for key in ("ratingCount", "reviewsCount", "reviews", "userRatingsTotal"):
        val = place.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return int(val)
    for key in ("ratingCount", "reviews", "reviewsText"):
        val = place.get(key, "")
        if isinstance(val, str):
            m = re.search(r"([\d,]+)", val)
            if m:
                return int(m.group(1).replace(",", ""))
    return 0


def serper_search(query, lat, lon):
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": query, "ll": f"@{lat},{lon},15z", "hl": "en", "gl": "ae"}
    try:
        r = requests.post(SERPER_MAPS_URL, headers=headers, json=payload, timeout=12)
        r.raise_for_status()
        return r.json().get("places", [])
    except Exception as e:
        print(f"  Serper error: {e}")
        return []


def try_queries(dealer_id, queries):
    """Try each (query, lat, lon) in order; return best match within MAX_DIST_KM."""
    for query, lat, lon in queries:
        places = serper_search(query, lat, lon)
        for place in places:
            r_lat = place.get("latitude")
            r_lon = place.get("longitude")
            if r_lat is None or r_lon is None:
                continue
            dist = haversine_km(lat, lon, float(r_lat), float(r_lon))
            if dist <= MAX_DIST_KM:
                return place, round(dist, 2), query
        time.sleep(0.2)
    return None, -1, ""


def main():
    if not SERPER_API_KEY:
        print("SERPER_API_KEY not set in .env")
        return

    df = pd.read_csv(RANKINGS_CSV)
    df = df.set_index("dealer_id")

    print(f"Patching {len(RETRY_TARGETS)} dealers...\n")
    print(f"{'ID':<10} {'Dealer':<48} {'Old Rev':>8} -> {'New Rev':>8}  {'Dist':>6}  Conf")
    print("-" * 95)

    for dealer_id, queries in RETRY_TARGETS.items():
        if dealer_id not in df.index:
            print(f"  {dealer_id} not in CSV — skipping")
            continue

        row         = df.loc[dealer_id]
        dealer_name = row["dealer_name"]
        old_reviews = int(row["user_ratings_total"])
        est_year    = int(row["established_year"])

        place, dist_km, query_used = try_queries(dealer_id, queries)

        if place:
            new_reviews = parse_review_count(place)
            rating      = place.get("rating")
            confidence  = confidence_label(dist_km)
            google_name = place.get("title", "")
            place_id    = place.get("placeId", place.get("place_id", ""))

            # Only accept if it's an improvement (found where not_found, or
            # new review count differs meaningfully from old suspicious match)
            is_improvement = (
                row["match_confidence"] == "not_found"
                or (old_reviews in (0, 1, 2) and new_reviews > old_reviews)
                or (old_reviews > 10000 and new_reviews < old_reviews)  # wrong match correction
            )

            if is_improvement:
                df.at[dealer_id, "google_place_id"]    = place_id
                df.at[dealer_id, "google_name"]        = google_name
                df.at[dealer_id, "google_rating"]      = rating
                df.at[dealer_id, "user_ratings_total"] = new_reviews
                df.at[dealer_id, "reviews_per_year"]   = round(new_reviews / max(1, 2026 - est_year), 1)
                df.at[dealer_id, "distance_km"]        = dist_km
                df.at[dealer_id, "match_confidence"]   = confidence
                df.at[dealer_id, "query_used"]         = query_used
                tag = "UPDATED"
            else:
                new_reviews = old_reviews
                tag = "kept old (no improvement)"

            print(f"{dealer_id:<10} {dealer_name:<48} {old_reviews:>8,} -> {new_reviews:>8,}  {dist_km:>5.2f}km  {confidence}  [{tag}]")
        else:
            print(f"{dealer_id:<10} {dealer_name:<48} {old_reviews:>8,} -> {'n/a':>8}  {'---':>6}  not_found  [no match]")

        time.sleep(0.2)

    # Recompute brand ranks and weights after patches
    df_out = df.reset_index()
    df_out["brand_rank"] = (
        df_out.groupby("brand")["user_ratings_total"]
              .rank(method="dense", ascending=False)
              .astype(int)
    )
    df_out["brand_rank_per_year"] = (
        df_out.groupby("brand")["reviews_per_year"]
              .rank(method="dense", ascending=False)
              .astype(int)
    )
    brand_totals = df_out.groupby("brand")["user_ratings_total"].transform("sum")
    df_out["brand_sales_weight"] = (
        df_out["user_ratings_total"] / brand_totals.replace(0, 1)
    ).round(4)

    df_out = df_out.sort_values(["brand", "brand_rank"]).reset_index(drop=True)
    df_out.to_csv(RANKINGS_CSV, index=False)

    print("\n" + "=" * 95)
    print(f"Saved updated rankings -> {RANKINGS_CSV}")

    found    = (df_out["match_confidence"] != "not_found").sum()
    high_cf  = (df_out["match_confidence"] == "high").sum()
    med_cf   = (df_out["match_confidence"] == "medium").sum()
    print(f"Matched: {found}/50  (high: {high_cf}  medium: {med_cf}  low: {found - high_cf - med_cf})")

    still_missing = df_out[df_out["match_confidence"] == "not_found"]["dealer_name"].tolist()
    if still_missing:
        print(f"\nStill not found ({len(still_missing)}) - will receive minimum brand weight in calibration:")
        for d in still_missing:
            print(f"  * {d}")

    print("\nFinal top 15 by review count:")
    top = df_out.nlargest(15, "user_ratings_total")[
        ["dealer_name", "brand", "user_ratings_total", "google_rating", "brand_rank", "match_confidence"]
    ]
    print(top.to_string(index=False))


if __name__ == "__main__":
    main()
