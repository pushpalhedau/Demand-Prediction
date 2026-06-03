import pandas as pd
import numpy as np


def clean_transactions(filepath):
    df = pd.read_csv(filepath)

    df['transaction_date'] = pd.to_datetime(df['transaction_date']).dt.date
    df['year'] = df['year'].fillna(pd.to_datetime(df['transaction_date']).dt.year).astype(int)
    df['month'] = df['month'].fillna(pd.to_datetime(df['transaction_date']).dt.month).astype(int)
    df['quarter'] = df['quarter'].fillna("Q1")
    df['day_of_week'] = df['day_of_week'].fillna("Monday")
    df['is_ramadan_period'] = df['is_ramadan_period'].fillna(False).astype(bool)
    df['market_event'] = df['market_event'].fillna("None")

    df['project_name'] = df['project_name'].fillna("Unknown Project")
    df['property_type'] = df['property_type'].fillna("Apartment")
    df['property_category'] = df['property_category'].fillna("Mid-Market")
    df['bedrooms'] = df['bedrooms'].fillna("2BR")
    df['completion_status'] = df['completion_status'].fillna("Off-Plan")
    df['possession_year'] = df['possession_year'].fillna(2026).astype(int)
    df['emirate'] = df['emirate'].fillna("Dubai")
    df['city'] = df['city'].fillna("Dubai")
    df['locality'] = df['locality'].fillna("Unknown")
    df['region'] = df['region'].fillna("South UAE")

    df['area_sqft'] = df['area_sqft'].fillna(df['area_sqft'].median())
    df['base_price_aed'] = df['base_price_aed'].fillna(0).astype(int)
    df['price_per_sqft_aed'] = df['price_per_sqft_aed'].fillna(df['price_per_sqft_aed'].median())
    df['discount_pct'] = df['discount_pct'].fillna(0.0)
    df['selling_price_aed'] = df['selling_price_aed'].fillna(df['base_price_aed']).astype(int)
    df['dld_transfer_fee_aed'] = df['dld_transfer_fee_aed'].fillna(0).astype(int)
    df['agency_commission_aed'] = df['agency_commission_aed'].fillna(0).astype(int)
    df['vat_amount_aed'] = df['vat_amount_aed'].fillna(0).astype(int)
    df['service_charge_annual_aed'] = df['service_charge_annual_aed'].fillna(0).astype(int)
    df['total_transaction_value_aed'] = df['total_transaction_value_aed'].fillna(
        df['selling_price_aed']
    ).astype(int)

    df['payment_plan'] = df['payment_plan'].fillna("Mortgage")
    df['mortgage_amount_aed'] = df['mortgage_amount_aed'].fillna(0).astype(int)
    df['booking_amount_aed'] = df['booking_amount_aed'].fillna(0).astype(int)
    df['golden_visa_eligible'] = df['golden_visa_eligible'].fillna(False).astype(bool)
    df['lead_to_close_days'] = df['lead_to_close_days'].fillna(30).astype(int)
    df['marketing_channel'] = df['marketing_channel'].fillna("Digital")
    df['booking_converted'] = df['booking_converted'].fillna(False).astype(bool)
    df['season_multiplier'] = df['season_multiplier'].fillna(1.0)
    df['freehold'] = df['freehold'].fillna(True).astype(bool)

    return df


def clean_buyers(filepath):
    df = pd.read_csv(filepath)

    df['name'] = df['name'].fillna("Unknown Buyer")
    df['age'] = df['age'].fillna(df['age'].median()).astype(int)
    df['gender'] = df['gender'].fillna("Male")
    df['nationality'] = df['nationality'].fillna("Unknown")
    df['residence_city'] = df['residence_city'].fillna("Dubai")
    df['emirate'] = df['emirate'].fillna("Dubai")
    df['occupation'] = df['occupation'].fillna("Salaried")
    df['annual_income_bracket'] = df['annual_income_bracket'].fillna("20K-40K")
    df['estimated_annual_income_aed'] = df['estimated_annual_income_aed'].fillna(
        df['estimated_annual_income_aed'].median()
    )
    df['buyer_type'] = df['buyer_type'].fillna("End User")
    df['expat_status'] = df['expat_status'].fillna(True).astype(bool)
    df['years_in_uae'] = df['years_in_uae'].fillna(df['years_in_uae'].median())
    df['number_of_past_purchases'] = df['number_of_past_purchases'].fillna(0).astype(int)
    df['preferred_property_type'] = df['preferred_property_type'].fillna("Apartment")
    df['preferred_property_category'] = df['preferred_property_category'].fillna("Mid-Market")
    df['preferred_city'] = df['preferred_city'].fillna("Dubai")
    df['preferred_locality'] = df['preferred_locality'].fillna("Unknown")
    df['preferred_bedrooms'] = df['preferred_bedrooms'].fillna("2BR")
    df['budget_min_aed'] = df['budget_min_aed'].fillna(0).astype(int)
    df['budget_max_aed'] = df['budget_max_aed'].fillna(2000000).astype(int)
    df['customer_segment'] = df['customer_segment'].fillna("End User")
    df['golden_visa_intent'] = df['golden_visa_intent'].fillna(False).astype(bool)
    df['off_plan_preference'] = df['off_plan_preference'].fillna(False).astype(bool)
    df['loyalty_score'] = df['loyalty_score'].fillna(50.0)
    df['marketing_response_score'] = df['marketing_response_score'].fillna(5.0)
    df['lead_source'] = df['lead_source'].fillna("Property Finder")
    df['email_opt_in'] = df['email_opt_in'].fillna(True).astype(bool)
    df['whatsapp_opted'] = df['whatsapp_opted'].fillna(True).astype(bool)
    df['site_visit_taken'] = df['site_visit_taken'].fillna(False).astype(bool)
    df['mortgage_preferred'] = df['mortgage_preferred'].fillna(True).astype(bool)
    df['down_payment_capacity_aed'] = df['down_payment_capacity_aed'].fillna(200000).astype(int)
    df['registration_date'] = pd.to_datetime(df['registration_date']).dt.date
    df['last_activity_date'] = pd.to_datetime(df['last_activity_date']).dt.date
    df['churn_risk_score'] = df['churn_risk_score'].fillna(0.5)

    return df


def clean_developers(filepath):
    df = pd.read_csv(filepath)

    df['developer_name'] = df['developer_name'].fillna("Unknown Developer")
    df['developer_type'] = df['developer_type'].fillna("Developer")
    df['primary_city'] = df['primary_city'].fillna("Dubai")
    df['operating_cities'] = df['operating_cities'].fillna("Dubai")
    df['emirate'] = df['emirate'].fillna("Dubai")
    df['address'] = df['address'].fillna("Unknown")
    df['tier'] = df['tier'].fillna("Tier 2")
    df['established_year'] = df['established_year'].fillna(2000).astype(int)
    df['rera_registration_no'] = df['rera_registration_no'].fillna("N/A")
    df['rera_registered'] = df['rera_registered'].fillna(True).astype(bool)
    df['adm_registered'] = df['adm_registered'].fillna(False).astype(bool)
    df['monthly_capacity_units'] = df['monthly_capacity_units'].fillna(
        df['monthly_capacity_units'].median()
    ).astype(int)
    df['office_area_sqft'] = df['office_area_sqft'].fillna(
        df['office_area_sqft'].median()
    ).astype(int)
    df['num_agents'] = df['num_agents'].fillna(df['num_agents'].median()).astype(int)
    df['annual_target_units'] = df['annual_target_units'].fillna(
        df['annual_target_units'].median()
    ).astype(int)
    df['performance_score'] = df['performance_score'].fillna(df['performance_score'].median())
    df['rating'] = df['rating'].fillna(3.5)
    df['total_projects_launched'] = df['total_projects_launched'].fillna(1).astype(int)
    df['active_projects'] = df['active_projects'].fillna(1).astype(int)
    df['completed_projects'] = df['completed_projects'].fillna(0).astype(int)
    df['specialization'] = df['specialization'].fillna("Residential")
    df['off_plan_focus'] = df['off_plan_focus'].fillna(False).astype(bool)
    df['latitude'] = df['latitude'].fillna(25.2048)   # Dubai default
    df['longitude'] = df['longitude'].fillna(55.2708)

    return df


def clean_properties(filepath):
    df = pd.read_csv(filepath)

    df['project_name'] = df['project_name'].fillna("Unknown Project")
    df['dld_permit_no'] = df['dld_permit_no'].fillna("N/A")
    df['property_type'] = df['property_type'].fillna("Apartment")
    df['property_category'] = df['property_category'].fillna("Mid-Market")
    df['bedrooms'] = df['bedrooms'].fillna("2BR")
    df['bathrooms'] = df['bathrooms'].fillna(2).astype(int)
    df['carpet_area_sqft_min'] = df['carpet_area_sqft_min'].fillna(
        df['carpet_area_sqft_min'].median()
    )
    df['carpet_area_sqft_max'] = df['carpet_area_sqft_max'].fillna(
        df['carpet_area_sqft_max'].median()
    )
    df['builtup_area_sqft'] = df['builtup_area_sqft'].fillna(df['builtup_area_sqft'].median())
    df['base_price_aed'] = df['base_price_aed'].fillna(0).astype(int)
    df['price_per_sqft_aed'] = df['price_per_sqft_aed'].fillna(df['price_per_sqft_aed'].median())
    df['emirate'] = df['emirate'].fillna("Dubai")
    df['city'] = df['city'].fillna("Dubai")
    df['locality'] = df['locality'].fillna("Unknown")
    df['region'] = df['region'].fillna("South UAE")
    df['total_floors'] = df['total_floors'].fillna(10).astype(int)
    df['parking_spaces'] = df['parking_spaces'].fillna(1).astype(int)
    df['amenities_score'] = df['amenities_score'].fillna(5.0)
    df['completion_status'] = df['completion_status'].fillna("Off-Plan")
    df['launch_year'] = df['launch_year'].fillna(2022).astype(int)
    df['possession_year'] = df['possession_year'].fillna(2026).astype(int)
    df['is_active'] = df['is_active'].fillna(True).astype(bool)
    df['freehold'] = df['freehold'].fillna(True).astype(bool)
    df['leasehold_years'] = df['leasehold_years'].fillna(0).astype(int)
    df['service_charge_aed_sqft'] = df['service_charge_aed_sqft'].fillna(15.0)
    df['rental_yield_pct'] = df['rental_yield_pct'].fillna(6.0)
    df['capital_appreciation_pct'] = df['capital_appreciation_pct'].fillna(7.0)
    df['roi_pct'] = df['roi_pct'].fillna(df['rental_yield_pct'] + df['capital_appreciation_pct'])
    df['golden_visa_eligible'] = df['golden_visa_eligible'].fillna(False).astype(bool)
    df['vat_applicable'] = df['vat_applicable'].fillna(False).astype(bool)

    return df


def clean_listings(filepath):
    df = pd.read_csv(filepath)

    df['record_date'] = pd.to_datetime(df['record_date']).dt.date
    df['project_name'] = df['project_name'].fillna("Unknown Project")
    df['dld_permit_no'] = df['dld_permit_no'].fillna("N/A")
    df['property_type'] = df['property_type'].fillna("Apartment")
    df['property_category'] = df['property_category'].fillna("Mid-Market")
    df['bedrooms'] = df['bedrooms'].fillna("2BR")
    df['completion_status'] = df['completion_status'].fillna("Off-Plan")
    df['construction_progress_pct'] = df['construction_progress_pct'].fillna(50.0)
    df['emirate'] = df['emirate'].fillna("Dubai")
    df['city'] = df['city'].fillna("Dubai")
    df['locality'] = df['locality'].fillna("Unknown")

    if 'possession_date' in df.columns:
        df['possession_date'] = pd.to_datetime(df['possession_date'], errors='coerce').dt.date

    df['total_units_in_project'] = df['total_units_in_project'].fillna(100).astype(int)
    df['available_units'] = df['available_units'].fillna(50).astype(int)
    df['booked_units'] = df['booked_units'].fillna(30).astype(int)
    df['registered_units'] = df['registered_units'].fillna(20).astype(int)
    df['demand_forecast_30d'] = df['demand_forecast_30d'].fillna(5).astype(int)
    df['booking_threshold'] = df['booking_threshold'].fillna(10).astype(int)
    df['days_on_market'] = df['days_on_market'].fillna(90).astype(int)
    df['unsold_flag'] = df['unsold_flag'].fillna(False).astype(bool)
    df['slow_moving_flag'] = df['slow_moving_flag'].fillna(False).astype(bool)
    df['overlaunch_flag'] = df['overlaunch_flag'].fillna(False).astype(bool)
    df['stockout_risk_score'] = df['stockout_risk_score'].fillna(0.0)
    df['holding_cost_per_day_aed'] = df['holding_cost_per_day_aed'].fillna(500.0)
    df['estimated_holding_cost_aed'] = df['estimated_holding_cost_aed'].fillna(
        df['holding_cost_per_day_aed'] * df['days_on_market']
    )
    df['units_sold_last_30d'] = df['units_sold_last_30d'].fillna(2).astype(int)
    df['units_launched_this_month'] = df['units_launched_this_month'].fillna(0).astype(int)
    df['rental_income_potential_aed'] = df['rental_income_potential_aed'].fillna(8000).astype(int)
    df['golden_visa_threshold_met'] = df['golden_visa_threshold_met'].fillna(False).astype(bool)
    df['off_plan_flag'] = df['off_plan_flag'].fillna(False).astype(bool)

    if 'last_price_revision_date' in df.columns:
        df['last_price_revision_date'] = pd.to_datetime(
            df['last_price_revision_date'], errors='coerce'
        ).dt.date

    return df


def clean_market_factors(filepath):
    df = pd.read_csv(filepath)

    df['date'] = pd.to_datetime(df['date'], format='mixed').dt.date
    df['year'] = df['year'].fillna(pd.to_datetime(df['date']).dt.year).astype(int)
    df['month'] = df['month'].fillna(pd.to_datetime(df['date']).dt.month).astype(int)
    df['quarter'] = df['quarter'].fillna("Q1")
    df['city'] = df['city'].fillna("Dubai")
    df['emirate'] = df['emirate'].fillna("Dubai")

    numeric_cols = [
        'uae_central_bank_base_rate_pct', 'mortgage_rate_avg_pct', 'oil_price_usd_bbl',
        'gdp_growth_pct', 'cpi_inflation_pct', 'consumer_confidence_index',
        'real_estate_price_index', 'transaction_volume_index', 'rental_yield_avg_pct',
        'steel_price_per_ton_aed', 'construction_cost_index', 'usd_aed_rate',
        'tourism_arrivals_index', 'foreign_investment_inflow_bn_aed',
        'institutional_investment_bn_aed', 'reit_activity_index',
        'off_plan_sales_share_pct', 'event_demand_multiplier',
        'vat_rate_pct', 'property_registration_fee_pct',
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    int_cols = [
        'new_project_launches', 'total_inventory_units', 'unsold_inventory_units',
        'golden_visa_applications', 'dld_transactions_count',
    ]
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    flag_cols = ['expo_effect', 'ramadan_month']
    for col in flag_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    df['market_event'] = df['market_event'].fillna("None")

    return df
