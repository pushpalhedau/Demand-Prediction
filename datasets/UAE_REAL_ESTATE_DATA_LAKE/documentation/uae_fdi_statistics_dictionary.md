# Data Dictionary: uae_fdi_statistics

**Source File:** `uae_fdi_statistics.csv`  
**Total Records:** 10  
**Total Columns:** 6  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `year` | int64 | 0.0% | 10 | Transaction year | min:2015.0, max:2024.0 |
| `fdi_inflows_usd_billion` | float64 | 0.0% | 10 | Fdi Inflows Usd Billion field | min:9.8, max:35.7 |
| `fdi_real_estate_pct` | float64 | 0.0% | 10 | Fdi Real Estate Pct field | min:18.1, max:24.5 |
| `fdi_financial_services_pct` | float64 | 0.0% | 10 | Fdi Financial Services Pct field | min:13.4, max:21.1 |
| `fdi_manufacturing_pct` | float64 | 0.0% | 8 | Fdi Manufacturing Pct field | min:13.6, max:19.5 |
| `top_source_country` | str | 0.0% | 2 | Top Source Country field | USA, USA |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.