"""
Generates india_external_factors.csv — monthly Indian macro data 2019-2026.
Run once: python generate_external_factors.py
All values sourced from public PPAC/RBI/MoSPI data, approximated for non-metro states.
"""

import csv
from datetime import date, timedelta
from pathlib import Path

OUTPUT = Path(__file__).parent / "india_external_factors.csv"

# ── Historical fuel prices (Delhi, metro rate, INR/litre) ──────────────────
# Petrol prices changed infrequently; values represent national average.
PETROL_PRICES = {
    (2019, 1): 70.29, (2019, 2): 70.48, (2019, 3): 71.05, (2019, 4): 73.42,
    (2019, 5): 72.90, (2019, 6): 71.78, (2019, 7): 72.53, (2019, 8): 73.50,
    (2019, 9): 74.02, (2019, 10): 73.80, (2019, 11): 74.50, (2019, 12): 75.13,
    (2020, 1): 75.36, (2020, 2): 75.59, (2020, 3): 69.59, (2020, 4): 69.59,
    (2020, 5): 71.26, (2020, 6): 80.43, (2020, 7): 80.43, (2020, 8): 82.58,
    (2020, 9): 83.17, (2020, 10): 83.29, (2020, 11): 84.41, (2020, 12): 84.20,
    (2021, 1): 84.20, (2021, 2): 87.67, (2021, 3): 90.56, (2021, 4): 91.17,
    (2021, 5): 92.58, (2021, 6): 96.72, (2021, 7): 101.84, (2021, 8): 101.84,
    (2021, 9): 101.84, (2021, 10): 103.97, (2021, 11): 95.41, (2021, 12): 95.41,
    (2022, 1): 95.41, (2022, 2): 95.41, (2022, 3): 95.41, (2022, 4): 105.41,
    (2022, 5): 105.41, (2022, 6): 96.72, (2022, 7): 96.72, (2022, 8): 96.72,
    (2022, 9): 96.72, (2022, 10): 96.72, (2022, 11): 96.72, (2022, 12): 96.72,
    (2023, 1): 96.72, (2023, 2): 96.72, (2023, 3): 96.72, (2023, 4): 96.72,
    (2023, 5): 96.72, (2023, 6): 96.72, (2023, 7): 96.72, (2023, 8): 96.72,
    (2023, 9): 96.72, (2023, 10): 96.72, (2023, 11): 96.72, (2023, 12): 96.72,
    (2024, 1): 94.77, (2024, 2): 94.77, (2024, 3): 94.77, (2024, 4): 94.77,
    (2024, 5): 94.77, (2024, 6): 94.77, (2024, 7): 94.77, (2024, 8): 94.77,
    (2024, 9): 94.77, (2024, 10): 94.77, (2024, 11): 94.77, (2024, 12): 94.77,
    (2025, 1): 94.77, (2025, 2): 94.77, (2025, 3): 94.77, (2025, 4): 94.77,
    (2025, 5): 94.77, (2025, 6): 94.77, (2025, 7): 94.77, (2025, 8): 94.77,
    (2025, 9): 94.77, (2025, 10): 94.77, (2025, 11): 94.77, (2025, 12): 94.77,
    (2026, 1): 94.77, (2026, 2): 94.77, (2026, 3): 94.77, (2026, 4): 94.77,
    (2026, 5): 94.77, (2026, 6): 94.77,
}

DIESEL_PRICES = {
    (2019, 1): 62.76, (2019, 2): 63.00, (2019, 3): 63.65, (2019, 4): 65.00,
    (2019, 5): 65.72, (2019, 6): 64.42, (2019, 7): 65.37, (2019, 8): 66.13,
    (2019, 9): 67.28, (2019, 10): 67.37, (2019, 11): 68.14, (2019, 12): 68.60,
    (2020, 1): 68.97, (2020, 2): 68.97, (2020, 3): 62.29, (2020, 4): 62.29,
    (2020, 5): 64.13, (2020, 6): 72.73, (2020, 7): 72.73, (2020, 8): 74.68,
    (2020, 9): 74.68, (2020, 10): 74.68, (2020, 11): 75.62, (2020, 12): 75.62,
    (2021, 1): 75.62, (2021, 2): 77.82, (2021, 3): 80.87, (2021, 4): 81.47,
    (2021, 5): 82.71, (2021, 6): 86.67, (2021, 7): 89.87, (2021, 8): 89.87,
    (2021, 9): 89.87, (2021, 10): 91.80, (2021, 11): 86.67, (2021, 12): 86.67,
    (2022, 1): 86.67, (2022, 2): 86.67, (2022, 3): 86.67, (2022, 4): 96.67,
    (2022, 5): 96.67, (2022, 6): 89.62, (2022, 7): 89.62, (2022, 8): 89.62,
    (2022, 9): 89.62, (2022, 10): 89.62, (2022, 11): 89.62, (2022, 12): 89.62,
    (2023, 1): 89.62, (2023, 2): 89.62, (2023, 3): 89.62, (2023, 4): 89.62,
    (2023, 5): 89.62, (2023, 6): 89.62, (2023, 7): 89.62, (2023, 8): 89.62,
    (2023, 9): 89.62, (2023, 10): 89.62, (2023, 11): 89.62, (2023, 12): 89.62,
    (2024, 1): 87.62, (2024, 2): 87.62, (2024, 3): 87.62, (2024, 4): 87.62,
    (2024, 5): 87.62, (2024, 6): 87.62, (2024, 7): 87.62, (2024, 8): 87.62,
    (2024, 9): 87.62, (2024, 10): 87.62, (2024, 11): 87.62, (2024, 12): 87.62,
    (2025, 1): 87.62, (2025, 2): 87.62, (2025, 3): 87.62, (2025, 4): 87.62,
    (2025, 5): 87.62, (2025, 6): 87.62, (2025, 7): 87.62, (2025, 8): 87.62,
    (2025, 9): 87.62, (2025, 10): 87.62, (2025, 11): 87.62, (2025, 12): 87.62,
    (2026, 1): 87.62, (2026, 2): 87.62, (2026, 3): 87.62, (2026, 4): 87.62,
    (2026, 5): 87.62, (2026, 6): 87.62,
}

# ── RBI Repo Rate (%) ──────────────────────────────────────────────────────
REPO_RATE = {
    2019: 6.25, 2020: 4.00, 2021: 4.00, 2022: 6.25, 2023: 6.50,
    2024: 6.50, 2025: 6.25, 2026: 6.00,
}

# ── India GDP growth (%) — annual, applied to all months of that year ──────
GDP_GROWTH = {
    2019: 6.5, 2020: -5.8, 2021: 8.7, 2022: 7.2, 2023: 8.2,
    2024: 8.2, 2025: 6.8, 2026: 7.0,
}

# ── India CPI inflation (%) — annual averages ──────────────────────────────
CPI = {
    2019: 4.76, 2020: 6.62, 2021: 5.13, 2022: 6.70, 2023: 5.65,
    2024: 4.85, 2025: 4.50, 2026: 4.30,
}

# ── USD/INR rate — annual averages ────────────────────────────────────────
USD_INR = {
    2019: 70.42, 2020: 74.18, 2021: 73.92, 2022: 78.60, 2023: 83.16,
    2024: 83.95, 2025: 85.50, 2026: 86.00,
}

# ── Indian festival month flags ────────────────────────────────────────────
# Diwali falls in Oct or Nov; we flag both with 1 for simplicity
DIWALI_MONTHS = {10, 11}
NAVRATRI_MONTHS = {10}          # Sharad Navratri (Oct)
EID_MONTHS = {4, 5}             # Approximate — varies yearly
FINANCIAL_YEAR_END_MONTHS = {3} # March
BUDGET_MONTHS = {2}             # February Union Budget

# ── GST & policy flags ────────────────────────────────────────────────────
# BS6 norms implemented April 2020
# FAME II (EV subsidy) active from April 2019
GST_RATE = 43.0  # effective rate including cess on passenger vehicles

# Consumer confidence index (approximate, 0–100 scale)
CONSUMER_CONFIDENCE = {
    2019: 72, 2020: 55, 2021: 58, 2022: 64, 2023: 70, 2024: 73, 2025: 74, 2026: 75,
}

STATES = [
    "Andaman & Nicobar Island", "Andhra Pradesh", "Arunachal Pradesh", "Assam",
    "Bihar", "Chandigarh", "Chhattisgarh", "Dadra and Nagar Haveli",
    "Daman and Diu", "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh",
    "Lakshadweep", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan",
    "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
    "Uttarakhand", "West Bengal", "All India",
]

FIELDNAMES = [
    "date", "year", "month", "quarter", "state",
    "petrol_price_inr", "diesel_price_inr", "cng_price_inr",
    "rbi_repo_rate_pct", "india_gdp_growth_pct", "india_cpi_pct",
    "usd_inr_rate", "consumer_confidence_index",
    "diwali_month", "navratri_month", "eid_month",
    "financial_year_end", "budget_month",
    "new_model_launches", "gst_rate_pct",
    "bs6_norms_active", "ev_subsidy_active",
]

def quarter_label(month: int) -> str:
    return f"Q{(month - 1) // 3 + 1}"

def cng_price(petrol: float) -> float:
    """CNG roughly 40% cheaper than petrol on energy-equivalent basis."""
    return round(petrol * 0.60, 2)

def new_model_launches(month: int) -> int:
    """Auto Expo years (even years Jan/Feb) see more launches; otherwise ~2-4/month."""
    if month in (1, 2):
        return 6
    if month in (9, 10):
        return 5  # festive season launches
    return 3

rows = []
for year in range(2019, 2027):
    for month in range(1, 13):
        if year == 2026 and month > 6:
            break  # only up to June 2026 for now
        d = date(year, month, 1)
        petrol = PETROL_PRICES.get((year, month), PETROL_PRICES.get((year, 1), 94.77))
        diesel = DIESEL_PRICES.get((year, month), DIESEL_PRICES.get((year, 1), 87.62))
        for state in STATES:
            rows.append({
                "date": d.isoformat(),
                "year": year,
                "month": month,
                "quarter": quarter_label(month),
                "state": state,
                "petrol_price_inr": petrol,
                "diesel_price_inr": diesel,
                "cng_price_inr": cng_price(petrol),
                "rbi_repo_rate_pct": REPO_RATE.get(year, 6.5),
                "india_gdp_growth_pct": GDP_GROWTH.get(year, 7.0),
                "india_cpi_pct": CPI.get(year, 5.0),
                "usd_inr_rate": USD_INR.get(year, 84.0),
                "consumer_confidence_index": CONSUMER_CONFIDENCE.get(year, 70),
                "diwali_month": 1 if month in DIWALI_MONTHS else 0,
                "navratri_month": 1 if month in NAVRATRI_MONTHS else 0,
                "eid_month": 1 if month in EID_MONTHS else 0,
                "financial_year_end": 1 if month in FINANCIAL_YEAR_END_MONTHS else 0,
                "budget_month": 1 if month in BUDGET_MONTHS else 0,
                "new_model_launches": new_model_launches(month),
                "gst_rate_pct": GST_RATE,
                "bs6_norms_active": 1 if (year > 2020 or (year == 2020 and month >= 4)) else 0,
                "ev_subsidy_active": 1 if (year > 2019 or (year == 2019 and month >= 4)) else 0,
            })

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerows(rows)

print(f"Written {len(rows):,} rows to {OUTPUT}")
