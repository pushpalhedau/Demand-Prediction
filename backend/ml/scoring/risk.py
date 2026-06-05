"""
Risk Scorer — identifies early warning signals and market risk factors.
Output: risk_score (0-100), risk_factors list, severity (low/medium/high/critical).
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class RiskScorer:

    def compute_market_risks(
        self,
        df_transactions: pd.DataFrame,
        df_price_index: pd.DataFrame,
        df_interest_rates: Optional[pd.DataFrame] = None,
        df_sentiment: Optional[pd.DataFrame] = None,
        df_listings: Optional[pd.DataFrame] = None,
    ) -> Dict:
        risks = []
        overall_score = 0

        # 1. Price Volatility Risk
        if not df_price_index.empty and "price_yoy_change_pct" in df_price_index.columns:
            recent_pi = df_price_index.sort_values(["year", "quarter"]).tail(8)
            vol = recent_pi["price_yoy_change_pct"].std()
            if vol > 15:
                risks.append({"factor": "High Price Volatility",
                               "description": f"Price changes showing {vol:.1f}% std deviation — elevated speculative risk.",
                               "severity": "high", "score": 25})
                overall_score += 25
            elif vol > 8:
                risks.append({"factor": "Moderate Price Volatility",
                               "description": f"Prices fluctuating at {vol:.1f}% std — monitor closely.",
                               "severity": "medium", "score": 12})
                overall_score += 12

        # 2. Rising Interest Rate Risk
        if df_interest_rates is not None and not df_interest_rates.empty:
            latest_rate = df_interest_rates["avg_mortgage_rate_pct"].iloc[-1] if "avg_mortgage_rate_pct" in df_interest_rates.columns else 0
            base_rate   = df_interest_rates["uae_base_rate_pct"].iloc[-1] if "uae_base_rate_pct" in df_interest_rates.columns else 0
            if base_rate > 5.0:
                risks.append({"factor": "Elevated Interest Rates",
                               "description": f"UAE base rate at {base_rate:.1f}% — dampening mortgage affordability.",
                               "severity": "high", "score": 20})
                overall_score += 20
            elif base_rate > 3.5:
                risks.append({"factor": "Rising Interest Rates",
                               "description": f"Mortgage rates at {latest_rate:.1f}% — watch for demand slowdown.",
                               "severity": "medium", "score": 10})
                overall_score += 10

        # 3. Transaction Volume Decline
        if not df_transactions.empty and "year" in df_transactions.columns:
            by_year = df_transactions.groupby("year").size()
            if len(by_year) >= 2:
                latest_yr = by_year.index.max()
                prev_yr   = latest_yr - 1
                if prev_yr in by_year.index:
                    change_pct = (by_year[latest_yr] - by_year[prev_yr]) / by_year[prev_yr] * 100
                    if change_pct < -10:
                        risks.append({"factor": "Transaction Volume Decline",
                                       "description": f"Volume fell {abs(change_pct):.1f}% YoY — demand contraction signal.",
                                       "severity": "high", "score": 20})
                        overall_score += 20
                    elif change_pct < -3:
                        risks.append({"factor": "Slowing Transaction Volume",
                                       "description": f"Volume growth slowed by {abs(change_pct):.1f}% — early warning.",
                                       "severity": "medium", "score": 10})
                        overall_score += 10

        # 4. Inventory Oversupply Risk
        if df_listings is not None and not df_listings.empty and "days_on_market" in df_listings.columns:
            median_days = df_listings["days_on_market"].median()
            if median_days > 90:
                risks.append({"factor": "High Inventory Overhang",
                               "description": f"Median days on market: {median_days:.0f} days — oversupply signal.",
                               "severity": "high", "score": 20})
                overall_score += 20
            elif median_days > 45:
                risks.append({"factor": "Rising Inventory Absorption Time",
                               "description": f"Properties taking {median_days:.0f} days on average to sell.",
                               "severity": "medium", "score": 8})
                overall_score += 8

        # 5. Negative Sentiment Risk
        if df_sentiment is not None and not df_sentiment.empty:
            latest_sent = df_sentiment.sort_values("date").iloc[-1] if "date" in df_sentiment.columns else None
            if latest_sent is not None:
                si = latest_sent.get("real_estate_sentiment_index", 70)
                if si < 45:
                    risks.append({"factor": "Negative Market Sentiment",
                                   "description": f"Sentiment index at {si:.0f} — below threshold of 50.",
                                   "severity": "critical", "score": 25})
                    overall_score += 25
                elif si < 60:
                    risks.append({"factor": "Weakening Market Sentiment",
                                   "description": f"Sentiment index at {si:.0f} — declining confidence.",
                                   "severity": "medium", "score": 12})
                    overall_score += 12

        overall_score = min(overall_score, 100)
        severity = "low" if overall_score < 25 else "medium" if overall_score < 50 else "high" if overall_score < 75 else "critical"

        # Early warning signals (actionable)
        early_warnings = [r for r in risks if r["severity"] in ("high", "critical")]

        return {
            "overall_risk_score": overall_score,
            "severity": severity,
            "risk_factors": sorted(risks, key=lambda x: x["score"], reverse=True),
            "early_warnings": early_warnings,
            "total_alerts": len(risks),
            "critical_count": sum(1 for r in risks if r["severity"] == "critical"),
            "recommendation": self._top_recommendation(overall_score, risks),
        }

    @staticmethod
    def _top_recommendation(score: int, risks: List[Dict]) -> str:
        if not risks:
            return "Market conditions appear stable. Continue monitoring key indicators."
        top = risks[0]["factor"] if risks else ""
        if score >= 75:
            return f"CRITICAL: {top} detected. Consider delaying new launches until conditions stabilise."
        if score >= 50:
            return f"WARNING: {top} requires attention. Adjust pricing strategy and review inventory."
        if score >= 25:
            return f"CAUTION: {top} — monitor closely. Opportunity with managed risk."
        return "Market risk is manageable. Proceed with standard risk controls."
