from sqlalchemy import func, and_, or_, extract, desc, asc
from sqlalchemy.orm import Session
from database.models import Customer, Vehicle, Dealer, Sale, Inventory, ExternalFactor
from database.connection import get_db_session # This line is already present, no change needed
import pandas as pd
from datetime import datetime, date

# Dataset is a representative sample of the modeled 8-state NA market.
# Multiply sample unit counts by this factor to get implied national figures.
NATIONAL_SCALE_FACTOR = 17


def get_executive_kpis(session: Session, filters: dict = None) -> dict:
    """
    Get core KPIs for the executive overview dashboard.
    Supports global filters.
    """
    query = session.query(
        func.sum(Sale.units_sold).label("total_sales"),
        func.sum(Sale.total_revenue_incl_tax).label("total_revenue"),
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
            func.sum(Sale.total_revenue_incl_tax).label("total_revenue"),
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

    # Get worst performing state
    region_query = session.query(Sale.state, func.sum(Sale.units_sold).label("cnt"))
    region_query = _apply_sale_filters(region_query, filters)
    worst_region_res = region_query.group_by(Sale.state).order_by(asc("cnt")).first()
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
        func.sum(Sale.total_revenue_incl_tax).label("revenue"),
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
        func.sum(Sale.total_revenue_incl_tax).label("revenue")
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
        func.sum(Sale.total_revenue_incl_tax).label("revenue")
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
        Dealer.city,
        Dealer.state,
        Dealer.performance_score,
        Dealer.tier,
        Dealer.google_rating,
        Dealer.ev_charging_station,
        Dealer.service_center,
        Dealer.latitude,
        Dealer.longitude,
        func.sum(Sale.units_sold).label("units_sold"),
        func.sum(Sale.total_revenue_incl_tax).label("revenue")
    ).join(Sale, Sale.dealer_id == Dealer.dealer_id)

    query = _apply_sale_filters(query, filters)

    query = query.group_by(
        Dealer.dealer_id,
        Dealer.dealer_name,
        Dealer.city,
        Dealer.state,
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
        func.sum(Sale.total_revenue_incl_tax).label("revenue"),
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
        Customer.nationality,
        Customer.estimated_annual_income_usd,
        Customer.credit_score,
        Customer.number_of_past_purchases,
        Customer.loyalty_score,
        Customer.customer_segment,
        Customer.churn_risk_score
    )
    return pd.read_sql(query.statement, session.bind)


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
# Import Tariff Exposure — constants & queries
# Section 232 auto tariffs (25% on imported vehicles/parts, effective Apr 2025)
# hit import-heavy brands harder than Big 3 domestic-built brands.
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
        func.avg(Sale.selling_price_usd).label("avg_price"),
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
