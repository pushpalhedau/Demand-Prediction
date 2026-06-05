# Data Dictionary: uae_tourism_statistics

**Source File:** `uae_tourism_statistics.csv`  
**Total Records:** 10  
**Total Columns:** 6  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `year` | int64 | 0.0% | 10 | Transaction year | min:2015.0, max:2024.0 |
| `international_visitors_millions` | float64 | 0.0% | 9 | International Visitors Millions field | min:5.6, max:18.6 |
| `hotel_occupancy_rate_pct` | float64 | 0.0% | 10 | Hotel Occupancy Rate Pct field | min:43.6, max:81.1 |
| `avg_daily_rate_hotel_aed` | int64 | 0.0% | 9 | Avg Daily Rate Hotel Aed field | min:593.0, max:855.0 |
| `tourism_gdp_pct` | float64 | 0.0% | 9 | Tourism Gdp Pct field | min:5.0, max:13.0 |
| `expo_boost` | int64 | 0.0% | 2 | Expo Boost field | min:0.0, max:1.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.