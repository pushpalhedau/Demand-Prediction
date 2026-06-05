# Data Dictionary: mena_population_worldbank

**Source File:** `mena_population_worldbank.csv`  
**Total Records:** 390  
**Total Columns:** 4  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `Country Name` | str | 0.0% | 6 | Country Name field | United Arab Emirates, United Arab Emirates |
| `Country Code` | str | 0.0% | 6 | Country Code field | ARE, ARE |
| `Year` | int64 | 0.0% | 65 | Year field | min:1960.0, max:2024.0 |
| `Value` | int64 | 0.0% | 390 | Value field | min:36010.0, max:35300280.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.