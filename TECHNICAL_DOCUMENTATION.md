# PredictaX Demand Prediction — Technical Documentation

**Product name (on screen):** Automobile Demand Intelligence Platform
**Purpose:** Streamlit dashboard for UAE automobile demand forecasting, customer/lead intelligence, inventory planning, and geopolitical/news sentiment analysis.

This document is for engineers joining the project. It covers architecture, data flow, database schema, the ML/forecasting internals, the sentiment pipeline, configuration, and deployment. Diagrams are Mermaid — they render natively on GitHub and in VS Code (with the Mermaid preview extension).

---

## 1. Tech Stack

| Layer | Technology |
|---|---|
| UI / app framework | Streamlit `>=1.35.0`, `streamlit-option-menu` for the sidebar nav |
| Charts | Plotly `>=5.22.0` (all charts, incl. the Mapbox dealer map) |
| Data layer | SQLAlchemy `>=2.0.0` ORM over **SQLite** (two separate `.db` files) |
| Forecasting | Facebook/Meta **Prophet** `>=1.1.5` |
| Customer segmentation | scikit-learn **KMeans** `>=1.4.0` |
| Lead scoring | **XGBoost** `>=2.0.0` (`XGBClassifier`) + **SHAP** `>=0.45.0` for explainability |
| News ingestion | **GDELT Doc 2.0 API** (public, no key) |
| Sentiment scoring | **xAI Grok** (`grok-3-mini`, via OpenAI-compatible SDK) with a deterministic keyword-based mock fallback |
| Config | `python-dotenv` (`.env`), no `st.secrets` used anywhere |
| Packaging / deploy | Docker (`Dockerfile`, `docker-compose.yml`) |

No JavaScript/frontend framework exists — Streamlit generates the entire UI server-side from Python.

---

## 2. Repository Layout

```
app.py                     Entry point / router / global filters
train_models.py            CLI: seeds test DB + trains all ML artifacts

dashboard/                 One render_*(filters) function per page
  overview.py               Executive Overview        [active]
  forecasting.py            Demand Forecasting         [active]
  comparison.py             Comparative Analytics      [active]
  regional.py                Regional Intelligence      [active]
  customers.py               Customer Intelligence      [active]
  inventory.py                Inventory Intelligence     [active]
  sentiment_analysis.py       Sentiment / Geo Risk        [active]
  ai_insights.py              Scenario Simulator          [written, NOT routed]
  upload_data.py              CSV upload + retrain UI      [written, NOT routed]
  metrics.py                  Model metrics viewer         [written, NOT routed]

database/
  connection.py             Dual SQLAlchemy engines, mode switch, writable-path fallback
  models.py                 ORM models — 9 tables
  queries.py                Every read query used by the dashboards

forecasting/
  prophet_forecasting.py    Prophet train/predict pipeline, market-driver overrides

ml_models/
  customer_segmentation.py  KMeans clustering (writes segments back to DB)
  xgboost_model.py          Lead-conversion classifier + SHAP explainability

sentiment/
  fetchers/gdelt_fetcher.py     GDELT news client (rate-limited)
  analyzers/grok_analyzer.py    LIVE (Grok) / MOCK sentiment scorer
  signal_processor.py           Aggregation, formulas, orchestration

preprocessing/
  seed_database.py          CSV → SQLite loader (test mode)
  seed_real_database.py     CSV → SQLite loader (real mode)
  clean_data.py              Shared per-table cleaning/typing functions
  fix_*.py, patch_*.py, ...  One-off data-repair scripts (hand-tuning real dataset)

utils/helpers.py            CSS injection, KPI card renderer, palette
models/                     Persisted pickles, mode-scoped: {clustering,xgboost}/{test,real}/
automobile_datasets/        Synthetic "test" mode source CSVs
realdata-datasets/          Real UAE market source CSVs
assets/                     Logo, custom.css
.streamlit/config.toml      Dark theme config (no secrets.toml committed)
Dockerfile, docker-compose.yml
```

Two SQLite files live at repo root and are used interchangeably depending on data mode: `automobile_demand.db` (test) and `real_demand.db` (real).

---

## 3. High-Level Architecture

```mermaid
flowchart TB
    subgraph Client["Browser"]
        UI[Streamlit UI]
    end

    subgraph App["app.py — Router"]
        Sidebar["Sidebar: Global Filters + Nav<br/>(streamlit_option_menu)"]
        Router{"Selected tab"}
    end

    subgraph Dashboards["dashboard/*.py"]
        D1[overview.py]
        D2[forecasting.py]
        D3[comparison.py]
        D4[regional.py]
        D5[customers.py]
        D6[inventory.py]
        D7[sentiment_analysis.py]
    end

    subgraph DataLayer["database/"]
        Conn["connection.py<br/>dual SQLAlchemy engines"]
        Q[queries.py]
        Models["models.py (ORM, 9 tables)"]
    end

    subgraph DBs["SQLite files"]
        RealDB[("real_demand.db")]
        TestDB[("automobile_demand.db")]
    end

    subgraph MLLayer["forecasting/ + ml_models/"]
        Prophet[prophet_forecasting.py]
        KMeans[customer_segmentation.py]
        XGB[xgboost_model.py]
    end

    subgraph SentLayer["sentiment/"]
        GDELT[gdelt_fetcher.py]
        Grok[grok_analyzer.py]
        SigProc[signal_processor.py]
    end

    subgraph ExtAPIs["External APIs"]
        GDELTAPI[GDELT Doc 2.0]
        GrokAPI[xAI Grok API]
    end

    UI --> Sidebar --> Router
    Router --> D1 & D2 & D3 & D4 & D5 & D6 & D7

    D1 & D3 & D4 & D6 --> Q
    D2 --> Prophet
    D5 --> KMeans
    D5 --> XGB
    D7 --> SigProc

    Q --> Conn
    Prophet --> Conn
    KMeans --> Conn
    XGB --> Conn
    SigProc --> Conn

    SigProc --> GDELT --> GDELTAPI
    SigProc --> Grok --> GrokAPI

    Conn --> RealDB
    Conn --> TestDB
    Prophet -. "reads daily_sentiment_summary when use_sentiment=True" .-> SigProc
```

**Key architectural fact:** there is **no caching layer anywhere** in the app (`@st.cache_data` / `@st.cache_resource` are not used). Every widget interaction triggers a full Streamlit script rerun, which re-runs all DB queries and — on the Forecasting page — **retrains Prophet from scratch twice** (once for validation metrics, once on the full dataset). This is fine for a demo/POC at current data volume but is the first thing to address before scaling usage.

---

## 4. Application Bootstrap & Routing (`app.py`)

1. `st.set_page_config(page_title="Automobile Demand Intelligence Platform", layout="wide", initial_sidebar_state="expanded")`.
2. `inject_custom_css()` (`utils/helpers.py`) loads `assets/styles/custom.css`.
3. **Data mode bootstrap**: `st.session_state.data_mode` defaults to `"real"`. The Test/Real switch UI exists in code but is fully commented out — the app is effectively hard-locked to Real mode unless someone edits `app.py` or calls `set_data_mode("test")` directly.
4. On first load in Real mode, if the `sales` table is empty, `preprocessing/seed_real_database.py::main()` runs inside a spinner, then `st.rerun()`.
5. Sidebar nav is `streamlit_option_menu.option_menu` with 7 live entries; 3 more (`Insights & Simulator`, `Data Ingestion Engine`, `Model Performance Metrics`) exist but their imports/menu entries are commented out.
6. **Global filters** (date range, Emirate, Area, Brand, Vehicle Category, Fuel Type) are collected once into a `filters: dict` and passed positionally into every `render_*(filters)` call. Area options dynamically re-query based on the selected Emirate.
7. Routing is a plain `if/elif` chain on the selected menu string → `dashboard.<module>.render_*(filters)`.

### Session state keys in use
`data_mode`, `market_overrides`, `sentiment_pipeline_running`, `sentiment_pipeline_status`, `sentiment_briefing`, `sentiment_briefing_stats`, `fc_cmp_base`, `fc_cmp_sent`, `fc_cmp_target`, `fc_cmp_horizon`.

---

## 5. Database Layer

### 5.1 Dual-engine design

`database/connection.py` maintains **two independent SQLAlchemy engines/sessions in the same process**:

| Mode | File | Env override |
|---|---|---|
| `real` (default, only reachable mode via UI) | `real_demand.db` | `REAL_DATABASE_URL` |
| `test` | `automobile_demand.db` | `DATABASE_URL` |

`set_data_mode(mode)` / `get_data_mode()` flip a module-level global; `get_db_session()` returns a session from whichever engine is active. This single switch also controls which model-pickle subfolder (`models/{clustering,xgboost}/{test,real}/`) each ML module loads from, and several dashboard branches (Overview, Customers, Regional) that show different KPI columns per mode.

### 5.2 Writable-path fallback

Relevant to the earlier commits fixing DB writability on read-only hosts (e.g. Streamlit Community Cloud):

```python
# database/connection.py — _resolve_writable_sqlite_path (paraphrased)
try:
    open(target_path, "r+b")           # actually probe the real DB file
except OSError:
    shutil.copy(target_path, tempfile.gettempdir())
    target_path = tempdir_copy_path    # writes land in temp, not the repo
```

The earlier bug was probing a *sibling* file's writability, which can succeed even when the committed DB file itself is locked/read-only. The fix opens the **actual target file**. If unwritable, it copies the committed DB into the OS temp directory and points the engine there — writes survive for the life of that process only; a redeploy always resets to the checked-in baseline. Both DBs go through this resolver independently.

### 5.3 Schema (ER diagram)

```mermaid
erDiagram
    CUSTOMERS ||--o{ SALES : makes
    VEHICLES ||--o{ SALES : "sold as"
    DEALERS ||--o{ SALES : sells
    DEALERS ||--o{ INVENTORY : stocks
    VEHICLES ||--o{ INVENTORY : "stocked as"
    NEWS_ARTICLES ||--|| SENTIMENT_SIGNALS : "scored into"
    SENTIMENT_SIGNALS }o--|| DAILY_SENTIMENT_SUMMARY : aggregates

    CUSTOMERS {
        int customer_id PK
        int age
        string gender
        string nationality
        string emirate
        string area
        string occupation
        float estimated_monthly_income_aed
        int credit_score
        int number_of_past_purchases
        string customer_segment
        float loyalty_score
        float churn_risk_score
    }
    VEHICLES {
        int vehicle_id PK
        string brand
        string model
        string category
        string fuel_type
        float price_aed
        int engine_cc
        int horsepower
        int range_km
    }
    DEALERS {
        int dealer_id PK
        string dealer_name
        string emirate
        string area
        string tier
        float performance_score
        float google_rating
        bool ev_charging_station
        float latitude
        float longitude
    }
    SALES {
        int sale_id PK
        date sale_date
        int customer_id FK
        int dealer_id FK
        int vehicle_id FK
        int units_sold
        float total_revenue_incl_vat
        float discount_pct
        string financing_type
        bool test_drive_converted
        int lead_to_close_days
        string marketing_channel
    }
    INVENTORY {
        int inventory_id PK
        int dealer_id FK
        int vehicle_id FK
        int current_stock
        float demand_forecast_30d
        int reorder_point
        int days_in_stock
        bool stockout_flag
        bool reorder_needed
        float stockout_risk_score
    }
    EXTERNAL_FACTORS {
        date date PK
        string emirate
        float petrol_95_price_aed_per_litre
        float crude_oil_price_usd
        float gdp_growth_pct
        float cpi_inflation_pct
        float usd_aed_rate
        float import_duty_pct
        int ev_charging_stations_uae
    }
    NEWS_ARTICLES {
        int id PK
        string url
        string title
        string source_domain
        date published_date
    }
    SENTIMENT_SIGNALS {
        int id PK
        int article_id FK
        float sentiment_score
        float impact_score
        string affected_vehicle_category
        string economic_risk
        string demand_direction
        float estimated_demand_change_pct
    }
    DAILY_SENTIMENT_SUMMARY {
        date summary_date PK
        string vehicle_category PK
        float avg_sentiment_score
        float avg_impact_score
        float geo_risk_score
    }
```

> Note: `Sale` denormalizes `brand`/`vehicle_category`/`fuel_type`/`emirate`/`area` directly onto each row (in addition to the FK relationships) purely for query-speed convenience in the dashboards.

### 5.4 Query layer (`database/queries.py`)

- Every function takes a SQLAlchemy `Session` and returns a `dict` (KPI functions) or a `pd.DataFrame` (via `pd.read_sql`).
- `_apply_sale_filters` is a shared helper applying region/city/category/fuel/brand/financing/date filters — used by nearly every `Sale`-based query.
- **National scaling**: the dataset is a documented 1-in-17 sample of the real UAE market. `NATIONAL_SCALE_FACTOR = 17` is applied to sales/revenue KPIs so displayed numbers represent estimated national totals, not raw row counts.
- The "Chinese Brand Pressure" queries (`get_chinese_brand_yearly_share`, `get_price_competitiveness`, `get_ev_segment_by_brand_year`, `get_market_share_shift`) intentionally **ignore the sidebar brand filter** so the competitive-analysis section always shows the full market. The 2027 share projection uses `np.polyfit` (simple linear regression) on year-over-year share.

---

## 6. Data Flow (Seed → Query → Render)

```mermaid
sequenceDiagram
    participant U as Browser
    participant App as app.py
    participant Seed as seed_real_database.py
    participant Conn as connection.py
    participant DB as real_demand.db
    participant Dash as dashboard/forecasting.py
    participant Q as queries.py / Prophet

    U->>App: streamlit run app.py
    App->>Conn: set_data_mode("real")
    Conn->>DB: resolve writable path (probe r+b, else copy to tempdir)
    App->>DB: SELECT count(*) FROM sales
    alt DB empty (first run)
        App->>Seed: main()
        Seed->>Seed: read CSVs from realdata-datasets/
        Seed->>Seed: rename + inject UAE columns (in-memory StringIO)
        Seed->>Seed: clean_data.py — impute, typecast, parse dates
        Seed->>DB: bulk_insert_mappings(...)
        App->>App: st.rerun()
    end
    U->>App: click "Demand Forecasting"
    App->>Dash: render_forecasting(filters)
    Dash->>Q: query sales + external_factors
    Q->>DB: SELECT ...
    DB-->>Q: rows
    Q-->>Dash: DataFrame
    Dash->>Dash: train_prophet_model(...)  (fresh, every rerun)
    Dash-->>U: Plotly chart
```

The sentiment pipeline is a separate, user-triggered flow (see §8) — it doesn't run on page load, only on the "Refresh Data" button or lazily via `ensure_recent_articles_analyzed()` (mock-only, on tab open).

---

## 7. Forecasting Engine (`forecasting/prophet_forecasting.py`)

Single entry point: `train_prophet_model(category, region, fuel_type, target, horizon_days=90, interval_width=0.95, use_sentiment=False, market_overrides=None)` — called fresh on every UI interaction, no caching.

**Pipeline:**
1. Pull daily `Sale.units_sold` or `Sale.total_revenue_incl_vat`, filtered by category/region/fuel_type, reindexed to fill missing dates with 0.
2. Pull `ExternalFactor` columns (monthly), resample to daily via `.resample('D').ffill()`, merge onto sales by date.
3. If `use_sentiment=True`, merge `avg_sentiment_score` and `geopolitical_risk_score` from `signal_processor.get_daily_summaries()` (wrapped in try/except — a missing sentiment table fails silently, forecast just proceeds without those regressors).
4. **Model config**: `Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False, interval_width=interval_width)`. Growth type and changepoint settings are left at Prophet defaults — not tuned anywhere.
5. **Regressors**: iterates a fixed candidate list of ~18 external-factor/sentiment columns; each is added via `model.add_regressor(reg)` only if present **and** has more than one distinct value (constant columns auto-excluded).
6. **Validation split**: last 30 rows held out; reports RMSE, MAE, and a custom `accuracy = max(0, min(1, 1 - mae/mean_y)) * 100`.
7. **Retrains on the full dataset** for the actual forecast — i.e. every call trains Prophet twice.
8. `future = full_model.make_future_dataframe(periods=horizon_days)`; historical regressor values are back-filled, then **user market-driver overrides are applied only to future-dated rows**.
9. `forecast = full_model.predict(future)`; negative `yhat`/bounds are clipped to 0.

### 7.1 What-if slider → forecast chart, full path

```mermaid
flowchart LR
    Slider["User moves e.g. Petrol Price slider"] --> Form["st.form('market_drivers_form')"]
    Form --> Session["st.session_state.market_overrides"]
    Session --> Train["train_prophet_model(market_overrides=...)"]
    Train --> Future["future dataframe rows after last_hist_date"]
    Future --> Regressor["future.loc[future_mask, 'petrol_price'] = value"]
    Regressor --> Predict["full_model.predict(future)"]
    Predict --> RawYhat["Prophet native yhat / yhat_lower / yhat_upper"]
    RawYhat --> Sensitivity["DRIVER_SENSITIVITY elasticity table<br/>(hand-authored, dashboard/forecasting.py)"]
    Sensitivity --> NetImpact["net_impact_pct = Σ (driver delta × sensitivity)"]
    NetImpact --> Scale["yhat_x *= clamp(1 + net_impact_pct/100, 0.3, 3.0)"]
    Scale --> Chart["Bear / Base / Bull chart"]
```

**Important nuance:** the visible chart movement when a slider is dragged is **not purely Prophet's regressor fit**. Two mechanisms stack:
1. The override value genuinely changes what Prophet sees as input (`future[col] = value`), so Prophet's own fitted regressor coefficient has a real (usually small) effect.
2. A separate, hand-authored `DRIVER_SENSITIVITY` dict in `dashboard/forecasting.py` (e.g. "−8% demand per +1 AED/L petrol", "+3.5% per +1pt GDP growth") computes a `net_impact_pct` from the override deltas and **multiplies** all three future-period lines by `1 + net_impact_pct/100`, clamped to `[0.3, 3.0]`. This static elasticity table is what dominates the visible chart delta and the "Market Driver Impact" summary banner — worth knowing if the forecast ever needs to be defended as "purely ML-driven."

**Bear/Base/Bull** = `yhat_lower` / `yhat` / `yhat_upper` — Prophet's native uncertainty interval at the chosen confidence-slider width, after the sensitivity scaling above is applied.

**Seasonality charts** are read directly off Prophet's own `forecast['weekly']` / `forecast['yearly']` component columns, grouped by day-name/month-name.

---

## 8. ML Models

### 8.1 Customer Segmentation (`ml_models/customer_segmentation.py`)

- Algorithm: scikit-learn **KMeans**, `n_clusters=5`, `random_state=42`, `n_init=10`.
- Features (6, median-imputed then `StandardScaler`-normalized): `age`, `estimated_monthly_income_aed`, `credit_score`, `number_of_past_purchases`, `loyalty_score`, `churn_risk_score`.
- Cluster → label mapping is **rule-based on centroid ranking**, not learned: highest-income cluster → "Premium Buyer"; lowest-income of the rest → "Budget Buyer"; highest past-purchases of the rest → "High Repeat"; highest loyalty of the rest → "EV Enthusiast"; leftover → "Fleet Buyer"/"Regular Buyer".
- **Side effect to know about**: training this model writes `customer_segment` back into the live `customers` table via `bulk_update_mappings` — it's not a pure read-only artifact-producing step.
- Persists `scaler.pkl`, `kmeans.pkl`, `cluster_mapping.pkl` to `models/clustering/{test|real}/`.
- Inference: `predict_customer_segment(customer_data: dict)` loads the pickles; falls back to `"Regular Buyer"` on any exception.

### 8.2 Lead Conversion Scoring (`ml_models/xgboost_model.py`)

- Predicts `Sale.test_drive_converted` (binary) via `XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.08, random_state=42, eval_metric="logloss")`.
- Features: 7 categorical (LabelEncoded: financing type, marketing channel, vehicle category, fuel type, emirate, gender, occupation) + 6 numeric (StandardScaler-scaled: base price, discount %, age, income, credit score, loyalty score).
- 80/20 stratified train/test split. Requires ≥100 rows to train.
- Persists `scaler.pkl`, `encoders.pkl`, `xgboost_model.pkl`, `feature_names.pkl` to `models/xgboost/{test|real}/` — **trained offline** (via `train_models.py`), loaded from pickle at inference time.

```mermaid
flowchart LR
    Form["Lead form: age, income, credit score, discount, ..."] --> Encode["LabelEncoders + StandardScaler"]
    Encode --> Model["XGBClassifier (.pkl)"]
    Model --> Prob["Conversion probability"]
    Prob --> Gauge["Gauge chart"]
    Encode --> SHAPCheck{"shap import OK?"}
    SHAPCheck -->|Yes| TreeExplainer["shap.TreeExplainer(model).shap_values(row)"]
    SHAPCheck -->|No / error| Heuristic["Hard-coded fallback heuristic:<br/>discount %, credit score, income only"]
    TreeExplainer --> Attribution["Feature Attribution bar chart"]
    Heuristic --> Attribution
    Prob --> Recommend["Rule-based Smart Action Recommendation<br/>(thresholds: ≥0.75 / ≥0.4 / below)"]
```

The SHAP path is real per-instance SHAP (`TreeExplainer`) when the `shap` package is importable and succeeds. If it throws for any reason, the UI silently switches to a hard-coded heuristic using only 3 fields — this is a **fallback that looks identical in the UI** but is not actually model-derived. Worth knowing before quoting the "explainability" feature as fully SHAP-backed in all cases.

### 8.3 `train_models.py` — what it actually trains

Run manually or at Docker build time (`Dockerfile` runs it during image build). It does 4 things, **all against the test-mode engine only**:
1. `preprocessing.seed_database.main()` — seeds `automobile_demand.db` from `automobile_datasets/`.
2. `train_customer_segmentation(n_clusters=5)`.
3. `train_xgboost_pipeline()`.
4. A verification-only Prophet run for `category="SUV"`.

**Gap to be aware of:** there is no equivalent orchestrator for **real**-mode ML artifacts. The `models/{clustering,xgboost}/real/` pickles and `real_demand.db` must have been produced/committed separately outside this script. If you need to retrain on updated real data, you'll need to either extend `train_models.py` to accept a `--mode real` flag or run the training functions manually against the real engine.

---

## 9. Sentiment & Geopolitical Risk Pipeline

### 9.1 News ingestion (`sentiment/fetchers/gdelt_fetcher.py`)

- Endpoint: `https://api.gdeltproject.org/api/v2/doc/doc` (GDELT Doc 2.0, free, no key). Uses both `mode=ArtList` (article search) and `mode=TimelineTone` (daily tone series).
- 6 themed queries (`UAE_AUTO_QUERIES`): `uae_auto_demand`, `ev_market_uae`, `fuel_oil_prices`, `uae_macro_economy`, `geopolitical_risk`, `luxury_suv_uae`.
- **Rate limiting**: client-enforced minimum 6-second gap between requests (GDELT's real limit is ~1 req/5s), serialized process-wide via a `threading.Lock` so concurrent Streamlit sessions can't both slip past the check. On HTTP 429: exponential backoff from 10s, up to 3 retries.
- `combine_queries=True` (default): issues **one** combined OR'd query instead of 6 separate calls, then re-tags each result to its best-matching theme by keyword overlap — a 6x reduction in request volume.
- `one_per_day=True` (default): keeps only the most recent article per `(theme, day)`.
- Persistence dedupes by URL (unique constraint + in-memory check) — idempotent inserts.

### 9.2 Sentiment scoring — LIVE vs MOCK (`sentiment/analyzers/grok_analyzer.py`)

The toggle is a single environment check:

```python
_XAI_API_KEY = os.getenv("XAI_API_KEY", "").strip()
def is_live_mode() -> bool:
    return bool(_XAI_API_KEY)
```

```mermaid
flowchart TB
    Start["User clicks 'Refresh Data'"] --> Fetch["gdelt_fetcher.py"]
    Fetch -->|"combined OR query, ≥6s between requests"| GDELT[("GDELT Doc 2.0 API")]
    GDELT --> Dedup["Dedupe by URL"] --> Save[("news_articles")]
    Save --> Check{"XAI_API_KEY set?"}
    Check -->|Yes| Live["_analyze_live()<br/>xAI Grok, model=grok-3-mini<br/>batches of 10, temp=0.1, JSON mode"]
    Check -->|No| Mock["_analyze_mock()<br/>keyword rules + md5(title)-seeded RNG"]
    Live -->|"on API/JSON failure"| Mock
    Live --> Signals[("sentiment_signals")]
    Mock --> Signals
    Signals --> Agg["signal_processor.recompute_daily_summaries()"]
    Agg --> Formula["geo_risk = avg_impact_score × (negative_signals / total_signals)"]
    Formula --> Summary[("daily_sentiment_summary")]
    Summary --> Prophet["Prophet use_sentiment=True regressors"]
    Summary --> Tabs["Geopolitical Risk / Economic Signals tabs"]
```

- **LIVE mode**: `openai.OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")` — the `openai` SDK is only used as a generic OpenAI-compatible client pointed at xAI, not OpenAI itself. Model defaults to `grok-3-mini` (overridable via `GROK_MODEL` env var). System prompt instructs a fixed JSON schema per article: `sentiment_score` (−1..1), `impact_score` (0..1), `affected_vehicle_category`, `economic_risk`, `demand_direction`, `estimated_demand_change_pct`, `confidence`, `summary`. If the returned count mismatches the batch, or parsing/the API call fails, that batch **silently falls back to mock scoring**.
- **MOCK mode**: fully deterministic — `hashlib.md5(title)` seeds a `random.Random`, so the same headline always scores identically. Uses hand-curated word lists for sentiment, impact, category, and risk.
- **Cost-control detail worth knowing**: `ensure_recent_articles_analyzed()` runs automatically every time the Geopolitical Risk / Economic Signals / AI Insights sub-tabs are opened, but it **always uses mock scoring regardless of `XAI_API_KEY`** — this is deliberate, to avoid firing billed Grok calls just from a tab click. Only the explicit "Refresh Data" button (`run_full_pipeline()`) uses real Grok analysis when the key is set.

### 9.3 Formulas (`sentiment/signal_processor.py`)

Per day (and per vehicle category, plus an "All" aggregate row):
- `positive_signals` = count where `sentiment_score > 0.15`; `negative_signals` = count where `< -0.15`; rest = neutral.
- `avg_sentiment_score`, `avg_impact_score`, `avg_demand_change_pct` = plain (NaN-safe) means.
- **Geopolitical risk index**: `geo_risk = avg_impact_score × (negative_signals / total_signals)` — impact scaled by the *proportion* of negative-sentiment articles that day, not raw sentiment magnitude.
- `dominant_demand_direction` = plurality vote across the day's signals.

The dashboard's "live" KPI variants (`compute_live_overall_stats`, etc.) recompute these same formulas directly from just-analyzed articles in memory, so the Geopolitical Risk tab updates instantly without waiting for the full `daily_sentiment_summary` table rebuild.

**Fallback values**: when there's no analyzed data yet, `dashboard/sentiment_analysis.py::_geo_risk_fallback()` generates plausible numbers seeded by `date.today().toordinal()` — stable within a day, varies day to day — instead of showing hard zeros. This is the mechanism behind the recent "Randomize Geopolitical Risk fallback values" commits.

### 9.4 Forecast Comparison (sentiment-enhanced forecasting)

`_render_forecast_comparison()` trains **two independent Prophet models**: `train_prophet_model(..., use_sentiment=False)` and `train_prophet_model(..., use_sentiment=True)`, then overlays both `yhat` lines + confidence bands and diffs RMSE/MAE/accuracy. There is no separate blending/ensemble logic — "enhancement" simply means Prophet gets two extra regressor columns (`avg_sentiment_score`, `geopolitical_risk_score`) and fits its own coefficients for them.

---

## 10. Dashboard Modules — Data & Logic Reference

| Module | Queries / models used | Core logic |
|---|---|---|
| `overview.py` | `get_executive_kpis`, `get_monthly_revenue_trend`, `get_sales_by_category`, `get_sales_by_fuel_type`, `get_sales_by_region` | KPI cards 3–4 swap content by data mode (Real: UAE base rate + top brand share; Test: avg discount + lead-close velocity) |
| `forecasting.py` | `forecasting.prophet_forecasting` | See §7 |
| `comparison.py` | `get_yoy_comparison`, plus Chinese-brand queries (`get_chinese_brand_yearly_share`, `get_price_competitiveness`, `get_ev_segment_by_brand_year`, `get_market_share_shift`) | YoY overlap, category/region growth, Chinese-brand competitive section (brand filter deliberately ignored, 2027 projection via `np.polyfit`) |
| `regional.py` | `get_dealer_performance_leaderboard` | Plotly Mapbox bubble map (lat/lon, size=units, color=revenue) with scatter fallback if coordinates missing; leaderboard table, mode-dependent columns |
| `customers.py` | `get_customer_segments_data`, `ml_models.customer_segmentation`, `ml_models.xgboost_model` | Tab 1: segmentation charts. Tab 2: live lead form → `predict_deal_probability()` → gauge + SHAP/heuristic bars + rule-based recommendation |
| `inventory.py` | `get_inventory_status` | KPI cards, urgent-restock table sorted by `stockout_risk_score`, stock-vs-forecast bar, slow-moving inventory, warehouse-zone pie |
| `sentiment_analysis.py` | `sentiment.signal_processor`, `sentiment.analyzers.grok_analyzer` | See §9. 4 active sub-tabs; a 5th ("Recent News") is written but commented out of the tab list |
| `ai_insights.py` (dead) | — | Scenario simulator (petrol shift, EV incentive checkbox, supply-chain constraint selector, marketing spend multiplier) — fully written, not wired into `app.py` |
| `upload_data.py` (dead) | — | CSV drag-and-drop, schema auto-detection, validation checklist — fully written, not wired into `app.py` |
| `metrics.py` (dead) | — | XGBoost hyperparameters + feature importances viewer, reads pickles directly — fully written, not wired into `app.py` |

---

## 11. Configuration & Environment Variables

`.env` (gitignored, loaded via `python-dotenv` in `database/connection.py` and `preprocessing/seed_real_database.py`):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Optional override for the test-mode SQLAlchemy URL |
| `REAL_DATABASE_URL` | Optional override for the real-mode SQLAlchemy URL |
| `DEBUG` | Debug flag |
| `XAI_API_KEY` | Presence toggles Grok LIVE mode; absence = MOCK sentiment scoring everywhere |
| `GROK_MODEL` | Optional, defaults to `grok-3-mini` |
| `SERPER_API_KEY` | Present in `.env` but **not referenced anywhere in the current codebase** — likely leftover/unused |

`.streamlit/config.toml` sets a fixed dark theme (`primaryColor #6366f1`, `backgroundColor #0b0f19`, etc.). No `secrets.toml` is committed, and no code reads `st.secrets` — all configuration flows through `.env`/`os.getenv`.

**Real/Test mode toggle**: `st.session_state.data_mode`, consumed via `get_data_mode()`/`set_data_mode()`. Controls: which SQLite engine every query hits, which model-pickle subfolder each ML module loads, and several dashboard rendering branches. The switch UI itself is commented out in `app.py` — full plumbing exists, but it's currently unreachable from the running app.

---

## 12. Dependencies (`requirements.txt`)

```
streamlit>=1.35.0        pandas>=2.2.0         numpy>=1.26.0
plotly>=5.22.0           prophet>=1.1.5        xgboost>=2.0.0
scikit-learn>=1.4.0      sqlalchemy>=2.0.0     python-dotenv
streamlit-option-menu    shap>=0.45.0          openai>=1.0.0
requests>=2.31.0
```

No `pyproject.toml` in the repo — `requirements.txt` is the single source of truth for dependencies.

---

## 13. Deployment

- **Local dev**: `streamlit run app.py`.
- **Docker**: `Dockerfile` (Python 3.11-slim) installs `requirements.txt`, then **runs `python train_models.py` at image build time** — this bakes a seeded test DB and trained test-mode ML pickles into the image. Exposes port 8501; `CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]`.
- **`docker-compose.yml`**: single `web` service built from the Dockerfile, `8501:8501`, mounts `.:/app` plus named volumes for `/app/.venv` and `/app/models`, sets `DATABASE_URL=sqlite:////app/automobile_demand.db`, `DEBUG=False`, `restart: always`.
- No CI config (`.github/workflows` absent), no `Procfile`.

---

## 14. Known Gaps / Things to Fix Before Scaling

These aren't bugs blocking the demo, but a new engineer should know about them before treating this as production-ready:

1. **No caching anywhere.** Prophet retrains twice per interaction on the Forecasting page and every DB query re-runs on every rerun. Adding `@st.cache_data` (for queries) and `@st.cache_resource` (for trained models, keyed by filter combination) would be the highest-leverage performance fix.
2. **Real-mode ML artifacts have no training script.** `train_models.py` only seeds/trains test mode. Retraining on updated real data currently requires manual intervention.
3. **Three dashboard modules are dead code** (`ai_insights.py`, `upload_data.py`, `metrics.py`) — fully written but not routed in `app.py`. Confirm with product whether these should be re-enabled, finished, or deleted.
4. **SHAP has a silent heuristic fallback.** If the `shap` import/computation fails, `xgboost_model.py` falls back to a 3-feature hard-coded heuristic that renders identically to real SHAP output in the UI — there's no visible indicator distinguishing the two. Worth surfacing a debug flag or log line if this matters for demo integrity.
5. **The "Market Driver Impact" chart movement is dominated by a static elasticity table** (`DRIVER_SENSITIVITY`), not purely by Prophet's fitted regressor coefficients. Fine for a compelling demo; be precise about this if asked "is this a real ML prediction" in a technical review.
6. **`SERPER_API_KEY` is unused** — likely safe to remove from `.env.example`/docs unless there's a planned integration.
7. **Real/Test mode switch is UI-disabled** but the full plumbing exists end-to-end — trivial to re-enable if a test-mode demo is ever needed again.
8. **`real_estate_demand.db`** at repo root is an unrelated/legacy file not referenced by any code — safe to delete after confirming with the team.

---

## 15. Quick Orientation for New Contributors

- Want to change a KPI or chart? Start in the relevant `dashboard/*.py` file — it will point you to the exact `queries.py` function or ML module it calls.
- Want to change what the forecast reacts to? `forecasting/prophet_forecasting.py` (data/regressors) + `dashboard/forecasting.py` (`DRIVER_SENSITIVITY`, `FACTOR_CONFIG` for slider bounds).
- Want to add a new DB column? Update `database/models.py`, then the relevant `preprocessing/clean_data.py` + `seed_*.py` functions, then any `queries.py` function that should expose it.
- Want to retrain ML models after a data change? Run `python train_models.py` for test mode; for real mode, call `train_customer_segmentation()` / `train_xgboost_pipeline()` manually against the real engine (`set_data_mode("real")` first).
- Want to test the sentiment pipeline without burning Grok API calls? Just don't set `XAI_API_KEY` — MOCK mode is deterministic and fully functional end-to-end.
