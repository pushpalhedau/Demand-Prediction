"""
preprocessing/fix_category_distribution.py

Fixes vehicle category distribution in realdata-datasets/sales.csv to match
real UAE market proportions. Run once, then re-seed the database.

Current problem (confirmed by audit):
  SUV            56.2%  →  real market ~43-50%  (too high)
  Sedan          26.6%  →  real market ~28-30%  (slightly low)
  Pickup/Comm    10.1%  →  real market ~13-15%  (too low)
  Hatchback       3.0%  →  real market  ~4-6%   (too low)
  MUV             0.0%  →  real market  ~2-3%   (missing entirely)
  EV              4.1%  →  already calibrated by year (do not change)

Fix approach:
  1. Add missing high-volume models to vehicles.csv:
       - Nissan Sunny: confirmed #2 best-seller in UAE 2024 (16,238 national
         units per Focus2move), missing from catalog entirely
       - Kia Carnival: popular 8-seat family MPV — represents MUV segment
       - Toyota Innova Cross: 8-seat family MUV, confirmed in UAE catalog
       - Hyundai Grand i10: entry-level hatchback sold in UAE
  2. Reassign vehicle_ids within each brand using real-world model popularity
     weights derived from Focus2move UAE data and brand sales reports.
     EV and Hybrid transactions are NOT touched — this preserves the already-
     calibrated EV% by year (2023: 2.2%, 2024: 7.1%, 2025: 8.2% confirmed).
  3. Update model, vehicle_category, fuel_type, base_price_aed from catalog.
  4. Recalculate all revenue columns (discount, VAT, add-ons) because
     base_price changes when the assigned vehicle changes.
  5. Fix known VHC014 typo (Nissan transactions) → VH0014.

Brands NOT touched (no vehicle catalog entries, categories already correct):
  MG (mostly SUV — correct for brand), Jetour (SUV — correct), BYD (EV),
  Geely (SUV/Sedan mix — leave as-is)

Data sources for model weights:
  - Nissan Patrol #1 UAE 2024: 16,399 units (Focus2move)
  - Nissan Sunny #2 UAE 2024: 16,238 units (Focus2move)
  - Toyota Hilux #3 UAE 2024: 14,216 units (Focus2move)
  - Mitsubishi L200: leading commercial pickup, fleet demand confirmed
  - UAE VAT: 5% on vehicle selling price (effective Jan 2018)
"""

import os
import sys
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REALDATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "realdata-datasets")
SALES_PATH    = os.path.join(REALDATA_DIR, "sales.csv")
VEHICLES_PATH = os.path.join(REALDATA_DIR, "vehicles.csv")

SEED     = 42
VAT_RATE = 0.05

# ---------------------------------------------------------------------------
# New vehicles to add to the catalog (all confirmed sold in UAE)
# ---------------------------------------------------------------------------
NEW_VEHICLES = [
    # Nissan Sunny: UAE's #2 best-selling model in 2024 (Focus2move confirmed).
    # 1.5L Petrol, AED 52k base from Nissan UAE brochure.
    {
        "vehicle_id": "VH0061", "brand": "Nissan", "model": "Sunny",
        "variant": "Base", "category": "Sedan", "fuel_type": "Petrol",
        "ex_showroom_price_aed": 52000, "engine_cc": 1498, "mileage_kmpl": 17.5,
        "range_km": None, "seating_capacity": 5, "transmission": "Automatic",
        "body_color_options": 5, "safety_rating_ncap": 4, "launch_year": 2019,
        "is_active": True, "ev_subsidy_eligible": 0, "warranty_years": 3,
    },
    # Kia Carnival: 8-seat family MPV, popular in UAE family segment.
    # 2.2L Petrol, AED 89k base from Kia UAE 2024 price list.
    {
        "vehicle_id": "VH0062", "brand": "Kia", "model": "Carnival",
        "variant": "Base", "category": "MUV", "fuel_type": "Petrol",
        "ex_showroom_price_aed": 89000, "engine_cc": 2151, "mileage_kmpl": 12.5,
        "range_km": None, "seating_capacity": 8, "transmission": "Automatic",
        "body_color_options": 5, "safety_rating_ncap": 5, "launch_year": 2021,
        "is_active": True, "ev_subsidy_eligible": 0, "warranty_years": 5,
    },
    # Toyota Innova Cross: 8-seat family MUV, AED 82k base (Toyota UAE catalog).
    # Launched in UAE 2023, strong family demand in mid-income segment.
    {
        "vehicle_id": "VH0063", "brand": "Toyota", "model": "Innova Cross",
        "variant": "Base", "category": "MUV", "fuel_type": "Petrol",
        "ex_showroom_price_aed": 82000, "engine_cc": 1987, "mileage_kmpl": 13.8,
        "range_km": None, "seating_capacity": 8, "transmission": "Automatic",
        "body_color_options": 4, "safety_rating_ncap": 5, "launch_year": 2023,
        "is_active": True, "ev_subsidy_eligible": 0, "warranty_years": 3,
    },
    # Hyundai Grand i10: entry-level hatchback, AED 48k base (Hyundai UAE).
    # Sold to budget buyers; represents UAE's small hatchback segment.
    {
        "vehicle_id": "VH0064", "brand": "Hyundai", "model": "Grand i10",
        "variant": "Base", "category": "Hatchback", "fuel_type": "Petrol",
        "ex_showroom_price_aed": 48000, "engine_cc": 1197, "mileage_kmpl": 19.0,
        "range_km": None, "seating_capacity": 5, "transmission": "Automatic",
        "body_color_options": 6, "safety_rating_ncap": 4, "launch_year": 2020,
        "is_active": True, "ev_subsidy_eligible": 0, "warranty_years": 3,
    },
]

# ---------------------------------------------------------------------------
# Model popularity weights — Petrol/Diesel pool only
# EV and Hybrid transactions are excluded from reassignment below.
# Weights are normalized automatically (don't need to sum to 1.0).
#
# Sources: Focus2move UAE 2024 top-10 model list; Nissan/Toyota UAE press
# releases; estimated brand model-mix from AutoData Arabia reports.
# ---------------------------------------------------------------------------
PETROL_DIESEL_WEIGHTS: dict[str, dict[str, float]] = {
    # Toyota: Hilux is #3 nationally (14,216/yr), Corolla strong budget sedan.
    # RAV4 is Hybrid — excluded from this pool automatically.
    "Toyota": {
        "VH0001": 0.09,  # Land Cruiser  SUV Petrol
        "VH0002": 0.07,  # Prado         SUV Petrol
        "VH0003": 0.10,  # Fortuner      SUV Diesel  ← strong commercial
        "VH0004": 0.20,  # Hilux         Pickup Diesel  ← ~18.4% of Toyota
        "VH0005": 0.12,  # Camry         Sedan Petrol
        "VH0006": 0.20,  # Corolla       Sedan Petrol  ← top volume sedan
        "VH0008": 0.10,  # Yaris         Hatchback Petrol
        "VH0009": 0.08,  # Prado GX      SUV Diesel
        "VH0063": 0.04,  # Innova Cross  MUV Petrol  ← new
    },
    # Nissan: Patrol and Sunny virtually tied nationally (#1 and #2 in 2024).
    # Navara at 8% reflects real commercial fleet share.
    "Nissan": {
        "VH0010": 0.31,  # Patrol        SUV Petrol  ← #1 UAE 2024
        "VH0011": 0.08,  # X-Trail       SUV Petrol
        "VH0012": 0.08,  # Navara        Pickup Diesel
        "VH0013": 0.05,  # Altima        Sedan Petrol
        "VH0014": 0.04,  # Sentra        Sedan Petrol
        "VH0015": 0.08,  # Kicks         SUV Petrol
        "VH0016": 0.02,  # Pathfinder    SUV Petrol
        "VH0061": 0.34,  # Sunny         Sedan Petrol  ← new, #2 UAE 2024
    },
    # Mitsubishi: L200 has strong UAE commercial fleet demand (oilfield, construction).
    # 45% L200 reflects high pickup-to-SUV ratio for this brand in UAE.
    "Mitsubishi": {
        "VH0017": 0.22,  # Pajero        SUV Petrol
        "VH0018": 0.45,  # L200          Pickup Diesel  ← fleet demand
        "VH0019": 0.18,  # Eclipse Cross SUV Petrol
        "VH0020": 0.15,  # Outlander     SUV Petrol
    },
    # Hyundai: Tucson/Santa Fe split, Elantra high volume, Grand i10 new.
    # IONIQ 5/6 (Electric) excluded from this pool.
    "Hyundai": {
        "VH0021": 0.30,  # Tucson        SUV Petrol
        "VH0022": 0.20,  # Santa Fe      SUV Petrol
        "VH0023": 0.20,  # Sonata        Sedan Petrol
        "VH0024": 0.20,  # Elantra       Sedan Petrol
        "VH0064": 0.10,  # Grand i10     Hatchback Petrol  ← new
    },
    # Kia: Sportage dominates, Cerato strong budget Sedan, Carnival family MUV.
    # EV6 (Electric) excluded from this pool.
    "Kia": {
        "VH0027": 0.33,  # Sportage      SUV Petrol
        "VH0028": 0.19,  # Sorento       SUV Petrol
        "VH0030": 0.30,  # Cerato        Sedan Petrol
        "VH0062": 0.18,  # Carnival      MUV Petrol  ← new
    },
    # Honda: all Petrol transactions are Accord/Civic. CR-V handled via Hybrid pool.
    "Honda": {
        "VH0032": 0.46,  # Accord        Sedan Petrol
        "VH0033": 0.54,  # Civic         Sedan Petrol
    },
    # Ford: F-150 strong (lifestyle + oilfield), Explorer family SUV, Mustang niche.
    "Ford": {
        "VH0034": 0.34,  # F-150         Pickup Petrol
        "VH0035": 0.40,  # Explorer      SUV Petrol
        "VH0036": 0.26,  # Mustang       Sedan Petrol
    },
    # BMW: X-series dominate UAE luxury SUV; 5 Series strong in business segment.
    # iX (Electric) excluded from this pool.
    "BMW": {
        "VH0037": 0.33,  # X5            SUV Petrol
        "VH0038": 0.27,  # X3            SUV Petrol
        "VH0039": 0.40,  # 5 Series      Sedan Petrol
    },
    # Mercedes: C/E-Class strong Sedan share; GLE for SUV. EQS excluded (EV pool).
    "Mercedes-Benz": {
        "VH0041": 0.30,  # GLE           SUV Petrol
        "VH0042": 0.38,  # C-Class       Sedan Petrol
        "VH0043": 0.32,  # E-Class       Sedan Petrol
    },
    # Chevrolet: Tahoe popular (V8 SUV culture), Silverado pickups, Malibu budget.
    "Chevrolet": {
        "VH0045": 0.38,  # Tahoe         SUV Petrol
        "VH0046": 0.33,  # Silverado     Pickup Petrol
        "VH0047": 0.29,  # Malibu        Sedan Petrol
    },
    # Volkswagen: Tiguan/Passat split; ID.4 excluded (EV pool).
    "Volkswagen": {
        "VH0057": 0.46,  # Tiguan        SUV Petrol
        "VH0058": 0.54,  # Passat        Sedan Petrol
    },
    # Jeep/Land Rover Diesel: only non-Hybrid models remain in Petrol/Diesel pool.
    "Jeep": {
        "VH0048": 0.45,  # Wrangler      SUV Petrol
        "VH0049": 0.55,  # Grand Cherokee SUV Petrol
    },
    "Land Rover": {
        "VH0050": 1.00,  # Defender      SUV Diesel (Hybrid = Range Rover Sport)
    },
    "Lexus": {
        "VH0052": 1.00,  # LX            SUV Petrol (RX is Hybrid)
    },
}

# EV pool: Electric fuel_type vehicles only, per brand
EV_WEIGHTS: dict[str, dict[str, float]] = {
    "BMW":           {"VH0040": 1.00},               # iX
    "Mercedes-Benz": {"VH0044": 1.00},               # EQS
    "Hyundai":       {"VH0025": 0.55, "VH0026": 0.45},  # IONIQ 6, IONIQ 5
    "Kia":           {"VH0029": 1.00},               # EV6
    "Tesla":         {"VH0054": 0.45, "VH0055": 0.42, "VH0056": 0.13},
    "Volkswagen":    {"VH0059": 1.00},               # ID.4
    "Polestar":      {"VH0060": 1.00},               # Polestar 2
}

# Hybrid pool: Hybrid fuel_type vehicles only, per brand
HYBRID_WEIGHTS: dict[str, dict[str, float]] = {
    "Toyota":     {"VH0007": 1.00},  # RAV4 Hybrid
    "Honda":      {"VH0031": 1.00},  # CR-V Hybrid
    "Land Rover": {"VH0051": 1.00},  # Range Rover Sport Hybrid
    "Lexus":      {"VH0053": 1.00},  # RX Hybrid
}

# ---------------------------------------------------------------------------
# Revenue recalculation parameters (same as regenerate_revenue.py)
# ---------------------------------------------------------------------------
DISCOUNT_BY_YEAR = {
    2019: (2.0,  6.0),
    2020: (8.0, 15.0),   # COVID spike
    2021: (4.0,  8.0),   # recovery + chip shortage
    2022: (3.0,  6.0),
    2023: (2.0,  5.0),
    2024: (2.0,  4.0),   # strong market
    2025: (2.0,  5.0),
    2026: (2.0,  5.0),   # Apr-May overridden below (Hormuz)
}
WARRANTY_RANGES = {
    "Hatchback":         (1_500,  3_000),
    "Sedan":             (2_000,  5_000),
    "MUV":               (2_000,  5_000),
    "SUV":               (3_500,  8_000),
    "Luxury":            (4_000, 10_000),
    "EV":                (3_500,  8_000),
    "Pickup/Commercial": (2_000,  5_000),
}
DEFAULT_WARRANTY_RANGE = (2_000, 5_000)


def _get_pool(
    brand: str, fuel_type: str, catalog_ids: set
) -> dict[str, float]:
    """Return the weight pool for (brand, fuel_type), filtered to known catalog IDs."""
    if fuel_type == "Electric":
        raw = EV_WEIGHTS.get(brand, {})
    elif fuel_type == "Hybrid":
        raw = HYBRID_WEIGHTS.get(brand, {})
    else:
        raw = PETROL_DIESEL_WEIGHTS.get(brand, {})
    return {k: v for k, v in raw.items() if k in catalog_ids}


def _recalculate_revenue(sales: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Rebuild all revenue columns from base_price_aed (vectorised)."""
    lo = pd.Series(2.0, index=sales.index)
    hi = pd.Series(6.0, index=sales.index)
    for year, (y_lo, y_hi) in DISCOUNT_BY_YEAR.items():
        mask = sales["year"] == year
        lo[mask] = y_lo
        hi[mask] = y_hi

    hormuz = (
        (sales["year"] == 2026)
        & (sales["month"].isin([4, 5]))
        & (~sales["fuel_type"].isin(["Electric", "Hybrid"]))
    )
    lo[hormuz] = 5.0
    hi[hormuz] = 10.0

    sales["discount_pct"] = (lo + rng.random(len(sales)) * (hi - lo)).round(2)
    sales["selling_price_aed"] = (
        sales["base_price_aed"] * (1 - sales["discount_pct"] / 100)
    ).round().astype(int)
    sales["accessories_revenue_aed"] = (
        sales["base_price_aed"] * rng.uniform(0.02, 0.04, len(sales))
    ).round().astype(int)
    sales["insurance_revenue_aed"] = (
        sales["selling_price_aed"] * rng.uniform(0.02, 0.03, len(sales))
    ).round().astype(int)

    attach = rng.random(len(sales)) < 0.50
    warranty_amounts = np.zeros(len(sales), dtype=int)
    for cat, (w_lo, w_hi) in WARRANTY_RANGES.items():
        mask = (sales["vehicle_category"] == cat) & attach
        n = mask.sum()
        if n:
            warranty_amounts[mask.values] = rng.integers(w_lo, w_hi + 1, n)
    unk = (~sales["vehicle_category"].isin(WARRANTY_RANGES)) & attach
    n = unk.sum()
    if n:
        warranty_amounts[unk.values] = rng.integers(
            DEFAULT_WARRANTY_RANGE[0], DEFAULT_WARRANTY_RANGE[1] + 1, n
        )
    sales["extended_warranty_aed"] = warranty_amounts
    sales["vat_amount_aed"] = (sales["selling_price_aed"] * VAT_RATE).round().astype(int)
    sales["total_revenue_excl_vat"] = (
        sales["selling_price_aed"]
        + sales["accessories_revenue_aed"]
        + sales["insurance_revenue_aed"]
        + sales["extended_warranty_aed"]
    ).astype(int)
    sales["total_revenue_incl_vat"] = (
        sales["total_revenue_excl_vat"] + sales["vat_amount_aed"]
    ).astype(int)
    sales["total_revenue_aed"] = sales["total_revenue_incl_vat"]
    return sales


def main():
    rng = np.random.default_rng(SEED)

    # -------------------------------------------------------------------------
    # Step 1: Extend vehicles.csv with new models
    # -------------------------------------------------------------------------
    print("Step 1: Adding new vehicles to vehicles.csv...")
    vehicles = pd.read_csv(VEHICLES_PATH)
    existing_ids = set(vehicles["vehicle_id"])
    new_rows = [v for v in NEW_VEHICLES if v["vehicle_id"] not in existing_ids]
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        for col in vehicles.columns:
            if col not in new_df.columns:
                new_df[col] = None
        new_df = new_df[vehicles.columns]
        vehicles = pd.concat([vehicles, new_df], ignore_index=True)
        vehicles.to_csv(VEHICLES_PATH, index=False)
        for v in new_rows:
            print(f"  + {v['vehicle_id']}  {v['brand']:12} {v['model']:20} {v['category']}")
    else:
        print("  All new vehicles already in catalog — skipping.")

    # Build catalog lookups
    catalog_ids = set(vehicles["vehicle_id"])
    cat_model    = vehicles.set_index("vehicle_id")["model"]
    cat_category = vehicles.set_index("vehicle_id")["category"]
    cat_fuel     = vehicles.set_index("vehicle_id")["fuel_type"]
    cat_price    = vehicles.set_index("vehicle_id")["ex_showroom_price_aed"].astype(int)

    # -------------------------------------------------------------------------
    # Step 2: Load sales and apply known data fixes
    # -------------------------------------------------------------------------
    print("\nStep 2: Loading sales data...")
    sales = pd.read_csv(SALES_PATH)
    print(f"  {len(sales):,} rows")

    typo_mask = sales["vehicle_id"] == "VHC014"
    if typo_mask.sum():
        sales.loc[typo_mask, "vehicle_id"] = "VH0014"
        print(f"  Fixed {typo_mask.sum():,} 'VHC014' -> 'VH0014' typos (Nissan Sentra)")

    before_cat = sales["vehicle_category"].value_counts()

    # -------------------------------------------------------------------------
    # Step 3: Vectorised vehicle_id reassignment by (brand, fuel_type) groups
    # -------------------------------------------------------------------------
    print("\nStep 3: Reassigning vehicle_ids with brand-aware model popularity weights...")
    new_vid = sales["vehicle_id"].copy()

    brands_touched = (
        set(PETROL_DIESEL_WEIGHTS) | set(EV_WEIGHTS) | set(HYBRID_WEIGHTS)
    )

    total_reassigned = 0
    for (brand, fuel_type), grp_idx in sales.groupby(["brand", "fuel_type"]).groups.items():
        if brand not in brands_touched:
            continue
        pool = _get_pool(brand, fuel_type, catalog_ids)
        if not pool:
            continue
        ids     = list(pool.keys())
        weights = np.array(list(pool.values()), dtype=float)
        weights /= weights.sum()
        sampled = rng.choice(ids, size=len(grp_idx), p=weights)
        new_vid.loc[grp_idx] = sampled
        changed = (sampled != sales.loc[grp_idx, "vehicle_id"].values).sum()
        total_reassigned += int(changed)

    print(f"  Transactions with new vehicle assignment: {total_reassigned:,}")

    # Apply new vehicle_id and derived columns (only for rows we handled)
    handled = sales["brand"].isin(brands_touched)
    sales.loc[handled, "vehicle_id"]       = new_vid[handled]
    sales.loc[handled, "model"]            = new_vid[handled].map(cat_model)
    sales.loc[handled, "vehicle_category"] = new_vid[handled].map(cat_category)
    sales.loc[handled, "fuel_type"]        = new_vid[handled].map(cat_fuel)
    sales.loc[handled, "base_price_aed"]   = new_vid[handled].map(cat_price)

    # -------------------------------------------------------------------------
    # Step 4: Recalculate revenue (base_price changed for many rows)
    # -------------------------------------------------------------------------
    print("\nStep 4: Recalculating revenue columns...")
    sales = _recalculate_revenue(sales, rng)

    # -------------------------------------------------------------------------
    # Step 5: Save
    # -------------------------------------------------------------------------
    sales.to_csv(SALES_PATH, index=False)
    print(f"\nSaved: {SALES_PATH}")

    # -------------------------------------------------------------------------
    # Report
    # -------------------------------------------------------------------------
    after_cat = sales["vehicle_category"].value_counts()
    total = len(sales)

    print("\n" + "=" * 72)
    print("  VEHICLE CATEGORY DISTRIBUTION — BEFORE vs AFTER")
    print("=" * 72)
    all_cats = sorted(set(before_cat.index) | set(after_cat.index))
    hdr = f"{'Category':<22} {'Before':>8} {'Before%':>8}  {'After':>8} {'After%':>8}  {'Delta':>8}"
    print(hdr)
    print("-" * 72)
    for cat in all_cats:
        b = before_cat.get(cat, 0)
        a = after_cat.get(cat, 0)
        print(
            f"{cat:<22} {b:>8,} {b/total*100:>7.1f}%"
            f"  {a:>8,} {a/total*100:>7.1f}%  {(a-b)/total*100:>+7.1f}pp"
        )

    print("\nTop 15 models by volume:")
    for model, cnt in sales["model"].value_counts().head(15).items():
        print(f"  {model:<24} {cnt:>7,}  ({cnt/total*100:.1f}%)")

    print("\nBrand share (top 10, should be unchanged):")
    for brand, cnt in sales["brand"].value_counts().head(10).items():
        print(f"  {brand:<20} {cnt:>7,}  ({cnt/total*100:.1f}%)")

    print("\nEV% by year (must be unchanged):")
    for yr in sorted(sales["year"].unique()):
        yr_df = sales[sales["year"] == yr]
        ev_pct = (yr_df["fuel_type"] == "Electric").sum() / len(yr_df) * 100
        print(f"  {yr}:  {ev_pct:.2f}%")

    print("\nRevenue sanity check (sample totals):")
    for yr in sorted(sales["year"].unique()):
        yr_df = sales[sales["year"] == yr]
        total_b = yr_df["total_revenue_incl_vat"].sum() / 1e9
        nat_b   = total_b * 17
        print(f"  {yr}:  sample AED {total_b:.2f}B  |  implied national AED {nat_b:.2f}B")

    print("\nDone. Next step: run  python preprocessing/seed_real_database.py")


if __name__ == "__main__":
    main()
