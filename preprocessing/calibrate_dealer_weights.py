"""
preprocessing/calibrate_dealer_weights.py

Redistributes dealer_id assignments in realdata-datasets/sales.csv using
real Google Maps review counts as the ranking proxy (from dealer_rankings_google.csv).

What this fixes:
  Before: dealer_id assigned flat-randomly within brand — all dealers get equal share
  After:  dealer_id assigned proportionally to review count — high-traffic dealers
          (e.g. Arabian Automobiles Deira, AGMC Dubai) receive more transactions

Weight strategy:
  - Found dealers:     weight = user_ratings_total / sum(brand total)
  - Not-found dealers: weight = 0.5 * min(found dealer reviews in brand)
                       i.e. they still get transactions but less than any found dealer
  - Brands with no dealers in rankings: left unchanged

Also updates region + city columns to match the newly assigned dealer's location.

Backup: realdata-datasets/sales_pre_calibration.csv (never overwritten if it exists)

Run:
  python preprocessing/calibrate_dealer_weights.py
"""

import os
import sys
import shutil
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

RANKINGS_CSV  = "realdata-datasets/dealer_rankings_google.csv"
SALES_CSV     = "realdata-datasets/sales.csv"
DEALERS_CSV   = "realdata-datasets/dealers.csv"
BACKUP_CSV    = "realdata-datasets/sales_pre_calibration.csv"
SEED          = 42


def compute_final_weights(rankings: pd.DataFrame) -> pd.DataFrame:
    """
    For each dealer, compute a calibrated weight within its brand.
      - Dealers with user_ratings_total > 0 : weight proportional to review count
      - Dealers with 0 / not_found           : 0.5 × minimum found count for that brand
    Returns rankings with a new column 'final_weight' (sums to 1.0 per brand).
    """
    out_rows = []

    for brand, grp in rankings.groupby("brand"):
        grp = grp.copy()
        found_mask  = grp["user_ratings_total"] > 0
        found_count = grp.loc[found_mask, "user_ratings_total"]

        # Minimum proxy for unresolved dealers
        if not found_count.empty:
            min_reviews = found_count.min()
        else:
            # Every dealer in this brand was not found — give equal weight
            min_reviews = 1

        grp["calibrated_reviews"] = grp["user_ratings_total"].copy()
        grp.loc[~found_mask, "calibrated_reviews"] = max(1, int(min_reviews * 0.5))

        total = grp["calibrated_reviews"].sum()
        grp["final_weight"] = (grp["calibrated_reviews"] / total).round(6)

        out_rows.append(grp)

    return pd.concat(out_rows, ignore_index=True)


def reassign_dealers(sales: pd.DataFrame,
                     rankings: pd.DataFrame,
                     dealer_lookup: pd.DataFrame) -> pd.DataFrame:
    """
    For each brand present in rankings, randomly re-assign dealer_id, region,
    and city in the sales DataFrame according to final_weight.
    Brands not covered by rankings are left untouched.
    """
    np.random.seed(SEED)
    result_parts = []

    covered_brands = set(rankings["brand"].unique())

    for brand, grp in sales.groupby("brand", sort=False):
        if brand not in covered_brands:
            result_parts.append(grp)
            continue

        brand_dealers = rankings[rankings["brand"] == brand].copy()
        dealer_ids = brand_dealers["dealer_id"].values
        weights    = brand_dealers["final_weight"].values

        # Safety normalise in case of floating-point drift
        weights = weights / weights.sum()

        n = len(grp)
        chosen_ids = np.random.choice(dealer_ids, size=n, p=weights)

        grp = grp.copy()
        grp["dealer_id"] = chosen_ids

        # Update region + city to match the assigned dealer
        loc = dealer_lookup.loc[chosen_ids, ["region", "city"]].values
        grp["region"] = loc[:, 0]
        grp["city"]   = loc[:, 1]

        result_parts.append(grp)

    return pd.concat(result_parts).sort_index()


def print_distribution_report(before: pd.DataFrame,
                               after: pd.DataFrame,
                               rankings: pd.DataFrame):
    """Print a before/after transaction share per dealer within each brand."""
    print("\nDealer transaction share — before vs after (top brands):\n")

    for brand in sorted(rankings["brand"].unique()):
        b_counts = before[before["brand"] == brand]["dealer_id"].value_counts()
        a_counts = after[after["brand"] == brand]["dealer_id"].value_counts()
        total    = len(before[before["brand"] == brand])
        if total == 0:
            continue

        brand_dealers = rankings[rankings["brand"] == brand].sort_values("brand_rank")
        print(f"  {brand}  ({total:,} transactions)")
        print(f"    {'Dealer':<48} {'Before%':>7}  {'After%':>7}  {'GoogleRev':>9}")
        for _, row in brand_dealers.iterrows():
            did    = row["dealer_id"]
            bpct   = b_counts.get(did, 0) / total * 100
            apct   = a_counts.get(did, 0) / total * 100
            revs   = int(row["user_ratings_total"])
            status = "" if row["match_confidence"] != "not_found" else " [unmatched]"
            print(f"    {row['dealer_name']:<48} {bpct:>6.1f}%  {apct:>6.1f}%  {revs:>9,}{status}")
        print()


def main():
    print("=" * 60)
    print("  Dealer Weight Calibration")
    print("=" * 60)

    # --- Load data ---
    if not os.path.exists(RANKINGS_CSV):
        print(f"ERROR: {RANKINGS_CSV} not found. Run fetch_dealer_rankings.py first.")
        sys.exit(1)

    rankings = pd.read_csv(RANKINGS_CSV)
    sales    = pd.read_csv(SALES_CSV)
    dealers  = pd.read_csv(DEALERS_CSV, index_col="dealer_id")[["region", "city"]]

    print(f"Loaded: {len(sales):,} sales rows  |  {len(rankings)} dealer rankings")

    # --- Backup original ---
    if not os.path.exists(BACKUP_CSV):
        shutil.copy(SALES_CSV, BACKUP_CSV)
        print(f"Backup saved -> {BACKUP_CSV}")
    else:
        print(f"Backup already exists at {BACKUP_CSV} (not overwritten)")

    # --- Compute weights ---
    rankings = compute_final_weights(rankings)

    found    = (rankings["user_ratings_total"] > 0).sum()
    missing  = (rankings["user_ratings_total"] == 0).sum()
    print(f"\nWeights computed: {found} dealers with real data, {missing} assigned minimum proxy")

    # --- Reassign ---
    print(f"\nReassigning dealer_id + region + city (seed={SEED})...")
    sales_before = sales.copy()
    sales_after  = reassign_dealers(sales, rankings, dealers)

    # --- Report ---
    print_distribution_report(sales_before, sales_after, rankings)

    # --- Save ---
    sales_after.to_csv(SALES_CSV, index=False)
    print(f"Saved calibrated sales -> {SALES_CSV}")

    # Quick sanity check
    total       = len(sales_after)
    unique_dlrs = sales_after["dealer_id"].nunique()
    print(f"\nSanity check:")
    print(f"  Total rows     : {total:,} (unchanged)")
    print(f"  Unique dealers : {unique_dlrs} (was {sales_before['dealer_id'].nunique()})")
    print(f"  Brands covered : {sales_after['brand'].nunique()}")
    print(f"\nCalibration complete. Run seed_real_database.py to reload real_demand.db.")


if __name__ == "__main__":
    main()
