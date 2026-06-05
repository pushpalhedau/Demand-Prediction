# Data Dictionary: uae_population_demographics

**Source File:** `uae_population_demographics.csv`  
**Total Records:** 25  
**Total Columns:** 11  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `year` | int64 | 0.0% | 25 | Transaction year | min:2000.0, max:2024.0 |
| `total_population` | int64 | 0.0% | 25 | Total Population field | min:3155000.0, max:10200000.0 |
| `uae_nationals_pct` | float64 | 0.0% | 1 | Uae Nationals Pct field | min:11.5, max:11.5 |
| `expats_pct` | float64 | 0.0% | 1 | Expats Pct field | min:88.5, max:88.5 |
| `dubai_population` | int64 | 0.0% | 25 | Dubai Population field | min:1104250.0, max:3570000.0 |
| `abu_dhabi_population` | int64 | 0.0% | 25 | Abu Dhabi Population field | min:946500.0, max:3060000.0 |
| `sharjah_population` | int64 | 0.0% | 25 | Sharjah Population field | min:441700.0, max:1428000.0 |
| `other_emirates_population` | int64 | 0.0% | 25 | Other Emirates Population field | min:662550.0, max:2142000.0 |
| `annual_growth_rate_pct` | float64 | 0.0% | 23 | Annual Growth Rate Pct field | min:-5.1, max:57.5 |
| `male_female_ratio` | float64 | 0.0% | 17 | Male Female Ratio field | min:2.0, max:2.3 |
| `working_age_pct` | float64 | 0.0% | 1 | Working Age Pct field | min:85.0, max:85.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.