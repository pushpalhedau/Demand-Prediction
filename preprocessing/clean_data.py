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

    df = df.drop_duplicates(subset=['transaction_id'], keep='first')

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


def _parse_date_col(df, col):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
    return df


def clean_leads_pipeline(filepath):
    df = pd.read_csv(filepath)

    date_cols = [
        'lead_date', 'contacted_date', 'qualified_date',
        'site_visit_scheduled_date', 'site_visit_done_date',
        'proposal_sent_date', 'booking_date', 'lost_date',
    ]
    for col in date_cols:
        df = _parse_date_col(df, col)

    bool_cols = ['converted', 'nri_flag', 'corporate_buyer_flag', 'whatsapp_engaged', 'email_opened']
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)

    df['lead_score'] = df['lead_score'].fillna(50).astype(int)
    df['follow_up_count'] = df['follow_up_count'].fillna(0).astype(int)
    df['time_in_stage_days'] = df['time_in_stage_days'].fillna(0).astype(int)
    df['total_funnel_days'] = df['total_funnel_days'].fillna(0).astype(int)
    df['budget_stated_aed'] = df['budget_stated_aed'].fillna(0).astype(int)

    float_cols = ['cost_per_lead_aed', 'response_time_hours', 'conversion_probability']
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    str_defaults = {
        'lead_source': 'Unknown', 'lead_campaign': 'Unknown', 'lead_medium': 'Unknown',
        'utm_source': 'Unknown', 'utm_campaign': 'Unknown', 'lead_stage': 'New',
        'lead_temperature': 'Cold', 'property_interest': 'Apartment',
        'project_interest': 'Unknown', 'lost_reason': 'None', 'salesperson_id': 'Unknown',
        'emirate_interest': 'Dubai', 'locality_interest': 'Unknown',
        'bedroom_preference': '2BR', 'ai_recommendation': 'None',
    }
    for col, default in str_defaults.items():
        if col in df.columns:
            df[col] = df[col].fillna(default)

    return df


def clean_construction_tracker(filepath):
    df = pd.read_csv(filepath)

    date_cols = [
        'report_date', 'milestone_planned_start', 'milestone_planned_end',
        'milestone_actual_start', 'milestone_actual_end',
        'next_milestone_due_date', 'handover_date_original', 'handover_date_revised',
    ]
    for col in date_cols:
        df = _parse_date_col(df, col)

    bool_cols = ['rera_inspection_passed', 'delay_risk_flag', 'escalation_flag']
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)

    int_cols = ['delay_days', 'labour_deployed', 'labour_planned', 'safety_incidents']
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    float_cols = [
        'planned_progress_pct', 'actual_progress_pct', 'progress_variance_pct',
        'planned_budget_aed', 'actual_cost_aed', 'cost_variance_aed', 'cost_overrun_pct',
        'total_project_budget_aed', 'total_spent_to_date_aed', 'budget_utilization_pct',
        'resource_utilization_pct', 'quality_score', 'project_health_score',
    ]
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    str_defaults = {
        'project_id': 'Unknown', 'project_name': 'Unknown Project',
        'developer_id': 'Unknown', 'milestone_name': 'Unknown',
        'delay_reason': 'None', 'contractor_id': 'Unknown',
        'contractor_name': 'Unknown', 'next_milestone': 'Unknown',
    }
    for col, default in str_defaults.items():
        if col in df.columns:
            df[col] = df[col].fillna(default)

    return df


def clean_contractors(filepath):
    df = pd.read_csv(filepath)

    bool_cols = ['preferred_vendor', 'blacklisted']
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)

    int_cols = ['established_year', 'total_projects_completed', 'active_projects_count',
                'safety_record_incidents', 'projects_with_this_developer']
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    float_cols = ['avg_delivery_score', 'avg_quality_score', 'avg_cost_adherence_score',
                  'overall_performance_score', 'rating', 'daily_rate_aed']
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    str_defaults = {
        'contractor_name': 'Unknown', 'contractor_type': 'Unknown',
        'specialization': 'General', 'country_of_origin': 'Unknown',
        'uae_license_no': 'N/A', 'grade': 'B',
    }
    for col, default in str_defaults.items():
        if col in df.columns:
            df[col] = df[col].fillna(default)

    return df


def clean_financials(filepath):
    df = pd.read_csv(filepath)

    df = _parse_date_col(df, 'period_date')

    df['year'] = df['year'].fillna(2024).astype(int)
    df['month'] = df['month'].fillna(1).astype(int)
    df['quarter'] = df['quarter'].fillna('Q1')
    df['entity_type'] = df['entity_type'].fillna('Project')
    df['project_id'] = df['project_id'].fillna('Unknown')
    df['project_name'] = df['project_name'].fillna('Unknown Project')
    df['developer_id'] = df['developer_id'].fillna('Unknown')

    aed_cols = [
        'revenue_booked_aed', 'revenue_registered_aed', 'revenue_recognized_aed',
        'collections_received_aed', 'collections_outstanding_aed', 'overdue_collections_aed',
        'overdue_30_60d_aed', 'overdue_60_90d_aed', 'overdue_90d_plus_aed',
        'gross_profit_aed', 'operating_expenses_aed', 'ebitda_aed', 'net_profit_aed',
        'cash_inflow_aed', 'cash_outflow_aed', 'net_cash_flow_aed',
        'cumulative_cash_position_aed', 'escrow_balance_aed', 'construction_draw_aed',
        'sales_target_aed', 'pipeline_value_aed', 'forecast_next_3m_aed',
        'forecast_next_12m_aed', 'bad_debt_provision_aed', 'refunds_issued_aed',
        'dld_fees_collected_aed', 'vat_collected_aed',
    ]
    for col in aed_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0.0)

    pct_cols = ['collection_efficiency_pct', 'gross_margin_pct', 'net_margin_pct', 'sales_achievement_pct']
    for col in pct_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    return df


def clean_competitor_market(filepath):
    df = pd.read_csv(filepath)

    date_cols = ['record_date', 'launch_date', 'expected_completion_date']
    for col in date_cols:
        df = _parse_date_col(df, col)

    int_cols = ['total_units', 'units_launched', 'units_sold_reported',
                'starting_price_aed', 'post_handover_years']
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    float_cols = ['latitude', 'longitude', 'price_per_sqft_min_aed', 'price_per_sqft_max_aed',
                  'distance_from_our_project_km']
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    str_defaults = {
        'builder_name': 'Unknown', 'builder_tier': 'Tier 2', 'project_name': 'Unknown',
        'project_type': 'Residential', 'property_segment': 'Mid-Market',
        'property_types_offered': 'Apartment', 'launch_status': 'Unknown',
        'emirate': 'Dubai', 'city': 'Dubai', 'locality': 'Unknown',
        'payment_plan_type': 'Standard', 'rera_registration_no': 'N/A',
        'amenities_offered': 'Unknown', 'source': 'Internal', 'data_confidence': 'Medium',
        'notes': '',
    }
    for col, default in str_defaults.items():
        if col in df.columns:
            df[col] = df[col].fillna(default)

    return df


def clean_rental_market(filepath):
    df = pd.read_csv(filepath)

    df = _parse_date_col(df, 'period_date')

    df['year'] = df['year'].fillna(2024).astype(int)
    df['month'] = df['month'].fillna(1).astype(int)
    df['quarter'] = df['quarter'].fillna('Q1')

    str_defaults = {
        'emirate': 'Dubai', 'city': 'Dubai', 'locality': 'Unknown',
        'property_type': 'Apartment', 'bedrooms': '2BR',
    }
    for col, default in str_defaults.items():
        if col in df.columns:
            df[col] = df[col].fillna(default)

    float_cols = [
        'avg_annual_rent_aed', 'median_annual_rent_aed', 'avg_monthly_rent_aed',
        'rent_yoy_change_pct', 'rent_mom_change_pct', 'gross_rental_yield_pct',
        'net_rental_yield_pct', 'occupancy_rate_pct', 'vacancy_rate_pct',
        'avg_tenancy_duration_months', 'short_term_rental_share_pct',
        'short_term_avg_daily_rate_aed', 'short_term_occupancy_pct',
        'short_term_annual_revenue_aed', 'market_avg_yield_pct', 'yield_vs_market_diff',
        'avg_property_price_aed', 'price_to_rent_ratio',
    ]
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    int_cols = ['new_listings_count', 'total_active_listings', 'ejari_registrations']
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    return df


def clean_documents_registry(filepath):
    df = pd.read_csv(filepath)

    date_cols = ['upload_date', 'document_date', 'expiry_date', 'handover_date_in_doc']
    for col in date_cols:
        df = _parse_date_col(df, col)

    bool_cols = ['notarized', 'registered_with_dld', 'penalty_clause_present']
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)

    df['days_to_expiry'] = df['days_to_expiry'].fillna(0).astype(int)
    df['page_count'] = df['page_count'].fillna(1).astype(int)
    df['file_size_kb'] = df['file_size_kb'].fillna(df['file_size_kb'].median())

    str_defaults = {
        'document_type': 'Unknown', 'document_name': 'Unknown',
        'project_name': 'Unknown Project', 'developer_id': 'Unknown',
        'buyer_id': 'Unknown', 'contractor_id': 'Unknown', 'transaction_id': 'Unknown',
        'dld_permit_no': 'N/A', 'rera_registration_no': 'N/A',
        'expiry_status': 'Unknown', 'signatory_buyer': 'Unknown',
        'signatory_developer': 'Unknown', 'key_clauses_extracted': '',
        'payment_schedule_json': '{}', 'ai_summary': '', 'language': 'English',
        'emirate': 'Dubai',
    }
    for col, default in str_defaults.items():
        if col in df.columns:
            df[col] = df[col].fillna(default)

    return df
