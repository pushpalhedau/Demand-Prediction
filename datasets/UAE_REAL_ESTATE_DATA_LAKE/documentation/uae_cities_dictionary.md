# Data Dictionary: uae_cities

**Source File:** `uae_cities.csv`  
**Total Records:** 63  
**Total Columns:** 4  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `name` | str | 0.0% | 63 | Name field | Warīsān, Umm Suqaym |
| `country` | str | 0.0% | 1 | Country field | United Arab Emirates, United Arab Emirates |
| `subcountry` | str | 0.0% | 7 | Subcountry field | Dubai, Dubai |
| `geonameid` | int64 | 0.0% | 63 | Geonameid field | min:290503.0, max:13118447.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.