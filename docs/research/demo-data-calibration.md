# Demo data calibration against real market data

The three demo tenants (`germany-demo`, `uae-demo`, `na-demo`) are synthetic. This note records how far their yearly volume path was from the real market, what was changed, and what is still unverified. Real data is used only to make the demo *plausible*; it says nothing about how accurate the forecasts would be for a real dealer group.

## What was wrong

Both generators build monthly volume as `YEAR_BASE × seasonal curve × macro response`. The Germany `YEAR_BASE` was already set to the real KBA totals, but the loaded data drifted far from it. Cause: the macro response (including a chip-shortage "scarcity" term) was normalised over the whole period, not within each year. In 2021 and 2022 it cut volume a second time, on top of a `YEAR_BASE` that already reflected the real fall. Fix in `scripts/generate_de_data.py` and `scripts/generate_uae_data.py`: normalise within each calendar year, so the macro response only moves deals between months and `YEAR_BASE` alone fixes each year's total.

## Year-on-year volume, before and after

| Market / year | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| **Germany, real (KBA / Destatis)** | -19.1% | -10.1% | +1.1% | +7.3% | -1.0% | +1.4% |
| Germany demo, before | -15.5% | -23.8% | -13.5% | +14.0% | +6.1% | +10.2% |
| Germany demo, after | -17.7% | -10.4% | -0.1% | +7.1% | +1.2% | +1.2% |
| **UAE, market (aggregator, see caveat)** | -30.5% | +28% | +2.7% | low confidence | low confidence | low confidence |
| UAE demo, before | -26.2% | +18.9% | -5.9% | +15.3% | +9.1% | +4.9% |
| UAE demo, after | -31.0% | +27.7% | +1.7% | +13.0% | +7.9% | +4.1% |
| **North America (US), real (BEA via FRED)** | -14.9% | +3.5% | -7.6% | +12.5% | +2.0% | +2.1% |
| NA demo (not changed) | -32.3% | +20.2% | -6.6% | +13.7% | +10.2% | +4.8% |

## Sources and confidence

- **Germany:** Kraftfahrt-Bundesamt annual balances (2020: 2.9 million, -19.1% vs 2019) and the Statistisches Bundesamt table (2021: 2,622.1k; 2022 +1.1%; 2023 +7.3%; 2024 -0.96%; 2025 +1.4%). High confidence.
- **UAE:** one aggregator (Statista): 2019 238,955 units; 2020 -30.5%; 2021 +28%; 2022 +2.7%. Those three years are internally consistent and are used. For 2023 onward, aggregators disagree (2024 is quoted as both about 269k and over 300k), so `YEAR_BASE` 2023 to 2026 is a conservative reading and **must be replaced with verified figures**. Low confidence.
- **United States:** FRED series `TOTALNSA` (all light vehicles, not seasonally adjusted), snapshot in `data/public/`. High confidence. It is the whole market, not one dealer group.
- 2026 is assumed flat on 2025 for Germany and UAE (no verified year-to-date data used).

## Still open

1. **`na-demo` in the database is still the old data** until the new America dataset is uploaded. `scripts/generate_us_data.py` now builds a US dealer group from the real monthly US market series (annual path within about 1.5 points of reality) and real macro series; `scripts/build_account_datasets.py` writes upload-ready sets for all three accounts to the untracked `Accounts-Datasets/` folder.
2. **Tracked sample CSVs are unchanged.** `data/samples/germany` still holds the old data (46 MB; regenerating it would add tens of MB to git history). The demo tenants in the local database were reloaded from freshly generated files; the repo samples were not.
3. **Only annual volume was calibrated.** Monthly seasonality was checked only for the US demo (correlation 0.90 with the real US monthly shape). Germany and UAE monthly shapes, price and discount levels, days in stock, brand mix and F&I attach rates are still the generator authors' assumptions, not verified against public data.
4. **A dealer group is not the market.** A 24-rooftop group can outgrow or trail its market. The demo now tracks the market within about 1 to 2 points a year, which is a reasonable default, not a fact about any real group.
