"""
preprocessing/fix_hybrid_distribution.py

Calibrates Hybrid fuel-type % per year against IEA Global EV Outlook 2025
and Toyota UAE electrified-vehicle sales announcements.

Problem: current dataset has ~7% Hybrid in 2019 falling to ~4.6% in 2024 —
the OPPOSITE of the real adoption curve. Hybrid penetration grows over time
as more models launch and awareness increases.

Year targets and their sources
────────────────────────────────────────────────────────────────────────────
 Year   Target   Primary anchor
 2019    3.5 %   RAV4 Hybrid just launched in UAE; very low initial uptake
 2020    4.0 %   Limited model availability; COVID-suppressed market
 2021    4.5 %   Growing but early-adoption phase
 2022    5.0 %   Toyota / Honda Hybrid push begins
 2023    5.5 %   IEA total electrified UAE ~8%; BEV 2.4% → HEV ~5.5%  ★ confirmed
 2024    6.0 %   Toyota UAE announced ~20% of sales electrified (HEV)   ★ confirmed
                 IEA total electrified UAE ~13%; BEV 7% → HEV ~6%      ★ confirmed
 2025    5.5 %   EV begins taking premium-segment share from Hybrid
 2026    5.0 %   Partial year (Jan–May); EV share accelerating

★ = cross-checkable from IEA Global EV Outlook 2025 / Toyota ME press release

Algorithm
  - For years where current Hybrid% > target: randomly convert excess Hybrid
    transactions to Petrol/Diesel vehicles of the SAME brand:
      Toyota RAV4   → Toyota Petrol/Diesel pool (Corolla / Hilux / Camry …)
      Honda CR-V    → Honda Accord or Civic (Petrol)
      Lexus RX      → Lexus LX (Petrol)
      LR RRS Hybrid → Land Rover Defender (Diesel)
  - For years where current Hybrid% < target: randomly convert eligible
    Petrol/Diesel transactions to the brand's Hybrid vehicle.
  - Revenue is fully recalculated after base_price changes.
"""

import os
import sys
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REALDATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "realdata-datasets")
SALES_PATH    = os.path.join(REALDATA_DIR, "sales.csv")
VEHICLES_PATH = os.path.join(REALDATA_DIR, "vehicles.csv")

SEED     = 123
VAT_RATE = 0.05

# ---------------------------------------------------------------------------
# IEA-anchored year targets  (★ = confirmed external source)
# ---------------------------------------------------------------------------
TARGET_HYBRID_PCT: dict[int, float] = {
    2019: 3.5,
    2020: 4.0,
    2021: 4.5,
    2022: 5.0,
    2023: 5.5,   # ★ IEA total electrified ~8%, BEV 2.4% → HEV ~5.5%
    2024: 6.0,   # ★ Toyota UAE ~20% electrified; IEA total ~13%, BEV 7% → HEV ~6%
    2025: 5.5,
    2026: 5.0,
}

# Hybrid vehicle per brand — the single Hybrid model each brand has in catalog
BRAND_HYBRID_VID: dict[str, str] = {
    "Toyota":     "VH0007",   # RAV4 Hybrid     AED 149,000
    "Honda":      "VH0031",   # CR-V Hybrid     AED 149,000
    "Land Rover": "VH0051",   # RR Sport Hybrid AED 699,000
    "Lexus":      "VH0053",   # RX Hybrid       AED 309,000
}

# When REMOVING Hybrid: replacement Petrol/Diesel vehicle pool per brand
# (same weights used in fix_category_distribution.py)
HYBRID_TO_PETROL: dict[str, list[tuple[str, float]]] = {
    "Toyota": [
        ("VH0001", 0.09), ("VH0002", 0.07), ("VH0003", 0.10),
        ("VH0004", 0.20), ("VH0005", 0.12), ("VH0006", 0.20),
        ("VH0008", 0.10), ("VH0009", 0.08), ("VH0063", 0.04),
    ],
    "Honda":      [("VH0032", 0.46), ("VH0033", 0.54)],
    "Land Rover": [("VH0050", 1.00)],   # Defender (Diesel)
    "Lexus":      [("VH0052", 1.00)],   # LX (Petrol)
}

# When ADDING Hybrid: proportional brand split based on catalog Hybrid fleet
# Toyota 3230 / Honda 1651 / LR 837 / Lexus 703  (total 6421)
HYBRID_BRAND_SHARE: dict[str, float] = {
    "Toyota":     3230 / 6421,
    "Honda":      1651 / 6421,
    "Land Rover":  837 / 6421,
    "Lexus":       703 / 6421,
}

# ---------------------------------------------------------------------------
# Revenue recalculation (identical to fix_category_distribution.py)
# ---------------------------------------------------------------------------
DISCOUNT_BY_YEAR = {
    2019: (2.0,  6.0), 2020: (8.0, 15.0), 2021: (4.0,  8.0),
    2022: (3.0,  6.0), 2023: (2.0,  5.0), 2024: (2.0,  4.0),
    2025: (2.0,  5.0), 2026: (2.0,  5.0),
}
WARRANTY_RANGES = {
    "Hatchback": (1_500, 3_000), "Sedan": (2_000, 5_000), "MUV": (2_000, 5_000),
    "SUV": (3_500, 8_000), "Luxury": (4_000, 10_000),
    "EV": (3_500, 8_000), "Pickup/Commercial": (2_000, 5_000),
}
DEFAULT_WARRANTY = (2_000, 5_000)


def _recalculate_revenue(sales: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    lo = pd.Series(2.0, index=sales.index)
    hi = pd.Series(6.0, index=sales.index)
    for year, (y_lo, y_hi) in DISCOUNT_BY_YEAR.items():
        m = sales["year"] == year
        lo[m] = y_lo
        hi[m] = y_hi
    hormuz = (
        (sales["year"] == 2026) & (sales["month"].isin([4, 5]))
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
    wa = np.zeros(len(sales), dtype=int)
    for cat, (w_lo, w_hi) in WARRANTY_RANGES.items():
        m = (sales["vehicle_category"] == cat) & attach
        n = m.sum()
        if n:
            wa[m.values] = rng.integers(w_lo, w_hi + 1, n)
    unk = (~sales["vehicle_category"].isin(WARRANTY_RANGES)) & attach
    n = unk.sum()
    if n:
        wa[unk.values] = rng.integers(DEFAULT_WARRANTY[0], DEFAULT_WARRANTY[1] + 1, n)
    sales["extended_warranty_aed"] = wa
    sales["vat_amount_aed"]        = (sales["selling_price_aed"] * VAT_RATE).round().astype(int)
    sales["total_revenue_excl_vat"] = (
        sales["selling_price_aed"] + sales["accessories_revenue_aed"]
        + sales["insurance_revenue_aed"] + sales["extended_warranty_aed"]
    ).astype(int)
    sales["total_revenue_incl_vat"] = (
        sales["total_revenue_excl_vat"] + sales["vat_amount_aed"]
    ).astype(int)
    sales["total_revenue_aed"] = sales["total_revenue_incl_vat"]
    return sales


def main():
    rng = np.random.default_rng(SEED)

    # Build vehicle catalog lookup
    vehicles = pd.read_csv(VEHICLES_PATH)
    cat_info = vehicles.set_index("vehicle_id")[
        ["model", "category", "fuel_type", "ex_showroom_price_aed"]
    ].copy()
    cat_info = cat_info.rename(columns={"ex_showroom_price_aed": "base_price_aed"})
    cat_info["base_price_aed"] = cat_info["base_price_aed"].astype(int)

    # Pre-build normalised replacement pools for Hybrid → Petrol
    petrol_pools: dict[str, tuple[list, np.ndarray]] = {}
    for brand, items in HYBRID_TO_PETROL.items():
        ids, wts = zip(*items)
        wts = np.array(wts, dtype=float)
        wts /= wts.sum()
        petrol_pools[brand] = (list(ids), wts)

    print("Loading sales data...")
    sales = pd.read_csv(SALES_PATH)
    print(f"  {len(sales):,} rows")

    # Snapshot before-state for reporting
    before_hybrid_by_year = (
        sales[sales["fuel_type"] == "Hybrid"]
        .groupby("year").size()
        .to_dict()
    )
    before_total_by_year = sales.groupby("year").size().to_dict()

    # Collect all index-level changes as a dict {idx: new_vehicle_id}
    updates: dict[int, str] = {}

    print("\nComputing per-year adjustments...")
    print(f"  {'Year':>4}  {'Current%':>9}  {'Target%':>8}  {'Delta':>8}")
    print("  " + "-" * 36)

    for year in sorted(sales["year"].unique()):
        yr = int(year)
        yr_mask = sales["year"] == yr
        n_total  = yr_mask.sum()
        target_pct = TARGET_HYBRID_PCT.get(yr, 5.0)
        target_n   = round(n_total * target_pct / 100)

        hyb_mask   = yr_mask & (sales["fuel_type"] == "Hybrid")
        current_n  = hyb_mask.sum()
        delta      = target_n - current_n
        current_pct = current_n / n_total * 100

        direction = "-" if delta < 0 else "+"
        print(
            f"  {yr:>4}  {current_pct:>7.2f}%  {target_pct:>6.1f}%  "
            f"{direction}{abs(delta):>5}"
        )

        if delta < 0:
            # REDUCE Hybrid: convert |delta| Hybrid rows → Petrol/Diesel
            n_remove = abs(delta)
            hyb_idx  = sales.index[hyb_mask & ~sales.index.isin(updates)].tolist()
            brand_counts = sales.loc[hyb_idx, "brand"].value_counts()
            removed = 0
            for brand, b_count in brand_counts.items():
                if brand not in petrol_pools:
                    continue
                n_brand = min(
                    round(n_remove * b_count / len(hyb_idx)),
                    b_count,
                    n_remove - removed,
                )
                if n_brand <= 0:
                    continue
                b_hyb_idx = [
                    i for i in sales.index[hyb_mask & (sales["brand"] == brand)]
                    if i not in updates
                ]
                if len(b_hyb_idx) < n_brand:
                    n_brand = len(b_hyb_idx)
                if n_brand <= 0:
                    continue
                chosen  = rng.choice(b_hyb_idx, size=n_brand, replace=False)
                ids, wts = petrol_pools[brand]
                new_vids = rng.choice(ids, size=n_brand, p=wts)
                for i, vid in zip(chosen, new_vids):
                    updates[int(i)] = vid
                removed += n_brand

        elif delta > 0:
            # ADD Hybrid: convert delta Petrol/Diesel rows → Hybrid
            brands = list(HYBRID_BRAND_SHARE.keys())
            bwts   = np.array([HYBRID_BRAND_SHARE[b] for b in brands])
            bwts  /= bwts.sum()
            added = 0
            for brand, bwt in zip(brands, bwts):
                n_brand = min(round(delta * bwt), delta - added)
                if n_brand <= 0:
                    continue
                eligible = [
                    i for i in sales.index[
                        yr_mask
                        & (sales["brand"] == brand)
                        & (sales["fuel_type"].isin(["Petrol", "Diesel"]))
                    ]
                    if i not in updates
                ]
                if len(eligible) < n_brand:
                    n_brand = len(eligible)
                if n_brand <= 0:
                    continue
                chosen = rng.choice(eligible, size=n_brand, replace=False)
                new_vid = BRAND_HYBRID_VID[brand]
                for i in chosen:
                    updates[int(i)] = new_vid
                added += n_brand

    # Apply all changes in one vectorised pass
    if updates:
        update_idx = list(updates.keys())
        new_vid_series = pd.Series(updates, dtype=str)
        sales.loc[update_idx, "vehicle_id"]       = new_vid_series.values
        sales.loc[update_idx, "model"]            = new_vid_series.map(cat_info["model"]).values
        sales.loc[update_idx, "vehicle_category"] = new_vid_series.map(cat_info["category"]).values
        sales.loc[update_idx, "fuel_type"]        = new_vid_series.map(cat_info["fuel_type"]).values
        sales.loc[update_idx, "base_price_aed"]   = new_vid_series.map(cat_info["base_price_aed"]).values

    print(f"\n  Total rows changed: {len(updates):,}")

    print("\nRecalculating revenue columns...")
    sales = _recalculate_revenue(sales, rng)

    sales.to_csv(SALES_PATH, index=False)
    print(f"Saved: {SALES_PATH}")

    # -------------------------------------------------------------------------
    # Final report
    # -------------------------------------------------------------------------
    sources = {
        2019: "est. - RAV4 Hybrid UAE launch, low penetration",
        2020: "est. - limited models + COVID",
        2021: "est. - early adoption",
        2022: "est. - Toyota/Honda push begins",
        2023: "IEA total elect. ~8%, BEV 2.4% => HEV ~5.5%  [confirmed]",
        2024: "Toyota UAE ~20% electrified + IEA total ~13%  [confirmed]",
        2025: "EV taking premium share from Hybrid",
        2026: "partial year Jan-May",
    }

    print("\n" + "=" * 78)
    print("  HYBRID % BY YEAR — CALIBRATION RESULT")
    print("=" * 78)
    print(f"  {'Year':>4}  {'Before':>8}  {'Target':>8}  {'After':>8}  Source")
    print("  " + "-" * 78)

    for yr in sorted(int(y) for y in sales["year"].unique()):
        yr_df   = sales[sales["year"] == yr]
        n_total = len(yr_df)
        hyb_n   = (yr_df["fuel_type"] == "Hybrid").sum()
        after_pct   = hyb_n / n_total * 100
        before_n    = before_hybrid_by_year.get(yr, 0)
        before_total = before_total_by_year.get(yr, 1)
        before_pct  = before_n / before_total * 100
        tgt = TARGET_HYBRID_PCT.get(yr, 5.0)
        src = sources.get(yr, "")
        print(
            f"  {yr:>4}  {before_pct:>6.2f}%  {tgt:>6.1f}%  "
            f"{after_pct:>6.2f}%  {src}"
        )

    print("\nFuel type distribution (all years):")
    total = len(sales)
    for ft, cnt in sales["fuel_type"].value_counts().items():
        print(f"  {ft:<12} {cnt:>7,}  ({cnt/total*100:.2f}%)")

    print("\nEV% by year (must be unchanged):")
    for yr in sorted(int(y) for y in sales["year"].unique()):
        yr_df  = sales[sales["year"] == yr]
        ev_pct = (yr_df["fuel_type"] == "Electric").sum() / len(yr_df) * 100
        print(f"  {yr}: {ev_pct:.2f}%")

    print("\nDone. Run  python preprocessing/seed_real_database.py")


if __name__ == "__main__":
    main()
