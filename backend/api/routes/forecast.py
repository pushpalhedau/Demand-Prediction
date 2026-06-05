"""Forecast & Demand Intelligence API — Tab 2"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd

from backend.data.loader import data_store
from backend.data.cache import cache
from backend.ml.forecasting.ensemble import ForecastEnsemble

router = APIRouter(prefix="/forecast", tags=["forecast"])
log    = logging.getLogger(__name__)

# Global ensemble instances (fitted lazily)
_ensembles: dict[str, ForecastEnsemble] = {}


def _get_ensemble(target: str = "units") -> ForecastEnsemble:
    if target not in _ensembles:
        fe = ForecastEnsemble(target=target)
        fe._load_cache()
        if not fe._is_fitted:
            log.info("Fitting ForecastEnsemble target=%s …", target)
            df_tx   = data_store.get("transactions")
            df_ir   = data_store.get("interest_rates")
            df_sent = data_store.get("sentiment_index")
            fe.fit(df_tx, df_ir, df_sent)
        _ensembles[target] = fe
    return _ensembles[target]


@router.get("/predict")
def predict_demand(
    target:  str = Query("units",  description="units | revenue"),
    horizon: int = Query(90,       description="Forecast horizon in days"),
    area:    Optional[str] = Query(None, description="Filter by area name"),
):
    ckey = {"target": target, "horizon": horizon, "area": area}
    cached = cache.get("forecast_predict", ckey)
    if cached:
        return cached

    fe = _get_ensemble(target)
    result = fe.predict(horizon_days=horizon)

    # If area filter requested, re-run on area subset
    if area:
        df_tx = data_store.get("transactions")
        df_area = df_tx[df_tx["area_name"].str.lower() == area.lower()] if not df_tx.empty else df_tx
        if len(df_area) >= 30:
            fe_area = ForecastEnsemble(target=target)
            df_ir   = data_store.get("interest_rates")
            df_sent = data_store.get("sentiment_index")
            fe_area.fit(df_area, df_ir, df_sent)
            result = fe_area.predict(horizon_days=horizon)
            result["area_filter"] = area

    cache.set("forecast_predict", ckey, result, ttl=600)
    return result


@router.get("/all-models")
def predict_all_models(
    target:  str = Query("units"),
    horizon: int = Query(90),
):
    fe = _get_ensemble(target)
    return fe.predict_all_models(horizon_days=horizon)


@router.get("/metrics")
def get_model_metrics(target: str = Query("units")):
    fe = _get_ensemble(target)
    return {"target": target, "metrics": fe.get_metrics(), "best_model": fe.best_model}


@router.get("/drivers")
def get_demand_drivers(target: str = Query("units")):
    fe = _get_ensemble(target)
    return {
        "target": target,
        "best_model": fe.best_model,
        "feature_importance": fe.get_feature_importance(),
    }


@router.get("/by-area")
def forecast_by_area(
    target:   str = Query("units"),
    horizon:  int = Query(90),
    top_n:    int = Query(10),
):
    """Forecast for each of the top N areas independently."""
    ckey = {"target": target, "horizon": horizon, "top_n": top_n}
    cached = cache.get("forecast_by_area", ckey)
    if cached:
        return cached

    df_tx   = data_store.get("transactions")
    df_ir   = data_store.get("interest_rates")
    df_sent = data_store.get("sentiment_index")

    top_areas = df_tx["area_name"].value_counts().head(top_n).index.tolist() if not df_tx.empty else []
    results = {}
    for area in top_areas:
        df_area = df_tx[df_tx["area_name"] == area]
        if len(df_area) < 30:
            continue
        try:
            fe = ForecastEnsemble(target=target)
            fe.fit(df_area, df_ir, df_sent)
            fc = fe.predict(horizon_days=horizon)
            results[area] = {
                "model": fc["model"],
                "mape":  fc["metrics"].get("mape", 0),
                "forecast_values": fc["forecast"]["values"][:3],
                "trend": "up" if fc["forecast"]["values"][-1] > fc["forecast"]["values"][0] else "down",
            }
        except Exception as exc:
            log.warning("Forecast failed for area %s: %s", area, exc)

    cache.set("forecast_by_area", ckey, results, ttl=900)
    return results


@router.get("/early-warnings")
def get_early_warnings():
    """Detect early demand warning signals from historical data."""
    df_tx   = data_store.get("transactions")
    df_sent = data_store.get("sentiment_index")
    df_ir   = data_store.get("interest_rates")

    warnings = []

    # Volume decline signal
    if not df_tx.empty and "year" in df_tx.columns:
        by_year = df_tx.groupby("year").size()
        if len(by_year) >= 2:
            latest = by_year.index.max()
            prev   = latest - 1
            if prev in by_year.index:
                chg = (by_year[latest] - by_year[prev]) / by_year[prev] * 100
                if chg < -5:
                    warnings.append({"signal": "Demand Contraction",
                                      "description": f"Transaction volume fell {abs(chg):.1f}% YoY.",
                                      "severity": "high", "action": "Review pricing strategy and incentives."})

    # Rising rates warning
    if not df_ir.empty and "avg_mortgage_rate_pct" in df_ir.columns:
        if len(df_ir) >= 3:
            rate_change = df_ir["avg_mortgage_rate_pct"].iloc[-1] - df_ir["avg_mortgage_rate_pct"].iloc[-3]
            if rate_change > 0.5:
                warnings.append({"signal": "Rising Mortgage Rates",
                                  "description": f"Rates up {rate_change:.2f}% in 3 months — affordability squeeze.",
                                  "severity": "medium", "action": "Offer payment plan flexibility."})

    # Sentiment drop
    if not df_sent.empty and "buyer_confidence_index" in df_sent.columns:
        if len(df_sent) >= 3:
            conf_chg = df_sent["buyer_confidence_index"].iloc[-1] - df_sent["buyer_confidence_index"].iloc[-3]
            if conf_chg < -5:
                warnings.append({"signal": "Buyer Confidence Decline",
                                  "description": f"Confidence index dropped {abs(conf_chg):.1f} pts in 3 months.",
                                  "severity": "medium", "action": "Increase marketing spend and trust signals."})

    return {"warnings": warnings, "total": len(warnings)}
