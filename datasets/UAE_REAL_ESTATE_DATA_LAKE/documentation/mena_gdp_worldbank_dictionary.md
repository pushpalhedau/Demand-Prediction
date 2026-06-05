# Data Dictionary: mena_gdp_worldbank

**Source File:** `mena_gdp_worldbank.csv`  
**Total Records:** 13,979  
**Total Columns:** 4  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `Country Name` | str | 0.0% | 262 | Country Name field | Afghanistan, Afghanistan |
| `Country Code` | str | 0.0% | 262 | Country Code field | AFG, AFG |
| `Year` | int64 | 0.0% | 64 | Year field | min:1960.0, max:2023.0 |
| `Value` | float64 | 0.0% | 13,900 | Value field | min:11502.6, max:105435039507024.1 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.