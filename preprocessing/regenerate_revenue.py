"""
preprocessing/regenerate_revenue.py

Rebuilds all revenue columns in realdata-datasets/sales.csv using real vehicle
prices as anchors and UAE-calibrated formulas. Run once, then re-seed the DB.

Formula per transaction:
  base_price_aed        → from vehicles.csv (DubiCars real prices)
  discount_pct          → year-calibrated ranges (COVID/Hormuz events embedded)
  selling_price_aed     → base × (1 - discount/100)
  accessories_revenue   → 2-4% of base price (floor mats, PPF, tints)
  insurance_revenue     → 2-3% of selling price (first-year bundled UAE insurance)
  extended_warranty     → 50% attach rate, category-based AED range
  vat_amount_aed        → 5% of selling price (UAE VAT, effective Jan 2018)
  total_revenue_excl_vat → selling + accessories + insurance + warranty
  total_revenue_incl_vat → excl_vat + vat_amount
"""

import os
import sys
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REALDATA_DIR = os.path.join(os.path.dirname(__file__), "..", "realdata-datasets")
SALES_PATH    = os.path.join(REALDATA_DIR, "sales.csv")
VEHICLES_PATH = os.path.join(REALDATA_DIR, "vehicles.csv")

SEED = 42
VAT_RATE = 0.05

# Discount % (lo, hi) calibrated to real UAE market events
DISCOUNT_BY_YEAR = {
    2019: (2.0,  6.0),
    2020: (8.0, 15.0),   # COVID — DATA_DICTIONARY confirms 14-20% spikes
    2021: (4.0,  8.0),   # Recovery + semiconductor shortage
    2022: (3.0,  6.0),
    2023: (2.0,  5.0),
    2024: (2.0,  4.0),   # Booming market
    2025: (2.0,  5.0),
    2026: (2.0,  5.0),   # Default; Apr-May overridden below (Hormuz)
}

# Extended warranty AED amounts by vehicle category (50% attach rate)
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


def main():
    rng = np.random.default_rng(SEED)

    print("Loading sales and vehicle data...")
    sales    = pd.read_csv(SALES_PATH)
    vehicles = pd.read_csv(VEHICLES_PATH)[["vehicle_id", "ex_showroom_price_aed", "category"]]

    original_rows = len(sales)
    print(f"  {original_rows:,} sale rows | {len(vehicles):,} vehicle catalog rows")

    # --- Anchor base_price_aed to real vehicle catalog prices ---
    sales = sales.merge(
        vehicles.rename(columns={
            "ex_showroom_price_aed": "_real_base",
            "category":              "_veh_cat",
        }),
        on="vehicle_id",
        how="left",
    )
    sales["base_price_aed"] = sales["_real_base"].fillna(sales["base_price_aed"]).astype(int)
    sales["_veh_cat"] = sales["_veh_cat"].fillna(sales["vehicle_category"])
    assert len(sales) == original_rows, "Merge changed row count — check vehicle_id FK integrity"

    # --- Discount: vectorised year-calibrated ranges ---
    lo = pd.Series(2.0, index=sales.index)
    hi = pd.Series(6.0, index=sales.index)
    for year, (y_lo, y_hi) in DISCOUNT_BY_YEAR.items():
        mask = sales["year"] == year
        lo[mask] = y_lo
        hi[mask] = y_hi

    # Hormuz crisis Apr-May 2026 → higher ICE discounts due to oversupply
    hormuz = (
        (sales["year"] == 2026)
        & (sales["month"].isin([4, 5]))
        & (~sales["fuel_type"].isin(["Electric", "Hybrid"]))
    )
    lo[hormuz] = 5.0
    hi[hormuz] = 10.0

    sales["discount_pct"] = (lo + rng.random(len(sales)) * (hi - lo)).round(2)

    # --- Selling price ---
    sales["selling_price_aed"] = (
        sales["base_price_aed"] * (1 - sales["discount_pct"] / 100)
    ).round().astype(int)

    # --- Accessories (2-4% of base price) ---
    sales["accessories_revenue_aed"] = (
        sales["base_price_aed"] * rng.uniform(0.02, 0.04, len(sales))
    ).round().astype(int)

    # --- Insurance (2-3% of selling price) ---
    sales["insurance_revenue_aed"] = (
        sales["selling_price_aed"] * rng.uniform(0.02, 0.03, len(sales))
    ).round().astype(int)

    # --- Extended warranty (50% attach, category-based AED amount) ---
    attach = rng.random(len(sales)) < 0.50
    warranty_amounts = np.zeros(len(sales), dtype=int)
    for cat, (w_lo, w_hi) in WARRANTY_RANGES.items():
        mask = (sales["_veh_cat"] == cat) & attach
        n = mask.sum()
        if n:
            warranty_amounts[mask.values] = rng.integers(w_lo, w_hi + 1, n)
    # Fallback for unrecognised categories
    unknown_mask = (~sales["_veh_cat"].isin(WARRANTY_RANGES)) & attach
    n = unknown_mask.sum()
    if n:
        warranty_amounts[unknown_mask.values] = rng.integers(
            DEFAULT_WARRANTY_RANGE[0], DEFAULT_WARRANTY_RANGE[1] + 1, n
        )
    sales["extended_warranty_aed"] = warranty_amounts

    # --- VAT: 5% on vehicle selling price ---
    sales["vat_amount_aed"] = (sales["selling_price_aed"] * VAT_RATE).round().astype(int)

    # --- Revenue totals ---
    sales["total_revenue_excl_vat"] = (
        sales["selling_price_aed"]
        + sales["accessories_revenue_aed"]
        + sales["insurance_revenue_aed"]
        + sales["extended_warranty_aed"]
    ).astype(int)
    sales["total_revenue_incl_vat"] = (
        sales["total_revenue_excl_vat"] + sales["vat_amount_aed"]
    ).astype(int)
    # Keep total_revenue_aed as incl-VAT for backward compatibility
    sales["total_revenue_aed"] = sales["total_revenue_incl_vat"]

    # Drop merge helper columns
    sales = sales.drop(columns=["_real_base", "_veh_cat"], errors="ignore")

    # --- Save ---
    sales.to_csv(SALES_PATH, index=False)
    print(f"\nSaved: {SALES_PATH}")

    # --- Calibration report ---
    print("\n=== Calibration Report (sample data; ×17 = implied national) ===")
    header = (
        f"{'Year':<8} {'Rows':>8} {'Avg Base':>12} {'Avg Sell':>12} "
        f"{'Avg Disc%':>10} {'Avg VAT':>10} "
        f"{'Sample Total (AED B)':>21} {'Nat. Implied (AED B)':>21}"
    )
    print(header)
    print("-" * len(header))
    for year in sorted(sales["year"].unique()):
        y = sales[sales["year"] == year]
        print(
            f"{year:<8} {len(y):>8,} "
            f"{y['base_price_aed'].mean():>12,.0f} "
            f"{y['selling_price_aed'].mean():>12,.0f} "
            f"{y['discount_pct'].mean():>10.2f} "
            f"{y['vat_amount_aed'].mean():>10,.0f} "
            f"{y['total_revenue_incl_vat'].sum()/1e9:>21.3f} "
            f"{y['total_revenue_incl_vat'].sum()*17/1e9:>21.3f}"
        )
    total_b = sales["total_revenue_incl_vat"].sum() / 1e9
    print(f"\nAll-years sample total: AED {total_b:.2f}B  |  Implied national: AED {total_b*17:.2f}B")


if __name__ == "__main__":
    main()
