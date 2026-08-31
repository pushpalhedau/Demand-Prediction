# Sentiment Analysis — Dealer-Facing Repositioning

**Date:** 2026-08-29
**Branch:** `NA-version`
**Scope:** `Sentiment Analysis` tab (module #6 in the module-by-module positioning pass)
**Trigger:** Same stakeholder feedback as the earlier passes — *"This is a dealer-facing
solution, not an OEM solution — confirm this positioning across the platform."*
**Predecessors:**
`docs/changelog/2026-08-27-executive-overview-dealer-positioning.md`,
`docs/changelog/2026-08-27-demand-forecasting-dealer-positioning.md`,
`docs/changelog/2026-08-28-comparative-analytics-dealer-positioning.md`,
`docs/changelog/2026-08-29-store-performance-dealer-positioning.md`,
`docs/changelog/2026-08-29-customer-intelligence-dealer-positioning.md`

---

## 1. Why this changed

The tab was a **macro-strategy / OEM-planning** lens bolted onto a dealer product. It was
literally titled a *"Sentiment Intelligence Platform"* and organised around a **"Geopolitical
Risk"** monitor and an **"Economic Signals"** tracker — the dashboard a manufacturer's
economist or a hedge-fund desk opens, not a dealer group. A 24-rooftop group has no
geopolitical analyst; it has GMs who need to know *what's in the news that will move showroom
traffic, demand mix, vehicle cost and financing over the next few weeks, and what to do about
it.*

| OEM / analyst element (before) | Problem for a dealer group |
|---|---|
| H2 **"Sentiment Intelligence Platform"**, sub *"Real-time geopolitical, economic & social sentiment signals for US automobile demand forecasting"* | Macro-desk product description. |
| Sub-tab **"Geopolitical Risk"** → **"Geopolitical Risk Monitor"**; KPI **"Geopolitical Risk Index"** (`avg_impact × negative_ratio`) shown as a 0–100 gauge with a red threshold line at 60 | An abstract index with no unit a GM recognises. Risk-desk furniture. |
| KPIs **"Negative Signal Rate %"**, **"Avg News Impact Score (0=low 1=high)"** | Analyst abstractions, no decision attached. |
| **`_geo_risk_fallback()`** — fabricated a risk score / negative-% / impact seeded by `date.today().toordinal()` when there was no analysed data | **A dealer product must not invent a number.** The last two commits before this pass (`ddc7e85`, `7bc4df6`) were band-aids on exactly this. |
| Sub-tab **"Economic Signals"** → **"Economic Signal Tracker"**, "Economic Risk Distribution", sentiment heatmap | Macro-economist framing. |
| Sub-tab **"AI Insights"** → card **"US AUTOMOBILE MARKET INTELLIGENCE BRIEFING"** | "Market intelligence briefing" is an OEM/analyst report. |
| **"Forecast Comparison"** — 6-KPI RMSE/MAE/Accuracy grid, "Active Regressors" badges, dual CI ribbons | The exact model-benchmarking framing the Demand Forecasting pass removed from *that* tab. |
| Each scored signal shown as `sentiment / impact / economic_risk / direction` columns | A scoring worksheet. No tie to the group's exposure, no action. |
| `grok_analyzer.py` system prompt: *"You are a financial and automotive market intelligence analyst…"* | Hedge-fund persona. |
| `get_color_palette`, local `_layout` / `_GRID` / `_glass_card` / `_badge`, hard-coded hex everywhere; `render_kpi_card` green ▲ for unfavourable deltas | Predated the shared glance-first system → guaranteed drift from the five finished tabs. |
| Menu label **"Sentimental  analysis"** (typo + double space) | Sloppy. |
| Dead `_render_sentiment_intelligence`, `_render_recent_news`, commented-out `tab1` | Dead code. |

**Confirmed clean:** no `NATIONAL_SCALE_FACTOR`-style inflation anywhere in the pipeline.

**Product decisions taken** (confirmed with the stakeholder before building):

1. **Keep as its own tab, reframed** — not folded into Demand Forecasting. It has its own data
   lifecycle (GDELT fetch), its own mock-vs-live honesty caveat, and the "does news improve our
   forecast" question is a *validation* view that would bloat the Forecasting tab. Collapsed
   from 4 sub-tabs to **2**.
2. **Keep the name "Sentiment Analysis"** — only the menu typo was fixed
   (`"Sentimental  analysis"` → `"Sentiment Analysis"`). No repo-wide module-list rename needed.
3. **Remove `_geo_risk_fallback()` entirely** → honest empty state.
4. **Headline = signed number + small 3-zone gauge** ("expected demand impact, next ~30 days").
5. **Themes:** add `auto_financing` + `incentives_rebates` GDELT themes now; defer
   footprint-aware (group's-states) scoping.

---

## 2. What the tab looks like now

**Framing:** "Sentiment Analysis — what's in the news that will move showroom traffic, vehicle
cost and financing over the next few weeks, and what to do about it."

The mock-vs-live status is reported in the pipeline-status line after a "Refresh news" click
(`… scorer: MOCK`). An earlier build carried a persistent header badge for this; it was
removed at the stakeholder's request along with the tab's descriptive sub-captions (§8b).

**Headline (above the sub-tabs):** a signed **"Expected demand impact · next ~30 days"** —
e.g. *"−1.8% · headwind · about −20 units vs a normal month"* — beside a 3-zone
headwind / flat / tailwind gauge (range ±6%). The number is `net_demand_signal_pct`: the
group's **sales-mix-weighted** read of the scored headlines (see §3), not the old
`avg_impact × negative_ratio` index.

**Bottom line (always visible, under the headline):** a deterministic plain-language
conclusion — direction + size + horizon, the leading news-theme driver and what it exposes,
the two most-affected segments, and the one call for the week (`_bottom_line()`). This is the
"so what" the earlier repositioned tabs each close with; on a quiet news day it says so
explicitly rather than leaving the reader to infer it from near-zero charts.

### Sub-tab 1 — Demand Watch

- **What's driving the signal** — mean demand read per news theme (Economy & rates, Auto
  financing, Fuel prices, Tariffs & trade, EV market, Incentives & rebates, …), diverging
  horizontal bar, green = helps the group / red = headwind, signed direct labels.
- **By segment** — `net_demand_signal_pct`'s per-segment components (SUV / Pickup / Sedan /
  Luxury / EV), same diverging bar; caption notes the headline weights these by the group's
  own mix.
- **Signals to work** — the headlines moving the group's demand the most (ranked by
  `impact × |demand_change|`), each as a card: title (linked) · source · date · news theme ·
  **the affected segment and the group's exposure** ("hits the group's import franchises —
  about 56% of units" / "lands on the group's pickup demand") · a one-line **desk action**
  (`grok_analyzer`'s `summary`, now written as an action, not a score).
- **This week's read for the group** — a short briefing (three sections: *What's moving
  demand* / *Where the group is exposed* / *What to do this week*) generated from the current
  signals. Mock templated text unless Grok is enabled; dealer-framed either way.

### Sub-tab 2 — Does news improve our forecast?

Replaces "Forecast Comparison". Trains the group's demand forecast twice
(`use_sentiment=False` / `True`) and answers one plain question with a one-line verdict:

- *Yes* — "feeding in the news signal made the forecast about X% more accurate over the
  backtest (error N → M)."
- *No* — "adding the news signal didn't improve the forecast this period."
- *Not enough signal yet* — the news-aware model couldn't add a regressor (signal too flat).

Plus one **monthly** chart (actuals · standard forecast · news-aware forecast — Prophet's
daily output resampled to months to match the Demand Forecasting tab) and the two RMSEs as a
caption. No RMSE/MAE/accuracy grid, no regressor badges.

Everything routes through `utils/helpers.py` (`_section`, `_base_layout`, `_compact`,
`_pct_label`, `_INK*`, `_HUE_*`). One hue per job (green tailwind / red headwind / indigo
forecast / grey history), direct labels, no dual-axis. `get_color_palette` is no longer
imported here. Per §8b the header caption, the scorer badge and most section sub-captions
were removed at the stakeholder's request — the tab leans on the headline, the **Bottom
line** box and the signal cards to carry the read.

---

## 3. Code changes

| File | Change |
|---|---|
| `dashboard/sentiment_analysis.py` | Full rewrite. Signed headline number + 3-zone gauge; **Bottom line** conclusion; 2 sub-tabs (Demand Watch / Does news improve our forecast?); theme-driver bar, mix-weighted segment bar, signal cards with exposure + action, briefing; monthly forecast verdict. Shared helpers; `get_color_palette` / `_layout` / `_glass_card` / `_geo_risk_fallback` / dead `_render_*` all gone. Header caption, scorer badge and most section sub-captions removed per §8b. |
| `sentiment/signal_processor.py` | New `_group_segment_mix()` (reads the group's unit mix from `sales`, cached, static fallback) and `_net_demand_signal()` → `net_demand_signal_pct` + `segment_changes`, added to `compute_live_overall_stats` / `get_overall_sentiment_stats` / `_empty_stats`. `geopolitical_risk_score` still computed and persisted unchanged (Prophet). Comment relabel: "demand-pressure", not "geopolitical". |
| `sentiment/analyzers/grok_analyzer.py` | `_SYSTEM_PROMPT` reframed (advisor to a 24-rooftop dealer group scoring news for retail demand + dealership ops); `_BRIEFING_SYSTEM_PROMPT` reframed (weekly read for GMs / F&I desk). **JSON schema unchanged.** `affected_vehicle_category` enum gains `"Pickup"` (additive — `"Commercial"` still valid). Mock: Pickup keyword bucket; impact word-list re-weighted to dealer terms (APR, incentive, rebate, tariff, gas price…); `estimated_demand_change_pct` multiplier calibrated (`×uniform(1.5,4.0)`, capped ±6) against published elasticities; `summary` → plain dealer-action sentence (no `[MOCK]` prefix); briefing mock template rewritten in dealer terms with real segment signals. |
| `sentiment/fetchers/gdelt_fetcher.py` | Two new `NA_AUTO_QUERIES` themes: `auto_financing`, `incentives_rebates`. `luxury_suv_na` `affected_category` → `"All"` (query spans luxury *and* pickup). `COMBINED_QUERY` extended to cover them, kept to ~10 phrases (GDELT rejects an over-long query — this bit once during testing). Docstring de-OEM'd. |
| `app.py` | Menu label `"Sentimental  analysis"` → `"Sentiment Analysis"`; routing key updated. Icon unchanged (`chat-left-quote`). |
| `TECHNICAL_DOCUMENTATION.md` | §9 retitled "Sentiment & Demand-Signal Pipeline" + framing note; §9.1 (8 themes), §9.2 (prompt reframe, Pickup), §9.3 (`net_demand_signal_pct`, fallback removed), §9.4 (verdict view), §10 row, §14 gap #13, session-state keys, repo-layout line, two Mermaid labels. |

**Not touched:** the `daily_sentiment_summary` table columns and the `grok_analyzer` JSON
output schema — downstream Prophet regressors (`avg_sentiment_score`,
`geopolitical_risk_score`) depend on them. `ensure_recent_articles_analyzed()` (mock-only on
tab open) kept as-is — it's a deliberate cost control, now reflected honestly by the badge.

---

## 4. Dataset changes

**None.** This tab runs on live GDELT + the sentiment tables, not the realdata CSVs.
`preprocessing/generate_na_data.py` was not touched; the `daily_sentiment_summary` schema is
unchanged. `_group_segment_mix()` reads the *existing* `sales` table.

---

## 5. Verification

- `streamlit.testing.v1.AppTest` — `app.py` and every render function (`overview`,
  `forecasting`, `comparison`, `regional`, `customers`, `inventory`, `sentiment_analysis`) run
  in **MOCK mode** (`XAI_API_KEY=""`) with **zero exceptions and zero error boxes**. The
  sentiment tab exercised on both the empty-state path (no articles) and the populated path,
  including the "Generate read" briefing and the "Run check" forecast verdict.
- One real GDELT refresh (`timespan=30d`, mock scoring) run once to populate the tables:
  7 headlines fetched, scored, 4 daily-summary rows across All / EV / Pickup — the new
  `"Pickup"` category value flows end-to-end.
- App launched (fresh process, `XAI_API_KEY=""` so the badge reads "keyword model (demo)"),
  Sentiment Analysis tab opened, both sub-tabs screenshotted and reviewed. Iterated:
  - gauge axis had cramped ±6 endpoint ticks rendering as stray glyphs → `tickvals` reduced
    to `[-3, 0, 3]`, ticks hidden;
  - the forecast chart was Prophet's raw **daily** output (a spiky mess, and inconsistent with
    the monthly Demand Forecasting tab) → resampled to monthly, partial edge months dropped;
  - one-sided "By segment" / theme bars ran the full width with no visible zero → x-axis
    forced to span zero symmetrically.
- **`XAI_API_KEY` note:** there is an (apparently invalid — xAI returns *"Incorrect API key
  provided"*) `XAI_API_KEY` in the gitignored `.env`. All of this work and every screenshot
  was done with it overridden to empty so no live Grok call fired. The dead key should be
  removed or replaced; until then the running app will *attempt* a live call on "Refresh news"
  and fall back to mock (the pipeline status line reports this honestly).

---

## 6. Benchmarks & sources

Used to calibrate the mock `estimated_demand_change_pct` and the signal→demand framing
(cross-checked against `GROUP_DEMAND_RESPONSE` from the Demand Forecasting pass):

- **Federal Reserve FEDS Notes**, Sep 2024 — *Rising Auto Loan Delinquencies and High Monthly
  Payments*: +140bp ⇒ ~+$15/mo (~3%) on a 60-mo loan. Basis for **−3% units per +1pt APR**.
- **Brandeis WP94** — *Interest Rates and the Market for New Light Vehicles*: sales fall
  within the first **two months** of a rate shock and stay below trend for **~6 months**;
  dealers' ~3 months of stock amplify and lag the response. Basis for the **~30-day horizon**
  on the headline (leading edge) with the caveat that the full effect is slower.
- **Resources for the Future WP 23-33** — *New Passenger Vehicle Demand Elasticities*:
  own-price elasticity of all new gasoline vehicles ≈ **−0.53** (modest); gas-price effects on
  segment mix have weakened over time but a sharp gas move still shifts **~4–10%** of
  car/light-truck share. Cross-checks the Demand Forecasting pass's **−4% truck/SUV per
  +$1/gal**, small total-volume drag.
- **University of Michigan Surveys of Consumers** — car-buying attitudes lead vehicle sales by
  **~2 quarters** (time-series correlation ≈ 0.73). Basis for treating consumer-sentiment
  headlines as a **leading, low-magnitude** signal (capped ~±2%).
- **KBB / Cox Automotive** (first year of Section 232): imported vehicles **+$5,000–$8,900**,
  domestic **+$1,600–$2,000**, average MSRP **+10.4%** — reused from the Comparative Analytics
  pass. Basis for scoring tariff headlines mainly as a **cost/price** signal with a modest
  demand tilt against import segments.

Group exposure figures used in the prompt and the signal cards (from `real_demand.db`,
2026-08 reseed): **~56%** of units are import-franchise; segment mix **SUV 49% · Pickup 23% ·
Sedan 16% · Luxury 9%**; 8-state footprint.

---

## 7. How this makes the product better

1. **It answers a dealer question.** "News is running a ~2% headwind on demand over the next
   month, mostly from rate coverage — hold pickup stock, pull incentives forward on the
   segments taking the hit" is a management conversation. "Geopolitical Risk Index 0.099" was
   not.
2. **Every signal is the group's exposure.** A tariff headline is shown as *"hits the group's
   import franchises — about 56% of units"*, not an abstract impact score.
3. **Every signal has an action.** Stock / hold, pull-forward vs hold incentives, brief the
   desk on a financing talk-track — on the card, not buried.
4. **No invented numbers.** `_geo_risk_fallback()` is gone; an empty tab says "click Refresh".
5. **The forecast view asks the honest question.** "Does watching the news actually improve
   OUR forecast?" with a one-line yes/no/not-yet — not an RMSE grid that reads as model
   benchmarking.
6. **Honest about the scorer.** The post-refresh status line reports whether the keyword demo
   model or Grok produced the scores (the header badge that did this was later removed on
   request — see §8b).
7. **One visual system.** Shared helpers, one hue per job, direct labels, a caption under
   every header, no dual-axis — matches the five finished tabs.

---

## 8a. Follow-up fixes (same day — "not working as expected")

First screenshots against a live GDELT pull exposed three real problems; all fixed:

1. **The badge lied.** `is_live_mode()` only checks that a key is *set*, so with the
   invalid `.env` key the badge said "Grok AI" while every score was really the keyword
   fallback. New `_effective_scorer()` reads the last pipeline run's actual mode — the
   badge now shows **"keyword model (demo) — API key set but rejected by xAI"** (red) until
   a real Grok call succeeds.
2. **GDELT dragged in junk.** The combined OR-query pulled micro-cap "short interest"
   filings, personal-finance listicles, and local crime/accident reports. New
   `_is_relevant()` gate in `gdelt_fetcher.py` — a headline must hit an auto/retail/finance
   term and must not look like markets-wire or crime noise. On the test set it dropped
   **8 of 15** cached articles.
3. **The mock scorer mis-signed almost everything "up".** Ambiguous tokens ("rally",
   "interest", "new", "high", "sales", "demand") were treated as positive, so a
   tariff-strain headline and a fatal truck crash both scored as demand tailwinds. Fixed
   in two parts:
   - the generic positive/negative word lists were pruned to unambiguous terms only; a
     "this is an event, not a signal" gate (crash / lawsuit / theft) forces a flat,
     low-impact read; a generic direction is only called when sentiment **and** impact
     both clear a bar — so most headlines land **neutral**, the honest read for a heuristic.
   - a **theme-aware directional read** (`_theme_directional_read`): for the themes whose
     demand mechanism is established — fuel price, financing cost, tariffs, incentives —
     the mock reads whether the lever is moving up or down ("gas prices soar", "Fed cuts
     rates", "tariff refund") and maps that straight to a demand direction and the right
     segment (dearer fuel → SUV/pickup headwind, rate cut → broad tailwind, duty on →
     import headwind). Deterministic and grounded in the elasticity research, not
     sentiment-guessing.

Downstream UI: the Demand Watch tab shows real signal cards when they exist and an honest
quiet state when they don't; the **Bottom line** box distinguishes "genuinely quiet" from
"signals present but offsetting". The forecast verdict got a **±2% meaningful-difference
threshold** (it was saying "Yes — 0% more accurate"). RMSE shown to 1 decimal.
`_title_key()` de-dupes syndicated wire stories (the same headline arrived under ~5 URLs).

**The page ships populated.** A GDELT combined fetch (2026-08-31) seeded ~63 relevance-
filtered, de-duplicated real articles into `real_demand.db`; on the current feed the net
read is genuinely **mixed/flat** (Venezuela-oil-deal talk of lower gas prices offsetting
elevated Labor-Day pump prices, plus a Canada-tariff cost warning), with 6 correctly-signed
fuel/tariff signal cards. A user's own "Refresh news" replaces this with whatever is
current.

---

## 8b. Copy trim (stakeholder request)

The stakeholder asked to strip the tab's descriptive prose. Removed: the header sub-title
("What's in the news that will move showroom traffic…"), the **scorer badge** (and its
`_effective_scorer` / `_scorer_badge` helpers; `is_live_mode` import dropped — mock-vs-live
is still reported in the post-refresh pipeline-status line), the headline's "sales-mix
weighted…" footnote, and the one-line captions under *What's driving the signal*, *Signals
to work*, *This week's read for the group*, and the forecast-verdict header. Captions under
*By segment* and *Latest headlines scanned* were kept (not in the request). This departs
from the "caption under every header" convention used on the other repositioned tabs — a
deliberate, tab-specific call.

**Second trim:** the forecast sub-tab's **verdict banner** (the "Yes / No / No meaningful
difference…" sentence) and its **RMSE caption** were also removed on request. That sub-tab
is now just its header, the controls, and the overlay chart (Actual · Standard forecast ·
News-aware forecast, with the "forecast starts" marker) — the reader compares the two
forecast lines directly. `bm` / `sm` / `sent_regs` / `improve` computation dropped with it.

---

## 8. Known limitations / follow-ups

- **MOCK vs LIVE.** The mock scorer is a **keyword heuristic** — deterministic, and now
  deliberately conservative: it calls "neutral" on anything it can't read unambiguously, so
  a quiet news day shows an honest "no clear signal" rather than invented movement. It
  still cannot understand context a sentence needs ("Fed *cuts* rates" reads neutral, not
  the tailwind it is). Every mock view is badged; LIVE Grok (a valid `XAI_API_KEY`) is the
  real fix. Built and verified entirely in mock mode.
- **GDELT source quality.** `_is_relevant()` removes the worst noise, but it's a keyword
  gate — some listicle/opinion content ("5 Advantages of Body-On-Frame SUVs") still passes,
  and a genuinely relevant headline with unusual wording could be dropped. A domain
  allowlist is the stronger follow-up.
- **Forecast tail divergence.** When the sentiment regressor is near-constant, Prophet
  still extrapolates it into mild noise in the forecast window (visible as the news-aware
  line drifting late). The verdict correctly reports "no meaningful difference"; the chart
  line is a Prophet artifact, not a real signal.
- **Footprint-aware themes deferred.** All 8 GDELT themes are national. Scoping the
  demand/economy queries to the group's 8 states needs its own GDELT-syntax + rate-limit
  testing pass.
- **`net_demand_signal_pct` is a heuristic blend**, not a fitted model — mix-weighted mean of
  per-segment `estimated_demand_change_pct` with `All`-tagged headlines blended at 40%. It
  moves in the right direction and magnitude; it is not a calibrated forecast delta.
- **The forecast verdict needs signal variance.** With only a few days of news the sentiment
  regressors are near-constant and Prophet drops them — the verdict correctly says "not
  enough signal yet". It becomes meaningful after several daily refreshes accumulate.
- **`geopolitical_risk_score` keeps its legacy column name** (Prophet regressor). The UI never
  shows that phrase — it's a "demand-pressure" read — but the schema and
  `prophet_forecasting.py` still use the old name. Renaming is a cross-module change for a
  later sweep.
- **`ARCHITECTURE_OVERVIEW.md` §8** still says "Sentiment & Geopolitical Risk Pipeline" and
  describes a "Geopolitical Risk dashboard" — folded into the deferred repo-wide
  positioning-copy sweep, consistent with the earlier passes.
- **The invalid `XAI_API_KEY` in `.env`** (see §5) should be removed or replaced.
- **Exec Overview / Demand Forecasting / Comparative / Customer changelogs quote pre-earlier-
  reseed figures.** This pass did not reseed, so those baselines are unchanged by it.
- Repo-wide `use_container_width` deprecation is unrelated and still outstanding.
