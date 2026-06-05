# Data Dictionary: developer_market_share

**Source File:** `developer_market_share.csv`  
**Total Records:** 336  
**Total Columns:** 7  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `year` | int64 | 0.0% | 6 | Transaction year | min:2019.0, max:2024.0 |
| `quarter` | str | 0.0% | 4 | Fiscal quarter (Q1-Q4) | Q1, Q1 |
| `developer` | str | 0.0% | 14 | Property developer name | Emaar Properties, DAMAC Properties |
| `market_share_pct` | float64 | 0.0% | 302 | Market Share Pct field | min:0.1, max:24.2 |
| `units_launched` | int64 | 0.0% | 276 | Units Launched field | min:0.0, max:800.0 |
| `units_sold` | int64 | 0.0% | 266 | Units Sold field | min:1.0, max:700.0 |
| `avg_price_per_sqft` | int64 | 0.0% | 318 | Avg Price Per Sqft field | min:719.0, max:4498.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.