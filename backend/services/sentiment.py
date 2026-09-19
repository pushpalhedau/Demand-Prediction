"""Market Sentiment: news intake, scoring, the demand read and the cross-module briefing."""
import pandas as pd

from backend.core.cache import tenant_cache
from backend.db.models import Sale
from backend.db.session import session_scope
from backend.sentiment.fetchers.gdelt_fetcher import TIMESPAN_OPTIONS, get_stored_articles
from backend.sentiment.group_briefing import build_briefing_context, generate_group_briefing
from backend.sentiment.signal_processor import (
    compute_live_overall_stats,
    ensure_recent_articles_analyzed,
    run_full_pipeline,
)

__all__ = ["TIMESPAN_OPTIONS", "analyze_pending_articles", "briefing_context", "generate_briefing",
           "group_monthly_runrate", "live_overall_stats", "refresh_news", "stored_articles"]


def refresh_news(timespan: str, max_articles_per_query: int = 50, analyze_limit: int = 200) -> dict:
    return run_full_pipeline(timespan=timespan, max_articles_per_query=max_articles_per_query,
                             analyze_limit=analyze_limit)


def analyze_pending_articles(limit: int = 30):
    return ensure_recent_articles_analyzed(limit=limit)


def live_overall_stats(days_back: int = 30) -> dict:
    return compute_live_overall_stats(days_back=days_back)


def stored_articles(days_back: int = 45, analyzed_only: bool = True, limit: int = 400) -> list:
    return get_stored_articles(days_back=days_back, analyzed_only=analyzed_only, limit=limit)


@tenant_cache(ttl=600)
def briefing_context(filters_key: str, _filters: dict, _stats: dict, _articles: list) -> dict:
    """Building the context sweeps every module's queries (~10s), so it is cached on the filter set."""
    return build_briefing_context(_filters, sentiment_stats=_stats, sentiment_articles=_articles)


def generate_briefing(context: dict) -> str:
    return generate_group_briefing(context)


@tenant_cache(ttl=600)
def group_monthly_runrate() -> float:
    """Average booked units per month over the last 12 months of data."""
    with session_scope() as s:
        rows = s.query(Sale.sale_date, Sale.units_sold).all()
    if not rows:
        return 0.0
    df = pd.DataFrame(rows, columns=["sale_date", "units"])
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    cutoff = df["sale_date"].max() - pd.DateOffset(months=12)
    return float(df[df["sale_date"] >= cutoff]["units"].sum()) / 12.0
