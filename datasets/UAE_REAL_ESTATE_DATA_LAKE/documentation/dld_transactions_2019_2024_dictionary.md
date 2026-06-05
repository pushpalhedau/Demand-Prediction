# Data Dictionary: dld_transactions_2019_2024

**Source File:** `dld_transactions_2019_2024.csv`  
**Total Records:** 456,000  
**Total Columns:** 18  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `transaction_id` | str | 0.0% | 456,000 | Unique transaction identifier | DLD-2019-0000001, DLD-2019-0000002 |
| `transaction_date` | str | 0.0% | 2,190 | Date of the transaction (YYYY-MM-DD) | 2019-01-13, 2019-02-14 |
| `year` | int64 | 0.0% | 6 | Transaction year | min:2019.0, max:2024.0 |
| `month` | int64 | 0.0% | 12 | Transaction month (1-12) | min:1.0, max:12.0 |
| `quarter` | str | 0.0% | 4 | Fiscal quarter (Q1-Q4) | Q1, Q1 |
| `area_name` | str | 0.0% | 20 | Dubai area/community name | Jumeirah Village Circle, Discovery Gardens |
| `zone` | str | 0.0% | 4 | Zone classification (A=Prime, D=Affordable) | C, D |
| `property_type` | str | 0.0% | 4 | Type of property | Apartment, Apartment |
| `bedrooms` | int64 | 0.0% | 6 | Number of bedrooms (0=Studio) | min:0.0, max:5.0 |
| `transaction_type` | str | 0.0% | 4 | Type of transaction (Sale/Gift/Mortgage/Transfer) | Sale, Sale |
| `transaction_value_aed` | int64 | 0.0% | 434,988 | Transaction value in UAE Dirhams | min:100000.0, max:20737790.0 |
| `transaction_value_usd` | float64 | 0.0% | 434,988 | Transaction value in US Dollars | min:27233.1, max:5647546.3 |
| `area_sqft` | int64 | 0.0% | 4,511 | Property area in square feet | min:300.0, max:5493.0 |
| `price_per_sqft_aed` | float64 | 0.0% | 255,970 | Price per square foot in AED | min:130.7, max:13372.8 |
| `developer` | str | 0.0% | 16 | Property developer name | Dubai Properties, Nakheel |
| `buyer_nationality` | str | 0.0% | 20 | Nationality of the buyer | Jordan, India |
| `is_off_plan` | bool | 0.0% | 2 | Whether property is off-plan (True/False) | False, False |
| `registration_type` | str | 0.0% | 2 | DLD registration type | New, New |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.