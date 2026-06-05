# Data Dictionary: uae_gdp_annual

**Source File:** `uae_gdp_annual.csv`  
**Total Records:** 25  
**Total Columns:** 7  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `year` | int64 | 0.0% | 25 | Transaction year | min:2000.0, max:2024.0 |
| `gdp_usd_billion` | float64 | 0.0% | 25 | GDP in billions of US Dollars | min:95.0, max:527.8 |
| `gdp_growth_rate_pct` | float64 | 0.0% | 25 | Year-over-year GDP growth rate | min:-19.6, max:24.1 |
| `oil_gdp_usd_billion` | float64 | 0.0% | 25 | Oil Gdp Usd Billion field | min:35.6, max:195.7 |
| `non_oil_gdp_usd_billion` | float64 | 0.0% | 24 | Non Oil Gdp Usd Billion field | min:59.1, max:352.6 |
| `gdp_aed_billion` | float64 | 0.0% | 25 | Gdp Aed Billion field | min:348.8, max:1938.1 |
| `per_capita_gdp_usd` | int64 | 0.0% | 25 | Per Capita Gdp Usd field | min:29043.0, max:72164.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.