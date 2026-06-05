# Data Dictionary: dld_units_data

**Source File:** `dld_units_data.csv`  
**Total Records:** 50,000  
**Total Columns:** 13  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `unit_id` | str | 0.0% | 50,000 | Unit Id field | UNIT-0000001, UNIT-0000002 |
| `building_id` | str | 0.0% | 14,470 | Building Id field | BLDG-005173, BLDG-004028 |
| `unit_number` | int64 | 0.0% | 1,600 | Unit Number field | min:101.0, max:8020.0 |
| `floor` | int64 | 0.0% | 80 | Floor field | min:1.0, max:80.0 |
| `bedrooms` | int64 | 0.0% | 6 | Number of bedrooms (0=Studio) | min:0.0, max:5.0 |
| `bathrooms` | int64 | 0.0% | 5 | Bathrooms field | min:1.0, max:5.0 |
| `area_sqft` | int64 | 0.0% | 4,601 | Property area in square feet | min:400.0, max:5000.0 |
| `property_type` | str | 0.0% | 5 | Type of property | Studio, Apartment |
| `view` | str | 0.0% | 5 | View field | Sea View, City View |
| `is_furnished` | bool | 0.0% | 2 | Is Furnished field | False, True |
| `current_status` | str | 0.0% | 3 | Current Status field | Occupied, Occupied |
| `last_transaction_year` | int64 | 0.0% | 10 | Last Transaction Year field | min:2015.0, max:2024.0 |
| `last_sale_price_aed` | int64 | 0.0% | 49,911 | Last Sale Price Aed field | min:300002.0, max:14999711.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.