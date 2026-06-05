"""Customer & Pricing Intelligence API — Tab 4"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd

from backend.data.loader import data_store
from backend.data.cache import cache
from backend.ml.segmentation.clustering import MarketSegmentation
from backend.ml.pricing.price_model import PriceModel

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
