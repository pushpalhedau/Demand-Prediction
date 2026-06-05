"""
Forecast Ensemble — trains multiple models and selects the best by a
combined MAPE + R² score.

Key design choices for the UAE DLD dataset
-------------------------------------------
* The data has year-level step changes with very little within-year
  seasonality (CoV ≈ 2-3 % per year).  Month / quarter features are
  therefore omitted — they introduce fake oscillation and inflate RMSE.

* Core predictive signal: lag12 (same month last year) + trend.
  yoy_log_diff captures the decelerating growth rate (40 % → 5 %).

* All tree targets are log1p-transformed so models learn growth rates
  rather than absolute values.  expm1 converts predictions back.

* Validation uses the most recent 12 months (fixed window) so both
  training and validation sit in the same market regime, giving R² a
  fair chance to be positive.

* Multi-step forecast maintains a rolling log-scale history buffer so
  lag features update correctly at every future step.
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

# Fixed validation window — always validate on the most recent N months.
_VAL_MONTHS = 12


class ForecastEnsemble:
    MODEL_NAMES = ["prophet", "lgbm", "xgb", "catboost"]

    def __init__(self, target: str = "units"):
        self.target = target
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
        self.best_model = min(
            self.metrics,
            key=lambda m: self._model_score(self.metrics[m]),
        )
        log.info(
            "Best model: %s  MAPE=%.2f%%  R²=%.4f",
            self.best_model,
            self.metrics[self.best_model].get("mape", 0),
            self.metrics[self.best_model].get("r2", 0),
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
        r2_penalty = max(0.0, -r2) * 20.0
        r2_reward  = max(0.0,  r2) * 5.0
        return mape + r2_penalty - r2_reward

    # ── Data Preparation ───────────────────────────────────────────────

    def _prepare_series(self,
                        df_tx: pd.DataFrame,
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

        # Log-transform target — models learn proportional growth rates.
        agg["y_log"] = np.log1p(agg["y"])

        # Time index
        agg["trend"] = np.arange(len(agg))

        # Core lag features in log scale.
        # lag12 is the dominant predictor: same month last year captures
        # the year-level baseline without introducing fake seasonality.
        agg["lag1"]  = agg["y_log"].shift(1)
        agg["lag3"]  = agg["y_log"].shift(3)
        agg["lag6"]  = agg["y_log"].shift(6)
        agg["lag12"] = agg["y_log"].shift(12)

        # Smooth rolling mean over the last 6 months (log scale)
        agg["roll6"] = agg["y_log"].shift(1).rolling(6).mean()

        # YoY log-difference ≈ annualised growth rate.
        # Captures the decelerating growth (40% → 5%) in this dataset.
        agg["yoy_log_diff"] = (agg["lag1"] - agg["lag12"]).fillna(0).clip(-2.0, 2.0)

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

        # Drop only the first row (lag1 is NaN there).
        # Remaining NaN (early lag12/lag6 rows) → 0 so training starts
        # from month 1, giving the model more data to learn the trend.
        agg = agg.dropna(subset=["lag1"]).reset_index(drop=True)
        num_cols = agg.select_dtypes(include=[np.number]).columns.difference(["y", "y_log"])
        agg[num_cols] = agg[num_cols].fillna(0)

        return agg

    def _train_val_split(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        # Fixed 12-month validation window so train and val sit in the
        # same market regime — gives R² a fair chance to be positive.
        val_n = min(_VAL_MONTHS, max(6, len(df) // 6))
        split = len(df) - val_n
        return df.iloc[:split].copy(), df.iloc[split:].copy()

    def _feature_cols(self, df: pd.DataFrame) -> List[str]:
        """
        Return the core feature set. Month and quarter are intentionally
        excluded — this dataset has no real within-year seasonality and
        including them adds noise that hurts R².
        """
        exclude = {"ds", "y", "y_log", "ym"}
        return [c for c in df.columns if c not in exclude and df[c].dtype != object]

    # ── Model Training ─────────────────────────────────────────────────

    def _train_model(self, name: str, train: pd.DataFrame, val: pd.DataFrame):
        log.info("Training %s …", name)
        if   name == "prophet":  self._train_prophet(train, val)
        elif name == "lgbm":     self._train_lgbm(train, val)
        elif name == "xgb":      self._train_xgb(train, val)
        elif name == "catboost": self._train_catboost(train, val)

    def _train_prophet(self, train: pd.DataFrame, val: pd.DataFrame):
        Prophet = _import_prophet()
        df_p = train[["ds", "y"]].copy()
        m = Prophet(
            yearly_seasonality=False,   # no real seasonality in this data
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.1,
            seasonality_mode="additive",
        )
        m.fit(df_p)
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
        X_val, y_val_orig  = val[feats].fillna(0),  val["y"]
        dtrain = lgb.Dataset(X_tr, label=y_tr_log)
        dval   = lgb.Dataset(X_val, label=val["y_log"], reference=dtrain)
        params = dict(
            objective="regression",
            metric="rmse",
            num_leaves=16,
            learning_rate=0.05,
            min_data_in_leaf=3,
            feature_fraction=0.9,
            bagging_fraction=0.9,
            bagging_freq=3,
            lambda_l1=0.1,
            lambda_l2=2.0,
            verbosity=-1,
            force_col_wise=True,
        )
        m = lgb.train(
            params, dtrain, num_boost_round=300,
            valid_sets=[dval],
            callbacks=[lgb.early_stopping(40, verbose=False),
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
        X_val, y_val_orig  = val[feats].fillna(0),  val["y"]
        m = xgb.XGBRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=3,
            min_child_weight=3,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_alpha=0.1,
            reg_lambda=2.0,
            verbosity=0,
            early_stopping_rounds=40,
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
        X_val, y_val_orig  = val[feats].fillna(0),  val["y"]
        m = CatBoostRegressor(
            iterations=300,
            learning_rate=0.05,
            depth=4,
            l2_leaf_reg=3,
            min_data_in_leaf=3,
            loss_function="RMSE",
            eval_metric="RMSE",
            verbose=False,
            early_stopping_rounds=40,
        )
        m.fit(X_tr, y_tr_log, eval_set=(X_val, val["y_log"]))
        y_pred = np.expm1(m.predict(X_val)).clip(min=0)
        self.models["catboost"]  = m
        self.metrics["catboost"] = self._compute_metrics(y_val_orig.values, y_pred)

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
            feats   = self.feature_names or self._feature_cols(hist)
            last_ds = hist["ds"].iloc[-1]

            # Rolling log-scale history — updated after each prediction so
            # lag1/lag3/lag6/lag12 reflect the most recent forecast values.
            history_log: List[float] = list(hist["y_log"].values.astype(float))

            last_row = hist[feats].iloc[-1].to_dict()
            std_orig = float(np.std(hist["y"].values[-12:]))
            preds, dates, lower, upper = [], [], [], []

            for i in range(1, n_months + 1):
                n_h = len(history_log)
                row: Dict[str, float] = {}

                # Core lag features from the rolling buffer (log scale)
                row["lag1"]  = history_log[-1]
                row["lag3"]  = history_log[-3]  if n_h >= 3  else history_log[-1]
                row["lag6"]  = history_log[-6]  if n_h >= 6  else history_log[-1]
                row["lag12"] = history_log[-12] if n_h >= 12 else history_log[-1]

                row["roll6"] = float(np.mean(history_log[-6:])) if n_h >= 6 else history_log[-1]

                row["yoy_log_diff"] = float(
                    np.clip(row["lag1"] - row["lag12"], -2.0, 2.0)
                )
                row["trend"] = float(hist["trend"].iloc[-1] + i)

                # Carry forward macro / sentiment
                for f in feats:
                    if f not in row:
                        row[f] = float(last_row.get(f, 0) or 0)

                X_fut = pd.DataFrame([row])[feats].fillna(0)

                if model_name == "lgbm":
                    pred_log = float(model.predict(X_fut.values)[0])
                else:
                    pred_log = float(model.predict(X_fut)[0])

                pred_orig = max(0.0, float(np.expm1(pred_log)))
                preds.append(pred_orig)
                dates.append(last_ds + pd.DateOffset(months=i))
                lower.append(max(0.0, pred_orig - 1.96 * std_orig))
                upper.append(pred_orig + 1.96 * std_orig)
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
        return {
            "rmse": round(rmse, 2),
            "mae":  round(mae, 2),
            "mape": round(mape, 2),
            "r2":   round(r2, 4),
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
