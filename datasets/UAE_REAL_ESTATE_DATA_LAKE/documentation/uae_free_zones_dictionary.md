# Data Dictionary: uae_free_zones

**Source File:** `uae_free_zones.csv`  
**Total Records:** 18  
**Total Columns:** 12  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `zone_code` | str | 0.0% | 18 | Zone Code field | DIFC, DAFZA |
| `zone_name` | str | 0.0% | 18 | Zone Name field | Dubai International Financial Centre, Dubai Airport Free Zone |
| `primary_sector` | str | 0.0% | 15 | Primary Sector field | Financial Services, Aviation & Logistics |
| `latitude` | float64 | 0.0% | 18 | Geographical latitude coordinate | min:24.4, max:25.3 |
| `longitude` | float64 | 0.0% | 18 | Geographical longitude coordinate | min:54.3, max:55.5 |
| `status` | str | 0.0% | 2 | Status field | Operational, Operational |
| `established_year` | int64 | 0.0% | 15 | Established Year field | min:1985.0, max:2024.0 |
| `num_companies` | int64 | 0.0% | 18 | Num Companies field | min:841.0, max:7961.0 |
| `area_sqkm` | float64 | 0.0% | 18 | Area Sqkm field | min:6.6, max:95.3 |
| `employment_thousands` | float64 | 0.0% | 18 | Employment Thousands field | min:9.3, max:94.5 |
| `foreign_ownership_pct` | float64 | 0.0% | 1 | Foreign Ownership Pct field | min:100.0, max:100.0 |
| `corporate_tax` | int64 | 0.0% | 1 | Corporate Tax field | min:0.0, max:0.0 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 100.0% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.