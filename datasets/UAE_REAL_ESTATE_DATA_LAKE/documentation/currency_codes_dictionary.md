# Data Dictionary: currency_codes

**Source File:** `currency_codes.csv`  
**Total Records:** 449  
**Total Columns:** 6  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `Entity` | str | 0.0% | 294 | Entity field | AFGHANISTAN, ÅLAND ISLANDS |
| `Currency` | str | 0.0% | 287 | Currency field | Afghani, Euro |
| `AlphabeticCode` | str | 0.67% | 307 | Alphabeticcode field | AFN, EUR |
| `NumericCode` | float64 | 1.34% | 257 | Numericcode field | min:4.0, max:999.0 |
| `MinorUnit` | str | 38.31% | 5 | Minorunit field | 2, 2 |
| `WithdrawalDate` | str | 62.36% | 99 | Withdrawaldate field | 2003-01, 2002-03 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 37.6% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.