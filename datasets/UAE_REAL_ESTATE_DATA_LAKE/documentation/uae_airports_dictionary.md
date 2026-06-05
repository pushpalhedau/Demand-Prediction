# Data Dictionary: uae_airports

**Source File:** `uae_airports.csv`  
**Total Records:** 305  
**Total Columns:** 13  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `ident` | str | 0.0% | 305 | Ident field | AE-0002, AE-0003 |
| `type` | str | 0.0% | 6 | Type field | heliport, small_airport |
| `name` | str | 0.0% | 300 | Name field | Burj al Arab Resort Helipad, Skydive Dubai Airport |
| `elevation_ft` | float64 | 38.36% | 84 | Elevation Ft field | min:0.0, max:1463.0 |
| `continent` | str | 0.0% | 1 | Continent field | AS, AS |
| `iso_country` | str | 0.0% | 1 | Iso Country field | AE, AE |
| `iso_region` | str | 0.0% | 7 | Iso Region field | AE-DU, AE-DU |
| `municipality` | str | 7.21% | 105 | Municipality field | Dubai, Dubai |
| `icao_code` | str | 91.15% | 27 | Icao Code field | OMQF, OMAY |
| `iata_code` | str | 95.41% | 14 | Iata Code field | DST, AYM |
| `gps_code` | str | 90.49% | 29 | Gps Code field | OMQF, OMLW |
| `local_code` | str | 98.69% | 4 | Local Code field | OMAY, ABOH |
| `coordinates` | str | 0.0% | 305 | Coordinates field | 25.141327, 55.185496, 25.090037, 55.132345 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 1.3% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.