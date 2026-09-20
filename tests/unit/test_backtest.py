import numpy as np
import pandas as pd
import pytest

from backend.ml import backtest as bt


def _series(values, start="2015-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"), dtype=float)


def _seasonal(years=8, growth=1.0):
    base = np.array([80, 85, 110, 100, 105, 108, 95, 90, 102, 99, 88, 130], dtype=float)
    values = np.tile(base, years)
    return _series(values * growth ** (np.arange(len(values)) / 12))


def test_seasonal_naive_repeats_the_same_month_last_year():
    s = _seasonal(3)
    fc = bt._seasonal_naive(s.iloc[:30], 12)          # history ends in June of year 3
    assert fc[0] == s.iloc[30 - 12]                   # July forecast = last July
    assert list(fc) == [s.iloc[30 - 12 + i] for i in range(12)]


def test_seasonal_naive_is_exact_on_a_perfectly_repeating_series():
    results = bt.rolling_backtest(_seasonal(6), horizon=6, min_train=24, step=5, models=("seasonal_naive",))
    assert (results["forecast"] - results["actual"]).abs().max() == 0


def test_seasonal_drift_follows_steady_growth_better_than_plain_naive():
    results = bt.rolling_backtest(_seasonal(8, growth=1.10), horizon=12, min_train=36, step=6,
                                  models=("seasonal_naive", "seasonal_drift"))
    err = (results["forecast"] - results["actual"]).abs().groupby(results["model"]).sum()
    wape = err / results["actual"].groupby(results["model"]).sum()
    assert wape["seasonal_drift"] < wape["seasonal_naive"] * 0.4


def test_a_forecast_never_sees_data_after_its_origin(monkeypatch):
    s = _seasonal(6)
    seen = []

    def spy(model, train, horizon):
        seen.append(train.index[-1])
        return np.zeros(horizon), np.full(horizon, np.nan), np.full(horizon, np.nan)

    monkeypatch.setattr(bt, "forecast_with", spy)
    results = bt.rolling_backtest(s, horizon=6, min_train=30, step=4, models=("seasonal_naive",))
    for origin, group in results.groupby("origin"):
        assert origin in seen and (group["target"] > origin).all()


def test_horizon_is_truncated_at_the_end_of_the_data_not_padded():
    results = bt.rolling_backtest(_seasonal(4), horizon=12, min_train=40, step=3, models=("seasonal_naive",))
    assert results["target"].max() == _seasonal(4).index[-1]
    assert results.groupby("origin")["horizon"].max().min() >= 1


def test_summary_metrics_and_coverage():
    df = pd.DataFrame({"model": "m", "horizon": 1, "origin": pd.Timestamp("2020-01-01"), "target": pd.Timestamp("2020-02-01"),
                       "actual": [100.0, 100.0, 100.0, 100.0], "forecast": [110.0, 90.0, 100.0, 120.0],
                       "lower": [95.0, 95.0, 95.0, 105.0], "upper": [115.0, 115.0, 115.0, 130.0]})
    row = bt.summarize(df).iloc[0]
    assert row["wape"] == pytest.approx(40 / 400) and row["bias"] == pytest.approx(20 / 400)
    assert row["coverage"] == pytest.approx(0.75)      # the last actual (100) is below its band (105..130)


def test_skill_is_positive_when_a_model_beats_the_baseline():
    summary = pd.DataFrame({"model": ["seasonal_naive", "prophet"], "horizon": [1, 1], "wape": [0.10, 0.05]})
    out = bt.skill_vs_baseline(summary)
    assert out.iloc[0]["skill"] == pytest.approx(0.5)


def test_quarter_errors_only_score_complete_quarters():
    results = bt.rolling_backtest(_seasonal(6), horizon=12, min_train=30, step=6, models=("seasonal_naive",))
    q = bt.quarter_errors(results)
    assert q.iloc[0]["wape"] == 0 and q.iloc[0]["n"] >= 1


def test_prophet_produces_a_usable_forecast_and_interval():
    train = _seasonal(6)
    fc, lo, hi = bt.forecast_with("prophet", train, 6)
    assert len(fc) == 6 and (lo <= fc).all() and (fc <= hi).all()
    assert abs(fc.sum() - train.iloc[:6].sum()) / train.iloc[:6].sum() < 0.15


def test_unknown_model_is_rejected():
    with pytest.raises(ValueError):
        bt.forecast_with("crystal_ball", _seasonal(3), 3)


def test_prophet_recent_only_uses_the_latest_window(monkeypatch):
    seen = {}
    real = bt._prophet

    def spy(train, horizon, multiplicative, window=None):
        seen["window"] = window
        return real(train, horizon, multiplicative, window)

    monkeypatch.setattr(bt, "_prophet", spy)
    bt.forecast_with("prophet_recent", _seasonal(12), 3)
    assert seen["window"] == bt.RECENT_MONTHS
