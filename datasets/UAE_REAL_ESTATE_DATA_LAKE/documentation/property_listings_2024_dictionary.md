# Data Dictionary: property_listings_2024

**Source File:** `property_listings_2024.csv`  
**Total Records:** 75,000  
**Total Columns:** 20  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `listing_id` | str | 0.0% | 75,000 | Listing Id field | PF-0000001, PF-0000002 |
| `platform` | str | 0.0% | 3 | Platform field | PropertyFinder, Dubizzle |
| `listing_date` | str | 0.0% | 365 | Listing Date field | 2024-09-13, 2024-03-11 |
| `area` | str | 0.0% | 15 | Area field | Dubai Creek Harbour, Dubai Hills Estate |
| `listing_type` | str | 0.0% | 2 | Listing Type field | Sale, Sale |
| `property_type` | str | 0.0% | 5 | Type of property | Studio, Townhouse |
| `bedrooms` | int64 | 0.0% | 6 | Number of bedrooms (0=Studio) | min:0.0, max:5.0 |
| `bathrooms` | int64 | 0.0% | 5 | Bathrooms field | min:1.0, max:5.0 |
| `area_sqft` | int64 | 0.0% | 5,601 | Property area in square feet | min:400.0, max:6000.0 |
| `price_aed` | int64 | 0.0% | 73,859 | Listing price in UAE Dirhams | min:71409.0, max:12749828.0 |
| `price_per_sqft` | float64 | 0.0% | 64,657 | Price Per Sqft field | min:102.7, max:29706.9 |
| `is_furnished` | bool | 0.0% | 2 | Is Furnished field | True, False |
| `has_parking` | bool | 0.0% | 2 | Has Parking field | True, False |
| `view` | str | 0.0% | 5 | View field | No View, City |
| `days_on_market` | int64 | 0.0% | 365 | Number of days listing has been active | min:1.0, max:365.0 |
| `num_views` | int64 | 0.0% | 4,991 | Num Views field | min:10.0, max:5000.0 |
| `num_inquiries` | int64 | 0.0% | 151 | Num Inquiries field | min:0.0, max:150.0 |
| `developer` | str | 0.0% | 7 | Property developer name | Nakheel, Independent |
| `is_verified` | bool | 0.0% | 2 | Is Verified field | True, True |
| `agent_id` | str | 0.0% | 5,000 | Agent Id field | AGT-00905, AGT-01000 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.