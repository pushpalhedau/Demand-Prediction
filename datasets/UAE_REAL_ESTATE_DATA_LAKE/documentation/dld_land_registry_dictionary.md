# Data Dictionary: dld_land_registry

**Source File:** `dld_land_registry.csv`  
**Total Records:** 8,000  
**Total Columns:** 11  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `plot_id` | str | 0.0% | 8,000 | Plot Id field | PLOT-000001, PLOT-000002 |
| `plot_number` | str | 0.0% | 7,390 | Plot Number field | 162-A, 5672-A |
| `area_name` | str | 0.0% | 40 | Dubai area/community name | Dubai Creek Harbour, Motor City |
| `plot_area_sqft` | int64 | 0.0% | 7,935 | Plot Area Sqft field | min:5011.0, max:499755.0 |
| `zoning` | str | 0.0% | 5 | Zoning field | Mixed, Mixed |
| `ownership_type` | str | 0.0% | 3 | Ownership Type field | Leasehold, Freehold |
| `registration_date` | str | 0.0% | 5,234 | Registration Date field | 2009-09-11, 2008-09-07 |
| `last_transfer_date` | str | 0.0% | 3,273 | Last Transfer Date field | 2017-09-06, 2016-10-15 |
| `market_value_aed` | int64 | 0.0% | 8,000 | Market Value Aed field | min:1023876.0, max:499823443.0 |
| `is_mortgaged` | bool | 0.0% | 2 | Is Mortgaged field | True, True |
| `developer_id` | str | 0.0% | 200 | Developer Id field | DEV-0164, DEV-0079 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.