from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from database.connection import Base


# ─────────────────────────────────────────────────────────────────────────────
# German (Bundesland) schema.
#
# Canonical values in this database are ENGLISH ("Estate", "Petrol", "Private").
# The German UI translates them at the render boundary only — never before a
# filter or a groupby, or the comparison silently matches nothing. See
# utils/i18n.py VALUE_MAP.
#
# Units follow German market convention: EUR, kW (not hp), l/100km (NOT km/l —
# LOWER IS BETTER, the opposite of the UAE build's mileage_kmpl), km, g CO2/km.
# ─────────────────────────────────────────────────────────────────────────────


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    # ~15% of German residents hold a non-German nationality (Turkish, Polish,
    # Romanian, Italian, Syrian and Croatian communities being the largest), so
    # the field carries some descriptive signal. It is surfaced ONLY as a
    # descriptive mix in Customer Intelligence and is deliberately kept OUT of
    # the per-lead XGBoost close score: scoring an individual on nationality is
    # a direct AGG (Allgemeines Gleichbehandlungsgesetz) exposure with no
    # defensible predictive justification. KMeans uses years_at_address for
    # tenure instead.
    nationality = Column(String(100), nullable=True)
    # "Private" (Privat) or "Commercial" (Gewerblich). ~60-65% of German new
    # registrations are commercial — fleet, company car, Dienstwagen under the
    # 1%-Regelung — so this is a first-class structural dimension here, not a
    # footnote.
    customer_type = Column(String(20), nullable=True)
    state = Column(String(50), nullable=True)                         # Bundesland
    city = Column(String(100), nullable=True)
    postal_code = Column(String(10), nullable=True)                   # PLZ, 5-digit
    occupation = Column(String(100), nullable=True)
    annual_income_bracket = Column(String(50), nullable=True)
    estimated_annual_income_eur = Column(Float, nullable=True)        # Bruttojahreseinkommen
    schufa_score = Column(Integer, nullable=True)                     # SCHUFA basis score, 0-100
    years_at_address = Column(Integer, nullable=True)
    number_of_past_purchases = Column(Integer, nullable=True)
    preferred_fuel_type = Column(String(50), nullable=True)
    preferred_vehicle_category = Column(String(50), nullable=True)
    customer_segment = Column(String(50), nullable=True)
    loyalty_score = Column(Float, nullable=True)
    marketing_response_score = Column(Float, nullable=True)
    lead_source = Column(String(50), nullable=True)
    email_opt_in = Column(Boolean, nullable=True)
    test_drive_taken = Column(Boolean, nullable=True)
    financing_preferred = Column(Boolean, nullable=True)              # prefers instalment / balloon over cash
    down_payment_capacity_eur = Column(Integer, nullable=True)
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
    price_eur = Column(Integer, nullable=True)                        # Listenpreis, incl. 19% USt
    engine_cc = Column(Integer, nullable=True)
    power_kw = Column(Integer, nullable=True)                         # kW (German spec leads with kW, PS in brackets)
    # Combined consumption, l/100km. LOWER IS BETTER — every comparison,
    # sort and "better substitute" test on this column runs the opposite
    # direction to the UAE build's km-per-litre field.
    consumption_l_per_100km = Column(Float, nullable=True)
    consumption_kwh_per_100km = Column(Float, nullable=True)          # BEV/PHEV electric consumption
    range_km = Column(Integer, nullable=True)                         # WLTP range (BEV)
    co2_g_per_km = Column(Integer, nullable=True)                     # WLTP; drives Kfz-Steuer
    emission_class = Column(String(20), nullable=True)                # Euro 6d / Euro 6e / BEV
    annual_vehicle_tax_eur = Column(Integer, nullable=True)           # Kfz-Steuer (CO2 + displacement based)
    seating_capacity = Column(Integer, nullable=True)
    transmission = Column(String(50), nullable=True)                  # Manual / Automatic / DSG
    drive_type = Column(String(50), nullable=True)
    body_color_options = Column(Integer, nullable=True)
    safety_rating = Column(Integer, nullable=True)                    # Euro NCAP stars
    launch_year = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=True)
    warranty_years = Column(Integer, nullable=True)                   # Herstellergarantie
    service_contract_available = Column(Boolean, nullable=True)       # Wartungsvertrag
    # "Domestic" for German-built (Wolfsburg, Zwickau, Ingolstadt, Sindelfingen,
    # Regensburg …) or "Import". Drives logistics lead time only — there is no
    # tariff / duty analysis in this build.
    origin = Column(String(20), nullable=True)

    # Share of list price retained at 36-month maturity. Drives lease residual
    # pricing and the return-equity model.
    residual_value_36mo = Column(Float, nullable=True)

    # Relationships
    sales = relationship("Sale", back_populates="vehicle")
    inventories = relationship("Inventory", back_populates="vehicle")


class Dealer(Base):
    __tablename__ = "dealers"

    dealer_id = Column(String(50), primary_key=True)
    dealer_name = Column(String(150), nullable=True)
    brand = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)                         # Bundesland
    city = Column(String(100), nullable=True)
    address = Column(String(250), nullable=True)
    postal_code = Column(String(10), nullable=True)                   # PLZ
    tier = Column(String(50), nullable=True)
    established_year = Column(Integer, nullable=True)
    monthly_capacity = Column(Integer, nullable=True)
    showroom_area_sqm = Column(Integer, nullable=True)
    service_center = Column(Boolean, nullable=True)                   # Meisterwerkstatt
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
    # Year End / Quarter End / Easter / Summer Holidays / IAA / New Year —
    # the German retail calendar. Canonical English, translated at render.
    season_period = Column(String(100), nullable=True)

    customer_id = Column(String(50), ForeignKey("customers.customer_id"), nullable=True)
    dealer_id = Column(String(50), ForeignKey("dealers.dealer_id"), nullable=True)
    vehicle_id = Column(String(50), ForeignKey("vehicles.vehicle_id"), nullable=True)

    # Denormalized columns for fast analytical queries
    brand = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    vehicle_category = Column(String(50), nullable=True)
    fuel_type = Column(String(50), nullable=True)
    state = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    customer_type = Column(String(20), nullable=True)                 # Private / Commercial
    is_fleet = Column(Boolean, nullable=True)                         # multi-unit fleet order

    base_price_eur = Column(Integer, nullable=True)
    discount_pct = Column(Float, nullable=True)
    selling_price_eur = Column(Integer, nullable=True)
    vat_amount_eur = Column(Integer, nullable=True)                   # 19% Umsatzsteuer
    accessories_revenue_eur = Column(Integer, nullable=True)
    insurance_revenue_eur = Column(Integer, nullable=True)
    extended_warranty_eur = Column(Integer, nullable=True)            # Anschlussgarantie
    total_revenue_excl_vat = Column(Integer, nullable=True)           # netto
    total_revenue_incl_vat = Column(Integer, nullable=True)           # brutto

    # Cash / Bank Loan / Dealer Financing / Balloon Financing / Lease.
    # "Balloon Financing" is the German Drei-Wege-/Schlussratenfinanzierung;
    # together with Lease it dominates German retail, unlike the cash-heavy Gulf.
    financing_type = Column(String(50), nullable=True)
    loan_amount_eur = Column(Integer, nullable=True)
    units_sold = Column(Integer, default=1)
    test_drive_converted = Column(Boolean, nullable=True)
    lead_to_close_days = Column(Integer, nullable=True)
    salesperson_id = Column(String(50), nullable=True)
    marketing_channel = Column(String(100), nullable=True)
    season_multiplier = Column(Float, nullable=True)

    # ── Lease contract terms (populated only when financing_type == "Lease") ──
    lease_term_months = Column(Integer, nullable=True)
    lease_maturity_date = Column(Date, nullable=True, index=True)
    residual_value_pct = Column(Float, nullable=True)        # share of list price at maturity
    residual_value_eur = Column(Integer, nullable=True)      # contractual buyout price
    contract_mileage_allowance = Column(Integer, nullable=True)  # total km over the term
    lease_monthly_payment_eur = Column(Integer, nullable=True)

    # ── Trade-in activity (Inzahlungnahme) ───────────────────────────────────
    trade_in_flag = Column(Boolean, nullable=True)
    trade_in_brand = Column(String(100), nullable=True)
    trade_in_model = Column(String(100), nullable=True)
    trade_in_year = Column(Integer, nullable=True)
    trade_in_mileage = Column(Integer, nullable=True)                # km
    trade_in_appraised_value_eur = Column(Integer, nullable=True)
    trade_in_allowance_eur = Column(Integer, nullable=True)
    trade_in_over_allowance_eur = Column(Integer, nullable=True)     # allowance - appraised
    trade_bonus_eur = Column(Integer, nullable=True)                 # promotional incentive

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
    state = Column(String(50), nullable=True)
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
    holding_cost_per_day_eur = Column(Float, nullable=True)
    estimated_holding_cost_eur = Column(Float, nullable=True)
    units_sold_last_30d = Column(Integer, nullable=True)
    units_ordered = Column(Integer, nullable=True)
    transit_stock = Column(Integer, nullable=True)
    # German plant (Wolfsburg, Zwickau, Ingolstadt …) for domestic build, or a
    # vehicle port (Bremerhaven, Emden, Cuxhaven) for imports. Domestic build
    # runs materially shorter lead times.
    origin_hub = Column(String(100), nullable=True)
    warehouse_zone = Column(String(50), nullable=True)
    last_replenishment_date = Column(Date, nullable=True)
    supplier_lead_time_days = Column(Integer, nullable=True)
    # EU-built stock is always cleared; only non-EU imports (Korean, Japanese,
    # Chinese build) can sit uncleared. No duty analysis is derived from this.
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
    state = Column(String(50), nullable=True)

    # Fuel prices (EUR/litre) — German pump prices incl. Energiesteuer and the
    # national CO2 price. Note the Tankrabatt window (Jun-Aug 2022).
    super_e10_price_eur_per_litre = Column(Float, nullable=True)
    super_e5_price_eur_per_litre = Column(Float, nullable=True)
    diesel_price_eur_per_litre = Column(Float, nullable=True)
    electricity_price_eur_per_kwh = Column(Float, nullable=True)      # household rate — BEV running cost
    crude_oil_price_usd = Column(Float, nullable=True)                # Brent benchmark (quoted in USD globally)

    # Macro-economic
    gdp_growth_pct = Column(Float, nullable=True)
    cpi_inflation_pct = Column(Float, nullable=True)
    ecb_rate_pct = Column(Float, nullable=True)                       # ECB main refinancing rate
    auto_loan_apr_pct = Column(Float, nullable=True)                  # policy rate + new-car spread; effektiver Jahreszins
    incentive_pct_of_atp = Column(Float, nullable=True)              # manufacturer + dealer incentive spend as a share of transaction price
    inventory_days_supply = Column(Float, nullable=True)             # new-vehicle days' supply on the group's lots
    consumer_confidence_index = Column(Float, nullable=True)          # GfK Konsumklima
    ifo_business_climate = Column(Float, nullable=True)               # ifo Geschäftsklimaindex
    de_house_price_index = Column(Float, nullable=True)               # German residential price index
    luxury_demand_index = Column(Float, nullable=True)
    # Share of new registrations that are commercial (gewerblich) rather than
    # private — the structural backbone of German new-car demand.
    commercial_registration_share_pct = Column(Float, nullable=True)

    # Events / Seasonal flags
    quarter_end_month = Column(Integer, nullable=True)                # Mar / Jun / Sep / Dec registration push
    year_end_month = Column(Integer, nullable=True)                   # December
    summer_holiday_month = Column(Integer, nullable=True)             # Sommerferien lull
    iaa_month = Column(Integer, nullable=True)                        # IAA Mobility, Munich (September, biennial)

    # Industry / policy
    new_model_launches = Column(Integer, nullable=True)
    vat_rate_pct = Column(Float, nullable=True)                       # 19% Umsatzsteuer (16% in the H2-2020 cut)
    co2_price_eur_per_tonne = Column(Float, nullable=True)            # national CO2 price (nEHS), from 2021
    # Umweltbonus BEV purchase subsidy. Ran to EUR 6,000 federal share, then
    # was cut abruptly to zero in December 2023 — the single sharpest demand
    # shock in this window and the anchor story for the forecasting tab.
    ev_subsidy_eur = Column(Integer, nullable=True)
    unemployment_rate_pct = Column(Float, nullable=True)
    population_millions = Column(Float, nullable=True)
    ev_charging_points_de = Column(Integer, nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# Sentiment Analysis Tables
# ─────────────────────────────────────────────────────────────────────────────

class NewsArticle(Base):
    """Raw articles fetched from Google News RSS (German-language, gl=DE)."""
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
    affected_vehicle_category = Column(String(100), nullable=True)  # SUV, EV, Luxury, Estate, All, etc.
    economic_risk = Column(String(20), nullable=True)          # low | medium | high
    demand_direction = Column(String(10), nullable=True)       # up | down | neutral
    estimated_demand_change_pct = Column(Float, nullable=True) # e.g. +3.5 or -2.1
    confidence = Column(Float, nullable=True)                  # 0.0 to 1.0
    summary = Column(Text, nullable=True)                      # one-sentence Grok summary (English)
    summary_de = Column(Text, nullable=True)                   # German rendering for the DE toggle
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
