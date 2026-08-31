# Regional Intelligence → Store Performance — Dealer-Facing Repositioning

**Date:** 2026-08-29
**Branch:** `NA-version`
**Scope:** `Regional Intelligence` tab → renamed **Store Performance** (module #4 in the
module-by-module positioning pass)
**Trigger:** Same stakeholder feedback as the earlier passes — *"This is a dealer-facing
solution, not an OEM solution — confirm this positioning across the platform."*
**Predecessors:**
`docs/changelog/2026-08-27-executive-overview-dealer-positioning.md`,
`docs/changelog/2026-08-27-demand-forecasting-dealer-positioning.md`,
`docs/changelog/2026-08-28-comparative-analytics-dealer-positioning.md`

---

## 1. Why this changed

The tab was built as a manufacturer's **field-operations / territory** view: a
continental-US coverage map, an OEM-assigned dealer **tier** (Platinum/Gold/Silver),
an opaque 0–100 **"Dealer Rating Index"**, and a top-20 **"leaderboard"** of *dealers*
scored on synthetic attributes. A single dealer group runs **stores**, not a market a
field team polices — and it manages those stores by units, pace against plan, gross and
showroom conversion, not by a rating index.

| OEM-style element (before) | Problem for a dealer group |
|---|---|
| Tab name **"Regional Intelligence & Dealer Analytics"** | "Region/territory" is the OEM's unit of management; "Dealer Analytics" implies analysing *other* dealers. |
| Map `center={lat 39, lon -98}, zoom 3.2` — geographic centre of the US, fixed | A national coverage map. Reads as "the market", not "our 24 rooftops". |
| Map `size=units_sold`, `color=revenue` | Both channels encode "big store" — redundant, and neither tells a GM which store needs attention. |
| `Dealer.tier` (Platinum/Gold/Silver) column | `rng.choice([...])` — random, unrelated to volume; mirrors an OEM's contractual dealer classification. |
| `Dealer.performance_score` / **"Dealer Rating Index"** axis | `rng.uniform(62, 96)` — an opaque synthetic score with no inputs a dealer can act on. |
| Header **"Top Performing Dealer Leaderboard"**, `.limit(20)` | "Leaderboard" framing; and it silently dropped 4 of the group's 24 rooftops. |
| Columns: Google Rating, EV Infrastructure, Avg Deal Value | Consumer-directory / OEM-audit attributes. Missing every number a multi-store operator lives on. |
| `px.scatter_mapbox` + `mapbox_style="open-street-map"` | Deprecated in Plotly 6 (we're on 6.9); light OSM basemap fights the dark app. |
| `get_data_mode()` branch to a "test mode" leaderboard with Tier/Score | Dead code — the app is locked to real mode (`_data_mode = "real"`). |
| `st.success("Top Dealer Alert: …")` — winner only | An OEM "dealer of the month" note. An operator needs the **laggards** more. |
| Stale comment: *"Avg Deal Value: ×17 cancels in numerator/denominator"* | Referenced the long-deleted `NATIONAL_SCALE_FACTOR`. |
| Local `paper_bgcolor`/font dicts, `get_color_palette` | Predated the shared glance-first system → guaranteed drift from the three finished tabs. |

**Product decisions taken** (confirmed with the stakeholder before building):

1. **Rename → "Store Performance"** (menu label in `app.py`, header, docs). Plain name,
   matches Executive Overview / Demand Forecasting / Comparative Analytics.
2. **Map encodes:** marker **size = units** this period, **colour = pace vs the store's
   own annual target** (`Dealer.annual_target_units`), diverging red→yellow→green
   centred at 95% (≈ holding last year's volume, since targets carry a +5% stretch).
   A big red bubble = a high-volume store losing ground — the one glance a GM wants.
3. **Drop `tier` and `performance_score` from the tab entirely.** Both columns stay
   defined on the `Dealer` model with a deprecation note; they are no longer selected
   by `get_dealer_performance_leaderboard`.
4. **Customer-catchment view: deferred.** The dataset now supports it (see §4), but the
   view itself — "where each store's buyers come from vs where the store sits" — is a
   network-expansion question, out of scope for a store-performance pass. Logged in
   `docs/next-pass-regional-intelligence.md`.

---

## 2. What the tab looks like now

**Framing:** "Store Performance — how each of the group's rooftops is tracking: units
and revenue this period, pace vs the store's own annual target, and year-over-year
growth."

**Headline row (3 cards):** Rooftops reporting · Units this period · Stores behind plan
(*N* of 24 running below 90% of their own trailing-12-month target).

### 1 — Where the rooftops are

`px.scatter_map` (MapLibre), `carto-darkmatter` basemap that matches the app. The view
**auto-fits to the group's actual footprint** (centroid of the stores in scope, zoom
derived from their lat/lon span) instead of a hard-coded continental-US frame. One dot
per store: **size = units** this period, **colour = pace vs target** (RdYlGn, midpoint
95%). Hover carries the store's franchise, city/state, units, revenue, % of target and
YoY. Colourbar reads "Pace vs target" in %.

### 2 — Rooftops by units sold

Every store (all 24, not a top-N), sorted, horizontal bar — same treatment as Executive
Overview's "Sales by Store" and Comparative's driver bars. Bar length = units this
period, **direct-labelled** (`5.9K`, `2.1K`…); colour = the same pace-vs-target scale as
the map, so the hue means one thing on both.

### 3 — Store scorecard

All 24 rooftops, sortable `st.dataframe` with `column_config` number formatting (so
sorting stays numeric):

| Column | Basis |
|---|---|
| Store · Franchise · State | identity |
| Units · Revenue ($M) | the selected window |
| YoY units % | trailing-12-months vs the prior 12 (**not** full-window vs shifted window) |
| Pace vs target % | trailing-12-month units ÷ the store's own `annual_target_units` |
| Est. gross ($M) | benchmark gross/unit (front-end + F&I) by franchise origin × the store's volume — an estimate, not booked gross (the `Sale` table carries no cost basis) |
| Close rate % | share of the store's test-drives that converted, in the window |
| Avg days to close | mean `lead_to_close_days`, in the window |
| Top segment | best-selling vehicle category, in the window |

### 4 — Both ends of the network

Replaces the single success box with a two-up: **"Carrying the group"** (highest pace
vs target) beside **"Needs attention"** (lowest), each with units · % of target · YoY,
and the "also down year-over-year" stores listed after the weakest.
On the default window: *Carrying the group — Honda of Jacksonville (100% of target,
+8.4% YoY); Needs attention — BMW of Jacksonville (85% of target, −4.7% YoY), also down:
Nissan of Houston, Toyota of Chicago, Kia of San Francisco.*

Everything routes through `utils/helpers.py` (`_section`, `_base_layout`, `_fmt_money`,
`_compact`, `_pct_label`, `_INK*`). No dual-axis, one hue per job. `get_color_palette`
is no longer imported here. (Per stakeholder request the section captions were dropped
after the first build — the headers and the "Pace vs target" colourbar/help-tooltip
carry the read now; `_section` still supports a caption for the other tabs.)

---

## 3. Code changes

| File | Change |
|---|---|
| `dashboard/regional.py` | Full rewrite. Rename to "Store Performance"; `px.scatter_map` + dark basemap + auto-fit; pace-vs-target colour on map and ranking bar; 24-row sortable scorecard; two-sided strongest/weakest callout; shared helpers; `get_data_mode` test branch and the stale `×17` comment gone; `get_color_palette` import dropped. |
| `database/queries.py` | `get_dealer_performance_leaderboard` **extended** (name kept): returns all stores (was `.limit(20)`), adds `brand`, `annual_target_units`, `ttm_units`, `prior_ttm_units`, `yoy_units_pct`, `attainment_pct`, `close_rate`, `avg_days_to_close`. **Dropped from the SELECT** (still on the `Dealer` model, docstring-flagged): `tier`, `performance_score`, `google_rating`, `ev_charging_station`, `service_center`. `import numpy as np` added. |
| `app.py` | Menu label `"Regional Intelligence"` → `"Store Performance"`; route updated; sidebar icon `geo-alt` → `shop`. |
| `preprocessing/generate_na_data.py` | Two dataset changes — see §4. |
| `TECHNICAL_DOCUMENTATION.md` | §2 repo-layout line, §5.4 query note, §10 `regional.py` row, module-graph label. |
| `README.md`, `ARCHITECTURE_OVERVIEW.md`, `PROJECTPLAN.md.txt` | Module name updated where the seven modules are listed. |

No column was deleted. `tier` / `performance_score` remain on the `Dealer` model and in
`get_dealer_directory` (used by Inventory Intelligence) with a deprecation note on the
leaderboard query.

---

## 4. Dataset changes (`preprocessing/generate_na_data.py`, real dataset only)

Regenerated `realdata-datasets/*` and reseeded `real_demand.db`. No schema change (both
affected columns already exist). Test dataset (`automobile_datasets/`) regenerated by
the same `main()`, unused by the app.

| Change | Before | After | Rationale / benchmark |
|---|---|---|---|
| **Customer ↔ store geography** | `customer_id` drawn as a plain random sample of all 42k customers — **independent** of the store the sale was routed to. A Michigan store's #1 buyer origin was *California*. | Each sale's customer is drawn preferring one whose `Customer.state` matches the **routed store's** state; ~82% local, the rest from anywhere the group sells. Realised: **84% in-state** buyers per store. | New-vehicle buyers are overwhelmingly local — median customer-to-dealership distance ≈ **5 miles**, the large majority buy within ~30 miles (Texas registration study; UK NFDA travel survey). Makes `Customer.state` meaningful per store so a later catchment view is truthful; **no group-level total moves** (customers are still sampled with replacement). |
| **Per-store sales effectiveness** | `test_drive_converted` = flat `random < 0.62` for every store; `lead_to_close_days` = `randint(1,60)` minus a trade-bonus effect. Every rooftop landed ~62% / ~30 days ± sampling noise — no real signal. | Each store gets a stable latent effectiveness (mean-zero across the network, ~1 s.d.): it shifts test-drive→sale conversion by ≈±7 points around the ~62% group average and pulls average time-to-close a few days either way. Realised: **close rate 50–72% by store** (group 61%), **avg days 25–35** (group 30). | So the scorecard's *Close rate* and *Avg days to close* columns carry a genuine between-store spread a GM can act on, instead of 24 identical numbers. Mean-preserving — the group close rate (~62%→61%) and the Lead-Conversion model's training target are effectively unchanged. |

**Blast radius (accepted, ~nil):** the Exec Overview default window (2021-01→2026-05)
holds at **71,830 units / $2.976B** (was 71,830 / $2.976B — identical; the tariff-rate
reseed on 2026-08-28 is the current baseline). Neither dataset change touches volume,
price, seasonality, the four demand levers, financing/trade/lease logic, or inventory.
All seven tabs verified rendering with zero errors (§5).

**Store-effectiveness realism:** close-rate here is a **test-drive→sale** rate (~50–72%),
not a lead→sale rate. Industry lead→sale runs far lower (~8–15% blended; ~25% for
showroom/walk-in leads within 30 days), but the dataset has no lead funnel above the
test drive — `test_drive_converted` is "shopper drove the car, then bought". 50–72% is a
defensible test-drive close band.

---

## 5. Verification

- `streamlit.testing.v1.AppTest` on `app.py` — **zero exceptions, zero error boxes**.
- Every render function (`overview`, `forecasting`, `comparison`, `regional`,
  `customers`, `inventory`, `sentiment_analysis`) run against the reseeded DB — all clean.
- `get_dealer_performance_leaderboard` exercised across filter combos: default window,
  `region=California`, `region=California + city=San Diego`, `brand=Toyota`,
  `brand=Toyota + region=Illinois`, `vehicle_category=Luxury`, and an empty combo
  (`region=Michigan + brand=Toyota` — the group has no Toyota rooftop in MI → friendly
  "no store sales" message, no crash).
- App launched; Store Performance screenshotted (full page + a MapLibre element crop —
  the full-page path can't composite the WebGL basemap in headless Chromium, so the map
  was verified via the element crop and a DOM check: `maplibregl-canvas` mounts,
  no GL/tile console errors). Iterated:
  - "Stores behind plan" was counting `< 95%` of a **+5%-stretch** target → 17 of 24,
    which overstated the problem. Changed to `< 90%` → **4 of 24**, a true headline.
  - map/bar colour was a custom red→green ramp anchored at 100% → most stores read
    orange because they sit at ~90–95% of a stretch target. Switched to `RdYlGn` with
    `color_continuous_midpoint=95` so "holding last year's volume" reads neutral-yellow,
    only genuine decline reads red.
  - YoY was full-window-vs-shifted-window (every store green over a 5-year sidebar
    range — the same artefact the Comparative pass fixed). Changed to
    trailing-12-vs-prior-12 → **9 of 24 stores down**, real winners and losers.
  - map auto-fit zoom was too wide (showed Canada→Guatemala) → tightened the span→zoom
    heuristic to frame the lower-48 footprint.

---

## 6. Benchmarks & sources

- **NADA — 2024 / 2025 Annual Financial Profile of America's Franchised New-Car
  Dealerships:** average franchised store ≈ **950 new units/yr** (16.2M ÷ ~17k dealers);
  average new-vehicle **front-end gross ≈ $2,247** for full-year 2024 (down ~33% YoY);
  **F&I income per vehicle retailed ≈ $1,581** (new + used blended, 2024).
- **Presidio-NCM Average Dealership Performance Benchmark (FY2024):** front-end gross per
  new vehicle — domestic **$1,952**, import **$1,699**, luxury **$5,679**.
- **Haig Partners Q2–Q3 2024 reports:** F&I gross **≈ $2,400 per vehicle retailed** at
  publicly-owned dealership groups.
- **Foureyes / Ruler Analytics / demandlocal dealership benchmarks (2024–25):**
  lead→sale ≈ 8–15% blended; **showroom / walk-in leads ≈ 25%** close within 30 days;
  phone ≈ 14%, internet ≈ 6–8%; new-vehicle **show-to-sale ≈ 41%**.
- **Customer travel distance:** Edmunds — median customer-to-dealership distance ≈ **5
  miles**, majority of purchases within ~30 miles; ready-to-buy shoppers will travel
  ~65 miles for a specific make/model (used-car travel has roughly doubled since 2019 to
  ~115 miles, new-car far less). Texas vehicle-registration study — median ≈ **5.2 mi**.
- **NADA 2025:** 16.2M light vehicles, US new retail **≈ +2% YoY** in 2025.

Constants realised in the tab: est. gross/unit — luxury **$8,100**, mainstream import
**$3,750**, domestic **$4,050** (front-end + F&I, `_GROSS_PER_UNIT` in `regional.py`).

---

## 7. How this makes the product better

1. **It's a store view, not a territory view.** The map reads as "our 24 rooftops",
   auto-framed to where the group actually operates, coloured by whether each store is
   holding its plan — not a national coverage chart.
2. **Metrics an operator manages by.** Units, revenue, YoY, pace vs the store's own
   target, estimated gross, showroom close rate, time-to-close — replacing a random tier
   badge and an opaque 0–100 index nobody could act on.
3. **Both ends of the network.** "Needs attention — BMW of Jacksonville, 85% of target,
   −4.7% YoY" is a management conversation. "Top Dealer Alert" was a trophy.
4. **All 24 rooftops.** The `.limit(20)` cap is gone; the group can't have four stores
   invisible on its own performance tab.
5. **Honest YoY.** Trailing-12-vs-prior-12, so a multi-year sidebar window doesn't paint
   every store green.
6. **Real store-to-store variation in the data.** Close rate and days-to-close now
   differ by rooftop because the generator gives each store a stable effectiveness —
   the columns mean something.
7. **One visual system.** Shared helpers, one hue per job, `px.scatter_map` (not the
   deprecated `scatter_mapbox`) — matches the three finished tabs.

---

## 8. Known limitations / follow-ups

- **Customer-catchment view is deferred.** The data now supports it (buyer home-state
  correlates with the routed store, 84% in-state), but "where each store draws from" as
  a visual is a next-pass item — see `docs/next-pass-regional-intelligence.md`.
- **Est. gross is a benchmark estimate, not booked gross.** `Sale` has no cost/invoice
  column (Comparative Analytics deferred a real gross measure for the same reason).
  Est. gross = published per-unit front-end + F&I gross by franchise origin × the
  store's window volume. A real per-deal `gross_profit_usd` would need a modelled cost
  basis (import brands carry the tariff in cost too) and another reseed.
- **Pace vs target tops out near 100%.** Targets are set at each store's own prior-TTM
  × 1.05; a year on, stores land ~85–100% of that. The band is realistic for a group
  broadly on last year's pace with a couple of laggards, but there's no store wildly
  over or under plan to dramatise.
- **Close rate is a test-drive→sale rate**, not a lead→sale rate (the dataset has no
  lead funnel above the test drive). Directionally fine; not comparable to CRM
  lead-conversion benchmarks.
- **Lead Conversion (XGBoost) model not retrained.** `test_drive_converted` (its target)
  now carries per-store variance and its group mean drifts ~62%→61%. The loaded pickle
  still predicts correctly (store effectiveness isn't a model feature, so predictions
  barely move); a retrain is optional cleanup, not required.
- **`Dealer.tier` / `performance_score` still populated by the generator** (random
  draws) and read by `get_dealer_directory` for Inventory Intelligence. Dropping them
  from the schema is a cross-module change for a later sweep.
- **Map basemap needs network access** to `basemaps.cartocdn.com` at render time
  (MapLibre vector tiles). Offline, the markers still plot on a blank canvas.
- Repo-wide `use_container_width` deprecation is unrelated and still outstanding.
- `README.md` / `ARCHITECTURE_OVERVIEW.md` still describe the platform in "North
  American market" language in places — full positioning-copy sweep deferred until all
  module passes land.
