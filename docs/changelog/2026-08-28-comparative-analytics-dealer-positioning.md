# Comparative Analytics — Dealer-Facing Repositioning

**Date:** 2026-08-28
**Branch:** `NA-version`
**Scope:** `Comparative Analytics` tab (module #3 in the module-by-module positioning pass)
**Trigger:** Same stakeholder feedback as the earlier passes — *"This is a dealer-facing
solution, not an OEM solution — confirm this positioning across the platform."*
**Predecessors:**
`docs/changelog/2026-08-27-executive-overview-dealer-positioning.md`,
`docs/changelog/2026-08-27-demand-forecasting-dealer-positioning.md`

---

## 1. Why this changed

This was the tab with the most genuine OEM / equity-analyst content on the platform.
It computed **market share** — "% of the Total US Market", "Import Brand Share",
"Domestic EV Segment Share of total US EV market", a **2027 import-share projection**
(`np.polyfit` on ~4 yearly points) — all from the group's **own 24-rooftop book**. A
single dealer group has a *sales mix*, not market share, and cannot see the national
industry, so those "% of US market" labels were literally wrong, not just off-tone.

| OEM-style element (before) | Problem for a dealer |
|---|---|
| Section header **"Import Tariff Exposure"** → "Domestic vs. Import **brand share**" | Manufacturer-vs-manufacturer framing of the group's own deal count. |
| Chart **"Brand Origin Market Share Growth"**, y-axis **"% of Total US Market"** (twice) | The number is % of *the group's* units. The label was wrong. |
| KPI **"Domestic EV Segment Share (2026) — of total US EV market"** | It's the group's own EV sales mix, anchored by Tesla. Not a market. |
| KPI **"Projected 2027 Import Share — based on 2022-2026 trend"** | Equity-analyst extrapolation of a market the dealer doesn't operate in, off a 4-point linear fit. |
| Chart **"Import Brands vs Total Market Volume"** — **dual-axis** | Dual-axis is banned by the glance-first system; "Total Market" = group total, mislabelled. |
| Chart **"Market Share Shift — who gained, who lost"** (★ = import) | Winners-and-losers scoreboard on 24 rooftops; compared a full base year to a partial 2026. |
| `_filters_no_brand` forcing every tariff query to **ignore the brand filter** "so the section always shows the full market" | Textbook OEM competitive-intelligence pattern. |
| **"Regional Growth Matrix"** = revenue by US **state** | District-manager / national-footprint framing (the Exec Overview pass already replaced its state bar with "Sales by Store"). |
| **"Year-over-Year Overlap Analysis"** — one line per calendar year, summary hard-coded to the latest 2 years regardless of the sidebar window | Substance was dealer-relevant; the title and the logic weren't. |
| Local `_BASE_LAYOUT` / `_ORIGIN_COLORS`, no shared helpers | Predated the glance-first system; guaranteed drift from the two finished tabs. |

**Product decisions taken** (confirmed with the stakeholder before building):

1. **Tariff section → reframe, don't cut.** Option (b): *"Tariff Exposure by Franchise"* —
   what the 25% Section 232 duty costs the group's **import-brand rooftops** specifically,
   and how it sits inside the price against the **domestic** models the group also sells.
   The group carries both, so this is a real question for them. All share-of-market and the
   2027 projection are gone.
2. **Core YoY view → group total + drill-down, Units & Revenue.** Headline is the whole
   group; below it, a "what moved the number" breakdown that toggles
   **store / franchise / segment**. No modeled gross (would need a cost basis the dataset
   doesn't carry — deferred). The comparison is **trailing-12-months vs the prior 12**,
   anchored to the sidebar's *end* date (not the full multi-year window) — see §2 and §7.

---

## 2. What the tab looks like now

**Framing:** "Comparative Analytics — how the group is tracking against last year, by
store, franchise and segment, and where the 25% import tariff is landing."

### Section 1 — How we're tracking vs last year (12 months to <end month>)

- **Measure toggle:** Units / Revenue.
- **Trailing-12-month framing.** Anchored to the sidebar *end* date; always compares the
  **last 12 whole calendar months to the 12 before**. The sidebar *start* date does not
  affect this section (it still drives Section 2 and the other tabs). This is the same
  pattern Executive Overview uses for Target Attainment, and it's the window a GM actually
  means by "how are we tracking vs last year".
- **Headline row (3 cards):** Last 12 months (+ % vs prior 12) · Prior 12 months ·
  Monthly run-rate.
- **Trend chart:** monthly booked units/revenue, last 12 months (indigo) over the 12 before
  (grey dotted), aligned by calendar month, with an in-chart headline
  ("15K units in the last 12 months · +1.4% vs the 12 before"). No dual axis.
- **"What moved the number" — by store / franchise / segment:** diverging horizontal bars,
  change vs the prior 12 months, green = ahead / red = behind, signed direct labels.
  On the default view this shows **9 of 24 stores down** — a real winners/losers picture,
  not the "everything grew" artefact a multi-year window produced. Stores capped to the 8
  biggest gains + 8 biggest drops.

### Section 2 — Tariff Exposure by Franchise

- **Sub-header:** "The 25% Section 232 duty on imported vehicles (effective April 2025)
  lands on the group's *N* import-brand rooftops (of 24)…"
- **Headline row (3 cards):** Imported units since Apr 2025 (share of the group's sales) ·
  Tariff cost carried into those stickers ($) · Added cost per imported unit
  (vs the domestic figure).
- **"Tariff cost carried into stickers, by month":** monthly Section 232 dollars baked into
  selling prices, single hue, with a "25% duty starts" marker on April 2025 (Jan–Mar 2025
  sit at zero so the step is obvious).
- **"What a shopper pays — and the tariff inside it, by segment":** per segment, the import
  bar (vehicle price + a red Section 232-duty slice) above the domestic bar (the alternative
  the group also sells), total prices direct-labelled. Shown only for segments with **≥150
  units on both sides** — a genuine cross-shop. On the default view that's **Pickup, SUV,
  Sedan**; Luxury is excluded (the group's only domestic-luxury nameplate is Tesla, so
  "domestic vs import luxury" isn't like-for-like), as are thin one-sided cells
  (Minivan, Coupe, Hatchback).
- **Plain-language takeaway:** *"Since April 2025 the group has retailed 9.7K imported units
  carrying $51.5M of Section 232 tariff cost — about $5,299 per imported unit, versus $1,788
  on a domestic one. The duty is heaviest on imported Pickup at about $5,507 a unit."*

Everything routes through the shared `utils/helpers.py` system (`_section`, `_base_layout`,
`_fmt_money`, `_compact`, `_pct_label`, `_INK*`, `_HUE_*`). Import vs domestic read as
**amber vs sky** so they can't be confused with the green/red "ahead/behind" hues used in
Section 1.

---

## 3. Code changes

| File | Change |
|---|---|
| `database/models.py` | `Sale` gains `tariff_cost_usd` (Integer) — the Section 232 dollars inside a deal's sticker; 0 before April 2025. |
| `preprocessing/generate_na_data.py` | Tariff pass-through reworked (see §4). New `tariff_cost_usd` column emitted. |
| `preprocessing/clean_data.py` | `clean_sales` median-safe-fills `tariff_cost_usd` (guarded on presence). |
| `database/queries.py` | **New:** `get_period_trend`, `get_yoy_drivers`, `get_tariff_exposure`, `get_tariff_cost_monthly`, `get_price_gap_by_segment`, `get_franchise_footprint`. **Deprecated (kept, docstring-flagged):** `get_brand_origin_yearly_share`, `get_ev_segment_by_brand_year`, `get_market_share_shift`; `get_yoy_comparison` marked superseded. `IMPORT_BRANDS` / `BRAND_ORIGIN` / `_filters_no_brand` retained. `get_price_competitiveness` retained (now unused by the tab). |
| `dashboard/comparison.py` | Full rewrite. Two sections, shared helpers, no dual-axis, no share-of-market, no `np.polyfit` projection, `_BASE_LAYOUT`/`_ORIGIN_COLORS` deleted. `get_sales_by_region` (state revenue bar) dropped from the tab. |
| `TECHNICAL_DOCUMENTATION.md` | §5.4 query notes, §10 `comparison.py` row, §14 gaps (#11–#12) updated. |
| `realdata-datasets/DATA_DICTIONARY.md` | Section 232 pass-through rates + `tariff_cost_usd` documented. |

Queries left defined but no longer called by any tab (per the "don't delete in case another
module claims it" constraint): `get_brand_origin_yearly_share`,
`get_ev_segment_by_brand_year`, `get_market_share_shift` (deprecation docstrings added),
plus `get_price_competitiveness`, `get_yoy_comparison` and `get_sales_by_region` (kept
generic, no docstring change). `get_sales_by_category` is untouched — still used by
`overview.py`.

---

## 4. Dataset changes (`preprocessing/generate_na_data.py`, real dataset only)

Regenerated `realdata-datasets/*` and reseeded `real_demand.db` (dropped the file so the
new column takes). Test dataset (`automobile_datasets/`) regenerated by the same `main()`,
unused by the app.

| Change | Before | After | Rationale / benchmark |
|---|---|---|---|
| **Section 232 pass-through** | import brands only, `tariff/100 × 0.5` = **+12.5%** on base; domestic **0%** | import brands **+15%** (`0.60 × 0.25`); domestic brands **+4.5%** (materials/imported-parts duties) — both from April 2025 | KBB/Cox Automotive, first year of the tariff: imported vehicles **+$5,000–$8,900**, domestic **+$1,600–$2,000**, average MSRP **+10.4%**. "Domestic = exempt" was wrong — domestic-*brand* ≠ domestic-*built*, and parts/materials duties still bite. Realised in the data: **$5,296** per imported unit, **$1,789** per domestic unit. |
| **New column `tariff_cost_usd`** | — | `base_price_pre_tariff × markup`, stored per deal (0 pre-April-2025) | So Comparative Analytics reads the group's real per-franchise tariff cost instead of reconstructing it from `base_price_usd` and a hard-coded rate. |

**Blast radius (accepted, small):** the Exec Overview default window (2021-01→2026-05) moves
from **71,830 units / $2.95B** to **71,830 units / $2.98B** — units unchanged (the tariff is
a price effect, not a volume one in the generator); revenue **+~0.9%**, concentrated in the
14 tariff-era months, which nudges the revenue-YoY KPI up ~1pt (2025–26 ATP genuinely rose
~10% with the tariff, so this is directionally right). All tabs verified rendering with zero
errors (§5).

**Checked and left alone:** the sale-level `tariff_markup` mechanism already existed in
`build_sales`; only the rates and the stored-column were changed. Retail seasonality, the
four demand levers, financing/trade-in/lease logic — all untouched.

---

## 5. Verification

- `streamlit.testing.v1.AppTest` — `app.py` plus every render function (`overview`,
  `forecasting`, `comparison`, `regional`, `customers`, `inventory`,
  `sentiment_analysis`) run with **zero exceptions and zero error boxes**.
- Comparative Analytics exercised across toggles and filters: Units/Revenue ×
  store/franchise/segment; `region=California` + `brand=Toyota` (the group has no Toyota
  rooftop in CA → empty window, handled with a friendly message, not a crash); a
  pre-April-2025 window (tariff section shows its "widen the date range" info state).
- App launched, Comparative Analytics screenshotted and reviewed; iterated:
  `get_tariff_exposure` was missing its `group_by(Sale.brand)` (returned one aggregate row
  mislabelled "Toyota") — fixed; the price-gap chart's legend swatch didn't match its
  per-bar colours → split into three single-hue traces (import price / import duty /
  domestic price); coarse `$5K`-style rounding on per-unit figures → exact `$5,299`;
  dropped a weak 17-row "rooftops by franchise" bar in favour of a one-line count in the
  sub-header.
- **Credibility review of the displayed numbers** (prompted by the question "are these
  believable to a client"): the original Section 1 compared the whole 65-month sidebar
  window to a 65-month window shifted back a year and labelled it "vs last year" — the KPI
  read "72K units this period" (5 years of sales) and every one of the 24 stores showed
  green (everything grows over 5 years). Reworked to trailing-12-vs-prior-12 (§2). Now:
  **14,770 units, +1.4% vs the prior 12** (real US new-retail was ≈+2% in 2025), **9 of 24
  stores down**. Price-gap chart tightened to real cross-shop segments only.

---

## 6. Benchmarks & sources

- **Kelley Blue Book / Cox Automotive** — *Tariff Costs: New-Car Prices Up ~10% Since Last
  Year* and the September-2025 ATP report: imported vehicles **+$5,000–$8,900**, domestic
  **+$1,600–$2,000**, industry **~$30B** added cost in year one, average MSRP **+10.4%**;
  new-vehicle ATP $47,462 (Mar 2025) → $48,699 (Apr) → **$50,080** (Sep 2025, first ever
  above $50K).
- **CBP / Congressional Research Service** — Section 232 automotive tariffs: 25% on
  imported vehicles effective **April 3, 2025**, parts May 3, 2025.
- **Cox Automotive** — 2025 US new-vehicle sales ~16.2–16.3M, **+~2% YoY** (best since 2019);
  2023 **+~12%** off the 2022 chip-shortage trough (2022 **−8%** YoY), 2024 **+2.5%**.
- **Presidio-NCM Average Dealership Performance Benchmark (FY2024)** — front-end gross per
  new vehicle: domestic **$1,952**, import **$1,699**, luxury **$5,679**; both down ~25% YoY.
  (Context for the deferred "estimated gross" measure — not modelled this pass.)

---

## 7. How this makes the product better

1. **The labels are true now.** "% of the US market" — computed from 24 rooftops — is gone.
   Every number on the tab is the group's own booked business.
2. **A YoY view a GM acts on.** "We're +7% on units, +$28M on Toyota, −X at these three
   stores" is a management conversation. "Import brand share is 55.7%, projected 54.9% in
   2027" was not.
3. **The tariff question a dual-franchise group actually has.** Not "who's winning the US
   market" but "what is Section 232 costing our import rooftops, and how big is the duty
   inside the price a shopper compares against our domestic models" — answered from their
   own deals, in dollars.
4. **One visual system.** Shared helpers, one hue per job, direct labels, a caption under
   every header, no dual-axis — matches Executive Overview and Demand Forecasting.
5. **Real tariff economics in the data.** Import +15% / domestic +4.5% pass-through and a
   per-deal `tariff_cost_usd` column, both benchmarked to KBB/Cox — so "this shows what the
   tariff costs us" is literally true rather than a hard-coded rate applied at render time.

---

## 8. Known limitations / follow-ups

- **Section 1 ignores the sidebar *start* date.** It is trailing-12-vs-prior-12 anchored to
  the *end* date. This is deliberate (a GM means "the last year" by "vs last year"), matches
  Exec Overview's Target Attainment, and is stated in the section header — but a user who
  sets a narrow window expecting a narrow comparison will get 12 months regardless.
- **Per-rooftop volume (~615 new units/yr in 2025) is ~35% below the NADA ~950 average** —
  same caveat the Exec Overview pass logged: consistent with an import/value-skewed group in
  mid-size metros, not tuned further. The *trend* and *YoY* are realistic; the absolute
  per-store level is conservative.
- **Per-unit revenue (~$41K incl. tax & F&I; ~$36K vehicle) vs a real ~$48–50K ATP.** The
  catalog carries base-ish 2019–24 trims. Revenue is directionally right but low; the
  *percentages* (YoY, tariff-as-%-of-price) are unaffected.
- **Domestic-Sedan cell is thin** (~450 units/yr, essentially one nameplate) so its ~$32.7K
  average is noisier than the SUV/Pickup bars next to it.
- **No estimated gross.** `Sale` has no cost/invoice column, so the Units/Revenue toggle
  has no third "gross" option. Adding one needs a modelled cost basis (import brands carry
  the tariff in cost too) and a reseed — deferred, per the stakeholder decision.
- **Deprecated queries still defined.** `get_brand_origin_yearly_share`,
  `get_ev_segment_by_brand_year`, `get_market_share_shift` are docstring-flagged and unused;
  remove once no module claims them. Same for `get_price_competitiveness` /
  `get_yoy_comparison` (kept generic).
- **German luxury is underpriced in the catalog** (BMW/Mercedes ATP ~$53–55K vs a real
  ~$65–75K). It no longer distorts a chart (Luxury is excluded from the price-gap view), but
  it's why the group's overall vehicle ATP runs low.
- **Exec Overview / Demand Forecasting changelogs quote pre-this-reseed figures.**
  Re-baseline when those tabs get their next pass; revenue is ~1% higher post-tariff-rate
  change.
- Repo-wide `use_container_width` deprecation is unrelated and still outstanding.
- `README.md` / `ARCHITECTURE_OVERVIEW.md` still say "North American automobile businesses" /
  "NA market dataset" — full copy sweep deferred until all module passes land.
