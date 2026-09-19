"""
Retention analytics over the customer book: who to contact now, where the book stands, and how the segments differ.

Presentation-free (labels are stable keys, never display text), so any frontend can render them.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from backend.analytics.benchmarks import gross_series

SEGMENT_ORDER = ["High-Value / Prime", "Loyal Repeat", "Core Mainstream", "Value Buyers", "Lapsed / At-Risk"]

# Highest priority first: a customer gets only the most actionable reason that applies.
REASON_PRIORITY = ["Lease maturing", "Overdue for next vehicle", "Lapsed high-value", "Churn-risk spike"]
REASON_PLAY = {
    "Lease maturing": "Lease pull-ahead offer",
    "Overdue for next vehicle": "Trade-cycle call",
    "Lapsed high-value": "GM win-back call",
    "Churn-risk spike": "Retention save call",
}

# Where a buyer sits in the ownership cycle, by months since their last deal (or an active lease).
BOOK_BANDS = [
    ("Active", 0, 24),
    ("In cycle — due back", 24, 48),
    ("Going quiet", 48, 84),
    ("Likely lost", 84, 10_000),
]


def action_queue(book: pd.DataFrame) -> pd.DataFrame:
    """
    Every customer who should be contacted now, one row each: the reason, the store that should own the outreach,
    the play, and the identified gross opportunity (benchmark gross on a like-for-like replacement).
    """
    today = pd.Timestamp(date.today())
    b = book[book["n_deals"] > 0].copy()
    months = b["months_since_last_deal"]
    lease_days = (pd.to_datetime(b["next_lease_maturity"]) - today).dt.days

    lease_due = lease_days.between(0, 120)
    overdue = (
        (b["n_deals"] >= 2)
        & b["cadence_months"].notna()
        & (months >= b["cadence_months"] + 3)
        & (months <= b["cadence_months"] + 30)
    )
    high_value_cut = b["lifetime_revenue"].quantile(0.70)
    lapsed_high_value = (
        (b["customer_segment"] == "Lapsed / At-Risk") & (b["lifetime_revenue"] >= high_value_cut) & (months >= 36)
    )
    churn = (b["churn_risk_score"].fillna(0) >= 0.62) & months.between(18, 48)

    # Lowest priority first, so the most actionable reason overwrites the rest.
    b["reason"] = pd.NA
    b.loc[churn, "reason"] = "Churn-risk spike"
    b.loc[lapsed_high_value, "reason"] = "Lapsed high-value"
    b.loc[overdue, "reason"] = "Overdue for next vehicle"
    b.loc[lease_due, "reason"] = "Lease maturing"

    q = b[b["reason"].notna()].copy()
    if q.empty:
        return q

    is_lease = q["reason"] == "Lease maturing"
    q["store"] = q["lease_store"].where(is_lease, q["last_store"])
    q["vehicle"] = q["lease_vehicle"].where(is_lease, q["last_brand"].astype(str) + " " + q["last_model"].astype(str))
    q["opportunity_amt"] = gross_series(q["last_brand"])
    q["lease_days"] = lease_days.reindex(q.index)
    q["when_days"] = np.where(is_lease, q["lease_days"].fillna(0), np.nan)
    q["play"] = q["reason"].map(REASON_PLAY)
    q["_prio"] = q["reason"].map({r: i for i, r in enumerate(REASON_PRIORITY)})
    # Lease maturities soonest first; everything else by the biggest opportunity.
    q["_order"] = np.where(is_lease, q["lease_days"].fillna(999), -q["opportunity_amt"])
    return q.sort_values(["_prio", "_order"])


def book_state(book: pd.DataFrame) -> list[dict]:
    b = book[book["n_deals"] > 0]
    if b.empty:
        return []
    months = b["months_since_last_deal"].fillna(9999)
    has_lease = pd.to_datetime(b["next_lease_maturity"], errors="coerce").notna()
    out = []
    for name, lo, hi in BOOK_BANDS:
        in_band = (months >= lo) & (months < hi)
        selected = (in_band | has_lease) if name == "Active" else (in_band & ~has_lease)
        out.append({"band": name, "customers": int(selected.sum()),
                    "lifetime_value": float(b.loc[selected, "lifetime_revenue"].sum())})
    return out


def segment_panel(df: pd.DataFrame) -> list[dict]:
    """One row per customer segment, for campaign planning."""
    rows, total = [], len(df)
    for seg in SEGMENT_ORDER:
        g = df[df["customer_segment"] == seg]
        if g.empty:
            continue
        deals = g["lifetime_deals"].sum()
        buyers = g[g["lifetime_deals"] > 0]
        rows.append({
            "segment": seg,
            "customers": int(len(g)),
            "share_pct": round(100 * len(g) / total, 1),
            "lifetime_revenue": float(g["lifetime_revenue"].sum()),
            "avg_deal_value": float(buyers["avg_deal_value"].mean() or 0),
            "repeat_rate_pct": float(100 * (buyers["number_of_past_purchases"] >= 2).mean()) if len(buyers) else 0.0,
            "lease_pct": float(100 * g["lease_deals"].sum() / deals) if deals else 0.0,
            "median_income": float(g["annual_income"].median() or 0),
            "avg_credit": float(g["credit_score"].mean() or 0),
            "months_since_deal": float(buyers["months_since_last_deal"].median()) if len(buyers) else None,
        })
    return rows
