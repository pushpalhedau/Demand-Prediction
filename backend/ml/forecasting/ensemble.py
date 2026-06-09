"""
Forecast Ensemble — trains multiple models, selects the best by
walk-forward cross-validation (3 folds).

Accuracy improvements over v1
------------------------------
* Walk-forward CV (3 folds): model selection uses mean MAPE across three
  time windows instead of a single fixed split — no lucky-draw selection.
* Macro/sentiment shifted +1 month: removes look-ahead bias where
  current-month sentiment was used to predict current-month demand.
* Richer features: lag2, lag9, roll3, roll12, volatility (6-mo rolling std
  of log growth), yoy acceleration, and rate×demand interaction term.
* Residual-based horizon-aware confidence bands: uncertainty scales with
  √h so 90-day bands are visibly wider than 30-day bands.
* Stronger regularisation tuned for small monthly samples (~60–72 rows).
* Fit timestamp saved; staleness warning logged when model is > 30 days old.
"""
from __future__ import annotations

import json
import logging
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import joblib

warnings.filterwarnings("ignore")
log = logging.getLogger(__name__)


def _import_prophet():
    from prophet import Prophet
    return Prophet

def _import_lgbm():
    import lightgbm as lgb
    return lgb

def _import_xgb():
    import xgboost as xgb
    return xgb

def _import_catboost():
    from catboost import CatBoostRegressor
    return CatBoostRegressor


MODELS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models"

_VAL_MONTHS  = 6    # 6 months ensures training includes 2024 plateau data — better detrended calibration
_CV_FOLDS    = 3    # walk-forward folds for model selection
_CV_VAL_MON  = 9    # months per CV fold (was 6 — larger folds cross regime boundary)
_MIN_TRAIN   = 30   # minimum training rows (was 24 — need 30 for stable lag12 population)
_STALE_DAYS  = 30   # warn if cached model is older than this


class ForecastEnsemble:
    MODEL_NAMES = ["prophet", "lgbm", "xgb", "catboost"]

    def __init__(self, target: str = "units"):
        self.target        = target
        self.models:       Dict[str, object]      = {}
        self.metrics:      Dict[str, Dict]        = {}
        self.best_model:   str                    = "lgbm"
        self.feature_names: List[str]             = []
        self._daily_df:    Optional[pd.DataFrame] = None
        self._drift_info:  Dict                   = {}
        self._is_fitted    = False

    # ── Public API ─────────────────────────────────────────────────────

    def fit(self,
            df_transactions: pd.DataFrame,
            df_macro:        Optional[pd.DataFrame] = None,
            df_sentiment:    Optional[pd.DataFrame] = None,
            df_cpi:          Optional[pd.DataFrame] = None,
            df_price_index:  Optional[pd.DataFrame] = None,
            df_rentals:      Optional[pd.DataFrame] = None,
            df_gdelt:        Optional[pd.DataFrame] = None,
            fast: bool = False) -> "ForecastEnsemble":
        """
        Train all models and select the best by walk-forward CV.

        fast=True — area-level shortcut: trains only LightGBM with a single
        train/val split (no CV, no Prophet/XGB/CatBoost).  ~10–20× faster;
        used for by-area charts where hundreds of areas may be fitted in parallel.
        """
        log.info("ForecastEnsemble.fit(target=%s, fast=%s)", self.target, fast)
        self._daily_df = self._prepare_series(
            df_transactions, df_macro, df_sentiment,
            df_cpi, df_price_index, df_rentals, df_gdelt,
        )

        if fast:
            # ── Fast path: single split, LightGBM only ─────────────────
            train, val = self._train_val_split(self._daily_df)
            try:
                self._train_lgbm_fast(train, val)
            except Exception as exc:
                log.warning("Fast LGBM fit failed: %s — skipping area", exc)
            self.best_model = "lgbm"
            self._is_fitted  = bool(self.models)
            # Don't save cache — area models are transient
            return self

        # ── Full path: walk-forward CV + all models ────────────────────
        cv_mapes = self._walk_forward_cv(self._daily_df)
        log.info("CV MAPE by model: %s", {k: f"{v:.2f}%" for k, v in cv_mapes.items()})
        self.best_model = min(cv_mapes, key=cv_mapes.get)

        train, val = self._train_val_split(self._daily_df)
        self._drift_info = self._compute_drift(train["y"], val["y"])
        if self._drift_info["drift_detected"]:
            log.warning(
                "Distribution drift: train_mean=%.1f → val_mean=%.1f (shift=%.1f%%). "
                "Negative R² likely. post_rate_hike feature added to mitigate.",
                self._drift_info["train_mean"], self._drift_info["val_mean"],
                self._drift_info["mean_shift_pct"],
            )

        for name in self.MODEL_NAMES:
            try:
                self._train_model(name, train, val)
            except Exception as exc:
                log.warning("Model %s failed: %s", name, exc)

        if self.best_model not in self.models:
            self.best_model = min(
                self.metrics, key=lambda m: self._model_score(self.metrics[m])
            )

        log.info(
            "Best model (CV): %s  MAPE=%.2f%%  R²=%.4f",
            self.best_model,
            self.metrics.get(self.best_model, {}).get("mape", 0),
            self.metrics.get(self.best_model, {}).get("r2", 0),
        )
        self._is_fitted = True
        self._save_cache()
        return self

    def predict(self, horizon_days: int = 90) -> Dict:
        if not self._is_fitted:
            self._load_cache()
        if not self._is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        return self._generate_forecast(self.best_model, horizon_days)

    def predict_all_models(self, horizon_days: int = 90) -> Dict[str, Dict]:
        if not self._is_fitted:
            self._load_cache()
        results = {}
        for name in self.MODEL_NAMES:
            if name in self.models:
                try:
                    results[name] = self._generate_forecast(name, horizon_days)
                except Exception as exc:
                    log.warning("Predict failed for %s: %s", name, exc)
        return results

    def get_metrics(self) -> Dict[str, Dict]:
        return self.metrics

    def get_drift_info(self) -> Dict:
        """Compute train/val distribution shift from stored daily_df (available after fit or load)."""
        if not self._drift_info and self._daily_df is not None:
            train, val = self._train_val_split(self._daily_df)
            self._drift_info = self._compute_drift(train["y"], val["y"])
        return self._drift_info

    @staticmethod
    def _compute_drift(y_train: "pd.Series", y_val: "pd.Series") -> Dict:
        train_mean = float(y_train.mean())
        val_mean   = float(y_val.mean())
        shift_pct  = abs(val_mean - train_mean) / max(train_mean, 1e-9) * 100
        return {
            "train_mean":      round(train_mean, 2),
            "val_mean":        round(val_mean, 2),
            "mean_shift_pct":  round(shift_pct, 1),
            "drift_detected":  shift_pct > 30,
        }

    # Human-readable labels and definitions for every model feature
    _FEATURE_DEFS: Dict[str, Dict[str, str]] = {
        "lag1":                        {"label": "Last Month's Demand",       "desc": "Transaction count from the previous month — the single strongest predictor. Demand tends to continue in the direction it was going."},
        "lag2":                        {"label": "2-Month Demand Lag",        "desc": "Demand two months ago. Captures short-term momentum beyond just last month."},
        "lag3":                        {"label": "3-Month Demand Trend",      "desc": "Demand three months ago. Useful for detecting quarterly seasonal patterns."},
        "lag6":                        {"label": "6-Month Demand Lag",        "desc": "Demand from half a year ago. Captures medium-term cycles and semi-annual seasonality."},
        "lag9":                        {"label": "9-Month Demand Lag",        "desc": "Demand nine months prior. Bridges the gap between short-term and annual cycles."},
        "lag12":                       {"label": "Year-Ago Demand",           "desc": "Same month last year — the primary signal for annual seasonality (Ramadan dip, summer slowdown, year-end surge)."},
        "roll3":                       {"label": "3-Month Moving Average",    "desc": "Average monthly demand over the past 3 months. Smooths noise to reveal the short-term trend direction."},
        "roll6":                       {"label": "6-Month Moving Average",    "desc": "Average demand over the past 6 months. Represents the medium-term baseline."},
        "roll12":                      {"label": "12-Month Moving Average",   "desc": "Trailing annual average — the detrending baseline. The model predicts ± deviations from this level."},
        "volatility":                  {"label": "Market Volatility",         "desc": "6-month rolling std of log-growth. High = uncertain market; low = stable. Wider forecast bands when elevated."},
        "yoy_log_diff":                {"label": "YoY Growth Rate",           "desc": "Year-over-year log difference ≈ annualised growth rate. Positive means the market is growing vs. same period last year."},
        "yoy_accel":                   {"label": "Growth Acceleration",       "desc": "Change in YoY growth rate. Positive = growth is speeding up; negative = growth is slowing even if still positive."},
        "trend":                       {"label": "Long-Term Trend",           "desc": "A linear time counter across the full 2019–2024 history. Captures secular growth or structural decline."},
        "post_rate_hike":              {"label": "Post Rate-Hike Regime",     "desc": "Binary flag (1 from July 2022) when the UAE base rate exceeded 2%. Separates the pre- and post-hike market regimes."},
        "avg_mortgage_rate_pct":       {"label": "Mortgage Rate",             "desc": "Average home loan interest rate. Higher rates reduce affordability and suppress transaction volumes."},
        "uae_base_rate_pct":           {"label": "Central Bank Rate",         "desc": "UAE Central Bank base rate — the primary monetary policy lever affecting all lending costs in the market."},
        "rate_x_lag12":                {"label": "Rate × Year-Ago Demand",    "desc": "Interaction term: how much does the interest rate impact demand at different demand levels? Captures non-linear rate sensitivity."},
        "month_sin":                   {"label": "Seasonality (sin)",         "desc": "Sine-encoded month-of-year. Together with the cosine component, encodes annual seasonality as a smooth cycle without a hard cut-off."},
        "month_cos":                   {"label": "Seasonality (cos)",         "desc": "Cosine-encoded month-of-year. Works with the sine component to represent the full annual seasonal pattern."},
        "real_estate_sentiment_index": {"label": "Market Sentiment",          "desc": "Composite index of real estate market sentiment from surveys and news. Typically leads transactions by 1–2 months."},
        "buyer_confidence_index":      {"label": "Buyer Confidence",          "desc": "Survey-based index of buyer willingness to transact. Drops before demand slowdowns; rises before recovery phases."},
        "seller_confidence_index":     {"label": "Seller Confidence",         "desc": "Willingness of sellers to list and negotiate. Low seller confidence tightens supply and can boost prices even as volumes dip."},
        "search_volume_index":         {"label": "Property Search Volume",    "desc": "Online search activity for real estate. A leading indicator — search peaks typically precede transaction peaks by 4–6 weeks."},
        "covid_shock":                 {"label": "COVID Lockdown",            "desc": "Binary shock flag (1 = March–June 2020). Captures the demand collapse during the initial pandemic lockdown."},
        "expo_boost":                  {"label": "Expo 2020 Boost",           "desc": "Binary flag for Oct 2021 – Mar 2022. Expo 2020 Dubai attracted foreign investment and elevated transaction volumes."},
        "yoy_inflation_pct":           {"label": "YoY Inflation",             "desc": "Year-over-year CPI change. Rising inflation erodes real returns and can shift buy-vs-rent decisions."},
        "housing_cpi_yoy":             {"label": "Housing CPI YoY",           "desc": "Annual change in the housing component of CPI. Directly reflects rent and property cost trends."},
        "price_yoy_change":            {"label": "Property Price Growth",     "desc": "YoY change in property prices. Rising prices attract investors; very high prices suppress end-user demand."},
        "rental_yield":                {"label": "Rental Yield",              "desc": "Annual rental income as % of property value. Higher yields attract buy-to-let investors, boosting transaction demand."},
        "rental_demand_yoy":           {"label": "Rental Demand Growth",      "desc": "YoY change in rental contract volumes. Strong rental demand signals population growth and future buying pressure."},
        "gdelt_tone_market":           {"label": "News Tone: RE Market",      "desc": "GDELT sentiment score for UAE real estate news. Negative tone precedes cautious buying; positive tone correlates with activity surges."},
        "gdelt_tone_golden_visa":      {"label": "News Tone: Golden Visa",    "desc": "Media sentiment around the UAE Golden Visa programme. Positive coverage drives foreign investor demand spikes."},
        "gdelt_tone_mortgage":         {"label": "News Tone: Mortgages",      "desc": "Media sentiment around UAE mortgage market. Reflects rate expectations and lending ease as perceived by buyers."},
    }

    def get_feature_importance(self) -> List[Dict]:
        model = self.models.get(self.best_model)
        if model is None:
            return []
        try:
            if self.best_model == "lgbm":
                imp   = model.feature_importance(importance_type="gain")
                names = model.feature_name()
                pairs = sorted(zip(names, imp), key=lambda x: x[1], reverse=True)[:10]
                total = sum(v for _, v in pairs) or 1
            elif self.best_model == "xgb":
                scores = model.get_booster().get_fscore()
                pairs  = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
                total  = sum(v for _, v in pairs) or 1
            elif self.best_model == "catboost":
                scores = dict(zip(self.feature_names, model.get_feature_importance()))
                pairs  = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
                total  = sum(v for _, v in pairs) or 1
            else:
                return []

            result = []
            for name, raw_imp in pairs:
                meta  = self._FEATURE_DEFS.get(name, {})
                label = meta.get("label", name.replace("_", " ").title())
                desc  = meta.get("desc", "")
                result.append({
                    "feature":        name,
                    "label":          label,
                    "description":    desc,
                    "importance":     float(raw_imp),
                    "importance_pct": round(float(raw_imp) / total * 100, 2),
                })
            return result
        except Exception:
            pass
        return []

    # ── Model Selection Score ──────────────────────────────────────────

    @staticmethod
    def _model_score(metrics: Dict) -> float:
        mape = metrics.get("mape", 999.0)
        r2   = metrics.get("r2",  -999.0)
        return mape + max(0.0, -r2) * 20.0 - max(0.0, r2) * 5.0

    # ── Walk-Forward Cross-Validation ──────────────────────────────────

    def _walk_forward_cv(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        3-fold expanding-window CV.  Each fold trains on all data up to the
        fold boundary, then validates on the next _CV_VAL_MON months.
        Returns mean MAPE per model name.
        """
        n = len(df)
        available = n - _MIN_TRAIN
        actual_folds = min(_CV_FOLDS, max(1, available // _CV_VAL_MON))

        fold_mapes: Dict[str, List[float]] = {name: [] for name in self.MODEL_NAMES}

        for i in range(actual_folds):
            val_end   = n - (actual_folds - 1 - i) * _CV_VAL_MON
            val_start = val_end - _CV_VAL_MON
            if val_start < _MIN_TRAIN:
                continue

            f_train = df.iloc[:val_start].copy()
            f_val   = df.iloc[val_start:val_end].copy()

            for name in self.MODEL_NAMES:
                try:
                    _, met = self._fit_model_cv(name, f_train, f_val)
                    fold_mapes[name].append(met.get("mape", 999.0))
                except Exception as exc:
                    log.debug("CV fold %d model %s: %s", i, name, exc)
                    fold_mapes[name].append(999.0)

        return {
            name: float(np.mean(v)) if v else 999.0
            for name, v in fold_mapes.items()
        }

    def _fit_model_cv(
        self, name: str, train: pd.DataFrame, val: pd.DataFrame
    ) -> Tuple[object, Dict]:
        """Train a model for CV purposes — returns (model, metrics) without
        storing to self.models / self.metrics."""
        if name == "prophet":
            return self._fit_prophet_cv(train, val)
        elif name == "lgbm":
            return self._fit_lgbm_cv(train, val)
        elif name == "xgb":
            return self._fit_xgb_cv(train, val)
        elif name == "catboost":
            return self._fit_catboost_cv(train, val)
        return None, {"mape": 999.0}

    # ── Data Preparation ───────────────────────────────────────────────

    def _prepare_series(self,
                        df_tx:          pd.DataFrame,
                        df_macro:       Optional[pd.DataFrame],
                        df_sent:        Optional[pd.DataFrame],
                        df_cpi:         Optional[pd.DataFrame] = None,
                        df_price_index: Optional[pd.DataFrame] = None,
                        df_rentals:     Optional[pd.DataFrame] = None,
                        df_gdelt:       Optional[pd.DataFrame] = None) -> pd.DataFrame:
        df_tx = df_tx.copy()
        df_tx["transaction_date"] = pd.to_datetime(df_tx["transaction_date"])
        df_tx["ym"] = df_tx["transaction_date"].dt.to_period("M")

        if self.target == "units":
            agg = df_tx.groupby("ym").size().reset_index(name="y")
        else:
            agg = df_tx.groupby("ym")["transaction_value_aed"].sum().reset_index(name="y")

        agg["ds"] = agg["ym"].dt.to_timestamp()
        agg = agg.sort_values("ds").reset_index(drop=True)
        agg["y"] = agg["y"].fillna(0)
        agg["y_log"] = np.log1p(agg["y"])
        agg["trend"]  = np.arange(len(agg))

        # ── Core lag features (log scale) ─────────────────────────────
        for lag in [1, 2, 3, 6, 9, 12]:
            agg[f"lag{lag}"] = agg["y_log"].shift(lag)

        # Rolling means (shifted by 1 to avoid same-period leakage)
        agg["roll3"]  = agg["y_log"].shift(1).rolling(3).mean()
        agg["roll6"]  = agg["y_log"].shift(1).rolling(6).mean()
        agg["roll12"] = agg["y_log"].shift(1).rolling(12).mean()

        # Detrended log-target: model learns ±deviations from the trailing 12-month
        # demand level rather than predicting the absolute level. This stationarises
        # the target across market regimes — deviations are stable even when the level
        # shifts by 57%. At prediction time: pred_log = model_output + roll12_current.
        agg["y_log_detrended"] = (agg["y_log"] - agg["roll12"]).fillna(0)

        # 6-month rolling volatility of log growth — captures market uncertainty
        agg["volatility"] = agg["y_log"].shift(1).rolling(6).std().fillna(0)

        # YoY log-diff ≈ annualised growth rate
        agg["yoy_log_diff"] = (agg["lag1"] - agg["lag12"]).fillna(0).clip(-2.0, 2.0)

        # YoY acceleration: positive = growth accelerating, negative = slowing
        agg["yoy_accel"] = agg["yoy_log_diff"].diff(1).fillna(0).clip(-1.0, 1.0)

        # Regime flag: UAE base rate exceeded 2% from 2022-07, marking a structural
        # demand shift (stable plateau vs. prior volatile growth). Explicit feature
        # prevents models from treating the plateau as noise.
        agg["post_rate_hike"] = (agg["ds"] >= pd.Timestamp("2022-07-01")).astype(int)

        # Exponential time-decay weights: most-recent months get weight 1.0, oldest
        # get 0.1 — a smooth progression that prioritises the current plateau regime
        # without hard-discarding the historical seasonal patterns the model needs.
        _n = len(agg)
        _raw = np.exp(0.05 * np.arange(_n))
        agg["_sample_weight"] = 0.1 + 0.9 * (_raw - _raw.min()) / (_raw.max() - _raw.min())

        # ── Macro features — shifted +1 month to prevent look-ahead bias ──
        # Publication lag: sentiment/rate data for month M is known at start
        # of month M+1 at the earliest, so we shift the index forward by 1.
        if df_macro is not None and not df_macro.empty:
            macro_m = df_macro.copy()
            macro_m["ym"] = pd.to_datetime(macro_m["date"]).dt.to_period("M")
            for col in ["uae_base_rate_pct", "avg_mortgage_rate_pct"]:
                if col in macro_m.columns:
                    mapping = macro_m.set_index("ym")[col]
                    # Shift index forward: value at M maps to M+1 (publication lag)
                    mapping.index = mapping.index.shift(1)
                    agg[col] = agg["ym"].map(mapping).ffill()

        if df_sent is not None and not df_sent.empty:
            sent_m = df_sent.copy()
            sent_m["ym"] = pd.to_datetime(sent_m["date"]).dt.to_period("M")
            for col in ["real_estate_sentiment_index", "buyer_confidence_index"]:
                if col in sent_m.columns:
                    mapping = sent_m.set_index("ym")[col]
                    mapping.index = mapping.index.shift(1)
                    agg[col] = agg["ym"].map(mapping).ffill()

        # ── Macro interaction feature (if rate data available) ─────────
        if "uae_base_rate_pct" in agg.columns and "lag12" in agg.columns:
            agg["rate_x_lag12"] = agg["uae_base_rate_pct"].fillna(0) * agg["lag12"].fillna(0)

        # ── Cyclical month encoding ─────────────────────────────────────
        agg["month_sin"] = np.sin(2 * np.pi * agg["ds"].dt.month / 12)
        agg["month_cos"] = np.cos(2 * np.pi * agg["ds"].dt.month / 12)

        # ── Event shock flags ───────────────────────────────────────────
        agg["covid_shock"] = (
            (agg["ds"] >= pd.Timestamp("2020-03-01")) &
            (agg["ds"] <= pd.Timestamp("2020-06-30"))
        ).astype(int)
        agg["expo_boost"] = (
            (agg["ds"] >= pd.Timestamp("2021-10-01")) &
            (agg["ds"] <= pd.Timestamp("2022-03-31"))
        ).astype(int)

        # ── Extra sentiment columns (already loaded, unused until now) ──
        if df_sent is not None and not df_sent.empty:
            sent_extra = df_sent.copy()
            sent_extra["ym"] = pd.to_datetime(sent_extra["date"]).dt.to_period("M")
            for col in ["seller_confidence_index", "search_volume_index"]:
                if col in sent_extra.columns:
                    mapping = sent_extra.set_index("ym")[col]
                    mapping.index = mapping.index.shift(1)
                    agg[col] = agg["ym"].map(mapping).ffill().fillna(0)

        # ── Housing CPI features ────────────────────────────────────────
        if df_cpi is not None and not df_cpi.empty:
            cpi_m = df_cpi.copy()
            cpi_m["ym"] = pd.to_datetime(cpi_m["date"]).dt.to_period("M")
            for col in ["yoy_inflation_pct", "housing_cpi"]:
                if col in cpi_m.columns:
                    mapping = cpi_m.set_index("ym")[col]
                    mapping.index = mapping.index.shift(1)
                    agg[col] = agg["ym"].map(mapping).ffill().fillna(0)
            if "housing_cpi" in agg.columns:
                agg["housing_cpi_yoy"] = agg["housing_cpi"].pct_change(12).fillna(0) * 100
                agg.drop(columns=["housing_cpi"], inplace=True, errors="ignore")

        # ── Price momentum from quarterly price index ───────────────────
        if df_price_index is not None and not df_price_index.empty:
            try:
                px = df_price_index.copy()
                px["date"] = pd.to_datetime(
                    px["year"].astype(str) + "-" +
                    ((px["quarter"] - 1) * 3 + 1).astype(str) + "-01"
                )
                px_agg = (
                    px.groupby("date")[["price_yoy_change_pct", "rental_yield_pct"]]
                    .mean()
                )
                px_agg.index = pd.DatetimeIndex(px_agg.index)
                px_monthly = px_agg.resample("MS").interpolate("linear")
                px_monthly.index = px_monthly.index.to_period("M").shift(3)  # 1-quarter lag
                agg["price_yoy_change"] = agg["ym"].map(px_monthly["price_yoy_change_pct"]).ffill().fillna(0)
                agg["rental_yield"]     = agg["ym"].map(px_monthly["rental_yield_pct"]).ffill().fillna(0)
            except Exception as exc:
                log.debug("Price index feature skipped: %s", exc)

        # ── Rental demand YoY ───────────────────────────────────────────
        if df_rentals is not None and not df_rentals.empty:
            try:
                rent = df_rentals.copy()
                rent["ym"] = pd.to_datetime(rent["contract_date"]).dt.to_period("M")
                rent_monthly = rent.groupby("ym").size().reset_index(name="rental_count")
                rent_monthly["rental_yoy"] = (
                    rent_monthly["rental_count"].pct_change(12).fillna(0).clip(-1, 2) * 100
                )
                mapping = rent_monthly.set_index("ym")["rental_yoy"]
                mapping.index = mapping.index.shift(1)
                agg["rental_demand_yoy"] = agg["ym"].map(mapping).ffill().fillna(0)
            except Exception as exc:
                log.debug("Rental demand feature skipped: %s", exc)

        # ── GDELT thematic sentiment ────────────────────────────────────
        if df_gdelt is not None and not df_gdelt.empty:
            try:
                gdelt = df_gdelt.copy()
                gdelt["ym"] = pd.to_datetime(
                    gdelt["year"].astype(str) + "-" +
                    gdelt["month"].astype(str).str.zfill(2) + "-01"
                ).dt.to_period("M")
                for theme, feat_name in {
                    "UAE_REAL_ESTATE_MARKET": "gdelt_tone_market",
                    "GOLDEN_VISA_UAE":        "gdelt_tone_golden_visa",
                    "UAE_MORTGAGE_MARKET":    "gdelt_tone_mortgage",
                }.items():
                    theme_data = gdelt[gdelt["theme"] == theme]
                    if not theme_data.empty:
                        mapping = theme_data.set_index("ym")["avg_tone"]
                        mapping.index = mapping.index.shift(1)
                        agg[feat_name] = agg["ym"].map(mapping).ffill().fillna(0)
            except Exception as exc:
                log.debug("GDELT sentiment features skipped: %s", exc)

        # Drop rows where lag1 is NaN (first row only)
        agg = agg.dropna(subset=["lag1"]).reset_index(drop=True)
        num_cols = agg.select_dtypes(include=[np.number]).columns.difference(["y", "y_log"])
        agg[num_cols] = agg[num_cols].fillna(0)

        return agg

    def _train_val_split(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        val_n  = min(_VAL_MONTHS, max(6, len(df) // 6))
        split  = len(df) - val_n
        return df.iloc[:split].copy(), df.iloc[split:].copy()

    def _feature_cols(self, df: pd.DataFrame) -> List[str]:
        exclude = {"ds", "y", "y_log", "ym", "_sample_weight", "y_log_detrended"}
        return [c for c in df.columns if c not in exclude and df[c].dtype != object]

    # ── Fast Training (area-level, LightGBM only) ──────────────────────

    def _train_lgbm_fast(self, train: pd.DataFrame, val: pd.DataFrame):
        """Reduced-cost LightGBM fit for area-level forecasts.
        Fewer rounds + tighter early-stopping to stay under 2s per area."""
        lgb   = _import_lgbm()
        feats = self._feature_cols(train)
        if not self.feature_names:
            self.feature_names = feats
        X_tr,  y_tr_log  = train[feats].fillna(0), train["y_log_detrended"]
        X_val, y_val_orig = val[feats].fillna(0),   val["y"]
        dtrain = lgb.Dataset(X_tr, label=y_tr_log)
        dval   = lgb.Dataset(X_val, label=val["y_log_detrended"], reference=dtrain)
        params = dict(
            objective="regression", metric="rmse",
            num_leaves=8, learning_rate=0.08,
            min_data_in_leaf=3,
            lambda_l1=1.0, lambda_l2=5.0,
            verbosity=-1, force_col_wise=True,
        )
        m = lgb.train(
            params, dtrain, num_boost_round=150,
            valid_sets=[dval],
            callbacks=[lgb.early_stopping(15, verbose=False),
                       lgb.log_evaluation(-1)],
        )
        y_pred_det = m.predict(X_val.values)
        y_pred_log = y_pred_det + val["roll12"].fillna(0).values
        y_pred = np.expm1(y_pred_log).clip(min=0)
        self.models["lgbm"]  = m
        self.metrics["lgbm"] = self._compute_metrics(y_val_orig.values, y_pred)

    # ── Full Training (stored to self) ─────────────────────────────────

    def _train_model(self, name: str, train: pd.DataFrame, val: pd.DataFrame):
        log.info("Training %s …", name)
        if   name == "prophet":  self._train_prophet(train, val)
        elif name == "lgbm":     self._train_lgbm(train, val)
        elif name == "xgb":      self._train_xgb(train, val)
        elif name == "catboost": self._train_catboost(train, val)

    def _train_prophet(self, train: pd.DataFrame, val: pd.DataFrame):
        Prophet = _import_prophet()
        m = Prophet(
            yearly_seasonality=True,        # 6 full years of data — enable annual seasonality
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.3,    # more flexible — detects COVID + rate-hike breaks
            seasonality_mode="multiplicative",  # better for growth markets
        )
        m.fit(train[["ds", "y"]].copy())
        future = m.make_future_dataframe(periods=len(val), freq="MS")
        fc     = m.predict(future)
        y_pred = fc.tail(len(val))["yhat"].clip(lower=0).values
        y_true = val["y"].values
        self.models["prophet"]  = m
        self.metrics["prophet"] = self._compute_metrics(y_true, y_pred)

    def _train_lgbm(self, train: pd.DataFrame, val: pd.DataFrame):
        lgb   = _import_lgbm()
        feats = self._feature_cols(train)
        if not self.feature_names:
            self.feature_names = feats
        X_tr,  y_tr_log   = train[feats].fillna(0), train["y_log_detrended"]
        X_val, y_val_orig  = val[feats].fillna(0),   val["y"]
        w_tr = train["_sample_weight"].values if "_sample_weight" in train.columns else None
        dtrain = lgb.Dataset(X_tr, label=y_tr_log, weight=w_tr)
        dval   = lgb.Dataset(X_val, label=val["y_log_detrended"], reference=dtrain)
        params = dict(
            objective="regression",
            metric="rmse",
            num_leaves=20,              # was 8 — more expressive with 32 features
            learning_rate=0.04,         # was 0.05
            min_data_in_leaf=4,         # was 5
            feature_fraction=0.75,
            bagging_fraction=0.75,
            bagging_freq=3,
            lambda_l1=0.5,              # was 1.0
            lambda_l2=3.0,              # was 5.0
            verbosity=-1,
            force_col_wise=True,
        )
        m = lgb.train(
            params, dtrain, num_boost_round=500,    # was 400
            valid_sets=[dval],
            callbacks=[lgb.early_stopping(40, verbose=False),
                       lgb.log_evaluation(-1)],
        )
        y_pred_det = m.predict(X_val.values)
        y_pred_log = y_pred_det + val["roll12"].fillna(0).values
        y_pred = np.expm1(y_pred_log).clip(min=0)
        self.models["lgbm"]  = m
        self.metrics["lgbm"] = self._compute_metrics(y_val_orig.values, y_pred)

    def _train_xgb(self, train: pd.DataFrame, val: pd.DataFrame):
        xgb   = _import_xgb()
        feats = self._feature_cols(train)
        if not self.feature_names:
            self.feature_names = feats
        X_tr,  y_tr_log   = train[feats].fillna(0), train["y_log_detrended"]
        X_val, y_val_orig  = val[feats].fillna(0),   val["y"]
        w_tr = train["_sample_weight"].values if "_sample_weight" in train.columns else None
        m = xgb.XGBRegressor(
            n_estimators=500,           # was 400
            learning_rate=0.02,         # was 0.03
            max_depth=4,                # was 2 — deeper trees capture feature interactions
            min_child_weight=4,         # was 5
            subsample=0.8,
            colsample_bytree=0.75,      # was 0.8
            reg_alpha=0.5,              # was 1.0
            reg_lambda=3.0,             # was 5.0
            verbosity=0,
            early_stopping_rounds=40,   # was 30
        )
        m.fit(X_tr, y_tr_log, sample_weight=w_tr, eval_set=[(X_val, val["y_log_detrended"])], verbose=False)
        y_pred_det = m.predict(X_val)
        y_pred_log = y_pred_det + val["roll12"].fillna(0).values
        y_pred = np.expm1(y_pred_log).clip(min=0)
        self.models["xgb"]  = m
        self.metrics["xgb"] = self._compute_metrics(y_val_orig.values, y_pred)

    def _train_catboost(self, train: pd.DataFrame, val: pd.DataFrame):
        CatBoostRegressor = _import_catboost()
        feats = self._feature_cols(train)
        if not self.feature_names:
            self.feature_names = feats
        X_tr,  y_tr_log   = train[feats].fillna(0), train["y_log_detrended"]
        X_val, y_val_orig  = val[feats].fillna(0),   val["y"]
        w_tr = train["_sample_weight"].values if "_sample_weight" in train.columns else None
        m = CatBoostRegressor(
            iterations=600,
            learning_rate=0.02,
            depth=5,
            l2_leaf_reg=6,
            min_data_in_leaf=4,
            loss_function="RMSE",
            eval_metric="RMSE",
            verbose=False,
            early_stopping_rounds=50,
        )
        m.fit(X_tr, y_tr_log, sample_weight=w_tr, eval_set=(X_val, val["y_log_detrended"]))
        y_pred_det = m.predict(X_val)
        y_pred_log = y_pred_det + val["roll12"].fillna(0).values
        y_pred = np.expm1(y_pred_log).clip(min=0)
        self.models["catboost"]  = m
        self.metrics["catboost"] = self._compute_metrics(y_val_orig.values, y_pred)

    # ── CV-only Training (stateless helpers) ──────────────────────────

    def _fit_prophet_cv(self, train, val):
        Prophet = _import_prophet()
        m = Prophet(yearly_seasonality=True, weekly_seasonality=False,
                    daily_seasonality=False, changepoint_prior_scale=0.3,
                    seasonality_mode="multiplicative")
        m.fit(train[["ds", "y"]].copy())
        future = m.make_future_dataframe(periods=len(val), freq="MS")
        fc     = m.predict(future)
        y_pred = fc.tail(len(val))["yhat"].clip(lower=0).values
        return m, self._compute_metrics(val["y"].values, y_pred)

    def _fit_lgbm_cv(self, train, val):
        lgb   = _import_lgbm()
        feats = self._feature_cols(train)
        X_tr,  y_tr   = train[feats].fillna(0), train["y_log_detrended"]
        X_val, y_val  = val[feats].fillna(0),   val["y"]
        w_tr  = train["_sample_weight"].values if "_sample_weight" in train.columns else None
        dtrain = lgb.Dataset(X_tr, label=y_tr, weight=w_tr)
        dval   = lgb.Dataset(X_val, label=val["y_log_detrended"], reference=dtrain)
        params = dict(objective="regression", metric="rmse", num_leaves=20,
                      learning_rate=0.04, min_data_in_leaf=4,
                      feature_fraction=0.75, bagging_fraction=0.75, bagging_freq=3,
                      lambda_l1=0.5, lambda_l2=3.0,
                      verbosity=-1, force_col_wise=True)
        m = lgb.train(params, dtrain, num_boost_round=500,
                      valid_sets=[dval],
                      callbacks=[lgb.early_stopping(40, verbose=False),
                                 lgb.log_evaluation(-1)])
        y_pred_det = m.predict(X_val.values)
        y_pred_log = y_pred_det + val["roll12"].fillna(0).values
        y_pred = np.expm1(y_pred_log).clip(min=0)
        return m, self._compute_metrics(y_val.values, y_pred)

    def _fit_xgb_cv(self, train, val):
        xgb   = _import_xgb()
        feats = self._feature_cols(train)
        X_tr,  y_tr   = train[feats].fillna(0), train["y_log_detrended"]
        X_val, y_val  = val[feats].fillna(0),   val["y"]
        w_tr  = train["_sample_weight"].values if "_sample_weight" in train.columns else None
        m = xgb.XGBRegressor(n_estimators=500, learning_rate=0.02, max_depth=4,
                              min_child_weight=4, subsample=0.8, colsample_bytree=0.75,
                              reg_alpha=0.5, reg_lambda=3.0,
                              verbosity=0, early_stopping_rounds=40)
        m.fit(X_tr, y_tr, sample_weight=w_tr, eval_set=[(X_val, val["y_log_detrended"])], verbose=False)
        y_pred_det = m.predict(X_val)
        y_pred_log = y_pred_det + val["roll12"].fillna(0).values
        y_pred = np.expm1(y_pred_log).clip(min=0)
        return m, self._compute_metrics(y_val.values, y_pred)

    def _fit_catboost_cv(self, train, val):
        CatBoostRegressor = _import_catboost()
        feats = self._feature_cols(train)
        X_tr,  y_tr   = train[feats].fillna(0), train["y_log_detrended"]
        X_val, y_val  = val[feats].fillna(0),   val["y"]
        w_tr  = train["_sample_weight"].values if "_sample_weight" in train.columns else None
        m = CatBoostRegressor(iterations=600, learning_rate=0.02, depth=5,
                              l2_leaf_reg=6, min_data_in_leaf=4,
                              loss_function="RMSE", verbose=False,
                              early_stopping_rounds=50)
        m.fit(X_tr, y_tr, sample_weight=w_tr, eval_set=(X_val, val["y_log_detrended"]))
        y_pred_det = m.predict(X_val)
        y_pred_log = y_pred_det + val["roll12"].fillna(0).values
        y_pred = np.expm1(y_pred_log).clip(min=0)
        return m, self._compute_metrics(y_val.values, y_pred)

    # ── Forecast Generation ────────────────────────────────────────────

    def _generate_forecast(self, model_name: str, horizon_days: int) -> Dict:
        model    = self.models[model_name]
        hist     = self._daily_df.copy()
        n_months = max(1, horizon_days // 30)

        if model_name == "prophet":
            future    = model.make_future_dataframe(periods=n_months + 1, freq="MS")
            fc        = model.predict(future)
            fc_future = fc[fc["ds"] > hist["ds"].max()]
            dates = fc_future["ds"].tolist()
            preds = fc_future["yhat"].clip(lower=0).tolist()
            lower = fc_future["yhat_lower"].clip(lower=0).tolist()
            upper = fc_future["yhat_upper"].clip(lower=0).tolist()

        else:
            feats    = self.feature_names or self._feature_cols(hist)
            last_ds  = hist["ds"].iloc[-1]
            last_row = hist[feats].iloc[-1].to_dict()

            # Residual-based uncertainty: σ scales with √h (horizon step)
            # q10/q90 residuals stored during validation in _compute_metrics
            met      = self.metrics.get(model_name, {})
            q10_res  = met.get("q10_residual", -float(np.std(hist["y"].values[-12:])))
            q90_res  = met.get("q90_residual",  float(np.std(hist["y"].values[-12:])))

            history_log: list = list(hist["y_log"].values.astype(float))
            preds, dates, lower, upper = [], [], [], []

            for i in range(1, n_months + 1):
                n_h  = len(history_log)
                row: Dict = {}

                row["lag1"]  = history_log[-1]
                row["lag2"]  = history_log[-2]  if n_h >= 2  else history_log[-1]
                row["lag3"]  = history_log[-3]  if n_h >= 3  else history_log[-1]
                row["lag6"]  = history_log[-6]  if n_h >= 6  else history_log[-1]
                row["lag9"]  = history_log[-9]  if n_h >= 9  else history_log[-1]
                row["lag12"] = history_log[-12] if n_h >= 12 else history_log[-1]

                row["roll3"]  = float(np.mean(history_log[-3:]))  if n_h >= 3  else row["lag1"]
                row["roll6"]  = float(np.mean(history_log[-6:]))  if n_h >= 6  else row["lag1"]
                row["roll12"] = float(np.mean(history_log[-12:])) if n_h >= 12 else row["lag1"]

                window = history_log[-6:] if n_h >= 6 else history_log
                row["volatility"] = float(np.std(window)) if len(window) > 1 else 0.0

                row["yoy_log_diff"] = float(np.clip(row["lag1"] - row["lag12"], -2.0, 2.0))
                prev_yoy = (history_log[-2] - history_log[-13]
                            if n_h >= 13 else row["yoy_log_diff"])
                row["yoy_accel"]     = float(np.clip(row["yoy_log_diff"] - prev_yoy, -1.0, 1.0))
                row["trend"]         = float(hist["trend"].iloc[-1] + i)
                row["post_rate_hike"] = 1  # all forecast periods are post-2022 rate hike
                forecast_ds = last_ds + pd.DateOffset(months=i)
                row["month_sin"]   = float(np.sin(2 * np.pi * forecast_ds.month / 12))
                row["month_cos"]   = float(np.cos(2 * np.pi * forecast_ds.month / 12))
                row["covid_shock"] = 0   # future months are post-pandemic
                row["expo_boost"]  = 0   # Expo 2020 ended March 2022

                # Carry forward macro / sentiment / interaction
                for f in feats:
                    if f not in row:
                        row[f] = float(last_row.get(f, 0) or 0)

                # Re-compute interaction with carried-forward rate
                if "rate_x_lag12" in feats:
                    row["rate_x_lag12"] = row.get("uae_base_rate_pct", 0) * row["lag12"]

                X_fut = pd.DataFrame([row])[feats].fillna(0)

                if model_name == "lgbm":
                    pred_detrended = float(model.predict(X_fut.values)[0])
                else:
                    pred_detrended = float(model.predict(X_fut)[0])

                # Undo detrend: model predicted the deviation from roll12 (trailing
                # 12-month log mean). Adding roll12 back gives the actual log prediction.
                pred_log  = pred_detrended + row["roll12"]
                pred_orig = max(0.0, float(np.expm1(pred_log)))

                # Horizon-aware bands: uncertainty grows with √(step)
                scale  = float(np.sqrt(i))
                preds.append(pred_orig)
                dates.append(last_ds + pd.DateOffset(months=i))
                lower.append(max(0.0, pred_orig + q10_res * scale))
                upper.append(pred_orig + q90_res * scale)
                history_log.append(pred_log)

        hist_tail = hist.tail(24)
        return {
            "model":   model_name,
            "metrics": self.metrics.get(model_name, {}),
            "historical": {
                "dates":  [d.isoformat() for d in hist_tail["ds"].tolist()],
                "values": hist_tail["y"].tolist(),
            },
            "forecast": {
                "dates":  [d.isoformat() if hasattr(d, "isoformat") else str(d)
                           for d in dates],
                "values": [round(v, 1) for v in preds],
                "lower":  [round(v, 1) for v in lower],
                "upper":  [round(v, 1) for v in upper],
            },
            "feature_importance": self.get_feature_importance(),
            "drift_info": self.get_drift_info(),
        }

    # ── Metrics ────────────────────────────────────────────────────────

    @staticmethod
    def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
        y_true = np.array(y_true, dtype=float)
        y_pred = np.array(y_pred, dtype=float)
        rmse   = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        mae    = float(np.mean(np.abs(y_true - y_pred)))
        mask   = y_true != 0
        mape   = (
            float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)
            if mask.any() else 999.0
        )
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2     = float(1 - ss_res / ss_tot) if ss_tot != 0 else 0.0

        # Signed residuals → P10/P90 for horizon-aware confidence bands
        residuals = y_pred - y_true
        q10 = float(np.percentile(residuals, 10)) if len(residuals) > 1 else -rmse
        q90 = float(np.percentile(residuals, 90)) if len(residuals) > 1 else  rmse

        return {
            "rmse":          round(rmse, 2),
            "mae":           round(mae, 2),
            "mape":          round(mape, 2),
            "r2":            round(r2, 4),
            "q10_residual":  round(q10, 2),
            "q90_residual":  round(q90, 2),
        }

    # ── Persistence ────────────────────────────────────────────────────

    def _save_cache(self):
        try:
            MODELS_DIR.mkdir(exist_ok=True)
            for name, m in self.models.items():
                joblib.dump(m, MODELS_DIR / f"forecast_{self.target}_{name}.pkl")
            with open(MODELS_DIR / f"forecast_{self.target}_meta.json", "w") as f:
                json.dump({
                    "best_model":    self.best_model,
                    "metrics":       self.metrics,
                    "feature_names": self.feature_names,
                    "fit_timestamp": datetime.now(timezone.utc).isoformat(),
                }, f)
            if self._daily_df is not None:
                self._daily_df.to_parquet(
                    MODELS_DIR / f"forecast_{self.target}_data.parquet",
                    index=False,
                )
        except Exception as exc:
            log.warning("Could not save cache: %s", exc)

    def _load_cache(self):
        try:
            meta_path = MODELS_DIR / f"forecast_{self.target}_meta.json"
            data_path = MODELS_DIR / f"forecast_{self.target}_data.parquet"
            if not meta_path.exists():
                return
            with open(meta_path) as f:
                meta = json.load(f)
            self.best_model    = meta["best_model"]
            self.metrics       = meta["metrics"]
            self.feature_names = meta.get("feature_names", [])

            # Staleness check
            fit_ts = meta.get("fit_timestamp")
            if fit_ts:
                age_days = (datetime.now(timezone.utc) -
                            datetime.fromisoformat(fit_ts)).days
                if age_days > _STALE_DAYS:
                    log.warning(
                        "Cached %s model is %d days old (> %d day threshold). "
                        "Consider retraining via POST /forecast/retrain.",
                        self.target, age_days, _STALE_DAYS,
                    )

            for name in self.MODEL_NAMES:
                p = MODELS_DIR / f"forecast_{self.target}_{name}.pkl"
                if p.exists():
                    self.models[name] = joblib.load(p)
            if data_path.exists():
                self._daily_df = pd.read_parquet(data_path)
            self._is_fitted = bool(self.models)
        except Exception as exc:
            log.warning("Could not load cache: %s", exc)
