"""
Opportunity Scorer — ranks every area/market 0-100 on investment potential.
Combines: price growth, transaction velocity, rental yield, infrastructure, sentiment.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Shared singleton — import this instead of creating new instances (B5)
# Prevents three separate route modules each calling score_all_areas() independently.


class OpportunityScorer:

    def score_all_areas(
        self,
        df_transactions: pd.DataFrame,
        df_price_index: pd.DataFrame,
        df_areas: pd.DataFrame,
        df_infrastructure: Optional[pd.DataFrame] = None,
        df_sentiment: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Return a DataFrame with one row per area, containing opportunity score and sub-scores.
        """
        scores = []

        # Latest year transactions
        latest_year = df_transactions["year"].max() if "year" in df_transactions.columns else 2024
        tx_latest = df_transactions[df_transactions["year"] == latest_year]
        tx_prev   = df_transactions[df_transactions["year"] == latest_year - 1]

        # Area-level transaction metrics
        tx_agg = tx_latest.groupby("area_name").agg(
            transaction_count=("transaction_id", "count"),
            avg_price_sqft=("price_per_sqft_aed", "mean"),
            total_value=("transaction_value_aed", "sum"),
            avg_value=("transaction_value_aed", "mean"),
        ).reset_index()

        tx_agg_prev = tx_prev.groupby("area_name").agg(
            prev_count=("transaction_id", "count"),
        ).reset_index()

        tx_agg = tx_agg.merge(tx_agg_prev, on="area_name", how="left")
        tx_agg["volume_growth_pct"] = (
            (tx_agg["transaction_count"] - tx_agg["prev_count"]) /
            tx_agg["prev_count"].replace(0, np.nan) * 100
        ).fillna(0)

        # Price index data (latest quarter per area)
        if not df_price_index.empty and "area" in df_price_index.columns:
            pi_latest = df_price_index.sort_values(["year", "quarter"]).groupby("area").last().reset_index()
            pi_latest = pi_latest.rename(columns={"area": "area_name"})
            tx_agg = tx_agg.merge(pi_latest[["area_name", "price_yoy_change_pct",
                                              "rental_yield_pct", "avg_days_to_sell"]],
                                   on="area_name", how="left")
        else:
            tx_agg["price_yoy_change_pct"] = 0
            tx_agg["rental_yield_pct"]     = 6.0
            tx_agg["avg_days_to_sell"]     = 30

        # Infrastructure proximity score (count of active projects in same emirate)
        if df_infrastructure is not None and not df_infrastructure.empty:
            infra_active = df_infrastructure[df_infrastructure.get("status", pd.Series(["Active"])) == "Active"]
            infra_count  = infra_active.get("emirate", pd.Series()).value_counts().to_dict()
            area_emirate = df_areas.set_index("area_name")["emirate"].to_dict() if not df_areas.empty else {}
            tx_agg["infra_score"] = tx_agg["area_name"].map(
                lambda a: min(infra_count.get(area_emirate.get(a, "Dubai"), 0) / 10, 1.0)
            )
        else:
            tx_agg["infra_score"] = 0.5

        # Composite score (0-100) — weighted sum of normalized sub-scores
        def norm(series: pd.Series) -> pd.Series:
            mn, mx = series.min(), series.max()
            if mx == mn:
                return pd.Series(0.5, index=series.index)
            return (series - mn) / (mx - mn)

        tx_agg = tx_agg.fillna(0)
        s_volume    = norm(tx_agg["transaction_count"])      * 20
        s_vol_growth = norm(tx_agg["volume_growth_pct"])     * 15
        s_price_growth = norm(tx_agg["price_yoy_change_pct"]) * 20
        s_yield     = norm(tx_agg["rental_yield_pct"])       * 20
        s_speed     = norm(-tx_agg["avg_days_to_sell"])      * 15  # lower days = better
        s_infra     = tx_agg["infra_score"] * 10

        tx_agg["opportunity_score"]   = (s_volume + s_vol_growth + s_price_growth +
                                          s_yield + s_speed + s_infra).clip(0, 100).round(1)
        tx_agg["success_probability"] = ((tx_agg["opportunity_score"] / 100) * 0.7 +
                                          norm(tx_agg["rental_yield_pct"]) * 0.3).clip(0, 1).round(3)
        tx_agg["expected_roi_pct"]    = (tx_agg["rental_yield_pct"].fillna(6) +
                                          tx_agg["price_yoy_change_pct"].fillna(0)).round(2)

        return tx_agg.sort_values("opportunity_score", ascending=False).reset_index(drop=True)

    def get_scored_areas_cached(
        self,
        df_transactions: pd.DataFrame,
        df_price_index: pd.DataFrame,
        df_areas: pd.DataFrame,
        df_infrastructure: Optional[pd.DataFrame] = None,
        df_sentiment: Optional[pd.DataFrame] = None,
        ttl: int = 900,
    ) -> pd.DataFrame:
        """Score all areas, caching the result so multiple route handlers share one
        computation pass per TTL window instead of each triggering their own (B5)."""
        from backend.data.cache import cache as _c
        cached = _c.get("opp_scored_areas", {})
        if cached is not None:
            return cached
        result = self.score_all_areas(
            df_transactions, df_price_index, df_areas, df_infrastructure, df_sentiment
        )
        _c.set("opp_scored_areas", {}, result, ttl=ttl)
        return result

    def top_opportunities(self, df_scored: pd.DataFrame, top_n: int = 10) -> List[Dict]:
        cols = ["area_name", "opportunity_score", "success_probability",
                "expected_roi_pct", "avg_price_sqft", "transaction_count",
                "price_yoy_change_pct", "rental_yield_pct"]
        available = [c for c in cols if c in df_scored.columns]
        top = df_scored[available].head(top_n)
        results = []
        for _, row in top.iterrows():
            d = row.to_dict()
            d["recommendation"] = self._recommendation(d)
            results.append(d)
        return results

    @staticmethod
    def _recommendation(row: Dict) -> str:
        score = row.get("opportunity_score", 0)
        roi   = row.get("expected_roi_pct", 0)
        area  = row.get("area_name", "this area")
        if score >= 75:
            return f"High-priority investment target. {area} shows strong demand growth and rental yield."
        if score >= 50:
            return f"Solid mid-tier opportunity in {area} with balanced risk/reward profile."
        return f"{area} is emerging — suitable for long-term positioning at lower entry prices."


opp_scorer = OpportunityScorer()
