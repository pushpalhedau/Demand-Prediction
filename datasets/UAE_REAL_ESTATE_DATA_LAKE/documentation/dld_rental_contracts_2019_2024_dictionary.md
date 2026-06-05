# Data Dictionary: dld_rental_contracts_2019_2024

**Source File:** `dld_rental_contracts_2019_2024.csv`  
**Total Records:** 123,500  
**Total Columns:** 13  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `contract_id` | str | 0.0% | 123,500 | Contract Id field | RERA-2019-0000001, RERA-2019-0000002 |
| `contract_date` | str | 0.0% | 2,190 | Contract Date field | 2019-07-28, 2019-01-27 |
| `year` | int64 | 0.0% | 6 | Transaction year | min:2019.0, max:2024.0 |
| `month` | int64 | 0.0% | 12 | Transaction month (1-12) | min:1.0, max:12.0 |
| `area` | str | 0.0% | 15 | Area field | Dubai Marina, Deira |
| `bedrooms` | int64 | 0.0% | 5 | Number of bedrooms (0=Studio) | min:0.0, max:4.0 |
| `property_type` | str | 0.0% | 2 | Type of property | Apartment, Apartment |
| `annual_rent_aed` | int64 | 0.0% | 92,031 | Annual Rent Aed field | min:15000.0, max:778395.0 |
| `monthly_rent_aed` | int64 | 0.0% | 25,249 | Monthly Rent Aed field | min:1250.0, max:64866.0 |
| `contract_duration_months` | int64 | 0.0% | 3 | Contract Duration Months field | min:6.0, max:24.0 |
| `payment_frequency` | str | 0.0% | 4 | Payment Frequency field | Quarterly, Annual |
| `is_renewal` | bool | 0.0% | 2 | Is Renewal field | False, True |
| `tenant_nationality` | str | 0.0% | 7 | Tenant Nationality field | Pakistan, India |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.