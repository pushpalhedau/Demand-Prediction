# Data Dictionary: airport_codes

**Source File:** `airport_codes.csv`  
**Total Records:** 85,543  
**Total Columns:** 13  
**Generated:** 2026-06-04  

---

## Column Definitions

| Column | Data Type | Null % | Unique Values | Description | Example Values |
|--------|-----------|--------|---------------|-------------|----------------|
| `ident` | str | 0.0% | 85,543 | Ident field | 00A, 00AA |
| `type` | str | 0.0% | 7 | Type field | heliport, small_airport |
| `name` | str | 0.0% | 81,009 | Name field | Total RF Heliport, Aero B Ranch Airport |
| `elevation_ft` | float64 | 17.38% | 6,473 | Elevation Ft field | min:-1266.0, max:17372.0 |
| `continent` | str | 46.27% | 6 | Continent field | OC, OC |
| `iso_country` | str | 0.35% | 246 | Iso Country field | US, US |
| `iso_region` | str | 0.0% | 3,007 | Iso Region field | US-PA, US-KS |
| `municipality` | str | 5.5% | 38,146 | Municipality field | Bensalem, Leoti |
| `icao_code` | str | 88.17% | 10,119 | Icao Code field | HCAD, OEBT |
| `iata_code` | str | 89.41% | 9,056 | Iata Code field | UTK, OCA |
| `gps_code` | str | 48.23% | 44,283 | Gps Code field | K00A, 00AA |
| `local_code` | str | 57.8% | 34,589 | Local Code field | 00A, 00AA |
| `coordinates` | str | 0.0% | 85,408 | Coordinates field | 40.070985, -74.933689, 38.704022, -101.473911 |

---

## Data Quality Notes

- **Duplicate Records:** 0
- **Completeness:** 10.6% (best column)

## Usage Notes

This dataset is modeled on publicly available UAE government statistics and open data.
For production use, validate against official DLD/FCSC/UAE Central Bank sources.