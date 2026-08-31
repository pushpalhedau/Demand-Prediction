# Prompt — Dealer-facing pass on the "Comparative Analytics" tab

Paste the block below into Claude Code.

---

```
Task: repositioning + visual pass on the "Comparative Analytics" tab (module #3
of the module-by-module dealer-facing sweep). This is the tab with the MOST
genuine OEM content, so expect a real product decision, not just relabelling.

CONTEXT
PredictaX is being repositioned from an OEM / market-analyst tool to a
DEALER-GROUP product: the dataset models ONE regional dealer group of 24
rooftops, not a market. "Executive Overview" and "Demand Forecasting" are
already done. Before touching anything, read:
  - docs/changelog/2026-08-27-executive-overview-dealer-positioning.md
  - docs/changelog/<the Demand Forecasting changelog>
  - TECHNICAL_DOCUMENTATION.md section 5.4 (queries) and section 10
    (comparison.py row)

Target file: dashboard/comparison.py
Supporting queries in database/queries.py:
  get_yoy_comparison, get_brand_origin_yearly_share, get_price_competitiveness,
  get_ev_segment_by_brand_year, get_market_share_shift, plus IMPORT_BRANDS /
  BRAND_ORIGIN / _filters_no_brand.
(NATIONAL_SCALE_FACTOR is already deleted; 2 captions in comparison.py were
already corrected in the Exec Overview pass.)

DO IT IN THIS ORDER

1. Read dashboard/comparison.py and the queries above end to end. Produce a
   table — (element -> why it reads as OEM/market-analyst -> proposed
   dealer-facing version) — and STOP. Don't change anything yet.

   Known OEM-flavoured content (confirm / correct / add to):
   - The entire "Import Tariff Exposure" section: Domestic-vs-Import MARKET
     SHARE, "Brand Origin Market Share Growth", "% of Total US Market", "Import
     Brands vs Total Market Volume", "Market Share Shift", "Projected 2027
     Import Share" (np.polyfit on ~4 points). A single dealer group has a SALES
     MIX, not market share, and can't see the national industry — these are
     manufacturer / equity-analyst views computed on the group's own 24-rooftop
     data, so the "% of Total US Market" labels are now literally wrong.
   - _filters_no_brand deliberately ignoring the brand filter "so the
     competitive-analysis section always shows the full market" — an OEM
     competitive-intelligence pattern.
   - "Domestic EV Segment Share ... of total US EV market" KPI.
   - YoY / quarter / month / category / region comparisons are dealer-relevant
     in substance but are titled/captioned as market analysis and "region"
     means US states rather than the group's own markets/stores.

2. THE DECISION I need to make — bring me options with a recommendation:
   What happens to the Import Tariff Exposure section?
     (a) Cut it entirely.
     (b) Reframe to "Tariff Exposure by Franchise": how the 25% Section 232
         tariff hits the group's IMPORT-brand rooftops specifically — added cost
         per imported unit, margin compression, the price gap vs the domestic
         alternatives the group ALSO sells, and demand shifting between the
         group's own import and domestic franchises. (The group carries both, so
         this is a real question for them.)
     (c) Keep a slimmed version: just "our import mix and its cost exposure",
         no share-of-market, no 2027 projection.
   Also decide the grain of the core YoY view: group total, per store, per
   brand, per category — and whether it should show units, revenue, and/or an
   estimated gross.

3. Research real numbers (web) for anything the dataset needs — e.g. how much of
   the Section 232 tariff actually passed through to sticker / transaction price
   in 2025-26, typical import vs domestic dealer gross, YoY new-retail growth
   rates 2021-2026. Cite sources in the changelog.

4. Regenerate the real dataset if needed (preprocessing/generate_na_data.py ->
   reseed real_demand.db), same rules as prior passes. Keep every other tab
   working. NOTE: the sale-level tariff pass-through logic already exists in
   build_sales (tariff_markup on import brands) — check it's realistic before
   changing.

5. Rebuild the visuals to the SAME glance-first system as Exec Overview /
   Demand Forecasting:
   - Import the shared helpers from utils/helpers.py (_fmt_money, _compact,
     _pct_label, _section, _INK / _INK_MUTED / _HUE_* — promoted there in the
     earlier passes). Don't copy-paste.
   - Calm, self-labelling charts; one hue per job; NO dual-axis (the current
     "Import Brands vs Total Market Volume" chart is a dual-axis — fix it);
     direct labels; one-line caption under each header.
   - A YoY comparison should read in one glance: this period vs last, the delta,
     and which stores / brands / categories drove it (up and down).

6. Verify: streamlit.testing.v1.AppTest with zero errors, THEN launch the app,
   screenshot the Comparative Analytics tab, and look at it. Iterate until every
   chart is glanceable.

7. Write docs/changelog/<today>-comparative-analytics-dealer-positioning.md in
   the same structure as the earlier changelogs (why / before -> after / dataset
   / benchmarks + sources / how it's better / known limitations). Update the
   TECHNICAL_DOCUMENTATION section 10 comparison.py row and the section 14
   "known gaps" note about the OEM tariff content being resolved.

CONSTRAINTS
- Don't touch other tabs except trivially-true caption fixes.
- Ask me before: cutting vs reframing the tariff section, and the grain/measures
  of the YoY view. Those change the product story.
- If a query (get_brand_origin_yearly_share etc.) ends up unused after the
  reframe, leave it defined with a deprecation note rather than deleting, in
  case another module claims it.
```
