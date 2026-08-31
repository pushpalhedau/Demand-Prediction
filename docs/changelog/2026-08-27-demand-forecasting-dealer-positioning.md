# Demand Forecasting — Dealer-Facing Repositioning

**Date:** 2026-08-27
**Branch:** `NA-version`
**Scope:** `Demand Forecasting` tab (module #2 in the module-by-module positioning pass)
**Trigger:** Same stakeholder feedback as the Exec Overview pass — *"This is a dealer-facing
solution, not an OEM solution — confirm this positioning across the platform."*
**Predecessor:** `docs/changelog/2026-08-27-executive-overview-dealer-positioning.md`

---

## 1. Why this changed

The forecasting tab was written as a **market-analyst / OEM** tool: it forecast a
single daily series framed as "US auto demand", and its what-if simulator drove on
macro shocks a *manufacturer's economist* watches (WTI crude, national GDP, CPI,
Section 232 tariff rate, a national EV-charging-station count, a "luxury demand
index"). None of those are levers a dealer principal can act on, and the headline
output ("cumulative X units over 90 days; spike expected on Thursday Nov 14") did
not connect to any decision a GM makes.

| OEM-style element (before) | Problem for a dealer |
|---|---|
| Chart title **"Revenue Forecast Under Market Scenarios"**, series **"Bear Market / Base Market / Bull Market"** | Equities-desk language. And "Bear/Bull" were just Prophet's confidence bounds `yhat_lower/upper` relabelled as if they were driver scenarios. |
| What-if sliders: **WTI crude, GDP growth, CPI inflation, tariff %, tourism index, luxury demand index, EV charging stations, diesel** | Manufacturer macro dials. A dealer GM never turns these. |
| `DRIVER_SENSITIVITY` — comment: *"US auto market elasticities"* | Presented as market elasticities; actually a hand-typed table, with entries (`us_fed_rate_pct`, `unemployment_rate_pct`, auto-show binaries) for drivers **not even exposed in the UI**. |
| Forecast grain: **total group, daily** | A dealer orders **monthly, per brand**. Daily group-unit noise isn't actionable. |
| Region filter surfaced as **"Select a State"** | "States of a nation" framing, not "our markets". |
| **"Weekly Seasonality Pattern"** chart | The generator assigned sale dates with **no day-of-week logic**, so Prophet's weekly component was fitting pure noise. |
| Summary: *"High demand spike expected on Thursday, November 14, 2025"* | A single named-day spike at daily grain is noise, not a plan. |
| Model-internals on a business screen: **"Active Regressors" badges, "[SENTIMENT]" tag, RMSE/MAE/accuracy** | Analyst framing. |

**Confirmed clean:** the Prophet path has **no `NATIONAL_SCALE_FACTOR`-style
inflation** — it forecasts the group's own booked `Sale.units_sold` /
`total_revenue_incl_tax` directly. Nothing to unscale.

---

## 2. What the tab looks like now

**Framing:** "Demand Forecast — Projected new-vehicle units the group will retail
across its rooftops, trained on the group's own booked sales, so you can plan what
to stock and order."

**Controls:** Forecast (Units / Revenue) · Looking ahead (3 / 6 / 12 months) ·
**Brand** (All brands = group total, or one franchise). The confidence band is
fixed at 80% — not a user knob — and its monthly half-width is shrunk to ~0.55×
the naive sum of Prophet's daily bounds (day-to-day forecast errors partly cancel
over a month, so the sum-of-bounds badly overstates monthly uncertainty). A
"Scope:" line states the active brand / segment / market / fuel filter in plain
words.

**What-if panel — 4 dealer levers** (each maps to a real `external_factors` column,
so the baseline forecast already reflects its history):

| Lever | Column | UI touch |
|---|---|---|
| **Pump price** ($/gal) | `gasoline_regular_usd_per_gallon` | — |
| **Auto-loan APR** (%) | `auto_loan_apr_pct` | shows the monthly-payment change on a $42K / 72-mo loan |
| **Incentive spend** (% of price) | `incentive_pct_of_atp` | — |
| **Inventory on hand** (days' supply) | `inventory_days_supply` | — |

Dropped sliders: diesel, WTI crude, GDP, CPI, tariff %, tourism index, luxury
demand index, EV charging stations.

**Headline row (3 cards):** Expected units/revenue for the window (+ % vs last year) ·
Confidence range (low–high) · Implied monthly run-rate (+ % vs trailing-12-mo).

**Charts:**
1. **History vs forecast** — monthly booked units (grey), then the forecast as an
   **Expected** line with a **Conservative / Optimistic** fan (the low and high of
   the same confidence range, dotted, each direct-labelled with its window total).
   In-chart headline ("3.5K units expected over the next 3 months · −2% vs last
   year") and a "forecast →" boundary marker sitting between the last booked month
   and the first forecast month. The window snaps to whole calendar months so the
   chart total, the headline number and the "next N months" label all agree. The
   old standalone scenario bar chart is folded into this one.
2. **When the group sells — by month** / **Busiest day of the week** — Prophet's
   fitted yearly/weekly components, green/red bars vs a flat period, with a dealer
   read ("Saturday carries the retail week").

**Plain-language takeaway** replaces the spike-day line:
*"Plan: stock and order toward 3.5K units across the group over the next 3 months;
the busiest month in that window is expected to be October. That's −2% against the
same window last year."*

**Scenario naming:** "Bear / Base / Bull Market" → **Conservative / Expected /
Optimistic**, and the band is honestly labelled **"model confidence range"**, not
"scenarios". The levers move the whole projection; they don't widen the band.

---

## 3. Code changes

| File | Change |
|---|---|
| `utils/helpers.py` | **Promoted the shared glance-first system** here (was partly inline in `overview.py`): `_fmt_money`, `_compact`, `_pct_label`, `_section`, `_base_layout`, and the `_INK` / `_INK_MUTED` / `_GRID` / `_HUE_*` tokens. |
| `dashboard/overview.py` | Dropped its local `_fmt_money`; imports it from `utils.helpers` now. No visual change. |
| `dashboard/forecasting.py` | Full rewrite. Monthly grain + per-brand selector; 4 dealer levers replacing 9 macro sliders; `GROUP_DEMAND_RESPONSE` (documented, single-mechanism) replaces `DRIVER_SENSITIVITY`; one glance-first forecast chart — booked history → Expected line with a Conservative/Optimistic fan, direct-labelled, headline + vs-last-year in-chart; captions under every header; monthly-payment translation for the rate lever. |
| `forecasting/prophet_forecasting.py` | Added a `brand=` filter param. Regressor set trimmed from ~18 macro columns to the 4 dealer levers + `holiday_season_month`. `ext_query` now selects those columns. `get_external_factor_stats` numeric list updated. Weekly seasonality kept (the data now has a real weekday pattern). |
| `database/models.py` | `ExternalFactor` gains `auto_loan_apr_pct`, `incentive_pct_of_atp`, `inventory_days_supply`. |
| `preprocessing/clean_data.py` | Median-fills the three new columns. |
| `preprocessing/generate_na_data.py` | See §4. |

The what-if **no longer double-counts**: it used to both (a) override Prophet's
future regressor rows *and* (b) multiply by the hand table. Now it passes
`market_overrides=None` to Prophet (baseline forecast) and applies **only** the
`GROUP_DEMAND_RESPONSE` table — one legible, documented mechanism.

**Not touched:** `dashboard/sentiment_analysis.py::_render_forecast_comparison`
(the "does watching the news improve our forecast" view). It lives in the Sentiment
Intelligence tab, not this one — reframing it is deferred to the sentiment pass.

---

## 4. Dataset changes (`preprocessing/generate_na_data.py`, real dataset only)

Regenerated `realdata-datasets/*` and reseeded `real_demand.db` (dropped the file
so the new columns take). Test dataset (`automobile_datasets/`) regenerated by the
same `main()` but unused by the app.

| Change | Before | After | Rationale / benchmark |
|---|---|---|---|
| **Retail seasonality** | `1 + 0.15·sin((month−3)/12·2π)` — a plain sinusoid, peak June, trough December | **Federal Reserve G.17 seasonal factors** for total light vehicles: Jan 0.848 · Feb 0.914 · Mar 1.079 · Apr 1.028 · **May 1.127** · Jun 0.990 · Jul 1.005 · Aug 1.056 · Sep 0.920 · Oct 0.986 · Nov 0.970 · **Dec 1.068** | The real US new-vehicle retail shape: Q1 trough, spring build to the May peak, summer strength, a September model-year-selldown dip, a December pickup/luxury bump. |
| **Day-of-week pattern** | none — `sale_date` day drawn `randint(1,28)`, no weekday logic | weekday-weighted day draw (Mon–Sun `0.130 / 0.130 / 0.135 / 0.140 / 0.160 / 0.215 / 0.090`). Realised: **Sat ≈ 150, Fri ≈ 112, Sun ≈ 64** (100 = avg day) | New-vehicle showroom traffic concentrates on Saturday; many states restrict Sunday sales. Makes Prophet's weekly component (and the "busiest day" chart) mean something. |
| **Macro demand modulation** | none — external factors were decorative; sale count `n` was fully exogenous | monthly volume weight now `year_base × Fed_seasonal × macro_mult`, where `macro_mult` responds to `GAS_REGULAR`, `AUTO_LOAN_APR`, `INCENTIVE_PCT_ATP`, `DAYS_SUPPLY` and is **mean-normalised + clipped to ±15%** | So Prophet fits real, correctly-signed coefficients on the four levers ("this forecast accounts for fuel prices and financing cost" is now literally true). Mean-normalisation keeps annual totals stable. |
| **New `external_factors` columns** | — | `auto_loan_apr_pct` = Fed funds + 3.0pt spread; `incentive_pct_of_atp` (9% pre-COVID → 2.4% in the 2021–22 shortage → 7.4% by 2025); `inventory_days_supply` (65 → ~28 in 2021–22 → ~80 in 2024–25) | Grounds the four what-if levers and the modulation above. |
| **`discount_pct`** | `normal(5.8%, 2.8)` — flat | `normal(incentive_pct_of_atp[month], 2.6)` — tracks the incentive era (near-zero 2021–22, ~7% by 2025) | Ties the per-deal discount to the same incentive series the lever exposes; also makes the Trade-In tab's incentive-elasticity read more real. |
| **December mix** | flat | Pickup ×1.5, Luxury ×1.25 in the model-selection weights for December sales | KBB/Cox: full-size pickups set a December record of **>233,000 units / $15B** in 2025; December ATP peaks. |

**Blast radius (accepted):** the Exec Overview default window (2021-01→2026-05)
moves from **74,322 units / $3.04B** to **71,830 units / $2.95B** (~3% lower —
the Fed seasonal curve and the mild macro drag on the 2021–22 shortage years
redistribute volume). All tabs verified rendering with zero errors (§5). YoY deltas
on Exec Overview / Comparative shift by a point or two; no tab logic breaks.

---

## 5. Verification

- `streamlit.testing.v1.AppTest` — `app.py` plus every render function
  (`forecasting`, `overview`, `comparison`, `regional`, `customers`, `inventory`,
  `sentiment_analysis`) run with **zero exceptions and zero error boxes**.
- What-if override path exercised (high pump + high APR + low days'-supply →
  correct red "demand down" banner); revenue target exercised.
- App launched, Demand Forecasting tab screenshotted and reviewed; iterated:
  `st.metric` deltas showed green up-arrows for negatives → switched to
  ASCII-hyphen numeric deltas; Streamlit was rendering `$` as LaTeX in the
  payment caption / plan line → escaped; forecast window snapped to whole
  calendar months so the monthly chart has no half-month edge that reads as a
  dip and its total matches the headline.

---

## 6. Benchmarks & sources

- **Federal Reserve G.17** — *Seasonal Factors for Motor Vehicle Sales*
  (`federalreserve.gov/releases/g17/mv_sales_sf.htm`): the monthly seasonal curve.
- **NADA** — *2025 Annual Financial Profile* (16.2M light vehicles ÷ 16,990
  franchised dealers ≈ 953 new units/store/yr; H1-2024 run-rate ≈ 922). The group
  models ~575/rooftop/yr — under the average, consistent with its import/value skew.
- **Cox Automotive / Kelley Blue Book** — incentive spend 7.0% of ATP (2024) →
  7.3% (Jul 2025), highest since 2021; collapsed to ~2–3% during the 2021–22 chip
  shortage. December 2025: full-size pickups >233,000 units, record $15B.
- **Cox Automotive days'-supply series** — 60 days = healthy; 70–85 through
  2024–25; ~25–35 during the shortage; ~$1,850 gross lost per unit past 60 days.
- **Resources for the Future / NBER** — *How Do Gasoline Prices Affect New Vehicle
  Sales?*: +$0.60/gal ⇒ light-truck share −4% to −6%, car share +4.5% to +9%;
  total-volume elasticity to gas is modest. Basis for the −4%/$1/gal response.
- **Federal Reserve FEDS Notes**, Sep 2024 — *Rising Auto Loan Delinquencies and
  High Monthly Payments*: +140bp ⇒ +$15/mo (~3%) on a 60-mo loan; NY Fed reports
  the highest auto-loan rejection rate on record in 2024. Basis for −3%/+1pt APR.

Elasticities used (`GROUP_DEMAND_RESPONSE`, `dashboard/forecasting.py`):
pump price **−4% units per +$1/gal**, loan APR **−3% per +1pt**, incentive spend
**+2% per +1pt of ATP**; inventory: **−1.1%/day below 55 days' supply**, no upside
from a glut.

---

## 7. How this makes the product better

1. **A forecast a GM acts on.** "Stock and order toward ~3.5K units over the next
   quarter, strongest month October, −2% vs last year" is a plan. "Spike on
   Thursday Nov 14" was not.
2. **Per-brand grain.** The group orders by franchise; the brand selector gives a
   per-franchise forecast instead of one undifferentiated group number.
3. **Levers a dealer owns.** Pump price, financing cost (shown as a monthly
   payment), incentive spend, and stock on hand — versus WTI crude and a national
   tourism index.
4. **Honest uncertainty.** The band is labelled as model confidence, not dressed
   up as three "market scenarios"; the what-if is one documented mechanism, not a
   hidden hand-table stacked on a Prophet override.
5. **The forecast genuinely reflects its inputs.** The dataset now bakes in real
   gas/rate/incentive covariation, so Prophet's fitted regressor coefficients are
   real rather than spurious fits on decorative national series.
6. **Real seasonality.** Spring build, September selldown, December truck bump,
   Saturday-heavy week — all from published factors, all visible in the tab.

---

## 8. Known limitations / follow-ups

- **`GROUP_DEMAND_RESPONSE` is a calibrated assumption table, not a per-group
  regression.** The dataset now supports fitting it (the covariation is real), but
  the tab still applies fixed coefficients. Fitting them per active scope
  (brand/region) from the group's own history is the natural next step.
- **Prophet's fitted December seasonality is weak** despite the dataset's December
  pickup/luxury boost — the "by month" chart shows December near flat. The boost is
  in model *selection* (mix), and the volume bump is modest; a stronger December
  volume weight would show it, at the cost of overstating a demo dataset.
- **Month-of-year raw counts look Sep–Dec-light** because the data ends Aug 2026 —
  those months have 7 years of history vs 8 for Jan–Aug. Per-year the shape is
  correct; Prophet's yearly fit is unaffected.
- **Revenue is new-vehicle front-end + F&I only** (no used / service / parts), so
  the ~$49M/store/yr it implies is below NADA's ~$73M total-revenue figure. Same
  conservative-ATP caveat as the Exec Overview pass.
- **`_render_forecast_comparison`** (sentiment-on vs sentiment-off) still reads as
  model benchmarking — deferred to the Sentiment Intelligence pass.
- **Exec Overview / Comparative headline numbers shifted ~3%** with the reseed;
  their changelogs quote the pre-reseed figures. Re-baseline when those tabs get
  their next pass.
- Repo-wide `use_container_width` deprecation is unrelated and still outstanding.
- `README.md` / `ARCHITECTURE_OVERVIEW.md` still say "North American automobile
  businesses" / "NA market dataset" — full copy sweep deferred until all module
  passes land.
