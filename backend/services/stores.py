"""Store Performance: how each rooftop is tracking."""
import pandas as pd

from backend.analytics.benchmarks import gross_series
from backend.db.session import with_session
from backend.repositories import dealers as dealers_repo

# Trailing-12-month units below this share of a store's own annual target is "behind plan".
BEHIND_PLAN_PCT = 90


@with_session
def dealer_leaderboard(session, filters: dict) -> pd.DataFrame:
    return dealers_repo.get_dealer_performance_leaderboard(session, filters)


def estimated_gross(brands: pd.Series) -> pd.Series:
    """Benchmark gross per unit for each brand (a share of the tenant's own average price for it)."""
    return gross_series(brands)


def scorecard(filters: dict) -> dict:
    """Every rooftop's units, revenue, pace against its own target, growth and showroom conversion."""
    df = dealer_leaderboard(filters)
    if df.empty:
        return {"rows": [], "behind_plan_pct": BEHIND_PLAN_PCT}
    df = df.copy()
    df["units_sold"] = df["units_sold"].fillna(0).astype(int)
    df["revenue"] = df["revenue"].fillna(0)
    # An estimate scaled by each store's own volume and brand mix, not booked gross (sales carry no cost basis).
    df["est_gross"] = df["units_sold"] * estimated_gross(df["brand"])
    return {"rows": df, "behind_plan_pct": BEHIND_PLAN_PCT}
