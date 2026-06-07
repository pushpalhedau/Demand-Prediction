"""Market & Opportunity Intelligence API — Tab 3"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Query
from typing import Optional
import numpy as np
import pandas as pd

from backend.data.loader import data_store
from backend.data.cache import cache
from backend.ml.scoring.opportunity import opp_scorer
from backend.sentiment.processor import sentiment_processor

router = APIRouter(prefix="/market", tags=["market"])
log    = logging.getLogger(__name__)


@router.get("/opportunities")
def get_opportunities(top_n: int = Query(15, le=30)):
    ckey = {"top_n": top_n}
    cached = cache.get("market_opportunities", ckey)
    if cached:
        return cached

    df_tx  = data_store.get("transactions")
    df_pi  = data_store.get("price_index")
    df_ar  = data_store.get("areas")
    df_inf = data_store.get("infrastructure")

    scored = opp_scorer.get_scored_areas_cached(df_tx, df_pi, df_ar, df_inf)
    top    = opp_scorer.top_opportunities(scored, top_n)
    result = {"opportunities": top, "total_areas_scored": len(scored)}
    cache.set("market_opportunities", ckey, result, ttl=600)
    return result


@router.get("/heatmap")
def get_opportunity_heatmap():
    ckey = {}
    cached = cache.get("market_heatmap", ckey)
    if cached:
        return cached

    df_tx  = data_store.get("transactions")
    df_pi  = data_store.get("price_index")
    df_ar  = data_store.get("areas")
    df_inf = data_store.get("infrastructure")

    scored = opp_scorer.get_scored_areas_cached(df_tx, df_pi, df_ar, df_inf)
    heatmap = scored[["area_name", "opportunity_score", "avg_price_sqft",
                       "transaction_count", "price_yoy_change_pct",
                       "rental_yield_pct", "expected_roi_pct"]].to_dict("records")
    cache.set("market_heatmap", ckey, heatmap, ttl=600)
    return heatmap


@router.get("/competitor-analysis")
def get_competitor_analysis(top_n: int = Query(10)):
    df_dev  = data_store.get("developer_share")
    df_list = data_store.get("listings")

    developer_rankings = []
    if not df_dev.empty:
        latest = df_dev.sort_values(["year", "quarter"]).groupby("developer").last().reset_index()
        top_devs = latest.nlargest(top_n, "market_share_pct")
        developer_rankings = top_devs[["developer", "market_share_pct", "units_sold",
                                        "units_launched", "avg_price_per_sqft"]].to_dict("records")

    platform_breakdown = []
    if not df_list.empty and "platform" in df_list.columns:
        pb = df_list.groupby("platform").agg(
            listings=("listing_id", "count"),
            avg_price=("price_aed", "mean"),
            avg_dom=("days_on_market", "mean"),
        ).reset_index()
        platform_breakdown = pb.to_dict("records")

    area_competition = []
    if not df_list.empty and "area" in df_list.columns:
        ac = df_list.groupby("area").agg(
            active_listings=("listing_id", "count"),
            avg_asking_price=("price_per_sqft", "mean"),
            avg_days_to_sell=("days_on_market", "mean"),
        ).reset_index().nlargest(15, "active_listings")
        area_competition = ac.to_dict("records")

    return {
        "developer_rankings":  developer_rankings,
        "platform_breakdown":  platform_breakdown,
        "area_competition":    area_competition,
    }


@router.get("/infrastructure-impact")
def get_infrastructure_impact():
    df_inf = data_store.get("infrastructure")
    df_ar  = data_store.get("areas")
    df_tx  = data_store.get("transactions")

    if df_inf.empty:
        return {"projects": [], "impact_summary": []}

    active = df_inf[df_inf["status"].isin(["Active", "Under Construction", "Planned"])] if "status" in df_inf.columns else df_inf
    projects = active[["project_name", "project_type", "emirate", "budget_aed_million",
                         "expected_completion_year", "impact_on_real_estate",
                         "latitude", "longitude"]].to_dict("records")

    impact_summary = []
    if "impact_on_real_estate" in df_inf.columns:
        by_impact = df_inf.groupby("impact_on_real_estate").agg(
            count=("project_id", "count"),
            total_budget=("budget_aed_million", "sum"),
        ).reset_index()
        impact_summary = by_impact.to_dict("records")

    return {"projects": projects[:50], "impact_summary": impact_summary}


@router.get("/migration-analysis")
def get_migration_analysis():
    df_pop  = data_store.get("population")
    df_tx   = data_store.get("transactions")

    result = {"population_trend": [], "nationality_demand": [], "expat_share": []}

    if not df_pop.empty:
        result["population_trend"] = df_pop[["year", "total_population", "dubai_population",
                                               "annual_growth_rate_pct", "expats_pct"]].to_dict("records")

    if not df_tx.empty and "buyer_nationality" in df_tx.columns:
        by_nat = df_tx.groupby(["year", "buyer_nationality"]).size().reset_index(name="transactions")
        latest_nat = by_nat[by_nat["year"] == df_tx["year"].max()]
        result["nationality_demand"] = latest_nat.nlargest(10, "transactions").to_dict("records")

    return result


@router.get("/white-space")
def get_white_space_analysis():
    """Areas with high demand but low supply = white space opportunities."""
    df_tx   = data_store.get("transactions")
    df_proj = data_store.get("projects")
    df_list = data_store.get("listings")

    if df_tx.empty:
        return {"white_space_areas": []}

    demand_by_area = df_tx.groupby("area_name").size().reset_index(name="demand_count")

    supply_by_area = pd.DataFrame(columns=["area_name", "supply_count"])
    if not df_list.empty and "area" in df_list.columns:
        supply_by_area = df_list.groupby("area").size().reset_index(name="supply_count")
        supply_by_area = supply_by_area.rename(columns={"area": "area_name"})

    merged = demand_by_area.merge(supply_by_area, on="area_name", how="left").fillna({"supply_count": 1})
    merged["demand_supply_ratio"] = merged["demand_count"] / merged["supply_count"].clip(lower=1)
    merged["white_space_score"]   = (merged["demand_supply_ratio"] / merged["demand_supply_ratio"].max() * 100).round(1)

    top_ws = merged.nlargest(10, "white_space_score")[
        ["area_name", "demand_count", "supply_count", "demand_supply_ratio", "white_space_score"]
    ].to_dict("records")
    return {"white_space_areas": top_ws}


@router.get("/price-trends")
def get_price_trends(area: Optional[str] = Query(None)):
    df_pi = data_store.get("price_index")
    if df_pi.empty:
        return {"trends": []}
    df = df_pi.copy()
    if area:
        df = df[df["area"].str.lower() == area.lower()]
    df["period"] = df["year"].astype(str) + "-Q" + df["quarter"].astype(str)
    return {"trends": df[["period", "area", "avg_sale_price_per_sqft_aed", "price_yoy_change_pct",
                           "rental_yield_pct", "avg_days_to_sell", "transaction_volume"]].to_dict("records")}
