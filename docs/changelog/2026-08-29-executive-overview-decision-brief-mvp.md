# Executive Overview → Decision Brief (MVP)

**Date:** 2026-08-29
**Branch:** `NA-version`
**Scope:** `Executive Overview` tab — turn it from a performance dashboard into a
decision tab.

---

## 1. Why

A "how did the business do" dashboard — KPI cards + trend + mix charts — is
something Tableau / Domo / DealerSocket already do. It doesn't help the people at
the top *decide* anything. The brief for this pass: make Executive Overview
produce **business-development decisions**, quantified, that a competitor's
dashboard can't — because they require joining a forward projection with the
current stock position, each store's own plan and economics, and turning that
into a ranked action list with dollars attached.

## 2. What shipped (MVP)

The tab is split into **two sub-tabs** (`st.tabs`) so the 10-second performance
read and the decision brief each get their own space:

- **Overview** — the KPI row + revenue/unit trend + category & fuel mix +
  sales-by-store (with a group-average line) + top models. The glance.
- **Recommendations** — the Decision Brief below.

### Recommendations sub-tab

1. **Hero band (3 tiles)**
   - *12-Month Landing* — forward projection vs. the sum of the stores' unit
     plans (e.g. "95% of plan · −794 units · $3.3M gross").
   - *Gross at Stake* — total modelled impact of the plays below.
   - *Gap to Close* — units/store/month needed to hit plan.

2. **The Decision Brief** — up to 5 prescriptive plays, ranked by
   `modelled impact × confidence`, one per store (the single biggest thing to
   fix there). Each card: category, confidence, the action, a rationale with the
   specific numbers, and a dollar figure. Current live examples:
   - *Ford of Savannah is running 86% of plan and slipping* — $592K
   - *Sedan demand is projected down 9% — and you're long on it* — $354K
   - *$2.1M of capital aging at Tesla of Houston* — $132K
   - *Deals at BMW of Jacksonville take 9 days longer to close* — $145K

3. **Where the year lands** — monthly units, actual → seasonal run-rate
   projection for the next 12 months, against the network's plan pace.

4. **Supporting detail** — the old KPI row + trend + mix + store + model charts,
   collapsed into an expander.

## 3. How it's built

New module: **`analytics/decision_engine.py`** (no Prophet — the tab retrains
nothing, so projections are a fast seasonal run-rate model in pandas).

| Piece | Method |
|---|---|
| `project_year_end()` | Deseasonalise the group's monthly units (month-of-year index over 36 mo), take the trailing-6-month level + a clamped drift, reseasonalise 12 months forward. Compare the sum to `Σ Dealer.annual_target_units` (filter-scoped). |
| `generate_plays()` | Run 7 rule-based generators, filter sub-$20K items, keep one play per store, rank by impact × confidence. |

Play generators, each traceable to a query + one benchmark constant:

| Generator | Fires when | Impact model |
|---|---|---|
| **Target** | store's TTM attainment < 92% **and** last-90-day run-rate < 88% of plan (both signals must agree — one noisy quarter on a small store doesn't trigger it) | unit gap × gross/unit |
| **Demand** | a segment's 12-mo projection is down >8% while the lot carries >55 days' supply | softening volume × gross/unit × 0.4 |
| **Inventory** | >$400K or >20 units sitting 90+ days at a store | 6% quarterly value erosion + 90-day floorplan |
| **Margin** | mix-adjusted "true concession" (discount + trade over-allowance + trade bonus) runs >$600/unit above peers | excess × TTM units × 0.5 recoverable |
| **Allocation** | one store <32 days' supply of a segment while another has >78 | movable units × gross/unit × 0.6 turn |
| **Velocity** | store's avg lead-to-close is >6 days above the group median | delay-proportional unit drag × gross/unit × 0.5 |
| **F&I** | store's non-cash penetration is >5 pts below the group median | half the gap × TTM units × $2,000 F&I/deal |

## 4. Benchmark constants (in `decision_engine.py`)

| Constant | Value | Basis |
|---|---|---|
| `GROSS_PER_NEW_UNIT` | $4,200 | blended front-end + F&I gross per new unit, US franchised dealers 2024 (NADA / Haig Report range ~$4,000–4,600) |
| `FNI_GROSS_PER_DEAL` | $2,000 | incremental F&I gross on one more financed deal (finance reserve + product), conservative vs. ~$2,400 industry avg |
| `RECOVERABLE_SHARE` | 0.5 | assumed share of an identified gap actually closable |
| aged-unit value erosion | 6% / quarter | floorplan interest (~8%/yr) + incremental markdown to move an aged unit |

These are the **only** non-data inputs to a dollar figure on a card. A dealer
replaces them with their own actuals once real gross / F&I data is connected
(per `DEALER_INTEGRATION_REQUIREMENTS.docx`).

## 5. Files

| File | Change |
|---|---|
| `analytics/__init__.py`, `analytics/decision_engine.py` | **new** — projection + play engine |
| `dashboard/overview.py` | rewritten: Decision Brief hero + play cards + landing chart; old charts moved into a `Supporting detail` expander; uses the shared `utils/helpers.py` tokens |

## 6. Known limitations / next

- **The synthetic dataset has little store-to-store variance** (it's generated
  from per-brand uniform distributions), so the generators find only a handful
  of real outliers — the brief currently leans on the same 3–4 stores. On real
  dealer data with genuine operational spread it will be richer. Some thresholds
  are tuned loose to keep the demo brief populated; tighten on real data.
- **No real gross / F&I / ad-spend / traffic feed** — every dollar figure is
  benchmark × the group's volumes. The high-value plays from the original pitch
  (Capital Allocation optimiser, precise Expansion white-space, live margin P&L)
  need that data.
- **Projection is a run-rate model, not Prophet.** Fine for a 12-month landing
  at group grain; the per-store Target play deliberately cross-checks TTM
  attainment against 90-day pace rather than trusting a per-store projection.
- Not yet built from the pitch: Franchise Portfolio Scorecard (grow/hold/fix/
  exit), Early-Warning Radar as a standalone, drill-through from a play card to
  the evidence.
- `_HUE_BAND` import in `overview.py` is now unused (harmless).
