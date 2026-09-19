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
from backend.services import forecasting

__all__ = ["TIMESPAN_OPTIONS", "analyze_pending_articles", "briefing_context", "forecast_check", "generate_briefing",
           "group_monthly_runrate", "live_overall_stats", "overview", "refresh_news", "stored_articles"]


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


def overview(days_back: int = 30) -> dict:
    """The current signal picture: overall stats, the scored articles behind them, and the group's monthly run-rate."""
    analyze_pending_articles(limit=30)
    stats = live_overall_stats(days_back=days_back)
    articles = stored_articles(days_back=45, analyzed_only=True, limit=400)
    return {"stats": stats, "articles": articles, "monthly_runrate": group_monthly_runrate()}


def _monthly(forecast: pd.DataFrame) -> pd.DataFrame:
    d = forecast.copy()
    d["ds"] = pd.to_datetime(d["ds"])
    d["m"] = d["ds"].dt.to_period("M").dt.to_timestamp()
    g = d.groupby("m").agg(yhat=("yhat", "sum"), actual=("actual", "sum"), n=("yhat", "size"),
                           act_n=("actual", "count")).reset_index()
    g = g[g["n"] >= 20]                      # drop partial edge months so the line does not dip artificially
    g.loc[g["act_n"] < 20, "actual"] = pd.NA
    return g


def forecast_check(filters: dict, *, target: str, horizon_days: int) -> dict:
    """Does adding news signals improve the forecast? The baseline model against a news-aware one, monthly."""
    scope = {"category": filters.get("vehicle_category"), "region": filters.get("region"),
             "fuel_type": filters.get("fuel_type"), "brand": filters.get("brand"), "target": target,
             "horizon_days": horizon_days}
    base, base_error = forecasting.train_forecast(**scope, use_sentiment=False)
    if base_error or not base:
        return {"status": "baseline_failed", "message": str(base_error or "")}
    news, news_error = forecasting.train_forecast(**scope, use_sentiment=True)

    baseline = _monthly(base["forecast"])
    split_raw = pd.to_datetime(base["forecast"]["ds"])[base["forecast"]["actual"].isnull()].min()
    split = pd.to_datetime(split_raw).to_period("M").to_timestamp() if pd.notnull(split_raw) else None
    start = (split - pd.DateOffset(months=12)) if split is not None else baseline["m"].min()
    baseline = baseline[baseline["m"] >= start]
    aware = None
    if news and not news_error:
        aware = _monthly(news["forecast"])
        aware = aware[aware["m"] >= start].set_index("m")["yhat"]
    rows = [{"x": r.m, "actual": r.actual if pd.notna(r.actual) else None, "standard": float(r.yhat),
             "news_aware": float(aware.get(r.m)) if aware is not None and r.m in aware.index else None}
            for r in baseline.itertuples()]
    return {"status": "ok", "target": target, "rows": rows, "forecast_starts": split}
