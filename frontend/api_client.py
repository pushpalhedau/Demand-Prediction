"""
HTTP client for Streamlit → FastAPI communication.
All calls are synchronous (Streamlit is single-threaded).
Implements retry, timeout, and graceful error handling.
Results are cached with st.cache_data to avoid redundant requests on every rerun.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import requests
import streamlit as st

log = logging.getLogger(__name__)

BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_BASE = f"{BASE_URL}/api/v1"
TIMEOUT  = 30  # reduced from 60s — fail fast rather than blocking the UI


class APIError(Exception):
    pass


def _get(path: str, params: Optional[Dict] = None, timeout: int = TIMEOUT) -> Any:
    url = f"{API_BASE}{path}"
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        raise APIError(f"Cannot connect to backend at {BASE_URL}. Is FastAPI running?")
    except requests.exceptions.Timeout:
        raise APIError(f"Request timed out after {timeout}s: {path}")
    except requests.exceptions.HTTPError as e:
        raise APIError(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        raise APIError(str(e))


def _post(path: str, data: Dict) -> Any:
    url = f"{API_BASE}{path}"
    try:
        resp = requests.post(url, json=data, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        raise APIError(f"Cannot connect to backend at {BASE_URL}.")
    except requests.exceptions.HTTPError as e:
        raise APIError(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        raise APIError(str(e))


# ── Executive ──────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_executive_kpis(year: Optional[int] = None) -> Dict:
    p = {"year": year} if year else {}
    return _get("/executive/kpis", p)

@st.cache_data(ttl=600, show_spinner=False)
def get_top_opportunities(top_n: int = 10) -> list:
    return _get("/executive/opportunities", {"top_n": top_n})

@st.cache_data(ttl=300, show_spinner=False)
def get_risk_summary() -> Dict:
    return _get("/executive/risks")

@st.cache_data(ttl=300, show_spinner=False)
def get_sentiment_summary() -> Dict:
    return _get("/executive/sentiment")

@st.cache_data(ttl=120, show_spinner=False)
def get_ai_executive_summary() -> Dict:
    return _get("/executive/ai-summary")

@st.cache_data(ttl=300, show_spinner=False)
def get_market_overview() -> Dict:
    return _get("/executive/market-overview")

# ── Forecast ───────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def predict_demand(target: str = "units", horizon: int = 90,
                   area: Optional[str] = None) -> Dict:
    p = {"target": target, "horizon": horizon}
    if area:
        p["area"] = area
    return _get("/forecast/predict", p)

@st.cache_data(ttl=600, show_spinner=False)
def predict_all_models(target: str = "units", horizon: int = 90) -> Dict:
    return _get("/forecast/all-models", {"target": target, "horizon": horizon})

@st.cache_data(ttl=600, show_spinner=False)
def get_model_metrics(target: str = "units") -> Dict:
    return _get("/forecast/metrics", {"target": target})

@st.cache_data(ttl=600, show_spinner=False)
def get_demand_drivers(target: str = "units") -> Dict:
    return _get("/forecast/drivers", {"target": target})

@st.cache_data(ttl=600, show_spinner=False)
def get_forecast_by_area(target: str = "units", horizon: int = 90, top_n: int = 10) -> Dict:
    # First call fits up to top_n area ensembles — needs extra time; 120s is safe
    return _get("/forecast/by-area", {"target": target, "horizon": horizon, "top_n": top_n},
                timeout=120)

@st.cache_data(ttl=300, show_spinner=False)
def get_early_warnings() -> Dict:
    return _get("/forecast/early-warnings")

# ── Market ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def get_market_opportunities(top_n: int = 15) -> Dict:
    return _get("/market/opportunities", {"top_n": top_n})

@st.cache_data(ttl=600, show_spinner=False)
def get_opportunity_heatmap() -> list:
    return _get("/market/heatmap")

@st.cache_data(ttl=900, show_spinner=False)
def get_competitor_analysis(top_n: int = 10) -> Dict:
    return _get("/market/competitor-analysis", {"top_n": top_n})

@st.cache_data(ttl=900, show_spinner=False)
def get_infrastructure_impact() -> Dict:
    return _get("/market/infrastructure-impact")

@st.cache_data(ttl=900, show_spinner=False)
def get_migration_analysis() -> Dict:
    return _get("/market/migration-analysis")

@st.cache_data(ttl=1800, show_spinner=False)
def get_white_space() -> Dict:
    return _get("/market/white-space")

@st.cache_data(ttl=600, show_spinner=False)
def get_price_trends(area: Optional[str] = None) -> Dict:
    p = {}
    if area:
        p["area"] = area
    return _get("/market/price-trends", p)

# ── Customer ───────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def get_buyer_segments() -> Dict:
    return _get("/customer/segments")

@st.cache_data(ttl=1800, show_spinner=False)
def get_segment_map(sample: int = 3000) -> Dict:
    return _get("/customer/segment-map", {"sample": sample})

@st.cache_data(ttl=300, show_spinner=False)
def predict_price(area: str, property_type: str, bedrooms: int, area_sqft: float,
                  is_off_plan: bool = False, year: int = 2024, month: int = 6) -> Dict:
    return _post("/customer/predict-price", {
        "area": area, "property_type": property_type,
        "bedrooms": bedrooms, "area_sqft": area_sqft,
        "is_off_plan": is_off_plan, "year": year, "month": month,
    })

def predict_price_ai(area: str, property_type: str, bedrooms: int, area_sqft: float,
                     is_off_plan: bool = False, year: int = 2026, month: int = 6) -> Dict:
    return _post("/customer/predict-price-ai", {
        "area": area, "property_type": property_type,
        "bedrooms": bedrooms, "area_sqft": area_sqft,
        "is_off_plan": is_off_plan, "year": year, "month": month,
    })

@st.cache_data(ttl=900, show_spinner=False)
def get_price_elasticity() -> list:
    return _get("/customer/price-elasticity")

@st.cache_data(ttl=900, show_spinner=False)
def get_nationality_demand(top_n: int = 12) -> Dict:
    return _get("/customer/nationality-demand", {"top_n": top_n})

@st.cache_data(ttl=900, show_spinner=False)
def get_property_preferences() -> Dict:
    return _get("/customer/property-preference")

@st.cache_data(ttl=900, show_spinner=False)
def get_price_trends_by_area(top_areas: int = 8) -> Dict:
    return _get("/customer/price-trends", {"top_areas": top_areas})

@st.cache_data(ttl=900, show_spinner=False)
def get_rental_analysis() -> Dict:
    return _get("/customer/rental-analysis")

# ── Inventory ──────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def get_project_status() -> Dict:
    return _get("/inventory/project-status")

@st.cache_data(ttl=600, show_spinner=False)
def get_absorption_analysis() -> Dict:
    return _get("/inventory/absorption-analysis")

@st.cache_data(ttl=300, show_spinner=False)
def launch_advisor(area: str, property_type: str, total_units: int,
                   price_per_sqft_aed: float, area_sqft_per_unit: float = 1000.0,
                   launch_year: int = 2025, launch_month: int = 6,
                   is_off_plan: bool = True, amenities_score: int = 7) -> Dict:
    return _post("/inventory/launch-advisor", {
        "area": area, "property_type": property_type, "total_units": total_units,
        "price_per_sqft_aed": price_per_sqft_aed, "area_sqft_per_unit": area_sqft_per_unit,
        "launch_date_year": launch_year, "launch_date_month": launch_month,
        "is_off_plan": is_off_plan, "amenities_score": amenities_score,
    })

def launch_advisor_ai(area: str, property_type: str, total_units: int,
                      price_per_sqft_aed: float, area_sqft_per_unit: float = 1000.0,
                      launch_year: int = 2025, launch_month: int = 6,
                      is_off_plan: bool = True, amenities_score: int = 7) -> Dict:
    return _post("/inventory/launch-advisor-ai", {
        "area": area, "property_type": property_type, "total_units": total_units,
        "price_per_sqft_aed": price_per_sqft_aed, "area_sqft_per_unit": area_sqft_per_unit,
        "launch_date_year": launch_year, "launch_date_month": launch_month,
        "is_off_plan": is_off_plan, "amenities_score": amenities_score,
    })

@st.cache_data(ttl=300, show_spinner=False)
def predict_sellout(area: str, units: int, price_per_sqft: float) -> Dict:
    return _get("/inventory/sellout-prediction",
                {"area": area, "units": units, "price_per_sqft": price_per_sqft})

# ── AI Studio ──────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def ai_query(question: str) -> Dict:
    return _post("/ai/query", {"question": question})

@st.cache_data(ttl=60, show_spinner=False)
def run_scenario(levers: Dict, horizon_months: int = 12, description: str = "") -> Dict:
    return _post("/ai/scenario", {"levers": levers, "horizon_months": horizon_months,
                                  "description": description})

@st.cache_data(ttl=60, show_spinner=False)
def run_monte_carlo(base_demand: float, base_price: float, horizon_months: int = 12,
                    n_simulations: int = 2000, volatility: float = 0.08) -> Dict:
    return _post("/ai/monte-carlo", {"base_demand": base_demand, "base_price": base_price,
                                     "horizon_months": horizon_months,
                                     "n_simulations": n_simulations, "volatility": volatility})

@st.cache_data(ttl=300, show_spinner=False)
def run_investment_analysis(purchase_price: float, area_sqft: float, rental_yield: float,
                             holding_years: int = 5, appreciation: float = 5.0,
                             financing: float = 0.0, mortgage_rate: float = 4.0) -> Dict:
    return _post("/ai/investment-analysis", {
        "purchase_price_aed": purchase_price, "area_sqft": area_sqft,
        "rental_yield_pct": rental_yield, "holding_years": holding_years,
        "appreciation_pct": appreciation, "financing_pct": financing,
        "mortgage_rate_pct": mortgage_rate,
    })

def run_investment_analysis_ai(purchase_price: float, area_sqft: float, rental_yield: float,
                                holding_years: int = 5, appreciation: float = 5.0,
                                financing: float = 0.0, mortgage_rate: float = 4.0,
                                area: str = "", property_type: str = "") -> Dict:
    return _post("/ai/investment-analysis-ai", {
        "purchase_price_aed": purchase_price, "area_sqft": area_sqft,
        "rental_yield_pct": rental_yield, "holding_years": holding_years,
        "appreciation_pct": appreciation, "financing_pct": financing,
        "mortgage_rate_pct": mortgage_rate,
        "area": area, "property_type": property_type,
    })

@st.cache_data(ttl=300, show_spinner=False)
def get_investment_verdict(purchase_price: float, rental_yield: float,
                           holding_years: int, total_roi_pct: float,
                           annualised_roi_pct: float) -> Dict:
    return _post("/ai/investment-verdict", {
        "purchase_price_aed": purchase_price,
        "rental_yield_pct": rental_yield,
        "holding_years": holding_years,
        "total_roi_pct": total_roi_pct,
        "annualised_roi_pct": annualised_roi_pct,
    })

def get_latest_news(category: str = "Market Overview") -> Dict:
    return _get("/ai/latest-news", {"category": category}, timeout=15)

@st.cache_data(ttl=3600, show_spinner=False)
def get_all_areas() -> list:
    return _get("/ai/areas")

def calibrate_levers_from_news(template_name: str, area: str, levers: list) -> Dict:
    return _post("/ai/news-lever-calibration", {
        "template_name": template_name,
        "area": area,
        "levers": levers,
    })

def get_news_forecast() -> Dict:
    return _get("/ai/news-forecast", timeout=30)

@st.cache_data(ttl=300, show_spinner=False)
def compare_markets(areas: str) -> Dict:
    return _get("/ai/market-comparison", {"areas": areas})

@st.cache_data(ttl=1800, show_spinner=False)
def get_scenario_levers() -> list:
    return _get("/ai/available-levers")

@st.cache_data(ttl=1800, show_spinner=False)
def get_strategy_templates() -> list:
    return _get("/ai/strategy-templates")

# ── Health ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def health_check() -> Dict:
    try:
        return requests.get(f"{BASE_URL}/health", timeout=5).json()
    except Exception:
        return {"status": "unreachable"}
