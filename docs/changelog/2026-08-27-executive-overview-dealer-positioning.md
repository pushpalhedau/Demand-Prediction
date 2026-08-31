# Executive Overview — Dealer-Facing Repositioning

**Date:** 2026-08-27
**Branch:** `NA-version`
**Scope:** `Executive Overview` tab only (first module in the module-by-module positioning pass)
**Trigger:** Stakeholder feedback — *"This is a dealer-facing solution, not an OEM solution — confirm this positioning across the platform."*

---

## 1. Why this changed

The platform is sold to a **car dealership / dealer group** (the retailer), not to a
**vehicle manufacturer** (OEM). Several things on the Executive Overview only made
sense for a manufacturer looking at a whole market:

| OEM-style element (before) | Problem for a dealer |
|---|---|
| Every unit & revenue figure multiplied by `NATIONAL_SCALE_FACTOR = 17` | A dealer wants **their own booked numbers**, not a sample extrapolated to a "national implied" total. The revenue KPI was showing **~$54 billion** for the default window. |
| KPI: *"#1 Brand — 23% market share"* (`get_top_brand_kpi`) | A franchise dealer *is* ~100% its brand; a group has a **sales mix**, never "market share". |
| KPI: *"US Fed Funds Rate"* | A raw macro rate as a headline exec KPI is analyst framing. |
| Chart: *"Regional Sales Analytics"* by state | Implies an 8-state footprint / district-manager view. |
| `worst_region` computation | "Rank the weak territory" is OEM field-ops. |
| Dataset: 48 rooftops evenly spread 6-per-state across 8 states, sales routed to any dealer regardless of brand (40% brand match) | Reads as a *market model*, not one group's business. |

## 2. What the tab looks like now

**Framing:** "Executive Overview — Group-wide new-vehicle retail performance across
_N_ rooftops — the group's own booked sales for the selected period."

**KPI row (4 cards):**

| Card | Meaning | Default-window value |
|---|---|---|
| **New Units Sold** | Units in the filtered window + YoY % | 74,322 units (+8% YoY) |
| **Total Revenue** | `total_revenue_incl_tax` in the window + YoY % | $3.04B (+10% YoY) |
| **Target Attainment (TTM)** | Trailing-12-month units ÷ Σ of in-scope stores' `annual_target_units` | 94% (14,456 of 15,375) |
| **Finance & Lease Penetration** | Share of deals **not** paid cash + YoY pts | 77% |

**Charts:**
1. Revenue & Unit Sales Trend (monthly, unscaled) — kept
2. Sales Mix by Vehicle Category (donut, by **units**) — renamed from "…Share", switched from revenue to units
3. Fuel Type Mix (bar, units) — OEM caption removed
4. **Sales by Store** (horizontal bar, top 15 rooftops, colour = revenue) — **replaces** "Regional Sales Analytics" by state
5. **Top-Selling Models** (horizontal bar, top 8) — **new**

Removed from the tab: national scaling, brand-market-share KPI, Fed-rate KPI,
worst-region, state-level revenue bar.

## 3. Code changes

| File | Change |
|---|---|
| `database/queries.py` | Deleted `NATIONAL_SCALE_FACTOR` and all 15 call sites. Rewrote `get_executive_kpis` (drops `worst_region`; adds `finance_lease_penetration` + YoY, target-attainment block). Added `_period_aggregates`, `_shift_years`, `get_target_attainment`, `_apply_dealer_scope`, `get_top_models`, `get_sales_by_store`. `get_top_brand_kpi` / `get_fed_rate_kpi` kept (defined, no longer used by Overview). |
| `dashboard/overview.py` | Full rewrite: new KPI row, dealer-group header with live rooftop count, `Sales by Store` + `Top-Selling Models`, category mix by units, captions de-OEM'd. |
| `dashboard/comparison.py` | Two captions that said "scaled to national implied volume" corrected (the scaling no longer exists). Rest of the Import-Tariff-Exposure section is deferred to the Comparative Analytics pass. |
| `TECHNICAL_DOCUMENTATION.md` | §5.4 national-scaling note and §10 `overview.py` row updated. |

## 4. Dataset changes (`preprocessing/generate_na_data.py`, real dataset only)

Regenerated `realdata-datasets/*` and reseeded `real_demand.db`. Test dataset
(`automobile_datasets/`) left on the legacy market grid — the app doesn't use it.

| Change | Before | After | Rationale / benchmark |
|---|---|---|---|
| **Network** | 48 rooftops, 6 per state, random brand each | **24 rooftops**, one regional group, distributed by market size (CA 5 / TX 4 / FL 4 / NY 3 / IL·GA·OH·MI 2), coherent one-franchise-per-rooftop portfolio covering all catalog brands | A 24-rooftop group @ ~600–700 new units/rooftop/yr is a realistic mid-size group (NADA 2024: avg franchised store ≈ **922** new units/yr, **$73.3M** total revenue incl. used/F&I/service). |
| **Sale → store routing** | any dealer in the sale's state (**40% brand match**) | routed to a store that franchises that brand, preferring the shopper's state (**100% brand match**); sale `state`/`city` = the **store's** location | "Sales by Store" would otherwise show stores selling brands they don't carry. |
| **`annual_target_units`** | `randint(500, 7000)` — unrelated to volume | each store's own trailing-12-month units × 1.05, rounded to 25 | Makes "Target Attainment" meaningful — it landed at 94% (was mathematically ~7%). |
| **Fuel mix** (model-selection weighting, era-aware for EV) | EV 13% / Hybrid 4.5% (flat) | EV 6.0% / Hybrid 5.1% / Gas 87% / Diesel 1.5%; EV rises 4%→7.4% (2019→2024) then dips post-Oct-2025 | Cox Automotive / KBB: BEV share **8.1% (2024), 7.8% (2025), ~6% (2026)**; blended-since-2019 ≈ 5–6%. Federal EV credit expired Oct 2025 → modeled dip. |
| **Nameplate demand skew** (`MODEL_TIER_WEIGHT`) | uniform across a brand's models → niche minivans/halo trims topped the board | flagship / strong / niche tiers → top sellers are Ram 1500, Silverado, F-150, RAV4, CR-V, Equinox, Grand Cherokee, Model Y, Rogue | A real best-seller board; needed once "Top-Selling Models" became a chart. |
| **Sticker discount** | `normal(4.5%, 2.5)` | `normal(5.8%, 2.8)` | KBB/Cox 2024-25: incentives ≈ **7% of ATP**; stacked with trade over-allowance + bonus the effective giveaway ≈ 7%. |

Distributions that were already realistic and left alone: category mix (SUV 49% /
Pickup 23% / Sedan 15% — group skews light-truck, defensible for a Sun-Belt group),
trade-in attach 55% (Edmunds ~50–55%), financing split (Cash 22% / Lease 25% /
Loan 53%; Experian new-vehicle lease ≈ 24–25%).

## 5. Benchmarks & sources

- NADA — *2024 Annual Financial Profile of America's Franchised New-Car Dealerships* (avg ≈ 922 new units/yr, $73.3M total sales/store).
- Cox Automotive / Kelley Blue Book — EV share of new sales: 8.1% (2024), 7.8% (2025), ~6% (Q1 2026); electrified (hybrid+PHEV+BEV) ≈ 20% in 2024; ATP ~$48–50K (2025); incentives ≈ 7% of ATP.
- Experian — *State of the Automotive Finance Market*: new-vehicle lease ≈ 24.9% (Q4 2024) → 24.4% (Q4 2025); ~80% of new vehicles financed or leased (≈20% cash), Q1 2024.
- Edmunds — ~25% of new-car trade-ins carried negative equity in 2024; roughly half of new purchases involve a trade.

## 6. How this makes the product better

1. **Believable numbers.** Revenue went from a fictional **$54B** to **$3.04B** for a 24-store group — a figure a dealer principal can sanity-check against their own DMS.
2. **Metrics a GM actually opens the dashboard for.** "Are we on plan?" (Target Attainment) and "how much F&I business are we writing?" (Finance & Lease Penetration) replace market-share vanity metrics no dealer can act on.
3. **Store-level visibility.** "Sales by Store" answers "which rooftops are carrying the group / which are lagging" — the core question for a multi-store operator.
4. **Data integrity for every downstream module.** 100% brand-to-store match means Regional Intelligence, Inventory, and Placement now reason about stores that actually sell the brand in question.
5. **Consistent story.** The product now matches the `DEALER_INTEGRATION_REQUIREMENTS.docx` it ships with, which already assumes a dealer supplies their own sales/inventory/customers.

## 7. Known limitations / follow-ups

- **Hybrid share (~5%) is below the real ~10–12%.** The vehicle catalog only carries 3 hybrid nameplates (Prius, Sienna, Maverick); reaching a realistic hybrid mix needs RAV4/CR-V/Camry-Hybrid style entries — a catalog expansion that also touches the Placement Assistant, so deferred.
- **Per-rooftop volume (~600–700/yr) is a little under the NADA ~900 average** — consistent with a group weighted toward import/value brands and smaller metros; acceptable, not tuned further.
- **ATP ≈ $35.6K** vs a real ~$48K — catalog MSRPs are base-ish 2019–2024 trims with only 2 trim levels in the real dataset. Revenue is directionally right but conservative.
- **Comparative Analytics still contains genuine OEM content** (import-vs-domestic *market share*, 2027 share projection). That's the next module's pass — decision needed there: cut vs. reframe as "tariff impact on our cost/mix".
- `get_top_brand_kpi` / `get_fed_rate_kpi` are now dead for Overview; remove once no other module claims them.
- Repo-wide `use_container_width` deprecation is unrelated and still outstanding.
- `README.md` / `ARCHITECTURE_OVERVIEW.md` still describe the platform as serving "North American automobile businesses" / a "NA market dataset". A full positioning-copy sweep of the docs is best done once all module passes land, not per-module.
- `preprocessing/generate_na_data.py::main()` regenerates **both** datasets; the `automobile_datasets/` (test) CSVs also changed here (unused by the app, changes are strictly improvements).
