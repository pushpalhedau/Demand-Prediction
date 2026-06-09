"""Forecast & Demand Intelligence API — Tab 2"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
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
_ensembles:      dict[str, ForecastEnsemble] = {}
# Area-specific ensemble cache — avoids refitting on every /predict?area=X call (B7)
_area_ensembles: dict[str, ForecastEnsemble] = {}
_MAX_AREA_CACHE  = 25  # keep at most N area models in memory


def _get_ensemble(target: str = "units") -> ForecastEnsemble:
    if target not in _ensembles:
        fe = ForecastEnsemble(target=target)
        fe._load_cache()
        if not fe._is_fitted:
            log.info("Fitting ForecastEnsemble target=%s …", target)
            df_tx    = data_store.get("transactions")
            df_ir    = data_store.get("interest_rates")
            df_sent  = data_store.get("sentiment_index")
            df_cpi   = data_store.get("cpi")
            df_px    = data_store.get("price_index")
            df_rent  = data_store.get("rentals")
            df_gdelt = data_store.get("gdelt_sentiment")
            fe.fit(df_tx, df_ir, df_sent, df_cpi, df_px, df_rent, df_gdelt)
        _ensembles[target] = fe
    return _ensembles[target]


def _get_area_ensemble(area: str, target: str,
                       df_tx: "pd.DataFrame",
                       df_ir: "pd.DataFrame",
                       df_sent: "pd.DataFrame") -> Optional[ForecastEnsemble]:
    """Return (or fit and cache) a ForecastEnsemble for a specific area (B7).
    Caps cache at _MAX_AREA_CACHE entries to bound memory use."""
    ck = f"{target}:{area}"
    if ck in _area_ensembles:
        return _area_ensembles[ck]
    df_area = df_tx[df_tx["area_name"] == area].copy()
    if len(df_area) < 30:
        return None
    try:
        fe = ForecastEnsemble(target=target)
        fe.fit(df_area, df_ir, df_sent, fast=True)  # area-level: LightGBM only, no CV
        if len(_area_ensembles) >= _MAX_AREA_CACHE:
            # Evict oldest entry (insertion order in Python 3.7+)
            _area_ensembles.pop(next(iter(_area_ensembles)))
        _area_ensembles[ck] = fe
        return fe
    except Exception as exc:
        log.warning("Area ensemble fit failed for %s: %s", area, exc)
        return None


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

    # If area filter requested, use cached area ensemble (B7)
    if area:
        df_tx   = data_store.get("transactions").copy()
        df_ir   = data_store.get("interest_rates").copy()
        df_sent = data_store.get("sentiment_index").copy()
        # Case-insensitive area match
        area_norm = next(
            (a for a in df_tx["area_name"].unique() if a.lower() == area.lower()), area
        ) if not df_tx.empty else area
        fe_area = _get_area_ensemble(area_norm, target, df_tx, df_ir, df_sent)
        if fe_area is not None:
            result = fe_area.predict(horizon_days=horizon)
            result["area_filter"] = area_norm

    # ── Daily enrichment: raw daily history + day-distributed forecast ──
    try:
        _df_raw = data_store.get("transactions")
        if _df_raw is not None and not _df_raw.empty:
            _df_d = _df_raw.copy()
            _area_val = result.get("area_filter")
            if _area_val:
                _df_d = _df_d[_df_d["area_name"] == _area_val]
            _df_d["transaction_date"] = pd.to_datetime(_df_d["transaction_date"])
            # Last 2 years of daily history
            _cutoff = _df_d["transaction_date"].max() - pd.DateOffset(years=2)
            _df_d = _df_d[_df_d["transaction_date"] >= _cutoff]
            if target == "revenue":
                _dh = (_df_d.groupby("transaction_date")["transaction_value_aed"]
                       .sum().reset_index(name="count"))
            else:
                _dh = (_df_d.groupby("transaction_date").size()
                       .reset_index(name="count"))
            _dh = _dh.sort_values("transaction_date")
            result["historical_daily"] = {
                "dates":  [d.isoformat() for d in _dh["transaction_date"]],
                "values": _dh["count"].round(1).tolist(),
            }
            # Distribute each monthly forecast value across the days of that month
            _fd, _fv, _fl, _fu = [], [], [], []
            for _ds, _v, _lo, _hi in zip(
                result["forecast"]["dates"],
                result["forecast"]["values"],
                result["forecast"]["lower"],
                result["forecast"]["upper"],
            ):
                _ms   = pd.Timestamp(_ds)
                _days = (_ms + pd.offsets.MonthEnd(1)).day
                _dv, _dlo, _dhi = _v / _days, _lo / _days, _hi / _days
                for _off in range(_days):
                    _fd.append((_ms + pd.Timedelta(days=_off)).isoformat())
                    _fv.append(round(_dv, 2))
                    _fl.append(round(_dlo, 2))
                    _fu.append(round(_dhi, 2))
            result["forecast_daily"] = {
                "dates": _fd, "values": _fv, "lower": _fl, "upper": _fu,
            }
    except Exception as _exc:
        log.warning("Daily enrichment failed: %s", _exc)

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

    df_tx   = data_store.get("transactions").copy()
    df_ir   = data_store.get("interest_rates").copy()
    df_sent = data_store.get("sentiment_index").copy()

    top_areas = df_tx["area_name"].value_counts().head(top_n).index.tolist() if not df_tx.empty else []

    def _fit_area(area: str):
        try:
            fe = _get_area_ensemble(area, target, df_tx, df_ir, df_sent)
            if fe is None:
                return area, None
            fc = fe.predict(horizon_days=horizon)
            return area, {
                "model": fc["model"],
                "mape":  fc["metrics"].get("mape", 0),
                "forecast_values": fc["forecast"]["values"][:3],
                "trend": "up" if fc["forecast"]["values"][-1] > fc["forecast"]["values"][0] else "down",
            }
        except Exception as exc:
            log.warning("Forecast failed for area %s: %s", area, exc)
            return area, None

    results = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for area, result in pool.map(_fit_area, top_areas):
            if result is not None:
                results[area] = result

    cache.set("forecast_by_area", ckey, results, ttl=900)
    return results


@router.post("/retrain")
def retrain_models(target: str = Query("units")):
    """Force retrain — deletes cached files and refits all models from scratch."""
    from backend.ml.forecasting.ensemble import MODELS_DIR
    import pathlib
    removed = []
    for suffix in ["_meta.json", f"_data.parquet",
                   "_prophet.pkl", "_lgbm.pkl", "_xgb.pkl", "_catboost.pkl"]:
        p = pathlib.Path(MODELS_DIR) / f"forecast_{target}{suffix}"
        if p.exists():
            p.unlink()
            removed.append(p.name)
    if target in _ensembles:
        del _ensembles[target]
    # Clear area-level cache for this target too
    for ck in [k for k in _area_ensembles if k.startswith(f"{target}:")]:
        del _area_ensembles[ck]
    fe = _get_ensemble(target)
    return {
        "status": "retrained",
        "target": target,
        "best_model": fe.best_model,
        "metrics": fe.metrics,
        "cache_cleared": removed,
    }


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
