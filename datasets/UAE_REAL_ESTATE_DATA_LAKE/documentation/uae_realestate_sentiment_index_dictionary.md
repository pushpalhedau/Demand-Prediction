# Data Dictionary: uae_realestate_sentiment_index

**Source File:** `uae_realestate_sentiment_index.csv`  
**Total Records:** 60  
**Total Columns:** 9  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `date` | str | 0.0% | 60 | Date field | 2020-01-01, 2020-02-01 |
| `year` | int64 | 0.0% | 5 | Transaction year | min:2020.0, max:2024.0 |
| `month` | int64 | 0.0% | 12 | Transaction month (1-12) | min:1.0, max:12.0 |
| `real_estate_sentiment_index` | float64 | 0.0% | 52 | Real Estate Sentiment Index field | min:45.2, max:88.1 |
| `buyer_confidence_index` | float64 | 0.0% | 55 | Buyer Confidence Index field | min:41.9, max:92.3 |
| `seller_confidence_index` | float64 | 0.0% | 55 | Seller Confidence Index field | min:44.7, max:90.2 |
| `media_sentiment_score` | float64 | 0.0% | 57 | Media Sentiment Score field | min:-1.9, max:1.6 |
| `search_volume_index` | float64 | 0.0% | 59 | Search Volume Index field | min:88.7, max:197.4 |
| `social_media_buzz_index` | float64 | 0.0% | 53 | Social Media Buzz Index field | min:26.0, max:88.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.