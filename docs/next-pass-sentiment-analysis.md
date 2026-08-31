# Prompt — Dealer-facing pass on the "Sentiment Analysis" tab

Paste the block below into Claude Code.

---

```
Task: repositioning + visual pass on the "Sentiment Analysis" tab (part of the
module-by-module dealer-facing sweep).

CONTEXT
PredictaX is being repositioned from an OEM / market-analyst tool to a
DEALER-GROUP product: the dataset models ONE regional dealer group of 24
rooftops, not a market. Executive Overview, Demand Forecasting, Comparative
Analytics, Regional Intelligence (now "Store Performance") and Customer
Intelligence are done. Before touching anything, read:
  - every file in docs/changelog/  (the pattern, dataset model, shared chart
    conventions, benchmark-research + changelog workflow)
  - TECHNICAL_DOCUMENTATION.md section 9 (the whole sentiment pipeline) and
    section 10

Target files:
  dashboard/sentiment_analysis.py
  sentiment/signal_processor.py
  sentiment/analyzers/grok_analyzer.py   (system prompt / scoring schema)
  sentiment/fetchers/gdelt_fetcher.py    (NA_AUTO_QUERIES themes)
Shared helpers live in utils/helpers.py (_section, _base_layout, _fmt_money,
_compact, _pct_label, _INK, _INK_MUTED, _HUE_*).

IMPORTANT: work and test in MOCK mode only — do NOT set XAI_API_KEY, do not
trigger live Grok calls. The mock scorer is deterministic and fully functional.
GDELT is a free public API; keep "Refresh" clicks to a minimum during testing.

DO IT IN THIS ORDER

1. Read the four files end to end. Produce a table — (element -> why it reads as
   OEM / hedge-fund / market-analyst -> proposed dealer-facing version) — and
   STOP. Don't change anything yet.

   Known problems (confirm / correct / add to):

   - FRAMING: the whole tab is a "Geopolitical Risk" / "Economic Signals"
     dashboard — a macro-strategy / OEM-planning lens. A dealer group has no
     geopolitical analyst. Reframe the tab as a demand ADVISORY: "what's in the
     news that will move showroom traffic, demand mix, vehicle cost and
     financing over the next few weeks — and what to do about it." Propose a
     rename (e.g. "Market Signals" / "Demand Watch" / "External Factors").

   - The "Geopolitical Risk Index" ( avg_impact x negative_ratio ) should become
     a plain demand-direction read: headwind / neutral / tailwind, with the
     estimated size and horizon, expressed in the group's own terms.

   - `_geo_risk_fallback()` FABRICATES a risk score seeded by
     date.today().toordinal() when there's no analyzed data. A dealer product
     must not invent a number — replace with an honest empty state ("no recent
     signals — click Refresh"). Keep the mechanism only if it's clearly labelled
     as a demo placeholder; better to remove it.

   - Each scored signal (`affected_vehicle_category`, `demand_direction`,
     `estimated_demand_change_pct`, `economic_risk`) should be tied to THE
     GROUP'S exposure: "tariff news hits import brands; 45% of your units are
     import franchises, so your exposure is ~X". Use the real sales mix.

   - Every signal card needs a concrete dealer ACTION: adjust stocking on
     segment Z, pull forward / hold incentives, brief the desk on financing
     talk-tracks, etc. — not just a sentiment score.

   - GDELT themes (NA_AUTO_QUERIES): na_auto_demand, ev_market_na, tariff_trade,
     fuel_oil_prices, us_macro_economy, luxury_suv_na — mostly fine for a dealer
     (fuel, rates, tariffs, incentives) but national-level. Consider making them
     footprint-aware (the group's states) and adding interest-rate / auto-loan
     and OEM-incentive-program coverage. Your call on scope.

   - grok_analyzer.py system prompt: "financial and automotive market
     intelligence analyst" -> reframe as an advisor to a dealer group scoring
     news for its effect on RETAIL vehicle demand and dealership operations.
     Keep the JSON output schema stable (Prophet + the daily_sentiment_summary
     table depend on it).

   - MOCK vs LIVE: the UI should honestly show which scorer produced the
     current view (a small badge), since the mock is a keyword heuristic.

   - "Forecast Comparison" (with vs without news signal), if it lives on this
     tab: frame it as "does watching the news actually improve OUR forecast",
     and keep it consistent with whatever the Demand Forecasting pass decided.

2. THE DECISIONS I need to make — options + a recommendation:
   - Keep this as its own tab, or fold it into Demand Forecasting as a
     "what's driving the outlook" panel? (I lean: keep, but reframed.)
   - The rename.
   - Remove `_geo_risk_fallback()` fabrication vs keep-but-label.
   - Footprint-aware / expanded news themes — in this pass or later.
   - The headline indicator: headwind/neutral/tailwind gauge vs a signed
     "expected demand impact next 30 days" number.

3. Research real numbers (web) for anything used to calibrate the signal->demand
   mapping — e.g. published elasticities of US new-vehicle sales to gas price,
   to interest rates, to consumer sentiment; how fast auto demand reacts to a
   macro shock. Reuse / cross-check whatever the Demand Forecasting pass already
   researched for DRIVER_SENSITIVITY. Cite sources.

4. Dataset: this tab runs on live GDELT + the sentiment tables, not the
   realdata CSVs, so a regen is unlikely to be needed. If you do touch
   preprocessing/generate_na_data.py, follow the same rules and keep every other
   tab working. Do NOT break the daily_sentiment_summary schema — Prophet reads
   avg_sentiment_score and geopolitical_risk_score from it.

5. Rebuild the visuals to the SAME glance-first system as the earlier tabs:
   - Import shared helpers from utils/helpers.py — no copy-paste, no new
     get_color_palette usage.
   - Calm, self-labelling charts; one hue per job; NO dual-axis; direct labels;
     one-line caption under every header.
   - Headline: one clear indicator (gauge or single number) = "net demand
     signal, next ~30 days", with the drivers as a short horizontal bar
     (green tailwind / red headwind), and the signal cards as a scannable list
     with source, date, affected segment, and the recommended action.
   - Honest empty state when there are no recent signals.

6. Verify: streamlit.testing.v1.AppTest with zero errors (mock mode), THEN
   launch the app, open the tab, click Refresh once, screenshot every sub-tab,
   and look at them.

7. Write docs/changelog/<today>-sentiment-analysis-dealer-positioning.md in the
   same structure as the earlier changelogs (why / before -> after / any
   dataset or schema notes / benchmarks + sources / how it's better / known
   limitations — including the mock-vs-live caveat). Update TECHNICAL_
   DOCUMENTATION section 9 (framing + fallback) and the section 10 row; if the
   tab is renamed, update app.py's menu and every doc that lists the seven
   modules.

CONSTRAINTS
- Don't touch other tabs except trivially-true caption fixes and the shared
  menu-label rename if we rename this tab.
- Do NOT change the daily_sentiment_summary table columns or the grok_analyzer
  JSON schema — downstream Prophet regressors depend on them.
- Ask me before: keeping vs folding the tab, the rename, and removing the
  fabricated fallback. Those change the product.
- Never enable live Grok scoring during this work.
```
