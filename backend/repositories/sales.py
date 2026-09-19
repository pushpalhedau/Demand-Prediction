"""Sales analytics queries: KPIs, trends and breakdowns over the tenant's booked deals."""
import pandas as pd
from datetime import date
from sqlalchemy import case, desc, func
from sqlalchemy.orm import Session

from backend.db.models import Customer, Dealer, Inventory, Sale
from backend.repositories._filters import apply_dealer_scope, apply_sale_filters, shift_years


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
    q = apply_sale_filters(q, filters)
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
            "start_date": shift_years(filters["start_date"], 1),
            "end_date": shift_years(filters["end_date"], 1),
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
    cat_query = apply_sale_filters(
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
    start = shift_years(end, 1)

    def _units(s, e):
        q = session.query(func.coalesce(func.sum(Sale.units_sold), 0))
        q = apply_sale_filters(q, {
            k: v for k, v in filters.items() if k not in ("start_date", "end_date")
        })
        return q.filter(Sale.sale_date > s, Sale.sale_date <= e).scalar() or 0

    ttm_units = _units(start, end)
    prior_ttm_units = _units(shift_years(start, 1), shift_years(end, 1))

    annual_target = apply_dealer_scope(
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
    query = apply_sale_filters(query, filters)
    query = query.group_by(Sale.brand, Sale.model).order_by(desc("units")).limit(limit)
    return pd.read_sql(query.statement, session.bind)


def get_sales_by_store(session: Session, filters: dict = None, limit: int = 20) -> pd.DataFrame:
    """Units and revenue booked per rooftop in the window, best first."""
    query = session.query(
        Dealer.dealer_name,
        Dealer.city,
        Dealer.region,
        Dealer.brand,
        func.sum(Sale.units_sold).label("units"),
        func.sum(Sale.total_revenue_incl_tax).label("revenue"),
    ).join(Sale, Sale.dealer_id == Dealer.dealer_id)
    query = apply_sale_filters(query, filters)
    query = query.group_by(
        Dealer.dealer_name, Dealer.city, Dealer.region, Dealer.brand
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
    query = apply_sale_filters(query, filters)
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
    query = apply_sale_filters(query, filters)
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
    query = apply_sale_filters(query, filters)
    query = query.group_by(Sale.fuel_type).order_by(desc("sales"))

    df = pd.read_sql(query.statement, session.bind)
    return df


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
        q = apply_sale_filters(q, f)
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
            "start_date": shift_years(filters["start_date"], 1),
            "end_date": shift_years(filters["end_date"], 1),
        })
        if not prior.empty:
            prior["date"] = prior["date"] + pd.DateOffset(years=1)
    prior["period"] = "Prior year"

    return pd.concat([cur[cols], prior[cols]], ignore_index=True)


def get_scope_monthly_trend(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Monthly booked units and revenue over ALL history for the scope filters
    (brand / region / segment / fuel) — the sidebar date window is ignored so
    the calendar-year comparison and its forecast have the full history to work
    from. Columns [date, units, revenue], one row per month, ascending.
    """
    f = {k: v for k, v in (filters or {}).items()
         if k not in ("start_date", "end_date")}
    q = session.query(
        Sale.year, Sale.month,
        func.sum(Sale.units_sold).label("units"),
        func.sum(Sale.total_revenue_incl_tax).label("revenue"),
    )
    q = apply_sale_filters(q, f)
    q = q.group_by(Sale.year, Sale.month).order_by(Sale.year, Sale.month)
    d = pd.read_sql(q.statement, session.bind)
    if d.empty:
        return d
    d["date"] = pd.to_datetime(d[["year", "month"]].assign(day=1))
    return d[["date", "units", "revenue"]]


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
        q = apply_sale_filters(q, f)
        q = q.group_by(dim_col)
        return pd.read_sql(q.statement, session.bind)

    cur = _agg(filters).rename(columns={"units": "curr_units", "revenue": "curr_revenue"})

    if filters.get("start_date") and filters.get("end_date"):
        prev = _agg({
            **filters,
            "start_date": shift_years(filters["start_date"], 1),
            "end_date": shift_years(filters["end_date"], 1),
        }).rename(columns={"units": "prev_units", "revenue": "prev_revenue"})
    else:
        prev = pd.DataFrame(columns=["name", "prev_units", "prev_revenue"])

    m = cur.merge(prev, on="name", how="outer")
    for c in ["curr_units", "prev_units", "curr_revenue", "prev_revenue"]:
        m[c] = m[c].fillna(0)
    m["delta_units"] = m["curr_units"] - m["prev_units"]
    m["delta_revenue"] = m["curr_revenue"] - m["prev_revenue"]
    return m
