from sqlalchemy import func, and_, or_, extract, desc, asc
from sqlalchemy.orm import Session
from database.models import (
    Customer, Vehicle, Dealer, Sale, Inventory, ExternalFactor,
    Registration, StateProfile, IndiaExternalFactor,
)
from database.connection import get_db_session
import pandas as pd
from datetime import datetime, date


def get_executive_kpis(session: Session, filters: dict = None) -> dict:
    """
    Get core KPIs for the executive overview dashboard.
    Supports global filters.
    """
    query = session.query(
        func.sum(Sale.units_sold).label("total_sales"),
        func.sum(Sale.total_revenue_incl_vat).label("total_revenue"),
        func.avg(Sale.discount_pct).label("avg_discount"),
        func.avg(Sale.lead_to_close_days).label("avg_lead_close")
    )

    # Initialize delta values
    total_sales_delta = None
    total_revenue_delta = None
    avg_discount_delta = None
    avg_lead_close_delta = None
    
    # Apply global filters
    current_period_query = _apply_sale_filters(query, filters)
    res = current_period_query.first()

    total_sales = (res.total_sales if res else 0) or 0
    total_revenue = (res.total_revenue if res else 0) or 0
    avg_discount = (res.avg_discount if res else 0.0) or 0.0
    avg_lead_close = (res.avg_lead_close if res else 0.0) or 0.0

    # Calculate YoY deltas if date filters are present
    if filters and filters.get("start_date") and filters.get("end_date"):
        current_start_date = filters["start_date"]
        current_end_date = filters["end_date"]

        # Calculate prior year dates
        prior_year_start_date = current_start_date.replace(year=current_start_date.year - 1)
        prior_year_end_date = current_end_date.replace(year=current_end_date.year - 1)

        prior_year_filters = filters.copy()
        prior_year_filters["start_date"] = prior_year_start_date
        prior_year_filters["end_date"] = prior_year_end_date

        prior_year_query = session.query(
            func.sum(Sale.units_sold).label("total_sales"),
            func.sum(Sale.total_revenue_incl_vat).label("total_revenue"),
            func.avg(Sale.discount_pct).label("avg_discount"),
            func.avg(Sale.lead_to_close_days).label("avg_lead_close")
        )
        prior_year_query = _apply_sale_filters(prior_year_query, prior_year_filters)
        prior_res = prior_year_query.first()

        prior_total_sales = (prior_res.total_sales if prior_res else 0) or 0
        prior_total_revenue = (prior_res.total_revenue if prior_res else 0) or 0
        prior_avg_discount = (prior_res.avg_discount if prior_res else 0.0) or 0.0
        prior_avg_lead_close = (prior_res.avg_lead_close if prior_res else 0.0) or 0.0

        # Calculate deltas
        if prior_total_sales > 0: total_sales_delta = ((total_sales - prior_total_sales) / prior_total_sales) * 100
        if prior_total_revenue > 0: total_revenue_delta = ((total_revenue - prior_total_revenue) / prior_total_revenue) * 100
        if prior_avg_discount > 0: avg_discount_delta = avg_discount - prior_avg_discount # Absolute change in percentage points
        if prior_avg_lead_close > 0: avg_lead_close_delta = prior_avg_lead_close - avg_lead_close # Faster is positive

    # Get top vehicle category
    cat_query = session.query(Sale.vehicle_category, func.sum(Sale.units_sold).label("cnt"))
    cat_query = _apply_sale_filters(cat_query, filters)
    top_cat_res = cat_query.group_by(Sale.vehicle_category).order_by(desc("cnt")).first()
    top_cat = top_cat_res[0] if top_cat_res else "N/A"

    # Get worst performing emirate
    region_query = session.query(Sale.emirate, func.sum(Sale.units_sold).label("cnt"))
    region_query = _apply_sale_filters(region_query, filters)
    worst_region_res = region_query.group_by(Sale.emirate).order_by(asc("cnt")).first()
    worst_region = worst_region_res[0] if worst_region_res else "N/A"

    # Get total customer count
    cust_count = session.query(func.count(Customer.customer_id)).scalar()

    # Get inventory stockout count and reorder count
    inv_stockout = session.query(func.count(Inventory.inventory_id)).filter(Inventory.stockout_flag == True).scalar()
    inv_reorder = session.query(func.count(Inventory.inventory_id)).filter(Inventory.reorder_needed == True).scalar()

    return {
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "avg_discount": avg_discount,
        "avg_lead_close": avg_lead_close,
        "total_sales_delta": total_sales_delta,
        "total_revenue_delta": total_revenue_delta,
        "avg_discount_delta": avg_discount_delta,
        "avg_lead_close_delta": avg_lead_close_delta,
        "top_vehicle_category": top_cat,
        "worst_region": worst_region,
        "total_customers": cust_count,
        "inventory_stockout": inv_stockout,
        "inventory_reorder": inv_reorder
    }


def get_monthly_revenue_trend(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Get monthly revenue trend for the revenue charts.
    """
    query = session.query(
        Sale.year,
        Sale.month,
        func.sum(Sale.total_revenue_incl_vat).label("revenue"),
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
        func.sum(Sale.total_revenue_incl_vat).label("revenue")
    )
    query = _apply_sale_filters(query, filters)
    query = query.group_by(Sale.vehicle_category).order_by(desc("sales"))

    return pd.read_sql(query.statement, session.bind)


def get_sales_by_fuel_type(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Get sales distribution by fuel type.
    """
    query = session.query(
        Sale.fuel_type,
        func.sum(Sale.units_sold).label("sales"),
        func.sum(Sale.total_revenue_incl_vat).label("revenue")
    )
    query = _apply_sale_filters(query, filters)
    query = query.group_by(Sale.fuel_type).order_by(desc("sales"))

    return pd.read_sql(query.statement, session.bind)


def get_sales_by_region(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Get sales distribution by emirate (was: region).
    """
    query = session.query(
        Sale.emirate,
        func.sum(Sale.units_sold).label("sales"),
        func.sum(Sale.total_revenue_incl_vat).label("revenue")
    )
    query = _apply_sale_filters(query, filters)
    query = query.group_by(Sale.emirate).order_by(desc("sales"))

    return pd.read_sql(query.statement, session.bind)


def get_dealer_performance_leaderboard(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Leaderboard of dealers based on units sold and total revenue.
    """
    query = session.query(
        Dealer.dealer_id,
        Dealer.dealer_name,
        Dealer.area,              # was: city
        Dealer.emirate,           # was: region
        Dealer.performance_score,
        Dealer.tier,
        Dealer.latitude,
        Dealer.longitude,
        func.sum(Sale.units_sold).label("units_sold"),
        func.sum(Sale.total_revenue_incl_vat).label("revenue")
    ).join(Sale, Sale.dealer_id == Dealer.dealer_id)

    query = _apply_sale_filters(query, filters)

    query = query.group_by(
        Dealer.dealer_id,
        Dealer.dealer_name,
        Dealer.area,
        Dealer.emirate,
        Dealer.performance_score,
        Dealer.tier,
        Dealer.latitude,
        Dealer.longitude
    ).order_by(desc("units_sold")).limit(20)

    return pd.read_sql(query.statement, session.bind)


def get_yoy_comparison(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Returns monthly comparisons across years for YoY analysis.
    """
    query = session.query(
        Sale.year,
        Sale.month,
        func.sum(Sale.total_revenue_incl_vat).label("revenue"),
        func.sum(Sale.units_sold).label("sales")
    )
    query = _apply_sale_filters(query, filters)
    query = query.group_by(Sale.year, Sale.month).order_by(Sale.month, Sale.year)

    df = pd.read_sql(query.statement, session.bind)
    return df


def get_customer_segments_data(session: Session) -> pd.DataFrame:
    """
    Query fields required for KMeans segmentation from customers table.
    """
    query = session.query(
        Customer.customer_id,
        Customer.age,
        Customer.gender,
        Customer.estimated_monthly_income_aed,    # was: estimated_annual_income
        Customer.credit_score,
        Customer.number_of_past_purchases,
        Customer.loyalty_score,
        Customer.customer_segment,
        Customer.churn_risk_score
    )
    return pd.read_sql(query.statement, session.bind)


def get_inventory_status(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Query inventory status to detect stock risk, overstock, holding costs, etc.
    """
    query = session.query(
        Inventory.inventory_id,
        Inventory.dealer_id,
        Inventory.area,                       # was: city
        Inventory.emirate,                    # was: region
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
        Inventory.holding_cost_per_day_aed,   # was: holding_cost_per_day
        Inventory.estimated_holding_cost_aed, # was: estimated_holding_cost
        Inventory.units_sold_last_30d,
        Inventory.units_ordered,
        Inventory.transit_stock,
        Inventory.warehouse_zone              # was: warehouse_location
    )

    if filters:
        if filters.get("region"):
            query = query.filter(Inventory.emirate == filters["region"])
        if filters.get("city"):
            query = query.filter(Inventory.area == filters["city"])
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


def get_unique_filter_options(session: Session) -> dict:
    """
    Gets lists of unique emirates, areas, categories, fuel types, brands and years
    to populate filters in the Streamlit sidebar.
    """
    regions = [r[0] for r in session.query(Sale.emirate).distinct().all() if r[0]]
    cities = [c[0] for c in session.query(Sale.area).distinct().all() if c[0]]
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

    # UAE schema keys
    if filters.get("region"):
        query = query.filter(Sale.emirate == filters["region"])
    if filters.get("city"):
        query = query.filter(Sale.area == filters["city"])

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


# ─────────────────────────────────────────────────────────────────────────────
# India / VAHAN Query Functions
# ─────────────────────────────────────────────────────────────────────────────

def get_india_filter_options(session: Session) -> dict:
    """Returns filter lists for India dashboard sidebar."""
    states = sorted([r[0] for r in session.query(Registration.state).distinct().all() if r[0]])
    makers = sorted([r[0] for r in session.query(Registration.maker).distinct().all() if r[0]])
    vehicle_classes = sorted([r[0] for r in session.query(Registration.vehicle_class).distinct().all() if r[0]])
    fuel_types = sorted([r[0] for r in session.query(Registration.fuel_type).distinct().all() if r[0]])
    years = sorted([r[0] for r in session.query(Registration.year).distinct().all() if r[0]])
    rtos = sorted([r[0] for r in session.query(Registration.rto_code).distinct().all() if r[0] and r[0] != ""])
    return {
        "regions": states,
        "cities": rtos,
        "categories": vehicle_classes,
        "fuel_types": fuel_types,
        "brands": makers,
        "years": years,
    }


def _apply_registration_filters(query, filters: dict = None):
    """Apply global filters to Registration table queries."""
    if not filters:
        return query
    if filters.get("state") or filters.get("emirate"):
        state_val = filters.get("state") or filters.get("emirate")
        query = query.filter(Registration.state == state_val)
    if filters.get("rto") or filters.get("area"):
        rto_val = filters.get("rto") or filters.get("area")
        query = query.filter(Registration.rto_code == rto_val)
    if filters.get("brand"):
        query = query.filter(Registration.maker == filters["brand"])
    if filters.get("vehicle_category"):
        query = query.filter(Registration.vehicle_class == filters["vehicle_category"])
    if filters.get("fuel_type"):
        query = query.filter(Registration.fuel_type == filters["fuel_type"])
    if filters.get("start_date"):
        query = query.filter(Registration.reg_date >= filters["start_date"])
    if filters.get("end_date"):
        query = query.filter(Registration.reg_date <= filters["end_date"])
    return query


def get_registration_kpis(session: Session, filters: dict = None) -> dict:
    """Core KPIs for India Executive Overview tab."""
    base = session.query(func.sum(Registration.registrations_count).label("total"))
    base = _apply_registration_filters(base, filters)
    total_reg = (base.scalar() or 0)

    ev_q = session.query(func.sum(Registration.registrations_count).label("ev_total"))
    ev_filters = (filters or {}).copy()
    ev_filters["fuel_type"] = "Electric"
    ev_q = _apply_registration_filters(ev_q, ev_filters)
    ev_total = (ev_q.scalar() or 0)
    ev_share = round((ev_total / total_reg * 100), 2) if total_reg > 0 else 0.0

    # YoY growth
    yoy_delta = None
    if filters and filters.get("start_date") and filters.get("end_date"):
        sd, ed = filters["start_date"], filters["end_date"]
        try:
            prior_filters = filters.copy()
            prior_filters["start_date"] = sd.replace(year=sd.year - 1)
            prior_filters["end_date"] = ed.replace(year=ed.year - 1)
            prior_q = session.query(func.sum(Registration.registrations_count))
            prior_q = _apply_registration_filters(prior_q, prior_filters)
            prior_total = prior_q.scalar() or 0
            if prior_total > 0:
                yoy_delta = round((total_reg - prior_total) / prior_total * 100, 2)
        except Exception:
            pass

    top_maker_res = (
        session.query(Registration.maker, func.sum(Registration.registrations_count).label("cnt"))
        .filter(Registration.maker != None, Registration.maker != "")
        .group_by(Registration.maker).order_by(desc("cnt")).first()
    )
    top_maker = top_maker_res[0] if top_maker_res else "N/A"

    worst_state_res = (
        session.query(Registration.state, func.sum(Registration.registrations_count).label("cnt"))
        .filter(Registration.state != None)
        .group_by(Registration.state).order_by(asc("cnt")).first()
    )
    worst_state = worst_state_res[0] if worst_state_res else "N/A"

    return {
        "total_registrations": total_reg,
        "ev_share_pct": ev_share,
        "yoy_growth_pct": yoy_delta,
        "top_maker": top_maker,
        "worst_state": worst_state,
        "total_ev_registrations": ev_total,
    }


def get_monthly_registration_trend(session: Session, filters: dict = None) -> pd.DataFrame:
    """Monthly registration counts for time-series chart."""
    query = session.query(
        Registration.year,
        Registration.month,
        func.sum(Registration.registrations_count).label("registrations"),
    )
    query = _apply_registration_filters(query, filters)
    query = query.group_by(Registration.year, Registration.month).order_by(
        Registration.year, Registration.month
    )
    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
    return df


def get_registrations_by_state(session: Session, filters: dict = None) -> pd.DataFrame:
    """Registrations aggregated per state for choropleth map."""
    query = session.query(
        Registration.state,
        func.sum(Registration.registrations_count).label("registrations"),
    )
    query = _apply_registration_filters(query, filters)
    query = query.filter(Registration.state != None).group_by(Registration.state).order_by(desc("registrations"))
    return pd.read_sql(query.statement, session.bind)


def get_registrations_by_maker(session: Session, filters: dict = None) -> pd.DataFrame:
    """Registrations aggregated per maker/brand."""
    query = session.query(
        Registration.maker,
        func.sum(Registration.registrations_count).label("registrations"),
    )
    query = _apply_registration_filters(query, filters)
    query = (
        query.filter(Registration.maker != None, Registration.maker != "")
        .group_by(Registration.maker).order_by(desc("registrations"))
    )
    return pd.read_sql(query.statement, session.bind)


def get_registrations_by_fuel(session: Session, filters: dict = None) -> pd.DataFrame:
    """Registrations aggregated per fuel type."""
    query = session.query(
        Registration.fuel_type,
        func.sum(Registration.registrations_count).label("registrations"),
    )
    query = _apply_registration_filters(query, filters)
    query = (
        query.filter(Registration.fuel_type != None, Registration.fuel_type != "")
        .group_by(Registration.fuel_type).order_by(desc("registrations"))
    )
    return pd.read_sql(query.statement, session.bind)


def get_registrations_by_vehicle_class(session: Session, filters: dict = None) -> pd.DataFrame:
    """Registrations aggregated per vehicle class/category."""
    query = session.query(
        Registration.vehicle_class,
        func.sum(Registration.registrations_count).label("registrations"),
    )
    query = _apply_registration_filters(query, filters)
    query = (
        query.filter(Registration.vehicle_class != None, Registration.vehicle_class != "")
        .group_by(Registration.vehicle_class).order_by(desc("registrations"))
    )
    return pd.read_sql(query.statement, session.bind)


def get_ev_adoption_trend(session: Session, filters: dict = None) -> pd.DataFrame:
    """Monthly EV vs total registrations for EV share trend chart."""
    total_q = session.query(
        Registration.year,
        Registration.month,
        func.sum(Registration.registrations_count).label("total"),
    )
    total_q = _apply_registration_filters(total_q, filters)
    total_q = total_q.group_by(Registration.year, Registration.month)
    df_total = pd.read_sql(total_q.statement, session.bind)

    ev_filters = (filters or {}).copy()
    ev_filters["fuel_type"] = "Electric"
    ev_q = session.query(
        Registration.year,
        Registration.month,
        func.sum(Registration.registrations_count).label("ev_count"),
    )
    ev_q = _apply_registration_filters(ev_q, ev_filters)
    ev_q = ev_q.group_by(Registration.year, Registration.month)
    df_ev = pd.read_sql(ev_q.statement, session.bind)

    if df_total.empty:
        return pd.DataFrame()
    df = df_total.merge(df_ev, on=["year", "month"], how="left").fillna(0)
    df["ev_share_pct"] = (df["ev_count"] / df["total"].replace(0, 1) * 100).round(2)
    df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
    return df


def get_yoy_registration_comparison(session: Session, filters: dict = None) -> pd.DataFrame:
    """Monthly YoY comparison for Comparative Analytics tab."""
    query = session.query(
        Registration.year,
        Registration.month,
        func.sum(Registration.registrations_count).label("registrations"),
    )
    query = _apply_registration_filters(query, filters)
    query = query.group_by(Registration.year, Registration.month).order_by(
        Registration.month, Registration.year
    )
    return pd.read_sql(query.statement, session.bind)


def get_state_growth_data(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    Per-state summary for market segmentation:
    total_registrations, ev_share_pct, yoy_growth_pct, dominant_fuel, top_maker.
    """
    query = session.query(
        Registration.state,
        Registration.fuel_type,
        Registration.maker,
        Registration.year,
        func.sum(Registration.registrations_count).label("cnt"),
    )
    query = _apply_registration_filters(query, filters)
    query = query.filter(Registration.state != None).group_by(
        Registration.state, Registration.fuel_type, Registration.maker, Registration.year
    )
    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return pd.DataFrame()

    state_total = df.groupby("state")["cnt"].sum().rename("total_registrations")
    ev_df = df[df["fuel_type"] == "Electric"].groupby("state")["cnt"].sum().rename("ev_count")
    dominant_fuel = df.groupby(["state", "fuel_type"])["cnt"].sum().reset_index()
    dominant_fuel = dominant_fuel.loc[dominant_fuel.groupby("state")["cnt"].idxmax()][["state", "fuel_type"]].rename(columns={"fuel_type": "dominant_fuel"})
    top_maker = df.groupby(["state", "maker"])["cnt"].sum().reset_index()
    top_maker = top_maker.loc[top_maker.groupby("state")["cnt"].idxmax()][["state", "maker"]].rename(columns={"maker": "top_maker"})

    result = state_total.reset_index()
    result = result.merge(ev_df.reset_index(), on="state", how="left").fillna(0)
    result["ev_share_pct"] = (result["ev_count"] / result["total_registrations"].replace(0, 1) * 100).round(2)
    result = result.merge(dominant_fuel, on="state", how="left")
    result = result.merge(top_maker, on="state", how="left")
    return result

    return query
