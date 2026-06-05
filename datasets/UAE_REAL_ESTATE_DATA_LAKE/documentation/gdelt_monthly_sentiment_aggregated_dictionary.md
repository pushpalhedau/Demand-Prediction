# Data Dictionary: gdelt_monthly_sentiment_aggregated

**Source File:** `gdelt_monthly_sentiment_aggregated.csv`  
**Total Records:** 1,200  
**Total Columns:** 8  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `year` | int64 | 0.0% | 5 | Transaction year | min:2020.0, max:2024.0 |
| `month` | int64 | 0.0% | 12 | Transaction month (1-12) | min:1.0, max:12.0 |
| `theme` | str | 0.0% | 20 | GDELT event theme classification | AFFORDABLE_HOUSING_UAE, ARAMCO_UAE_OIL |
| `event_count` | int64 | 0.0% | 38 | Event Count field | min:24.0, max:65.0 |
| `avg_tone` | float64 | 0.0% | 239 | Avg Tone field | min:-0.6, max:2.6 |
| `avg_mentions` | float64 | 0.0% | 953 | Avg Mentions field | min:53.7, max:98.5 |
| `positive_pct` | float64 | 0.0% | 290 | Positive Pct field | min:27.5, max:74.2 |
| `negative_pct` | float64 | 0.0% | 242 | Negative Pct field | min:2.3, max:42.5 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.