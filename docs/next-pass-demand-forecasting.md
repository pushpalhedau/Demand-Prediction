# Prompt — Dealer-facing pass on the "Demand Forecasting" tab

Paste the block below into Claude Code.

---

```
Task: repositioning + visual pass on the "Demand Forecasting" tab (module #2
of the module-by-module dealer-facing sweep).

CONTEXT
PredictaX is being repositioned from an OEM / market-analyst tool to a
DEALER-GROUP product: the dataset models ONE regional dealer group of 24
rooftops, not a market. The "Executive Overview" tab was already done — before
touching anything, read:
  - docs/changelog/2026-08-27-executive-overview-dealer-positioning.md
    (the pattern: what "OEM framing" means, the new dataset model, the shared
     chart conventions, the benchmark-research + changelog workflow)
  - TECHNICAL_DOCUMENTATION.md sections 6 and 7 (forecasting internals)

Target files: dashboard/forecasting.py, forecasting/prophet_forecasting.py
(also dashboard/sentiment_analysis.py::_render_forecast_comparison if it's
wired to this tab).

DO IT IN THIS ORDER

1. Read dashboard/forecasting.py and forecasting/prophet_forecasting.py end to
   end. Produce a table — (element -> why it reads as OEM/market-analyst ->
   proposed dealer-facing version) — and STOP. Don't change anything yet; let
   me make the calls on the open decisions.

   Things I already suspect are OEM-flavoured (confirm / correct / add to):
   - Output framed as "US auto demand" / "market demand" instead of "units this
     group will sell" / "demand across our stores".
   - The what-if simulator driving on shocks a MANUFACTURER worries about
     (semiconductor supply constraint, national EV federal subsidy, Section 232
     tariff rate) rather than levers a DEALER actually feels (local pump price,
     interest rate -> monthly-payment affordability, incentive/discount spend,
     allocation / inventory availability).
   - DRIVER_SENSITIVITY described as "US auto market elasticities" — should be
     the group's own historical demand response, ideally fitted from its data
     rather than hand-authored, or at least relabelled.
   - Forecast grain: is it at a level a dealer acts on? (total group units, or
     per-brand / per-store / per-category) and does it connect to a decision
     ("so plan to stock / order roughly this many")?
   - Region filter meaning — the group's own markets, not "states of a nation".
   - Any NATIONAL_SCALE_FACTOR-style inflation. Exec Overview's is deleted;
     confirm the Prophet path never multiplies units/revenue up to a market
     number. If the forecast currently forecasts a scaled series, unscale it.
   - Bear / Base / Bull naming (fine, or "Conservative / Expected / Optimistic").
   - "Forecast Comparison" (with vs without news sentiment) — keep, but frame as
     "does watching the news improve OUR forecast", not market commentary.

2. Research real numbers (web) for whatever the dataset needs so the forecast
   figures are sane for a 24-rooftop group — e.g. monthly new-unit throughput
   per rooftop, the seasonality shape of US new-vehicle retail (spring / Q3
   selldown / December pickup-truck spike), and how much a $1/gal pump move or a
   1-pt rate move actually shifts dealer unit sales. Cite sources.

3. If the dataset needs changes for the numbers to make sense, edit
   preprocessing/generate_na_data.py and reseed real_demand.db — same rules as
   the Exec Overview pass (seeded, reproducible, keep every other tab working,
   test dataset left alone).

4. Rebuild the visuals to the SAME glance-first system as Exec Overview:
   - First promote the shared helpers from dashboard/overview.py
     (_fmt_money, _compact, _pct_label, _section, the _INK / _INK_MUTED /
     _HUE_* tokens) into utils/helpers.py and import them in both files — don't
     copy-paste.
   - Calm, self-labelling charts; one hue per job; NO dual-axis; direct labels
     over axis-reading; a one-line caption under every chart header explaining
     what it shows and what the shaded band means.
   - The main forecast chart must read in one glance: history vs projection, the
     headline expected number, the range, and the "so what" (vs last year / vs
     target / vs current run-rate).
   - Scenario + seasonality-decomposition charts get the same treatment.

5. Verify: streamlit.testing.v1.AppTest run with zero errors, THEN launch the
   app, screenshot the Demand Forecasting tab, and look at it. Iterate on
   anything that isn't glanceable.

6. Write docs/changelog/<today>-demand-forecasting-dealer-positioning.md in the
   same structure as the Exec Overview changelog: why it changed / before ->
   after / dataset changes / benchmarks + sources / how it's better / known
   limitations + follow-ups. Add a one-line pointer from TECHNICAL_DOCUMENTATION
   section 10.

CONSTRAINTS
- Don't touch other tabs except trivially-true caption fixes.
- Ask me before any decision that changes the product story: what we forecast,
  at what grain, and which levers the what-if simulator exposes.
- Comparative Analytics still has genuine OEM content (import-vs-domestic market
  share, 2027 share projection) — that's a later pass, leave it.
```
