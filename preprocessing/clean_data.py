import pandas as pd
import numpy as np

def clean_customers(filepath):
    """
    Clean customers.csv dataset.
    """
    df = pd.read_csv(filepath)
    
    # Fill missing values
    df['name'] = df['name'].fillna("Unknown Customer")
    df['age'] = df['age'].fillna(df['age'].median())
    df['gender'] = df['gender'].fillna("Other")
    df['city'] = df['city'].fillna("Unknown")
    df['region'] = df['region'].fillna("Central")
    df['state'] = df['state'].fillna("Unknown")
    df['occupation'] = df['occupation'].fillna("Self-Employed")
    
    # Financial fields
    df['estimated_annual_income'] = df['estimated_annual_income'].fillna(df['estimated_annual_income'].median())
    df['credit_score'] = df['credit_score'].fillna(df['credit_score'].median())
    df['down_payment_capacity'] = df['down_payment_capacity'].fillna(0)
    
    # Booleans
    df['email_opt_in'] = df['email_opt_in'].fillna(False).astype(bool)
    df['whatsapp_opted'] = df['whatsapp_opted'].fillna(False).astype(bool)
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
    Clean vehicles.csv dataset.
    """
    df = pd.read_csv(filepath)
    
    # Strings
    df['brand'] = df['brand'].fillna("Unknown")
    df['model'] = df['model'].fillna("Unknown")
    df['variant'] = df['variant'].fillna("Base")
    df['category'] = df['category'].fillna("Sedan")
    df['fuel_type'] = df['fuel_type'].fillna("Petrol")
    df['transmission'] = df['transmission'].fillna("Manual")
    
    # Pricing
    df['ex_showroom_price'] = df['ex_showroom_price'].fillna(0).astype(int)
    
    # Technical Specs (EV ranges can be null for ICE, Engine CC can be null for EV)
    df['engine_cc'] = df['engine_cc'].apply(lambda x: int(x) if pd.notnull(x) else None)
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
    df['ev_subsidy_eligible'] = df['ev_subsidy_eligible'].fillna(False).astype(bool)
    
    return df


def clean_dealers(filepath):
    """
    Clean dealers.csv dataset.
    """
    df = pd.read_csv(filepath)
    
    # Strings
    df['dealer_name'] = df['dealer_name'].fillna("Unknown Dealer")
    df['brand'] = df['brand'].fillna("Unknown")
    df['region'] = df['region'].fillna("Central")
    df['city'] = df['city'].fillna("Unknown")
    df['state'] = df['state'].fillna("Unknown")
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
    df['rating'] = df['rating'].fillna(df['rating'].median())
    
    # Geo
    df['latitude'] = df['latitude'].fillna(0.0)
    df['longitude'] = df['longitude'].fillna(0.0)
    
    return df


def clean_sales(filepath):
    """
    Clean sales.csv dataset.
    """
    df = pd.read_csv(filepath)
    
    # Crucial fields: Dates
    df['sale_date'] = pd.to_datetime(df['sale_date']).dt.date
    df['year'] = df['year'].fillna(pd.to_datetime(df['sale_date']).dt.year).astype(int)
    df['month'] = df['month'].fillna(pd.to_datetime(df['sale_date']).dt.month).astype(int)
    
    # Strings
    df['quarter'] = df['quarter'].fillna("Q1")
    df['day_of_week'] = df['day_of_week'].fillna("Monday")
    df['festival_period'] = df['festival_period'].fillna("None")
    df['brand'] = df['brand'].fillna("Unknown")
    df['model'] = df['model'].fillna("Unknown")
    df['vehicle_category'] = df['vehicle_category'].fillna("Sedan")
    df['fuel_type'] = df['fuel_type'].fillna("Petrol")
    df['region'] = df['region'].fillna("Central")
    df['city'] = df['city'].fillna("Unknown")
    
    # Pricing
    df['base_price'] = df['base_price'].fillna(0).astype(int)
    df['discount_pct'] = df['discount_pct'].fillna(0.0)
    df['selling_price'] = df['selling_price'].fillna(df['base_price']).astype(int)
    df['accessories_revenue'] = df['accessories_revenue'].fillna(0).astype(int)
    df['insurance_revenue'] = df['insurance_revenue'].fillna(0).astype(int)
    df['extended_warranty'] = df['extended_warranty'].fillna(0).astype(int)
    df['total_revenue'] = df['total_revenue'].fillna(df['selling_price']).astype(int)
    
    # Financial details
    df['financing_type'] = df['financing_type'].fillna("Cash")
    df['loan_amount'] = df['loan_amount'].fillna(0).astype(int)
    df['units_sold'] = df['units_sold'].fillna(1).astype(int)
    df['test_drive_converted'] = df['test_drive_converted'].fillna(False).astype(bool)
    df['lead_to_close_days'] = df['lead_to_close_days'].fillna(0).astype(int)
    df['season_multiplier'] = df['season_multiplier'].fillna(1.0)
    
    return df


def clean_inventory(filepath):
    """
    Clean inventory.csv dataset.
    """
    df = pd.read_csv(filepath)
    
    df['record_date'] = pd.to_datetime(df['record_date']).dt.date
    df['brand'] = df['brand'].fillna("Unknown")
    df['model'] = df['model'].fillna("Unknown")
    df['vehicle_category'] = df['vehicle_category'].fillna("Sedan")
    df['fuel_type'] = df['fuel_type'].fillna("Petrol")
    df['region'] = df['region'].fillna("Central")
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
    df['holding_cost_per_day'] = df['holding_cost_per_day'].fillna(0.0)
    df['estimated_holding_cost'] = df['estimated_holding_cost'].fillna(0.0)
    
    df['units_sold_last_30d'] = df['units_sold_last_30d'].fillna(0).astype(int)
    df['units_ordered'] = df['units_ordered'].fillna(0).astype(int)
    df['transit_stock'] = df['transit_stock'].fillna(0).astype(int)
    df['warehouse_location'] = df['warehouse_location'].fillna("Zone A")
    
    df['last_replenishment_date'] = pd.to_datetime(df['last_replenishment_date']).dt.date
    df['supplier_lead_time_days'] = df['supplier_lead_time_days'].fillna(7).astype(int)
    
    return df


def clean_external_factors(filepath):
    """
    Clean external_factors.csv dataset.
    """
    df = pd.read_csv(filepath)
    
    df['date'] = pd.to_datetime(df['date']).dt.date
    df['year'] = df['year'].fillna(pd.to_datetime(df['date']).dt.year).astype(int)
    df['month'] = df['month'].fillna(pd.to_datetime(df['date']).dt.month).astype(int)
    df['quarter'] = df['quarter'].fillna("Q1")
    df['region'] = df['region'].fillna("Central")
    
    # Financial and economic indexes
    df['petrol_price_per_litre'] = df['petrol_price_per_litre'].fillna(df['petrol_price_per_litre'].median())
    df['diesel_price_per_litre'] = df['diesel_price_per_litre'].fillna(df['diesel_price_per_litre'].median())
    df['gdp_growth_pct'] = df['gdp_growth_pct'].fillna(df['gdp_growth_pct'].median())
    df['cpi_inflation_pct'] = df['cpi_inflation_pct'].fillna(df['cpi_inflation_pct'].median())
    df['rbi_repo_rate_pct'] = df['rbi_repo_rate_pct'].fillna(df['rbi_repo_rate_pct'].median())
    df['consumer_confidence_index'] = df['consumer_confidence_index'].fillna(df['consumer_confidence_index'].median())
    df['auto_industry_index'] = df['auto_industry_index'].fillna(df['auto_industry_index'].median())
    
    df['semiconductor_shortage'] = df['semiconductor_shortage'].fillna(0).astype(int)
    df['ev_subsidy_active'] = df['ev_subsidy_active'].fillna(0).astype(int)
    df['ev_subsidy_amount_per_vehicle'] = df['ev_subsidy_amount_per_vehicle'].fillna(0).astype(int)
    df['steel_price_per_ton'] = df['steel_price_per_ton'].fillna(df['steel_price_per_ton'].median())
    df['usd_inr_rate'] = df['usd_inr_rate'].fillna(df['usd_inr_rate'].median())
    
    df['festival_month'] = df['festival_month'].fillna(0).astype(int)
    df['festival_name'] = df['festival_name'].fillna("None")
    df['unemployment_rate_pct'] = df['unemployment_rate_pct'].fillna(df['unemployment_rate_pct'].median())
    df['new_model_launches'] = df['new_model_launches'].fillna(0).astype(int)
    df['government_infra_spend_bn'] = df['government_infra_spend_bn'].fillna(df['government_infra_spend_bn'].median())
    df['registration_tax_pct'] = df['registration_tax_pct'].fillna(df['registration_tax_pct'].median())
    df['road_cess_pct'] = df['road_cess_pct'].fillna(df['road_cess_pct'].median())
    
    return df
