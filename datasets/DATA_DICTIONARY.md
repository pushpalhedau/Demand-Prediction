# AI-Powered Real Estate Demand Intelligence Platform
## Enterprise Dataset — Data Dictionary (UAE)

---

## UI Modules & Data Requirements

| Module | Real Estate Input Data | AI/Analytics Layer | Output/Insight | Business Use Case |
|--------|----------------------|-------------------|----------------|------------------|
| Executive Overview | Property listings, transactions, sales value, booking data | Aggregation + trend analytics | Total sales value, units sold, avg price per sq.ft, conversion rate | Leadership dashboard for performance tracking |
| Demand Forecasting | Historical sales, emirate demand, economic indicators, seasonality | Time-series forecasting (Prophet/ML) | Predicted demand by emirate, property type, price segment | Project planning, inventory release strategy |
| Price Intelligence | Property prices, competitor listings, historical trends | Regression + trend modeling | Optimal price range, price elasticity | Dynamic pricing, maximizing margins |
| Comparative Analytics | Year-wise or project-wise data, location trends | Trend comparison models | Growth by emirate/project/type, seasonal peaks | Identify high-performing markets and segments |
| Regional Intelligence | Emirate, micro-location data, transaction volumes | Geo-spatial analytics | Demand heatmaps, location attractiveness score | Site selection, expansion planning |
| Inventory Intelligence | Available units, unit types, booking status, aging inventory | Demand vs supply optimization | Unsold inventory, slow-moving units, stock gaps | Reduce holding cost, optimize unit release |
| Customer Segmentation | Buyer demographics, income, preferences, behavior | Clustering (K-Means) | Segments: Portfolio Investor, Golden Visa Seeker, End User, Rental Investor | Personalized marketing, campaign targeting |
| Lead Scoring | Lead profile, source channel, budget, interaction data | Predictive modeling | Conversion probability score | Prioritize high-quality leads |

---

## Dataset Overview

| File | Rows | Columns | Size (est.) | Primary Use |
|------|------|---------|-------------|-------------|
| re_transactions.csv | ~100,000 | 41 | ~22 MB | Forecasting, YoY comparisons, revenue analytics, price intelligence |
| re_buyers.csv | ~50,000 | 35 | ~10 MB | Segmentation, churn prediction, lead scoring |
| re_listings.csv | ~30,000 | 34 | ~6 MB | Inventory intelligence, unsold unit tracking, stock gaps |
| re_developers.csv | ~50 | 25 | ~0.05 MB | Regional analysis, developer performance, leaderboard |
| re_properties.csv | ~800 | 32 | ~0.2 MB | Product analytics, pricing catalog, ROI benchmarks |
| re_market_factors.csv | ~455 | 34 | ~0.15 MB | Economic intelligence, Prophet regressors, scenario simulation |

**Date Range:** Transactions: Jan 2021 – Early 2026 | Market Factors: Jan 2021 – Early 2026
**Geography:** Dubai, Abu Dhabi, Sharjah, Ras Al Khaimah, Ajman, Fujairah, Umm Al Quwain

---

## 1. re_transactions.csv — Property Transaction Data

Each row is one completed property transaction (booking/DLD registration).

| Column | Type | Description |
|--------|------|-------------|
| transaction_id | string | Unique transaction ID (TXN0000001) |
| transaction_date | date | Date of transaction (YYYY-MM-DD) |
| year | int | Transaction year |
| month | int | Transaction month (1–12) |
| quarter | string | Q1/Q2/Q3/Q4 |
| day_of_week | string | Monday–Sunday |
| is_ramadan_period | bool | True if transaction falls within Ramadan month |
| market_event | string | Active market event or "None" (e.g., UAE Golden Visa push, Expo 2020, Cityscape) |
| buyer_id | string | FK → re_buyers.buyer_id |
| developer_id | string | FK → re_developers.developer_id |
| property_id | string | FK → re_properties.property_id |
| project_name | string | Name of the real estate project |
| property_type | string | Apartment/Villa/Townhouse/Penthouse/Plot/Commercial/Studio |
| property_category | string | Affordable/Mid-Market/Premium/Luxury/Ultra-Luxury |
| bedrooms | string | Studio/1BR/2BR/3BR/4BR/5BR+ |
| completion_status | string | Ready/Off-Plan |
| possession_year | int | Expected or actual possession year |
| emirate | string | Dubai/Abu Dhabi/Sharjah/Ras Al Khaimah/Ajman/Fujairah/Umm Al Quwain |
| city | string | City within the emirate |
| locality | string | Micro-market/locality (Dubai Hills Estate/Downtown Dubai/Al Reem Island etc.) |
| region | string | South UAE/North UAE/Central UAE |
| area_sqft | float | Built-up area in square feet |
| base_price_aed | int | Developer base price (AED) |
| price_per_sqft_aed | float | Price per sq.ft at transaction (AED) |
| discount_pct | float | Negotiation or scheme discount (%) |
| selling_price_aed | int | Final agreed selling price (AED) |
| dld_transfer_fee_aed | int | DLD transfer fee — typically 4% of property value (AED) |
| agency_commission_aed | int | Agency/brokerage commission (AED) |
| vat_amount_aed | int | VAT paid — 5% on commercial; 0% on residential (AED) |
| service_charge_annual_aed | int | Annual service/maintenance charge (AED) |
| total_transaction_value_aed | int | selling_price + dld_fee + agency_commission + vat |
| payment_plan | string | Cash/Mortgage/Post-Handover Payment Plan (PHPP)/Deferred Payment/Construction-Linked |
| mortgage_amount_aed | int | Mortgage loan amount (0 if cash) |
| booking_amount_aed | int | Token/booking amount paid at time of booking |
| golden_visa_eligible | bool | Transaction value ≥ AED 2M — buyer qualifies for UAE Golden Visa |
| lead_to_close_days | int | Days from first inquiry to booking |
| salesperson_id | string | Internal CRM agent/broker ID |
| marketing_channel | string | Digital/Property Finder/Bayut/Social Media/Referral/Walk-in/Property Expo/WhatsApp |
| booking_converted | bool | Was initial inquiry converted to booking? |
| season_multiplier | float | Seasonal demand adjustment factor |
| freehold | bool | Freehold property (True) or Leasehold (False) |

**Key use:**
- **Executive Overview:** units_sold, total_transaction_value_aed, avg price_per_sqft_aed, booking conversion rate
- **Demand Forecasting:** Prophet (ds=transaction_date, y=units_sold or total_transaction_value_aed)
- **Price Intelligence:** price_per_sqft_aed trend by property_type, locality, completion_status, bedrooms
- **Comparative Analytics:** YoY/MoM by emirate, property_category
- **Regional Intelligence:** transaction volume heatmaps by locality/city/emirate

---

## 2. re_buyers.csv — Buyer Master

Each row is a unique buyer/lead profile.

| Column | Type | Description |
|--------|------|-------------|
| buyer_id | string | Unique ID (BUY000001) |
| name | string | Full name |
| age | int | Age (21–75) |
| gender | string | Male/Female/Other |
| nationality | string | Buyer's nationality |
| residence_city | string | Current city of residence in UAE |
| emirate | string | Current emirate of residence |
| occupation | string | Salaried/Business Owner/Self-Employed/Healthcare/Real Estate/Retired etc. |
| annual_income_bracket | string | <5K AED/mo / 5K-10K / 10K-20K / 20K-40K / 40K-80K / >80K AED/mo |
| estimated_annual_income_aed | float | Estimated annual income (AED) |
| buyer_type | string | End User/Investor/Off-Plan Investor/Portfolio Investor/HNI |
| expat_status | bool | True if expatriate (non-UAE national) |
| years_in_uae | float | Years of UAE residency |
| number_of_past_purchases | int | Prior UAE property transactions |
| preferred_property_type | string | Apartment/Villa/Townhouse/Plot/Commercial |
| preferred_property_category | string | Affordable/Mid-Market/Premium/Luxury/Ultra-Luxury |
| preferred_city | string | Preferred city for purchase |
| preferred_locality | string | Preferred locality/micro-market |
| preferred_bedrooms | string | Studio/1BR/2BR/3BR/4BR/5BR+ |
| budget_min_aed | int | Minimum stated budget (AED) |
| budget_max_aed | int | Maximum stated budget (AED) |
| customer_segment | string | Portfolio Investor / First-Home Buyer / Upgrader / Golden Visa Seeker / End User / Rental Investor |
| golden_visa_intent | bool | Intends to qualify for UAE Golden Visa through property purchase |
| off_plan_preference | bool | Prefers off-plan (under-construction) properties |
| loyalty_score | float | 0–100 repeat purchase / referral loyalty index |
| marketing_response_score | float | 0–10 likelihood to respond to campaigns |
| lead_source | string | Property Finder/Bayut/Website/Referral/Social Media/Property Expo/WhatsApp/App |
| email_opt_in | bool | Email marketing consent |
| whatsapp_opted | bool | WhatsApp campaign consent |
| site_visit_taken | bool | Has visited project site or show flat |
| mortgage_preferred | bool | Prefers mortgage financing |
| down_payment_capacity_aed | int | Estimated down payment capacity (AED) |
| registration_date | date | CRM registration date |
| last_activity_date | date | Last platform interaction date |
| churn_risk_score | float | 0–1 churn/dropout probability |

**Key use:**
- **Customer Segmentation:** KMeans on age, income, buyer_type, expat_status, loyalty_score, past_purchases, budget, golden_visa_intent, off_plan_preference
  → Segments: Portfolio Investor, First-Home Buyer, Upgrader, Golden Visa Seeker, End User, Rental Investor
- **Lead Scoring:** XGBoost on site_visit_taken, lead_source, budget, marketing_response_score, golden_visa_intent → booking_converted
- **SHAP Explainability:** feature importance per conversion prediction

---

## 3. re_listings.csv — Property Inventory Snapshot

Each row is a point-in-time inventory snapshot per project per configuration.

| Column | Type | Description |
|--------|------|-------------|
| listing_id | string | Unique snapshot record ID |
| record_date | date | Snapshot date |
| developer_id | string | FK → re_developers |
| property_id | string | FK → re_properties |
| project_name | string | Project name |
| dld_permit_no | string | DLD (Dubai Land Department) permit/NOC number |
| property_type | string | Apartment/Villa/Townhouse/Penthouse/Plot/Commercial |
| property_category | string | Affordable/Mid-Market/Premium/Luxury/Ultra-Luxury |
| bedrooms | string | Studio/1BR/2BR/3BR/4BR/5BR+ |
| completion_status | string | Ready/Off-Plan |
| construction_progress_pct | float | % construction completion (Off-Plan only) |
| possession_date | date | Scheduled possession/handover date |
| emirate | string | Emirate |
| city | string | City |
| locality | string | Locality/micro-market |
| total_units_in_project | int | Total units approved in project |
| available_units | int | Units currently available for sale |
| booked_units | int | Units with confirmed bookings |
| registered_units | int | Units with completed DLD registration |
| demand_forecast_30d | int | 30-day demand forecast (units) |
| booking_threshold | int | Minimum bookings to trigger next phase launch |
| days_on_market | int | Average days units listed without booking |
| unsold_flag | bool | True if available_units > 0 beyond 6 months of launch |
| slow_moving_flag | bool | True if days_on_market > emirate/category average |
| overlaunch_flag | bool | True if available_units > 1.5× demand_forecast_30d |
| stockout_risk_score | float | 0–1 urgency score (near sold-out risk) |
| holding_cost_per_day_aed | float | Daily carrying/finance cost per unsold unit (AED) |
| estimated_holding_cost_aed | float | Total accrued holding cost for unsold units (AED) |
| units_sold_last_30d | int | Booking velocity last 30 days |
| units_launched_this_month | int | New units released this month |
| rental_income_potential_aed | int | Monthly rental income potential if leased (AED) |
| last_price_revision_date | date | Date of last listed price revision |
| golden_visa_threshold_met | bool | True if property price ≥ AED 2M (Golden Visa eligibility) |
| off_plan_flag | bool | True if property is off-plan/under-construction |

**Key use:**
- **Inventory Intelligence:** available_units, unsold_flag, slow_moving_flag, holding_cost_aed, days_on_market
- **Supply Trends:** units_launched_this_month, total_units_in_project, construction_progress_pct, off_plan_flag
- **Executive Overview:** absorption rate = units_sold_last_30d / available_units
- **Golden Visa Tracking:** golden_visa_threshold_met units count by locality

---

## 4. re_developers.csv — Developer Network

Each row is a real estate developer/builder operating in UAE.

| Column | Type | Description |
|--------|------|-------------|
| developer_id | string | Unique ID (DEV0001) |
| developer_name | string | Developer/builder company name |
| developer_type | string | Developer/Boutique Developer/Channel Partner/Brokerage |
| primary_city | string | Primary city of operation |
| operating_cities | string | Comma-separated list of active cities |
| emirate | string | Emirate of headquarters |
| address | string | Registered HQ address |
| tier | string | Tier 1 / Tier 2 / Tier 3 (by UAE market share) |
| established_year | int | Year of establishment |
| rera_registration_no | string | RERA/DLD developer registration number |
| rera_registered | bool | Active RERA/DLD registration |
| adm_registered | bool | Abu Dhabi Municipality (ADM) registration |
| monthly_capacity_units | int | Max monthly new unit launches |
| office_area_sqft | int | Corporate office / experience centre size |
| num_agents | int | Active sales agents/channel partners |
| annual_target_units | int | Annual sales/booking target |
| performance_score | float | 0–100 performance index |
| rating | float | Buyer satisfaction rating (1.0–5.0) |
| total_projects_launched | int | Lifetime projects launched |
| active_projects | int | Currently under-construction + selling projects |
| completed_projects | int | Delivered/handover-completed projects |
| specialization | string | Residential/Commercial/Mixed-Use/Luxury/Affordable/Plotted |
| off_plan_focus | bool | True if developer primarily sells off-plan |
| latitude | float | HQ latitude |
| longitude | float | HQ longitude |

**Key use:**
- **Regional Intelligence:** developer geo-distribution, project coverage heatmaps by emirate/city
- **Comparative Analytics:** developer performance leaderboard, Tier 1 vs Tier 2 market share
- **Executive Overview:** top developers by revenue, units sold, DLD/RERA compliance

---

## 5. re_properties.csv — Property Product Catalog

Each row is a unique property configuration within a project.

| Column | Type | Description |
|--------|------|-------------|
| property_id | string | Unique ID (PROP0001) |
| project_name | string | Project name |
| developer_id | string | FK → re_developers |
| dld_permit_no | string | DLD permit/NOC number |
| property_type | string | Apartment/Villa/Townhouse/Penthouse/Plot/Commercial/Studio |
| property_category | string | Affordable/Mid-Market/Premium/Luxury/Ultra-Luxury |
| bedrooms | string | Studio/1BR/2BR/3BR/4BR/5BR+ |
| bathrooms | int | Number of bathrooms |
| carpet_area_sqft_min | float | Minimum net area (sq.ft) |
| carpet_area_sqft_max | float | Maximum net area (sq.ft) |
| builtup_area_sqft | float | Built-up area including common areas |
| base_price_aed | int | Developer listed base price (AED) |
| price_per_sqft_aed | float | Base price per sq.ft (AED) |
| emirate | string | Emirate |
| city | string | City |
| locality | string | Locality/micro-market |
| region | string | South UAE/North UAE/Central UAE |
| total_floors | int | Number of floors in building/tower |
| parking_spaces | int | Covered parking included |
| amenities_score | float | 0–10 score (pool, gym, concierge, beach access, retail, school proximity) |
| completion_status | string | Ready/Off-Plan |
| launch_year | int | Year of project launch |
| possession_year | int | Scheduled possession year |
| is_active | bool | Currently available for sale |
| freehold | bool | Freehold property (True) or Leasehold (False) |
| leasehold_years | int | Leasehold duration in years (0 if freehold) |
| service_charge_aed_sqft | float | Annual service charge per sq.ft (AED) |
| rental_yield_pct | float | Expected gross rental yield (%) |
| capital_appreciation_pct | float | Expected annual capital appreciation (%) |
| roi_pct | float | Blended ROI estimate (rental yield + appreciation) |
| golden_visa_eligible | bool | Value ≥ AED 2M — buyer qualifies for UAE Golden Visa |
| vat_applicable | bool | VAT applicable (True for commercial; residential is exempt) |

**Key use:**
- **Price Intelligence:** price_per_sqft_aed benchmarks by property_type, locality, emirate, bedrooms
- **Inventory Intelligence:** product catalog for unsold unit analysis
- **Customer Segmentation:** preferred_property_type + preferred_bedrooms → product matching
- **Investment Trends:** rental_yield_pct, capital_appreciation_pct, roi_pct, golden_visa_eligible, freehold

---

## 6. re_market_factors.csv — Economic & Market Intelligence

Monthly macro/market indicators for UAE real estate, broken down by city/emirate.

| Column | Type | Description |
|--------|------|-------------|
| date | date | Monthly date (1st of month) |
| year | int | Year |
| month | int | Month (1–12) |
| quarter | string | Q1/Q2/Q3/Q4 |
| city | string | City-level breakdown |
| emirate | string | Emirate |
| uae_central_bank_base_rate_pct | float | UAE Central Bank base rate (%) — pegged to US Fed funds rate |
| mortgage_rate_avg_pct | float | Average UAE mortgage rate — ENBD/FAB/ADCB weighted avg (%) |
| oil_price_usd_bbl | float | Brent crude price (USD/barrel) — key UAE fiscal revenue driver |
| gdp_growth_pct | float | UAE GDP growth rate (%) |
| cpi_inflation_pct | float | CPI inflation rate (%) |
| consumer_confidence_index | float | Consumer sentiment index (0–100) |
| real_estate_price_index | float | Emirate-level residential price index |
| transaction_volume_index | float | Monthly DLD transaction volume index vs baseline |
| rental_yield_avg_pct | float | Average gross rental yield in city/emirate (%) |
| new_project_launches | int | New DLD/RERA-registered projects launched that month |
| total_inventory_units | int | Total tracked units in emirate/city |
| unsold_inventory_units | int | Units listed >6 months without booking |
| steel_price_per_ton_aed | float | Steel price (AED/ton) — construction cost driver |
| construction_cost_index | float | Composite building material + labour cost index |
| usd_aed_rate | float | USD/AED exchange rate (pegged ~3.6725) |
| tourism_arrivals_index | float | Tourist arrivals index — proxy for short-term rental and hospitality-linked demand |
| foreign_investment_inflow_bn_aed | float | Foreign real estate investment inflows (AED Bn) |
| institutional_investment_bn_aed | float | PE/fund/REIT institutional investment (AED Bn) |
| reit_activity_index | float | Listed REIT transaction and NAV activity index |
| golden_visa_applications | int | Monthly Golden Visa property investment applications |
| off_plan_sales_share_pct | float | Off-plan as % of total property sales that month |
| dld_transactions_count | int | Total DLD-registered transactions that month |
| expo_effect | int | 0/1 — Dubai Expo 2020 effect period (Oct 2021–Mar 2022) |
| ramadan_month | int | 0/1 — Ramadan month (typically slower transaction activity) |
| market_event | string | Active market event or "None" |
| event_demand_multiplier | float | Demand multiplier for active market event |
| vat_rate_pct | float | VAT rate (%) — 5% on commercial property |
| property_registration_fee_pct | float | DLD property registration fee (% of transaction value) |

**Key use:**
- **Demand Forecasting:** Prophet regressors — uae_central_bank_base_rate, mortgage_rate, consumer_confidence, ramadan_month, golden_visa_applications, expo_effect, event_demand_multiplier
- **Price Intelligence:** real_estate_price_index trend, mortgage_rate impact on affordability, off_plan_sales_share_pct
- **Investment Trends:** foreign_investment_inflow, institutional_investment, reit_activity_index, golden_visa_applications
- **Scenario Simulation:** rate hike, Golden Visa threshold change, VAT revision, supply surge impact

---

## Relationships (Star Schema)

```
re_market_factors ──(date+city)──┐
                                 ↓
re_buyers ──(buyer_id)──→ RE_TRANSACTIONS ←──(developer_id)── re_developers
                                 ↑
re_properties ──(property_id)────┘
                    ↑
            re_listings ──(developer_id)── re_developers
```

---

## ML Module Mapping

| Module | Primary Dataset | Features | Output |
|--------|----------------|----------|--------|
| Prophet Demand Forecasting | re_transactions + re_market_factors | transaction_date, units_sold, uae_base_rate, mortgage_rate, ramadan_month, expo_effect, golden_visa_applications, consumer_confidence, event_demand_multiplier | Predicted units/revenue by emirate, property_type, price_segment |
| XGBoost Lead Scoring | re_transactions + re_buyers | age, income, buyer_type, expat_status, site_visit, lead_source, budget, golden_visa_intent, off_plan_preference, mortgage_preferred | booking_converted probability |
| KMeans Buyer Segmentation | re_buyers | estimated_income, past_purchases, buyer_type, budget_max, loyalty_score, golden_visa_intent, off_plan_preference, years_in_uae | 6 segments: Portfolio Investor / First-Home Buyer / Upgrader / Golden Visa Seeker / End User / Rental Investor |
| Price Intelligence Model | re_transactions + re_properties + re_market_factors | price_per_sqft_aed, locality, property_type, bedrooms, amenities_score, mortgage_rate, freehold, completion_status | Optimal price range, price elasticity score |
| Inventory Intelligence | re_listings + re_transactions | available_units, demand_forecast_30d, days_on_market, holding_cost_aed, off_plan_flag, golden_visa_threshold_met | Unsold unit risk, slow-mover flag, absorption rate |
| Developer Performance | re_developers + re_transactions | performance_score, tier, emirate, monthly_capacity vs actual_bookings, rera_registered, off_plan_focus | Leaderboard, underperformer flags, DLD compliance |
| SHAP Explainability | XGBoost outputs | Feature importance per lead score prediction | Top drivers: site_visit > income > buyer_type > lead_source > golden_visa_intent |

---

## Key Metrics per UI Module

### Executive Overview
| KPI | Formula | Source |
|-----|---------|--------|
| Total Sales Value (AED) | SUM(total_transaction_value_aed) | re_transactions |
| Units Sold / Booked | COUNT(transaction_id) | re_transactions |
| Avg Price per Sq.Ft (AED) | AVG(price_per_sqft_aed) | re_transactions |
| Booking Conversion Rate | COUNT(booking_converted=True) / COUNT(all_leads) | re_transactions + re_buyers |
| Inventory Absorption Rate | units_sold_last_30d / available_units | re_listings |
| Golden Visa Eligible Transactions | COUNT(golden_visa_eligible=True) | re_transactions |
| DLD Transfer Fees Collected | SUM(dld_transfer_fee_aed) | re_transactions |

### Demand Trends
| Signal | Metric | Source |
|--------|--------|--------|
| Property searches | Lead registrations COUNT per period | re_buyers.registration_date |
| Lead inquiries | New CRM buyer entries | re_buyers |
| Site visits | site_visit_taken COUNT | re_buyers |
| Mortgage applications | mortgage_preferred + lead pipeline | re_buyers |
| Booking rates | booking_converted rate MoM | re_transactions |
| Golden Visa applications | golden_visa_applications monthly | re_market_factors |

### Price Trends
| Signal | Metric | Source |
|--------|--------|--------|
| Property price appreciation | price_per_sqft_aed YoY % change | re_transactions |
| Price per sq.ft growth | Trend by locality, emirate, property_type | re_transactions |
| Rental yield growth | rental_yield_avg_pct trend | re_market_factors + re_properties |
| Off-plan vs ready price gap | price_per_sqft_aed by completion_status | re_transactions |

### Supply Trends
| Signal | Metric | Source |
|--------|--------|--------|
| New project launches | new_project_launches (DLD-registered) monthly | re_market_factors |
| Inventory availability | total_inventory_units, available_units by emirate | re_listings + re_market_factors |
| Unsold inventory | unsold_inventory_units, unsold_flag (>6 months) | re_listings + re_market_factors |
| Construction pipeline | construction_progress_pct, possession_date | re_listings |
| Off-plan sales share | off_plan_sales_share_pct | re_market_factors |

### Investment Trends
| Signal | Metric | Source |
|--------|--------|--------|
| Investor activity | buyer_type=Investor/Off-Plan Investor share of transactions | re_transactions + re_buyers |
| Institutional investments | institutional_investment_bn_aed | re_market_factors |
| REIT investments | reit_activity_index | re_market_factors |
| Foreign investment inflows | foreign_investment_inflow_bn_aed | re_market_factors |
| Golden Visa pipeline | golden_visa_applications monthly | re_market_factors |
| Freehold vs leasehold split | COUNT by freehold flag | re_transactions + re_properties |

### Location Trends
| Signal | Metric | Source |
|--------|--------|--------|
| Emerging micro-markets | Localities with highest YoY transaction growth | re_transactions |
| High-growth localities | price_per_sqft_aed growth rate by locality | re_transactions |
| Infrastructure-driven corridors | market_event + locality correlation | re_market_factors + re_properties |
| Golden Visa hotspots | golden_visa_eligible transactions by locality | re_transactions |

---

## UAE-Specific Reference Data

### Emirates & Cities Covered
| Emirate | Key Cities | Tier |
|---------|-----------|------|
| Dubai | Dubai | 1 |
| Abu Dhabi | Abu Dhabi, Al Ain | 1 |
| Sharjah | Sharjah | 1 |
| Ras Al Khaimah | Ras Al Khaimah | 2 |
| Ajman | Ajman | 2 |
| Fujairah | Fujairah | 2 |
| Umm Al Quwain | Umm Al Quwain | 3 |

### Key Micro-Markets per Emirate
| Emirate | Key Localities |
|---------|---------------|
| Dubai | Downtown Dubai, Dubai Marina, Palm Jumeirah, Dubai Hills Estate, Business Bay, JVC, Mohammed Bin Rashid City (MBR), Al Furjan, JBR, Creek Harbour, DAMAC Hills |
| Abu Dhabi | Al Reem Island, Saadiyat Island, Yas Island, Al Raha Beach, Khalifa City, Corniche, Al Reef |
| Sharjah | Al Majaz, Al Nahda, Muwaileh, Al Khan |
| Ras Al Khaimah | Al Hamra Village, Mina Al Arab, Al Marjan Island |
| Umm Al Quwain | UAQ Free Trade Zone |

### Property Categories vs Price Bands (AED per sq.ft)
| Category | Total Price Range | Apartments (AED/sq.ft) | Villas/Townhouses (AED/sq.ft) |
|----------|------------------|-----------------------|------------------------------|
| Affordable | < AED 500K | 500–900 | 300–600 |
| Mid-Market | AED 500K – 1.5M | 900–1,500 | 600–1,200 |
| Premium | AED 1.5M – 3M | 1,500–3,000 | 1,200–2,500 |
| Luxury | AED 3M – 10M | 3,000–7,000 | 2,500–6,000 |
| Ultra-Luxury | > AED 10M | 7,000+ | 6,000+ |

### Buyer Segments (UAE)
| Segment | Profile | Typical Budget (AED) | Key Driver |
|---------|---------|---------------------|-----------|
| Portfolio Investor | Multi-property buyer, yield/appreciation focused | 1M – 10M+ | Rental income, capital appreciation, off-plan discount |
| First-Home Buyer | UAE resident, end-use purchase | 400K – 1.5M | Mortgage affordability, location, schools |
| Upgrader | Trading up from smaller/older unit | 1M – 3M | Lifestyle upgrade, better community, amenities |
| Golden Visa Seeker | Investment + UAE residency | 2M+ | AED 2M threshold unlocks 10-year UAE residency |
| End User | Long-term occupier, community-focused | 500K – 2M | Freehold title, community, amenities |
| Rental Investor | Yield-focused, typically off-plan | 500K – 3M | Rental yield, short-term rental potential, off-plan discount |

### Top UAE Developers by Tier
| Tier | Developers |
|------|-----------|
| Tier 1 (National) | Emaar Properties, DAMAC Properties, Aldar Properties, Nakheel, Meraas, Dubai Properties, Sobha Realty, Meydan |
| Tier 2 (Regional) | Azizi Developments, Danube Properties, Binghatti, Imtiaz Developments, Select Group, Ellington Properties, Tiger Properties |
| Tier 3 (Boutique) | Smaller/niche developers; locality-specific and luxury boutique projects |

### Key Market Events / Property Seasons (UAE)
| Event | Period | Impact |
|-------|--------|--------|
| Cityscape Global | Oct–Nov | Annual property expo — major launches, developer discounts, off-plan deals |
| UAE National Day | December | Government announcements, new project launches |
| Dubai Expo 2020 Effect | Oct 2021 – Mar 2022 | Tourism and foreign investment surge; transaction spike |
| UAE Golden Visa Push | Ongoing | Properties ≥ AED 2M surge in demand for residency eligibility |
| Ramadan | Mar–Apr (varies) | Typically slower transactions; post-Ramadan rebound |
| Summer Slowdown | Jul–Aug | Off-peak; many buyers travel; slower season |
| Q4 Year-End Push | Oct–Dec | Developer year-end promotions, flexible payment plans |

### Key Economic Drivers for Prophet Models
1. `uae_central_bank_base_rate_pct` — pegged to US Fed rate; rate hike → mortgage cost rise → demand dip
2. `mortgage_rate_avg_pct` — direct monthly payment affordability; most sensitive demand lever
3. `ramadan_month` — typically slower transaction activity; post-Ramadan surge
4. `consumer_confidence_index` — leading indicator; tracks employment & business sentiment
5. `golden_visa_applications` — strong demand driver for properties ≥ AED 2M
6. `expo_effect` — Dubai Expo 2020 created a measurable investment and transaction surge
7. `new_project_launches` — supply signal; excess launches → price pressure
8. `tourism_arrivals_index` — proxy for short-term rental demand and hospitality-linked investment
9. `foreign_investment_inflow_bn_aed` — offshore capital flows amplify demand cycles
10. `off_plan_sales_share_pct` — high off-plan share signals speculative activity; leading risk indicator
11. `oil_price_usd_bbl` — UAE fiscal health; high oil → government spending → infrastructure → real estate demand
12. `event_demand_multiplier` — quantifies demand uplift from Cityscape, National Day, and other market events
