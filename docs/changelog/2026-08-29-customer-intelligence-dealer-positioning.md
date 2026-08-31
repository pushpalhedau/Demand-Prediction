# Customer Intelligence — Dealer-Facing Repositioning

**Date:** 2026-08-29
**Branch:** `NA-version`
**Scope:** `Customer Intelligence` tab (module #5 in the module-by-module positioning pass)
**Trigger:** Same stakeholder feedback as the earlier passes — *"This is a dealer-facing
solution, not an OEM solution — confirm this positioning across the platform."*
**Predecessors:**
`docs/changelog/2026-08-27-executive-overview-dealer-positioning.md`,
`docs/changelog/2026-08-27-demand-forecasting-dealer-positioning.md`,
`docs/changelog/2026-08-28-comparative-analytics-dealer-positioning.md`,
`docs/changelog/2026-08-29-store-performance-dealer-positioning.md`

---

## 1. Why this changed

The tab was the last major holdover from the platform's **UAE origin**. It was built
around `nationality`: a "Nationality Distribution" donut, a "Nationality Characteristic
Analysis" that cross-tabbed **income and age by national origin**, an "Age vs Income
Profile **by Nationality**" scatter, and `nationality` sitting in the customer table as a
first-class field. For a US franchise dealer, customer analytics keyed to national origin
/ ethnicity is a **fair-lending / ECOA / disparate-impact liability** — the income-by-
ethnicity cross-tab is precisely the exhibit a regulator or plaintiff's counsel builds a
case from. It informs no decision a dealer makes.

Beyond the compliance problem, the tab did not read as the group's **own CRM**:

| Element (before) | Problem for a dealer |
|---|---|
| H2 "Customer Intelligence & **Lead Optimization**"; "Clustering Analysis" / "Nationality & Demographics Analysis" headers | Market-analyst framing. Reads as "the market's customers", not "our buyer base". |
| `is_real` branch — a whole second **test-mode** code path ("Segment Distribution", "Segment Characteristic Analysis", "Age vs Churn Risk") | Dead code. The app is locked to real mode (`_data_mode = "real"`). |
| **Segmentation** (KMeans, 5 segments): "Premium / Budget / High Repeat / **EV Enthusiast** / **Fleet**" | "EV Enthusiast" was assigned to the *highest-`loyalty_score`* cluster — nothing to do with EVs. "Fleet Buyer" was the leftover label — the group sells to individual retail consumers, there is no fleet flag. Two of the six clustering features (`loyalty_score`, `churn_risk_score`) were **drawn from unrelated distributions** at customer-build time and carried no real signal. And the tab showed the clusters but none of what a dealer needs to *act* on a segment: count, revenue contribution, deal value, repeat rate, financing mix. |
| **Lead form** had no store | `predict_deal_probability` silently defaulted `state="California"` for every lead. The group has 24 rooftops across 8 states. |
| **Lead form** collected `gender` → the XGBoost model **used `gender` as a feature** | ECOA prohibits considering the sex of an applicant. A live lead-prioritisation score weighted partly on customer gender is a disparate-treatment risk — and, unlike a report, it is an input to an individual decision. |
| Lead form fields: "Loyalty Rating 0–100", channel list `["Referral","Digital","Auto Expo","TV"]`, `fuel_type` including "CNG" | A fresh lead has no loyalty history; the channel / fuel / category option lists **did not match the values the model was trained on**, so unseen labels were silently coerced to the encoder's first class. |
| "Feature Attributions (**SHAP explainers**)" | The SHAP path has a **silent fallback** to a 3-field hard-coded heuristic that renders identically. Nothing told the user which ran. |
| "Smart Action Recommendation" | Not tied to a store, a follow-up cadence, or an escalation trigger. "Target a different vehicle category" / "secure downpayment within 48 hours" is boilerplate. |
| `render_customers(filters)` — `filters` accepted, **never used** | Every other tab honours the sidebar region filter. |
| Local `get_color_palette` / `paper_bgcolor` dicts, `px.pie` for everything, a raw scatter as the hero | Predated the shared glance-first system → guaranteed drift from the four finished tabs. |

**Confirmed clean:** no `NATIONAL_SCALE_FACTOR`-style inflation — customer counts were
already raw `value_counts()`.

**Product decisions taken** (confirmed with the stakeholder before building):

1. **Cut `nationality` entirely** — from every chart, from the segmentation feature set,
   from `get_customer_segments_data`, and from the data generator. Not kept as an
   "aggregate-only rollup": it is still origin-keyed analytics with no dealer use. The
   `Customer.nationality` column stays on the model (nullable, deprecation-commented) for
   schema stability. **Also removed `gender` from the XGBoost lead model** (same ECOA
   family; retrained without it). `age` is kept — a standard, behaviourally-grounded CRM
   signal, not used here for a credit decision — and flagged below as a considered risk.
2. **Replacement segmentation feature set:** `age`, `estimated_annual_income_usd`,
   `credit_score`, **real** `number_of_past_purchases`, **real** `recency_days`,
   `avg_deal_value`. `loyalty_score` / `churn_risk_score` dropped from the clustering.
   Five clusters, relabelled to value/behaviour tiers: **High-Value / Prime · Loyal
   Repeat · Core Mainstream · Value Buyers · Lapsed / At-Risk**. Geography stays out of
   the clustering, shown in the per-segment panel.
3. **Equity-mining / upgrade-opportunity → its own pass.** It needs a real loan-paydown /
   current-equity model in the generator (`loan_amount_usd` is origination-only today)
   and reconciliation with Inventory Intelligence's lease-return view. Logged in
   `docs/next-pass-customer-intelligence-equity-mining.md`.
4. **Lead form → explicit store selector** (the 24 rooftops, labelled by city + state).
   "Infer from market" has nothing to infer from — a lead form is a fresh prospect.
5. **Tab 1 reworked from a descriptive "customer base" into a retention worklist** (second
   round of stakeholder feedback: *"subtab 1 has repeated data and isn't useful to a
   dealer — add something the other platforms don't have"*). The four descriptive charts
   (segment bar, per-segment panel, income-band, credit-tier, "due back") were
   ~five views of the same distribution and told a dealer nothing to *do*. Replaced with
   an **action queue** + a **book-state** view; the per-segment panel is kept in a
   collapsed expander for campaign planning.

---

## 2. What the tab looks like now

**Framing:** "Customer Intelligence — the group's own buyer base across its rooftops:
who our customers are, what each segment is worth, and who is due back in market."

### Tab 1 — Retention & Actions

**Headline row (4 cards):** Buyers on file · Repeat rate (buyers with 2+ lifetime deals) ·
Repeat share of sales (deals to a prior customer) · Flagged for outreach. Plus a one-line
read: *"Repeat buyers are 37% of the group's booked business. 8,710 customers are flagged
to contact now — $37.2M in identified gross, about $10.4M at a typical 28% win-back rate."*

1. **Retention action queue** *(the hero — nothing comparable in DealerSocket / VinSolutions
   / AutoAlert, which surface equity alerts as a flat feed)*. Every customer to contact
   now, one row each, with a **reason** (`Lease maturing` / `Overdue for next vehicle` /
   `Lapsed high-value` / `Churn-risk spike`), the **store** that should own the outreach,
   the **play**, when to call, the vehicle, months since last deal, **identified gross**
   ($), and whether email consent is on file. Filter by store (hand a rooftop its list)
   and by reason; **export to CSV**. Sorted lease-first (soonest maturity up top), then the
   rest by gross. All four reasons come from data on hand — the *positive-equity* reason
   arrives with the equity-mining pass.
2. **Where the book stands** — every lifetime buyer placed into one of four present-tense
   bands by months since their last deal (or an active lease): **Active** (<24 mo / on a
   lease) · **In cycle — due back** (24–48 mo) · **Going quiet** (48–84 mo) · **Likely
   lost** (84 mo+). Each bar carries the count and the **lifetime revenue** in that band,
   so "$647M of lifetime customer value is going quiet" is a number a GM can act on. No
   cohort-censoring — these are facts as of today.
3. **Segment detail** *(collapsed expander)* — the per-segment value panel (customers, %
   of base, lifetime revenue, avg deal value, repeat rate, lease %, median income, avg
   credit, recency), kept for campaign planning.

Cut from the tab: the standalone segment breakdown bar, the income-band and credit-tier
distribution charts, and the standalone "due back in market" chart — all restated the same
distribution and carried no action.

### Tab 2 — Lead Close Score

**Framing:** "Score a showroom or BDC lead for one of the group's stores — the closing
probability, what is moving it, and the next action."

- **Store selector** (24 rooftops → sets `state`, names the store in the recommendation).
- **Form:** age · occupation · income · credit score · vehicle category · fuel type ·
  lead source · **prior relationship** (Brand-new / Prior service customer / Repeat
  buyer — maps to the model's `loyalty_score` input) · discount you can offer · base
  price. All option lists match the trained encoder classes. **No `gender` field.**
- **Result:** the probability as a single gauge with a red/amber/green zone band and a
  plain "Zone: green — work it now" caption; the top ± drivers as a small horizontal
  tornado bar (green = pushing the score up, red = down); and a **badge** — "Per-lead
  SHAP attribution" vs "Quick estimate — SHAP unavailable, three fields only".
- **Recommendation** is dealer-actionable and tied to the selected store:
  - *Hot (≥70%):* call from {store} within the hour, book same/next-day, 3-touch confirm,
    F&I pre-qualify, no extra discount needed.
  - *Warm (45–70%):* {store}'s BDC, 6–8 touches over 14–21 days, lead with an
    appointment; if they stall the lever is a stronger trade allowance or a rate buy-down
    that lowers the monthly payment — not sticker discount; re-score after the appointment.
  - *Cold (<45%):* one call + one email, then the monthly nurture list; check a lower
    trim / different segment fits the payment; escalate to a manager only if they book
    and show.

Everything routes through `utils/helpers.py` (`_section`, `_base_layout`, `_fmt_money`,
`_compact`, `_pct_label`, `_INK*`, `_HUE_*`). One hue per job, direct labels, a caption
under every header, no dual-axis. `get_color_palette` is no longer imported here.

---

## 3. Code changes

| File | Change |
|---|---|
| `dashboard/customers.py` | Full rewrite. Tab 1 = retention action queue (`_build_action_queue`) + book-state bands (`_book_state`) + segment-detail expander; `nationality` gone, `is_real` test branch gone; the descriptive charts removed. Tab 2 lead form: store selector, `gender` removed, real option lists, "prior relationship" replaces "loyalty rating", SHAP/heuristic badge, store-and-cadence recommendation. Honours `filters['region']`. |
| `ml_models/customer_segmentation.py` | New 6-feature set (`FEATURES`), `nationality` and the two noise scores dropped. New `load_customer_features()` joins each customer's real deal history (recency, avg deal value) from `sales`. `_assign_labels()` maps the five clusters deterministically on centroid ranking to the new value/behaviour labels. Persists `feature_names.pkl` alongside the pickles. `predict_customer_segment()` takes the new feature vector, falls back to "Core Mainstream". |
| `ml_models/xgboost_model.py` | `gender` removed from `cat_features` (train + predict). `predict_deal_probability()` returns `explainer_used` ∈ {"shap","heuristic","none"} so the UI can label the attribution honestly. |
| `database/queries.py` | `get_customer_segments_data(session, filters=None)` — drops `nationality`, adds sales-history aggregates, optional region scoping (used by the segment-detail expander). **New `get_customer_book(session, filters=None)`** — one row per customer with first/last deal, lifetime deals & revenue, last store & vehicle, own purchase cadence, and nearest upcoming lease maturity (shaped from one sales+dealer pull, ~1.7 s). **New `get_repeat_contribution(session, filters=None)`** — share of the group's booked deals that went to a prior customer. |
| `database/models.py` | `Customer.nationality` — deprecation comment, kept nullable, never populated. |
| `preprocessing/generate_na_data.py` | See §4. |
| `preprocessing/clean_data.py` | `clean_customers` guards `nationality` (`if 'nationality' in df.columns`) so a legacy CSV still loads. |
| `TECHNICAL_DOCUMENTATION.md` | §8.1 / §8.2 feature lists, §10 `customers.py` row, §14 gap #4 (SHAP badge now exists). |

`predict_customer_segment` is defined but still not wired to any UI (no "classify this
customer" control) — left in place, harmless.

---

## 4. Dataset changes (`preprocessing/generate_na_data.py`, real dataset only)

Regenerated `realdata-datasets/*` and reseeded `real_demand.db`. Test dataset
(`automobile_datasets/`) regenerated by the same `main()`, unused by the app.

| Change | Before | After | Rationale / benchmark |
|---|---|---|---|
| **`nationality`** | `rng.choice(NATIONALITY_MIX, p=…)` per customer, persisted to the column | **not generated.** `NATIONALITY_MIX` / `NATIONALITY_P` deleted. | Fair-lending / ECOA. A US dealer has no legitimate use for customer national-origin analytics. |
| **Customer ↔ sale assignment** | 42,000 customers, drawn per deal by a uniform random pick (in-state 82%), no time order ⇒ ~90% of the table had bought 2+ times, **repeat-transaction share ~75%**, and a same-year re-buy was as likely as a 5-year one | **70,000 customers**, assigned **oldest deal first** with a ~52% returning / ~48% new-or-conquest split and a **≥22-month trade-cooldown** on any re-buy (`P_RETURNING` / `MIN_REBUY_MONTHS` in `build_sales`) | Real dealership volume is a blend of first-time and returning buyers; repeat business runs **~30–40%** of units and repurchases follow a multi-year trade cycle. Realised: **repeat-transaction share 37%**, repeat rate **46% of buyers**, purchase **cadence median ~34 months**, ~13% not-yet-converted prospects, **84% in-state** buyers (unchanged — a 16% out-of-state travel tail is modelled). |
| **`number_of_past_purchases`** | `rng.poisson(1.1)` — drawn at customer-build, unrelated to the customer's own `Sale` rows | each customer's **real lifetime deal count** with the group (`_derive_customer_history`) | So "repeat rate", the "Loyal Repeat" segment, the retention bands and the action-queue "overdue" logic all mean something. |
| **`last_activity_date`** | random offset from registration | the later of (generated activity, **the customer's last deal date**) | Makes recency real — it is the basis of the "Lapsed / At-Risk" segment and the "due back in market" view. |
| **`loyalty_score` (0–100)** | `rng.normal(50, 22)` — decorative | `clip(30 + 13·deals − 7·recency_years, 0, 100)` — frequency up, staleness down | Scale unchanged (Inventory Intelligence's lease-recapture reads it). Now carries signal, though it is **not** a segmentation feature (redundant with recency/frequency). |
| **`churn_risk_score` (0–1)** | `rng.beta(2, 5)` — decorative | `clip(0.6·beta_base + 0.14·recency_years − 0.04·deals + 0.05, 0, 1)` | Same — scale kept, now climbs the longer since the last deal. |
| **`test_drive_converted`** (the Lead Conversion model's target) | `rng.random(n) < (0.62 ± 0.07·store_effect)` — **independent of every customer/deal feature**, so the model fit noise and predictions barely spread | outcome now responds to real levers, **mean-normalised to hold the ~62% group close rate**: lead channel (walk-in/referral high, internet low), discount vs the month's going incentive, credit score, payment stress (price vs ~55% of income), trade-in present, store effectiveness | Foureyes / Demand Local 2025: showroom leads close ~25% / phone ~14% / internet ~6% within 30 days (modelled as a spread around the post-test-drive rate). NADA show-to-sale ~41%. So the lead score and its SHAP attribution are now real: realised close rate **49% (subprime) → 75% (super-prime)**, **72% walk-in → 55% social**, **64% with a trade vs 60% without**. |
| **`lead_to_close_days`** | store effect + trade bonus | also `− 14·(conv_p − 0.62)` — a higher-intent shopper closes quicker | Keeps the trade-bonus elasticity on Store Performance meaningful and adds a customer-intent component. Group mean holds at ~30 days. |

**Blast radius (accepted, small):** the Exec Overview default window (2021-01→2026-05)
moves from **71,830 units / $2.976B** to **71,378 units / $2.96B** (−0.6% / −0.5%).
Units and revenue are not driven by any of these fields; the drift is the RNG stream
shifting (no `nationality` draw, larger customer array, chronological customer assignment).
All seven tabs verified rendering with zero errors (§5). Store Performance close-rate
columns now carry within-store deal-level variance on top of the store latent effect; each
store's *mean* close rate is essentially unchanged, so that tab's numbers and its
changelog still stand. Customer↔store home-state correlation holds at **84% in-state**
(the Store Performance catchment note). Inventory Intelligence's lease-recapture "loyal vs
at-risk" split is unchanged in behaviour (same score scales).

**Retrained (real mode):**

- `models/clustering/real/` — KMeans on the new 6 features, new label mapping, new
  `feature_names.pkl`. Segments (post-reseed): Value Buyers 25.4k / Loyal Repeat 21.7k /
  Lapsed 10.4k / Core Mainstream 7.4k / High-Value 5.1k. `customer_segment` re-written
  onto the 70k-row customers table.
- `models/xgboost/real/` — retrained without `gender`; **11 features**. Test accuracy
  **~0.64** against a 0.62 base rate (was ~0.62, i.e. no better than guessing). Feature
  importance led by `credit_score`, then `marketing_channel`, `state`, `vehicle_category`,
  `discount_pct`.

**Known gap (unchanged):** `train_models.py` still only trains **test mode**. The real-
mode pickles were retrained by running `train_customer_segmentation()` /
`train_xgboost_pipeline()` manually against the real engine (`set_data_mode("real")`).

---

## 5. Verification

- `streamlit.testing.v1.AppTest` — `app.py` render functions (`overview`, `forecasting`,
  `comparison`, `regional`, `customers`, `inventory`, `sentiment_analysis`) run against
  the reseeded DB with **zero exceptions and zero error boxes**; `customers` also run
  with `region="California"` (filter path).
- `predict_deal_probability` exercised across hot / warm / cold leads: probabilities
  **0.87 / 0.68 / 0.41**, `explainer_used="shap"` each time, SHAP top driver
  `credit_score` (matches feature importance).
- App launched; both sub-tabs screenshotted and reviewed. Iterated: gauge axis ticks
  fixed to `[0,25,50,75,100]` + plain zone caption; SHAP bars re-sorted into a signed
  tornado; action-queue sort changed to lease-first-by-soonest-maturity then gross;
  `_REASON_PLAY` shortened so the table fits; the standalone descriptive charts removed
  after the second round of feedback.
- Data realism checked post-reseed: repeat-transaction share **37%** (target ~30–40%),
  purchase cadence median **~34 months**, in-state buyer rate **84%**, action queue
  **~8.7k customers / ~$37M identified gross**, book-state bands
  Active 32k / In cycle 17k / Going quiet 12k ($0.65B lifetime) / Likely lost 1.5k.

---

## 6. Benchmarks & sources

- **JD Power 2025 U.S. Automotive Brand Loyalty Study / S&P Global Mobility** — new-
  vehicle brand loyalty **~49–51%** in 2025 (Toyota ~60%, Ford trucks ~67%); nationwide
  brand retention **~43.9%** (2024, TVI MarketPro3).
- **Demand Local / Foureyes / Ruler Analytics dealership benchmarks (2024–25)** — lead-
  to-sale: showroom/walk-in **~25%** within 30 days, phone **~14%**, internet **~6%**;
  appointment set rate 40% internet / 74% phone; appointment show rate **50–60%** (80%+
  with a 3-touch confirm); **6–8 follow-up attempts over 14–21 days**.
- **NADA 2024/2025** — new-vehicle show-to-sale **~41%**; F&I per vehicle retailed
  **~$1,600–2,400**.
- **Cox Automotive / Edmunds / Kelley Blue Book (2025)** — average new-vehicle ownership
  **8+ years**; **new-vehicle trade-in age ~7.6 years** in Q1 2025 (oldest since 2019);
  lease returns cluster at ~36 months.
- **Experian State of the Automotive Finance Market (Q4 2025 / Q1 2026)** — average new-
  car loan credit score **~751**; subprime **~15%** of vehicle financing; new-vehicle
  lease **~24%**.
- **Demand Local repeat-buyer statistics** — a buyer who returns for service is ~30 pts
  more likely to repurchase from the same store; existing customers spend ~67% more;
  acquiring a new customer costs 5–25× retaining one. Repeat/loyal customers are commonly
  **~30–40% of a franchised store's new-vehicle volume**.
- **Equity-mining / retention CRM landscape** (AutoAlert, TradePending, Orbee,
  DealerSocket/VinSolutions, Cox Automotive) — all surface lease-maturity and equity
  *alerts*, typically as a chronological feed per rooftop. None rank the *whole* customer
  base by dollar opportunity with the reason and the play in one exportable list, and
  none tie the customer base to a demand forecast — the gap this tab (and a later
  retention-vs-forecast view) aims at.

---

## 7. How this makes the product better

1. **The compliance liability is gone.** No customer view — and no model input — keyed to
   national origin or sex. The income-by-ethnicity cross-tab that a fair-lending exam
   builds a case from no longer exists in the product or the data.
2. **Tab 1 is a worklist, not a wall chart.** "Contact these 8,710 customers now —
   $37M of identified gross, lease maturities first, here's the store and the play, export
   the list" is what a BDC opens a screen for. Five overlapping distribution charts were
   not. The retention CRMs on the market (AutoAlert et al.) surface equity alerts as a
   flat feed; ranking the whole base by dollar opportunity with the reason and the play in
   one export is the differentiator.
3. **"Where the book stands" quantifies the leak.** $647M of lifetime customer value in
   "going quiet" buyers is a number that gets a GM to fund a win-back campaign.
4. **The lead score is real.** Its target used to be a coin flip uncorrelated with any
   input; now it responds to credit, channel, discount, payment stress and trade, so the
   probability spreads (0.4→0.9) and the SHAP drivers mean something. Accuracy went from
   0.62 (= the base rate) to ~0.64.
5. **Every lead is tied to a store.** The 24-rooftop group scores a lead for a specific
   rooftop; the recommendation names that store's BDC and a concrete cadence.
6. **Honest explainability.** The UI now says whether it is showing real per-lead SHAP or
   the 3-field fallback.
7. **A believable CRM shape.** 70k customers, ~37% repeat-transaction share, a ~34-month
   purchase cadence, a real recency distribution — versus a closed 42k table where 75% of
   deals were re-buys, many within the same year.
8. **One visual system.** Shared helpers, one hue per job, direct labels, a caption under
   every header — matches the four finished tabs.

---

## 8. Known limitations / follow-ups

- **Equity-mining / upgrade-opportunity is deferred to its own pass** — see
  `docs/next-pass-customer-intelligence-equity-mining.md`. `loan_amount_usd` is
  origination-only (no amortization / current-equity), so the action queue has no
  "positive equity" reason yet — the four it ships (lease maturing, overdue for next
  vehicle, lapsed high-value, churn-risk spike) all come from data on hand.
- **The retention-vs-forecast tie-in is not built.** The headline reports the repeat share
  of *past* sales (~37%). Wiring the Demand Forecasting Prophet output in to project how
  much of *next* quarter's volume should come from the base — the "no competitor can do
  this" view pitched alongside — is a follow-up; it was scoped out to avoid a second
  Prophet dependency on this tab.
- **The action queue's "identified gross" is a flat benchmark per franchise origin**
  ($8.1k luxury / $3.75k import / $4.05k domestic), not a per-deal estimate. It sizes the
  opportunity honestly ("identified", not "expected") but every row of the same origin
  shows the same number.
- **Cadence and trade cycle are compressed.** The dataset spans 2019–2026, so a customer's
  purchase cadence lands at ~34 months and the "overdue" window is 22–64 months rather
  than the real ~7-year loan trade cycle. Internally consistent (the queue uses each
  customer's own cadence), just shorter than reality.
- **`age` is retained as a model / segmentation input.** It is an ECOA-protected basis
  for *credit* decisions; this is a sales-follow-up prioritisation score, not a credit
  decision or adverse action, and age is a standard CRM signal — but the risk was
  considered and is logged here. Removing it can be revisited if the score is ever used
  to gate anything credit-adjacent.
- **Customer credit is `normal(690, 75)`** — ~34% of the base sits below prime, above the
  ~15% subprime share of *booked new-vehicle loans*. Defensible for a CRM that includes
  un-converted prospects, not just closed deals; not tuned further this pass.
- **`loyalty_score` / `churn_risk_score` are now real but unused by the segmentation.**
  They still feed Inventory Intelligence's lease-recapture view. That view's
  `loyalty_score >= 0.6` test is effectively always-true (0–100 scale vs a 0–1
  threshold) — a pre-existing quirk in `dashboard/inventory.py`, not touched here.
- **Segment sizes are lopsided after the reseed** — Loyal Repeat balloons to ~22k and
  High-Value / Prime shrinks to ~5k because 46% of buyers now repeat. The k-means split
  and the centroid-ranked labels are deterministic and defensible; not re-tuned.
- **Segmentation training writes `customer_segment` back to the live table.** A reseed
  now requires: regenerate → `seed_real_database` → retrain segmentation (real) so the
  column is repopulated. Documented in §8.1.
- **`predict_customer_segment` is unwired** — no "which segment is this walk-in" control.
- **Exec Overview / Demand Forecasting / Comparative changelogs quote pre-this-reseed
  figures** — re-baseline on their next pass (units −0.6%, revenue −0.5% vs the
  2026-08-28 baseline).
- Repo-wide `use_container_width` deprecation is unrelated and still outstanding.
- `README.md` / `ARCHITECTURE_OVERVIEW.md` still carry "North American market" language
  in places — full positioning-copy sweep deferred until all module passes land.
