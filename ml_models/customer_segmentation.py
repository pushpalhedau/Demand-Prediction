import os
import sys
import pandas as pd
import numpy as np
import pickle
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import get_db_session
from database.models import Buyer

MODEL_DIR = "models/clustering"
os.makedirs(MODEL_DIR, exist_ok=True)

# UAE buyer segment labels (6 segments)
SEGMENT_LABELS = [
    "Portfolio Investor",
    "Upgrader",
    "Golden Visa Seeker",
    "First-Home Buyer",
    "End User",
    "Rental Investor",
]


def train_buyer_segmentation(n_clusters: int = 6):
    """
    Cluster buyers into 6 UAE real estate segments using KMeans.
    Features: income, past_purchases, budget_max, loyalty_score, golden_visa_intent, off_plan_preference.
    """
    session = get_db_session()
    try:
        query = session.query(
            Buyer.buyer_id,
            Buyer.age,
            Buyer.estimated_annual_income_aed,
            Buyer.number_of_past_purchases,
            Buyer.budget_max_aed,
            Buyer.loyalty_score,
            Buyer.churn_risk_score,
            Buyer.golden_visa_intent,
            Buyer.expat_status,
            Buyer.off_plan_preference,
            Buyer.site_visit_taken,
        )
        df = pd.read_sql(query.statement, session.bind)
        if df.empty:
            return None, "No buyer data available."

        features = [
            "age",
            "estimated_annual_income_aed",
            "number_of_past_purchases",
            "budget_max_aed",
            "loyalty_score",
            "churn_risk_score",
        ]

        X = df[features].copy()
        for col in features:
            X[col] = X[col].fillna(X[col].median())

        # Boolean flags as float features
        df["golden_visa_intent"] = df["golden_visa_intent"].fillna(False).astype(float)
        df["expat_status"] = df["expat_status"].fillna(True).astype(float)
        df["off_plan_preference"] = df["off_plan_preference"].fillna(False).astype(float)
        X["golden_visa_flag"] = df["golden_visa_intent"]
        X["expat_flag"] = df["expat_status"]
        X["off_plan_flag"] = df["off_plan_preference"]

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df["cluster"] = kmeans.fit_predict(X_scaled)

        cluster_means = df.groupby("cluster")[
            features + ["golden_visa_intent", "expat_status", "off_plan_preference"]
        ].mean()

        # Assign semantic labels based on cluster characteristics
        cluster_mapping = {}
        remaining = list(range(n_clusters))

        # Portfolio Investor: highest income AND highest budget AND most past purchases
        income_rank = cluster_means["estimated_annual_income_aed"].rank(ascending=False)
        budget_rank = cluster_means["budget_max_aed"].rank(ascending=False)
        purchase_rank = cluster_means["number_of_past_purchases"].rank(ascending=False)
        pi_score = income_rank + budget_rank + purchase_rank
        pi_c = pi_score.idxmin()
        cluster_mapping[pi_c] = "Portfolio Investor"
        remaining.remove(pi_c)

        # Golden Visa Seeker: highest golden_visa_intent proportion AND high budget
        remaining_df = cluster_means.loc[remaining]
        gv_score = remaining_df["golden_visa_intent"].rank(ascending=False) + remaining_df["budget_max_aed"].rank(ascending=False)
        gv_c = gv_score.idxmin()
        cluster_mapping[gv_c] = "Golden Visa Seeker"
        remaining.remove(gv_c)

        # First-Home Buyer: lowest number_of_past_purchases AND lowest budget
        remaining_df = cluster_means.loc[remaining]
        ftb_score = remaining_df["number_of_past_purchases"].rank(ascending=True) + remaining_df["budget_max_aed"].rank(ascending=True)
        ftb_c = ftb_score.idxmin()
        cluster_mapping[ftb_c] = "First-Home Buyer"
        remaining.remove(ftb_c)

        if len(remaining) >= 3:
            remaining_df = cluster_means.loc[remaining]
            # Upgrader: higher past purchases, mid-range budget
            upg_c = remaining_df["number_of_past_purchases"].idxmax()
            cluster_mapping[upg_c] = "Upgrader"
            remaining.remove(upg_c)

        if len(remaining) >= 2:
            remaining_df = cluster_means.loc[remaining]
            # Rental Investor: highest off_plan_preference
            ri_c = remaining_df["off_plan_preference"].idxmax()
            cluster_mapping[ri_c] = "Rental Investor"
            remaining.remove(ri_c)

        if remaining:
            cluster_mapping[remaining[0]] = "End User"

        df["assigned_segment"] = df["cluster"].map(cluster_mapping)

        # Write segments back to database
        update_mappings = [
            {"buyer_id": bid, "customer_segment": seg}
            for bid, seg in zip(df["buyer_id"], df["assigned_segment"])
        ]
        session.bulk_update_mappings(Buyer, update_mappings)
        session.commit()

        with open(os.path.join(MODEL_DIR, "scaler.pkl"), "wb") as f:
            pickle.dump(scaler, f)
        with open(os.path.join(MODEL_DIR, "kmeans.pkl"), "wb") as f:
            pickle.dump(kmeans, f)
        with open(os.path.join(MODEL_DIR, "cluster_mapping.pkl"), "wb") as f:
            pickle.dump(cluster_mapping, f)

        print(f"Buyer segmentation complete. Segment distribution:\n{df['assigned_segment'].value_counts()}")
        return {
            "buyers_df": df,
            "cluster_means": cluster_means,
            "cluster_mapping": cluster_mapping,
        }, None

    except Exception as e:
        session.rollback()
        import traceback
        traceback.print_exc()
        return None, f"Segmentation pipeline error: {str(e)}"
    finally:
        session.close()


def predict_buyer_segment(buyer_data: dict) -> str:
    """Predict segment for a new buyer profile."""
    try:
        with open(os.path.join(MODEL_DIR, "scaler.pkl"), "rb") as f:
            scaler = pickle.load(f)
        with open(os.path.join(MODEL_DIR, "kmeans.pkl"), "rb") as f:
            kmeans = pickle.load(f)
        with open(os.path.join(MODEL_DIR, "cluster_mapping.pkl"), "rb") as f:
            cluster_mapping = pickle.load(f)

        features = [
            buyer_data.get("age", 35),
            buyer_data.get("estimated_annual_income_aed", 300000.0),
            buyer_data.get("number_of_past_purchases", 0),
            buyer_data.get("budget_max_aed", 2000000),
            buyer_data.get("loyalty_score", 50.0),
            buyer_data.get("churn_risk_score", 0.4),
            float(buyer_data.get("golden_visa_intent", False)),
            float(buyer_data.get("expat_status", True)),
            float(buyer_data.get("off_plan_preference", False)),
        ]

        scaled = scaler.transform([features])
        cluster_idx = kmeans.predict(scaled)[0]
        return cluster_mapping.get(cluster_idx, "End User")
    except Exception:
        return "End User"
