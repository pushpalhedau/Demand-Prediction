import pandas as pd
import numpy as np


def clean_customers(filepath):
    """
    Clean customers.csv dataset (NA schema).
    """
    df = pd.read_csv(filepath)

    # Identity
    df['name'] = df['name'].fillna("Unknown Customer")
    df['age'] = df['age'].fillna(df['age'].median())
    df['gender'] = df['gender'].fillna("Other")
    df['nationality'] = df['nationality'].fillna("Unknown")
    df['state'] = df['state'].fillna("California")
    df['city'] = df['city'].fillna("Unknown")
    df['occupation'] = df['occupation'].fillna("Self-Employed")
    df['years_at_address'] = df['years_at_address'].fillna(df['years_at_address'].median()).astype(int)

    # Financial fields
    df['income_bracket'] = df['income_bracket'].fillna("Unknown")
    df['estimated_annual_income_usd'] = df['estimated_annual_income_usd'].fillna(
        df['estimated_annual_income_usd'].median()
    )
    df['credit_score'] = df['credit_score'].fillna(df['credit_score'].median())
    df['down_payment_capacity_usd'] = df['down_payment_capacity_usd'].fillna(0)

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
    Clean vehicles.csv dataset (NA schema).
    """
    df = pd.read_csv(filepath)

    # Strings
    df['brand'] = df['brand'].fillna("Unknown")
    df['model'] = df['model'].fillna("Unknown")
    df['variant'] = df['variant'].fillna("Base")
    df['category'] = df['category'].fillna("SUV")
    df['fuel_type'] = df['fuel_type'].fillna("Gasoline")
    df['transmission'] = df['transmission'].fillna("Automatic")
    df['drive_type'] = df['drive_type'].fillna("FWD")

    # Pricing (USD)
    df['price_usd'] = df['price_usd'].fillna(0).astype(int)

    # Technical specs (EV range can be null for ICE; engine_cc null for EV)
    df['engine_cc'] = df['engine_cc'].apply(lambda x: int(x) if pd.notnull(x) else None)
    df['horsepower'] = df['horsepower'].apply(lambda x: int(x) if pd.notnull(x) else None)
    df['mpg'] = df['mpg'].apply(lambda x: float(x) if pd.notnull(x) else None)
    df['range_miles'] = df['range_miles'].apply(lambda x: int(x) if pd.notnull(x) else None)

    # Standard numbers
    df['seating_capacity'] = df['seating_capacity'].fillna(5).astype(int)
    df['body_color_options'] = df['body_color_options'].fillna(1).astype(int)
    df['safety_rating'] = df['safety_rating'].fillna(3).astype(int)
    df['launch_year'] = df['launch_year'].fillna(2020).astype(int)
    df['warranty_years'] = df['warranty_years'].fillna(3).astype(int)

    # Flags
    df['is_active'] = df['is_active'].fillna(True).astype(bool)
    df['service_contract_available'] = df['service_contract_available'].fillna(False).astype(bool)
    df['ev_incentive_eligible'] = df['ev_incentive_eligible'].fillna(False).astype(bool)

    return df


def clean_dealers(filepath):
    """
    Clean dealers.csv dataset (NA schema).
    """
    df = pd.read_csv(filepath)

    # Strings
    df['dealer_name'] = df['dealer_name'].fillna("Unknown Dealer")
    df['brand'] = df['brand'].fillna("Unknown")
    df['state'] = df['state'].fillna("California")
    df['city'] = df['city'].fillna("Unknown")
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
    Clean sales.csv dataset (NA schema).
    """
    df = pd.read_csv(filepath)

    # Dates
    df['sale_date'] = pd.to_datetime(df['sale_date']).dt.date
    df['year'] = df['year'].fillna(pd.to_datetime(df['sale_date']).dt.year).astype(int)
    df['month'] = df['month'].fillna(pd.to_datetime(df['sale_date']).dt.month).astype(int)

    # Strings
    df['quarter'] = df['quarter'].fillna("Q1")
    df['day_of_week'] = df['day_of_week'].fillna("Monday")
    df['holiday_period'] = df['holiday_period'].fillna("None")
    df['brand'] = df['brand'].fillna("Unknown")
    df['model'] = df['model'].fillna("Unknown")
    df['vehicle_category'] = df['vehicle_category'].fillna("SUV")
    df['fuel_type'] = df['fuel_type'].fillna("Gasoline")
    df['state'] = df['state'].fillna("California")
    df['city'] = df['city'].fillna("Unknown")

    # Pricing (USD)
    df['base_price_usd'] = df['base_price_usd'].fillna(0).astype(int)
    df['discount_pct'] = df['discount_pct'].fillna(0.0)
    df['selling_price_usd'] = df['selling_price_usd'].fillna(df['base_price_usd']).astype(int)
    df['sales_tax_amount_usd'] = df['sales_tax_amount_usd'].fillna(0).astype(int)
    df['accessories_revenue_usd'] = df['accessories_revenue_usd'].fillna(0).astype(int)
    df['insurance_revenue_usd'] = df['insurance_revenue_usd'].fillna(0).astype(int)
    df['extended_warranty_usd'] = df['extended_warranty_usd'].fillna(0).astype(int)
    df['total_revenue_excl_tax'] = df['total_revenue_excl_tax'].fillna(df['selling_price_usd']).astype(int)
    df['total_revenue_incl_tax'] = df['total_revenue_incl_tax'].fillna(
        df['total_revenue_excl_tax'] + df['sales_tax_amount_usd']
    ).astype(int)

    # Financial details
    df['financing_type'] = df['financing_type'].fillna("Cash")
    df['loan_amount_usd'] = df['loan_amount_usd'].fillna(0).astype(int)
    df['units_sold'] = df['units_sold'].fillna(1).astype(int)
    df['test_drive_converted'] = df['test_drive_converted'].fillna(False).astype(bool)
    df['lead_to_close_days'] = df['lead_to_close_days'].fillna(0).astype(int)
    df['season_multiplier'] = df['season_multiplier'].fillna(1.0)

    return df


def clean_inventory(filepath):
    """
    Clean inventory.csv dataset (NA schema).
    """
    df = pd.read_csv(filepath)

    df['record_date'] = pd.to_datetime(df['record_date']).dt.date
    df['brand'] = df['brand'].fillna("Unknown")
    df['model'] = df['model'].fillna("Unknown")
    df['vehicle_category'] = df['vehicle_category'].fillna("SUV")
    df['fuel_type'] = df['fuel_type'].fillna("Gasoline")
    df['state'] = df['state'].fillna("California")
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
    df['holding_cost_per_day_usd'] = df['holding_cost_per_day_usd'].fillna(0.0)
    df['estimated_holding_cost_usd'] = df['estimated_holding_cost_usd'].fillna(0.0)

    df['units_sold_last_30d'] = df['units_sold_last_30d'].fillna(0).astype(int)
    df['units_ordered'] = df['units_ordered'].fillna(0).astype(int)
    df['transit_stock'] = df['transit_stock'].fillna(0).astype(int)
    df['warehouse_zone'] = df['warehouse_zone'].fillna("Zone A")
    df['port_of_entry'] = df['port_of_entry'].fillna("Port of Long Beach")
    df['customs_cleared'] = df['customs_cleared'].fillna(True).astype(bool)

    df['last_replenishment_date'] = pd.to_datetime(df['last_replenishment_date']).dt.date
    df['supplier_lead_time_days'] = df['supplier_lead_time_days'].fillna(7).astype(int)

    return df


def clean_external_factors(filepath):
    """
    Clean external_factors.csv dataset (NA schema).
    """
    df = pd.read_csv(filepath)

    df['date'] = pd.to_datetime(df['date'], format='mixed').dt.date
    df['year'] = df['year'].fillna(pd.to_datetime(df['date']).dt.year).astype(int)
    df['month'] = df['month'].fillna(pd.to_datetime(df['date']).dt.month).astype(int)
    df['quarter'] = df['quarter'].fillna("Q1")
    df['state'] = df['state'].fillna("California")

    # Fuel prices (USD/gallon)
    df['gasoline_regular_usd_per_gallon'] = df['gasoline_regular_usd_per_gallon'].fillna(
        df['gasoline_regular_usd_per_gallon'].median()
    )
    df['gasoline_premium_usd_per_gallon'] = df['gasoline_premium_usd_per_gallon'].fillna(
        df['gasoline_premium_usd_per_gallon'].median()
    )
    df['diesel_usd_per_gallon'] = df['diesel_usd_per_gallon'].fillna(
        df['diesel_usd_per_gallon'].median()
    )
    df['wti_crude_price_usd'] = df['wti_crude_price_usd'].fillna(df['wti_crude_price_usd'].median())

    # Macro-economic
    df['gdp_growth_pct'] = df['gdp_growth_pct'].fillna(df['gdp_growth_pct'].median())
    df['cpi_inflation_pct'] = df['cpi_inflation_pct'].fillna(df['cpi_inflation_pct'].median())
    df['us_fed_rate_pct'] = df['us_fed_rate_pct'].fillna(df['us_fed_rate_pct'].median())
    df['consumer_confidence_index'] = df['consumer_confidence_index'].fillna(
        df['consumer_confidence_index'].median()
    )
    df['tourism_index'] = df['tourism_index'].fillna(df['tourism_index'].median())
    df['home_price_index'] = df['home_price_index'].fillna(df['home_price_index'].median())
    df['luxury_demand_index'] = df['luxury_demand_index'].fillna(df['luxury_demand_index'].median())

    # Event / seasonal flags
    df['holiday_season_month'] = df['holiday_season_month'].fillna(0).astype(int)
    df['july_4th_month'] = df['july_4th_month'].fillna(0).astype(int)
    df['detroit_auto_show_month'] = df['detroit_auto_show_month'].fillna(0).astype(int)
    df['la_auto_show_month'] = df['la_auto_show_month'].fillna(0).astype(int)

    # Industry
    df['new_model_launches'] = df['new_model_launches'].fillna(0).astype(int)
    df['tariff_pct'] = df['tariff_pct'].fillna(df['tariff_pct'].median())
    df['avg_sales_tax_pct'] = df['avg_sales_tax_pct'].fillna(df['avg_sales_tax_pct'].median())
    df['unemployment_rate_pct'] = df['unemployment_rate_pct'].fillna(df['unemployment_rate_pct'].median())
    df['population_millions'] = df['population_millions'].fillna(df['population_millions'].median())
    df['ev_charging_stations'] = df['ev_charging_stations'].fillna(0).astype(int)

    return df
