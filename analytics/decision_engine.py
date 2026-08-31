"""
Executive decision engine — turns the dealer group's own transaction and
inventory data into a ranked list of prescriptive plays, each with a modelled
dollar impact and a confidence, plus a forward 12-month landing vs. plan.

This is what makes the Executive Overview a decision tab rather than a set of
charts: BI tools show what happened; this joins a forward projection with the
current stock position, each store's own economics and plan, and turns it into
"do this, it's worth roughly $X".

Deliberately NOT Prophet: the Overview tab retrains nothing and must stay
responsive, so projections here are a fast seasonal run-rate model in pandas.
The plays are rules over the group's data, not an ML model — every number on a
card is traceable to a query result and one of the benchmark constants below.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import func, case

from database.models import Sale, Dealer
from database.queries import (
    _apply_sale_filters,
    _shift_years,
    get_inventory_snapshot,
    get_dealer_performance_leaderboard,
)

# ─────────────────────────────────────────────────────────────────────────────
# Benchmark constants (US franchised new-vehicle retail, 2024-25).
# Sources are listed in the tab's changelog. These are the ONLY non-data inputs
# to a dollar figure on a card; a dealer replaces them with their own actuals
# once real gross / F&I data is connected (see DEALER_INTEGRATION_REQUIREMENTS).
# ─────────────────────────────────────────────────────────────────────────────
GROSS_PER_NEW_UNIT = 4_200      # blended front-end + F&I gross per new unit
FNI_GROSS_PER_DEAL = 2_000      # incremental F&I gross on one more financed deal
RECOVERABLE_SHARE = 0.5        # share of an identified gap realistically closable
TURN_ON_TRANSFER = 0.6        # prob. a transferred unit actually sells in 60d
AGED_MARKUP_PER_UNIT_MONTH = 250   # extra markdown taken per aged unit per month

_CONF_WEIGHT = {"High": 1.0, "Medium": 0.65, "Low": 0.4}


@dataclass
class Play:
    category: str            # Allocation | Target | Margin | Inventory | F&I
    title: str               # the action, imperative
    detail: str              # one or two sentences with the specific numbers
    impact_usd: float        # modelled gross impact / gross at stake
    horizon: str             # e.g. "next 60 days"
    confidence: str          # High | Medium | Low
    store: str | None = None
    tags: list = field(default_factory=list)

    @property
    def rank_score(self) -> float:
        return self.impact_usd * _CONF_WEIGHT.get(self.confidence, 0.5)


_CATEGORY_ACCENT = {
    "Allocation": "#6366f1",
    "Target": "#f59e0b",
    "Margin": "#ef4444",
    "Inventory": "#06b6d4",
    "F&I": "#10b981",
    "Velocity": "#a855f7",
    "Demand": "#ec4899",
}


def category_accent(category: str) -> str:
    return _CATEGORY_ACCENT.get(category, "#6366f1")


# ─────────────────────────────────────────────────────────────────────────────
# Fast seasonal projection
# ─────────────────────────────────────────────────────────────────────────────
def _monthly_units(session, filters: dict, by_store: bool = False) -> pd.DataFrame:
    """Booked units per calendar month (optionally per store) over ALL history —
    the sidebar date window is ignored so the seasonal shape is stable."""
    tf = {k: v for k, v in (filters or {}).items()
          if k not in ("start_date", "end_date")}
    cols = [Sale.year, Sale.month]
    if by_store:
        cols = [Sale.dealer_id] + cols
    q = session.query(*cols, func.sum(Sale.units_sold).label("units"))
    q = _apply_sale_filters(q, tf).group_by(*cols)
    df = pd.read_sql(q.statement, session.bind)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1))
    return df.sort_values("date")


def _project_series(s: pd.Series, months_ahead: int = 12) -> pd.Series:
    """s: monthly values indexed by month-start Timestamp, sorted ascending.
    Returns a Series of `months_ahead` future months (seasonal run-rate)."""
    s = s.astype(float).sort_index()
    # drop a trailing partial month (common: data ends mid-month)
    if len(s) >= 2 and s.iloc[-1] < 0.55 * s.iloc[-13:-1].mean():
        s = s.iloc[:-1]
    if len(s) < 6:
        base = s.mean() if len(s) else 0.0
        idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1) if len(s) else pd.Timestamp.today(),
                            periods=months_ahead, freq="MS")
        return pd.Series(base, index=idx)

    hist = s.tail(36)
    by_month = hist.groupby(hist.index.month).mean()
    seas = (by_month / hist.mean()).reindex(range(1, 13)).fillna(1.0)

    deseason = s / s.index.month.map(seas)
    level = deseason.tail(6).mean()
    mom = deseason.tail(13).pct_change().tail(12).median()
    drift = float(np.clip(mom if np.isfinite(mom) else 0.0, -0.025, 0.025))

    future_idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1),
                               periods=months_ahead, freq="MS")
    out = []
    for i, ts in enumerate(future_idx, start=1):
        out.append(max(level * (1 + drift) ** i * seas.get(ts.month, 1.0), 0.0))
    return pd.Series(out, index=future_idx)


def _annual_target(session, filters: dict) -> int:
    q = session.query(func.coalesce(func.sum(Dealer.annual_target_units), 0))
    f = filters or {}
    if f.get("region"):
        q = q.filter(Dealer.state == f["region"])
    if f.get("city"):
        q = q.filter(Dealer.city == f["city"])
    if f.get("brand"):
        q = q.filter(Dealer.brand == f["brand"])
    return int(q.scalar() or 0)


def project_year_end(session, filters: dict) -> dict:
    """Forward 12-month projection for the in-scope group vs. the sum of the
    stores' own annual unit targets."""
    m = _monthly_units(session, filters)
    if m.empty:
        return {}
    s = m.set_index("date")["units"]
    proj = _project_series(s, 12)

    n_stores = session.query(func.count(Dealer.dealer_id))
    f = filters or {}
    if f.get("region"):
        n_stores = n_stores.filter(Dealer.state == f["region"])
    if f.get("city"):
        n_stores = n_stores.filter(Dealer.city == f["city"])
    if f.get("brand"):
        n_stores = n_stores.filter(Dealer.brand == f["brand"])
    n_stores = int(n_stores.scalar() or 1)

    target = _annual_target(session, filters)
    proj_units = float(proj.sum())
    attainment = (100.0 * proj_units / target) if target else None
    gap = (target - proj_units) if target else 0.0
    ttm = float(s[s.index > pd.Timestamp(_shift_years(s.index.max().date(), 1))].sum())

    # tidy history for the chart (last 18 months of complete data)
    hist = s.copy()
    if len(hist) >= 2 and hist.iloc[-1] < 0.55 * hist.iloc[-13:-1].mean():
        hist = hist.iloc[:-1]
    hist = hist.tail(18)

    return {
        "history": hist,
        "projection": proj,
        "projected_12m_units": proj_units,
        "annual_target": target,
        "attainment_pct": attainment,
        "unit_gap": gap,                       # +ve = short of plan
        "gap_per_store_month": (gap / n_stores / 12) if n_stores else 0.0,
        "ttm_units": ttm,
        "n_stores": n_stores,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Play generators
# ─────────────────────────────────────────────────────────────────────────────
def _play_allocation(snap: pd.DataFrame) -> list[Play]:
    if snap.empty:
        return []
    g = snap.assign(daily=snap["demand_forecast_30d"].clip(lower=0) / 30.0)
    grp = g.groupby(["dealer_name", "vehicle_category"]).agg(
        stock=("current_stock", "sum"), daily=("daily", "sum")
    ).reset_index()
    grp = grp[grp["daily"] > 0.08]
    grp["dos"] = (grp["stock"] / grp["daily"]).round(0)

    HEALTHY = 45.0
    plays: list[Play] = []
    for cat, sub in grp.groupby("vehicle_category"):
        surplus = sub[sub["dos"] > 78].sort_values("dos", ascending=False)
        deficit = sub[sub["dos"] < 32].sort_values("dos")
        if surplus.empty or deficit.empty:
            continue
        sup, defc = surplus.iloc[0], deficit.iloc[0]
        movable = int(min(
            max(sup["stock"] - sup["daily"] * (HEALTHY + 15), 0),
            max(defc["daily"] * HEALTHY - defc["stock"], 0),
        ))
        if movable < 4:
            continue
        tight = defc["dos"] < 18
        impact = movable * GROSS_PER_NEW_UNIT * TURN_ON_TRANSFER
        plays.append(Play(
            category="Allocation",
            title=f"Move ~{movable} {cat.lower()} units to {defc['dealer_name']}",
            detail=(
                f"{defc['dealer_name']} is down to {defc['dos']:.0f} days' supply of "
                f"{cat.lower()}s{' (stockout risk)' if tight else ''}, while "
                f"{sup['dealer_name']} is sitting on {sup['dos']:.0f} days. Rebalancing "
                f"puts sellable metal where the demand is instead of aging on one lot."
            ),
            impact_usd=impact,
            horizon="next 60 days",
            confidence="High" if tight and sup["dos"] > 95 else "Medium",
            store=defc["dealer_name"],
            tags=[cat, "inventory transfer"],
        ))
    return plays


def _play_targets(session, filters: dict, scorecard: pd.DataFrame) -> list[Play]:
    """Flag a store only when BOTH signals agree — its trailing-12-month
    attainment is already behind AND its last-90-day run-rate says it stays
    behind. One noisy quarter on a low-volume store doesn't trigger a play."""
    if scorecard.empty:
        return []
    tf = {k: v for k, v in (filters or {}).items()
          if k not in ("start_date", "end_date")}
    end = (filters or {}).get("end_date") or session.query(func.max(Sale.sale_date)).scalar() or date.today()
    q = session.query(Sale.dealer_id, func.sum(Sale.units_sold).label("u90"))
    q = _apply_sale_filters(q, tf).filter(
        Sale.sale_date > end - pd.Timedelta(days=90), Sale.sale_date <= end
    ).group_by(Sale.dealer_id)
    pace90 = dict(pd.read_sql(q.statement, session.bind).itertuples(index=False, name=None))

    d = scorecard.copy()
    d["target"] = d["annual_target_units"].fillna(0)
    d["pace_units"] = (d["dealer_id"].map(pace90).fillna(0) * (365.0 / 90.0))
    d["pace_pct"] = np.where(d["target"] > 0, 100.0 * d["pace_units"] / d["target"], np.nan)
    d = d[d["target"] >= 250]

    plays: list[Play] = []
    behind = d[(d["attainment_pct"] < 92) & (d["pace_pct"] < 88)].sort_values("pace_pct")
    for _, r in behind.head(2).iterrows():
        gap = r["target"] - r["pace_units"]
        strong = r["attainment_pct"] < 85 and r["pace_pct"] < 82 and r["ttm_units"] > 500
        plays.append(Play(
            category="Target",
            title=f"{r['dealer_name']} is running {r['pace_pct']:.0f}% of plan and slipping",
            detail=(
                f"Trailing 12 months it hit {r['attainment_pct']:.0f}% of its "
                f"{r['target']:,.0f}-unit plan, and the last 90 days annualise to only "
                f"{r['pace_units']:,.0f}. Closing the gap is ~+{gap / 12:,.0f} units/month — "
                f"ad spend, a desk change, or shift allocation here."
            ),
            impact_usd=gap * GROSS_PER_NEW_UNIT,
            horizon="this plan year",
            confidence="High" if strong else "Medium",
            store=r["dealer_name"],
            tags=["pace to plan"],
        ))
    ahead = d[(d["attainment_pct"] > 108) & (d["pace_pct"] > 110)].sort_values("pace_pct", ascending=False)
    if not ahead.empty:
        r = ahead.iloc[0]
        surplus = r["pace_units"] - r["target"]
        plays.append(Play(
            category="Target",
            title=f"{r['dealer_name']} is outrunning its plan by ~{surplus:,.0f} units",
            detail=(
                f"It is at {r['attainment_pct']:.0f}% trailing and the last 90 days "
                f"annualise to {r['pace_units']:,.0f} vs a {r['target']:,.0f} plan. Give it "
                f"more allocation, or its target is set too low for next year."
            ),
            impact_usd=surplus * GROSS_PER_NEW_UNIT * 0.5,
            horizon="this plan year",
            confidence="Medium",
            store=r["dealer_name"],
            tags=["capacity", "allocation"],
        ))
    return plays


def _play_margin(session, filters: dict, scorecard: pd.DataFrame) -> list[Play]:
    tf = {k: v for k, v in (filters or {}).items()
          if k not in ("start_date", "end_date")}
    end = (filters or {}).get("end_date") or session.query(func.max(Sale.sale_date)).scalar() or date.today()
    q = session.query(
        Sale.dealer_id, Sale.vehicle_category,
        func.sum(Sale.units_sold).label("units"),
        func.sum(
            Sale.discount_pct / 100.0 * Sale.base_price_usd
            + func.coalesce(Sale.trade_in_over_allowance_usd, 0)
            + func.coalesce(Sale.trade_bonus_usd, 0)
        ).label("concession"),
    )
    q = _apply_sale_filters(q, tf).filter(
        Sale.sale_date > _shift_years(end, 1), Sale.sale_date <= end
    ).group_by(Sale.dealer_id, Sale.vehicle_category)
    df = pd.read_sql(q.statement, session.bind)
    if df.empty:
        return []
    df["per_unit"] = df["concession"] / df["units"].clip(lower=1)

    grp_cat = df.groupby("vehicle_category").apply(
        lambda x: x["concession"].sum() / max(x["units"].sum(), 1)
    ).to_dict()
    name = dict(zip(scorecard["dealer_id"], scorecard["dealer_name"]))

    plays: list[Play] = []
    rows = []
    for did, sub in df.groupby("dealer_id"):
        units = sub["units"].sum()
        if units < 120:
            continue
        expected = sum(grp_cat.get(c, 0) * u for c, u in zip(sub["vehicle_category"], sub["units"])) / units
        actual = sub["concession"].sum() / units
        rows.append((did, name.get(did, did), units, actual - expected))
    for did, nm, units, excess in sorted(rows, key=lambda r: -r[3])[:2]:
        if excess < 600:
            continue
        annual = excess * units
        plays.append(Play(
            category="Margin",
            title=f"{nm} is giving away ~${excess:,.0f}/unit over peers",
            detail=(
                f"Adjusted for its segment mix, {nm}'s true concession (discount + "
                f"trade over-allowance + trade bonus) runs ~${excess:,.0f}/unit above "
                f"the group — about ${annual:,.0f}/year. A desk-discipline and "
                f"pricing-guardrail question, not a volume one."
            ),
            impact_usd=annual * RECOVERABLE_SHARE,
            horizon="ongoing",
            confidence="High" if excess > 1200 and units > 250 else "Medium",
            store=nm,
            tags=["true concession", "desk process"],
        ))
    return plays


def _play_aged_inventory(snap: pd.DataFrame) -> list[Play]:
    if snap.empty or "days_in_stock" not in snap.columns:
        return []
    aged = snap[snap["days_in_stock"] > 90]
    if aged.empty:
        return []
    grp = aged.groupby("dealer_name").agg(
        units=("current_stock", "sum"),
        value=("inventory_value_usd", "sum"),
        daily_hold=("holding_cost_per_day_usd", "sum"),
    ).reset_index().sort_values("value", ascending=False)

    plays: list[Play] = []
    for _, r in grp.iterrows():
        if r["value"] < 400_000 and r["units"] < 20:
            continue
        # ~6% of an aged unit's value erodes each quarter it sits: floorplan
        # interest plus the deeper markdown it takes to finally move.
        impact = r["value"] * 0.06 + r["daily_hold"] * 90
        plays.append(Play(
            category="Inventory",
            title=f"${r['value']:,.0f} of capital aging at {r['dealer_name']}",
            detail=(
                f"{int(r['units'])} units have sat 90+ days at {r['dealer_name']} — "
                f"~${r['daily_hold']:,.0f}/day in floorplan and depreciating toward a "
                f"deeper markdown. Transfer to a store selling that model, or take the "
                f"hit now while there's still gross to protect."
            ),
            impact_usd=impact,
            horizon="next 90 days",
            confidence="High",
            store=r["dealer_name"],
            tags=["aged units", "floorplan"],
        ))
        if len(plays) >= 2:
            break
    return plays


def _play_fni(session, filters: dict, scorecard: pd.DataFrame) -> list[Play]:
    tf = {k: v for k, v in (filters or {}).items()
          if k not in ("start_date", "end_date")}
    end = (filters or {}).get("end_date") or session.query(func.max(Sale.sale_date)).scalar() or date.today()
    q = session.query(
        Sale.dealer_id,
        func.sum(Sale.units_sold).label("units"),
        func.sum(case((Sale.financing_type == "Cash", 0), else_=Sale.units_sold)).label("noncash"),
    )
    q = _apply_sale_filters(q, tf).filter(
        Sale.sale_date > _shift_years(end, 1), Sale.sale_date <= end
    ).group_by(Sale.dealer_id)
    df = pd.read_sql(q.statement, session.bind)
    if df.empty:
        return []
    df = df[df["units"] >= 250].copy()
    if df.empty:
        return []
    df["pen"] = 100.0 * df["noncash"] / df["units"]
    median = df["pen"].median()
    name = dict(zip(scorecard["dealer_id"], scorecard["dealer_name"]))

    plays: list[Play] = []
    for _, r in df.sort_values("pen").head(1).iterrows():
        gap = median - r["pen"]
        if gap < 5:
            continue
        deals = (gap / 2 / 100) * r["units"]
        plays.append(Play(
            category="F&I",
            title=f"{name.get(r['dealer_id'], r['dealer_id'])} under-finances by {gap:.0f} pts",
            detail=(
                f"{name.get(r['dealer_id'], r['dealer_id'])} finances or leases "
                f"{r['pen']:.0f}% of deals vs the group's {median:.0f}%. Closing half "
                f"that gap is ~{deals:,.0f} more F&I deals a year at roughly "
                f"${FNI_GROSS_PER_DEAL:,} each."
            ),
            impact_usd=deals * FNI_GROSS_PER_DEAL,
            horizon="next 12 months",
            confidence="Medium",
            store=name.get(r["dealer_id"], r["dealer_id"]),
            tags=["F&I penetration", "desk process"],
        ))
    return plays


def _play_velocity(scorecard: pd.DataFrame) -> list[Play]:
    """A store whose deals take materially longer to close than the group —
    pipeline / desk friction that costs ups and carrying days."""
    if scorecard.empty or "avg_days_to_close" not in scorecard.columns:
        return []
    d = scorecard.dropna(subset=["avg_days_to_close"]).copy()
    d = d[d["units_sold"] >= 150]
    if len(d) < 5:
        return []
    med = d["avg_days_to_close"].median()
    worst = d.sort_values("avg_days_to_close", ascending=False).iloc[0]
    extra = worst["avg_days_to_close"] - med
    if extra < 6:
        return []
    # every extra day in the pipeline is roughly one lost deal per N ups; model
    # the drag as a share of TTM units proportional to the delay.
    lost = worst["ttm_units"] * min(extra / 60.0, 0.15)
    return [Play(
        category="Velocity",
        title=f"Deals at {worst['dealer_name']} take {extra:.0f} days longer to close",
        detail=(
            f"Average lead-to-close is {worst['avg_days_to_close']:.0f} days vs the "
            f"group's {med:.0f}. That pipeline friction is worth roughly {lost:,.0f} "
            f"units a year in walk-outs and stale leads — a BDC / desk-process fix."
        ),
        impact_usd=lost * GROSS_PER_NEW_UNIT * RECOVERABLE_SHARE,
        horizon="ongoing",
        confidence="Medium" if extra > 10 else "Low",
        store=worst["dealer_name"],
        tags=["lead-to-close", "BDC"],
    )]


def _play_category_momentum(session, filters: dict, snap: pd.DataFrame) -> list[Play]:
    """A segment the group's demand is projected to fall in while it is still
    carrying a full lot of it — cut orders or move the metal with incentive."""
    tf = {k: v for k, v in (filters or {}).items()
          if k not in ("start_date", "end_date")}
    q = session.query(
        Sale.year, Sale.month, Sale.vehicle_category,
        func.sum(Sale.units_sold).label("units"),
    )
    q = _apply_sale_filters(q, tf).group_by(Sale.year, Sale.month, Sale.vehicle_category)
    m = pd.read_sql(q.statement, session.bind)
    if m.empty:
        return []
    m["date"] = pd.to_datetime(dict(year=m.year, month=m.month, day=1))

    dos_by_cat = {}
    if not snap.empty:
        g = snap.assign(daily=snap["demand_forecast_30d"].clip(lower=0) / 30.0)
        gc = g.groupby("vehicle_category").agg(stock=("current_stock", "sum"),
                                               daily=("daily", "sum"))
        dos_by_cat = (gc["stock"] / gc["daily"].replace(0, np.nan)).to_dict()

    plays: list[Play] = []
    for cat, sub in m.groupby("vehicle_category"):
        s = sub.sort_values("date").set_index("date")["units"]
        if s.tail(12).sum() < 200:
            continue
        proj = _project_series(s, 12).sum()
        recent = s.tail(12).sum()
        change = (proj / recent - 1) * 100 if recent else 0
        dos = dos_by_cat.get(cat, 0)
        if change < -8 and dos > 55:
            plays.append(Play(
                category="Demand",
                title=f"{cat} demand is projected down {abs(change):.0f}% — and you're long on it",
                detail=(
                    f"The group's {cat.lower()} volume is trending to {abs(change):.0f}% "
                    f"below the last 12 months, while the lot is carrying ~{dos:.0f} days' "
                    f"supply. Cut the next order, or get ahead of it with a targeted "
                    f"incentive before the segment softens."
                ),
                impact_usd=recent * (abs(change) / 100) * GROSS_PER_NEW_UNIT * 0.4,
                horizon="next two quarters",
                confidence="Medium",
                store=None,
                tags=[cat, "order planning"],
            ))
    return plays


def generate_plays(session, filters: dict, limit: int = 5) -> list[Play]:
    """Run every generator, rank by (impact × confidence), return the top `limit`."""
    snap = get_inventory_snapshot(session, filters)
    scorecard = get_dealer_performance_leaderboard(session, filters)

    plays: list[Play] = []
    for gen in (
        lambda: _play_allocation(snap),
        lambda: _play_targets(session, filters, scorecard),
        lambda: _play_margin(session, filters, scorecard),
        lambda: _play_aged_inventory(snap),
        lambda: _play_fni(session, filters, scorecard),
        lambda: _play_velocity(scorecard),
        lambda: _play_category_momentum(session, filters, snap),
    ):
        try:
            plays.extend(gen())
        except Exception:
            continue

    # An executive brief shouldn't carry sub-scale items next to six-figure ones.
    plays = [p for p in plays if p.impact_usd >= 20_000] or plays

    plays.sort(key=lambda p: p.rank_score, reverse=True)

    # One play per store — the single biggest thing to fix there — then the
    # strongest of those across the network. With 24 rooftops this naturally
    # spreads across problem types without forcing it.
    best_per_store: dict[str, Play] = {}
    for p in plays:
        k = p.store or p.title
        if k not in best_per_store:
            best_per_store[k] = p
    ranked = sorted(best_per_store.values(), key=lambda p: p.rank_score, reverse=True)
    return ranked[:limit]
