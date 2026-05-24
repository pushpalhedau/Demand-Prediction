from sqlalchemy import Column, String, Integer, Float, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database.connection import Base

class Customer(Base):
    __tablename__ = "customers"
    
    customer_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    city = Column(String(100), nullable=True)
    region = Column(String(50), nullable=True)
    state = Column(String(100), nullable=True)
    occupation = Column(String(100), nullable=True)
    annual_income_bracket = Column(String(50), nullable=True)
    estimated_annual_income = Column(Float, nullable=True)
    credit_score = Column(Integer, nullable=True)
    number_of_past_purchases = Column(Integer, nullable=True)
    preferred_fuel_type = Column(String(50), nullable=True)
    preferred_vehicle_category = Column(String(50), nullable=True)
    customer_segment = Column(String(50), nullable=True)
    loyalty_score = Column(Float, nullable=True)
    marketing_response_score = Column(Float, nullable=True)
    lead_source = Column(String(50), nullable=True)
    email_opt_in = Column(Boolean, nullable=True)
    whatsapp_opted = Column(Boolean, nullable=True)
    test_drive_taken = Column(Boolean, nullable=True)
    emi_preferred = Column(Boolean, nullable=True)
    down_payment_capacity = Column(Integer, nullable=True)
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
    ex_showroom_price = Column(Integer, nullable=True)
    engine_cc = Column(Integer, nullable=True)
    mileage_kmpl = Column(Float, nullable=True)
    range_km = Column(Integer, nullable=True)
    seating_capacity = Column(Integer, nullable=True)
    transmission = Column(String(50), nullable=True)
    body_color_options = Column(Integer, nullable=True)
    safety_rating = Column(Integer, nullable=True)
    launch_year = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=True)
    ev_subsidy_eligible = Column(Boolean, nullable=True)
    warranty_years = Column(Integer, nullable=True)
    
    # Relationships
    sales = relationship("Sale", back_populates="vehicle")
    inventories = relationship("Inventory", back_populates="vehicle")


class Dealer(Base):
    __tablename__ = "dealers"
    
    dealer_id = Column(String(50), primary_key=True)
    dealer_name = Column(String(150), nullable=True)
    brand = Column(String(100), nullable=True)
    region = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    address = Column(String(250), nullable=True)
    pincode = Column(String(20), nullable=True)
    tier = Column(String(50), nullable=True)
    established_year = Column(Integer, nullable=True)
    monthly_capacity = Column(Integer, nullable=True)
    showroom_area_sqft = Column(Integer, nullable=True)
    service_center = Column(Boolean, nullable=True)
    ev_charging_station = Column(Boolean, nullable=True)
    num_salespeople = Column(Integer, nullable=True)
    annual_target_units = Column(Integer, nullable=True)
    performance_score = Column(Float, nullable=True)
    rating = Column(Float, nullable=True)
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
    
    # Denormalized columns for high speed analytical queries
    brand = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    vehicle_category = Column(String(50), nullable=True)
    fuel_type = Column(String(50), nullable=True)
    region = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    
    base_price = Column(Integer, nullable=True)
    discount_pct = Column(Float, nullable=True)
    selling_price = Column(Integer, nullable=True)
    accessories_revenue = Column(Integer, nullable=True)
    insurance_revenue = Column(Integer, nullable=True)
    extended_warranty = Column(Integer, nullable=True)
    total_revenue = Column(Integer, nullable=True)
    
    financing_type = Column(String(50), nullable=True)
    loan_amount = Column(Integer, nullable=True)
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
    region = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    
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
    warehouse_location = Column(String(50), nullable=True)
    last_replenishment_date = Column(Date, nullable=True)
    supplier_lead_time_days = Column(Integer, nullable=True)
    
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
    region = Column(String(50), nullable=True)
    petrol_price_per_litre = Column(Float, nullable=True)
    diesel_price_per_litre = Column(Float, nullable=True)
    gdp_growth_pct = Column(Float, nullable=True)
    cpi_inflation_pct = Column(Float, nullable=True)
    rbi_repo_rate_pct = Column(Float, nullable=True)
    consumer_confidence_index = Column(Float, nullable=True)
    auto_industry_index = Column(Float, nullable=True)
    semiconductor_shortage = Column(Integer, nullable=True)
    ev_subsidy_active = Column(Integer, nullable=True)
    ev_subsidy_amount_per_vehicle = Column(Integer, nullable=True)
    steel_price_per_ton = Column(Float, nullable=True)
    usd_inr_rate = Column(Float, nullable=True)
    festival_month = Column(Integer, nullable=True)
    festival_name = Column(String(100), nullable=True)
    unemployment_rate_pct = Column(Float, nullable=True)
    new_model_launches = Column(Integer, nullable=True)
    government_infra_spend_bn = Column(Float, nullable=True)
    registration_tax_pct = Column(Float, nullable=True)
    road_cess_pct = Column(Float, nullable=True)
