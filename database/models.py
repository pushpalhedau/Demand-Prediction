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
    state = Column(String(50), nullable=True)                         # was: emirate
    city = Column(String(100), nullable=True)                         # was: area
    occupation = Column(String(100), nullable=True)
    income_bracket = Column(String(50), nullable=True)                # was: monthly_income_bracket
    estimated_annual_income_usd = Column(Float, nullable=True)        # was: estimated_monthly_income_aed
    credit_score = Column(Integer, nullable=True)
    years_at_address = Column(Integer, nullable=True)                 # was: years_in_uae
    number_of_past_purchases = Column(Integer, nullable=True)
    preferred_fuel_type = Column(String(50), nullable=True)
    preferred_vehicle_category = Column(String(50), nullable=True)
    customer_segment = Column(String(50), nullable=True)
    loyalty_score = Column(Float, nullable=True)
    marketing_response_score = Column(Float, nullable=True)
    lead_source = Column(String(50), nullable=True)
    email_opt_in = Column(Boolean, nullable=True)
    test_drive_taken = Column(Boolean, nullable=True)
    emi_preferred = Column(Boolean, nullable=True)                    # financing preferred (was: emi_preferred)
    down_payment_capacity_usd = Column(Integer, nullable=True)        # was: down_payment_capacity_aed
    registration_date = Column(Date, nullable=True)
    last_activity_date = Column(Date, nullable=True)
    churn_risk_score = Column(Float, nullable=True)

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
    price_usd = Column(Integer, nullable=True)                        # was: price_aed
    engine_cc = Column(Integer, nullable=True)
    horsepower = Column(Integer, nullable=True)
    mpg = Column(Float, nullable=True)                                # was: mileage_kmpl
    range_miles = Column(Integer, nullable=True)                      # was: range_km
    seating_capacity = Column(Integer, nullable=True)
    transmission = Column(String(50), nullable=True)
    drive_type = Column(String(50), nullable=True)
    body_color_options = Column(Integer, nullable=True)
    safety_rating = Column(Integer, nullable=True)
    launch_year = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=True)
    warranty_years = Column(Integer, nullable=True)
    service_contract_available = Column(Boolean, nullable=True)
    ev_incentive_eligible = Column(Boolean, nullable=True)            # was: gcc_spec (repurposed: federal EV tax credit eligibility)

    # Relationships
    sales = relationship("Sale", back_populates="vehicle")
    inventories = relationship("Inventory", back_populates="vehicle")


class Dealer(Base):
    __tablename__ = "dealers"

    dealer_id = Column(String(50), primary_key=True)
    dealer_name = Column(String(150), nullable=True)
    brand = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)                         # was: emirate
    city = Column(String(100), nullable=True)                         # was: area
    address = Column(String(250), nullable=True)
    zip_code = Column(String(20), nullable=True)                      # was: po_box
    tier = Column(String(50), nullable=True)
    established_year = Column(Integer, nullable=True)
    monthly_capacity = Column(Integer, nullable=True)
    showroom_area_sqft = Column(Integer, nullable=True)
    service_center = Column(Boolean, nullable=True)
    ev_charging_station = Column(Boolean, nullable=True)
    num_salespeople = Column(Integer, nullable=True)
    annual_target_units = Column(Integer, nullable=True)
    performance_score = Column(Float, nullable=True)
    google_rating = Column(Float, nullable=True)
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
    holiday_period = Column(String(100), nullable=True)               # was: festival_period

    customer_id = Column(String(50), ForeignKey("customers.customer_id"), nullable=True)
    dealer_id = Column(String(50), ForeignKey("dealers.dealer_id"), nullable=True)
    vehicle_id = Column(String(50), ForeignKey("vehicles.vehicle_id"), nullable=True)

    # Denormalized columns for fast analytical queries
    brand = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    vehicle_category = Column(String(50), nullable=True)
    fuel_type = Column(String(50), nullable=True)
    state = Column(String(50), nullable=True)                         # was: emirate
    city = Column(String(100), nullable=True)                         # was: area

    base_price_usd = Column(Integer, nullable=True)                   # was: base_price_aed
    discount_pct = Column(Float, nullable=True)
    selling_price_usd = Column(Integer, nullable=True)                # was: selling_price_aed
    sales_tax_amount_usd = Column(Integer, nullable=True)             # was: vat_amount_aed
    accessories_revenue_usd = Column(Integer, nullable=True)          # was: accessories_revenue_aed
    insurance_revenue_usd = Column(Integer, nullable=True)            # was: insurance_revenue_aed
    extended_warranty_usd = Column(Integer, nullable=True)            # was: extended_warranty_aed
    total_revenue_excl_tax = Column(Integer, nullable=True)           # was: total_revenue_excl_vat
    total_revenue_incl_tax = Column(Integer, nullable=True)           # was: total_revenue_incl_vat

    financing_type = Column(String(50), nullable=True)
    loan_amount_usd = Column(Integer, nullable=True)                  # was: loan_amount_aed
    units_sold = Column(Integer, default=1)
    test_drive_converted = Column(Boolean, nullable=True)
    lead_to_close_days = Column(Integer, nullable=True)
    salesperson_id = Column(String(50), nullable=True)
    marketing_channel = Column(String(100), nullable=True)
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
    state = Column(String(50), nullable=True)                         # was: emirate
    city = Column(String(100), nullable=True)                         # was: area

    current_stock = Column(Integer, nullable=True)
    demand_forecast_30d = Column(Integer, nullable=True)
    reorder_point = Column(Integer, nullable=True)
    days_in_stock = Column(Integer, nullable=True)
    stockout_flag = Column(Boolean, nullable=True)
    overstock_flag = Column(Boolean, nullable=True)
    reorder_needed = Column(Boolean, nullable=True)
    stockout_risk_score = Column(Float, nullable=True)
    overstock_risk_score = Column(Float, nullable=True)
    holding_cost_per_day_usd = Column(Float, nullable=True)           # was: holding_cost_per_day_aed
    estimated_holding_cost_usd = Column(Float, nullable=True)         # was: estimated_holding_cost_aed
    units_sold_last_30d = Column(Integer, nullable=True)
    units_ordered = Column(Integer, nullable=True)
    transit_stock = Column(Integer, nullable=True)
    port_of_entry = Column(String(100), nullable=True)
    warehouse_zone = Column(String(50), nullable=True)
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
    state = Column(String(50), nullable=True)                         # was: emirate

    # Fuel Prices (USD)
    gasoline_regular_usd_per_gallon = Column(Float, nullable=True)    # was: petrol_95_price_aed_per_litre
    gasoline_premium_usd_per_gallon = Column(Float, nullable=True)    # was: petrol_98_price_aed_per_litre
    diesel_usd_per_gallon = Column(Float, nullable=True)              # was: diesel_price_aed_per_litre
    wti_crude_price_usd = Column(Float, nullable=True)                # was: crude_oil_price_usd (Brent -> WTI benchmark)

    # Macro-economic
    gdp_growth_pct = Column(Float, nullable=True)
    cpi_inflation_pct = Column(Float, nullable=True)
    us_fed_rate_pct = Column(Float, nullable=True)
    consumer_confidence_index = Column(Float, nullable=True)
    tourism_index = Column(Float, nullable=True)
    home_price_index = Column(Float, nullable=True)                   # was: dubai_re_price_index
    luxury_demand_index = Column(Float, nullable=True)

    # Events / Seasonal flags
    holiday_season_month = Column(Integer, nullable=True)             # was: ramadan_month (Nov/Dec holiday shopping season)
    july_4th_month = Column(Integer, nullable=True)                   # was: national_day_month
    detroit_auto_show_month = Column(Integer, nullable=True)          # was: dubai_motor_show (NAIAS)
    la_auto_show_month = Column(Integer, nullable=True)               # was: abu_dhabi_motor_show

    # Industry
    new_model_launches = Column(Integer, nullable=True)
    tariff_pct = Column(Float, nullable=True)                         # was: import_duty_pct (Section 232 auto tariffs)
    avg_sales_tax_pct = Column(Float, nullable=True)                  # was: vat_rate_pct
    unemployment_rate_pct = Column(Float, nullable=True)
    population_millions = Column(Float, nullable=True)
    ev_charging_stations = Column(Integer, nullable=True)             # was: ev_charging_stations_uae


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
