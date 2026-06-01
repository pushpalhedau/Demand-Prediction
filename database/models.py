from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from database.connection import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    nationality = Column(String(100), nullable=True)
    emirate = Column(String(50), nullable=True)   # was: region / city
    area = Column(String(100), nullable=True)
    occupation = Column(String(100), nullable=True)
    monthly_income_bracket = Column(String(50), nullable=True)        # was: annual_income_bracket
    estimated_monthly_income_aed = Column(Float, nullable=True)       # was: estimated_annual_income
    emirates_id = Column(String(50), nullable=True)
    resident_type = Column(String(50), nullable=True)
    years_in_uae = Column(Integer, nullable=True)
    credit_score = Column(Integer, nullable=True)
    number_of_past_purchases = Column(Integer, nullable=True)
    preferred_fuel_type = Column(String(50), nullable=True)
    preferred_vehicle_category = Column(String(50), nullable=True)
    customer_segment = Column(String(50), nullable=True)
    loyalty_score = Column(Float, nullable=True)
    marketing_response_score = Column(Float, nullable=True)
    lead_source = Column(String(50), nullable=True)
    whatsapp_opted = Column(Boolean, nullable=True)
    test_drive_taken = Column(Boolean, nullable=True)
    emi_preferred = Column(Boolean, nullable=True)
    down_payment_capacity_aed = Column(Integer, nullable=True)        # was: down_payment_capacity
    registration_date = Column(Date, nullable=True)
    last_activity_date = Column(Date, nullable=True)
    churn_risk_score = Column(Float, nullable=True)
    visa_expiry_year = Column(Integer, nullable=True)

    # Relationships
    sales = relationship("Sale", back_populates="customer")


class Vehicle(Base):
    __tablename__ = "vehicles"

    vehicle_id = Column(String(50), primary_key=True)
    brand = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    variant = Column(String(100), nullable=True)
    category = Column(String(50), nullable=True)
    fuel_type = Column(String(50), nullable=True)
    price_aed = Column(Integer, nullable=True)                        # was: ex_showroom_price
    engine_cc = Column(Integer, nullable=True)
    horsepower = Column(Integer, nullable=True)
    mileage_kmpl = Column(Float, nullable=True)
    range_km = Column(Integer, nullable=True)
    seating_capacity = Column(Integer, nullable=True)
    transmission = Column(String(50), nullable=True)
    drive_type = Column(String(50), nullable=True)
    body_color_options = Column(Integer, nullable=True)
    safety_rating = Column(Integer, nullable=True)
    launch_year = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=True)
    vat_inclusive_price = Column(Integer, nullable=True)
    warranty_years = Column(Integer, nullable=True)
    service_contract_available = Column(Boolean, nullable=True)
    gcc_spec = Column(Boolean, nullable=True)

    # Relationships
    sales = relationship("Sale", back_populates="vehicle")
    inventories = relationship("Inventory", back_populates="vehicle")


class Dealer(Base):
    __tablename__ = "dealers"

    dealer_id = Column(String(50), primary_key=True)
    dealer_name = Column(String(150), nullable=True)
    brand = Column(String(100), nullable=True)
    emirate = Column(String(50), nullable=True)                       # was: region
    area = Column(String(100), nullable=True)                         # was: city
    address = Column(String(250), nullable=True)
    po_box = Column(String(20), nullable=True)                        # was: pincode
    tier = Column(String(50), nullable=True)
    established_year = Column(Integer, nullable=True)
    monthly_capacity = Column(Integer, nullable=True)
    showroom_area_sqft = Column(Integer, nullable=True)
    service_center = Column(Boolean, nullable=True)
    ev_charging_station = Column(Boolean, nullable=True)
    num_salespeople = Column(Integer, nullable=True)
    annual_target_units = Column(Integer, nullable=True)
    performance_score = Column(Float, nullable=True)
    google_rating = Column(Float, nullable=True)                      # was: rating
    vat_registered = Column(Boolean, nullable=True)
    trn_number = Column(String(50), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Relationships
    sales = relationship("Sale", back_populates="dealer")
    inventories = relationship("Inventory", back_populates="dealer")


class Sale(Base):
    __tablename__ = "sales"

    sale_id = Column(String(50), primary_key=True)
    sale_date = Column(Date, nullable=False, index=True)
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    quarter = Column(String(10), nullable=True)
    day_of_week = Column(String(20), nullable=True)
    festival_period = Column(String(100), nullable=True)

    customer_id = Column(String(50), ForeignKey("customers.customer_id"), nullable=True)
    dealer_id = Column(String(50), ForeignKey("dealers.dealer_id"), nullable=True)
    vehicle_id = Column(String(50), ForeignKey("vehicles.vehicle_id"), nullable=True)

    # Denormalized columns for fast analytical queries
    brand = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    vehicle_category = Column(String(50), nullable=True)
    fuel_type = Column(String(50), nullable=True)
    emirate = Column(String(50), nullable=True)                       # was: region
    area = Column(String(100), nullable=True)                         # was: city

    base_price_aed = Column(Integer, nullable=True)                   # was: base_price
    discount_pct = Column(Float, nullable=True)
    selling_price_aed = Column(Integer, nullable=True)                # was: selling_price
    vat_amount_aed = Column(Integer, nullable=True)
    accessories_revenue_aed = Column(Integer, nullable=True)          # was: accessories_revenue
    insurance_revenue_aed = Column(Integer, nullable=True)            # was: insurance_revenue
    extended_warranty_aed = Column(Integer, nullable=True)            # was: extended_warranty
    total_revenue_excl_vat = Column(Integer, nullable=True)           # was: total_revenue (split into two)
    total_revenue_incl_vat = Column(Integer, nullable=True)

    financing_type = Column(String(50), nullable=True)
    loan_amount_aed = Column(Integer, nullable=True)                  # was: loan_amount
    units_sold = Column(Integer, default=1)
    test_drive_converted = Column(Boolean, nullable=True)
    lead_to_close_days = Column(Integer, nullable=True)
    salesperson_id = Column(String(50), nullable=True)
    marketing_channel = Column(String(100), nullable=True)
    gcc_spec = Column(Boolean, nullable=True)
    export_sale = Column(Boolean, nullable=True)
    season_multiplier = Column(Float, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="sales")
    dealer = relationship("Dealer", back_populates="sales")
    vehicle = relationship("Vehicle", back_populates="sales")


class Inventory(Base):
    __tablename__ = "inventory"

    inventory_id = Column(String(50), primary_key=True)
    record_date = Column(Date, nullable=False, index=True)

    dealer_id = Column(String(50), ForeignKey("dealers.dealer_id"), nullable=True)
    vehicle_id = Column(String(50), ForeignKey("vehicles.vehicle_id"), nullable=True)

    brand = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    vehicle_category = Column(String(50), nullable=True)
    fuel_type = Column(String(50), nullable=True)
    emirate = Column(String(50), nullable=True)                       # was: region
    area = Column(String(100), nullable=True)                         # was: city

    current_stock = Column(Integer, nullable=True)
    demand_forecast_30d = Column(Integer, nullable=True)
    reorder_point = Column(Integer, nullable=True)
    days_in_stock = Column(Integer, nullable=True)
    stockout_flag = Column(Boolean, nullable=True)
    overstock_flag = Column(Boolean, nullable=True)
    reorder_needed = Column(Boolean, nullable=True)
    stockout_risk_score = Column(Float, nullable=True)
    overstock_risk_score = Column(Float, nullable=True)
    holding_cost_per_day_aed = Column(Float, nullable=True)           # was: holding_cost_per_day
    estimated_holding_cost_aed = Column(Float, nullable=True)        # was: estimated_holding_cost
    units_sold_last_30d = Column(Integer, nullable=True)
    units_ordered = Column(Integer, nullable=True)
    transit_stock = Column(Integer, nullable=True)
    port_of_entry = Column(String(100), nullable=True)
    warehouse_zone = Column(String(50), nullable=True)                # was: warehouse_location
    last_replenishment_date = Column(Date, nullable=True)
    supplier_lead_time_days = Column(Integer, nullable=True)
    customs_cleared = Column(Boolean, nullable=True)

    # Relationships
    dealer = relationship("Dealer", back_populates="inventories")
    vehicle = relationship("Vehicle", back_populates="inventories")


class ExternalFactor(Base):
    __tablename__ = "external_factors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    quarter = Column(String(10), nullable=True)
    emirate = Column(String(50), nullable=True)                       # was: region

    # Fuel Prices (AED)
    petrol_95_price_aed_per_litre = Column(Float, nullable=True)     # was: petrol_price_per_litre
    petrol_98_price_aed_per_litre = Column(Float, nullable=True)
    diesel_price_aed_per_litre = Column(Float, nullable=True)         # was: diesel_price_per_litre
    crude_oil_price_usd = Column(Float, nullable=True)

    # Macro-economic
    gdp_growth_pct = Column(Float, nullable=True)
    cpi_inflation_pct = Column(Float, nullable=True)
    us_fed_rate_pct = Column(Float, nullable=True)                    # was: rbi_repo_rate_pct
    consumer_confidence_index = Column(Float, nullable=True)
    tourism_index = Column(Float, nullable=True)
    dubai_re_price_index = Column(Float, nullable=True)
    luxury_demand_index = Column(Float, nullable=True)
    usd_aed_rate = Column(Float, nullable=True)                       # was: usd_inr_rate

    # Events / Seasonal flags
    expo_2020_active = Column(Integer, nullable=True)
    ramadan_month = Column(Integer, nullable=True)                    # was: festival_month
    national_day_month = Column(Integer, nullable=True)
    dubai_motor_show = Column(Integer, nullable=True)
    abu_dhabi_motor_show = Column(Integer, nullable=True)

    # Industry
    new_model_launches = Column(Integer, nullable=True)
    import_duty_pct = Column(Float, nullable=True)                    # was: registration_tax_pct
    vat_rate_pct = Column(Float, nullable=True)                       # was: road_cess_pct
    unemployment_rate_pct = Column(Float, nullable=True)
    population_millions = Column(Float, nullable=True)
    ev_charging_stations_uae = Column(Integer, nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# India Tables (VAHAN-based)
# ─────────────────────────────────────────────────────────────────────────────

class Registration(Base):
    """Monthly vehicle registrations from VAHAN (India fact table)."""
    __tablename__ = "registrations"

    reg_id = Column(Integer, primary_key=True, autoincrement=True)
    reg_date = Column(Date, nullable=False, index=True)
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    quarter = Column(String(10), nullable=True)

    state = Column(String(100), nullable=True, index=True)
    rto_code = Column(String(20), nullable=True)

    maker = Column(String(100), nullable=True, index=True)
    vehicle_class = Column(String(100), nullable=True)
    vehicle_category_group = Column(String(100), nullable=True)
    fuel_type = Column(String(50), nullable=True, index=True)
    norms = Column(String(50), nullable=True)   # BS4, BS6, etc.

    registrations_count = Column(Integer, nullable=True)


class StateProfile(Base):
    """Geographic dimension: Indian states with centroid coords and market segment."""
    __tablename__ = "state_profiles"

    state_code = Column(String(10), primary_key=True)
    state_name = Column(String(100), nullable=False)
    region = Column(String(50), nullable=True)          # North/South/East/West/Central/Northeast
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_metro = Column(Boolean, nullable=True)
    total_area_km2 = Column(Float, nullable=True)
    population_millions = Column(Float, nullable=True)
    market_segment = Column(String(100), nullable=True) # written back by KMeans


class IndiaExternalFactor(Base):
    """Monthly Indian macro-economic and policy indicators per state."""
    __tablename__ = "india_external_factors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    quarter = Column(String(10), nullable=True)
    state = Column(String(100), nullable=True)

    petrol_price_inr = Column(Float, nullable=True)
    diesel_price_inr = Column(Float, nullable=True)
    cng_price_inr = Column(Float, nullable=True)

    rbi_repo_rate_pct = Column(Float, nullable=True)
    india_gdp_growth_pct = Column(Float, nullable=True)
    india_cpi_pct = Column(Float, nullable=True)
    usd_inr_rate = Column(Float, nullable=True)
    consumer_confidence_index = Column(Float, nullable=True)

    diwali_month = Column(Integer, nullable=True)
    navratri_month = Column(Integer, nullable=True)
    eid_month = Column(Integer, nullable=True)
    financial_year_end = Column(Integer, nullable=True)
    budget_month = Column(Integer, nullable=True)

    new_model_launches = Column(Integer, nullable=True)
    gst_rate_pct = Column(Float, nullable=True)
    bs6_norms_active = Column(Integer, nullable=True)
    ev_subsidy_active = Column(Integer, nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# Sentiment Analysis Tables
# ─────────────────────────────────────────────────────────────────────────────

class NewsArticle(Base):
    """Raw articles fetched from GDELT Doc v2 API."""
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(1000), unique=True, nullable=False)
    title = Column(Text, nullable=True)
    source_domain = Column(String(300), nullable=True)
    source_country = Column(String(10), nullable=True)
    published_date = Column(Date, nullable=True)
    fetched_at = Column(DateTime, nullable=False)
    search_query = Column(String(300), nullable=True)
    language = Column(String(10), nullable=True)
    social_image_url = Column(String(1000), nullable=True)

    # Relationship to AI-extracted signal (one article → one signal)
    sentiment_signal = relationship("SentimentSignal", back_populates="article", uselist=False)


class SentimentSignal(Base):
    """Grok AI-extracted forecasting signals for each news article."""
    __tablename__ = "sentiment_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("news_articles.id"), nullable=False, unique=True)
    analyzed_at = Column(DateTime, nullable=False)

    # Grok-extracted fields
    sentiment_score = Column(Float, nullable=True)             # -1.0 (very negative) to +1.0 (very positive)
    impact_score = Column(Float, nullable=True)                # 0.0 (no impact) to 1.0 (high impact)
    affected_vehicle_category = Column(String(100), nullable=True)  # SUV, EV, Luxury, Sedan, All, etc.
    affected_maker = Column(String(100), nullable=True)              # Maruti Suzuki, Tata, All, etc.
    economic_risk = Column(String(20), nullable=True)          # low | medium | high
    demand_direction = Column(String(10), nullable=True)       # up | down | neutral
    estimated_demand_change_pct = Column(Float, nullable=True) # e.g. +3.5 or -2.1
    confidence = Column(Float, nullable=True)                  # 0.0 to 1.0
    summary = Column(Text, nullable=True)                      # one-sentence Grok summary
    raw_response = Column(Text, nullable=True)                 # full JSON from Grok (for debugging)

    # Relationship back to article
    article = relationship("NewsArticle", back_populates="sentiment_signal")


class DailySentimentSummary(Base):
    """
    Daily aggregated sentiment scores per vehicle category.
    Used as external regressors in Prophet forecasting.
    One row per (summary_date, vehicle_category).
    NULL vehicle_category = aggregate across all categories.
    """
    __tablename__ = "daily_sentiment_summary"
    __table_args__ = (
        UniqueConstraint("summary_date", "vehicle_category", name="uq_daily_sentiment"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    summary_date = Column(Date, nullable=False, index=True)
    vehicle_category = Column(String(100), nullable=True)  # NULL = all categories combined

    avg_sentiment_score = Column(Float, nullable=True)
    avg_impact_score = Column(Float, nullable=True)
    avg_demand_change_pct = Column(Float, nullable=True)
    geopolitical_risk_score = Column(Float, nullable=True) # derived: avg_impact * negative_ratio

    positive_signals = Column(Integer, nullable=True)
    negative_signals = Column(Integer, nullable=True)
    neutral_signals = Column(Integer, nullable=True)
    total_articles = Column(Integer, nullable=True)
    dominant_demand_direction = Column(String(10), nullable=True)  # up | down | neutral

    computed_at = Column(DateTime, nullable=False)
