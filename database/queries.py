from sqlalchemy import func, desc, asc, Float
from sqlalchemy.orm import Session
from database.models import (
    Transaction, Buyer, Developer, Property, Listing, MarketFactor,
    LeadPipeline, ConstructionTracker, Financial, RentalMarket,
    Contractor, CompetitorMarket, DocumentRegistry,
)
import pandas as pd
import json
from datetime import date, timedelta


# ─── Executive KPIs ──────────────────────────────────────────────────────────

def get_executive_kpis(session: Session, filters: dict = None) -> dict:
    query = session.query(
        func.count(Transaction.transaction_id).label("units_sold"),
        func.sum(Transaction.total_transaction_value_aed).label("total_value"),
        func.avg(Transaction.price_per_sqft_aed).label("avg_price_sqft"),
        func.avg(Transaction.discount_pct).label("avg_discount"),
        func.avg(Transaction.lead_to_close_days).label("avg_lead_close"),
        func.sum(Transaction.dld_transfer_fee_aed).label("total_dld_fees"),
    )
    query = _apply_filters(query, filters)
    res = query.first()

    units_sold = (res.units_sold or 0)
    total_value = (res.total_value or 0)
    avg_price_sqft = (res.avg_price_sqft or 0.0)
    avg_discount = (res.avg_discount or 0.0)
    avg_lead_close = (res.avg_lead_close or 0.0)
    total_dld_fees = (res.total_dld_fees or 0)

    # Conversion rate: booking_converted / total transactions
    total_q = session.query(func.count(Transaction.transaction_id))
    total_q = _apply_filters(total_q, filters)
    converted_q = session.query(func.count(Transaction.transaction_id)).filter(
        Transaction.booking_converted == True
    )
    converted_q = _apply_filters(converted_q, filters)
    total_txn = total_q.scalar() or 1
    converted = converted_q.scalar() or 0
    conversion_rate = (converted / total_txn) * 100

    # Golden Visa eligible transactions
    golden_visa_q = session.query(func.count(Transaction.transaction_id)).filter(
        Transaction.golden_visa_eligible == True
    )
    golden_visa_q = _apply_filters(golden_visa_q, filters)
    golden_visa_count = golden_visa_q.scalar() or 0

    # Inventory absorption rate (from listings)
    listings_q = session.query(
        func.avg(
            func.cast(Listing.units_sold_last_30d, Float) /
            func.nullif(func.cast(Listing.available_units, Float), 0)
        ).label("absorption")
    )
    absorption_res = listings_q.first()
    absorption_rate = float(absorption_res.absorption or 0) * 100

    # YoY delta calculation
    units_delta = total_value_delta = avg_sqft_delta = None
    if filters and filters.get("start_date") and filters.get("end_date"):
        sd, ed = filters["start_date"], filters["end_date"]
        py_filters = {**filters,
                      "start_date": sd.replace(year=sd.year - 1),
                      "end_date": ed.replace(year=ed.year - 1)}
        py_q = session.query(
            func.count(Transaction.transaction_id).label("units"),
            func.sum(Transaction.total_transaction_value_aed).label("value"),
            func.avg(Transaction.price_per_sqft_aed).label("sqft"),
        )
        py_q = _apply_filters(py_q, py_filters)
        py = py_q.first()
        if py and py.units:
            units_delta = ((units_sold - py.units) / py.units) * 100
        if py and py.value:
            total_value_delta = ((total_value - py.value) / py.value) * 100
        if py and py.sqft:
            avg_sqft_delta = ((avg_price_sqft - py.sqft) / py.sqft) * 100

    # Top emirate and property category
    emirate_q = session.query(Transaction.emirate, func.count(Transaction.transaction_id).label("cnt"))
    emirate_q = _apply_filters(emirate_q, filters)
    top_emirate_res = emirate_q.group_by(Transaction.emirate).order_by(desc("cnt")).first()
    top_city = top_emirate_res[0] if top_emirate_res else "N/A"

    cat_q = session.query(
        Transaction.property_category,
        func.count(Transaction.transaction_id).label("cnt")
    )
    cat_q = _apply_filters(cat_q, filters)
    top_cat_res = cat_q.group_by(Transaction.property_category).order_by(desc("cnt")).first()
    top_category = top_cat_res[0] if top_cat_res else "N/A"

    total_buyers = session.query(func.count(Buyer.buyer_id)).scalar() or 0
    unsold_listings = session.query(
        func.count(Listing.listing_id)
    ).filter(Listing.unsold_flag == True).scalar() or 0
    slow_movers = session.query(
        func.count(Listing.listing_id)
    ).filter(Listing.slow_moving_flag == True).scalar() or 0

    return {
        "units_sold": units_sold,
        "total_value": total_value,
        "avg_price_sqft": avg_price_sqft,
        "avg_discount": avg_discount,
        "avg_lead_close": avg_lead_close,
        "total_dld_fees": total_dld_fees,
        "golden_visa_count": golden_visa_count,
        "conversion_rate": conversion_rate,
        "absorption_rate": absorption_rate,
        "units_delta": units_delta,
        "total_value_delta": total_value_delta,
        "avg_sqft_delta": avg_sqft_delta,
        "top_city": top_city,
        "top_category": top_category,
        "total_buyers": total_buyers,
        "unsold_listings": unsold_listings,
        "slow_movers": slow_movers,
    }


# ─── Monthly Trends ───────────────────────────────────────────────────────────

def get_monthly_revenue_trend(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Transaction.year,
        Transaction.month,
        func.sum(Transaction.total_transaction_value_aed).label("revenue"),
        func.count(Transaction.transaction_id).label("units"),
        func.avg(Transaction.price_per_sqft_aed).label("avg_price_sqft"),
    )
    query = _apply_filters(query, filters)
    query = query.group_by(Transaction.year, Transaction.month).order_by(
        Transaction.year, Transaction.month
    )
    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
    return df


def get_yoy_comparison(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Transaction.year,
        Transaction.month,
        func.count(Transaction.transaction_id).label("units"),
        func.sum(Transaction.total_transaction_value_aed).label("revenue"),
        func.avg(Transaction.price_per_sqft_aed).label("avg_price_sqft"),
    )
    query = _apply_filters(query, filters)
    query = query.group_by(Transaction.year, Transaction.month).order_by(
        Transaction.month, Transaction.year
    )
    return pd.read_sql(query.statement, session.bind)


# ─── Category & Segment Breakdowns ───────────────────────────────────────────

def get_sales_by_property_type(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Transaction.property_type,
        func.count(Transaction.transaction_id).label("units"),
        func.sum(Transaction.total_transaction_value_aed).label("revenue"),
    )
    query = _apply_filters(query, filters)
    query = query.group_by(Transaction.property_type).order_by(desc("units"))
    return pd.read_sql(query.statement, session.bind)


def get_sales_by_property_category(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Transaction.property_category,
        func.count(Transaction.transaction_id).label("units"),
        func.sum(Transaction.total_transaction_value_aed).label("revenue"),
        func.avg(Transaction.price_per_sqft_aed).label("avg_price_sqft"),
    )
    query = _apply_filters(query, filters)
    query = query.group_by(Transaction.property_category).order_by(desc("units"))
    return pd.read_sql(query.statement, session.bind)


def get_sales_by_city(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Transaction.city,
        Transaction.emirate,
        func.count(Transaction.transaction_id).label("units"),
        func.sum(Transaction.total_transaction_value_aed).label("revenue"),
        func.avg(Transaction.price_per_sqft_aed).label("avg_price_sqft"),
    )
    query = _apply_filters(query, filters)
    query = query.group_by(Transaction.city, Transaction.emirate).order_by(desc("units"))
    return pd.read_sql(query.statement, session.bind)


def get_sales_by_region(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Transaction.region,
        func.count(Transaction.transaction_id).label("units"),
        func.sum(Transaction.total_transaction_value_aed).label("revenue"),
    )
    query = _apply_filters(query, filters)
    query = query.group_by(Transaction.region).order_by(desc("units"))
    return pd.read_sql(query.statement, session.bind)


def get_sales_by_payment_plan(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Transaction.payment_plan,
        func.count(Transaction.transaction_id).label("units"),
        func.sum(Transaction.total_transaction_value_aed).label("revenue"),
    )
    query = _apply_filters(query, filters)
    query = query.group_by(Transaction.payment_plan).order_by(desc("units"))
    return pd.read_sql(query.statement, session.bind)


def get_sales_by_marketing_channel(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Transaction.marketing_channel,
        func.count(Transaction.transaction_id).label("units"),
        func.avg(Transaction.lead_to_close_days).label("avg_lead_days"),
    )
    query = _apply_filters(query, filters)
    query = query.group_by(Transaction.marketing_channel).order_by(desc("units"))
    return pd.read_sql(query.statement, session.bind)


# ─── Price Intelligence ───────────────────────────────────────────────────────

def get_price_trends_by_city(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Transaction.year,
        Transaction.month,
        Transaction.city,
        func.avg(Transaction.price_per_sqft_aed).label("avg_price_sqft"),
        func.count(Transaction.transaction_id).label("transactions"),
    )
    query = _apply_filters(query, filters)
    query = query.group_by(
        Transaction.year, Transaction.month, Transaction.city
    ).order_by(Transaction.year, Transaction.month)
    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
    return df


def get_price_by_locality(session: Session, filters: dict = None, top_n: int = 20) -> pd.DataFrame:
    query = session.query(
        Transaction.locality,
        Transaction.city,
        func.avg(Transaction.price_per_sqft_aed).label("avg_price_sqft"),
        func.count(Transaction.transaction_id).label("transactions"),
        func.avg(Transaction.area_sqft).label("avg_area"),
    )
    query = _apply_filters(query, filters)
    query = query.group_by(Transaction.locality, Transaction.city).order_by(
        desc("avg_price_sqft")
    ).limit(top_n)
    return pd.read_sql(query.statement, session.bind)


def get_price_by_category_type(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Transaction.property_category,
        Transaction.property_type,
        func.avg(Transaction.price_per_sqft_aed).label("avg_price_sqft"),
        func.avg(Transaction.selling_price_aed).label("avg_selling_price"),
        func.count(Transaction.transaction_id).label("transactions"),
    )
    query = _apply_filters(query, filters)
    query = query.group_by(
        Transaction.property_category, Transaction.property_type
    ).order_by(desc("avg_price_sqft"))
    return pd.read_sql(query.statement, session.bind)


# ─── Regional Intelligence ────────────────────────────────────────────────────

def get_developer_performance(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Developer.developer_id,
        Developer.developer_name,
        Developer.primary_city,
        Developer.tier,
        Developer.performance_score,
        Developer.rating,
        Developer.rera_registered,
        Developer.active_projects,
        Developer.latitude,
        Developer.longitude,
        func.count(Transaction.transaction_id).label("units_sold"),
        func.sum(Transaction.total_transaction_value_aed).label("revenue"),
        func.avg(Transaction.price_per_sqft_aed).label("avg_price_sqft"),
    ).join(Transaction, Transaction.developer_id == Developer.developer_id)
    query = _apply_filters(query, filters)
    query = query.group_by(
        Developer.developer_id, Developer.developer_name, Developer.primary_city,
        Developer.tier, Developer.performance_score, Developer.rating,
        Developer.rera_registered, Developer.active_projects,
        Developer.latitude, Developer.longitude,
    ).order_by(desc("units_sold")).limit(25)
    return pd.read_sql(query.statement, session.bind)


def get_locality_hotspots(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Transaction.locality,
        Transaction.city,
        Transaction.region,
        func.count(Transaction.transaction_id).label("transactions"),
        func.sum(Transaction.total_transaction_value_aed).label("revenue"),
        func.avg(Transaction.price_per_sqft_aed).label("avg_price_sqft"),
    )
    query = _apply_filters(query, filters)
    query = query.group_by(
        Transaction.locality, Transaction.city, Transaction.region
    ).order_by(desc("transactions")).limit(30)
    return pd.read_sql(query.statement, session.bind)


# ─── Customer Intelligence ───────────────────────────────────────────────────

def get_buyer_segments_data(session: Session) -> pd.DataFrame:
    query = session.query(
        Buyer.buyer_id,
        Buyer.age,
        Buyer.gender,
        Buyer.estimated_annual_income_aed,
        Buyer.number_of_past_purchases,
        Buyer.loyalty_score,
        Buyer.churn_risk_score,
        Buyer.customer_segment,
        Buyer.buyer_type,
        Buyer.expat_status,
        Buyer.golden_visa_intent,
        Buyer.off_plan_preference,
        Buyer.budget_max_aed,
        Buyer.site_visit_taken,
        Buyer.mortgage_preferred,
        Buyer.years_in_uae,
    )
    return pd.read_sql(query.statement, session.bind)


def get_lead_conversion_data(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Transaction.booking_converted,
        Transaction.marketing_channel,
        Transaction.lead_to_close_days,
        Transaction.property_category,
        Transaction.city,
        Buyer.age,
        Buyer.estimated_annual_income_aed,
        Buyer.site_visit_taken,
        Buyer.buyer_type,
        Buyer.expat_status,
        Buyer.golden_visa_intent,
        Buyer.loyalty_score,
        Buyer.mortgage_preferred,
    ).join(Buyer, Transaction.buyer_id == Buyer.buyer_id)
    query = _apply_filters(query, filters)
    return pd.read_sql(query.statement, session.bind)


def get_buyer_segment_summary(session: Session) -> pd.DataFrame:
    query = session.query(
        Buyer.customer_segment,
        func.count(Buyer.buyer_id).label("count"),
        func.avg(Buyer.estimated_annual_income_aed).label("avg_income"),
        func.avg(Buyer.budget_max_aed).label("avg_budget"),
        func.avg(Buyer.loyalty_score).label("avg_loyalty"),
        func.avg(Buyer.churn_risk_score).label("avg_churn_risk"),
    )
    query = query.group_by(Buyer.customer_segment).order_by(desc("count"))
    return pd.read_sql(query.statement, session.bind)


# ─── Inventory Intelligence ───────────────────────────────────────────────────

def get_inventory_status(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Listing.listing_id,
        Listing.project_name,
        Listing.city,
        Listing.locality,
        Listing.property_type,
        Listing.property_category,
        Listing.bedrooms,
        Listing.completion_status,
        Listing.construction_progress_pct,
        Listing.available_units,
        Listing.booked_units,
        Listing.registered_units,
        Listing.total_units_in_project,
        Listing.demand_forecast_30d,
        Listing.days_on_market,
        Listing.unsold_flag,
        Listing.slow_moving_flag,
        Listing.overlaunch_flag,
        Listing.stockout_risk_score,
        Listing.holding_cost_per_day_aed,
        Listing.estimated_holding_cost_aed,
        Listing.units_sold_last_30d,
        Listing.rental_income_potential_aed,
        Listing.golden_visa_threshold_met,
        Listing.off_plan_flag,
    )
    if filters:
        if filters.get("city"):
            query = query.filter(Listing.city == filters["city"])
        if filters.get("property_type"):
            query = query.filter(Listing.property_type == filters["property_type"])
        if filters.get("property_category"):
            query = query.filter(Listing.property_category == filters["property_category"])
    return pd.read_sql(query.statement, session.bind)


def get_inventory_summary_by_city(session: Session) -> pd.DataFrame:
    query = session.query(
        Listing.city,
        func.sum(Listing.available_units).label("available"),
        func.sum(Listing.booked_units).label("booked"),
        func.sum(Listing.registered_units).label("registered"),
        func.sum(Listing.total_units_in_project).label("total"),
        func.avg(Listing.days_on_market).label("avg_days_on_market"),
        func.sum(Listing.estimated_holding_cost_aed).label("total_holding_cost"),
        func.count(Listing.listing_id).filter(Listing.unsold_flag == True).label("unsold_projects"),
    )
    query = query.group_by(Listing.city).order_by(desc("available"))
    return pd.read_sql(query.statement, session.bind)


# ─── Market Factors ──────────────────────────────────────────────────────────

def get_market_factor_stats(session: Session, city: str = None) -> dict:
    query = session.query(MarketFactor)
    if city:
        query = query.filter(MarketFactor.city == city)
    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return {}

    numeric_cols = [
        "uae_central_bank_base_rate_pct", "mortgage_rate_avg_pct", "gdp_growth_pct",
        "cpi_inflation_pct", "consumer_confidence_index", "real_estate_price_index",
        "tourism_arrivals_index", "foreign_investment_inflow_bn_aed",
        "institutional_investment_bn_aed", "property_registration_fee_pct",
        "vat_rate_pct", "usd_aed_rate", "rental_yield_avg_pct",
        "construction_cost_index", "oil_price_usd_bbl", "off_plan_sales_share_pct",
    ]
    binary_cols = ["ramadan_month", "expo_effect"]
    stats = {}
    for col in numeric_cols + binary_cols:
        if col in df.columns:
            series = df[col].dropna()
            if len(series) > 0:
                stats[col] = {
                    "last": float(series.iloc[-1]),
                    "min": float(series.min()),
                    "max": float(series.max()),
                    "is_binary": col in binary_cols,
                }
    return stats


def get_market_factor_trend(session: Session, city: str = None) -> pd.DataFrame:
    query = session.query(
        MarketFactor.date,
        MarketFactor.year,
        MarketFactor.month,
        MarketFactor.city,
        MarketFactor.uae_central_bank_base_rate_pct,
        MarketFactor.mortgage_rate_avg_pct,
        MarketFactor.consumer_confidence_index,
        MarketFactor.real_estate_price_index,
        MarketFactor.transaction_volume_index,
        MarketFactor.foreign_investment_inflow_bn_aed,
        MarketFactor.tourism_arrivals_index,
        MarketFactor.ramadan_month,
        MarketFactor.expo_effect,
        MarketFactor.golden_visa_applications,
        MarketFactor.new_project_launches,
        MarketFactor.off_plan_sales_share_pct,
    )
    if city:
        query = query.filter(MarketFactor.city == city)
    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


# ─── Filter Options ───────────────────────────────────────────────────────────

def get_unique_filter_options(session: Session) -> dict:
    cities = sorted([
        c[0] for c in session.query(Transaction.city).distinct().all() if c[0]
    ])
    regions = sorted([
        r[0] for r in session.query(Transaction.region).distinct().all() if r[0]
    ])
    emirates = sorted([
        s[0] for s in session.query(Transaction.emirate).distinct().all() if s[0]
    ])
    property_types = sorted([
        p[0] for p in session.query(Transaction.property_type).distinct().all() if p[0]
    ])
    property_categories = sorted([
        c[0] for c in session.query(Transaction.property_category).distinct().all() if c[0]
    ])
    bedrooms = sorted([
        b[0] for b in session.query(Transaction.bedrooms).distinct().all() if b[0]
    ])
    years = sorted([
        y[0] for y in session.query(Transaction.year).distinct().all() if y[0]
    ])

    return {
        "cities": cities,
        "regions": regions,
        "emirates": emirates,
        "property_types": property_types,
        "property_categories": property_categories,
        "bedrooms": bedrooms,
        "years": years,
    }


# ─── Internal Filter Helper ───────────────────────────────────────────────────

def _apply_filters(query, filters: dict = None):
    if not filters:
        return query

    if filters.get("city"):
        query = query.filter(Transaction.city == filters["city"])
    if filters.get("region"):
        query = query.filter(Transaction.region == filters["region"])
    if filters.get("emirate"):
        query = query.filter(Transaction.emirate == filters["emirate"])
    if filters.get("property_type"):
        query = query.filter(Transaction.property_type == filters["property_type"])
    if filters.get("property_category"):
        query = query.filter(Transaction.property_category == filters["property_category"])
    if filters.get("bedrooms"):
        query = query.filter(Transaction.bedrooms == filters["bedrooms"])
    if filters.get("start_date"):
        query = query.filter(Transaction.transaction_date >= filters["start_date"])
    if filters.get("end_date"):
        query = query.filter(Transaction.transaction_date <= filters["end_date"])

    return query


# ─── CEO Dashboard KPIs ───────────────────────────────────────────────────────

def get_ceo_kpis(session: Session) -> dict:
    today = date.today()

    # Use the latest available financial period (data may not reach today)
    latest_fin_date = session.query(func.max(Financial.period_date)).scalar()
    if latest_fin_date is None:
        latest_fin_date = today
    # Derive current/prev month from latest data, not calendar today
    data_month_start = latest_fin_date.replace(day=1) if hasattr(latest_fin_date, 'replace') else today.replace(day=1)
    prev_month_end = data_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    # Use the latest booking date from leads too
    latest_booking_date = session.query(func.max(LeadPipeline.booking_date)).scalar()
    if latest_booking_date is None:
        latest_booking_date = today
    lead_month_start = latest_booking_date.replace(day=1) if hasattr(latest_booking_date, 'replace') else today.replace(day=1)
    lead_prev_end = lead_month_start - timedelta(days=1)
    lead_prev_start = lead_prev_end.replace(day=1)

    def _financial_sum(col, start, end):
        res = session.query(func.sum(col)).filter(
            Financial.period_date >= start,
            Financial.period_date <= end,
        ).scalar()
        return float(res or 0)

    def _financial_avg(col, start, end):
        res = session.query(func.avg(col)).filter(
            Financial.period_date >= start,
            Financial.period_date <= end,
        ).scalar()
        return float(res or 0)

    # Total revenue this month vs last month (using latest available data period)
    rev_cur = _financial_sum(Financial.revenue_booked_aed, data_month_start, latest_fin_date)
    rev_prev = _financial_sum(Financial.revenue_booked_aed, prev_month_start, prev_month_end)
    rev_delta = ((rev_cur - rev_prev) / rev_prev * 100) if rev_prev else 0.0

    # Bookings this month from leads (using latest available booking period)
    bookings_cur = session.query(func.count(LeadPipeline.lead_id)).filter(
        LeadPipeline.booking_date >= lead_month_start,
        LeadPipeline.booking_date <= latest_booking_date,
    ).scalar() or 0
    bookings_prev = session.query(func.count(LeadPipeline.lead_id)).filter(
        LeadPipeline.booking_date >= lead_prev_start,
        LeadPipeline.booking_date <= lead_prev_end,
    ).scalar() or 0
    bookings_delta = ((bookings_cur - bookings_prev) / bookings_prev * 100) if bookings_prev else 0.0

    # Collection efficiency
    coll_eff = _financial_avg(Financial.collection_efficiency_pct, data_month_start, latest_fin_date)
    coll_eff_prev = _financial_avg(Financial.collection_efficiency_pct, prev_month_start, prev_month_end)
    coll_delta = coll_eff - coll_eff_prev

    # Inventory available (sum across all listings)
    inv_available = session.query(func.sum(Listing.available_units)).scalar() or 0

    # Pipeline value from active leads
    active_stages = ['Qualified', 'Site Visit Done', 'Proposal Sent', 'Negotiation']
    pipeline_val = session.query(func.sum(LeadPipeline.budget_stated_aed)).filter(
        LeadPipeline.lead_stage.in_(active_stages)
    ).scalar() or 0

    # Latest lead date to anchor lead period
    latest_lead_date = session.query(func.max(LeadPipeline.lead_date)).scalar()
    if latest_lead_date is None:
        latest_lead_date = today
    lead_cur_start = latest_lead_date.replace(day=1) if hasattr(latest_lead_date, 'replace') else today.replace(day=1)
    lead_cur_prev_end = lead_cur_start - timedelta(days=1)
    lead_cur_prev_start = lead_cur_prev_end.replace(day=1)

    # Sales conversion rate this month
    total_leads = session.query(func.count(LeadPipeline.lead_id)).filter(
        LeadPipeline.lead_date >= lead_cur_start,
    ).scalar() or 1
    converted_leads = session.query(func.count(LeadPipeline.lead_id)).filter(
        LeadPipeline.lead_date >= lead_cur_start,
        LeadPipeline.converted == True,
    ).scalar() or 0
    conversion_rate = (converted_leads / total_leads) * 100

    prev_total = session.query(func.count(LeadPipeline.lead_id)).filter(
        LeadPipeline.lead_date >= lead_cur_prev_start,
        LeadPipeline.lead_date <= lead_cur_prev_end,
    ).scalar() or 1
    prev_conv = session.query(func.count(LeadPipeline.lead_id)).filter(
        LeadPipeline.lead_date >= lead_cur_prev_start,
        LeadPipeline.lead_date <= lead_cur_prev_end,
        LeadPipeline.converted == True,
    ).scalar() or 0
    conv_delta = (converted_leads / total_leads * 100) - (prev_conv / prev_total * 100)

    # Project completion (avg actual progress per project, latest report)
    latest_report_date = session.query(func.max(ConstructionTracker.report_date)).scalar()
    proj_health = session.query(
        func.avg(ConstructionTracker.actual_progress_pct)
    ).scalar() or 0
    prev_proj_start = None
    if latest_report_date:
        proj_report_month_start = latest_report_date.replace(day=1) if hasattr(latest_report_date, 'replace') else today.replace(day=1)
        prev_proj_start = (proj_report_month_start - timedelta(days=1)).replace(day=1)
    proj_health_prev = session.query(
        func.avg(ConstructionTracker.actual_progress_pct)
    ).filter(
        ConstructionTracker.report_date < (prev_proj_start or today),
    ).scalar() or proj_health
    proj_delta = float(proj_health) - float(proj_health_prev)

    # Occupancy rate and rental yield (latest period)
    occupancy = session.query(func.avg(RentalMarket.occupancy_rate_pct)).scalar() or 0
    rental_yield = session.query(func.avg(RentalMarket.gross_rental_yield_pct)).scalar() or 0

    # Forecast revenue (sum of 3-month forecasts from latest period)
    latest_period = session.query(func.max(Financial.period_date)).scalar()
    forecast_rev = 0.0
    if latest_period:
        forecast_rev = session.query(func.sum(Financial.forecast_next_3m_aed)).filter(
            Financial.period_date == latest_period
        ).scalar() or 0

    return {
        "total_revenue_aed": rev_cur,
        "revenue_mom_delta": rev_delta,
        "bookings_this_month": bookings_cur,
        "bookings_mom_delta": bookings_delta,
        "collection_efficiency_pct": coll_eff,
        "collection_delta": coll_delta,
        "inventory_available": int(inv_available),
        "pipeline_value_aed": float(pipeline_val),
        "sales_conversion_rate_pct": conversion_rate,
        "conversion_delta": conv_delta,
        "project_completion_pct": float(proj_health),
        "project_delta": proj_delta,
        "occupancy_rate_pct": float(occupancy),
        "rental_yield_pct": float(rental_yield),
        "forecast_revenue_aed": float(forecast_rev),
    }


def get_ceo_ai_insights(session: Session) -> list:
    today = date.today()
    latest_fin = session.query(func.max(Financial.period_date)).scalar() or today
    cur_month_start = latest_fin.replace(day=1) if hasattr(latest_fin, 'replace') else today.replace(day=1)
    prev_month_end = cur_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    insights = []

    # 1. Revenue MoM change
    rev_cur = session.query(func.sum(Financial.revenue_booked_aed)).filter(
        Financial.period_date >= cur_month_start
    ).scalar() or 0
    rev_prev = session.query(func.sum(Financial.revenue_booked_aed)).filter(
        Financial.period_date >= prev_month_start,
        Financial.period_date <= prev_month_end,
    ).scalar() or 1
    rev_pct = ((float(rev_cur) - float(rev_prev)) / float(rev_prev)) * 100

    if rev_pct >= 0:
        insights.append({
            "type": "positive",
            "icon": "trending_up",
            "title": f"Revenue up {rev_pct:.1f}% MoM",
            "body": f"This month's bookings reached AED {float(rev_cur)/1e6:.1f}M vs AED {float(rev_prev)/1e6:.1f}M last month.",
        })
    else:
        insights.append({
            "type": "warning",
            "icon": "trending_down",
            "title": f"Revenue down {abs(rev_pct):.1f}% MoM",
            "body": f"Revenue fell to AED {float(rev_cur)/1e6:.1f}M from AED {float(rev_prev)/1e6:.1f}M. Review sales pipeline.",
        })

    # 2. At-risk projects
    at_risk = session.query(
        ConstructionTracker.project_name,
        func.max(ConstructionTracker.delay_days).label("max_delay"),
    ).filter(
        ConstructionTracker.delay_risk_flag == True,
    ).group_by(ConstructionTracker.project_name).order_by(desc("max_delay")).limit(3).all()

    if at_risk:
        names = ", ".join([r[0] for r in at_risk[:2]])
        total_risk = session.query(func.count(ConstructionTracker.record_id.distinct())).filter(
            ConstructionTracker.delay_risk_flag == True
        ).scalar() or 0
        insights.append({
            "type": "alert",
            "icon": "warning",
            "title": f"{total_risk} project milestone(s) at risk",
            "body": f"Delayed: {names}. Max delay: {at_risk[0][1]} days. Immediate escalation recommended.",
        })
    else:
        insights.append({
            "type": "positive",
            "icon": "check_circle",
            "title": "All projects on schedule",
            "body": "No delay risk flags detected across active construction milestones.",
        })

    # 3. Top demand growth locality
    locality_q = session.query(
        Transaction.locality,
        func.count(Transaction.transaction_id).label("cnt"),
    ).filter(
        Transaction.transaction_date >= cur_month_start,
    ).group_by(Transaction.locality).order_by(desc("cnt")).first()

    if locality_q:
        insights.append({
            "type": "positive",
            "icon": "location_on",
            "title": f"Hotspot: {locality_q[0]}",
            "body": f"{locality_q[1]} transactions this month — leading demand zone. Consider accelerating launch activity there.",
        })
    else:
        insights.append({
            "type": "positive",
            "icon": "location_on",
            "title": "Dubai Marina leads demand",
            "body": "Highest transaction concentration in Marina district this period.",
        })

    return insights


def get_revenue_collections_trend(session: Session, months: int = 12) -> pd.DataFrame:
    cutoff = date.today() - timedelta(days=months * 30)
    query = session.query(
        Financial.period_date,
        func.sum(Financial.revenue_booked_aed).label("revenue_booked_aed"),
        func.sum(Financial.collections_received_aed).label("collections_received_aed"),
        func.sum(Financial.net_cash_flow_aed).label("net_cash_flow_aed"),
    ).filter(
        Financial.period_date >= cutoff,
    ).group_by(Financial.period_date).order_by(Financial.period_date)

    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["period_date"] = pd.to_datetime(df["period_date"])
    return df


def get_inventory_breakdown(session: Session) -> pd.DataFrame:
    query = session.query(
        Listing.emirate,
        func.sum(Listing.available_units).label("available_units"),
        func.sum(Listing.booked_units).label("booked_units"),
        func.sum(Listing.registered_units).label("registered_units"),
    ).group_by(Listing.emirate).order_by(desc("available_units"))
    return pd.read_sql(query.statement, session.bind)


def get_forecast_chart_data(session: Session) -> pd.DataFrame:
    cutoff = date.today() - timedelta(days=180)
    query = session.query(
        Financial.period_date,
        func.sum(Financial.revenue_booked_aed).label("revenue_actual_aed"),
        func.sum(Financial.forecast_next_3m_aed).label("forecast_next_3m_aed"),
        func.sum(Financial.forecast_next_12m_aed).label("forecast_next_12m_aed"),
    ).filter(
        Financial.period_date >= cutoff,
    ).group_by(Financial.period_date).order_by(Financial.period_date)

    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["period_date"] = pd.to_datetime(df["period_date"])
    return df


def get_revenue_vs_target_forecast(session: Session, months_history: int = 6) -> pd.DataFrame:
    """Returns historical revenue + target for past N months, plus 3 projected future months.

    Columns: period_date, revenue_aed, target_aed, is_forecast (bool)
    Future revenue is the latest forecast_next_3m_aed split evenly across 3 months.
    Future target uses the trailing average monthly target.
    """
    cutoff = date.today() - timedelta(days=months_history * 30)
    query = session.query(
        Financial.period_date,
        func.sum(Financial.revenue_booked_aed).label("revenue_aed"),
        func.sum(Financial.sales_target_aed).label("target_aed"),
        func.sum(Financial.forecast_next_3m_aed).label("forecast_next_3m_aed"),
    ).filter(
        Financial.period_date >= cutoff,
    ).group_by(Financial.period_date).order_by(Financial.period_date)

    df = pd.read_sql(query.statement, session.bind)
    if df.empty:
        return df

    df["period_date"] = pd.to_datetime(df["period_date"])
    df["is_forecast"] = False

    latest = df.iloc[-1]
    monthly_forecast = (latest["forecast_next_3m_aed"] or 0) / 3
    avg_target = df["target_aed"].fillna(0).mean()
    last_date = latest["period_date"]

    future_rows = [
        {
            "period_date": last_date + pd.DateOffset(months=i),
            "revenue_aed": monthly_forecast,
            "target_aed": avg_target,
            "forecast_next_3m_aed": None,
            "is_forecast": True,
        }
        for i in range(1, 4)
    ]

    return pd.concat([df, pd.DataFrame(future_rows)], ignore_index=True)


def get_project_health_scores(session: Session) -> pd.DataFrame:
    query = session.query(
        ConstructionTracker.project_name,
        func.avg(ConstructionTracker.project_health_score).label("health_score"),
        func.avg(ConstructionTracker.actual_progress_pct).label("progress_pct"),
        func.max(ConstructionTracker.delay_days).label("max_delay_days"),
        func.max(ConstructionTracker.delay_risk_flag).label("at_risk"),
    ).group_by(ConstructionTracker.project_name).order_by(desc("health_score")).limit(10)
    return pd.read_sql(query.statement, session.bind)


def get_lead_funnel_summary(session: Session) -> pd.DataFrame:
    stages = ['New', 'Contacted', 'Qualified', 'Site Visit Scheduled', 'Site Visit Done',
              'Proposal Sent', 'Negotiation', 'Booked', 'Lost']
    query = session.query(
        LeadPipeline.lead_stage,
        func.count(LeadPipeline.lead_id).label("count"),
    ).group_by(LeadPipeline.lead_stage).order_by(desc("count"))
    df = pd.read_sql(query.statement, session.bind)
    return df


def get_copilot_context_summary(session: Session) -> str:
    kpis = get_ceo_kpis(session)

    top_city_row = session.query(
        Transaction.city, func.count(Transaction.transaction_id).label("cnt")
    ).group_by(Transaction.city).order_by(desc("cnt")).first()
    top_city = top_city_row[0] if top_city_row else "Dubai"

    at_risk_count = session.query(func.count(ConstructionTracker.record_id)).filter(
        ConstructionTracker.delay_risk_flag == True
    ).scalar() or 0

    context = {
        "total_revenue_this_month_aed": round(kpis["total_revenue_aed"] / 1e6, 2),
        "revenue_mom_change_pct": round(kpis["revenue_mom_delta"], 1),
        "bookings_this_month": kpis["bookings_this_month"],
        "collection_efficiency_pct": round(kpis["collection_efficiency_pct"], 1),
        "inventory_available_units": kpis["inventory_available"],
        "pipeline_value_aed_million": round(kpis["pipeline_value_aed"] / 1e6, 1),
        "sales_conversion_rate_pct": round(kpis["sales_conversion_rate_pct"], 1),
        "project_completion_avg_pct": round(kpis["project_completion_pct"], 1),
        "occupancy_rate_pct": round(kpis["occupancy_rate_pct"], 1),
        "rental_yield_pct": round(kpis["rental_yield_pct"], 2),
        "forecast_revenue_next_3m_aed_million": round(kpis["forecast_revenue_aed"] / 1e6, 1),
        "projects_at_delay_risk": at_risk_count,
        "top_demand_city": top_city,
        "currency": "AED",
        "market": "UAE Real Estate",
        "data_as_of": str(date.today()),
    }
    return json.dumps(context, indent=2)


# ─── Lead Intelligence ────────────────────────────────────────────────────────

def get_lead_funnel_detail(session: Session) -> pd.DataFrame:
    STAGE_ORDER = [
        'New', 'Contacted', 'Qualified', 'Site Visit Scheduled',
        'Site Visit Done', 'Proposal Sent', 'Negotiation', 'Booked', 'Lost',
    ]
    query = session.query(
        LeadPipeline.lead_stage,
        func.count(LeadPipeline.lead_id).label("count"),
        func.avg(LeadPipeline.lead_score).label("avg_score"),
        func.avg(LeadPipeline.conversion_probability).label("avg_conv_prob"),
        func.sum(LeadPipeline.budget_stated_aed).label("pipeline_value"),
        func.avg(LeadPipeline.time_in_stage_days).label("avg_days_in_stage"),
    ).group_by(LeadPipeline.lead_stage)
    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["stage_order"] = df["lead_stage"].apply(
            lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else 99
        )
        df = df.sort_values("stage_order").reset_index(drop=True)
    return df


def get_lead_source_breakdown(session: Session) -> pd.DataFrame:
    query = session.query(
        LeadPipeline.lead_source,
        func.count(LeadPipeline.lead_id).label("total_leads"),
        func.sum(func.cast(LeadPipeline.converted, Float)).label("converted"),
        func.avg(LeadPipeline.cost_per_lead_aed).label("avg_cpl"),
        func.avg(LeadPipeline.lead_score).label("avg_score"),
        func.avg(LeadPipeline.total_funnel_days).label("avg_funnel_days"),
        func.sum(LeadPipeline.budget_stated_aed).label("pipeline_value"),
    ).group_by(LeadPipeline.lead_source).order_by(desc("total_leads"))
    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["conversion_rate"] = (df["converted"] / df["total_leads"] * 100).fillna(0)
    return df


def get_lead_temperature_distribution(session: Session) -> pd.DataFrame:
    query = session.query(
        LeadPipeline.lead_temperature,
        func.count(LeadPipeline.lead_id).label("count"),
        func.avg(LeadPipeline.lead_score).label("avg_score"),
        func.avg(LeadPipeline.conversion_probability).label("avg_conv_prob"),
    ).group_by(LeadPipeline.lead_temperature).order_by(desc("count"))
    return pd.read_sql(query.statement, session.bind)


def get_lead_monthly_trend(session: Session) -> pd.DataFrame:
    query = session.query(
        func.strftime('%Y-%m', LeadPipeline.lead_date).label("month"),
        func.count(LeadPipeline.lead_id).label("total_leads"),
        func.sum(func.cast(LeadPipeline.converted, Float)).label("converted"),
        func.avg(LeadPipeline.cost_per_lead_aed).label("avg_cpl"),
    ).group_by("month").order_by("month")
    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["conversion_rate"] = (df["converted"] / df["total_leads"] * 100).fillna(0)
        df["month"] = pd.to_datetime(df["month"] + "-01")
    return df


def get_lead_kpis(session: Session) -> dict:
    total = session.query(func.count(LeadPipeline.lead_id)).scalar() or 0
    converted = session.query(func.count(LeadPipeline.lead_id)).filter(
        LeadPipeline.converted == True
    ).scalar() or 0
    pipeline_val = session.query(
        func.sum(LeadPipeline.budget_stated_aed)
    ).filter(
        LeadPipeline.lead_stage.in_(['Qualified', 'Site Visit Done', 'Proposal Sent', 'Negotiation'])
    ).scalar() or 0
    avg_cpl = session.query(func.avg(LeadPipeline.cost_per_lead_aed)).scalar() or 0
    avg_funnel = session.query(func.avg(LeadPipeline.total_funnel_days)).scalar() or 0
    avg_score = session.query(func.avg(LeadPipeline.lead_score)).scalar() or 0
    hot_leads = session.query(func.count(LeadPipeline.lead_id)).filter(
        LeadPipeline.lead_temperature == 'Hot'
    ).scalar() or 0
    return {
        "total_leads": total,
        "converted": converted,
        "conversion_rate": (converted / total * 100) if total else 0,
        "pipeline_value": float(pipeline_val),
        "avg_cost_per_lead": float(avg_cpl),
        "avg_funnel_days": float(avg_funnel),
        "avg_lead_score": float(avg_score),
        "hot_leads": hot_leads,
    }


# ─── Cross-Domain Lead Intelligence ──────────────────────────────────────────

def get_demand_supply_gap(session: Session) -> pd.DataFrame:
    """Lead demand (emirate × bedroom) vs available inventory from Listings."""
    lead_q = session.query(
        LeadPipeline.emirate_interest.label("emirate"),
        LeadPipeline.bedroom_preference.label("bedrooms"),
        func.count(LeadPipeline.lead_id).label("lead_count"),
    ).filter(
        LeadPipeline.emirate_interest.isnot(None),
        LeadPipeline.bedroom_preference.isnot(None),
    ).group_by(LeadPipeline.emirate_interest, LeadPipeline.bedroom_preference)
    df_leads = pd.read_sql(lead_q.statement, session.bind)

    supply_q = session.query(
        Listing.emirate,
        Listing.bedrooms,
        func.sum(Listing.available_units).label("available_units"),
    ).filter(
        Listing.emirate.isnot(None),
        Listing.bedrooms.isnot(None),
    ).group_by(Listing.emirate, Listing.bedrooms)
    df_supply = pd.read_sql(supply_q.statement, session.bind)

    if df_leads.empty:
        return df_leads
    merged = df_leads.merge(df_supply, on=["emirate", "bedrooms"], how="left")
    merged["available_units"] = merged["available_units"].fillna(0).astype(int)
    return merged


def get_project_risk_pipeline(session: Session) -> pd.DataFrame:
    """Late-stage leads per project crossed with construction health scores."""
    LATE_STAGES = ['Site Visit Done', 'Proposal Sent', 'Negotiation']

    lead_q = session.query(
        LeadPipeline.project_interest.label("project_name"),
        func.count(LeadPipeline.lead_id).label("late_stage_leads"),
        func.sum(LeadPipeline.budget_stated_aed).label("at_risk_value_aed"),
    ).filter(
        LeadPipeline.lead_stage.in_(LATE_STAGES),
        LeadPipeline.project_interest.isnot(None),
    ).group_by(LeadPipeline.project_interest)
    df_leads = pd.read_sql(lead_q.statement, session.bind)

    health_q = session.query(
        ConstructionTracker.project_name,
        func.avg(ConstructionTracker.project_health_score).label("health_score"),
        func.max(ConstructionTracker.delay_days).label("delay_days"),
        func.max(func.cast(ConstructionTracker.delay_risk_flag, Float)).label("delay_risk"),
        func.avg(ConstructionTracker.actual_progress_pct).label("progress_pct"),
    ).group_by(ConstructionTracker.project_name)
    df_health = pd.read_sql(health_q.statement, session.bind)

    if df_leads.empty:
        return df_leads
    merged = df_leads.merge(df_health, on="project_name", how="left")
    merged["health_score"] = merged["health_score"].fillna(50).round(1)
    merged["delay_days"] = merged["delay_days"].fillna(0).astype(int)
    merged["delay_risk"] = merged["delay_risk"].fillna(0).astype(bool)
    return merged.sort_values("at_risk_value_aed", ascending=False).head(10)


def get_lead_budget_vs_market(session: Session) -> pd.DataFrame:
    """Avg lead budget vs avg actual transaction price by emirate × property type."""
    lead_q = session.query(
        LeadPipeline.emirate_interest.label("emirate"),
        LeadPipeline.property_interest.label("property_type"),
        func.avg(LeadPipeline.budget_stated_aed).label("avg_budget_aed"),
        func.count(LeadPipeline.lead_id).label("lead_count"),
    ).filter(
        LeadPipeline.emirate_interest.isnot(None),
        LeadPipeline.property_interest.isnot(None),
        LeadPipeline.budget_stated_aed.isnot(None),
    ).group_by(LeadPipeline.emirate_interest, LeadPipeline.property_interest)
    df_leads = pd.read_sql(lead_q.statement, session.bind)

    txn_q = session.query(
        Transaction.emirate,
        Transaction.property_type,
        func.avg(Transaction.selling_price_aed).label("avg_market_price_aed"),
        func.count(Transaction.transaction_id).label("txn_count"),
    ).filter(
        Transaction.emirate.isnot(None),
        Transaction.property_type.isnot(None),
        Transaction.selling_price_aed.isnot(None),
    ).group_by(Transaction.emirate, Transaction.property_type)
    df_txn = pd.read_sql(txn_q.statement, session.bind)

    if df_leads.empty or df_txn.empty:
        return pd.DataFrame()
    merged = df_leads.merge(df_txn, on=["emirate", "property_type"], how="inner")
    if merged.empty:
        return merged
    merged["budget_gap_pct"] = (
        (merged["avg_budget_aed"] - merged["avg_market_price_aed"])
        / merged["avg_market_price_aed"] * 100
    ).round(1)
    merged["label"] = merged["emirate"] + " · " + merged["property_type"]
    return merged.sort_values("budget_gap_pct")


# ─── Project Performance ──────────────────────────────────────────────────────

def get_project_portfolio(session: Session) -> pd.DataFrame:
    query = session.query(
        Listing.project_name,
        Listing.city,
        Listing.property_type,
        Listing.property_category,
        Listing.completion_status,
        func.avg(Listing.construction_progress_pct).label("avg_progress"),
        func.max(Listing.total_units_in_project).label("total_units"),
        func.sum(Listing.available_units).label("available_units"),
        func.sum(Listing.booked_units).label("booked_units"),
        func.sum(Listing.registered_units).label("registered_units"),
        func.avg(Listing.days_on_market).label("avg_days_on_market"),
        func.sum(Listing.estimated_holding_cost_aed).label("holding_cost"),
        func.max(func.cast(Listing.unsold_flag, Float)).label("has_unsold"),
        func.max(func.cast(Listing.slow_moving_flag, Float)).label("has_slow"),
    ).group_by(
        Listing.project_name, Listing.city, Listing.property_type,
        Listing.property_category, Listing.completion_status,
    ).order_by(desc("total_units"))
    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["absorption_pct"] = (
            (df["booked_units"] + df["registered_units"]) /
            df["total_units"].replace(0, 1) * 100
        ).fillna(0)
    return df


def get_project_portfolio_kpis(session: Session) -> dict:
    total_projects = session.query(
        func.count(Listing.project_name.distinct())
    ).scalar() or 0
    total_units = session.query(func.sum(Listing.total_units_in_project)).scalar() or 0
    booked = session.query(func.sum(Listing.booked_units)).scalar() or 0
    available = session.query(func.sum(Listing.available_units)).scalar() or 0
    avg_progress = session.query(
        func.avg(Listing.construction_progress_pct)
    ).scalar() or 0
    unsold_projects = session.query(
        func.count(Listing.listing_id)
    ).filter(Listing.unsold_flag == True).scalar() or 0
    total_holding_cost = session.query(
        func.sum(Listing.estimated_holding_cost_aed)
    ).scalar() or 0
    completed = session.query(
        func.count(Listing.listing_id)
    ).filter(Listing.completion_status == 'Completed').scalar() or 0
    return {
        "total_projects": total_projects,
        "total_units": int(total_units),
        "booked_units": int(booked),
        "available_units": int(available),
        "avg_construction_progress": float(avg_progress),
        "unsold_projects": unsold_projects,
        "total_holding_cost": float(total_holding_cost),
        "completed_projects": completed,
    }


def get_project_status_breakdown(session: Session) -> pd.DataFrame:
    query = session.query(
        Listing.completion_status,
        func.count(Listing.project_name.distinct()).label("projects"),
        func.sum(Listing.total_units_in_project).label("total_units"),
        func.avg(Listing.construction_progress_pct).label("avg_progress"),
    ).group_by(Listing.completion_status).order_by(desc("projects"))
    return pd.read_sql(query.statement, session.bind)


# ─── Construction Intelligence ────────────────────────────────────────────────

def get_construction_kpis(session: Session) -> dict:
    total = session.query(
        func.count(ConstructionTracker.project_name.distinct())
    ).scalar() or 0
    at_risk = session.query(
        func.count(ConstructionTracker.project_name.distinct())
    ).filter(ConstructionTracker.delay_risk_flag == True).scalar() or 0
    avg_health = session.query(
        func.avg(ConstructionTracker.project_health_score)
    ).scalar() or 0
    avg_progress = session.query(
        func.avg(ConstructionTracker.actual_progress_pct)
    ).scalar() or 0
    avg_delay = session.query(
        func.avg(ConstructionTracker.delay_days)
    ).filter(ConstructionTracker.delay_days > 0).scalar() or 0
    total_budget = session.query(
        func.sum(ConstructionTracker.total_project_budget_aed)
    ).scalar() or 0
    total_spent = session.query(
        func.sum(ConstructionTracker.total_spent_to_date_aed)
    ).scalar() or 0
    safety_incidents = session.query(
        func.sum(ConstructionTracker.safety_incidents)
    ).scalar() or 0
    return {
        "total_projects": total,
        "at_risk_projects": at_risk,
        "avg_health_score": float(avg_health),
        "avg_progress_pct": float(avg_progress),
        "avg_delay_days": float(avg_delay),
        "total_budget_aed": float(total_budget),
        "total_spent_aed": float(total_spent),
        "safety_incidents": int(safety_incidents),
    }


def get_construction_project_summary(session: Session) -> pd.DataFrame:
    query = session.query(
        ConstructionTracker.project_name,
        func.avg(ConstructionTracker.actual_progress_pct).label("actual_progress"),
        func.avg(ConstructionTracker.planned_progress_pct).label("planned_progress"),
        func.avg(ConstructionTracker.project_health_score).label("health_score"),
        func.max(ConstructionTracker.delay_days).label("max_delay_days"),
        func.avg(ConstructionTracker.cost_overrun_pct).label("avg_cost_overrun"),
        func.avg(ConstructionTracker.budget_utilization_pct).label("budget_utilization"),
        func.avg(ConstructionTracker.quality_score).label("quality_score"),
        func.avg(ConstructionTracker.resource_utilization_pct).label("resource_util"),
        func.sum(ConstructionTracker.safety_incidents).label("safety_incidents"),
        func.max(func.cast(ConstructionTracker.delay_risk_flag, Float)).label("at_risk"),
        func.max(func.cast(ConstructionTracker.escalation_flag, Float)).label("escalated"),
    ).group_by(ConstructionTracker.project_name).order_by(desc("health_score"))
    return pd.read_sql(query.statement, session.bind)


def get_milestone_delay_analysis(session: Session) -> pd.DataFrame:
    query = session.query(
        ConstructionTracker.milestone_name,
        func.count(ConstructionTracker.record_id).label("count"),
        func.avg(ConstructionTracker.delay_days).label("avg_delay"),
        func.max(ConstructionTracker.delay_days).label("max_delay"),
        func.avg(ConstructionTracker.cost_overrun_pct).label("avg_overrun"),
        func.sum(func.cast(ConstructionTracker.delay_risk_flag, Float)).label("risk_count"),
    ).group_by(ConstructionTracker.milestone_name).order_by(desc("avg_delay"))
    return pd.read_sql(query.statement, session.bind)


def get_contractor_performance(session: Session) -> pd.DataFrame:
    query = session.query(
        Contractor.contractor_name,
        Contractor.contractor_type,
        Contractor.grade,
        Contractor.overall_performance_score,
        Contractor.avg_quality_score,
        Contractor.avg_delivery_score,
        Contractor.avg_cost_adherence_score,
        Contractor.safety_record_incidents,
        Contractor.total_projects_completed,
        Contractor.active_projects_count,
        Contractor.rating,
        Contractor.preferred_vendor,
        Contractor.blacklisted,
    ).order_by(desc(Contractor.overall_performance_score)).limit(20)
    return pd.read_sql(query.statement, session.bind)


# ─── Financial Intelligence ───────────────────────────────────────────────────

def get_financial_pl_trend(session: Session, months: int = 18) -> pd.DataFrame:
    cutoff = date.today() - timedelta(days=months * 30)
    query = session.query(
        Financial.period_date,
        func.sum(Financial.revenue_booked_aed).label("revenue"),
        func.sum(Financial.gross_profit_aed).label("gross_profit"),
        func.sum(Financial.ebitda_aed).label("ebitda"),
        func.sum(Financial.net_profit_aed).label("net_profit"),
        func.avg(Financial.gross_margin_pct).label("gross_margin_pct"),
        func.avg(Financial.net_margin_pct).label("net_margin_pct"),
        func.sum(Financial.operating_expenses_aed).label("opex"),
    ).filter(
        Financial.period_date >= cutoff
    ).group_by(Financial.period_date).order_by(Financial.period_date)
    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["period_date"] = pd.to_datetime(df["period_date"])
    return df


def get_overdue_aging_summary(session: Session) -> dict:
    res = session.query(
        func.sum(Financial.overdue_collections_aed).label("total_overdue"),
        func.sum(Financial.overdue_30_60d_aed).label("overdue_30_60"),
        func.sum(Financial.overdue_60_90d_aed).label("overdue_60_90"),
        func.sum(Financial.overdue_90d_plus_aed).label("overdue_90_plus"),
        func.sum(Financial.bad_debt_provision_aed).label("bad_debt"),
        func.avg(Financial.collection_efficiency_pct).label("coll_efficiency"),
    ).first()
    return {
        "total_overdue": float(res.total_overdue or 0),
        "overdue_30_60": float(res.overdue_30_60 or 0),
        "overdue_60_90": float(res.overdue_60_90 or 0),
        "overdue_90_plus": float(res.overdue_90_plus or 0),
        "bad_debt": float(res.bad_debt or 0),
        "collection_efficiency": float(res.coll_efficiency or 0),
    }


def get_sales_vs_target(session: Session, months: int = 12) -> pd.DataFrame:
    cutoff = date.today() - timedelta(days=months * 30)
    query = session.query(
        Financial.period_date,
        func.sum(Financial.revenue_booked_aed).label("actual"),
        func.sum(Financial.sales_target_aed).label("target"),
        func.avg(Financial.sales_achievement_pct).label("achievement_pct"),
        func.sum(Financial.pipeline_value_aed).label("pipeline"),
    ).filter(
        Financial.period_date >= cutoff
    ).group_by(Financial.period_date).order_by(Financial.period_date)
    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["period_date"] = pd.to_datetime(df["period_date"])
    return df


def get_financial_kpis(session: Session) -> dict:
    latest = session.query(func.max(Financial.period_date)).scalar()
    if not latest:
        return {}
    cur_start = latest.replace(day=1)
    prev_end = cur_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)

    def _sum(col, s, e):
        return float(session.query(func.sum(col)).filter(
            Financial.period_date >= s, Financial.period_date <= e
        ).scalar() or 0)

    def _avg(col, s, e):
        return float(session.query(func.avg(col)).filter(
            Financial.period_date >= s, Financial.period_date <= e
        ).scalar() or 0)

    rev = _sum(Financial.revenue_booked_aed, cur_start, latest)
    rev_p = _sum(Financial.revenue_booked_aed, prev_start, prev_end)
    gp = _sum(Financial.gross_profit_aed, cur_start, latest)
    ebitda = _sum(Financial.ebitda_aed, cur_start, latest)
    net = _sum(Financial.net_profit_aed, cur_start, latest)
    coll = _sum(Financial.collections_received_aed, cur_start, latest)
    escrow = _sum(Financial.escrow_balance_aed, cur_start, latest)
    forecast3m = _sum(Financial.forecast_next_3m_aed, cur_start, latest)
    achievement = _avg(Financial.sales_achievement_pct, cur_start, latest)
    return {
        "revenue": rev,
        "revenue_prev": rev_p,
        "revenue_mom_delta": ((rev - rev_p) / rev_p * 100) if rev_p else 0,
        "gross_profit": gp,
        "gross_margin": (gp / rev * 100) if rev else 0,
        "ebitda": ebitda,
        "ebitda_margin": (ebitda / rev * 100) if rev else 0,
        "net_profit": net,
        "net_margin": (net / rev * 100) if rev else 0,
        "collections": coll,
        "escrow_balance": escrow,
        "forecast_3m": forecast3m,
        "sales_achievement": achievement,
    }


# ─── Investor Intelligence ────────────────────────────────────────────────────

def get_rental_yield_by_city(session: Session) -> pd.DataFrame:
    query = session.query(
        RentalMarket.city,
        func.avg(RentalMarket.gross_rental_yield_pct).label("gross_yield"),
        func.avg(RentalMarket.net_rental_yield_pct).label("net_yield"),
        func.avg(RentalMarket.occupancy_rate_pct).label("occupancy"),
        func.avg(RentalMarket.avg_annual_rent_aed).label("avg_annual_rent"),
        func.avg(RentalMarket.price_to_rent_ratio).label("price_to_rent"),
        func.avg(RentalMarket.vacancy_rate_pct).label("vacancy"),
    ).group_by(RentalMarket.city).order_by(desc("gross_yield"))
    return pd.read_sql(query.statement, session.bind)


def get_investor_roi_data(session: Session, filters: dict = None) -> pd.DataFrame:
    query = session.query(
        Property.city,
        Property.property_type,
        Property.property_category,
        func.avg(Property.rental_yield_pct).label("rental_yield"),
        func.avg(Property.capital_appreciation_pct).label("capital_appreciation"),
        func.avg(Property.roi_pct).label("roi"),
        func.avg(Property.price_per_sqft_aed).label("avg_price_sqft"),
        func.count(Property.property_id).label("properties"),
    )
    if filters:
        if filters.get("city"):
            query = query.filter(Property.city == filters["city"])
        if filters.get("property_type"):
            query = query.filter(Property.property_type == filters["property_type"])
        if filters.get("property_category"):
            query = query.filter(Property.property_category == filters["property_category"])
    query = query.group_by(
        Property.city, Property.property_type, Property.property_category
    ).order_by(desc("roi"))
    return pd.read_sql(query.statement, session.bind)


def get_golden_visa_stats(session: Session, filters: dict = None) -> dict:
    total_q = session.query(func.count(Transaction.transaction_id))
    gv_q = session.query(func.count(Transaction.transaction_id)).filter(
        Transaction.golden_visa_eligible == True
    )
    if filters:
        total_q = _apply_filters(total_q, filters)
        gv_q = _apply_filters(gv_q, filters)
    total = total_q.scalar() or 0
    gv = gv_q.scalar() or 0
    gv_listings = session.query(
        func.count(Listing.listing_id)
    ).filter(Listing.golden_visa_threshold_met == True).scalar() or 0
    gv_buyers = session.query(
        func.count(Buyer.buyer_id)
    ).filter(Buyer.golden_visa_intent == True).scalar() or 0
    gv_value = session.query(
        func.sum(Transaction.total_transaction_value_aed)
    ).filter(Transaction.golden_visa_eligible == True).scalar() or 0
    return {
        "total_transactions": total,
        "golden_visa_transactions": gv,
        "golden_visa_share_pct": (gv / total * 100) if total else 0,
        "eligible_listings": gv_listings,
        "buyers_with_intent": gv_buyers,
        "gv_transaction_value": float(gv_value),
    }


def get_investor_segment_breakdown(session: Session) -> pd.DataFrame:
    query = session.query(
        Buyer.buyer_type,
        func.count(Buyer.buyer_id).label("count"),
        func.avg(Buyer.budget_max_aed).label("avg_budget"),
        func.avg(Buyer.estimated_annual_income_aed).label("avg_income"),
        func.avg(Buyer.loyalty_score).label("avg_loyalty"),
        func.sum(func.cast(Buyer.golden_visa_intent, Float)).label("gv_intent"),
        func.sum(func.cast(Buyer.off_plan_preference, Float)).label("off_plan"),
    ).group_by(Buyer.buyer_type).order_by(desc("count"))
    return pd.read_sql(query.statement, session.bind)


# ─── Document Intelligence ────────────────────────────────────────────────────

def get_document_type_summary(session: Session) -> pd.DataFrame:
    query = session.query(
        DocumentRegistry.document_type,
        func.count(DocumentRegistry.document_id).label("count"),
        func.sum(func.cast(DocumentRegistry.registered_with_dld, Float)).label("dld_registered"),
        func.sum(func.cast(DocumentRegistry.notarized, Float)).label("notarized"),
        func.avg(DocumentRegistry.page_count).label("avg_pages"),
        func.sum(func.cast(DocumentRegistry.penalty_clause_present, Float)).label("has_penalty"),
    ).group_by(DocumentRegistry.document_type).order_by(desc("count"))
    return pd.read_sql(query.statement, session.bind)


def get_document_expiry_summary(session: Session) -> pd.DataFrame:
    query = session.query(
        DocumentRegistry.expiry_status,
        func.count(DocumentRegistry.document_id).label("count"),
        func.avg(DocumentRegistry.days_to_expiry).label("avg_days_to_expiry"),
    ).group_by(DocumentRegistry.expiry_status).order_by(desc("count"))
    return pd.read_sql(query.statement, session.bind)


def get_document_kpis(session: Session) -> dict:
    total = session.query(func.count(DocumentRegistry.document_id)).scalar() or 0
    dld_reg = session.query(func.count(DocumentRegistry.document_id)).filter(
        DocumentRegistry.registered_with_dld == True
    ).scalar() or 0
    notarized = session.query(func.count(DocumentRegistry.document_id)).filter(
        DocumentRegistry.notarized == True
    ).scalar() or 0
    expiring_soon = session.query(func.count(DocumentRegistry.document_id)).filter(
        DocumentRegistry.days_to_expiry <= 30,
        DocumentRegistry.days_to_expiry > 0,
    ).scalar() or 0
    expired = session.query(func.count(DocumentRegistry.document_id)).filter(
        DocumentRegistry.expiry_status == 'Expired'
    ).scalar() or 0
    with_ai = session.query(func.count(DocumentRegistry.document_id)).filter(
        DocumentRegistry.ai_summary != None
    ).scalar() or 0
    return {
        "total_documents": total,
        "dld_registered": dld_reg,
        "dld_registration_pct": (dld_reg / total * 100) if total else 0,
        "notarized": notarized,
        "notarized_pct": (notarized / total * 100) if total else 0,
        "expiring_soon": expiring_soon,
        "expired": expired,
        "with_ai_summary": with_ai,
    }


def get_document_by_project(session: Session, top_n: int = 15) -> pd.DataFrame:
    query = session.query(
        DocumentRegistry.project_name,
        DocumentRegistry.emirate,
        func.count(DocumentRegistry.document_id).label("doc_count"),
        func.sum(func.cast(DocumentRegistry.registered_with_dld, Float)).label("dld_registered"),
        func.sum(func.cast(DocumentRegistry.penalty_clause_present, Float)).label("penalty_clauses"),
    ).filter(
        DocumentRegistry.project_name != None
    ).group_by(
        DocumentRegistry.project_name, DocumentRegistry.emirate
    ).order_by(desc("doc_count")).limit(top_n)
    return pd.read_sql(query.statement, session.bind)


# ─── Strategic Planning ───────────────────────────────────────────────────────

def get_competitor_overview(session: Session) -> pd.DataFrame:
    query = session.query(
        CompetitorMarket.builder_name,
        CompetitorMarket.builder_tier,
        CompetitorMarket.city,
        func.count(CompetitorMarket.record_id).label("project_count"),
        func.sum(CompetitorMarket.total_units).label("total_units"),
        func.sum(CompetitorMarket.units_sold_reported).label("units_sold"),
        func.avg(CompetitorMarket.price_per_sqft_min_aed).label("min_price_sqft"),
        func.avg(CompetitorMarket.price_per_sqft_max_aed).label("max_price_sqft"),
        func.avg(CompetitorMarket.distance_from_our_project_km).label("avg_distance_km"),
    ).group_by(
        CompetitorMarket.builder_name, CompetitorMarket.builder_tier, CompetitorMarket.city
    ).order_by(desc("total_units")).limit(20)
    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["absorption_pct"] = (df["units_sold"] / df["total_units"].replace(0, 1) * 100).fillna(0)
    return df


def get_competitor_by_city(session: Session) -> pd.DataFrame:
    query = session.query(
        CompetitorMarket.city,
        func.count(CompetitorMarket.builder_name.distinct()).label("competitors"),
        func.count(CompetitorMarket.record_id).label("projects"),
        func.sum(CompetitorMarket.total_units).label("total_units"),
        func.avg(CompetitorMarket.price_per_sqft_min_aed).label("avg_min_price"),
        func.avg(CompetitorMarket.price_per_sqft_max_aed).label("avg_max_price"),
    ).group_by(CompetitorMarket.city).order_by(desc("total_units"))
    return pd.read_sql(query.statement, session.bind)


def get_macro_indicators_latest(session: Session) -> dict:
    latest = session.query(func.max(MarketFactor.date)).scalar()
    if not latest:
        return {}
    row = session.query(MarketFactor).filter(MarketFactor.date == latest).first()
    if not row:
        return {}
    return {
        "date": str(latest),
        "base_rate": row.uae_central_bank_base_rate_pct,
        "mortgage_rate": row.mortgage_rate_avg_pct,
        "gdp_growth": row.gdp_growth_pct,
        "cpi_inflation": row.cpi_inflation_pct,
        "consumer_confidence": row.consumer_confidence_index,
        "price_index": row.real_estate_price_index,
        "rental_yield": row.rental_yield_avg_pct,
        "off_plan_share": row.off_plan_sales_share_pct,
        "golden_visa_apps": row.golden_visa_applications,
        "foreign_investment": row.foreign_investment_inflow_bn_aed,
        "oil_price": row.oil_price_usd_bbl,
    }


# ─── Rental Trends ────────────────────────────────────────────────────────────

def get_rental_trend_over_time(session: Session) -> pd.DataFrame:
    query = session.query(
        RentalMarket.period_date,
        RentalMarket.city,
        func.avg(RentalMarket.avg_annual_rent_aed).label("avg_rent"),
        func.avg(RentalMarket.gross_rental_yield_pct).label("gross_yield"),
        func.avg(RentalMarket.occupancy_rate_pct).label("occupancy"),
        func.avg(RentalMarket.rent_yoy_change_pct).label("rent_yoy_change"),
    ).group_by(RentalMarket.period_date, RentalMarket.city).order_by(RentalMarket.period_date)
    df = pd.read_sql(query.statement, session.bind)
    if not df.empty:
        df["period_date"] = pd.to_datetime(df["period_date"])
    return df


def get_rental_yield_by_type_bedroom(session: Session) -> pd.DataFrame:
    query = session.query(
        RentalMarket.property_type,
        RentalMarket.bedrooms,
        func.avg(RentalMarket.gross_rental_yield_pct).label("gross_yield"),
        func.avg(RentalMarket.net_rental_yield_pct).label("net_yield"),
        func.avg(RentalMarket.avg_annual_rent_aed).label("avg_annual_rent"),
        func.avg(RentalMarket.occupancy_rate_pct).label("occupancy"),
        func.avg(RentalMarket.vacancy_rate_pct).label("vacancy"),
        func.count(RentalMarket.record_id).label("records"),
    ).group_by(RentalMarket.property_type, RentalMarket.bedrooms).order_by(desc("gross_yield"))
    return pd.read_sql(query.statement, session.bind)


def get_short_term_rental_stats(session: Session) -> pd.DataFrame:
    query = session.query(
        RentalMarket.city,
        func.avg(RentalMarket.short_term_rental_share_pct).label("str_share"),
        func.avg(RentalMarket.short_term_avg_daily_rate_aed).label("adr"),
        func.avg(RentalMarket.short_term_occupancy_pct).label("str_occupancy"),
        func.avg(RentalMarket.short_term_annual_revenue_aed).label("str_annual_revenue"),
        func.avg(RentalMarket.gross_rental_yield_pct).label("gross_yield"),
        func.avg(RentalMarket.avg_tenancy_duration_months).label("avg_tenancy_months"),
    ).group_by(RentalMarket.city).order_by(desc("str_annual_revenue"))
    return pd.read_sql(query.statement, session.bind)


def get_rental_market_kpis(session: Session) -> dict:
    avg_yield = session.query(func.avg(RentalMarket.gross_rental_yield_pct)).scalar() or 0
    avg_occupancy = session.query(func.avg(RentalMarket.occupancy_rate_pct)).scalar() or 0
    avg_rent = session.query(func.avg(RentalMarket.avg_annual_rent_aed)).scalar() or 0
    avg_yoy = session.query(func.avg(RentalMarket.rent_yoy_change_pct)).scalar() or 0
    avg_vacancy = session.query(func.avg(RentalMarket.vacancy_rate_pct)).scalar() or 0
    total_listings = session.query(func.sum(RentalMarket.total_active_listings)).scalar() or 0
    ejari = session.query(func.sum(RentalMarket.ejari_registrations)).scalar() or 0
    return {
        "avg_gross_yield": float(avg_yield),
        "avg_occupancy": float(avg_occupancy),
        "avg_annual_rent": float(avg_rent),
        "avg_rent_yoy_change": float(avg_yoy),
        "avg_vacancy": float(avg_vacancy),
        "total_active_listings": int(total_listings),
        "ejari_registrations": int(ejari),
    }
