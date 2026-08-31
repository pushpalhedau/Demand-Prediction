from sqlalchemy import func, and_, or_, extract, desc, asc, case
from sqlalchemy.orm import Session
from database.models import Customer, Vehicle, Dealer, Sale, Inventory, ExternalFactor
from database.connection import get_db_session # This line is already present, no change needed
import pandas as pd
import numpy as np
from datetime import datetime, date

# NOTE: figures in this module are the dealer group's own booked sales and
# revenue — one row per retail deal at one of the group's rooftops. There is no
# market-level extrapolation. (A prior build multiplied every unit/revenue
# figure by a fixed "national implied volume" factor; that was an OEM/market-
# analyst framing and has been removed for the dealer-facing product.)


def _shift_years(d, n):
    try:
        return d.replace(year=d.year - n)
    except ValueError:            # Feb 29 → Feb 28
        return d.replace(year=d.year - n, day=28)


def _period_aggregates(session: Session, filters: dict) -> dict:
    """One pass over the filtered sales window: units, revenue, non-cash mix,
    average discount, average lead-to-close."""
    q = session.query(
        func.coalesce(func.sum(Sale.units_sold), 0).label("units"),
        func.coalesce(func.sum(Sale.total_revenue_incl_tax), 0).label("revenue"),
        func.coalesce(func.avg(Sale.discount_pct), 0.0).label("avg_discount"),
        func.coalesce(func.avg(Sale.lead_to_close_days), 0.0).label("avg_lead_close"),
        func.coalesce(
            func.sum(case((Sale.financing_type == "Cash", 0), else_=Sale.units_sold)), 0
        ).label("noncash_units"),
    )
    q = _apply_sale_filters(q, filters)
    r = q.first()
    units = r.units or 0
    return {
        "units": units,
        "revenue": r.revenue or 0,
        "avg_discount": r.avg_discount or 0.0,
        "avg_lead_close": r.avg_lead_close or 0.0,
        "noncash_pct": (100.0 * (r.noncash_units or 0) / units) if units else 0.0,
    }


def get_executive_kpis(session: Session, filters: dict = None) -> dict:
    """
    Core KPIs for the dealer-group Executive Overview.

    Every figure is the group's own booked retail volume/revenue for the
    filtered window — no market extrapolation. KPIs are chosen for a dealer
    principal / GM audience: volume, revenue, pace against the store network's
    own sales targets, and how much of the business is financed vs. cash.
    """
    filters = filters or {}
    cur = _period_aggregates(session, filters)

    total_sales = cur["units"]
    total_revenue = cur["revenue"]
    avg_discount = cur["avg_discount"]
    avg_lead_close = cur["avg_lead_close"]
    finance_lease_penetration = cur["noncash_pct"]

    total_sales_delta = total_revenue_delta = None
    avg_discount_delta = avg_lead_close_delta = None
    finance_lease_penetration_delta = None

    if filters.get("start_date") and filters.get("end_date"):
        prior = _period_aggregates(session, {
            **filters,
            "start_date": _shift_years(filters["start_date"], 1),
            "end_date": _shift_years(filters["end_date"], 1),
        })
        if prior["units"] > 0:
            total_sales_delta = (total_sales - prior["units"]) / prior["units"] * 100
        if prior["revenue"] > 0:
            total_revenue_delta = (total_revenue - prior["revenue"]) / prior["revenue"] * 100
        if prior["avg_discount"] > 0:
            avg_discount_delta = avg_discount - prior["avg_discount"]
        if prior["avg_lead_close"] > 0:
            avg_lead_close_delta = prior["avg_lead_close"] - avg_lead_close
        if prior["units"] > 0:
            finance_lease_penetration_delta = finance_lease_penetration - prior["noncash_pct"]

    # ── Target attainment: trailing 12 months vs the network's annual target ──
    attain = get_target_attainment(session, filters)

    # Top-selling vehicle category in the window
    cat_query = _apply_sale_filters(
        session.query(Sale.vehicle_category, func.sum(Sale.units_sold).label("cnt")), filters
    )
    top_cat_res = cat_query.group_by(Sale.vehicle_category).order_by(desc("cnt")).first()
    top_cat = top_cat_res[0] if top_cat_res else "N/A"

    cust_count = session.query(func.count(Customer.customer_id)).scalar()
    inv_stockout = session.query(func.count(Inventory.inventory_id)).filter(Inventory.stockout_flag == True).scalar()
    inv_reorder = session.query(func.count(Inventory.inventory_id)).filter(Inventory.reorder_needed == True).scalar()

    return {
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "avg_discount": avg_discount,
        "avg_lead_close": avg_lead_close,
        "finance_lease_penetration": finance_lease_penetration,
        "finance_lease_penetration_delta": finance_lease_penetration_delta,
        "total_sales_delta": total_sales_delta,
        "total_revenue_delta": total_revenue_delta,
        "avg_discount_delta": avg_discount_delta,
        "avg_lead_close_delta": avg_lead_close_delta,
        "top_vehicle_category": top_cat,
        "total_customers": cust_count,
        "inventory_stockout": inv_stockout,
        "inventory_reorder": inv_reorder,
        **attain,
    }


def _apply_dealer_scope(query, filters: dict):
    """Apply the location/brand slice of the global filters to a Dealer query."""
    if not filters:
        return query
    if filters.get("region"):
        query = query.filter(Dealer.state == filters["region"])
    if filters.get("city"):
        query = query.filter(Dealer.city == filters["city"])
    if filters.get("brand"):
        query = query.filter(Dealer.brand == filters["brand"])
    return query


def get_target_attainment(session: Session, filters: dict = None) -> dict:
    """
    Trailing-12-month unit sales for the in-scope stores vs. the sum of those
    stores' annual sales targets. This is 'are we on plan?', the number a GM
    opens the dashboard for — not a share-of-market figure.
    """
    filters = filters or {}
    end = filters.get("end_date")
    if end is None:
        end = session.query(func.max(Sale.sale_date)).scalar() or date.today()
    start = _shift_years(end, 1)

    def _units(s, e):
        q = session.query(func.coalesce(func.sum(Sale.units_sold), 0))
        q = _apply_sale_filters(q, {
            k: v for k, v in filters.items() if k not in ("start_date", "end_date")
        })
        return q.filter(Sale.sale_date > s, Sale.sale_date <= e).scalar() or 0

    ttm_units = _units(start, end)
    prior_ttm_units = _units(_shift_years(start, 1), _shift_years(end, 1))

    annual_target = _apply_dealer_scope(
        session.query(func.coalesce(func.sum(Dealer.annual_target_units), 0)), filters
    ).scalar() or 0

    attainment_pct = (100.0 * ttm_units / annual_target) if annual_target else None
    prior_attainment_pct = (100.0 * prior_ttm_units / annual_target) if annual_target else None
    delta = (
        attainment_pct - prior_attainment_pct
        if attainment_pct is not None and prior_attainment_pct is not None
        else None
    )
    return {
        "ttm_units": ttm_units,
        "annual_target": annual_target,
        "target_attainment_pct": attainment_pct,
        "target_attainment_delta": delta,
    }


def get_top_models(session: Session, filters: dict = None, limit: int = 8) -> pd.DataFrame:
    """Best-selling models in the window (brand + model), by units and revenue."""
    query = session.query(
        Sale.brand,
        Sale.model,
        func.sum(Sale.units_sold).label("units"),
        func.sum(Sale.total_revenue_incl_tax).label("revenue"),
    )
    query = _apply_sale_filters(query, filters)
    query = query.group_by(Sale.brand, Sale.model).order_by(desc("units")).limit(limit)
    return pd.read_sql(query.statement, session.bind)


def get_sales_by_store(session: Session, filters: dict = None, limit: int = 20) -> pd.DataFrame:
    """Units and revenue booked per rooftop in the window, best first."""
    query = session.query(
        Dealer.dealer_name,
        Dealer.city,
        Dealer.state,
        Dealer.brand,
        func.sum(Sale.units_sold).label("units"),
        func.sum(Sale.total_revenue_incl_tax).label("revenue"),
    ).join(Sale, Sale.dealer_id == Dealer.dealer_id)
    query = _apply_sale_filters(query, filters)
    query = query.group_by(
        Dealer.dealer_name, Dealer.city, Dealer.state, Dealer.brand
    ).order_by(desc("units")).limit(limit)
    return pd.read_sql(query.statement, session.bind)


def get_monthly_revenue_trend(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Get monthly revenue trend for the revenue charts.
    """
    query = session.query(
        Sale.year,
        Sale.month,
        func.sum(Sale.total_revenue_incl_tax).label("revenue"),
        func.sum(Sale.units_sold).label("sales")
    )
    query = _apply_sale_filters(query, filters)
    query = query.group_by(Sale.year, Sale.month).order_by(Sale.year, Sale.month)

    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df['date'] = pd.to_datetime(df[['year', 'month']].assign(day=1))
    return df


def get_sales_by_category(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Get sales distribution by vehicle category.
    """
    query = session.query(
        Sale.vehicle_category,
        func.sum(Sale.units_sold).label("sales"),
        func.sum(Sale.total_revenue_incl_tax).label("revenue")
    )
    query = _apply_sale_filters(query, filters)
    query = query.group_by(Sale.vehicle_category).order_by(desc("sales"))

    df = pd.read_sql(query.statement, session.bind)
    return df


def get_sales_by_fuel_type(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Get sales distribution by fuel type.
    """
    query = session.query(
        Sale.fuel_type,
        func.sum(Sale.units_sold).label("sales"),
        func.sum(Sale.total_revenue_incl_tax).label("revenue")
    )
    query = _apply_sale_filters(query, filters)
    query = query.group_by(Sale.fuel_type).order_by(desc("sales"))

    df = pd.read_sql(query.statement, session.bind)
    return df


def get_sales_by_region(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Get sales distribution by state.
    """
    query = session.query(
        Sale.state,
        func.sum(Sale.units_sold).label("sales"),
        func.sum(Sale.total_revenue_incl_tax).label("revenue")
    )
    query = _apply_sale_filters(query, filters)
    query = query.group_by(Sale.state).order_by(desc("sales"))

    df = pd.read_sql(query.statement, session.bind)
    return df


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
        Dealer.state,
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
    query = _apply_sale_filters(query, filters)
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
        q = _apply_sale_filters(q, tf).filter(
            Sale.sale_date > s, Sale.sale_date <= e
        ).group_by(Sale.dealer_id)
        return dict(pd.read_sql(q.statement, session.bind).itertuples(index=False, name=None))

    ttm_units = _units_by_store(_shift_years(end, 1), end)
    prior_ttm_units = _units_by_store(_shift_years(end, 2), _shift_years(end, 1))

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
    cat_q = _apply_sale_filters(cat_q, filters)
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

    return df


def get_yoy_comparison(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Returns monthly units/revenue by (year, month) for every year in the window.

    SUPERSEDED for the Comparative Analytics tab by get_period_trend(), which
    frames the same data as "this period vs the same period last year" (two
    aligned series) rather than one line per calendar year. Kept for any other
    caller and for ad-hoc multi-year overlays.
    """
    query = session.query(
        Sale.year,
        Sale.month,
        func.sum(Sale.total_revenue_incl_tax).label("revenue"),
        func.sum(Sale.units_sold).label("sales")
    )
    query = _apply_sale_filters(query, filters)
    query = query.group_by(Sale.year, Sale.month).order_by(Sale.month, Sale.year)

    df = pd.read_sql(query.statement, session.bind)
    return df


def get_customer_segments_data(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    One row per customer in the group's CRM, with the KMeans `customer_segment`
    label and each customer's real booked history (lifetime deals, revenue,
    average deal value, financing mix, months since last deal) joined from the
    sales table — everything the Customer Intelligence tab needs to describe a
    segment as an actionable group rather than a scatter cluster.

    `nationality` is intentionally not selected — segmenting or profiling US auto
    customers by national origin is a fair-lending liability (see the model
    comment on Customer.nationality). `filters['region']` optionally scopes the
    view to customers whose home state matches the sidebar region.
    """
    cust = pd.read_sql(
        session.query(
            Customer.customer_id,
            Customer.age,
            Customer.state,
            Customer.income_bracket,
            Customer.estimated_annual_income_usd,
            Customer.credit_score,
            Customer.number_of_past_purchases,
            Customer.loyalty_score,
            Customer.churn_risk_score,
            Customer.customer_segment,
            Customer.last_activity_date,
        ).statement,
        session.bind,
    )
    if filters and filters.get("region"):
        cust = cust[cust["state"] == filters["region"]]

    deals = pd.read_sql(
        session.query(
            Sale.customer_id.label("customer_id"),
            func.count(Sale.sale_id).label("lifetime_deals"),
            func.sum(Sale.total_revenue_incl_tax).label("lifetime_revenue"),
            func.avg(Sale.total_revenue_incl_tax).label("avg_deal_value"),
            func.max(Sale.sale_date).label("last_deal_date"),
            func.sum(case((Sale.financing_type == "Lease", 1), else_=0)).label("lease_deals"),
            func.sum(case((Sale.financing_type == "Cash", 1), else_=0)).label("cash_deals"),
        ).group_by(Sale.customer_id).statement,
        session.bind,
    )

    df = cust.merge(deals, on="customer_id", how="left")
    for c in ["lifetime_deals", "lifetime_revenue", "lease_deals", "cash_deals"]:
        df[c] = df[c].fillna(0)
    df["finance_deals"] = (df["lifetime_deals"] - df["lease_deals"] - df["cash_deals"]).clip(lower=0)

    ref = pd.Timestamp(date.today())
    last_deal = pd.to_datetime(df["last_deal_date"], errors="coerce")
    df["months_since_last_deal"] = ((ref - last_deal).dt.days / 30.44).round(1)

    return df


def get_customer_book(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    One row per CRM customer, shaped for the Retention & Actions view: identity +
    segment + credit/income, and — joined from the sales table — first & last
    deal dates, lifetime deals/revenue, the store and vehicle of the most recent
    deal, the customer's own average months-between-purchases (cadence), and the
    nearest upcoming lease maturity (date + vehicle + store). `filters['region']`
    scopes to customers whose home state matches the sidebar region.

    No `nationality` (fair-lending). Customer counts are raw.
    """
    cust = pd.read_sql(
        session.query(
            Customer.customer_id,
            Customer.name,
            Customer.age,
            Customer.state,
            Customer.city,
            Customer.income_bracket,
            Customer.estimated_annual_income_usd,
            Customer.credit_score,
            Customer.customer_segment,
            Customer.churn_risk_score,
            Customer.email_opt_in,
        ).statement,
        session.bind,
    )
    if filters and filters.get("region"):
        cust = cust[cust["state"] == filters["region"]]

    sales = pd.read_sql(
        session.query(
            Sale.customer_id.label("customer_id"),
            Sale.sale_date,
            Sale.brand,
            Sale.model,
            Sale.vehicle_category,
            Sale.financing_type,
            Sale.lease_maturity_date,
            Sale.total_revenue_incl_tax.label("deal_revenue"),
            Dealer.dealer_name.label("store"),
        ).join(Dealer, Sale.dealer_id == Dealer.dealer_id).statement,
        session.bind,
    )
    sales = sales[sales["customer_id"].isin(set(cust["customer_id"]))]
    sales["sale_date"] = pd.to_datetime(sales["sale_date"], errors="coerce")
    sales = sales.sort_values("sale_date")

    g = sales.groupby("customer_id")
    agg = g.agg(
        n_deals=("sale_date", "size"),
        first_deal=("sale_date", "min"),
        last_deal=("sale_date", "max"),
        lifetime_revenue=("deal_revenue", "sum"),
    )

    last_row = sales.drop_duplicates("customer_id", keep="last").set_index("customer_id")
    agg["last_store"] = last_row["store"]
    agg["last_brand"] = last_row["brand"]
    agg["last_model"] = last_row["model"]
    agg["last_category"] = last_row["vehicle_category"]

    # Average months between consecutive purchases, per repeat buyer — the mean
    # gap is just the span divided by the number of gaps.
    span_days = (agg["last_deal"] - agg["first_deal"]).dt.days
    agg["cadence_months"] = (span_days / (agg["n_deals"] - 1).where(agg["n_deals"] > 1) / 30.44).round(1)

    # Nearest lease maturity still ahead of us.
    ref = pd.Timestamp(date.today())
    lm = sales[
        (sales["financing_type"] == "Lease")
        & sales["lease_maturity_date"].notna()
    ].copy()
    lm["lease_maturity_date"] = pd.to_datetime(lm["lease_maturity_date"], errors="coerce")
    lm = lm[lm["lease_maturity_date"] >= ref].sort_values("lease_maturity_date")
    lm_first = lm.drop_duplicates("customer_id", keep="first").set_index("customer_id")
    agg["next_lease_maturity"] = lm_first["lease_maturity_date"]
    agg["lease_store"] = lm_first["store"]
    agg["lease_vehicle"] = (lm_first["brand"].astype(str) + " " + lm_first["model"].astype(str))

    df = cust.merge(agg, on="customer_id", how="left")
    df["n_deals"] = df["n_deals"].fillna(0).astype(int)
    df["lifetime_revenue"] = df["lifetime_revenue"].fillna(0)
    df["months_since_last_deal"] = ((ref - pd.to_datetime(df["last_deal"])).dt.days / 30.44).round(1)
    df["first_deal_year"] = pd.to_datetime(df["first_deal"]).dt.year
    return df


def get_repeat_contribution(session: Session, filters: dict = None) -> dict:
    """
    How much of the group's recent volume is repeat business: the share of the
    last 12 months' deals that went to a customer who had bought from the group
    before, plus the all-time share. `filters['region']` scopes by the store's
    state (same as the other Sale-based queries)."""
    q = session.query(Sale.customer_id, Sale.sale_date, Sale.state)
    df = pd.read_sql(q.statement, session.bind)
    if filters and filters.get("region"):
        df = df[df["state"] == filters["region"]]
    if df.empty:
        return {"ttm_total": 0, "ttm_repeat": 0, "ttm_pct": 0.0, "all_pct": 0.0}

    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    df = df.sort_values("sale_date")
    df["first_dt"] = df.groupby("customer_id")["sale_date"].transform("min")
    df["is_repeat_txn"] = df["sale_date"] > df["first_dt"]

    ref = df["sale_date"].max()
    ttm = df[df["sale_date"] >= ref - pd.Timedelta(days=365)]
    return {
        "ttm_total": int(len(ttm)),
        "ttm_repeat": int(ttm["is_repeat_txn"].sum()),
        "ttm_pct": float(100 * ttm["is_repeat_txn"].mean()) if len(ttm) else 0.0,
        "all_pct": float(100 * df["is_repeat_txn"].mean()),
    }


def get_inventory_status(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    SUPERSEDED — use get_inventory_snapshot() for any present-day figure.

    This returns every row of the inventory table, which holds month-end
    snapshots. Aggregating the result counts the same physical car once for
    every month it sat on the lot: summing current_stock over the full table
    reports ~953k units against a real network position of ~2.2k. It also
    ignores the brand filter.

    Kept only so existing callers do not break. No longer used by the dashboard.
    """
    query = session.query(
        Inventory.inventory_id,
        Inventory.dealer_id,
        Inventory.city,
        Inventory.state,
        Inventory.brand,
        Inventory.model,
        Inventory.vehicle_category,
        Inventory.current_stock,
        Inventory.demand_forecast_30d,
        Inventory.reorder_point,
        Inventory.days_in_stock,
        Inventory.stockout_flag,
        Inventory.overstock_flag,
        Inventory.reorder_needed,
        Inventory.stockout_risk_score,
        Inventory.overstock_risk_score,
        Inventory.holding_cost_per_day_usd,
        Inventory.estimated_holding_cost_usd,
        Inventory.units_sold_last_30d,
        Inventory.units_ordered,
        Inventory.transit_stock,
        Inventory.warehouse_zone
    )

    if filters:
        if filters.get("region"):
            query = query.filter(Inventory.state == filters["region"])
        if filters.get("city"):
            query = query.filter(Inventory.city == filters["city"])
        if filters.get("vehicle_category"):
            query = query.filter(Inventory.vehicle_category == filters["vehicle_category"])
        if filters.get("fuel_type"):
            query = query.filter(Inventory.fuel_type == filters["fuel_type"])

    df = pd.read_sql(query.statement, session.bind)
    return df


def update_inventory_from_csv(session: Session, df: pd.DataFrame):
    """
    Helper to support the 'Upload CSV' requirement.
    Bulk insert/update the inventory table.
    """
    pass


def get_fed_rate_kpi(session: Session, filters: dict = None) -> dict:
    """
    Returns the US Federal Funds Rate for the selected period and YoY delta.
    Uses the period-end rate (last month within the date range).
    """
    def _period_end_rate(start_date, end_date):
        q = session.query(ExternalFactor.us_fed_rate_pct, ExternalFactor.year, ExternalFactor.month)
        if start_date and end_date:
            sy, sm = start_date.year, start_date.month
            ey, em = end_date.year, end_date.month
            q = q.filter(
                (ExternalFactor.year * 100 + ExternalFactor.month) >= (sy * 100 + sm),
                (ExternalFactor.year * 100 + ExternalFactor.month) <= (ey * 100 + em),
            )
        row = q.order_by(ExternalFactor.year.desc(), ExternalFactor.month.desc()).first()
        return row.us_fed_rate_pct if row else None

    current_rate = _period_end_rate(
        filters.get("start_date") if filters else None,
        filters.get("end_date") if filters else None,
    )

    delta = None
    if filters and filters.get("start_date") and filters.get("end_date") and current_rate is not None:
        sd, ed = filters["start_date"], filters["end_date"]
        prior_rate = _period_end_rate(
            sd.replace(year=sd.year - 1),
            ed.replace(year=ed.year - 1),
        )
        if prior_rate is not None:
            delta = round(current_rate - prior_rate, 2)

    return {"rate": current_rate or 0.0, "delta": delta}


def get_top_brand_kpi(session: Session, filters: dict = None) -> dict:
    """
    Returns the #1 brand by national-implied units sold for the selected period,
    its market share %, and YoY share delta.
    """
    def _brand_shares(f):
        q = session.query(Sale.brand, func.sum(Sale.units_sold).label("units"))
        q = _apply_sale_filters(q, f)
        rows = q.group_by(Sale.brand).all()
        if not rows:
            return None, None
        total = sum(r.units for r in rows)
        top = max(rows, key=lambda r: r.units)
        share = round((top.units / total) * 100, 1) if total else 0.0
        return top.brand, share

    brand, share = _brand_shares(filters)

    delta = None
    if filters and filters.get("start_date") and filters.get("end_date") and share is not None:
        sd, ed = filters["start_date"], filters["end_date"]
        prior_filters = filters.copy()
        prior_filters["start_date"] = sd.replace(year=sd.year - 1)
        prior_filters["end_date"] = ed.replace(year=ed.year - 1)
        _, prior_share = _brand_shares(prior_filters)
        if prior_share is not None:
            delta = round(share - prior_share, 1)

    return {"brand": brand or "N/A", "share": share or 0.0, "delta": delta}


def get_unique_filter_options(session: Session) -> dict:
    """
    Gets lists of unique states, cities, categories, fuel types, brands and years
    to populate filters in the Streamlit sidebar.
    """
    regions = [r[0] for r in session.query(Sale.state).distinct().all() if r[0]]
    cities = [c[0] for c in session.query(Sale.city).distinct().all() if c[0]]
    categories = [cat[0] for cat in session.query(Sale.vehicle_category).distinct().all() if cat[0]]
    fuels = [f[0] for f in session.query(Sale.fuel_type).distinct().all() if f[0]]
    brands = [b[0] for b in session.query(Sale.brand).distinct().all() if b[0]]
    years = sorted([y[0] for y in session.query(Sale.year).distinct().all() if y[0]])

    return {
        "regions": sorted(regions),
        "cities": sorted(cities),
        "categories": sorted(categories),
        "fuel_types": sorted(fuels),
        "brands": sorted(brands),
        "years": years
    }


def _apply_sale_filters(query, filters: dict = None):
    """
    Helper to apply global filters to sales-related queries.
    """
    if not filters:
        return query

    if filters.get("region"):
        query = query.filter(Sale.state == filters["region"])
    if filters.get("city"):
        query = query.filter(Sale.city == filters["city"])

    if filters.get("vehicle_category"):
        query = query.filter(Sale.vehicle_category == filters["vehicle_category"])
    if filters.get("fuel_type"):
        query = query.filter(Sale.fuel_type == filters["fuel_type"])
    if filters.get("brand"):
        query = query.filter(Sale.brand == filters["brand"])
    if filters.get("financing_type"):
        query = query.filter(Sale.financing_type == filters["financing_type"])

    # Apply date filters
    if filters.get("start_date"):
        query = query.filter(Sale.sale_date >= filters["start_date"])
    if filters.get("end_date"):
        query = query.filter(Sale.sale_date <= filters["end_date"])

    return query


# ─────────────────────────────────────────────────────────────────────────────
# Tariff exposure — constants & queries
#
# Section 232 auto tariffs (25% on imported vehicles, effective Apr 2025) raise
# the landed cost of the group's IMPORT-brand franchises far more than its
# domestic ones. The dealer-facing question is "what does this cost our import
# rooftops, and how does it move the price gap against the domestic models we
# also sell" — get_tariff_exposure / get_tariff_cost_monthly / get_price_gap_*
# answer that from the group's own booked deals (tariff_cost_usd per row).
#
# The older share-of-market views below (get_brand_origin_yearly_share,
# get_ev_segment_by_brand_year, get_market_share_shift) computed "% of the US
# market" from the group's own 24-rooftop book — an OEM / equity-analyst frame
# that does not fit a dealer group. They are retained (unused) in case another
# module has a legitimate use; do not wire them back into Comparative Analytics.
# ─────────────────────────────────────────────────────────────────────────────

IMPORT_BRANDS = ['Toyota', 'Honda', 'Nissan', 'Subaru', 'Lexus', 'Hyundai', 'Kia', 'BMW', 'Mercedes-Benz', 'Volkswagen']

BRAND_ORIGIN = {
    'Toyota': 'Japanese',      'Nissan': 'Japanese',
    'Honda': 'Japanese',       'Lexus': 'Japanese',       'Subaru': 'Japanese',
    'Hyundai': 'Korean',       'Kia': 'Korean',
    'BMW': 'European',         'Mercedes-Benz': 'European', 'Volkswagen': 'European',
    'Ford': 'Domestic',        'Chevrolet': 'Domestic',    'Jeep': 'Domestic',
    'GMC': 'Domestic',         'Ram': 'Domestic',
    'Tesla': 'Domestic',
}


def _filters_no_brand(filters: dict) -> dict:
    """Return a copy of filters with brand cleared so import/domestic queries see all brands."""
    if not filters:
        return {}
    return {**filters, 'brand': None}


def get_brand_origin_yearly_share(session: Session, filters: dict = None) -> pd.DataFrame:
    """Year-by-year units per brand with origin tag. Brand filter is always ignored.

    DEPRECATED (2026-08-28): powered the "Brand Origin Market Share Growth" /
    "% of Total US Market" charts, which read the group's own book as if it were
    the national market. Left defined; not called by any tab."""
    query = session.query(
        Sale.year,
        Sale.brand,
        func.sum(Sale.units_sold).label("units")
    )
    query = _apply_sale_filters(query, _filters_no_brand(filters))
    query = query.group_by(Sale.year, Sale.brand).order_by(Sale.year)
    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return df
    df['origin'] = df['brand'].map(BRAND_ORIGIN).fillna('Other')
    return df


def get_price_competitiveness(session: Session, filters: dict = None) -> pd.DataFrame:
    """Weighted avg selling price and total units per brand+category. Brand filter ignored."""
    query = session.query(
        Sale.brand,
        Sale.vehicle_category,
        func.avg(Sale.selling_price_usd).label("avg_price"),
        func.sum(Sale.units_sold).label("units")
    )
    query = _apply_sale_filters(query, _filters_no_brand(filters))
    query = query.group_by(Sale.brand, Sale.vehicle_category)
    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return df
    df['origin'] = df['brand'].map(BRAND_ORIGIN).fillna('Other')
    grand_total = df['units'].sum()
    df['market_share_pct'] = (df['units'] / grand_total * 100).round(2) if grand_total else 0.0
    return df


def get_ev_segment_by_brand_year(session: Session, filters: dict = None) -> pd.DataFrame:
    """Electric vehicle units by brand and year. Brand and fuel_type filters ignored.

    DEPRECATED (2026-08-28): powered "EV Segment Ownership by Origin" / the
    "Domestic EV Segment Share of total US EV market" KPI — again the group's
    own EV deals mislabelled as a national segment. Left defined; not called."""
    f = {**_filters_no_brand(filters), 'fuel_type': None}
    query = session.query(
        Sale.year,
        Sale.brand,
        func.sum(Sale.units_sold).label("ev_units")
    ).filter(Sale.fuel_type == 'Electric')
    query = _apply_sale_filters(query, f)
    query = query.group_by(Sale.year, Sale.brand).order_by(Sale.year)
    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return df
    df['origin'] = df['brand'].map(BRAND_ORIGIN).fillna('Other')
    return df


def get_market_share_shift(session: Session, filters: dict = None) -> pd.DataFrame:
    """Brand market share in the base year vs latest year within the filter date range.

    DEPRECATED (2026-08-28): powered the "Market Share Shift — who gained, who
    lost" diverging bar, an equity-analyst winners/losers view computed on the
    group's own book (and comparing a full base year against a partial latest
    year). Left defined; not called by any tab."""
    if filters and filters.get("start_date") and filters.get("end_date"):
        base_year = filters["start_date"].year
        curr_year = filters["end_date"].year
    else:
        base_year, curr_year = 2019, 2026

    if base_year >= curr_year:
        curr_year = base_year + 1

    # Apply region/category filters only — no date or brand filtering here
    extra: dict = {}
    if filters:
        if filters.get("region"):
            extra["region"] = filters["region"]
        if filters.get("vehicle_category"):
            extra["vehicle_category"] = filters["vehicle_category"]

    def _year_shares(yr: int) -> dict:
        q = session.query(Sale.brand, func.sum(Sale.units_sold).label("units"))
        q = _apply_sale_filters(q, extra)
        q = q.filter(Sale.year == yr).group_by(Sale.brand)
        rows = q.all()
        total = sum(r.units for r in rows)
        return {r.brand: round(r.units / total * 100, 2) for r in rows} if total else {}

    base_shares = _year_shares(base_year)
    curr_shares  = _year_shares(curr_year)
    all_brands   = set(base_shares) | set(curr_shares)

    records = [{
        'brand':        b,
        'base_share':   base_shares.get(b, 0.0),
        'curr_share':   curr_shares.get(b,  0.0),
        'share_change': round(curr_shares.get(b, 0.0) - base_shares.get(b, 0.0), 2),
        'origin':       BRAND_ORIGIN.get(b, 'Other'),
        'base_year':    base_year,
        'curr_year':    curr_year,
    } for b in all_brands]

    return pd.DataFrame(records).sort_values('share_change', ascending=False)


# ─────────────────────────────────────────────────────────────────────────────
# Comparative Analytics — "how are we tracking vs last year" + tariff exposure
# ─────────────────────────────────────────────────────────────────────────────

def get_period_trend(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Monthly booked units and revenue for the selected window, plus the SAME
    window one year earlier, aligned on the calendar month so the two series
    overlay directly. Long form: columns [date, period, units, revenue] where
    period is "This period" or "Prior year".
    """
    filters = filters or {}

    cols = ["date", "period", "units", "revenue"]

    def _monthly(f: dict) -> pd.DataFrame:
        q = session.query(
            Sale.year, Sale.month,
            func.sum(Sale.units_sold).label("units"),
            func.sum(Sale.total_revenue_incl_tax).label("revenue"),
        )
        q = _apply_sale_filters(q, f)
        q = q.group_by(Sale.year, Sale.month).order_by(Sale.year, Sale.month)
        d = pd.read_sql(q.statement, session.bind)
        if d.empty:
            return pd.DataFrame(columns=["date", "units", "revenue"])
        d["date"] = pd.to_datetime(d[["year", "month"]].assign(day=1))
        return d[["date", "units", "revenue"]]

    cur = _monthly(filters)
    cur["period"] = "This period"

    prior = pd.DataFrame(columns=["date", "units", "revenue"])
    if filters.get("start_date") and filters.get("end_date"):
        prior = _monthly({
            **filters,
            "start_date": _shift_years(filters["start_date"], 1),
            "end_date": _shift_years(filters["end_date"], 1),
        })
        if not prior.empty:
            prior["date"] = prior["date"] + pd.DateOffset(years=1)
    prior["period"] = "Prior year"

    return pd.concat([cur[cols], prior[cols]], ignore_index=True)


def get_yoy_drivers(session: Session, filters: dict = None,
                    dimension: str = "store") -> pd.DataFrame:
    """
    Window total vs the same window a year earlier, broken out by one dimension
    so the tab can show WHAT moved the number. dimension ∈ {store, brand,
    category}. Returns [name, curr_units, prev_units, curr_revenue,
    prev_revenue, delta_units, delta_revenue].
    """
    filters = filters or {}
    dim_col = {
        "store": Dealer.dealer_name,
        "brand": Sale.brand,
        "category": Sale.vehicle_category,
    }.get(dimension, Dealer.dealer_name)

    def _agg(f: dict) -> pd.DataFrame:
        q = session.query(
            dim_col.label("name"),
            func.sum(Sale.units_sold).label("units"),
            func.sum(Sale.total_revenue_incl_tax).label("revenue"),
        )
        if dimension == "store":
            q = q.join(Dealer, Sale.dealer_id == Dealer.dealer_id)
        q = _apply_sale_filters(q, f)
        q = q.group_by(dim_col)
        return pd.read_sql(q.statement, session.bind)

    cur = _agg(filters).rename(columns={"units": "curr_units", "revenue": "curr_revenue"})

    if filters.get("start_date") and filters.get("end_date"):
        prev = _agg({
            **filters,
            "start_date": _shift_years(filters["start_date"], 1),
            "end_date": _shift_years(filters["end_date"], 1),
        }).rename(columns={"units": "prev_units", "revenue": "prev_revenue"})
    else:
        prev = pd.DataFrame(columns=["name", "prev_units", "prev_revenue"])

    m = cur.merge(prev, on="name", how="outer")
    for c in ["curr_units", "prev_units", "curr_revenue", "prev_revenue"]:
        m[c] = m[c].fillna(0)
    m["delta_units"] = m["curr_units"] - m["prev_units"]
    m["delta_revenue"] = m["curr_revenue"] - m["prev_revenue"]
    return m


_TARIFF_START = date(2025, 4, 1)   # Section 232 25% duty on imported vehicles


def get_tariff_exposure(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Per-brand units, tariff dollars baked into stickers, and selling-price total
    for the group's deals since the tariff took effect. Location/category/fuel
    filters are honored; the single-brand filter is ignored so the import-vs-
    domestic contrast always holds. Columns: [brand, origin, is_import, units,
    tariff_total, sales_total].
    """
    f = _filters_no_brand(filters)
    q = session.query(
        Sale.brand,
        func.sum(Sale.units_sold).label("units"),
        func.coalesce(func.sum(Sale.tariff_cost_usd), 0).label("tariff_total"),
        func.coalesce(func.sum(Sale.selling_price_usd), 0).label("sales_total"),
    )
    q = _apply_sale_filters(q, f)
    q = q.filter(Sale.sale_date >= _TARIFF_START)
    q = q.group_by(Sale.brand)
    df = pd.read_sql(q.statement, session.bind)
    if df.empty:
        return df
    df["origin"] = df["brand"].map(BRAND_ORIGIN).fillna("Other")
    df["is_import"] = df["origin"].isin(["Japanese", "Korean", "European"])
    return df


def get_tariff_cost_monthly(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Monthly tariff dollars absorbed into the group's stickers and the number of
    tariffed (imported) units, from Jan 2025 so the April step change is visible.
    Columns: [date, tariff_total, tariffed_units].

    Not currently called by any tab (2026-08-31): the "tariff cost by month" bar
    was cut from Comparative Analytics as it only restated the KPI total. Kept
    defined for a future forward-cost view.
    """
    f = _filters_no_brand(filters)
    q = session.query(
        Sale.year, Sale.month,
        func.coalesce(func.sum(Sale.tariff_cost_usd), 0).label("tariff_total"),
        func.coalesce(
            func.sum(case((Sale.tariff_cost_usd > 0, Sale.units_sold), else_=0)), 0
        ).label("tariffed_units"),
    )
    q = _apply_sale_filters(q, f)
    q = q.filter(Sale.sale_date >= date(2025, 1, 1))
    q = q.group_by(Sale.year, Sale.month).order_by(Sale.year, Sale.month)
    df = pd.read_sql(q.statement, session.bind)
    if not df.empty:
        df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
    return df


def get_import_mix_monthly(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Monthly import-franchise share of the group's booked units, spanning ~24
    months to the sidebar end date so a shift in the mix after the April-2025
    tariff is visible. Location/segment/fuel filters honored; single-brand
    filter ignored. Columns: [date, import_units, total_units, import_share_pct].
    """
    f = _filters_no_brand(filters)
    end = f.get("end_date") or session.query(func.max(Sale.sale_date)).scalar() or date.today()
    start = (pd.Timestamp(end).replace(day=1) - pd.DateOffset(months=23)).date()
    q = session.query(
        Sale.year, Sale.month, Sale.brand,
        func.sum(Sale.units_sold).label("units"),
    )
    q = _apply_sale_filters(q, {**f, "start_date": start})
    q = q.group_by(Sale.year, Sale.month, Sale.brand)
    df = pd.read_sql(q.statement, session.bind)
    if df.empty:
        return df
    df["is_import"] = (
        df["brand"].map(BRAND_ORIGIN).fillna("Other")
        .isin(["Japanese", "Korean", "European"])
    )
    g = (
        df.assign(imp=lambda x: x["units"].where(x["is_import"], 0))
        .groupby(["year", "month"], as_index=False)
        .agg(import_units=("imp", "sum"), total_units=("units", "sum"))
    )
    g["date"] = pd.to_datetime(g[["year", "month"]].assign(day=1))
    g["import_share_pct"] = (g["import_units"] / g["total_units"].clip(lower=1) * 100).round(1)
    return g.sort_values("date")


def get_price_gap_by_segment(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Average selling price for the group's IMPORT-franchise deals vs its
    DOMESTIC-franchise deals, by vehicle category, since the tariff took effect,
    plus the average Section 232 tariff dollars inside each price.
    Columns: [vehicle_category, group, avg_price, avg_tariff, units].
    """
    f = _filters_no_brand(filters)
    q = session.query(
        Sale.vehicle_category,
        Sale.brand,
        func.sum(Sale.units_sold).label("units"),
        func.coalesce(func.sum(Sale.selling_price_usd), 0).label("price_sum"),
        func.coalesce(func.sum(Sale.tariff_cost_usd), 0).label("tariff_sum"),
    )
    q = _apply_sale_filters(q, f)
    q = q.filter(Sale.sale_date >= _TARIFF_START)
    q = q.group_by(Sale.vehicle_category, Sale.brand)
    df = pd.read_sql(q.statement, session.bind)
    if df.empty:
        return df
    origin = df["brand"].map(BRAND_ORIGIN).fillna("Other")
    df["group"] = origin.isin(["Japanese", "Korean", "European"]).map(
        {True: "Import franchises", False: "Domestic franchises"}
    )
    g = (
        df.groupby(["vehicle_category", "group"], as_index=False)
        .agg(price_sum=("price_sum", "sum"), tariff_sum=("tariff_sum", "sum"),
             units=("units", "sum"))
    )
    units = g["units"].clip(lower=1)
    g["avg_price"] = (g["price_sum"] / units).round(0)
    g["avg_tariff"] = (g["tariff_sum"] / units).round(0)
    return g[["vehicle_category", "group", "avg_price", "avg_tariff", "units"]]


def get_franchise_footprint(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    The group's own rooftops by franchise brand and origin (location filters
    honored, single-brand filter ignored). Columns: [brand, rooftops, origin].
    """
    q = session.query(
        Dealer.brand, func.count(Dealer.dealer_id).label("rooftops")
    )
    q = _apply_dealer_scope(q, _filters_no_brand(filters))
    q = q.group_by(Dealer.brand).order_by(desc("rooftops"))
    df = pd.read_sql(q.statement, session.bind)
    if not df.empty:
        df["origin"] = df["brand"].map(BRAND_ORIGIN).fillna("Other")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Inventory Intelligence — snapshot, flow, trade-in and placement queries
#
# The guiding rule here is that the inventory table holds month-end *snapshots*,
# so the same physical car appears once per month it was on the lot. Any query
# that reports a present-day position must therefore reduce to the latest
# snapshot per (dealer, vehicle) before it aggregates — summing the raw table
# counts each car once for every month of its life.
# ─────────────────────────────────────────────────────────────────────────────

# Healthy days-of-supply band used across the stock-health views.
DAYS_SUPPLY_HEALTHY_LOW = 45
DAYS_SUPPLY_HEALTHY_HIGH = 75

# Aging ladder buckets, in days on the lot.
AGING_BUCKETS = [(0, 30), (31, 60), (61, 90), (91, 10_000)]
AGING_LABELS = ["0-30 days", "31-60 days", "61-90 days", "90+ days"]


def _apply_inventory_filters(query, filters: dict = None):
    """Apply the global sidebar filters to an inventory-rooted query."""
    if not filters:
        return query
    if filters.get("region"):
        query = query.filter(Inventory.state == filters["region"])
    if filters.get("city"):
        query = query.filter(Inventory.city == filters["city"])
    if filters.get("brand"):
        query = query.filter(Inventory.brand == filters["brand"])
    if filters.get("vehicle_category"):
        query = query.filter(Inventory.vehicle_category == filters["vehicle_category"])
    if filters.get("fuel_type"):
        query = query.filter(Inventory.fuel_type == filters["fuel_type"])
    return query


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
            Inventory.state,
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
            Inventory.holding_cost_per_day_usd,
            Inventory.estimated_holding_cost_usd,
            Inventory.units_sold_last_30d,
            Inventory.units_ordered,
            Inventory.transit_stock,
            Inventory.supplier_lead_time_days,
            Inventory.port_of_entry,
            Inventory.warehouse_zone,
            Dealer.dealer_name,
            Dealer.tier.label("dealer_tier"),
            Dealer.latitude,
            Dealer.longitude,
            Vehicle.variant,
            Vehicle.price_usd,
            Vehicle.residual_value_36mo,
        )
        .outerjoin(Dealer, Inventory.dealer_id == Dealer.dealer_id)
        .outerjoin(Vehicle, Inventory.vehicle_id == Vehicle.vehicle_id)
        .filter(Inventory.record_date == latest_date)
    )
    query = _apply_inventory_filters(query, filters)

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
    df["inventory_value_usd"] = df["current_stock"] * df["price_usd"].fillna(0)
    return df


def get_inventory_trend(session: Session, filters: dict = None) -> pd.DataFrame:
    """Month-end network stock, transit and holding cost over the snapshot history."""
    query = session.query(
        Inventory.record_date,
        func.sum(Inventory.current_stock).label("units_in_stock"),
        func.sum(Inventory.transit_stock).label("units_in_transit"),
        func.sum(Inventory.estimated_holding_cost_usd).label("holding_cost_usd"),
        func.avg(Inventory.days_in_stock).label("avg_days_in_stock"),
        func.sum(Inventory.units_sold_last_30d).label("units_sold_30d"),
    )
    query = _apply_inventory_filters(query, filters)
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
            "capital_usd": float(sel["inventory_value_usd"].sum()),
            "holding_cost_usd": float(sel["estimated_holding_cost_usd"].sum()),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Lease returns — the forward supply book
# ─────────────────────────────────────────────────────────────────────────────

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
            Sale.state,
            Sale.city,
            Sale.lease_term_months,
            Sale.lease_maturity_date,
            Sale.residual_value_pct,
            Sale.residual_value_usd,
            Sale.contract_mileage_allowance,
            Sale.lease_monthly_payment_usd,
            Sale.selling_price_usd,
            Sale.base_price_usd,
            Dealer.dealer_name,
            Vehicle.variant,
            Vehicle.price_usd.label("current_msrp"),
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
            query = query.filter(Sale.state == filters["region"])
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
    est_market = df["current_msrp"].fillna(df["base_price_usd"]) * df["residual_value_36mo"].fillna(0.55)
    df["est_market_value_usd"] = est_market.round(0)
    df["equity_usd"] = (df["est_market_value_usd"] - df["residual_value_usd"]).round(0)
    df["in_the_money"] = df["equity_usd"] > 0
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
            Sale.state,
            Sale.lease_maturity_date,
            Sale.lease_monthly_payment_usd,
            Sale.residual_value_usd,
            Customer.name.label("customer_name"),
            Customer.customer_segment,
            Customer.loyalty_score,
            Customer.churn_risk_score,
            Customer.estimated_annual_income_usd,
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
            query = query.filter(Sale.state == filters["region"])
        if filters.get("brand"):
            query = query.filter(Sale.brand == filters["brand"])
        if filters.get("vehicle_category"):
            query = query.filter(Sale.vehicle_category == filters["vehicle_category"])
    return pd.read_sql(query.statement, session.bind)


# ─────────────────────────────────────────────────────────────────────────────
# Trade-in activity
# ─────────────────────────────────────────────────────────────────────────────

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
        Sale.state,
        Sale.city,
        Sale.dealer_id,
        Sale.financing_type,
        Sale.base_price_usd,
        Sale.selling_price_usd,
        Sale.discount_pct,
        Sale.lead_to_close_days,
        Sale.holiday_period,
        Sale.trade_in_flag,
        Sale.trade_in_brand,
        Sale.trade_in_model,
        Sale.trade_in_year,
        Sale.trade_in_mileage,
        Sale.trade_in_appraised_value_usd,
        Sale.trade_in_allowance_usd,
        Sale.trade_in_over_allowance_usd,
        Sale.trade_bonus_usd,
    )
    query = _apply_sale_filters(query, filters)
    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return df

    # True concession = sticker discount + over-allowance + trade bonus. Only
    # the first of these shows up in discount_pct, which is why reported
    # discount understates what the store actually gave away.
    df["sticker_discount_usd"] = (df["base_price_usd"] - df["selling_price_usd"]).clip(lower=0)
    df["over_allowance_usd"] = df["trade_in_over_allowance_usd"].fillna(0)
    df["trade_bonus_usd"] = df["trade_bonus_usd"].fillna(0)
    df["true_concession_usd"] = (
        df["sticker_discount_usd"] + df["over_allowance_usd"] + df["trade_bonus_usd"]
    )
    df["true_concession_pct"] = (
        df["true_concession_usd"] / df["base_price_usd"].replace(0, pd.NA) * 100
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
    query = _apply_sale_filters(query, filters)
    query = query.group_by(Sale.trade_in_brand, Sale.brand, Sale.vehicle_category)
    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return df
    return df.sort_values("deals", ascending=False)


# ─────────────────────────────────────────────────────────────────────────────
# Alternative vehicle placement
# ─────────────────────────────────────────────────────────────────────────────

def get_vehicle_catalog(session: Session) -> pd.DataFrame:
    """Full product catalog with the spec attributes the matcher scores on."""
    query = session.query(
        Vehicle.vehicle_id,
        Vehicle.brand,
        Vehicle.model,
        Vehicle.variant,
        Vehicle.category,
        Vehicle.fuel_type,
        Vehicle.price_usd,
        Vehicle.horsepower,
        Vehicle.mpg,
        Vehicle.range_miles,
        Vehicle.seating_capacity,
        Vehicle.drive_type,
        Vehicle.safety_rating,
        Vehicle.warranty_years,
        Vehicle.residual_value_36mo,
        Vehicle.ev_incentive_eligible,
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
        func.avg(Sale.selling_price_usd).label("avg_price"),
    )
    query = _apply_sale_filters(query, filters)
    query = query.group_by(Sale.vehicle_category, Sale.brand, Sale.model, Sale.fuel_type)
    return pd.read_sql(query.statement, session.bind)


def get_dealer_directory(session: Session) -> pd.DataFrame:
    """Dealer identity and coordinates, for locating stock at nearby stores."""
    query = session.query(
        Dealer.dealer_id,
        Dealer.dealer_name,
        Dealer.brand,
        Dealer.state,
        Dealer.city,
        Dealer.tier,
        Dealer.latitude,
        Dealer.longitude,
        Dealer.performance_score,
    )
    return pd.read_sql(query.statement, session.bind)
