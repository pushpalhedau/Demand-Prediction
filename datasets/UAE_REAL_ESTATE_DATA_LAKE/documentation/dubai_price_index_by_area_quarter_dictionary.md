# Data Dictionary: dubai_price_index_by_area_quarter

**Source File:** `dubai_price_index_by_area_quarter.csv`  
**Total Records:** 600  
**Total Columns:** 10  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `year` | int64 | 0.0% | 10 | Transaction year | min:2015.0, max:2024.0 |
| `quarter` | str | 0.0% | 4 | Fiscal quarter (Q1-Q4) | Q1, Q1 |
| `area` | str | 0.0% | 15 | Area field | Dubai Marina, Downtown Dubai |
| `avg_sale_price_per_sqft_aed` | float64 | 0.0% | 514 | Avg Sale Price Per Sqft Aed field | min:595.0, max:5152.0 |
| `avg_asking_price_aed` | float64 | 0.0% | 600 | Avg Asking Price Aed field | min:1089387.0, max:9835505.0 |
| `transaction_volume` | int64 | 0.0% | 528 | Transaction Volume field | min:51.0, max:2499.0 |
| `price_qoq_change_pct` | float64 | 0.0% | 375 | Price Qoq Change Pct field | min:-3.1, max:6.2 |
| `price_yoy_change_pct` | float64 | 0.0% | 441 | Price Yoy Change Pct field | min:-6.6, max:7.7 |
| `avg_days_to_sell` | int64 | 0.0% | 147 | Avg Days To Sell field | min:30.0, max:180.0 |
| `rental_yield_pct` | float64 | 0.0% | 220 | Rental Yield Pct field | min:3.8, max:7.7 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.