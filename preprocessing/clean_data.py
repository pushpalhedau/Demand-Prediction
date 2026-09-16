import pandas as pd
import numpy as np


def clean_customers(filepath):
    """
    Clean customers.csv dataset (German schema).
    """
    df = pd.read_csv(filepath)

    # Identity
    df['name'] = df['name'].fillna("Unknown Customer")
    df['age'] = df['age'].fillna(df['age'].median())
    df['gender'] = df['gender'].fillna("Other")
    df['nationality'] = df['nationality'].fillna("Unknown")
    df['customer_type'] = df['customer_type'].fillna("Private")
    df['state'] = df['state'].fillna("Nordrhein-Westfalen")
    df['city'] = df['city'].fillna("Unknown")
    df['postal_code'] = df['postal_code'].astype(str).str.zfill(5).replace("00nan", None)
    df['occupation'] = df['occupation'].fillna("Salaried Employee")
    df['years_at_address'] = df['years_at_address'].fillna(df['years_at_address'].median()).astype(int)

    # Financial fields
    df['annual_income_bracket'] = df['annual_income_bracket'].fillna("Unknown")
    df['estimated_annual_income_eur'] = df['estimated_annual_income_eur'].fillna(
        df['estimated_annual_income_eur'].median()
    )
    df['schufa_score'] = df['schufa_score'].fillna(df['schufa_score'].median())
    df['down_payment_capacity_eur'] = df['down_payment_capacity_eur'].fillna(0)

    # Booleans
    df['email_opt_in'] = df['email_opt_in'].fillna(False).astype(bool)
    df['test_drive_taken'] = df['test_drive_taken'].fillna(False).astype(bool)
    df['financing_preferred'] = df['financing_preferred'].fillna(False).astype(bool)

    # Dates
    df['registration_date'] = pd.to_datetime(df['registration_date']).dt.date
    df['last_activity_date'] = pd.to_datetime(df['last_activity_date']).dt.date

    # Numeric scores
    df['loyalty_score'] = df['loyalty_score'].fillna(50.0)
    df['marketing_response_score'] = df['marketing_response_score'].fillna(5.0)
    df['churn_risk_score'] = df['churn_risk_score'].fillna(0.5)
    df['number_of_past_purchases'] = df['number_of_past_purchases'].fillna(0).astype(int)

    return df


def clean_vehicles(filepath):
    """
    Clean vehicles.csv dataset (German schema).
    """
    df = pd.read_csv(filepath)

    # Strings
    df['brand'] = df['brand'].fillna("Unknown")
    df['model'] = df['model'].fillna("Unknown")
    df['variant'] = df['variant'].fillna("Basis")
    df['category'] = df['category'].fillna("Compact")
    df['fuel_type'] = df['fuel_type'].fillna("Petrol")
    df['transmission'] = df['transmission'].fillna("Manual")
    df['drive_type'] = df['drive_type'].fillna("FWD")
    df['emission_class'] = df['emission_class'].fillna("Euro 6d")
    df['origin'] = df['origin'].fillna("Import")

    # Pricing (EUR, Listenpreis incl. USt)
    df['price_eur'] = df['price_eur'].fillna(0).astype(int)

    # Technical specs. These stay NULL where the drivetrain has no such figure:
    # an ICE car has no kWh/100km or WLTP range, a BEV has no engine size or
    # l/100km. Filling either with a zero would make a BEV look like the most
    # economical petrol car on the lot.
    df['engine_cc'] = df['engine_cc'].apply(lambda x: int(x) if pd.notnull(x) else None)
    df['power_kw'] = df['power_kw'].apply(lambda x: int(x) if pd.notnull(x) else None)
    df['consumption_l_per_100km'] = df['consumption_l_per_100km'].apply(
        lambda x: float(x) if pd.notnull(x) else None
    )
    df['consumption_kwh_per_100km'] = df['consumption_kwh_per_100km'].apply(
        lambda x: float(x) if pd.notnull(x) else None
    )
    df['range_km'] = df['range_km'].apply(lambda x: int(x) if pd.notnull(x) else None)
    df['co2_g_per_km'] = df['co2_g_per_km'].apply(lambda x: int(x) if pd.notnull(x) else None)
    df['annual_vehicle_tax_eur'] = df['annual_vehicle_tax_eur'].fillna(0).astype(int)

    # Standard numbers
    df['seating_capacity'] = df['seating_capacity'].fillna(5).astype(int)
    df['body_color_options'] = df['body_color_options'].fillna(1).astype(int)
    df['safety_rating'] = df['safety_rating'].fillna(3).astype(int)
    df['launch_year'] = df['launch_year'].fillna(2020).astype(int)
    # German statutory Gewährleistung is two years, so that is the honest
    # fallback rather than the Gulf build's three.
    df['warranty_years'] = df['warranty_years'].fillna(2).astype(int)

    # Flags
    df['is_active'] = df['is_active'].fillna(True).astype(bool)
    df['service_contract_available'] = df['service_contract_available'].fillna(False).astype(bool)

    # Residual curve. Falls back to the market-average 36-month residual so a
    # catalog without the column still prices leases sanely.
    if 'residual_value_36mo' in df.columns:
        df['residual_value_36mo'] = df['residual_value_36mo'].fillna(0.48).astype(float)
    else:
        df['residual_value_36mo'] = 0.48

    return df


def clean_dealers(filepath):
    """
    Clean dealers.csv dataset (German schema).
    """
    df = pd.read_csv(filepath)

    # Strings
    df['dealer_name'] = df['dealer_name'].fillna("Unbekanntes Autohaus")
    df['brand'] = df['brand'].fillna("Unknown")
    df['state'] = df['state'].fillna("Nordrhein-Westfalen")
    df['city'] = df['city'].fillna("Unknown")
    df['postal_code'] = df['postal_code'].astype(str).str.zfill(5).replace("00nan", None)
    df['tier'] = df['tier'].fillna("Silver")

    # Numeric
    df['established_year'] = df['established_year'].fillna(1995).astype(int)
    df['monthly_capacity'] = df['monthly_capacity'].fillna(df['monthly_capacity'].median()).astype(int)
    df['showroom_area_sqm'] = df['showroom_area_sqm'].fillna(df['showroom_area_sqm'].median()).astype(int)
    df['num_salespeople'] = df['num_salespeople'].fillna(df['num_salespeople'].median()).astype(int)
    df['annual_target_units'] = df['annual_target_units'].fillna(df['annual_target_units'].median()).astype(int)

    # Flags
    df['service_center'] = df['service_center'].fillna(False).astype(bool)
    df['ev_charging_station'] = df['ev_charging_station'].fillna(False).astype(bool)

    # Scores
    df['performance_score'] = df['performance_score'].fillna(df['performance_score'].median())
    df['google_rating'] = df['google_rating'].fillna(df['google_rating'].median())

    # Geo
    df['latitude'] = df['latitude'].fillna(0.0)
    df['longitude'] = df['longitude'].fillna(0.0)

    return df


def clean_sales(filepath):
    """
    Clean sales.csv dataset (German schema).
    """
    df = pd.read_csv(filepath)

    # Dates
    df['sale_date'] = pd.to_datetime(df['sale_date']).dt.date
    df['year'] = df['year'].fillna(pd.to_datetime(df['sale_date']).dt.year).astype(int)
    df['month'] = df['month'].fillna(pd.to_datetime(df['sale_date']).dt.month).astype(int)

    # Strings
    df['quarter'] = df['quarter'].fillna("Q1")
    df['day_of_week'] = df['day_of_week'].fillna("Monday")
    df['season_period'] = df['season_period'].fillna("None")
    df['brand'] = df['brand'].fillna("Unknown")
    df['model'] = df['model'].fillna("Unknown")
    df['vehicle_category'] = df['vehicle_category'].fillna("Compact")
    df['fuel_type'] = df['fuel_type'].fillna("Petrol")
    df['state'] = df['state'].fillna("Nordrhein-Westfalen")
    df['city'] = df['city'].fillna("Unknown")
    df['customer_type'] = df['customer_type'].fillna("Private")
    df['is_fleet'] = df['is_fleet'].fillna(False).astype(bool)

    # Pricing (EUR)
    df['base_price_eur'] = df['base_price_eur'].fillna(0).astype(int)
    df['discount_pct'] = df['discount_pct'].fillna(0.0)
    df['selling_price_eur'] = df['selling_price_eur'].fillna(df['base_price_eur']).astype(int)
    df['vat_amount_eur'] = df['vat_amount_eur'].fillna(0).astype(int)
    df['accessories_revenue_eur'] = df['accessories_revenue_eur'].fillna(0).astype(int)
    df['insurance_revenue_eur'] = df['insurance_revenue_eur'].fillna(0).astype(int)
    df['extended_warranty_eur'] = df['extended_warranty_eur'].fillna(0).astype(int)
    df['total_revenue_excl_vat'] = df['total_revenue_excl_vat'].fillna(df['selling_price_eur']).astype(int)
    df['total_revenue_incl_vat'] = df['total_revenue_incl_vat'].fillna(
        df['total_revenue_excl_vat'] + df['vat_amount_eur']
    ).astype(int)

    # Financial details
    df['financing_type'] = df['financing_type'].fillna("Cash")
    df['loan_amount_eur'] = df['loan_amount_eur'].fillna(0).astype(int)
    df['units_sold'] = df['units_sold'].fillna(1).astype(int)
    df['test_drive_converted'] = df['test_drive_converted'].fillna(False).astype(bool)
    df['lead_to_close_days'] = df['lead_to_close_days'].fillna(0).astype(int)
    df['season_multiplier'] = df['season_multiplier'].fillna(1.0)

    # ── Lease contract terms ─────────────────────────────────────────────────
    # These stay NULL on non-lease rows on purpose: a cash deal has no maturity
    # date, and filling one in would invent lease returns that never happen.
    if 'lease_maturity_date' in df.columns:
        df['lease_maturity_date'] = pd.to_datetime(
            df['lease_maturity_date'], errors='coerce'
        ).dt.date
        df['lease_maturity_date'] = df['lease_maturity_date'].where(
            pd.notnull(df['lease_maturity_date']), None
        )
    for col in ['lease_term_months', 'residual_value_eur',
                'contract_mileage_allowance', 'lease_monthly_payment_eur']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: int(x) if pd.notnull(x) else None)
    if 'residual_value_pct' in df.columns:
        df['residual_value_pct'] = df['residual_value_pct'].apply(
            lambda x: float(x) if pd.notnull(x) else None
        )

    # ── Trade-in activity (Inzahlungnahme) ───────────────────────────────────
    if 'trade_in_flag' in df.columns:
        df['trade_in_flag'] = df['trade_in_flag'].fillna(False).astype(bool)
    for col in ['trade_in_brand', 'trade_in_model']:
        if col in df.columns:
            df[col] = df[col].where(pd.notnull(df[col]), None)
    for col in ['trade_in_year', 'trade_in_mileage', 'trade_in_appraised_value_eur',
                'trade_in_allowance_eur', 'trade_in_over_allowance_eur']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: int(x) if pd.notnull(x) else None)
    # A deal with no trade simply had no bonus, so zero is the honest value.
    if 'trade_bonus_eur' in df.columns:
        df['trade_bonus_eur'] = df['trade_bonus_eur'].fillna(0).astype(int)

    return df


def clean_inventory(filepath):
    """
    Clean inventory.csv dataset (German schema).
    """
    df = pd.read_csv(filepath)

    df['record_date'] = pd.to_datetime(df['record_date']).dt.date
    df['brand'] = df['brand'].fillna("Unknown")
    df['model'] = df['model'].fillna("Unknown")
    df['vehicle_category'] = df['vehicle_category'].fillna("Compact")
    df['fuel_type'] = df['fuel_type'].fillna("Petrol")
    df['state'] = df['state'].fillna("Nordrhein-Westfalen")
    df['city'] = df['city'].fillna("Unknown")

    df['current_stock'] = df['current_stock'].fillna(0).astype(int)
    df['demand_forecast_30d'] = df['demand_forecast_30d'].fillna(0).astype(int)
    df['reorder_point'] = df['reorder_point'].fillna(0).astype(int)
    df['days_in_stock'] = df['days_in_stock'].fillna(0).astype(int)

    df['stockout_flag'] = df['stockout_flag'].fillna(df['current_stock'] == 0).astype(bool)
    df['overstock_flag'] = df['overstock_flag'].fillna(False).astype(bool)
    df['reorder_needed'] = df['reorder_needed'].fillna(False).astype(bool)

    df['stockout_risk_score'] = df['stockout_risk_score'].fillna(0.0)
    df['overstock_risk_score'] = df['overstock_risk_score'].fillna(0.0)
    df['holding_cost_per_day_eur'] = df['holding_cost_per_day_eur'].fillna(0.0)
    df['estimated_holding_cost_eur'] = df['estimated_holding_cost_eur'].fillna(0.0)

    df['units_sold_last_30d'] = df['units_sold_last_30d'].fillna(0).astype(int)
    df['units_ordered'] = df['units_ordered'].fillna(0).astype(int)
    df['transit_stock'] = df['transit_stock'].fillna(0).astype(int)
    df['warehouse_zone'] = df['warehouse_zone'].fillna("Zone A")
    df['origin_hub'] = df['origin_hub'].fillna("Bremerhaven")
    # EU-built stock needs no customs clearance at all, so True is the correct
    # default here rather than an optimistic guess.
    df['customs_cleared'] = df['customs_cleared'].fillna(True).astype(bool)

    df['last_replenishment_date'] = pd.to_datetime(df['last_replenishment_date']).dt.date
    df['supplier_lead_time_days'] = df['supplier_lead_time_days'].fillna(21).astype(int)

    return df


def clean_external_factors(filepath):
    """
    Clean external_factors.csv dataset (German schema).
    """
    df = pd.read_csv(filepath)

    df['date'] = pd.to_datetime(df['date'], format='mixed').dt.date
    df['year'] = df['year'].fillna(pd.to_datetime(df['date']).dt.year).astype(int)
    df['month'] = df['month'].fillna(pd.to_datetime(df['date']).dt.month).astype(int)
    df['quarter'] = df['quarter'].fillna("Q1")
    df['state'] = df['state'].fillna("Nordrhein-Westfalen")

    # Fuel and energy prices (EUR)
    for _col in ('super_e10_price_eur_per_litre', 'super_e5_price_eur_per_litre',
                 'diesel_price_eur_per_litre', 'electricity_price_eur_per_kwh',
                 'crude_oil_price_usd'):
        if _col in df.columns:
            df[_col] = df[_col].fillna(df[_col].median())

    # Macro-economic. NOTE consumer_confidence_index is the GfK Konsumklima and
    # is genuinely negative for most of this window — median is the right
    # fallback, and nothing downstream may treat it as a 100-centred index.
    for _col in ('gdp_growth_pct', 'cpi_inflation_pct', 'ecb_rate_pct',
                 'auto_loan_apr_pct', 'incentive_pct_of_atp', 'inventory_days_supply',
                 'consumer_confidence_index', 'ifo_business_climate',
                 'de_house_price_index', 'luxury_demand_index',
                 'commercial_registration_share_pct', 'unemployment_rate_pct',
                 'population_millions'):
        if _col in df.columns:
            df[_col] = df[_col].fillna(df[_col].median())

    # Event / seasonal flags
    for _col in ('quarter_end_month', 'year_end_month', 'summer_holiday_month', 'iaa_month'):
        if _col in df.columns:
            df[_col] = df[_col].fillna(0).astype(int)

    # Industry / policy
    df['new_model_launches'] = df['new_model_launches'].fillna(0).astype(int)
    df['vat_rate_pct'] = df['vat_rate_pct'].fillna(19.0)
    df['co2_price_eur_per_tonne'] = df['co2_price_eur_per_tonne'].fillna(0.0)
    # The Umweltbonus is genuinely zero after December 2023, so zero is the
    # correct fallback, not the median of a series that used to be 6000.
    df['ev_subsidy_eur'] = df['ev_subsidy_eur'].fillna(0).astype(int)
    df['ev_charging_points_de'] = df['ev_charging_points_de'].fillna(0).astype(int)

    return df
