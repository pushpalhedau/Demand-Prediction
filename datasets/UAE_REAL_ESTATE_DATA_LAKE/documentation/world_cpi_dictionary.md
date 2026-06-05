# Data Dictionary: world_cpi

**Source File:** `world_cpi.csv`  
**Total Records:** 11,182  
**Total Columns:** 4  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `Country` | str | 0.0% | 240 | Country field | Aruba, Aruba |
| `Country Code` | str | 0.0% | 240 | Country Code field | ABW, ABW |
| `Year` | int64 | 0.0% | 65 | Year field | min:1960.0, max:2024.0 |
| `CPI` | float64 | 0.0% | 9,950 | Cpi field | min:-17.6, max:23773.1 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.