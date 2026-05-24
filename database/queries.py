from sqlalchemy import func, and_, or_, extract, desc, asc
from sqlalchemy.orm import Session
from database.models import Customer, Vehicle, Dealer, Sale, Inventory, ExternalFactor
from database.connection import get_db_session # This line is already present, no change needed
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

    return query
