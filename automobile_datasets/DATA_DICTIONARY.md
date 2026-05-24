# 🚗 AI-Powered Automobile Demand Intelligence Platform
## Enterprise Dataset — Data Dictionary

---

## Dataset Overview

| File | Rows | Columns | Size | Primary Use |
|------|------|---------|------|-------------|
| sales.csv | ~107,857 | 31 | 21 MB | Forecasting, YoY comparisons, revenue analytics |
| customers.csv | 50,000 | 26 | 9.8 MB | Segmentation, churn prediction, lead scoring |
| inventory.csv | 30,000 | 27 | 4.6 MB | Stock intelligence, reorder recommendations |
| dealers.csv | 500 | 20 | 0.1 MB | Regional analysis, dealer performance |
| vehicles.csv | 198 | 18 | — | Product analytics, pricing |
| external_factors.csv | 375 | 24 | — | Economic intelligence, Prophet regressors |

**Date Range:** Sales: Jan 2021 – Mar 2025 | External: Jan 2019 – Mar 2025

---

## 1. sales.csv — Transaction Data

| Column | Type | Description |
|--------|------|-------------|
| sale_id | string | Unique transaction ID (SAL0000001) |
| sale_date | date | Date of sale (YYYY-MM-DD) |
| year | int | Sale year |
| month | int | Sale month (1–12) |
| quarter | string | Q1/Q2/Q3/Q4 |
| day_of_week | string | Monday–Sunday |
| festival_period | string | Festival name or "None" |
| customer_id | string | FK → customers.customer_id |
| dealer_id | string | FK → dealers.dealer_id |
| vehicle_id | string | FK → vehicles.vehicle_id |
| brand | string | Vehicle brand |
| model | string | Vehicle model name |
| vehicle_category | string | Sedan/SUV/Hatchback/MUV/Luxury/EV/Commercial |
| fuel_type | string | Petrol/Diesel/CNG/Electric/Hybrid |
| region | string | North/South/West/East/Central |
| city | string | City of sale |
| base_price | int | Ex-showroom base price (INR) |
| discount_pct | float | Discount applied (%) |
| selling_price | int | Final vehicle price (INR) |
| accessories_revenue | int | Add-on accessories revenue |
| insurance_revenue | int | Insurance sold |
| extended_warranty | int | Extended warranty sold |
| total_revenue | int | Total transaction revenue |
| financing_type | string | Cash/Bank Loan/Dealer Finance/Lease |
| loan_amount | int | Loan amount (0 if cash) |
| units_sold | int | Always 1 per transaction |
| test_drive_converted | bool | Was test drive conducted before sale? |
| lead_to_close_days | int | Days from first lead to sale |
| salesperson_id | string | Internal salesperson reference |
| marketing_channel | string | Digital/Print/TV/Referral/Walk-in/Auto Expo |
| season_multiplier | float | Seasonal demand factor applied |

**Key use:** Prophet forecasting (ds=sale_date, y=units_sold or total_revenue), XGBoost demand prediction, YoY/MoM comparison, region heatmaps.

---

## 2. customers.csv — Customer Master

| Column | Type | Description |
|--------|------|-------------|
| customer_id | string | Unique ID (CUS000001) |
| name | string | Synthetic full name |
| age | int | Age (21–70) |
| gender | string | Male/Female/Other |
| city | string | Home city |
| region | string | North/South/West/East/Central |
| state | string | Indian state |
| occupation | string | Salaried/Business Owner/Self-Employed/Govt/Student/Retired |
| annual_income_bracket | string | <3L / 3-6L / 6-10L / 10-20L / 20-50L / >50L |
| estimated_annual_income | float | Estimated income (INR) |
| credit_score | int | 550–850 |
| number_of_past_purchases | int | Historical vehicle purchases |
| preferred_fuel_type | string | Preferred fuel |
| preferred_vehicle_category | string | Preferred category |
| customer_segment | string | Budget Buyer / Premium Buyer / EV Enthusiast / Fleet Buyer / High Repeat |
| loyalty_score | float | 0–100 loyalty index |
| marketing_response_score | float | 0–10 likelihood to respond |
| lead_source | string | Website/Walk-in/Referral/Social Media/Auto Expo/App |
| email_opt_in | bool | Email marketing consent |
| whatsapp_opted | bool | WhatsApp marketing consent |
| test_drive_taken | bool | Has taken a test drive |
| emi_preferred | bool | Prefers EMI financing |
| down_payment_capacity | int | Estimated down payment (INR) |
| registration_date | date | CRM registration date |
| last_activity_date | date | Last platform activity |
| churn_risk_score | float | 0–1 churn probability |

**Key use:** KMeans clustering (segment by income, loyalty, purchases), XGBoost lead scoring, churn prediction.

---

## 3. inventory.csv — Stock Intelligence

| Column | Type | Description |
|--------|------|-------------|
| inventory_id | string | Unique record ID |
| record_date | date | Snapshot date |
| dealer_id | string | FK → dealers |
| vehicle_id | string | FK → vehicles |
| brand / model / vehicle_category / fuel_type | string | Denormalized for fast queries |
| region / city | string | Dealer location |
| current_stock | int | Units currently in stock |
| demand_forecast_30d | int | 30-day demand forecast |
| reorder_point | int | Minimum stock threshold |
| days_in_stock | int | Average days vehicles sit in lot |
| stockout_flag | bool | True if stock = 0 |
| overstock_flag | bool | True if stock > 1.5× forecast |
| reorder_needed | bool | True if stock < reorder_point |
| stockout_risk_score | float | 0–1 stockout urgency |
| overstock_risk_score | float | 0–1 overstock risk |
| holding_cost_per_day | float | Daily holding cost (INR) |
| estimated_holding_cost | float | Total holding cost so far |
| units_sold_last_30d | int | Recent velocity |
| units_ordered | int | Units on order |
| transit_stock | int | Units in transit |
| warehouse_location | string | Zone A/B/C/D |
| last_replenishment_date | date | Last restocking date |
| supplier_lead_time_days | int | Days to receive from supplier |

**Key use:** Stockout/overstock gauge charts, reorder recommendations, inventory vs demand dual-axis charts.

---

## 4. dealers.csv — Dealer Network

| Column | Type | Description |
|--------|------|-------------|
| dealer_id | string | Unique ID (DLR0001) |
| dealer_name | string | Showroom name |
| brand | string | Authorized brand |
| region / city / state | string | Location hierarchy |
| address / pincode | string | Full address |
| tier | string | Platinum/Gold/Silver/Bronze |
| established_year | int | Year of establishment |
| monthly_capacity | int | Max monthly sales capacity |
| showroom_area_sqft | int | Showroom size |
| service_center | bool | Has service center |
| ev_charging_station | bool | Has EV charger |
| num_salespeople | int | Sales team size |
| annual_target_units | int | Annual unit target |
| performance_score | float | 45–98 performance index |
| rating | float | Customer rating (3.0–5.0) |
| latitude / longitude | float | GPS coordinates |

**Key use:** Geo heatmaps, dealer leaderboards, underperformer detection, drill-down from region→city→dealer.

---

## 5. vehicles.csv — Product Catalog

| Column | Type | Description |
|--------|------|-------------|
| vehicle_id | string | Unique ID (VH0001) |
| brand / model / variant | string | Product hierarchy |
| category | string | Sedan/SUV/Hatchback/MUV/Luxury/EV/Commercial |
| fuel_type | string | Petrol/Diesel/CNG/Electric/Hybrid |
| ex_showroom_price | int | Base ex-showroom price (INR) |
| engine_cc | int | Engine displacement |
| mileage_kmpl | float | Fuel efficiency (null for EV) |
| range_km | int | EV range (null for ICE) |
| seating_capacity | int | Number of seats |
| transmission | string | Manual/Automatic |
| body_color_options | int | Number of color variants |
| safety_rating | int | NCAP stars (3/4/5) |
| launch_year | int | Year of launch |
| is_active | bool | Currently in production |
| ev_subsidy_eligible | bool | Eligible for FAME II subsidy |
| warranty_years | int | Standard warranty period |

---

## 6. external_factors.csv — Economic Intelligence

| Column | Type | Description |
|--------|------|-------------|
| date | date | Monthly date (1st of month) |
| year / month / quarter | int/str | Time dimensions |
| region | string | Regional breakdown |
| petrol_price_per_litre | float | Regional petrol price (INR) |
| diesel_price_per_litre | float | Regional diesel price (INR) |
| gdp_growth_pct | float | GDP growth rate (%) |
| cpi_inflation_pct | float | CPI inflation (%) |
| rbi_repo_rate_pct | float | RBI repo rate (%) |
| consumer_confidence_index | float | Consumer sentiment (0–100) |
| auto_industry_index | float | Auto sector activity index |
| semiconductor_shortage | int | 0/1 shortage flag (2021–22) |
| ev_subsidy_active | int | 0/1 FAME II active |
| ev_subsidy_amount_per_vehicle | int | Subsidy per EV (INR) |
| steel_price_per_ton | float | Steel input cost (INR) |
| usd_inr_rate | float | Exchange rate |
| festival_month | int | 0/1 festival month |
| festival_name | string | Festival name or "None" |
| unemployment_rate_pct | float | Unemployment (%) |
| new_model_launches | int | New models launched that month |
| government_infra_spend_bn | float | Infra spending (INR Bn) |
| registration_tax_pct | float | Vehicle registration tax (%) |
| road_cess_pct | float | Road cess (%) |

**Key use:** Prophet external regressors (petrol prices, GDP, festivals), scenario simulation (fuel price increase, EV subsidy launch).

---

## Relationships (Star Schema)

```
external_factors ──(date+region)──┐
                                  ↓
customers ──(customer_id)──→ SALES ←──(dealer_id)── dealers
                               ↑
vehicles ──(vehicle_id)────────┘
               ↑
          inventory ──(dealer_id)── dealers
```

---

## ML Module Mapping

| Module | Primary Dataset | Features |
|--------|----------------|----------|
| Prophet Forecasting | sales + external_factors | sale_date, units_sold, petrol_price, festival_month, gdp_growth |
| XGBoost Demand Prediction | sales + customers + vehicles | age, income, region, category, fuel_type, credit_score, season |
| KMeans Segmentation | customers | estimated_income, loyalty_score, purchases, credit_score, churn_risk |
| Inventory Intelligence | inventory + sales | current_stock, demand_forecast_30d, stockout_risk, days_in_stock |
| Dealer Performance | dealers + sales | performance_score, region, tier, monthly_capacity vs actual_sales |
| SHAP Explainability | XGBoost outputs | feature_importance per prediction |

