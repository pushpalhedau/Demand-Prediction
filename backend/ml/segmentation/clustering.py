"""
Buyer / Market Segmentation using KMeans, HDBSCAN, and GMM.
Derives segments from DLD transaction data (area, property type, price band, nationality).
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

log = logging.getLogger(__name__)

# Segment labels mapped from cluster centres (price + property type profile)
SEGMENT_LABELS = [
    "Ultra-Luxury Investor",
    "Premium Buyer",
    "Mid-Market Resident",
    "Affordable Homebuyer",
    "Off-Plan Speculator",
    "Commercial Investor",
]


class MarketSegmentation:
    """
    Segments the market using multiple clustering approaches.
    Features derived purely from transaction data (no Buyer table needed).
    """

    def __init__(self, n_clusters: int = 6):
        self.n_clusters = n_clusters
        self.kmeans: Optional[KMeans] = None
        self.gmm: Optional[GaussianMixture] = None
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=2)
        self._segment_profiles: List[Dict] = []
        self._is_fitted = False

    def fit(self, df_transactions: pd.DataFrame) -> "MarketSegmentation":
        X, labels = self._build_features(df_transactions)
        if X is None or len(X) < self.n_clusters * 2:
            log.warning("Not enough data for segmentation")
            return self
        X_scaled = self.scaler.fit_transform(X)

        # KMeans
        self.kmeans = KMeans(n_clusters=self.n_clusters, random_state=42, n_init=10)
        km_labels = self.kmeans.fit_predict(X_scaled)

        # GMM
        self.gmm = GaussianMixture(n_components=self.n_clusters, random_state=42, max_iter=200)
        self.gmm.fit(X_scaled)

        # PCA for 2-D visualisation
        self.pca.fit(X_scaled[:5000])  # fit on a sample if large

        # Compute segment profiles
        df_seg = pd.DataFrame(X, columns=labels)
        df_seg["cluster"] = km_labels
        self._segment_profiles = self._compute_profiles(df_seg, df_transactions, km_labels)
        self._is_fitted = True
        log.info("Segmentation fitted. %d clusters.", self.n_clusters)
        return self

    def predict_segments(self, df_transactions: pd.DataFrame) -> pd.DataFrame:
        """Return the input df enriched with cluster and segment label columns."""
        X, _ = self._build_features(df_transactions)
        if X is None or self.kmeans is None:
            df_transactions["segment"] = "Unknown"
            return df_transactions
        X_scaled = self.scaler.transform(X)
        clusters = self.kmeans.predict(X_scaled)
        df_out = df_transactions.copy()
        df_out["cluster"] = clusters
        label_map = self._build_label_map()
        df_out["segment"] = df_out["cluster"].map(label_map).fillna("Other")
        return df_out

    def get_segment_profiles(self) -> List[Dict]:
        return self._segment_profiles

    def get_2d_projection(self, df_transactions: pd.DataFrame, sample: int = 3000) -> Dict:
        X, _ = self._build_features(df_transactions)
        if X is None or self.kmeans is None:
            return {"x": [], "y": [], "cluster": [], "segment": []}
        X_scaled = self.scaler.transform(X)
        idx = np.random.choice(len(X_scaled), min(sample, len(X_scaled)), replace=False)
        X_2d = self.pca.transform(X_scaled[idx])
        clusters = self.kmeans.predict(X_scaled[idx])
        label_map = self._build_label_map()
        return {
            "x":       X_2d[:, 0].tolist(),
            "y":       X_2d[:, 1].tolist(),
            "cluster": clusters.tolist(),
            "segment": [label_map.get(c, "Other") for c in clusters],
        }

    # ── Feature Engineering ────────────────────────────────────────────

    def _build_features(self, df: pd.DataFrame):
        needed = ["transaction_value_aed", "price_per_sqft_aed", "area_sqft",
                  "bedrooms", "is_off_plan", "property_type", "area_name", "buyer_nationality"]
        missing = [c for c in needed[:5] if c not in df.columns]
        if missing:
            log.warning("Missing columns for segmentation: %s", missing)
            return None, None

        df2 = df.copy()

        # Numeric features
        num_cols = ["transaction_value_aed", "price_per_sqft_aed", "area_sqft"]
        df2[num_cols] = df2[num_cols].apply(pd.to_numeric, errors="coerce")
        df2["bedrooms_num"] = pd.to_numeric(df2.get("bedrooms", 0), errors="coerce").fillna(0)
        df2["is_off_plan_num"] = df2["is_off_plan"].astype(int) if "is_off_plan" in df2.columns else 0

        # Price tier (0-4)
        df2["price_tier"] = pd.qcut(df2["transaction_value_aed"].fillna(df2["transaction_value_aed"].median()),
                                     q=5, labels=False, duplicates="drop")

        # Property type encoding
        if "property_type" in df2.columns:
            type_map = {"Apartment": 0, "Villa": 1, "Townhouse": 2,
                        "Penthouse": 3, "Studio": 4, "Plot": 5, "Commercial": 6}
            df2["prop_type_enc"] = df2["property_type"].map(type_map).fillna(7)
        else:
            df2["prop_type_enc"] = 0

        feature_cols = ["transaction_value_aed", "price_per_sqft_aed", "area_sqft",
                        "bedrooms_num", "is_off_plan_num", "price_tier", "prop_type_enc"]
        df2 = df2[feature_cols].fillna(df2[feature_cols].median())

        # Clip extreme values
        for c in ["transaction_value_aed", "price_per_sqft_aed", "area_sqft"]:
            q99 = df2[c].quantile(0.99)
            df2[c] = df2[c].clip(upper=q99)

        return df2.values, feature_cols

    def _compute_profiles(self, df_seg: pd.DataFrame, df_tx: pd.DataFrame,
                           km_labels: np.ndarray) -> List[Dict]:
        profiles = []
        label_map = self._build_label_map()
        for c in range(self.n_clusters):
            mask = km_labels == c
            tx_subset = df_tx[mask] if len(df_tx) == len(km_labels) else df_tx.iloc[mask]
            count = int(mask.sum())
            avg_val = float(df_seg[mask]["transaction_value_aed"].mean()) if "transaction_value_aed" in df_seg.columns else 0
            profiles.append({
                "cluster": c,
                "label":   label_map.get(c, f"Segment {c}"),
                "count":   count,
                "pct":     round(count / max(len(km_labels), 1) * 100, 1),
                "avg_transaction_value_aed": round(avg_val, 0),
                "top_areas":       self._top_values(tx_subset, "area_name"),
                "top_nationalities": self._top_values(tx_subset, "buyer_nationality"),
                "top_prop_types":  self._top_values(tx_subset, "property_type"),
            })
        return sorted(profiles, key=lambda x: x["avg_transaction_value_aed"], reverse=True)

    def _build_label_map(self) -> Dict[int, str]:
        if not self._segment_profiles:
            return {i: SEGMENT_LABELS[i % len(SEGMENT_LABELS)] for i in range(self.n_clusters)}
        sorted_p = sorted(self._segment_profiles, key=lambda x: x["avg_transaction_value_aed"], reverse=True)
        return {p["cluster"]: SEGMENT_LABELS[i % len(SEGMENT_LABELS)] for i, p in enumerate(sorted_p)}

    @staticmethod
    def _top_values(df: pd.DataFrame, col: str, top_n: int = 3) -> List[str]:
        if col not in df.columns or df.empty:
            return []
        return df[col].value_counts().head(top_n).index.tolist()
