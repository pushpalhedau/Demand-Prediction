# Data Dictionary: world_cities

**Source File:** `world_cities.csv`  
**Total Records:** 33,747  
**Total Columns:** 4  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `name` | str | 0.0% | 31,914 | Name field | les Escaldes, Andorra la Vella |
| `country` | str | 0.0% | 244 | Country field | Andorra, Andorra |
| `subcountry` | str | 0.37% | 2,694 | Subcountry field | Escaldes-Engordany, Andorra la Vella |
| `geonameid` | int64 | 0.0% | 33,747 | Geonameid field | min:490.0, max:13645442.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 99.6% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.