# Prompt — Dealer-facing pass on the "Customer Intelligence" tab

Paste the block below into Claude Code.

---

```
Task: repositioning + visual pass on the "Customer Intelligence" tab (module #5
of the module-by-module dealer-facing sweep).

CONTEXT
PredictaX is being repositioned from an OEM / market-analyst tool to a
DEALER-GROUP product: the dataset models ONE regional dealer group of 24
rooftops, not a market. "Executive Overview", "Demand Forecasting",
"Comparative Analytics" and "Regional Intelligence" (now "Store Performance")
are done. Before touching anything, read:
  - every file in docs/changelog/  (the pattern, dataset model, shared chart
    conventions, benchmark-research + changelog workflow)
  - docs/next-pass-regional-intelligence.md  (now holds the deferred
    customer-catchment note — relevant, it also touches customer geography)
  - TECHNICAL_DOCUMENTATION.md sections 8 (ML models) and 10

Target files:
  dashboard/customers.py
  ml_models/customer_segmentation.py
  ml_models/xgboost_model.py
  database/queries.py::get_customer_segments_data
Shared helpers live in utils/helpers.py (_section, _base_layout, _fmt_money,
_compact, _pct_label, _INK, _INK_MUTED, _HUE_*). NATIONAL_SCALE_FACTOR is gone.

DO IT IN THIS ORDER

1. Read dashboard/customers.py, both ml_models files, and get_customer_segments_data
   end to end. Produce a table — (element -> problem for a dealer -> proposed
   fix) — and STOP. Don't change anything yet.

   Known problems (confirm / correct / add to):

   - COMPLIANCE / LEGACY: the tab is built heavily around `nationality` —
     "Nationality Distribution", "Nationality Characteristic Analysis", "Age vs
     Income Profile by Nationality". This is a holdover from the UAE version. A
     US auto dealer running analytics that segment or target customers by
     national origin / ethnicity is a fair-lending / ECOA / disparate-impact
     liability, not a feature. Strong recommendation: remove nationality from
     every chart and from the segmentation feature set; replace with income
     band, credit tier, life-stage / age band, household geography, and
     purchase history. Bring me the specific replacements.

   - FRAMING: "Customer Intelligence" should clearly be the GROUP'S OWN CRM /
     buyer base, not "the market's customers". Header + captions.

   - SEGMENTATION (KMeans, 5 segments): keep the idea, reframe as "our customer
     base". Check the segment labels still make sense for a US dealer group
     (Premium / Budget / High-Repeat / EV Enthusiast / Fleet). Add what a dealer
     actually wants next to each segment: count, share, revenue contribution,
     avg deal value, repeat rate, financing mix — so a segment is an actionable
     group, not just a scatter cluster.

   - LEAD SCORING (XGBoost + SHAP): genuinely dealer-relevant (a BDC / sales-desk
     tool) — keep and sharpen:
       * The lead should be tied to a STORE (the group has 24). Add a store
         selector, or infer from the customer's market.
       * `financing_type` is deliberately excluded (leakage) — keep excluded.
       * SHAP has a SILENT fallback to a 3-feature heuristic that renders
         identically — surface which one ran (a small badge / caption).
       * The "Smart Action Recommendation" must be dealer-actionable: which
         follow-up cadence, which incentive lever, when to escalate — not
         "switch the customer to a bank loan".

   - MISSING dealer-CRM staples (decide which are in scope for this pass):
       * Repeat-purchase / retention / defection rate.
       * Equity-mining / upgrade opportunities — customers whose lease or loan is
         near maturity who could be pulled forward into a new deal. The data
         supports it: Sale.lease_maturity_date, residual_value_usd,
         loan_amount_usd. (Inventory Intelligence already has a lease-RETURN
         view from the supply side; this is the customer/sales side — flag if
         it's better as its own pass.)
       * Days-since-last-purchase / "in-market" scoring.

   - Any NATIONAL_SCALE_FACTOR-style inflation (customer counts should be raw).

2. THE DECISIONS I need to make — options + a recommendation:
   - Cut nationality entirely vs keep an aggregate-only "customer origin"
     rollup with no targeting use. (I lean cut.)
   - The replacement segmentation feature set and the per-segment metric panel.
   - Whether equity-mining / upgrade-opportunity is in THIS pass or its own.
   - Lead form: store selector vs infer-from-market.

3. RETRAIN THE REAL-MODE MODELS. The 2026-08-2x reseeds changed the customer and
   sales distributions, so models/clustering/real/ and models/xgboost/real/ are
   stale. Retrain both against the real engine (set_data_mode("real") first) —
   with nationality removed from the segmentation features — and commit the new
   pickles. Note in the changelog that train_models.py still only covers test
   mode (known gap).

4. Research real numbers (web) for anything the dataset needs so the CRM figures
   are sane — e.g. franchise-dealer customer-retention / repeat-buyer rates,
   lease vs loan customer mix, share of buyers who are "in-market" again within
   3 years, appointment-to-sale close rates. Cite sources in the changelog.

5. Regenerate the real dataset if needed (preprocessing/generate_na_data.py ->
   reseed real_demand.db), same rules as prior passes. Likely small: e.g.
   number_of_past_purchases / churn_risk realism, or dropping the NATIONALITY_*
   generation if we cut it. Keep every other tab working, and re-run step 3 if
   you reseed.

6. Rebuild the visuals to the SAME glance-first system as the earlier tabs:
   - Import shared helpers from utils/helpers.py — no copy-paste, no new
     get_color_palette usage.
   - Calm, self-labelling charts; one hue per job; NO dual-axis; direct labels;
     one-line caption under every header.
   - Segmentation: a clean segment breakdown (sorted bar / treemap) + the
     per-segment metric panel, not a raw KMeans scatter as the hero.
   - Lead form result: the probability as a single clear gauge or bar, the
     top +/- drivers as a small horizontal bar, and the recommendation as
     plain-language next steps.

7. Verify: streamlit.testing.v1.AppTest with zero errors, THEN launch the app,
   run a lead through the form, screenshot both sub-tabs, and look at them.

8. Write docs/changelog/<today>-customer-intelligence-dealer-positioning.md in
   the same structure as the earlier changelogs (why / before -> after /
   dataset + model changes / benchmarks + sources / how it's better / known
   limitations). Update TECHNICAL_DOCUMENTATION sections 8.1 / 8.2 (feature
   lists) and the section 10 customers.py row.

CONSTRAINTS
- Don't touch other tabs except trivially-true caption fixes.
- Ask me before: cutting nationality, the new segmentation features, and
  whether equity-mining is in scope. Those change the product.
- Removing nationality from the model changes its inputs — retrain, don't just
  hide the column in the UI.
```
