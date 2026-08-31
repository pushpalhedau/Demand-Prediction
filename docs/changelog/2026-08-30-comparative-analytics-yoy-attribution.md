# Comparative Analytics §1 → YoY Attribution ("Controllable YoY")

**Date:** 2026-08-30
**Branch:** `NA-version`
**Scope:** `Comparative Analytics` tab, Section 1 ("How we're tracking vs last year") only.
**Predecessor:** `docs/changelog/2026-08-28-comparative-analytics-dealer-positioning.md`
(the repositioning pass that built this section as a plain YoY view).
**Trigger:** *"This tab is just showing the data with some graphs — how does it actually
help the end user make a decision? Give them action items, and make the section unique —
both versus other platforms and versus the other modules."*

---

## 1. Why

A "+1.4% vs last year" headline with a store leaderboard is what every dealer BI product
(CDK, Tekion, DealerSocket, vAuto dashboards) already shows. It tells a principal *the
number*, not *why it moved* or *how much of it was theirs to influence*. And it risked
overlapping the Executive Overview's new Decision Brief
(`analytics/decision_engine.py`, `2026-08-29-executive-overview-decision-brief-mvp.md`),
which is the *prescriptive* "do this, it's worth $X" tab.

This pass gives §1 a distinct job: **retrospective attribution**. Decompose the YoY move
into parts a dealer treats differently, and separate what the group *earned* from what it
was *handed*.

Four features were built (from a longer pitch; the rest — a closed-loop action ledger and
a matched-peer "copy the winner" diff — are deferred):

1. **Controllable YoY KPI**
2. **The "Us vs the group" split** on every driver (Feature 1)
3. **The YoY bridge** (Feature 2)
4. **Significance filtering** (Feature 5)

---

## 2. What shipped

The tab is split into **two sub-tabs** (`st.tabs`, matching the Executive Overview
pattern): **"How we're tracking vs last year"** (everything below) and **"Tariff exposure
by franchise"** (the repositioning pass's §2, unchanged). The 10-second performance read
and the tariff analysis each get their own space.

> **Revised 2026-08-31 (stakeholder):** subtab 1 stripped back to the trend chart + "what
> moved it". The KPI cards (Last-12 / Controllable YoY / Prior-12) and the YoY bridge
> waterfall were removed from the UI. Trend chart x-axis changed from calendar dates to
> **calendar-month names** (Jun … May): the grey "prior 12 months" line is the *same months
> a year earlier* plotted aligned, so real-date labels put 2024 data under 2025 ticks and
> read as confusing. Both date ranges are now stated explicitly in the caption, and the
> hover shows the true month/year per point. `analytics/yoy_attribution.py` keeps `summary` and
> `build_bridge` — the shift-share split and significance still drive "what moved it", and
> `summary` still resolves the window and the `comparable` guard. Sections 3–4 below
> describe the method; §2's KPI/bridge descriptions are retained for when they land
> elsewhere.
>
> **Tariff subtab rebuilt 2026-08-31 (stakeholder review — "is this adding value?").**
> The subtab was over-built: four visuals for two ideas. Changes:
> - **KPIs reframed** to lead with the decision-relevant figure: "Volume exposed to the
>   duty" (% + rooftop count), "Tariff carried into import prices" (+ an annualised
>   run-rate for the budget), "Added cost per imported unit" (+ the $ *gap* vs domestic).
> - **Chart A (monthly tariff-$ bar) cut** — it restated KPI 2 as a picture; the "the step
>   is the duty" reveal is stale in 2026 and no decision hung on it.
> - **New chart: "Did the tariff shift our mix?"** — 3-month-smoothed import-franchise
>   share of the group's units, ~24 months, with the April-2025 marker and pre/post average
>   lines. Answers "are our customers moving to our domestic rooftops" (on the current data:
>   no — held ~55%, which is itself the finding). New query `get_import_mix_monthly`.
> - **Gross caveat surfaced** — a visible caption: this is the duty in the *price*; whether
>   it hit *gross* or was passed on needs the F&I/gross feed (per DEALER_INTEGRATION_REQUIREMENTS).
> - **Chart B (price gap by segment + tariff slice) kept unchanged** — the one element with
>   a concrete per-aisle decision.
> - `get_tariff_cost_monthly` no longer called by the tab (kept defined).

New module **`analytics/yoy_attribution.py`** — pure functions over query results, no
Streamlit. Windows: the last 12 whole calendar months to the sidebar *end* date vs the 12
before (same TTM framing the repositioning pass established). All maths reconciles exactly
(`structural + specific == total` per entity; bridge steps sum to the endpoint) and is
verified across region / brand / category / narrow-window scopes.

### KPI row (was: Last-12 / Prior-12 / run-rate)

| Card | Meaning |
|---|---|
| **Last 12 months · {units\|revenue}** | window total + **total YoY %** |
| **Controllable YoY** | the same-store, selling-day-adjusted move — for revenue, also **ex tariff pass-through and ex other price/mix**. The part the group actually operated. |
| **Prior 12 months** | the comparison base |

A caption spells out, from whatever was actually material, what "controllable" removed:
e.g. *"Headline is +9.0%. Controllable strips out +\$45.4M of tariff pass-through in
sticker prices; −\$3.0M of other price & mix — leaving +1.3% on the business the group
actually operated."*

> **This is the signature number.** On the default scope, revenue is **+9.0%** but
> **+1.3% controllable** — ~7.7 pts of the gain is the Section 232 duty inflating sticker
> prices, not more or better-sold metal. No competitor dashboard surfaces this.

### Feature 2 — the YoY bridge

A waterfall under the trend chart: **Prior 12 months → Selling days → Rooftops
opened/closed → [revenue only: Tariff pass-through → Price & mix] → Comp volume → Last 12
months**. Zero-value steps are dropped; tiny ones fold into "Other". The y-axis zooms to
the band the steps live in so a +258-unit step isn't an invisible sliver on a 15,000 base.

### Feature 1 — "what moved it", as a shift-share split

Each store / franchise / segment's YoY change is split against the group as the benchmark:

- **structural** = what it would have done growing at the group's same-store rate
- **specific** = the residual it owns

The chart shows only the **specific** part (green = its own gain, red = its own loss),
because that is the actionable half; the group-wide rate that was removed is stated in the
caption. Sorted by |specific|, capped for legibility. Hover carries the total.

A **sibling read** for stores: where the group runs ≥2 rooftops of a franchise, the
narration says whether the franchise-mates moved the same way ("read it as the franchise,
not the store") or not ("this is the rooftop"). Where the group runs only one rooftop of a
marque, it says the franchise cycle and the store can't be separated from internal data —
rather than pretending to.

Two or three **plain-language sentences** are generated under the chart, e.g.
*"Lexus of Cincinnati is 66 units behind last year. At the group's pace it should have
been about +6; the −72 beyond that is rooftop-specific — the group runs no other Lexus
rooftop, so the franchise cycle and the store can't be separated from this data alone."*

### Feature 5 — significance

For each entity, its observed rolling-12-month YoY move is z-scored against the
distribution of its **own** rolling-12-month YoY moves across all history. `|z| ≥ 1.5`
(with ≥ 8 YoY observations and a σ floor) flags it as "outside its normal swing"; a
relative-outlier fallback covers short histories. Flagged entities carry a ★ and full
opacity; the rest are dimmed. When ≥ 3 are flagged, a checkbox narrows the chart to just
those. On the synthetic dataset most rooftops genuinely sit within their normal range —
the honest read is "one store, Lexus of Cincinnati, moved unusually; start there."

---

## 3. Method notes (why it's defensible, and its limits)

- **"Controllable" is a same-store, day-adjusted comp** — the standard retail metric. It
  does **not** claim to strip out segment demand or a franchise product cycle at the group
  level, because with only internal data any relative decomposition of the group total
  nets to zero. It removes exactly what can be cleanly measured: M&A (rooftop count),
  the calendar (distinct selling days), and — for revenue — tariff dollars
  (`Sale.tariff_cost_usd`) and the residual price/mix effect.
- **The per-entity split IS a real market-vs-execution split**, because one store/brand/
  segment has a legitimate external benchmark (the rest of the group).
- **Selling days** = count of distinct `sale_date` values in each window (captures leap
  years, and any scope/coverage gaps).
- **Nothing is hard-coded.** No dates, no growth rates, no store names, no thresholds tied
  to the data. The only constants are statistical (`z = 1.5`, min history = 8 points, a σ
  floor). Change the database and every figure, sentence and bar recomputes.

---

## 4. Files

| File | Change |
|---|---|
| `analytics/yoy_attribution.py` | **new** — `resolve_windows`, `build_bridge`, `summary`, `driver_split`, `_significance`, `movement_sentences` |
| `dashboard/comparison.py` | §1 rewritten: Controllable-YoY KPI + caption, `_render_bridge`, `_render_drivers` (shift-share split + significance + sentences). Drops the old `get_yoy_drivers` call. `$` escaped in `st.markdown`/`st.caption` (Streamlit was rendering it as LaTeX). |
| `database/queries.py` | `get_yoy_drivers` retained but no longer called by the tab (superseded by `driver_split`); left with the other deprecated helpers. |
| `TECHNICAL_DOCUMENTATION.md` | §10 `comparison.py` row updated. |

---

## 5. Verification

- `streamlit.testing.v1.AppTest` — every render function, zero errors / exceptions;
  Comparative also exercised with Revenue + brand filter and a pre-tariff window.
- `analytics/yoy_attribution` reconciliation checked (`structural+specific==total`,
  bridge sums) across default / region=Florida / brand=Ford / category=Sedan / a 2024
  calendar-year window.
- App launched, both measures screenshotted and reviewed; iterated: bridge y-axis zoom so
  small steps show; driver chart reduced from a grouped structural+specific bar (the
  tariff-inflated grey bar dominated every revenue row) to a specific-only bar with the
  group rate in the caption; negative-bar labels anchored at the zero line to clear the
  y-axis gutter; `$`→LaTeX escaping.

---

## 6. Known limitations / next

- **Controllable YoY ignores the sidebar start date** (it's TTM-anchored to the end date),
  same as the repositioning pass and Exec Overview's Target Attainment. Stated in the
  section header.
- **Group-level demand vs execution is not separated** — see §3. A real external
  new-vehicle-sales series (regional) would let "structural" mean "the market", not "the
  rest of the group".
- **Sparse significance on the synthetic data.** The generator has little genuine
  store-to-store variance, so usually only 1–2 entities clear the z-gate. On real DMS data
  with real operational spread the flagged list will be richer.
- **Not yet built** (from the pitch): the closed-loop **action ledger** (assign an owner +
  due date to a flagged item, and have the next visit grade whether it worked) and the
  **matched-peer playbook diff** ("Chevy SD closes in 11 days at 78% F&I; Chevy NYC in 19
  at 61% — start there"). Both need a small persistence store.
