"""
Generate synthetic German automobile demand datasets.

Replaces the UAE-modeled CSVs in automobile_datasets/ and realdata-datasets/
with data in the German schema (see database/models.py). All row generation is
seeded (numpy default_rng) for reproducibility.

The dataset models ONE regional dealer group of 24 rooftops trading across six
Bundesländer (NRW, Bayern, Baden-Württemberg, Hessen, Niedersachsen,
Rheinland-Pfalz) — not a national market model.

Structural differences from the UAE build that matter:
  - Germany has a large DOMESTIC industry. `Vehicle.origin` splits Domestic /
    Import, but only to drive logistics lead time — there is no tariff or
    duty analysis anywhere in this build.
  - Consumption is l/100km (LOWER IS BETTER). Every comparison on it runs the
    opposite direction to the UAE build's km-per-litre field.
  - ~62% of units go to COMMERCIAL buyers (gewerblich — fleet, Dienstwagen
    under the 1%-Regelung). Private retail is the minority here.
  - Showrooms cannot sell on Sundays (Ladenschlussgesetz), so the day-of-week
    curve has a hard Sunday floor.
  - Leasing and balloon financing dominate; cash is a minority.

Real-world anchors baked into the external-factor time series (for narrative /
demo authenticity, not precise historical accuracy):
  - ECB main refinancing rate 2019-2026 (zero until Jul 2022, the 2022-23
    hiking cycle to 4.50%, 2024-25 cuts)
  - German pump prices EUR/litre incl. the Tankrabatt window (Jun-Aug 2022)
    and the national CO2 price (nEHS) from 2021
  - German CPI (peak ~8.8% Oct 2022), GDP (-3.8% 2020, recession 2023/24),
    unemployment, GfK Konsumklima, ifo Geschäftsklimaindex
  - German residential price index — note it FALLS 2022-23, the inverse of
    the Dubai index in the UAE build
  - Umweltbonus BEV subsidy and its abrupt end in December 2023, which is the
    sharpest single demand shock in this window
  - German retail calendar: quarter-end registration pushes, year-end,
    Ostern, Sommerferien, IAA (Sep, biennial)

Run: python -m preprocessing.generate_de_data
"""

import os
import sys
import calendar
import numpy as np
import pandas as pd
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ─────────────────────────────────────────────────────────────────────────────
# Geography: a regional group across six Bundesländer.
#
# A 24-rooftop group spread over all 16 Länder would be unrealistically thin,
# so the footprint is the dense western/southern corridor where most German
# new-car retail actually sits. `ev_index` is a relative EV-readiness weight
# (charging density, household solar, local policy) — Baden-Württemberg and
# Bayern lead, the Ruhr trails.
#
# VAT is a single federal rate, so it is not carried per state.
# ─────────────────────────────────────────────────────────────────────────────
STATES = [
    {"name": "Nordrhein-Westfalen", "weight": 30, "ev_index": 0.88, "pop_m": 17.9,
     "cities": [("Köln", 50.9375, 6.9603, "50"), ("Düsseldorf", 51.2277, 6.7735, "40"),
                ("Dortmund", 51.5136, 7.4653, "44"), ("Essen", 51.4556, 7.0116, "45"),
                ("Duisburg", 51.4344, 6.7623, "47"), ("Bochum", 51.4818, 7.2162, "44")]},
    {"name": "Bayern", "weight": 22, "ev_index": 1.00, "pop_m": 13.2,
     "cities": [("München", 48.1351, 11.5820, "80"), ("Nürnberg", 49.4521, 11.0767, "90"),
                ("Augsburg", 48.3705, 10.8978, "86"), ("Regensburg", 49.0134, 12.1016, "93"),
                ("Ingolstadt", 48.7665, 11.4258, "85")]},
    {"name": "Baden-Württemberg", "weight": 18, "ev_index": 1.00, "pop_m": 11.3,
     "cities": [("Stuttgart", 48.7758, 9.1829, "70"), ("Karlsruhe", 49.0069, 8.4037, "76"),
                ("Mannheim", 49.4875, 8.4660, "68"), ("Freiburg", 47.9990, 7.8421, "79")]},
    {"name": "Hessen", "weight": 13, "ev_index": 0.92, "pop_m": 6.4,
     "cities": [("Frankfurt am Main", 50.1109, 8.6821, "60"), ("Wiesbaden", 50.0782, 8.2398, "65"),
                ("Kassel", 51.3127, 9.4797, "34"), ("Darmstadt", 49.8728, 8.6512, "64")]},
    {"name": "Niedersachsen", "weight": 11, "ev_index": 0.82, "pop_m": 8.1,
     "cities": [("Hannover", 52.3759, 9.7320, "30"), ("Braunschweig", 52.2689, 10.5268, "38"),
                ("Osnabrück", 52.2799, 8.0472, "49"), ("Wolfsburg", 52.4227, 10.7865, "38")]},
    {"name": "Rheinland-Pfalz", "weight": 6, "ev_index": 0.78, "pop_m": 4.1,
     "cities": [("Mainz", 49.9929, 8.2473, "55"), ("Ludwigshafen", 49.4774, 8.4452, "67"),
                ("Koblenz", 50.3569, 7.5890, "56")]},
]
STATE_NAMES = [s["name"] for s in STATES]
STATE_WEIGHTS = np.array([s["weight"] for s in STATES], dtype=float)
STATE_WEIGHTS = STATE_WEIGHTS / STATE_WEIGHTS.sum()

VAT_RATE_STANDARD = 19.0    # Umsatzsteuer
VAT_RATE_COVID_CUT = 16.0   # Konjunkturpaket: 1 Jul - 31 Dec 2020

# ─────────────────────────────────────────────────────────────────────────────
# Vehicle catalog — real German-market model specs.
#
# Specs come from the catalog rather than random draws, because the Placement
# Assistant matches substitutes on these attributes (a shopper cross-shops a
# Tiguan against a Kodiaq because the specs genuinely line up).
#
# Tuple layout:
#   (model, category, fuel, base_price_eur, power_kw, engine_cc,
#    l_per_100km, kwh_per_100km, range_km, co2_g_per_km, seats, drive_type,
#    residual_36mo, model_year_intro)
#
# Prices are Listenpreis incl. 19% USt, in the German convention.
# l_per_100km is None for BEV; kwh_per_100km / range_km are None for ICE.
# PHEV carries both (the l/100km being the flattering WLTP combined figure).
#
# residual_36mo = share of list price retained at 36-month maturity. German
# residuals are driven by brand desirability and segment, not by 4x4 body-on-
# frame durability as in the Gulf: premium German marques and Toyota hybrids
# hold hardest (0.50-0.56), volume brands sit mid (0.44-0.52), and BEVs plus
# Chinese brands depreciate hardest (0.34-0.43) — the post-Umweltbonus used-BEV
# collapse is real and is priced in here.
# ─────────────────────────────────────────────────────────────────────────────
BRAND_CATALOG = {
    "Volkswagen": (19, [
        ("Golf",            "Compact",   "Petrol",          32000, 110, 1498, 5.6,  None, None, 127, 5, "FWD", 0.52, 2020),
        ("Golf Variant",    "Estate",    "Diesel",          36000, 110, 1968, 4.8,  None, None, 126, 5, "FWD", 0.51, 2021),
        ("Golf GTI",        "Compact",   "Petrol",          45000, 195, 1984, 7.3,  None, None, 166, 5, "FWD", 0.56, 2021),
        ("T-Roc",           "SUV",       "Petrol",          31000, 110, 1498, 6.2,  None, None, 141, 5, "FWD", 0.54, 2022),
        ("T-Cross",         "SUV",       "Petrol",          26000,  85,  999, 5.8,  None, None, 132, 5, "FWD", 0.50, 2022),
        ("Tiguan",          "SUV",       "Petrol",          40000, 110, 1498, 6.5,  None, None, 148, 5, "FWD", 0.55, 2024),
        ("Tiguan eHybrid",  "SUV",       "Plug-in Hybrid",  48000, 150, 1395, 1.4,  None, None,  32, 5, "FWD", 0.50, 2024),
        ("Passat Variant",  "Estate",    "Diesel",          45000, 110, 1968, 5.2,  None, None, 137, 5, "FWD", 0.50, 2024),
        ("Polo",            "Small Car", "Petrol",          22000,  70,  999, 5.4,  None, None, 123, 5, "FWD", 0.50, 2021),
        ("ID.3",            "Compact",   "Electric",        37000, 150, None, None, 15.8,  429,   0, 5, "RWD", 0.42, 2023),
        ("ID.4",            "SUV",       "Electric",        45000, 150, None, None, 16.9,  522,   0, 5, "RWD", 0.43, 2022),
        ("Touran",          "Van",       "Diesel",          38000, 110, 1968, 5.4,  None, None, 142, 7, "FWD", 0.48, 2019),
        ("Caddy",           "Van",       "Diesel",          32000,  90, 1968, 5.6,  None, None, 147, 5, "FWD", 0.49, 2021),
    ]),
    "Mercedes-Benz": (9.5, [
        ("A-Klasse",          "Compact", "Petrol",   36000, 120, 1332, 5.9,  None, None, 134, 5, "FWD", 0.48, 2023),
        ("C-Klasse",          "Sedan",   "Petrol",   52000, 150, 1496, 6.5,  None, None, 148, 5, "RWD", 0.50, 2022),
        ("C-Klasse T-Modell", "Estate",  "Diesel",   55000, 147, 1993, 4.9,  None, None, 129, 5, "RWD", 0.51, 2022),
        ("GLA",               "SUV",     "Petrol",   43000, 120, 1332, 6.4,  None, None, 146, 5, "FWD", 0.50, 2023),
        ("GLC",               "SUV",     "Diesel",   62000, 145, 1993, 5.5,  None, None, 145, 5, "AWD", 0.55, 2023),
        ("E-Klasse",          "Luxury",  "Diesel",   62000, 145, 1993, 5.1,  None, None, 134, 5, "RWD", 0.47, 2024),
        ("S-Klasse",          "Luxury",  "Petrol",  115000, 270, 2999, 8.0,  None, None, 182, 5, "AWD", 0.44, 2021),
        ("EQA",               "SUV",     "Electric", 51000, 140, None, None, 16.5,  486,   0, 5, "FWD", 0.40, 2021),
        ("V-Klasse",          "Van",     "Diesel",   62000, 140, 1950, 6.8,  None, None, 178, 8, "RWD", 0.52, 2020),
    ]),
    "BMW": (9, [
        ("1er",         "Compact", "Petrol",   36000, 115, 1499, 6.0,  None, None, 136, 5, "FWD", 0.48, 2024),
        ("3er",         "Sedan",   "Diesel",   52000, 140, 1995, 4.9,  None, None, 128, 5, "RWD", 0.50, 2022),
        ("3er Touring", "Estate",  "Diesel",   54000, 140, 1995, 5.1,  None, None, 133, 5, "RWD", 0.51, 2022),
        ("X1",          "SUV",     "Petrol",   46000, 125, 1499, 6.3,  None, None, 143, 5, "AWD", 0.53, 2023),
        ("X3",          "SUV",     "Diesel",   62000, 145, 1995, 5.6,  None, None, 147, 5, "AWD", 0.54, 2024),
        ("5er",         "Luxury",  "Diesel",   68000, 145, 1995, 5.3,  None, None, 139, 5, "RWD", 0.46, 2024),
        ("X5",          "Luxury",  "Diesel",   85000, 220, 2993, 6.4,  None, None, 168, 5, "AWD", 0.50, 2019),
        ("i4",          "Sedan",   "Electric", 58000, 250, None, None, 16.1,  493,   0, 5, "RWD", 0.43, 2022),
        ("iX1",         "SUV",     "Electric", 55000, 230, None, None, 17.0,  440,   0, 5, "AWD", 0.42, 2023),
    ]),
    "Audi": (8, [
        ("A1",           "Small Car", "Petrol",   27000,  85,  999, 5.6,  None, None, 127, 5, "FWD", 0.48, 2019),
        ("A3 Sportback", "Compact",   "Petrol",   36000, 110, 1498, 5.5,  None, None, 125, 5, "FWD", 0.50, 2021),
        ("A4 Avant",     "Estate",    "Diesel",   50000, 120, 1968, 4.9,  None, None, 129, 5, "FWD", 0.49, 2020),
        ("A6 Avant",     "Estate",    "Diesel",   65000, 150, 1968, 5.4,  None, None, 142, 5, "FWD", 0.46, 2019),
        ("Q3",           "SUV",       "Petrol",   43000, 110, 1498, 6.3,  None, None, 143, 5, "FWD", 0.52, 2019),
        ("Q5",           "SUV",       "Diesel",   60000, 150, 1968, 5.6,  None, None, 147, 5, "AWD", 0.53, 2021),
        ("Q7",           "Luxury",    "Diesel",   82000, 170, 2967, 7.1,  None, None, 186, 7, "AWD", 0.48, 2020),
        ("Q4 e-tron",    "SUV",       "Electric", 48000, 150, None, None, 16.6,  522,   0, 5, "RWD", 0.42, 2022),
    ]),
    "Skoda": (7, [
        ("Fabia",         "Small Car", "Petrol",   21000,  70,  999, 5.2,  None, None, 118, 5, "FWD", 0.49, 2021),
        ("Scala",         "Compact",   "Petrol",   25000,  85,  999, 5.4,  None, None, 123, 5, "FWD", 0.47, 2019),
        ("Octavia Combi", "Estate",    "Diesel",   34000, 110, 1968, 4.8,  None, None, 126, 5, "FWD", 0.51, 2020),
        ("Superb Combi",  "Estate",    "Diesel",   45000, 142, 1968, 5.2,  None, None, 137, 5, "FWD", 0.48, 2024),
        ("Karoq",         "SUV",       "Petrol",   33000, 110, 1498, 6.0,  None, None, 137, 5, "FWD", 0.52, 2022),
        ("Kodiaq",        "SUV",       "Diesel",   42000, 110, 1968, 5.6,  None, None, 147, 7, "AWD", 0.54, 2024),
        ("Enyaq",         "SUV",       "Electric", 44000, 150, None, None, 16.4,  534,   0, 5, "RWD", 0.43, 2021),
    ]),
    "Opel": (5, [
        ("Corsa",          "Small Car", "Petrol",   21000,  74, 1199, 5.5,  None, None, 124, 5, "FWD", 0.46, 2020),
        ("Corsa Electric", "Small Car", "Electric", 33000, 100, None, None, 15.3,  357,   0, 5, "FWD", 0.38, 2023),
        ("Astra",          "Compact",   "Petrol",   29000,  81, 1199, 5.5,  None, None, 126, 5, "FWD", 0.46, 2022),
        ("Mokka",          "SUV",       "Petrol",   27000,  96, 1199, 5.8,  None, None, 132, 5, "FWD", 0.47, 2021),
        ("Grandland",      "SUV",       "Diesel",   36000,  96, 1499, 5.1,  None, None, 133, 5, "FWD", 0.45, 2022),
        ("Combo Life",     "Van",       "Diesel",   32000,  96, 1499, 5.3,  None, None, 139, 7, "FWD", 0.45, 2019),
    ]),
    "Ford": (4, [
        ("Focus",           "Compact", "Petrol",         28000,  92,  999, 5.7,  None, None, 129, 5, "FWD", 0.44, 2022),
        ("Focus Turnier",   "Estate",  "Diesel",         32000,  88, 1499, 4.9,  None, None, 128, 5, "FWD", 0.44, 2022),
        ("Puma",            "SUV",     "Petrol",         28000,  92,  999, 5.6,  None, None, 127, 5, "FWD", 0.47, 2020),
        ("Kuga",            "SUV",     "Plug-in Hybrid", 42000, 165, 2488, 1.4,  None, None,  32, 5, "FWD", 0.46, 2020),
        ("Transit Custom",  "Van",     "Diesel",         42000, 100, 1995, 7.1,  None, None, 187, 3, "FWD", 0.48, 2023),
        ("Mustang Mach-E",  "SUV",     "Electric",       52000, 198, None, None, 17.0,  600,   0, 5, "RWD", 0.38, 2021),
    ]),
    "Hyundai": (4, [
        ("i20",      "Small Car", "Petrol",   21000,  74, 1197, 5.5,  None, None, 125, 5, "FWD", 0.45, 2020),
        ("i30",      "Compact",   "Petrol",   26000,  88, 1482, 5.9,  None, None, 134, 5, "FWD", 0.46, 2020),
        ("Tucson",   "SUV",       "Hybrid",   38000, 169, 1598, 5.6,  None, None, 127, 5, "FWD", 0.50, 2021),
        ("Santa Fe", "SUV",       "Hybrid",   52000, 158, 1598, 6.4,  None, None, 145, 7, "AWD", 0.48, 2024),
        ("Kona",     "SUV",       "Electric", 42000, 160, None, None, 16.6,  514,   0, 5, "FWD", 0.41, 2023),
        ("Ioniq 5",  "SUV",       "Electric", 47000, 168, None, None, 16.7,  507,   0, 5, "RWD", 0.42, 2021),
    ]),
    "Kia": (3.5, [
        ("Picanto",  "Small Car", "Petrol",   17000,  46,  998, 5.1,  None, None, 116, 5, "FWD", 0.44, 2020),
        ("Ceed SW",  "Estate",    "Petrol",   27000, 103, 1482, 6.0,  None, None, 136, 5, "FWD", 0.46, 2019),
        ("Niro",     "SUV",       "Hybrid",   34000, 104, 1580, 4.6,  None, None, 105, 5, "FWD", 0.48, 2022),
        ("Sportage", "SUV",       "Hybrid",   38000, 169, 1598, 5.7,  None, None, 129, 5, "FWD", 0.50, 2022),
        ("Sorento",  "SUV",       "Diesel",   52000, 148, 2151, 6.0,  None, None, 157, 7, "AWD", 0.50, 2020),
        ("EV6",      "SUV",       "Electric", 49000, 168, None, None, 16.5,  528,   0, 5, "RWD", 0.43, 2021),
    ]),
    "Seat": (4, [
        ("Ibiza",           "Small Car", "Petrol",   21000,  70,  999, 5.4,  None, None, 122, 5, "FWD", 0.46, 2021),
        ("Leon",            "Compact",   "Petrol",   27000, 110, 1498, 5.5,  None, None, 125, 5, "FWD", 0.47, 2020),
        ("Arona",           "SUV",       "Petrol",   24000,  85,  999, 5.7,  None, None, 130, 5, "FWD", 0.47, 2021),
        ("Ateca",           "SUV",       "Diesel",   33000, 110, 1968, 5.2,  None, None, 137, 5, "FWD", 0.48, 2020),
        ("Cupra Formentor", "SUV",       "Petrol",   38000, 140, 1498, 6.2,  None, None, 141, 5, "FWD", 0.50, 2021),
        ("Cupra Born",      "Compact",   "Electric", 40000, 170, None, None, 16.0,  424,   0, 5, "RWD", 0.41, 2022),
    ]),
    "Toyota": (3.5, [
        ("Yaris",                  "Small Car", "Hybrid",         25000,  85, 1490, 4.2, None, None,  96, 5, "FWD", 0.52, 2020),
        ("Yaris Cross",            "SUV",       "Hybrid",         28000,  85, 1490, 4.4, None, None, 100, 5, "FWD", 0.53, 2021),
        ("Corolla Touring Sports", "Estate",    "Hybrid",         34000, 103, 1798, 4.5, None, None, 102, 5, "FWD", 0.53, 2019),
        ("C-HR",                   "SUV",       "Hybrid",         34000, 103, 1798, 4.7, None, None, 105, 5, "FWD", 0.52, 2023),
        ("RAV4",                   "SUV",       "Plug-in Hybrid", 52000, 225, 2487, 1.0, None, None,  22, 5, "AWD", 0.55, 2021),
        ("Proace City",            "Van",       "Diesel",         31000,  96, 1499, 5.4, None, None, 142, 5, "FWD", 0.48, 2020),
    ]),
    "Renault": (3.5, [
        ("Clio",           "Small Car", "Hybrid",   24000, 105, 1598, 4.3,  None, None,  98, 5, "FWD", 0.44, 2020),
        ("Captur",         "SUV",       "Petrol",   25000,  67,  999, 5.8,  None, None, 132, 5, "FWD", 0.45, 2021),
        ("Austral",        "SUV",       "Hybrid",   38000, 147, 1199, 4.7,  None, None, 105, 5, "FWD", 0.44, 2023),
        ("Kangoo",         "Van",       "Diesel",   30000,  85, 1461, 5.3,  None, None, 139, 5, "FWD", 0.43, 2021),
        ("Megane E-Tech",  "Compact",   "Electric", 42000, 160, None, None, 16.1,  470,   0, 5, "FWD", 0.38, 2022),
    ]),
    "Dacia": (2.5, [
        ("Sandero", "Small Car", "Petrol",   14000,  66,  999, 5.6,  None, None, 127, 5, "FWD", 0.52, 2021),
        ("Duster",  "SUV",       "Petrol",   20000,  96, 1333, 6.3,  None, None, 143, 5, "FWD", 0.54, 2024),
        ("Jogger",  "Van",       "Hybrid",   25000, 103, 1598, 4.8,  None, None, 109, 7, "FWD", 0.50, 2022),
        ("Spring",  "Small Car", "Electric", 18000,  48, None, None, 13.2,  225,   0, 4, "FWD", 0.36, 2021),
    ]),
    "Tesla": (2, [
        ("Model 3", "Sedan", "Electric", 42000, 208, None, None, 13.2, 513, 0, 5, "RWD", 0.41, 2021),
        ("Model Y", "SUV",   "Electric", 46000, 220, None, None, 15.7, 565, 0, 5, "RWD", 0.40, 2022),
    ]),
    "MINI": (2, [
        ("Cooper",      "Small Car", "Petrol",   28000, 115, 1499, 5.9,  None, None, 134, 4, "FWD", 0.50, 2024),
        ("Cooper SE",   "Small Car", "Electric", 35000, 160, None, None, 14.8,  305,   0, 4, "FWD", 0.42, 2021),
        ("Countryman",  "SUV",       "Petrol",   38000, 125, 1499, 6.4,  None, None, 146, 5, "AWD", 0.49, 2024),
    ]),
    "MG": (1.5, [
        ("ZS",           "SUV",     "Petrol",         22000,  78, 1498, 6.3,  None, None, 143, 5, "FWD", 0.35, 2021),
        ("HS",           "SUV",     "Plug-in Hybrid", 38000, 190, 1498, 1.8,  None, None,  41, 5, "FWD", 0.36, 2023),
        ("MG4 Electric", "Compact", "Electric",       35000, 150, None, None, 16.0,  450,   0, 5, "RWD", 0.36, 2022),
        ("MG5 Estate",   "Estate",  "Electric",       36000, 115, None, None, 17.0,  400,   0, 5, "FWD", 0.34, 2022),
    ]),
}

# Real German trim ladders per brand, cheapest -> most expensive. The Placement
# Assistant surfaces these by name ("der Kunde wollte einen R-Line"), so generic
# Base/Mid/Full labels would read as fake to anyone who sells cars in Germany.
BRAND_TRIMS = {
    "Volkswagen":    ["Life", "Style", "R-Line", "R"],
    "Mercedes-Benz": ["Basis", "Avantgarde", "AMG Line", "AMG Line Premium"],
    "BMW":           ["Advantage", "Sport Line", "M Sport", "M Sport Pro"],
    "Audi":          ["Basis", "advanced", "S line", "edition one"],
    "Skoda":         ["Essence", "Selection", "Sportline", "Laurin & Klement"],
    "Opel":          ["Edition", "Elegance", "GS Line", "Ultimate"],
    "Ford":          ["Trend", "Titanium", "ST-Line", "Active"],
    "Hyundai":       ["Select", "Trend", "Prime", "N Line"],
    "Kia":           ["Edition", "Vision", "Spirit", "GT-Line"],
    "Seat":          ["Reference", "Style", "FR", "Xcellence"],
    "Toyota":        ["Basis", "Business Edition", "Team Deutschland", "GR Sport"],
    "Renault":       ["Evolution", "Techno", "Esprit Alpine", "Iconic"],
    "Dacia":         ["Essential", "Expression", "Journey", "Extreme"],
    "Tesla":         ["Standard", "Long Range", "Performance", "Plaid"],
    "MINI":          ["Essential", "Classic", "Favoured", "John Cooper Works"],
    "MG":            ["Standard", "Comfort", "Luxury", "Trophy"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Nameplate demand skew.
#
# Within a brand, real German retail volume is heavily skewed toward a couple
# of mainstream nameplates (a VW store sells far more Golfs, T-Rocs and
# Tiguans than Touarans and GTIs). Uniform model selection would put niche
# trims at the top of the sales board. Anything not listed sits at 1.0.
# ─────────────────────────────────────────────────────────────────────────────
MODEL_FLAGSHIP = {
    "Golf", "T-Roc", "Tiguan", "Polo", "Octavia Combi", "Fabia", "Corsa",
    "Astra", "Focus", "3er", "X1", "A3 Sportback", "Q3", "C-Klasse",
    "A-Klasse", "GLC", "Sandero", "Model Y", "Clio", "i30", "Leon", "Ibiza",
}
MODEL_STRONG = {
    "Golf Variant", "Passat Variant", "T-Cross", "ID.3", "ID.4", "Karoq",
    "Kodiaq", "Scala", "Superb Combi", "Mokka", "Grandland", "Puma",
    "Focus Turnier", "1er", "3er Touring", "X3", "A4 Avant", "Q5", "Q4 e-tron",
    "A1", "GLA", "C-Klasse T-Modell", "i20", "Tucson", "Picanto", "Sportage",
    "Niro", "Ceed SW", "Arona", "Ateca", "Yaris", "Yaris Cross",
    "Corolla Touring Sports", "C-HR", "Captur", "Duster", "Model 3", "Cooper",
    "Countryman", "Enyaq", "ZS", "MG4 Electric", "Cupra Formentor",
}
MODEL_NICHE = {
    "Golf GTI", "Tiguan eHybrid", "Touran", "Caddy", "S-Klasse", "E-Klasse",
    "V-Klasse", "EQA", "5er", "X5", "i4", "iX1", "A6 Avant", "Q7", "Combo Life",
    "Kuga", "Transit Custom", "Mustang Mach-E", "Santa Fe", "Kona", "Ioniq 5",
    "Sorento", "EV6", "Cupra Born", "RAV4", "Proace City", "Austral", "Kangoo",
    "Megane E-Tech", "Jogger", "Spring", "Cooper SE", "HS", "MG5 Estate",
    "Corsa Electric",
}
MODEL_TIER_WEIGHT = {
    **{m: 2.6 for m in MODEL_FLAGSHIP},
    **{m: 1.7 for m in MODEL_STRONG},
    **{m: 0.45 for m in MODEL_NICHE},
}

# Trim ladder economics: price multiplier, kW uplift, consumption PENALTY
# (bigger wheels / heavier equipment burn MORE, so l/100km goes UP the ladder —
# the sign is the opposite of the UAE build's km-per-litre delta).
TRIM_PRICE_MULT = [1.00, 1.10, 1.22, 1.36]
TRIM_KW_MULT = [1.00, 1.00, 1.06, 1.14]
TRIM_CONSUMPTION_DELTA = [0.0, 0.2, 0.4, 0.7]      # l/100km ADDED
TRIM_KWH_DELTA = [0.0, 0.3, 0.6, 1.0]              # kWh/100km ADDED

# The Kia / Hyundai / MG long manufacturer warranty is a genuine German market
# differentiator, so it is modelled rather than randomised. German statutory
# Gewährleistung is 2 years; most brands offer exactly that.
BRAND_WARRANTY_YEARS = {"Kia": 7, "MG": 7, "Hyundai": 5, "Toyota": 3, "Dacia": 3}

# Real German-market exterior paint names, so a Placement Assistant request
# reads like a real one ("weißer Tiguan R-Line").
PAINT_COLORS = [
    "Uni Weiß", "Deep Black Perleffekt", "Reflexsilber", "Indiumgrau",
    "Atlantic Blue", "Kings Red", "Mondsteingrau", "Oryxweiß",
]

# Where a brand's German-market stock is actually built. Drives ONLY logistics
# lead time and the Domestic/Import label — there is no tariff or duty analysis
# anywhere in this build.
BRAND_ORIGIN_REGION = {
    "Volkswagen": "Germany", "Mercedes-Benz": "Germany", "BMW": "Germany",
    "Audi": "Germany", "Opel": "Germany", "Ford": "Germany",
    "Tesla": "Germany",                       # Model Y/3 for Europe: Grünheide
    "Skoda": "EU-Central",                    # Mladá Boleslav
    "Hyundai": "EU-Central",                  # Nošovice
    "Kia": "EU-Central",                      # Žilina
    "Seat": "EU-South",                       # Martorell
    "Renault": "EU-West", "Toyota": "EU-West",
    "Dacia": "EU-East",                       # Mioveni
    "MINI": "UK",                             # Oxford
    "MG": "China",
}
ORIGIN_LEAD_DAYS = {
    "Germany": (10, 28), "EU-Central": (14, 32), "EU-West": (16, 34),
    "EU-South": (16, 34), "EU-East": (18, 36), "UK": (20, 38), "China": (40, 65),
}

GERMAN_PLANTS = [
    "Wolfsburg", "Zwickau", "Emden", "Ingolstadt", "Neckarsulm",
    "Sindelfingen", "Bremen", "Regensburg", "Dingolfing", "Rüsselsheim",
    "Köln-Niehl", "Grünheide",
]
IMPORT_PORTS = ["Bremerhaven", "Emden (Hafen)", "Cuxhaven", "Hamburg"]

BRAND_NAMES = list(BRAND_CATALOG.keys())
BRAND_WEIGHTS = np.array([BRAND_CATALOG[b][0] for b in BRAND_NAMES], dtype=float)
BRAND_WEIGHTS = BRAND_WEIGHTS / BRAND_WEIGHTS.sum()

# Segment-mix control.
#
# The catalog is SUV-dense (most brands field two or three), so selecting
# models on nameplate popularity alone lands SUV near 42% of units against a
# real German share of ~33%. These multipliers pull the booked mix back onto
# the KBA segment shape. Tune these, not the catalog, when the mix drifts.
#   target: SUV 34 / Compact 20 / Estate 17 / Small Car 12 / Sedan 8 /
#           Van 5 / Luxury 3 / Coupe 1
CATEGORY_MARKET_WEIGHT = {
    "SUV": 0.74, "Compact": 1.00, "Estate": 1.18, "Small Car": 1.08,
    "Sedan": 1.30, "Van": 1.70, "Luxury": 1.55, "Coupe": 1.00,
}

# Manual transmission is still roughly a third of German new-car sales — a
# dimension that simply does not exist in the Gulf build. Probability of a
# manual gearbox by segment.
MANUAL_RATE_BY_CATEGORY = {
    "Small Car": 0.62, "Compact": 0.42, "Estate": 0.26, "Sedan": 0.18,
    "SUV": 0.22, "Van": 0.34, "Luxury": 0.02, "Coupe": 0.15,
}
VW_GROUP = {"Volkswagen", "Audi", "Skoda", "Seat"}

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


def _step_series(by_month):
    """by_month: dict of (year, month) -> value, held flat until the next entry."""
    keys = sorted(by_month)
    out = np.zeros(N_MONTHS)
    cur = by_month[keys[0]]
    ki = 0
    for i in range(N_MONTHS):
        while ki < len(keys) and _month_index(*keys[ki]) <= i:
            cur = by_month[keys[ki]]
            ki += 1
        out[i] = cur
    return out


MONTH_OF = np.array([d.month for d in MONTHS])
YEAR_OF = np.array([d.year for d in MONTHS])

# ─────────────────────────────────────────────────────────────────────────────
# Real-anchored macro series (approximate, for narrative authenticity)
# ─────────────────────────────────────────────────────────────────────────────

# ECB main refinancing rate. Flat zero until Jul 2022, then the fastest hiking
# cycle in the euro's history to 4.50% by Sep 2023, then the 2024-25 cuts.
# Modelled as steps, not an interpolation — ECB moves are discrete decisions.
ECB_RATE = _step_series({
    (2019, 1): 0.00, (2022, 7): 0.50, (2022, 9): 1.25, (2022, 11): 2.00,
    (2022, 12): 2.50, (2023, 2): 3.00, (2023, 3): 3.50, (2023, 5): 3.75,
    (2023, 6): 4.00, (2023, 8): 4.25, (2023, 9): 4.50, (2024, 6): 4.25,
    (2024, 9): 3.65, (2024, 10): 3.40, (2024, 12): 3.15, (2025, 3): 2.65,
    (2025, 6): 2.15, (2025, 9): 2.00,
})

# Super E10, EUR/litre. The 2022 Russia/Ukraine spike, the Tankrabatt
# (Energiesteuersenkung, 1 Jun - 31 Aug 2022) and the nEHS CO2 price are all
# visible. The rebate is applied as a discrete cut rather than smoothed through
# the interpolation, because that is how drivers experienced it.
_E10_BASE = _interp_series([
    (2019, 1, 1.38), (2019, 12, 1.42), (2020, 4, 1.12), (2020, 12, 1.25),
    (2021, 6, 1.52), (2021, 12, 1.62), (2022, 3, 2.20), (2022, 5, 2.12),
    (2022, 9, 1.95), (2022, 12, 1.75), (2023, 6, 1.78), (2023, 12, 1.76),
    (2024, 6, 1.79), (2024, 12, 1.70), (2025, 6, 1.68), (2025, 12, 1.70),
    (2026, 8, 1.72),
])
_TANKRABATT = np.zeros(N_MONTHS)
for _y, _m in [(2022, 6), (2022, 7), (2022, 8)]:
    _TANKRABATT[_month_index(_y, _m)] = 0.30
SUPER_E10 = _E10_BASE - _TANKRABATT
SUPER_E5 = SUPER_E10 + 0.06

_DIESEL_BASE = _interp_series([
    (2019, 1, 1.25), (2020, 4, 1.05), (2021, 12, 1.50), (2022, 3, 2.15),
    (2022, 5, 2.02), (2022, 9, 2.10), (2022, 12, 1.85), (2023, 12, 1.72),
    (2024, 12, 1.65), (2025, 12, 1.62), (2026, 8, 1.65),
])
_DIESEL_REBATE = np.zeros(N_MONTHS)
for _y, _m in [(2022, 6), (2022, 7), (2022, 8)]:
    _DIESEL_REBATE[_month_index(_y, _m)] = 0.14
DIESEL_PRICE = _DIESEL_BASE - _DIESEL_REBATE

# Household electricity, EUR/kWh — the BEV running-cost side of the equation.
ELECTRICITY_PRICE = _interp_series([
    (2019, 1, 0.30), (2020, 1, 0.31), (2021, 1, 0.32), (2022, 1, 0.37),
    (2023, 1, 0.46), (2023, 12, 0.42), (2024, 12, 0.40), (2025, 12, 0.39),
    (2026, 8, 0.38),
])

BRENT_CRUDE = _interp_series([
    (2019, 1, 55), (2019, 12, 66), (2020, 4, 23), (2020, 12, 50),
    (2021, 12, 78), (2022, 6, 118), (2022, 12, 82), (2023, 12, 77),
    (2024, 12, 74), (2025, 12, 70), (2026, 8, 72),
])
# German CPI — the 2022 energy shock took it to ~8.8%, far above anything the
# UAE series sees.
CPI_INFLATION = _interp_series([
    (2019, 1, 1.4), (2019, 12, 1.5), (2020, 6, 0.6), (2020, 12, -0.3),
    (2021, 12, 5.3), (2022, 10, 8.8), (2022, 12, 8.1), (2023, 6, 6.4),
    (2023, 12, 3.7), (2024, 6, 2.2), (2024, 12, 2.6), (2025, 12, 2.0),
    (2026, 8, 2.0),
])
UNEMPLOYMENT = _interp_series([
    (2019, 1, 5.0), (2020, 8, 6.4), (2021, 12, 5.1), (2022, 12, 5.4),
    (2023, 12, 5.8), (2024, 12, 6.1), (2025, 12, 6.3), (2026, 8, 6.2),
])
# German GDP — the deep 2020 COVID trough, then the 2023 and 2024 contractions.
# This economy does NOT boom over the window, which is the opposite of the UAE
# series and is the honest backdrop for the group's volume story.
GDP_GROWTH = _interp_series([
    (2019, 1, 0.6), (2019, 12, 0.6), (2020, 6, -11.3), (2020, 12, -3.8),
    (2021, 12, 3.2), (2022, 12, 1.4), (2023, 12, -0.3), (2024, 12, -0.2),
    (2025, 12, 0.4), (2026, 8, 0.9),
])
# GfK Konsumklima. NOTE: this index is genuinely NEGATIVE for most of the
# window (it collapsed to -42.8 in Sep 2022). Downstream code must not assume a
# 100-centred index or take ratios of it.
CONSUMER_CONF = _interp_series([
    (2019, 1, 10.4), (2020, 5, -23.1), (2020, 12, -7.5), (2021, 8, -1.6),
    (2022, 9, -42.8), (2023, 6, -25.4), (2024, 6, -21.0), (2025, 6, -20.0),
    (2026, 8, -18.0),
])
# ifo Geschäftsklimaindex (2015 = 100) — the 100-centred business-side index.
IFO_CLIMATE = _interp_series([
    (2019, 1, 99.1), (2020, 4, 74.3), (2020, 12, 92.2), (2021, 6, 101.2),
    (2022, 9, 84.4), (2023, 6, 88.6), (2024, 6, 88.6), (2025, 6, 88.0),
    (2026, 8, 89.0),
])
# German residential price index (2019 = 100). Rises hard to 2022, then FALLS
# through the rate shock — the inverse of the Dubai index in the UAE build.
DE_HOUSE_PRICE_IDX = _interp_series([
    (2019, 1, 100), (2020, 1, 107), (2021, 1, 118), (2022, 1, 131),
    (2022, 6, 134), (2023, 6, 124), (2024, 1, 121), (2025, 1, 123),
    (2026, 8, 127),
])
LUXURY_DEMAND_IDX = _interp_series([
    (2019, 1, 100), (2020, 6, 84), (2021, 12, 106), (2022, 12, 110),
    (2023, 12, 108), (2024, 12, 104), (2025, 12, 102), (2026, 8, 101),
])
EV_CHARGING_POINTS = _interp_series([
    (2019, 1, 17000), (2020, 12, 33000), (2021, 12, 50000), (2022, 12, 77000),
    (2023, 12, 105000), (2024, 12, 150000), (2025, 12, 185000), (2026, 8, 205000),
])
# Share of new registrations that are commercial rather than private.
COMMERCIAL_SHARE = _interp_series([
    (2019, 1, 64), (2020, 12, 63), (2022, 12, 65), (2024, 12, 68), (2026, 8, 68),
])

# National CO2 price (nEHS), EUR/tonne — introduced Jan 2021, stepped annually.
CO2_PRICE = _step_series({
    (2019, 1): 0, (2021, 1): 25, (2022, 1): 30, (2023, 1): 30,
    (2024, 1): 45, (2025, 1): 55, (2026, 1): 65,
})

# Umweltbonus — the federal share of the BEV purchase subsidy, EUR.
# The Innovationsprämie doubled it in Jul 2020; it was trimmed in 2023, and on
# 17 Dec 2023 the programme was halted overnight when the Klima- und
# Transformationsfonds was ruled unconstitutional. That cliff is the single
# sharpest demand shock in this window.
EV_SUBSIDY = _step_series({
    (2019, 1): 2000, (2020, 7): 6000, (2023, 1): 4500, (2023, 12): 0,
})

# Umsatzsteuer — 19%, except the Konjunkturpaket cut to 16% for H2 2020.
VAT_RATE = np.full(N_MONTHS, VAT_RATE_STANDARD)
for _y, _m in [(2020, m) for m in range(7, 13)]:
    VAT_RATE[_month_index(_y, _m)] = VAT_RATE_COVID_CUT

# ─────────────────────────────────────────────────────────────────────────────
# German retail calendar.
#
# Nothing here carries over from the UAE build: no Ramadan, no National Day, no
# shopping festival. What moves German metal is the quarter-end registration
# push, the year-end run-out, Ostern and the Sommerferien lull.
# ─────────────────────────────────────────────────────────────────────────────
EASTER_SUNDAY = {
    2019: date(2019, 4, 21), 2020: date(2020, 4, 12), 2021: date(2021, 4, 4),
    2022: date(2022, 4, 17), 2023: date(2023, 4, 9),  2024: date(2024, 3, 31),
    2025: date(2025, 4, 20), 2026: date(2026, 4, 5),
}

# IAA — Frankfurt to 2019, then IAA Mobility in Munich from 2021, biennial.
_IAA_YEARS = {2019, 2021, 2023, 2025}

QUARTER_END_MONTH = np.where(np.isin(MONTH_OF, [3, 6, 9, 12]), 1, 0)
YEAR_END_MONTH = np.where(MONTH_OF == 12, 1, 0)
SUMMER_HOLIDAY_MONTH = np.where(np.isin(MONTH_OF, [7, 8]), 1, 0)
IAA_MONTH = np.array([
    1 if (int(MONTH_OF[i]) == 9 and int(YEAR_OF[i]) in _IAA_YEARS) else 0
    for i in range(N_MONTHS)
])
# German model-year changeover and facelift announcements cluster around the
# IAA in September and the spring launch season.
NEW_MODEL_LAUNCHES = np.where(np.isin(MONTH_OF, [3, 4, 9, 10]), 3, 1)


def _season_period(d):
    """Retail sales-event label for a given calendar date, or None.

    Canonical ENGLISH labels — the German UI translates them at render."""
    y = d.year
    if y in EASTER_SUNDAY:
        es = EASTER_SUNDAY[y]
        if abs((d - es).days) <= 10:
            return "Easter Campaign"
    if d.month == 12 and d.day >= 15:
        return "Year-End Registration Push"
    if d.month in (3, 6, 9) and d.day >= 20:
        return "Quarter-End Push"
    if d.month == 9 and y in _IAA_YEARS and d.day <= 20:
        return "IAA Mobility"
    if d.month == 1 and d.day <= 15:
        return "New Year"
    if d.month in (7, 8):
        return "Summer Holidays"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Retail demand shape — this is ONE regional dealer group's own sales pattern,
# not a market model. The series below drive WHICH months and weekdays book
# deals; the group's annual volume is set by n_sales and is not inflated by
# any of this (the net macro effect is mean-normalised in build_sales).
# ─────────────────────────────────────────────────────────────────────────────

# German new-registration seasonality, index average = 100. The shape is driven
# by quarter-end pushes (March, June, September) where manufacturers and
# dealers self-register to hit targets, a December run-out, a dead January
# after the year-end pull-forward, and the August Sommerferien trough.
RETAIL_SEASONAL_FACTOR = {
    1: 0.82, 2: 0.88, 3: 1.20, 4: 0.95, 5: 0.98, 6: 1.15,
    7: 1.02, 8: 0.88, 9: 1.12, 10: 0.98, 11: 0.98, 12: 1.04,
}

# Day-of-week retail pattern (Mon..Sun, sums to 1).
#
# HARD CONSTRAINT: the Ladenschlussgesetz bans Sunday selling. German
# showrooms may open for a "Schautag" (viewing only, no sales staff, no
# contracts), so Sunday is a residual for online orders dated that day — not a
# trading day. This is the exact inverse of the UAE build, where Saturday and
# Sunday were the two peak days.
RETAIL_DOW_WEIGHT = np.array([0.150, 0.155, 0.155, 0.165, 0.175, 0.195, 0.005])

# What a German customer actually finances at: the effektiver Jahreszins on a
# new-car Autokredit — policy rate plus a typical new-car spread across a
# blended book of manufacturer-subvented and bank paper.
AUTO_LOAN_SPREAD_PCT = 3.0
AUTO_LOAN_APR = ECB_RATE + AUTO_LOAN_SPREAD_PCT

# Manufacturer + dealer incentive spend as a share of transaction price.
# German list-price discounting (Nachlässe) is structurally heavy on volume
# brands: double digits pre-COVID, collapsed to almost nothing in the 2021-22
# chip shortage when anything buildable sold at list, then rebuilt hard through
# 2024-25 as BEV stock backed up after the Umweltbonus ended.
INCENTIVE_PCT_ATP = _interp_series([
    (2019, 1, 11.0), (2020, 6, 12.5), (2021, 6, 8.0), (2021, 12, 4.5),
    (2022, 9, 4.0), (2023, 6, 7.0), (2024, 6, 10.5), (2025, 6, 12.0),
    (2026, 8, 12.5),
])

# New-vehicle days' supply on the group's lots. ~60 is healthy; the shortage
# years ran 20-30, then supply rebuilt past 70 in 2024-25 as demand softened.
DAYS_SUPPLY = _interp_series([
    (2019, 1, 62), (2019, 12, 60), (2020, 5, 58), (2021, 6, 28),
    (2021, 12, 20), (2022, 9, 26), (2023, 6, 46), (2024, 3, 64),
    (2024, 12, 74), (2025, 9, 72), (2026, 8, 70),
])


def _kfz_steuer(fuel, cc, co2):
    """
    Annual Kfz-Steuer in EUR, per the German formula: a displacement component
    (2.00 EUR per 100cm3 petrol, 9.50 EUR per 100cm3 diesel) plus a tiered CO2
    component on everything above 95 g/km. BEVs are exempt.
    """
    if fuel == "Electric":
        return 0
    cc = cc or 0
    per_100 = 9.50 if fuel == "Diesel" else 2.00
    base = (cc / 100.0) * per_100

    co2 = co2 or 0
    tiers = [(115, 2.00), (135, 2.20), (155, 2.50), (175, 2.90), (195, 3.40)]
    co2_component = 0.0
    lower = 95
    for upper, rate in tiers:
        if co2 > lower:
            co2_component += (min(co2, upper) - lower) * rate
            lower = upper
    if co2 > 195:
        co2_component += (co2 - 195) * 4.00
    return int(round(base + co2_component))


def build_vehicle_catalog(rng, n_trims=2):
    """
    Expand BRAND_CATALOG into one row per (model, trim).

    Specs come from the catalog table rather than random draws, so a Polo
    cannot end up with 300 kW and a Q7 cannot end up at 3 l/100km. Only
    genuinely variable attributes (paint count, service contract) are
    randomised.
    """
    rows = []
    vid = 1
    for brand, (_share, models) in BRAND_CATALOG.items():
        trims = BRAND_TRIMS[brand][:n_trims]
        origin_region = BRAND_ORIGIN_REGION.get(brand, "EU-Central")
        for (model, category, fuel, price, kw, cc, l100, kwh100, rng_km,
             co2, seats, drive, resid36, intro_year) in models:
            is_ev = fuel == "Electric"
            for ti, trim in enumerate(trims):
                trim_price = int(round(price * TRIM_PRICE_MULT[ti] / 500.0) * 500)
                trim_kw = int(round(kw * TRIM_KW_MULT[ti]))
                # Consumption RISES up the trim ladder — heavier, wider wheels.
                trim_l100 = (None if l100 is None
                             else round(l100 + TRIM_CONSUMPTION_DELTA[ti], 1))
                trim_kwh = (None if kwh100 is None
                            else round(kwh100 + TRIM_KWH_DELTA[ti], 1))
                trim_range = (None if rng_km is None
                              else int(round(rng_km * (1.0 - 0.03 * ti))))
                trim_co2 = (None if co2 is None
                            else int(round(co2 * (1.0 + 0.04 * ti))))

                if is_ev:
                    transmission = "Single-Speed"
                elif rng.random() < MANUAL_RATE_BY_CATEGORY.get(category, 0.25):
                    transmission = "Manual"
                else:
                    transmission = "DSG" if brand in VW_GROUP else "Automatic"

                if is_ev:
                    emission_class = "BEV"
                else:
                    emission_class = "Euro 6e" if intro_year >= 2024 else "Euro 6d"

                rows.append({
                    "vehicle_id": f"VH{vid:04d}",
                    "brand": brand,
                    "model": model,
                    "variant": trim,
                    "category": category,
                    "fuel_type": fuel,
                    "price_eur": trim_price,
                    "engine_cc": None if is_ev else cc,
                    "power_kw": trim_kw,
                    "consumption_l_per_100km": trim_l100,
                    "consumption_kwh_per_100km": trim_kwh,
                    "range_km": trim_range,
                    "co2_g_per_km": trim_co2,
                    "emission_class": emission_class,
                    "annual_vehicle_tax_eur": _kfz_steuer(fuel, cc, trim_co2),
                    "seating_capacity": seats,
                    "transmission": transmission,
                    "drive_type": drive,
                    "body_color_options": int(rng.integers(5, 10)),
                    "safety_rating": 5 if resid36 >= 0.48 else int(rng.choice([4, 5], p=[0.35, 0.65])),
                    "launch_year": intro_year,
                    "is_active": True,
                    "warranty_years": BRAND_WARRANTY_YEARS.get(brand, 2),
                    "service_contract_available": bool(rng.random() < 0.7),
                    "origin": "Domestic" if origin_region == "Germany" else "Import",
                    # Not persisted to the DB — carried through generation so
                    # the lease book can price residuals per trim.
                    "_residual_36mo": resid36,
                })
                vid += 1
    return pd.DataFrame(rows)


# Residual curves are quoted at 36 months; shorter terms leave more value on
# the car, longer terms less.
LEASE_TERM_RESIDUAL_ADJ = {24: +0.10, 36: 0.00, 48: -0.10}
LEASE_TERMS = [24, 36, 48]
LEASE_TERM_WEIGHTS = [0.30, 0.50, 0.20]
# German leasing contracts are written at 10/15/20k km a year — materially
# lower than the Gulf's 15/20/25k, because annual mileage here is lower.
LEASE_ANNUAL_KM = [10000, 15000, 20000]
LEASE_KM_WEIGHTS = [0.35, 0.45, 0.20]

# Lease penetration by segment. This is the mirror image of the UAE build:
# German retail runs heavily on Leasing and Drei-Wege-Finanzierung, and
# commercial buyers lease almost by default (handled with a further uplift in
# build_sales), so these are roughly four times the Gulf rates.
LEASE_RATE_BY_CATEGORY = {
    "Luxury": 0.55, "Sedan": 0.45, "Estate": 0.48, "SUV": 0.42,
    "Coupe": 0.40, "Van": 0.40, "Compact": 0.35, "Small Car": 0.25,
}

# Slow-turning segments attract larger over-allowances on the trade, because
# that is where the store has to buy the deal to move the unit.
TRADE_OVER_ALLOWANCE_MULT = {
    "Sedan": 1.35, "Small Car": 1.30, "Compact": 1.20, "Van": 1.15,
    "Estate": 1.00, "SUV": 0.95, "Luxury": 1.10, "Coupe": 1.25,
}


DEALER_TEMPLATES = [
    "Autohaus {name} {city}", "{brand} Zentrum {city}", "Auto {name} {city}",
    "{brand} Niederlassung {city}", "Autohaus {city}-{name}",
]
DEALER_FAMILY_NAMES = [
    "Müller", "Schmidt", "Weber", "Wagner", "Becker", "Hoffmann",
    "Schäfer", "Koch", "Bauer", "Richter", "Klein", "Wolf",
]
DEALER_STREETS = [
    "Hauptstraße", "Industriestraße", "Robert-Bosch-Straße",
    "Carl-Benz-Straße", "Daimlerstraße", "Otto-Hahn-Straße",
    "Am Autohof", "Bundesstraße", "Gewerbering", "Rudolf-Diesel-Straße",
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
    coherent portfolio of franchises, weighted toward the high-volume
    mainstream brands, with every brand it sells backed by at least one rooftop
    so a customer buying that brand always has a store to buy it from.
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


def _plz(prefix, rng):
    """A plausible 5-digit PLZ inside a city's postal district."""
    return f"{prefix}{int(rng.integers(0, 1000)):03d}"


def build_dealers(rng, n_rooftops=None, dealers_per_state=None):
    """
    Build the dealer network.

    - `n_rooftops` (dealer-group mode): a single group of that many rooftops,
      spread across Bundesländer in proportion to market size, each rooftop a
      single coherent franchise, sales targets filled in later from actual
      volume.
    - `dealers_per_state` (legacy/market mode): an even grid of independent
      dealers, kept for the larger "test" dataset.
    """
    rows = []
    did = 1

    if n_rooftops is not None:
        per_state = _distribute_by_weight(n_rooftops, STATE_WEIGHTS)
        brands = _group_brand_portfolio(rng, n_rooftops)
        bi = 0
        for st, k in zip(STATES, per_state):
            for _ in range(int(k)):
                brand = brands[bi]; bi += 1
                city, lat, lon, plz_prefix = st["cities"][rng.integers(0, len(st["cities"]))]
                name = f"{brand} Zentrum {city}"
                tier = rng.choice(["Platinum", "Gold", "Silver"], p=[0.25, 0.50, 0.25])
                rows.append({
                    "dealer_id": f"DLR{did:04d}", "dealer_name": name, "brand": brand,
                    "state": st["name"], "city": city,
                    "address": f"{rng.choice(DEALER_STREETS)} {int(rng.integers(1, 180))}",
                    "postal_code": _plz(plz_prefix, rng),
                    "tier": tier,
                    "established_year": int(rng.integers(1955, 2015)),
                    "monthly_capacity": int(rng.integers(90, 340)),
                    "showroom_area_sqm": int(rng.integers(700, 3200)),
                    "service_center": bool(rng.random() < 0.95),
                    "ev_charging_station": bool(rng.random() < (0.9 if brand in ("Tesla", "MG", "Hyundai", "Kia", "BMW") else 0.6)),
                    "num_salespeople": int(rng.integers(10, 38)),
                    "annual_target_units": 0,  # filled from trailing-12-month actuals in generate_dataset()
                    "performance_score": round(float(rng.uniform(62, 96)), 1),
                    "google_rating": round(float(rng.uniform(3.9, 4.9)), 1),
                    "latitude": round(lat + rng.uniform(-0.05, 0.05), 5),
                    "longitude": round(lon + rng.uniform(-0.05, 0.05), 5),
                })
                did += 1
        return pd.DataFrame(rows)

    # ── legacy even-grid market mode ────────────────────────────────────────
    for st in STATES:
        for _ in range(dealers_per_state):
            brand = rng.choice(BRAND_NAMES, p=BRAND_WEIGHTS)
            city, lat, lon, plz_prefix = st["cities"][rng.integers(0, len(st["cities"]))]
            template = rng.choice(DEALER_TEMPLATES)
            name = template.format(brand=brand, city=city,
                                   name=rng.choice(DEALER_FAMILY_NAMES))
            tier = rng.choice(["Platinum", "Gold", "Silver"], p=[0.15, 0.45, 0.40])
            rows.append({
                "dealer_id": f"DLR{did:04d}", "dealer_name": name, "brand": brand,
                "state": st["name"], "city": city,
                "address": f"{rng.choice(DEALER_STREETS)} {int(rng.integers(1, 180))}",
                "postal_code": _plz(plz_prefix, rng),
                "tier": tier,
                "established_year": int(rng.integers(1950, 2015)),
                "monthly_capacity": int(rng.integers(60, 480)),
                "showroom_area_sqm": int(rng.integers(400, 2800)),
                "service_center": bool(rng.random() < 0.85),
                "ev_charging_station": bool(rng.random() < (0.8 if brand in ("Tesla", "MG", "Hyundai", "Kia", "BMW") else 0.45)),
                "num_salespeople": int(rng.integers(4, 60)),
                "annual_target_units": int(rng.integers(300, 4500)),
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
# Germany: income is ANNUAL GROSS (Bruttojahreseinkommen), credit is the SCHUFA
# Basisscore (0-100, and genuinely compressed near the top — most consumers sit
# above 90), and roughly a third of the book is commercial.
#
# `nationality` reflects the real German resident mix. It is DESCRIPTIVE ONLY.
# Deliberately, income here is drawn INDEPENDENTLY of nationality: the UAE
# build carried a nationality→income multiplier table because Gulf earnings
# genuinely stratify that way, but reproducing that pattern for Germany would
# bake an ethnic income stereotype into synthetic data that a dashboard then
# displays as if it were a finding. The mix panel shows counts; nothing scores
# on it, and it is not a KMeans or XGBoost feature.
# ─────────────────────────────────────────────────────────────────────────────
NATIONALITIES = [
    ("German", 85.0, "german"),
    ("Turkish", 3.2, "turkish"),
    ("Polish", 2.4, "polish"),
    ("Romanian", 1.6, "romanian"),
    ("Italian", 1.0, "italian"),
    ("Syrian", 1.0, "arabic"),
    ("Croatian", 0.8, "balkan"),
    ("Greek", 0.6, "greek"),
    ("Russian", 0.6, "russian"),
    ("Other EU", 2.0, "german"),
    ("Other Non-EU", 1.8, "german"),
]
NAT_NAMES = [n for n, _, _ in NATIONALITIES]
NAT_WEIGHTS = np.array([w for _, w, _ in NATIONALITIES], dtype=float)
NAT_WEIGHTS = NAT_WEIGHTS / NAT_WEIGHTS.sum()

NAME_POOLS = {
    "german": (
        ["Lukas", "Felix", "Jonas", "Maximilian", "Leon", "Paul", "Elias", "Noah",
         "Thomas", "Michael", "Andreas", "Stefan", "Anna", "Sophie", "Marie",
         "Laura", "Lena", "Julia", "Sabine", "Katrin", "Petra", "Nicole"],
        ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner",
         "Becker", "Schulz", "Hoffmann", "Schäfer", "Koch", "Bauer", "Richter",
         "Klein", "Wolf", "Neumann", "Schwarz", "Zimmermann", "Braun"],
    ),
    "turkish": (
        ["Mehmet", "Mustafa", "Ahmet", "Ali", "Hüseyin", "Emre", "Can",
         "Ayşe", "Fatma", "Emine", "Zeynep", "Elif", "Merve"],
        ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Öztürk",
         "Aydın", "Arslan", "Doğan"],
    ),
    "polish": (
        ["Piotr", "Krzysztof", "Andrzej", "Tomasz", "Paweł", "Marcin",
         "Anna", "Maria", "Katarzyna", "Małgorzata", "Agnieszka", "Magdalena"],
        ["Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kowalczyk",
         "Kamiński", "Lewandowski", "Zieliński", "Szymański", "Woźniak"],
    ),
    "romanian": (
        ["Andrei", "Alexandru", "Mihai", "Ion", "Gabriel", "Cristian",
         "Maria", "Elena", "Ioana", "Andreea", "Alexandra", "Cristina"],
        ["Popescu", "Ionescu", "Popa", "Radu", "Dumitru", "Stan",
         "Stoica", "Gheorghe", "Matei", "Constantin"],
    ),
    "italian": (
        ["Marco", "Giuseppe", "Antonio", "Luca", "Francesco", "Matteo",
         "Maria", "Giulia", "Francesca", "Sara", "Chiara", "Anna"],
        ["Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano",
         "Colombo", "Ricci", "Marino", "Greco"],
    ),
    "arabic": (
        ["Omar", "Youssef", "Karim", "Tarek", "Hassan", "Nabil", "Sami",
         "Layla", "Rana", "Nour", "Hala", "Yasmin", "Maha"],
        ["Haddad", "Khoury", "Mansour", "Nasser", "Saleh", "Ibrahim",
         "Darwish", "Aziz", "Hijazi", "Sayed"],
    ),
    "balkan": (
        ["Ivan", "Marko", "Ante", "Josip", "Luka", "Nikola",
         "Ana", "Marija", "Ivana", "Petra", "Katarina", "Nikolina"],
        ["Horvat", "Kovačević", "Babić", "Marić", "Jurić", "Novak",
         "Knežević", "Vuković", "Perić", "Matić"],
    ),
    "greek": (
        ["Giorgos", "Dimitris", "Nikos", "Kostas", "Ioannis", "Christos",
         "Maria", "Eleni", "Katerina", "Sofia", "Dimitra", "Georgia"],
        ["Papadopoulos", "Georgiou", "Nikolaou", "Vasiliou", "Ioannou",
         "Dimitriou", "Christou", "Antoniou", "Pappas", "Makris"],
    ),
    "russian": (
        ["Alexander", "Dmitri", "Sergei", "Andrei", "Ivan", "Nikolai",
         "Olga", "Elena", "Natalia", "Irina", "Svetlana", "Tatiana"],
        ["Ivanov", "Smirnov", "Kuznetsov", "Popov", "Sokolov",
         "Lebedev", "Kozlov", "Novikov", "Morozov", "Petrov"],
    ),
}

# Canonical English occupation labels; the German UI renders Angestellter,
# Beamter, Selbstständig, Freiberufler and so on from VALUE_MAP.
OCCUPATIONS = ["Salaried Employee", "Civil Servant", "Self-Employed", "Freelancer",
               "Business Owner", "Skilled Worker", "Public Sector", "Retired"]
# Annual GROSS income brackets, EUR (Bruttojahreseinkommen) — the German
# convention, replacing the Gulf's monthly tax-free banding.
INCOME_BRACKETS = ["<30K", "30K-50K", "50K-80K", "80K-120K", ">120K"]
BRACKET_MID_ANNUAL = {0: 24000, 1: 40000, 2: 63000, 3: 96000, 4: 160000}

# Share of the customer book that is commercial. Lower than the commercial
# share of UNITS (~62-68%), because fleet and Dienstwagen buyers come back far
# more often — build_sales does the weighting that turns one into the other.
# Sized so the commercial fresh pool never exhausts and spills into Private.
COMMERCIAL_CUSTOMER_SHARE = 0.38


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

    customer_type = np.where(rng.random(n) < COMMERCIAL_CUSTOMER_SHARE,
                             "Commercial", "Private")

    age = np.clip(rng.normal(46, 13, n), 20, 80).astype(int)
    gender = rng.choice(["Male", "Female", "Other"], size=n, p=[0.58, 0.40, 0.02])

    state_idx = rng.choice(len(STATES), size=n, p=STATE_WEIGHTS)
    state = [STATES[i]["name"] for i in state_idx]
    _city_pick = [STATES[i]["cities"][rng.integers(0, len(STATES[i]["cities"]))] for i in state_idx]
    city = [c[0] for c in _city_pick]
    postal_code = [_plz(c[3], rng) for c in _city_pick]

    occupation = rng.choice(OCCUPATIONS, size=n)

    # Income: annual gross, drawn independently of nationality (see the module
    # comment above). German median gross is ~EUR 45k, mean ~EUR 53k, with a
    # long right tail — a lognormal fits well.
    base_income = np.clip(rng.lognormal(np.log(46000), 0.52, n), 14000, 600000)
    # Commercial contacts are buying on a company budget, so the relevant
    # capacity sits higher than their personal salary.
    base_income = base_income * np.where(customer_type == "Commercial", 1.45, 1.0)
    est_income_annual = base_income.round(0)
    income_bracket_idx = np.digitize(est_income_annual, [30000, 50000, 80000, 120000])
    income_bracket = [INCOME_BRACKETS[i] for i in income_bracket_idx]

    # SCHUFA Basisscore, 0-100. Genuinely compressed near the top — the vast
    # majority of German consumers score above 90, so a normal draw centred at
    # 94 with a thin bad tail is the right shape (an even 300-900 spread, as in
    # the AECB model, would be wrong here).
    schufa_base = 94.0 + 0.9 * np.log1p(est_income_annual / 46000.0) + rng.normal(0, 5.5, n)
    schufa_score = np.clip(schufa_base, 40, 100).astype(int)

    years_at_address = np.clip(rng.exponential(7, n), 0, 45).astype(int)
    number_of_past_purchases = rng.poisson(1.1, n)   # placeholder, rewritten from sales

    # German fuel preference: diesel is a real and substantial share (unlike the
    # Gulf), and BEV/PHEV intent is high.
    preferred_fuel = rng.choice(["Petrol", "Diesel", "Hybrid", "Plug-in Hybrid", "Electric"],
                                size=n, p=[0.40, 0.21, 0.17, 0.07, 0.15])
    preferred_category = rng.choice(
        ["SUV", "Compact", "Estate", "Small Car", "Sedan", "Van", "Luxury", "Coupe"],
        size=n, p=[0.32, 0.20, 0.16, 0.13, 0.08, 0.05, 0.04, 0.02])

    loyalty_score = np.clip(rng.normal(50, 22, n), 0, 100)          # placeholder
    marketing_response = np.clip(rng.normal(5, 2.2, n), 0, 10)      # placeholder
    lead_source = rng.choice(["Online Ad", "Referral", "Dealer Walk-in", "Search Engine",
                              "Social Media", "Marketplace Portal"], size=n)
    email_opt_in = rng.random(n) < 0.55     # GDPR double-opt-in: lower than the Gulf
    test_drive_taken = rng.random(n) < 0.58
    financing_preferred = rng.random(n) < 0.68   # leasing/balloon-heavy market
    down_payment_capacity = np.clip(est_income_annual * rng.uniform(0.10, 0.35, n), 1500, None).astype(int)

    days_range = (end - start).days
    reg_offset = rng.integers(0, days_range, n)
    registration_date = [start + pd.Timedelta(days=int(o)) for o in reg_offset]
    activity_offset = [rng.integers(0, max((end - rd).days, 1)) for rd in registration_date]
    last_activity_date = [rd + pd.Timedelta(days=int(o)) for rd, o in zip(registration_date, activity_offset)]
    churn_risk = np.clip(rng.beta(2, 5, n), 0, 1)

    return pd.DataFrame({
        "customer_id": customer_id, "name": name, "age": age, "gender": gender,
        "nationality": nationality, "customer_type": customer_type,
        "state": state, "city": city, "postal_code": postal_code,
        "occupation": occupation, "annual_income_bracket": income_bracket,
        "estimated_annual_income_eur": est_income_annual, "schufa_score": schufa_score,
        "years_at_address": years_at_address,
        "number_of_past_purchases": number_of_past_purchases,
        "preferred_fuel_type": preferred_fuel, "preferred_vehicle_category": preferred_category,
        "customer_segment": "Unclassified", "loyalty_score": loyalty_score.round(2),
        "marketing_response_score": marketing_response.round(2), "lead_source": lead_source,
        "email_opt_in": email_opt_in, "test_drive_taken": test_drive_taken,
        "financing_preferred": financing_preferred,
        "down_payment_capacity_eur": down_payment_capacity,
        "registration_date": registration_date,
        "last_activity_date": last_activity_date,
        "churn_risk_score": churn_risk.round(3),
    })


def build_external_factors(rng):
    rows = []
    for mi in range(N_MONTHS):
        y, m = int(YEAR_OF[mi]), int(MONTH_OF[mi])
        for st in STATES:
            charge_points = int(EV_CHARGING_POINTS[mi] * st["ev_index"] * (st["weight"] / 100.0))
            rows.append({
                "date": date(y, m, 1), "year": y, "month": m, "quarter": f"Q{(m - 1) // 3 + 1}",
                "state": st["name"],
                "super_e10_price_eur_per_litre": round(float(SUPER_E10[mi] + rng.uniform(-0.02, 0.02)), 3),
                "super_e5_price_eur_per_litre": round(float(SUPER_E5[mi] + rng.uniform(-0.02, 0.02)), 3),
                "diesel_price_eur_per_litre": round(float(DIESEL_PRICE[mi] + rng.uniform(-0.02, 0.02)), 3),
                "electricity_price_eur_per_kwh": round(float(ELECTRICITY_PRICE[mi] + rng.uniform(-0.01, 0.01)), 3),
                "crude_oil_price_usd": round(float(BRENT_CRUDE[mi] + rng.uniform(-2, 2)), 2),
                "gdp_growth_pct": round(float(GDP_GROWTH[mi] + rng.uniform(-0.2, 0.2)), 2),
                "cpi_inflation_pct": round(float(CPI_INFLATION[mi] + rng.uniform(-0.15, 0.15)), 2),
                "ecb_rate_pct": round(float(ECB_RATE[mi]), 2),
                "auto_loan_apr_pct": round(float(AUTO_LOAN_APR[mi]), 2),
                "incentive_pct_of_atp": round(float(INCENTIVE_PCT_ATP[mi]), 2),
                "inventory_days_supply": round(float(DAYS_SUPPLY[mi]), 1),
                "consumer_confidence_index": round(float(CONSUMER_CONF[mi] + rng.uniform(-1.5, 1.5)), 1),
                "ifo_business_climate": round(float(IFO_CLIMATE[mi] + rng.uniform(-1.0, 1.0)), 1),
                "de_house_price_index": round(float(DE_HOUSE_PRICE_IDX[mi] * (0.92 + st["weight"] / 220.0) + rng.uniform(-1.5, 1.5)), 1),
                "luxury_demand_index": round(float(LUXURY_DEMAND_IDX[mi] + rng.uniform(-3, 3)), 1),
                "commercial_registration_share_pct": round(float(COMMERCIAL_SHARE[mi] + rng.uniform(-1, 1)), 1),
                "quarter_end_month": int(QUARTER_END_MONTH[mi]),
                "year_end_month": int(YEAR_END_MONTH[mi]),
                "summer_holiday_month": int(SUMMER_HOLIDAY_MONTH[mi]),
                "iaa_month": int(IAA_MONTH[mi]),
                "new_model_launches": int(NEW_MODEL_LAUNCHES[mi]),
                "vat_rate_pct": float(VAT_RATE[mi]),
                "co2_price_eur_per_tonne": float(CO2_PRICE[mi]),
                "ev_subsidy_eur": int(EV_SUBSIDY[mi]),
                "unemployment_rate_pct": round(float(UNEMPLOYMENT[mi] + rng.uniform(-0.15, 0.15)), 2),
                "population_millions": st["pop_m"],
                "ev_charging_points_de": charge_points,
            })
    return pd.DataFrame(rows)


def build_sales(rng, n, vehicles_df, dealers_df, customers_df, start, end):
    # ── Monthly volume shape ───────────────────────────────────────────────
    # Three layers: (1) a year-level base — COVID, the chip shortage and the
    # fact the German market never recovered to 2019, (2) the German
    # registration seasonal curve, (3) the group's response to conditions its
    # customers actually feel. The macro response is mean-normalised, so it
    # moves WHICH months book deals without changing annual totals.
    #   pump price  ~ -10% units per +1 EUR/litre
    #   loan APR    ~ -3% units per +1pt
    #   incentives  ~ +1.5% units per +1pt of transaction price
    #   scarcity    :  below ~45 days' supply, unfillable demand walks
    petrol_e = -0.10 * (SUPER_E10 - 1.70)
    apr_e = -0.03 * (AUTO_LOAN_APR - 4.50)
    inc_e = 0.015 * (INCENTIVE_PCT_ATP - 9.00)
    macro_mult = np.clip(1.0 + petrol_e + apr_e + inc_e, 0.85, 1.15)
    scarcity = np.clip(0.70 + DAYS_SUPPLY / 120.0, 0.82, 1.0)
    macro_mult = macro_mult * scarcity
    # Normalise WITHIN each calendar year, weighted by that year's seasonal curve: the macro response then only
    # moves deals between months, and YEAR_BASE alone fixes each year's total. (Normalising over the whole period
    # let the chip-shortage "scarcity" term cut 2021-22 on top of a YEAR_BASE that already reflects the real fall.)
    _seasonal = np.array([RETAIL_SEASONAL_FACTOR[int(m)] for m in MONTH_OF])
    for _year in np.unique(YEAR_OF):
        _sel = YEAR_OF == _year
        macro_mult[_sel] /= (_seasonal[_sel] * macro_mult[_sel]).sum() / _seasonal[_sel].sum()

    # Indexed to KBA Neuzulassungen: 3.61m (2019), 2.92m (2020), 2.62m (2021),
    # 2.65m (2022), 2.84m (2023), 2.82m (2024). The German market genuinely
    # never got back to its 2019 level — an honest and slightly bleak backdrop.
    YEAR_BASE = {2019: 1.00, 2020: 0.81, 2021: 0.73, 2022: 0.73,
                 2023: 0.79, 2024: 0.78, 2025: 0.80, 2026: 0.82}
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

    # ── Powertrain-mix control ────────────────────────────────────────────
    # The catalog is electrified-dense relative to the market, so uniform model
    # selection would overstate BEV share. Weight model choice by fuel type
    # along the REAL German adoption path:
    #   BEV share  1.8% (2019) -> 13.6% (2021) -> 18.4% (2023) -> 13.5% (2024)
    # The 2024 fall is the Umweltbonus cliff of 17 Dec 2023 — the subsidy was
    # halted overnight and BEV registrations dropped by roughly a quarter.
    EV_WEIGHT_BY_YEAR = {2019: 0.15, 2020: 0.45, 2021: 1.10, 2022: 1.60,
                         2023: 1.85, 2024: 1.30, 2025: 1.75, 2026: 2.10}
    # PHEV had its own cliff a year earlier: the plug-in subsidy ended
    # Dec 2022 and company-car buyers moved on.
    PHEV_WEIGHT_BY_YEAR = {2019: 1.00, 2020: 3.00, 2021: 5.50, 2022: 6.00,
                           2023: 2.50, 2024: 2.20, 2025: 2.80, 2026: 3.20}
    # Diesel's long post-Dieselgate decline: ~32% of registrations in 2019,
    # ~17% by 2024.
    DIESEL_WEIGHT_BY_YEAR = {2019: 1.25, 2020: 1.05, 2021: 0.85, 2022: 0.78,
                             2023: 0.70, 2024: 0.65, 2025: 0.62, 2026: 0.58}
    HYBRID_WEIGHT = 2.0

    veh_by_brand = {b: vehicles_df[vehicles_df["brand"] == b].reset_index(drop=True) for b in BRAND_NAMES}
    brand_fuel = {b: veh_by_brand[b]["fuel_type"].to_numpy() for b in BRAND_NAMES}
    brand_cat = {b: veh_by_brand[b]["category"].to_numpy() for b in BRAND_NAMES}
    brand_pop = {
        b: np.array([MODEL_TIER_WEIGHT.get(m, 1.0) for m in veh_by_brand[b]["model"]], dtype=float)
           * np.array([CATEGORY_MARKET_WEIGHT.get(c, 1.0) for c in veh_by_brand[b]["category"]], dtype=float)
        for b in BRAND_NAMES
    }

    # ── Route each sale to a store that actually franchises the brand ──────
    # Demand arises in a Bundesland (weighted by market size), but the customer
    # buys from one of the group's rooftops that carries that brand — preferring
    # a store in their own state, otherwise the nearest one the group operates.
    # The sale is booked at that store, so state/city on the sale is the STORE's
    # location (where revenue lands), not the shopper's home city.
    state_name_to_idx = {s["name"]: i for i, s in enumerate(STATES)}
    dealers_by_brand = {b: dealers_df[dealers_df["brand"] == b] for b in BRAND_NAMES}
    dealers_by_brand_state = {}
    for b in BRAND_NAMES:
        for st in STATE_NAMES:
            sub = dealers_df[(dealers_df["brand"] == b) & (dealers_df["state"] == st)]
            if len(sub):
                dealers_by_brand_state[(b, st)] = sub

    dealer_state = dict(zip(dealers_df["dealer_id"], dealers_df["state"]))
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
    state = [dealer_state[d] for d in dealer_ids]
    city = [dealer_city[d] for d in dealer_ids]
    state_arr = np.array(state)

    # ── Private vs commercial ─────────────────────────────────────────────
    # Drawn per SALE from the real commercial share of registrations (~62-68%,
    # rising over the window), then used to pick a customer of that type.
    comm_share_at_sale = COMMERCIAL_SHARE[sale_month_idx] / 100.0
    wants_commercial = rng.random(n) < comm_share_at_sale
    sale_customer_type = np.where(wants_commercial, "Commercial", "Private")

    # ── Per-store sales effectiveness ────────────────────────────────────
    _elist = list(dealers_df["dealer_id"])
    _eff = rng.normal(0.0, 1.0, len(_elist))
    _eff = _eff - _eff.mean()
    _dealer_eff = dict(zip(_elist, _eff))
    eff_arr = np.array([_dealer_eff[d] for d in dealer_ids])

    # ── Vehicle selection ─────────────────────────────────────────────────
    # Commercial buyers skew to the Dienstwagen shapes — Estate, Compact,
    # Sedan and diesel — while private retail skews to Small Car and SUV.
    vehicle_rows = []
    for b, yr, mo, is_comm in zip(brand_choice, sale_year, sale_mo, wants_commercial):
        pool = veh_by_brand[b]
        fuels = brand_fuel[b]
        cats = brand_cat[b]
        w = brand_pop[b].copy()
        w[fuels == "Electric"] *= EV_WEIGHT_BY_YEAR.get(int(yr), 1.0)
        w[fuels == "Plug-in Hybrid"] *= PHEV_WEIGHT_BY_YEAR.get(int(yr), 1.0)
        w[fuels == "Diesel"] *= DIESEL_WEIGHT_BY_YEAR.get(int(yr), 1.0)
        w[fuels == "Hybrid"] *= HYBRID_WEIGHT
        if is_comm:
            w[np.isin(cats, ["Estate", "Sedan", "Compact"])] *= 1.55
            w[np.isin(cats, ["Small Car"])] *= 0.45
            w[fuels == "Diesel"] *= 1.35
        else:
            w[np.isin(cats, ["Small Car"])] *= 1.30
            w[np.isin(cats, ["SUV"])] *= 1.05
            w[np.isin(cats, ["Estate"])] *= 0.80
        if mo in (3, 6, 9, 12):
            # Quarter-end: the registration push leans on whatever is in stock,
            # which is disproportionately the higher-margin metal.
            w[cats == "SUV"] *= 1.10
            w[cats == "Luxury"] *= 1.15
        w /= w.sum()
        vehicle_rows.append(pool.iloc[int(rng.choice(len(pool), p=w))])
    veh_df_sel = pd.DataFrame(vehicle_rows).reset_index(drop=True)

    # ── Attach a customer: chronological, with a realistic new-vs-returning
    # split, and matched on private/commercial ───────────────────────────────
    # Pools are keyed by (state, customer_type) so a commercial sale lands on a
    # commercial contact. Commercial buyers rebuy far sooner — a fleet cycles
    # every ~3 years, a private owner every ~7.
    P_RETURNING_BY_TYPE = {"Commercial": 0.75, "Private": 0.45}
    P_OUT_OF_STATE = 0.22
    REBUY_MONTHS = {"Commercial": 10, "Private": 26}

    _cust_state = dict(zip(customers_df["customer_id"], customers_df["state"]))
    _cust_type = dict(zip(customers_df["customer_id"], customers_df["customer_type"]))
    _fresh = {}
    for st in STATE_NAMES:
        for ct in ("Private", "Commercial"):
            sel = (customers_df["state"] == st) & (customers_df["customer_type"] == ct)
            _fresh[(st, ct)] = list(rng.permutation(customers_df.loc[sel, "customer_id"].to_numpy()))
    _fresh_any = {ct: [] for ct in ("Private", "Commercial")}

    _bought_month = {}
    _return_all = {ct: [] for ct in ("Private", "Commercial")}
    _return_by_state = {(st, ct): [] for st in STATE_NAMES for ct in ("Private", "Commercial")}
    _want_return = rng.random(n) < np.array(
        [P_RETURNING_BY_TYPE[ct] for ct in sale_customer_type])
    _travel = rng.random(n) < P_OUT_OF_STATE
    _order = np.argsort(sale_month_idx, kind="stable")
    _sm = sale_month_idx.astype(int)
    customer_ids = np.empty(n, dtype=object)

    def _take_fresh(_st, _ct):
        q = _fresh.get((_st, _ct)) if _st is not None else None
        if q:
            return q.pop()
        for _stx in STATE_NAMES:
            if _fresh[(_stx, _ct)]:
                return _fresh[(_stx, _ct)].pop()
        # Fall back to the other type rather than failing — only reachable when
        # one type's population is exhausted.
        _other = "Private" if _ct == "Commercial" else "Commercial"
        for _stx in STATE_NAMES:
            if _fresh[(_stx, _other)]:
                return _fresh[(_stx, _other)].pop()
        return None

    for _i in _order:
        _cur_m = _sm[_i]
        _ct = sale_customer_type[_i]
        _st = None if _travel[_i] else state_arr[_i]
        _gap = REBUY_MONTHS[_ct]
        _picked = None
        if _want_return[_i] and len(_return_all[_ct]) > 200:
            _pool = (_return_by_state.get((_st, _ct)) or []) if _st is not None else _return_all[_ct]
            if len(_pool) < 12:
                _pool = _return_all[_ct]
            for _try in range(6):
                _cand = _pool[int(rng.integers(0, len(_pool)))]
                if _cur_m - _bought_month[_cand] >= _gap:
                    _picked = _cand
                    break
        if _picked is None:
            _cid = _take_fresh(_st, _ct)
            if _cid is None:
                _picked = _return_all[_ct][int(rng.integers(0, len(_return_all[_ct])))]
            else:
                _picked = _cid
                _actual_ct = _cust_type.get(_cid, _ct)
                _return_all[_actual_ct].append(_cid)
                _cst = _cust_state.get(_cid)
                if (_cst, _actual_ct) in _return_by_state:
                    _return_by_state[(_cst, _actual_ct)].append(_cid)
        customer_ids[_i] = _picked
        _bought_month[_picked] = _cur_m

    # The sale's type is the type of the customer actually attached, so the
    # denormalized column can never disagree with the customer master.
    sale_customer_type = np.array([_cust_type.get(c, "Private") for c in customer_ids])
    is_commercial = sale_customer_type == "Commercial"
    # A third of commercial deals are genuine multi-unit fleet orders.
    is_fleet = is_commercial & (rng.random(n) < 0.35)

    _cust_ix = customers_df.set_index("customer_id")
    cust_schufa = _cust_ix["schufa_score"].reindex(customer_ids).to_numpy(dtype=float)
    cust_income_annual = _cust_ix["estimated_annual_income_eur"].reindex(customer_ids).to_numpy(dtype=float)

    # ── Price ────────────────────────────────────────────────────────────
    # base_price is the vehicle's Listenpreis; what moves it is the month's
    # discount environment, plus the extra Nachlass a fleet buyer commands.
    base_price = veh_df_sel["price_eur"].values.astype(float)

    incentive_at_sale = INCENTIVE_PCT_ATP[sale_month_idx]
    discount_pct = np.clip(rng.normal(incentive_at_sale, 3.0, n), 0, 30)
    # Fleet and commercial buyers negotiate structurally harder.
    discount_pct = discount_pct + np.where(is_fleet, 6.0, np.where(is_commercial, 2.5, 0.0))
    discount_pct = np.clip(discount_pct, 0, 34)
    selling_price = (base_price * (1 - discount_pct / 100)).round(0)

    # Umsatzsteuer at the month's rate — 19%, or 16% in the H2-2020 cut.
    vat_rate_at_sale = VAT_RATE[sale_month_idx]
    vat_amount = (selling_price * (vat_rate_at_sale / 100.0)).round(0)

    accessories_rev = np.clip(rng.normal(1400, 600, n), 0, None).round(0)
    insurance_rev = np.clip(rng.normal(700, 300, n), 0, None).round(0)
    extended_warranty = np.where(rng.random(n) < 0.40,
                                 np.clip(rng.normal(1200, 400, n), 0, None), 0).round(0)
    total_excl_vat = (selling_price + accessories_rev + insurance_rev + extended_warranty).round(0)
    total_incl_vat = (total_excl_vat + vat_amount).round(0)

    # ── Financing mix ────────────────────────────────────────────────────
    veh_category = veh_df_sel["category"].values
    veh_fuel = veh_df_sel["fuel_type"].values
    lease_p = np.array([LEASE_RATE_BY_CATEGORY.get(c, 0.35) for c in veh_category])
    lease_p = lease_p + np.where(is_commercial, 0.22, 0.0)
    lease_p = np.clip(lease_p + np.where(veh_fuel == "Electric", 0.08, 0.0), 0.05, 0.85)
    is_lease = rng.random(n) < lease_p
    # Balloon financing (Drei-Wege-/Schlussratenfinanzierung) is the dominant
    # German retail alternative to leasing; cash is a shrinking minority.
    non_lease = rng.choice(["Cash", "Bank Loan", "Dealer Financing", "Balloon Financing"],
                           size=n, p=[0.30, 0.22, 0.20, 0.28])
    financing_type = np.where(is_lease, "Lease", non_lease)
    loan_amount = np.where(financing_type == "Cash", 0, (selling_price * rng.uniform(0.6, 0.95, n)).round(0))

    # ── Lease contract terms ─────────────────────────────────────────────
    list_price = veh_df_sel["price_eur"].values.astype(float)
    lease_term = rng.choice(LEASE_TERMS, size=n, p=LEASE_TERM_WEIGHTS)
    annual_km = rng.choice(LEASE_ANNUAL_KM, size=n, p=LEASE_KM_WEIGHTS)

    resid_pct = veh_df_sel["_residual_36mo"].values.astype(float)
    resid_pct = resid_pct + np.array([LEASE_TERM_RESIDUAL_ADJ[t] for t in lease_term])
    resid_pct = resid_pct + np.select(
        [annual_km == 10000, annual_km == 20000], [0.03, -0.03], default=0.0
    )
    resid_pct = np.clip(resid_pct + rng.normal(0, 0.012, n), 0.22, 0.82)
    residual_eur = (list_price * resid_pct).round(0)

    lease_apr = np.clip(ECB_RATE[sale_month_idx] + rng.normal(3.4, 0.9, n), 0.5, 12.0)
    money_factor = lease_apr / 2400.0
    lease_payment = ((selling_price - residual_eur) / lease_term
                     + (selling_price + residual_eur) * money_factor).round(0)

    _sd = pd.to_datetime(sale_date)
    _tot = _sd.year * 12 + (_sd.month - 1) + lease_term
    maturity = pd.to_datetime(dict(year=_tot // 12, month=_tot % 12 + 1,
                                   day=np.minimum(_sd.day, 28)))

    _no_lease = ~is_lease
    lease_term_col = np.where(_no_lease, np.nan, lease_term)
    resid_pct_col = np.where(_no_lease, np.nan, resid_pct.round(4))
    resid_eur_col = np.where(_no_lease, np.nan, residual_eur)
    lease_payment_col = np.where(_no_lease, np.nan, lease_payment)
    mileage_allow_col = np.where(_no_lease, np.nan, annual_km * lease_term / 12.0)
    maturity_col = pd.Series(maturity).where(is_lease)

    # ── Trade-in (Inzahlungnahme) ────────────────────────────────────────
    # German attach rates are high on private retail — the Autohaus takes the
    # old car as a matter of course. Commercial deals rarely trade: fleet
    # returns go back to the leasing company's remarketing channel instead.
    trade_base = np.where(is_commercial, 0.18,
                          np.where(financing_type == "Cash", 0.42, 0.56))
    has_trade = rng.random(n) < trade_base

    trade_age = rng.choice([3, 4, 5, 6, 7, 8, 9, 10], size=n,
                           p=[0.11, 0.15, 0.16, 0.15, 0.14, 0.12, 0.09, 0.08])
    trade_year = YEAR_OF[sale_month_idx].astype(int) - trade_age
    # German annual mileage runs ~13,000 km, well below the Gulf's ~17,500.
    trade_mileage = np.clip(
        (trade_age * rng.normal(13000, 2800, n)).round(-2), 8000, 300000
    ).astype(int)

    trade_pick = rng.integers(0, len(vehicles_df), n)
    trade_brand = vehicles_df["brand"].values[trade_pick]
    trade_model = vehicles_df["model"].values[trade_pick]
    trade_orig_price = vehicles_df["price_eur"].values[trade_pick].astype(float)

    # German used-car depreciation: ~24% in year one, ~12%/yr compounding.
    dep_factor = 0.76 * np.power(0.88, np.maximum(trade_age - 1, 0))
    expected_km = np.maximum(trade_age * 13000, 1)
    excess_ratio = (trade_mileage - expected_km) / expected_km
    mileage_factor = np.clip(1.0 - 0.20 * excess_ratio, 0.70, 1.20)
    appraised = np.maximum(trade_orig_price * dep_factor * mileage_factor, 800).round(0)

    over_mult = np.array([TRADE_OVER_ALLOWANCE_MULT.get(c, 1.0) for c in veh_category])
    over_allow = np.maximum(rng.normal(900, 700, n) * over_mult, 0).round(0)
    over_allow = np.where(rng.random(n) < 0.25, 0.0, over_allow)

    # Quarter-end and year-end are when the store buys the deal to hit target.
    is_event = np.isin(MONTH_OF[sale_month_idx], [3, 6, 9, 12])
    bonus_p = np.clip(0.18 + 0.22 * is_event + 0.12 * (over_mult > 1.0), 0, 0.75)
    trade_bonus = np.where(
        rng.random(n) < bonus_p,
        rng.choice([500, 750, 1000, 1500, 2500], size=n, p=[0.32, 0.26, 0.22, 0.13, 0.07]),
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
    _schufa = np.nan_to_num(cust_schufa, nan=94.0)
    _income_annual = np.nan_to_num(cust_income_annual, nan=46000.0)
    pay_stress = np.clip((selling_price - 0.55 * _income_annual) / 60000.0, 0, None)
    conv_z = (
        0.07 * eff_arr
        + chan_eff
        + 0.012 * (discount_pct - incentive_at_sale)
        + 0.010 * (_schufa - 94.0)
        - 0.05 * pay_stress
        + 0.05 * has_trade.astype(float)
        # Commercial deals are pre-qualified before anyone drives anything.
        + 0.06 * is_commercial.astype(float)
    )
    conv_p = 0.62 + conv_z
    conv_p = conv_p - conv_p.mean() + 0.62
    conv_p = np.clip(conv_p, 0.28, 0.93)
    test_drive_converted = rng.random(n) < conv_p

    lead_to_close_days = np.clip(
        rng.integers(1, 60, n)
        - (trade_bonus_col / 400.0).round(0)
        - (3.5 * eff_arr).round(0)
        - (14.0 * (conv_p - 0.62)).round(0),
        1, 60,
    ).astype(int)
    salesperson_id = [f"SP{int(x):04d}" for x in rng.integers(1, 400, n)]
    season_multiplier = np.clip(rng.normal(1.0, 0.08, n), 0.75, 1.35)

    quarter = [f"Q{(int(MONTH_OF[mi]) - 1) // 3 + 1}" for mi in sale_month_idx]
    day_of_week = pd.to_datetime(sale_date).day_name()
    season_period = [_season_period(d) for d in sale_date]

    df = pd.DataFrame({
        "sale_id": [f"SAL{i:07d}" for i in range(1, n + 1)],
        "sale_date": sale_date, "year": YEAR_OF[sale_month_idx].astype(int),
        "month": MONTH_OF[sale_month_idx].astype(int),
        "quarter": quarter, "day_of_week": day_of_week, "season_period": season_period,
        "customer_id": customer_ids, "dealer_id": dealer_ids, "vehicle_id": veh_df_sel["vehicle_id"].values,
        "brand": veh_df_sel["brand"].values, "model": veh_df_sel["model"].values,
        "vehicle_category": veh_df_sel["category"].values, "fuel_type": veh_df_sel["fuel_type"].values,
        "state": state, "city": city,
        "customer_type": sale_customer_type, "is_fleet": is_fleet,
        "base_price_eur": base_price.round(0).astype(int),
        "discount_pct": discount_pct.round(2),
        "selling_price_eur": selling_price.astype(int), "vat_amount_eur": vat_amount.astype(int),
        "accessories_revenue_eur": accessories_rev.astype(int),
        "insurance_revenue_eur": insurance_rev.astype(int),
        "extended_warranty_eur": extended_warranty.astype(int),
        "total_revenue_excl_vat": total_excl_vat.astype(int),
        "total_revenue_incl_vat": total_incl_vat.astype(int), "financing_type": financing_type,
        "loan_amount_eur": loan_amount.astype(int), "units_sold": 1,
        "test_drive_converted": test_drive_converted,
        "lead_to_close_days": lead_to_close_days, "salesperson_id": salesperson_id,
        "marketing_channel": marketing_channel, "season_multiplier": season_multiplier.round(3),
        # Lease contract terms (Lease rows only)
        "lease_term_months": lease_term_col,
        "lease_maturity_date": maturity_col.dt.date,
        "residual_value_pct": resid_pct_col,
        "residual_value_eur": resid_eur_col,
        "contract_mileage_allowance": mileage_allow_col,
        "lease_monthly_payment_eur": lease_payment_col,
        # Trade-in activity
        "trade_in_flag": trade_flag_col,
        "trade_in_brand": trade_brand_col,
        "trade_in_model": trade_model_col,
        "trade_in_year": trade_year_col,
        "trade_in_mileage": trade_mileage_col,
        "trade_in_appraised_value_eur": appraised_col,
        "trade_in_allowance_eur": allowance_col,
        "trade_in_over_allowance_eur": over_allow_col,
        "trade_bonus_eur": trade_bonus_col,
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
      - lead times split Domestic vs Import — a car from Wolfsburg lands in
        weeks, one from China takes months
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
        origin_region = BRAND_ORIGIN_REGION.get(dealer["brand"], "EU-Central")
        lo, hi = ORIGIN_LEAD_DAYS.get(origin_region, (16, 34))
        is_domestic = origin_region == "Germany"

        for _, veh in pool.iterrows():
            resid = float(veh["_residual_36mo"])
            desirability = np.clip((resid - 0.34) / (0.56 - 0.34), 0.0, 1.0)
            lead_time = int(rng.integers(lo, hi))

            # German floorplan (Einkaufsfinanzierung) runs a touch below the
            # Gulf rate.
            floorplan_apr = 0.065
            holding_per_day = round(
                veh["price_eur"] * floorplan_apr / 365.0 + rng.uniform(4.0, 11.0), 2
            )

            observed_rate = rate_lookup.get((dealer["dealer_id"], veh["vehicle_id"]), 0.0)
            base_rate = max(observed_rate, per_model_capacity * 0.06)

            zone = WAREHOUSE_ZONES[inv_id % len(WAREHOUSE_ZONES)]
            hub = (rng.choice(GERMAN_PLANTS) if is_domestic else rng.choice(IMPORT_PORTS))

            for mi, month_start in enumerate(months):
                month_no = month_start.month
                # German selling strength peaks at quarter-ends, troughs in
                # January and August.
                seasonal = RETAIL_SEASONAL_FACTOR[month_no]
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
                    "holding_cost_per_day_eur": holding_per_day,
                    "estimated_holding_cost_eur": round(holding_per_day * stock * 30.0, 2),
                    "units_sold_last_30d": sold_30d,
                    "units_ordered": units_ordered,
                    "transit_stock": in_transit,
                    "origin_hub": hub,
                    "warehouse_zone": zone,
                    "last_replenishment_date": last_replen,
                    "supplier_lead_time_days": lead_time,
                    # EU-built stock needs no clearance at all.
                    "customs_cleared": True if origin_region != "China" else bool(rng.random() < 0.92),
                })
                inv_id += 1

    return pd.DataFrame(rows)


def _derive_customer_history(customers, sales, end):
    """
    Replace the decorative purchase-history fields with each customer's real
    behaviour in the sales table:
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
                     dealers_per_state=None, n_rooftops=None):
    rng = np.random.default_rng(seed)
    os.makedirs(out_dir, exist_ok=True)

    vehicles = build_vehicle_catalog(rng, n_trims=n_trims)
    dealers = build_dealers(rng, n_rooftops=n_rooftops, dealers_per_state=dealers_per_state)
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
    # of 24 rooftops across six Bundesländer (not a market sample).
    generate_dataset(
        os.path.join(ROOT, "realdata-datasets"), seed=42,
        n_customers=70000, n_rooftops=24, n_sales=100000, n_trims=2,
    )
    # automobile_datasets: larger "test" mode dataset (legacy market grid)
    generate_dataset(
        os.path.join(ROOT, "automobile_datasets"), seed=7,
        n_customers=98000, dealers_per_state=15, n_sales=140000, n_trims=3,
    )


if __name__ == "__main__":
    main()
