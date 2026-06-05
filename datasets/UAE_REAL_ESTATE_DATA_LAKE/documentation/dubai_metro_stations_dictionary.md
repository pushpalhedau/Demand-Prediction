# Data Dictionary: dubai_metro_stations

**Source File:** `dubai_metro_stations.csv`  
**Total Records:** 30  
**Total Columns:** 11  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `station_name` | str | 0.0% | 28 | Metro station name | UAE Exchange, Energy |
| `line` | str | 0.0% | 2 | Metro line color | Red, Red |
| `station_order` | int64 | 0.0% | 19 | Station Order field | min:1.0, max:19.0 |
| `latitude` | float64 | 0.0% | 27 | Geographical latitude coordinate | min:24.9, max:25.3 |
| `longitude` | float64 | 0.0% | 28 | Geographical longitude coordinate | min:55.0, max:55.3 |
| `area` | str | 0.0% | 17 | Area field | Jebel Ali, Jebel Ali |
| `is_operational` | bool | 0.0% | 2 | Is Operational field | True, True |
| `daily_ridership_avg` | int64 | 0.0% | 30 | Average daily passenger ridership | min:9573.0, max:78278.0 |
| `has_parking` | bool | 0.0% | 2 | Has Parking field | False, False |
| `accessibility_score` | float64 | 0.0% | 22 | Accessibility Score field | min:0.6, max:1.0 |
| `retail_catchment_radius_km` | float64 | 0.0% | 1 | Retail Catchment Radius Km field | min:1.5, max:1.5 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.