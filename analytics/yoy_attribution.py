"""
Year-over-year attribution for the Comparative Analytics tab.

BI dashboards show "+1.4% vs last year" and stop. This module decomposes that
move into parts a dealer principal can act on differently:

  - **selling days**   the calendar handed you (or took away) trading days
  - **network**        rooftops opened / closed since last year (M&A, not ops)
  - **price & tariff**  (revenue only) higher transaction prices / Section 232
                        pass-through — not more metal sold
  - **comp volume**    same rooftops, same trading intensity, selling more or
                        fewer units — the part the group actually *ran*

"Controllable YoY" is that last part expressed as a rate. It is deliberately a
same-store, selling-day-adjusted number — the retail "comp" metric — because
without an external market-sales feed that is the strongest honest claim about
what the group earned versus what it was handed.

The per-entity split (`driver_split`) then uses shift-share against the group as
the benchmark, which *is* valid for one store / brand / segment: each entity's
change is "moved with the group" + (for a store) "its franchise's group-wide
trend" + "the residual that is specific to it".

Everything here is computed from query results and a handful of **statistical**
constants (a z-threshold, a minimum history length). There are no hard-coded
figures about the data, the dates, or the dealer group — change the database and
every number and sentence recomputes.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import func

from database.models import Sale, Dealer
from database.queries import _apply_sale_filters

# ── Statistical constants (not data) ─────────────────────────────────────────
_SIGNIF_Z = 1.5          # |z| beyond which a YoY move is "outside normal variation"
_MIN_YOY_POINTS = 8      # YoY observations needed to estimate an entity's own volatility
_MIN_SIGMA = 1.0         # floor on the volatility estimate, in units (avoids /0 on flat series)
_MATERIAL_FRAC = 0.002   # a bridge step smaller than this share of the base is folded away

_DIM_COL = {
    "store": "store",
    "brand": "brand",
    "category": "category",
}

# What the two parts of a shift-share split mean, per dimension.
STRUCTURAL_LABEL = {
    "store": "Moved with the group",
    "brand": "Moved with the group",
    "category": "Moved with the group",
}
SPECIFIC_LABEL = {
    "store": "Rooftop-specific",
    "brand": "Franchise-specific",
    "category": "Segment-specific",
}


# ─────────────────────────────────────────────────────────────────────────────
# Windows & scope
# ─────────────────────────────────────────────────────────────────────────────
def resolve_windows(end_date) -> dict:
    """Last 12 whole calendar months to `end_date`, and the 12 before that."""
    end_ts = pd.Timestamp(end_date or date.today())
    cur_end = (end_ts.replace(day=1) + pd.offsets.MonthEnd(0)).normalize()
    cur_start = (end_ts.replace(day=1) - pd.DateOffset(months=11)).normalize()
    prior_end = cur_start - pd.Timedelta(days=1)
    prior_start = (cur_start - pd.DateOffset(years=1)).normalize()
    return {
        "cur": (cur_start.date(), cur_end.date()),
        "prior": (prior_start.date(), prior_end.date()),
        "cur_label": cur_end.strftime("%b %Y"),
    }


def _scope(filters: dict) -> dict:
    """Sidebar filters minus the date window (this module sets its own)."""
    return {k: v for k, v in (filters or {}).items()
            if k not in ("start_date", "end_date")}


def _period_frame(session, filters: dict, start, end) -> pd.DataFrame:
    """Units / revenue / tariff for the window, grouped store × brand × segment.
    One query; the caller aggregates to whatever dimension it needs."""
    q = session.query(
        Dealer.dealer_name.label("store"),
        Sale.brand.label("brand"),
        Sale.vehicle_category.label("category"),
        func.coalesce(func.sum(Sale.units_sold), 0).label("units"),
        func.coalesce(func.sum(Sale.total_revenue_incl_tax), 0).label("revenue"),
        func.coalesce(func.sum(Sale.tariff_cost_usd), 0).label("tariff"),
    ).join(Dealer, Sale.dealer_id == Dealer.dealer_id)
    q = _apply_sale_filters(q, {**_scope(filters), "start_date": start, "end_date": end})
    q = q.group_by(Dealer.dealer_name, Sale.brand, Sale.vehicle_category)
    df = pd.read_sql(q.statement, session.bind)
    for c in ("units", "revenue", "tariff"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df


def _selling_days(session, filters: dict, start, end) -> int:
    q = session.query(func.count(func.distinct(Sale.sale_date)))
    q = _apply_sale_filters(q, {**_scope(filters), "start_date": start, "end_date": end})
    return int(q.scalar() or 0)


# ─────────────────────────────────────────────────────────────────────────────
# The bridge (group-level waterfall) + the headline summary
# ─────────────────────────────────────────────────────────────────────────────
def _bridge_core(session, filters: dict) -> dict | None:
    w = resolve_windows((filters or {}).get("end_date"))
    cs, ce = w["cur"]
    ps, pe = w["prior"]

    cur = _period_frame(session, filters, cs, ce)
    pri = _period_frame(session, filters, ps, pe)
    if cur["units"].sum() == 0 and pri["units"].sum() == 0:
        return None

    stores_cur = set(cur.loc[cur["units"] > 0, "store"])
    stores_pri = set(pri.loc[pri["units"] > 0, "store"])
    ss = stores_cur & stores_pri
    opened = stores_cur - stores_pri
    closed = stores_pri - stores_cur

    d0 = _selling_days(session, filters, ps, pe)
    d1 = _selling_days(session, filters, cs, ce)
    day_ratio = (d1 / d0 - 1.0) if d0 else 0.0
    # If the prior window predates the data (or a scope only starts mid-history),
    # the two periods aren't a fair YoY — the caller should caveat, not headline.
    comparable = bool(d0 > 0 and d1 > 0 and d0 >= 0.85 * d1)

    def agg(df, col, stores=None):
        if stores is not None:
            df = df[df["store"].isin(stores)]
        return float(df[col].sum())

    out = {"windows": w, "selling_days": (d0, d1), "comparable": comparable,
           "n_stores": (len(stores_pri), len(stores_cur)),
           "opened": sorted(opened), "closed": sorted(closed),
           "same_store": ss, "cur": cur, "pri": pri}

    for col in ("units", "revenue"):
        v0, v1 = agg(pri, col), agg(cur, col)
        ss_v0, ss_v1 = agg(pri, col, ss), agg(cur, col, ss)
        network = agg(cur, col, opened) - agg(pri, col, closed)
        sd = ss_v0 * day_ratio
        comp = (ss_v1 - ss_v0) - sd
        out[col] = {
            "start": v0, "end": v1, "delta": v1 - v0,
            "selling_days": sd, "network": network,
            "comp": comp, "ss_start": ss_v0, "ss_end": ss_v1,
        }

    # Revenue: split the comp move into "sold more/better metal" vs "price + tariff"
    u = out["units"]; r = out["revenue"]
    ss_t0 = agg(pri, "tariff", ss); ss_t1 = agg(cur, "tariff", ss)
    tariff_rev = ss_t1 - ss_t0
    atp0 = (r["ss_start"] / u["ss_start"]) if u["ss_start"] else 0.0
    volume_rev = u["comp"] * atp0
    price_rev = r["comp"] - tariff_rev - volume_rev
    r["tariff"] = tariff_rev
    r["price_mix"] = price_rev
    r["volume"] = volume_rev
    return out


def build_bridge(session, filters: dict, measure: str) -> dict | None:
    """Ordered waterfall steps for the active measure, plus reconciliation."""
    core = _bridge_core(session, filters)
    if core is None:
        return None
    is_units = measure == "units"
    m = core["units"] if is_units else core["revenue"]
    base = m["start"] or 1.0

    steps = [("Prior 12 months", m["start"], "absolute")]
    cand = [("Selling days", m["selling_days"]), ("Rooftops opened / closed", m["network"])]
    if not is_units:
        cand += [("Tariff pass-through", m["tariff"]), ("Price & mix", m["price_mix"]),
                 ("Comp volume", m["volume"])]
    else:
        cand += [("Comp volume", m["comp"])]

    folded = 0.0
    for label, val in cand:
        if label == "Comp volume":
            steps.append((label, val, "relative"))
            continue
        if val == 0:
            continue                                   # nothing happened here
        if abs(val) < _MATERIAL_FRAC * abs(base):
            folded += val                              # too small to be its own bar
            continue
        steps.append((label, val, "relative"))
    if abs(folded) > 0:
        steps.append(("Other", folded, "relative"))
    steps.append(("Last 12 months", m["end"], "total"))

    return {
        "steps": steps,
        "measure": measure,
        "windows": core["windows"],
        "start": m["start"], "end": m["end"],
        "opened": core["opened"], "closed": core["closed"],
        "selling_days": core["selling_days"],
    }


def summary(session, filters: dict, measure: str) -> dict | None:
    """Headline numbers: total YoY, controllable (comp) YoY, and the spread of
    execution across entities."""
    core = _bridge_core(session, filters)
    if core is None:
        return None
    is_units = measure == "units"
    m = core["units"] if is_units else core["revenue"]

    total_yoy = (m["end"] / m["start"] - 1) * 100 if m["start"] else None
    if is_units:
        controllable_abs = m["comp"]
    else:
        controllable_abs = m["price_mix"] + m["volume"]
    controllable_yoy = (controllable_abs / m["ss_start"] * 100) if m["ss_start"] else None

    # Execution spread: per continuing store, its move vs the group's rate.
    split = driver_split(session, filters, "store", measure)
    spread = {}
    if split is not None and not split.empty:
        cont = split[split["kind"] == "continuing"].copy()
        if not cont.empty and cont["base"].sum() > 0:
            g_ss = cont["cur"].sum() / cont["base"].sum() - 1
            beat = int((cont["specific"] > 0).sum())
            worst = cont.sort_values("own_dev_pct").iloc[0]
            best = cont.sort_values("own_dev_pct").iloc[-1]
            spread = {
                "n_beat": beat, "n_total": int(len(cont)),
                "group_growth_pct": float(g_ss * 100),
                "worst_name": str(worst["name"]), "worst_pct": float(worst["own_dev_pct"]),
                "best_name": str(best["name"]), "best_pct": float(best["own_dev_pct"]),
            }

    return {
        "measure": measure,
        "windows": core["windows"],
        "comparable": core["comparable"],
        "total_yoy_pct": total_yoy,
        "total_end": m["end"], "total_start": m["start"],
        "controllable_yoy_pct": controllable_yoy,
        "controllable_abs": controllable_abs,
        "selling_days": core["selling_days"],
        "n_stores": core["n_stores"],
        "opened": core["opened"], "closed": core["closed"],
        "removed": {  # what "controllable" strips out, in the measure's units
            "selling_days": m["selling_days"],
            "network": m["network"],
            **({"tariff": m["tariff"], "price_mix": m["price_mix"]} if not is_units else {}),
        },
        "spread": spread,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Per-entity split — shift-share against the group
# ─────────────────────────────────────────────────────────────────────────────
def driver_split(session, filters: dict, dimension: str, measure: str) -> pd.DataFrame | None:
    """Each entity's YoY change split by shift-share against the group:
    `structural` = what it would have done growing at the group's same-store rate,
    `specific` = the residual it owns. For a store, `sibling` records how its
    franchise-mates moved, so narration can tell "it's the franchise" from
    "it's this rooftop"."""
    core = _bridge_core(session, filters)
    if core is None:
        return None
    col = "units" if measure == "units" else "revenue"
    dim = _DIM_COL.get(dimension, "store")
    cur, pri, ss = core["cur"], core["pri"], core["same_store"]

    cur_ss = cur[cur["store"].isin(ss)]
    pri_ss = pri[pri["store"].isin(ss)]
    g0 = float(pri_ss[col].sum())
    g1 = float(cur_ss[col].sum())
    g_ss = (g1 / g0 - 1) if g0 else 0.0

    cur_e = cur.groupby(dim)[col].sum()
    pri_e = pri.groupby(dim)[col].sum()
    brand_of = cur.groupby(dim)["brand"].first().to_dict() if dim == "store" else {}

    # per-brand same-store growth + rooftop count, for the sibling read
    if dim == "store":
        pb = pri_ss.groupby("brand")[col].sum()
        cb = cur_ss.groupby("brand")[col].sum()
        brand_n = cur_ss.groupby("brand")["store"].nunique().to_dict()
        brand_g = {b: (float(cb.get(b, 0)) / float(pb.get(b, 0)) - 1) if pb.get(b, 0) else np.nan
                   for b in set(pb.index) | set(cb.index)}

    rows = []
    for name in sorted(set(cur_e.index) | set(pri_e.index)):
        c = float(cur_e.get(name, 0.0))
        p = float(pri_e.get(name, 0.0))
        if p <= 0 and c > 0:
            rows.append(dict(name=name, kind="new", base=0.0, cur=c,
                             total=c, structural=0.0, specific=c, sibling=np.nan))
            continue
        if c <= 0 and p > 0:
            rows.append(dict(name=name, kind="gone", base=p, cur=0.0,
                             total=-p, structural=0.0, specific=-p, sibling=np.nan))
            continue
        if p <= 0:
            continue
        total = c - p
        structural = p * g_ss
        specific = total - structural
        sibling = np.nan
        if dim == "store":
            b = brand_of.get(name)
            # sibling deviation = how the rest of this franchise moved vs the group
            if b is not None and brand_n.get(b, 1) >= 2 and np.isfinite(brand_g.get(b, np.nan)):
                sibling = (brand_g[b] - g_ss) * 100.0
        rows.append(dict(name=name, kind="continuing", base=p, cur=c,
                         total=total, structural=structural, specific=specific,
                         sibling=sibling))

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["own_dev_pct"] = np.where(df["base"] > 0, df["specific"] / df["base"] * 100.0, np.nan)

    sig = _significance(session, filters, dimension, df)
    df = df.merge(sig, on="name", how="left")
    df["significant"] = df["significant"].fillna(False)
    df["z"] = df["z"].fillna(0.0)
    return df.sort_values("total")


# ─────────────────────────────────────────────────────────────────────────────
# Feature 5 — significance: is this move outside the entity's own normal swing?
# ─────────────────────────────────────────────────────────────────────────────
def _monthly_entity_units(session, filters: dict, dimension: str) -> pd.DataFrame:
    dim_sql = {
        "store": Dealer.dealer_name,
        "brand": Sale.brand,
        "category": Sale.vehicle_category,
    }.get(dimension, Dealer.dealer_name)
    q = session.query(
        dim_sql.label("name"), Sale.year, Sale.month,
        func.coalesce(func.sum(Sale.units_sold), 0).label("units"),
    )
    if dimension == "store":
        q = q.join(Dealer, Sale.dealer_id == Dealer.dealer_id)
    q = _apply_sale_filters(q, _scope(filters))          # all history, scope only
    q = q.group_by(dim_sql, Sale.year, Sale.month)
    df = pd.read_sql(q.statement, session.bind)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1))
    return df


def _significance(session, filters: dict, dimension: str, split: pd.DataFrame) -> pd.DataFrame:
    """For each entity, z-score its observed YoY unit move against the
    distribution of its *own* rolling-12-month YoY moves across all history.
    Falls back to a relative-outlier test when history is too short."""
    # Significance is judged on a real unit swing, not the active measure — a
    # revenue wobble from price alone shouldn't flag a store as "moving".
    hist = _monthly_entity_units(session, filters, dimension)

    recs = []
    med_abs_pct = None
    if not hist.empty:
        piv = hist.pivot_table(index="date", columns="name", values="units",
                               aggfunc="sum").sort_index().fillna(0.0)
        # drop a trailing partial month
        if len(piv) >= 14 and piv.iloc[-1].sum() < 0.55 * piv.iloc[-13:-1].sum().mean():
            piv = piv.iloc[:-1]
        roll = piv.rolling(12).sum()
        yoy = roll.diff(12).dropna(how="all")
        pct_moves = []
        for name in piv.columns:
            series = yoy[name].dropna()
            cur12 = roll[name].iloc[-1] if len(roll) else np.nan
            pri12 = roll[name].iloc[-13] if len(roll) > 12 else np.nan
            obs = (cur12 - pri12) if np.isfinite(cur12) and np.isfinite(pri12) else np.nan
            if np.isfinite(obs) and np.isfinite(pri12) and pri12 > 0:
                pct_moves.append(abs(obs / pri12))
            recs.append({"name": name, "_obs": obs, "_pri12": pri12,
                         "_mu": series.mean() if len(series) else np.nan,
                         "_sigma": series.std() if len(series) >= _MIN_YOY_POINTS else np.nan,
                         "_n": len(series)})
        med_abs_pct = float(np.median(pct_moves)) if pct_moves else None

    rows = []
    for r in recs:
        z, sig = 0.0, False
        sigma = r["_sigma"]
        if np.isfinite(sigma) and sigma >= _MIN_SIGMA and np.isfinite(r["_obs"]):
            z = (r["_obs"] - (r["_mu"] if np.isfinite(r["_mu"]) else 0.0)) / sigma
            sig = abs(z) >= _SIGNIF_Z
        elif med_abs_pct and np.isfinite(r["_obs"]) and np.isfinite(r["_pri12"]) and r["_pri12"] > 0:
            sig = abs(r["_obs"] / r["_pri12"]) >= max(1.5 * med_abs_pct, 0.10)
        rows.append({"name": r["name"], "z": float(z) if np.isfinite(z) else 0.0,
                     "significant": bool(sig)})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["name", "z", "significant"])


# ─────────────────────────────────────────────────────────────────────────────
# Narration — one dynamic sentence per notable mover
# ─────────────────────────────────────────────────────────────────────────────
def movement_sentences(split: pd.DataFrame, dimension: str, measure: str,
                       fmt, limit: int = 3) -> list[str]:
    if split is None or split.empty:
        return []
    unit = "units" if measure == "units" else "revenue"
    sig = split[split["significant"]] if split["significant"].any() else split
    sig = sig.reindex(sig["total"].abs().sort_values(ascending=False).index)

    out = []
    for _, r in sig.head(limit).iterrows():
        if r["kind"] == "new":
            out.append(f"**{r['name']}** is new to the group this year — "
                       f"{fmt(abs(r['cur']))} {unit}.")
            continue
        if r["kind"] == "gone":
            out.append(f"**{r['name']}** did not trade this year "
                       f"(was {fmt(abs(r['base']))} {unit}).")
            continue
        spec, struct = r["specific"], r["structural"]
        direction = "ahead of" if r["total"] >= 0 else "behind"
        s = f"**{r['name']}** is {fmt(abs(r['total']))} {unit} {direction} last year"

        if abs(spec) < max(1.0, 0.20 * abs(struct)):
            out.append(s + f" — moving with the group ({_signed(struct, fmt)}), nothing unusual.")
            continue

        pace = "should have been about " + _signed(struct, fmt)
        label = SPECIFIC_LABEL.get(dimension, "entity-specific").lower()
        s += (f". At the group's pace it {pace}; the {_signed(spec, fmt)} beyond that is {label}")

        sib = r.get("sibling", np.nan)
        if dimension == "store":
            marque = r["name"].split(" of ")[0]
            if np.isfinite(sib):
                same_way = (sib < 0) == (spec < 0) and abs(sib) >= 1.5
                if same_way:
                    s += (f" — but the group's other {marque} rooftops moved the same way "
                          f"({sib:+.0f}% vs the group), so treat it as the franchise, not the store")
                else:
                    s += (f" — and the group's other {marque} rooftops did not ({sib:+.0f}% vs the group), "
                          f"so this is the rooftop")
            else:
                s += (f" — the group runs no other {marque} rooftop, so the franchise cycle and the "
                      f"store can't be separated from this data alone")
        out.append(s + ".")
    return out


def _signed(v, fmt) -> str:
    return ("+" if v >= 0 else "−") + fmt(abs(v))
