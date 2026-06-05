# Data Dictionary: uae_cpi_inflation_monthly

**Source File:** `uae_cpi_inflation_monthly.csv`  
**Total Records:** 180  
**Total Columns:** 10  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `year` | int64 | 0.0% | 15 | Transaction year | min:2010.0, max:2024.0 |
| `month` | int64 | 0.0% | 12 | Transaction month (1-12) | min:1.0, max:12.0 |
| `date` | str | 0.0% | 180 | Date field | 2010-01-01, 2010-02-01 |
| `overall_cpi` | float64 | 0.0% | 170 | Consumer Price Index (2010=100) | min:99.6, max:125.0 |
| `housing_cpi` | float64 | 0.0% | 172 | Housing Cpi field | min:101.4, max:128.2 |
| `food_cpi` | float64 | 0.0% | 170 | Food Cpi field | min:97.0, max:123.4 |
| `transport_cpi` | float64 | 0.0% | 170 | Transport Cpi field | min:93.4, max:120.4 |
| `education_cpi` | float64 | 0.0% | 165 | Education Cpi field | min:104.5, max:131.3 |
| `healthcare_cpi` | float64 | 0.0% | 175 | Healthcare Cpi field | min:102.3, max:129.1 |
| `yoy_inflation_pct` | float64 | 0.0% | 160 | Year-over-year inflation rate percentage | min:-2.5, max:5.4 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.