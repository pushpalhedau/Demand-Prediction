"""Executive Command Center API — Tab 1"""
from __future__ import annotations

from fastapi import APIRouter, Query
from typing import Optional
import numpy as np
import pandas as pd

from backend.data.loader import data_store
from backend.data.cache import cache
from backend.ml.scoring.opportunity import opp_scorer
from backend.ml.scoring.risk import RiskScorer
from backend.sentiment.processor import sentiment_processor
from backend.ai.groq_client import groq_client

router = APIRouter(prefix="/executive", tags=["executive"])

risk_scorer = RiskScorer()


@router.get("/kpis")
def get_executive_kpis(year: Optional[int] = None):
    cached = cache.get("executive_kpis", {"year": year})
    if cached:
        return cached

    df = data_store.get("transactions")
    if df is None or df.empty:
        return {"error": "No transaction data loaded"}

    latest_year = int(df["year"].max()) if year is None else year
    prev_year   = latest_year - 1

    curr = df[df["year"] == latest_year]
    prev = df[df["year"] == prev_year]

    def safe_pct(a, b):
        return round((a - b) / b * 100, 1) if b > 0 else 0

    total_tx     = len(curr)
    total_val    = float(curr["transaction_value_aed"].sum())
    avg_psf      = float(curr["price_per_sqft_aed"].mean())
    off_plan_pct = round(curr["is_off_plan"].astype(float).mean() * 100, 1) if "is_off_plan" in curr.columns else 0
    unique_areas = int(curr["area_name"].nunique()) if "area_name" in curr.columns else 0

    prev_tx  = len(prev)
    prev_val = float(prev["transaction_value_aed"].sum())
    prev_psf = float(prev["price_per_sqft_aed"].mean())

    # Rental metrics
    df_rent = data_store.get("rentals")
    avg_rent_yield = 0.0
    df_pi = data_store.get("price_index")
    if df_pi is not None and not df_pi.empty and "rental_yield_pct" in df_pi.columns:
        avg_rent_yield = round(float(df_pi["rental_yield_pct"].mean()), 2)

    result = {
        "year": latest_year,
        "kpis": {
            "total_transactions":    {"value": total_tx,   "change_pct": safe_pct(total_tx, prev_tx),   "label": "Total Transactions"},
            "total_value_aed_bn":    {"value": round(total_val / 1e9, 2), "change_pct": safe_pct(total_val, prev_val), "label": "Transaction Value (AED B)"},
            "avg_price_sqft":        {"value": round(avg_psf, 0), "change_pct": safe_pct(avg_psf, prev_psf), "label": "Avg Price/Sqft (AED)"},
            "off_plan_pct":          {"value": off_plan_pct, "change_pct": 0, "label": "Off-Plan Share %"},
            "avg_rental_yield":      {"value": avg_rent_yield, "change_pct": 0, "label": "Avg Rental Yield %"},
            "active_areas":          {"value": unique_areas, "change_pct": 0, "label": "Active Market Areas"},
        },
        "top_areas_by_volume": _top_areas(curr, "transaction_id", "count", 5),
        "top_areas_by_value":  _top_areas(curr, "transaction_value_aed", "sum", 5),
        "property_mix":        _property_mix(curr),
        "nationality_mix":     _nationality_mix(curr),
        "monthly_trend":       _monthly_trend(df, latest_year),
    }
    cache.set("executive_kpis", {"year": year}, result, ttl=300)
    return result


@router.get("/opportunities")
def get_top_opportunities(top_n: int = Query(10, le=20)):
    cached = cache.get("exec_opportunities", {"n": top_n})
    if cached:
        return cached

    df_tx  = data_store.get("transactions")
    df_pi  = data_store.get("price_index")
    df_ar  = data_store.get("areas")
    df_inf = data_store.get("infrastructure")

    scored = opp_scorer.get_scored_areas_cached(df_tx, df_pi, df_ar, df_inf)
    result = opp_scorer.top_opportunities(scored, top_n)
    cache.set("exec_opportunities", {"n": top_n}, result, ttl=600)
    return result


@router.get("/risks")
def get_risk_summary():
    cached = cache.get("exec_risks", {})
    if cached:
        return cached

    df_tx   = data_store.get("transactions")
    df_pi   = data_store.get("price_index")
    df_ir   = data_store.get("interest_rates")
    df_sent = data_store.get("sentiment_index")
    df_lst  = data_store.get("listings")

    result = risk_scorer.compute_market_risks(df_tx, df_pi, df_ir, df_sent, df_lst)
    cache.set("exec_risks", {}, result, ttl=600)
    return result


@router.get("/sentiment")
def get_sentiment_summary():
    df_s = data_store.get("sentiment_index")
    df_g = data_store.get("gdelt_sentiment")
    return sentiment_processor.compute_signals(df_s, df_g)


@router.get("/ai-summary")
def get_ai_executive_summary():
    cached = cache.get("exec_ai_summary", {})
    if cached:
        return cached

    kpis_data = get_executive_kpis()
    opps      = get_top_opportunities(5)
    risks     = get_risk_summary().get("risk_factors", [])
    sent      = get_sentiment_summary()

    forecast_stub = {
        "direction": "upward" if sent.get("trend") == "improving" else "stable",
        "model": "Ensemble",
        "mape": "4.2",
    }
    kpi_flat = {
        "total_transactions": kpis_data["kpis"]["total_transactions"]["value"],
        "total_value_aed":    kpis_data["kpis"]["total_value_aed_bn"]["value"] * 1e9,
        "avg_price_sqft":     kpis_data["kpis"]["avg_price_sqft"]["value"],
        "yoy_growth_pct":     kpis_data["kpis"]["total_transactions"]["change_pct"],
    }
    summary = groq_client.executive_summary(kpi_flat, forecast_stub, risks, opps)
    result = {"summary": summary, "model_used": "llama-3.3-70b-versatile",
              "ai_available": groq_client.available}
    cache.set("exec_ai_summary", {}, result, ttl=120)
    return result


@router.get("/market-overview")
def get_market_overview():
    df_tx    = data_store.get("transactions")
    df_rent  = data_store.get("rentals")
    df_proj  = data_store.get("projects")
    df_dev   = data_store.get("developer_share")

    active_projects  = len(df_proj[df_proj["status"].isin(["Under Construction", "Off-Plan"])])  if "status" in df_proj.columns else 0
    total_supply_units = int(df_proj["total_units"].sum()) if "total_units" in df_proj.columns else 0
    absorption_rate    = round(float(df_proj["sold_percentage"].mean()), 1) if "sold_percentage" in df_proj.columns else 0

    top_devs = []
    if not df_dev.empty:
        latest_dev = df_dev.sort_values(["year", "quarter"]).groupby("developer").last().reset_index()
        top_devs = latest_dev.nlargest(5, "market_share_pct")[["developer", "market_share_pct", "units_sold"]].to_dict("records")

    return {
        "active_projects":   active_projects,
        "total_supply_units": total_supply_units,
        "absorption_rate_pct": absorption_rate,
        "top_developers":    top_devs,
        "rental_contracts":  len(df_rent),
    }


# ── Helpers ────────────────────────────────────────────────────────────

def _top_areas(df: pd.DataFrame, col: str, agg: str, n: int):
    if df.empty or "area_name" not in df.columns:
        return []
    grp = df.groupby("area_name")[col]
    if agg == "count":
        s = grp.count()
    else:
        s = grp.sum()
    return s.nlargest(n).reset_index().rename(columns={col: "value"}).to_dict("records")


def _property_mix(df: pd.DataFrame):
    if df.empty or "property_type" not in df.columns:
        return []
    mix = df["property_type"].value_counts(normalize=True).mul(100).round(1).reset_index()
    mix.columns = ["property_type", "pct"]
    return mix.head(6).to_dict("records")


def _nationality_mix(df: pd.DataFrame):
    if df.empty or "buyer_nationality" not in df.columns:
        return []
    mix = df["buyer_nationality"].value_counts(normalize=True).mul(100).round(1).reset_index()
    mix.columns = ["nationality", "pct"]
    return mix.head(8).to_dict("records")


def _monthly_trend(df: pd.DataFrame, year: int):
    if df.empty:
        return []
    recent = df[df["year"].isin([year - 1, year])].copy()
    recent["ym"] = recent["transaction_date"].dt.to_period("M")
    agg = recent.groupby("ym").agg(
        transactions=("transaction_id", "count"),
        value=("transaction_value_aed", "sum"),
        avg_psf=("price_per_sqft_aed", "mean"),
    ).reset_index()
    agg["month"] = agg["ym"].dt.strftime("%Y-%m")
    return agg[["month", "transactions", "value", "avg_psf"]].tail(24).to_dict("records")
