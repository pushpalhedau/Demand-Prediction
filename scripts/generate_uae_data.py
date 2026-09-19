"""
Generate synthetic United Arab Emirates (7-emirate) automobile demand datasets.

Replaces the NA-modeled CSVs in automobile_datasets/ and realdata-datasets/ with
data in the UAE schema (see database/models.py). All row generation is seeded
(numpy default_rng) for reproducibility.

The dataset models ONE regional dealer group of 24 rooftops trading across the
seven emirates — not a national market model. There is no domestic UAE car
industry: every vehicle is imported, so there is no import-vs-domestic tariff
split (a flat 5% GCC customs duty applies to everything and is already in the
retail price). The only consumption tax is the federal 5% VAT (since Jan 2018;
our window starts 2019 so it is always on).

Real-world anchors baked into the external-factor time series (for narrative /
demo authenticity, not precise historical accuracy):
  - CBUAE base rate path 2019-2026 (pegged to the Fed: COVID cut to ~0.15%,
    2022-23 hiking cycle to ~5.4%, 2024-25 cuts)
  - UAE regulated petrol price path, AED/litre (2020 COVID crash to ~1.32,
    2022 Russia/Ukraine spike to ~4.15, settling ~2.6-2.7 in 2025-26)
  - Brent crude price path
  - UAE CPI path (2019-20 mild deflation, 2022 peak ~5.4%)
  - GDP path (2020 COVID + oil contraction ~-5%, 2022 oil boom ~+7.9%)
  - Dubai residential price index (2019-20 downcycle, 2021-25 boom)
  - Dubai tourism index (2020 near-total collapse, fast recovery)
  - Ramadan / Eid windows 2019-2026 (real Hijri dates), UAE National Day (Dec),
    Dubai Shopping Festival (Jan), Dubai International Motor Show (Nov, biennial)

Run: python -m preprocessing.generate_uae_data
"""

import calendar
import os
import sys
from datetime import date

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ─────────────────────────────────────────────────────────────────────────────
# Geography: 7-emirate UAE model
#
# Dubai + Abu Dhabi carry the overwhelming majority of new-vehicle retail; the
# northern emirates are thin. `vat` is a single federal 5% (no per-emirate
# sales tax), so it is not carried here — it is a constant in build_sales.
# `ev_index` is a rough relative EV-readiness weight (charging density, policy).
# ─────────────────────────────────────────────────────────────────────────────
EMIRATES = [
    {"name": "Dubai", "weight": 42, "ev_index": 1.00, "pop_m": 3.65,
     "areas": [("Deira", 25.2711, 55.3095), ("Bur Dubai", 25.2582, 55.2962),
               ("Sheikh Zayed Road", 25.2180, 55.2790), ("Al Quoz", 25.1400, 55.2300),
               ("Dubai Marina", 25.0805, 55.1403), ("Deira Automarket", 25.2830, 55.3480)]},
    {"name": "Abu Dhabi", "weight": 30, "ev_index": 0.80, "pop_m": 3.80,
     "areas": [("Abu Dhabi City", 24.4539, 54.3773), ("Musaffah", 24.3560, 54.5010),
               ("Al Ain", 24.2075, 55.7447), ("Khalifa City", 24.4200, 54.5800),
               ("Mussafah Auto Market", 24.3480, 54.4900)]},
    {"name": "Sharjah", "weight": 17, "ev_index": 0.55, "pop_m": 1.80,
     "areas": [("Sharjah City", 25.3463, 55.4209), ("Industrial Area", 25.3120, 55.4300),
               ("Al Nahda", 25.3050, 55.3720), ("Al Rahmaniya", 25.2900, 55.4700)]},
    {"name": "Ajman", "weight": 4, "ev_index": 0.35, "pop_m": 0.55,
     "areas": [("Ajman City", 25.4052, 55.5136), ("Al Jurf", 25.4130, 55.4820)]},
    {"name": "Ras Al Khaimah", "weight": 3.5, "ev_index": 0.30, "pop_m": 0.42,
     "areas": [("RAK City", 25.7895, 55.9432), ("Al Nakheel", 25.7600, 55.9470)]},
    {"name": "Fujairah", "weight": 2, "ev_index": 0.25, "pop_m": 0.26,
     "areas": [("Fujairah City", 25.1288, 56.3265), ("Dibba", 25.5920, 56.2620)]},
    {"name": "Umm Al Quwain", "weight": 1.5, "ev_index": 0.20, "pop_m": 0.09,
     "areas": [("UAQ City", 25.5647, 55.5551), ("Al Salamah", 25.5300, 55.6800)]},
]
EMIRATE_NAMES = [e["name"] for e in EMIRATES]
EMIRATE_WEIGHTS = np.array([e["weight"] for e in EMIRATES], dtype=float)
EMIRATE_WEIGHTS = EMIRATE_WEIGHTS / EMIRATE_WEIGHTS.sum()

VAT_RATE_PCT = 5.0          # federal, flat, since Jan 2018
GCC_CUSTOMS_DUTY_PCT = 5.0  # flat duty on all imports — already in the retail price

# ─────────────────────────────────────────────────────────────────────────────
# Vehicle catalog — real UAE-market model specs
#
# Each model carries its actual published specification rather than a random
# draw, because the Placement Assistant matches substitutes on these attributes
# (a shopper cross-shops a Prado against a Fortuner because the specs genuinely
# line up, not because a random number generator put them near each other).
#
# Tuple layout:
#   (model, category, fuel, base_price_aed, hp, engine_cc, km_per_litre,
#    range_km, seats, drive_type, residual_36mo, model_year_intro)
#
# residual_36mo = share of the price the vehicle is worth at 36-month
# maturity. Body-on-frame 4x4s (Land Cruiser, Patrol, Wrangler-class) and
# Toyota/Lexus hold value hardest in the Gulf used market (0.60-0.72);
# mainstream sedans sit mid-pack (0.44-0.55); Chinese brands and EVs
# depreciate hardest (0.38-0.46).
# ─────────────────────────────────────────────────────────────────────────────
BRAND_CATALOG = {
    "Toyota": (28, [
        ("Land Cruiser",  "SUV",       "Petrol",   285000, 409, 3444, 9,   None, 7, "4WD", 0.70, 2022),
        ("Prado",         "SUV",       "Petrol",   172000, 278, 3500, 10,  None, 7, "4WD", 0.68, 2024),
        ("Hilux",         "Pickup",    "Petrol",   108000, 235, 3956, 11,  None, 5, "4WD", 0.66, 2021),
        ("Fortuner",      "SUV",       "Petrol",   135000, 235, 3956, 9,   None, 7, "4WD", 0.60, 2020),
        ("RAV4",          "SUV",       "Petrol",   118000, 203, 2487, 14,  None, 5, "AWD", 0.58, 2019),
        ("RAV4 Hybrid",   "SUV",       "Hybrid",   135000, 219, 2487, 21,  None, 5, "AWD", 0.60, 2021),
        ("Corolla",       "Sedan",     "Petrol",   82000,  170, 1987, 16,  None, 5, "FWD", 0.55, 2020),
        ("Corolla Hybrid","Sedan",     "Hybrid",   92000,  138, 1798, 25,  None, 5, "FWD", 0.56, 2022),
        ("Camry",         "Sedan",     "Petrol",   122000, 203, 2487, 15,  None, 5, "FWD", 0.52, 2018),
        ("Camry Hybrid",  "Sedan",     "Hybrid",   135000, 225, 2487, 22,  None, 5, "FWD", 0.55, 2021),
        ("Yaris",         "Sedan",     "Petrol",   60000,  106, 1496, 18,  None, 5, "FWD", 0.50, 2022),
        ("Rush",          "SUV",       "Petrol",   84000,  102, 1496, 14,  None, 7, "RWD", 0.52, 2019),
        ("bZ4X",          "SUV",       "Electric", 165000, 218, None, None, 411, 5, "AWD", 0.42, 2023),
    ]),
    "Nissan": (14, [
        ("Patrol",       "SUV",    "Petrol", 245000, 400, 5552, 8,  None, 8, "4WD", 0.68, 2020),
        ("X-Trail",      "SUV",    "Petrol", 105000, 181, 2488, 13, None, 7, "AWD", 0.52, 2022),
        ("Sunny",        "Sedan",  "Petrol", 52000,  99,  1498, 18, None, 5, "FWD", 0.48, 2020),
        ("Altima",       "Sedan",  "Petrol", 92000,  188, 2488, 14, None, 5, "FWD", 0.47, 2019),
        ("Kicks",        "SUV",    "Petrol", 72000,  118, 1598, 16, None, 5, "FWD", 0.50, 2021),
        ("Pathfinder",   "SUV",    "Petrol", 145000, 284, 3498, 11, None, 7, "4WD", 0.52, 2022),
        ("Navara",       "Pickup", "Diesel", 95000,  190, 2488, 13, None, 5, "4WD", 0.56, 2021),
        ("Patrol Nismo", "SUV",    "Petrol", 320000, 428, 5552, 8,  None, 5, "4WD", 0.62, 2021),
    ]),
    "Mitsubishi": (8, [
        ("Pajero",         "SUV",    "Petrol", 135000, 190, 3828, 9,  None, 7, "4WD", 0.55, 2019),
        ("Montero Sport",  "SUV",    "Petrol", 128000, 220, 2998, 10, None, 7, "4WD", 0.56, 2021),
        ("L200",           "Pickup", "Diesel", 92000,  178, 2442, 13, None, 5, "4WD", 0.55, 2020),
        ("Attrage",        "Sedan",  "Petrol", 48000,  78,  1193, 20, None, 5, "FWD", 0.45, 2020),
        ("Xpander",        "SUV",    "Petrol", 72000,  105, 1499, 15, None, 7, "FWD", 0.50, 2022),
        ("Eclipse Cross",  "SUV",    "Petrol", 89000,  150, 1499, 13, None, 5, "AWD", 0.48, 2022),
    ]),
    "Hyundai": (8, [
        ("Tucson",   "SUV",   "Petrol",   95000,  187, 2497, 13,  None, 5, "AWD", 0.53, 2022),
        ("Elantra",  "Sedan", "Petrol",   72000,  147, 1999, 16,  None, 5, "FWD", 0.50, 2021),
        ("Creta",    "SUV",   "Petrol",   78000,  115, 1497, 15,  None, 5, "FWD", 0.51, 2020),
        ("Santa Fe", "SUV",   "Petrol",   130000, 277, 2497, 11,  None, 7, "AWD", 0.52, 2024),
        ("Accent",   "Sedan", "Petrol",   58000,  123, 1591, 17,  None, 5, "FWD", 0.47, 2019),
        ("Sonata",   "Sedan", "Petrol",   105000, 191, 2497, 13,  None, 5, "FWD", 0.46, 2020),
        ("Palisade", "SUV",   "Petrol",   165000, 291, 3778, 10,  None, 8, "AWD", 0.55, 2023),
        ("Ioniq 5",  "SUV",   "Electric", 175000, 225, None, None, 481, 5, "RWD", 0.45, 2022),
    ]),
    "Kia": (7, [
        ("Sportage",  "SUV",     "Petrol",   92000,  187, 2497, 13,  None, 5, "AWD", 0.52, 2023),
        ("Cerato",    "Sedan",   "Petrol",   68000,  147, 1999, 16,  None, 5, "FWD", 0.49, 2022),
        ("Seltos",    "SUV",     "Petrol",   78000,  115, 1497, 15,  None, 5, "FWD", 0.50, 2021),
        ("Sorento",   "SUV",     "Petrol",   128000, 191, 2497, 11,  None, 7, "AWD", 0.53, 2021),
        ("Pegas",     "Sedan",   "Petrol",   50000,  94,  1368, 19,  None, 5, "FWD", 0.44, 2020),
        ("Carnival",  "Minivan", "Petrol",   145000, 287, 3470, 10,  None, 8, "FWD", 0.54, 2022),
        ("Telluride", "SUV",     "Petrol",   165000, 291, 3778, 10,  None, 8, "AWD", 0.60, 2020),
        ("EV6",       "SUV",     "Electric", 180000, 225, None, None, 528, 5, "RWD", 0.44, 2022),
    ]),
    "Honda": (5, [
        ("CR-V",          "SUV",   "Petrol", 115000, 190, 1498, 13, None, 5, "AWD", 0.55, 2023),
        ("Civic",         "Sedan", "Petrol", 95000,  158, 1996, 16, None, 5, "FWD", 0.54, 2022),
        ("Accord",        "Sedan", "Petrol", 125000, 192, 1498, 14, None, 5, "FWD", 0.50, 2023),
        ("Accord Hybrid", "Sedan", "Hybrid", 140000, 204, 1993, 22, None, 5, "FWD", 0.51, 2023),
        ("City",          "Sedan", "Petrol", 68000,  121, 1498, 18, None, 5, "FWD", 0.48, 2021),
        ("Pilot",         "SUV",   "Petrol", 175000, 285, 3500, 10, None, 8, "AWD", 0.52, 2023),
        ("HR-V",          "SUV",   "Petrol", 89000,  121, 1498, 15, None, 5, "FWD", 0.50, 2022),
    ]),
    "MG": (6, [
        ("MG5",    "Sedan",     "Petrol",   62000,  114, 1498, 16,  None, 5, "FWD", 0.40, 2021),
        ("ZS",     "SUV",       "Petrol",   68000,  111, 1498, 15,  None, 5, "FWD", 0.41, 2020),
        ("RX5",    "SUV",       "Petrol",   82000,  174, 1998, 12,  None, 5, "FWD", 0.40, 2022),
        ("HS",     "SUV",       "Petrol",   88000,  168, 1498, 13,  None, 5, "FWD", 0.42, 2021),
        ("MG6",    "Sedan",     "Petrol",   78000,  168, 1498, 14,  None, 5, "FWD", 0.39, 2021),
        ("MG4 EV", "Hatchback", "Electric", 110000, 168, None, None, 425, 5, "RWD", 0.40, 2023),
    ]),
    "Chevrolet": (5, [
        ("Tahoe",       "SUV",    "Petrol", 235000, 355, 5328, 8,  None, 8, "4WD", 0.58, 2021),
        ("Trailblazer", "SUV",    "Petrol", 82000,  155, 1341, 14, None, 5, "FWD", 0.46, 2021),
        ("Groove",      "SUV",    "Petrol", 68000,  106, 1499, 15, None, 5, "FWD", 0.44, 2020),
        ("Captiva",     "SUV",    "Petrol", 78000,  141, 1499, 14, None, 7, "FWD", 0.44, 2019),
        ("Malibu",      "Sedan",  "Petrol", 92000,  160, 1490, 15, None, 5, "FWD", 0.43, 2019),
        ("Silverado",   "Pickup", "Petrol", 210000, 420, 6162, 7,  None, 5, "4WD", 0.55, 2022),
    ]),
    "Lexus": (4, [
        ("LX",      "Luxury", "Petrol", 470000, 409, 3444, 8,  None, 7, "4WD", 0.62, 2022),
        ("ES",      "Luxury", "Petrol", 175000, 203, 2487, 14, None, 5, "FWD", 0.52, 2019),
        ("ES 300h", "Luxury", "Hybrid", 195000, 215, 2487, 23, None, 5, "FWD", 0.53, 2020),
        ("RX",      "Luxury", "Petrol", 245000, 275, 2393, 11, None, 5, "AWD", 0.55, 2023),
        ("NX",      "Luxury", "Petrol", 195000, 275, 2393, 12, None, 5, "AWD", 0.54, 2022),
        ("GX",      "Luxury", "Petrol", 305000, 349, 3445, 9,  None, 7, "4WD", 0.60, 2024),
    ]),
    "Ford": (4, [
        ("Explorer",  "SUV",   "Petrol", 165000, 300, 2264, 11, None, 7, "4WD", 0.50, 2020),
        ("Territory", "SUV",   "Petrol", 95000,  190, 1496, 13, None, 5, "FWD", 0.44, 2023),
        ("F-150",     "Pickup", "Petrol", 220000, 400, 3500, 8,  None, 5, "4WD", 0.55, 2021),
        ("Mustang",   "Coupe",  "Petrol", 185000, 315, 2264, 11, None, 4, "RWD", 0.55, 2024),
        ("Edge",      "SUV",   "Petrol", 135000, 250, 1997, 11, None, 5, "AWD", 0.46, 2019),
        ("Bronco",    "SUV",   "Petrol", 195000, 300, 2264, 10, None, 5, "4WD", 0.62, 2022),
    ]),
    "Mercedes-Benz": (4, [
        ("C-Class", "Luxury", "Petrol", 245000, 258, 1999, 14, None, 5, "RWD", 0.49, 2022),
        ("E-Class", "Luxury", "Petrol", 320000, 258, 1999, 13, None, 5, "RWD", 0.46, 2024),
        ("GLC",     "Luxury", "Petrol", 285000, 258, 1999, 12, None, 5, "AWD", 0.52, 2023),
        ("GLE",     "Luxury", "Petrol", 420000, 375, 2999, 10, None, 5, "AWD", 0.50, 2020),
        ("S-Class", "Luxury", "Petrol", 650000, 429, 2999, 10, None, 5, "AWD", 0.45, 2021),
        ("G-Class", "Luxury", "Petrol", 850000, 585, 3982, 7,  None, 5, "4WD", 0.72, 2019),
    ]),
    "BMW": (3, [
        ("3 Series", "Luxury", "Petrol",   235000, 255, 1998, 15,  None, 5, "RWD", 0.48, 2019),
        ("5 Series", "Luxury", "Petrol",   330000, 375, 2998, 13,  None, 5, "RWD", 0.46, 2024),
        ("X3",       "Luxury", "Petrol",   255000, 248, 1998, 13,  None, 5, "AWD", 0.50, 2018),
        ("X5",       "Luxury", "Petrol",   400000, 375, 2998, 11,  None, 5, "AWD", 0.52, 2019),
        ("X7",       "Luxury", "Petrol",   520000, 375, 2998, 10,  None, 7, "AWD", 0.53, 2023),
        ("i4",       "Luxury", "Electric", 285000, 340, None, None, 493, 5, "RWD", 0.42, 2022),
    ]),
    "Land Rover": (2, [
        ("Range Rover Sport",  "Luxury", "Petrol", 550000, 400, 2996, 9,  None, 5, "4WD", 0.55, 2023),
        ("Range Rover Evoque", "Luxury", "Petrol", 260000, 249, 1997, 12, None, 5, "AWD", 0.48, 2020),
        ("Defender",           "SUV",    "Petrol", 340000, 400, 2996, 9,  None, 5, "4WD", 0.60, 2021),
        ("Range Rover Velar",  "Luxury", "Petrol", 320000, 250, 1997, 11, None, 5, "AWD", 0.47, 2019),
        ("Discovery",          "SUV",    "Petrol", 330000, 355, 2996, 9,  None, 7, "4WD", 0.48, 2021),
    ]),
    "Mazda": (3, [
        ("CX-5",   "SUV",   "Petrol", 105000, 187, 2488, 13, None, 5, "AWD", 0.50, 2022),
        ("Mazda 3", "Sedan", "Petrol", 82000, 186, 1998, 15, None, 5, "FWD", 0.48, 2021),
        ("CX-9",   "SUV",   "Petrol", 155000, 227, 2488, 11, None, 7, "AWD", 0.50, 2020),
        ("Mazda 6", "Sedan", "Petrol", 105000, 194, 2488, 14, None, 5, "FWD", 0.46, 2019),
        ("CX-30",  "SUV",   "Petrol", 89000,  186, 1998, 14, None, 5, "AWD", 0.48, 2021),
        ("CX-60",  "SUV",   "Petrol", 165000, 328, 3283, 11, None, 5, "AWD", 0.50, 2023),
    ]),
    "Suzuki": (2, [
        ("Jimny",        "SUV",       "Petrol", 82000, 101, 1462, 14, None, 4, "4WD", 0.68, 2020),
        ("Dzire",        "Sedan",     "Petrol", 44000, 89,  1197, 22, None, 5, "FWD", 0.44, 2020),
        ("Baleno",       "Hatchback", "Petrol", 46000, 89,  1197, 21, None, 5, "FWD", 0.43, 2022),
        ("Ertiga",       "Minivan",   "Petrol", 62000, 103, 1462, 17, None, 7, "FWD", 0.46, 2019),
        ("Fronx",        "SUV",       "Petrol", 58000, 100, 1197, 18, None, 5, "FWD", 0.47, 2023),
        ("Grand Vitara", "SUV",       "Petrol", 78000, 103, 1462, 16, None, 5, "AWD", 0.48, 2023),
    ]),
}

# Real trim ladders per brand, cheapest -> most expensive. The Placement
# Assistant surfaces these by name ("the customer wanted a VXR"), so generic
# Base/Mid/Full labels would read as fake to anyone who sells cars in the Gulf.
BRAND_TRIMS = {
    "Toyota":        ["GX", "GXR", "VXR", "GR Sport"],
    "Nissan":        ["S", "SE", "SL", "Platinum"],
    "Mitsubishi":    ["GLX", "GLS", "Highline", "Adventure"],
    "Hyundai":       ["Smart", "Comfort", "Premium", "Signature"],
    "Kia":           ["LX", "EX", "GT-Line", "Prestige"],
    "Honda":         ["DX", "LX", "EX", "Touring"],
    "MG":            ["STD", "COM", "LUX", "Trophy"],
    "Chevrolet":     ["LS", "LT", "RS", "Premier"],
    "Lexus":         ["Base", "Prestige", "F Sport", "Signature"],
    "Ford":          ["Ambiente", "Trend", "Titanium", "Wildtrak"],
    "Mercedes-Benz": ["Base", "Exclusive", "AMG Line", "AMG Line Premium"],
    "BMW":           ["sDrive", "xDrive", "M Sport", "M Sport Pro"],
    "Land Rover":    ["S", "SE", "HSE", "Autobiography"],
    "Mazda":         ["Core", "Touring", "GT", "Signature"],
    "Suzuki":        ["GL", "GLX", "GLX+", "AllGrip"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Nameplate demand skew.
#
# Within a brand, real Gulf retail volume is heavily skewed toward a couple of
# mainstream nameplates (a Toyota store sells far more Land Cruisers, Prados and
# Corollas than Rushes and bZ4Xs). Uniform model selection made every nameplate
# equally likely, which put niche trims at the top of the sales board. These
# tiers restore a realistic best-seller shape; anything not listed sits at the
# neutral 1.0 weight.
# ─────────────────────────────────────────────────────────────────────────────
MODEL_FLAGSHIP = {
    "Land Cruiser", "Prado", "Hilux", "Patrol", "Corolla", "Sunny", "Pajero",
    "Tucson", "Sportage", "MG5", "ZS", "Tahoe", "RX", "Explorer", "GLC", "X5",
    "Defender", "CX-5", "Dzire",
}
MODEL_STRONG = {
    "Fortuner", "RAV4", "RAV4 Hybrid", "Camry", "Camry Hybrid", "Corolla Hybrid",
    "Yaris", "X-Trail", "Altima", "Kicks", "Montero Sport", "Attrage", "Elantra",
    "Creta", "Accent", "Cerato", "Seltos", "Pegas", "Civic", "City", "HS", "RX5",
    "Trailblazer", "Groove", "ES", "ES 300h", "NX", "Territory", "C-Class",
    "3 Series", "X3", "Range Rover Evoque", "Mazda 3", "CX-30", "Baleno", "Fronx",
    "Grand Vitara", "Ioniq 5", "EV6", "MG4 EV",
}
MODEL_NICHE = {
    "Rush", "bZ4X", "Patrol Nismo", "Eclipse Cross", "Pilot",
    "MG6", "Carnival", "Telluride", "Silverado", "LX", "GX", "F-150",
    "Mustang", "Bronco", "E-Class", "GLE", "S-Class", "G-Class", "5 Series",
    "X7", "i4", "Range Rover Sport", "Range Rover Velar", "Discovery", "CX-9",
    "Mazda 6", "CX-60", "Jimny", "Ertiga", "Palisade", "Sonata", "Pathfinder",
    "Navara", "L200", "Accord Hybrid",
}
MODEL_TIER_WEIGHT = {
    **{m: 2.6 for m in MODEL_FLAGSHIP},
    **{m: 1.7 for m in MODEL_STRONG},
    **{m: 0.45 for m in MODEL_NICHE},
}

# Trim ladder economics: price multiplier, hp uplift, km/L penalty (bigger
# wheels / heavier equipment), applied by position on the ladder.
TRIM_PRICE_MULT = [1.00, 1.10, 1.22, 1.36]
TRIM_HP_MULT = [1.00, 1.00, 1.06, 1.14]
TRIM_KMPL_DELTA = [0, -1, -1, -2]

# The Hyundai / Kia / MG long basic warranty is a genuine Gulf market
# differentiator, so it is modelled rather than randomised.
BRAND_WARRANTY_YEARS = {"Hyundai": 5, "Kia": 5, "MG": 5, "Mitsubishi": 5}

# Real exterior paint names, used by the Placement Assistant so a shopper
# request reads like a real one ("white Prado VXR").
PAINT_COLORS = [
    "Pearl White", "Attitude Black", "Silver Metallic", "Grey Metallic",
    "Desert Sand", "Dark Blue", "Bronze Mica", "Red Mica",
]

# Region a brand ships from — drives port of entry and ocean-freight lead time.
# Not a tariff input: every brand pays the same flat 5% GCC customs duty.
BRAND_ORIGIN_REGION = {
    "Toyota": "Japan", "Nissan": "Japan", "Mitsubishi": "Japan", "Honda": "Japan",
    "Mazda": "Japan", "Lexus": "Japan", "Suzuki": "Japan/India",
    "Hyundai": "Korea", "Kia": "Korea",
    "MG": "China",
    "Chevrolet": "USA", "Ford": "USA",
    "Mercedes-Benz": "Europe", "BMW": "Europe", "Land Rover": "Europe",
}
ORIGIN_LEAD_DAYS = {
    "Japan": (28, 42), "Japan/India": (22, 40), "Korea": (26, 40),
    "China": (24, 38), "USA": (40, 60), "Europe": (34, 52),
}

BRAND_NAMES = list(BRAND_CATALOG.keys())
BRAND_WEIGHTS = np.array([BRAND_CATALOG[b][0] for b in BRAND_NAMES], dtype=float)
BRAND_WEIGHTS = BRAND_WEIGHTS / BRAND_WEIGHTS.sum()

IMPORT_PORTS = ["Jebel Ali Port", "Khalifa Port", "Mina Zayed", "Sharjah (Khor Fakkan)", "Hamriyah Port"]

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


# ─────────────────────────────────────────────────────────────────────────────
# Real-anchored macro series (approximate, for narrative authenticity)
# ─────────────────────────────────────────────────────────────────────────────

# CBUAE base rate — pegged to the Fed, so the path mirrors it: 2020 COVID cut
# to ~0.15%, the 2022-23 hiking cycle to ~5.4%, 2024-25 cuts.
CBUAE_RATE = _interp_series([
    (2019, 1, 2.75), (2019, 12, 2.0), (2020, 3, 0.75), (2020, 5, 0.35),
    (2021, 12, 0.15), (2022, 3, 0.4), (2022, 12, 4.4), (2023, 7, 5.4),
    (2024, 8, 5.4), (2024, 12, 4.65), (2025, 6, 4.4), (2025, 12, 4.15), (2026, 8, 4.0),
])
# UAE regulated petrol (Special 95), AED per litre — set monthly by the Fuel
# Price Committee. 2020 COVID crash to ~1.32, 2022 spike to ~4.15, ~2.6 in 2025.
PETROL_95 = _interp_series([
    (2019, 1, 2.13), (2019, 12, 2.30), (2020, 4, 1.32), (2020, 7, 1.79),
    (2020, 12, 1.91), (2021, 6, 2.34), (2021, 12, 2.65), (2022, 3, 3.32),
    (2022, 6, 4.15), (2022, 12, 2.90), (2023, 6, 3.15), (2023, 12, 2.83),
    (2024, 6, 3.03), (2024, 12, 2.74), (2025, 6, 2.72), (2025, 12, 2.60), (2026, 8, 2.66),
])
DIESEL_PRICE = _interp_series([
    (2019, 1, 2.28), (2020, 4, 1.55), (2021, 12, 2.62), (2022, 7, 4.76),
    (2022, 12, 3.20), (2023, 12, 2.95), (2024, 12, 2.68), (2025, 12, 2.55), (2026, 8, 2.60),
])
BRENT_CRUDE = _interp_series([
    (2019, 1, 55), (2019, 12, 66), (2020, 4, 23), (2020, 12, 50),
    (2021, 12, 78), (2022, 6, 118), (2022, 12, 82), (2023, 12, 77),
    (2024, 12, 74), (2025, 12, 70), (2026, 8, 72),
])
CPI_INFLATION = _interp_series([
    (2019, 1, -1.5), (2019, 12, -1.9), (2020, 12, -2.1), (2021, 12, 2.5),
    (2022, 6, 5.4), (2022, 12, 4.8), (2023, 12, 1.6), (2024, 12, 2.0),
    (2025, 12, 2.1), (2026, 8, 2.0),
])
UNEMPLOYMENT = _interp_series([
    (2019, 1, 2.3), (2020, 6, 3.6), (2020, 12, 3.4), (2021, 12, 3.0),
    (2022, 12, 2.7), (2023, 12, 2.6), (2024, 12, 2.7), (2025, 12, 2.7), (2026, 8, 2.7),
])
GDP_GROWTH = _interp_series([
    (2019, 1, 1.1), (2019, 12, 1.1), (2020, 6, -6.0), (2020, 12, -5.0),
    (2021, 12, 4.4), (2022, 12, 7.9), (2023, 12, 3.6), (2024, 12, 3.8),
    (2025, 12, 4.5), (2026, 8, 4.4),
])
CONSUMER_CONF = _interp_series([
    (2019, 1, 108), (2020, 4, 82), (2020, 12, 90), (2021, 12, 112),
    (2022, 12, 108), (2023, 12, 112), (2024, 12, 114), (2025, 12, 113), (2026, 8, 112),
])
# Dubai residential price index (2019 = 100). 2019-20 downcycle, then the
# 2021-2025 boom driven by post-COVID wealth migration.
DUBAI_RE_IDX = _interp_series([
    (2019, 1, 100), (2020, 1, 93), (2021, 1, 91), (2022, 1, 101),
    (2023, 1, 120), (2024, 1, 140), (2025, 1, 162), (2026, 8, 182),
])
TOURISM_IDX = _interp_series([
    (2019, 1, 100), (2020, 4, 8), (2020, 12, 35), (2021, 6, 45),
    (2022, 6, 88), (2023, 6, 100), (2024, 6, 109), (2025, 6, 114), (2026, 8, 116),
])
LUXURY_DEMAND_IDX = _interp_series([
    (2019, 1, 98), (2020, 6, 80), (2021, 12, 116), (2022, 12, 120),
    (2023, 12, 122), (2024, 12, 124), (2025, 12, 123), (2026, 8, 122),
])
EV_STATIONS_NATIONAL = _interp_series([
    (2019, 1, 190), (2020, 12, 340), (2021, 12, 460), (2022, 12, 620),
    (2023, 12, 760), (2024, 12, 1050), (2025, 12, 1400), (2026, 8, 1600),
])

# GCC customs duty is a flat 5% on every import, no step change — kept as a
# constant reference column, not a demand or pricing driver.
IMPORT_DUTY_PCT = np.full(N_MONTHS, GCC_CUSTOMS_DUTY_PCT)

MONTH_OF = np.array([d.month for d in MONTHS])
YEAR_OF = np.array([d.year for d in MONTHS])

# ─────────────────────────────────────────────────────────────────────────────
# Islamic calendar events — real Ramadan windows 2019-2026 (Gregorian). Eid
# Al Fitr immediately follows Ramadan; Eid Al Adha falls ~68 days after Ramadan
# ends. These drive the `festival_period` label on a sale and the seasonal
# flags in external_factors.
# ─────────────────────────────────────────────────────────────────────────────
RAMADAN = {
    2019: (date(2019, 5, 6),  date(2019, 6, 3)),
    2020: (date(2020, 4, 24), date(2020, 5, 23)),
    2021: (date(2021, 4, 13), date(2021, 5, 12)),
    2022: (date(2022, 4, 2),  date(2022, 5, 1)),
    2023: (date(2023, 3, 23), date(2023, 4, 20)),
    2024: (date(2024, 3, 11), date(2024, 4, 9)),
    2025: (date(2025, 3, 1),  date(2025, 3, 29)),
    2026: (date(2026, 2, 18), date(2026, 3, 19)),
}


def _ramadan_months_for(year):
    """Set of (year, month) tuples any part of that year's Ramadan touches."""
    if year not in RAMADAN:
        return set()
    s, e = RAMADAN[year]
    out = set()
    d = s
    while d <= e:
        out.add((d.year, d.month))
        d = d + pd.Timedelta(days=1)
    return out


_RAMADAN_MONTH_SET = set().union(*[_ramadan_months_for(y) for y in RAMADAN])

# Dubai International Motor Show — November, biennial. 2021 edition was
# cancelled (COVID), so 2019 / 2023 / 2025.
_MOTOR_SHOW_YEARS = {2019, 2023, 2025}

RAMADAN_MONTH = np.array([
    1 if (int(YEAR_OF[i]), int(MONTH_OF[i])) in _RAMADAN_MONTH_SET else 0
    for i in range(N_MONTHS)
])
NATIONAL_DAY_MONTH = np.where(MONTH_OF == 12, 1, 0)                       # UAE National Day, Dec 2
DSF_MONTH = np.where(MONTH_OF == 1, 1, 0)                                 # Dubai Shopping Festival, January
MOTOR_SHOW_MONTH = np.array([
    1 if (int(MONTH_OF[i]) == 11 and int(YEAR_OF[i]) in _MOTOR_SHOW_YEARS) else 0
    for i in range(N_MONTHS)
])
NEW_MODEL_LAUNCHES = np.where(np.isin(MONTH_OF, [1, 9, 10, 11]), 3, 1)


def _festival_period(d):
    """Retail sales-event label for a given calendar date, or None."""
    y = d.year
    if y in RAMADAN:
        r_start, r_end = RAMADAN[y]
        if r_start <= d <= r_end:
            return "Ramadan Offers"
        eid_fitr_end = r_end + pd.Timedelta(days=4)
        if r_end < d <= eid_fitr_end:
            return "Eid Al Fitr"
        adha_start = r_end + pd.Timedelta(days=66)
        adha_end = adha_start + pd.Timedelta(days=5)
        if adha_start <= d <= adha_end:
            return "Eid Al Adha"
    if d.month == 12 and 20 <= d.day <= 31:
        return "Year-End Clearance"
    if d.month == 11 and d.day >= 24:
        return "UAE National Day"
    if d.month == 12 and d.day <= 5:
        return "UAE National Day"
    if d.month == 1 and d.day <= 29:
        return "Dubai Shopping Festival"
    if d.month in (8, 9):
        return "Back to School"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Retail demand shape — this is ONE regional dealer group's own sales pattern,
# not a market model. The series below drive WHICH months and weekdays book
# deals; the group's annual volume is set by n_sales and is not inflated by
# any of this (the net macro effect is mean-normalised in build_sales).
# ─────────────────────────────────────────────────────────────────────────────

# UAE new-vehicle retail seasonality, index average = 100. Cooler-season peak
# (Q4 National Day promos + Q1 Dubai Shopping Festival and the January
# number-plate-year change), deep summer trough as residents travel and the
# heat keeps shoppers off the forecourt.
RETAIL_SEASONAL_FACTOR = {
    1: 1.14, 2: 1.04, 3: 1.02, 4: 0.98, 5: 0.90, 6: 0.82,
    7: 0.80, 8: 0.86, 9: 1.02, 10: 1.08, 11: 1.16, 12: 1.18,
}

# Day-of-week retail pattern (Mon..Sun, sums to 1). The UAE weekend is
# Saturday-Sunday (since Jan 2022; Friday-Saturday before), and showroom
# traffic concentrates on the weekend with a Thursday-evening lead-in.
RETAIL_DOW_WEIGHT = np.array([0.115, 0.115, 0.120, 0.130, 0.145, 0.190, 0.185])

# Car-loan APR the group's customers finance at: the policy rate plus a typical
# new-car spread for a blended prime / near-prime book (conventional + Islamic
# Murabaha profit rate quoted on the same basis).
AUTO_LOAN_SPREAD_PCT = 3.0
AUTO_LOAN_APR = CBUAE_RATE + AUTO_LOAN_SPREAD_PCT

# Distributor + dealer incentive spend as a share of transaction price. The UAE
# market is promotion-heavy (0% finance, free registration/insurance, service
# packages): high pre-COVID (~7.5%), collapsed during the 2021-22 chip shortage
# (~3%), rebuilt to ~8% by 2024-25.
INCENTIVE_PCT_ATP = _interp_series([
    (2019, 1, 7.5), (2020, 6, 9.0), (2021, 6, 5.5), (2021, 12, 3.5),
    (2022, 9, 3.0), (2023, 6, 5.5), (2024, 6, 7.5), (2025, 6, 8.0), (2026, 8, 8.2),
])

# New-vehicle days' supply on the group's lots. ~60 is healthy; the shortage
# years ran 22-30, then supply rebuilt to the 64-68 of 2024-25.
DAYS_SUPPLY = _interp_series([
    (2019, 1, 62), (2019, 12, 60), (2020, 5, 55), (2021, 6, 30),
    (2021, 12, 22), (2022, 9, 28), (2023, 6, 45), (2024, 3, 60),
    (2024, 12, 68), (2025, 9, 66), (2026, 8, 64),
])


def build_vehicle_catalog(rng, n_trims=2):
    """
    Expand BRAND_CATALOG into one row per (model, trim).

    Specs come from the catalog table rather than random draws, so a Corolla
    cannot end up with 420 hp and a Land Cruiser cannot end up returning
    30 km/L. Only genuinely variable attributes (paint count, service contract)
    are randomised.
    """
    rows = []
    vid = 1
    for brand, (_share, models) in BRAND_CATALOG.items():
        trims = BRAND_TRIMS[brand][:n_trims]
        for (model, category, fuel, price, hp, cc, kmpl, rng_km,
             seats, drive, resid36, intro_year) in models:
            is_ev = fuel == "Electric"
            for ti, trim in enumerate(trims):
                trim_price = int(round(price * TRIM_PRICE_MULT[ti] / 500.0) * 500)
                trim_hp = int(round(hp * TRIM_HP_MULT[ti]))
                trim_kmpl = None if is_ev else max(6, kmpl + TRIM_KMPL_DELTA[ti])
                trim_range = None if not is_ev else int(round(rng_km * (1.0 - 0.02 * ti)))
                rows.append({
                    "vehicle_id": f"VH{vid:04d}",
                    "brand": brand,
                    "model": model,
                    "variant": trim,
                    "category": category,
                    "fuel_type": fuel,
                    "price_aed": trim_price,
                    "engine_cc": None if is_ev else cc,
                    "horsepower": trim_hp,
                    "mileage_kmpl": trim_kmpl,
                    "range_km": trim_range,
                    "seating_capacity": seats,
                    "transmission": "Single-Speed" if is_ev else "Automatic",
                    "drive_type": drive,
                    "body_color_options": int(rng.integers(5, 9)),
                    "safety_rating": 5 if resid36 >= 0.55 else int(rng.choice([4, 5], p=[0.35, 0.65])),
                    "launch_year": intro_year,
                    "is_active": True,
                    "warranty_years": BRAND_WARRANTY_YEARS.get(brand, 3),
                    "service_contract_available": bool(rng.random() < 0.6),
                    # GCC-spec: built for Gulf heat (larger cooling, higher-temp
                    # tyres, sand filters). The group sells GCC-spec almost
                    # exclusively; a thin tail of grey-import / American-spec
                    # stock is modelled as False.
                    "gcc_spec": bool(rng.random() < 0.94),
                    # Not persisted to the DB — carried through generation so
                    # the lease book can price residuals per trim.
                    "_residual_36mo": resid36,
                })
                vid += 1
    return pd.DataFrame(rows)


# Residual curves are quoted at 36 months; shorter terms leave more value on
# the car, longer terms less.
LEASE_TERM_RESIDUAL_ADJ = {24: +0.10, 36: 0.00, 39: -0.02, 48: -0.10}
LEASE_TERMS = [24, 36, 39, 48]
LEASE_TERM_WEIGHTS = [0.16, 0.60, 0.12, 0.12]
LEASE_ANNUAL_KM = [15000, 20000, 25000]
LEASE_KM_WEIGHTS = [0.30, 0.50, 0.20]

# Lease penetration by segment. UAE retail leasing is far lighter than the US
# (most personal buyers finance or pay cash; leasing is mostly a corporate /
# fleet product), so these run roughly half the US rates and blend to ~10%.
LEASE_RATE_BY_CATEGORY = {
    "Luxury": 0.22, "Coupe": 0.12, "Sedan": 0.10, "SUV": 0.10,
    "Hatchback": 0.09, "Minivan": 0.08, "Pickup": 0.05,
}

# Slow-turning segments attract larger over-allowances, because that is where
# the store has to buy the deal to move the unit.
TRADE_OVER_ALLOWANCE_MULT = {
    "Sedan": 1.45, "Hatchback": 1.40, "Coupe": 1.25, "Minivan": 1.15,
    "SUV": 1.00, "Luxury": 1.10, "Pickup": 0.80,
}


DEALER_TEMPLATES = [
    "{brand} {city}", "{city} {brand}", "Al Futtaim {brand} {city}",
    "{brand} Showroom {city}", "Premier {brand} {city}", "{brand} Emirates {city}",
    "Gulf {brand} {city}", "{brand} Centre {city}",
]

DEALER_STREETS = [
    "Sheikh Zayed Road", "Airport Road", "Al Ittihad Road", "Maliya Street",
    "Industrial Area", "Corniche Road", "Emirates Road", "Al Wahda Street",
]


def _distribute_by_weight(total, weights):
    """Split `total` integer units across buckets in proportion to `weights`
    using the largest-remainder method, so the parts always sum back to total."""
    weights = np.asarray(weights, dtype=float)
    weights = weights / weights.sum()
    raw = weights * total
    base = np.floor(raw).astype(int)
    remainder = total - base.sum()
    if remainder > 0:
        order = np.argsort(-(raw - base))
        base[order[:remainder]] += 1
    return base


def _group_brand_portfolio(rng, n_rooftops):
    """
    Pick the set of franchises a single dealer *group* operates.

    A real dealer group is not a market sample — it carries a deliberate,
    coherent portfolio of franchises, weighted toward the high-volume mainstream
    brands, with every brand it sells backed by at least one rooftop so a
    customer buying that brand always has a store to buy it from.
    """
    picks = list(rng.choice(BRAND_NAMES, size=n_rooftops, p=BRAND_WEIGHTS))
    missing = [b for b in BRAND_NAMES if b not in picks]
    if missing:
        from collections import Counter
        for b in missing:
            counts = Counter(picks)
            donor = max(counts, key=lambda k: (counts[k], k))
            if counts[donor] <= 1:
                break
            picks[picks.index(donor)] = b
    rng.shuffle(picks)
    return picks


def build_dealers(rng, n_rooftops=None, dealers_per_emirate=None):
    """
    Build the dealer network.

    - `n_rooftops` (dealer-group mode): a single group of that many rooftops,
      spread across emirates in proportion to market size, each rooftop a single
      coherent franchise, sales targets filled in later from actual volume.
    - `dealers_per_emirate` (legacy/market mode): an even grid of independent
      dealers, kept for the larger "test" dataset.
    """
    rows = []
    did = 1

    if n_rooftops is not None:
        per_emirate = _distribute_by_weight(n_rooftops, EMIRATE_WEIGHTS)
        brands = _group_brand_portfolio(rng, n_rooftops)
        bi = 0
        for em, k in zip(EMIRATES, per_emirate):
            for _ in range(int(k)):
                brand = brands[bi]; bi += 1
                area, lat, lon = em["areas"][rng.integers(0, len(em["areas"]))]
                name = f"{brand} {area}"
                tier = rng.choice(["Platinum", "Gold", "Silver"], p=[0.25, 0.50, 0.25])
                rows.append({
                    "dealer_id": f"DLR{did:04d}", "dealer_name": name, "brand": brand,
                    "emirate": em["name"], "area": area,
                    "address": f"{rng.choice(['Showroom','Auto Mall','Motor City'])}, {rng.choice(DEALER_STREETS)}",
                    "po_box": f"P.O. Box {int(rng.integers(1000, 99999))}",
                    "tier": tier,
                    "established_year": int(rng.integers(1990, 2018)),
                    "monthly_capacity": int(rng.integers(120, 420)),
                    "showroom_area_sqft": int(rng.integers(14000, 52000)),
                    "service_center": bool(rng.random() < 0.95),
                    "ev_charging_station": bool(rng.random() < (0.85 if brand in ("MG", "Hyundai", "Kia", "BMW") else 0.45)),
                    "num_salespeople": int(rng.integers(14, 46)),
                    "annual_target_units": 0,  # filled from trailing-12-month actuals in generate_dataset()
                    "performance_score": round(float(rng.uniform(62, 96)), 1),
                    "google_rating": round(float(rng.uniform(3.9, 4.9)), 1),
                    "latitude": round(lat + rng.uniform(-0.05, 0.05), 5),
                    "longitude": round(lon + rng.uniform(-0.05, 0.05), 5),
                })
                did += 1
        return pd.DataFrame(rows)

    # ── legacy even-grid market mode ────────────────────────────────────────
    for em in EMIRATES:
        for _ in range(dealers_per_emirate):
            brand = rng.choice(BRAND_NAMES, p=BRAND_WEIGHTS)
            area, lat, lon = em["areas"][rng.integers(0, len(em["areas"]))]
            template = rng.choice(DEALER_TEMPLATES)
            name = template.format(brand=brand, city=area)
            tier = rng.choice(["Platinum", "Gold", "Silver"], p=[0.15, 0.45, 0.40])
            rows.append({
                "dealer_id": f"DLR{did:04d}", "dealer_name": name, "brand": brand,
                "emirate": em["name"], "area": area,
                "address": f"{rng.choice(['Showroom','Auto Mall','Motor City','Trade Centre'])}, {rng.choice(DEALER_STREETS)}",
                "po_box": f"P.O. Box {int(rng.integers(1000, 99999))}",
                "tier": tier,
                "established_year": int(rng.integers(1988, 2018)),
                "monthly_capacity": int(rng.integers(80, 600)),
                "showroom_area_sqft": int(rng.integers(8000, 45000)),
                "service_center": bool(rng.random() < 0.85),
                "ev_charging_station": bool(rng.random() < (0.7 if brand in ("MG", "Hyundai", "Kia", "BMW") else 0.35)),
                "num_salespeople": int(rng.integers(5, 80)),
                "annual_target_units": int(rng.integers(400, 6000)),
                "performance_score": round(float(rng.uniform(55, 98)), 1),
                "google_rating": round(float(rng.uniform(3.4, 4.9)), 1),
                "latitude": round(lat + rng.uniform(-0.05, 0.05), 5),
                "longitude": round(lon + rng.uniform(-0.05, 0.05), 5),
            })
            did += 1
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Customer master
#
# The UAE resident population is ~88% expatriate, so `nationality` and length
# of residency are first-class demand and credit signals here. Income runs on a
# monthly basis (Gulf salary norm) and is tax-free. Credit is scored by Al
# Etihad Credit Bureau (AECB), range 300-900.
# ─────────────────────────────────────────────────────────────────────────────
NATIONALITIES = [
    ("Emirati", 11, "gulf"),      ("Indian", 27, "south_asian"),
    ("Pakistani", 12, "south_asian"), ("Bangladeshi", 7, "south_asian"),
    ("Filipino", 6, "seasia"),     ("Egyptian", 4, "arab"),
    ("Jordanian", 2, "arab"),      ("Lebanese", 2, "arab"),
    ("Syrian", 2, "arab"),         ("Sudanese", 1, "arab"),
    ("Other Arab", 4, "arab"),     ("British", 3, "western"),
    ("Other European", 3, "western"), ("American", 1, "western"),
    ("Sri Lankan", 3, "south_asian"), ("Nepali", 2, "south_asian"),
    ("Other African", 2, "african"), ("Other Asian", 3, "seasia"),
]
NAT_NAMES = [n for n, _, _ in NATIONALITIES]
NAT_WEIGHTS = np.array([w for _, w, _ in NATIONALITIES], dtype=float)
NAT_WEIGHTS = NAT_WEIGHTS / NAT_WEIGHTS.sum()
NAT_GROUP = {n: g for n, _, g in NATIONALITIES}

# Relative income multiplier by nationality — reflects the real earnings
# structure of the UAE resident population (Emirati + Western households at the
# top, some labour-supplying nationalities well below the mean). This is what
# makes `nationality` a genuine segmentation feature rather than noise.
NAT_INCOME_MULT = {
    "Emirati": 1.95, "British": 1.75, "Other European": 1.65, "American": 1.80,
    "Lebanese": 1.15, "Jordanian": 1.10, "Egyptian": 0.90, "Syrian": 0.85,
    "Other Arab": 0.95, "Sudanese": 0.65, "Indian": 0.95, "Pakistani": 0.72,
    "Bangladeshi": 0.52, "Sri Lankan": 0.55, "Nepali": 0.52,
    "Filipino": 0.78, "Other African": 0.62, "Other Asian": 0.75,
}

NAME_POOLS = {
    "gulf": (
        ["Mohammed", "Ahmed", "Ali", "Khalid", "Saeed", "Sultan", "Hamdan", "Rashid",
         "Fatima", "Maryam", "Aisha", "Noora", "Shamma", "Alia", "Hessa", "Latifa"],
        ["Al Maktoum", "Al Nahyan", "Al Marri", "Al Mansoori", "Al Shamsi", "Al Zaabi",
         "Al Hammadi", "Al Falasi", "Al Suwaidi", "Al Ketbi"],
    ),
    "arab": (
        ["Omar", "Youssef", "Karim", "Tarek", "Hassan", "Nabil", "Sami", "Fadi",
         "Layla", "Rana", "Dina", "Nour", "Hala", "Yasmin", "Maha", "Rania"],
        ["Haddad", "Khoury", "Mansour", "Nasser", "Saleh", "Ibrahim", "Darwish",
         "Aziz", "Farah", "Hijazi"],
    ),
    "south_asian": (
        ["Rahul", "Arjun", "Vikram", "Imran", "Bilal", "Faisal", "Suresh", "Anand",
         "Priya", "Anjali", "Sana", "Ayesha", "Deepa", "Kavya", "Fatima", "Nadia"],
        ["Sharma", "Patel", "Khan", "Kumar", "Nair", "Reddy", "Iqbal", "Hussain",
         "Menon", "Chowdhury", "Rahman", "Perera", "Fernando", "Thapa"],
    ),
    "seasia": (
        ["Jose", "Mark", "John", "Michael", "Nathaniel", "Rex", "Emmanuel", "Ferdinand",
         "Maria", "Grace", "Jenny", "Rowena", "Cristina", "Angel", "Divine", "Rose"],
        ["Santos", "Reyes", "Cruz", "Bautista", "Garcia", "Mendoza", "Torres",
         "Aquino", "Dela Cruz", "Ramos"],
    ),
    "western": (
        ["James", "William", "Oliver", "Jack", "Thomas", "Daniel", "Alexander", "Henry",
         "Emma", "Olivia", "Sophie", "Charlotte", "Emily", "Hannah", "Grace", "Chloe"],
        ["Smith", "Jones", "Brown", "Wilson", "Taylor", "Davies", "Evans", "Walker",
         "Clarke", "Robinson", "Schmidt", "Muller", "Johnson"],
    ),
    "african": (
        ["Emeka", "Kwame", "Tunde", "Chidi", "Kofi", "Femi", "Sipho", "Musa",
         "Amara", "Zainab", "Ngozi", "Aminata", "Fatoumata", "Halima", "Chioma", "Yaa"],
        ["Okafor", "Mensah", "Adeyemi", "Diallo", "Bello", "Nkosi", "Traore",
         "Osei", "Abubakar", "Kamara"],
    ),
}

OCCUPATIONS = ["Salaried Professional", "Self-Employed", "Business Owner", "Government Employee",
               "Free Zone Employee", "Public Sector", "Retired", "Contract Worker"]
# Monthly income brackets, AED (tax-free). Gulf salary convention.
INCOME_BRACKETS = ["<5K", "5K-15K", "15K-30K", "30K-60K", ">60K"]
BRACKET_MID_MONTHLY = {0: 4000, 1: 9500, 2: 21000, 3: 42000, 4: 85000}


def build_customers(rng, n, start, end):
    idx = np.arange(1, n + 1)
    customer_id = [f"CUS{i:06d}" for i in idx]

    nat_idx = rng.choice(len(NATIONALITIES), size=n, p=NAT_WEIGHTS)
    nationality = np.array([NAT_NAMES[i] for i in nat_idx])
    groups = np.array([NATIONALITIES[i][2] for i in nat_idx])

    first, last = [], []
    for g in groups:
        fp, lp = NAME_POOLS[g]
        first.append(fp[rng.integers(0, len(fp))])
        last.append(lp[rng.integers(0, len(lp))])
    name = [f"{f} {l}" for f, l in zip(first, last)]

    age = np.clip(rng.normal(39, 11, n), 20, 72).astype(int)
    gender = rng.choice(["Male", "Female", "Other"], size=n, p=[0.62, 0.36, 0.02])

    emirate_idx = rng.choice(len(EMIRATES), size=n, p=EMIRATE_WEIGHTS)
    emirate = [EMIRATES[i]["name"] for i in emirate_idx]
    area = [EMIRATES[i]["areas"][rng.integers(0, len(EMIRATES[i]["areas"]))][0] for i in emirate_idx]

    occupation = rng.choice(OCCUPATIONS, size=n)

    # Income: a base monthly draw shaped by nationality, mapped to a bracket.
    nat_mult = np.array([NAT_INCOME_MULT[nn] for nn in nationality])
    base_income = np.clip(rng.lognormal(np.log(9000), 0.62, n) * nat_mult, 2200, 400000)
    est_income_monthly = base_income.round(0)
    income_bracket_idx = np.digitize(est_income_monthly, [5000, 15000, 30000, 60000])
    income_bracket = [INCOME_BRACKETS[i] for i in income_bracket_idx]

    # AECB credit score, 300-900. Higher and tighter for longer-tenured and
    # higher-income residents; a prospect-inclusive spread overall.
    credit_base = 620 + 0.6 * (est_income_monthly / 1000).clip(0, 120) + rng.normal(0, 70, n)
    credit_score = np.clip(credit_base, 300, 900).astype(int)

    years_in_uae = np.clip(rng.exponential(6, n), 0, 40).astype(int)
    number_of_past_purchases = rng.poisson(1.1, n)   # placeholder, rewritten from sales

    preferred_fuel = rng.choice(["Petrol", "Hybrid", "Electric", "Diesel"], size=n, p=[0.82, 0.09, 0.08, 0.01])
    preferred_category = rng.choice(["SUV", "Sedan", "Pickup", "Hatchback", "Minivan", "Luxury", "Coupe"], size=n,
                                    p=[0.50, 0.28, 0.06, 0.04, 0.02, 0.07, 0.03])

    loyalty_score = np.clip(rng.normal(50, 22, n), 0, 100)          # placeholder
    marketing_response = np.clip(rng.normal(5, 2.2, n), 0, 10)      # placeholder
    lead_source = rng.choice(["Online Ad", "Referral", "Dealer Walk-in", "Search Engine", "Social Media", "Marketplace Portal"], size=n)
    email_opt_in = rng.random(n) < 0.62
    test_drive_taken = rng.random(n) < 0.55
    emi_preferred = rng.random(n) < 0.55
    down_payment_capacity = np.clip(est_income_monthly * rng.uniform(2.5, 6.0, n), 3000, None).astype(int)

    days_range = (end - start).days
    reg_offset = rng.integers(0, days_range, n)
    registration_date = [start + pd.Timedelta(days=int(o)) for o in reg_offset]
    activity_offset = [rng.integers(0, max((end - rd).days, 1)) for rd in registration_date]
    last_activity_date = [rd + pd.Timedelta(days=int(o)) for rd, o in zip(registration_date, activity_offset)]
    churn_risk = np.clip(rng.beta(2, 5, n), 0, 1)

    return pd.DataFrame({
        "customer_id": customer_id, "name": name, "age": age, "gender": gender,
        "nationality": nationality, "emirate": emirate, "area": area,
        "occupation": occupation, "monthly_income_bracket": income_bracket,
        "estimated_monthly_income_aed": est_income_monthly, "credit_score": credit_score,
        "years_in_uae": years_in_uae, "number_of_past_purchases": number_of_past_purchases,
        "preferred_fuel_type": preferred_fuel, "preferred_vehicle_category": preferred_category,
        "customer_segment": "Unclassified", "loyalty_score": loyalty_score.round(2),
        "marketing_response_score": marketing_response.round(2), "lead_source": lead_source,
        "email_opt_in": email_opt_in, "test_drive_taken": test_drive_taken, "emi_preferred": emi_preferred,
        "down_payment_capacity_aed": down_payment_capacity,
        "registration_date": registration_date,
        "last_activity_date": last_activity_date,
        "churn_risk_score": churn_risk.round(3),
    })


def build_external_factors(rng):
    rows = []
    for mi in range(N_MONTHS):
        y, m = int(YEAR_OF[mi]), int(MONTH_OF[mi])
        for em in EMIRATES:
            ev_stations = int(EV_STATIONS_NATIONAL[mi] * em["ev_index"] * (em["weight"] / 100) * 6)
            rows.append({
                "date": date(y, m, 1), "year": y, "month": m, "quarter": f"Q{(m - 1) // 3 + 1}",
                "emirate": em["name"],
                "petrol_95_price_aed_per_litre": round(float(PETROL_95[mi] + rng.uniform(-0.02, 0.02)), 3),
                "petrol_98_price_aed_per_litre": round(float(PETROL_95[mi] * 1.05 + 0.06 + rng.uniform(-0.02, 0.02)), 3),
                "diesel_price_aed_per_litre": round(float(DIESEL_PRICE[mi] + rng.uniform(-0.02, 0.02)), 3),
                "crude_oil_price_usd": round(float(BRENT_CRUDE[mi] + rng.uniform(-2, 2)), 2),
                "gdp_growth_pct": round(float(GDP_GROWTH[mi] + rng.uniform(-0.2, 0.2)), 2),
                "cpi_inflation_pct": round(float(CPI_INFLATION[mi] + rng.uniform(-0.15, 0.15)), 2),
                "cbuae_rate_pct": round(float(CBUAE_RATE[mi]), 2),
                "auto_loan_apr_pct": round(float(AUTO_LOAN_APR[mi]), 2),
                "incentive_pct_of_atp": round(float(INCENTIVE_PCT_ATP[mi]), 2),
                "inventory_days_supply": round(float(DAYS_SUPPLY[mi]), 1),
                "consumer_confidence_index": round(float(CONSUMER_CONF[mi] + rng.uniform(-3, 3)), 1),
                "tourism_index": round(float(TOURISM_IDX[mi] + rng.uniform(-3, 3)), 1),
                "dubai_re_price_index": round(float(DUBAI_RE_IDX[mi] * (0.80 + em["weight"] / 90) + rng.uniform(-2, 2)), 1),
                "luxury_demand_index": round(float(LUXURY_DEMAND_IDX[mi] + rng.uniform(-3, 3)), 1),
                "ramadan_month": int(RAMADAN_MONTH[mi]), "national_day_month": int(NATIONAL_DAY_MONTH[mi]),
                "dubai_motor_show_month": int(MOTOR_SHOW_MONTH[mi]), "dsf_month": int(DSF_MONTH[mi]),
                "new_model_launches": int(NEW_MODEL_LAUNCHES[mi]),
                "import_duty_pct": float(IMPORT_DUTY_PCT[mi]), "vat_rate_pct": VAT_RATE_PCT,
                "unemployment_rate_pct": round(float(UNEMPLOYMENT[mi] + rng.uniform(-0.15, 0.15)), 2),
                "population_millions": em["pop_m"],
                "ev_charging_stations_uae": ev_stations,
            })
    return pd.DataFrame(rows)


def build_sales(rng, n, vehicles_df, dealers_df, customers_df, start, end):
    days_range = (end - start).days

    # ── Monthly volume shape ───────────────────────────────────────────────
    # Three layers: (1) a year-level base — the COVID dip and the recovery,
    # (2) the UAE new-vehicle retail seasonal curve, (3) the group's response
    # to conditions its customers actually feel. The macro response is
    # mean-normalised, so it moves WHICH months book deals without changing the
    # group's annual totals.
    #   pump price  ~ -3% units per +1 AED/litre
    #   loan APR    ~ -3% units per +1pt
    #   incentives  ~ +2% units per +1pt of transaction price
    #   scarcity    :  below ~45 days' supply, unfillable demand walks
    petrol_e = -0.03 * (PETROL_95 - 2.70)
    apr_e = -0.03 * (AUTO_LOAN_APR - 7.00)
    inc_e = 0.02 * (INCENTIVE_PCT_ATP - 5.50)
    macro_mult = np.clip(1.0 + petrol_e + apr_e + inc_e, 0.85, 1.15)
    scarcity = np.clip(0.70 + DAYS_SUPPLY / 120.0, 0.82, 1.0)
    macro_mult = macro_mult * scarcity
    macro_mult = macro_mult / macro_mult.mean()

    YEAR_BASE = {2019: 1.0, 2020: 0.72, 2021: 0.94, 2022: 1.02,
                 2023: 1.12, 2024: 1.20, 2025: 1.18, 2026: 1.15}
    month_weight = np.array([
        YEAR_BASE[int(YEAR_OF[mi])]
        * RETAIL_SEASONAL_FACTOR[int(MONTH_OF[mi])]
        * macro_mult[mi]
        for mi in range(N_MONTHS)
    ])
    month_p = month_weight / month_weight.sum()
    sale_month_idx = rng.choice(N_MONTHS, size=n, p=month_p)

    day_in_month = np.empty(n, dtype=int)
    for mi in np.unique(sale_month_idx):
        y, m = int(YEAR_OF[mi]), int(MONTH_OF[mi])
        days = np.arange(1, calendar.monthrange(y, m)[1] + 1)
        wd = np.array([date(y, m, int(d)).weekday() for d in days])
        p = RETAIL_DOW_WEIGHT[wd]
        p = p / p.sum()
        sel = sale_month_idx == mi
        day_in_month[sel] = rng.choice(days, size=int(sel.sum()), p=p)
    sale_date = [date(int(YEAR_OF[mi]), int(MONTH_OF[mi]), int(d)) for mi, d in zip(sale_month_idx, day_in_month)]

    brand_choice = rng.choice(BRAND_NAMES, size=n, p=BRAND_WEIGHTS)
    sale_year = YEAR_OF[sale_month_idx].astype(int)
    sale_mo = MONTH_OF[sale_month_idx].astype(int)

    # ── Fuel-mix control ──────────────────────────────────────────────────
    # The catalog is EV-dense relative to the UAE market, so uniform model
    # selection over-states EV share. Weight model choice by fuel type; the EV
    # weight follows the real UAE adoption curve — a trickle to 2021, a steep
    # 2023-2025 ramp as Dubai/Abu Dhabi policy and Chinese-brand pricing land.
    # There is no federal purchase credit to expire, so the curve does not step
    # down. Hybrids are catalog-thin, so they carry a boost.
    EV_WEIGHT_BY_YEAR = {2019: 0.20, 2020: 0.30, 2021: 0.55, 2022: 1.10,
                         2023: 1.90, 2024: 2.80, 2025: 3.40, 2026: 3.30}
    HYBRID_WEIGHT = 2.2

    veh_by_brand = {b: vehicles_df[vehicles_df["brand"] == b].reset_index(drop=True) for b in BRAND_NAMES}
    brand_fuel = {b: veh_by_brand[b]["fuel_type"].to_numpy() for b in BRAND_NAMES}
    brand_cat = {b: veh_by_brand[b]["category"].to_numpy() for b in BRAND_NAMES}
    brand_pop = {
        b: np.array([MODEL_TIER_WEIGHT.get(m, 1.0) for m in veh_by_brand[b]["model"]], dtype=float)
        for b in BRAND_NAMES
    }
    vehicle_rows = []
    for b, yr, mo in zip(brand_choice, sale_year, sale_mo):
        pool = veh_by_brand[b]
        fuels = brand_fuel[b]
        cats = brand_cat[b]
        w = brand_pop[b].copy()
        w[fuels == "Electric"] *= EV_WEIGHT_BY_YEAR.get(int(yr), 1.0)
        w[fuels == "Hybrid"] *= HYBRID_WEIGHT
        if mo == 12:
            # December: National Day + year-end 4x4 / luxury surge.
            w[cats == "SUV"] *= 1.15
            w[cats == "Luxury"] *= 1.30
        w /= w.sum()
        vehicle_rows.append(pool.iloc[int(rng.choice(len(pool), p=w))])
    veh_df_sel = pd.DataFrame(vehicle_rows).reset_index(drop=True)

    # ── Route each sale to a store that actually franchises the brand ──────
    # Demand arises in an emirate (weighted by market size), but the customer
    # buys from one of the group's rooftops that carries that brand — preferring
    # a store in their own emirate, otherwise the nearest one the group
    # operates. The sale is booked at that store, so emirate/area on the sale is
    # the STORE's location (where revenue lands), not the shopper's home area.
    emirate_name_to_idx = {e["name"]: i for i, e in enumerate(EMIRATES)}
    dealers_by_brand = {b: dealers_df[dealers_df["brand"] == b] for b in BRAND_NAMES}
    dealers_by_brand_emirate = {}
    for b in BRAND_NAMES:
        for em in EMIRATE_NAMES:
            sub = dealers_df[(dealers_df["brand"] == b) & (dealers_df["emirate"] == em)]
            if len(sub):
                dealers_by_brand_emirate[(b, em)] = sub

    dealer_emirate = dict(zip(dealers_df["dealer_id"], dealers_df["emirate"]))
    dealer_area = dict(zip(dealers_df["dealer_id"], dealers_df["area"]))
    pref_emirate_idx = rng.choice(len(EMIRATES), size=n, p=EMIRATE_WEIGHTS)
    dealer_ids = []
    for b, psi in zip(brand_choice, pref_emirate_idx):
        pool = dealers_by_brand_emirate.get((b, EMIRATE_NAMES[psi]))
        if pool is None or len(pool) == 0:
            pool = dealers_by_brand.get(b)
        if pool is None or len(pool) == 0:
            pool = dealers_df
        dealer_ids.append(pool.iloc[int(rng.integers(0, len(pool)))]["dealer_id"])
    emirate = [dealer_emirate[d] for d in dealer_ids]
    area = [dealer_area[d] for d in dealer_ids]
    emirate_idx = np.array([emirate_name_to_idx[s] for s in emirate])
    emirate_arr = np.array(emirate)

    # ── Per-store sales effectiveness ────────────────────────────────────
    _elist = list(dealers_df["dealer_id"])
    _eff = rng.normal(0.0, 1.0, len(_elist))
    _eff = _eff - _eff.mean()
    _dealer_eff = dict(zip(_elist, _eff))
    eff_arr = np.array([_dealer_eff[d] for d in dealer_ids])

    # ── Attach a customer: chronological, with a realistic new-vs-returning
    # split ──────────────────────────────────────────────────────────────
    P_RETURNING = 0.52
    P_OUT_OF_EMIRATE = 0.28   # cross-emirate buying is common (Sharjah -> Dubai)
    MIN_REBUY_MONTHS = 22
    _cust_emirate = dict(zip(customers_df["customer_id"], customers_df["emirate"]))
    _fresh_by_emirate = {
        st: list(rng.permutation(
            customers_df.loc[customers_df["emirate"] == st, "customer_id"].to_numpy()
        ))
        for st in EMIRATE_NAMES
    }
    _fresh_any = list(rng.permutation(
        customers_df.loc[~customers_df["emirate"].isin(EMIRATE_NAMES), "customer_id"].to_numpy()
    ))
    _bought_month = {}
    _return_all = []
    _return_by_emirate = {st: [] for st in EMIRATE_NAMES}
    _want_return = rng.random(n) < P_RETURNING
    _travel = rng.random(n) < P_OUT_OF_EMIRATE
    _order = np.argsort(sale_month_idx, kind="stable")
    _sm = sale_month_idx.astype(int)
    customer_ids = np.empty(n, dtype=object)

    def _take_fresh(_st):
        q = _fresh_by_emirate.get(_st) if _st is not None else None
        if q:
            return q.pop()
        for _stx in EMIRATE_NAMES:
            if _fresh_by_emirate[_stx]:
                return _fresh_by_emirate[_stx].pop()
        return _fresh_any.pop() if _fresh_any else None

    for _i in _order:
        _cur_m = _sm[_i]
        _st = None if _travel[_i] else emirate_arr[_i]
        _picked = None
        if _want_return[_i] and len(_return_all) > 300:
            _pool = (_return_by_emirate.get(_st) or []) if _st is not None else _return_all
            if len(_pool) < 12:
                _pool = _return_all
            for _try in range(6):
                _cand = _pool[int(rng.integers(0, len(_pool)))]
                if _cur_m - _bought_month[_cand] >= MIN_REBUY_MONTHS:
                    _picked = _cand
                    break
        if _picked is None:
            _cid = _take_fresh(_st)
            if _cid is None:
                _picked = _return_all[int(rng.integers(0, len(_return_all)))]
            else:
                _picked = _cid
                _return_all.append(_cid)
                _cst = _cust_emirate.get(_cid)
                if _cst in _return_by_emirate:
                    _return_by_emirate[_cst].append(_cid)
        customer_ids[_i] = _picked
        _bought_month[_picked] = _cur_m

    _cust_ix = customers_df.set_index("customer_id")
    cust_credit = _cust_ix["credit_score"].reindex(customer_ids).to_numpy(dtype=float)
    cust_income_monthly = _cust_ix["estimated_monthly_income_aed"].reindex(customer_ids).to_numpy(dtype=float)

    # ── Price ────────────────────────────────────────────────────────────
    # Every vehicle is imported and every brand pays the same flat 5% GCC
    # customs duty, which has always been inside the retail price — so there is
    # no tariff step to model. base_price is the vehicle's list price; the only
    # thing that moves it is the month's discount environment.
    base_price = veh_df_sel["price_aed"].values.astype(float)

    incentive_at_sale = INCENTIVE_PCT_ATP[sale_month_idx]
    discount_pct = np.clip(rng.normal(incentive_at_sale, 2.6, n), 0, 18)
    selling_price = (base_price * (1 - discount_pct / 100)).round(0)

    # Federal VAT, flat 5%, on the vehicle selling price.
    vat_amount = (selling_price * (VAT_RATE_PCT / 100.0)).round(0)
    accessories_rev = np.clip(rng.normal(4200, 1600, n), 0, None).round(0)
    insurance_rev = np.clip(rng.normal(3800, 1400, n), 0, None).round(0)
    extended_warranty = np.where(rng.random(n) < 0.35, np.clip(rng.normal(5200, 1300, n), 0, None), 0).round(0)
    total_excl_vat = (selling_price + accessories_rev + insurance_rev + extended_warranty).round(0)
    total_incl_vat = (total_excl_vat + vat_amount).round(0)

    # ── Financing mix ────────────────────────────────────────────────────
    veh_category = veh_df_sel["category"].values
    veh_fuel = veh_df_sel["fuel_type"].values
    lease_p = np.array([LEASE_RATE_BY_CATEGORY.get(c, 0.09) for c in veh_category])
    lease_p = np.clip(lease_p + np.where(veh_fuel == "Electric", 0.06, 0.0), 0.03, 0.40)
    is_lease = rng.random(n) < lease_p
    non_lease = rng.choice(["Cash", "Bank Loan", "Islamic Finance", "Dealer Financing"],
                           size=n, p=[0.34, 0.30, 0.22, 0.14])
    financing_type = np.where(is_lease, "Lease", non_lease)
    loan_amount = np.where(financing_type == "Cash", 0, (selling_price * rng.uniform(0.6, 0.90, n)).round(0))

    # ── Lease contract terms ─────────────────────────────────────────────
    list_price = veh_df_sel["price_aed"].values.astype(float)
    lease_term = rng.choice(LEASE_TERMS, size=n, p=LEASE_TERM_WEIGHTS)
    annual_km = rng.choice(LEASE_ANNUAL_KM, size=n, p=LEASE_KM_WEIGHTS)

    resid_pct = veh_df_sel["_residual_36mo"].values.astype(float)
    resid_pct = resid_pct + np.array([LEASE_TERM_RESIDUAL_ADJ[t] for t in lease_term])
    resid_pct = resid_pct + np.select(
        [annual_km == 15000, annual_km == 25000], [0.02, -0.02], default=0.0
    )
    resid_pct = np.clip(resid_pct + rng.normal(0, 0.012, n), 0.25, 0.85)
    residual_aed = (list_price * resid_pct).round(0)

    lease_apr = np.clip(CBUAE_RATE[sale_month_idx] + rng.normal(3.2, 0.8, n), 1.0, 12.0)
    money_factor = lease_apr / 2400.0
    lease_payment = ((selling_price - residual_aed) / lease_term
                     + (selling_price + residual_aed) * money_factor).round(0)

    _sd = pd.to_datetime(sale_date)
    _tot = _sd.year * 12 + (_sd.month - 1) + lease_term
    maturity = pd.to_datetime(dict(year=_tot // 12, month=_tot % 12 + 1,
                                   day=np.minimum(_sd.day, 28)))

    _no_lease = ~is_lease
    lease_term_col = np.where(_no_lease, np.nan, lease_term)
    resid_pct_col = np.where(_no_lease, np.nan, resid_pct.round(4))
    resid_aed_col = np.where(_no_lease, np.nan, residual_aed)
    lease_payment_col = np.where(_no_lease, np.nan, lease_payment)
    mileage_allow_col = np.where(_no_lease, np.nan, annual_km * lease_term / 12.0)
    maturity_col = pd.Series(maturity).where(is_lease)

    # ── Trade-in activity ────────────────────────────────────────────────
    # UAE trade attach rate is lighter than the US — many sellers use
    # specialist used-car buyers or marketplace portals rather than trading in.
    trade_base = np.where(financing_type == "Cash", 0.28, 0.42)
    has_trade = rng.random(n) < trade_base

    trade_age = rng.choice([3, 4, 5, 6, 7, 8, 9, 10], size=n,
                           p=[0.13, 0.17, 0.17, 0.15, 0.13, 0.10, 0.08, 0.07])
    trade_year = YEAR_OF[sale_month_idx].astype(int) - trade_age
    trade_mileage = np.clip(
        (trade_age * rng.normal(17500, 3200, n)).round(-2), 10000, 320000
    ).astype(int)

    trade_pick = rng.integers(0, len(vehicles_df), n)
    trade_brand = vehicles_df["brand"].values[trade_pick]
    trade_model = vehicles_df["model"].values[trade_pick]
    trade_orig_price = vehicles_df["price_aed"].values[trade_pick].astype(float)

    # Desert heat + high annual km depreciate the Gulf used car a little harder:
    # ~22% off year one, ~13%/yr compounding after.
    dep_factor = 0.78 * np.power(0.87, np.maximum(trade_age - 1, 0))
    expected_km = np.maximum(trade_age * 17500, 1)
    excess_ratio = (trade_mileage - expected_km) / expected_km
    mileage_factor = np.clip(1.0 - 0.20 * excess_ratio, 0.70, 1.20)
    appraised = np.maximum(trade_orig_price * dep_factor * mileage_factor, 3000).round(0)

    over_mult = np.array([TRADE_OVER_ALLOWANCE_MULT.get(c, 1.0) for c in veh_category])
    over_allow = np.maximum(rng.normal(3200, 2400, n) * over_mult, 0).round(0)
    over_allow = np.where(rng.random(n) < 0.25, 0.0, over_allow)

    is_event = np.isin(MONTH_OF[sale_month_idx], [11, 12, 1])
    bonus_p = np.clip(0.18 + 0.22 * is_event + 0.12 * (over_mult > 1.0), 0, 0.75)
    trade_bonus = np.where(
        rng.random(n) < bonus_p,
        rng.choice([1500, 2500, 4000, 6000, 8000], size=n, p=[0.32, 0.26, 0.22, 0.13, 0.07]),
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

    marketing_channel = rng.choice(["Online Ad", "Referral", "Showroom Walk-in", "Search Engine",
                                    "Social Media", "Marketplace Portal", "TV/Radio"], size=n)

    # ── Test-drive → sale ────────────────────────────────────────────────
    _CHANNEL_CONV = {
        "Showroom Walk-in": 0.10, "Referral": 0.06, "Marketplace Portal": 0.00,
        "TV/Radio": 0.00, "Search Engine": -0.03, "Online Ad": -0.05,
        "Social Media": -0.06,
    }
    chan_eff = np.array([_CHANNEL_CONV[c] for c in marketing_channel])
    _credit = np.nan_to_num(cust_credit, nan=690.0)
    _income_annual = np.nan_to_num(cust_income_monthly, nan=9500.0) * 12.0
    pay_stress = np.clip((selling_price - 0.55 * _income_annual) / 300000.0, 0, None)
    conv_z = (
        0.07 * eff_arr
        + chan_eff
        + 0.012 * (discount_pct - incentive_at_sale)
        + 0.0011 * (_credit - 690.0)
        - 0.05 * pay_stress
        + 0.05 * has_trade.astype(float)
    )
    conv_p = 0.62 + conv_z
    conv_p = conv_p - conv_p.mean() + 0.62
    conv_p = np.clip(conv_p, 0.28, 0.93)
    test_drive_converted = rng.random(n) < conv_p

    lead_to_close_days = np.clip(
        rng.integers(1, 60, n)
        - (trade_bonus_col / 1200.0).round(0)
        - (3.5 * eff_arr).round(0)
        - (14.0 * (conv_p - 0.62)).round(0),
        1, 60,
    ).astype(int)
    salesperson_id = [f"SP{int(x):04d}" for x in rng.integers(1, 400, n)]
    season_multiplier = np.clip(rng.normal(1.0, 0.08, n), 0.75, 1.35)

    quarter = [f"Q{(int(MONTH_OF[mi]) - 1) // 3 + 1}" for mi in sale_month_idx]
    day_of_week = pd.to_datetime(sale_date).day_name()
    festival_period = [_festival_period(d) for d in sale_date]

    df = pd.DataFrame({
        "sale_id": [f"SAL{i:07d}" for i in range(1, n + 1)],
        "sale_date": sale_date, "year": YEAR_OF[sale_month_idx].astype(int), "month": MONTH_OF[sale_month_idx].astype(int),
        "quarter": quarter, "day_of_week": day_of_week, "festival_period": festival_period,
        "customer_id": customer_ids, "dealer_id": dealer_ids, "vehicle_id": veh_df_sel["vehicle_id"].values,
        "brand": veh_df_sel["brand"].values, "model": veh_df_sel["model"].values,
        "vehicle_category": veh_df_sel["category"].values, "fuel_type": veh_df_sel["fuel_type"].values,
        "emirate": emirate, "area": area,
        "base_price_aed": base_price.round(0).astype(int),
        "discount_pct": discount_pct.round(2),
        "selling_price_aed": selling_price.astype(int), "vat_amount_aed": vat_amount.astype(int),
        "accessories_revenue_aed": accessories_rev.astype(int), "insurance_revenue_aed": insurance_rev.astype(int),
        "extended_warranty_aed": extended_warranty.astype(int), "total_revenue_excl_vat": total_excl_vat.astype(int),
        "total_revenue_incl_vat": total_incl_vat.astype(int), "financing_type": financing_type,
        "loan_amount_aed": loan_amount.astype(int), "units_sold": 1, "test_drive_converted": test_drive_converted,
        "lead_to_close_days": lead_to_close_days, "salesperson_id": salesperson_id,
        "marketing_channel": marketing_channel, "season_multiplier": season_multiplier.round(3),
        # Lease contract terms (Lease rows only)
        "lease_term_months": lease_term_col,
        "lease_maturity_date": maturity_col.dt.date,
        "residual_value_pct": resid_pct_col,
        "residual_value_aed": resid_aed_col,
        "contract_mileage_allowance": mileage_allow_col,
        "lease_monthly_payment_aed": lease_payment_col,
        # Trade-in activity
        "trade_in_flag": trade_flag_col,
        "trade_in_brand": trade_brand_col,
        "trade_in_model": trade_model_col,
        "trade_in_year": trade_year_col,
        "trade_in_mileage": trade_mileage_col,
        "trade_in_appraised_value_aed": appraised_col,
        "trade_in_allowance_aed": allowance_col,
        "trade_in_over_allowance_aed": over_allow_col,
        "trade_bonus_aed": trade_bonus_col,
    })
    return df


WAREHOUSE_ZONES = ["Zone A", "Zone B", "Zone C", "Zone D"]
INVENTORY_HISTORY_MONTHS = 36


def build_inventory(rng, vehicles_df, dealers_df, sales_df):
    """
    Month-end stock snapshots for every (dealer, vehicle) the dealer actually
    franchises. Stock behaviour is derived rather than drawn at random:
      - turn rate follows the model's residual strength (desirable metal moves)
      - holding cost is floorplan interest on the actual list price
      - lead times split by the brand's shipping origin (all stock is imported)
    """
    months = MONTHS[-INVENTORY_HISTORY_MONTHS:]

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
        per_model_capacity = max(dealer["monthly_capacity"] / max(len(pool), 1), 2.0)
        origin = BRAND_ORIGIN_REGION.get(dealer["brand"], "Japan")
        lo, hi = ORIGIN_LEAD_DAYS.get(origin, (28, 45))

        for _, veh in pool.iterrows():
            resid = float(veh["_residual_36mo"])
            desirability = np.clip((resid - 0.38) / (0.72 - 0.38), 0.0, 1.0)
            base_days = 25.0 + (1.0 - desirability) * 85.0
            lead_time = int(rng.integers(lo, hi))

            floorplan_apr = 0.075
            holding_per_day = round(
                veh["price_aed"] * floorplan_apr / 365.0 + rng.uniform(8.0, 18.0), 2
            )

            observed_rate = rate_lookup.get((dealer["dealer_id"], veh["vehicle_id"]), 0.0)
            base_rate = max(observed_rate, per_model_capacity * 0.06)

            zone = WAREHOUSE_ZONES[inv_id % len(WAREHOUSE_ZONES)]
            port = rng.choice(IMPORT_PORTS)

            for mi, month_start in enumerate(months):
                month_no = month_start.month
                # Cooler-season selling strength (Q4/Q1), summer softness.
                seasonal = 1.0 + 0.18 * np.sin((month_no - 12) / 12 * 2 * np.pi)
                monthly_demand = max(base_rate * seasonal * rng.uniform(0.75, 1.3), 0.4)

                sold_30d = int(np.clip(rng.poisson(monthly_demand), 0, None))
                daily_demand = monthly_demand / 30.0

                days_supply_target = 28.0 + (1.0 - desirability) * 67.0
                fluctuation = float(np.clip(rng.normal(1.0, 0.30), 0.12, 2.1))
                stock = int(np.clip(round(daily_demand * days_supply_target * fluctuation), 0, 400))

                safety = 1.28 * np.sqrt(max(daily_demand, 0.01) * lead_time)
                reorder_pt = max(int(round(min(daily_demand * lead_time + safety,
                                               daily_demand * days_supply_target * 0.65))), 1)

                if desirability > 0.6 and rng.random() < 0.06:
                    stock = 0

                forecast_30d = int(max(round(monthly_demand * rng.uniform(0.9, 1.15)), 0))
                in_transit = int(rng.poisson(max(monthly_demand * 0.5, 0.3))) if rng.random() < 0.55 else 0
                units_ordered = int(rng.poisson(max(monthly_demand * 0.8, 0.5)))

                days_supply = float(np.clip(stock / max(daily_demand, 0.001), 0, 260))
                days_in_stock = int(np.clip(rng.normal(days_supply, 8), 1, 260))

                stockout = stock == 0
                overstock = days_supply > 90
                reorder_needed = (not stockout) and stock <= reorder_pt

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
                    "emirate": dealer["emirate"],
                    "area": dealer["area"],
                    "current_stock": stock,
                    "demand_forecast_30d": forecast_30d,
                    "reorder_point": reorder_pt,
                    "days_in_stock": days_in_stock,
                    "stockout_flag": bool(stockout),
                    "overstock_flag": bool(overstock),
                    "reorder_needed": bool(reorder_needed),
                    "stockout_risk_score": round(stockout_risk, 3),
                    "overstock_risk_score": round(overstock_risk, 3),
                    "holding_cost_per_day_aed": holding_per_day,
                    "estimated_holding_cost_aed": round(holding_per_day * stock * 30.0, 2),
                    "units_sold_last_30d": sold_30d,
                    "units_ordered": units_ordered,
                    "transit_stock": in_transit,
                    "port_of_entry": port,
                    "warehouse_zone": zone,
                    "last_replenishment_date": last_replen,
                    "supplier_lead_time_days": lead_time,
                    "customs_cleared": bool(rng.random() < 0.96),
                })
                inv_id += 1

    return pd.DataFrame(rows)


def _derive_customer_history(customers, sales, end):
    """
    Replace the decorative purchase-history fields with each customer's real
    behaviour in the sales table (identical logic to the NA build):
      number_of_past_purchases, last_activity_date, loyalty_score, churn_risk_score
    """
    end_ts = pd.Timestamp(end)
    sd = pd.to_datetime(sales["sale_date"])
    grp = sales.assign(_sd=sd).groupby("customer_id")["_sd"]
    deal_count = grp.size()
    last_deal = grp.max()

    cid = customers["customer_id"]
    n_deals = cid.map(deal_count).fillna(0).astype(int)

    gen_activity = pd.to_datetime(customers["last_activity_date"])
    last_deal_dt = cid.map(last_deal)
    combined = last_deal_dt.fillna(gen_activity)
    combined = pd.Series(
        np.maximum(combined.to_numpy("datetime64[ns]"),
                   gen_activity.to_numpy("datetime64[ns]")),
        index=customers.index,
    )
    recency_years = ((end_ts - combined).dt.days / 365.25).clip(lower=0)

    loyalty = np.clip(30 + 13 * n_deals - 7 * recency_years, 0, 100)
    base_churn = customers["churn_risk_score"].astype(float).to_numpy()
    churn = np.clip(0.6 * base_churn + 0.14 * recency_years - 0.04 * n_deals + 0.05, 0, 1)

    customers = customers.copy()
    customers["number_of_past_purchases"] = n_deals.to_numpy()
    customers["last_activity_date"] = combined.dt.date
    customers["loyalty_score"] = np.round(loyalty, 2)
    customers["churn_risk_score"] = np.round(churn, 3)
    return customers


def _fill_dealer_targets(dealers, sales, end):
    """Set annual_target_units from each store's own trailing-12-month volume
    plus a modest stretch, rounded to a round number a GM would be handed."""
    cutoff = pd.Timestamp(end) - pd.DateOffset(months=12)
    sd = pd.to_datetime(sales["sale_date"])
    last12 = sales.loc[sd >= cutoff].groupby("dealer_id")["units_sold"].sum()
    STRETCH = 1.05
    targets = {}
    for d in dealers["dealer_id"]:
        actual = float(last12.get(d, 0.0))
        t = max(actual * STRETCH, 180.0)
        targets[d] = int(round(t / 25.0) * 25)
    dealers["annual_target_units"] = dealers["dealer_id"].map(targets)
    return dealers


def generate_dataset(out_dir, seed, n_customers, n_sales, n_trims,
                     dealers_per_emirate=None, n_rooftops=None):
    rng = np.random.default_rng(seed)
    os.makedirs(out_dir, exist_ok=True)

    vehicles = build_vehicle_catalog(rng, n_trims=n_trims)
    dealers = build_dealers(rng, n_rooftops=n_rooftops, dealers_per_emirate=dealers_per_emirate)
    customers = build_customers(rng, n_customers, START, END)
    external_factors = build_external_factors(rng)
    sales = build_sales(rng, n_sales, vehicles, dealers, customers, START, END)
    customers = _derive_customer_history(customers, sales, END)
    if n_rooftops is not None:
        dealers = _fill_dealer_targets(dealers, sales, END)
    inventory = build_inventory(rng, vehicles, dealers, sales)

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
    # realdata-datasets: primary "real" mode dataset — ONE regional dealer group
    # of 24 rooftops across the seven emirates (not a market sample).
    generate_dataset(
        os.path.join(ROOT, "realdata-datasets"), seed=42,
        n_customers=70000, n_rooftops=24, n_sales=100000, n_trims=2,
    )
    # automobile_datasets: larger "test" mode dataset (legacy market grid)
    generate_dataset(
        os.path.join(ROOT, "automobile_datasets"), seed=7,
        n_customers=98000, dealers_per_emirate=15, n_sales=140000, n_trims=3,
    )


if __name__ == "__main__":
    main()
