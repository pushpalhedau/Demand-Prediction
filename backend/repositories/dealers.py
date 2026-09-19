"""Dealer (rooftop) queries: the performance leaderboard and the store directory."""
import numpy as np
import pandas as pd
from datetime import date
from sqlalchemy import case, desc, func
from sqlalchemy.orm import Session

from backend.db.models import Dealer, Sale
from backend.repositories._filters import apply_sale_filters, shift_years


def get_dealer_performance_leaderboard(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Per-rooftop operating scorecard for the Store Performance tab — EVERY store in
    the group (not a top-N leaderboard), with the numbers a multi-store operator
    actually manages by:

      units / revenue      booked in the filtered window
      ttm_units            trailing-12-month units to the window end
      prior_ttm_units      the 12 months before that
      yoy_units_pct        ttm vs prior-ttm growth (NOT full-window vs shifted
                           window — over a multi-year sidebar range that just
                           shows "everything grew"; the trailing-12 framing is
                           the one a GM means and it surfaces real laggards)
      annual_target_units  the store's own plan (Dealer.annual_target_units)
      attainment_pct       ttm_units / annual_target_units
      close_rate           share of test-drives that converted, in the window
      avg_days_to_close    mean lead_to_close_days, in the window
      top_category         best-selling segment, in the window
      latitude / longitude for the footprint map

    History (2026-08-29, Store Performance repositioning): this used to return the
    synthetic OEM-style fields `Dealer.tier` (Platinum/Gold/Silver) and
    `Dealer.performance_score` (opaque 0-100) and rank stores by them, capped at
    `.limit(20)`. Both fields are still defined on the Dealer model but are no
    longer selected here; the cap is gone (the group has 24 rooftops and the tab
    shows all of them). `google_rating`, `ev_charging_station`, `service_center`
    were consumer-directory attributes and are likewise dropped from this result.
    """
    filters = filters or {}
    group_cols = [
        Dealer.dealer_id,
        Dealer.dealer_name,
        Dealer.brand,
        Dealer.city,
        Dealer.region,
        Dealer.latitude,
        Dealer.longitude,
        Dealer.annual_target_units,
    ]

    query = session.query(
        *group_cols,
        func.sum(Sale.units_sold).label("units_sold"),
        func.sum(Sale.total_revenue_incl_tax).label("revenue"),
        func.count(Sale.sale_id).label("deal_rows"),
        func.sum(case((Sale.test_drive_converted == True, 1), else_=0)).label("td_converted"),
        func.avg(Sale.lead_to_close_days).label("avg_days_to_close"),
    ).join(Sale, Sale.dealer_id == Dealer.dealer_id)
    query = apply_sale_filters(query, filters)
    query = query.group_by(*group_cols).order_by(desc("units_sold"))

    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return df

    df["close_rate"] = df.pop("td_converted") / df["deal_rows"].clip(lower=1)

    # Trailing-12-month units (to the window end) and the 12 months before it —
    # for attainment vs the store's own target and for a YoY that means what a
    # GM means by "vs last year" (same framing as get_target_attainment and
    # Comparative Analytics §1; the sidebar *start* date does not affect these).
    end = filters.get("end_date") or session.query(func.max(Sale.sale_date)).scalar() or date.today()
    tf = {k: v for k, v in filters.items() if k not in ("start_date", "end_date")}

    def _units_by_store(s, e):
        q = session.query(Sale.dealer_id, func.sum(Sale.units_sold).label("u"))
        q = apply_sale_filters(q, tf).filter(
            Sale.sale_date > s, Sale.sale_date <= e
        ).group_by(Sale.dealer_id)
        return dict(pd.read_sql(q.statement, session.bind).itertuples(index=False, name=None))

    ttm_units = _units_by_store(shift_years(end, 1), end)
    prior_ttm_units = _units_by_store(shift_years(end, 2), shift_years(end, 1))

    df["ttm_units"] = df["dealer_id"].map(ttm_units).fillna(0)
    df["prior_ttm_units"] = df["dealer_id"].map(prior_ttm_units).fillna(0)
    df["yoy_units_pct"] = np.where(
        df["prior_ttm_units"] > 0,
        100.0 * (df["ttm_units"] - df["prior_ttm_units"]) / df["prior_ttm_units"],
        np.nan,
    )
    df["attainment_pct"] = np.where(
        df["annual_target_units"].fillna(0) > 0,
        100.0 * df["ttm_units"] / df["annual_target_units"],
        np.nan,
    )

    # Top vehicle category per dealer (respects same date/region filters)
    cat_q = session.query(
        Sale.dealer_id,
        Sale.vehicle_category,
        func.sum(Sale.units_sold).label("cnt")
    )
    cat_q = apply_sale_filters(cat_q, filters)
    cat_q = cat_q.group_by(Sale.dealer_id, Sale.vehicle_category)
    cat_df = pd.read_sql(cat_q.statement, session.bind)
    if not cat_df.empty:
        top_cat_df = (
            cat_df.sort_values("cnt", ascending=False)
                  .drop_duplicates("dealer_id")[["dealer_id", "vehicle_category"]]
                  .rename(columns={"vehicle_category": "top_category"})
        )
        df = df.merge(top_cat_df, on="dealer_id", how="left")
    else:
        df["top_category"] = None

    # Stores built from a sales-only upload have no targets/ratings, which arrive as all-None
    # object columns; make every metric numeric so .round() and comparisons work downstream.
    for c in ("yoy_units_pct", "attainment_pct", "close_rate", "avg_days_to_close", "annual_target_units",
              "performance_score", "google_rating", "revenue", "units_sold"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def get_dealer_directory(session: Session) -> pd.DataFrame:
    """Dealer identity and coordinates, for locating stock at nearby stores."""
    query = session.query(
        Dealer.dealer_id,
        Dealer.dealer_name,
        Dealer.brand,
        Dealer.region,
        Dealer.city,
        Dealer.tier,
        Dealer.latitude,
        Dealer.longitude,
        Dealer.performance_score,
    )
    return pd.read_sql(query.statement, session.bind)
