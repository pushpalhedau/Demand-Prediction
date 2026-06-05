# Data Dictionary: gdelt_uae_realestate_events

**Source File:** `gdelt_uae_realestate_events.csv`  
**Total Records:** 50,000  
**Total Columns:** 16  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `event_id` | str | 0.0% | 50,000 | Event Id field | GDELT-0000001, GDELT-0000002 |
| `datetime` | str | 0.0% | 49,504 | Datetime field | 2024-05-19 21:05:00, 2023-08-18 10:41:00 |
| `date` | str | 0.0% | 1,827 | Date field | 2024-05-19, 2023-08-18 |
| `year` | int64 | 0.0% | 5 | Transaction year | min:2020.0, max:2024.0 |
| `month` | int64 | 0.0% | 12 | Transaction month (1-12) | min:1.0, max:12.0 |
| `theme` | str | 0.0% | 20 | GDELT event theme classification | PROPTECH_UAE, EXPO2020_DUBAI |
| `source_domain` | str | 0.0% | 15 | Source Domain field | ft.com, cnbc.com |
| `source_country` | str | 0.0% | 2 | Source Country field | GLOBAL, GLOBAL |
| `headline_sentiment` | str | 0.0% | 3 | Headline Sentiment field | Negative, Neutral |
| `tone_score` | float64 | 0.0% | 1,631 | Sentiment tone score (-10 negative to +10 positive) | min:-10.3, max:9.6 |
| `goldstein_scale` | float64 | 0.0% | 201 | Goldstein Scale field | min:-10.0, max:10.0 |
| `num_mentions` | int64 | 0.0% | 150 | Num Mentions field | min:1.0, max:150.0 |
| `num_sources` | int64 | 0.0% | 30 | Num Sources field | min:1.0, max:30.0 |
| `avg_tone` | float64 | 0.0% | 1,890 | Avg Tone field | min:-11.3, max:11.1 |
| `quad_class` | str | 0.0% | 4 | Quad Class field | Verbal Conflict, Verbal Cooperation |
| `is_real_estate_specific` | int64 | 0.0% | 2 | Is Real Estate Specific field | min:0.0, max:1.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.