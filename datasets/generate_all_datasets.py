"""
generate_all_datasets.py
========================
Generates / extends all 13 datasets for the CEO Real Estate Intelligence Platform.
Coverage: January 2019 – May 2026 (UAE)

Run:  python datasets/generate_all_datasets.py
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
import random
import os
import math

np.random.seed(42)
random.seed(42)

BASE = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────────────────
# SHARED REFERENCE DATA
# ─────────────────────────────────────────────────────────────────────────────

EMIRATES = ['Dubai', 'Abu Dhabi', 'Sharjah', 'Ras Al Khaimah', 'Ajman', 'Fujairah', 'Umm Al Quwain']

LOCALITIES = {
    'Dubai': ['Downtown Dubai', 'Dubai Marina', 'Palm Jumeirah', 'Dubai Hills Estate',
              'Business Bay', 'JVC', 'MBR City', 'Al Furjan', 'JBR', 'Creek Harbour',
              'DAMAC Hills', 'Dubai South', 'Meydan', 'Sports City'],
    'Abu Dhabi': ['Al Reem Island', 'Saadiyat Island', 'Yas Island', 'Al Raha Beach',
                  'Khalifa City', 'Corniche', 'Al Reef', 'Masdar City'],
    'Sharjah': ['Al Majaz', 'Al Nahda', 'Muwaileh', 'Al Khan', 'Al Taawun'],
    'Ras Al Khaimah': ['Al Hamra Village', 'Mina Al Arab', 'Al Marjan Island', 'Hayat Island'],
    'Ajman': ['Al Nuaimiyah', 'Al Rashidiya', 'Corniche Ajman'],
    'Fujairah': ['Fujairah City', 'Dibba Al Fujairah'],
    'Umm Al Quwain': ['UAQ Free Trade Zone', 'Umm Al Quwain City'],
}

REGION_MAP = {
    'Dubai': 'South UAE', 'Abu Dhabi': 'Central UAE', 'Sharjah': 'North UAE',
    'Ras Al Khaimah': 'North UAE', 'Ajman': 'North UAE',
    'Fujairah': 'North UAE', 'Umm Al Quwain': 'North UAE',
}

PROPERTY_TYPES = ['Apartment', 'Villa', 'Townhouse', 'Penthouse', 'Plot', 'Commercial', 'Studio']
PROPERTY_CATEGORIES = ['Affordable', 'Mid-Market', 'Premium', 'Luxury', 'Ultra-Luxury']
BEDROOMS = ['Studio', '1BR', '2BR', '3BR', '4BR', '5BR+']
PAYMENT_PLANS = ['Cash', 'Mortgage', 'Post-Handover Payment Plan (PHPP)', 'Deferred Payment', 'Construction-Linked']
MARKETING_CHANNELS = ['Digital', 'Property Finder', 'Bayut', 'Social Media', 'Referral', 'Walk-in', 'Property Expo', 'WhatsApp']

RAMADAN = {2019:(5,6), 2020:(4,5), 2021:(4,5), 2022:(4,5), 2023:(3,4), 2024:(3,4), 2025:(3,4), 2026:(3,4)}

PRICE_BANDS = {
    'Affordable':   (300_000,   500_000),
    'Mid-Market':   (500_000,  1_500_000),
    'Premium':     (1_500_000, 3_000_000),
    'Luxury':      (3_000_000,10_000_000),
    'Ultra-Luxury':(10_000_000,35_000_000),
}

def market_event(dt):
    y, m = dt.year, dt.month
    if (y == 2021 and m >= 10) or (y == 2022 and m <= 3):
        return 'Dubai Expo 2020', 1.35
    if m in [10, 11]:
        return 'Cityscape Global', 1.20
    if m == 12:
        return 'UAE National Day', 1.10
    return 'None', 1.0

def ramadan_flag(dt):
    r = RAMADAN.get(dt.year, (13, 14))
    return 1 if dt.month in r else 0

def quarter(m):
    return f'Q{(m - 1) // 3 + 1}'

def date_range_months(start_year, start_month, end_year, end_month):
    """Yield (year, month) tuples inclusive."""
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1

def rand_date(year, month):
    days = [31,28,31,30,31,30,31,31,30,31,30,31][month - 1]
    if year % 4 == 0 and month == 2:
        days = 29
    return date(year, month, random.randint(1, days))

# ─────────────────────────────────────────────────────────────────────────────
# LOAD EXISTING DATA
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("Loading existing datasets …")
txn        = pd.read_csv(f'{BASE}/re_transactions.csv')
buyers     = pd.read_csv(f'{BASE}/re_buyers.csv')
listings   = pd.read_csv(f'{BASE}/re_listings.csv')
developers = pd.read_csv(f'{BASE}/re_developers.csv')
properties = pd.read_csv(f'{BASE}/re_properties.csv')
mf         = pd.read_csv(f'{BASE}/re_market_factors.csv')

buyer_ids    = buyers['buyer_id'].tolist()
dev_ids      = developers['developer_id'].tolist()
prop_ids     = properties['property_id'].tolist()
proj_names   = txn['project_name'].unique().tolist()
sp_ids       = [f'SP{i:04d}' for i in range(1, 101)]

print(f"  txn={len(txn):,}  buyers={len(buyers):,}  listings={len(listings):,}")
print(f"  developers={len(developers)}  properties={len(properties):,}  market_factors={len(mf):,}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — ADD MISSING COLUMNS TO EXISTING DATASETS
# ─────────────────────────────────────────────────────────────────────────────

print("\n[1/10] Patching existing datasets with missing columns …")

# ── re_buyers.csv ────────────────────────────────────────────
if 'estimated_lifetime_value_aed' not in buyers.columns:
    buyers['estimated_lifetime_value_aed'] = (
        buyers['budget_max_aed'] * np.random.uniform(1.1, 3.5, len(buyers))
    ).round(0).astype(int)
if 'properties_owned' not in buyers.columns:
    buyers['properties_owned'] = np.random.choice(
        [0,1,2,3,4,5], len(buyers), p=[0.30,0.35,0.20,0.10,0.03,0.02])
if 'communication_preference' not in buyers.columns:
    buyers['communication_preference'] = np.random.choice(
        ['WhatsApp','Email','Phone','In-Person'], len(buyers), p=[0.45,0.25,0.20,0.10])
buyers.to_csv(f'{BASE}/re_buyers.csv', index=False)
print(f"  re_buyers.csv        -> {len(buyers):,} rows, {len(buyers.columns)} cols")

# ── re_market_factors.csv ────────────────────────────────────
if 'google_trends_index' not in mf.columns:
    vals = []
    for _, r in mf.iterrows():
        yr, mo = int(r['year']), int(r['month'])
        seasonal = 10 * math.sin(2 * math.pi * (mo - 3) / 12)
        covid    = -28 if (yr == 2020 and mo in [4,5,6]) else 0
        growth   = (yr - 2019) * 4.0
        v = 58 + seasonal + covid + growth + np.random.normal(0, 3)
        vals.append(round(max(10, min(100, v)), 1))
    mf['google_trends_index'] = vals

if 'nri_investment_share_pct' not in mf.columns:
    mf['nri_investment_share_pct'] = [
        round(18 + (int(r['year']) - 2019) * 1.5 + np.random.uniform(-2, 2), 1)
        for _, r in mf.iterrows()
    ]
mf.to_csv(f'{BASE}/re_market_factors.csv', index=False)
print(f"  re_market_factors    -> {len(mf):,} rows, {len(mf.columns)} cols")

# ── re_developers.csv ────────────────────────────────────────
if 'dfm_listed' not in developers.columns:
    dfm = {'Emaar Properties', 'DAMAC Properties'}
    adx = {'Aldar Properties', 'RAK Properties'}
    caps = {'Emaar Properties':52.0,'DAMAC Properties':18.5,'Aldar Properties':38.0,'RAK Properties':4.2}
    developers['dfm_listed']       = developers['developer_name'].isin(dfm)
    developers['adx_listed']       = developers['developer_name'].isin(adx)
    developers['market_cap_bn_aed']= developers['developer_name'].map(caps).fillna(0.0)
developers.to_csv(f'{BASE}/re_developers.csv', index=False)
print(f"  re_developers.csv    -> {len(developers)} rows, {len(developers.columns)} cols")

# ── re_properties.csv ────────────────────────────────────────
if 'irr_pct' not in properties.columns:
    properties['irr_pct'] = (properties['roi_pct'] * np.random.uniform(0.85, 1.15, len(properties))).round(2)
if 'payback_period_years' not in properties.columns:
    properties['payback_period_years'] = (100 / properties['rental_yield_pct'].clip(1, 20)).round(1)
properties.to_csv(f'{BASE}/re_properties.csv', index=False)
print(f"  re_properties.csv    -> {len(properties):,} rows, {len(properties.columns)} cols")

# ── re_listings.csv ──────────────────────────────────────────
if 'reserved_units' not in listings.columns:
    ru = (listings['available_units'] * np.random.uniform(0.02, 0.12, len(listings))).round(0).astype(int)
    listings['reserved_units'] = np.minimum(ru, listings['available_units'])
if 'inventory_age_bucket' not in listings.columns:
    def age_b(d):
        if d <= 30:  return '0-30d'
        if d <= 90:  return '30-90d'
        if d <= 180: return '90-180d'
        return '180d+'
    listings['inventory_age_bucket'] = listings['days_on_market'].apply(age_b)
listings.to_csv(f'{BASE}/re_listings.csv', index=False)
print(f"  re_listings.csv      -> {len(listings):,} rows, {len(listings.columns)} cols")

print("  [1/10] ✓ done")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — EXTEND re_transactions.csv -> 2019-2020
# ─────────────────────────────────────────────────────────────────────────────

print("\n[2/10] Extending re_transactions.csv to Jan 2019 …")

PT_W   = [0.50,0.18,0.12,0.03,0.04,0.05,0.08]   # property_type weights
CAT_W  = [0.15,0.30,0.30,0.18,0.07]
BED_W  = [0.12,0.28,0.28,0.18,0.09,0.05]
PAY_W  = [0.30,0.35,0.20,0.10,0.05]
CH_W   = [0.15,0.20,0.20,0.15,0.12,0.08,0.05,0.05]
EMI_W  = [0.55,0.25,0.10,0.04,0.03,0.02,0.01]

year_cfg = {
    2019: {'count':18_000, 'price_factor':0.96},
    2020: {'count':12_000, 'price_factor':0.91},
}

# Monthly volume weights per year
monthly_normal = np.array([0.07,0.07,0.09,0.07,0.08,0.07,0.05,0.05,0.09,0.12,0.12,0.12])
monthly_covid  = np.array([0.09,0.09,0.06,0.02,0.02,0.04,0.07,0.09,0.11,0.13,0.13,0.15])

new_rows = []
ctr = 200_001

for yr, cfg in year_cfg.items():
    mon_w = monthly_covid if yr == 2020 else monthly_normal
    mon_w = mon_w / mon_w.sum()
    counts = np.random.multinomial(cfg['count'], mon_w)
    pf = cfg['price_factor']

    for mi, cnt in enumerate(counts):
        mo = mi + 1
        for _ in range(int(cnt)):
            dt   = rand_date(yr, mo)
            emi  = random.choices(EMIRATES, weights=EMI_W)[0]
            loc  = random.choice(LOCALITIES[emi])
            pt   = random.choices(PROPERTY_TYPES, weights=PT_W)[0]
            cat  = random.choices(PROPERTY_CATEGORIES, weights=CAT_W)[0]
            bed  = random.choices(BEDROOMS, weights=BED_W)[0]
            plan = random.choices(PAYMENT_PLANS, weights=PAY_W)[0]
            ch   = random.choices(MARKETING_CHANNELS, weights=CH_W)[0]
            comp = random.choices(['Ready','Off-Plan'], weights=[0.48,0.52])[0]

            lo, hi = PRICE_BANDS[cat]
            area   = random.uniform(420, 7500) if pt in ['Villa','Penthouse'] else random.uniform(350, 3200)
            ppf    = random.uniform(lo / area * 0.85, hi / area * 1.15) * pf
            ppf    = max(380, min(ppf, 9000))
            sell   = max(lo, min(round(ppf * area / 1000) * 1000, hi))
            base   = round(sell * random.uniform(1.0, 1.12) / 1000) * 1000
            disc   = max(0.0, round((base - sell) / base * 100, 1))
            dld    = round(sell * 0.04 / 500) * 500
            comm   = round(sell * 0.02 / 500) * 500
            vat    = round(sell * 0.05 / 500) * 500 if pt == 'Commercial' else 0
            svc    = round(sell * 0.012 / 1000) * 1000
            total  = sell + dld + comm + vat
            mort   = round(sell * random.uniform(0.6, 0.8) / 10000) * 10000 if plan == 'Mortgage' else 0
            book   = round(sell * random.uniform(0.05, 0.15) / 1000) * 1000
            poss   = yr + random.randint(0,3) if comp == 'Off-Plan' else yr - random.randint(0,5)
            poss   = max(2015, min(poss, 2028))
            ev, em = market_event(dt)

            new_rows.append({
                'transaction_id':           f'TXN{ctr:07d}',
                'transaction_date':         dt.strftime('%Y-%m-%d'),
                'year':                     yr,
                'month':                    mo,
                'quarter':                  quarter(mo),
                'day_of_week':              dt.strftime('%A'),
                'is_ramadan_period':        bool(ramadan_flag(dt)),
                'market_event':             ev,
                'buyer_id':                 random.choice(buyer_ids),
                'developer_id':             random.choice(dev_ids),
                'property_id':              random.choice(prop_ids),
                'project_name':             random.choice(proj_names),
                'property_type':            pt,
                'property_category':        cat,
                'bedrooms':                 bed,
                'completion_status':        comp,
                'possession_year':          poss,
                'emirate':                  emi,
                'city':                     emi,
                'locality':                 loc,
                'region':                   REGION_MAP[emi],
                'area_sqft':                round(area, 1),
                'base_price_aed':           base,
                'price_per_sqft_aed':       round(ppf, 2),
                'discount_pct':             disc,
                'selling_price_aed':        sell,
                'dld_transfer_fee_aed':     dld,
                'agency_commission_aed':    comm,
                'vat_amount_aed':           vat,
                'service_charge_annual_aed':svc,
                'total_transaction_value_aed': total,
                'payment_plan':             plan,
                'mortgage_amount_aed':      mort,
                'booking_amount_aed':       book,
                'golden_visa_eligible':     sell >= 2_000_000,
                'lead_to_close_days':       random.randint(2, 300 if (yr==2020 and mo in [4,5,6]) else 180),
                'salesperson_id':           random.choice(sp_ids),
                'marketing_channel':        ch,
                'booking_converted':        True,
                'season_multiplier':        em,
                'freehold':                 random.random() > 0.15,
            })
            ctr += 1

new_txn_df = pd.DataFrame(new_rows)
txn_full   = pd.concat([new_txn_df, txn], ignore_index=True).sort_values('transaction_date').reset_index(drop=True)
txn_full.to_csv(f'{BASE}/re_transactions.csv', index=False)
print(f"  re_transactions.csv  -> {len(txn_full):,} rows  (added {len(new_rows):,} rows for 2019-2020)")
print("  [2/10] ✓ done")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — EXTEND re_market_factors.csv -> 2019-2020
# ─────────────────────────────────────────────────────────────────────────────

print("\n[3/10] Extending re_market_factors.csv to Jan 2019 …")

# Historical macro values (calibrated to real UAE data)
macro = {
    # yr: (base_rate, oil, gdp, cpi, consumer_conf)
    2019: (2.45, 64.0,  3.3,  -1.9, 115),
    2020: (0.50, 41.5, -6.1,  -2.1,  88),
}

new_mf_rows = []
for yr in [2019, 2020]:
    br, oil_base, gdp, cpi_base, cc_base = macro[yr]
    for mo in range(1, 13):
        dt = date(yr, mo, 1)
        # Oil monthly variation
        oil = oil_base + np.random.uniform(-8, 8)
        if yr == 2020 and mo in [4, 5]:
            oil = random.uniform(18, 32)   # COVID crash
        oil = max(15, oil)

        # CPI monthly
        cpi = cpi_base + np.random.uniform(-0.5, 0.5)

        # Consumer confidence — COVID dip
        cc = cc_base + np.random.uniform(-5, 5)
        if yr == 2020 and mo in [3,4,5,6]:
            cc = cc_base * 0.72 + np.random.uniform(-3, 3)

        # Mortgage rate ~ base + 2.5%
        mort_rate = br + 2.5 + np.random.uniform(-0.2, 0.2)

        # Price index (base 100 at Jan 2019)
        price_idx = 100 + (yr - 2019) * (-3) + (mo - 1) * (-0.2) + np.random.uniform(-1, 1)
        if yr == 2020 and mo > 3:
            price_idx -= 5

        # Transaction volume
        txn_vol_base = 0.65 if yr == 2019 else 0.48
        if yr == 2020 and mo in [4,5,6]:
            txn_vol_base = 0.20
        txn_vol = txn_vol_base + np.random.uniform(-0.05, 0.05)

        # Rental yield
        ry = 5.8 + np.random.uniform(-0.4, 0.4)
        if yr == 2020:
            ry = 5.4 + np.random.uniform(-0.3, 0.3)

        # DLD count
        dld_cnt = int(random.uniform(1800, 3200) * txn_vol_base)
        if yr == 2020 and mo in [4,5,6]:
            dld_cnt = int(dld_cnt * 0.28)

        # New launches
        new_launches = random.randint(8, 25)
        if yr == 2020 and mo in [4,5,6]:
            new_launches = random.randint(1, 6)

        # Tourism
        tour_idx = 90 + np.random.uniform(-8, 8)
        if yr == 2020 and mo in [3,4,5,6,7,8]:
            tour_idx = random.uniform(12, 40)   # borders closed

        # FDI
        fdi = random.uniform(3.5, 7.5)
        if yr == 2020:
            fdi = random.uniform(1.8, 4.5)

        # Golden Visa (introduced mid-2019)
        gv_apps = 0
        if yr == 2019 and mo >= 6:
            gv_apps = random.randint(200, 800)
        elif yr == 2020:
            gv_apps = random.randint(100, 600) if mo not in [4,5,6] else random.randint(10, 80)

        # Off-plan share
        op_share = 52 + np.random.uniform(-5, 5)
        if yr == 2020 and mo in [4,5,6]:
            op_share = 38 + np.random.uniform(-5, 5)

        # Google trends
        seasonal = 10 * math.sin(2 * math.pi * (mo - 3) / 12)
        covid_dip = -28 if (yr == 2020 and mo in [4,5,6]) else 0
        gt_idx = round(max(10, min(100, 58 + seasonal + covid_dip + np.random.normal(0,3))), 1)

        nri_share = round(18 + (yr - 2019) * 1.5 + np.random.uniform(-2, 2), 1)

        ev, ev_mult = market_event(dt)
        ram = ramadan_flag(dt)

        for emi in EMIRATES:
            # Emirate-level scaling
            emi_scale = {'Dubai':1.0,'Abu Dhabi':0.85,'Sharjah':0.70,'Ras Al Khaimah':0.45,
                         'Ajman':0.35,'Fujairah':0.25,'Umm Al Quwain':0.15}[emi]
            total_inv  = int(random.uniform(12000, 22000) * emi_scale)
            unsold_inv = int(total_inv * random.uniform(0.08, 0.22))

            new_mf_rows.append({
                'date':                             dt.strftime('%Y-%m-%d'),
                'year':                             yr,
                'month':                            mo,
                'quarter':                          quarter(mo),
                'city':                             emi,
                'emirate':                          emi,
                'uae_central_bank_base_rate_pct':   round(br, 2),
                'mortgage_rate_avg_pct':            round(mort_rate, 2),
                'oil_price_usd_bbl':                round(oil, 2),
                'gdp_growth_pct':                   round(gdp + np.random.uniform(-0.3, 0.3), 2),
                'cpi_inflation_pct':                round(cpi, 2),
                'consumer_confidence_index':        round(cc, 1),
                'real_estate_price_index':          round(price_idx * emi_scale, 2),
                'transaction_volume_index':         round(txn_vol, 3),
                'rental_yield_avg_pct':             round(ry + np.random.uniform(-0.3, 0.3), 2),
                'new_project_launches':             max(0, int(new_launches * emi_scale)),
                'total_inventory_units':            total_inv,
                'unsold_inventory_units':           unsold_inv,
                'steel_price_per_ton_aed':          round(random.uniform(1600, 2200), 0),
                'construction_cost_index':          round(90 + (yr-2019)*2 + np.random.uniform(-2,2), 2),
                'usd_aed_rate':                     3.6725,
                'tourism_arrivals_index':           round(tour_idx, 1),
                'foreign_investment_inflow_bn_aed': round(fdi * emi_scale, 2),
                'institutional_investment_bn_aed':  round(fdi * 0.3 * emi_scale, 2),
                'reit_activity_index':              round(50 + np.random.uniform(-10, 10), 1),
                'golden_visa_applications':         gv_apps,
                'off_plan_sales_share_pct':         round(op_share, 1),
                'dld_transactions_count':           int(dld_cnt * emi_scale),
                'expo_effect':                      0,
                'ramadan_month':                    ram,
                'market_event':                     ev,
                'event_demand_multiplier':          round(ev_mult, 2),
                'vat_rate_pct':                     5.0,
                'property_registration_fee_pct':    4.0,
                'google_trends_index':              gt_idx,
                'nri_investment_share_pct':         nri_share,
            })

new_mf_df = pd.DataFrame(new_mf_rows)
mf_full   = pd.concat([new_mf_df, mf], ignore_index=True).sort_values(['date','emirate']).reset_index(drop=True)
mf_full.to_csv(f'{BASE}/re_market_factors.csv', index=False)
print(f"  re_market_factors    -> {len(mf_full):,} rows  (added {len(new_mf_rows):,} rows for 2019-2020)")
print("  [3/10] ✓ done")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — re_leads_pipeline.csv  (80,000 rows, 2019-May 2026)
# ─────────────────────────────────────────────────────────────────────────────

print("\n[4/10] Generating re_leads_pipeline.csv (80,000 rows) …")

LEAD_SOURCES   = ['Google Ads','Facebook','Property Finder','Bayut','Referral','Broker','Walk-in','Property Expo','WhatsApp','Website']
LEAD_SRC_W     = [0.18,0.14,0.18,0.14,0.10,0.08,0.05,0.04,0.05,0.04]
LEAD_STAGES    = ['New','Contacted','Qualified','Site Visit Scheduled','Site Visit Done',
                  'Proposal Sent','Negotiation','Booked','Lost']
AI_RECS        = ['Call within 24 hours','Schedule Site Visit','Send Digital Brochure',
                  'Offer Special Discount','Follow up via WhatsApp','Assign Senior Agent']
LOST_REASONS   = ['Budget','Competitor','No Response','Project Not Suitable','Timing','Relocated']
CAMPAIGNS      = ['Summer Promo','Year-End Push','Golden Visa Campaign','NRI Special',
                  'Luxury Launch','Off-Plan Offer','Post-Ramadan Drive','Digital Spring']

# Year volumes ramp up over time
YEAR_LEAD_W = {2019:0.07,2020:0.05,2021:0.09,2022:0.12,2023:0.16,2024:0.20,2025:0.19,2026:0.12}
YEAR_LEAD_W_ARR = np.array(list(YEAR_LEAD_W.values()))
YEAR_LEAD_W_ARR /= YEAR_LEAD_W_ARR.sum()
YEARS_LIST = list(YEAR_LEAD_W.keys())

STAGE_CONV = {
    'New':0.00,'Contacted':0.70,'Qualified':0.55,'Site Visit Scheduled':0.75,
    'Site Visit Done':0.65,'Proposal Sent':0.50,'Negotiation':0.60,'Booked':1.0,'Lost':0.0,
}

leads = []
for i in range(80_000):
    yr   = random.choices(YEARS_LIST, weights=YEAR_LEAD_W_ARR)[0]
    # cap 2026 at May
    mo   = random.randint(1, 5) if yr == 2026 else random.randint(1, 12)
    # COVID 2020: fewer leads Apr-Jun
    if yr == 2020 and mo in [4,5,6] and random.random() < 0.6:
        mo = random.choice([1,2,3,7,8,9,10,11,12])
    dt_lead = rand_date(yr, mo)

    src     = random.choices(LEAD_SOURCES, weights=LEAD_SRC_W)[0]
    emi     = random.choices(EMIRATES, weights=EMI_W)[0]
    loc     = random.choice(LOCALITIES[emi])
    pt      = random.choices(PROPERTY_TYPES, weights=PT_W)[0]
    cat     = random.choices(PROPERTY_CATEGORIES, weights=CAT_W)[0]
    bed     = random.choices(BEDROOMS, weights=BED_W)[0]

    lo, hi  = PRICE_BANDS[cat]
    budget  = round(random.uniform(lo * 0.9, hi * 1.1) / 5000) * 5000

    # CPL varies by source
    cpl_map = {'Google Ads':350,'Facebook':220,'Property Finder':420,'Bayut':380,
               'Referral':50,'Broker':30,'Walk-in':0,'Property Expo':180,'WhatsApp':60,'Website':90}
    cpl = cpl_map.get(src, 150) + random.randint(-50, 80)
    cpl = max(0, cpl)

    # Determine final stage
    r = random.random()
    if r < 0.22:    stage = 'Booked'
    elif r < 0.30:  stage = 'Negotiation'
    elif r < 0.40:  stage = 'Proposal Sent'
    elif r < 0.52:  stage = 'Site Visit Done'
    elif r < 0.60:  stage = 'Site Visit Scheduled'
    elif r < 0.70:  stage = 'Qualified'
    elif r < 0.82:  stage = 'Contacted'
    elif r < 0.90:  stage = 'Lost'
    else:           stage = 'New'

    converted = (stage == 'Booked')

    # Dates through funnel
    contact_lag       = random.randint(0, 5) if src != 'Walk-in' else 0
    qualified_lag     = contact_lag + random.randint(1, 14)
    sv_sched_lag      = qualified_lag + random.randint(1, 10)
    sv_done_lag       = sv_sched_lag + random.randint(1, 5)
    proposal_lag      = sv_done_lag + random.randint(1, 7)
    neg_lag           = proposal_lag + random.randint(1, 14)
    booking_lag       = neg_lag + random.randint(1, 10)

    def fdate(lag): return (dt_lead + timedelta(days=lag)).strftime('%Y-%m-%d')

    stages_reached = LEAD_STAGES.index(stage)

    contacted_date        = fdate(contact_lag)       if stages_reached >= 1 else None
    qualified_date        = fdate(qualified_lag)     if stages_reached >= 2 else None
    sv_sched_date         = fdate(sv_sched_lag)      if stages_reached >= 3 else None
    sv_done_date          = fdate(sv_done_lag)       if stages_reached >= 4 else None
    proposal_date         = fdate(proposal_lag)      if stages_reached >= 5 else None
    booking_date          = fdate(booking_lag)       if converted else None
    lost_date             = fdate(sv_done_lag + random.randint(1,30)) if stage == 'Lost' else None
    lost_reason           = random.choice(LOST_REASONS) if stage == 'Lost' else None

    score       = round(random.uniform(60, 100) if converted else
                  random.uniform(70, 95) if stage in ['Negotiation','Proposal Sent'] else
                  random.uniform(40, 80) if stage in ['Site Visit Done','Site Visit Scheduled','Qualified'] else
                  random.uniform(10, 55), 0)
    temperature = 'Hot' if score >= 80 else ('Warm' if score >= 50 else 'Cold')

    total_days  = booking_lag if converted else (sv_done_lag if stages_reached >= 4 else qualified_lag if stages_reached >= 2 else contact_lag + 3)
    resp_time   = round(random.uniform(0.5, 72) if src != 'Walk-in' else random.uniform(0, 1), 1)
    if yr == 2020 and mo in [4,5,6]:
        resp_time = round(random.uniform(12, 120), 1)   # slower during COVID

    nri = (random.random() < 0.22)
    corp= (random.random() < 0.06)

    leads.append({
        'lead_id':                  f'LEAD{i+1:06d}',
        'buyer_id':                 random.choice(buyer_ids),
        'lead_date':                dt_lead.strftime('%Y-%m-%d'),
        'lead_source':              src,
        'lead_campaign':            random.choice(CAMPAIGNS),
        'lead_medium':              random.choice(['CPC','Organic','Social','Email','Direct','Offline']),
        'utm_source':               src.lower().replace(' ','_'),
        'utm_campaign':             random.choice(CAMPAIGNS).lower().replace(' ','_'),
        'cost_per_lead_aed':        cpl,
        'lead_stage':               stage,
        'lead_score':               int(score),
        'lead_temperature':         temperature,
        'property_interest':        pt,
        'project_interest':         random.choice(proj_names),
        'budget_stated_aed':        budget,
        'contacted_date':           contacted_date,
        'qualified_date':           qualified_date,
        'site_visit_scheduled_date':sv_sched_date,
        'site_visit_done_date':     sv_done_date,
        'proposal_sent_date':       proposal_date,
        'booking_date':             booking_date,
        'lost_date':                lost_date,
        'lost_reason':              lost_reason,
        'salesperson_id':           random.choice(sp_ids),
        'follow_up_count':          random.randint(0, 12),
        'response_time_hours':      resp_time,
        'time_in_stage_days':       random.randint(1, 45),
        'total_funnel_days':        total_days,
        'converted':                converted,
        'conversion_probability':   round(score / 100 * random.uniform(0.8, 1.2), 3),
        'emirate_interest':         emi,
        'locality_interest':        loc,
        'bedroom_preference':       bed,
        'nri_flag':                 nri,
        'corporate_buyer_flag':     corp,
        'whatsapp_engaged':         (src == 'WhatsApp') or (random.random() < 0.45),
        'email_opened':             random.random() < 0.38,
        'ai_recommendation':        random.choice(AI_RECS),
    })

leads_df = pd.DataFrame(leads).sort_values('lead_date').reset_index(drop=True)
leads_df.to_csv(f'{BASE}/re_leads_pipeline.csv', index=False)
print(f"  re_leads_pipeline    -> {len(leads_df):,} rows, {len(leads_df.columns)} cols")
print("  [4/10] ✓ done")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — re_contractors.csv  (200 rows)
# ─────────────────────────────────────────────────────────────────────────────

print("\n[5/10] Generating re_contractors.csv (200 rows) …")

CONTRACTOR_TYPES = ['Main Contractor','MEP Contractor','Civil','Façade','Interior Fit-Out','Landscaping','Structural']
SPECIALIZATIONS  = ['High-Rise Residential','Low-Rise Residential','Commercial Towers',
                    'Mixed-Use','Luxury Villas','MEP Systems','Façade & Cladding',
                    'Interior Finishing','Landscaping & Public Realm','Structural Works']
ORIGINS          = ['UAE','India','Pakistan','China','Turkey','UK','Germany','South Korea','Egypt','Philippines']
ORIG_W           = [0.12,0.22,0.18,0.12,0.08,0.05,0.05,0.04,0.08,0.06]

MC_NAMES = [
    'Al Habtoor Engineering','Arabtec Construction','Shapoorji Pallonji ME','Khansaheb Civil Engineering',
    'ACC (Arabian Construction Co)','ASGC Construction','Consolidated Contractors (CCC)',
    'Ssangyong Engineering','Hyundai Engineering UAE','China State Construction UAE',
    'Multiplex Constructions ME','Brookfield Multiplex','Alec Contracting','Drake & Scull',
    'Ginco General Contracting','Energoprojekt','Dutco Balfour Beatty','Carillion Alawi',
    'Besix ME','Six Construct','Depa United','Interiors & Contracting','ECC Contracting',
    'National Projects & Construction','Al Fara\'a Group','Deyaar Construction',
    'Gulf Contracting','National Marine Dredging','Cansult Maunsell','Laing O\'Rourke ME',
]

contractors = []
for i in range(200):
    name = MC_NAMES[i % len(MC_NAMES)] + (f' LLC' if i >= len(MC_NAMES) else '')
    ct   = random.choices(CONTRACTOR_TYPES)[0]
    spec = random.choice(SPECIALIZATIONS)
    org  = random.choices(ORIGINS, weights=ORIG_W)[0]
    grade= random.choices(['A','B','C'], weights=[0.25,0.40,0.35])[0]
    est  = random.randint(1975, 2015)
    comp_total = random.randint(10, 180)
    active= random.randint(1, 12)
    score_d = round(random.uniform(55, 97), 1)
    score_q = round(random.uniform(60, 98), 1)
    score_c = round(random.uniform(50, 96), 1)
    overall = round((score_d + score_q + score_c) / 3, 1)
    incidents = random.randint(0, 8)
    rating = round(random.uniform(3.0, 5.0), 1)
    pref   = overall >= 80
    black  = incidents > 6

    contractors.append({
        'contractor_id':                f'CONT{i+1:03d}',
        'contractor_name':              name,
        'contractor_type':              ct,
        'specialization':               spec,
        'country_of_origin':            org,
        'uae_license_no':               f'DM-{random.randint(10000,99999)}',
        'grade':                        grade,
        'established_year':             est,
        'total_projects_completed':     comp_total,
        'active_projects_count':        active,
        'avg_delivery_score':           score_d,
        'avg_quality_score':            score_q,
        'avg_cost_adherence_score':     score_c,
        'overall_performance_score':    overall,
        'safety_record_incidents':      incidents,
        'rating':                       rating,
        'preferred_vendor':             pref,
        'blacklisted':                  black,
        'daily_rate_aed':               round(random.uniform(180, 480), 0),
        'projects_with_this_developer': random.randint(0, 15),
    })

contractors_df = pd.DataFrame(contractors)
contractors_df.to_csv(f'{BASE}/re_contractors.csv', index=False)
print(f"  re_contractors.csv   -> {len(contractors_df)} rows, {len(contractors_df.columns)} cols")
print("  [5/10] ✓ done")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — re_construction_tracker.csv  (5,000 rows)
# ─────────────────────────────────────────────────────────────────────────────

print("\n[6/10] Generating re_construction_tracker.csv (5,000 rows) …")

MILESTONES      = ['Foundation','Structure','MEP','Façade','Fit-Out','Handover']
DELAY_REASONS   = ['Labour Shortage','Material Delay','Design Change','Weather','Regulatory','Financing','COVID-19']
contractor_ids  = contractors_df['contractor_id'].tolist()
contractor_names= contractors_df['contractor_name'].tolist()

# Pick 55 off-plan projects
off_plan_projects = [(n, random.choice(dev_ids)) for n in random.sample(proj_names, min(55, len(proj_names)))]

tracker_rows = []
rec_ctr = 1
for proj_name, dev_id in off_plan_projects:
    # Project starts between 2019 and 2023
    proj_start_yr = random.randint(2019, 2023)
    proj_start_mo = random.randint(1, 12)
    proj_start    = date(proj_start_yr, proj_start_mo, 1)

    total_budget  = random.randint(80_000_000, 2_000_000_000)
    handover_orig = proj_start + timedelta(days=random.randint(730, 1460))   # 2-4 yr build time
    delay_total   = random.randint(-30, 300)
    handover_rev  = handover_orig + timedelta(days=max(0, delay_total))

    health_base   = round(random.uniform(55, 92), 1)
    c_id          = random.choice(contractor_ids)
    c_name        = contractors_df.loc[contractors_df['contractor_id']==c_id,'contractor_name'].values[0]

    for mi, ms in enumerate(MILESTONES):
        # Each milestone ~4 months
        ms_start_planned = proj_start + timedelta(days=mi * 120)
        ms_end_planned   = ms_start_planned + timedelta(days=110)

        delay_ms = random.randint(-10, delay_total // len(MILESTONES) + 15)
        actual_offset   = random.randint(0, max(0, delay_ms)) if delay_ms > 0 else 0
        ms_start_actual = ms_start_planned + timedelta(days=actual_offset)
        ms_end_actual   = ms_end_planned   + timedelta(days=max(0, delay_ms))

        # Generate monthly progress snapshots for this milestone
        cur = ms_start_planned
        end = min(ms_end_planned + timedelta(days=60), date(2026, 5, 31))
        while cur <= end:
            planned_pct = min(100, max(0, round((cur - ms_start_planned).days / 110 * 100, 1)))
            actual_pct  = min(100, max(0, round(planned_pct - random.uniform(-8, 15) + (delay_ms * -0.3), 1)))
            pvar        = round(actual_pct - planned_pct, 1)
            spent       = round(total_budget * (mi / len(MILESTONES)) + total_budget / len(MILESTONES) * (actual_pct / 100), 0)
            planned_cost= round(total_budget * (mi / len(MILESTONES)) + total_budget / len(MILESTONES) * (planned_pct / 100), 0)
            cost_var    = spent - planned_cost
            cost_ovr    = round(cost_var / max(planned_cost, 1) * 100, 1)
            labour_p    = random.randint(150, 800)
            labour_d    = int(labour_p * random.uniform(0.7, 1.1))
            res_util    = round(labour_d / labour_p * 100, 1)
            q_score     = round(random.uniform(70, 98), 1)
            safety_inc  = random.choices([0,0,0,0,1,2], weights=[0.60,0.15,0.10,0.08,0.05,0.02])[0]
            health      = round(health_base + pvar * 0.3 - safety_inc * 5 + np.random.normal(0,2), 1)
            health      = max(20, min(100, health))
            delay_flag  = abs(pvar) > 10 or delay_ms > 30
            esc_flag    = cost_ovr > 15 or safety_inc > 0
            next_mi_idx = mi + 1
            next_ms     = MILESTONES[next_mi_idx] if next_mi_idx < len(MILESTONES) else 'Completed'
            next_due    = (ms_end_planned + timedelta(days=5)).strftime('%Y-%m-%d')

            tracker_rows.append({
                'record_id':                f'CONS{rec_ctr:06d}',
                'project_id':               f'PROJ{off_plan_projects.index((proj_name,dev_id))+1:03d}',
                'project_name':             proj_name,
                'developer_id':             dev_id,
                'report_date':              cur.strftime('%Y-%m-%d'),
                'milestone_name':           ms,
                'milestone_planned_start':  ms_start_planned.strftime('%Y-%m-%d'),
                'milestone_planned_end':    ms_end_planned.strftime('%Y-%m-%d'),
                'milestone_actual_start':   ms_start_actual.strftime('%Y-%m-%d'),
                'milestone_actual_end':     ms_end_actual.strftime('%Y-%m-%d') if actual_pct >= 100 else None,
                'planned_progress_pct':     planned_pct,
                'actual_progress_pct':      actual_pct,
                'progress_variance_pct':    pvar,
                'delay_days':               max(0, delay_ms),
                'delay_reason':             random.choice(DELAY_REASONS) if delay_ms > 0 else None,
                'planned_budget_aed':       planned_cost,
                'actual_cost_aed':          spent,
                'cost_variance_aed':        cost_var,
                'cost_overrun_pct':         cost_ovr,
                'total_project_budget_aed': total_budget,
                'total_spent_to_date_aed':  spent,
                'budget_utilization_pct':   round(spent / total_budget * 100, 1),
                'contractor_id':            c_id,
                'contractor_name':          c_name,
                'labour_deployed':          labour_d,
                'labour_planned':           labour_p,
                'resource_utilization_pct': res_util,
                'rera_inspection_passed':   planned_pct >= 100 and actual_pct >= 90,
                'quality_score':            q_score,
                'safety_incidents':         safety_inc,
                'project_health_score':     health,
                'delay_risk_flag':          delay_flag,
                'escalation_flag':          esc_flag,
                'next_milestone':           next_ms,
                'next_milestone_due_date':  next_due,
                'handover_date_original':   handover_orig.strftime('%Y-%m-%d'),
                'handover_date_revised':    handover_rev.strftime('%Y-%m-%d'),
            })
            rec_ctr += 1
            cur = date(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)
            if len(tracker_rows) >= 5000:
                break
        if len(tracker_rows) >= 5000:
            break

tracker_df = pd.DataFrame(tracker_rows[:5000])
tracker_df.to_csv(f'{BASE}/re_construction_tracker.csv', index=False)
print(f"  re_construction_tracker -> {len(tracker_df):,} rows, {len(tracker_df.columns)} cols")
print("  [6/10] ✓ done")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — re_financials.csv  (2,400 rows)
# ─────────────────────────────────────────────────────────────────────────────

print("\n[7/10] Generating re_financials.csv (2,400 rows) …")

# Pick 20 main projects; generate monthly financials 2019-May 2026
fin_projects = random.sample(proj_names, min(20, len(proj_names)))
fin_rows = []
fin_ctr  = 1

# Year-level revenue scaling (market conditions)
YR_REV_SCALE = {2019:0.70,2020:0.48,2021:0.90,2022:1.20,2023:1.55,2024:1.80,2025:1.75,2026:0.90}

for proj in fin_projects:
    dev_id = random.choice(dev_ids)
    # Base monthly revenue for this project
    base_monthly_rev = random.uniform(15_000_000, 180_000_000)
    pipeline_base    = base_monthly_rev * random.uniform(3, 8)

    for yr, mo in date_range_months(2019, 1, 2026, 5):
        yr_scale  = YR_REV_SCALE.get(yr, 1.0)
        seasonality = 1 + 0.15 * math.sin(2 * math.pi * (mo - 3) / 12)
        if yr == 2020 and mo in [4,5,6]:
            yr_scale *= 0.28

        rev_booked = round(base_monthly_rev * yr_scale * seasonality * random.uniform(0.7, 1.3) / 100000) * 100000
        rev_reg    = round(rev_booked * random.uniform(0.60, 0.85) / 100000) * 100000
        rev_recog  = round(rev_booked * random.uniform(0.70, 0.90) / 100000) * 100000

        coll_rate  = random.uniform(0.72, 0.94)
        collections= round(rev_booked * coll_rate / 100000) * 100000
        outstanding= round(rev_booked - collections) / 100000 * 100000
        coll_eff   = round(coll_rate * 100, 1)

        # Overdue buckets
        overdue_total = max(0, outstanding * random.uniform(0.25, 0.65))
        od_30_60  = round(overdue_total * random.uniform(0.30, 0.50) / 10000) * 10000
        od_60_90  = round(overdue_total * random.uniform(0.20, 0.35) / 10000) * 10000
        od_90plus = round(max(0, overdue_total - od_30_60 - od_60_90) / 10000) * 10000

        gp_margin = random.uniform(0.28, 0.48)
        gp        = round(rev_recog * gp_margin / 100000) * 100000
        opex      = round(rev_recog * random.uniform(0.10, 0.18) / 100000) * 100000
        ebitda    = round((gp - opex) / 100000) * 100000
        net_pr    = round(ebitda * random.uniform(0.55, 0.75) / 100000) * 100000
        net_margin= round(net_pr / max(rev_recog, 1) * 100, 1)

        cash_in   = round(collections * random.uniform(0.95, 1.05) / 100000) * 100000
        cash_out  = round((opex + rev_recog * random.uniform(0.15, 0.30)) / 100000) * 100000
        net_cf    = cash_in - cash_out

        target    = round(base_monthly_rev * yr_scale * 1.05 / 100000) * 100000
        achieve   = round(rev_booked / max(target, 1) * 100, 1)

        fin_rows.append({
            'record_id':                 f'FIN{fin_ctr:06d}',
            'period_date':               date(yr, mo, 1).strftime('%Y-%m-%d'),
            'year':                      yr,
            'month':                     mo,
            'quarter':                   quarter(mo),
            'entity_type':               'Project',
            'project_id':                f'PROJ{fin_projects.index(proj)+1:03d}',
            'project_name':              proj,
            'developer_id':              dev_id,
            'revenue_booked_aed':        rev_booked,
            'revenue_registered_aed':    rev_reg,
            'revenue_recognized_aed':    rev_recog,
            'collections_received_aed':  collections,
            'collections_outstanding_aed':outstanding,
            'overdue_collections_aed':   round(overdue_total / 10000) * 10000,
            'overdue_30_60d_aed':        od_30_60,
            'overdue_60_90d_aed':        od_60_90,
            'overdue_90d_plus_aed':      od_90plus,
            'collection_efficiency_pct': coll_eff,
            'gross_profit_aed':          gp,
            'gross_margin_pct':          round(gp_margin * 100, 1),
            'operating_expenses_aed':    opex,
            'ebitda_aed':                ebitda,
            'net_profit_aed':            net_pr,
            'net_margin_pct':            net_margin,
            'cash_inflow_aed':           cash_in,
            'cash_outflow_aed':          cash_out,
            'net_cash_flow_aed':         net_cf,
            'cumulative_cash_position_aed': round(net_cf * random.uniform(5, 12) / 100000) * 100000,
            'escrow_balance_aed':        round(collections * 0.30 / 100000) * 100000,
            'construction_draw_aed':     round(collections * 0.22 / 100000) * 100000,
            'sales_target_aed':          target,
            'sales_achievement_pct':     achieve,
            'pipeline_value_aed':        round(pipeline_base * yr_scale * random.uniform(0.8, 1.2) / 100000) * 100000,
            'forecast_next_3m_aed':      round(rev_booked * 3 * random.uniform(0.95, 1.15) / 100000) * 100000,
            'forecast_next_12m_aed':     round(rev_booked * 12 * random.uniform(0.90, 1.25) / 100000) * 100000,
            'bad_debt_provision_aed':    round(od_90plus * 0.50 / 10000) * 10000,
            'refunds_issued_aed':        round(rev_booked * random.uniform(0.005, 0.025) / 10000) * 10000,
            'dld_fees_collected_aed':    round(rev_booked * 0.04 / 10000) * 10000,
            'vat_collected_aed':         round(rev_booked * 0.01 / 10000) * 10000,
        })
        fin_ctr += 1

fin_df = pd.DataFrame(fin_rows)
fin_df.to_csv(f'{BASE}/re_financials.csv', index=False)
print(f"  re_financials.csv    -> {len(fin_df):,} rows, {len(fin_df.columns)} cols")
print("  [7/10] ✓ done")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — re_competitor_market.csv  (3,000 rows)
# ─────────────────────────────────────────────────────────────────────────────

print("\n[8/10] Generating re_competitor_market.csv (3,000 rows) …")

COMPETITOR_BUILDERS = [
    ('Emaar Properties','Tier 1'),('DAMAC Properties','Tier 1'),('Aldar Properties','Tier 1'),
    ('Nakheel','Tier 1'),('Meraas','Tier 1'),('Sobha Realty','Tier 1'),('Meydan','Tier 1'),
    ('Azizi Developments','Tier 2'),('Danube Properties','Tier 2'),('Binghatti','Tier 2'),
    ('Ellington Properties','Tier 2'),('Select Group','Tier 2'),('Imtiaz Developments','Tier 2'),
    ('Tiger Properties','Tier 2'),('RAK Properties','Tier 2'),('Wasl Properties','Tier 2'),
    ('Reportage Properties','Tier 3'),('Deyaar','Tier 3'),('Gulf Properties','Tier 3'),
    ('Emkaan','Tier 3'),('Object 1','Tier 3'),('Majid Al Futtaim Properties','Tier 2'),
]

PROJ_SUFFIXES = ['Residences','Heights','Tower','Gardens','Park','Square','View','Bay',
                 'Marina','Hills','Villas','Suites','Terraces','Pavilion','Edge','Grand']
PROJ_PREFIXES = ['Al','The','One','Sky','Blue','Green','Palm','Creek','Dubai','Urban',
                 'Royal','Elite','Prime','Pearl','Golden','Sapphire','Crystal','Azure']

STATUSES   = ['Announced','Launched','Active Selling','Sold Out','Cancelled']
STATUS_W   = [0.08,0.25,0.35,0.25,0.07]
SRC_TYPES  = ['DLD Data','Bayut','PropertyFinder','News Report','Cityscape','Direct Observation']
PAY_TYPES  = ['Post-Handover','Construction-Linked','Cash','Mortgage']

comp_rows = []
for i in range(3000):
    builder, tier = random.choice(COMPETITOR_BUILDERS)
    pname = f"{random.choice(PROJ_PREFIXES)} {builder.split()[0]} {random.choice(PROJ_SUFFIXES)}"
    ptype = random.choices(['Residential','Commercial','Mixed-Use'], weights=[0.65,0.15,0.20])[0]
    seg   = random.choices(PROPERTY_CATEGORIES, weights=CAT_W)[0]
    stat  = random.choices(STATUSES, weights=STATUS_W)[0]

    # Launch date
    launch_yr  = random.randint(2019, 2025)
    launch_mo  = random.randint(1, 12)
    launch_date= rand_date(launch_yr, launch_mo)

    completion_date = launch_date + timedelta(days=random.randint(730, 1460))
    if completion_date > date(2030, 12, 31):
        completion_date = date(2030, 12, 31)

    emi    = random.choices(EMIRATES, weights=EMI_W)[0]
    loc    = random.choice(LOCALITIES[emi])
    units  = random.randint(50, 1200)
    launched_u = int(units * random.uniform(0.4, 1.0))
    sold_u     = int(launched_u * random.uniform(0.1, 0.95)) if stat not in ['Announced'] else 0

    lo, hi = PRICE_BANDS[seg]
    ppsf_min = lo / 1200
    ppsf_max = hi / 400
    ppsf_min = max(380, ppsf_min)
    ppsf_max = min(12000, ppsf_max)
    start_price = round(lo * random.uniform(0.9, 1.1) / 50000) * 50000

    pay_type  = random.choice(PAY_TYPES)
    ph_years  = random.randint(2,5) if pay_type == 'Post-Handover' else 0
    dist_km   = round(random.uniform(0.5, 15), 1)
    src       = random.choices(SRC_TYPES, weights=[0.30,0.20,0.18,0.15,0.10,0.07])[0]
    conf      = 'High' if src in ['DLD Data','Cityscape'] else ('Medium' if src in ['Bayut','PropertyFinder'] else 'Low')

    lat_base = {'Dubai':25.2048,'Abu Dhabi':24.4539,'Sharjah':25.3463,
                'Ras Al Khaimah':25.7953,'Ajman':25.4052,'Fujairah':25.1288,'Umm Al Quwain':25.5644}
    lon_base = {'Dubai':55.2708,'Abu Dhabi':54.3773,'Sharjah':55.4209,
                'Ras Al Khaimah':55.9795,'Ajman':55.5136,'Fujairah':56.3264,'Umm Al Quwain':55.5551}

    comp_rows.append({
        'record_id':                f'MKT{i+1:06d}',
        'record_date':              launch_date.strftime('%Y-%m-%d'),
        'builder_name':             builder,
        'builder_tier':             tier,
        'project_name':             pname,
        'project_type':             ptype,
        'property_segment':         seg,
        'property_types_offered':   random.choice(['Apartment','Apartment,Studio','Villa,Townhouse','Apartment,Penthouse','Mixed']),
        'launch_status':            stat,
        'launch_date':              launch_date.strftime('%Y-%m-%d'),
        'expected_completion_date': completion_date.strftime('%Y-%m-%d'),
        'emirate':                  emi,
        'city':                     emi,
        'locality':                 loc,
        'latitude':                 round(lat_base.get(emi,25.2) + random.uniform(-0.08,0.08), 4),
        'longitude':                round(lon_base.get(emi,55.2) + random.uniform(-0.08,0.08), 4),
        'total_units':              units,
        'units_launched':           launched_u,
        'units_sold_reported':      sold_u,
        'price_per_sqft_min_aed':   round(ppsf_min, 0),
        'price_per_sqft_max_aed':   round(ppsf_max, 0),
        'starting_price_aed':       start_price,
        'payment_plan_type':        pay_type,
        'post_handover_years':      ph_years,
        'distance_from_our_project_km': dist_km,
        'rera_registration_no':     f'RERA-{random.randint(100000,999999)}',
        'amenities_offered':        random.choice(['Pool,Gym','Pool,Gym,Beach','Pool,Gym,School,Retail',
                                                   'Gym,Concierge','Pool,Gym,Concierge,Beach Access']),
        'source':                   src,
        'data_confidence':          conf,
        'notes':                    None,
    })

comp_df = pd.DataFrame(comp_rows).sort_values('record_date').reset_index(drop=True)
comp_df.to_csv(f'{BASE}/re_competitor_market.csv', index=False)
print(f"  re_competitor_market -> {len(comp_df):,} rows, {len(comp_df.columns)} cols")
print("  [8/10] ✓ done")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 9 — re_rental_market.csv  (5,000 rows)
# ─────────────────────────────────────────────────────────────────────────────

print("\n[9/10] Generating re_rental_market.csv (5,000 rows) …")

# All localities flat list
ALL_LOCALITIES = [(emi, loc) for emi, locs in LOCALITIES.items() for loc in locs]
RENTAL_PROP_TYPES = ['Apartment','Villa']

# Base annual rent (AED) by locality tier
RENT_BASE = {
    'Downtown Dubai':120000,'Dubai Marina':100000,'Palm Jumeirah':200000,
    'Dubai Hills Estate':130000,'Business Bay':90000,'JVC':65000,'MBR City':140000,
    'Al Furjan':72000,'JBR':110000,'Creek Harbour':100000,'DAMAC Hills':85000,
    'Dubai South':60000,'Meydan':95000,'Sports City':58000,
    'Al Reem Island':75000,'Saadiyat Island':160000,'Yas Island':90000,
    'Al Raha Beach':100000,'Khalifa City':70000,'Corniche':110000,'Al Reef':65000,'Masdar City':58000,
    'Al Majaz':48000,'Al Nahda':42000,'Muwaileh':38000,'Al Khan':45000,'Al Taawun':40000,
    'Al Hamra Village':60000,'Mina Al Arab':55000,'Al Marjan Island':70000,'Hayat Island':65000,
    'Al Nuaimiyah':35000,'Al Rashidiya':32000,'Corniche Ajman':38000,
    'Fujairah City':30000,'Dibba Al Fujairah':28000,
    'UAQ Free Trade Zone':25000,'Umm Al Quwain City':22000,
}

# Year-over-year rent change (cumulative from 2019 base)
RENT_YR_FACTOR = {2019:1.00,2020:0.92,2021:0.95,2022:1.08,2023:1.22,2024:1.38,2025:1.45,2026:1.48}

rental_rows = []
rent_ctr = 1

# Sample localities to keep to ~5000 rows
sampled_pairs = [(emi,loc,pt) for emi,loc in ALL_LOCALITIES for pt in RENTAL_PROP_TYPES]
# 89 months × ~56 pairs would be 4984 rows - perfect
target_pairs  = sampled_pairs[:56]

for yr, mo in date_range_months(2019, 1, 2026, 5):
    for emi, loc, pt in target_pairs:
        base_rent = RENT_BASE.get(loc, 55000)
        if pt == 'Villa':
            base_rent *= random.uniform(1.8, 3.5)

        yr_factor    = RENT_YR_FACTOR.get(yr, 1.0)
        seasonal_adj = 1 + 0.08 * math.sin(2 * math.pi * (mo - 1) / 12)
        if yr == 2020 and mo in [4,5,6]:
            yr_factor *= 0.85

        avg_rent  = round(base_rent * yr_factor * seasonal_adj * random.uniform(0.92, 1.08) / 1000) * 1000
        med_rent  = round(avg_rent * random.uniform(0.92, 1.05) / 1000) * 1000
        mo_rent   = round(avg_rent / 12 / 100) * 100

        # avg property price for yield calc
        prop_price_base = avg_rent * random.uniform(16, 26)
        gross_yield = round(avg_rent / prop_price_base * 100, 2)
        net_yield   = round(gross_yield - random.uniform(0.5, 1.2), 2)

        occupancy   = round(random.uniform(78, 97) if yr >= 2022 else random.uniform(70, 90), 1)
        if yr == 2020 and mo in [4,5,6]:
            occupancy = round(random.uniform(45, 65), 1)
        vacancy     = round(100 - occupancy, 1)

        ejari_cnt   = int(random.uniform(80, 600) * ({'Dubai':1.0,'Abu Dhabi':0.6,'Sharjah':0.4,
            'Ras Al Khaimah':0.2,'Ajman':0.15,'Fujairah':0.1,'Umm Al Quwain':0.05}.get(emi,0.1)))

        st_share    = round(random.uniform(5, 20) if loc in ['Dubai Marina','Palm Jumeirah','JBR','Downtown Dubai','Saadiyat Island','Yas Island'] else random.uniform(1, 8), 1)
        st_adr      = round(mo_rent / 28 * random.uniform(1.2, 2.5) / 10) * 10
        st_occ      = round(random.uniform(55, 88), 1)
        st_rev      = round(st_adr * 365 * st_occ / 100 / 1000) * 1000

        mkt_avg_yield = round(gross_yield + random.uniform(-0.5, 0.5), 2)
        yoy_change  = round((yr_factor - RENT_YR_FACTOR.get(yr-1, yr_factor)) / RENT_YR_FACTOR.get(yr-1, yr_factor) * 100, 1)
        mom_change  = round(random.uniform(-2.5, 3.5), 1)
        p2r         = round(prop_price_base / max(avg_rent, 1), 1)
        tenancy_dur = round(random.uniform(10, 24), 1)

        rental_rows.append({
            'record_id':                    f'RENT{rent_ctr:06d}',
            'period_date':                  date(yr, mo, 1).strftime('%Y-%m-%d'),
            'year':                         yr,
            'month':                        mo,
            'quarter':                      quarter(mo),
            'emirate':                      emi,
            'city':                         emi,
            'locality':                     loc,
            'property_type':                pt,
            'bedrooms':                     random.choices(BEDROOMS, weights=BED_W)[0],
            'avg_annual_rent_aed':          avg_rent,
            'median_annual_rent_aed':       med_rent,
            'avg_monthly_rent_aed':         mo_rent,
            'rent_yoy_change_pct':          yoy_change,
            'rent_mom_change_pct':          mom_change,
            'gross_rental_yield_pct':       gross_yield,
            'net_rental_yield_pct':         net_yield,
            'occupancy_rate_pct':           occupancy,
            'vacancy_rate_pct':             vacancy,
            'avg_tenancy_duration_months':  tenancy_dur,
            'new_listings_count':           random.randint(10, 250),
            'total_active_listings':        random.randint(50, 1200),
            'short_term_rental_share_pct':  st_share,
            'short_term_avg_daily_rate_aed':st_adr,
            'short_term_occupancy_pct':     st_occ,
            'short_term_annual_revenue_aed':st_rev,
            'market_avg_yield_pct':         mkt_avg_yield,
            'yield_vs_market_diff':         round(gross_yield - mkt_avg_yield, 2),
            'avg_property_price_aed':       round(prop_price_base / 50000) * 50000,
            'price_to_rent_ratio':          p2r,
            'ejari_registrations':          ejari_cnt,
        })
        rent_ctr += 1
        if len(rental_rows) >= 5000:
            break
    if len(rental_rows) >= 5000:
        break

rental_df = pd.DataFrame(rental_rows[:5000]).sort_values(['period_date','locality']).reset_index(drop=True)
rental_df.to_csv(f'{BASE}/re_rental_market.csv', index=False)
print(f"  re_rental_market     -> {len(rental_df):,} rows, {len(rental_df.columns)} cols")
print("  [9/10] ✓ done")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 10 — re_documents_registry.csv  (10,000 rows)
# ─────────────────────────────────────────────────────────────────────────────

print("\n[10/10] Generating re_documents_registry.csv (10,000 rows) …")

DOC_TYPES = ['SPA','MOU','Title Deed','RERA NOC','Escrow Agreement',
             'Lease Agreement','Contractor Agreement','NOC Letter','Completion Certificate']
DOC_W     = [0.28,0.12,0.18,0.10,0.06,0.14,0.05,0.04,0.03]
LANGUAGES = ['English','Arabic','Bilingual']
LANG_W    = [0.45,0.20,0.35]

# Key clauses library
CLAUSES = {
    'SPA':                  'Payment schedule: 10% booking + 40% construction + 50% handover. Handover penalty: AED 200/day after grace period of 6 months.',
    'MOU':                  'Deposit: 10% held by broker. Validity: 30 days. Subject to SPA execution.',
    'Title Deed':           'Freehold title registered with DLD. No encumbrances noted.',
    'RERA NOC':             'NOC valid for 3 months from issue date. Project escrow account verified.',
    'Escrow Agreement':     'Escrow account: FAB/ENBD. Withdrawal milestones per RERA guidelines.',
    'Lease Agreement':      'Lease term: 12 months renewable. Notice period: 90 days. Ejari registered.',
    'Contractor Agreement': 'Fixed-price contract. 10% retention. Defects liability: 12 months post-handover.',
    'NOC Letter':           'No objection for transfer/resale. Valid 30 days from issue.',
    'Completion Certificate': 'BCC issued by DM/DED. All inspections passed. Fit for occupation.',
}

AI_SUMMARIES = {
    'SPA':                  'Sale and Purchase Agreement between buyer and developer for off-plan unit. Key terms include payment schedule, handover date, and penalty clauses for delay.',
    'MOU':                  'Memorandum of Understanding for property purchase with 10% deposit held in escrow. Subject to execution of formal SPA within 30 days.',
    'Title Deed':           'Freehold title deed registered with Dubai Land Department. Property transferred free of encumbrances.',
    'RERA NOC':             'RERA No Objection Certificate confirming project compliance and escrow fund adequacy for phase release.',
    'Escrow Agreement':     'Escrow arrangement per RERA Law 8 of 2007. Funds released against certified construction milestones.',
    'Lease Agreement':      'Residential tenancy agreement registered with Ejari. Standard RERA lease terms apply.',
    'Contractor Agreement': 'Fixed-price construction contract with milestone payments and performance retention.',
    'NOC Letter':           'No Objection Certificate from developer allowing buyer to resell or transfer the property.',
    'Completion Certificate': 'Building Completion Certificate from Dubai Municipality confirming property is habitable.',
}

txn_ids  = txn_full['transaction_id'].tolist()
doc_rows = []
for i in range(10_000):
    dt   = random.choices(DOC_TYPES, weights=DOC_W)[0]
    yr   = random.randint(2019, 2026)
    mo   = random.randint(1, 5) if yr == 2026 else random.randint(1, 12)
    doc_date = rand_date(yr, mo)

    # Expiry logic
    if dt in ['RERA NOC','NOC Letter']:
        exp_date = doc_date + timedelta(days=90)
    elif dt == 'MOU':
        exp_date = doc_date + timedelta(days=30)
    elif dt in ['Lease Agreement']:
        exp_date = doc_date + timedelta(days=365)
    elif dt in ['Contractor Agreement']:
        exp_date = doc_date + timedelta(days=random.randint(365, 1460))
    else:
        exp_date = None

    days_to_exp = (exp_date - date.today()).days if exp_date else None
    if days_to_exp is not None:
        exp_status = 'Expired' if days_to_exp < 0 else ('Expiring Soon' if days_to_exp <= 30 else 'Active')
    else:
        exp_status = 'Active'

    proj = random.choice(proj_names)
    dev  = random.choice(dev_ids)
    buyer= random.choice(buyer_ids) if dt in ['SPA','MOU','Title Deed','Lease Agreement'] else None
    cont = random.choice(contractors_df['contractor_id'].tolist()) if dt in ['Contractor Agreement'] else None
    t_id = random.choice(txn_ids) if dt in ['SPA','Title Deed','NOC Letter'] else None
    emi  = random.choices(EMIRATES, weights=EMI_W)[0]

    penalty = dt in ['SPA','Contractor Agreement']
    notarized = dt in ['SPA','Title Deed','Lease Agreement'] and random.random() < 0.80
    reg_dld   = dt in ['SPA','Title Deed'] and random.random() < 0.90

    doc_rows.append({
        'document_id':              f'DOC{i+1:06d}',
        'document_type':            dt,
        'document_name':            f'{dt.replace(" ","_")}_{proj.replace(" ","_")[:20]}_{doc_date.strftime("%Y%m%d")}.pdf',
        'project_name':             proj,
        'developer_id':             dev,
        'buyer_id':                 buyer,
        'contractor_id':            cont,
        'transaction_id':           t_id,
        'dld_permit_no':            f'DLD-{random.randint(100000,999999)}' if dt in ['SPA','Title Deed','RERA NOC'] else None,
        'rera_registration_no':     f'RERA-{random.randint(100000,999999)}' if dt == 'RERA NOC' else None,
        'upload_date':              (doc_date + timedelta(days=random.randint(0,7))).strftime('%Y-%m-%d'),
        'document_date':            doc_date.strftime('%Y-%m-%d'),
        'expiry_date':              exp_date.strftime('%Y-%m-%d') if exp_date else None,
        'days_to_expiry':           days_to_exp,
        'expiry_status':            exp_status,
        'signatory_buyer':          f'Buyer {random.randint(1000,9999)}' if buyer else None,
        'signatory_developer':      f'{random.choice(["Mr.","Ms.","Dr."])} {random.choice(["Al Maktoum","Rahman","Singh","Sharma","Patel","Ali","Khan"])}',
        'notarized':                notarized,
        'registered_with_dld':      reg_dld,
        'key_clauses_extracted':    CLAUSES.get(dt, 'Standard terms apply.'),
        'payment_schedule_json':    '{"10%":"On Booking","40%":"During Construction","50%":"On Handover"}' if dt == 'SPA' else None,
        'handover_date_in_doc':     (doc_date + timedelta(days=random.randint(365,1460))).strftime('%Y-%m-%d') if dt in ['SPA','MOU'] else None,
        'penalty_clause_present':   penalty,
        'ai_summary':               AI_SUMMARIES.get(dt, 'Standard document.'),
        'file_size_kb':             round(random.uniform(120, 4500), 1),
        'page_count':               random.randint(3, 85),
        'language':                 random.choices(LANGUAGES, weights=LANG_W)[0],
        'emirate':                  emi,
    })

docs_df = pd.DataFrame(doc_rows).sort_values('document_date').reset_index(drop=True)
docs_df.to_csv(f'{BASE}/re_documents_registry.csv', index=False)
print(f"  re_documents_registry -> {len(docs_df):,} rows, {len(docs_df.columns)} cols")
print("  [10/10] ✓ done")

# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("ALL DATASETS GENERATED SUCCESSFULLY")
print("=" * 60)

all_files = [
    're_transactions.csv','re_buyers.csv','re_listings.csv','re_developers.csv',
    're_properties.csv','re_market_factors.csv','re_leads_pipeline.csv',
    're_construction_tracker.csv','re_contractors.csv','re_financials.csv',
    're_competitor_market.csv','re_rental_market.csv','re_documents_registry.csv',
]

total_rows = 0
print(f"\n{'File':<35} {'Rows':>8}  {'Cols':>5}  {'Size (MB)':>10}")
print("-" * 65)
for f in all_files:
    path = f'{BASE}/{f}'
    df   = pd.read_csv(path)
    size = os.path.getsize(path) / 1_048_576
    print(f"{f:<35} {len(df):>8,}  {len(df.columns):>5}  {size:>9.2f} MB")
    total_rows += len(df)

print("-" * 65)
print(f"{'TOTAL':<35} {total_rows:>8,}")
print(f"\nDate coverage : Jan 2019 – May 2026")
print(f"All files saved to: {BASE}")
