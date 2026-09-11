import pandas as pd
import numpy as np


def clean_customers(filepath):
    """
    Clean customers.csv dataset (UAE schema).
    """
    df = pd.read_csv(filepath)

    # Identity
    df['name'] = df['name'].fillna("Unknown Customer")
    df['age'] = df['age'].fillna(df['age'].median())
    df['gender'] = df['gender'].fillna("Other")
    df['nationality'] = df['nationality'].fillna("Unknown")
    df['emirate'] = df['emirate'].fillna("Dubai")
    df['area'] = df['area'].fillna("Unknown")
    df['occupation'] = df['occupation'].fillna("Salaried Professional")
    df['years_in_uae'] = df['years_in_uae'].fillna(df['years_in_uae'].median()).astype(int)

    # Financial fields
    df['monthly_income_bracket'] = df['monthly_income_bracket'].fillna("Unknown")
    df['estimated_monthly_income_aed'] = df['estimated_monthly_income_aed'].fillna(
        df['estimated_monthly_income_aed'].median()
    )
    df['credit_score'] = df['credit_score'].fillna(df['credit_score'].median())
    df['down_payment_capacity_aed'] = df['down_payment_capacity_aed'].fillna(0)

    # Booleans
    df['email_opt_in'] = df['email_opt_in'].fillna(False).astype(bool)
    df['test_drive_taken'] = df['test_drive_taken'].fillna(False).astype(bool)
    df['emi_preferred'] = df['emi_preferred'].fillna(False).astype(bool)

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
    Clean vehicles.csv dataset (UAE schema).
    """
    df = pd.read_csv(filepath)

    # Strings
    df['brand'] = df['brand'].fillna("Unknown")
    df['model'] = df['model'].fillna("Unknown")
    df['variant'] = df['variant'].fillna("Base")
    df['category'] = df['category'].fillna("SUV")
    df['fuel_type'] = df['fuel_type'].fillna("Petrol")
    df['transmission'] = df['transmission'].fillna("Automatic")
    df['drive_type'] = df['drive_type'].fillna("FWD")

    # Pricing (AED)
    df['price_aed'] = df['price_aed'].fillna(0).astype(int)

    # Technical specs (EV range can be null for ICE; engine_cc null for EV)
    df['engine_cc'] = df['engine_cc'].apply(lambda x: int(x) if pd.notnull(x) else None)
    df['horsepower'] = df['horsepower'].apply(lambda x: int(x) if pd.notnull(x) else None)
    df['mileage_kmpl'] = df['mileage_kmpl'].apply(lambda x: float(x) if pd.notnull(x) else None)
    df['range_km'] = df['range_km'].apply(lambda x: int(x) if pd.notnull(x) else None)

    # Standard numbers
    df['seating_capacity'] = df['seating_capacity'].fillna(5).astype(int)
    df['body_color_options'] = df['body_color_options'].fillna(1).astype(int)
    df['safety_rating'] = df['safety_rating'].fillna(3).astype(int)
    df['launch_year'] = df['launch_year'].fillna(2020).astype(int)
    df['warranty_years'] = df['warranty_years'].fillna(3).astype(int)

    # Flags
    df['is_active'] = df['is_active'].fillna(True).astype(bool)
    df['service_contract_available'] = df['service_contract_available'].fillna(False).astype(bool)
    df['gcc_spec'] = df['gcc_spec'].fillna(True).astype(bool)

    # Residual curve. Falls back to the market-average 36-month residual so a
    # catalog without the column still prices leases sanely.
    if 'residual_value_36mo' in df.columns:
        df['residual_value_36mo'] = df['residual_value_36mo'].fillna(0.52).astype(float)
    else:
        df['residual_value_36mo'] = 0.52

    return df


def clean_dealers(filepath):
    """
    Clean dealers.csv dataset (UAE schema).
    """
    df = pd.read_csv(filepath)

    # Strings
    df['dealer_name'] = df['dealer_name'].fillna("Unknown Dealer")
    df['brand'] = df['brand'].fillna("Unknown")
    df['emirate'] = df['emirate'].fillna("Dubai")
    df['area'] = df['area'].fillna("Unknown")
    df['tier'] = df['tier'].fillna("Silver")

    # Numeric
    df['established_year'] = df['established_year'].fillna(2010).astype(int)
    df['monthly_capacity'] = df['monthly_capacity'].fillna(df['monthly_capacity'].median()).astype(int)
    df['showroom_area_sqft'] = df['showroom_area_sqft'].fillna(df['showroom_area_sqft'].median()).astype(int)
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
    Clean sales.csv dataset (UAE schema).
    """
    df = pd.read_csv(filepath)

    # Dates
    df['sale_date'] = pd.to_datetime(df['sale_date']).dt.date
    df['year'] = df['year'].fillna(pd.to_datetime(df['sale_date']).dt.year).astype(int)
    df['month'] = df['month'].fillna(pd.to_datetime(df['sale_date']).dt.month).astype(int)

    # Strings
    df['quarter'] = df['quarter'].fillna("Q1")
    df['day_of_week'] = df['day_of_week'].fillna("Monday")
    df['festival_period'] = df['festival_period'].fillna("None")
    df['brand'] = df['brand'].fillna("Unknown")
    df['model'] = df['model'].fillna("Unknown")
    df['vehicle_category'] = df['vehicle_category'].fillna("SUV")
    df['fuel_type'] = df['fuel_type'].fillna("Petrol")
    df['emirate'] = df['emirate'].fillna("Dubai")
    df['area'] = df['area'].fillna("Unknown")

    # Pricing (AED)
    df['base_price_aed'] = df['base_price_aed'].fillna(0).astype(int)
    df['discount_pct'] = df['discount_pct'].fillna(0.0)
    df['selling_price_aed'] = df['selling_price_aed'].fillna(df['base_price_aed']).astype(int)
    df['vat_amount_aed'] = df['vat_amount_aed'].fillna(0).astype(int)
    df['accessories_revenue_aed'] = df['accessories_revenue_aed'].fillna(0).astype(int)
    df['insurance_revenue_aed'] = df['insurance_revenue_aed'].fillna(0).astype(int)
    df['extended_warranty_aed'] = df['extended_warranty_aed'].fillna(0).astype(int)
    df['total_revenue_excl_vat'] = df['total_revenue_excl_vat'].fillna(df['selling_price_aed']).astype(int)
    df['total_revenue_incl_vat'] = df['total_revenue_incl_vat'].fillna(
        df['total_revenue_excl_vat'] + df['vat_amount_aed']
    ).astype(int)

    # Financial details
    df['financing_type'] = df['financing_type'].fillna("Cash")
    df['loan_amount_aed'] = df['loan_amount_aed'].fillna(0).astype(int)
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
    for col in ['lease_term_months', 'residual_value_aed',
                'contract_mileage_allowance', 'lease_monthly_payment_aed']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: int(x) if pd.notnull(x) else None)
    if 'residual_value_pct' in df.columns:
        df['residual_value_pct'] = df['residual_value_pct'].apply(
            lambda x: float(x) if pd.notnull(x) else None
        )

    # ── Trade-in activity ────────────────────────────────────────────────────
    if 'trade_in_flag' in df.columns:
        df['trade_in_flag'] = df['trade_in_flag'].fillna(False).astype(bool)
    for col in ['trade_in_brand', 'trade_in_model']:
        if col in df.columns:
            df[col] = df[col].where(pd.notnull(df[col]), None)
    for col in ['trade_in_year', 'trade_in_mileage', 'trade_in_appraised_value_aed',
                'trade_in_allowance_aed', 'trade_in_over_allowance_aed']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: int(x) if pd.notnull(x) else None)
    # A deal with no trade simply had no bonus, so zero is the honest value.
    if 'trade_bonus_aed' in df.columns:
        df['trade_bonus_aed'] = df['trade_bonus_aed'].fillna(0).astype(int)

    return df


def clean_inventory(filepath):
    """
    Clean inventory.csv dataset (UAE schema).
    """
    df = pd.read_csv(filepath)

    df['record_date'] = pd.to_datetime(df['record_date']).dt.date
    df['brand'] = df['brand'].fillna("Unknown")
    df['model'] = df['model'].fillna("Unknown")
    df['vehicle_category'] = df['vehicle_category'].fillna("SUV")
    df['fuel_type'] = df['fuel_type'].fillna("Petrol")
    df['emirate'] = df['emirate'].fillna("Dubai")
    df['area'] = df['area'].fillna("Unknown")

    df['current_stock'] = df['current_stock'].fillna(0).astype(int)
    df['demand_forecast_30d'] = df['demand_forecast_30d'].fillna(0).astype(int)
    df['reorder_point'] = df['reorder_point'].fillna(0).astype(int)
    df['days_in_stock'] = df['days_in_stock'].fillna(0).astype(int)

    df['stockout_flag'] = df['stockout_flag'].fillna(df['current_stock'] == 0).astype(bool)
    df['overstock_flag'] = df['overstock_flag'].fillna(False).astype(bool)
    df['reorder_needed'] = df['reorder_needed'].fillna(False).astype(bool)

    df['stockout_risk_score'] = df['stockout_risk_score'].fillna(0.0)
    df['overstock_risk_score'] = df['overstock_risk_score'].fillna(0.0)
    df['holding_cost_per_day_aed'] = df['holding_cost_per_day_aed'].fillna(0.0)
    df['estimated_holding_cost_aed'] = df['estimated_holding_cost_aed'].fillna(0.0)

    df['units_sold_last_30d'] = df['units_sold_last_30d'].fillna(0).astype(int)
    df['units_ordered'] = df['units_ordered'].fillna(0).astype(int)
    df['transit_stock'] = df['transit_stock'].fillna(0).astype(int)
    df['warehouse_zone'] = df['warehouse_zone'].fillna("Zone A")
    df['port_of_entry'] = df['port_of_entry'].fillna("Jebel Ali Port")
    df['customs_cleared'] = df['customs_cleared'].fillna(True).astype(bool)

    df['last_replenishment_date'] = pd.to_datetime(df['last_replenishment_date']).dt.date
    df['supplier_lead_time_days'] = df['supplier_lead_time_days'].fillna(30).astype(int)

    return df


def clean_external_factors(filepath):
    """
    Clean external_factors.csv dataset (UAE schema).
    """
    df = pd.read_csv(filepath)

    df['date'] = pd.to_datetime(df['date'], format='mixed').dt.date
    df['year'] = df['year'].fillna(pd.to_datetime(df['date']).dt.year).astype(int)
    df['month'] = df['month'].fillna(pd.to_datetime(df['date']).dt.month).astype(int)
    df['quarter'] = df['quarter'].fillna("Q1")
    df['emirate'] = df['emirate'].fillna("Dubai")

    # Fuel prices (AED/litre)
    df['petrol_95_price_aed_per_litre'] = df['petrol_95_price_aed_per_litre'].fillna(
        df['petrol_95_price_aed_per_litre'].median()
    )
    df['petrol_98_price_aed_per_litre'] = df['petrol_98_price_aed_per_litre'].fillna(
        df['petrol_98_price_aed_per_litre'].median()
    )
    df['diesel_price_aed_per_litre'] = df['diesel_price_aed_per_litre'].fillna(
        df['diesel_price_aed_per_litre'].median()
    )
    df['crude_oil_price_usd'] = df['crude_oil_price_usd'].fillna(df['crude_oil_price_usd'].median())

    # Macro-economic
    df['gdp_growth_pct'] = df['gdp_growth_pct'].fillna(df['gdp_growth_pct'].median())
    df['cpi_inflation_pct'] = df['cpi_inflation_pct'].fillna(df['cpi_inflation_pct'].median())
    df['cbuae_rate_pct'] = df['cbuae_rate_pct'].fillna(df['cbuae_rate_pct'].median())
    for _col in ('auto_loan_apr_pct', 'incentive_pct_of_atp', 'inventory_days_supply'):
        if _col in df.columns:
            df[_col] = df[_col].fillna(df[_col].median())
    df['consumer_confidence_index'] = df['consumer_confidence_index'].fillna(
        df['consumer_confidence_index'].median()
    )
    df['tourism_index'] = df['tourism_index'].fillna(df['tourism_index'].median())
    df['dubai_re_price_index'] = df['dubai_re_price_index'].fillna(df['dubai_re_price_index'].median())
    df['luxury_demand_index'] = df['luxury_demand_index'].fillna(df['luxury_demand_index'].median())

    # Event / seasonal flags
    df['ramadan_month'] = df['ramadan_month'].fillna(0).astype(int)
    df['national_day_month'] = df['national_day_month'].fillna(0).astype(int)
    df['dubai_motor_show_month'] = df['dubai_motor_show_month'].fillna(0).astype(int)
    df['dsf_month'] = df['dsf_month'].fillna(0).astype(int)

    # Industry
    df['new_model_launches'] = df['new_model_launches'].fillna(0).astype(int)
    df['import_duty_pct'] = df['import_duty_pct'].fillna(5.0)
    df['vat_rate_pct'] = df['vat_rate_pct'].fillna(5.0)
    df['unemployment_rate_pct'] = df['unemployment_rate_pct'].fillna(df['unemployment_rate_pct'].median())
    df['population_millions'] = df['population_millions'].fillna(df['population_millions'].median())
    df['ev_charging_stations_uae'] = df['ev_charging_stations_uae'].fillna(0).astype(int)

    return df
