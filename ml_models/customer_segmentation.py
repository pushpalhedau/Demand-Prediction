import os
import sys
import datetime as _dt
import pandas as pd
import numpy as np
import pickle
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Add the project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import get_db_session, get_data_mode
from database.models import Customer, Sale
from sqlalchemy import func

_BASE_MODEL_DIR = "models/clustering"

# Segmentation feature set (2026-08-29 dealer-positioning pass).
#
# `nationality` was removed — segmenting US auto customers by national origin /
# ethnicity is a fair-lending (ECOA / disparate-impact) liability. The two
# decorative "score" fields (`loyalty_score`, `churn_risk_score`) were dropped
# too; they now carry real signal but it is redundant with recency/frequency.
# What's left is what a dealer actually groups a customer base by: how much they
# earn, their credit tier, their life-stage, how many times they've bought from
# the group, how long since the last deal, and how big their deals run.
FEATURES = [
    "age",
    "estimated_annual_income_usd",
    "credit_score",
    "number_of_past_purchases",
    "recency_days",
    "avg_deal_value",
]

SEGMENT_LABELS = [
    "High-Value / Prime",
    "Core Mainstream",
    "Value Buyers",
    "Loyal Repeat",
    "Lapsed / At-Risk",
]


def _model_dir() -> str:
    """Return mode-specific model directory: models/clustering/test or .../real"""
    d = os.path.join(_BASE_MODEL_DIR, get_data_mode())
    os.makedirs(d, exist_ok=True)
    return d


def load_customer_features(session, as_of: _dt.date = None) -> pd.DataFrame:
    """
    One row per customer with the six segmentation features, joining each
    customer's real deal history from the sales table:
      recency_days   — days since the customer's last activity / last deal
      avg_deal_value — mean total_revenue_incl_tax across their deals
    Customers with no deal on file get recency from last_activity_date and the
    buyer-median deal value (so they still cluster somewhere sensible).
    """
    if as_of is None:
        as_of = _dt.date.today()

    cust = pd.read_sql(
        session.query(
            Customer.customer_id,
            Customer.age,
            Customer.estimated_annual_income_usd,
            Customer.credit_score,
            Customer.number_of_past_purchases,
            Customer.last_activity_date,
        ).statement,
        session.bind,
    )

    deals = pd.read_sql(
        session.query(
            Sale.customer_id.label("customer_id"),
            func.avg(Sale.total_revenue_incl_tax).label("avg_deal_value"),
        ).group_by(Sale.customer_id).statement,
        session.bind,
    )

    df = cust.merge(deals, on="customer_id", how="left")

    as_of_ts = pd.Timestamp(as_of)
    last_act = pd.to_datetime(df["last_activity_date"], errors="coerce")
    df["recency_days"] = (as_of_ts - last_act).dt.days
    df["recency_days"] = df["recency_days"].clip(lower=0).fillna(df["recency_days"].median())

    buyer_median = df.loc[df["avg_deal_value"].notna(), "avg_deal_value"].median()
    df["avg_deal_value"] = df["avg_deal_value"].fillna(buyer_median)

    df["age"] = df["age"].fillna(df["age"].median())
    df["estimated_annual_income_usd"] = df["estimated_annual_income_usd"].fillna(
        df["estimated_annual_income_usd"].median()
    )
    df["credit_score"] = df["credit_score"].fillna(df["credit_score"].median())
    df["number_of_past_purchases"] = df["number_of_past_purchases"].fillna(0)

    return df


def _assign_labels(cluster_means: pd.DataFrame) -> dict:
    """
    Rank clusters into the five dealer-facing labels on their centroid values
    (original feature space). Deterministic given the centroids.
    """
    mapping = {}
    remaining = list(cluster_means.index)

    # Lapsed / At-Risk — the cluster that hasn't been back in the longest.
    c = cluster_means.loc[remaining, "recency_days"].idxmax()
    mapping[c] = "Lapsed / At-Risk"
    remaining.remove(c)

    # Loyal Repeat — most lifetime deals of what's left.
    c = cluster_means.loc[remaining, "number_of_past_purchases"].idxmax()
    mapping[c] = "Loyal Repeat"
    remaining.remove(c)

    # High-Value / Prime — highest income of what's left.
    c = cluster_means.loc[remaining, "estimated_annual_income_usd"].idxmax()
    mapping[c] = "High-Value / Prime"
    remaining.remove(c)

    # Value Buyers — smallest average deal value of what's left.
    c = cluster_means.loc[remaining, "avg_deal_value"].idxmin()
    mapping[c] = "Value Buyers"
    remaining.remove(c)

    # Core Mainstream — whatever is left (there should be exactly one).
    for c in remaining:
        mapping[c] = "Core Mainstream"
    return mapping


def train_customer_segmentation(n_clusters: int = 5):
    """
    Build the six-feature customer frame, scale, fit KMeans, map clusters to the
    five dealer-facing labels, write the labels back onto the customers table,
    and persist scaler / kmeans / mapping to models/clustering/{mode}/.
    """
    session = get_db_session()
    try:
        df = load_customer_features(session)
        if df.empty:
            return None, "No customer data available in database."

        X = df[FEATURES].copy()

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df["cluster"] = kmeans.fit_predict(X_scaled)

        cluster_means = df.groupby("cluster")[FEATURES].mean()
        cluster_mapping = _assign_labels(cluster_means)
        df["assigned_segment"] = df["cluster"].map(cluster_mapping)

        print("Writing segmentations back to database customers table...")
        session.bulk_update_mappings(
            Customer,
            [
                {"customer_id": cid, "customer_segment": seg}
                for cid, seg in zip(df["customer_id"], df["assigned_segment"])
            ],
        )
        session.commit()

        mdir = _model_dir()
        with open(os.path.join(mdir, "scaler.pkl"), "wb") as f:
            pickle.dump(scaler, f)
        with open(os.path.join(mdir, "kmeans.pkl"), "wb") as f:
            pickle.dump(kmeans, f)
        with open(os.path.join(mdir, "cluster_mapping.pkl"), "wb") as f:
            pickle.dump(cluster_mapping, f)
        with open(os.path.join(mdir, "feature_names.pkl"), "wb") as f:
            pickle.dump(list(FEATURES), f)

        print("Customer clustering completed and models saved.")
        return {
            "customers_df": df,
            "cluster_means": cluster_means,
            "cluster_mapping": cluster_mapping,
        }, None

    except Exception as e:
        session.rollback()
        import traceback
        traceback.print_exc()
        return None, f"Customer clustering pipeline error: {str(e)}"
    finally:
        session.close()


def predict_customer_segment(customer_data: dict) -> str:
    """
    Predict the segment for a customer profile given the six features
    (age, estimated_annual_income_usd, credit_score, number_of_past_purchases,
    recency_days, avg_deal_value). Falls back to "Core Mainstream" on any error.
    """
    try:
        mdir = _model_dir()
        with open(os.path.join(mdir, "scaler.pkl"), "rb") as f:
            scaler = pickle.load(f)
        with open(os.path.join(mdir, "kmeans.pkl"), "rb") as f:
            kmeans = pickle.load(f)
        with open(os.path.join(mdir, "cluster_mapping.pkl"), "rb") as f:
            cluster_mapping = pickle.load(f)

        row = [
            customer_data.get("age", 45),
            customer_data.get("estimated_annual_income_usd", 75000.0),
            customer_data.get("credit_score", 700),
            customer_data.get("number_of_past_purchases", 1),
            customer_data.get("recency_days", 540),
            customer_data.get("avg_deal_value", 42000.0),
        ]
        cluster_idx = int(kmeans.predict(scaler.transform([row]))[0])
        return cluster_mapping.get(cluster_idx, "Core Mainstream")
    except Exception as e:
        print(f"Prediction error: {e}")
        return "Core Mainstream"
