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
# Vehicle catalog — real US-market model specs
#
# Each model carries its actual published specification rather than a random
# draw, because the Placement Assistant matches substitutes on these attributes
# (a shopper cross-shops a RAV4 against a CR-V because the specs genuinely line
# up, not because a random number generator put them near each other).
#
# Tuple layout:
#   (model, category, fuel, base_msrp, hp, engine_cc, mpg_combined,
#    range_miles, seats, drive_type, residual_36mo, model_year_intro)
#
# residual_36mo = share of MSRP the vehicle is worth at 36-month lease
# maturity. These follow real ALG / Black Book style residual behaviour:
# body-on-frame trucks and Toyota/Subaru hold value (0.60-0.72), mainstream
# sedans sit mid-pack (0.47-0.58), and luxury sedans and EVs depreciate hardest
# (0.38-0.50). This single column drives the entire lease-return equity model.
# ─────────────────────────────────────────────────────────────────────────────
BRAND_CATALOG = {
    "Toyota": (15, [
        ("RAV4",        "SUV",       "Gasoline", 29000, 203, 2487, 30,  None, 5, "AWD", 0.62, 2019),
        ("Camry",       "Sedan",     "Gasoline", 28400, 225, 2487, 32,  None, 5, "FWD", 0.57, 2018),
        ("Corolla",     "Sedan",     "Gasoline", 22300, 169, 1987, 35,  None, 5, "FWD", 0.58, 2020),
        ("Highlander",  "SUV",       "Gasoline", 39500, 265, 2393, 24,  None, 8, "AWD", 0.60, 2020),
        ("Tacoma",      "Pickup",    "Gasoline", 32000, 278, 2393, 21,  None, 5, "4WD", 0.72, 2024),
        ("Tundra",      "Pickup",    "Gasoline", 41000, 389, 3445, 20,  None, 5, "4WD", 0.65, 2022),
        ("4Runner",     "SUV",       "Gasoline", 42000, 278, 2393, 21,  None, 7, "4WD", 0.70, 2025),
        ("Prius",       "Hatchback", "Hybrid",   28350, 194, 1987, 57,  None, 5, "FWD", 0.60, 2023),
        ("Sienna",      "Minivan",   "Hybrid",   39000, 245, 2487, 36,  None, 8, "FWD", 0.61, 2021),
        ("bZ4X",        "SUV",       "Electric", 37000, 214, None, None, 252, 5, "FWD", 0.42, 2023),
    ]),
    "Ford": (13, [
        ("F-150",          "Pickup", "Gasoline", 38000, 400, 3500, 20,  None, 5, "4WD", 0.60, 2021),
        ("Explorer",       "SUV",    "Gasoline", 38500, 300, 2264, 24,  None, 7, "AWD", 0.55, 2020),
        ("Escape",         "SUV",    "Gasoline", 29500, 180, 1497, 30,  None, 5, "FWD", 0.53, 2020),
        ("Mustang",        "Coupe",  "Gasoline", 32000, 315, 2264, 25,  None, 4, "RWD", 0.58, 2024),
        ("Bronco",         "SUV",    "Gasoline", 39000, 300, 2264, 20,  None, 5, "4WD", 0.70, 2021),
        ("Ranger",         "Pickup", "Gasoline", 33000, 270, 2264, 22,  None, 5, "4WD", 0.62, 2024),
        ("Expedition",     "SUV",    "Gasoline", 58000, 400, 3500, 19,  None, 8, "4WD", 0.58, 2022),
        ("Maverick",       "Pickup", "Hybrid",   26000, 191, 2500, 37,  None, 5, "FWD", 0.72, 2022),
        ("Mustang Mach-E", "SUV",    "Electric", 43000, 266, None, None, 250, 5, "RWD", 0.44, 2021),
    ]),
    "Chevrolet": (12, [
        ("Silverado", "Pickup",    "Gasoline", 37000, 355, 5300, 19,  None, 5, "4WD", 0.57, 2019),
        ("Equinox",   "SUV",       "Gasoline", 28500, 175, 1500, 28,  None, 5, "FWD", 0.52, 2022),
        ("Malibu",    "Sedan",     "Gasoline", 26000, 160, 1500, 32,  None, 5, "FWD", 0.48, 2019),
        ("Traverse",  "SUV",       "Gasoline", 38000, 328, 2700, 22,  None, 8, "AWD", 0.54, 2024),
        ("Tahoe",     "SUV",       "Gasoline", 58000, 355, 5300, 18,  None, 8, "4WD", 0.60, 2021),
        ("Colorado",  "Pickup",    "Gasoline", 31000, 237, 2700, 20,  None, 5, "4WD", 0.58, 2023),
        ("Blazer",    "SUV",       "Gasoline", 36000, 228, 2000, 25,  None, 5, "AWD", 0.52, 2019),
        ("Bolt EUV",  "Hatchback", "Electric", 28000, 200, None, None, 247, 5, "FWD", 0.40, 2022),
    ]),
    "Honda": (9, [
        ("CR-V",      "SUV",     "Gasoline", 30000, 190, 1498, 30, None, 5, "AWD", 0.63, 2023),
        ("Civic",     "Sedan",   "Gasoline", 24500, 158, 1996, 36, None, 5, "FWD", 0.62, 2022),
        ("Accord",    "Sedan",   "Gasoline", 28000, 192, 1498, 32, None, 5, "FWD", 0.58, 2023),
        ("Pilot",     "SUV",     "Gasoline", 40000, 285, 3500, 22, None, 8, "AWD", 0.60, 2023),
        ("HR-V",      "SUV",     "Gasoline", 26500, 158, 1996, 28, None, 5, "AWD", 0.58, 2023),
        ("Passport",  "SUV",     "Gasoline", 42000, 280, 3500, 21, None, 5, "AWD", 0.56, 2022),
        ("Ridgeline", "Pickup",  "Gasoline", 40000, 280, 3500, 21, None, 5, "AWD", 0.60, 2021),
        ("Odyssey",   "Minivan", "Gasoline", 38500, 280, 3500, 22, None, 8, "FWD", 0.57, 2021),
    ]),
    "Nissan": (7, [
        ("Rogue",      "SUV",    "Gasoline", 28500, 201, 1497, 31,  None, 5, "AWD", 0.52, 2021),
        ("Altima",     "Sedan",  "Gasoline", 26000, 188, 2488, 32,  None, 5, "FWD", 0.47, 2019),
        ("Sentra",     "Sedan",  "Gasoline", 21500, 149, 1998, 33,  None, 5, "FWD", 0.50, 2020),
        ("Pathfinder", "SUV",    "Gasoline", 37000, 284, 3498, 23,  None, 8, "AWD", 0.52, 2022),
        ("Murano",     "SUV",    "Gasoline", 35500, 260, 3498, 23,  None, 5, "AWD", 0.48, 2025),
        ("Frontier",   "Pickup", "Gasoline", 31000, 310, 3800, 20,  None, 5, "4WD", 0.58, 2022),
        ("Ariya",      "SUV",    "Electric", 40000, 238, None, None, 289, 5, "FWD", 0.40, 2023),
    ]),
    "Jeep": (6, [
        ("Grand Cherokee", "SUV",    "Gasoline", 39000, 293, 3600, 22, None, 5, "4WD", 0.55, 2022),
        ("Wrangler",       "SUV",    "Gasoline", 33000, 285, 3600, 20, None, 5, "4WD", 0.68, 2018),
        ("Compass",        "SUV",    "Gasoline", 27000, 200, 1300, 27, None, 5, "AWD", 0.50, 2022),
        ("Gladiator",      "Pickup", "Gasoline", 39000, 285, 3600, 19, None, 5, "4WD", 0.62, 2020),
        ("Wagoneer",       "SUV",    "Gasoline", 60000, 420, 5700, 18, None, 8, "4WD", 0.52, 2022),
    ]),
    "Hyundai": (6, [
        ("Tucson",   "SUV",   "Gasoline", 28000, 187, 2497, 29,  None, 5, "AWD", 0.55, 2022),
        ("Elantra",  "Sedan", "Gasoline", 22000, 147, 1999, 36,  None, 5, "FWD", 0.52, 2021),
        ("Santa Fe", "SUV",   "Gasoline", 34000, 277, 2497, 25,  None, 7, "AWD", 0.54, 2024),
        ("Sonata",   "Sedan", "Gasoline", 27000, 191, 2497, 31,  None, 5, "FWD", 0.49, 2020),
        ("Palisade", "SUV",   "Gasoline", 38000, 291, 3800, 22,  None, 8, "AWD", 0.57, 2023),
        ("Ioniq 5",  "SUV",   "Electric", 42000, 225, None, None, 303, 5, "RWD", 0.45, 2022),
    ]),
    "Kia": (5, [
        ("Sportage",  "SUV",     "Gasoline", 27500, 187, 2497, 28,  None, 5, "AWD", 0.54, 2023),
        ("Forte",     "Sedan",   "Gasoline", 21000, 147, 1999, 35,  None, 5, "FWD", 0.51, 2022),
        ("Telluride", "SUV",     "Gasoline", 37000, 291, 3800, 23,  None, 8, "AWD", 0.64, 2020),
        ("Sorento",   "SUV",     "Gasoline", 32000, 191, 2497, 26,  None, 7, "AWD", 0.54, 2021),
        ("Carnival",  "Minivan", "Gasoline", 35000, 287, 3500, 22,  None, 8, "FWD", 0.55, 2022),
        ("EV6",       "SUV",     "Electric", 43000, 225, None, None, 310, 5, "RWD", 0.44, 2022),
    ]),
    "Ram": (5, [
        ("1500", "Pickup", "Gasoline", 40000, 395, 5700, 20, None, 5, "4WD", 0.58, 2019),
        ("2500", "Pickup", "Diesel",   55000, 370, 6700, 17, None, 5, "4WD", 0.63, 2019),
    ]),
    "GMC": (4, [
        ("Sierra",  "Pickup", "Gasoline", 40000, 355, 5300, 19, None, 5, "4WD", 0.60, 2019),
        ("Terrain", "SUV",    "Gasoline", 30500, 175, 1500, 28, None, 5, "AWD", 0.51, 2022),
        ("Acadia",  "SUV",    "Gasoline", 38000, 328, 2500, 23, None, 7, "AWD", 0.53, 2024),
        ("Yukon",   "SUV",    "Gasoline", 61000, 355, 5300, 18, None, 8, "4WD", 0.60, 2021),
    ]),
    "Subaru": (4, [
        ("Outback",   "SUV", "Gasoline", 30000, 182, 2498, 28, None, 5, "AWD", 0.60, 2020),
        ("Forester",  "SUV", "Gasoline", 28000, 182, 2498, 29, None, 5, "AWD", 0.61, 2019),
        ("Crosstrek", "SUV", "Gasoline", 25500, 152, 2000, 29, None, 5, "AWD", 0.63, 2024),
        ("Ascent",    "SUV", "Gasoline", 35500, 260, 2400, 23, None, 8, "AWD", 0.55, 2019),
    ]),
    "BMW": (3, [
        ("3 Series", "Luxury", "Gasoline", 45000, 255, 1998, 30,  None, 5, "RWD", 0.50, 2019),
        ("X3",       "Luxury", "Gasoline", 47000, 248, 1998, 27,  None, 5, "AWD", 0.52, 2018),
        ("i4",       "Luxury", "Electric", 53000, 335, None, None, 301, 5, "RWD", 0.42, 2022),
        ("5 Series", "Luxury", "Gasoline", 58000, 375, 2998, 28,  None, 5, "RWD", 0.48, 2024),
        ("X5",       "Luxury", "Gasoline", 66000, 375, 2998, 24,  None, 5, "AWD", 0.53, 2019),
    ]),
    "Mercedes-Benz": (3, [
        ("C-Class", "Luxury", "Gasoline", 47000, 255, 1999, 28,  None, 5, "RWD", 0.49, 2022),
        ("GLC",     "Luxury", "Gasoline", 49000, 255, 1999, 25,  None, 5, "AWD", 0.52, 2023),
        ("E-Class", "Luxury", "Gasoline", 62000, 255, 1999, 27,  None, 5, "AWD", 0.46, 2024),
        ("GLE",     "Luxury", "Gasoline", 63000, 375, 2999, 22,  None, 5, "AWD", 0.50, 2020),
        ("EQE",     "Luxury", "Electric", 75000, 288, None, None, 305, 5, "RWD", 0.38, 2023),
    ]),
    "Tesla": (4, [
        ("Model 3", "Sedan",  "Electric", 39000, 283, None, None, 272, 5, "RWD", 0.47, 2018),
        ("Model Y", "SUV",    "Electric", 45000, 384, None, None, 320, 5, "AWD", 0.48, 2020),
        ("Model S", "Luxury", "Electric", 75000, 670, None, None, 405, 5, "AWD", 0.42, 2021),
        ("Model X", "Luxury", "Electric", 81000, 670, None, None, 335, 7, "AWD", 0.41, 2021),
    ]),
    "Volkswagen": (2, [
        ("Jetta",  "Sedan", "Gasoline", 22000, 158, 1498, 34,  None, 5, "FWD", 0.50, 2022),
        ("Tiguan", "SUV",   "Gasoline", 28500, 184, 1984, 26,  None, 7, "AWD", 0.50, 2022),
        ("Atlas",  "SUV",   "Gasoline", 38000, 269, 1984, 23,  None, 7, "AWD", 0.51, 2021),
        ("ID.4",   "SUV",   "Electric", 40000, 282, None, None, 275, 5, "AWD", 0.40, 2021),
    ]),
    "Lexus": (2, [
        ("ES", "Luxury", "Gasoline", 43000, 203, 2487, 30, None, 5, "FWD", 0.55, 2019),
        ("NX", "Luxury", "Gasoline", 41000, 275, 2393, 27, None, 5, "AWD", 0.57, 2022),
        ("RX", "Luxury", "Gasoline", 49000, 275, 2393, 25, None, 5, "AWD", 0.58, 2023),
        ("GX", "Luxury", "Gasoline", 65000, 349, 3445, 19, None, 7, "4WD", 0.62, 2024),
    ]),
}

# Real trim ladders per brand, cheapest -> most expensive. The Placement
# Assistant surfaces these by name ("the customer wanted a Limited"), so
# generic Base/Sport/Limited labels would read as fake to anyone who sells cars.
BRAND_TRIMS = {
    "Toyota":        ["LE", "XLE", "Limited", "TRD Pro"],
    "Ford":          ["XL", "XLT", "Lariat", "Platinum"],
    "Chevrolet":     ["LS", "LT", "RS", "Premier"],
    "Honda":         ["LX", "Sport", "EX-L", "Touring"],
    "Nissan":        ["S", "SV", "SL", "Platinum"],
    "Jeep":          ["Sport", "Latitude", "Limited", "Trailhawk"],
    "Hyundai":       ["SE", "SEL", "N Line", "Limited"],
    "Kia":           ["LX", "EX", "GT-Line", "SX Prestige"],
    "Ram":           ["Tradesman", "Big Horn", "Laramie", "Limited"],
    "GMC":           ["Elevation", "SLE", "SLT", "Denali"],
    "Subaru":        ["Base", "Premium", "Limited", "Touring"],
    "BMW":           ["sDrive", "xDrive", "M Sport", "M Sport Pro"],
    "Mercedes-Benz": ["Base", "4MATIC", "AMG Line", "AMG Line Premium"],
    "Tesla":         ["RWD", "Long Range", "Performance", "Plaid"],
    "Volkswagen":    ["S", "SE", "SEL", "SEL Premium"],
    "Lexus":         ["Base", "Premium", "F Sport", "Luxury"],
}

# Trim ladder economics: price multiplier, hp uplift, mpg penalty (bigger
# wheels / heavier equipment), applied by position on the ladder.
TRIM_PRICE_MULT = [1.00, 1.09, 1.19, 1.31]
TRIM_HP_MULT = [1.00, 1.00, 1.06, 1.14]
TRIM_MPG_DELTA = [0, -1, -1, -2]

# The Hyundai/Kia 5yr-60k basic warranty is a genuine market differentiator,
# so it is modelled rather than randomised.
BRAND_WARRANTY_YEARS = {"Hyundai": 5, "Kia": 5}

# Real exterior paint names, used by the Placement Assistant so a shopper
# request reads like a real one ("white Grand Cherokee Limited").
PAINT_COLORS = [
    "Super White", "Midnight Black", "Magnetic Gray", "Silver Metallic",
    "Blueprint Blue", "Barcelona Red", "Deep Forest Green", "Ruby Flare Pearl",
]

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


def build_vehicle_catalog(rng, n_trims=2):
    """
    Expand BRAND_CATALOG into one row per (model, trim).

    Specs come from the catalog table rather than random draws, so a Corolla
    cannot end up with 420 hp and an F-150 cannot end up returning 38 mpg.
    Only genuinely variable attributes (paint count, service contract) are
    randomised.
    """
    rows = []
    vid = 1
    for brand, (_share, models) in BRAND_CATALOG.items():
        trims = BRAND_TRIMS[brand][:n_trims]
        for (model, category, fuel, msrp, hp, cc, mpg, rng_mi,
             seats, drive, resid36, intro_year) in models:
            is_ev = fuel == "Electric"
            for ti, trim in enumerate(trims):
                trim_price = int(round(msrp * TRIM_PRICE_MULT[ti] / 100.0) * 100)
                trim_hp = int(round(hp * TRIM_HP_MULT[ti]))
                trim_mpg = None if is_ev else max(12, mpg + TRIM_MPG_DELTA[ti])
                # Higher trims carry bigger wheels and more mass, which costs
                # a little real-world range on an EV.
                trim_range = None if not is_ev else int(round(rng_mi * (1.0 - 0.02 * ti)))
                rows.append({
                    "vehicle_id": f"VH{vid:04d}",
                    "brand": brand,
                    "model": model,
                    "variant": trim,
                    "category": category,
                    "fuel_type": fuel,
                    "price_usd": trim_price,
                    "engine_cc": None if is_ev else cc,
                    "horsepower": trim_hp,
                    "mpg": trim_mpg,
                    "range_miles": trim_range,
                    "seating_capacity": seats,
                    "transmission": "Single-Speed" if is_ev else "Automatic",
                    "drive_type": drive,
                    "body_color_options": int(rng.integers(5, 9)),
                    "safety_rating": 5 if resid36 >= 0.55 else int(rng.choice([4, 5], p=[0.35, 0.65])),
                    "launch_year": intro_year,
                    "is_active": True,
                    "warranty_years": BRAND_WARRANTY_YEARS.get(brand, 3),
                    "service_contract_available": bool(rng.random() < 0.6),
                    # Federal EV credit rules: battery-electric, MSRP cap of
                    # $55k for cars / $80k for SUVs and trucks.
                    "ev_incentive_eligible": bool(
                        is_ev and trim_price <= (80000 if category in ("SUV", "Pickup") else 55000)
                    ),
                    # Not persisted to the DB — carried through generation so
                    # the lease book can price residuals per trim.
                    "_residual_36mo": resid36,
                })
                vid += 1
    return pd.DataFrame(rows)


# Residual curves are quoted at 36 months; shorter terms leave more value on
# the car, longer terms less. Real lease residual tables behave this way.
LEASE_TERM_RESIDUAL_ADJ = {24: +0.10, 36: 0.00, 39: -0.02, 48: -0.10}
LEASE_TERMS = [24, 36, 39, 48]
LEASE_TERM_WEIGHTS = [0.12, 0.62, 0.14, 0.12]
LEASE_ANNUAL_MILES = [10000, 12000, 15000]
LEASE_MILEAGE_WEIGHTS = [0.22, 0.56, 0.22]

# Lease penetration by segment. Real US new-retail behaviour: luxury leases
# around half its volume, pickups roughly a tenth. Blends to ~24% nationally.
LEASE_RATE_BY_CATEGORY = {
    "Luxury": 0.52, "Coupe": 0.28, "Sedan": 0.26, "SUV": 0.24,
    "Hatchback": 0.22, "Minivan": 0.20, "Pickup": 0.11,
}

# Slow-turning segments attract larger over-allowances, because that is where
# the store has to buy the deal to move the unit.
TRADE_OVER_ALLOWANCE_MULT = {
    "Sedan": 1.45, "Hatchback": 1.40, "Coupe": 1.25, "Minivan": 1.15,
    "SUV": 1.00, "Luxury": 1.10, "Pickup": 0.75,
}


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

    # ── Financing mix ────────────────────────────────────────────────────────
    # Lease penetration is segment-driven in the real US market, not uniform:
    # luxury leases around half of all units, pickups barely a tenth. EVs lease
    # heavily because the federal credit was easiest to capture through a lease.
    # Blended, this lands near the ~24% national new-retail lease rate.
    veh_category = veh_df_sel["category"].values
    veh_fuel = veh_df_sel["fuel_type"].values
    lease_p = np.array([LEASE_RATE_BY_CATEGORY.get(c, 0.22) for c in veh_category])
    lease_p = np.clip(lease_p + np.where(veh_fuel == "Electric", 0.15, 0.0), 0.05, 0.75)
    is_lease = rng.random(n) < lease_p
    non_lease = rng.choice(["Cash", "Bank Loan", "Dealer Financing"], size=n, p=[0.30, 0.47, 0.23])
    financing_type = np.where(is_lease, "Lease", non_lease)
    loan_amount = np.where(financing_type == "Cash", 0, (selling_price * rng.uniform(0.6, 0.95, n)).round(0))

    # ── Lease contract terms ─────────────────────────────────────────────────
    msrp = veh_df_sel["price_usd"].values.astype(float)
    lease_term = rng.choice(LEASE_TERMS, size=n, p=LEASE_TERM_WEIGHTS)
    annual_miles = rng.choice(LEASE_ANNUAL_MILES, size=n, p=LEASE_MILEAGE_WEIGHTS)

    # Residual starts from the model's own 36-month curve, then moves with the
    # term and the mileage allowance the way a real residual table does.
    resid_pct = veh_df_sel["_residual_36mo"].values.astype(float)
    resid_pct = resid_pct + np.array([LEASE_TERM_RESIDUAL_ADJ[t] for t in lease_term])
    resid_pct = resid_pct + np.select(
        [annual_miles == 10000, annual_miles == 15000], [0.02, -0.02], default=0.0
    )
    resid_pct = np.clip(resid_pct + rng.normal(0, 0.012, n), 0.25, 0.85)
    residual_usd = (msrp * resid_pct).round(0)

    # Standard lease payment: monthly depreciation plus the rent charge.
    # Money factor tracks the Fed path with a lender spread, so payments climb
    # through the 2022-23 hiking cycle exactly as they did in the market.
    lease_apr = np.clip(FED_RATE[sale_month_idx] + rng.normal(3.2, 0.8, n), 1.0, 12.0)
    money_factor = lease_apr / 2400.0
    lease_payment = ((selling_price - residual_usd) / lease_term
                     + (selling_price + residual_usd) * money_factor).round(0)

    # Exact month arithmetic so the return calendar buckets cleanly by month.
    _sd = pd.to_datetime(sale_date)
    _tot = _sd.year * 12 + (_sd.month - 1) + lease_term
    maturity = pd.to_datetime(dict(year=_tot // 12, month=_tot % 12 + 1,
                                   day=np.minimum(_sd.day, 28)))

    _no_lease = ~is_lease
    lease_term_col = np.where(_no_lease, np.nan, lease_term)
    resid_pct_col = np.where(_no_lease, np.nan, resid_pct.round(4))
    resid_usd_col = np.where(_no_lease, np.nan, residual_usd)
    lease_payment_col = np.where(_no_lease, np.nan, lease_payment)
    mileage_allow_col = np.where(_no_lease, np.nan, annual_miles * lease_term / 12.0)
    maturity_col = pd.Series(maturity).where(is_lease)

    # ── Trade-in activity ────────────────────────────────────────────────────
    # Around half of US new-vehicle deals carry a trade. Cash buyers trade less
    # (often an additional-car purchase); financed buyers trade more.
    trade_base = np.where(financing_type == "Cash", 0.42, 0.58)
    has_trade = rng.random(n) < trade_base

    trade_age = rng.choice([3, 4, 5, 6, 7, 8, 9, 10], size=n,
                           p=[0.13, 0.17, 0.17, 0.15, 0.13, 0.10, 0.08, 0.07])
    trade_year = YEAR_OF[sale_month_idx].astype(int) - trade_age
    trade_mileage = np.clip(
        (trade_age * rng.normal(13500, 2600, n)).round(-2), 8000, 220000
    ).astype(int)

    # Trades are sampled from the same catalog (an older car of the same market)
    trade_pick = rng.integers(0, len(vehicles_df), n)
    trade_brand = vehicles_df["brand"].values[trade_pick]
    trade_model = vehicles_df["model"].values[trade_pick]
    trade_orig_msrp = vehicles_df["price_usd"].values[trade_pick].astype(float)

    # Depreciation: ~20% off in year one, ~12%/yr compounding after. A 5-year-old
    # car lands near 48% of original MSRP, which matches real used-market values.
    dep_factor = 0.80 * np.power(0.88, np.maximum(trade_age - 1, 0))
    expected_miles = np.maximum(trade_age * 13500, 1)
    excess_ratio = (trade_mileage - expected_miles) / expected_miles
    mileage_factor = np.clip(1.0 - 0.20 * excess_ratio, 0.70, 1.20)
    appraised = np.maximum(trade_orig_msrp * dep_factor * mileage_factor, 800).round(0)

    # Over-allowance: the amount credited above appraised value. This is a real
    # discount that never appears in discount_pct, and it runs higher on the
    # slow-turning segments where the store needs help closing.
    over_mult = np.array([TRADE_OVER_ALLOWANCE_MULT.get(c, 1.0) for c in veh_category])
    over_allow = np.maximum(rng.normal(900, 700, n) * over_mult, 0).round(0)
    over_allow = np.where(rng.random(n) < 0.25, 0.0, over_allow)

    # Trade bonus: a promotional incentive, concentrated in the big retail
    # events and on the segments that need the push.
    is_event = np.isin(MONTH_OF[sale_month_idx], [11, 12])
    bonus_p = np.clip(0.18 + 0.22 * is_event + 0.12 * (over_mult > 1.0), 0, 0.75)
    trade_bonus = np.where(
        rng.random(n) < bonus_p,
        rng.choice([500, 750, 1000, 1500, 2000], size=n, p=[0.32, 0.26, 0.22, 0.13, 0.07]),
        0,
    ).astype(float)

    allowance = appraised + over_allow

    trade_flag_col = has_trade
    trade_brand_col = np.where(has_trade, trade_brand, None)
    trade_model_col = np.where(has_trade, trade_model, None)
    trade_year_col = np.where(has_trade, trade_year, np.nan)
    trade_mileage_col = np.where(has_trade, trade_mileage, np.nan)
    appraised_col = np.where(has_trade, appraised, np.nan)
    allowance_col = np.where(has_trade, allowance, np.nan)
    over_allow_col = np.where(has_trade, over_allow, np.nan)
    trade_bonus_col = np.where(has_trade, trade_bonus, 0.0)

    test_drive_converted = rng.random(n) < 0.62

    # Deal velocity: incentive money measurably shortens time-to-close, which is
    # what makes the trade-bonus elasticity read on the dashboard a real signal
    # rather than noise.
    lead_to_close_days = np.clip(
        rng.integers(1, 60, n) - (trade_bonus_col / 250.0).round(0), 1, 60
    ).astype(int)
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
        # Lease contract terms (Lease rows only)
        "lease_term_months": lease_term_col,
        "lease_maturity_date": maturity_col.dt.date,
        "residual_value_pct": resid_pct_col,
        "residual_value_usd": resid_usd_col,
        "contract_mileage_allowance": mileage_allow_col,
        "lease_monthly_payment_usd": lease_payment_col,
        # Trade-in activity
        "trade_in_flag": trade_flag_col,
        "trade_in_brand": trade_brand_col,
        "trade_in_model": trade_model_col,
        "trade_in_year": trade_year_col,
        "trade_in_mileage": trade_mileage_col,
        "trade_in_appraised_value_usd": appraised_col,
        "trade_in_allowance_usd": allowance_col,
        "trade_in_over_allowance_usd": over_allow_col,
        "trade_bonus_usd": trade_bonus_col,
    })
    return df


WAREHOUSE_ZONES = ["Zone A", "Zone B", "Zone C", "Zone D"]

# Months of stock history to snapshot. Dealer management systems keep a rolling
# operational window, not a decade, and 36 months is plenty of trend for the
# dashboard.
INVENTORY_HISTORY_MONTHS = 36


def build_inventory(rng, vehicles_df, dealers_df, sales_df):
    """
    Month-end stock snapshots for every (dealer, vehicle) the dealer actually
    franchises.

    The previous version scattered rows across ~2,800 random dates, which made
    "current stock" impossible to read: summing the table double-counted the
    same car across every snapshot it appeared in. Regular month-end snapshots
    give an unambiguous current position and a clean trend line.

    Stock behaviour is derived rather than drawn at random:
      - turn rate follows the model's residual strength (desirable metal moves)
      - holding cost is floorplan interest on the actual MSRP
      - lead times split domestic vs. ocean-freighted imports
    """
    months = MONTHS[-INVENTORY_HISTORY_MONTHS:]

    # Observed 30-day sales rate per (dealer, vehicle) anchors the forecast, so
    # demand_forecast_30d reflects the sales table instead of a random number.
    obs = (sales_df.groupby(["dealer_id", "vehicle_id"]).size()
           .rename("total_units").reset_index())
    span_months = max(len(MONTHS), 1)
    obs["monthly_rate"] = obs["total_units"] / span_months
    rate_lookup = dict(zip(zip(obs["dealer_id"], obs["vehicle_id"]), obs["monthly_rate"]))

    veh_by_brand = {b: vehicles_df[vehicles_df["brand"] == b] for b in BRAND_NAMES}

    rows = []
    inv_id = 1
    for _, dealer in dealers_df.iterrows():
        pool = veh_by_brand.get(dealer["brand"])
        if pool is None or len(pool) == 0:
            continue
        # Capacity is shared across the franchise's line-up.
        per_model_capacity = max(dealer["monthly_capacity"] / max(len(pool), 1), 2.0)

        for _, veh in pool.iterrows():
            is_import = veh["brand"] in IMPORT_BRANDS
            resid = float(veh["_residual_36mo"])

            # Desirability: 0 = hardest to move, 1 = fastest turning.
            desirability = np.clip((resid - 0.38) / (0.72 - 0.38), 0.0, 1.0)
            # US dealer average lands near 60-70 days supply; fast Toyota metal
            # turns in under a month, slow luxury EVs sit past 100 days.
            base_days = 25.0 + (1.0 - desirability) * 85.0

            # Ocean freight vs. a domestic plant is the dominant lead-time split.
            lead_time = int(rng.integers(38, 70)) if is_import else int(rng.integers(8, 26))

            # Floorplan interest on the unit plus fixed lot overhead. A $40k
            # unit at ~8% floorplan costs roughly $9/day to hold, and that is
            # what the holding-cost KPI should reflect.
            floorplan_apr = 0.075
            holding_per_day = round(
                veh["price_usd"] * floorplan_apr / 365.0 + rng.uniform(2.0, 4.5), 2
            )

            observed_rate = rate_lookup.get((dealer["dealer_id"], veh["vehicle_id"]), 0.0)
            # Blend observed history with capacity so thinly-sold trims still
            # carry a sane baseline.
            base_rate = max(observed_rate, per_model_capacity * 0.06)

            zone = WAREHOUSE_ZONES[inv_id % len(WAREHOUSE_ZONES)]
            port = rng.choice(IMPORT_PORTS) if is_import else "N/A (Domestic)"

            for mi, month_start in enumerate(months):
                month_no = month_start.month
                global_mi = len(MONTHS) - INVENTORY_HISTORY_MONTHS + mi

                # Spring and early-autumn selling seasons.
                seasonal = 1.0 + 0.18 * np.sin((month_no - 3) / 12 * 2 * np.pi)
                monthly_demand = max(base_rate * seasonal * rng.uniform(0.75, 1.3), 0.4)

                sold_30d = int(np.clip(rng.poisson(monthly_demand), 0, None))
                daily_demand = monthly_demand / 30.0

                # Textbook reorder point: demand over the replenishment lead
                # time plus safety stock sized on demand variability. Import
                # brands carry higher reorder points purely because ocean
                # freight makes their pipeline longer.
                # Target days of supply is the number a dealer principal
                # actually manages to. Desirable metal runs lean because it
                # keeps selling (~30 days); slow metal piles up (~95 days).
                # The industry healthy band is 45-75 days.
                days_supply_target = 28.0 + (1.0 - desirability) * 67.0

                # Actual stock drifts around that target between deliveries.
                fluctuation = float(np.clip(rng.normal(1.0, 0.30), 0.12, 2.1))
                stock = int(np.clip(round(daily_demand * days_supply_target * fluctuation), 0, 400))

                # Reorder point at a 90% service level, but never above 65% of
                # the target stocking level. The cap matters: at trim level a
                # store sells only a few units a month, so an uncapped Poisson
                # safety stock would set the trigger above the target itself and
                # flag most of the line-up as permanently urgent.
                safety = 1.28 * np.sqrt(max(daily_demand, 0.01) * lead_time)
                reorder_pt = max(int(round(min(daily_demand * lead_time + safety,
                                               daily_demand * days_supply_target * 0.65))), 1)

                # Occasional genuine stockouts on fast-moving, allocation-
                # constrained models.
                if desirability > 0.6 and rng.random() < 0.06:
                    stock = 0

                forecast_30d = int(max(round(monthly_demand * rng.uniform(0.9, 1.15)), 0))

                in_transit = int(rng.poisson(max(monthly_demand * 0.5, 0.3))) if rng.random() < 0.55 else 0
                units_ordered = int(rng.poisson(max(monthly_demand * 0.8, 0.5)))

                # Days of supply on hand — the number a dealer principal
                # actually manages to. Industry healthy band is 45-75 days.
                days_supply = float(np.clip(stock / max(daily_demand, 0.001), 0, 260))
                days_in_stock = int(np.clip(rng.normal(days_supply, 8), 1, 260))

                stockout = stock == 0
                overstock = days_supply > 90
                reorder_needed = (not stockout) and stock <= reorder_pt

                # Risk scores are read off the actual position rather than drawn
                # from an unrelated beta distribution.
                cover_ratio = stock / reorder_pt
                stockout_risk = float(np.clip(1.0 - cover_ratio / 2.0, 0.0, 1.0))
                overstock_risk = float(np.clip((days_supply - 60.0) / 90.0, 0.0, 1.0))

                record_date = (month_start + pd.offsets.MonthEnd(0)).date()
                last_replen = (month_start - pd.Timedelta(days=int(rng.integers(5, 50)))).date()

                rows.append({
                    "inventory_id": f"INV{inv_id:07d}",
                    "record_date": record_date,
                    "dealer_id": dealer["dealer_id"],
                    "vehicle_id": veh["vehicle_id"],
                    "brand": veh["brand"],
                    "model": veh["model"],
                    "vehicle_category": veh["category"],
                    "fuel_type": veh["fuel_type"],
                    "state": dealer["state"],
                    "city": dealer["city"],
                    "current_stock": stock,
                    "demand_forecast_30d": forecast_30d,
                    "reorder_point": reorder_pt,
                    "days_in_stock": days_in_stock,
                    "stockout_flag": bool(stockout),
                    "overstock_flag": bool(overstock),
                    "reorder_needed": bool(reorder_needed),
                    "stockout_risk_score": round(stockout_risk, 3),
                    "overstock_risk_score": round(overstock_risk, 3),
                    "holding_cost_per_day_usd": holding_per_day,
                    # Cost of floorplanning the units on hand for 30 days.
                    "estimated_holding_cost_usd": round(holding_per_day * stock * 30.0, 2),
                    "units_sold_last_30d": sold_30d,
                    "units_ordered": units_ordered,
                    "transit_stock": in_transit,
                    "port_of_entry": port,
                    "warehouse_zone": zone,
                    "last_replenishment_date": last_replen,
                    "supplier_lead_time_days": lead_time,
                    "customs_cleared": bool(rng.random() < 0.96) if is_import else True,
                })
                inv_id += 1

    return pd.DataFrame(rows)


def generate_dataset(out_dir, seed, n_customers, dealers_per_state, n_sales, n_trims):
    rng = np.random.default_rng(seed)
    os.makedirs(out_dir, exist_ok=True)

    vehicles = build_vehicle_catalog(rng, n_trims=n_trims)
    dealers = build_dealers(rng, dealers_per_state)
    customers = build_customers(rng, n_customers, START, END)
    external_factors = build_external_factors(rng)
    sales = build_sales(rng, n_sales, vehicles, dealers, customers, START, END)
    # Inventory is derived from the sales history, so it is built last and
    # sized by the dealer network rather than by a row count.
    inventory = build_inventory(rng, vehicles, dealers, sales)

    # _residual_36mo is an internal generation field; persist it under its
    # public column name so the lease-equity model can read it back.
    vehicles = vehicles.rename(columns={"_residual_36mo": "residual_value_36mo"})

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
        n_customers=42000, dealers_per_state=6, n_sales=100000, n_trims=2,
    )
    # automobile_datasets: larger "test" mode dataset
    generate_dataset(
        os.path.join(ROOT, "automobile_datasets"), seed=7,
        n_customers=56000, dealers_per_state=15, n_sales=140000, n_trims=3,
    )


if __name__ == "__main__":
    main()
