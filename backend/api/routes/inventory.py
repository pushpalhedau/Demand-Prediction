"""Project & Inventory Intelligence API — Tab 5"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional
import numpy as np
import pandas as pd

from backend.data.loader import data_store
from backend.data.cache import cache
from backend.ai.groq_client import groq_client
from backend.ml.scoring.opportunity import opp_scorer

router = APIRouter(prefix="/inventory", tags=["inventory"])
log    = logging.getLogger(__name__)


class LaunchRequest(BaseModel):
    area: str
    property_type: str
    total_units: int
    price_per_sqft_aed: float
    area_sqft_per_unit: float = 1000.0
    launch_date_year: int = 2025
    launch_date_month: int = 6
    is_off_plan: bool = True
    amenities_score: int = 7


@router.get("/project-status")
def get_project_status():
    df_proj = data_store.get("projects")
    if df_proj.empty:
        return {"by_status": [], "top_projects": [], "summary": {}}

    by_status = df_proj.groupby("status").agg(
        count=("project_id", "count"),
        total_units=("total_units", "sum"),
        avg_absorption=("sold_percentage", "mean"),
    ).reset_index().round(1).to_dict("records") if "status" in df_proj.columns else []

    top_projects = df_proj.nlargest(15, "total_units")[
        ["project_name", "developer", "area", "status", "total_units", "sold_units",
         "sold_percentage", "avg_price_per_sqft_aed", "completion_year"]
    ].fillna(0).to_dict("records")

    summary = {
        "total_projects":      len(df_proj),
        "active_projects":     int((df_proj["status"].isin(["Under Construction", "Off-Plan"])).sum())
                               if "status" in df_proj.columns else 0,
        "completed_projects":  int((df_proj["status"] == "Completed").sum())
                               if "status" in df_proj.columns else 0,
        "avg_absorption_rate": round(float(df_proj["sold_percentage"].mean()), 1),
        "total_units":         int(df_proj["total_units"].sum()),
        "sold_units":          int(df_proj["sold_units"].sum()),
    }
    return {"by_status": by_status, "top_projects": top_projects, "summary": summary}


@router.get("/absorption-analysis")
def get_absorption_analysis():
    df_proj = data_store.get("projects")
    df_pi   = data_store.get("price_index")

    if df_proj.empty:
        return {"by_developer": [], "by_area": [], "by_type": []}

    by_dev  = df_proj.groupby("developer").agg(
        avg_absorption=("sold_percentage", "mean"),
        total_projects=("project_id", "count"),
        total_units=("total_units", "sum"),
    ).reset_index().nlargest(10, "avg_absorption").round(1).to_dict("records") if "developer" in df_proj.columns else []

    by_area = df_proj.groupby("area").agg(
        avg_absorption=("sold_percentage", "mean"),
        total_units=("total_units", "sum"),
    ).reset_index().nlargest(10, "avg_absorption").round(1).to_dict("records") if "area" in df_proj.columns else []

    by_type = df_proj.groupby("project_type").agg(
        avg_absorption=("sold_percentage", "mean"),
        total_units=("total_units", "sum"),
    ).reset_index().round(1).to_dict("records") if "project_type" in df_proj.columns else []

    return {"by_developer": by_dev, "by_area": by_area, "by_type": by_type}


@router.post("/launch-advisor")
def project_launch_advisor(req: LaunchRequest):
    """Score a proposed project and provide AI-powered recommendations."""
    df_tx  = data_store.get("transactions")
    df_pi  = data_store.get("price_index")
    df_ar  = data_store.get("areas")
    df_inf = data_store.get("infrastructure")

    # Area-level context
    area_tx = df_tx[df_tx["area_name"].str.lower() == req.area.lower()] if not df_tx.empty else df_tx
    area_pi = {}
    if not df_pi.empty and "area" in df_pi.columns:
        pi_rows = df_pi[df_pi["area"].str.lower() == req.area.lower()].sort_values(["year", "quarter"])
        if not pi_rows.empty:
            area_pi = pi_rows.iloc[-1].to_dict()

    # Scoring
    area_tx_count     = len(area_tx)
    avg_psf_area      = float(area_tx["price_per_sqft_aed"].mean()) if not area_tx.empty else 1000
    price_premium_pct = round((req.price_per_sqft_aed - avg_psf_area) / avg_psf_area * 100, 1)
    yoy_growth        = float(area_pi.get("price_yoy_change_pct", 0))
    rental_yield      = float(area_pi.get("rental_yield_pct", 6.0))
    days_to_sell      = float(area_pi.get("avg_days_to_sell", 30))

    # Demand score (0-100)
    demand_score = min(100, area_tx_count / 2000 * 100)

    # Price competitiveness score (penalty if priced too high)
    price_score = max(0, 100 - abs(price_premium_pct) * 2)

    # Market velocity score
    velocity_score = max(0, 100 - days_to_sell / 2)

    # Amenity score
    amenity_score = req.amenities_score * 10

    # Composite success probability
    success_prob = round(
        (demand_score * 0.35 + price_score * 0.30 + velocity_score * 0.20 + amenity_score * 0.15) / 100, 3
    )

    # Revenue projections
    total_value_aed = req.total_units * req.area_sqft_per_unit * req.price_per_sqft_aed
    expected_units_sold_12m = int(req.total_units * success_prob)
    months_to_sellout = round(req.total_units / max(expected_units_sold_12m / 12, 1), 1)

    # Monte Carlo for revenue uncertainty
    rng = np.random.default_rng(42)
    demand_sims = rng.normal(success_prob, 0.1, 2000).clip(0, 1)
    rev_sims    = demand_sims * total_value_aed
    revenue_dist = {
        "p10": round(float(np.percentile(rev_sims, 10)), 0),
        "p50": round(float(np.percentile(rev_sims, 50)), 0),
        "p90": round(float(np.percentile(rev_sims, 90)), 0),
    }

    # Inventory risk
    if months_to_sellout > 36:
        inv_risk = "Critical"
    elif months_to_sellout > 24:
        inv_risk = "High"
    elif months_to_sellout > 12:
        inv_risk = "Medium"
    else:
        inv_risk = "Low"

    # AI narrative
    context = (f"Project: {req.total_units} units in {req.area}, {req.property_type}\n"
               f"Price: AED {req.price_per_sqft_aed:,.0f}/sqft (market avg: AED {avg_psf_area:,.0f}/sqft)\n"
               f"Price premium vs market: {price_premium_pct:+.1f}%\n"
               f"Area YoY price growth: {yoy_growth:.1f}% | Rental yield: {rental_yield:.1f}%\n"
               f"Success probability: {success_prob:.1%} | Months to sell out: {months_to_sellout:.0f}")
    ai_advice = groq_client.launch_recommendation(
        req.area, req.property_type, req.total_units, req.price_per_sqft_aed, context
    )

    return {
        "area":                 req.area,
        "property_type":        req.property_type,
        "total_units":          req.total_units,
        "success_probability":  success_prob,
        "expected_revenue_aed": round(total_value_aed * success_prob, 0),
        "revenue_distribution": revenue_dist,
        "months_to_sellout":    months_to_sellout,
        "inventory_risk":       inv_risk,
        "price_premium_pct":    price_premium_pct,
        "market_avg_psf":       round(avg_psf_area, 0),
        "demand_score":         round(demand_score, 1),
        "price_score":          round(price_score, 1),
        "velocity_score":       round(velocity_score, 1),
        "rental_yield_pct":     rental_yield,
        "area_yoy_growth_pct":  yoy_growth,
        "ai_recommendation":    ai_advice,
    }


@router.get("/sellout-prediction")
def predict_sellout(
    area: str = Query(...),
    units: int = Query(100),
    price_per_sqft: float = Query(1500),
):
    """Predict months to sell out a given inventory."""
    df_tx = data_store.get("transactions")
    area_tx = df_tx[df_tx["area_name"].str.lower() == area.lower()] if not df_tx.empty else df_tx

    # Monthly absorption rate in the area
    if not area_tx.empty:
        monthly_tx = area_tx.groupby(["year", "month"]).size()
        avg_monthly = float(monthly_tx.mean())
    else:
        avg_monthly = 50.0

    market_avg_psf = float(area_tx["price_per_sqft_aed"].mean()) if not area_tx.empty else 1200
    price_sensitivity = 1 - (price_per_sqft - market_avg_psf) / market_avg_psf * 0.3
    adjusted_monthly  = avg_monthly * max(0.1, min(price_sensitivity, 1.5))
    months_to_sellout = round(units / max(adjusted_monthly, 1), 1)

    return {
        "area":             area,
        "units":            units,
        "monthly_absorption": round(adjusted_monthly, 1),
        "months_to_sellout": months_to_sellout,
        "sellout_date_estimate": f"{months_to_sellout:.0f} months from launch",
    }
