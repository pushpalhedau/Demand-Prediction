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

_VAL_MONTHS  = 12   # validation window for final reported metrics
_CV_FOLDS    = 3    # walk-forward folds for model selection
_CV_VAL_MON  = 6    # months per CV fold
_MIN_TRAIN   = 24   # minimum training rows (need lag12 to be valid)
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
            df_macro:     Optional[pd.DataFrame] = None,
            df_sentiment: Optional[pd.DataFrame] = None,
            fast: bool = False) -> "ForecastEnsemble":
        """
        Train all models and select the best by walk-forward CV.

        fast=True — area-level shortcut: trains only LightGBM with a single
        train/val split (no CV, no Prophet/XGB/CatBoost).  ~10–20× faster;
        used for by-area charts where hundreds of areas may be fitted in parallel.
        """
        log.info("ForecastEnsemble.fit(target=%s, fast=%s)", self.target, fast)
        self._daily_df = self._prepare_series(df_transactions, df_macro, df_sentiment)

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

    def get_feature_importance(self) -> List[Dict]:
        model = self.models.get(self.best_model)
        if model is None:
            return []
        try:
            if self.best_model == "lgbm":
                imp   = model.feature_importance(importance_type="gain")
                names = model.feature_name()
                pairs = sorted(zip(names, imp), key=lambda x: x[1], reverse=True)
                return [{"feature": n, "importance": float(v)} for n, v in pairs[:10]]
            if self.best_model in ("xgb", "catboost"):
                if self.best_model == "xgb":
                    scores = model.get_booster().get_fscore()
                else:
                    scores = dict(zip(self.feature_names, model.get_feature_importance()))
                pairs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                total = sum(v for _, v in pairs) or 1
                return [{"feature": k, "importance": round(v / total, 4)} for k, v in pairs[:10]]
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
                        df_tx:    pd.DataFrame,
                        df_macro: Optional[pd.DataFrame],
                        df_sent:  Optional[pd.DataFrame]) -> pd.DataFrame:
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
        exclude = {"ds", "y", "y_log", "ym"}
        return [c for c in df.columns if c not in exclude and df[c].dtype != object]

    # ── Fast Training (area-level, LightGBM only) ──────────────────────

    def _train_lgbm_fast(self, train: pd.DataFrame, val: pd.DataFrame):
        """Reduced-cost LightGBM fit for area-level forecasts.
        Fewer rounds + tighter early-stopping to stay under 2s per area."""
        lgb   = _import_lgbm()
        feats = self._feature_cols(train)
        if not self.feature_names:
            self.feature_names = feats
        X_tr,  y_tr_log  = train[feats].fillna(0), train["y_log"]
        X_val, y_val_orig = val[feats].fillna(0),   val["y"]
        dtrain = lgb.Dataset(X_tr, label=y_tr_log)
        dval   = lgb.Dataset(X_val, label=val["y_log"], reference=dtrain)
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
        y_pred = np.expm1(m.predict(X_val.values)).clip(min=0)
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
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.1,
            seasonality_mode="additive",
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
        X_tr,  y_tr_log   = train[feats].fillna(0), train["y_log"]
        X_val, y_val_orig  = val[feats].fillna(0),   val["y"]
        dtrain = lgb.Dataset(X_tr, label=y_tr_log)
        dval   = lgb.Dataset(X_val, label=val["y_log"], reference=dtrain)
        # Stronger regularisation for ~50 training rows
        params = dict(
            objective="regression",
            metric="rmse",
            num_leaves=8,
            learning_rate=0.05,
            min_data_in_leaf=5,
            feature_fraction=0.8,
            bagging_fraction=0.8,
            bagging_freq=3,
            lambda_l1=1.0,
            lambda_l2=5.0,
            verbosity=-1,
            force_col_wise=True,
        )
        m = lgb.train(
            params, dtrain, num_boost_round=400,
            valid_sets=[dval],
            callbacks=[lgb.early_stopping(30, verbose=False),
                       lgb.log_evaluation(-1)],
        )
        y_pred = np.expm1(m.predict(X_val.values)).clip(min=0)
        self.models["lgbm"]  = m
        self.metrics["lgbm"] = self._compute_metrics(y_val_orig.values, y_pred)

    def _train_xgb(self, train: pd.DataFrame, val: pd.DataFrame):
        xgb   = _import_xgb()
        feats = self._feature_cols(train)
        if not self.feature_names:
            self.feature_names = feats
        X_tr,  y_tr_log   = train[feats].fillna(0), train["y_log"]
        X_val, y_val_orig  = val[feats].fillna(0),   val["y"]
        m = xgb.XGBRegressor(
            n_estimators=400,
            learning_rate=0.03,
            max_depth=2,
            min_child_weight=5,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=1.0,
            reg_lambda=5.0,
            verbosity=0,
            early_stopping_rounds=30,
        )
        m.fit(X_tr, y_tr_log, eval_set=[(X_val, val["y_log"])], verbose=False)
        y_pred = np.expm1(m.predict(X_val)).clip(min=0)
        self.models["xgb"]  = m
        self.metrics["xgb"] = self._compute_metrics(y_val_orig.values, y_pred)

    def _train_catboost(self, train: pd.DataFrame, val: pd.DataFrame):
        CatBoostRegressor = _import_catboost()
        feats = self._feature_cols(train)
        if not self.feature_names:
            self.feature_names = feats
        X_tr,  y_tr_log   = train[feats].fillna(0), train["y_log"]
        X_val, y_val_orig  = val[feats].fillna(0),   val["y"]
        m = CatBoostRegressor(
            iterations=400,
            learning_rate=0.03,
            depth=3,
            l2_leaf_reg=10,
            min_data_in_leaf=5,
            loss_function="RMSE",
            eval_metric="RMSE",
            verbose=False,
            early_stopping_rounds=30,
        )
        m.fit(X_tr, y_tr_log, eval_set=(X_val, val["y_log"]))
        y_pred = np.expm1(m.predict(X_val)).clip(min=0)
        self.models["catboost"]  = m
        self.metrics["catboost"] = self._compute_metrics(y_val_orig.values, y_pred)

    # ── CV-only Training (stateless helpers) ──────────────────────────

    def _fit_prophet_cv(self, train, val):
        Prophet = _import_prophet()
        m = Prophet(yearly_seasonality=False, weekly_seasonality=False,
                    daily_seasonality=False, changepoint_prior_scale=0.1)
        m.fit(train[["ds", "y"]].copy())
        future = m.make_future_dataframe(periods=len(val), freq="MS")
        fc     = m.predict(future)
        y_pred = fc.tail(len(val))["yhat"].clip(lower=0).values
        return m, self._compute_metrics(val["y"].values, y_pred)

    def _fit_lgbm_cv(self, train, val):
        lgb   = _import_lgbm()
        feats = self._feature_cols(train)
        X_tr,  y_tr   = train[feats].fillna(0), train["y_log"]
        X_val, y_val  = val[feats].fillna(0),   val["y"]
        dtrain = lgb.Dataset(X_tr, label=y_tr)
        dval   = lgb.Dataset(X_val, label=val["y_log"], reference=dtrain)
        params = dict(objective="regression", metric="rmse", num_leaves=8,
                      learning_rate=0.05, min_data_in_leaf=5,
                      lambda_l1=1.0, lambda_l2=5.0,
                      verbosity=-1, force_col_wise=True)
        m = lgb.train(params, dtrain, num_boost_round=400,
                      valid_sets=[dval],
                      callbacks=[lgb.early_stopping(30, verbose=False),
                                 lgb.log_evaluation(-1)])
        y_pred = np.expm1(m.predict(X_val.values)).clip(min=0)
        return m, self._compute_metrics(y_val.values, y_pred)

    def _fit_xgb_cv(self, train, val):
        xgb   = _import_xgb()
        feats = self._feature_cols(train)
        X_tr,  y_tr   = train[feats].fillna(0), train["y_log"]
        X_val, y_val  = val[feats].fillna(0),   val["y"]
        m = xgb.XGBRegressor(n_estimators=400, learning_rate=0.03, max_depth=2,
                              min_child_weight=5, reg_alpha=1.0, reg_lambda=5.0,
                              verbosity=0, early_stopping_rounds=30)
        m.fit(X_tr, y_tr, eval_set=[(X_val, val["y_log"])], verbose=False)
        y_pred = np.expm1(m.predict(X_val)).clip(min=0)
        return m, self._compute_metrics(y_val.values, y_pred)

    def _fit_catboost_cv(self, train, val):
        CatBoostRegressor = _import_catboost()
        feats = self._feature_cols(train)
        X_tr,  y_tr   = train[feats].fillna(0), train["y_log"]
        X_val, y_val  = val[feats].fillna(0),   val["y"]
        m = CatBoostRegressor(iterations=400, learning_rate=0.03, depth=3,
                              l2_leaf_reg=10, min_data_in_leaf=5,
                              loss_function="RMSE", verbose=False,
                              early_stopping_rounds=30)
        m.fit(X_tr, y_tr, eval_set=(X_val, val["y_log"]))
        y_pred = np.expm1(m.predict(X_val)).clip(min=0)
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

                # Carry forward macro / sentiment / interaction
                for f in feats:
                    if f not in row:
                        row[f] = float(last_row.get(f, 0) or 0)

                # Re-compute interaction with carried-forward rate
                if "rate_x_lag12" in feats:
                    row["rate_x_lag12"] = row.get("uae_base_rate_pct", 0) * row["lag12"]

                X_fut = pd.DataFrame([row])[feats].fillna(0)

                if model_name == "lgbm":
                    pred_log = float(model.predict(X_fut.values)[0])
                else:
                    pred_log = float(model.predict(X_fut)[0])

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
