"""
Sentiment Processor — transforms GDELT events and the sentiment index into
platform-ready signals that feed into forecasts, risk scores, and opportunity scoring.
"""
from __future__ import annotations

import logging
from typing import Dict, List
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class SentimentProcessor:

    def compute_signals(
        self,
        df_sentiment: pd.DataFrame,
        df_gdelt: pd.DataFrame,
    ) -> Dict:
        """Return a unified sentiment dict used across all tabs."""
        result = {
            "current_score":        50,
            "buyer_confidence":     50,
            "seller_confidence":    50,
            "media_score":          50,
            "trend":                "neutral",
            "trend_direction":      0,
            "monthly_history":      [],
            "gdelt_tone":           0,
            "positive_pct":         50,
            "negative_pct":         50,
            "alert":                None,
        }

        if not df_sentiment.empty and "real_estate_sentiment_index" in df_sentiment.columns:
            latest = df_sentiment.sort_values("date").iloc[-1]
            prev   = df_sentiment.sort_values("date").iloc[-3] if len(df_sentiment) >= 3 else latest
            result["current_score"]    = round(float(latest.get("real_estate_sentiment_index", 50)), 1)
            result["buyer_confidence"] = round(float(latest.get("buyer_confidence_index", 50)), 1)
            result["seller_confidence"]= round(float(latest.get("seller_confidence_index", 50)), 1)
            result["media_score"]      = round(float(latest.get("media_sentiment_score", 50)), 1)
            direction = result["current_score"] - float(prev.get("real_estate_sentiment_index", 50))
            result["trend_direction"]  = round(direction, 1)
            if direction > 3:
                result["trend"] = "improving"
            elif direction < -3:
                result["trend"] = "deteriorating"
            else:
                result["trend"] = "stable"

            history = df_sentiment.sort_values("date").tail(24)
            result["monthly_history"] = [
                {"date": str(row["date"])[:10],
                 "score": round(float(row.get("real_estate_sentiment_index", 50)), 1),
                 "buyer": round(float(row.get("buyer_confidence_index", 50)), 1)}
                for _, row in history.iterrows()
            ]

            # Alert if score drops below threshold
            if result["current_score"] < 45:
                result["alert"] = {
                    "severity": "critical",
                    "message": f"Sentiment index at {result['current_score']:.0f} — below critical threshold of 45.",
                }
            elif result["current_score"] < 55:
                result["alert"] = {
                    "severity": "warning",
                    "message": f"Sentiment declining to {result['current_score']:.0f} — monitor closely.",
                }

        if not df_gdelt.empty and "avg_tone" in df_gdelt.columns:
            latest_gdelt = df_gdelt.sort_values(["year", "month"]).tail(3)
            result["gdelt_tone"]    = round(float(latest_gdelt["avg_tone"].mean()), 2)
            result["positive_pct"]  = round(float(latest_gdelt["positive_pct"].mean()), 1)
            result["negative_pct"]  = round(float(latest_gdelt["negative_pct"].mean()), 1)

        return result

    def sentiment_as_features(self, df_sentiment: pd.DataFrame) -> pd.DataFrame:
        """Return monthly sentiment features for use as ML regressors."""
        if df_sentiment.empty:
            return pd.DataFrame()
        df = df_sentiment.copy()
        df["ym"] = pd.to_datetime(df["date"]).dt.to_period("M")
        df["sentiment_lag1"]    = df["real_estate_sentiment_index"].shift(1)
        df["sentiment_roll3"]   = df["real_estate_sentiment_index"].rolling(3).mean()
        df["confidence_change"] = df["buyer_confidence_index"].diff()
        return df[["ym", "real_estate_sentiment_index", "buyer_confidence_index",
                   "sentiment_lag1", "sentiment_roll3", "confidence_change"]]

    def gdelt_theme_breakdown(self, df_gdelt: pd.DataFrame, top_n: int = 10) -> List[Dict]:
        if df_gdelt.empty or "theme" not in df_gdelt.columns:
            return []
        latest = df_gdelt.sort_values(["year", "month"]).tail(12)
        by_theme = latest.groupby("theme").agg(
            total_events=("event_count", "sum"),
            avg_tone=("avg_tone", "mean"),
        ).reset_index()
        by_theme = by_theme.sort_values("total_events", ascending=False).head(top_n)
        return by_theme.to_dict("records")


sentiment_processor = SentimentProcessor()
