"""
The Demand Forecast tab as data: a baseline model turned into a whole-calendar-month forecast window with its
confidence range, seasonality, and the effect of any what-if market conditions.

The window starts at the first month that is not yet fully booked (if today is 21 Aug it opens on 1 Aug, and that
month's total is what is booked so far plus the projection for the rest of it). That keeps the chart, the headline
number and the "next N months" wording in agreement.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.analytics.what_if import LOAN_MONTHS, net_response_pct
from backend.ml.demand_forecast import get_external_factor_stats, train_prophet_model

CONFIDENCE_LEVEL = 0.80
# Summing a model's daily bounds over a month assumes every day's error moves the same way. They partly cancel, so the
# monthly total is far less uncertain than that sum implies: shrink the half-width toward the sqrt-of-N scaling.
_BAND_SHRINK = 0.55

# The levers a dealer GM can reason about; each maps to a real column of the tenant's external factors.
LEVERS = {
    "crude_oil_price_usd": {"unit": "usd_per_barrel", "step": 1.0},
    "petrol_price_per_litre": {"unit": "per_litre", "step": None},
    "diesel_price_per_litre": {"unit": "per_litre", "step": None},
    "auto_loan_apr_pct": {"unit": "percent", "step": 0.10},
}


def lever_ranges(region: str | None) -> list[dict]:
    """Each available lever with its current value and a sensible slider range."""
    stats = get_external_factor_stats(region=region)
    out = []
    for key, cfg in LEVERS.items():
        if key not in stats:
            continue
        s = stats[key]
        lo = round(max(0.0, s["min"] - (s["max"] - s["min"]) * 0.2), 2)
        hi = round(s["max"] + (s["max"] - s["min"]) * 0.2, 2)
        if hi <= lo:
            hi = lo + max((cfg["step"] or 0.05) * 5, 1.0)
        out.append({"key": key, "unit": cfg["unit"], "current": float(s["last"]), "min": lo, "max": hi,
                    "step": float(cfg["step"] or max(round(s["last"] * 0.02, 2), 0.01))})
    return out


def _window(hist: pd.DataFrame, horizon_months: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    data_end = hist["ds"].max()
    month_end = (data_end + pd.offsets.MonthEnd(0)).normalize()
    start = (data_end + pd.Timedelta(days=1)).normalize() if data_end >= month_end else data_end.normalize().replace(day=1)
    return start, start + pd.DateOffset(months=horizon_months) - pd.Timedelta(days=1)


def build(*, filters: dict, target: str, horizon_months: int, brand: str | None, overrides: dict | None,
          average_loan: float) -> dict:
    region, category, fuel = filters.get("region"), filters.get("vehicle_category"), filters.get("fuel_type")
    result, error = train_prophet_model(
        category=category, region=region, fuel_type=fuel, brand=brand, target=target,
        horizon_days=horizon_months * 31 + 15, interval_width=CONFIDENCE_LEVEL, use_sentiment=False,
        market_overrides=None,
    )
    if error:
        return {"status": "no_data" if "No data" in error else "insufficient_history"}

    fc = result["forecast"].copy()
    fc["ds"] = pd.to_datetime(fc["ds"])

    factor_stats = get_external_factor_stats(region=region)
    net_pct = net_response_pct(overrides, factor_stats)
    future_mask = fc["actual"].isnull()
    if abs(net_pct) >= 0.1:
        multiplier = float(np.clip(1 + net_pct / 100.0, 0.4, 2.5))
        for col in ("yhat", "yhat_lower", "yhat_upper"):
            fc.loc[future_mask, col] = (fc.loc[future_mask, col] * multiplier).clip(lower=0)

    hist = fc[fc["actual"].notna()].copy()
    future = fc[fc["actual"].isnull()].copy()
    if future.empty or hist.empty:
        return {"status": "insufficient_history"}

    start, end = _window(hist, horizon_months)
    future_in = future[(future["ds"] >= start) & (future["ds"] <= end)]
    booked_in = hist[(hist["ds"] >= start) & (hist["ds"] <= end)]
    if future_in.empty:
        return {"status": "horizon_too_short"}

    def month_totals(col: str) -> pd.Series:
        booked = booked_in.set_index("ds")["actual"].resample("MS").sum() if not booked_in.empty else pd.Series(dtype=float)
        return future_in.set_index("ds")[col].resample("MS").sum().add(booked, fill_value=0.0)

    mid, lo, hi = month_totals("yhat"), month_totals("yhat_lower"), month_totals("yhat_upper")
    window = pd.DataFrame({
        "expected": mid,
        "low": (mid - (mid - lo) * _BAND_SHRINK).clip(lower=0),
        "high": mid + (hi - mid) * _BAND_SHRINK,
    })
    expected, low, high = (float(window[c].sum()) for c in ("expected", "low", "high"))

    year_ago = hist[(hist["ds"] >= start - pd.DateOffset(years=1)) & (hist["ds"] <= end - pd.DateOffset(years=1))]["actual"].sum()
    yoy = (expected / float(year_ago) - 1) * 100 if year_ago > 0 else None
    trailing = float(hist[hist["ds"] >= start - pd.DateOffset(months=12)]["actual"].sum()) / 12
    run_rate = expected / horizon_months
    run_rate_delta = (run_rate / trailing - 1) * 100 if trailing > 0 else None

    history = hist.set_index("ds")["actual"].resample("MS").sum()
    history = history[history.index < start].tail(13)

    seasonality: dict = {"monthly": None, "weekly": None}
    if "yearly" in fc.columns:
        by_month = fc.groupby(fc["ds"].dt.month)["yearly"].mean()
        seasonality["monthly"] = [{"month": m, "effect": float(by_month.get(m, 0.0))} for m in range(1, 13)]
    if "weekly" in fc.columns:
        by_day = fc.groupby(fc["ds"].dt.dayofweek)["weekly"].mean()
        seasonality["weekly"] = [{"day": d, "effect": float(by_day.get(d, 0.0))} for d in range(7)]

    return {
        "status": "ok",
        "target": target,
        "horizon_months": horizon_months,
        "window": {"start": start, "end": end},
        "headline": {"expected": expected, "low": low, "high": high, "yoy_pct": yoy, "run_rate": run_rate,
                     "run_rate_delta_pct": run_rate_delta, "confidence_pct": int(CONFIDENCE_LEVEL * 100)},
        "history": [{"x": d, "y": float(v)} for d, v in history.items()],
        "forecast": [{"x": d, "expected": float(r.expected), "low": float(r.low), "high": float(r.high)}
                     for d, r in window.iterrows()],
        "busiest_month": int(window["expected"].idxmax().month),
        "seasonality": seasonality,
        "what_if": {
            "net_pct": net_pct,
            "active": bool(overrides) and abs(net_pct) >= 0.1,
            "value_shift": abs(expected - expected / (1 + net_pct / 100)) if abs(net_pct) >= 0.1 else 0.0,
            "average_loan": average_loan,
            "loan_months": LOAN_MONTHS,
        },
    }
