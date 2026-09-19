"""
Market-neutral schema.

Every business table carries `tenant_id` (row-level security keys off it) and an
`extras` JSONB for source columns that have no canonical field. Money columns
carry no currency in their name: the currency is the tenant's config. Physical
quantities are stored metric (km, kW, sqm, l/100km — lower is better). The
schema/catalog.py field catalog mirrors these columns and is checked against
them by tests.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Text, Integer, Float, Date, DateTime, Boolean, ForeignKey, ForeignKeyConstraint,
    Index, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from database.connection import Base
from database.rls import TENANT_EXPR


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def tenant_col(pk: bool = False):
    """
    Owner tenant of a row. Defaults from the transaction's app.current_tenant_id,
    so application inserts never pass it, and the RLS WITH CHECK rejects any
    attempt to write a row for a different tenant.
    """
    return Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=pk,
        nullable=False,
        server_default=text(TENANT_EXPR),
        index=not pk,
    )


class Tenant(Base):
    """
    One row per customer account. `config` replaces what used to be per-market
    code branches: currency, currency_symbol, symbol_position, language,
    region_label, country, news_hl/news_gl (news edition).
    """
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="active")     # active | suspended
    plan = Column(Text, nullable=True)
    config = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class ColumnMapping(Base):
    """A tenant's saved source-column -> canonical-field mapping for one table, reused on re-uploads."""
    __tablename__ = "column_mappings"

    tenant_id = tenant_col(pk=True)
    table_name = Column(Text, primary_key=True)
    mapping = Column(JSONB, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=_utcnow)


class IngestJob(Base):
    """One upload-and-load run, executed by the background worker."""
    __tablename__ = "ingest_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = tenant_col()
    status = Column(Text, nullable=False, default="queued")     # queued | running | succeeded | failed
    stage = Column(Text, nullable=True)
    progress = Column(Float, nullable=False, default=0.0)       # 0..1
    message = Column(Text, nullable=True)
    options = Column(JSONB, nullable=True)                      # files, mappings, replace, units
    report = Column(JSONB, nullable=True)                       # row counts, warnings, errors
    created_by = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class Customer(Base):
    __tablename__ = "customers"

    tenant_id = tenant_col(pk=True)
    customer_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(Text, nullable=True)
    # Descriptive only. Deliberately kept out of any per-lead scoring: scoring an
    # individual on nationality is a discrimination exposure in most markets.
    nationality = Column(Text, nullable=True)
    customer_type = Column(Text, nullable=True)                       # e.g. Private / Commercial
    region = Column(Text, nullable=True)                              # state / emirate / Bundesland / province
    city = Column(Text, nullable=True)
    postal_code = Column(Text, nullable=True)
    occupation = Column(Text, nullable=True)
    income_bracket = Column(Text, nullable=True)
    annual_income = Column(Float, nullable=True)                      # tenant currency, per year
    credit_score = Column(Integer, nullable=True)                     # bureau score; scale is the source's own
    years_at_address = Column(Integer, nullable=True)
    number_of_past_purchases = Column(Integer, nullable=True)
    preferred_fuel_type = Column(Text, nullable=True)
    preferred_vehicle_category = Column(Text, nullable=True)
    customer_segment = Column(Text, nullable=True)
    loyalty_score = Column(Float, nullable=True)
    marketing_response_score = Column(Float, nullable=True)
    lead_source = Column(Text, nullable=True)
    email_opt_in = Column(Boolean, nullable=True)
    test_drive_taken = Column(Boolean, nullable=True)
    financing_preferred = Column(Boolean, nullable=True)
    down_payment_capacity = Column(Float, nullable=True)
    registration_date = Column(Date, nullable=True)
    last_activity_date = Column(Date, nullable=True)
    churn_risk_score = Column(Float, nullable=True)
    extras = Column(JSONB, nullable=True)


class Vehicle(Base):
    __tablename__ = "vehicles"

    tenant_id = tenant_col(pk=True)
    vehicle_id = Column(Text, primary_key=True)
    brand = Column(Text, nullable=True)
    model = Column(Text, nullable=True)
    variant = Column(Text, nullable=True)
    category = Column(Text, nullable=True)
    fuel_type = Column(Text, nullable=True)
    price = Column(Float, nullable=True)                              # list price, tenant currency
    engine_cc = Column(Integer, nullable=True)
    power_kw = Column(Integer, nullable=True)
    # Combined consumption, l/100km. LOWER IS BETTER. NULL where the drivetrain
    # has no such figure (a BEV): a zero would make it look like the most
    # economical petrol car.
    consumption_l_per_100km = Column(Float, nullable=True)
    consumption_kwh_per_100km = Column(Float, nullable=True)
    range_km = Column(Integer, nullable=True)
    co2_g_per_km = Column(Integer, nullable=True)
    origin = Column(Text, nullable=True)                              # e.g. Domestic / Import
    seating_capacity = Column(Integer, nullable=True)
    transmission = Column(Text, nullable=True)
    drive_type = Column(Text, nullable=True)
    body_color_options = Column(Integer, nullable=True)
    safety_rating = Column(Integer, nullable=True)
    launch_year = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=True)
    warranty_years = Column(Integer, nullable=True)
    service_contract_available = Column(Boolean, nullable=True)
    residual_value_36mo = Column(Float, nullable=True)                # share of list price retained at 36 months
    extras = Column(JSONB, nullable=True)


class Dealer(Base):
    __tablename__ = "dealers"

    tenant_id = tenant_col(pk=True)
    dealer_id = Column(Text, primary_key=True)
    dealer_name = Column(Text, nullable=True)
    brand = Column(Text, nullable=True)
    region = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    postal_code = Column(Text, nullable=True)
    tier = Column(Text, nullable=True)
    established_year = Column(Integer, nullable=True)
    monthly_capacity = Column(Integer, nullable=True)
    showroom_area_sqm = Column(Integer, nullable=True)
    service_center = Column(Boolean, nullable=True)
    ev_charging_station = Column(Boolean, nullable=True)
    num_salespeople = Column(Integer, nullable=True)
    annual_target_units = Column(Integer, nullable=True)
    performance_score = Column(Float, nullable=True)
    google_rating = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    extras = Column(JSONB, nullable=True)


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "customer_id"], ["customers.tenant_id", "customers.customer_id"]),
        ForeignKeyConstraint(["tenant_id", "dealer_id"], ["dealers.tenant_id", "dealers.dealer_id"]),
        ForeignKeyConstraint(["tenant_id", "vehicle_id"], ["vehicles.tenant_id", "vehicles.vehicle_id"]),
        Index("ix_sales_tenant_date", "tenant_id", "sale_date"),
        # Referencing-side indexes: without them every parent delete/update is a full child scan.
        Index("ix_sales_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_sales_tenant_dealer", "tenant_id", "dealer_id"),
        Index("ix_sales_tenant_vehicle", "tenant_id", "vehicle_id"),
    )

    tenant_id = tenant_col(pk=True)
    sale_id = Column(Text, primary_key=True)
    sale_date = Column(Date, nullable=False, index=True)
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    quarter = Column(Text, nullable=True)
    day_of_week = Column(Text, nullable=True)
    season_period = Column(Text, nullable=True)                       # local retail calendar, canonical English

    customer_id = Column(Text, nullable=True)
    dealer_id = Column(Text, nullable=True)
    vehicle_id = Column(Text, nullable=True)

    # Denormalized columns for fast analytical queries
    brand = Column(Text, nullable=True)
    model = Column(Text, nullable=True)
    vehicle_category = Column(Text, nullable=True)
    fuel_type = Column(Text, nullable=True)
    region = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    customer_type = Column(Text, nullable=True)
    is_fleet = Column(Boolean, nullable=True)

    base_price = Column(Float, nullable=True)
    discount_pct = Column(Float, nullable=True)
    selling_price = Column(Float, nullable=True)
    tax_amount = Column(Float, nullable=True)                         # VAT / sales tax
    accessories_revenue = Column(Float, nullable=True)
    insurance_revenue = Column(Float, nullable=True)
    extended_warranty = Column(Float, nullable=True)
    total_revenue_excl_tax = Column(Float, nullable=True)
    total_revenue_incl_tax = Column(Float, nullable=True)
    financing_type = Column(Text, nullable=True)                      # Cash / Loan / Lease / ...
    loan_amount = Column(Float, nullable=True)
    units_sold = Column(Integer, default=1)
    test_drive_converted = Column(Boolean, nullable=True)
    lead_to_close_days = Column(Integer, nullable=True)
    salesperson_id = Column(Text, nullable=True)
    marketing_channel = Column(Text, nullable=True)
    season_multiplier = Column(Float, nullable=True)

    # Lease contract terms — populated only for lease deals; NULL otherwise on
    # purpose (a cash deal has no maturity date, and inventing one would invent
    # lease returns that never happen).
    lease_term_months = Column(Integer, nullable=True)
    lease_maturity_date = Column(Date, nullable=True, index=True)
    residual_value_pct = Column(Float, nullable=True)
    residual_value = Column(Float, nullable=True)
    contract_mileage_allowance = Column(Integer, nullable=True)       # km over the term
    lease_monthly_payment = Column(Float, nullable=True)

    # Trade-in activity
    trade_in_flag = Column(Boolean, nullable=True)
    trade_in_brand = Column(Text, nullable=True)
    trade_in_model = Column(Text, nullable=True)
    trade_in_year = Column(Integer, nullable=True)
    trade_in_mileage = Column(Integer, nullable=True)                 # km
    trade_in_appraised_value = Column(Float, nullable=True)
    trade_in_allowance = Column(Float, nullable=True)
    trade_in_over_allowance = Column(Float, nullable=True)            # allowance - appraised
    trade_bonus = Column(Float, nullable=True)
    extras = Column(JSONB, nullable=True)


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "dealer_id"], ["dealers.tenant_id", "dealers.dealer_id"]),
        ForeignKeyConstraint(["tenant_id", "vehicle_id"], ["vehicles.tenant_id", "vehicles.vehicle_id"]),
        Index("ix_inventory_tenant_date", "tenant_id", "record_date"),
        Index("ix_inventory_tenant_dealer", "tenant_id", "dealer_id"),
        Index("ix_inventory_tenant_vehicle", "tenant_id", "vehicle_id"),
    )

    tenant_id = tenant_col(pk=True)
    inventory_id = Column(Text, primary_key=True)
    record_date = Column(Date, nullable=False, index=True)

    dealer_id = Column(Text, nullable=True)
    vehicle_id = Column(Text, nullable=True)

    brand = Column(Text, nullable=True)
    model = Column(Text, nullable=True)
    vehicle_category = Column(Text, nullable=True)
    fuel_type = Column(Text, nullable=True)
    region = Column(Text, nullable=True)
    city = Column(Text, nullable=True)

    current_stock = Column(Integer, nullable=True)
    demand_forecast_30d = Column(Integer, nullable=True)
    reorder_point = Column(Integer, nullable=True)
    days_in_stock = Column(Integer, nullable=True)
    stockout_flag = Column(Boolean, nullable=True)
    overstock_flag = Column(Boolean, nullable=True)
    reorder_needed = Column(Boolean, nullable=True)
    stockout_risk_score = Column(Float, nullable=True)
    overstock_risk_score = Column(Float, nullable=True)
    holding_cost_per_day = Column(Float, nullable=True)
    estimated_holding_cost = Column(Float, nullable=True)
    units_sold_last_30d = Column(Integer, nullable=True)
    units_ordered = Column(Integer, nullable=True)
    transit_stock = Column(Integer, nullable=True)
    origin_hub = Column(Text, nullable=True)                          # plant or port of entry
    warehouse_zone = Column(Text, nullable=True)
    last_replenishment_date = Column(Date, nullable=True)
    supplier_lead_time_days = Column(Integer, nullable=True)
    customs_cleared = Column(Boolean, nullable=True)
    extras = Column(JSONB, nullable=True)


class ExternalFactor(Base):
    """Monthly market conditions. Market-specific series (local events, subsidies) live in `extras`."""
    __tablename__ = "external_factors"
    __table_args__ = (Index("ix_external_factors_tenant_date", "tenant_id", "date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = tenant_col()
    date = Column(Date, nullable=False, index=True)
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    quarter = Column(Text, nullable=True)
    region = Column(Text, nullable=True)

    # Fuel and energy — per litre in the tenant's currency (gallon sources are converted)
    petrol_price_per_litre = Column(Float, nullable=True)
    diesel_price_per_litre = Column(Float, nullable=True)
    crude_oil_price_usd = Column(Float, nullable=True)                # Brent/WTI benchmark, quoted in USD globally

    # Macro-economic
    policy_rate_pct = Column(Float, nullable=True)                    # central bank policy rate
    auto_loan_apr_pct = Column(Float, nullable=True)
    incentive_pct_of_atp = Column(Float, nullable=True)               # incentive spend as a share of transaction price
    inventory_days_supply = Column(Float, nullable=True)
    gdp_growth_pct = Column(Float, nullable=True)
    cpi_inflation_pct = Column(Float, nullable=True)
    consumer_confidence_index = Column(Float, nullable=True)
    business_climate_index = Column(Float, nullable=True)
    house_price_index = Column(Float, nullable=True)
    luxury_demand_index = Column(Float, nullable=True)
    unemployment_rate_pct = Column(Float, nullable=True)
    population_millions = Column(Float, nullable=True)

    # Industry / policy
    new_model_launches = Column(Integer, nullable=True)
    tax_rate_pct = Column(Float, nullable=True)
    ev_charging_points = Column(Integer, nullable=True)

    # Calendar flags (retail push months)
    quarter_end_month = Column(Integer, nullable=True)
    year_end_month = Column(Integer, nullable=True)
    extras = Column(JSONB, nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# Sentiment Analysis Tables
# ─────────────────────────────────────────────────────────────────────────────

class NewsArticle(Base):
    """Raw articles fetched from Google News RSS, in the tenant's news edition."""
    __tablename__ = "news_articles"
    __table_args__ = (UniqueConstraint("tenant_id", "url", name="uq_news_tenant_url"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = tenant_col()
    url = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    source_domain = Column(Text, nullable=True)
    source_country = Column(Text, nullable=True)
    published_date = Column(Date, nullable=True)
    fetched_at = Column(DateTime, nullable=False)
    search_query = Column(Text, nullable=True)
    language = Column(Text, nullable=True)
    social_image_url = Column(Text, nullable=True)

    # Relationship to AI-extracted signal (one article → one signal)
    sentiment_signal = relationship("SentimentSignal", back_populates="article", uselist=False)


class SentimentSignal(Base):
    """Forecasting signals extracted for each news article."""
    __tablename__ = "sentiment_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = tenant_col()
    article_id = Column(Integer, ForeignKey("news_articles.id"), nullable=False, unique=True)
    analyzed_at = Column(DateTime, nullable=False)

    sentiment_score = Column(Float, nullable=True)             # -1.0 (very negative) to +1.0 (very positive)
    impact_score = Column(Float, nullable=True)                # 0.0 (no impact) to 1.0 (high impact)
    affected_vehicle_category = Column(Text, nullable=True)    # SUV, EV, Luxury, All, etc.
    economic_risk = Column(Text, nullable=True)                # low | medium | high
    demand_direction = Column(Text, nullable=True)             # up | down | neutral
    estimated_demand_change_pct = Column(Float, nullable=True) # e.g. +3.5 or -2.1
    confidence = Column(Float, nullable=True)                  # 0.0 to 1.0
    summary = Column(Text, nullable=True)                      # one-sentence summary (English)
    summary_de = Column(Text, nullable=True)                   # German rendering for the DE toggle
    raw_response = Column(Text, nullable=True)                 # full model JSON (for debugging)

    article = relationship("NewsArticle", back_populates="sentiment_signal")


class DailySentimentSummary(Base):
    """
    Daily aggregated sentiment scores per vehicle category, used as external
    regressors in Prophet forecasting. One row per (summary_date, vehicle_category);
    NULL vehicle_category = aggregate across all categories.
    """
    __tablename__ = "daily_sentiment_summary"
    __table_args__ = (
        UniqueConstraint("tenant_id", "summary_date", "vehicle_category", name="uq_daily_sentiment"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = tenant_col()
    summary_date = Column(Date, nullable=False, index=True)
    vehicle_category = Column(Text, nullable=True)

    avg_sentiment_score = Column(Float, nullable=True)
    avg_impact_score = Column(Float, nullable=True)
    avg_demand_change_pct = Column(Float, nullable=True)
    geopolitical_risk_score = Column(Float, nullable=True)     # derived: avg_impact * negative_ratio

    positive_signals = Column(Integer, nullable=True)
    negative_signals = Column(Integer, nullable=True)
    neutral_signals = Column(Integer, nullable=True)
    total_articles = Column(Integer, nullable=True)
    dominant_demand_direction = Column(Text, nullable=True)    # up | down | neutral

    computed_at = Column(DateTime, nullable=False)
