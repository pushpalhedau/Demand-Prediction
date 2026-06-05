# Manual Download Instructions for Blocked Sources

## Priority 1: DLD Real Estate Data (Dubai Pulse)

### Step 1: Register
1. Go to: https://www.dubaipulse.gov.ae
2. Click "Register" / Sign Up with UAE Pass or email

### Step 2: Find DLD Datasets
Search for these dataset IDs:
- `dld-transactions` - Property sale transactions
- `dld-rental` - Rental contracts (RERA)
- `dld-areas` - Areas lookup
- `dld-projects` - Project register
- `dld-buildings` - Buildings register

### Step 3: Download or API
Each dataset has a "Download CSV" button or API endpoint:
```
https://www.dubaipulse.gov.ae/api/3/action/datastore_search?resource_id={ID}&limit=100000
```

---

## Priority 2: GDELT UAE News Data

Download latest GDELT GKG (Global Knowledge Graph) files:
```bash
# Get latest file list
curl http://data.gdeltproject.org/gdeltv2/lastupdate.txt

# Download and filter for UAE
wget http://data.gdeltproject.org/gdeltv2/YYYYMMDDHHMMSS.gkg.csv.zip
# Filter: grep "UAE\|Dubai\|Abu Dhabi" file.csv > uae_news.csv
```

GDELT Theme codes for UAE real estate:
- `ENV_BUILTENVIRON` - Built environment
- `ECON_REALESTATE` - Real estate economy
- `WB_2671_REAL_ESTATE` - World Bank real estate theme

---

## Priority 3: World Bank API

UAE country code: `ARE`

```bash
# GDP
curl "https://api.worldbank.org/v2/country/ARE/indicator/NY.GDP.MKTP.CD?format=json&per_page=100"

# Population  
curl "https://api.worldbank.org/v2/country/ARE/indicator/SP.POP.TOTL?format=json&per_page=100"

# Inflation CPI
curl "https://api.worldbank.org/v2/country/ARE/indicator/FP.CPI.TOTL.ZG?format=json&per_page=100"

# Unemployment
curl "https://api.worldbank.org/v2/country/ARE/indicator/SL.UEM.TOTL.ZS?format=json&per_page=100"
```

---

## Priority 4: UAE Central Bank EIBOR

Visit: https://www.centralbank.ae/en/forex-eibor/eibor
Download historical EIBOR rates (Excel available)

---

## Priority 5: Kaggle DLD Dataset

1. Login: https://www.kaggle.com
2. Download: https://www.kaggle.com/datasets/azharsaleem/dubai-real-estate-market-transactions-dld
   - Contains 1M+ transactions 2000-2024
   
Also: https://www.kaggle.com/datasets/azharsaleem/uae-real-estate-market-data

---

## Priority 6: FCSC Statistics

Visit: https://fcsc.gov.ae/en-us/Pages/Statistics/Statistics-by-Domain.aspx

Download:
- Population statistics
- Labor force statistics  
- GDP by sector
- National accounts

