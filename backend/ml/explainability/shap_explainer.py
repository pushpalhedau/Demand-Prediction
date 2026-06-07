"""
SHAP Explainer — wraps any tree model with SHAP explanation.
Returns top N drivers with direction and magnitude.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class SHAPExplainer:

    def __init__(self, model, feature_names: List[str]):
        self.model = model
        self.feature_names = feature_names
        self._explainer = None

    def _get_explainer(self):
        if self._explainer is None:
            try:
                import shap
                self._explainer = shap.TreeExplainer(self.model)
            except Exception as exc:
                log.warning("SHAP explainer init failed: %s", exc)
        return self._explainer

    def explain_prediction(self, X: pd.DataFrame, top_n: int = 8) -> List[Dict]:
        explainer = self._get_explainer()
        if explainer is None:
            return self._fallback_importance(top_n)
        try:
            import shap
            X_sample = X.fillna(0)
            # Cap at 500 rows — SHAP is O(n×features×trees), 10k+ rows times out (A18)
            if len(X_sample) > 500:
                X_sample = X_sample.sample(500, random_state=42)
            X_arr = X_sample.values
            shap_values = explainer.shap_values(X_arr)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            mean_shap = np.abs(shap_values).mean(axis=0) if shap_values.ndim > 1 else np.abs(shap_values)
            pairs = sorted(zip(self.feature_names, mean_shap), key=lambda x: x[1], reverse=True)[:top_n]
            total = sum(v for _, v in pairs) or 1
            results = []
            for name, importance in pairs:
                if shap_values.ndim > 1:
                    direction_vals = shap_values[:, self.feature_names.index(name)]
                    # Median is more robust than mean for skewed SHAP distributions
                    direction = "positive" if float(np.median(direction_vals)) > 0 else "negative"
                else:
                    direction = "positive" if float(np.median(shap_values)) > 0 else "negative"
                results.append({
                    "feature":        name,
                    "importance":     round(float(importance), 4),
                    "importance_pct": round(float(importance / total) * 100, 1),
                    "direction":      direction,
                    "label":          self._human_label(name, direction),
                })
            return results
        except Exception as exc:
            log.warning("SHAP explain failed: %s", exc)
            return self._fallback_importance(top_n)

    def _fallback_importance(self, top_n: int) -> List[Dict]:
        try:
            if hasattr(self.model, "feature_importance"):
                imp = self.model.feature_importance(importance_type="gain")
            elif hasattr(self.model, "feature_importances_"):
                imp = self.model.feature_importances_
            else:
                return []
            total = sum(imp) or 1
            pairs = sorted(zip(self.feature_names, imp), key=lambda x: x[1], reverse=True)[:top_n]
            return [{"feature": n, "importance": round(float(v), 4),
                     "importance_pct": round(float(v / total) * 100, 1),
                     "direction": "positive",
                     "label": self._human_label(n, "positive")} for n, v in pairs]
        except Exception:
            return []

    @staticmethod
    def _human_label(feature: str, direction: str) -> str:
        labels = {
            "lag1":                        "Last month's demand",
            "lag2":                        "2-month demand lag",
            "lag3":                        "3-month demand trend",
            "lag6":                        "6-month demand lag",
            "lag9":                        "9-month demand lag",
            "lag12":                       "Year-ago demand",
            "roll3":                       "3-month moving average",
            "roll6":                       "6-month moving average",
            "roll12":                      "12-month moving average",
            "volatility":                  "Recent market volatility",
            "yoy_log_diff":                "YoY growth rate",
            "yoy_accel":                   "Growth acceleration",
            "rate_x_lag12":                "Rate × year-ago demand",
            "avg_mortgage_rate_pct":       "Mortgage rate",
            "uae_base_rate_pct":           "Central bank rate",
            "month":                       "Seasonality",
            "trend":                       "Long-term trend",
            "year":                        "Annual trend",
            "real_estate_sentiment_index": "Market sentiment",
            "buyer_confidence_index":      "Buyer confidence",
        }
        base = labels.get(feature, feature.replace("_", " ").title())
        arrow = " ↑" if direction == "positive" else " ↓"
        return base + arrow
