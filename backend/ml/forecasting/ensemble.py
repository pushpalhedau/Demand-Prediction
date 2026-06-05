"""
Forecast Ensemble — trains multiple models and selects the best by validation RMSE.
Supports: Prophet, LightGBM, XGBoost, CatBoost, SARIMA.
"""
from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

import numpy as np
import pandas as pd
import joblib

warnings.filterwarnings("ignore")
log = logging.getLogger(__name__)

# Lazy imports — only loaded when first used
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

def _import_sarima():
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    return SARIMAX


MODELS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models"


class ForecastEnsemble:
    """
    Multi-model forecast ensemble for UAE real estate demand.

    Usage:
        fe = ForecastEnsemble()
        fe.fit(df_transactions, df_macro)
        result = fe.predict(horizon_days=90)
    """

    MODEL_NAMES = ["prophet", "lgbm", "xgb", "catboost"]

    def __init__(self, target: str = "units"):
        self.target = target       # "units" | "revenue"
        self.models: Dict[str, object] = {}
        self.metrics: Dict[str, Dict] = {}
        self.best_model: str = "lgbm"
        self.feature_names: List[str] = []
        self._daily_df: Optional[pd.DataFrame] = None
        self._is_fitted = False

    # ── Public API ─────────────────────────────────────────────────────

    def fit(self, df_transactions: pd.DataFrame,
            df_macro: Optional[pd.DataFrame] = None,
            df_sentiment: Optional[pd.DataFrame] = None) -> "ForecastEnsemble":
        log.info("ForecastEnsemble.fit(target=%s)", self.target)
        self._daily_df = self._prepare_series(df_transactions, df_macro, df_sentiment)
        train, val = self._train_val_split(self._daily_df)
        for name in self.MODEL_NAMES:
            try:
                self._train_model(name, train, val)
            except Exception as exc:
                log.warning("Model %s failed: %s", name, exc)
        self.best_model = min(self.metrics, key=lambda m: self.metrics[m].get("mape", 999))
        log.info("Best model: %s  MAPE=%.2f%%", self.best_model,
                 self.metrics[self.best_model].get("mape", 0))
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

    def get_feature_importance(self) -> List[Dict]:
        model = self.models.get(self.best_model)
        if model is None:
            return []
        try:
            if self.best_model == "lgbm":
                import lightgbm as lgb
                imp = model.feature_importance(importance_type="gain")
                names = model.feature_name()
                pairs = sorted(zip(names, imp), key=lambda x: x[1], reverse=True)
                return [{"feature": n, "importance": float(v)} for n, v in pairs[:10]]
            if self.best_model in ("xgb", "catboost"):
                scores = model.get_booster().get_fscore() if self.best_model == "xgb" else \
                         dict(zip(self.feature_names, model.get_feature_importance()))
                pairs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                total = sum(v for _, v in pairs) or 1
                return [{"feature": k, "importance": round(v / total, 4)} for k, v in pairs[:10]]
        except Exception:
            pass
        return []

    # ── Data Preparation ───────────────────────────────────────────────

    def _prepare_series(self, df_tx: pd.DataFrame,
                        df_macro: Optional[pd.DataFrame],
                        df_sent: Optional[pd.DataFrame]) -> pd.DataFrame:
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

        # Lag + rolling features
        agg["lag1"]  = agg["y"].shift(1)
        agg["lag3"]  = agg["y"].shift(3)
        agg["lag6"]  = agg["y"].shift(6)
        agg["lag12"] = agg["y"].shift(12)
        agg["roll3"] = agg["y"].shift(1).rolling(3).mean()
        agg["roll6"] = agg["y"].shift(1).rolling(6).mean()

        # Calendar
        agg["month"]   = agg["ds"].dt.month
        agg["quarter"] = agg["ds"].dt.quarter
        agg["year"]    = agg["ds"].dt.year
        agg["trend"]   = np.arange(len(agg))

        # Macro features
        if df_macro is not None and not df_macro.empty:
            macro_m = df_macro.copy()
            macro_m["ym"] = pd.to_datetime(macro_m["date"]).dt.to_period("M")
            for col in ["uae_base_rate_pct", "avg_mortgage_rate_pct"]:
                if col in macro_m.columns:
                    mapping = macro_m.set_index("ym")[col]
                    agg[col] = agg["ym"].map(mapping).ffill().bfill()

        # Sentiment
        if df_sent is not None and not df_sent.empty:
            sent_m = df_sent.copy()
            sent_m["ym"] = pd.to_datetime(sent_m["date"]).dt.to_period("M")
            for col in ["real_estate_sentiment_index", "buyer_confidence_index"]:
                if col in sent_m.columns:
                    mapping = sent_m.set_index("ym")[col]
                    agg[col] = agg["ym"].map(mapping).ffill().bfill()

        agg = agg.dropna(subset=["lag1"]).reset_index(drop=True)
        return agg

    def _train_val_split(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        n = len(df)
        split = int(n * 0.8)
        return df.iloc[:split].copy(), df.iloc[split:].copy()

    def _feature_cols(self, df: pd.DataFrame) -> List[str]:
        exclude = {"ds", "y", "ym"}
        cols = [c for c in df.columns if c not in exclude and df[c].dtype != object]
        self.feature_names = cols
        return cols

    # ── Model Training ─────────────────────────────────────────────────

    def _train_model(self, name: str, train: pd.DataFrame, val: pd.DataFrame):
        log.info("Training %s …", name)
        if name == "prophet":
            self._train_prophet(train, val)
        elif name == "lgbm":
            self._train_lgbm(train, val)
        elif name == "xgb":
            self._train_xgb(train, val)
        elif name == "catboost":
            self._train_catboost(train, val)

    def _train_prophet(self, train: pd.DataFrame, val: pd.DataFrame):
        Prophet = _import_prophet()
        df_p = train[["ds", "y"]].copy()
        m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False,
                    changepoint_prior_scale=0.05, seasonality_prior_scale=10)
        m.fit(df_p)
        future = m.make_future_dataframe(periods=len(val), freq="MS")
        fc = m.predict(future)
        y_pred = fc.tail(len(val))["yhat"].values
        y_true = val["y"].values
        self.models["prophet"] = m
        self.metrics["prophet"] = self._compute_metrics(y_true, y_pred)

    def _train_lgbm(self, train: pd.DataFrame, val: pd.DataFrame):
        lgb = _import_lgbm()
        feats = self._feature_cols(train)
        X_tr, y_tr = train[feats].fillna(0), train["y"]
        X_val, y_val = val[feats].fillna(0), val["y"]
        dtrain = lgb.Dataset(X_tr, label=y_tr)
        dval   = lgb.Dataset(X_val, label=y_val, reference=dtrain)
        params = dict(objective="regression", metric="rmse", num_leaves=31,
                      learning_rate=0.05, n_estimators=500, verbosity=-1,
                      force_col_wise=True)
        m = lgb.train(params, dtrain, num_boost_round=500,
                      valid_sets=[dval],
                      callbacks=[lgb.early_stopping(50, verbose=False),
                                  lgb.log_evaluation(-1)])
        y_pred = m.predict(X_val.values)
        self.models["lgbm"] = m
        self.metrics["lgbm"] = self._compute_metrics(y_val.values, y_pred)

    def _train_xgb(self, train: pd.DataFrame, val: pd.DataFrame):
        xgb = _import_xgb()
        feats = self._feature_cols(train)
        X_tr, y_tr = train[feats].fillna(0), train["y"]
        X_val, y_val = val[feats].fillna(0), val["y"]
        m = xgb.XGBRegressor(n_estimators=500, learning_rate=0.05,
                              max_depth=5, subsample=0.8,
                              colsample_bytree=0.8, verbosity=0,
                              early_stopping_rounds=50)
        m.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
        y_pred = m.predict(X_val)
        self.models["xgb"] = m
        self.metrics["xgb"] = self._compute_metrics(y_val.values, y_pred)

    def _train_catboost(self, train: pd.DataFrame, val: pd.DataFrame):
        CatBoostRegressor = _import_catboost()
        feats = self._feature_cols(train)
        X_tr, y_tr = train[feats].fillna(0), train["y"]
        X_val, y_val = val[feats].fillna(0), val["y"]
        m = CatBoostRegressor(iterations=500, learning_rate=0.05,
                              depth=6, loss_function="RMSE",
                              eval_metric="RMSE", verbose=False,
                              early_stopping_rounds=50)
        m.fit(X_tr, y_tr, eval_set=(X_val, y_val))
        y_pred = m.predict(X_val)
        self.models["catboost"] = m
        self.metrics["catboost"] = self._compute_metrics(y_val.values, y_pred)

    # ── Forecast Generation ────────────────────────────────────────────

    def _generate_forecast(self, model_name: str, horizon_days: int) -> Dict:
        model = self.models[model_name]
        hist = self._daily_df.copy()

        if model_name == "prophet":
            future = model.make_future_dataframe(periods=horizon_days // 30 + 1, freq="MS")
            fc = model.predict(future)
            fc_future = fc[fc["ds"] > hist["ds"].max()]
            dates  = fc_future["ds"].tolist()
            preds  = fc_future["yhat"].clip(lower=0).tolist()
            lower  = fc_future["yhat_lower"].clip(lower=0).tolist()
            upper  = fc_future["yhat_upper"].clip(lower=0).tolist()
        else:
            feats = self._feature_cols(hist)
            last_row = hist[feats].iloc[-1:].fillna(0)
            last_y   = hist["y"].iloc[-1]
            last_ds  = hist["ds"].iloc[-1]
            n_months = max(1, horizon_days // 30)
            future_rows = []
            cur_y = last_y
            for i in range(1, n_months + 1):
                row = last_row.copy()
                for f in feats:
                    if "lag" in f:
                        row[f] = cur_y
                    if "roll" in f:
                        row[f] = cur_y
                    if f == "trend":
                        row[f] = hist["trend"].iloc[-1] + i
                    if f == "month":
                        row[f] = ((last_ds.month + i - 1) % 12) + 1
                future_rows.append(row)
            X_fut = pd.concat(future_rows, ignore_index=True).fillna(0)
            if model_name == "lgbm":
                preds = model.predict(X_fut.values).clip(min=0).tolist()
            else:
                preds = model.predict(X_fut).clip(min=0).tolist()
            dates = [last_ds + pd.DateOffset(months=i) for i in range(1, n_months + 1)]
            std   = float(np.std(hist["y"].values[-12:]))
            lower = [max(0, p - 1.96 * std) for p in preds]
            upper = [p + 1.96 * std for p in preds]

        # Historical tail (last 24 months)
        hist_tail = hist.tail(24)
        return {
            "model": model_name,
            "metrics": self.metrics.get(model_name, {}),
            "historical": {
                "dates":  [d.isoformat() for d in hist_tail["ds"].tolist()],
                "values": hist_tail["y"].tolist(),
            },
            "forecast": {
                "dates":  [d.isoformat() if hasattr(d, "isoformat") else str(d) for d in dates],
                "values": [round(v, 1) for v in preds],
                "lower":  [round(v, 1) for v in lower],
                "upper":  [round(v, 1) for v in upper],
            },
            "feature_importance": self.get_feature_importance(),
        }

    # ── Metrics ────────────────────────────────────────────────────────

    @staticmethod
    def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
        y_true = np.array(y_true, dtype=float)
        y_pred = np.array(y_pred, dtype=float)
        rmse   = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        mae    = float(np.mean(np.abs(y_true - y_pred)))
        mask   = y_true != 0
        mape   = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100) if mask.any() else 999.0
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2     = float(1 - ss_res / ss_tot) if ss_tot != 0 else 0.0
        return {"rmse": round(rmse, 2), "mae": round(mae, 2),
                "mape": round(mape, 2), "r2": round(r2, 4)}

    # ── Persistence ────────────────────────────────────────────────────

    def _save_cache(self):
        try:
            MODELS_DIR.mkdir(exist_ok=True)
            for name, m in self.models.items():
                joblib.dump(m, MODELS_DIR / f"forecast_{self.target}_{name}.pkl")
            with open(MODELS_DIR / f"forecast_{self.target}_meta.json", "w") as f:
                json.dump({"best_model": self.best_model, "metrics": self.metrics,
                           "feature_names": self.feature_names}, f)
            if self._daily_df is not None:
                self._daily_df.to_parquet(MODELS_DIR / f"forecast_{self.target}_data.parquet", index=False)
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
            self.best_model   = meta["best_model"]
            self.metrics      = meta["metrics"]
            self.feature_names = meta["feature_names"]
            for name in self.MODEL_NAMES:
                p = MODELS_DIR / f"forecast_{self.target}_{name}.pkl"
                if p.exists():
                    self.models[name] = joblib.load(p)
            if data_path.exists():
                self._daily_df = pd.read_parquet(data_path)
            self._is_fitted = bool(self.models)
        except Exception as exc:
            log.warning("Could not load cache: %s", exc)
