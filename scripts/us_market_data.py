"""
US market reference data for scripts/generate_us_data.py: geography, brand and model catalog, taxes.

Model specs are approximate 2025-26 US-market figures written the way an American shopper reads them (MSRP in USD,
horsepower, EPA mpg and miles of range); the generator converts to the platform's metric canon (kW, l/100km, km).
They are realistic, not authoritative: trim-level prices, mpg and residuals vary by source and model year.
"""

# ── Geography: a mainstream Sun Belt / Midwest group across six states ─────────────────────────────────────────
# weight = share of the group's demand; pop_m = state population in millions (Census 2023 estimate);
# gas_offset = typical retail regular-gasoline difference vs the US average, USD per gallon (EIA regional patterns,
# approximate); tax = effective state + typical local sales/title tax on a new vehicle, percent (approximate; real
# rules differ: NC and GA charge flat highway-use / title-ad-valorem taxes, TN caps local tax on the first ~$1.6k).
STATES = [
    {"name": "Texas", "weight": 30, "pop_m": 30.5, "gas_offset": -0.27, "tax": 6.25, "ev_index": 0.85,
     "cities": [("Dallas", 32.7767, -96.7970, "752"), ("Houston", 29.7604, -95.3698, "770"),
                ("Austin", 30.2672, -97.7431, "787"), ("San Antonio", 29.4241, -98.4936, "782"),
                ("Fort Worth", 32.7555, -97.3308, "761")]},
    {"name": "Florida", "weight": 24, "pop_m": 22.6, "gas_offset": -0.03, "tax": 6.7, "ev_index": 0.90,
     "cities": [("Miami", 25.7617, -80.1918, "331"), ("Orlando", 28.5383, -81.3792, "328"),
                ("Tampa", 27.9506, -82.4572, "336"), ("Jacksonville", 30.3322, -81.6557, "322")]},
    {"name": "Georgia", "weight": 14, "pop_m": 11.0, "gas_offset": -0.13, "tax": 7.0, "ev_index": 0.80,
     "cities": [("Atlanta", 33.7490, -84.3880, "303"), ("Savannah", 32.0809, -81.0912, "314"),
                ("Augusta", 33.4735, -82.0105, "309")]},
    {"name": "Ohio", "weight": 12, "pop_m": 11.8, "gas_offset": -0.10, "tax": 7.25, "ev_index": 0.70,
     "cities": [("Columbus", 39.9612, -82.9988, "432"), ("Cleveland", 41.4993, -81.6944, "441"),
                ("Cincinnati", 39.1031, -84.5120, "452")]},
    {"name": "North Carolina", "weight": 12, "pop_m": 11.0, "gas_offset": -0.11, "tax": 3.0, "ev_index": 0.85,
     "cities": [("Charlotte", 35.2271, -80.8431, "282"), ("Raleigh", 35.7796, -78.6382, "276"),
                ("Greensboro", 36.0726, -79.7920, "274")]},
    {"name": "Tennessee", "weight": 8, "pop_m": 7.1, "gas_offset": -0.19, "tax": 7.5, "ev_index": 0.75,
     "cities": [("Nashville", 36.1627, -86.7816, "372"), ("Memphis", 35.1495, -90.0490, "381"),
                ("Knoxville", 35.9606, -83.9207, "379")]},
]

# Brand -> (relative share of US new-vehicle sales 2024, assembly region). Shares are approximate; a mainstream
# multi-franchise group carries most of the volume brands. "North America" assembly = Domestic for lead-time purposes.
BRAND_SHARE = {
    "Toyota": 15.3, "Ford": 12.9, "Chevrolet": 11.6, "Honda": 9.4, "Hyundai": 5.5, "Nissan": 5.1, "Kia": 4.6,
    "Subaru": 3.9, "GMC": 3.8, "Jeep": 3.5, "Ram": 3.3, "Mazda": 2.4, "Volkswagen": 2.2, "Cadillac": 1.1,
    "Dodge": 1.0, "Buick": 0.9,
}
BRAND_ORIGIN_REGION = {
    "Toyota": "North America", "Ford": "North America", "Chevrolet": "North America", "Honda": "North America",
    "GMC": "North America", "Jeep": "North America", "Ram": "North America", "Cadillac": "North America",
    "Dodge": "North America", "Nissan": "North America",
    "Hyundai": "Asia", "Kia": "Asia", "Subaru": "Asia", "Mazda": "Asia", "Buick": "Asia", "Volkswagen": "Europe",
}
ORIGIN_LEAD_DAYS = {"North America": (7, 24), "Asia": (32, 62), "Europe": (38, 66)}
US_PLANTS = ["Dearborn, MI", "Louisville, KY", "Arlington, TX", "Fort Wayne, IN", "Kansas City, MO", "Georgetown, KY",
             "Princeton, IN", "Smyrna, TN", "Marysville, OH", "Spring Hill, TN", "Toledo, OH", "Montgomery, AL",
             "West Point, GA", "Lansing, MI", "Chattanooga, TN"]
IMPORT_PORTS = ["Port of Long Beach", "Port of Savannah", "Port of Baltimore", "Port of Houston",
                "Port of Jacksonville", "Port of Charleston"]
BRAND_WARRANTY_YEARS = {"Hyundai": 5, "Kia": 5, "Volkswagen": 4, "Cadillac": 4}     # bumper-to-bumper; others 3

BRAND_TRIMS = {
    "Toyota": ["LE", "SE", "XLE", "Limited"], "Ford": ["XLT", "Lariat", "Platinum", "Limited"],
    "Chevrolet": ["LT", "RST", "Z71", "High Country"], "GMC": ["SLE", "SLT", "AT4", "Denali"],
    "Honda": ["LX", "EX", "Sport", "Touring"], "Nissan": ["S", "SV", "SR", "Platinum"],
    "Hyundai": ["SE", "SEL", "N Line", "Limited"], "Kia": ["LX", "EX", "S", "SX"],
    "Jeep": ["Sport", "Latitude", "Limited", "Overland"], "Ram": ["Tradesman", "Big Horn", "Laramie", "Limited"],
    "Subaru": ["Base", "Premium", "Sport", "Limited"], "Mazda": ["Select", "Preferred", "Carbon Edition", "Premium Plus"],
    "Volkswagen": ["S", "SE", "SEL", "SEL R-Line"], "Dodge": ["SXT", "GT", "R/T", "Scat Pack"],
    "Buick": ["Preferred", "Sport Touring", "Avenir", "Essence"],
    "Cadillac": ["Luxury", "Premium Luxury", "Sport", "V-Series"],
}

# Tuple: (model, category, fuel, msrp_usd, hp, engine_cc, mpg_combined, kwh_per_100mi, range_mi, seats, drive,
#         residual_36mo, launch_year)
# mpg for hybrids is the combined EPA figure; for EVs mpg is None and kwh_per_100mi / range_mi are given.
BRAND_CATALOG = {
    "Toyota": [
        ("Corolla",        "Sedan",     "Petrol",   22500, 169, 1987, 35, None, None, 5, "FWD", 0.58, 2020),
        ("Camry",          "Sedan",     "Hybrid",   29000, 232, 2487, 51, None, None, 5, "FWD", 0.57, 2025),
        ("Prius",          "Hatchback", "Hybrid",   28000, 194, 1987, 57, None, None, 5, "FWD", 0.56, 2023),
        ("RAV4",           "SUV",       "Petrol",   30500, 203, 2487, 30, None, None, 5, "AWD", 0.62, 2019),
        ("RAV4 Hybrid",    "SUV",       "Hybrid",   33500, 219, 2487, 39, None, None, 5, "AWD", 0.63, 2019),
        ("Highlander",     "SUV",       "Petrol",   40500, 265, 2393, 24, None, None, 7, "AWD", 0.60, 2020),
        ("4Runner",        "SUV",       "Petrol",   42500, 278, 3956, 19, None, None, 7, "4WD", 0.68, 2010),
        ("Tacoma",         "Pickup",    "Petrol",   33500, 278, 2393, 22, None, None, 5, "4WD", 0.68, 2024),
        ("Tundra",         "Pickup",    "Petrol",   43000, 348, 3445, 20, None, None, 5, "4WD", 0.62, 2022),
        ("Sienna",         "Minivan",   "Hybrid",   39500, 245, 2487, 36, None, None, 8, "FWD", 0.60, 2021),
        ("bZ4X",           "SUV",       "Electric", 38000, 214, None, None, 29, 252, 5, "AWD", 0.36, 2023),
    ],
    "Ford": [
        ("F-150",          "Pickup",    "Petrol",   38000, 325, 2694, 20, None, None, 5, "4WD", 0.56, 2021),
        ("F-150 Lightning","Pickup",    "Electric", 56000, 452, None, None, 48, 320, 5, "4WD", 0.40, 2022),
        ("F-250 Super Duty","Pickup",   "Diesel",   52000, 475, 6699, 15, None, None, 6, "4WD", 0.56, 2023),
        ("Maverick",       "Pickup",    "Hybrid",   29000, 191, 2488, 37, None, None, 5, "FWD", 0.58, 2022),
        ("Escape",         "SUV",       "Petrol",   30000, 180, 1499, 28, None, None, 5, "FWD", 0.46, 2020),
        ("Bronco Sport",   "SUV",       "Petrol",   32500, 180, 1499, 26, None, None, 5, "AWD", 0.56, 2021),
        ("Bronco",         "SUV",       "Petrol",   40000, 300, 2300, 20, None, None, 5, "4WD", 0.63, 2021),
        ("Explorer",       "SUV",       "Petrol",   39500, 300, 2300, 23, None, None, 7, "RWD", 0.52, 2020),
        ("Expedition",     "SUV",       "Petrol",   57000, 380, 3496, 20, None, None, 8, "4WD", 0.55, 2022),
        ("Mustang",        "Coupe",     "Petrol",   33000, 315, 2261, 24, None, None, 4, "RWD", 0.55, 2024),
        ("Mustang Mach-E", "SUV",       "Electric", 40000, 266, None, None, 32, 250, 5, "RWD", 0.36, 2021),
    ],
    "Chevrolet": [
        ("Trax",           "SUV",       "Petrol",   21500, 137, 1330, 30, None, None, 5, "FWD", 0.46, 2024),
        ("Equinox",        "SUV",       "Petrol",   29500, 175, 1498, 28, None, None, 5, "FWD", 0.48, 2025),
        ("Equinox EV",     "SUV",       "Electric", 34500, 210, None, None, 31, 319, 5, "FWD", 0.34, 2024),
        ("Blazer",         "SUV",       "Petrol",   37000, 228, 1998, 24, None, None, 5, "FWD", 0.47, 2019),
        ("Traverse",       "SUV",       "Petrol",   38500, 228, 1998, 22, None, None, 7, "FWD", 0.49, 2024),
        ("Tahoe",          "SUV",       "Petrol",   61000, 355, 5328, 18, None, None, 8, "4WD", 0.57, 2021),
        ("Suburban",       "SUV",       "Petrol",   63000, 355, 5328, 17, None, None, 9, "4WD", 0.57, 2021),
        ("Silverado 1500", "Pickup",    "Petrol",   38500, 310, 2700, 20, None, None, 5, "4WD", 0.54, 2019),
        ("Silverado 2500HD","Pickup",   "Diesel",   50000, 470, 6600, 15, None, None, 6, "4WD", 0.54, 2020),
        ("Colorado",       "Pickup",    "Petrol",   31500, 237, 2700, 22, None, None, 5, "4WD", 0.52, 2023),
        ("Malibu",         "Sedan",     "Petrol",   26500, 163, 1490, 29, None, None, 5, "FWD", 0.38, 2019),
    ],
    "GMC": [
        ("Sierra 1500",    "Pickup",    "Petrol",   40500, 310, 2700, 20, None, None, 5, "4WD", 0.55, 2019),
        ("Sierra 2500HD",  "Pickup",    "Diesel",   52000, 470, 6600, 15, None, None, 6, "4WD", 0.55, 2020),
        ("Canyon",         "Pickup",    "Petrol",   33500, 237, 2700, 22, None, None, 5, "4WD", 0.54, 2023),
        ("Terrain",        "SUV",       "Petrol",   30500, 175, 1498, 26, None, None, 5, "AWD", 0.48, 2018),
        ("Acadia",         "SUV",       "Petrol",   41000, 328, 2000, 23, None, None, 7, "AWD", 0.50, 2024),
        ("Yukon",          "SUV",       "Petrol",   65000, 355, 5328, 17, None, None, 8, "4WD", 0.58, 2021),
    ],
    "Honda": [
        ("Civic",          "Sedan",     "Petrol",   24500, 158, 1996, 35, None, None, 5, "FWD", 0.62, 2022),
        ("Accord",         "Sedan",     "Petrol",   28500, 192, 1498, 32, None, None, 5, "FWD", 0.58, 2023),
        ("Accord Hybrid",  "Sedan",     "Hybrid",   33500, 204, 1993, 48, None, None, 5, "FWD", 0.58, 2023),
        ("HR-V",           "SUV",       "Petrol",   25500, 158, 1996, 28, None, None, 5, "AWD", 0.56, 2023),
        ("CR-V",           "SUV",       "Petrol",   31000, 190, 1498, 30, None, None, 5, "AWD", 0.62, 2023),
        ("CR-V Hybrid",    "SUV",       "Hybrid",   35500, 204, 1993, 40, None, None, 5, "AWD", 0.62, 2023),
        ("Passport",       "SUV",       "Petrol",   43000, 280, 3471, 21, None, None, 5, "AWD", 0.55, 2019),
        ("Pilot",          "SUV",       "Petrol",   41500, 285, 3471, 22, None, None, 8, "AWD", 0.56, 2023),
        ("Odyssey",        "Minivan",   "Petrol",   40500, 280, 3471, 22, None, None, 8, "FWD", 0.55, 2018),
        ("Ridgeline",      "Pickup",    "Petrol",   41000, 280, 3471, 21, None, None, 5, "AWD", 0.56, 2017),
        ("Prologue",       "SUV",       "Electric", 47500, 288, None, None, 35, 296, 5, "AWD", 0.34, 2024),
    ],
    "Nissan": [
        ("Versa",          "Sedan",     "Petrol",   17500, 122, 1598, 35, None, None, 5, "FWD", 0.38, 2020),
        ("Sentra",         "Sedan",     "Petrol",   21500, 149, 1998, 33, None, None, 5, "FWD", 0.42, 2020),
        ("Altima",         "Sedan",     "Petrol",   27000, 188, 2488, 32, None, None, 5, "FWD", 0.41, 2019),
        ("Kicks",          "SUV",       "Petrol",   22500, 122, 1598, 33, None, None, 5, "FWD", 0.44, 2025),
        ("Rogue",          "SUV",       "Petrol",   30000, 201, 1498, 30, None, None, 5, "AWD", 0.48, 2021),
        ("Murano",         "SUV",       "Petrol",   39500, 260, 3498, 23, None, None, 5, "AWD", 0.45, 2019),
        ("Pathfinder",     "SUV",       "Petrol",   38000, 284, 3498, 23, None, None, 7, "AWD", 0.50, 2022),
        ("Frontier",       "Pickup",    "Petrol",   33500, 310, 3800, 21, None, None, 5, "4WD", 0.55, 2022),
        ("Ariya",          "SUV",       "Electric", 40000, 214, None, None, 33, 289, 5, "FWD", 0.32, 2023),
    ],
    "Hyundai": [
        ("Elantra",        "Sedan",     "Petrol",   23000, 147, 1999, 37, None, None, 5, "FWD", 0.50, 2021),
        ("Sonata",         "Sedan",     "Petrol",   28000, 191, 2497, 32, None, None, 5, "FWD", 0.44, 2020),
        ("Venue",          "SUV",       "Petrol",   21500, 121, 1598, 30, None, None, 5, "FWD", 0.47, 2020),
        ("Kona",           "SUV",       "Petrol",   26000, 147, 1999, 31, None, None, 5, "FWD", 0.48, 2024),
        ("Tucson",         "SUV",       "Petrol",   30000, 187, 2497, 26, None, None, 5, "AWD", 0.54, 2022),
        ("Tucson Hybrid",  "SUV",       "Hybrid",   34500, 231, 1598, 37, None, None, 5, "AWD", 0.55, 2022),
        ("Santa Fe",       "SUV",       "Petrol",   34500, 191, 2497, 27, None, None, 5, "AWD", 0.51, 2024),
        ("Palisade",       "SUV",       "Petrol",   39500, 291, 3778, 22, None, None, 8, "AWD", 0.58, 2020),
        ("Santa Cruz",     "Pickup",    "Petrol",   29500, 191, 2497, 24, None, None, 5, "AWD", 0.52, 2022),
        ("Ioniq 5",        "SUV",       "Electric", 43000, 225, None, None, 29, 303, 5, "AWD", 0.34, 2022),
    ],
    "Kia": [
        ("Forte",          "Sedan",     "Petrol",   21500, 147, 1999, 33, None, None, 5, "FWD", 0.46, 2020),
        ("K5",             "Sedan",     "Petrol",   27500, 180, 1598, 31, None, None, 5, "FWD", 0.44, 2021),
        ("Soul",           "Hatchback", "Petrol",   21500, 147, 1999, 31, None, None, 5, "FWD", 0.44, 2020),
        ("Seltos",         "SUV",       "Petrol",   26500, 146, 1999, 29, None, None, 5, "AWD", 0.50, 2021),
        ("Sportage",       "SUV",       "Petrol",   29000, 187, 2497, 28, None, None, 5, "AWD", 0.52, 2023),
        ("Sportage Hybrid","SUV",       "Hybrid",   33000, 227, 1598, 42, None, None, 5, "AWD", 0.54, 2023),
        ("Sorento",        "SUV",       "Petrol",   34500, 191, 2497, 26, None, None, 7, "AWD", 0.52, 2021),
        ("Telluride",      "SUV",       "Petrol",   39500, 291, 3778, 22, None, None, 8, "AWD", 0.62, 2020),
        ("Carnival",       "Minivan",   "Petrol",   35000, 290, 3470, 22, None, None, 8, "FWD", 0.52, 2022),
        ("EV6",            "SUV",       "Electric", 43500, 225, None, None, 30, 310, 5, "AWD", 0.34, 2022),
    ],
    "Jeep": [
        ("Compass",        "SUV",       "Petrol",   29500, 200, 1995, 26, None, None, 5, "4WD", 0.48, 2022),
        ("Wrangler",       "SUV",       "Petrol",   34500, 285, 3604, 20, None, None, 5, "4WD", 0.66, 2019),
        ("Grand Cherokee", "SUV",       "Petrol",   42000, 293, 3604, 22, None, None, 5, "4WD", 0.52, 2022),
        ("Gladiator",      "Pickup",    "Petrol",   39500, 285, 3604, 19, None, None, 5, "4WD", 0.64, 2020),
        ("Wagoneer",       "SUV",       "Petrol",   61000, 420, 2993, 20, None, None, 8, "4WD", 0.48, 2022),
    ],
    "Ram": [
        ("1500",           "Pickup",    "Petrol",   41000, 305, 3604, 21, None, None, 6, "4WD", 0.54, 2019),
        ("1500 Classic",   "Pickup",    "Petrol",   38000, 305, 3604, 20, None, None, 6, "4WD", 0.52, 2019),
        ("2500",           "Pickup",    "Diesel",   50000, 420, 6698, 15, None, None, 6, "4WD", 0.56, 2019),
    ],
    "Subaru": [
        ("Impreza",        "Hatchback", "Petrol",   24500, 152, 2498, 30, None, None, 5, "AWD", 0.56, 2024),
        ("Legacy",         "Sedan",     "Petrol",   26500, 182, 2498, 30, None, None, 5, "AWD", 0.50, 2020),
        ("WRX",            "Sedan",     "Petrol",   33500, 271, 2387, 22, None, None, 5, "AWD", 0.56, 2022),
        ("BRZ",            "Coupe",     "Petrol",   31500, 228, 2387, 25, None, None, 4, "RWD", 0.55, 2022),
        ("Crosstrek",      "SUV",       "Petrol",   27500, 152, 2498, 29, None, None, 5, "AWD", 0.60, 2024),
        ("Forester",       "SUV",       "Petrol",   31500, 182, 2498, 29, None, None, 5, "AWD", 0.62, 2019),
        ("Outback",        "SUV",       "Petrol",   31500, 182, 2498, 29, None, None, 5, "AWD", 0.60, 2020),
        ("Ascent",         "SUV",       "Petrol",   37500, 260, 2387, 22, None, None, 8, "AWD", 0.55, 2019),
        ("Solterra",       "SUV",       "Electric", 45500, 215, None, None, 34, 227, 5, "AWD", 0.32, 2023),
    ],
    "Mazda": [
        ("Mazda3",         "Sedan",     "Petrol",   25500, 191, 2488, 31, None, None, 5, "FWD", 0.55, 2019),
        ("MX-5 Miata",     "Coupe",     "Petrol",   30500, 181, 1998, 30, None, None, 2, "RWD", 0.58, 2016),
        ("CX-30",          "SUV",       "Petrol",   26500, 191, 2488, 28, None, None, 5, "AWD", 0.52, 2020),
        ("CX-5",           "SUV",       "Petrol",   31000, 187, 2488, 28, None, None, 5, "AWD", 0.56, 2017),
        ("CX-50",          "SUV",       "Petrol",   33500, 187, 2488, 27, None, None, 5, "AWD", 0.54, 2023),
        ("CX-90",          "SUV",       "Petrol",   41000, 280, 3283, 25, None, None, 7, "AWD", 0.52, 2024),
    ],
    "Volkswagen": [
        ("Jetta",          "Sedan",     "Petrol",   22500, 158, 1984, 32, None, None, 5, "FWD", 0.44, 2019),
        ("Golf GTI",       "Hatchback", "Petrol",   32500, 241, 1984, 27, None, None, 5, "FWD", 0.56, 2022),
        ("Taos",           "SUV",       "Petrol",   26500, 158, 1984, 28, None, None, 5, "AWD", 0.44, 2022),
        ("Tiguan",         "SUV",       "Petrol",   31500, 184, 1984, 25, None, None, 7, "AWD", 0.48, 2018),
        ("Atlas",          "SUV",       "Petrol",   38000, 269, 1984, 22, None, None, 7, "AWD", 0.46, 2018),
        ("ID.4",           "SUV",       "Electric", 40500, 201, None, None, 33, 291, 5, "RWD", 0.32, 2021),
    ],
    "Cadillac": [
        ("CT4",            "Luxury",    "Petrol",   34500, 237, 1998, 26, None, None, 5, "RWD", 0.40, 2020),
        ("CT5",            "Luxury",    "Petrol",   40000, 237, 1998, 25, None, None, 5, "RWD", 0.42, 2020),
        ("XT5",            "Luxury",    "Petrol",   46500, 235, 1998, 24, None, None, 5, "AWD", 0.46, 2017),
        ("XT6",            "Luxury",    "Petrol",   54000, 310, 3649, 22, None, None, 7, "AWD", 0.44, 2020),
        ("Escalade",       "Luxury",    "Petrol",   86000, 420, 6162, 16, None, None, 7, "4WD", 0.60, 2021),
        ("Lyriq",          "Luxury",    "Electric", 58500, 340, None, None, 35, 314, 5, "RWD", 0.32, 2023),
    ],
    "Dodge": [
        ("Charger",        "Sedan",     "Petrol",   34500, 292, 3604, 21, None, None, 5, "RWD", 0.46, 2019),
        ("Challenger",     "Coupe",     "Petrol",   33500, 303, 3604, 21, None, None, 5, "RWD", 0.52, 2019),
        ("Durango",        "SUV",       "Petrol",   41500, 293, 3604, 20, None, None, 7, "AWD", 0.50, 2019),
        ("Hornet",         "SUV",       "Petrol",   32500, 268, 1995, 25, None, None, 5, "AWD", 0.40, 2023),
    ],
    "Buick": [
        ("Encore GX",      "SUV",       "Petrol",   26500, 155, 1341, 30, None, None, 5, "FWD", 0.40, 2020),
        ("Envision",       "SUV",       "Petrol",   36000, 228, 1998, 25, None, None, 5, "AWD", 0.42, 2021),
        ("Enclave",        "SUV",       "Petrol",   47500, 310, 3649, 22, None, None, 7, "AWD", 0.48, 2018),
    ],
}

# Nameplate demand skew: real US retail volume is heavily concentrated in a handful of nameplates.
MODEL_FLAGSHIP = {
    "F-150", "Silverado 1500", "1500", "Sierra 1500", "RAV4", "CR-V", "Civic", "Camry", "Corolla", "Equinox", "Rogue",
    "Tucson", "Tacoma", "Explorer", "Escape", "Grand Cherokee", "Wrangler", "Forester", "Outback", "Accord", "Altima",
    "Sportage", "Elantra", "Model Y", "Tahoe", "Highlander", "Bronco Sport", "Trax", "Sentra", "Santa Fe",
}
MODEL_STRONG = {
    "RAV4 Hybrid", "CR-V Hybrid", "Accord Hybrid", "Tucson Hybrid", "Sportage Hybrid", "Prius", "Sienna", "Tundra",
    "Bronco", "Maverick", "Blazer", "Traverse", "Colorado", "Canyon", "Terrain", "Acadia", "Yukon", "Suburban",
    "Pilot", "HR-V", "Passport", "Odyssey", "Ridgeline", "Kicks", "Pathfinder", "Frontier", "Kona", "Palisade",
    "Telluride", "Seltos", "Sorento", "Forte", "K5", "Soul", "Compass", "Gladiator", "Crosstrek", "Ascent",
    "Impreza", "Mazda3", "CX-5", "CX-30", "CX-50", "Jetta", "Taos", "Tiguan", "Mustang", "Durango", "Envision",
    "Encore GX", "Charger", "Escalade", "XT5", "1500 Classic",
}
MODEL_NICHE = {
    "F-250 Super Duty", "Silverado 2500HD", "Sierra 2500HD", "2500", "F-150 Lightning", "Mustang Mach-E", "bZ4X",
    "Equinox EV", "Prologue", "Ariya", "Ioniq 5", "EV6", "ID.4", "Solterra", "Lyriq", "Wagoneer", "Expedition",
    "4Runner", "MX-5 Miata", "BRZ", "WRX", "Golf GTI", "Challenger", "Hornet", "Versa", "Murano", "Santa Cruz",
    "Carnival", "CX-90", "Atlas", "XT6", "CT4", "CT5", "Malibu", "Legacy", "Venue", "Enclave",
}
MODEL_TIER_WEIGHT = {**{m: 2.8 for m in MODEL_FLAGSHIP}, **{m: 1.6 for m in MODEL_STRONG}, **{m: 0.40 for m in MODEL_NICHE}}

TRIM_PRICE_MULT = [1.00, 1.16, 1.36, 1.62]
TRIM_HP_MULT = [1.00, 1.00, 1.05, 1.12]
TRIM_MPG_DELTA = [0.0, -0.4, -0.8, -1.4]          # heavier trims burn a little more
TRIM_KWH_DELTA = [0.0, 0.5, 1.0, 1.6]              # kWh/100mi added

# Segment mix control (tuned to land near the real US shape for a mainstream group: SUV ~ 57%, Pickup ~ 19%,
# Sedan ~ 14%, Minivan ~ 3%, Hatchback ~ 3%, Coupe ~ 1.5%, Luxury ~ 1.5%). Tune these, not the catalog, if the booked mix drifts.
CATEGORY_MARKET_WEIGHT = {"SUV": 0.86, "Pickup": 0.75, "Sedan": 0.80, "Hatchback": 0.95, "Minivan": 1.10,
                          "Luxury": 0.85, "Coupe": 0.90}
MANUAL_MODELS = {"MX-5 Miata": 0.35, "BRZ": 0.40, "WRX": 0.30, "Golf GTI": 0.15, "Mustang": 0.08, "Wrangler": 0.12}
CVT_BRANDS = {"Nissan", "Subaru"}

LEASE_RATE_BY_CATEGORY = {"Luxury": 0.50, "Sedan": 0.26, "SUV": 0.22, "Pickup": 0.10, "Minivan": 0.15,
                          "Hatchback": 0.20, "Coupe": 0.25}
TRADE_OVER_ALLOWANCE_MULT = {"Sedan": 1.30, "Hatchback": 1.25, "Minivan": 1.10, "SUV": 0.95, "Pickup": 0.85,
                             "Luxury": 1.10, "Coupe": 1.20}

DEALER_FAMILY_NAMES = ["Sunbelt", "Lone Star", "Heartland", "Peach State", "Buckeye", "Carolina", "Volunteer", "Gateway",
                       "Premier", "Landmark", "Crossroads", "Summit", "Liberty", "Patriot", "Metro", "Capital", "Coastal",
                       "Magnolia", "Cardinal", "Frontier"]
DEALER_STREETS = ["Auto Mall Dr", "Motor Pkwy", "Dealer Way", "Automotive Blvd", "Auto Plaza", "Motor Mile",
                  "US Hwy 31", "State Hwy 121", "Interstate Access Rd", "Commerce Dr"]

FIRST_NAMES = [
    "James", "Michael", "Robert", "John", "David", "William", "Richard", "Joseph", "Thomas", "Christopher", "Daniel",
    "Matthew", "Anthony", "Mark", "Steven", "Andrew", "Kevin", "Brian", "Jason", "Eric", "Ryan", "Jacob", "Tyler",
    "Brandon", "Mary", "Jennifer", "Linda", "Patricia", "Elizabeth", "Susan", "Jessica", "Sarah", "Karen", "Nancy",
    "Lisa", "Ashley", "Emily", "Amanda", "Melissa", "Stephanie", "Nicole", "Rachel", "Megan", "Lauren", "Samantha",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez",
    "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez",
    "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen",
    "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall",
    "Rivera", "Campbell", "Mitchell", "Carter", "Roberts",
]
NAME_POOLS_EXTRA = {
    "hispanic": (["Jose", "Luis", "Carlos", "Juan", "Miguel", "Maria", "Ana", "Carmen", "Sofia", "Isabel", "Diego", "Ricardo"],
                 ["Garcia", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Perez", "Sanchez", "Ramirez", "Torres"]),
    "indian": (["Amit", "Raj", "Vikram", "Sanjay", "Anil", "Priya", "Neha", "Anita", "Kavita", "Deepa", "Rohan", "Arjun"],
               ["Patel", "Shah", "Singh", "Sharma", "Kumar", "Gupta", "Reddy", "Iyer", "Mehta", "Desai"]),
    "chinese": (["Wei", "Jun", "Ming", "Hao", "Lei", "Li", "Mei", "Xin", "Yan", "Jing", "Kevin", "Jenny"],
                ["Chen", "Wang", "Zhang", "Liu", "Yang", "Huang", "Zhao", "Wu", "Zhou", "Lin"]),
}
# Foreign-born share of the US resident population is ~14%; the buyer book mirrors that mix by birth country.
NATIONALITIES = [("United States", 86.0, "general"), ("Mexico", 2.6, "hispanic"), ("India", 1.6, "indian"),
                 ("China", 1.0, "chinese"), ("Philippines", 0.7, "general"), ("Vietnam", 0.6, "general"),
                 ("Canada", 0.5, "general"), ("Other", 7.0, "general")]
OCCUPATIONS = ["Professional / Technical", "Management", "Healthcare", "Education", "Skilled Trades",
               "Sales / Service", "Administrative", "Self-Employed", "Retired", "Government / Military"]
OCCUPATION_WEIGHTS = [0.17, 0.14, 0.11, 0.07, 0.11, 0.13, 0.08, 0.07, 0.08, 0.04]
INCOME_BRACKETS = ["<$40K", "$40K-$70K", "$70K-$110K", "$110K-$170K", ">$170K"]
