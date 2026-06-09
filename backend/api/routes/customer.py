"""Customer & Pricing Intelligence API — Tab 4"""
from __future__ import annotations

import json
import logging
import re
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd

from backend.data.loader import data_store
from backend.data.cache import cache
from backend.ml.segmentation.clustering import MarketSegmentation
from backend.ml.pricing.price_model import PriceModel
from backend.ai.groq_client import groq_client
from backend.ai.news_client import news_client
from backend.ai.rag import rag_engine

router = APIRouter(prefix="/customer", tags=["customer"])
log    = logging.getLogger(__name__)

_segmentation: Optional[MarketSegmentation] = None
_price_model:  Optional[PriceModel]          = None


def _get_segmentation() -> MarketSegmentation:
    global _segmentation
    if _segmentation is None or not _segmentation._is_fitted:
        seg = MarketSegmentation(n_clusters=6)
        df_tx = data_store.get("transactions")
        if not df_tx.empty:
            seg.fit(df_tx)
        _segmentation = seg
    return _segmentation


def _get_price_model() -> PriceModel:
    global _price_model
    if _price_model is None or not _price_model._is_fitted:
        pm = PriceModel()
        df_tx = data_store.get("transactions")
        if not df_tx.empty:
            pm.fit(df_tx)
        _price_model = pm
    return _price_model


class PricingRequest(BaseModel):
    area: str
    property_type: str
    bedrooms: int
    area_sqft: float
    is_off_plan: bool = False
    year: int = 2024
    month: int = 6


@router.get("/segments")
def get_buyer_segments():
    cached = cache.get("customer_segments", {})
    if cached:
        return cached

    seg = _get_segmentation()
    result = {"segments": seg.get_segment_profiles(), "n_clusters": seg.n_clusters}
    cache.set("customer_segments", {}, result, ttl=900)
    return result


@router.get("/segment-map")
def get_segment_2d_map(sample: int = Query(3000, le=5000)):
    df_tx = data_store.get("transactions")
    seg   = _get_segmentation()
    return seg.get_2d_projection(df_tx, sample=sample)


@router.post("/predict-price")
def predict_price(req: PricingRequest):
    pm = _get_price_model()
    return pm.predict_price(
        area=req.area, property_type=req.property_type,
        bedrooms=req.bedrooms, area_sqft=req.area_sqft,
        is_off_plan=req.is_off_plan, year=req.year, month=req.month,
    )


class PricingRequestAI(BaseModel):
    area: str
    property_type: str
    bedrooms: int
    area_sqft: float
    is_off_plan: bool = False
    year: int = 2026
    month: int = 6


@router.post("/predict-price-ai")
def predict_price_ai(req: PricingRequestAI):
    """Hybrid price prediction: DLD statistical anchor + Groq LLM + live news."""
    df_tx = data_store.get("transactions")

    # ── Step 1: DLD statistical anchor (last 12 months) ──────────────
    anchor_psf = None
    n_tx       = 0
    yoy_pct    = 0.0

    if not df_tx.empty and "transaction_date" in df_tx.columns:
        latest  = df_tx["transaction_date"].max()
        cutoff  = latest - pd.DateOffset(months=12)
        df_rec  = df_tx[df_tx["transaction_date"] >= cutoff]

        # Specific: area + property_type + bedrooms
        mask = (
            (df_rec["area_name"].str.lower() == req.area.lower()) &
            (df_rec["property_type"].str.lower() == req.property_type.lower()) &
            (df_rec["bedrooms"] == req.bedrooms)
        )
        grp = df_rec[mask]
        if len(grp) >= 5:
            anchor_psf = float(grp["price_per_sqft_aed"].median())
            n_tx = len(grp)

        # Fallback: area only
        if anchor_psf is None:
            grp_area = df_rec[df_rec["area_name"].str.lower() == req.area.lower()]
            if len(grp_area) >= 3:
                anchor_psf = float(grp_area["price_per_sqft_aed"].median())
                n_tx = len(grp_area)

        # YoY for this area
        cutoff_prev = cutoff - pd.DateOffset(months=12)
        df_prev = df_tx[
            (df_tx["transaction_date"] >= cutoff_prev) &
            (df_tx["transaction_date"] < cutoff) &
            (df_tx["area_name"].str.lower() == req.area.lower())
        ]
        if len(df_prev) >= 3 and anchor_psf:
            prev_med = float(df_prev["price_per_sqft_aed"].median())
            if prev_med > 0:
                yoy_pct = round((anchor_psf - prev_med) / prev_med * 100, 1)

    # Final fallback: model medians
    pm = _get_price_model()
    if anchor_psf is None:
        anchor_psf = float(
            pm._fallback_medians.get("area", {}).get(req.area) or
            pm._fallback_medians.get("property_type", {}).get(req.property_type) or
            pm._fallback_medians.get("global") or
            1400.0
        )

    # ── Step 2: RAG context ──────────────────────────────────────────
    rag_context = rag_engine.retrieve(
        f"{req.area} {req.property_type} price yield", top_k=4
    )

    # ── Step 3: News ─────────────────────────────────────────────────
    articles, _ = news_client._fetch_google_news_rss(
        f"{req.area} property real estate prices Dubai", max_results=8
    )

    news_lines = "\n".join(
        f"{i+1}. {a['title']} — {a.get('source','Unknown')} — {a.get('publishedAt','')[:10]}"
        for i, a in enumerate(articles)
    ) or "No recent news available."

    # ── Step 4: Groq prompt ──────────────────────────────────────────
    system_prompt = (
        "You are a UAE real estate pricing expert. "
        "Return ONLY valid JSON — no markdown, no explanation outside the JSON. "
        "Keys: price_adjustment_pct, final_price_per_sqft_aed, reasoning, confidence, key_signals."
    )
    prompt = f"""Estimate the optimal price per sqft for this Dubai property.

STATISTICAL ANCHOR (DLD transactions, last 12 months):
- Area: {req.area} | Type: {req.property_type} | Beds: {req.bedrooms}
- Median price/sqft: AED {anchor_psf:,.0f} (from {n_tx} transactions)
- YoY area price change: {yoy_pct:+.1f}%

PROPERTY SPECS:
- Size: {req.area_sqft:.0f} sqft | Off-plan: {"Yes" if req.is_off_plan else "No"}
- Target period: {req.month}/{req.year}

MARKET CONTEXT:
{rag_context[:800] if rag_context else "Not available."}

RECENT NEWS ({len(articles)} articles):
{news_lines}

Return ONLY valid JSON:
{{
  "price_adjustment_pct": <float -20 to +20, relative to anchor>,
  "final_price_per_sqft_aed": <float>,
  "reasoning": "<2-3 sentences explaining key pricing factors>",
  "confidence": "<high|medium|low>",
  "key_signals": ["<signal 1>", "<signal 2>", "<signal 3>"]
}}"""

    raw = groq_client.chat(
        prompt, system_override=system_prompt,
        max_tokens=512, temperature=0.2, cache_ttl=300,
    )

    # ── Step 5: Parse Groq JSON ──────────────────────────────────────
    adj_pct     = 0.0
    final_psf   = anchor_psf
    reasoning   = "Price based on DLD transaction median for this area and property type."
    confidence  = "medium"
    key_signals: List[str] = []

    try:
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            parsed      = json.loads(json_match.group())
            adj_pct     = float(parsed.get("price_adjustment_pct", 0))
            final_psf   = float(parsed.get("final_price_per_sqft_aed",
                                           anchor_psf * (1 + adj_pct / 100)))
            reasoning   = str(parsed.get("reasoning", reasoning))
            confidence  = str(parsed.get("confidence", "medium"))
            key_signals = list(parsed.get("key_signals", []))
    except Exception as exc:
        log.warning("Could not parse Groq pricing JSON: %s | raw: %.200s", exc, raw)

    final_psf   = max(300.0, float(final_psf))
    total_price = final_psf * req.area_sqft

    return {
        "recommended_price_per_sqft_aed": round(final_psf, 0),
        "recommended_total_price_aed":    round(total_price, 0),
        "premium_ceiling_aed":            round(final_psf * 1.15 * req.area_sqft, 0),
        "discount_floor_aed":             round(final_psf * 0.90 * req.area_sqft, 0),
        "anchor_price_per_sqft_aed":      round(anchor_psf, 0),
        "price_adjustment_pct":           round(adj_pct, 1),
        "reasoning":                      reasoning,
        "confidence":                     confidence,
        "key_signals":                    key_signals[:3],
        "news_used": [
            {
                "title":       a.get("title", ""),
                "source":      a.get("source", ""),
                "publishedAt": a.get("publishedAt", "")[:10],
                "url":         a.get("url", ""),
            }
            for a in articles[:6]
        ],
    }


@router.get("/price-elasticity")
def get_price_elasticity():
    cached = cache.get("price_elasticity", {})
    if cached:
        return cached
    pm    = _get_price_model()
    df_tx = data_store.get("transactions")
    result = pm.price_elasticity(df_tx)
    cache.set("price_elasticity", {}, result, ttl=900)
    return result


@router.get("/nationality-demand")
def get_nationality_demand(top_n: int = Query(12)):
    df_tx = data_store.get("transactions")
    if df_tx.empty or "buyer_nationality" not in df_tx.columns:
        return {"data": []}

    latest_year = int(df_tx["year"].max())
    curr = df_tx[df_tx["year"] == latest_year]
    prev = df_tx[df_tx["year"] == latest_year - 1]

    curr_cnt = curr["buyer_nationality"].value_counts().head(top_n).reset_index()
    curr_cnt.columns = ["nationality", "transactions_curr"]
    prev_cnt = prev["buyer_nationality"].value_counts().reset_index()
    prev_cnt.columns = ["nationality", "transactions_prev"]

    merged = curr_cnt.merge(prev_cnt, on="nationality", how="left").fillna(0)
    merged["yoy_change_pct"] = (
        (merged["transactions_curr"] - merged["transactions_prev"]) /
        merged["transactions_prev"].replace(0, 1) * 100
    ).round(1)
    return {"data": merged.to_dict("records"), "year": latest_year}


@router.get("/property-preference")
def get_property_preferences():
    df_tx = data_store.get("transactions")
    if df_tx.empty:
        return {}

    return {
        "by_type": df_tx["property_type"].value_counts(normalize=True).mul(100).round(1).to_dict()
                   if "property_type" in df_tx.columns else {},
        "by_bedrooms": df_tx["bedrooms"].value_counts(normalize=True).mul(100).round(1).to_dict()
                       if "bedrooms" in df_tx.columns else {},
        "off_plan_share": round(float(df_tx["is_off_plan"].astype(float).mean() * 100), 1)
                          if "is_off_plan" in df_tx.columns else 0,
        "avg_transaction_value": round(float(df_tx["transaction_value_aed"].mean()), 0),
        "median_transaction_value": round(float(df_tx["transaction_value_aed"].median()), 0),
    }


@router.get("/price-trends")
def get_price_trends_by_area(top_areas: int = Query(8)):
    pm    = _get_price_model()
    df_tx = data_store.get("transactions")
    if df_tx.empty:
        return {"trends": []}

    trends_df = pm.area_price_trends(df_tx)
    top_area_list = df_tx["area_name"].value_counts().head(top_areas).index.tolist()
    filtered = trends_df[trends_df["area_name"].isin(top_area_list)]
    filtered["period"] = filtered["ds"].dt.strftime("%Y-%m")
    return {"trends": filtered[["area_name", "period", "avg_price_sqft", "tx_count"]].to_dict("records")}


@router.get("/rental-analysis")
def get_rental_analysis():
    df_rent = data_store.get("rentals")
    if df_rent.empty:
        return {"summary": {}, "by_area": [], "by_type": []}

    summary = {
        "total_contracts": len(df_rent),
        "avg_annual_rent": round(float(df_rent["annual_rent_aed"].mean()), 0),
        "median_annual_rent": round(float(df_rent["annual_rent_aed"].median()), 0),
        "renewal_rate_pct": round(df_rent["is_renewal"].astype(float).mean() * 100, 1)
                             if "is_renewal" in df_rent.columns else 0,
    }

    by_area = []
    if "area" in df_rent.columns:
        by_area = df_rent.groupby("area").agg(
            contracts=("contract_id", "count"),
            avg_annual_rent=("annual_rent_aed", "mean"),
        ).reset_index().nlargest(10, "contracts").round(0).to_dict("records")

    by_type = []
    if "property_type" in df_rent.columns:
        by_type = df_rent.groupby("property_type").agg(
            contracts=("contract_id", "count"),
            avg_annual_rent=("annual_rent_aed", "mean"),
        ).reset_index().round(0).to_dict("records")

    return {"summary": summary, "by_area": by_area, "by_type": by_type}
