"""Inventory queries: stock snapshot, ageing, lease returns, trade-ins and substitution history."""
import pandas as pd
from datetime import date
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models import Customer, Dealer, Inventory, Sale, Vehicle
from backend.repositories._filters import apply_inventory_filters, apply_sale_filters


# Healthy days-of-supply band used across the stock-health views.
DAYS_SUPPLY_HEALTHY_LOW = 45


DAYS_SUPPLY_HEALTHY_HIGH = 75


# Aging ladder buckets, in days on the lot.
AGING_BUCKETS = [(0, 30), (31, 60), (61, 90), (91, 10_000)]


AGING_LABELS = ["0-30 days", "31-60 days", "61-90 days", "90+ days"]


def get_inventory_snapshot(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Current stock position: the most recent snapshot for each (dealer, vehicle).

    Enriched with dealer identity and vehicle economics so the dashboard can
    show which store is holding what, and what it is worth.
    """
    latest_date = session.query(func.max(Inventory.record_date)).scalar()
    if latest_date is None:
        return pd.DataFrame()

    query = (
        session.query(
            Inventory.inventory_id,
            Inventory.record_date,
            Inventory.dealer_id,
            Inventory.vehicle_id,
            Inventory.brand,
            Inventory.model,
            Inventory.vehicle_category,
            Inventory.fuel_type,
            Inventory.region,
            Inventory.city,
            Inventory.current_stock,
            Inventory.demand_forecast_30d,
            Inventory.reorder_point,
            Inventory.days_in_stock,
            Inventory.stockout_flag,
            Inventory.overstock_flag,
            Inventory.reorder_needed,
            Inventory.stockout_risk_score,
            Inventory.overstock_risk_score,
            Inventory.holding_cost_per_day,
            Inventory.estimated_holding_cost,
            Inventory.units_sold_last_30d,
            Inventory.units_ordered,
            Inventory.transit_stock,
            Inventory.supplier_lead_time_days,
            Inventory.origin_hub,
            Inventory.warehouse_zone,
            Dealer.dealer_name,
            Dealer.tier.label("dealer_tier"),
            Dealer.latitude,
            Dealer.longitude,
            Vehicle.variant,
            Vehicle.price,
            Vehicle.residual_value_36mo,
        )
        .outerjoin(Dealer, Inventory.dealer_id == Dealer.dealer_id)
        .outerjoin(Vehicle, Inventory.vehicle_id == Vehicle.vehicle_id)
        .filter(Inventory.record_date == latest_date)
    )
    query = apply_inventory_filters(query, filters)

    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return df

    # Days of supply is the operating metric; derive it once here so every
    # downstream view agrees on the definition.
    daily_demand = df["demand_forecast_30d"].clip(lower=0) / 30.0
    # A line with no forecast demand has effectively unbounded days of supply;
    # 999 stands in for "will never sell at the current rate".
    df["days_of_supply"] = (
        df["current_stock"] / daily_demand.replace(0, float("nan"))
    ).fillna(999).clip(upper=999).round(0)
    df["inventory_value_amt"] = df["current_stock"] * df["price"].fillna(0)
    return df


def get_inventory_trend(session: Session, filters: dict = None) -> pd.DataFrame:
    """Month-end network stock, transit and holding cost over the snapshot history."""
    query = session.query(
        Inventory.record_date,
        func.sum(Inventory.current_stock).label("units_in_stock"),
        func.sum(Inventory.transit_stock).label("units_in_transit"),
        func.sum(Inventory.estimated_holding_cost).label("holding_cost_amt"),
        func.avg(Inventory.days_in_stock).label("avg_days_in_stock"),
        func.sum(Inventory.units_sold_last_30d).label("units_sold_30d"),
    )
    query = apply_inventory_filters(query, filters)
    query = query.group_by(Inventory.record_date).order_by(Inventory.record_date)
    return pd.read_sql(query.statement, session.bind)


def get_aging_buckets(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    """Aging ladder over a snapshot, with units and tied-up capital per bucket."""
    if snapshot_df.empty:
        return pd.DataFrame()
    rows = []
    for (lo, hi), label in zip(AGING_BUCKETS, AGING_LABELS):
        sel = snapshot_df[
            (snapshot_df["days_in_stock"] >= lo) & (snapshot_df["days_in_stock"] <= hi)
        ]
        rows.append({
            "bucket": label,
            "units": int(sel["current_stock"].sum()),
            "lines": int(len(sel)),
            "capital_amt": float(sel["inventory_value_amt"].sum()),
            "holding_cost_amt": float(sel["estimated_holding_cost"].sum()),
        })
    return pd.DataFrame(rows)


def get_lease_return_pipeline(session: Session, filters: dict = None,
                              months_ahead: int = 12,
                              as_of: date = None) -> pd.DataFrame:
    """
    Units scheduled to return off lease between `as_of` and `months_ahead` out.

    Unlike a demand forecast this is close to deterministic: the contract fixes
    the maturity date, so this is supply the network already owns. Returned at
    contract-line grain with the residual (contractual buyout) attached.
    """
    if as_of is None:
        as_of = date.today()
    horizon_month = as_of.year * 12 + (as_of.month - 1) + months_ahead
    horizon = date(horizon_month // 12, horizon_month % 12 + 1, 28)

    query = (
        session.query(
            Sale.sale_id,
            Sale.sale_date,
            Sale.customer_id,
            Sale.dealer_id,
            Sale.vehicle_id,
            Sale.brand,
            Sale.model,
            Sale.vehicle_category,
            Sale.fuel_type,
            Sale.region,
            Sale.city,
            Sale.lease_term_months,
            Sale.lease_maturity_date,
            Sale.residual_value_pct,
            Sale.residual_value,
            Sale.contract_mileage_allowance,
            Sale.lease_monthly_payment,
            Sale.selling_price,
            Sale.base_price,
            Dealer.dealer_name,
            Vehicle.variant,
            Vehicle.price.label("current_msrp"),
            Vehicle.residual_value_36mo,
        )
        .outerjoin(Dealer, Sale.dealer_id == Dealer.dealer_id)
        .outerjoin(Vehicle, Sale.vehicle_id == Vehicle.vehicle_id)
        .filter(Sale.financing_type == "Lease")
        .filter(Sale.lease_maturity_date.isnot(None))
        .filter(Sale.lease_maturity_date >= as_of)
        .filter(Sale.lease_maturity_date <= horizon)
    )

    if filters:
        if filters.get("region"):
            query = query.filter(Sale.region == filters["region"])
        if filters.get("city"):
            query = query.filter(Sale.city == filters["city"])
        if filters.get("brand"):
            query = query.filter(Sale.brand == filters["brand"])
        if filters.get("vehicle_category"):
            query = query.filter(Sale.vehicle_category == filters["vehicle_category"])
        if filters.get("fuel_type"):
            query = query.filter(Sale.fuel_type == filters["fuel_type"])

    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return df

    df["lease_maturity_date"] = pd.to_datetime(df["lease_maturity_date"])
    df["maturity_month"] = df["lease_maturity_date"].dt.to_period("M").dt.to_timestamp()

    # Estimated wholesale value at return, from the vehicle's own residual curve
    # applied to today's MSRP. Where that exceeds the contractual buyout the unit
    # comes back "in the money" and is worth retaining rather than grounding to
    # auction.
    est_market = df["current_msrp"].fillna(df["base_price"]) * df["residual_value_36mo"].fillna(0.55)
    df["est_market_value_amt"] = est_market.round(0)
    df["equity_amt"] = (df["est_market_value_amt"] - df["residual_value"]).round(0)
    df["in_the_money"] = df["equity_amt"] > 0
    return df


def get_lease_maturity_recapture(session: Session, filters: dict = None,
                                 days_ahead: int = 90,
                                 as_of: date = None) -> pd.DataFrame:
    """
    Customers whose lease matures inside the window — a lease return is also a
    shopper who needs a replacement vehicle in the next quarter.
    """
    if as_of is None:
        as_of = date.today()
    horizon = as_of + pd.Timedelta(days=days_ahead).to_pytimedelta()

    query = (
        session.query(
            Sale.sale_id,
            Sale.customer_id,
            Sale.dealer_id,
            Sale.brand,
            Sale.model,
            Sale.vehicle_category,
            Sale.region,
            Sale.lease_maturity_date,
            Sale.lease_monthly_payment,
            Sale.residual_value,
            Customer.name.label("customer_name"),
            Customer.customer_segment,
            Customer.loyalty_score,
            Customer.churn_risk_score,
            Customer.annual_income,
            Customer.preferred_vehicle_category,
            Dealer.dealer_name,
        )
        .outerjoin(Customer, Sale.customer_id == Customer.customer_id)
        .outerjoin(Dealer, Sale.dealer_id == Dealer.dealer_id)
        .filter(Sale.financing_type == "Lease")
        .filter(Sale.lease_maturity_date.isnot(None))
        .filter(Sale.lease_maturity_date >= as_of)
        .filter(Sale.lease_maturity_date <= horizon)
    )
    if filters:
        if filters.get("region"):
            query = query.filter(Sale.region == filters["region"])
        if filters.get("brand"):
            query = query.filter(Sale.brand == filters["brand"])
        if filters.get("vehicle_category"):
            query = query.filter(Sale.vehicle_category == filters["vehicle_category"])
    return pd.read_sql(query.statement, session.bind)


def get_trade_in_activity(session: Session, filters: dict = None) -> pd.DataFrame:
    """Deal-level trade-in detail, for concession and elasticity analysis."""
    query = session.query(
        Sale.sale_id,
        Sale.sale_date,
        Sale.year,
        Sale.month,
        Sale.brand,
        Sale.model,
        Sale.vehicle_category,
        Sale.region,
        Sale.city,
        Sale.dealer_id,
        Sale.financing_type,
        Sale.base_price,
        Sale.selling_price,
        Sale.discount_pct,
        Sale.lead_to_close_days,
        Sale.season_period,
        Sale.trade_in_flag,
        Sale.trade_in_brand,
        Sale.trade_in_model,
        Sale.trade_in_year,
        Sale.trade_in_mileage,
        Sale.trade_in_appraised_value,
        Sale.trade_in_allowance,
        Sale.trade_in_over_allowance,
        Sale.trade_bonus,
    )
    query = apply_sale_filters(query, filters)
    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return df

    # True concession = sticker discount + over-allowance + trade bonus. Only
    # the first of these shows up in discount_pct, which is why reported
    # discount understates what the store actually gave away.
    df["sticker_discount_amt"] = (df["base_price"] - df["selling_price"]).clip(lower=0)
    df["over_allowance_amt"] = df["trade_in_over_allowance"].fillna(0)
    df["trade_bonus"] = df["trade_bonus"].fillna(0)
    df["true_concession_amt"] = (
        df["sticker_discount_amt"] + df["over_allowance_amt"] + df["trade_bonus"]
    )
    df["true_concession_pct"] = (
        df["true_concession_amt"] / df["base_price"].replace(0, pd.NA) * 100
    ).astype(float)
    return df


def get_trade_replacement_flow(session: Session, filters: dict = None,
                               top_n: int = 12) -> pd.DataFrame:
    """
    What customers traded in vs. what they drove away in.

    This is revealed substitution behaviour straight from closed deals, and it
    is the empirical half of the placement recommender.
    """
    query = (
        session.query(
            Sale.trade_in_brand,
            Sale.brand.label("purchased_brand"),
            Sale.vehicle_category.label("purchased_category"),
            func.count(Sale.sale_id).label("deals"),
        )
        .filter(Sale.trade_in_flag.is_(True))
        .filter(Sale.trade_in_brand.isnot(None))
    )
    query = apply_sale_filters(query, filters)
    query = query.group_by(Sale.trade_in_brand, Sale.brand, Sale.vehicle_category)
    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return df
    return df.sort_values("deals", ascending=False)


def get_vehicle_catalog(session: Session) -> pd.DataFrame:
    """Full product catalog with the spec attributes the matcher scores on."""
    query = session.query(
        Vehicle.vehicle_id,
        Vehicle.brand,
        Vehicle.model,
        Vehicle.variant,
        Vehicle.category,
        Vehicle.fuel_type,
        Vehicle.price,
        Vehicle.power_kw,
        Vehicle.consumption_l_per_100km,
        Vehicle.range_km,
        Vehicle.seating_capacity,
        Vehicle.drive_type,
        Vehicle.safety_rating,
        Vehicle.warranty_years,
        Vehicle.residual_value_36mo,
        Vehicle.co2_g_per_km,
    ).filter(Vehicle.is_active.is_(True))
    return pd.read_sql(query.statement, session.bind)


def get_substitution_history(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Co-purchase behaviour by segment: for each (category, price band), which
    models actually sell. Used to weight attribute similarity toward pairs that
    real buyers genuinely cross-shop.
    """
    query = session.query(
        Sale.vehicle_category,
        Sale.brand,
        Sale.model,
        Sale.fuel_type,
        func.count(Sale.sale_id).label("units"),
        func.avg(Sale.selling_price).label("avg_price"),
    )
    query = apply_sale_filters(query, filters)
    query = query.group_by(Sale.vehicle_category, Sale.brand, Sale.model, Sale.fuel_type)
    return pd.read_sql(query.statement, session.bind)
