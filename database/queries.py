from sqlalchemy import func, and_, or_, extract, desc, asc
from sqlalchemy.orm import Session
from database.models import Customer, Vehicle, Dealer, Sale, Inventory, ExternalFactor
from database.connection import get_db_session # This line is already present, no change needed
import pandas as pd
from datetime import datetime, date

# Dataset is a 1/17 (~5.9%) sample of the UAE national market.
# Multiply sample unit counts by this factor to get implied national figures.
NATIONAL_SCALE_FACTOR = 17


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
        "total_sales": total_sales * NATIONAL_SCALE_FACTOR,
        "total_revenue": total_revenue * NATIONAL_SCALE_FACTOR,
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
        df['sales'] = df['sales'] * NATIONAL_SCALE_FACTOR
        df['revenue'] = df['revenue'] * NATIONAL_SCALE_FACTOR
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

    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df['sales'] = df['sales'] * NATIONAL_SCALE_FACTOR
        df['revenue'] = df['revenue'] * NATIONAL_SCALE_FACTOR
    return df


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

    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df['sales'] = df['sales'] * NATIONAL_SCALE_FACTOR
        df['revenue'] = df['revenue'] * NATIONAL_SCALE_FACTOR
    return df


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

    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df['sales'] = df['sales'] * NATIONAL_SCALE_FACTOR
        df['revenue'] = df['revenue'] * NATIONAL_SCALE_FACTOR
    return df


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
        Dealer.google_rating,
        Dealer.ev_charging_station,
        Dealer.service_center,
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
        Dealer.google_rating,
        Dealer.ev_charging_station,
        Dealer.service_center,
        Dealer.latitude,
        Dealer.longitude
    ).order_by(desc("units_sold")).limit(20)

    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df['units_sold'] = df['units_sold'] * NATIONAL_SCALE_FACTOR
        df['revenue']    = df['revenue']    * NATIONAL_SCALE_FACTOR

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
    if not df.empty:
        df['sales'] = df['sales'] * NATIONAL_SCALE_FACTOR
        df['revenue'] = df['revenue'] * NATIONAL_SCALE_FACTOR
    return df


def get_customer_segments_data(session: Session) -> pd.DataFrame:
    """
    Query fields required for KMeans segmentation from customers table.
    """
    query = session.query(
        Customer.customer_id,
        Customer.age,
        Customer.gender,
        Customer.nationality,                      # REAL — FCSC 2023 census
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


def get_uae_base_rate_kpi(session: Session, filters: dict = None) -> dict:
    """
    Returns the UAE base rate (CBUAE OPR) for the selected period and YoY delta.
    Uses the period-end rate (last month within the date range).
    Stored as ExternalFactor.us_fed_rate_pct (renamed during seeding).
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


# ─────────────────────────────────────────────────────────────────────────────
# Chinese Brand Market Impact — constants & queries
# ─────────────────────────────────────────────────────────────────────────────

CHINESE_BRANDS = ['MG', 'BYD', 'Jetour', 'Geely']

BRAND_ORIGIN = {
    'Toyota': 'Japanese',      'Nissan': 'Japanese',       'Mitsubishi': 'Japanese',
    'Honda': 'Japanese',       'Lexus': 'Japanese',
    'Hyundai': 'Korean',       'Kia': 'Korean',
    'BMW': 'European',         'Mercedes-Benz': 'European', 'Volkswagen': 'European',
    'Land Rover': 'European',  'Polestar': 'European',
    'Ford': 'American',        'Chevrolet': 'American',    'Jeep': 'American',
    'Tesla': 'American',
    'MG': 'Chinese',           'BYD': 'Chinese',           'Jetour': 'Chinese',
    'Geely': 'Chinese',
}


def _filters_no_brand(filters: dict) -> dict:
    """Return a copy of filters with brand cleared so Chinese brand queries see all brands."""
    if not filters:
        return {}
    return {**filters, 'brand': None}


def get_chinese_brand_yearly_share(session: Session, filters: dict = None) -> pd.DataFrame:
    """Year-by-year units per brand with origin tag. Brand filter is always ignored."""
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
    df['units'] = df['units'] * NATIONAL_SCALE_FACTOR
    df['origin'] = df['brand'].map(BRAND_ORIGIN).fillna('Other')
    return df


def get_price_competitiveness(session: Session, filters: dict = None) -> pd.DataFrame:
    """Weighted avg selling price and total units per brand+category. Brand filter ignored."""
    query = session.query(
        Sale.brand,
        Sale.vehicle_category,
        func.avg(Sale.selling_price_aed).label("avg_price"),
        func.sum(Sale.units_sold).label("units")
    )
    query = _apply_sale_filters(query, _filters_no_brand(filters))
    query = query.group_by(Sale.brand, Sale.vehicle_category)
    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return df
    df['units'] = df['units'] * NATIONAL_SCALE_FACTOR
    df['origin'] = df['brand'].map(BRAND_ORIGIN).fillna('Other')
    grand_total = df['units'].sum()
    df['market_share_pct'] = (df['units'] / grand_total * 100).round(2) if grand_total else 0.0
    return df


def get_ev_segment_by_brand_year(session: Session, filters: dict = None) -> pd.DataFrame:
    """Electric vehicle units by brand and year. Brand and fuel_type filters ignored."""
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
    df['ev_units'] = df['ev_units'] * NATIONAL_SCALE_FACTOR
    df['origin'] = df['brand'].map(BRAND_ORIGIN).fillna('Other')
    return df


def get_market_share_shift(session: Session, filters: dict = None) -> pd.DataFrame:
    """Brand market share in the base year vs latest year within the filter date range."""
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
