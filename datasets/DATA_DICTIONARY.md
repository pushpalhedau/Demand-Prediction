# AI-Powered Real Estate CEO Intelligence Platform
## Enterprise Dataset — Data Dictionary (UAE)
## Coverage: All 20 Dashboard Screens

---

## 20-Screen → Dataset Coverage Map

| # | Screen | Primary Datasets | Secondary Datasets |
|---|--------|------------------|--------------------|
| 1 | CEO Executive Dashboard | re_transactions, re_financials | re_listings, re_market_factors, re_leads_pipeline |
| 2 | AI Executive Copilot | ALL datasets | — |
| 3 | Sales Performance Dashboard | re_leads_pipeline, re_transactions | re_buyers, re_market_factors |
| 4 | Lead Intelligence Dashboard | re_leads_pipeline, re_buyers | re_transactions |
| 5 | Lead Source Quality Dashboard | re_leads_pipeline, re_transactions | re_buyers |
| 6 | Customer 360 Dashboard | re_buyers, re_transactions | re_leads_pipeline, re_communications |
| 7 | Buyer Segmentation Dashboard | re_buyers, re_transactions | re_market_factors |
| 8 | Project Performance Dashboard | re_construction_tracker, re_transactions | re_listings, re_financials |
| 9 | Construction Intelligence Dashboard | re_construction_tracker, re_contractors | re_financials |
| 10 | Inventory Intelligence Dashboard | re_listings, re_transactions | re_properties, re_market_factors |
| 11 | Pricing Intelligence Dashboard | re_transactions, re_competitor_market | re_market_factors, re_properties |
| 12 | Demand Forecast Dashboard | re_transactions, re_market_factors | re_listings, re_leads_pipeline |
| 13 | Market Intelligence Dashboard | re_competitor_market, re_market_factors | re_developers |
| 14 | Builder Launch Tracker | re_competitor_market, re_developers | re_market_factors |
| 15 | Rental Trends Dashboard | re_rental_market, re_market_factors | re_properties, re_listings |
| 16 | Investor Intelligence Dashboard | re_rental_market, re_properties | re_transactions, re_market_factors |
| 17 | Financial Intelligence Dashboard | re_financials, re_transactions | re_market_factors |
| 18 | Risk Management Dashboard | re_financials, re_construction_tracker | re_market_factors, re_transactions |
| 19 | Document Intelligence Dashboard | re_documents_registry | re_transactions, re_developers |
| 20 | Strategic Planning Dashboard | re_market_factors, re_financials | re_transactions, re_competitor_market |

---

## Dataset Overview (All 12 Datasets)

| # | File | Rows (est.) | Size (est.) | Primary Screens |
|---|------|-------------|-------------|-----------------|
| 1 | re_transactions.csv | ~100,000 | ~22 MB | 1,2,3,5,7,10,11,12,16,17 |
| 2 | re_buyers.csv | ~50,000 | ~10 MB | 4,5,6,7 |
| 3 | re_listings.csv | ~30,000 | ~6 MB | 8,10,12,15 |
| 4 | re_developers.csv | ~50 | ~0.05 MB | 13,14,19 |
| 5 | re_properties.csv | ~800 | ~0.2 MB | 10,11,15,16 |
| 6 | re_market_factors.csv | ~455 | ~0.15 MB | 1,2,12,13,15,17,18,20 |
| 7 | re_leads_pipeline.csv | ~80,000 | ~15 MB | 1,3,4,5,6 |
| 8 | re_construction_tracker.csv | ~5,000 | ~2 MB | 8,9,18 |
| 9 | re_contractors.csv | ~200 | ~0.1 MB | 9 |
| 10 | re_financials.csv | ~2,400 | ~1 MB | 1,17,18,20 |
| 11 | re_competitor_market.csv | ~3,000 | ~1 MB | 11,13,14,20 |
| 12 | re_rental_market.csv | ~5,000 | ~2 MB | 15,16 |
| 13 | re_documents_registry.csv | ~10,000 | ~3 MB | 19 |

**Date Range:** Jan 2021 – Early 2026 (all datasets aligned)
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

**Screens served:** 1 (Revenue KPIs), 3 (Sales trend), 5 (Channel conversion), 7 (Segment revenue), 10 (Absorption rate), 11 (Price benchmarks), 12 (Demand forecast target), 16 (Investor ROI base), 17 (Revenue + collections)

**Free Data Sources:**
- **DLD Open Data** (dubailand.gov.ae/en/open-data) — Real Dubai transaction records, quarterly CSV releases, DLD permit numbers, registered transactions since 2010
- **Abu Dhabi DMT** (dmt.gov.ae) — Abu Dhabi transaction records
- **data.gov.ae** — UAE government open data portal, real estate category
- **Bayut UAE Market Reports** (bayut.com/research) — Quarterly price index reports with downloadable data tables
- **PropertyFinder Market Intelligence** (propertyfinder.ae/research) — Free quarterly reports with price trends and transaction volumes

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
| estimated_lifetime_value_aed | float | Predicted total revenue from buyer over lifetime (AED) |
| properties_owned | int | Number of UAE properties currently owned |
| communication_preference | string | Email/WhatsApp/Phone/In-Person |

**Screens served:** 4 (Lead scoring), 5 (Source quality), 6 (Customer 360 profile), 7 (Buyer segments), 12 (Lead demand signal)

**Free Data Sources:**
- **Internal CRM data** (Salesforce/HubSpot/Zoho exports) — synthetic/anonymized buyer profiles
- **UAE FCSC Census** (fcsc.gov.ae) — Nationality and demographic composition of UAE residents
- **Dubai Statistics Center** (dsc.gov.ae) — Population by nationality, income proxies

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
| reserved_units | int | Units on temporary hold pending confirmation |
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
| inventory_age_bucket | string | 0-30d / 30-90d / 90-180d / 180d+ (Screen 10 aging analysis) |

**Screens served:** 1 (Inventory Available KPI), 8 (Project sales status), 10 (Inventory aging, available/sold/reserved), 12 (Supply signal for forecast)

**Free Data Sources:**
- **DLD Open Data** (dubailand.gov.ae) — Real estate project registrations, unit counts, NOC numbers
- **RERA Project Status** (dubailand.gov.ae/en/RERAServices) — Off-plan project escrow tracking, construction updates
- **Bayut / PropertyFinder listings** — Publicly listed active inventory (web scraping permitted for personal use; check TOS)
- **data.gov.ae** — UAE inventory and project launch statistics

---

## 4. re_developers.csv — Developer / Builder Master

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
| dfm_listed | bool | True if listed on Dubai Financial Market |
| adx_listed | bool | True if listed on Abu Dhabi Securities Exchange |
| market_cap_bn_aed | float | Market capitalisation in AED Bn (if listed) |
| latitude | float | HQ latitude |
| longitude | float | HQ longitude |

**Screens served:** 8 (Project performance by developer), 13 (Market intelligence), 14 (Builder launch tracker), 19 (Document registry linkage)

**Free Data Sources:**
- **DLD Developer Registry** (dubailand.gov.ae) — RERA-registered developers list, license numbers
- **DFM (Dubai Financial Market)** (dfm.ae) — Listed developer financial data (Emaar, DAMAC)
- **ADX (Abu Dhabi Securities Exchange)** (adx.ae) — Aldar Properties, SODIC data
- **Mubasher Finance** (mubasher.info) — UAE listed company profiles, financial summaries
- **LinkedIn Company Pages** — Developer profiles, team size, founding year

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
| irr_pct | float | Internal Rate of Return over 5-year hold period (%) |
| payback_period_years | float | Estimated payback period from rental income (years) |
| golden_visa_eligible | bool | Value ≥ AED 2M — buyer qualifies for UAE Golden Visa |
| vat_applicable | bool | VAT applicable (True for commercial; residential is exempt) |

**Screens served:** 10 (Product catalog for inventory), 11 (Price benchmarks), 15 (Rental yield base), 16 (ROI/IRR inputs)

**Free Data Sources:**
- **DLD Permit Database** (dubailand.gov.ae) — Property permit numbers, project details
- **RERA Project Registry** — Registered off-plan projects with unit breakdown
- **Bayut / PropertyFinder** — Price per sqft by locality, bedroom type (free market reports)
- **Knight Frank UAE Research** (knightfrank.ae/research) — Price per sqft benchmarks by area, annual reports
- **JLL UAE Market Reports** (jll.ae/en/research) — Quarterly price indices, rental yields by area

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
| google_trends_index | float | Google Trends search index for "buy property [emirate]" — 0–100 |
| nri_investment_share_pct | float | NRI (Non-Resident Indian) buyer share of transactions (%) |

**Screens served:** 1 (AI Insights macro context), 12 (Demand forecast regressors), 13 (Market intelligence), 15 (Rental market context), 17 (Financial forecasts), 18 (Risk factors), 20 (Scenario modeling inputs)

**Free Data Sources:**
- **UAE Central Bank** (centralbank.ae/en/data-and-statistics) — Base rate, mortgage rates, banking statistics; monthly CSV downloads
- **FRED - Federal Reserve** (fred.stlouisfed.org) — US Fed Funds Rate (UAE pegged), SOFR; free API (api.stlouisfed.org)
- **EIA (US Energy Information Administration)** (eia.gov/petroleum) — Brent crude weekly prices; free API (api.eia.gov)
- **World Bank Open Data** (data.worldbank.org) — UAE GDP (NY.GDP.MKTP.KD.ZG), CPI (FP.CPI.TOTL.ZG), population; free REST API
- **IMF World Economic Outlook** (imf.org/en/Publications/WEO) — UAE GDP forecasts, inflation projections; free semiannual release
- **Dubai Statistics Center** (dsc.gov.ae) — Dubai CPI, tourism arrivals, economic indicators
- **FCSC (Federal Competitiveness and Statistics Centre)** (fcsc.gov.ae) — UAE national statistics, census, economic data
- **DLD Monthly Market Report** (dubailand.gov.ae) — Transaction volumes, new launches, price indices monthly
- **Google Trends** (trends.google.com/trends/explore) — Search interest "buy apartment Dubai", "property UAE" — free CSV export; unofficial API via pytrends

---

## 7. re_leads_pipeline.csv — CRM Sales Funnel Data

Each row is one lead interaction record tracking the full funnel from inquiry to booking.
**Covers Screens: 1 (Bookings KPI), 3 (Funnel analysis), 4 (Lead intelligence), 5 (Source quality), 6 (Customer 360 comms)**

| Column | Type | Description |
|--------|------|-------------|
| lead_id | string | Unique lead record ID (LEAD000001) |
| buyer_id | string | FK → re_buyers.buyer_id (null until profiled) |
| lead_date | date | Date lead was first captured |
| lead_source | string | Google Ads/Facebook/Property Finder/Bayut/Referral/Broker/Walk-in/Property Expo/WhatsApp/Website |
| lead_campaign | string | Specific campaign name or ad set |
| lead_medium | string | CPC/Organic/Social/Email/Direct/Offline |
| utm_source | string | UTM source tag from digital campaigns |
| utm_campaign | string | UTM campaign tag |
| cost_per_lead_aed | float | Marketing spend to acquire this lead (AED) |
| lead_stage | string | New / Contacted / Qualified / Site Visit Scheduled / Site Visit Done / Proposal Sent / Negotiation / Booked / Lost |
| lead_score | int | 0–100 AI-computed quality score |
| lead_temperature | string | Hot (score 80+) / Warm (50-79) / Cold (<50) |
| property_interest | string | Property type enquired about |
| project_interest | string | Specific project of interest |
| budget_stated_aed | int | Buyer stated budget (AED) |
| contacted_date | date | Date of first contact attempt |
| qualified_date | date | Date lead was qualified |
| site_visit_scheduled_date | date | Date site visit was scheduled |
| site_visit_done_date | date | Date site visit was completed |
| proposal_sent_date | date | Date proposal/brochure was sent |
| booking_date | date | Date booking was confirmed (null if not booked) |
| lost_date | date | Date lead was marked as lost (null if active) |
| lost_reason | string | Budget/Competitor/No Response/Project Not Suitable/Timing (null if not lost) |
| salesperson_id | string | Assigned sales agent ID |
| follow_up_count | int | Number of follow-up attempts made |
| response_time_hours | float | Time from lead capture to first contact (hours) |
| time_in_stage_days | int | Days spent in current stage |
| total_funnel_days | int | Total days from lead_date to booking_date or today |
| converted | bool | True if lead reached Booked stage |
| conversion_probability | float | ML-predicted booking probability (0–1) |
| emirate_interest | string | Emirate of interest |
| locality_interest | string | Preferred locality |
| bedroom_preference | string | Studio/1BR/2BR/3BR/4BR/5BR+ |
| nri_flag | bool | True if lead is Non-Resident Indian |
| corporate_buyer_flag | bool | True if lead is a corporate/institutional buyer |
| whatsapp_engaged | bool | True if lead responded on WhatsApp |
| email_opened | bool | True if lead opened any email |
| ai_recommendation | string | AI suggested next action (Call/Schedule Visit/Send Brochure/Offer Discount) |

**Free Data Sources:**
- **HubSpot CRM Free Tier** (hubspot.com/crm) — Full CRM with lead pipeline, free forever for core CRM
- **Zoho CRM Free** (zoho.com/crm) — 3 users free, pipeline management, lead scoring
- **Google Ads Keyword Planner** (ads.google.com/home/tools/keyword-planner) — CPL estimates for digital channels
- **Meta Ads Library** (facebook.com/ads/library) — Competitor ad intelligence for real estate

---

## 8. re_construction_tracker.csv — Construction Progress Tracking

Each row is one milestone/checkpoint record per project per reporting period.
**Covers Screens: 8 (Project Performance Gantt), 9 (Construction Intelligence), 18 (Construction Risk)**

| Column | Type | Description |
|--------|------|-------------|
| record_id | string | Unique record ID (CONS000001) |
| project_id | string | FK → re_developers project reference |
| project_name | string | Project name |
| developer_id | string | FK → re_developers |
| report_date | date | Monthly reporting date |
| milestone_name | string | Foundation/Structure/MEP/Façade/Fit-Out/Handover |
| milestone_planned_start | date | Planned start date for this milestone |
| milestone_planned_end | date | Planned completion date for this milestone |
| milestone_actual_start | date | Actual start date (null if not started) |
| milestone_actual_end | date | Actual completion date (null if ongoing) |
| planned_progress_pct | float | Expected % completion at report date |
| actual_progress_pct | float | Actual % completion at report date |
| progress_variance_pct | float | actual_progress_pct - planned_progress_pct (negative = delay) |
| delay_days | int | Estimated delay in days (0 if on track) |
| delay_reason | string | Labour Shortage/Material Delay/Design Change/Weather/Regulatory/Financing |
| planned_budget_aed | float | Planned cost for this milestone phase (AED) |
| actual_cost_aed | float | Actual spend to date for this milestone (AED) |
| cost_variance_aed | float | actual_cost_aed - planned_budget_aed |
| cost_overrun_pct | float | (actual_cost - planned_budget) / planned_budget × 100 |
| total_project_budget_aed | float | Total approved project budget (AED) |
| total_spent_to_date_aed | float | Cumulative spend to date (AED) |
| budget_utilization_pct | float | total_spent / total_budget × 100 |
| contractor_id | string | FK → re_contractors |
| contractor_name | string | Primary contractor for this milestone |
| labour_deployed | int | Workers on site at report date |
| labour_planned | int | Planned workforce for current phase |
| resource_utilization_pct | float | labour_deployed / labour_planned × 100 |
| rera_inspection_passed | bool | RERA/DLD inspection cleared for this milestone |
| quality_score | float | 0–100 quality inspection score |
| safety_incidents | int | Safety incidents in reporting period |
| project_health_score | float | 0–100 composite health score (progress + cost + quality) |
| delay_risk_flag | bool | True if delay_days > 30 or progress_variance < -10% |
| escalation_flag | bool | True if cost_overrun_pct > 15% or safety_incidents > 0 |
| next_milestone | string | Name of next upcoming milestone |
| next_milestone_due_date | date | Due date for next milestone |
| handover_date_original | date | Originally committed handover date |
| handover_date_revised | date | Revised handover date (updated based on delays) |

**Free Data Sources:**
- **RERA Dubai Project Status** (dubailand.gov.ae/en/RERAServices/Escrow-Monitoring) — Escrow fund utilisation, construction milestones for RERA-registered projects
- **Abu Dhabi Urban Planning Council** (dmt.gov.ae) — Abu Dhabi project permits, completion certificates
- **Turner & Townsend International Construction Survey** (turnerandtownsend.com/insights) — Free annual construction cost benchmarks by city
- **AECOM Cost Information** (aecom.com) — Annual construction cost guide (free PDF download)
- **Trading Economics — Steel Price** (tradingeconomics.com/commodity/steel) — Steel rebar prices, construction material indices

---

## 9. re_contractors.csv — Contractor Master Data

Each row is one contractor entity (main contractor or subcontractor).
**Covers Screens: 9 (Contractor Performance panel)**

| Column | Type | Description |
|--------|------|-------------|
| contractor_id | string | Unique ID (CONT001) |
| contractor_name | string | Contractor/subcontractor company name |
| contractor_type | string | Main Contractor/MEP Contractor/Civil/Façade/Interior Fit-Out/Landscaping |
| specialization | string | Specific trade expertise |
| country_of_origin | string | Contractor HQ country |
| uae_license_no | string | UAE contractor license number (Municipality/RERA) |
| grade | string | Grade A/B/C (UAE contractor grading system) |
| established_year | int | Year of establishment |
| total_projects_completed | int | Total UAE projects completed |
| active_projects_count | int | Currently active projects |
| avg_delivery_score | float | 0–100 on-time delivery performance score |
| avg_quality_score | float | 0–100 quality inspection average |
| avg_cost_adherence_score | float | 0–100 budget compliance score |
| overall_performance_score | float | Composite 0–100 score (delivery + quality + cost) |
| safety_record_incidents | int | Total recorded safety incidents (all time) |
| rating | float | Developer satisfaction rating (1.0–5.0) |
| preferred_vendor | bool | True if on developer preferred vendor list |
| blacklisted | bool | True if contractor is blacklisted/suspended |
| daily_rate_aed | float | Average daily rate per worker (AED) |
| projects_with_this_developer | int | Number of past projects with this specific developer |

**Free Data Sources:**
- **Dubai Municipality Contractor Registry** (dm.gov.ae) — Licensed contractor list by category
- **Abu Dhabi Municipality Contractor List** (dmt.gov.ae) — Approved contractor registry
- **UAE RERA Approved Contractors** (dubailand.gov.ae) — RERA-approved construction firms

---

## 10. re_financials.csv — Financial Intelligence Data

Each row is one monthly financial summary per project or at company level.
**Covers Screens: 1 (Total Revenue, Collection Status KPIs), 17 (Financial Intelligence), 18 (Risk — collection risk), 20 (Scenario impact on revenue)**

| Column | Type | Description |
|--------|------|-------------|
| record_id | string | Unique record ID (FIN000001) |
| period_date | date | Month-end date (YYYY-MM-01) |
| year | int | Year |
| month | int | Month (1–12) |
| quarter | string | Q1/Q2/Q3/Q4 |
| entity_type | string | Company / Project |
| project_id | string | Project reference (null if company-level) |
| project_name | string | Project name (null if company-level) |
| developer_id | string | FK → re_developers |
| revenue_booked_aed | float | Revenue from confirmed bookings this month (AED) |
| revenue_registered_aed | float | Revenue from DLD-registered transactions (AED) |
| revenue_recognized_aed | float | Revenue recognized (accounting) this month (AED) |
| collections_received_aed | float | Cash actually collected from buyers this month (AED) |
| collections_outstanding_aed | float | Total outstanding receivable from buyers (AED) |
| overdue_collections_aed | float | Collections overdue >30 days (AED) |
| overdue_30_60d_aed | float | Overdue 30–60 days (AED) |
| overdue_60_90d_aed | float | Overdue 60–90 days (AED) |
| overdue_90d_plus_aed | float | Overdue >90 days — high risk (AED) |
| collection_efficiency_pct | float | collections_received / revenue_booked × 100 |
| gross_profit_aed | float | Revenue - direct construction + land cost (AED) |
| gross_margin_pct | float | gross_profit / revenue × 100 |
| operating_expenses_aed | float | SGA + marketing + overhead (AED) |
| ebitda_aed | float | Earnings before interest, tax, depreciation, amortisation (AED) |
| net_profit_aed | float | Bottom-line net profit (AED) |
| net_margin_pct | float | net_profit / revenue × 100 |
| cash_inflow_aed | float | Total cash received this month (AED) |
| cash_outflow_aed | float | Total cash paid out this month (AED) |
| net_cash_flow_aed | float | cash_inflow - cash_outflow (AED) |
| cumulative_cash_position_aed | float | Running cash balance (AED) |
| escrow_balance_aed | float | RERA escrow account balance for off-plan collections (AED) |
| construction_draw_aed | float | Funds drawn from escrow for construction this month (AED) |
| sales_target_aed | float | Monthly revenue target (AED) |
| sales_achievement_pct | float | revenue_booked / sales_target × 100 |
| pipeline_value_aed | float | Total value of leads in booking pipeline (AED) |
| forecast_next_3m_aed | float | AI revenue forecast for next 3 months (AED) |
| forecast_next_12m_aed | float | AI revenue forecast for next 12 months (AED) |
| bad_debt_provision_aed | float | Provision for uncollectable receivables (AED) |
| refunds_issued_aed | float | Booking cancellation refunds this month (AED) |
| dld_fees_collected_aed | float | DLD fees paid through transactions (AED) |
| vat_collected_aed | float | VAT collected on commercial transactions (AED) |

**Free Data Sources:**
- **DFM / ADX Financial Filings** (dfm.ae, adx.ae) — Listed developer quarterly P&L, revenue, collections (Emaar, DAMAC, Aldar)
- **Dubai Land Department Annual Report** (dubailand.gov.ae) — Total Dubai transaction values, DLD fee collections
- **UAE Central Bank Financial Stability Report** (centralbank.ae) — UAE real estate financing, mortgage NPL ratios
- **Aldar Properties Investor Relations** (aldar.com/en/investor-relations) — Free quarterly financials, project revenues (Abu Dhabi benchmark)
- **Emaar Properties Annual Report** (emaar.com/investor-relations) — Revenue recognition, collections model benchmark

---

## 11. re_competitor_market.csv — Market Intelligence & Competitor Launches

Each row is one competitor project launch or market intelligence record.
**Covers Screens: 11 (Competitor pricing), 13 (Market intelligence), 14 (Builder launch tracker), 20 (Competitor scenario)**

| Column | Type | Description |
|--------|------|-------------|
| record_id | string | Unique record ID (MKT000001) |
| record_date | date | Date of record (launch date or update date) |
| builder_name | string | Competitor builder/developer name |
| builder_tier | string | Tier 1 / Tier 2 / Tier 3 |
| project_name | string | Competitor project name |
| project_type | string | Residential/Commercial/Mixed-Use |
| property_segment | string | Affordable/Mid-Market/Premium/Luxury/Ultra-Luxury |
| property_types_offered | string | Comma-separated: Apartment/Villa/Townhouse/Commercial |
| launch_status | string | Announced/Launched/Active Selling/Sold Out/Cancelled |
| launch_date | date | Official launch date |
| expected_completion_date | date | Projected handover date |
| emirate | string | Emirate |
| city | string | City |
| locality | string | Locality/micro-market |
| latitude | float | Project latitude (for geo-mapping) |
| longitude | float | Project longitude (for geo-mapping) |
| total_units | int | Total units in competitor project |
| units_launched | int | Units put on market at launch |
| units_sold_reported | int | Sold units as publicly reported |
| price_per_sqft_min_aed | float | Minimum price per sqft (AED) |
| price_per_sqft_max_aed | float | Maximum price per sqft (AED) |
| starting_price_aed | int | Minimum unit price in project (AED) |
| payment_plan_type | string | Post-Handover/Construction-Linked/Cash/Mortgage |
| post_handover_years | int | Post-handover payment period (years, 0 if not applicable) |
| distance_from_our_project_km | float | Distance from nearest own project (km) |
| rera_registration_no | string | RERA project permit number |
| amenities_offered | string | Key amenities (pool, gym, beach, school etc.) |
| source | string | DLD Data/Bayut/PropertyFinder/News Report/Cityscape/Direct Observation |
| data_confidence | string | High/Medium/Low (based on source reliability) |
| notes | string | Additional context or analyst notes |

**Free Data Sources:**
- **DLD Project Launch Data** (dubailand.gov.ae/en/open-data) — Newly registered projects with permit data, unit counts
- **RERA Off-Plan Registry** (dubailand.gov.ae/en/RERAServices) — All RERA-registered off-plan projects publicly searchable
- **Bayut New Projects** (bayut.com/off-plan/) — Publicly listed new launches with pricing and unit info
- **PropertyFinder New Projects** (propertyfinder.ae/off-plan) — New project listings with developer info
- **Property Monitor** (propertymonitor.ae) — Dubai transaction intelligence, limited free tier
- **Gulf News Real Estate** (gulfnews.com/uae/property) — Free news coverage of new launches
- **Khaleej Times Property** (khaleejtimes.com/property) — New project announcements
- **Cityscape Intelligence** (cityscapeintelligence.com) — Annual launch data, some free reports
- **MEED Projects** (meed.com/projects) — Construction project database, limited free access

---

## 12. re_rental_market.csv — Rental Trends & Market Data

Each row is one monthly rental market record per locality/area.
**Covers Screens: 15 (Rental Trends Dashboard), 16 (Investor Intelligence ROI)**

| Column | Type | Description |
|--------|------|-------------|
| record_id | string | Unique record ID (RENT000001) |
| period_date | date | Monthly date (YYYY-MM-01) |
| year | int | Year |
| month | int | Month (1–12) |
| quarter | string | Q1/Q2/Q3/Q4 |
| emirate | string | Emirate |
| city | string | City |
| locality | string | Locality/micro-market |
| property_type | string | Apartment/Villa/Townhouse/Commercial |
| bedrooms | string | Studio/1BR/2BR/3BR/4BR/5BR+ |
| avg_annual_rent_aed | float | Average annual rent for this type/location (AED) |
| median_annual_rent_aed | float | Median annual rent (AED) |
| avg_monthly_rent_aed | float | Monthly equivalent (avg_annual_rent / 12) |
| rent_yoy_change_pct | float | Year-on-year rent change (%) |
| rent_mom_change_pct | float | Month-on-month rent change (%) |
| gross_rental_yield_pct | float | avg_annual_rent / avg_property_price × 100 |
| net_rental_yield_pct | float | (annual_rent - service_charges - mgmt_fee) / property_price × 100 |
| occupancy_rate_pct | float | % of rental units currently occupied (0–100) |
| vacancy_rate_pct | float | % of rental units vacant = 100 - occupancy_rate |
| avg_tenancy_duration_months | float | Average lease length in months |
| new_listings_count | int | New rental listings added this month |
| total_active_listings | int | Total active rental listings in this locality |
| short_term_rental_share_pct | float | % of units listed on Airbnb/short-term platforms |
| short_term_avg_daily_rate_aed | float | Average nightly rate for short-term rentals (AED) |
| short_term_occupancy_pct | float | Short-term rental occupancy rate (%) |
| short_term_annual_revenue_aed | float | Estimated annual revenue from short-term rental (AED) |
| market_avg_yield_pct | float | City-wide average rental yield for benchmarking |
| yield_vs_market_diff | float | gross_rental_yield_pct - market_avg_yield_pct |
| avg_property_price_aed | float | Average property sale price in locality (AED) |
| price_to_rent_ratio | float | avg_property_price / avg_annual_rent (lower = better for investor) |
| ejari_registrations | int | Monthly Ejari (Dubai rental contract) registrations in locality |

**Free Data Sources:**
- **Ejari / RERA Rental Data** (dubailand.gov.ae/en/RERAServices/Ejari) — Dubai rental registrations, average rents by area (Ejari data published in DLD reports)
- **RERA Rental Index** (dubailand.gov.ae) — Official Dubai rental price calculator by area, property type, bedrooms
- **Bayut Annual Rental Report** (bayut.com/research) — Free annual rental yield and price trends by area
- **PropertyFinder Rental Reports** (propertyfinder.ae/research) — Free quarterly rental market data by emirate
- **Numbeo UAE** (numbeo.com/property-investment/country_result.jsp?country=United+Arab+Emirates) — Crowdsourced rental yields and price-to-rent ratios by city
- **Airbnb/Vrbo Public Data via AirDNA** (airdna.co) — Short-term rental data; free tier available for some markets
- **Abu Dhabi Department of Municipalities** (dmt.gov.ae) — Abu Dhabi rental market reports and indices
- **Sharjah Real Estate Registration Department** (srerd.gov.ae) — Sharjah rental and transaction data

---

## 13. re_documents_registry.csv — Document Intelligence Registry

Each row is metadata for one registered document (not the document itself).
**Covers Screen: 19 (Document Intelligence Dashboard)**

| Column | Type | Description |
|--------|------|-------------|
| document_id | string | Unique document ID (DOC000001) |
| document_type | string | SPA/MOU/Title Deed/RERA NOC/Escrow Agreement/Lease Agreement/Contractor Agreement/NOC Letter/Completion Certificate |
| document_name | string | Document file name |
| project_name | string | Associated project |
| developer_id | string | FK → re_developers |
| buyer_id | string | FK → re_buyers (null for non-buyer docs) |
| contractor_id | string | FK → re_contractors (null for non-contractor docs) |
| transaction_id | string | FK → re_transactions (null if pre-transaction) |
| dld_permit_no | string | Associated DLD permit (if applicable) |
| rera_registration_no | string | Associated RERA registration (if applicable) |
| upload_date | date | Date document was uploaded to system |
| document_date | date | Document execution / issue date |
| expiry_date | date | Expiry/renewal date (null if perpetual) |
| days_to_expiry | int | Days remaining to expiry (computed) |
| expiry_status | string | Active / Expiring Soon (<30d) / Expired |
| signatory_buyer | string | Buyer signatory name |
| signatory_developer | string | Developer signatory name |
| notarized | bool | True if document is notarized |
| registered_with_dld | bool | True if registered with Dubai Land Department |
| key_clauses_extracted | string | JSON or text — AI-extracted key clauses (payment schedule, handover date, penalty clauses) |
| payment_schedule_json | string | Payment milestones extracted from SPA (JSON) |
| handover_date_in_doc | date | Handover date as stated in document |
| penalty_clause_present | bool | True if document contains delay penalty clause |
| ai_summary | string | 2–3 sentence AI-generated document summary |
| file_size_kb | float | Document file size (KB) |
| page_count | int | Number of pages |
| language | string | English/Arabic/Bilingual |
| emirate | string | Emirate this document relates to |

**Free Data Sources:**
- **DLD Document Templates** (dubailand.gov.ae) — Standard SPA, MOU, Title Deed formats and samples
- **RERA Standard Contracts** (dubailand.gov.ae/en/RERAServices) — RERA approved SPA and lease templates
- **UAE Ministry of Justice** (moj.gov.ae) — Notarization requirements, standard legal templates
- **Abu Dhabi Judicial Department** (adjd.gov.ae) — Abu Dhabi standard contract templates

---

## Relationships (Updated Star Schema)

```
re_market_factors ──(date+city)──────────────────────────────┐
re_rental_market ──(date+locality)───────────────────────────┤
re_competitor_market ──(locality+date)───────────────────────┤
                                                              ↓
re_leads_pipeline ──(buyer_id)──────────────────────────────→ RE_TRANSACTIONS ←──(developer_id)── re_developers
re_buyers ──────────────────(buyer_id)──────────────────────→ ↑                        ↑
                                                              │                re_construction_tracker
re_properties ──────────────(property_id)───────────────────→ ┘                        ↑
                                 ↑                                           re_contractors ──(contractor_id)
re_listings ──(property_id + developer_id)──┘
re_financials ──(developer_id + project)────────────────────────────────────────────────┘
re_documents_registry ──(developer_id + buyer_id + transaction_id)──────────────────────┘
```

---

## ML Module Mapping (All 20 Screens)

| Screen | Model | Primary Datasets | Features | Output |
|--------|-------|-----------------|----------|--------|
| 1 CEO Dashboard | Aggregation + anomaly detection | re_financials, re_transactions, re_listings | Monthly KPIs | KPI scorecards, trend alerts |
| 2 AI Copilot | LLM + RAG over all datasets | ALL | Natural language query | Charts + explanations + recommendations |
| 3 Sales Performance | Funnel analytics | re_leads_pipeline, re_transactions | Stage conversion rates, time-in-stage | Funnel drop-off, conversion %, trend |
| 4 Lead Intelligence | XGBoost lead scoring | re_leads_pipeline, re_buyers | age, income, lead_source, site_visit, budget, response_time | Conversion probability 0–1, temperature |
| 5 Lead Source Quality | Attribution model | re_leads_pipeline | cost_per_lead, source, converted | CPL, CPB, ROAS per source |
| 6 Customer 360 | Customer profile enrichment | re_buyers, re_transactions, re_leads_pipeline | All buyer + transaction fields | Unified 360 view + propensity score |
| 7 Buyer Segmentation | KMeans clustering (k=6) | re_buyers | income, budget, buyer_type, loyalty, past_purchases | 6 segments with revenue + CLV |
| 8 Project Performance | Gantt + progress scoring | re_construction_tracker, re_transactions | progress_pct, budget_variance, units_sold | Health score, timeline, revenue |
| 9 Construction Intelligence | Delay prediction (XGBoost) | re_construction_tracker, re_contractors | progress_variance, cost_overrun, contractor_score | Delay risk flag, days at risk |
| 10 Inventory Intelligence | Demand-supply optimization | re_listings, re_transactions | available_units, velocity, days_on_market | Aging buckets, slow-mover flags |
| 11 Pricing Intelligence | Regression + competitor benchmarking | re_transactions, re_competitor_market, re_market_factors | price_per_sqft, locality, mortgage_rate, demand_score | Optimal price, expected impact |
| 12 Demand Forecast | Prophet time-series | re_transactions, re_market_factors | transaction_date, units_sold, macro regressors | 3/6/12 month demand by location, type, price |
| 13 Market Intelligence | Geospatial clustering | re_competitor_market, re_market_factors | launch_count, locality, segment, pricing | Supply saturation heatmap, launch summary |
| 14 Builder Launch Tracker | Competitive intelligence aggregation | re_competitor_market, re_developers | builder, segment, units, pricing, status | Builder activity timeline, pricing comparison |
| 15 Rental Trends | Yield trend analysis | re_rental_market, re_market_factors | rental_yield, occupancy, ejari_registrations | Area-wise yield rankings, vacancy trend |
| 16 Investor Intelligence | Financial modelling (DCF/IRR) | re_rental_market, re_properties, re_transactions | purchase_price, rental_income, appreciation | ROI, IRR, payback period, ranked opportunities |
| 17 Financial Intelligence | Revenue + cash flow forecasting | re_financials, re_transactions | revenue, collections, cash_flow, margin | Monthly P&L, collection status, forecast |
| 18 Risk Management | Multi-dimensional risk scoring | re_financials, re_construction_tracker, re_market_factors | overdue_collections, delay_days, market_factors | Risk score per dimension, at-risk projects |
| 19 Document Intelligence | NLP/LLM document parsing | re_documents_registry | document_type, expiry_date, key_clauses | Expiring contracts, AI summary, clause extraction |
| 20 Strategic Planning | Scenario simulation (Monte Carlo) | re_market_factors, re_financials, re_competitor_market | interest_rate, competitor_count, price_change | Revenue/demand/inventory impact per scenario |

---

## Screen-by-Screen KPI Formulas

### Screen 1: CEO Executive Dashboard
| KPI | Formula | Source |
|-----|---------|--------|
| Total Revenue (AED) | SUM(revenue_booked_aed) current month | re_financials |
| Bookings This Month | COUNT(booking_date = current_month) | re_leads_pipeline |
| Collection Status (%) | SUM(collections_received) / SUM(revenue_booked) × 100 | re_financials |
| Inventory Available | SUM(available_units) across all active projects | re_listings |
| Pipeline Value (AED) | SUM(budget_stated_aed WHERE lead_stage IN [Qualified, Site Visit, Negotiation]) | re_leads_pipeline |
| Sales Conversion Rate (%) | COUNT(converted=True) / COUNT(lead_id) × 100 MTD | re_leads_pipeline |
| Project Completion % | AVG(actual_progress_pct) across active projects | re_construction_tracker |
| Occupancy Rate (%) | AVG(occupancy_rate_pct) across owned rental portfolio | re_rental_market |
| Rental Yield (%) | AVG(gross_rental_yield_pct) by locality | re_rental_market |
| Forecast Revenue (AED) | SUM(forecast_next_3m_aed) | re_financials |

### Screen 3: Sales Performance Dashboard
| KPI | Formula | Source |
|-----|---------|--------|
| Total Leads | COUNT(lead_id) MTD | re_leads_pipeline |
| Qualified Leads | COUNT(lead_stage IN [Qualified, Site Visit, Negotiation, Booked]) | re_leads_pipeline |
| Site Visits | COUNT(site_visit_done_date IS NOT NULL) MTD | re_leads_pipeline |
| Bookings | COUNT(converted=True) MTD | re_leads_pipeline |
| Conversion % | Bookings / Total Leads × 100 | re_leads_pipeline |
| Lead → Qualified Rate | Qualified / Total Leads × 100 | re_leads_pipeline |
| Avg Response Time | AVG(response_time_hours) | re_leads_pipeline |

### Screen 5: Lead Source Quality
| KPI | Formula | Source |
|-----|---------|--------|
| Cost Per Lead (AED) | SUM(cost_per_lead_aed) / COUNT(lead_id) by source | re_leads_pipeline |
| Cost Per Booking (AED) | SUM(cost_per_lead_aed) / COUNT(converted=True) by source | re_leads_pipeline |
| Conversion Rate by Source | COUNT(converted=True) / COUNT(lead_id) by source × 100 | re_leads_pipeline |

### Screen 16: Investor Intelligence (ROI Calculator)
| Output | Formula | Source |
|--------|---------|--------|
| Gross Rental Yield | avg_annual_rent / purchase_price × 100 | re_rental_market + re_properties |
| Net Rental Yield | (annual_rent - service_charges - mgmt_fee) / purchase_price × 100 | re_rental_market + re_properties |
| Capital Appreciation (5yr) | purchase_price × (1 + capital_appreciation_pct)^5 - purchase_price | re_properties |
| Total ROI | (rental_income_5yr + capital_gain) / purchase_price × 100 | computed |
| IRR | Internal rate of return on 5-year DCF | computed |
| Payback Period | purchase_price / net_annual_rental_income | computed |

---

## Comprehensive Free Data Sources

### UAE Government & Regulatory (Most Authoritative)
| Source | URL | Data Available | Format | Update Frequency |
|--------|-----|----------------|--------|-----------------|
| Dubai Land Department Open Data | dubailand.gov.ae/en/open-data | Transaction records, project registrations, permit numbers, broker registry | CSV, PDF | Quarterly |
| RERA Services Portal | dubailand.gov.ae/en/RERAServices | Off-plan project status, escrow tracking, developer registry, NOC status | Web portal | Real-time |
| Ejari Rental Index | dubailand.gov.ae (RERA calculator) | Average rent by area, bedroom type, property type | Web calculator | Annual |
| Abu Dhabi DMT Real Estate | dmt.gov.ae | Abu Dhabi transactions, permits, property values | Reports, PDF | Quarterly |
| data.gov.ae | data.gov.ae | UAE government open datasets including real estate, population, economy | CSV, JSON, API | Varies |
| Dubai Statistics Center | dsc.gov.ae | Dubai CPI, population by nationality, tourism arrivals, GDP indicators | Excel, PDF | Monthly/Annual |
| FCSC (Federal Statistics) | fcsc.gov.ae | UAE national statistics, census, economic indicators, GDP | Excel, PDF | Annual |
| Sharjah SRERD | srerd.gov.ae | Sharjah rental and transaction statistics | Reports | Quarterly |

### Financial & Economic Data (Free APIs Available)
| Source | URL | Data Available | API | Frequency |
|--------|-----|----------------|-----|-----------|
| UAE Central Bank | centralbank.ae/en/data-and-statistics | Base rate, mortgage rates, banking stats, monetary data | None (CSV download) | Monthly |
| FRED (Federal Reserve) | fred.stlouisfed.org | US Fed rate (UAE pegged), SOFR, USD rates | Yes — free API key | Daily/Monthly |
| World Bank Open Data | data.worldbank.org | UAE GDP, CPI, population, FDI, inflation | Yes — REST API (no key) | Annual |
| IMF WEO Database | imf.org/en/Publications/WEO | UAE GDP forecasts, inflation projections, current account | Excel download | Semiannual |
| EIA Petroleum Data | eia.gov/petroleum | Brent crude oil prices (weekly), energy stats | Yes — free API key | Weekly |
| Trading Economics UAE | tradingeconomics.com/united-arab-emirates | Interest rates, inflation, property prices, GDP, trade | Limited free; API paid | Daily |
| Mubasher Finance | mubasher.info | UAE listed company data, DFM/ADX market data | Web scraping | Daily |
| DFM (Dubai Financial Market) | dfm.ae | Emaar, DAMAC stock price, financial disclosures | PDF filings | Quarterly |
| ADX (Abu Dhabi Securities Exchange) | adx.ae | Aldar Properties, RAK Properties financial data | PDF filings | Quarterly |

### Property Market Research (Free Reports)
| Source | URL | Data Available | Format | Frequency |
|--------|-----|----------------|--------|-----------|
| Bayut UAE Research | bayut.com/research | Price indices, rental yields, transaction volumes by area | Interactive reports, PDF | Quarterly |
| PropertyFinder Research | propertyfinder.ae/research | Price trends, demand analysis, buyer profiles | PDF, Blog | Quarterly |
| Knight Frank Intelligence Lab | knightfrank.ae/research | UAE price indices, rental yields, investment analysis | PDF | Annual/Quarterly |
| JLL UAE Market Reports | jll.ae/en/research | Dubai/Abu Dhabi office, residential, retail market stats | PDF | Quarterly |
| CBRE UAE Research | cbre.ae/research-reports | Market snapshots, capital markets, rental data | PDF | Quarterly |
| Savills UAE Research | savills.ae/research | Prime residential, commercial, investment trends | PDF | Annual/Quarterly |
| Asteco Property Research | asteco.com/research | UAE rental and sales market data | PDF | Annual |
| Chestertons UAE Research | chestertons.ae/en-ae/research | Residential and commercial market reports | PDF | Quarterly |

### Construction & Cost Data (Free)
| Source | URL | Data Available | Format | Frequency |
|--------|-----|----------------|--------|-----------|
| Turner & Townsend Construction Survey | turnerandtownsend.com/insights | Construction cost per sqm by UAE city, labour rates | PDF | Annual |
| AECOM Cost Guide | aecom.com/services/construction-management | Building cost benchmarks, material prices UAE | PDF | Annual |
| Arcadis Construction Cost Guide | arcadis.com/en/knowledge-hub | International construction cost comparison | PDF | Annual |
| Trading Economics — Steel | tradingeconomics.com/commodity/steel | Steel rebar price index, cement prices | Web | Daily |
| Dubai Municipality Permit Stats | dm.gov.ae | Building permits issued, construction starts | PDF reports | Monthly |

### Demand Proxy & Search Data (Free)
| Source | URL | Data Available | Format | Frequency |
|--------|-----|----------------|--------|-----------|
| Google Trends | trends.google.com | Search interest: "buy apartment Dubai", "property UAE" — proxy for demand | CSV export | Daily/Weekly |
| pytrends (Python library) | pypi.org/project/pytrends | Programmatic Google Trends access | Python API | Real-time |
| Meta Ad Library | facebook.com/ads/library | Competitor real estate ad spend, creative intelligence | Web | Real-time |
| Google Ads Keyword Planner | ads.google.com/home/tools/keyword-planner | Search volume for property-related keywords | Web | Monthly |

### Tourism & Lifestyle (Free)
| Source | URL | Data Available | Format | Frequency |
|--------|-----|----------------|--------|-----------|
| Dubai Tourism Annual Report | visitdubai.com/en/business-events/tourism-performance | Tourism arrivals, hotel occupancy, nationality breakdown | PDF | Annual |
| UNWTO Statistics | unwto.org/tourism-statistics | International tourist arrivals to UAE | Excel, PDF | Annual |
| UAE GCAA Airport Traffic | gcaa.gov.ae | Dubai/Abu Dhabi/Sharjah airport passenger data | Reports | Monthly |
| Airbnb Newsroom (AirDNA) | airdna.co | Short-term rental occupancy and ADR data | Limited free | Monthly |
| Numbeo Property Investment | numbeo.com/property-investment | Price-to-rent ratios, yields, cost of living UAE cities | Web (free) | Continuously |

### Community & Crowdsourced (Free)
| Source | URL | Data Available | Format | Frequency |
|--------|-----|----------------|--------|-----------|
| Kaggle UAE Real Estate | kaggle.com/datasets (search "UAE real estate") | Community-shared UAE property datasets | CSV | Varies |
| GitHub Awesome Real Estate Data | github.com (search "UAE property data") | Open-source scrapers, datasets | Various | Varies |
| Property Monitor (Dubai) | propertymonitor.ae | Dubai transaction intelligence, RERA data | Free tier limited | Monthly |
| REIDIN Reports | reidin.com/reports | UAE real estate reports, some free | PDF | Quarterly |

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
| Dubai | Downtown Dubai, Dubai Marina, Palm Jumeirah, Dubai Hills Estate, Business Bay, JVC, Mohammed Bin Rashid City (MBR), Al Furjan, JBR, Creek Harbour, DAMAC Hills, Dubai South, Meydan, Sports City |
| Abu Dhabi | Al Reem Island, Saadiyat Island, Yas Island, Al Raha Beach, Khalifa City, Corniche, Al Reef, Masdar City |
| Sharjah | Al Majaz, Al Nahda, Muwaileh, Al Khan, Al Taawun |
| Ras Al Khaimah | Al Hamra Village, Mina Al Arab, Al Marjan Island, Hayat Island |
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
| NRI Buyer | Non-Resident Indian, investment + lifestyle | 1M – 5M | USD/INR depreciation hedge, Golden Visa, yields |
| Corporate Buyer | Company/fund purchasing commercial or residential portfolio | 5M+ | Balance sheet, staff accommodation, yield |

### Top UAE Developers by Tier
| Tier | Developers |
|------|-----------|
| Tier 1 (National) | Emaar Properties, DAMAC Properties, Aldar Properties, Nakheel, Meraas, Dubai Properties, Sobha Realty, Meydan |
| Tier 2 (Regional) | Azizi Developments, Danube Properties, Binghatti, Imtiaz Developments, Select Group, Ellington Properties, Tiger Properties, RAK Properties |
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
| UAE Flag Day / National Events | Nov–Dec | Patriotic sentiment, government policy announcements |

### Key Economic Drivers for Prophet Demand Models
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
13. `nri_investment_share_pct` — NRI buyer influx driven by USD/INR rates and UAE residency programs
14. `google_trends_index` — real-time search intent; leading indicator of 4–6 week demand pipeline
