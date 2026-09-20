"""
Rolling-origin forecast backtesting on a monthly series.

For each origin month the model sees ONLY the history up to it, forecasts the next `horizon` months, and the
forecasts are scored against what really happened. Every model is compared with plain seasonal baselines: a forecast
that cannot beat "same month last year" is not worth a customer's trust.

Pure functions over a pandas Series (month-start DatetimeIndex): no database, so the same code scores public market
data today and a customer's own sales history later.
"""
from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

MODELS = ("seasonal_naive", "seasonal_drift", "prophet", "prophet_multiplicative", "prophet_recent")
RECENT_MONTHS = 120
BASELINE = "seasonal_naive"


def _seasonal_naive(train: pd.Series, horizon: int) -> np.ndarray:
    values = train.to_numpy(dtype=float)
    return np.array([values[len(values) + h - 1 - 12 * math.ceil(h / 12)] for h in range(1, horizon + 1)])


def _seasonal_drift(train: pd.Series, horizon: int) -> np.ndarray:
    """Seasonal naive scaled by the latest year-on-year change (clipped, so one odd year cannot run away)."""
    values = train.to_numpy(dtype=float)
    ratio = values[-12:].sum() / values[-24:-12].sum() if len(values) >= 24 and values[-24:-12].sum() > 0 else 1.0
    return _seasonal_naive(train, horizon) * float(np.clip(ratio, 0.7, 1.3))


def _prophet(train: pd.Series, horizon: int, multiplicative: bool, window: int | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    from prophet import Prophet

    if window:
        train = train.iloc[-window:]      # old regimes can drag a flexible trend the wrong way

    for name in ("cmdstanpy", "prophet"):
        logging.getLogger(name).setLevel(logging.ERROR)
    model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False, interval_width=0.95,
                    seasonality_mode="multiplicative" if multiplicative else "additive")
    model.fit(pd.DataFrame({"ds": train.index, "y": train.to_numpy(dtype=float)}))
    forecast = model.predict(model.make_future_dataframe(periods=horizon, freq="MS")).tail(horizon)
    return forecast["yhat"].to_numpy(), forecast["yhat_lower"].to_numpy(), forecast["yhat_upper"].to_numpy()


def forecast_with(model: str, train: pd.Series, horizon: int):
    """(forecast, lower, upper) for one model; baselines have no interval, so lower/upper are NaN."""
    nan = np.full(horizon, np.nan)
    if model == "seasonal_naive":
        return _seasonal_naive(train, horizon), nan, nan
    if model == "seasonal_drift":
        return _seasonal_drift(train, horizon), nan, nan
    if model in ("prophet", "prophet_multiplicative"):
        return _prophet(train, horizon, multiplicative=(model == "prophet_multiplicative"))
    if model == "prophet_recent":
        return _prophet(train, horizon, multiplicative=True, window=RECENT_MONTHS)
    raise ValueError(f"unknown model {model!r}")


def rolling_backtest(series: pd.Series, *, horizon: int = 12, min_train: int = 60, step: int = 3,
                     first_origin: str | None = None, models: tuple[str, ...] = MODELS) -> pd.DataFrame:
    """
    One row per (model, origin, horizon): the forecast made from `origin` (the last month the model saw) for a month
    `horizon` steps later, and the actual. Origins advance `step` months; the model never sees past its origin.
    """
    series = series.dropna().sort_index()
    if len(series) < min_train + 1:
        raise ValueError(f"need at least {min_train + 1} months, have {len(series)}")
    start = max(min_train, series.index.get_loc(pd.Timestamp(first_origin)) + 1) if first_origin else min_train
    rows = []
    for end in range(start, len(series), step):            # `end` = number of months of history the model may use
        train, future = series.iloc[:end], series.iloc[end:end + horizon]
        h = len(future)
        for model in models:
            fc, lo, hi = forecast_with(model, train, h)
            for i in range(h):
                rows.append((model, train.index[-1], i + 1, future.index[i], float(future.iloc[i]),
                             float(fc[i]), float(lo[i]), float(hi[i])))
    return pd.DataFrame(rows, columns=["model", "origin", "horizon", "target", "actual", "forecast", "lower", "upper"])


def summarize(results: pd.DataFrame, by: str = "horizon") -> pd.DataFrame:
    """
    Per model and `by` group: WAPE (total absolute error / total actual), bias (signed, + = over-forecast) and,
    where the model gives an interval, how often the actual really fell inside it (a 95% band should cover ~95%).
    """
    df = results.assign(err=lambda d: d["forecast"] - d["actual"], abs_err=lambda d: (d["forecast"] - d["actual"]).abs())
    df["inside"] = ((df["actual"] >= df["lower"]) & (df["actual"] <= df["upper"])).where(df["lower"].notna())
    grouped = df.groupby(["model", by])
    out = pd.DataFrame({
        "n": grouped.size(),
        "wape": grouped["abs_err"].sum() / grouped["actual"].sum(),
        "bias": grouped["err"].sum() / grouped["actual"].sum(),
        "coverage": grouped["inside"].mean(),
    }).reset_index()
    return out


def quarter_errors(results: pd.DataFrame) -> pd.DataFrame:
    """Error on the next-3-months TOTAL from each origin: the number a dealer actually plans a quarter on."""
    q = results[results["horizon"] <= 3]
    full = q.groupby(["model", "origin"]).filter(lambda g: len(g) == 3)
    totals = full.groupby(["model", "origin"])[["actual", "forecast"]].sum().reset_index()
    totals["abs_err"] = (totals["forecast"] - totals["actual"]).abs()
    totals["err"] = totals["forecast"] - totals["actual"]
    grouped = totals.groupby("model")
    return pd.DataFrame({"n": grouped.size(), "wape": grouped["abs_err"].sum() / grouped["actual"].sum(),
                         "bias": grouped["err"].sum() / grouped["actual"].sum()}).reset_index()


def skill_vs_baseline(summary: pd.DataFrame, by: str = "horizon") -> pd.DataFrame:
    """1 - WAPE(model)/WAPE(seasonal naive): positive means it beats 'same month last year', negative means it loses."""
    base = summary[summary["model"] == BASELINE].set_index(by)["wape"]
    out = summary[summary["model"] != BASELINE].copy()
    out["skill"] = 1 - out["wape"] / out[by].map(base)
    return out
