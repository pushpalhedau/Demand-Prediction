"""
preprocessing/fix_customer_purchases.py

Recalibrates number_of_past_purchases in customers.csv to reflect
the real UAE automobile replacement cycle.

Real anchor:
  UAE average car replacement cycle is 4–5 years. DubiCars H1 2025 market
  report attributes the strong used-car market volume to 4–5 year trade-in
  patterns. Dataset covers Jan 2019 – May 2026 (7.4 years max tenure).

Problem before fix:
  Values randomly assigned 0–5 with no regard for registration_date.
  A customer registered in 2024 could show 5 past purchases — impossible
  in a 4.5-year cycle over ~2 years of activity.

Logic after fix:
  years_active  = (2026-05-31 − registration_date).days / 365.25
  base          = floor(years_active / 4.5)         → 0 or 1 for all rows
  early_replace = 15% chance if >50% through current cycle
  result        = min(base + early_replace, 2)

Expected output distribution:
  0 purchases : ~65% (registered after 2022, or still in first cycle)
  1 purchase  : ~30% (registered pre-2022 + early-replacers)
  2 purchases :  ~5% (only customers who hit two cycles — registered 2019)

Run:
  python preprocessing/fix_customer_purchases.py
"""

import os
import sys
import shutil
import numpy as np
import pandas as pd
from datetime import date

CUSTOMERS_CSV = "realdata-datasets/customers.csv"
BACKUP_CSV    = "realdata-datasets/customers_pre_purchase_fix.csv"
SEED          = 42
DATASET_END   = date(2026, 5, 31)
REPLACEMENT_CYCLE_YEARS = 4.5


def fix_purchases(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    df = df.copy()

    reg_dates = pd.to_datetime(df["registration_date"]).dt.date
    years_active = reg_dates.apply(lambda d: (DATASET_END - d).days / 365.25)

    # Full replacement cycles completed within tenure
    base = (years_active / REPLACEMENT_CYCLE_YEARS).apply(int)

    # Fractional progress through the current (incomplete) cycle
    fraction = (years_active % REPLACEMENT_CYCLE_YEARS) / REPLACEMENT_CYCLE_YEARS

    # 15% early-replacement probability once past the halfway point of cycle
    early = (fraction > 0.5) & (rng.random(len(df)) < 0.15)

    purchases = (base + early.astype(int)).clip(0, 2)
    df["number_of_past_purchases"] = purchases.values
    return df


def main():
    print("=" * 60)
    print("  Customer Purchase History Calibration")
    print("  Real anchor: UAE auto replacement cycle = 4.5 years")
    print("=" * 60)

    if not os.path.exists(CUSTOMERS_CSV):
        print(f"ERROR: {CUSTOMERS_CSV} not found.")
        sys.exit(1)

    df = pd.read_csv(CUSTOMERS_CSV)
    print(f"Loaded: {len(df):,} customer rows")

    print("\nBefore (number_of_past_purchases distribution):")
    before_counts = df["number_of_past_purchases"].value_counts().sort_index()
    for val, cnt in before_counts.items():
        print(f"  {val} purchases: {cnt:,}  ({cnt/len(df)*100:.1f}%)")

    if not os.path.exists(BACKUP_CSV):
        shutil.copy(CUSTOMERS_CSV, BACKUP_CSV)
        print(f"\nBackup saved -> {BACKUP_CSV}")
    else:
        print(f"\nBackup already exists at {BACKUP_CSV} (not overwritten)")

    rng = np.random.default_rng(SEED)
    df_fixed = fix_purchases(df, rng)

    print("\nAfter (number_of_past_purchases distribution):")
    after_counts = df_fixed["number_of_past_purchases"].value_counts().sort_index()
    for val, cnt in after_counts.items():
        print(f"  {val} purchases: {cnt:,}  ({cnt/len(df_fixed)*100:.1f}%)")

    # Sanity: spot-check early registered customers
    early = df_fixed[pd.to_datetime(df_fixed["registration_date"]).dt.year <= 2019]
    print(f"\nSpot-check (registered <= 2019, n={len(early):,}):")
    early_counts = early["number_of_past_purchases"].value_counts().sort_index()
    for val, cnt in early_counts.items():
        print(f"  {val} purchases: {cnt:,}  ({cnt/len(early)*100:.1f}%)")

    df_fixed.to_csv(CUSTOMERS_CSV, index=False)
    print(f"\nSaved -> {CUSTOMERS_CSV}")
    print("\nRun seed_real_database.py to reload real_demand.db.")


if __name__ == "__main__":
    main()
