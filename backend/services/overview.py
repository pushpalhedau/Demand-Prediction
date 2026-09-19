"""Executive Overview: headline KPIs, trends, breakdowns and the prescriptive plays."""
import pandas as pd

from backend.analytics import decision_engine as engine
from backend.db.session import with_session
from backend.repositories import sales as sales_repo

Play = engine.Play


@with_session
def executive_kpis(session, filters: dict) -> dict:
    return sales_repo.get_executive_kpis(session, filters)


@with_session
def monthly_revenue_trend(session, filters: dict) -> pd.DataFrame:
    return sales_repo.get_monthly_revenue_trend(session, filters)


@with_session
def sales_by_category(session, filters: dict) -> pd.DataFrame:
    return sales_repo.get_sales_by_category(session, filters)


@with_session
def sales_by_fuel_type(session, filters: dict) -> pd.DataFrame:
    return sales_repo.get_sales_by_fuel_type(session, filters)


@with_session
def sales_by_store(session, filters: dict, limit: int = 500) -> pd.DataFrame:
    return sales_repo.get_sales_by_store(session, filters, limit=limit)


@with_session
def year_end_projection(session, filters: dict) -> dict:
    return engine.project_year_end(session, filters)


@with_session
def recommended_plays(session, filters: dict, limit: int = 5) -> list[Play]:
    return engine.generate_plays(session, filters, limit=limit)


@with_session
def gross_per_unit(session) -> float:
    """Benchmark gross per new unit for this tenant (a share of its own average selling price)."""
    return engine.bench_for(session).gross_per_unit


def project_series(series: pd.Series, months_ahead: int = 12) -> pd.Series:
    """Seasonal run-rate projection of a monthly series (pure computation, no data access)."""
    return engine.project_series(series, months_ahead)


def category_accent(category: str) -> str:
    return engine.category_accent(category)
