# Forecast backtest on public market data

Generated 2026-09-20 by `scripts/backtest_public_data.py`. Data: US Bureau of Economic Analysis / Census series via FRED (snapshots in `data/public/`).


## TOTALNSA: All light vehicles sold (thousand units, not seasonally adjusted)

Origins: Dec 2007 to Jun 2026, every 3 months.

**Error by forecast horizon (WAPE: total absolute error / total actual; lower is better)**

| horizon | seasonal_naive | seasonal_drift | prophet | prophet_multiplicative | prophet_recent |
|---|---|---|---|---|---|
| 1 | 9.2% | 8.5% | 12.9% | 12.6% | 8.7% |
| 3 | 11.4% | 11.5% | 15.7% | 15.8% | 10.2% |
| 6 | 11.4% | 12.5% | 16.7% | 16.8% | 11.5% |
| 12 | 11.0% | 12.1% | 18.1% | 18.4% | 13.5% |

**Skill vs 'same month last year' (positive = better than that baseline, negative = worse)**

| horizon | prophet | prophet_multiplicative | prophet_recent | seasonal_drift |
|---|---|---|---|---|
| 1 | -40.3% | -36.8% | 4.9% | 7.1% |
| 3 | -37.1% | -38.3% | 11.0% | -0.5% |
| 6 | -46.6% | -47.6% | -0.5% | -9.2% |
| 12 | -64.0% | -67.2% | -22.3% | -9.8% |

**Next-quarter total (what a dealer plans on)**

| model | quarter WAPE | quarter bias | origins |
|---|---|---|---|
| prophet | 13.3% | 0.2% | 74 |
| prophet_multiplicative | 13.4% | 0.1% | 74 |
| prophet_recent | 8.5% | -0.3% | 74 |
| seasonal_drift | 8.6% | 0.6% | 74 |
| seasonal_naive | 9.0% | -0.0% | 74 |

**Error by market regime, all horizons pooled**

| period (origin dates) | seasonal_naive | seasonal_drift | prophet | prophet_multiplicative | prophet_recent | origins |
|---|---|---|---|---|---|---|
| 2008-2009 financial crisis | 25.6% | 28.8% | 39.3% | 39.2% | 26.9% | 8 |
| 2010-2019 steady market | 7.1% | 6.0% | 15.5% | 15.6% | 9.9% | 40 |
| 2020-2021 COVID and chip shortage | 20.7% | 22.9% | 18.0% | 17.3% | 12.0% | 8 |
| 2022 onward | 7.2% | 10.4% | 5.5% | 5.4% | 8.9% | 18 |

**How often the actual fell inside Prophet's 95% band (should be about 95%)**

| horizon | prophet | prophet_multiplicative | prophet_recent |
|---|---|---|---|
| 1 | 92.0% | 92.0% | 85.3% |
| 3 | 73.0% | 74.3% | 73.0% |
| 6 | 71.2% | 71.2% | 65.8% |
| 12 | 67.6% | 64.8% | 66.2% |

## LAUTONSA: Light-weight autos sold (thousand units, NSA)

Origins: Dec 2007 to Jun 2026, every 3 months.

**Error by forecast horizon (WAPE: total absolute error / total actual; lower is better)**

| horizon | seasonal_naive | seasonal_drift | prophet | prophet_multiplicative | prophet_recent |
|---|---|---|---|---|---|
| 1 | 12.4% | 10.0% | 18.8% | 18.3% | 11.0% |
| 3 | 13.4% | 12.1% | 20.5% | 19.2% | 12.7% |
| 6 | 13.6% | 13.4% | 21.8% | 20.7% | 15.4% |
| 12 | 13.5% | 14.0% | 24.2% | 23.1% | 19.5% |

**Skill vs 'same month last year' (positive = better than that baseline, negative = worse)**

| horizon | prophet | prophet_multiplicative | prophet_recent | seasonal_drift |
|---|---|---|---|---|
| 1 | -51.3% | -46.9% | 11.1% | 19.5% |
| 3 | -52.8% | -43.1% | 5.2% | 10.2% |
| 6 | -60.8% | -52.6% | -13.0% | 1.4% |
| 12 | -79.3% | -71.4% | -44.4% | -3.8% |

**Next-quarter total (what a dealer plans on)**

| model | quarter WAPE | quarter bias | origins |
|---|---|---|---|
| prophet | 19.0% | 5.6% | 74 |
| prophet_multiplicative | 18.2% | 5.5% | 74 |
| prophet_recent | 11.1% | 0.8% | 74 |
| seasonal_drift | 10.0% | 1.1% | 74 |
| seasonal_naive | 12.1% | 5.1% | 74 |

**Error by market regime, all horizons pooled**

| period (origin dates) | seasonal_naive | seasonal_drift | prophet | prophet_multiplicative | prophet_recent | origins |
|---|---|---|---|---|---|---|
| 2008-2009 financial crisis | 24.7% | 29.6% | 27.3% | 27.8% | 22.2% | 8 |
| 2010-2019 steady market | 10.7% | 7.9% | 18.5% | 18.1% | 14.2% | 40 |
| 2020-2021 COVID and chip shortage | 29.2% | 26.6% | 55.0% | 55.3% | 14.9% | 8 |
| 2022 onward | 9.3% | 14.0% | 20.1% | 14.5% | 16.1% | 18 |

**How often the actual fell inside Prophet's 95% band (should be about 95%)**

| horizon | prophet | prophet_multiplicative | prophet_recent |
|---|---|---|---|
| 1 | 93.3% | 94.7% | 89.3% |
| 3 | 90.5% | 90.5% | 82.4% |
| 6 | 89.0% | 90.4% | 68.5% |
| 12 | 81.7% | 80.3% | 62.0% |

## LTRUCKNSA: Light-weight trucks sold (thousand units, NSA)

Origins: Dec 2007 to Jun 2026, every 3 months.

**Error by forecast horizon (WAPE: total absolute error / total actual; lower is better)**

| horizon | seasonal_naive | seasonal_drift | prophet | prophet_multiplicative | prophet_recent |
|---|---|---|---|---|---|
| 1 | 10.2% | 9.7% | 15.1% | 14.1% | 9.0% |
| 3 | 12.8% | 12.4% | 16.8% | 16.9% | 10.2% |
| 6 | 12.7% | 13.3% | 18.2% | 18.2% | 11.3% |
| 12 | 12.2% | 12.7% | 20.3% | 20.3% | 12.8% |

**Skill vs 'same month last year' (positive = better than that baseline, negative = worse)**

| horizon | prophet | prophet_multiplicative | prophet_recent | seasonal_drift |
|---|---|---|---|---|
| 1 | -47.4% | -37.5% | 11.6% | 5.2% |
| 3 | -31.3% | -32.5% | 20.2% | 3.0% |
| 6 | -43.7% | -43.7% | 10.8% | -4.6% |
| 12 | -65.9% | -66.3% | -4.7% | -3.9% |

**Next-quarter total (what a dealer plans on)**

| model | quarter WAPE | quarter bias | origins |
|---|---|---|---|
| prophet | 14.4% | -1.3% | 74 |
| prophet_multiplicative | 14.5% | -1.1% | 74 |
| prophet_recent | 8.3% | -1.3% | 74 |
| seasonal_drift | 9.1% | 0.8% | 74 |
| seasonal_naive | 10.4% | -2.7% | 74 |

**Error by market regime, all horizons pooled**

| period (origin dates) | seasonal_naive | seasonal_drift | prophet | prophet_multiplicative | prophet_recent | origins |
|---|---|---|---|---|---|---|
| 2008-2009 financial crisis | 28.8% | 30.2% | 43.4% | 42.7% | 30.7% | 8 |
| 2010-2019 steady market | 9.0% | 6.6% | 19.9% | 19.6% | 9.6% | 40 |
| 2020-2021 COVID and chip shortage | 19.5% | 22.7% | 18.3% | 18.1% | 13.7% | 8 |
| 2022 onward | 7.6% | 10.2% | 6.6% | 5.9% | 7.4% | 18 |

**How often the actual fell inside Prophet's 95% band (should be about 95%)**

| horizon | prophet | prophet_multiplicative | prophet_recent |
|---|---|---|---|
| 1 | 69.3% | 69.3% | 85.3% |
| 3 | 45.9% | 48.6% | 68.9% |
| 6 | 45.2% | 47.9% | 64.4% |
| 12 | 43.7% | 36.6% | 63.4% |

## MRTSSM44112USN: Used-car dealers retail sales (million USD, NSA; includes price inflation)

Origins: Dec 2007 to Jun 2026, every 3 months.

**Error by forecast horizon (WAPE: total absolute error / total actual; lower is better)**

| horizon | seasonal_naive | seasonal_drift | prophet | prophet_multiplicative | prophet_recent |
|---|---|---|---|---|---|
| 1 | 9.2% | 8.7% | 8.4% | 8.2% | 7.1% |
| 3 | 9.6% | 10.4% | 10.2% | 9.0% | 8.5% |
| 6 | 9.6% | 12.1% | 10.9% | 9.7% | 9.6% |
| 12 | 9.6% | 13.2% | 12.4% | 11.3% | 12.3% |

**Skill vs 'same month last year' (positive = better than that baseline, negative = worse)**

| horizon | prophet | prophet_multiplicative | prophet_recent | seasonal_drift |
|---|---|---|---|---|
| 1 | 8.8% | 10.6% | 23.2% | 5.2% |
| 3 | -7.0% | 5.8% | 10.5% | -9.2% |
| 6 | -13.4% | -0.3% | 0.1% | -25.5% |
| 12 | -28.6% | -16.7% | -27.4% | -36.5% |

**Next-quarter total (what a dealer plans on)**

| model | quarter WAPE | quarter bias | origins |
|---|---|---|---|
| prophet | 8.3% | -0.3% | 74 |
| prophet_multiplicative | 8.0% | 0.1% | 74 |
| prophet_recent | 6.9% | 0.8% | 74 |
| seasonal_drift | 8.2% | 0.4% | 74 |
| seasonal_naive | 8.2% | -4.4% | 74 |

**Error by market regime, all horizons pooled**

| period (origin dates) | seasonal_naive | seasonal_drift | prophet | prophet_multiplicative | prophet_recent | origins |
|---|---|---|---|---|---|---|
| 2008-2009 financial crisis | 13.9% | 18.4% | 18.9% | 19.1% | 18.5% | 8 |
| 2010-2019 steady market | 7.6% | 6.7% | 7.8% | 7.1% | 5.9% | 40 |
| 2020-2021 COVID and chip shortage | 18.7% | 23.0% | 16.2% | 15.5% | 16.0% | 8 |
| 2022 onward | 5.5% | 9.2% | 9.1% | 8.5% | 9.8% | 18 |

**How often the actual fell inside Prophet's 95% band (should be about 95%)**

| horizon | prophet | prophet_multiplicative | prophet_recent |
|---|---|---|---|
| 1 | 73.3% | 64.0% | 74.7% |
| 3 | 52.7% | 59.5% | 60.8% |
| 6 | 46.6% | 56.2% | 61.6% |
| 12 | 36.6% | 40.8% | 52.1% |
