import os
import sys
import pandas as pd
import numpy as np
import pickle
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Add the project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import get_db_session, get_data_mode
from database.models import Customer

_BASE_MODEL_DIR = "models/clustering"


def _model_dir() -> str:
    """Return mode-specific model directory: models/clustering/test or .../real"""
    d = os.path.join(_BASE_MODEL_DIR, get_data_mode())
    os.makedirs(d, exist_ok=True)
    return d

def train_customer_segmentation(n_clusters: int = 5):
    """
    Query customer data, scale features, train KMeans, assign logical segment labels,
    and save model files.
    """
    session = get_db_session()
    try:
        # 1. Fetch relevant numerical features for customer segmentation
        query = session.query(
            Customer.customer_id,
            Customer.age,
            Customer.estimated_annual_income_usd,
            Customer.credit_score,
            Customer.number_of_past_purchases,
            Customer.loyalty_score,
            Customer.churn_risk_score,
            Customer.preferred_vehicle_category,
            Customer.preferred_fuel_type
        )
        df = pd.read_sql(query.statement, session.bind)
        if df.empty:
            return None, "No customer data available in database."
            
        # Select numeric features for clustering
        features = [
            'age', 
            'estimated_annual_income_usd', 
            'credit_score', 
            'number_of_past_purchases', 
            'loyalty_score', 
            'churn_risk_score'
        ]
        
        # Fill missing values just in case
        X = df[features].copy()
        X['age'] = X['age'].fillna(X['age'].median())
        X['estimated_annual_income_usd'] = X['estimated_annual_income_usd'].fillna(X['estimated_annual_income_usd'].median())
        X['credit_score'] = X['credit_score'].fillna(X['credit_score'].median())
        X['number_of_past_purchases'] = X['number_of_past_purchases'].fillna(0)
        X['loyalty_score'] = X['loyalty_score'].fillna(50.0)
        X['churn_risk_score'] = X['churn_risk_score'].fillna(0.5)
        
        # Standardize the data
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Fit KMeans
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df['cluster'] = kmeans.fit_predict(X_scaled)
        
        # logical mapping of clusters to segments based on centroids
        centroids = kmeans.cluster_centers_
        
        # Calculate cluster means in original space to assign titles
        cluster_means = df.groupby('cluster')[features].mean()
        
        # Standard mapping
        # Budget Buyer: low income
        # Premium Buyer: high income
        # EV Enthusiast: high loyalty/score and preferred EV category
        # Fleet Buyer: high past purchases, lower loyalty or specific demographics
        # High Repeat: high past purchases, high loyalty
        
        # Let's write an algorithm to dynamically assign segment names to each cluster
        cluster_mapping = {}
        unassigned_labels = ["Budget Buyer", "Premium Buyer", "EV Enthusiast", "Fleet Buyer", "High Repeat"]
        
        # Identify "Premium Buyer" as the cluster with the highest average monthly income
        premium_cluster = cluster_means['estimated_annual_income_usd'].idxmax()
        cluster_mapping[premium_cluster] = "Premium Buyer"
        if "Premium Buyer" in unassigned_labels: unassigned_labels.remove("Premium Buyer")
        
        # Identify "Budget Buyer" as the cluster with the lowest average monthly income
        remaining = [c for c in range(n_clusters) if c not in cluster_mapping]
        budget_cluster = cluster_means.loc[remaining, 'estimated_annual_income_usd'].idxmin()
        cluster_mapping[budget_cluster] = "Budget Buyer"
        if "Budget Buyer" in unassigned_labels: unassigned_labels.remove("Budget Buyer")
        
        # Identify "High Repeat" as the cluster with highest past purchases (excluding already mapped)
        remaining = [c for c in range(n_clusters) if c not in cluster_mapping]
        repeat_cluster = cluster_means.loc[remaining, 'number_of_past_purchases'].idxmax()
        cluster_mapping[repeat_cluster] = "High Repeat"
        if "High Repeat" in unassigned_labels: unassigned_labels.remove("High Repeat")
        
        # Identify "EV Enthusiast" as the one with high loyalty or younger age/modern segment
        remaining = [c for c in range(n_clusters) if c not in cluster_mapping]
        if remaining:
            ev_cluster = cluster_means.loc[remaining, 'loyalty_score'].idxmax()
            cluster_mapping[ev_cluster] = "EV Enthusiast"
            if "EV Enthusiast" in unassigned_labels: unassigned_labels.remove("EV Enthusiast")
            
        # Assign remaining cluster to Fleet Buyer
        remaining = [c for c in range(n_clusters) if c not in cluster_mapping]
        for c in remaining:
            if unassigned_labels:
                cluster_mapping[c] = unassigned_labels.pop(0)
            else:
                cluster_mapping[c] = "Regular Buyer"
                
        # Apply labels to DataFrame
        df['assigned_segment'] = df['cluster'].map(cluster_mapping)
        
        # Update database with assigned segments so the analytics reflect it
        # This will write the segment labels back to the customers table
        print("Writing segmentations back to database customers table...")
        update_mappings = [
            {"customer_id": cid, "customer_segment": seg}
            for cid, seg in zip(df['customer_id'], df['assigned_segment'])
        ]
        session.bulk_update_mappings(Customer, update_mappings)
        session.commit()
        
        # Save scaler and model files (mode-specific directory)
        mdir = _model_dir()
        with open(os.path.join(mdir, "scaler.pkl"), "wb") as f:
            pickle.dump(scaler, f)
        with open(os.path.join(mdir, "kmeans.pkl"), "wb") as f:
            pickle.dump(kmeans, f)
        with open(os.path.join(mdir, "cluster_mapping.pkl"), "wb") as f:
            pickle.dump(cluster_mapping, f)
            
        print("Customer clustering completed and models saved.")
        return {
            "customers_df": df,
            "cluster_means": cluster_means,
            "cluster_mapping": cluster_mapping
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
    Predict the segment for a new customer based on their input attributes.
    """
    try:
        mdir = _model_dir()
        with open(os.path.join(mdir, "scaler.pkl"), "rb") as f:
            scaler = pickle.load(f)
        with open(os.path.join(mdir, "kmeans.pkl"), "rb") as f:
            kmeans = pickle.load(f)
        with open(os.path.join(mdir, "cluster_mapping.pkl"), "rb") as f:
            cluster_mapping = pickle.load(f)
            
        features = [
            customer_data.get('age', 40),
            customer_data.get('estimated_annual_income_usd', 75000.0),
            customer_data.get('credit_score', 700),
            customer_data.get('number_of_past_purchases', 1),
            customer_data.get('loyalty_score', 50.0),
            customer_data.get('churn_risk_score', 0.5)
        ]
        
        scaled_features = scaler.transform([features])
        cluster_idx = kmeans.predict(scaled_features)[0]
        return cluster_mapping.get(cluster_idx, "Regular Buyer")
    except Exception as e:
        print(f"Prediction error: {e}")
        return "Regular Buyer"
