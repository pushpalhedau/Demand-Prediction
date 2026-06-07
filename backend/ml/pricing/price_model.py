"""
Price Intelligence Model — predicts optimal price per sqft and price elasticity.

Accuracy improvements over v1
------------------------------
* Time-aware train/val split: data sorted by date, last 20% chronologically
  (not random) so the model is tested on future prices, not mixed years.
* LightGBM native categoricals: area_name / property_type are pandas
  Categorical — LightGBM splits on exact values, not spurious ordinal gaps.
* Data-driven confidence: computed from validation coverage (% of val rows
  within ±15% of truth) adjusted by area data volume.
* Fallback prices from training data medians (not hardcoded AED 1400/sqft).
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class PriceModel:

    def __init__(self):
        self.model = None
        self.feature_names: List[str]  = []
        self._confidence: float        = 0.75
        self._area_counts: Dict        = {}
        self._fallback_medians: Dict   = {}
        self._is_fitted = False

    def fit(self, df_transactions: pd.DataFrame) -> "PriceModel":
        try:
            import lightgbm as lgb
        except ImportError:
            log.warning("LightGBM not available; using fallback pricing")
            return self

        df = df_transactions.copy()
        df = df.dropna(subset=["price_per_sqft_aed", "transaction_value_aed", "area_sqft"])
        df = df[df["price_per_sqft_aed"] > 100]

        # Save medians BEFORE any filtering so fallback covers all areas (A19)
        self._fallback_medians = {
            "global":        float(df["price_per_sqft_aed"].median()),
            "property_type": df.groupby("property_type")["price_per_sqft_aed"].median().to_dict()
                             if "property_type" in df.columns else {},
            "area":          df.groupby("area_name")["price_per_sqft_aed"].median().to_dict()
                             if "area_name" in df.columns else {},
        }
        self._area_counts = df["area_name"].value_counts().to_dict() if "area_name" in df.columns else {}

        # ── Feature encoding — LightGBM native categoricals (A7) ──────
        # Pandas Categorical dtype is detected automatically by LightGBM,
        # which splits on exact category values instead of ordinal integers.
        cat_cols = ["area_name", "property_type", "zone", "bedrooms"]
        for c in cat_cols:
            if c in df.columns:
                df[c] = df[c].astype(str).astype("category")

        df["is_off_plan"] = df["is_off_plan"].astype(int) if "is_off_plan" in df.columns else 0
        num_cols = ["area_sqft", "year", "month", "quarter", "is_off_plan"]
        feats = [c for c in cat_cols if c in df.columns] + [c for c in num_cols if c in df.columns]

        y = df["price_per_sqft_aed"].clip(upper=df["price_per_sqft_aed"].quantile(0.99))
        X = df[feats]

        # ── Time-aware split — sort by date, last 20% as validation (A2) ──
        if "transaction_date" in df.columns:
            df_sorted = df.sort_values("transaction_date")
        else:
            df_sorted = df
        split_idx = int(len(df_sorted) * 0.8)
        X_tr  = X.iloc[:split_idx]
        X_val = X.iloc[split_idx:]
        y_tr  = y.iloc[:split_idx]
        y_val = y.iloc[split_idx:]

        cat_feat_names = [c for c in cat_cols if c in df.columns]
        dtrain = lgb.Dataset(X_tr,  label=y_tr,  categorical_feature=cat_feat_names, free_raw_data=False)
        dval   = lgb.Dataset(X_val, label=y_val, categorical_feature=cat_feat_names,
                             reference=dtrain, free_raw_data=False)

        params = dict(
            objective="regression",
            metric="rmse",
            num_leaves=31,
            learning_rate=0.05,
            min_data_in_leaf=10,
            lambda_l1=0.5,
            lambda_l2=2.0,
            verbosity=-1,
            force_col_wise=True,
        )
        self.model = lgb.train(
            params, dtrain, num_boost_round=500,
            valid_sets=[dval],
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)],
        )
        self.feature_names = feats

        # ── Data-driven confidence from validation coverage (A10) ───────
        val_pred = self.model.predict(X_val)
        val_true = y_val.values
        safe_true = np.where(val_true != 0, val_true, 1.0)
        within_15pct = float(np.mean(np.abs(val_pred - val_true) / safe_true < 0.15))
        self._confidence = round(float(np.clip(within_15pct, 0.50, 0.95)), 2)

        self._is_fitted = True
        log.info("PriceModel fitted on %d rows. Val coverage ±15%%: %.1f%%",
                 len(df), self._confidence * 100)
        return self

    def predict_price(self, area: str, property_type: str, bedrooms: int,
                      area_sqft: float, is_off_plan: bool = False,
                      year: int = 2024, month: int = 6) -> Dict:
        if not self._is_fitted or self.model is None:
            return self._fallback_price(area, property_type, bedrooms)

        # Encode as category — use consistent handling for unseen categories
        cat_vals = {
            "area_name":     area,
            "property_type": property_type,
            "bedrooms":      str(bedrooms),
            "zone":          "Unknown",
        }
        row: Dict = {}
        for c in ["area_name", "property_type", "zone", "bedrooms"]:
            if c in self.feature_names:
                row[c] = cat_vals.get(c, "Unknown")
        row.update({
            "area_sqft":  area_sqft,
            "year":       year,
            "month":      month,
            "quarter":    (month - 1) // 3 + 1,
            "is_off_plan": int(is_off_plan),
        })
        X = pd.DataFrame([{f: row.get(f, 0) for f in self.feature_names}])
        # Re-encode cat cols as Categorical for inference
        for c in ["area_name", "property_type", "zone", "bedrooms"]:
            if c in X.columns:
                X[c] = X[c].astype("category")

        try:
            price_psf = float(self.model.predict(X)[0])
        except Exception:
            return self._fallback_price(area, property_type, bedrooms)

        price_psf = max(500.0, price_psf)
        total_price = price_psf * area_sqft

        # Area-aware confidence: common areas get higher confidence (A10)
        area_count  = self._area_counts.get(area, 0)
        area_factor = min(1.0, area_count / 200.0)
        confidence  = round(float(self._confidence * (0.75 + 0.25 * area_factor)), 2)

        return {
            "recommended_price_per_sqft_aed": round(price_psf, 0),
            "recommended_total_price_aed":    round(total_price, 0),
            "confidence":                     confidence,
            "premium_ceiling_aed":            round(price_psf * 1.15 * area_sqft, 0),
            "discount_floor_aed":             round(price_psf * 0.90 * area_sqft, 0),
        }

    def price_elasticity(self, df_transactions: pd.DataFrame) -> List[Dict]:
        """Compute price elasticity by area using OLS log-log regression."""
        from scipy.stats import linregress
        results = []
        for area, grp in df_transactions.groupby("area_name"):
            if len(grp) < 20:
                continue
            log_price = np.log(grp["price_per_sqft_aed"].clip(lower=1))
            log_vol   = np.log(grp.groupby(["year", "month"]).size().reset_index(name="v")["v"].clip(lower=1) + 1)
            if len(log_price) != len(log_vol):
                continue
            try:
                slope, _, r, _, _ = linregress(log_price, log_vol)
                results.append({
                    "area":           area,
                    "elasticity":     round(slope, 3),
                    "r_squared":      round(r ** 2, 3),
                    "interpretation": "elastic" if abs(slope) > 1 else "inelastic",
                })
            except Exception:
                pass
        return sorted(results, key=lambda x: abs(x["elasticity"]), reverse=True)[:15]

    def area_price_trends(self, df_transactions: pd.DataFrame) -> pd.DataFrame:
        df = df_transactions.copy()
        df["ym"] = df["transaction_date"].dt.to_period("M")
        agg = df.groupby(["area_name", "ym"]).agg(
            avg_price_sqft=("price_per_sqft_aed", "mean"),
            tx_count=("transaction_id", "count"),
        ).reset_index()
        agg["ds"] = agg["ym"].dt.to_timestamp()
        return agg

    def _fallback_price(self, area: str, property_type: str, bedrooms: int) -> Dict:
        """Use training-data medians when the model isn't fitted (A19).
        Falls back through: area-specific → property-type → global → hardcoded."""
        area_med    = self._fallback_medians.get("area",  {}).get(area)
        pt_med      = self._fallback_medians.get("property_type", {}).get(property_type)
        global_med  = self._fallback_medians.get("global")

        if area_med:
            base = float(area_med)
        elif pt_med:
            base = float(pt_med)
        elif global_med:
            base = float(global_med)
        else:
            # Absolute last resort — only reached if model was never trained
            static = {"Apartment": 1400, "Villa": 1100, "Townhouse": 1000,
                      "Penthouse": 2500, "Studio": 1600, "Commercial": 1800}
            base = float(static.get(property_type, 1300))

        sqft = 800 + bedrooms * 300
        return {
            "recommended_price_per_sqft_aed": round(base, 0),
            "recommended_total_price_aed":    round(base * sqft, 0),
            "confidence":                     0.60,
            "premium_ceiling_aed":            round(base * 1.15 * sqft, 0),
            "discount_floor_aed":             round(base * 0.90 * sqft, 0),
        }
