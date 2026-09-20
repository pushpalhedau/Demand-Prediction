# Public reference data

Monthly US vehicle-market series downloaded from FRED (Federal Reserve Bank of St. Louis), snapshot 2026-09-20. Used only to backtest forecasting methods and to sanity-check the demo data; never mixed into customer data.

| File | Series | Source |
|---|---|---|
| `TOTALNSA.csv` | Light weight vehicle sales: total, not seasonally adjusted (thousand units) | U.S. Bureau of Economic Analysis |
| `LAUTONSA.csv` | Light weight vehicle sales: autos, NSA (thousand units) | U.S. Bureau of Economic Analysis |
| `LTRUCKNSA.csv` | Light weight vehicle sales: trucks, NSA (thousand units) | U.S. Bureau of Economic Analysis |
| `MRTSSM44112USN.csv` | Retail sales: used car dealers, NSA (million USD) | U.S. Census Bureau |

Refresh with `python scripts/backtest_public_data.py --refresh`. `backtest_*.csv` files are generated output and are not tracked.
