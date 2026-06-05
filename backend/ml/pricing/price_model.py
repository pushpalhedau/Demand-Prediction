"""
Price Intelligence Model — predicts optimal price per sqft and analyses price elasticity.
Uses LightGBM Regressor trained on DLD transaction data.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split

log = logging.getLogger(__name__)


class PriceModel:

    def __init__(self):
        self.model = None
        self.encoders: Dict[str, LabelEncoder] = {}
        self.feature_names: List[str] = []
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

        cat_cols = ["area_name", "property_type", "zone", "bedrooms"]
        for c in cat_cols:
            if c in df.columns:
                enc = LabelEncoder()
                df[c + "_enc"] = enc.fit_transform(df[c].astype(str))
                self.encoders[c] = enc

        num_cols = ["area_sqft", "year", "month", "quarter", "is_off_plan"]
        feats = [c + "_enc" for c in cat_cols if c in df.columns] + \
                [c for c in num_cols if c in df.columns]

        df["is_off_plan"] = df["is_off_plan"].astype(int) if "is_off_plan" in df.columns else 0
        X = df[feats].fillna(0)
        y = df["price_per_sqft_aed"].clip(upper=df["price_per_sqft_aed"].quantile(0.99))

        X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        dtrain = lgb.Dataset(X_tr, label=y_tr)
        dval   = lgb.Dataset(X_val, label=y_val, reference=dtrain)

        params = dict(objective="regression", metric="rmse", num_leaves=63,
                      learning_rate=0.05, verbosity=-1, force_col_wise=True)
        self.model = lgb.train(params, dtrain, num_boost_round=500,
                               valid_sets=[dval],
                               callbacks=[lgb.early_stopping(50, verbose=False),
                                           lgb.log_evaluation(-1)])
        self.feature_names = feats
        self._is_fitted = True
        log.info("PriceModel fitted on %d rows.", len(df))
        return self

    def predict_price(self, area: str, property_type: str, bedrooms: int,
                       area_sqft: float, is_off_plan: bool = False,
                       year: int = 2024, month: int = 6) -> Dict:
        if not self._is_fitted or self.model is None:
            return self._fallback_price(area, property_type, bedrooms)

        row = {}
        for c in ["area_name", "property_type", "bedrooms"]:
            if c in self.encoders:
                val = {"area_name": area, "property_type": property_type,
                       "bedrooms": str(bedrooms)}.get(c, "Unknown")
                try:
                    row[c + "_enc"] = self.encoders[c].transform([str(val)])[0]
                except Exception:
                    row[c + "_enc"] = 0
        row.update({"area_sqft": area_sqft, "year": year, "month": month,
                    "quarter": (month - 1) // 3 + 1, "is_off_plan": int(is_off_plan)})
        X = pd.DataFrame([{f: row.get(f, 0) for f in self.feature_names}])
        price_psf = float(self.model.predict(X)[0])
        price_psf = max(500, price_psf)
        total_price = price_psf * area_sqft
        return {
            "recommended_price_per_sqft_aed": round(price_psf, 0),
            "recommended_total_price_aed": round(total_price, 0),
            "confidence": 0.82,
            "premium_ceiling_aed": round(price_psf * 1.15 * area_sqft, 0),
            "discount_floor_aed":  round(price_psf * 0.90 * area_sqft, 0),
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
                    "area": area,
                    "elasticity": round(slope, 3),
                    "r_squared":  round(r ** 2, 3),
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

    @staticmethod
    def _fallback_price(area: str, property_type: str, bedrooms: int) -> Dict:
        base_map = {"Apartment": 1400, "Villa": 1100, "Townhouse": 1000,
                    "Penthouse": 2500, "Studio": 1600, "Commercial": 1800}
        base = base_map.get(property_type, 1300)
        sqft = 800 + bedrooms * 300
        return {
            "recommended_price_per_sqft_aed": base,
            "recommended_total_price_aed": round(base * sqft, 0),
            "confidence": 0.60,
            "premium_ceiling_aed": round(base * 1.15 * sqft, 0),
            "discount_floor_aed":  round(base * 0.90 * sqft, 0),
        }
