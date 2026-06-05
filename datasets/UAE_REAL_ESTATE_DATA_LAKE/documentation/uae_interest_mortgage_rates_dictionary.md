# Data Dictionary: uae_interest_mortgage_rates

**Source File:** `uae_interest_mortgage_rates.csv`  
**Total Records:** 120  
**Total Columns:** 12  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `year` | int64 | 0.0% | 10 | Transaction year | min:2015.0, max:2024.0 |
| `month` | int64 | 0.0% | 12 | Transaction month (1-12) | min:1.0, max:12.0 |
| `date` | str | 0.0% | 120 | Date field | 2015-01-01, 2015-02-01 |
| `uae_base_rate_pct` | float64 | 0.0% | 114 | Uae Base Rate Pct field | min:0.4, max:5.8 |
| `eibor_1m_pct` | float64 | 0.0% | 115 | Eibor 1M Pct field | min:0.5, max:5.9 |
| `eibor_3m_pct` | float64 | 0.0% | 115 | Eibor 3M Pct field | min:0.6, max:6.0 |
| `eibor_6m_pct` | float64 | 0.0% | 112 | Eibor 6M Pct field | min:0.7, max:6.2 |
| `eibor_12m_pct` | float64 | 0.0% | 111 | Eibor 12M Pct field | min:0.9, max:6.3 |
| `avg_mortgage_rate_pct` | float64 | 0.0% | 116 | Avg Mortgage Rate Pct field | min:2.3, max:7.9 |
| `fixed_mortgage_rate_pct` | float64 | 0.0% | 117 | Fixed Mortgage Rate Pct field | min:2.8, max:8.4 |
| `variable_mortgage_rate_pct` | float64 | 0.0% | 120 | Variable Mortgage Rate Pct field | min:2.1, max:7.8 |
| `fed_funds_rate_pct` | float64 | 0.0% | 8 | Fed Funds Rate Pct field | min:0.2, max:5.5 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.