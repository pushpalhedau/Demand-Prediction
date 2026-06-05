"""AI Strategy Studio API — Tab 6"""
from __future__ import annotations

import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any
import pandas as pd

from backend.data.loader import data_store
from backend.data.cache import cache
from backend.ai.groq_client import groq_client
from backend.ai.rag import rag_engine
from backend.ai.scenario_engine import scenario_engine

router = APIRouter(prefix="/ai", tags=["ai-studio"])
log    = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    question: str
    context_limit: int = 2000


class ScenarioRequest(BaseModel):
    levers: Dict[str, float]
    horizon_months: int = 12
    description: Optional[str] = None


class MonteCarloRequest(BaseModel):
    base_demand: float
    base_price: float
    horizon_months: int = 12
    n_simulations: int = 2000
    volatility: float = 0.08


class InvestmentRequest(BaseModel):
    purchase_price_aed: float
    area_sqft: float
    rental_yield_pct: float
    holding_years: int = 5
    appreciation_pct: float = 5.0
    financing_pct: float = 0.0
    mortgage_rate_pct: float = 4.0


@router.post("/query")
def answer_query(req: QueryRequest):
    """Natural language query answered by GROQ + RAG context."""
    retrieved_context = rag_engine.retrieve(req.question, top_k=6)

    # Augment with live data if topic detected
    live_context = _build_live_context(req.question)
    full_context = "\n\n".join(filter(None, [retrieved_context, live_context]))

    if len(full_context) > req.context_limit:
        full_context = full_context[:req.context_limit] + "\n[context truncated]"

    answer = groq_client.answer_strategy_query(req.question, full_context)
    return {
        "question":       req.question,
        "answer":         answer,
        "context_used":   len(full_context),
        "rag_available":  rag_engine._available,
        "ai_available":   groq_client.available,
    }


@router.post("/scenario")
def run_scenario(req: ScenarioRequest):
    """What-if scenario analysis using lever-impact model."""
    df_tx = data_store.get("transactions")
    df_pi = data_store.get("price_index")

    # Base values from latest data
    base_demand = float(df_tx.groupby(["year", "month"]).size().mean()) if not df_tx.empty else 1000
    base_price  = float(df_tx["price_per_sqft_aed"].mean()) if not df_tx.empty else 1200

    result = scenario_engine.what_if(
        levers=req.levers,
        base_demand=base_demand,
        base_price=base_price,
        horizon_months=req.horizon_months,
    )

    # AI narrative
    desc = req.description or f"Scenario with {len(req.levers)} lever(s)"
    result["ai_analysis"] = groq_client.analyze_scenario(desc, {
        "demand_change": result["demand_delta_pct"],
        "price_change":  result["price_delta_pct"],
        "key_levers":    [l["lever"] for l in result["applied_levers"]],
    })
    return result


@router.post("/monte-carlo")
def run_monte_carlo(req: MonteCarloRequest):
    return scenario_engine.monte_carlo(
        base_demand=req.base_demand,
        base_price=req.base_price,
        horizon_months=req.horizon_months,
        n_simulations=req.n_simulations,
        volatility=req.volatility,
    )


@router.post("/investment-analysis")
def run_investment_analysis(req: InvestmentRequest):
    result = scenario_engine.investment_analysis(
        purchase_price_aed=req.purchase_price_aed,
        area_sqft=req.area_sqft,
        rental_yield_pct=req.rental_yield_pct,
        holding_years=req.holding_years,
        appreciation_pct=req.appreciation_pct,
        financing_pct=req.financing_pct,
        mortgage_rate_pct=req.mortgage_rate_pct,
    )
    # AI narrative
    context = f"Investment: AED {req.purchase_price_aed:,.0f} property, {req.rental_yield_pct:.1f}% yield, {req.holding_years}yr hold"
    question = f"Is this a good real estate investment in UAE? ROI={result['total_roi_pct']:.1f}%, annualised={result['annualised_roi_pct']:.1f}%"
    result["ai_verdict"] = groq_client.answer_strategy_query(question, context)
    return result


@router.get("/market-comparison")
def compare_markets(areas: str = "Dubai South,Downtown Dubai,Business Bay,JVC"):
    area_list = [a.strip() for a in areas.split(",")]
    df_tx = data_store.get("transactions")
    df_pi = data_store.get("price_index")

    comparisons = []
    for area in area_list:
        area_tx = df_tx[df_tx["area_name"].str.lower() == area.lower()] if not df_tx.empty else pd.DataFrame()
        pi_row  = {}
        if not df_pi.empty and "area" in df_pi.columns:
            pi_rows = df_pi[df_pi["area"].str.lower() == area.lower()].sort_values(["year", "quarter"])
            if not pi_rows.empty:
                pi_row = pi_rows.iloc[-1].to_dict()
        comparisons.append({
            "area":               area,
            "total_transactions": len(area_tx),
            "avg_psf":            round(float(area_tx["price_per_sqft_aed"].mean()), 0) if not area_tx.empty else 0,
            "yoy_growth_pct":     round(float(pi_row.get("price_yoy_change_pct", 0)), 1),
            "rental_yield_pct":   round(float(pi_row.get("rental_yield_pct", 0)), 1),
            "avg_days_to_sell":   round(float(pi_row.get("avg_days_to_sell", 0)), 0),
        })

    context = "\n".join([
        f"{c['area']}: AED {c['avg_psf']:,}/sqft, {c['yoy_growth_pct']:+.1f}% YoY, "
        f"{c['rental_yield_pct']:.1f}% yield"
        for c in comparisons
    ])
    ai_comparison = groq_client.answer_strategy_query(
        f"Compare these UAE real estate markets for investment: {areas}. Which offers the best risk-adjusted return?",
        context
    )
    return {"comparisons": comparisons, "ai_analysis": ai_comparison}


@router.get("/available-levers")
def get_available_levers():
    """Return list of scenario levers with descriptions."""
    from backend.ai.scenario_engine import LEVER_IMPACTS
    return [
        {
            "lever": key,
            "label": key.replace("_", " ").title(),
            "demand_coefficient": val["demand"],
            "price_coefficient":  val["price"],
            "description": _lever_description(key),
        }
        for key, val in LEVER_IMPACTS.items()
    ]


@router.get("/strategy-templates")
def get_strategy_templates():
    """Pre-built scenario templates for common strategic questions."""
    return [
        {
            "name":  "Rate Hike Impact",
            "description": "Fed raises rates by 100bps — what happens to demand?",
            "levers": {"interest_rate_change_pct": 1.0},
        },
        {
            "name":  "Golden Visa Expansion",
            "description": "UAE announces expanded Golden Visa programme",
            "levers": {"visa_policy_change": 1.0, "population_growth_pct": 0.5},
        },
        {
            "name":  "Supply Surge",
            "description": "5,000 new units enter the market",
            "levers": {"new_supply_units_k": 5.0},
        },
        {
            "name":  "Oil Price Boom",
            "description": "Oil hits $100/barrel — GCC wealth effect",
            "levers": {"oil_price_change_pct": 20.0, "gdp_growth_pct": 1.0},
        },
        {
            "name":  "Infrastructure Boom",
            "description": "AED 5B infrastructure investment announced",
            "levers": {"infrastructure_investment_bn": 5.0, "sentiment_change_index": 15.0},
        },
    ]


# ── Helpers ────────────────────────────────────────────────────────────

def _build_live_context(question: str) -> str:
    """Attach relevant live data to the query based on topic detection."""
    q = question.lower()
    parts = []

    df_tx = data_store.get("transactions")
    if df_tx is not None and not df_tx.empty and any(w in q for w in ["transaction", "demand", "volume", "market"]):
        latest_year = int(df_tx["year"].max())
        curr = df_tx[df_tx["year"] == latest_year]
        parts.append(f"Live Transactions {latest_year}: {len(curr):,} total, "
                     f"AED {curr['transaction_value_aed'].sum()/1e9:.1f}B total value, "
                     f"AED {curr['price_per_sqft_aed'].mean():,.0f}/sqft avg")

    df_ir = data_store.get("interest_rates")
    if df_ir is not None and not df_ir.empty and any(w in q for w in ["rate", "mortgage", "interest", "finance"]):
        last = df_ir.iloc[-1]
        parts.append(f"Latest Rates: UAE Base {last.get('uae_base_rate_pct', 0):.2f}%, "
                     f"Avg Mortgage {last.get('avg_mortgage_rate_pct', 0):.2f}%")

    df_pi = data_store.get("price_index")
    if df_pi is not None and not df_pi.empty and any(w in q for w in ["price", "sqft", "yield", "roi"]):
        avg_yield = df_pi["rental_yield_pct"].mean()
        avg_growth = df_pi["price_yoy_change_pct"].mean()
        parts.append(f"Market Averages: Rental Yield {avg_yield:.1f}%, Price YoY Growth {avg_growth:.1f}%")

    return "\n".join(parts)


def _lever_description(lever: str) -> str:
    desc = {
        "interest_rate_change_pct":     "Change in UAE Central Bank base rate (%)",
        "population_growth_pct":        "Change in population growth rate (%)",
        "gdp_growth_pct":               "Change in UAE GDP growth rate (%)",
        "visa_policy_change":           "Golden Visa / residency policy expansion (1=major, 0.5=moderate)",
        "new_supply_units_k":           "New housing units entering market (thousands)",
        "oil_price_change_pct":         "Change in Brent crude oil price (%)",
        "sentiment_change_index":       "Change in market sentiment index points",
        "infrastructure_investment_bn": "Infrastructure investment (AED billions)",
    }
    return desc.get(lever, "")
