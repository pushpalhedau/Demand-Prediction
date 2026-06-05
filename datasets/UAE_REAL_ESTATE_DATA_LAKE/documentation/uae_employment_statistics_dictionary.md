# Data Dictionary: uae_employment_statistics

**Source File:** `uae_employment_statistics.csv`  
**Total Records:** 60  
**Total Columns:** 10  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `year` | int64 | 0.0% | 15 | Transaction year | min:2010.0, max:2024.0 |
| `quarter` | str | 0.0% | 4 | Fiscal quarter (Q1-Q4) | Q1, Q2 |
| `date` | str | 0.0% | 60 | Date field | 2010-03-01, 2010-06-01 |
| `labor_force_thousands` | int64 | 0.0% | 60 | Labor Force Thousands field | min:5785.0, max:7656.0 |
| `employed_thousands` | int64 | 0.0% | 60 | Employed Thousands field | min:5612.0, max:7462.0 |
| `unemployment_rate_pct` | float64 | 0.0% | 49 | Unemployment Rate Pct field | min:1.8, max:5.5 |
| `private_sector_pct` | float64 | 0.0% | 41 | Private Sector Pct field | min:77.1, max:86.8 |
| `construction_employment_thousands` | int64 | 0.0% | 55 | Construction Employment Thousands field | min:1069.0, max:1432.0 |
| `real_estate_employment_thousands` | int64 | 0.0% | 40 | Real Estate Employment Thousands field | min:88.0, max:170.0 |
| `avg_monthly_salary_aed` | int64 | 0.0% | 60 | Avg Monthly Salary Aed field | min:7102.0, max:11074.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.