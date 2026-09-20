"""
Generate a realistic US dealer-group dataset (24 rooftops across six states) in the platform's canonical format.

Column names are the platform's own field names, values are metric and currency-free (the account's settings carry
USD), so every column maps with "exact" confidence on upload.

What is REAL (downloaded into data/public/ from FRED, i.e. BLS / BEA / Census / Federal Reserve / EIA):
  - the group's monthly volume follows the real US new light-vehicle sales series (TOTALNSA), so the 2020 collapse,
    the 2021-22 chip shortage and the 2023-25 recovery land in the right months
  - gasoline / diesel / crude prices, fed funds rate, 48-month new-car loan rate, CPI inflation, unemployment, GDP growth,
    consumer sentiment, house prices, dealer inventory-to-sales ratio (as days' supply)
  - list prices follow the CPI for new vehicles, trade-in values follow the CPI for used vehicles (the 2021-22 spike)
What is MODELLED (no public dealer-level data exists): every individual sale, customer, store and stock position; model
specs and prices are approximate; incentive spend and state tax rates are approximate.

Run: python scripts/generate_us_data.py --out DIR
"""
import argparse
import calendar
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from us_market_data import (  # noqa: E402
    BRAND_CATALOG, BRAND_ORIGIN_REGION, BRAND_SHARE, BRAND_TRIMS, BRAND_WARRANTY_YEARS, CATEGORY_MARKET_WEIGHT, CVT_BRANDS,
    DEALER_FAMILY_NAMES, DEALER_STREETS, FIRST_NAMES, IMPORT_PORTS, INCOME_BRACKETS, LAST_NAMES,
    LEASE_RATE_BY_CATEGORY, MANUAL_MODELS, MODEL_TIER_WEIGHT, NAME_POOLS_EXTRA, NATIONALITIES, OCCUPATION_WEIGHTS,
    OCCUPATIONS, ORIGIN_LEAD_DAYS, STATES, TRADE_OVER_ALLOWANCE_MULT, TRIM_HP_MULT, TRIM_KWH_DELTA, TRIM_MPG_DELTA,
    TRIM_PRICE_MULT, US_PLANTS,
)

ROOT = HERE.parent
PUBLIC = ROOT / "data" / "public"
START = date(2019, 1, 1)
END = date(2026, 8, 31)
MONTHS = pd.date_range(START, END, freq="MS")
N_MONTHS = len(MONTHS)
MONTH_OF = np.array([d.month for d in MONTHS])
YEAR_OF = np.array([d.year for d in MONTHS])

MI_TO_KM = 1.609344
GAL_TO_L = 3.785411784
L100_FROM_MPG = 235.214583
HP_TO_KW = 0.7456999

STATE_NAMES = [s["name"] for s in STATES]
STATE_WEIGHTS = np.array([s["weight"] for s in STATES], dtype=float)
STATE_WEIGHTS = STATE_WEIGHTS / STATE_WEIGHTS.sum()
STATE_TAX = {s["name"]: s["tax"] for s in STATES}

BRAND_NAMES = list(BRAND_CATALOG)
BRAND_WEIGHTS = np.array([BRAND_SHARE[b] for b in BRAND_NAMES], dtype=float)
BRAND_WEIGHTS = BRAND_WEIGHTS / BRAND_WEIGHTS.sum()


# ── real series ─────────────────────────────────────────────────────────────────────────────────────────────────

def _fred(series_id: str) -> pd.Series:
    path = PUBLIC / f"fred_{series_id}.csv"
    if not path.exists():
        path = PUBLIC / f"{series_id}.csv"
    df = pd.read_csv(path)
    return pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").to_numpy(), index=pd.to_datetime(df.iloc[:, 0])).dropna()


def _monthly(series: pd.Series) -> np.ndarray:
    """Align a monthly / quarterly series to MONTHS, carrying the latest published value forward."""
    full = pd.date_range(min(series.index.min(), MONTHS[0]), MONTHS[-1], freq="MS")
    return series.reindex(full).ffill().reindex(MONTHS).to_numpy(dtype=float)


MARKET_UNITS = _monthly(_fred("TOTALNSA"))                       # real US light-vehicle sales, thousand units, NSA
GAS_PER_GAL = _monthly(_fred("GASREGM"))
DIESEL_PER_GAL = _monthly(_fred("GASDESM"))
WTI = _monthly(_fred("MCOILWTICO"))
FED_FUNDS = _monthly(_fred("FEDFUNDS"))
AUTO_LOAN_APR = _monthly(_fred("TERMCBAUTO48NS"))
_cpi = _fred("CPIAUCSL")
CPI_YOY = _monthly((_cpi.pct_change(12) * 100).dropna())
UNEMPLOYMENT = _monthly(_fred("UNRATE"))
GDP_GROWTH = _monthly(_fred("A191RL1Q225SBEA"))
CONSUMER_SENTIMENT = _monthly(_fred("UMCSENT"))
_hpi = _fred("CSUSHPINSA")
HOUSE_PRICE_IDX = _monthly(_hpi) / float(_hpi["2019-01-01"]) * 100
DAYS_SUPPLY = _monthly(_fred("AISRSA")) * 30.0                    # dealer inventory / sales ratio (months) -> days
_new = _monthly(_fred("CUSR0000SETA01"))
NEW_PRICE_IDX = _new / _new[-1]                                   # list-price level relative to the catalog (latest = 1)
_used = _monthly(_fred("CUSR0000SETA02"))
USED_PRICE_IDX = _used / float(np.mean(_used[:12]))               # used-vehicle value relative to 2019

# J.D. Power-style incentive spend as % of average transaction price. Approximate published trend: rich pre-COVID,
# collapsing in the 2021-22 shortage, rebuilding since. Approximate, not a dataset.
_INC_ANCHORS = [(2019, 1, 10.2), (2019, 12, 10.8), (2020, 4, 10.0), (2020, 9, 10.6), (2020, 12, 9.2), (2021, 3, 7.0),
                (2021, 8, 4.8), (2021, 12, 3.8), (2022, 6, 2.9), (2022, 12, 3.2), (2023, 6, 5.3), (2023, 12, 6.7),
                (2024, 6, 7.1), (2024, 12, 7.4), (2025, 6, 7.2), (2025, 12, 7.4), (2026, 8, 7.5)]
INCENTIVE_PCT_ATP = np.interp(np.arange(N_MONTHS),
                              [(y - 2019) * 12 + m - 1 for y, m, _ in _INC_ANCHORS], [v for _, _, v in _INC_ANCHORS])

_normal = MARKET_UNITS[(YEAR_OF <= 2019) | (YEAR_OF >= 2023)]
_normal_m = MONTH_OF[(YEAR_OF <= 2019) | (YEAR_OF >= 2023)]
RETAIL_SEASONAL_FACTOR = {m: float(np.mean(_normal[_normal_m == m]) / np.mean(_normal)) for m in range(1, 13)}

QUARTER_END_MONTH = np.where(np.isin(MONTH_OF, [3, 6, 9, 12]), 1, 0)
YEAR_END_MONTH = np.where(MONTH_OF == 12, 1, 0)
NEW_MODEL_LAUNCHES = np.where(np.isin(MONTH_OF, [8, 9, 10]), 3, 1)      # model-year changeover

# Day-of-week pattern (Mon..Sun): Saturday peak, Sunday mostly closed (several of these states restrict Sunday sales).
DOW_WEIGHT = np.array([0.125, 0.130, 0.135, 0.145, 0.175, 0.260, 0.030])

# ── powertrain mix by year (relative weights applied to catalog nameplates; tuned to the real US shares) ────────────
# Franchised dealers only: Tesla sells direct, so the group's BEV share is roughly half the national ~8% in 2024.
EV_WEIGHT_BY_YEAR = {2019: 0.55, 2020: 0.60, 2021: 0.90, 2022: 1.55, 2023: 2.05, 2024: 2.20, 2025: 2.25, 2026: 1.70}
HYBRID_WEIGHT_BY_YEAR = {2019: 0.25, 2020: 0.33, 2021: 0.45, 2022: 0.60, 2023: 0.88, 2024: 1.33, 2025: 1.78, 2026: 1.98}
DIESEL_WEIGHT_BY_YEAR = {y: 1.0 for y in range(2019, 2027)}
LEASE_YEAR_MULT = {2019: 1.44, 2020: 1.31, 2021: 1.01, 2022: 0.79, 2023: 0.91, 2024: 1.03, 2025: 1.06, 2026: 1.08}
COMMERCIAL_SHARE_PCT = 19.0


def _season_period(d: date):
    """Retail sales-event label (canonical English), or None."""
    y = d.year
    def nth_weekday(month, weekday, n):
        first = date(y, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last_may = max(date(y, 5, x) for x in range(25, 32) if date(y, 5, x).weekday() == 0)
    events = {"Presidents Day": nth_weekday(2, 0, 3), "Memorial Day": last_may, "Fourth of July": date(y, 7, 4),
              "Labor Day": nth_weekday(9, 0, 1), "Black Friday": nth_weekday(11, 4, 4)}
    for label, when in events.items():
        if abs((d - when).days) <= 3:
            return label
    if d.month == 12 and d.day >= 15:
        return "Year-End Sales Event"
    if (d.month == 2 and d.day >= 15) or (d.month == 3 and d.day <= 31):
        return "Tax Refund Season"
    return None


# ── vehicles ────────────────────────────────────────────────────────────────────────────────────────────────────

def build_vehicle_catalog(rng, n_trims=2):
    rows, vid = [], 1
    for brand, models in BRAND_CATALOG.items():
        trims = BRAND_TRIMS[brand][:n_trims]
        origin = "Domestic" if BRAND_ORIGIN_REGION[brand] == "North America" else "Import"
        for (model, category, fuel, msrp, hp, cc, mpg, kwh_mi, range_mi, seats, drive, resid, intro) in models:
            is_ev = fuel == "Electric"
            for ti, trim in enumerate(trims):
                price = int(round(msrp * TRIM_PRICE_MULT[ti] / 50.0) * 50)
                kw = int(round(hp * TRIM_HP_MULT[ti] * HP_TO_KW))
                l100 = None if is_ev else round(L100_FROM_MPG / max(mpg + TRIM_MPG_DELTA[ti], 8.0), 1)
                kwh100 = round((kwh_mi + TRIM_KWH_DELTA[ti]) / MI_TO_KM, 1) if is_ev else None
                range_km = int(round(range_mi * MI_TO_KM * (1.0 - 0.03 * ti))) if is_ev else None
                if is_ev:
                    co2 = 0
                else:
                    grams_per_gal = 10180.0 if fuel == "Diesel" else 8887.0
                    co2 = int(round(grams_per_gal / max(mpg + TRIM_MPG_DELTA[ti], 8.0) / MI_TO_KM))
                if is_ev:
                    transmission = "Single-Speed"
                elif model in MANUAL_MODELS and rng.random() < MANUAL_MODELS[model]:
                    transmission = "Manual"
                elif fuel == "Hybrid":
                    transmission = "eCVT"
                elif brand in CVT_BRANDS:
                    transmission = "CVT"
                else:
                    transmission = "Automatic"
                rows.append({
                    "vehicle_id": f"VH{vid:04d}", "brand": brand, "model": model, "variant": trim, "category": category,
                    "fuel_type": fuel, "price": price, "engine_cc": None if is_ev else cc, "power_kw": kw,
                    "consumption_l_per_100km": l100, "consumption_kwh_per_100km": kwh100, "range_km": range_km,
                    "co2_g_per_km": co2, "origin": origin, "seating_capacity": seats, "transmission": transmission,
                    "drive_type": drive, "body_color_options": int(rng.integers(6, 12)),
                    "safety_rating": 5 if resid >= 0.50 else int(rng.choice([4, 5], p=[0.35, 0.65])),
                    "launch_year": intro, "is_active": True, "warranty_years": BRAND_WARRANTY_YEARS.get(brand, 3),
                    "service_contract_available": bool(rng.random() < 0.85), "_residual_36mo": resid,
                })
                vid += 1
    return pd.DataFrame(rows)


# ── dealers ─────────────────────────────────────────────────────────────────────────────────────────────────────

def _distribute_by_weight(total, weights):
    weights = np.asarray(weights, dtype=float)
    weights = weights / weights.sum()
    raw = weights * total
    base = np.floor(raw).astype(int)
    remainder = total - base.sum()
    if remainder > 0:
        base[np.argsort(-(raw - base))[:remainder]] += 1
    return base


def _group_brand_portfolio(rng, n_rooftops):
    picks = list(rng.choice(BRAND_NAMES, size=n_rooftops, p=BRAND_WEIGHTS))
    from collections import Counter
    for b in [b for b in BRAND_NAMES if b not in picks]:
        counts = Counter(picks)
        donor = max(counts, key=lambda k: (counts[k], k))
        if counts[donor] <= 1:
            break
        picks[picks.index(donor)] = b
    rng.shuffle(picks)
    return picks


def build_dealers(rng, n_rooftops):
    per_state = _distribute_by_weight(n_rooftops, STATE_WEIGHTS)
    brands = _group_brand_portfolio(rng, n_rooftops)
    rows, did, bi, used_names = [], 1, 0, set()
    for st, k in zip(STATES, per_state):
        for _ in range(int(k)):
            brand = brands[bi]
            bi += 1
            city, lat, lon, zip_prefix = st["cities"][rng.integers(0, len(st["cities"]))]
            for _try in range(20):
                template = rng.choice(["{brand} of {city}", "{family} {brand}", "{city} {brand}", "{family} {brand} of {city}"])
                name = template.format(brand=brand, city=city, family=rng.choice(DEALER_FAMILY_NAMES))
                if name not in used_names:
                    break
            else:
                name = f"{name} {did}"
            used_names.add(name)
            rows.append({
                "dealer_id": f"DLR{did:04d}", "dealer_name": name, "brand": brand, "region": st["name"], "city": city,
                "address": f"{int(rng.integers(100, 9900))} {rng.choice(DEALER_STREETS)}",
                "postal_code": f"{zip_prefix}{int(rng.integers(0, 100)):02d}",
                "tier": rng.choice(["Platinum", "Gold", "Silver"], p=[0.25, 0.50, 0.25]),
                "established_year": int(rng.integers(1958, 2016)),
                "monthly_capacity": int(rng.integers(90, 340)),
                "showroom_area_sqm": int(rng.integers(900, 3600)),
                "service_center": bool(rng.random() < 0.97),
                "ev_charging_station": bool(rng.random() < (0.85 if brand in ("Hyundai", "Kia", "Cadillac", "Volkswagen", "Ford", "Chevrolet") else 0.55)),
                "num_salespeople": int(rng.integers(12, 40)),
                "annual_target_units": 0,
                "performance_score": round(float(rng.uniform(62, 96)), 1),
                "google_rating": round(float(rng.uniform(3.9, 4.8)), 1),
                "latitude": round(lat + rng.uniform(-0.08, 0.08), 5), "longitude": round(lon + rng.uniform(-0.08, 0.08), 5),
            })
            did += 1
    return pd.DataFrame(rows)


# ── customers ───────────────────────────────────────────────────────────────────────────────────────────────────

def build_customers(rng, n, start, end):
    customer_id = [f"CUS{i:06d}" for i in range(1, n + 1)]
    nat_names = [x[0] for x in NATIONALITIES]
    nat_w = np.array([x[1] for x in NATIONALITIES]) / sum(x[1] for x in NATIONALITIES)
    nat_idx = rng.choice(len(NATIONALITIES), size=n, p=nat_w)
    nationality = np.array([nat_names[i] for i in nat_idx])
    names = []
    for i in nat_idx:
        pool = NATIONALITIES[i][2]
        firsts, lasts = NAME_POOLS_EXTRA.get(pool, (FIRST_NAMES, LAST_NAMES))
        names.append(f"{firsts[rng.integers(0, len(firsts))]} {lasts[rng.integers(0, len(lasts))]}")

    commercial_customer_share = 0.13
    customer_type = np.where(rng.random(n) < commercial_customer_share, "Commercial", "Private")
    age = np.clip(rng.normal(52, 13, n), 21, 88).astype(int)
    gender = rng.choice(["Male", "Female", "Other"], size=n, p=[0.55, 0.44, 0.01])

    state_idx = rng.choice(len(STATES), size=n, p=STATE_WEIGHTS)
    state = [STATES[i]["name"] for i in state_idx]
    picks = [STATES[i]["cities"][rng.integers(0, len(STATES[i]["cities"]))] for i in state_idx]
    city = [c[0] for c in picks]
    postal_code = [f"{c[3]}{int(rng.integers(0, 100)):02d}" for c in picks]
    occupation = rng.choice(OCCUPATIONS, size=n, p=np.array(OCCUPATION_WEIGHTS) / sum(OCCUPATION_WEIGHTS))

    income = np.clip(rng.lognormal(np.log(78000), 0.55, n), 18000, 900000)
    income = income * np.where(customer_type == "Commercial", 1.4, 1.0)
    income = income.round(0)
    bracket = [INCOME_BRACKETS[i] for i in np.digitize(income, [40000, 70000, 110000, 170000])]

    # FICO: mean ~715, sd ~85, long lower tail; new-vehicle buyers skew a little higher with income.
    fico = 300 + 550 * rng.beta(5.2, 1.8, n) + 14 * np.log1p(income / 78000)
    credit = np.clip(fico, 420, 850).astype(int)

    return pd.DataFrame({
        "customer_id": customer_id, "name": names, "age": age, "gender": gender, "nationality": nationality,
        "customer_type": customer_type, "region": state, "city": city, "postal_code": postal_code,
        "occupation": occupation, "income_bracket": bracket, "annual_income": income, "credit_score": credit,
        "years_at_address": np.clip(rng.exponential(6.5, n), 0, 45).astype(int),
        "number_of_past_purchases": rng.poisson(1.1, n),
        "preferred_fuel_type": rng.choice(["Petrol", "Hybrid", "Electric", "Diesel"], size=n, p=[0.76, 0.14, 0.07, 0.03]),
        "preferred_vehicle_category": rng.choice(["SUV", "Pickup", "Sedan", "Hatchback", "Minivan", "Luxury", "Coupe"],
                                                 size=n, p=[0.46, 0.18, 0.16, 0.04, 0.04, 0.07, 0.05]),
        "customer_segment": "Unclassified",
        "loyalty_score": np.clip(rng.normal(50, 22, n), 0, 100).round(2),
        "marketing_response_score": np.clip(rng.normal(5, 2.2, n), 0, 10).round(2),
        "lead_source": rng.choice(["Online Ad", "Referral", "Dealer Walk-in", "Search Engine", "Social Media", "Marketplace Portal"],
                                  size=n, p=[0.14, 0.14, 0.16, 0.20, 0.10, 0.26]),
        "email_opt_in": rng.random(n) < 0.62, "test_drive_taken": rng.random(n) < 0.58,
        "financing_preferred": rng.random(n) < 0.78,
        "down_payment_capacity": np.clip(income * rng.uniform(0.06, 0.25, n), 500, None).astype(int),
        "registration_date": [start + timedelta(days=int(o)) for o in rng.integers(0, (end - start).days, n)],
        "last_activity_date": [start] * n,       # rewritten from the sales below
        "churn_risk_score": np.clip(rng.beta(2, 5, n), 0, 1).round(3),
    })


# ── external factors (real national series; per-state gas price and tax) ─────────────────────────────────────────

def build_external_factors(rng):
    rows = []
    for mi in range(N_MONTHS):
        y, m = int(YEAR_OF[mi]), int(MONTH_OF[mi])
        for st in STATES:
            gas = max(GAS_PER_GAL[mi] + st["gas_offset"], 1.0) / GAL_TO_L
            diesel = max(DIESEL_PER_GAL[mi] + st["gas_offset"] * 0.8, 1.2) / GAL_TO_L
            rows.append({
                "date": date(y, m, 1), "year": y, "month": m, "quarter": f"Q{(m - 1) // 3 + 1}", "region": st["name"],
                "petrol_price_per_litre": round(float(gas), 3), "diesel_price_per_litre": round(float(diesel), 3),
                "crude_oil_price_usd": round(float(WTI[mi]), 2), "gdp_growth_pct": round(float(GDP_GROWTH[mi]), 2),
                "cpi_inflation_pct": round(float(CPI_YOY[mi]), 2), "policy_rate_pct": round(float(FED_FUNDS[mi]), 2),
                "auto_loan_apr_pct": round(float(AUTO_LOAN_APR[mi]), 2),
                "incentive_pct_of_atp": round(float(INCENTIVE_PCT_ATP[mi]), 2),
                "inventory_days_supply": round(float(DAYS_SUPPLY[mi]), 1),
                "consumer_confidence_index": round(float(CONSUMER_SENTIMENT[mi]), 1),
                "house_price_index": round(float(HOUSE_PRICE_IDX[mi]), 1),
                "unemployment_rate_pct": round(float(UNEMPLOYMENT[mi]), 2),
                "population_millions": st["pop_m"], "new_model_launches": int(NEW_MODEL_LAUNCHES[mi]),
                "tax_rate_pct": st["tax"], "quarter_end_month": int(QUARTER_END_MONTH[mi]),
                "year_end_month": int(YEAR_END_MONTH[mi]),
            })
    return pd.DataFrame(rows)


# ── sales ───────────────────────────────────────────────────────────────────────────────────────────────────────

def build_sales(rng, n, vehicles_df, dealers_df, customers_df, start, end):
    # Monthly volume = the real US market shape x a slowly drifting group-specific share. The group's annual totals
    # therefore follow the real market year by year (COVID, chip shortage, recovery).
    drift = np.zeros(N_MONTHS)
    for i in range(1, N_MONTHS):
        drift[i] = 0.85 * drift[i - 1] + rng.normal(0, 0.012)     # mean-reverting: the group tracks its market
    share = np.exp(drift + rng.normal(0, 0.02, N_MONTHS))
    month_weight = MARKET_UNITS * share
    for year in np.unique(YEAR_OF):          # tie each year's total to the real market total (share only shapes the months)
        sel = YEAR_OF == year
        month_weight[sel] *= MARKET_UNITS[sel].sum() / month_weight[sel].sum()
    month_p = month_weight / month_weight.sum()
    sale_month_idx = rng.choice(N_MONTHS, size=n, p=month_p)

    day_in_month = np.empty(n, dtype=int)
    for mi in np.unique(sale_month_idx):
        y, m = int(YEAR_OF[mi]), int(MONTH_OF[mi])
        last = calendar.monthrange(y, m)[1]
        days = np.arange(1, last + 1)
        wd = np.array([date(y, m, int(d)).weekday() for d in days])
        p = DOW_WEIGHT[wd] * np.where(days >= last - 3, 1.35, 1.0)      # month-end push (commission tiers, quotas)
        p = p / p.sum()
        sel = sale_month_idx == mi
        day_in_month[sel] = rng.choice(days, size=int(sel.sum()), p=p)
    sale_date = [date(int(YEAR_OF[mi]), int(MONTH_OF[mi]), int(d)) for mi, d in zip(sale_month_idx, day_in_month)]

    brand_choice = rng.choice(BRAND_NAMES, size=n, p=BRAND_WEIGHTS)
    sale_year = YEAR_OF[sale_month_idx].astype(int)
    sale_mo = MONTH_OF[sale_month_idx].astype(int)

    veh_by_brand = {b: vehicles_df[vehicles_df["brand"] == b].reset_index(drop=True) for b in BRAND_NAMES}
    brand_fuel = {b: veh_by_brand[b]["fuel_type"].to_numpy() for b in BRAND_NAMES}
    brand_cat = {b: veh_by_brand[b]["category"].to_numpy() for b in BRAND_NAMES}
    brand_pop = {b: np.array([MODEL_TIER_WEIGHT.get(m, 1.0) for m in veh_by_brand[b]["model"]], dtype=float)
                 * np.array([CATEGORY_MARKET_WEIGHT.get(c, 1.0) for c in veh_by_brand[b]["category"]], dtype=float)
                 for b in BRAND_NAMES}

    # Route each sale to a store of that brand, preferring the shopper's own state.
    dealers_by_brand = {b: dealers_df[dealers_df["brand"] == b] for b in BRAND_NAMES}
    dealers_by_brand_state = {(b, st): dealers_df[(dealers_df["brand"] == b) & (dealers_df["region"] == st)]
                              for b in BRAND_NAMES for st in STATE_NAMES}
    dealer_state = dict(zip(dealers_df["dealer_id"], dealers_df["region"]))
    dealer_city = dict(zip(dealers_df["dealer_id"], dealers_df["city"]))
    pref_state_idx = rng.choice(len(STATES), size=n, p=STATE_WEIGHTS)
    dealer_ids = []
    for b, psi in zip(brand_choice, pref_state_idx):
        pool = dealers_by_brand_state.get((b, STATE_NAMES[psi]))
        if pool is None or len(pool) == 0:
            pool = dealers_by_brand.get(b)
        if pool is None or len(pool) == 0:
            pool = dealers_df
        dealer_ids.append(pool.iloc[int(rng.integers(0, len(pool)))]["dealer_id"])
    region = [dealer_state[d] for d in dealer_ids]
    city = [dealer_city[d] for d in dealer_ids]
    state_arr = np.array(region)

    wants_commercial = rng.random(n) < COMMERCIAL_SHARE_PCT / 100.0
    sale_customer_type = np.where(wants_commercial, "Commercial", "Private")

    _elist = list(dealers_df["dealer_id"])
    _eff = rng.normal(0.0, 1.0, len(_elist))
    _eff = _eff - _eff.mean()
    eff_arr = np.array([dict(zip(_elist, _eff))[d] for d in dealer_ids])

    # Vehicle selection: powertrain mix follows the real adoption path; fleet buyers lean to pickups and vans.
    vehicle_rows = []
    for b, yr, mo, is_comm in zip(brand_choice, sale_year, sale_mo, wants_commercial):
        pool, fuels, cats = veh_by_brand[b], brand_fuel[b], brand_cat[b]
        w = brand_pop[b].copy()
        w[fuels == "Electric"] *= EV_WEIGHT_BY_YEAR[int(yr)]
        w[fuels == "Hybrid"] *= HYBRID_WEIGHT_BY_YEAR[int(yr)]
        w[fuels == "Diesel"] *= DIESEL_WEIGHT_BY_YEAR[int(yr)]
        if is_comm:
            w[cats == "Pickup"] *= 1.9
            w[cats == "Minivan"] *= 1.3
            w[cats == "Luxury"] *= 0.3
            w[cats == "Coupe"] *= 0.2
            w[fuels == "Diesel"] *= 2.5
        else:
            w[cats == "SUV"] *= 1.05
        if mo in (3, 6, 9, 12):
            w[cats == "SUV"] *= 1.05
            w[cats == "Luxury"] *= 1.10
        w /= w.sum()
        vehicle_rows.append(pool.iloc[int(rng.choice(len(pool), p=w))])
    veh = pd.DataFrame(vehicle_rows).reset_index(drop=True)

    # Customer attachment: chronological, a realistic new-vs-returning split, matched on private/commercial.
    P_RETURNING = {"Commercial": 0.72, "Private": 0.42}
    REBUY_MONTHS = {"Commercial": 10, "Private": 30}
    _cust_state = dict(zip(customers_df["customer_id"], customers_df["region"]))
    _cust_type = dict(zip(customers_df["customer_id"], customers_df["customer_type"]))
    fresh = {}
    for st in STATE_NAMES:
        for ct in ("Private", "Commercial"):
            sel = (customers_df["region"] == st) & (customers_df["customer_type"] == ct)
            fresh[(st, ct)] = list(rng.permutation(customers_df.loc[sel, "customer_id"].to_numpy()))
    bought_month = {}
    return_all = {ct: [] for ct in ("Private", "Commercial")}
    return_by_state = {(st, ct): [] for st in STATE_NAMES for ct in ("Private", "Commercial")}
    want_return = rng.random(n) < np.array([P_RETURNING[ct] for ct in sale_customer_type])
    travel = rng.random(n) < 0.20
    order = np.argsort(sale_month_idx, kind="stable")
    sm = sale_month_idx.astype(int)
    customer_ids = np.empty(n, dtype=object)

    def take_fresh(st, ct):
        q = fresh.get((st, ct)) if st is not None else None
        if q:
            return q.pop()
        for sx in STATE_NAMES:
            if fresh[(sx, ct)]:
                return fresh[(sx, ct)].pop()
        other = "Private" if ct == "Commercial" else "Commercial"
        for sx in STATE_NAMES:
            if fresh[(sx, other)]:
                return fresh[(sx, other)].pop()
        return None

    for i in order:
        cur, ct = sm[i], sale_customer_type[i]
        st = None if travel[i] else state_arr[i]
        picked = None
        if want_return[i] and len(return_all[ct]) > 200:
            pool = (return_by_state.get((st, ct)) or []) if st is not None else return_all[ct]
            if len(pool) < 12:
                pool = return_all[ct]
            for _ in range(6):
                cand = pool[int(rng.integers(0, len(pool)))]
                if cur - bought_month[cand] >= REBUY_MONTHS[ct]:
                    picked = cand
                    break
        if picked is None:
            cid = take_fresh(st, ct)
            if cid is None:
                picked = return_all[ct][int(rng.integers(0, len(return_all[ct])))]
            else:
                picked = cid
                actual = _cust_type.get(cid, ct)
                return_all[actual].append(cid)
                cst = _cust_state.get(cid)
                if (cst, actual) in return_by_state:
                    return_by_state[(cst, actual)].append(cid)
        customer_ids[i] = picked
        bought_month[picked] = cur

    sale_customer_type = np.array([_cust_type.get(c, "Private") for c in customer_ids])
    is_commercial = sale_customer_type == "Commercial"
    is_fleet = is_commercial & (rng.random(n) < 0.35)
    cix = customers_df.set_index("customer_id")
    cust_credit = cix["credit_score"].reindex(customer_ids).to_numpy(dtype=float)
    cust_income = cix["annual_income"].reindex(customer_ids).to_numpy(dtype=float)

    # Price: MSRP follows the real new-vehicle CPI; the discount follows the month's incentive environment.
    base_price = (veh["price"].values.astype(float) * NEW_PRICE_IDX[sale_month_idx] / 50.0).round(0) * 50.0
    incentive_at_sale = INCENTIVE_PCT_ATP[sale_month_idx]
    discount_pct = np.clip(rng.normal(incentive_at_sale, 2.6, n), 0, 30)
    discount_pct = np.clip(discount_pct + np.where(is_fleet, 5.0, np.where(is_commercial, 2.0, 0.0)), 0, 32)
    selling_price = (base_price * (1 - discount_pct / 100)).round(0)
    tax_rate = np.array([STATE_TAX[s] for s in state_arr]) / 100.0
    tax_amount = (selling_price * tax_rate).round(0)

    accessories = np.clip(rng.normal(1100, 550, n), 0, None).round(0)
    insurance = np.clip(rng.normal(650, 300, n), 0, None).round(0)            # GAP and credit products
    ext_warranty = np.where(rng.random(n) < 0.45, np.clip(rng.normal(1450, 450, n), 0, None), 0).round(0)
    total_excl = (selling_price + accessories + insurance + ext_warranty).round(0)
    total_incl = (total_excl + tax_amount).round(0)

    category, fuel = veh["category"].values, veh["fuel_type"].values
    lease_p = np.array([LEASE_RATE_BY_CATEGORY.get(c, 0.2) for c in category]) * np.array([LEASE_YEAR_MULT[int(y)] for y in sale_year])
    lease_p = np.clip(lease_p + np.where(is_commercial, 0.08, 0.0) + np.where(fuel == "Electric", 0.10, 0.0), 0.03, 0.70)
    is_lease = rng.random(n) < lease_p
    non_lease = rng.choice(["Cash", "Bank Loan", "Dealer Financing", "Captive Finance"], size=n, p=[0.19, 0.30, 0.25, 0.26])
    financing_type = np.where(is_lease, "Lease", non_lease)
    loan_amount = np.where(financing_type == "Cash", 0, (selling_price * rng.uniform(0.72, 0.98, n)).round(0))

    lease_terms, lease_term_w = [24, 36, 48], [0.25, 0.55, 0.20]
    annual_miles = np.array([10000, 12000, 15000])
    annual_km_choices = (annual_miles * MI_TO_KM).round(-1).astype(int)
    lease_term = rng.choice(lease_terms, size=n, p=lease_term_w)
    km_pick = rng.choice(3, size=n, p=[0.30, 0.45, 0.25])
    annual_km = annual_km_choices[km_pick]
    resid = veh["_residual_36mo"].values.astype(float) + np.array([{24: 0.10, 36: 0.0, 48: -0.10}[t] for t in lease_term])
    resid = resid + np.select([km_pick == 0, km_pick == 2], [0.03, -0.03], default=0.0)
    resid_pct = np.clip(resid + rng.normal(0, 0.012, n), 0.22, 0.80)
    residual = (base_price * resid_pct).round(0)
    lease_apr = np.clip(AUTO_LOAN_APR[sale_month_idx] + rng.normal(-0.8, 1.1, n), 0.9, 12.0)
    lease_payment = ((selling_price - residual) / lease_term + (selling_price + residual) * (lease_apr / 2400.0)).round(0)
    sd = pd.to_datetime(sale_date)
    tot = sd.year * 12 + (sd.month - 1) + lease_term
    maturity = pd.to_datetime(dict(year=tot // 12, month=tot % 12 + 1, day=np.minimum(sd.day, 28)))
    no_lease = ~is_lease

    # Trade-ins: values follow the real used-vehicle CPI, so the 2021-22 spike shows up in appraisals.
    trade_base = np.where(is_commercial, 0.15, np.where(financing_type == "Cash", 0.46, 0.60))
    has_trade = rng.random(n) < trade_base
    trade_age = rng.choice([3, 4, 5, 6, 7, 8, 9, 10], size=n, p=[0.10, 0.14, 0.16, 0.15, 0.14, 0.12, 0.10, 0.09])
    trade_year = sale_year - trade_age
    trade_mileage = np.clip((trade_age * rng.normal(21700, 4500, n)).round(-2), 12000, 450000).astype(int)   # km
    pick_w = np.array([BRAND_SHARE[b] for b in vehicles_df["brand"]]) * np.array([MODEL_TIER_WEIGHT.get(m, 1.0) for m in vehicles_df["model"]])
    trade_pick = rng.choice(len(vehicles_df), size=n, p=pick_w / pick_w.sum())
    trade_brand = vehicles_df["brand"].values[trade_pick]
    trade_model = vehicles_df["model"].values[trade_pick]
    orig_price = vehicles_df["price"].values[trade_pick].astype(float) * float(np.mean(NEW_PRICE_IDX[:12]))
    dep = 0.80 * np.power(0.90, np.maximum(trade_age - 1, 0))
    expected_km = np.maximum(trade_age * 21700, 1)
    mileage_factor = np.clip(1.0 - 0.20 * (trade_mileage - expected_km) / expected_km, 0.70, 1.20)
    appraised = np.maximum(orig_price * dep * mileage_factor * np.clip(USED_PRICE_IDX[sale_month_idx], 0.9, 1.6), 1500).round(0)
    over_mult = np.array([TRADE_OVER_ALLOWANCE_MULT.get(c, 1.0) for c in category])
    over_allow = np.maximum(rng.normal(1100, 800, n) * over_mult, 0).round(0)
    over_allow = np.where(rng.random(n) < 0.30, 0.0, over_allow)
    is_event = np.isin(MONTH_OF[sale_month_idx], [3, 6, 9, 12])
    bonus_p = np.clip(0.16 + 0.20 * is_event + 0.10 * (over_mult > 1.0), 0, 0.7)
    trade_bonus = np.where(rng.random(n) < bonus_p, rng.choice([500, 1000, 1500, 2000, 3000], size=n, p=[0.30, 0.28, 0.22, 0.13, 0.07]), 0).astype(float)
    allowance = appraised + over_allow

    channels = ["Online Ad", "Referral", "Showroom Walk-in", "Search Engine", "Social Media", "Marketplace Portal", "TV/Radio"]
    marketing_channel = rng.choice(channels, size=n, p=[0.14, 0.12, 0.20, 0.20, 0.08, 0.22, 0.04])
    chan = {"Showroom Walk-in": 0.10, "Referral": 0.06, "Marketplace Portal": 0.0, "TV/Radio": 0.0, "Search Engine": -0.03,
            "Online Ad": -0.05, "Social Media": -0.06}
    chan_eff = np.array([chan[c] for c in marketing_channel])
    pay_stress = np.clip((selling_price - 0.55 * np.nan_to_num(cust_income, nan=78000.0)) / 80000.0, 0, None)
    conv_z = (0.07 * eff_arr + chan_eff + 0.012 * (discount_pct - incentive_at_sale)
              + 0.0011 * (np.nan_to_num(cust_credit, nan=715.0) - 715.0) - 0.05 * pay_stress
              + 0.05 * has_trade.astype(float) + 0.06 * is_commercial.astype(float))
    conv_p = np.clip(0.62 + conv_z - conv_z.mean(), 0.28, 0.93)
    test_drive_converted = rng.random(n) < conv_p
    lead_to_close_days = np.clip(rng.integers(1, 60, n) - (trade_bonus / 400.0).round(0) - (3.5 * eff_arr).round(0)
                                 - (14.0 * (conv_p - 0.62)).round(0), 1, 60).astype(int)

    return pd.DataFrame({
        "sale_id": [f"SAL{i:07d}" for i in range(1, n + 1)], "sale_date": sale_date,
        "year": sale_year, "month": sale_mo, "quarter": [f"Q{(int(m) - 1) // 3 + 1}" for m in sale_mo],
        "day_of_week": pd.to_datetime(sale_date).day_name(), "season_period": [_season_period(d) for d in sale_date],
        "customer_id": customer_ids, "dealer_id": dealer_ids, "vehicle_id": veh["vehicle_id"].values,
        "brand": veh["brand"].values, "model": veh["model"].values, "vehicle_category": category, "fuel_type": fuel,
        "region": region, "city": city, "customer_type": sale_customer_type, "is_fleet": is_fleet,
        "base_price": base_price.astype(int), "discount_pct": discount_pct.round(2), "selling_price": selling_price.astype(int),
        "tax_amount": tax_amount.astype(int), "accessories_revenue": accessories.astype(int),
        "insurance_revenue": insurance.astype(int), "extended_warranty": ext_warranty.astype(int),
        "total_revenue_excl_tax": total_excl.astype(int), "total_revenue_incl_tax": total_incl.astype(int),
        "financing_type": financing_type, "loan_amount": loan_amount.astype(int), "units_sold": 1,
        "test_drive_converted": test_drive_converted, "lead_to_close_days": lead_to_close_days,
        "salesperson_id": [f"SP{int(x):04d}" for x in rng.integers(1, 400, n)], "marketing_channel": marketing_channel,
        "season_multiplier": np.clip(rng.normal(1.0, 0.08, n), 0.75, 1.35).round(3),
        "lease_term_months": np.where(no_lease, np.nan, lease_term),
        "lease_maturity_date": pd.Series(maturity).where(is_lease).dt.date,
        "residual_value_pct": np.where(no_lease, np.nan, resid_pct.round(4)),
        "residual_value": np.where(no_lease, np.nan, residual),
        "contract_mileage_allowance": np.where(no_lease, np.nan, (annual_km * lease_term / 12.0).round(-1)),
        "lease_monthly_payment": np.where(no_lease, np.nan, lease_payment),
        "trade_in_flag": has_trade, "trade_in_brand": np.where(has_trade, trade_brand, None),
        "trade_in_model": np.where(has_trade, trade_model, None), "trade_in_year": np.where(has_trade, trade_year, np.nan),
        "trade_in_mileage": np.where(has_trade, trade_mileage, np.nan),
        "trade_in_appraised_value": np.where(has_trade, appraised, np.nan),
        "trade_in_allowance": np.where(has_trade, allowance, np.nan),
        "trade_in_over_allowance": np.where(has_trade, over_allow, np.nan),
        "trade_bonus": np.where(has_trade, trade_bonus, 0.0),
    })


# ── inventory ───────────────────────────────────────────────────────────────────────────────────────────────────

def build_inventory(rng, vehicles_df, dealers_df, sales_df, history_months=36):
    months = MONTHS[-history_months:]
    month_pos = {m: i for i, m in enumerate(MONTHS)}
    obs = sales_df.groupby(["dealer_id", "vehicle_id"]).size().rename("total_units").reset_index()
    rate_lookup = dict(zip(zip(obs["dealer_id"], obs["vehicle_id"]), obs["total_units"] / max(N_MONTHS, 1)))
    veh_by_brand = {b: vehicles_df[vehicles_df["brand"] == b] for b in BRAND_NAMES}
    zones = ["Zone A", "Zone B", "Zone C", "Zone D"]
    rows, inv_id = [], 1
    for _, dealer in dealers_df.iterrows():
        pool = veh_by_brand.get(dealer["brand"])
        if pool is None or len(pool) == 0:
            continue
        per_model_capacity = max(dealer["monthly_capacity"] / max(len(pool), 1), 2.0)
        origin_region = BRAND_ORIGIN_REGION.get(dealer["brand"], "North America")
        lo, hi = ORIGIN_LEAD_DAYS[origin_region]
        domestic = origin_region == "North America"
        for _, v in pool.iterrows():
            desirability = float(np.clip((float(v["_residual_36mo"]) - 0.32) / (0.68 - 0.32), 0.0, 1.0))
            lead_time = int(rng.integers(lo, hi))
            base_rate = max(rate_lookup.get((dealer["dealer_id"], v["vehicle_id"]), 0.0), per_model_capacity * 0.06)
            zone = zones[inv_id % len(zones)]
            hub = rng.choice(US_PLANTS) if domestic else rng.choice(IMPORT_PORTS)
            for month_start in months:
                mi = month_pos[month_start]
                floorplan_apr = (FED_FUNDS[mi] + 2.5) / 100.0            # floor-plan financing tracks the policy rate
                holding_per_day = round(v["price"] * NEW_PRICE_IDX[mi] * floorplan_apr / 365.0 + rng.uniform(5.0, 14.0), 2)
                monthly_demand = max(base_rate * RETAIL_SEASONAL_FACTOR[month_start.month] * rng.uniform(0.75, 1.3), 0.4)
                sold_30d = int(np.clip(rng.poisson(monthly_demand), 0, None))
                daily = monthly_demand / 30.0
                supply_factor = float(np.clip(DAYS_SUPPLY[mi] / 55.0, 0.45, 1.7))     # real dealer stock tightness
                target = (28.0 + (1.0 - desirability) * 67.0) * supply_factor
                stock = int(np.clip(round(daily * target * float(np.clip(rng.normal(1.0, 0.30), 0.12, 2.1))), 0, 400))
                safety = 1.28 * np.sqrt(max(daily, 0.01) * lead_time)
                reorder_pt = max(int(round(min(daily * lead_time + safety, daily * max(target, 20.0) * 0.65))), 1)
                if desirability > 0.6 and rng.random() < (0.06 if supply_factor >= 0.8 else 0.16):
                    stock = 0
                forecast_30d = int(max(round(monthly_demand * rng.uniform(0.9, 1.15)), 0))
                in_transit = int(rng.poisson(max(monthly_demand * 0.5, 0.3))) if rng.random() < 0.55 else 0
                units_ordered = int(rng.poisson(max(monthly_demand * 0.8, 0.5)))
                days_supply = float(np.clip(stock / max(daily, 0.001), 0, 260))
                days_in_stock = int(np.clip(rng.normal(days_supply, 8), 1, 260))
                stockout, overstock = stock == 0, days_supply > 90
                cover = stock / reorder_pt
                rows.append({
                    "inventory_id": f"INV{inv_id:07d}", "record_date": (month_start + pd.offsets.MonthEnd(0)).date(),
                    "dealer_id": dealer["dealer_id"], "vehicle_id": v["vehicle_id"], "brand": v["brand"], "model": v["model"],
                    "vehicle_category": v["category"], "fuel_type": v["fuel_type"], "region": dealer["region"], "city": dealer["city"],
                    "current_stock": stock, "demand_forecast_30d": forecast_30d, "reorder_point": reorder_pt,
                    "days_in_stock": days_in_stock, "stockout_flag": bool(stockout), "overstock_flag": bool(overstock),
                    "reorder_needed": bool((not stockout) and stock <= reorder_pt),
                    "stockout_risk_score": round(float(np.clip(1.0 - cover / 2.0, 0.0, 1.0)), 3),
                    "overstock_risk_score": round(float(np.clip((days_supply - 60.0) / 90.0, 0.0, 1.0)), 3),
                    "holding_cost_per_day": holding_per_day, "estimated_holding_cost": round(holding_per_day * stock * 30.0, 2),
                    "units_sold_last_30d": sold_30d, "units_ordered": units_ordered, "transit_stock": in_transit,
                    "origin_hub": hub, "warehouse_zone": zone,
                    "last_replenishment_date": (month_start - pd.Timedelta(days=int(rng.integers(5, 50)))).date(),
                    "supplier_lead_time_days": lead_time, "customs_cleared": True if domestic else bool(rng.random() < 0.985),
                })
                inv_id += 1
    return pd.DataFrame(rows)


def _derive_customer_history(customers, sales, end):
    end_ts = pd.Timestamp(end)
    grp = sales.assign(_sd=pd.to_datetime(sales["sale_date"])).groupby("customer_id")["_sd"]
    n_deals = customers["customer_id"].map(grp.size()).fillna(0).astype(int)
    last_deal = customers["customer_id"].map(grp.max())
    gen_activity = pd.to_datetime(customers["registration_date"]) + pd.to_timedelta(
        np.random.default_rng(1).integers(0, 400, len(customers)), unit="D")
    gen_activity = gen_activity.clip(upper=end_ts)
    combined = pd.Series(np.maximum(last_deal.fillna(gen_activity).to_numpy("datetime64[ns]"), gen_activity.to_numpy("datetime64[ns]")),
                         index=customers.index)
    recency = ((end_ts - combined).dt.days / 365.25).clip(lower=0)
    out = customers.copy()
    out["number_of_past_purchases"] = n_deals.to_numpy()
    out["last_activity_date"] = combined.dt.date
    out["loyalty_score"] = np.round(np.clip(30 + 13 * n_deals - 7 * recency, 0, 100), 2)
    out["churn_risk_score"] = np.round(np.clip(0.6 * customers["churn_risk_score"].astype(float).to_numpy() + 0.14 * recency - 0.04 * n_deals + 0.05, 0, 1), 3)
    return out


def _fill_dealer_targets(dealers, sales, end):
    cutoff = pd.Timestamp(end) - pd.DateOffset(months=12)
    last12 = sales.loc[pd.to_datetime(sales["sale_date"]) >= cutoff].groupby("dealer_id")["units_sold"].sum()
    dealers["annual_target_units"] = dealers["dealer_id"].map(
        {d: int(round(max(float(last12.get(d, 0.0)) * 1.05, 180.0) / 25.0) * 25) for d in dealers["dealer_id"]})
    return dealers


def generate_dataset(out_dir, seed=42, n_customers=70000, n_sales=100000, n_rooftops=24, n_trims=2):
    rng = np.random.default_rng(seed)
    os.makedirs(out_dir, exist_ok=True)
    vehicles = build_vehicle_catalog(rng, n_trims)
    dealers = build_dealers(rng, n_rooftops)
    customers = build_customers(rng, n_customers, START, END)
    external = build_external_factors(rng)
    sales = build_sales(rng, n_sales, vehicles, dealers, customers, START, END)
    customers = _derive_customer_history(customers, sales, END)
    dealers = _fill_dealer_targets(dealers, sales, END)
    inventory = build_inventory(rng, vehicles, dealers, sales)
    vehicles = vehicles.rename(columns={"_residual_36mo": "residual_value_36mo"})
    tables = {"vehicles": vehicles, "dealers": dealers, "customers": customers, "external_factors": external,
              "sales": sales, "inventory": inventory}
    for name, df in tables.items():
        df.to_csv(os.path.join(out_dir, f"{name}.csv"), index=False)
    print(f"[{out_dir}] " + " ".join(f"{k}={len(v)}" for k, v in tables.items()))
    return tables


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sales", type=int, default=100000)
    ap.add_argument("--customers", type=int, default=70000)
    a = ap.parse_args()
    generate_dataset(a.out, seed=a.seed, n_customers=a.customers, n_sales=a.sales)
