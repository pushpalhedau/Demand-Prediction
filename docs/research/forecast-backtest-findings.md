# What the public-data backtest tells us

Full tables: [forecast-backtest-public-data.md](forecast-backtest-public-data.md) (regenerate with `python scripts/backtest_public_data.py`). Method: rolling origin, 74 origins every 3 months from Dec 2007 to Jun 2026; each model sees only earlier data and forecasts 12 months ahead; error is WAPE (total absolute error / total actual). Data: four real US monthly series (all light vehicles, autos, trucks, used-car dealer retail sales), not seasonally adjusted.

## Findings

1. **"Same month last year" is a hard baseline to beat.** On aggregate market data it is off by roughly 9 to 14% at 1 to 12 months ahead, and 8 to 12% on next-quarter totals. Nothing tested was dramatically better.
2. **The platform's current Prophet setup (all history, default settings) is worse than that baseline in normal times**: 15.5% vs 7.1% in the steady 2010-2019 market on all light vehicles, 18.5% vs 10.7% on autos, 19.9% vs 9.0% on trucks. It only matches the baseline on used-car dealer sales. Fitting it on all history since 1976 lets old regimes drag the trend.
3. **Limiting Prophet to the last 10 years fixes most of that** (`prophet_recent`): next-quarter error 8.5% vs 9.0% (all vehicles), 8.3% vs 10.4% (trucks), 11.1% vs 12.1% (autos), 6.9% vs 8.2% (used cars). It is still worse than the baseline in the steady 2010-2019 stretch on all vehicles (9.9% vs 7.1%).
4. **It is much better in shocks**: during 2020-2021 it was 12.0% vs 20.7% (all vehicles), 14.9% vs 29.2% (autos), 13.7% vs 19.5% (trucks). So the value of a modelled forecast shows up when conditions change, and the cost is a bit of accuracy when they don't.
5. **Nobody predicted 2008-2009.** Every model on the vehicle-sales series was 22 to 43% off at that point (the used-car series 14 to 19%). A forecast cannot see a crash coming; the product should not imply that it can.
6. **The confidence bands are too narrow.** A 95% band should contain the actual value about 95% of the time. At one month ahead it was close for all vehicles and autos (85 to 95%) but already low for trucks and used-car sales (64 to 85%). By 3 to 12 months ahead it contained the actual only about 65 to 74% of the time on all vehicles, and as little as 44% (trucks) and 37% (used-car sales). Showing a "95% range" that is really about a 65% range gives false comfort.

## Reading the code, two related issues

- The model's built-in "accuracy" (`train_prophet_model` in `backend/ml/demand_forecast.py`) is `1 - MAE / mean` on one 30-day daily holdout, using the *actual* macro values for that window. Daily noise and one window make it unstable, and using true future regressor values flatters it. It should not be quoted as accuracy.
- The forecast runs at daily grain, which this backtest did not test (no public daily data). Dealers plan monthly and quarterly, so monthly is the right level to prove first.

## What this does and does not show

- It is **US market-level** data, not a dealer group. A single dealer group has smaller, noisier numbers, so errors will be higher. It says the engine is sound at a market level, not that any customer's forecast is X% accurate.
- The macro regressors (fuel, rates, incentives) were **not** tested. Testing them properly needs their future values, which are not known at forecast time.
- Germany and UAE were not backtested (no free monthly series was reachable).

## Recommended changes (not built yet; your call)

1. **Per-account champion and challenger.** On every import, run this rolling backtest on the account's own monthly history, pick the best of seasonal baseline, seasonal-with-trend, and recent-window Prophet, and use that for the forecast. This also protects against the case where Prophet loses.
2. **Honest ranges.** Build the interval from the backtest's own error distribution instead of Prophet's default band, so a "95% range" is about 95%.
3. **Show measured accuracy on screen**, per account: "in the last N months, next-quarter totals were within X% of actual", or "not enough history yet".
4. **Stop showing the current "accuracy" figure**, or relabel it.
