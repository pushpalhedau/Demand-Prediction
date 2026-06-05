# Data Dictionary: uae_mena_gdp_filtered

**Source File:** `uae_mena_gdp_filtered.csv`  
**Total Records:** 464  
**Total Columns:** 4  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `Country Name` | str | 0.0% | 8 | Country Name field | Bahrain, Bahrain |
| `Country Code` | str | 0.0% | 8 | Country Code field | BHR, BHR |
| `Year` | int64 | 0.0% | 64 | Year field | min:1960.0, max:2023.0 |
| `Value` | float64 | 0.0% | 464 | Value field | min:63279974.7, max:1108571466666.7 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.