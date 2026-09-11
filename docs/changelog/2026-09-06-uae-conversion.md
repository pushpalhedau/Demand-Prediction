# 2026-09-06 — UAE conversion (NA-version → UAE-version2)

Re-localised the whole platform from the North America (US, 8-state) dealer-group
model to a **UAE dealer group of 24 rooftops across the seven emirates**. The
product shape is unchanged — same tabs, same models, same mechanics — only the
market, the data and the labelling changed.

## Decisions (stakeholder-confirmed)

1. **It is a dealer-group product, not an OEM/market tool** — carried over
   unchanged from the NA build. Every figure is the group's own booked retail
   sales; no market extrapolation.
2. **Tariff / import-vs-domestic analysis dropped entirely.** There is no
   domestic UAE car industry; every vehicle is imported and pays the same flat
   5% GCC customs duty, always inside the retail price. Comparative Analytics is
   now a single "How we're tracking vs last year" view; the `Sale.tariff_cost`
   column, the Section 232 pass-through in the generator, the four tariff
   queries, and the tariff component of `analytics/yoy_attribution.py` are gone.
3. **`nationality` re-introduced.** The UAE resident base is ~88% expatriate, so
   nationality / residency is a first-class market-segmentation dimension (no
   ECOA equivalent). It is generated, stored, and surfaced descriptively in
   Customer Intelligence. KMeans clusters on behavioural / financial features
   plus `years_in_uae` (residency tenure); nationality itself is not a
   clustering feature (one-hot of ~18 nationalities would swamp the metric) and
   is kept OUT of the per-lead XGBoost close score.
4. **Income is monthly AED** (`estimated_monthly_income_aed`,
   `monthly_income_bracket`) — the Gulf salary norm.
5. **Brand catalog swapped to the UAE market mix** — Toyota-led, plus Nissan,
   Mitsubishi, Hyundai, Kia, Honda, MG, Chevrolet, Lexus, Ford, Mercedes-Benz,
   BMW, Land Rover, Mazda, Suzuki. Top nameplates: Land Cruiser, Patrol, Prado,
   Hilux, Corolla, Camry, Sunny, Pajero. Real GCC-market specs (`price_aed`,
   `mileage_kmpl`, `range_km`), real trim ladders (GXR / VXR / GLX …). Toyota /
   Honda / Lexus hybrids added; EV adoption curve steepened (Dubai/Abu Dhabi
   policy, no purchase credit to expire).

## Data / schema

- **New generator:** `preprocessing/generate_uae_data.py` (replaces
  `generate_na_data.py`). Seeded, deterministic. 7 emirates weighted
  Dubai 42 / Abu Dhabi 30 / Sharjah 17 / rest ~11. Real anchors: CBUAE base
  rate, UAE regulated petrol (Special 95, AED/litre), Brent crude, UAE CPI /
  GDP, Dubai residential price index, Dubai tourism index, real Ramadan / Eid
  windows 2019-2026, UAE National Day (Dec), Dubai Shopping Festival (Jan),
  Dubai International Motor Show (Nov, biennial). UAE weekend (Sat-Sun) DOW
  shape; summer trough, cool-season peak.
- **Schema renames** (`database/models.py`): `state`→`emirate`, `city`→`area`,
  `zip_code`→`po_box`, all `*_usd`→`*_aed`, `sales_tax_amount_usd`→
  `vat_amount_aed`, `total_revenue_*_tax`→`*_vat`, `mpg`→`mileage_kmpl`,
  `range_miles`→`range_km`, `ev_incentive_eligible`→`gcc_spec`,
  `holiday_period`→`festival_period`, `income_bracket`→`monthly_income_bracket`,
  `estimated_annual_income_usd`→`estimated_monthly_income_aed`,
  `years_at_address`→`years_in_uae`, `us_fed_rate_pct`→`cbuae_rate_pct`,
  `gasoline_*_usd_per_gallon`→`petrol_9{5,8}_price_aed_per_litre`,
  `diesel_usd_per_gallon`→`diesel_price_aed_per_litre`,
  `wti_crude_price_usd`→`crude_oil_price_usd`, `home_price_index`→
  `dubai_re_price_index`, `avg_sales_tax_pct`→`vat_rate_pct`, `tariff_pct`→
  `import_duty_pct` (constant 5), `ev_charging_stations`→
  `ev_charging_stations_uae`, `holiday_season_month`→`ramadan_month`,
  `july_4th_month`→`national_day_month`, `detroit_auto_show_month`→
  `dubai_motor_show_month`, `la_auto_show_month`→`dsf_month`. `Sale.tariff_cost_usd`
  removed.
- **Reseed:** `python -m preprocessing.generate_uae_data` then
  `rm real_demand.db automobile_demand.db` and re-run both seeders. ML artifacts
  retrained for both modes (`models/{clustering,xgboost}/{real,test}/`).

## Modules touched

`database/queries.py` (tariff block + deprecated share queries removed,
`get_fed_rate_kpi`→`get_cbuae_rate_kpi`), all seven dashboards, `utils/helpers.py`
(`_fmt_money` → AED), `analytics/{yoy_attribution,decision_engine}.py`,
`ml_models/{customer_segmentation,xgboost_model,vehicle_placement}.py`,
`forecasting/prophet_forecasting.py` (regressor set: petrol, APR, incentive,
days'-supply, Ramadan), `sentiment/fetchers/gdelt_fetcher.py`
(`UAE_AUTO_QUERIES`, `sourcecountry:AE`), `sentiment/analyzers/grok_analyzer.py`
(both system prompts rewritten for a UAE all-import dealer group),
`sentiment/group_briefing.py`, `app.py` (Emirate/Area filters, fallback lists),
`preprocessing/clean_data.py`, README / ARCHITECTURE_OVERVIEW / TECHNICAL_DOCUMENTATION.

## Verified

`streamlit.testing` AppTest run of every dashboard page (default filters and
Dubai/Toyota/SUV filters) — 0 exceptions, 0 `st.error`. Prophet what-if,
XGBoost lead score, KMeans segmentation and the mock group briefing all run
end-to-end against the reseeded `real_demand.db`.
