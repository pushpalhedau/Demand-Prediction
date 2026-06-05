# Data Dictionary: dld_buildings_data

**Source File:** `dld_buildings_data.csv`  
**Total Records:** 15,000  
**Total Columns:** 13  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `building_id` | str | 0.0% | 15,000 | Building Id field | BLDG-000001, BLDG-000002 |
| `building_name` | str | 0.0% | 7,250 | Building Name field | Dubai Tower 7, Dubai Tower 25 |
| `area` | str | 0.0% | 40 | Area field | Dubai Investment Park, Dubai Creek Harbour |
| `building_type` | str | 0.0% | 4 | Building Type field | Mixed, Mixed |
| `floors` | int64 | 0.0% | 99 | Floors field | min:2.0, max:100.0 |
| `units_count` | int64 | 0.0% | 491 | Units Count field | min:10.0, max:500.0 |
| `built_year` | int64 | 0.0% | 35 | Built Year field | min:1990.0, max:2024.0 |
| `parking_spaces` | int64 | 0.0% | 591 | Parking Spaces field | min:10.0, max:600.0 |
| `has_gym` | bool | 0.0% | 2 | Has Gym field | False, False |
| `has_pool` | bool | 0.0% | 2 | Has Pool field | True, False |
| `has_concierge` | bool | 0.0% | 2 | Has Concierge field | False, False |
| `service_charge_per_sqft` | float64 | 0.0% | 2,693 | Service Charge Per Sqft field | min:8.0, max:35.0 |
| `grade` | str | 0.0% | 3 | Grade field | A, B |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.