# 🚗 AI-Powered Automobile Demand Intelligence Platform — UAE Edition

Welcome to the **AI-Powered Automobile Demand Intelligence Platform**, an enterprise-grade decision support suite that integrates advanced machine learning forecasting models, behavioral customer segmentation matrices, and interactive simulation capabilities into a cohesive, high-performance web dashboard.

The dataset models **one regional dealer group of 24 rooftops trading across the seven emirates** (Dubai, Abu Dhabi, Sharjah, Ajman, Ras Al Khaimah, Fujairah, Umm Al Quwain). All figures are the group's own booked retail sales — there is no market-level extrapolation. Currency is **AED**; every vehicle is imported (flat 5% GCC customs duty, flat 5% federal VAT).

---

## 🌟 Core Features

- **Executive Analytics:** High-impact KPI indicators (Total Revenue, Sales Volume, average discounts, and lead closing velocity) backed by rich Plotly charts.
- **AI-Powered Forecasting:** Dynamic time-series projections leveraging **Facebook Prophet** integrated with monthly per-emirate indicators (regulated petrol price, CBUAE base rate, incentive spend, days' supply, Ramadan) upsampled daily as external regressors.
- **Customer Segmentation:** Automated customer profiling using **KMeans clustering** to partition the customer base into actionable cohorts (High-Value / Prime, Loyal Repeat, Core Mainstream, Value Buyers, Lapsed / At-Risk) and seeding those segments back into the primary database. Features include monthly income (AED), AECB credit score and residency tenure; `nationality` is retained on the record and surfaced descriptively (the UAE resident base is ~88% expatriate) but is not itself a clustering feature.
- **Lead Close Predictive Modeling:** A production-grade **XGBoost Classifier** that calculates the exact conversion probability of a sales lead, backed by a **SHAP explainability** layer mapping the explicit positive and negative feature contributions in real-time.
- **What-if Levers (Demand Forecasting tab):** Alter the four conditions a dealer GM actually reasons about — pump price (Special 95, AED/litre), car-loan APR, incentive spend, days' supply on hand — and see the modelled shift against the baseline forecast.
- **Dynamic Ingestion Engine:** Live dataset uploading with automatic column detection, data validation, and real-time model retraining triggers.

---

## 🏗️ Repository Architecture

The platform is designed with a strictly modular, clean separation of concerns:

```
automobile-demand-intelligence/
│
├── app.py                      # Main entrypoint and navigation framework
├── requirements.txt            # Package dependencies
├── README.md                   # System documentation
├── .env                        # Environment configurations
├── train_models.py             # Seeding & training pipeline runner script
│
├── assets/
│   └── styles/
│       └── custom.css          # Premium glassmorphism dark stylesheet
│
├── database/
│   ├── connection.py           # SQLAlchemy engine and session initializer
│   ├── models.py               # Star Schema table definitions
│   └── queries.py              # Optimized analytical aggregations
│
├── preprocessing/
│   ├── generate_uae_data.py    # Synthetic UAE (7-emirate) dataset generator (seeded)
│   ├── clean_data.py           # Data scrubbing and normalization functions
│   ├── seed_database.py        # "test" DB seeder (automobile_datasets/ → automobile_demand.db)
│   └── seed_real_database.py   # "real" DB seeder (realdata-datasets/ → real_demand.db)
│
├── forecasting/
│   └── prophet_forecasting.py   # Prophet trainer and forecast generator
│
├── ml_models/
│   ├── customer_segmentation.py # KMeans segmentation and classifiers
│   └── xgboost_model.py         # XGBoost lead scoring and SHAP explainers
│
└── dashboard/                  # Dashboard individual tabs
    ├── overview.py             # Landing metrics and volume graphs
    ├── forecasting.py          # Prophet uncertainty and decomposition views
    ├── comparison.py           # Overlapping YoY comparison charts
    ├── regional.py             # Store Performance — footprint map + per-rooftop scorecard
    ├── customers.py            # KMeans 2D/3D profiles and lead scorers
    ├── ai_insights.py          # Automated growth recommendations & Simulator
    ├── upload_data.py          # Ingestion engine and uploader
    └── metrics.py              # ML Hyperparameters and elbow profiles
```

---

## ⚡ Quickstart Guide

### 1. Prerequisites
Ensure you have **Python 3.10 to 3.13** installed on your machine. This platform uses the high-performance **`uv`** package manager for super-fast dependency installations.

### 2. Environment Setup & Dependency Installation
Create a python virtual environment and install all necessary packages inside it:

```bash
# Create virtual environment
uv venv

# Activate on Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Activate on Linux/macOS
source .venv/bin/activate

# Install requirements
uv pip install -r requirements.txt
```

### 3. Generate Data, Ingest & Train Machine Learning Models

Regenerate the synthetic UAE datasets (seeded — deterministic), then seed both SQLite databases and train the ML assets:

```bash
# (re)generate realdata-datasets/ and automobile_datasets/ from scratch
python -m preprocessing.generate_uae_data

# seed the "real" DB (real_demand.db) and the "test" DB (automobile_demand.db)
python -m preprocessing.seed_real_database
python -m preprocessing.seed_database

# train KMeans clustering + XGBoost classifier (per data mode)
python train_models.py
```

The Streamlit app also auto-seeds `real_demand.db` on first launch if it is empty.

### 4. Launch the Streamlit Dashboard
Start the production-ready Streamlit app locally:

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser to explore the fully functional dashboard!

---

## 💾 Database Schema (Star Schema)

The database utilizes standard relational mappings built via SQLAlchemy ORM:
- **`sales` (Fact Table):** Tracks all individual sale transactions, fully denormalized with emirate/area, vehicle categories, and fuel types for high-performance analytical aggregates. All money columns are AED (`selling_price_aed`, `vat_amount_aed`, …).
- **`customers` (Dimension Table):** CRM profiles — nationality, emirate/area, AECB credit score, occupation, estimated **monthly** income (AED), residency tenure, and assigned customer segments.
- **`vehicles` (Dimension Table):** The product catalog containing specifications, `mileage_kmpl`, `range_km` (for EVs), `price_aed`, `gcc_spec`, and launch details.
- **`dealers` (Dimension Table):** Rooftop network data — brand, emirate/area, P.O. box, capacity, and latitude/longitude coordinates.
- **`inventory` (Dimension Table):** Month-end stock snapshots, daily holding costs (AED), stockout alerts, port of entry and transit quantities.
- **`external_factors` (Dimension Table):** Per-emirate monthly conditions — regulated petrol price (AED/litre), CBUAE base rate, Dubai real-estate index, tourism index, Ramadan / National Day / DSF flags.
