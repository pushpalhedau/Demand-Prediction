# Data Dictionary: dld_projects_data

**Source File:** `dld_projects_data.csv`  
**Total Records:** 2,500  
**Total Columns:** 17  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `project_id` | str | 0.0% | 2,500 | Project Id field | PRJ-00001, PRJ-00002 |
| `project_name` | str | 0.0% | 1,347 | Project Name field | Motor Residences 17, Tiger Al Tower 1 |
| `developer` | str | 0.0% | 19 | Property developer name | Sobha Realty, Tiger Properties |
| `area` | str | 0.0% | 30 | Area field | Motor City, Al Karama |
| `project_type` | str | 0.0% | 4 | Project Type field | Residential, Residential |
| `total_units` | int64 | 0.0% | 1,425 | Total Units field | min:50.0, max:2000.0 |
| `sold_units` | int64 | 0.0% | 1,292 | Sold Units field | min:14.0, max:1970.0 |
| `sold_percentage` | float64 | 0.0% | 730 | Sold Percentage field | min:20.1, max:100.0 |
| `launch_year` | int64 | 0.0% | 20 | Launch Year field | min:2005.0, max:2024.0 |
| `completion_year` | float64 | 55.48% | 23 | Completion Year field | min:2007.0, max:2029.0 |
| `status` | str | 0.0% | 4 | Status field | Under Construction, Under Construction |
| `avg_price_per_sqft_aed` | int64 | 0.0% | 1,811 | Avg Price Per Sqft Aed field | min:701.0, max:4498.0 |
| `min_price_aed` | int64 | 0.0% | 2,497 | Min Price Aed field | min:300201.0, max:1499822.0 |
| `max_price_aed` | int64 | 0.0% | 2,500 | Max Price Aed field | min:2018185.0, max:24993973.0 |
| `floors` | int64 | 0.0% | 76 | Floors field | min:5.0, max:80.0 |
| `has_amenities` | bool | 0.0% | 2 | Has Amenities field | False, False |
| `is_freehold` | bool | 0.0% | 2 | Is Freehold field | True, True |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 44.5% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.