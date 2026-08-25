"""
Signal Processor — orchestrates the full sentiment pipeline.

Execution order:
  1. Fetch fresh articles from GDELT (all NA auto themes)
  2. Deduplicate and persist new articles to news_articles
  3. Identify articles with no SentimentSignal yet
  4. Analyze them via Grok (or mock fallback)
  5. Persist SentimentSignal records
  6. Recompute DailySentimentSummary aggregates
     (one row per date × vehicle_category; used as Prophet regressors)

Entry points:
  run_full_pipeline()  — called from the dashboard's Refresh button
  recompute_daily_summaries() — can be called standalone to refresh aggregates
  get_daily_summaries()       — returns a DataFrame ready for Prophet
  get_overall_sentiment_stats() — KPI dict for the dashboard header cards
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import get_db_session, init_all_tables
from database.models import NewsArticle, SentimentSignal, DailySentimentSummary
from sentiment.fetchers.gdelt_fetcher import (
    fetch_all_themes,
    save_articles_to_db,
    get_stored_articles,
    get_article_stats,
)
from sentiment.analyzers.grok_analyzer import (
    analyze_articles,
    save_signals_to_db,
    get_unanalyzed_articles,
    is_live_mode,
    _analyze_mock,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_full_pipeline(
    timespan: str = "30d",
    max_articles_per_query: int = 50,
    analyze_limit: int = 200,
) -> Dict:
    """
    Run the complete fetch → analyze → summarize pipeline.

    Args:
        timespan:              GDELT lookback window (e.g. "7d", "30d", "90d").
        max_articles_per_query: Articles fetched per GDELT theme query.
        analyze_limit:         Max articles to send to Grok in one pipeline run.

    Returns:
        Status report dict with keys: fetch, analyze, summarize, mode, errors.
    """
    init_all_tables()
    status: Dict = {
        "mode":      "live" if is_live_mode() else "mock",
        "fetch":     {},
        "analyze":   {},
        "summarize": {},
        "errors":    [],
    }

    # ── Step 1: Fetch from GDELT ──────────────────────────────────────────
    logger.info("Pipeline | Step 1: Fetching articles from GDELT (timespan=%s)", timespan)
    try:
        raw_articles = fetch_all_themes(
            timespan=timespan,
            max_records_per_query=max_articles_per_query,
        )
        fetch_result = save_articles_to_db(raw_articles)
        status["fetch"] = {
            "fetched_from_gdelt": len(raw_articles),
            **fetch_result,
        }
        logger.info("Pipeline | fetch done: %s", fetch_result)
    except Exception as e:
        msg = f"GDELT fetch failed: {e}"
        logger.error(msg)
        status["errors"].append(msg)
        status["fetch"] = {"fetched_from_gdelt": 0, "inserted": 0, "skipped": 0, "errors": 1}

    # ── Step 2: Analyze unanalyzed articles ──────────────────────────────
    logger.info("Pipeline | Step 2: Analyzing unanalyzed articles")
    try:
        unanalyzed = get_unanalyzed_articles(limit=analyze_limit)
        if unanalyzed:
            signals = analyze_articles(unanalyzed)
            analyze_result = save_signals_to_db(unanalyzed, signals)
            # is_live_mode() only checks that a key is *set*. If the key is
            # rejected, the analyzer silently falls back to mock scoring while
            # the UI still claims "LIVE". Report what actually happened.
            used_mock = any(sig.get("_mock") for sig in signals)
            status["analyze"] = {
                "articles_found": len(unanalyzed),
                "used_mock_fallback": used_mock,
                **analyze_result,
            }
            if used_mock and is_live_mode():
                status["mode"] = "mock (Grok call failed - check XAI_API_KEY)"
                status["errors"].append(
                    "Grok API rejected the request; sentiment scores are "
                    "keyword-based mock values, not AI analysis."
                )
            logger.info("Pipeline | analyze done: %s", analyze_result)
        else:
            status["analyze"] = {"articles_found": 0, "inserted": 0, "skipped": 0, "errors": 0}
            logger.info("Pipeline | no new articles to analyze")
    except Exception as e:
        msg = f"Analysis failed: {e}"
        logger.error(msg)
        status["errors"].append(msg)
        status["analyze"] = {"articles_found": 0, "inserted": 0, "skipped": 0, "errors": 1}

    # ── Step 3: Recompute daily summaries ─────────────────────────────────
    logger.info("Pipeline | Step 3: Recomputing daily sentiment summaries")
    try:
        summary_result = recompute_daily_summaries()
        status["summarize"] = summary_result
        logger.info("Pipeline | summarize done: %s", summary_result)
    except Exception as e:
        msg = f"Daily summary recompute failed: {e}"
        logger.error(msg)
        status["errors"].append(msg)
        status["summarize"] = {"rows_computed": 0}

    return status


# ─────────────────────────────────────────────────────────────────────────────
# Daily Summary Aggregation
# ─────────────────────────────────────────────────────────────────────────────

def recompute_daily_summaries() -> Dict:
    """
    Rebuild the daily_sentiment_summary table from all analyzed articles.

    Logic:
      - Group signals by (published_date, affected_vehicle_category)
      - Also compute an "All" row per date aggregating across categories
      - Deletes all existing rows and reinserts (fast for this data volume)

    Returns:
        {"rows_computed": N, "categories_covered": [...]}
    """
    # Load all analyzed articles with their signals
    rows = get_stored_articles(days_back=3650, analyzed_only=True)  # 10 years back = "all"
    if not rows:
        logger.info("No analyzed articles — skipping daily summary recompute")
        return {"rows_computed": 0, "categories_covered": []}

    df = pd.DataFrame(rows)

    # Ensure required columns exist and have correct types
    for col in ["sentiment_score", "impact_score", "demand_change_pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["published_date"] = pd.to_datetime(df["published_date"]).dt.date
    df["demand_direction"] = df["demand_direction"].fillna("neutral")
    df["affected_category"] = df["affected_category"].fillna("All")

    summaries: List[Dict] = []

    # Per-category daily rows
    for category in df["affected_category"].unique():
        cat_df = df[df["affected_category"] == category]
        summaries.extend(_compute_daily_stats(cat_df, vehicle_category=category))

    # "All" category — aggregate everything (all categories per date)
    summaries.extend(_compute_daily_stats(df, vehicle_category=None))

    # Persist
    session = get_db_session()
    try:
        session.query(DailySentimentSummary).delete()

        now = datetime.utcnow()
        for row in summaries:
            session.add(DailySentimentSummary(computed_at=now, **row))

        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

    categories_covered = list({s["vehicle_category"] for s in summaries if s["vehicle_category"]})
    logger.info("Daily summaries recomputed: %d rows across %d categories", len(summaries), len(categories_covered))
    return {
        "rows_computed": len(summaries),
        "categories_covered": sorted(categories_covered),
    }


def _compute_daily_stats(df: pd.DataFrame, vehicle_category: Optional[str]) -> List[Dict]:
    """
    For each unique published_date in df, compute one summary row.
    vehicle_category=None → "All" aggregate row.
    """
    if df.empty:
        return []

    summaries = []
    for day, group in df.groupby("published_date"):
        n = len(group)
        pos = int((group["sentiment_score"] > 0.15).sum())
        neg = int((group["sentiment_score"] < -0.15).sum())
        neu = n - pos - neg

        avg_sentiment   = _safe_mean(group["sentiment_score"])
        avg_impact      = _safe_mean(group["impact_score"])
        avg_demand_chg  = _safe_mean(group["demand_change_pct"])

        # Geopolitical risk: impact weighted by share of negative signals
        neg_ratio = neg / n if n > 0 else 0.0
        geo_risk  = round((avg_impact or 0.0) * neg_ratio, 4)

        # Dominant demand direction by plurality vote
        dir_counts = group["demand_direction"].value_counts()
        dominant = dir_counts.index[0] if not dir_counts.empty else "neutral"

        summaries.append({
            "summary_date":             day,
            "vehicle_category":         vehicle_category,
            "avg_sentiment_score":      round(avg_sentiment, 4) if avg_sentiment is not None else None,
            "avg_impact_score":         round(avg_impact, 4)    if avg_impact    is not None else None,
            "avg_demand_change_pct":    round(avg_demand_chg, 4) if avg_demand_chg is not None else None,
            "geopolitical_risk_score":  geo_risk,
            "positive_signals":         pos,
            "negative_signals":         neg,
            "neutral_signals":          neu,
            "total_articles":           n,
            "dominant_demand_direction": dominant,
        })

    return summaries


def _safe_mean(series: pd.Series) -> Optional[float]:
    """Return float mean of a numeric series ignoring NaN, or None if all NaN."""
    valid = series.dropna()
    return float(valid.mean()) if not valid.empty else None


# ─────────────────────────────────────────────────────────────────────────────
# Read helpers for dashboard & Prophet
# ─────────────────────────────────────────────────────────────────────────────

def get_daily_summaries(
    days_back: int = 365,
    vehicle_category: Optional[str] = None,
) -> pd.DataFrame:
    """
    Return a DataFrame of DailySentimentSummary rows for use as Prophet regressors.

    Columns: summary_date, avg_sentiment_score, avg_impact_score,
             avg_demand_change_pct, geopolitical_risk_score,
             dominant_demand_direction, total_articles

    Args:
        days_back:        How many days back to include.
        vehicle_category: Filter to a specific category; None = "All" aggregate rows.
    """
    session = get_db_session()
    try:
        cutoff = date.today() - timedelta(days=days_back)
        q = session.query(DailySentimentSummary).filter(
            DailySentimentSummary.summary_date >= cutoff
        )
        if vehicle_category is not None:
            q = q.filter(DailySentimentSummary.vehicle_category == vehicle_category)
        else:
            q = q.filter(DailySentimentSummary.vehicle_category.is_(None))

        rows = q.order_by(DailySentimentSummary.summary_date).all()

        if not rows:
            return pd.DataFrame()

        records = [
            {
                "summary_date":             r.summary_date,
                "avg_sentiment_score":      r.avg_sentiment_score,
                "avg_impact_score":         r.avg_impact_score,
                "avg_demand_change_pct":    r.avg_demand_change_pct,
                "geopolitical_risk_score":  r.geopolitical_risk_score,
                "dominant_demand_direction": r.dominant_demand_direction,
                "total_articles":           r.total_articles,
                "positive_signals":         r.positive_signals,
                "negative_signals":         r.negative_signals,
            }
            for r in rows
        ]
        df = pd.DataFrame(records)
        df["summary_date"] = pd.to_datetime(df["summary_date"])
        return df
    finally:
        session.close()


def ensure_recent_articles_analyzed(limit: int = 30) -> Dict:
    """
    Best-effort: analyze whatever's currently unanalyzed in the cached-article
    pool (the same one the "Recent News" tab reads), up to `limit` articles.

    Without this, compute_live_overall_stats()/compute_live_daily_df() would
    only ever reflect old articles that happen to already have a
    SentimentSignal — freshly fetched news sits with a sentiment_score of
    None until something analyzes it. This lets the Geopolitical Risk KPIs
    pick up fresh cached news directly, without depending on run_full_pipeline()
    (and its live GDELT fetch step, which can be rate-limited) ever completing.

    Always uses fast keyword-based mock scoring, regardless of whether live
    Grok mode is configured — this runs automatically just from opening a
    tab, so it deliberately never makes a real (slow, billed) Grok API call.
    Explicit "Refresh Data" clicks still go through analyze_articles() and
    use real Grok analysis when XAI_API_KEY is set.

    Never raises — any failure is swallowed and reported in the returned
    dict so callers can proceed with whatever was already analyzed.
    """
    try:
        unanalyzed = get_unanalyzed_articles(limit=limit)
        if not unanalyzed:
            return {"analyzed": 0}
        signals = _analyze_mock(unanalyzed)
        result = save_signals_to_db(unanalyzed, signals)
        return {"analyzed": result.get("inserted", 0)}
    except Exception as e:
        logger.warning("ensure_recent_articles_analyzed failed, continuing with what's already analyzed: %s", e)
        return {"analyzed": 0, "error": str(e)}


def compute_live_daily_df(days_back: int = 90, vehicle_category: Optional[str] = None) -> pd.DataFrame:
    """
    Build daily aggregate rows directly from currently cached, analyzed
    articles — the same pool the "Recent News" tab reads via
    get_stored_articles() — instead of the persisted DailySentimentSummary
    table. This decouples the Geopolitical Risk charts from needing a full
    fetch -> analyze -> summarize pipeline run to have completed; it just
    reflects whatever's already analyzed in the DB right now.

    Returns a DataFrame shaped like get_daily_summaries()'s output.
    """
    rows = get_stored_articles(days_back=days_back, analyzed_only=True, limit=2000)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    for col in ["sentiment_score", "impact_score", "demand_change_pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["published_date"] = pd.to_datetime(df["published_date"]).dt.date
    df["demand_direction"] = df["demand_direction"].fillna("neutral")
    df["affected_category"] = df["affected_category"].fillna("All")

    if vehicle_category is not None:
        df = df[df["affected_category"] == vehicle_category]

    summaries = _compute_daily_stats(df, vehicle_category=vehicle_category)
    if not summaries:
        return pd.DataFrame()

    out = pd.DataFrame(summaries)
    out["summary_date"] = pd.to_datetime(out["summary_date"])
    return out


def compute_live_category_summary(days_back: int = 90) -> pd.DataFrame:
    """
    Per-(category, day) sentiment averages computed directly from currently
    cached, analyzed articles — the same pool as the "Recent News" tab —
    instead of the persisted DailySentimentSummary table. Used by the
    Economic Signals and AI Insights category breakdowns/heatmap.

    Returns a DataFrame shaped like get_category_sentiment_summary()'s output:
    columns category, date, sentiment, impact, demand_change, geo_risk,
    total_articles, positive, negative.
    """
    rows = get_stored_articles(days_back=days_back, analyzed_only=True, limit=2000)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    for col in ["sentiment_score", "impact_score", "demand_change_pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["published_date"] = pd.to_datetime(df["published_date"]).dt.date
    df["demand_direction"] = df["demand_direction"].fillna("neutral")
    df["affected_category"] = df["affected_category"].fillna("All")

    records: List[Dict] = []
    for category in df["affected_category"].unique():
        cat_df = df[df["affected_category"] == category]
        for row in _compute_daily_stats(cat_df, vehicle_category=category):
            records.append({
                "category":       category,
                "date":           row["summary_date"],
                "sentiment":      row["avg_sentiment_score"] or 0.0,
                "impact":         row["avg_impact_score"] or 0.0,
                "demand_change":  row["avg_demand_change_pct"] or 0.0,
                "geo_risk":       row["geopolitical_risk_score"] or 0.0,
                "total_articles": row["total_articles"] or 0,
                "positive":       row["positive_signals"] or 0,
                "negative":       row["negative_signals"] or 0,
            })

    return pd.DataFrame(records)


def compute_live_overall_stats(days_back: int = 30) -> Dict:
    """
    KPI-card stats computed directly from currently cached, analyzed articles
    (the same pool as the "Recent News" tab), instead of the persisted
    DailySentimentSummary table. Always reflects what's in the DB right now —
    no dependency on run_full_pipeline()'s summarize step having completed.

    Returns the same shape as get_overall_sentiment_stats().
    """
    rows = get_stored_articles(days_back=days_back, analyzed_only=True, limit=2000)
    if not rows:
        return _empty_stats()

    df = pd.DataFrame(rows)
    df["sentiment_score"] = pd.to_numeric(df["sentiment_score"], errors="coerce")
    df["impact_score"] = pd.to_numeric(df["impact_score"], errors="coerce")
    df["demand_change_pct"] = pd.to_numeric(df.get("demand_change_pct"), errors="coerce")
    df["demand_direction"] = df["demand_direction"].fillna("neutral")
    df["published_date"] = pd.to_datetime(df["published_date"])

    total_articles = len(df)
    total_pos = int((df["sentiment_score"] > 0.15).sum())
    total_neg = int((df["sentiment_score"] < -0.15).sum())

    cutoff_7 = pd.Timestamp(date.today() - timedelta(days=7))
    last_7 = df[df["published_date"] >= cutoff_7]["sentiment_score"].mean()
    prior  = df[df["published_date"] <  cutoff_7]["sentiment_score"].mean()
    trend_7d = round(float(last_7 - prior), 4) if pd.notna(last_7) and pd.notna(prior) else 0.0

    dir_counts = df["demand_direction"].value_counts()
    dominant_dir = dir_counts.index[0] if not dir_counts.empty else "neutral"

    avg_impact = _safe_mean(df["impact_score"]) or 0.0
    neg_ratio = total_neg / total_articles if total_articles else 0.0

    return {
        "avg_sentiment":     round(_safe_mean(df["sentiment_score"]) or 0.0, 3),
        "avg_impact":        round(avg_impact, 3),
        "avg_demand_change": round(_safe_mean(df["demand_change_pct"]) or 0.0, 3),
        "geopolitical_risk": round(avg_impact * neg_ratio, 3),
        "total_articles":    total_articles,
        "positive_pct":      round(total_pos / total_articles * 100, 1) if total_articles else 0.0,
        "negative_pct":      round(total_neg / total_articles * 100, 1) if total_articles else 0.0,
        "dominant_direction": dominant_dir,
        "trend_7d":          trend_7d,
        "last_updated":      df["published_date"].max(),
        "mode":              "live" if is_live_mode() else "mock",
    }


def get_overall_sentiment_stats() -> Dict:
    """
    Aggregate stats across all DailySentimentSummary rows (vehicle_category=None).
    Used for the dashboard KPI header cards.

    Returns dict with:
        avg_sentiment, avg_impact, avg_demand_change, geopolitical_risk,
        total_articles, positive_pct, negative_pct, last_updated,
        dominant_direction, trend_7d  (change in avg_sentiment over last 7 days)
    """
    session = get_db_session()
    try:
        # Pull "All" rows from last 30 days
        cutoff_30 = date.today() - timedelta(days=30)
        cutoff_7  = date.today() - timedelta(days=7)

        rows_30 = (
            session.query(DailySentimentSummary)
            .filter(
                DailySentimentSummary.vehicle_category.is_(None),
                DailySentimentSummary.summary_date >= cutoff_30,
            )
            .order_by(DailySentimentSummary.summary_date)
            .all()
        )

        if not rows_30:
            return _empty_stats()

        df = pd.DataFrame([{
            "date":            r.summary_date,
            "sentiment":       r.avg_sentiment_score or 0.0,
            "impact":          r.avg_impact_score or 0.0,
            "demand_change":   r.avg_demand_change_pct or 0.0,
            "geo_risk":        r.geopolitical_risk_score or 0.0,
            "positive":        r.positive_signals or 0,
            "negative":        r.negative_signals or 0,
            "total":           r.total_articles or 0,
            "direction":       r.dominant_demand_direction or "neutral",
            "computed_at":     r.computed_at,
        } for r in rows_30])

        total_articles = int(df["total"].sum())
        total_pos = int(df["positive"].sum())
        total_neg = int(df["negative"].sum())

        # Trend: avg_sentiment last 7 days vs 8–30 days ago
        df["date"] = pd.to_datetime(df["date"])
        last_7   = df[df["date"] >= pd.Timestamp(cutoff_7)]["sentiment"].mean()
        prior    = df[df["date"] <  pd.Timestamp(cutoff_7)]["sentiment"].mean()
        trend_7d = round(float(last_7 - prior), 4) if pd.notna(last_7) and pd.notna(prior) else 0.0

        # Dominant direction (plurality across all days)
        dir_counts = df["direction"].value_counts()
        dominant_dir = dir_counts.index[0] if not dir_counts.empty else "neutral"

        last_updated = df["computed_at"].max()

        return {
            "avg_sentiment":    round(float(df["sentiment"].mean()), 3),
            "avg_impact":       round(float(df["impact"].mean()), 3),
            "avg_demand_change": round(float(df["demand_change"].mean()), 3),
            "geopolitical_risk": round(float(df["geo_risk"].mean()), 3),
            "total_articles":   total_articles,
            "positive_pct":     round(total_pos / total_articles * 100, 1) if total_articles else 0.0,
            "negative_pct":     round(total_neg / total_articles * 100, 1) if total_articles else 0.0,
            "dominant_direction": dominant_dir,
            "trend_7d":         trend_7d,
            "last_updated":     last_updated,
            "mode":             "live" if is_live_mode() else "mock",
        }
    finally:
        session.close()


def get_category_sentiment_summary(days_back: int = 30) -> pd.DataFrame:
    """
    Return average sentiment per vehicle_category over the past N days.
    Used for category comparison charts on the dashboard.
    """
    session = get_db_session()
    try:
        cutoff = date.today() - timedelta(days=days_back)
        rows = (
            session.query(DailySentimentSummary)
            .filter(
                DailySentimentSummary.vehicle_category.isnot(None),
                DailySentimentSummary.summary_date >= cutoff,
            )
            .all()
        )
        if not rows:
            return pd.DataFrame()

        records = [{
            "category":         r.vehicle_category,
            "date":             r.summary_date,
            "sentiment":        r.avg_sentiment_score or 0.0,
            "impact":           r.avg_impact_score or 0.0,
            "demand_change":    r.avg_demand_change_pct or 0.0,
            "geo_risk":         r.geopolitical_risk_score or 0.0,
            "total_articles":   r.total_articles or 0,
            "positive":         r.positive_signals or 0,
            "negative":         r.negative_signals or 0,
        } for r in rows]

        return pd.DataFrame(records)
    finally:
        session.close()


def _empty_stats() -> Dict:
    return {
        "avg_sentiment": 0.0, "avg_impact": 0.0, "avg_demand_change": 0.0,
        "geopolitical_risk": 0.0, "total_articles": 0, "positive_pct": 0.0,
        "negative_pct": 0.0, "dominant_direction": "neutral",
        "trend_7d": 0.0, "last_updated": None, "mode": "mock",
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI smoke-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    print("=" * 60)
    print("SIGNAL PROCESSOR SMOKE TEST")
    print("=" * 60)

    # Run full pipeline using already-stored test data (no GDELT call needed)
    # by passing 0 articles to the GDELT step via a tiny timespan
    print("\n[1] Recomputing daily summaries from existing DB data...")
    summary_result = recompute_daily_summaries()
    print(f"    Result: {summary_result}")

    print("\n[2] Overall sentiment stats (last 30 days)...")
    stats = get_overall_sentiment_stats()
    for k, v in stats.items():
        print(f"    {k}: {v}")

    print("\n[3] Daily summaries DataFrame (All categories)...")
    df = get_daily_summaries(days_back=400, vehicle_category=None)
    if df.empty:
        print("    No summary data found.")
    else:
        print(df.to_string(index=False))

    print("\n[4] Per-category sentiment summary...")
    cat_df = get_category_sentiment_summary(days_back=400)
    if cat_df.empty:
        print("    No per-category data found.")
    else:
        agg = cat_df.groupby("category")[["sentiment", "impact", "demand_change"]].mean().round(3)
        print(agg.to_string())

    print("\nDone.")
