import os
import sys
import pandas as pd
import numpy as np
import pickle
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import get_db_session
from database.models import Transaction, Buyer

MODEL_DIR = "models/xgboost"
os.makedirs(MODEL_DIR, exist_ok=True)


def train_xgboost_pipeline():
    """
    Train XGBoost to predict booking_converted from buyer + transaction features.
    Returns feature importances and accuracy metrics.
    """
    session = get_db_session()
    try:
        query = session.query(
            Transaction.booking_converted,
            Transaction.property_category,
            Transaction.property_type,
            Transaction.marketing_channel,
            Transaction.payment_plan,
            Transaction.city,
            Transaction.discount_pct,
            Transaction.area_sqft,
            Transaction.lead_to_close_days,
            Buyer.age,
            Buyer.gender,
            Buyer.occupation,
            Buyer.estimated_annual_income_aed,
            Buyer.loyalty_score,
            Buyer.site_visit_taken,
            Buyer.expat_status,
            Buyer.golden_visa_intent,
            Buyer.off_plan_preference,
            Buyer.buyer_type,
            Buyer.mortgage_preferred,
        ).join(Buyer, Transaction.buyer_id == Buyer.buyer_id)

        df = pd.read_sql(query.statement, session.bind)
        if df.empty or len(df) < 100:
            return None, "Insufficient data (need at least 100 transactions)."

        df["booking_converted"] = df["booking_converted"].fillna(False).astype(int)

        cat_features = [
            "property_category", "property_type", "marketing_channel",
            "payment_plan", "city", "gender", "occupation", "buyer_type",
        ]
        bool_features = [
            "site_visit_taken", "expat_status", "golden_visa_intent",
            "off_plan_preference", "mortgage_preferred",
        ]
        num_features = [
            "discount_pct", "area_sqft", "lead_to_close_days",
            "age", "estimated_annual_income_aed", "loyalty_score",
        ]

        for col in cat_features:
            df[col] = df[col].fillna("Unknown")
        for col in bool_features:
            df[col] = df[col].fillna(False).astype(int)
        for col in num_features:
            df[col] = df[col].fillna(df[col].median())

        encoders = {}
        X = pd.DataFrame()
        for col in cat_features:
            le = LabelEncoder()
            X[col] = le.fit_transform(df[col].astype(str))
            encoders[col] = le
        for col in bool_features:
            X[col] = df[col]
        for col in num_features:
            X[col] = df[col]

        y = df["booking_converted"]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        scaler = StandardScaler()
        X_train_s = X_train.copy()
        X_test_s = X_test.copy()
        X_train_s[num_features] = scaler.fit_transform(X_train[num_features])
        X_test_s[num_features] = scaler.transform(X_test[num_features])

        model = XGBClassifier(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.08,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric="logloss",
        )
        model.fit(X_train_s, y_train)

        with open(os.path.join(MODEL_DIR, "scaler.pkl"), "wb") as f:
            pickle.dump(scaler, f)
        with open(os.path.join(MODEL_DIR, "encoders.pkl"), "wb") as f:
            pickle.dump(encoders, f)
        with open(os.path.join(MODEL_DIR, "xgboost_model.pkl"), "wb") as f:
            pickle.dump(model, f)
        with open(os.path.join(MODEL_DIR, "feature_names.pkl"), "wb") as f:
            pickle.dump(list(X.columns), f)

        feature_importance_df = pd.DataFrame({
            "Feature": X.columns,
            "Importance": model.feature_importances_,
        }).sort_values("Importance", ascending=False)

        return {
            "feature_importance": feature_importance_df,
            "accuracy": float(model.score(X_test_s, y_test)),
            "train_size": len(X_train),
            "test_size": len(X_test),
        }, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"XGBoost pipeline error: {str(e)}"
    finally:
        session.close()


def predict_booking_probability(input_data: dict) -> dict:
    """
    Predict booking conversion probability for a lead profile.
    """
    try:
        with open(os.path.join(MODEL_DIR, "scaler.pkl"), "rb") as f:
            scaler = pickle.load(f)
        with open(os.path.join(MODEL_DIR, "encoders.pkl"), "rb") as f:
            encoders = pickle.load(f)
        with open(os.path.join(MODEL_DIR, "xgboost_model.pkl"), "rb") as f:
            model = pickle.load(f)
        with open(os.path.join(MODEL_DIR, "feature_names.pkl"), "rb") as f:
            feature_names = pickle.load(f)

        cat_features = [
            "property_category", "property_type", "marketing_channel",
            "payment_plan", "city", "gender", "occupation", "buyer_type",
        ]
        bool_features = [
            "site_visit_taken", "expat_status", "golden_visa_intent",
            "off_plan_preference", "mortgage_preferred",
        ]
        num_features = [
            "discount_pct", "area_sqft", "lead_to_close_days",
            "age", "estimated_annual_income_aed", "loyalty_score",
        ]

        record = {
            "property_category": input_data.get("property_category", "Mid-Market"),
            "property_type": input_data.get("property_type", "Apartment"),
            "marketing_channel": input_data.get("marketing_channel", "Property Finder"),
            "payment_plan": input_data.get("payment_plan", "Mortgage"),
            "city": input_data.get("city", "Dubai"),
            "gender": input_data.get("gender", "Male"),
            "occupation": input_data.get("occupation", "Salaried"),
            "buyer_type": input_data.get("buyer_type", "End User"),
            "site_visit_taken": int(input_data.get("site_visit_taken", False)),
            "expat_status": int(input_data.get("expat_status", True)),
            "golden_visa_intent": int(input_data.get("golden_visa_intent", False)),
            "off_plan_preference": int(input_data.get("off_plan_preference", False)),
            "mortgage_preferred": int(input_data.get("mortgage_preferred", True)),
            "discount_pct": float(input_data.get("discount_pct", 2.0)),
            "area_sqft": float(input_data.get("area_sqft", 1000.0)),
            "lead_to_close_days": float(input_data.get("lead_to_close_days", 30.0)),
            "age": float(input_data.get("age", 35.0)),
            "estimated_annual_income_aed": float(input_data.get("estimated_annual_income_aed", 300000.0)),
            "loyalty_score": float(input_data.get("loyalty_score", 60.0)),
        }

        df_enc = pd.DataFrame(index=[0])
        for col in cat_features:
            le = encoders[col]
            val = str(record[col])
            if val not in le.classes_:
                val = le.classes_[0]
            df_enc[col] = le.transform([val])[0]
        for col in bool_features:
            df_enc[col] = record[col]
        for col in num_features:
            df_enc[col] = record[col]

        df_scaled = df_enc.copy()
        df_scaled[num_features] = scaler.transform(df_enc[num_features])

        prob = float(model.predict_proba(df_scaled)[0, 1])

        shap_explanations = []
        try:
            import shap
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(df_scaled)
            for name, val in zip(feature_names, shap_values[0]):
                direction = "positive" if val > 0 else "negative"
                shap_explanations.append({
                    "feature": name,
                    "score": float(val),
                    "direction": direction,
                    "description": f"{name.replace('_', ' ').title()} — {direction} impact ({val:+.3f})",
                })
            shap_explanations.sort(key=lambda x: abs(x["score"]), reverse=True)
        except Exception:
            income = record["estimated_annual_income_aed"]
            site_visit = record["site_visit_taken"]
            golden_visa = record["golden_visa_intent"]
            shap_explanations = [
                {
                    "feature": "site_visit_taken",
                    "score": 0.30 if site_visit else -0.20,
                    "direction": "positive" if site_visit else "negative",
                    "description": f"Site visit {'completed — strong buying intent' if site_visit else 'not taken — low intent signal'}",
                },
                {
                    "feature": "estimated_annual_income_aed",
                    "score": 0.15 if income > 400000 else (-0.10 if income < 150000 else 0.03),
                    "direction": "positive" if income >= 150000 else "negative",
                    "description": f"Annual income AED {int(income):,} — {'strong affordability' if income > 400000 else 'budget constraint'}",
                },
                {
                    "feature": "golden_visa_intent",
                    "score": 0.20 if golden_visa else 0.0,
                    "direction": "positive" if golden_visa else "neutral",
                    "description": f"Golden Visa intent {'present — high-value buyer signal' if golden_visa else 'not indicated'}",
                },
            ]
            shap_explanations.sort(key=lambda x: abs(x["score"]), reverse=True)

        return {"booking_probability": prob, "explanations": shap_explanations}

    except Exception as e:
        return {"booking_probability": 0.5, "explanations": []}
