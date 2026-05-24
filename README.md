# 🚗 AI-Powered Automobile Demand Intelligence Platform

Welcome to the **AI-Powered Automobile Demand Intelligence Platform**, an enterprise-grade decision support suite that integrates advanced machine learning forecasting models, behavioral customer segmentation matrices, and interactive simulation capabilities into a cohesive, high-performance web dashboard.

---

## 🌟 Core Features

- **Executive Analytics:** High-impact KPI indicators (Total Revenue, Sales Volume, average discounts, and lead closing velocity) backed by rich Plotly charts.
- **AI-Powered Forecasting:** Dynamic time-series projections leveraging **Facebook Prophet** integrated with monthly regional macroeconomic indicators (petrol prices, GDP shifts, CPI inflation) upsampled daily as external regressors.
- **Customer Segmentation:** Automated customer profiling using **KMeans clustering** to partition the customer base into actionable cohorts (Budget Buyers, Premium Buyers, EV Enthusiasts, Fleet Buyers, High Repeat Customers) and seeding those segments back into the primary database.
- **Lead Close Predictive Modeling:** A production-grade **XGBoost Classifier** that calculates the exact conversion probability of a sales lead, backed by a **SHAP explainability** layer mapping the explicit positive and negative feature contributions in real-time.
- **Business Scenario Simulator:** A interactive simulator allowing executives to alter external market conditions (macroeconomic inflation, petrol pricing, EV subsidies, semiconductor constraints) and view simulated forecast shifts live.
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
│   ├── clean_data.py           # Data scrubbing and normalization functions
│   └── seed_database.py        # Relational database seeding script
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
    ├── regional.py             # GPS Map and dealer leaderboards
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

### 3. Ingest Datasets & Train Machine Learning Models
Run the pipeline runner script to ingest all raw CSV datasets into the local SQLite database (`automobile_demand.db`) and train all KMeans clustering and XGBoost classifier assets:

```bash
python train_models.py
```

### 4. Launch the Streamlit Dashboard
Start the production-ready Streamlit app locally:

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser to explore the fully functional dashboard!

---

## 💾 Database Schema (Star Schema)

The database utilizes standard relational mappings built via SQLAlchemy ORM:
- **`sales` (Fact Table):** Tracks all individual sale transactions, fully denormalized with region, vehicle categories, and fuel types for high-performance analytical aggregates.
- **`customers` (Dimension Table):** Hosts CRM profiles, including credit score, occupation, estimated annual income, and assigned customer segments.
- **`vehicles` (Dimension Table):** The product catalog containing specifications, range (for EVs), pricing, and launch details.
- **`dealers` (Dimension Table):** Showroom network data containing tier listings, capacity, and latitude/longitude coordinates.
- **`inventory` (Dimension Table):** Stock levels, daily holding costs, stockout alerts, and transit quantities.
- **`external_factors` (Dimension Table):** Macroeconomic conditions tracked monthly per region.
