"""Store Performance: how each rooftop is tracking."""
import pandas as pd

from backend.analytics.benchmarks import gross_series
from backend.db.session import with_session
from backend.repositories import dealers as dealers_repo


@with_session
def dealer_leaderboard(session, filters: dict) -> pd.DataFrame:
    return dealers_repo.get_dealer_performance_leaderboard(session, filters)


def estimated_gross(brands: pd.Series) -> pd.Series:
    """Benchmark gross per unit for each brand (a share of the tenant's own average price for it)."""
    return gross_series(brands)
