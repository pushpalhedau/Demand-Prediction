"""
Generate synthetic North America (US, 8-state) automobile demand datasets.

Replaces the old UAE-modeled CSVs in automobile_datasets/ and realdata-datasets/
with data in the new NA schema (see database/models.py). All row generation is
seeded (numpy default_rng) for reproducibility.

Real-world anchors baked into the external-factor time series (for narrative/
demo authenticity, not precise historical accuracy):
  - Fed funds rate path 2019-2026 (COVID cut, 2022-23 hiking cycle, 2024-25 cuts)
  - US regular gasoline price path (2020 COVID crash, 2022 Russia/Ukraine spike)
  - WTI crude oil price path
  - CPI inflation path (2022 peak ~9.1%)
  - Unemployment path (2020 COVID spike to ~14.7%)
  - Section 232 auto tariffs: 0% -> 25% step change in April 2025
  - Federal EV tax credit ($7,500): active through Sept 2025, expires Oct 2025
    (modeled as an EV-share growth deceleration after that date)

Run: python -m preprocessing.generate_na_data
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ─────────────────────────────────────────────────────────────────────────────
# Geography: 8-state NA market model
# ─────────────────────────────────────────────────────────────────────────────
STATES = [
    {"name": "California", "weight": 21, "sales_tax": 7.25, "ev_index": 1.00, "pop_m": 39.0,
     "cities": [("Los Angeles", 34.0522, -118.2437), ("San Francisco", 37.7749, -122.4194),
                ("San Diego", 32.7157, -117.1611), ("Sacramento", 38.5816, -121.4944)]},
    {"name": "Texas", "weight": 18, "sales_tax": 6.25, "ev_index": 0.55, "pop_m": 30.5,
     "cities": [("Houston", 29.7604, -95.3698), ("Dallas", 32.7767, -96.7970),
                ("Austin", 30.2672, -97.7431), ("San Antonio", 29.4241, -98.4936)]},
    {"name": "Florida", "weight": 15, "sales_tax": 6.00, "ev_index": 0.50, "pop_m": 22.6,
     "cities": [("Miami", 25.7617, -80.1918), ("Orlando", 28.5383, -81.3792),
                ("Tampa", 27.9506, -82.4572), ("Jacksonville", 30.3322, -81.6557)]},
    {"name": "New York", "weight": 11, "sales_tax": 4.00, "ev_index": 0.70, "pop_m": 19.6,
     "cities": [("New York City", 40.7128, -74.0060), ("Buffalo", 42.8864, -78.8784),
                ("Albany", 42.6526, -73.7562), ("Rochester", 43.1566, -77.6088)]},
    {"name": "Illinois", "weight": 9, "sales_tax": 6.25, "ev_index": 0.45, "pop_m": 12.5,
     "cities": [("Chicago", 41.8781, -87.6298), ("Naperville", 41.7508, -88.1535),
                ("Springfield", 39.7817, -89.6501)]},
    {"name": "Georgia", "weight": 9, "sales_tax": 4.00, "ev_index": 0.40, "pop_m": 11.0,
     "cities": [("Atlanta", 33.7490, -84.3880), ("Savannah", 32.0809, -81.0912),
                ("Augusta", 33.4735, -82.0105)]},
    {"name": "Ohio", "weight": 9, "sales_tax": 5.75, "ev_index": 0.30, "pop_m": 11.8,
     "cities": [("Columbus", 39.9612, -82.9988), ("Cleveland", 41.4993, -81.6944),
                ("Cincinnati", 39.1031, -84.5120)]},
    {"name": "Michigan", "weight": 8, "sales_tax": 6.00, "ev_index": 0.35, "pop_m": 10.0,
     "cities": [("Detroit", 42.3314, -83.0458), ("Grand Rapids", 42.9634, -85.6681),
                ("Ann Arbor", 42.2808, -83.7430)]},
]
STATE_NAMES = [s["name"] for s in STATES]
STATE_WEIGHTS = np.array([s["weight"] for s in STATES], dtype=float)
STATE_WEIGHTS = STATE_WEIGHTS / STATE_WEIGHTS.sum()

# ─────────────────────────────────────────────────────────────────────────────
# Vehicle catalog: brand -> (share%, [(model, category, fuel_type, base_price)])
# ─────────────────────────────────────────────────────────────────────────────
BRAND_CATALOG = {
    "Toyota": (15, [
        ("RAV4", "SUV", "Gasoline", 32000), ("Camry", "Sedan", "Gasoline", 27000),
        ("Corolla", "Sedan", "Gasoline", 23000), ("Highlander", "SUV", "Gasoline", 40000),
        ("Tacoma", "Pickup", "Gasoline", 35000), ("Prius", "Hatchback", "Hybrid", 28000),
        ("bZ4X", "SUV", "Electric", 45000),
    ]),
    "Ford": (13, [
        ("F-150", "Pickup", "Gasoline", 45000), ("Explorer", "SUV", "Gasoline", 39000),
        ("Escape", "SUV", "Gasoline", 29000), ("Mustang", "Coupe", "Gasoline", 32000),
        ("Edge", "SUV", "Gasoline", 38000), ("Bronco", "SUV", "Gasoline", 42000),
        ("Mustang Mach-E", "SUV", "Electric", 48000),
    ]),
    "Chevrolet": (12, [
        ("Silverado", "Pickup", "Gasoline", 42000), ("Equinox", "SUV", "Gasoline", 29000),
        ("Malibu", "Sedan", "Gasoline", 25000), ("Traverse", "SUV", "Gasoline", 37000),
        ("Tahoe", "SUV", "Gasoline", 55000), ("Bolt EV", "Hatchback", "Electric", 29000),
    ]),
    "Honda": (9, [
        ("CR-V", "SUV", "Gasoline", 30000), ("Civic", "Sedan", "Gasoline", 24000),
        ("Accord", "Sedan", "Gasoline", 28000), ("Pilot", "SUV", "Gasoline", 40000),
        ("HR-V", "SUV", "Gasoline", 26000), ("Odyssey", "Minivan", "Gasoline", 36000),
    ]),
    "Nissan": (7, [
        ("Rogue", "SUV", "Gasoline", 29000), ("Altima", "Sedan", "Gasoline", 26000),
        ("Sentra", "Sedan", "Gasoline", 21000), ("Pathfinder", "SUV", "Gasoline", 38000),
        ("Frontier", "Pickup", "Gasoline", 32000), ("Ariya", "SUV", "Electric", 44000),
    ]),
    "Jeep": (6, [
        ("Grand Cherokee", "SUV", "Gasoline", 40000), ("Wrangler", "SUV", "Gasoline", 38000),
        ("Compass", "SUV", "Gasoline", 28000), ("Cherokee", "SUV", "Gasoline", 30000),
    ]),
    "Hyundai": (6, [
        ("Tucson", "SUV", "Gasoline", 29000), ("Elantra", "Sedan", "Gasoline", 22000),
        ("Santa Fe", "SUV", "Gasoline", 33000), ("Sonata", "Sedan", "Gasoline", 26000),
        ("Ioniq 5", "SUV", "Electric", 44000),
    ]),
    "Kia": (5, [
        ("Sportage", "SUV", "Gasoline", 28000), ("Forte", "Sedan", "Gasoline", 21000),
        ("Telluride", "SUV", "Gasoline", 38000), ("Carnival", "Minivan", "Gasoline", 34000),
        ("EV6", "SUV", "Electric", 44000),
    ]),
    "Ram": (5, [("1500", "Pickup", "Gasoline", 44000), ("2500", "Pickup", "Diesel", 56000)]),
    "GMC": (4, [
        ("Sierra", "Pickup", "Gasoline", 43000), ("Terrain", "SUV", "Gasoline", 31000),
        ("Yukon", "SUV", "Gasoline", 56000),
    ]),
    "Subaru": (4, [
        ("Outback", "SUV", "Gasoline", 30000), ("Forester", "SUV", "Gasoline", 28000),
        ("Crosstrek", "SUV", "Gasoline", 25000),
    ]),
    "BMW": (3, [
        ("X5", "Luxury", "Gasoline", 65000), ("3 Series", "Luxury", "Gasoline", 45000),
        ("X3", "Luxury", "Gasoline", 47000),
    ]),
    "Mercedes-Benz": (3, [
        ("C-Class", "Luxury", "Gasoline", 45000), ("GLC", "Luxury", "Gasoline", 48000),
        ("E-Class", "Luxury", "Gasoline", 58000),
    ]),
    "Tesla": (4, [
        ("Model Y", "SUV", "Electric", 47000), ("Model 3", "Sedan", "Electric", 40000),
        ("Model S", "Luxury", "Electric", 75000), ("Model X", "Luxury", "Electric", 80000),
    ]),
    "Volkswagen": (2, [
        ("Tiguan", "SUV", "Gasoline", 28000), ("Jetta", "Sedan", "Gasoline", 22000),
        ("Atlas", "SUV", "Gasoline", 36000),
    ]),
    "Lexus": (2, [
        ("RX", "Luxury", "Gasoline", 48000), ("ES", "Luxury", "Gasoline", 42000),
        ("NX", "Luxury", "Gasoline", 40000),
    ]),
}
IMPORT_BRANDS = {"Toyota", "Honda", "Nissan", "Subaru", "Lexus", "Hyundai", "Kia", "BMW", "Mercedes-Benz", "Volkswagen"}
BRAND_NAMES = list(BRAND_CATALOG.keys())
BRAND_WEIGHTS = np.array([BRAND_CATALOG[b][0] for b in BRAND_NAMES], dtype=float)
BRAND_WEIGHTS = BRAND_WEIGHTS / BRAND_WEIGHTS.sum()

IMPORT_PORTS = ["Port of Long Beach", "Port of Baltimore", "Port of Jacksonville", "Port of Brunswick"]

# ─────────────────────────────────────────────────────────────────────────────
# Time range: Jan 2019 - Aug 2026 (92 months)
# ─────────────────────────────────────────────────────────────────────────────
START = date(2019, 1, 1)
END = date(2026, 8, 21)
MONTHS = pd.date_range(START, END, freq="MS")
N_MONTHS = len(MONTHS)


def _month_index(y, m):
    return (y - 2019) * 12 + (m - 1)


def _interp_series(anchors):
    """anchors: list of (year, month, value) -> array of length N_MONTHS via linear interp."""
    xs = np.array([_month_index(y, m) for y, m, _ in anchors])
    ys = np.array([v for _, _, v in anchors])
    all_x = np.arange(N_MONTHS)
    return np.interp(all_x, xs, ys)


# Real-anchored macro series (approximate, for narrative authenticity)
FED_RATE = _interp_series([
    (2019, 1, 2.4), (2019, 12, 1.75), (2020, 3, 0.25), (2021, 12, 0.25),
    (2022, 3, 0.5), (2022, 12, 4.5), (2023, 7, 5.5), (2024, 8, 5.5),
    (2024, 12, 4.5), (2025, 6, 4.0), (2025, 12, 3.75), (2026, 8, 3.5),
])
GAS_REGULAR = _interp_series([
    (2019, 1, 2.25), (2019, 12, 2.58), (2020, 4, 1.87), (2020, 12, 2.25),
    (2021, 12, 3.28), (2022, 6, 5.00), (2022, 12, 3.20), (2023, 12, 3.10),
    (2024, 12, 3.05), (2025, 12, 3.05), (2026, 8, 3.15),
])
WTI_CRUDE = _interp_series([
    (2019, 1, 50), (2019, 12, 60), (2020, 4, 20), (2020, 12, 48),
    (2021, 12, 75), (2022, 6, 110), (2022, 12, 80), (2023, 12, 72),
    (2024, 12, 70), (2025, 12, 65), (2026, 8, 68),
])
CPI_INFLATION = _interp_series([
    (2019, 1, 1.6), (2019, 12, 2.3), (2020, 12, 1.4), (2021, 12, 7.0),
    (2022, 6, 9.1), (2022, 12, 6.5), (2023, 12, 3.4), (2024, 12, 2.9),
    (2025, 12, 2.7), (2026, 8, 2.5),
])
UNEMPLOYMENT = _interp_series([
    (2019, 1, 4.0), (2019, 12, 3.6), (2020, 4, 14.7), (2020, 12, 6.7),
    (2021, 12, 3.9), (2022, 12, 3.5), (2023, 12, 3.7), (2024, 12, 4.1),
    (2025, 12, 4.2), (2026, 8, 4.1),
])
GDP_GROWTH = _interp_series([
    (2019, 1, 2.5), (2019, 12, 2.5), (2020, 6, -5.0), (2020, 12, -2.2),
    (2021, 12, 5.8), (2022, 12, 1.9), (2023, 12, 2.5), (2024, 12, 2.8),
    (2025, 12, 2.0), (2026, 8, 1.8),
])
CONSUMER_CONF = _interp_series([
    (2019, 1, 121), (2019, 12, 126), (2020, 4, 85), (2020, 12, 88),
    (2021, 12, 115), (2022, 12, 108), (2023, 12, 110), (2024, 12, 104),
    (2025, 12, 100), (2026, 8, 98),
])
HOME_PRICE_IDX = _interp_series([
    (2019, 1, 100), (2020, 1, 105), (2021, 1, 116), (2022, 1, 135),
    (2023, 1, 142), (2024, 1, 148), (2025, 1, 154), (2026, 8, 160),
])
TOURISM_IDX = _interp_series([
    (2019, 1, 100), (2020, 4, 30), (2021, 6, 55), (2022, 6, 85),
    (2023, 6, 95), (2024, 6, 100), (2025, 6, 103), (2026, 8, 105),
])
LUXURY_DEMAND_IDX = _interp_series([
    (2019, 1, 95), (2020, 6, 70), (2021, 12, 105), (2022, 12, 100),
    (2023, 12, 98), (2024, 12, 96), (2025, 12, 94), (2026, 8, 93),
])
EV_STATIONS_NATIONAL = _interp_series([
    (2019, 1, 25000), (2020, 12, 43000), (2021, 12, 55000), (2022, 12, 65000),
    (2023, 12, 95000), (2024, 12, 175000), (2025, 12, 230000), (2026, 8, 250000),
])

# Tariff: 0% -> 25% step in April 2025 (Section 232 auto tariffs)
TARIFF_PCT = np.where(np.arange(N_MONTHS) >= _month_index(2025, 4), 25.0, 0.0)

# EV federal tax credit ($7,500): active through Sept 2025, expires Oct 2025
EV_CREDIT_ACTIVE = np.arange(N_MONTHS) < _month_index(2025, 10)

MONTH_OF = np.array([d.month for d in MONTHS])
YEAR_OF = np.array([d.year for d in MONTHS])
HOLIDAY_SEASON = np.where(np.isin(MONTH_OF, [11, 12]), 1, 0)
JULY_4TH = np.where(MONTH_OF == 7, 1, 0)
DETROIT_SHOW = np.where(MONTH_OF == 1, 1, 0)
LA_SHOW = np.where(MONTH_OF == 11, 1, 0)
NEW_MODEL_LAUNCHES = np.where(np.isin(MONTH_OF, [1, 9, 10]), 3, 1)


def build_vehicle_catalog(rng, with_variants=False):
    rows = []
    vid = 1
    for brand, (_share, models) in BRAND_CATALOG.items():
        for model, category, fuel, price in models:
            variants = ["Base"] if not with_variants else ["Base", "Sport", "Limited"]
            for variant in variants:
                vprice = price if variant == "Base" else int(price * (1.12 if variant == "Sport" else 1.22))
                is_ev = fuel == "Electric"
                rows.append({
                    "vehicle_id": f"VH{vid:04d}",
                    "brand": brand, "model": model, "variant": variant, "category": category,
                    "fuel_type": fuel, "price_usd": vprice,
                    "engine_cc": None if is_ev else int(rng.integers(1500, 5500)),
                    "horsepower": int(rng.integers(150, 420)),
                    "mpg": None if is_ev else round(float(rng.uniform(20, 38)), 1),
                    "range_miles": int(rng.integers(220, 330)) if is_ev else None,
                    "seating_capacity": 7 if category in ("SUV", "Minivan") and model not in ("Bolt EV",) else 5,
                    "transmission": "Automatic" if not is_ev else "Single-Speed",
                    "drive_type": rng.choice(["FWD", "AWD", "4WD", "RWD"], p=[0.35, 0.35, 0.15, 0.15]),
                    "body_color_options": int(rng.integers(4, 9)),
                    "safety_rating": int(rng.integers(4, 6)),
                    "launch_year": int(rng.integers(2018, 2025)),
                    "is_active": True,
                    "warranty_years": int(rng.choice([3, 5, 8])) if is_ev else int(rng.choice([3, 5])),
                    "service_contract_available": bool(rng.random() < 0.6),
                    "ev_incentive_eligible": bool(is_ev and vprice <= 55000),
                })
                vid += 1
    return pd.DataFrame(rows)


DEALER_TEMPLATES = [
    "{brand} of {city}", "{city} {brand}", "Highline {brand} {city}",
    "{brand} Superstore {city}", "Legacy {brand} of {city}", "Metro {brand} {city}",
    "{city} Auto Group {brand}", "Premier {brand} {city}",
]


def build_dealers(rng, dealers_per_state):
    rows = []
    did = 1
    for st in STATES:
        for _ in range(dealers_per_state):
            brand = rng.choice(BRAND_NAMES, p=BRAND_WEIGHTS)
            city, lat, lon = st["cities"][rng.integers(0, len(st["cities"]))]
            template = rng.choice(DEALER_TEMPLATES)
            name = template.format(brand=brand, city=city)
            tier = rng.choice(["Platinum", "Gold", "Silver"], p=[0.15, 0.45, 0.40])
            rows.append({
                "dealer_id": f"DLR{did:04d}", "dealer_name": name, "brand": brand,
                "state": st["name"], "city": city,
                "address": f"{int(rng.integers(100, 9999))} {rng.choice(['Main St','Auto Plaza Dr','Commerce Way','Highway 1','Market St'])}",
                "zip_code": f"{int(rng.integers(10000, 99999))}",
                "tier": tier,
                "established_year": int(rng.integers(1985, 2016)),
                "monthly_capacity": int(rng.integers(80, 600)),
                "showroom_area_sqft": int(rng.integers(8000, 45000)),
                "service_center": bool(rng.random() < 0.85),
                "ev_charging_station": bool(rng.random() < (0.7 if brand in ("Tesla", "Hyundai", "Kia", "Chevrolet", "Ford", "Nissan") else 0.35)),
                "num_salespeople": int(rng.integers(5, 80)),
                "annual_target_units": int(rng.integers(500, 7000)),
                "performance_score": round(float(rng.uniform(55, 98)), 1),
                "google_rating": round(float(rng.uniform(3.4, 4.9)), 1),
                "latitude": round(lat + rng.uniform(-0.15, 0.15), 5),
                "longitude": round(lon + rng.uniform(-0.15, 0.15), 5),
            })
            did += 1
    return pd.DataFrame(rows)


NATIONALITY_MIX = ["American", "Mexican-American", "Chinese-American", "Indian-American",
                    "Filipino-American", "Vietnamese-American", "Other/Mixed"]
NATIONALITY_P = [0.68, 0.11, 0.05, 0.05, 0.04, 0.03, 0.04]
FIRST_NAMES = ["James", "Maria", "Michael", "Ashley", "David", "Jennifer", "Robert", "Linda",
               "William", "Elizabeth", "Carlos", "Emily", "Daniel", "Jessica", "Kevin", "Sarah",
               "Brian", "Amanda", "Steven", "Melissa", "Wei", "Priya", "Juan", "Sophia", "Ryan", "Nicole"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Garcia", "Martinez", "Davis", "Rodriguez",
              "Wilson", "Anderson", "Taylor", "Thomas", "Moore", "Martin", "Lee", "Perez",
              "Thompson", "White", "Harris", "Clark", "Lewis", "Robinson", "Walker", "Young"]
OCCUPATIONS = ["Salaried", "Self-Employed", "Business Owner", "Retired", "Government Employee", "Contract Worker"]
INCOME_BRACKETS = ["<40K", "40K-80K", "80K-120K", "120K-200K", ">200K"]


def build_customers(rng, n, start, end):
    idx = np.arange(1, n + 1)
    customer_id = [f"CUS{i:06d}" for i in idx]
    first = rng.choice(FIRST_NAMES, size=n)
    last = rng.choice(LAST_NAMES, size=n)
    name = [f"{f} {l}" for f, l in zip(first, last)]
    age = np.clip(rng.normal(43, 13, n), 18, 80).astype(int)
    gender = rng.choice(["Male", "Female", "Other"], size=n, p=[0.48, 0.48, 0.04])
    nationality = rng.choice(NATIONALITY_MIX, size=n, p=NATIONALITY_P)

    state_idx = rng.choice(len(STATES), size=n, p=STATE_WEIGHTS)
    state = [STATES[i]["name"] for i in state_idx]
    city = [STATES[i]["cities"][rng.integers(0, len(STATES[i]["cities"]))][0] for i in state_idx]

    occupation = rng.choice(OCCUPATIONS, size=n)
    income_bracket_idx = np.clip(rng.normal(1.6, 1.0, n), 0, 4).astype(int)
    income_bracket = [INCOME_BRACKETS[i] for i in income_bracket_idx]
    bracket_mid = {0: 32000, 1: 60000, 2: 100000, 3: 160000, 4: 260000}
    estimated_income = np.array([bracket_mid[i] * rng.uniform(0.85, 1.15) for i in income_bracket_idx])

    credit_score = np.clip(rng.normal(690, 75, n), 300, 850).astype(int)
    years_at_address = np.clip(rng.exponential(5, n), 0, 30).astype(int)
    number_of_past_purchases = rng.poisson(1.1, n)
    preferred_fuel = rng.choice(["Gasoline", "Hybrid", "Electric", "Diesel"], size=n, p=[0.62, 0.16, 0.18, 0.04])
    preferred_category = rng.choice(["SUV", "Sedan", "Pickup", "Hatchback", "Minivan", "Luxury", "Coupe"], size=n,
                                     p=[0.38, 0.20, 0.18, 0.06, 0.05, 0.09, 0.04])
    loyalty_score = np.clip(rng.normal(50, 22, n), 0, 100)
    marketing_response = np.clip(rng.normal(5, 2.2, n), 0, 10)
    lead_source = rng.choice(["Online Ad", "Referral", "Dealer Walk-in", "Search Engine", "Social Media", "Email Campaign"], size=n)
    email_opt_in = rng.random(n) < 0.62
    test_drive_taken = rng.random(n) < 0.55
    emi_preferred = rng.random(n) < 0.42
    down_payment_capacity = np.clip(estimated_income * rng.uniform(0.03, 0.12, n), 500, None).astype(int)

    days_range = (end - start).days
    reg_offset = rng.integers(0, days_range, n)
    registration_date = [start + pd.Timedelta(days=int(o)) for o in reg_offset]
    activity_offset = [rng.integers(0, max((end - rd).days, 1)) for rd in registration_date]
    last_activity_date = [rd + pd.Timedelta(days=int(o)) for rd, o in zip(registration_date, activity_offset)]
    churn_risk = np.clip(rng.beta(2, 5, n), 0, 1)

    return pd.DataFrame({
        "customer_id": customer_id, "name": name, "age": age, "gender": gender, "nationality": nationality,
        "state": state, "city": city, "occupation": occupation, "income_bracket": income_bracket,
        "estimated_annual_income_usd": estimated_income.round(2), "credit_score": credit_score,
        "years_at_address": years_at_address, "number_of_past_purchases": number_of_past_purchases,
        "preferred_fuel_type": preferred_fuel, "preferred_vehicle_category": preferred_category,
        "customer_segment": "Unclassified", "loyalty_score": loyalty_score.round(2),
        "marketing_response_score": marketing_response.round(2), "lead_source": lead_source,
        "email_opt_in": email_opt_in, "test_drive_taken": test_drive_taken, "emi_preferred": emi_preferred,
        "down_payment_capacity_usd": down_payment_capacity,
        "registration_date": registration_date,
        "last_activity_date": last_activity_date,
        "churn_risk_score": churn_risk.round(3),
    })


def build_external_factors(rng):
    rows = []
    for mi in range(N_MONTHS):
        y, m = int(YEAR_OF[mi]), int(MONTH_OF[mi])
        for st in STATES:
            ev_stations = int(EV_STATIONS_NATIONAL[mi] * st["ev_index"] * (st["weight"] / 100) * 8)
            rows.append({
                "date": date(y, m, 1), "year": y, "month": m, "quarter": f"Q{(m - 1) // 3 + 1}",
                "state": st["name"],
                "gasoline_regular_usd_per_gallon": round(float(GAS_REGULAR[mi] + rng.uniform(-0.08, 0.08)), 3),
                "gasoline_premium_usd_per_gallon": round(float(GAS_REGULAR[mi] * 1.18 + rng.uniform(-0.08, 0.08)), 3),
                "diesel_usd_per_gallon": round(float(GAS_REGULAR[mi] * 1.12 + rng.uniform(-0.08, 0.08)), 3),
                "wti_crude_price_usd": round(float(WTI_CRUDE[mi] + rng.uniform(-2, 2)), 2),
                "gdp_growth_pct": round(float(GDP_GROWTH[mi] + rng.uniform(-0.2, 0.2)), 2),
                "cpi_inflation_pct": round(float(CPI_INFLATION[mi] + rng.uniform(-0.15, 0.15)), 2),
                "us_fed_rate_pct": round(float(FED_RATE[mi]), 2),
                "consumer_confidence_index": round(float(CONSUMER_CONF[mi] + rng.uniform(-3, 3)), 1),
                "tourism_index": round(float(TOURISM_IDX[mi] + rng.uniform(-3, 3)), 1),
                "home_price_index": round(float(HOME_PRICE_IDX[mi] * (0.85 + st["weight"] / 100) + rng.uniform(-2, 2)), 1),
                "luxury_demand_index": round(float(LUXURY_DEMAND_IDX[mi] + rng.uniform(-3, 3)), 1),
                "holiday_season_month": int(HOLIDAY_SEASON[mi]), "july_4th_month": int(JULY_4TH[mi]),
                "detroit_auto_show_month": int(DETROIT_SHOW[mi]), "la_auto_show_month": int(LA_SHOW[mi]),
                "new_model_launches": int(NEW_MODEL_LAUNCHES[mi]),
                "tariff_pct": float(TARIFF_PCT[mi]), "avg_sales_tax_pct": st["sales_tax"],
                "unemployment_rate_pct": round(float(UNEMPLOYMENT[mi] + rng.uniform(-0.2, 0.2)), 2),
                "population_millions": st["pop_m"],
                "ev_charging_stations": ev_stations,
            })
    return pd.DataFrame(rows)


HOLIDAY_PERIODS = {1: None, 2: "Presidents Day Sale", 5: "Memorial Day Sale", 7: "July 4th Sale",
                    9: "Labor Day Sale", 11: "Black Friday", 12: "Year-End Clearance"}


def build_sales(rng, n, vehicles_df, dealers_df, customers_df, start, end):
    days_range = (end - start).days
    # Monthly volume shape: COVID dip 2020, recovery, mild growth + seasonality
    month_weight = np.ones(N_MONTHS)
    for mi in range(N_MONTHS):
        y = int(YEAR_OF[mi])
        base = {2019: 1.0, 2020: 0.68, 2021: 0.92, 2022: 0.98, 2023: 1.08, 2024: 1.15, 2025: 1.12, 2026: 1.10}[y]
        seasonal = 1.0 + 0.15 * np.sin((MONTH_OF[mi] - 3) / 12 * 2 * np.pi)
        month_weight[mi] = base * seasonal
    month_p = month_weight / month_weight.sum()
    sale_month_idx = rng.choice(N_MONTHS, size=n, p=month_p)
    day_in_month = rng.integers(1, 28, n)
    sale_date = [date(int(YEAR_OF[mi]), int(MONTH_OF[mi]), int(d)) for mi, d in zip(sale_month_idx, day_in_month)]

    brand_choice = rng.choice(BRAND_NAMES, size=n, p=BRAND_WEIGHTS)
    veh_by_brand = {b: vehicles_df[vehicles_df["brand"] == b].reset_index(drop=True) for b in BRAND_NAMES}
    vehicle_rows = []
    for b in brand_choice:
        pool = veh_by_brand[b]
        vehicle_rows.append(pool.iloc[rng.integers(0, len(pool))])
    veh_df_sel = pd.DataFrame(vehicle_rows).reset_index(drop=True)

    state_idx = rng.choice(len(STATES), size=n, p=STATE_WEIGHTS)
    state = [STATES[i]["name"] for i in state_idx]
    city = [STATES[i]["cities"][rng.integers(0, len(STATES[i]["cities"]))][0] for i in state_idx]

    dealer_ids = []
    dealers_by_brand_state = {}
    for b in BRAND_NAMES:
        for st in STATE_NAMES:
            dealers_by_brand_state[(b, st)] = dealers_df[(dealers_df["brand"] == b) & (dealers_df["state"] == st)]
    fallback_dealers = dealers_df
    for b, st in zip(brand_choice, state):
        pool = dealers_by_brand_state.get((b, st))
        if pool is None or len(pool) == 0:
            pool = dealers_df[dealers_df["state"] == st]
        if len(pool) == 0:
            pool = fallback_dealers
        dealer_ids.append(pool.iloc[rng.integers(0, len(pool))]["dealer_id"])

    customer_ids = customers_df["customer_id"].sample(n, replace=True, random_state=int(rng.integers(0, 1e9))).values

    base_price = veh_df_sel["price_usd"].values.astype(float)
    tariff_at_sale = TARIFF_PCT[sale_month_idx]
    is_import = veh_df_sel["brand"].isin(IMPORT_BRANDS).values
    tariff_markup = np.where(is_import, tariff_at_sale / 100.0 * 0.5, 0.0)  # tariff partially passed to sticker price
    base_price = base_price * (1 + tariff_markup)

    discount_pct = np.clip(rng.normal(4.5, 2.5, n), 0, 15)
    selling_price = (base_price * (1 - discount_pct / 100)).round(0)

    tax_rate = np.array([STATES[i]["sales_tax"] for i in state_idx]) / 100.0
    accessories_rev = np.clip(rng.normal(1400, 500, n), 0, None).round(0)
    insurance_rev = np.clip(rng.normal(1200, 450, n), 0, None).round(0)
    extended_warranty = np.where(rng.random(n) < 0.35, np.clip(rng.normal(1600, 400, n), 0, None), 0).round(0)
    total_excl_tax = (selling_price + accessories_rev + insurance_rev + extended_warranty).round(0)
    sales_tax_amount = (selling_price * tax_rate).round(0)
    total_incl_tax = (total_excl_tax + sales_tax_amount).round(0)

    financing_type = rng.choice(["Cash", "Bank Loan", "Dealer Financing", "Lease"], size=n, p=[0.24, 0.38, 0.22, 0.16])
    loan_amount = np.where(financing_type == "Cash", 0, (selling_price * rng.uniform(0.6, 0.95, n)).round(0))

    test_drive_converted = rng.random(n) < 0.62
    lead_to_close_days = rng.integers(1, 60, n)
    salesperson_id = [f"SP{int(x):04d}" for x in rng.integers(1, 400, n)]
    marketing_channel = rng.choice(["Online Ad", "Referral", "Showroom Walk-in", "Search Engine",
                                     "Social Media", "Email Campaign", "TV/Radio"], size=n)
    season_multiplier = np.clip(rng.normal(1.0, 0.08, n), 0.75, 1.35)

    quarter = [f"Q{(int(MONTH_OF[mi]) - 1) // 3 + 1}" for mi in sale_month_idx]
    day_of_week = pd.to_datetime(sale_date).day_name()
    holiday_period = [HOLIDAY_PERIODS.get(int(MONTH_OF[mi])) for mi in sale_month_idx]

    df = pd.DataFrame({
        "sale_id": [f"SAL{i:07d}" for i in range(1, n + 1)],
        "sale_date": sale_date, "year": YEAR_OF[sale_month_idx].astype(int), "month": MONTH_OF[sale_month_idx].astype(int),
        "quarter": quarter, "day_of_week": day_of_week, "holiday_period": holiday_period,
        "customer_id": customer_ids, "dealer_id": dealer_ids, "vehicle_id": veh_df_sel["vehicle_id"].values,
        "brand": veh_df_sel["brand"].values, "model": veh_df_sel["model"].values,
        "vehicle_category": veh_df_sel["category"].values, "fuel_type": veh_df_sel["fuel_type"].values,
        "state": state, "city": city,
        "base_price_usd": base_price.round(0).astype(int), "discount_pct": discount_pct.round(2),
        "selling_price_usd": selling_price.astype(int), "sales_tax_amount_usd": sales_tax_amount.astype(int),
        "accessories_revenue_usd": accessories_rev.astype(int), "insurance_revenue_usd": insurance_rev.astype(int),
        "extended_warranty_usd": extended_warranty.astype(int), "total_revenue_excl_tax": total_excl_tax.astype(int),
        "total_revenue_incl_tax": total_incl_tax.astype(int), "financing_type": financing_type,
        "loan_amount_usd": loan_amount.astype(int), "units_sold": 1, "test_drive_converted": test_drive_converted,
        "lead_to_close_days": lead_to_close_days, "salesperson_id": salesperson_id,
        "marketing_channel": marketing_channel, "season_multiplier": season_multiplier.round(3),
    })
    return df


WAREHOUSE_ZONES = ["Zone A", "Zone B", "Zone C", "Zone D"]


def build_inventory(rng, n, vehicles_df, dealers_df, start, end):
    days_range = (end - start).days
    dealer_sel = dealers_df.sample(n, replace=True, random_state=int(rng.integers(0, 1e9))).reset_index(drop=True)
    veh_by_brand = {b: vehicles_df[vehicles_df["brand"] == b].reset_index(drop=True) for b in BRAND_NAMES}
    vehicle_rows = []
    for b in dealer_sel["brand"]:
        pool = veh_by_brand[b]
        vehicle_rows.append(pool.iloc[rng.integers(0, len(pool))])
    veh_sel = pd.DataFrame(vehicle_rows).reset_index(drop=True)

    record_offset = rng.integers(0, days_range, n)
    record_date = [start + pd.Timedelta(days=int(o)) for o in record_offset]

    current_stock = rng.integers(0, 120, n)
    demand_forecast = np.clip((current_stock * rng.uniform(0.6, 1.3, n)), 0, None).astype(int)
    reorder_point = (current_stock.astype(float) * rng.uniform(0.2, 0.4, n)).astype(int)
    days_in_stock = rng.integers(1, 90, n)
    stockout_flag = current_stock == 0
    overstock_flag = current_stock > (reorder_point * 4)
    reorder_needed = current_stock <= reorder_point
    stockout_risk = np.clip(rng.beta(2, 6, n), 0, 1)
    overstock_risk = np.clip(rng.beta(2, 6, n), 0, 1)
    holding_cost_per_day = np.clip(rng.normal(18, 6, n), 3, None)
    estimated_holding_cost = (holding_cost_per_day * days_in_stock).round(2)
    units_sold_30d = rng.integers(0, 60, n)
    units_ordered = rng.integers(0, 40, n)
    transit_stock = rng.integers(0, 25, n)
    warehouse_zone = rng.choice(WAREHOUSE_ZONES, size=n)
    is_import = veh_sel["brand"].isin(IMPORT_BRANDS).values
    port_of_entry = np.where(is_import, rng.choice(IMPORT_PORTS, size=n), "N/A (Domestic)")
    customs_cleared = np.where(is_import, rng.random(n) < 0.96, True)
    last_replenishment = [rd - pd.Timedelta(days=int(rng.integers(1, 45))) for rd in record_date]
    supplier_lead_time = rng.integers(3, 60, n)

    return pd.DataFrame({
        "inventory_id": [f"INV{i:07d}" for i in range(1, n + 1)],
        "record_date": [d.date() if hasattr(d, "date") else d for d in record_date],
        "dealer_id": dealer_sel["dealer_id"].values, "vehicle_id": veh_sel["vehicle_id"].values,
        "brand": veh_sel["brand"].values, "model": veh_sel["model"].values,
        "vehicle_category": veh_sel["category"].values, "fuel_type": veh_sel["fuel_type"].values,
        "state": dealer_sel["state"].values, "city": dealer_sel["city"].values,
        "current_stock": current_stock, "demand_forecast_30d": demand_forecast,
        "reorder_point": reorder_point, "days_in_stock": days_in_stock,
        "stockout_flag": stockout_flag, "overstock_flag": overstock_flag, "reorder_needed": reorder_needed,
        "stockout_risk_score": stockout_risk.round(3), "overstock_risk_score": overstock_risk.round(3),
        "holding_cost_per_day_usd": holding_cost_per_day.round(2), "estimated_holding_cost_usd": estimated_holding_cost,
        "units_sold_last_30d": units_sold_30d, "units_ordered": units_ordered, "transit_stock": transit_stock,
        "port_of_entry": port_of_entry, "warehouse_zone": warehouse_zone,
        "last_replenishment_date": [d.date() if hasattr(d, "date") else d for d in last_replenishment],
        "supplier_lead_time_days": supplier_lead_time, "customs_cleared": customs_cleared,
    })


def generate_dataset(out_dir, seed, n_customers, dealers_per_state, n_sales, n_inventory, with_variants):
    rng = np.random.default_rng(seed)
    os.makedirs(out_dir, exist_ok=True)

    vehicles = build_vehicle_catalog(rng, with_variants=with_variants)
    dealers = build_dealers(rng, dealers_per_state)
    customers = build_customers(rng, n_customers, START, END)
    external_factors = build_external_factors(rng)
    sales = build_sales(rng, n_sales, vehicles, dealers, customers, START, END)
    inventory = build_inventory(rng, n_inventory, vehicles, dealers, START, END)

    vehicles.to_csv(os.path.join(out_dir, "vehicles.csv"), index=False)
    dealers.to_csv(os.path.join(out_dir, "dealers.csv"), index=False)
    customers.to_csv(os.path.join(out_dir, "customers.csv"), index=False)
    external_factors.to_csv(os.path.join(out_dir, "external_factors.csv"), index=False)
    sales.to_csv(os.path.join(out_dir, "sales.csv"), index=False)
    inventory.to_csv(os.path.join(out_dir, "inventory.csv"), index=False)

    print(f"[{out_dir}] vehicles={len(vehicles)} dealers={len(dealers)} customers={len(customers)} "
          f"external_factors={len(external_factors)} sales={len(sales)} inventory={len(inventory)}")


def main():
    # realdata-datasets: primary "real" mode dataset
    generate_dataset(
        os.path.join(ROOT, "realdata-datasets"), seed=42,
        n_customers=42000, dealers_per_state=6, n_sales=100000, n_inventory=16000,
        with_variants=False,
    )
    # automobile_datasets: larger "test" mode dataset
    generate_dataset(
        os.path.join(ROOT, "automobile_datasets"), seed=7,
        n_customers=56000, dealers_per_state=15, n_sales=140000, n_inventory=26000,
        with_variants=True,
    )


if __name__ == "__main__":
    main()
