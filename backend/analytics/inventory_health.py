"""
Stock health as data, computed once so the KPIs, coverage chart and both worklists agree.

The inventory table holds month-end snapshots (one physical car appears once per month it sat on the lot), so
everything here starts from the latest-snapshot-per-(dealer, vehicle) frame, never the raw table.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.repositories import inventory as inv

DAYS_SUPPLY_HEALTHY_LOW = inv.DAYS_SUPPLY_HEALTHY_LOW
DAYS_SUPPLY_HEALTHY_HIGH = inv.DAYS_SUPPLY_HEALTHY_HIGH

# Economic assumptions that turn unit positions into money. Kept here so every figure sizes capital and risk alike.
INVOICE_COST_FACTOR = 0.93        # MSRP -> approximate dealer invoice / floorplan basis
FLOORPLAN_APR = 0.075             # matches the rate used to seed holding cost
NEW_VEHICLE_GROSS_MARGIN = 0.08   # front-end + F&I, for sizing lost-sale exposure
AGED_THRESHOLD_DAYS = (45, 60, 75, 90, 120)
AGED_DEFAULT_DAYS = 90
WORKLIST_ROWS = 15


def position_frame(snapshot: pd.DataFrame) -> pd.DataFrame:
    """
    Derive every position column once:
      _daily_demand  30-day forecast as a daily rate        _inbound       in transit + on order
      _net_position  on hand + inbound                      _net_deficit   reorder trigger minus net position (>= 0)
      _surplus_units on hand above the healthy line         _cost_value    units valued at ~invoice, not MSRP
      _gp_at_risk    expected gross given up over the refill lead time
    """
    df = snapshot.copy()
    daily = df["demand_forecast_30d"].clip(lower=0) / 30.0
    df["_daily_demand"] = daily
    df["_inbound"] = df["transit_stock"].fillna(0) + df["units_ordered"].fillna(0)
    df["_net_position"] = df["current_stock"] + df["_inbound"]
    df["_net_deficit"] = (df["reorder_point"] - df["_net_position"]).clip(lower=0)
    df["_healthy_stock"] = np.ceil(daily * DAYS_SUPPLY_HEALTHY_HIGH)
    df["_surplus_units"] = (df["current_stock"] - df["_healthy_stock"]).clip(lower=0).astype(int)
    df["_cost_value"] = df["current_stock"] * df["price"].fillna(0) * INVOICE_COST_FACTOR
    df["_gp_at_risk"] = (
        daily * df["supplier_lead_time_days"].fillna(30) * df["price"].fillna(0)
        * NEW_VEHICLE_GROSS_MARGIN * df["stockout_risk_score"].fillna(0)
    )
    return df


def kpis(snap: pd.DataFrame, aged_days: int) -> dict:
    units = int(snap["current_stock"].sum())
    daily_demand = snap["demand_forecast_30d"].clip(lower=0).sum() / 30.0
    cost_value = float(snap["_cost_value"].sum())
    floorplan_month = cost_value * FLOORPLAN_APR / 12.0
    fixed_month = max(float(snap["estimated_holding_cost"].sum()) - floorplan_month, 0.0)
    aged = snap[snap["days_in_stock"] > aged_days]
    return {
        "units": units,
        "in_transit": int(snap["transit_stock"].fillna(0).sum()),
        "on_order": int(snap["units_ordered"].fillna(0).sum()),
        "net_days_supply": float(units / daily_demand) if daily_demand > 0 else 0.0,
        "healthy_low": DAYS_SUPPLY_HEALTHY_LOW,
        "healthy_high": DAYS_SUPPLY_HEALTHY_HIGH,
        "cost_value": cost_value,
        "carry_per_month": floorplan_month + fixed_month,
        "floorplan_per_month": floorplan_month,
        "aged_days": aged_days,
        "aged_units": int(aged["current_stock"].sum()),
        "aged_capital": float(aged["_cost_value"].sum()),
        "aged_burn_per_month": float(aged["estimated_holding_cost"].sum()),
    }


def coverage(snap: pd.DataFrame) -> dict | None:
    """Does on-hand (+ inbound) stock cover the forecast demand over 30 / 60 / 90 days?"""
    daily_total = float((snap["demand_forecast_30d"].clip(lower=0) / 30.0).sum())
    if daily_total <= 0:
        return None
    on_hand = int(snap["current_stock"].sum())
    with_pipeline = on_hand + int(snap["transit_stock"].fillna(0).sum()) + int(snap["units_ordered"].fillna(0).sum())
    return {"on_hand": on_hand, "with_pipeline": with_pipeline,
            "demand": [{"days": h, "units": daily_total * h} for h in (30, 60, 90)]}


def stock_vs_demand(snap: pd.DataFrame) -> dict:
    """Points for the stock-vs-demand chart, classed by position, plus the lines that are stocked out."""
    on_shelf = snap[snap["current_stock"] > 0].copy()
    on_shelf["position"] = np.where(
        on_shelf["days_of_supply"] > 90, "overstocked",
        np.where(on_shelf["reorder_needed"].fillna(False), "below_reorder", "healthy"),
    )
    stocked_out = snap[(snap["current_stock"] == 0) & (snap["demand_forecast_30d"] > 0)]
    cols = ["brand", "model", "dealer_name", "days_of_supply", "demand_forecast_30d", "current_stock",
            "inventory_value_amt", "position"]
    return {
        "points": on_shelf[cols],
        "stocked_out": stocked_out[["brand", "model", "dealer_name", "demand_forecast_30d"]],
        "healthy_low": DAYS_SUPPLY_HEALTHY_LOW,
        "healthy_high": DAYS_SUPPLY_HEALTHY_HIGH,
    }


def _vehicle_name(df: pd.DataFrame) -> pd.Series:
    return (df["brand"] + " " + df["model"] + " " + df["variant"].fillna("")).str.strip()


def reorder_priorities(snap: pd.DataFrame) -> list[dict]:
    """Lines below their reorder point, most urgent first, with how each shortfall can be covered."""
    surplus_by_vehicle = {}
    for vid, grp in snap[snap["_surplus_units"] > 0].groupby("vehicle_id"):
        best = grp.loc[grp["_surplus_units"].idxmax()]
        surplus_by_vehicle[vid] = (best["dealer_name"], int(best["_surplus_units"]))

    r = snap[snap["reorder_needed"].fillna(False)].copy()
    if r.empty:
        return []
    r["_urgency"] = (
        r["stockout_risk_score"].fillna(0) * 0.5
        + (r["supplier_lead_time_days"].fillna(30) / 70.0).clip(upper=1) * 0.3
        + (r["_net_deficit"] / r["reorder_point"].replace(0, np.nan)).fillna(0).clip(upper=1) * 0.2
    )

    def cover(row) -> dict:
        if row["_net_deficit"] <= 0:
            return {"kind": "inbound", "units": int(row["_inbound"]), "store": None}
        other = surplus_by_vehicle.get(row["vehicle_id"])
        if other and other[0] != row["dealer_name"]:
            return {"kind": "dealer_trade", "units": other[1], "store": other[0]}
        return {"kind": "factory_order", "units": None, "store": None}

    r["coverage"] = r.apply(cover, axis=1)
    r = r.sort_values("_urgency", ascending=False)
    return [
        {
            "dealer": row["dealer_name"], "vehicle": name, "region": row["region"],
            "on_hand": int(row["current_stock"]), "inbound": int(row["_inbound"]),
            "reorder_point": int(row["reorder_point"]), "net_short": int(row["_net_deficit"]),
            "lead_time_days": int(row["supplier_lead_time_days"]) if pd.notna(row["supplier_lead_time_days"]) else 30,
            "gp_at_risk": float(round(row["_gp_at_risk"], -2)),
            "coverage": row["coverage"], "urgency": float(round(row["_urgency"] * 100)),
        }
        for (_, row), name in zip(r.iterrows(), _vehicle_name(r))
    ]


def aged_actions(snap: pd.DataFrame, aged_days: int) -> list[dict]:
    """Stock older than the threshold, biggest capital-tied-up-for-longest first, with a suggested disposal route."""
    short_at = {}
    for vid, grp in snap[snap["reorder_needed"].fillna(False)].groupby("vehicle_id"):
        short_at[vid] = grp.loc[grp["_net_deficit"].idxmax()]["dealer_name"]

    aged = snap[(snap["days_in_stock"] > aged_days) & (snap["current_stock"] > 0)].copy()
    if aged.empty:
        return []
    aged["_pressure"] = aged["_cost_value"] * aged["days_in_stock"]

    def action(row) -> dict:
        elsewhere = short_at.get(row["vehicle_id"])
        if row["_daily_demand"] < 0.05 or row["days_of_supply"] >= 120 or row["days_in_stock"] >= 150:
            return {"kind": "wholesale", "store": None}
        if elsewhere and elsewhere != row["dealer_name"]:
            return {"kind": "dealer_trade", "store": elsewhere}
        if row["days_of_supply"] <= DAYS_SUPPLY_HEALTHY_LOW:
            return {"kind": "hold", "store": None}
        return {"kind": "markdown", "store": None}

    aged["action"] = aged.apply(action, axis=1)
    aged = aged.sort_values("_pressure", ascending=False)
    return [
        {
            "dealer": row["dealer_name"], "vehicle": name, "region": row["region"],
            "units": int(row["current_stock"]), "days_on_lot": int(row["days_in_stock"]),
            "days_of_supply": int(row["days_of_supply"]), "capital": float(row["_cost_value"]),
            "monthly_burn": float(row["estimated_holding_cost"]), "action": row["action"],
        }
        for (_, row), name in zip(aged.iterrows(), _vehicle_name(aged))
    ]
