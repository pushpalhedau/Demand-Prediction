# Data Dictionary: dubai_bus_routes

**Source File:** `dubai_bus_routes.csv`  
**Total Records:** 200  
**Total Columns:** 10  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `route_number` | int64 | 0.0% | 178 | Route Number field | min:2.0, max:998.0 |
| `route_name` | str | 0.0% | 200 | Route Name field | Route 1, Route 2 |
| `from_terminal` | str | 0.0% | 6 | From Terminal field | Al Satwa, Al Ghubaiba |
| `to_terminal` | str | 0.0% | 5 | To Terminal field | International City, Silicon Oasis |
| `total_stops` | int64 | 0.0% | 37 | Total Stops field | min:8.0, max:45.0 |
| `route_length_km` | float64 | 0.0% | 184 | Route Length Km field | min:8.1, max:85.0 |
| `frequency_mins` | int64 | 0.0% | 5 | Frequency Mins field | min:10.0, max:60.0 |
| `is_express` | bool | 0.0% | 2 | Is Express field | False, False |
| `daily_ridership` | int64 | 0.0% | 199 | Daily Ridership field | min:511.0, max:24964.0 |
| `ac_buses` | bool | 0.0% | 1 | Ac Buses field | True, True |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.