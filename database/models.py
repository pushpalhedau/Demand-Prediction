from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from database.connection import Base


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String(50), primary_key=True)
    transaction_date = Column(Date, nullable=False, index=True)
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    quarter = Column(String(10), nullable=True)
    day_of_week = Column(String(20), nullable=True)
    is_ramadan_period = Column(Boolean, nullable=True)
    market_event = Column(String(200), nullable=True)

    buyer_id = Column(String(50), ForeignKey("buyers.buyer_id"), nullable=True)
    developer_id = Column(String(50), ForeignKey("developers.developer_id"), nullable=True)
    property_id = Column(String(50), ForeignKey("properties.property_id"), nullable=True)

    project_name = Column(String(200), nullable=True)
    property_type = Column(String(100), nullable=True)
    property_category = Column(String(100), nullable=True)
    bedrooms = Column(String(20), nullable=True)
    completion_status = Column(String(50), nullable=True)
    possession_year = Column(Integer, nullable=True)
    emirate = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    locality = Column(String(150), nullable=True)
    region = Column(String(50), nullable=True)

    area_sqft = Column(Float, nullable=True)
    base_price_aed = Column(Integer, nullable=True)
    price_per_sqft_aed = Column(Float, nullable=True)
    discount_pct = Column(Float, nullable=True)
    selling_price_aed = Column(Integer, nullable=True)
    dld_transfer_fee_aed = Column(Integer, nullable=True)
    agency_commission_aed = Column(Integer, nullable=True)
    vat_amount_aed = Column(Integer, nullable=True)
    service_charge_annual_aed = Column(Integer, nullable=True)
    total_transaction_value_aed = Column(Integer, nullable=True)

    payment_plan = Column(String(100), nullable=True)
    mortgage_amount_aed = Column(Integer, nullable=True)
    booking_amount_aed = Column(Integer, nullable=True)
    golden_visa_eligible = Column(Boolean, nullable=True)
    lead_to_close_days = Column(Integer, nullable=True)
    salesperson_id = Column(String(50), nullable=True)
    marketing_channel = Column(String(100), nullable=True)
    booking_converted = Column(Boolean, nullable=True)
    season_multiplier = Column(Float, nullable=True)
    freehold = Column(Boolean, nullable=True)

    buyer = relationship("Buyer", back_populates="transactions")
    developer = relationship("Developer", back_populates="transactions")
    property = relationship("Property", back_populates="transactions")


class Buyer(Base):
    __tablename__ = "buyers"

    buyer_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    nationality = Column(String(100), nullable=True)
    residence_city = Column(String(100), nullable=True)
    emirate = Column(String(100), nullable=True)
    occupation = Column(String(100), nullable=True)
    annual_income_bracket = Column(String(50), nullable=True)
    estimated_annual_income_aed = Column(Float, nullable=True)
    buyer_type = Column(String(50), nullable=True)
    expat_status = Column(Boolean, nullable=True)
    years_in_uae = Column(Float, nullable=True)
    number_of_past_purchases = Column(Integer, nullable=True)
    preferred_property_type = Column(String(100), nullable=True)
    preferred_property_category = Column(String(100), nullable=True)
    preferred_city = Column(String(100), nullable=True)
    preferred_locality = Column(String(150), nullable=True)
    preferred_bedrooms = Column(String(20), nullable=True)
    budget_min_aed = Column(Integer, nullable=True)
    budget_max_aed = Column(Integer, nullable=True)
    customer_segment = Column(String(100), nullable=True)
    golden_visa_intent = Column(Boolean, nullable=True)
    off_plan_preference = Column(Boolean, nullable=True)
    loyalty_score = Column(Float, nullable=True)
    marketing_response_score = Column(Float, nullable=True)
    lead_source = Column(String(100), nullable=True)
    email_opt_in = Column(Boolean, nullable=True)
    whatsapp_opted = Column(Boolean, nullable=True)
    site_visit_taken = Column(Boolean, nullable=True)
    mortgage_preferred = Column(Boolean, nullable=True)
    down_payment_capacity_aed = Column(Integer, nullable=True)
    registration_date = Column(Date, nullable=True)
    last_activity_date = Column(Date, nullable=True)
    churn_risk_score = Column(Float, nullable=True)

    transactions = relationship("Transaction", back_populates="buyer")


class Developer(Base):
    __tablename__ = "developers"

    developer_id = Column(String(50), primary_key=True)
    developer_name = Column(String(200), nullable=True)
    developer_type = Column(String(100), nullable=True)
    primary_city = Column(String(100), nullable=True)
    operating_cities = Column(String(500), nullable=True)
    emirate = Column(String(100), nullable=True)
    address = Column(String(500), nullable=True)
    tier = Column(String(50), nullable=True)
    established_year = Column(Integer, nullable=True)
    rera_registration_no = Column(String(100), nullable=True)
    rera_registered = Column(Boolean, nullable=True)
    adm_registered = Column(Boolean, nullable=True)
    monthly_capacity_units = Column(Integer, nullable=True)
    office_area_sqft = Column(Integer, nullable=True)
    num_agents = Column(Integer, nullable=True)
    annual_target_units = Column(Integer, nullable=True)
    performance_score = Column(Float, nullable=True)
    rating = Column(Float, nullable=True)
    total_projects_launched = Column(Integer, nullable=True)
    active_projects = Column(Integer, nullable=True)
    completed_projects = Column(Integer, nullable=True)
    specialization = Column(String(100), nullable=True)
    off_plan_focus = Column(Boolean, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    transactions = relationship("Transaction", back_populates="developer")
    listings = relationship("Listing", back_populates="developer")


class Property(Base):
    __tablename__ = "properties"

    property_id = Column(String(50), primary_key=True)
    project_name = Column(String(200), nullable=True)
    developer_id = Column(String(50), ForeignKey("developers.developer_id"), nullable=True)
    dld_permit_no = Column(String(100), nullable=True)
    property_type = Column(String(100), nullable=True)
    property_category = Column(String(100), nullable=True)
    bedrooms = Column(String(20), nullable=True)
    bathrooms = Column(Integer, nullable=True)
    carpet_area_sqft_min = Column(Float, nullable=True)
    carpet_area_sqft_max = Column(Float, nullable=True)
    builtup_area_sqft = Column(Float, nullable=True)
    base_price_aed = Column(Integer, nullable=True)
    price_per_sqft_aed = Column(Float, nullable=True)
    emirate = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    locality = Column(String(150), nullable=True)
    region = Column(String(50), nullable=True)
    total_floors = Column(Integer, nullable=True)
    parking_spaces = Column(Integer, nullable=True)
    amenities_score = Column(Float, nullable=True)
    completion_status = Column(String(50), nullable=True)
    launch_year = Column(Integer, nullable=True)
    possession_year = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=True)
    freehold = Column(Boolean, nullable=True)
    leasehold_years = Column(Integer, nullable=True)
    service_charge_aed_sqft = Column(Float, nullable=True)
    rental_yield_pct = Column(Float, nullable=True)
    capital_appreciation_pct = Column(Float, nullable=True)
    roi_pct = Column(Float, nullable=True)
    golden_visa_eligible = Column(Boolean, nullable=True)
    vat_applicable = Column(Boolean, nullable=True)

    transactions = relationship("Transaction", back_populates="property")


class Listing(Base):
    __tablename__ = "listings"

    listing_id = Column(String(50), primary_key=True)
    record_date = Column(Date, nullable=False, index=True)
    developer_id = Column(String(50), ForeignKey("developers.developer_id"), nullable=True)
    property_id = Column(String(50), nullable=True)
    project_name = Column(String(200), nullable=True)
    dld_permit_no = Column(String(100), nullable=True)
    property_type = Column(String(100), nullable=True)
    property_category = Column(String(100), nullable=True)
    bedrooms = Column(String(20), nullable=True)
    completion_status = Column(String(50), nullable=True)
    construction_progress_pct = Column(Float, nullable=True)
    possession_date = Column(Date, nullable=True)
    emirate = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    locality = Column(String(150), nullable=True)
    total_units_in_project = Column(Integer, nullable=True)
    available_units = Column(Integer, nullable=True)
    booked_units = Column(Integer, nullable=True)
    registered_units = Column(Integer, nullable=True)
    demand_forecast_30d = Column(Integer, nullable=True)
    booking_threshold = Column(Integer, nullable=True)
    days_on_market = Column(Integer, nullable=True)
    unsold_flag = Column(Boolean, nullable=True)
    slow_moving_flag = Column(Boolean, nullable=True)
    overlaunch_flag = Column(Boolean, nullable=True)
    stockout_risk_score = Column(Float, nullable=True)
    holding_cost_per_day_aed = Column(Float, nullable=True)
    estimated_holding_cost_aed = Column(Float, nullable=True)
    units_sold_last_30d = Column(Integer, nullable=True)
    units_launched_this_month = Column(Integer, nullable=True)
    rental_income_potential_aed = Column(Integer, nullable=True)
    last_price_revision_date = Column(Date, nullable=True)
    golden_visa_threshold_met = Column(Boolean, nullable=True)
    off_plan_flag = Column(Boolean, nullable=True)

    developer = relationship("Developer", back_populates="listings")


class MarketFactor(Base):
    __tablename__ = "market_factors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    quarter = Column(String(10), nullable=True)
    city = Column(String(100), nullable=True)
    emirate = Column(String(100), nullable=True)

    uae_central_bank_base_rate_pct = Column(Float, nullable=True)
    mortgage_rate_avg_pct = Column(Float, nullable=True)
    oil_price_usd_bbl = Column(Float, nullable=True)
    gdp_growth_pct = Column(Float, nullable=True)
    cpi_inflation_pct = Column(Float, nullable=True)
    consumer_confidence_index = Column(Float, nullable=True)
    real_estate_price_index = Column(Float, nullable=True)
    transaction_volume_index = Column(Float, nullable=True)
    rental_yield_avg_pct = Column(Float, nullable=True)
    new_project_launches = Column(Integer, nullable=True)
    total_inventory_units = Column(Integer, nullable=True)
    unsold_inventory_units = Column(Integer, nullable=True)
    steel_price_per_ton_aed = Column(Float, nullable=True)
    construction_cost_index = Column(Float, nullable=True)
    usd_aed_rate = Column(Float, nullable=True)
    tourism_arrivals_index = Column(Float, nullable=True)
    foreign_investment_inflow_bn_aed = Column(Float, nullable=True)
    institutional_investment_bn_aed = Column(Float, nullable=True)
    reit_activity_index = Column(Float, nullable=True)
    golden_visa_applications = Column(Integer, nullable=True)
    off_plan_sales_share_pct = Column(Float, nullable=True)
    dld_transactions_count = Column(Integer, nullable=True)
    expo_effect = Column(Integer, nullable=True)
    ramadan_month = Column(Integer, nullable=True)
    market_event = Column(String(200), nullable=True)
    event_demand_multiplier = Column(Float, nullable=True)
    vat_rate_pct = Column(Float, nullable=True)
    property_registration_fee_pct = Column(Float, nullable=True)


class NewsArticle(Base):
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

    sentiment_signal = relationship("SentimentSignal", back_populates="article", uselist=False)


class SentimentSignal(Base):
    __tablename__ = "sentiment_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("news_articles.id"), nullable=False, unique=True)
    analyzed_at = Column(DateTime, nullable=False)

    sentiment_score = Column(Float, nullable=True)
    impact_score = Column(Float, nullable=True)
    affected_property_category = Column(String(100), nullable=True)
    economic_risk = Column(String(20), nullable=True)
    demand_direction = Column(String(10), nullable=True)
    estimated_demand_change_pct = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)

    article = relationship("NewsArticle", back_populates="sentiment_signal")


class DailySentimentSummary(Base):
    __tablename__ = "daily_sentiment_summary"
    __table_args__ = (
        UniqueConstraint("summary_date", "property_category", name="uq_daily_sentiment"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    summary_date = Column(Date, nullable=False, index=True)
    property_category = Column(String(100), nullable=True)

    avg_sentiment_score = Column(Float, nullable=True)
    avg_impact_score = Column(Float, nullable=True)
    avg_demand_change_pct = Column(Float, nullable=True)
    geopolitical_risk_score = Column(Float, nullable=True)

    positive_signals = Column(Integer, nullable=True)
    negative_signals = Column(Integer, nullable=True)
    neutral_signals = Column(Integer, nullable=True)
    total_articles = Column(Integer, nullable=True)
    dominant_demand_direction = Column(String(10), nullable=True)

    computed_at = Column(DateTime, nullable=False)
