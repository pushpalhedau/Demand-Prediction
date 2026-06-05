# Data Dictionary: dld_areas_lookup

**Source File:** `dld_areas_lookup.csv`  
**Total Records:** 61  
**Total Columns:** 9  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `area_code` | str | 0.0% | 61 | Area Code field | A0001, A0002 |
| `area_name` | str | 0.0% | 61 | Dubai area/community name | Dubai Marina, Downtown Dubai |
| `emirate` | str | 0.0% | 1 | Emirate field | Dubai, Dubai |
| `zone_type` | str | 0.0% | 3 | Zone Type field | Freehold, Leasehold |
| `primary_use` | str | 0.0% | 4 | Primary Use field | Commercial, Commercial |
| `municipality` | str | 0.0% | 3 | Municipality field | Dubai Municipality, DAFZA |
| `avg_price_per_sqft_2024` | int64 | 0.0% | 60 | Avg Price Per Sqft 2024 field | min:879.0, max:4963.0 |
| `num_projects` | int64 | 0.0% | 52 | Num Projects field | min:11.0, max:246.0 |
| `established_year` | int64 | 0.0% | 24 | Established Year field | min:1995.0, max:2020.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.