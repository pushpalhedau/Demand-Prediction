import os
import sys
import pandas as pd
import numpy as np
import pickle
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

# Add the project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import get_db_session
from database.tenant_context import require_tenant_id
from utils.i18n import fmt_money
from database.models import Sale, Customer, Vehicle

_BASE_MODEL_DIR = "models/xgboost"


def _model_dir() -> str:
    """Per-tenant model directory: models/<kind>/<tenant_id>"""
    d = os.path.join(_BASE_MODEL_DIR, str(require_tenant_id()))
    os.makedirs(d, exist_ok=True)
    return d

def train_xgboost_pipeline():
    """
    Train an XGBoost classifier to predict whether a customer will convert after a test drive
    (test_drive_converted = True) based on demographics and transaction parameters.
    Saves the scaler, label encoders, and model, and returns feature importances.
    """
    session = get_db_session()
    try:
        # Join Sales, Customers, and Vehicles to compile a rich feature set
        query = session.query(
            Sale.test_drive_converted,
            Sale.base_price.label('base_price'),
            Sale.discount_pct,
            Sale.marketing_channel,
            Sale.vehicle_category,
            Sale.fuel_type,
            Sale.region,
            Customer.age,
            Customer.occupation,
            Customer.annual_income,
            Customer.credit_score,
            Customer.loyalty_score
        ).join(Customer, Sale.customer_id == Customer.customer_id) \
         .join(Vehicle, Sale.vehicle_id == Vehicle.vehicle_id)

        df = pd.read_sql(query.statement, session.bind)
        if df.empty or len(df) < 100:
            return None, "Insufficient data to train XGBoost lead scoring model (need at least 100 transactions)."

        # Target column: test_drive_converted (binary classification)
        df['test_drive_converted'] = df['test_drive_converted'].fillna(False).astype(int)

        # Features to use
        #
        # `gender` and `nationality` are deliberately NOT features of this
        # per-lead close score. Nationality is a legitimate market-segmentation
        # dimension in some markets and is used by the KMeans segmentation, but
        # weighting an individual lead-prioritisation score on the customer's
        # nationality or sex is a fairness risk with no defensible predictive
        # role in "will this test-drive convert". `age` is kept as a standard
        # behavioural CRM signal (not a credit decision here).
        #
        # financing_type is deliberately NOT a feature.
        #
        # How a deal is paid for is an outcome of the negotiation, not a driver
        # of whether the customer buys: it is agreed late in the process, so
        # including it lets the model partly predict the close from the close.
        # Left in, it drew a large SHAP attribution and produced advice to
        # "switch the customer to a Bank Loan", which is an artifact of that
        # leakage rather than a lever anyone can pull. Financing is still
        # captured on the deal record and drives the lease-return pipeline in
        # Inventory Intelligence, where it genuinely is predictive.
        cat_features = ['marketing_channel', 'vehicle_category', 'fuel_type', 'region', 'occupation']
        num_features = ['base_price', 'discount_pct', 'age', 'annual_income', 'credit_score', 'loyalty_score']

        lead_stats = {
            c: {"p25": float(df[c].quantile(0.25)), "p50": float(df[c].median()),
                "p75": float(df[c].quantile(0.75)), "lo": float(df[c].min()), "hi": float(df[c].max())}
            for c in num_features if df[c].notna().any()
        }

        # Handle missing values
        for cat in cat_features:
            df[cat] = df[cat].fillna("Unknown")
        for num in num_features:
            df[num] = df[num].fillna(df[num].median())
            
        # Encode categorical variables
        encoders = {}
        X_encoded = pd.DataFrame()
        for cat in cat_features:
            le = LabelEncoder()
            X_encoded[cat] = le.fit_transform(df[cat].astype(str))
            encoders[cat] = le
            
        # Combine numeric features
        for num in num_features:
            X_encoded[num] = df[num]
            
        y = df['test_drive_converted']
        X = X_encoded
        
        # Train / test split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        
        # Standard scaler for numerical features
        scaler = StandardScaler()
        # Scale only numerical columns
        X_train_scaled = X_train.copy()
        X_test_scaled = X_test.copy()
        
        X_train_scaled[num_features] = scaler.fit_transform(X_train[num_features])
        X_test_scaled[num_features] = scaler.transform(X_test[num_features])
        
        # Train XGBoost
        model = XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.08,
            random_state=42,
            use_label_encoder=False,
            eval_metric="logloss"
        )
        model.fit(X_train_scaled, y_train)
        
        # Save pipelines and models (mode-specific directory)
        mdir = _model_dir()
        with open(os.path.join(mdir, "scaler.pkl"), "wb") as f:
            pickle.dump(scaler, f)
        with open(os.path.join(mdir, "encoders.pkl"), "wb") as f:
            pickle.dump(encoders, f)
        with open(os.path.join(mdir, "xgboost_model.pkl"), "wb") as f:
            pickle.dump(model, f)
        with open(os.path.join(mdir, "feature_names.pkl"), "wb") as f:
            pickle.dump(list(X.columns), f)
        with open(os.path.join(mdir, "lead_stats.pkl"), "wb") as f:
            pickle.dump(lead_stats, f)
            
        # Get feature importances
        importances = model.feature_importances_
        feature_importance_df = pd.DataFrame({
            'Feature': X.columns,
            'Importance': importances
        }).sort_values(by='Importance', ascending=False)
        
        print("XGBoost classifier pipeline completed successfully.")
        return {
            "feature_importance": feature_importance_df,
            "accuracy": float(model.score(X_test_scaled, y_test)),
            "train_size": len(X_train),
            "test_size": len(X_test)
        }, None
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"XGBoost pipeline error: {str(e)}"
    finally:
        session.close()

def get_lead_form_context():
    """
    Option lists and numeric ranges for the lead-scoring form, read from this
    tenant's own trained model so the form can only offer values the model saw.
    Returns None until the model has been trained.
    """
    try:
        mdir = _model_dir()
        with open(os.path.join(mdir, "encoders.pkl"), "rb") as f:
            encoders = pickle.load(f)
        with open(os.path.join(mdir, "lead_stats.pkl"), "rb") as f:
            stats = pickle.load(f)
    except Exception:
        return None
    options = {k: [c for c in le.classes_ if c != "Unknown"] or list(le.classes_) for k, le in encoders.items()}
    return {"options": options, "stats": stats}


def predict_deal_probability(input_data: dict) -> dict:
    """
    Predict probability of a deal closing based on model features.
    Provides feature contributions as a lightweight explainability layer.
    """
    try:
        # Load pipeline elements (mode-specific directory)
        mdir = _model_dir()
        with open(os.path.join(mdir, "scaler.pkl"), "rb") as f:
            scaler = pickle.load(f)
        with open(os.path.join(mdir, "encoders.pkl"), "rb") as f:
            encoders = pickle.load(f)
        with open(os.path.join(mdir, "xgboost_model.pkl"), "rb") as f:
            model = pickle.load(f)
        with open(os.path.join(mdir, "feature_names.pkl"), "rb") as f:
            feature_names = pickle.load(f)
            
        # Compile input into record
        # Must mirror the training feature set exactly (financing_type excluded).
        cat_features = ['marketing_channel', 'vehicle_category', 'fuel_type', 'region', 'occupation']
        num_features = ['base_price', 'discount_pct', 'age', 'annual_income', 'credit_score', 'loyalty_score']

        with open(os.path.join(mdir, "lead_stats.pkl"), "rb") as f:
            stats = pickle.load(f)

        # Anything not supplied falls back to what this tenant's model was trained on.
        record = {cat: input_data.get(cat, encoders[cat].classes_[0]) for cat in cat_features}
        record.update({num: float(input_data.get(num, stats.get(num, {}).get("p50", 0.0))) for num in num_features})
        
        # Build encoded DataFrame
        df_encoded = pd.DataFrame(index=[0])
        for cat in cat_features:
            le = encoders[cat]
            val = str(record[cat])
            # Handle unseen label gracefully
            if val not in le.classes_:
                val = le.classes_[0]
            df_encoded[cat] = le.transform([val])[0]
            
        for num in num_features:
            df_encoded[num] = record[num]
            
        # Scale numeric features
        df_encoded_scaled = df_encoded.copy()
        df_encoded_scaled[num_features] = scaler.transform(df_encoded[num_features])
        
        # Predict probability
        prob = float(model.predict_proba(df_encoded_scaled)[0, 1])
        
        # Dynamic Explainability (SHAP fallback or linear attribution)
        # `explainer_used` tells the caller which path actually ran so the UI can
        # label it honestly: "shap" = real per-instance TreeExplainer values,
        # "heuristic" = the 3-field rough estimate below (shap unavailable).
        shap_explanations = []
        explainer_used = "heuristic"
        try:
            import shap
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(df_encoded_scaled)
            explainer_used = "shap"

            # Attributions
            attribs = {}
            for name, val in zip(feature_names, shap_values[0]):
                attribs[name] = float(val)
                
            # Format nicely
            for name, score in attribs.items():
                influence = "positive" if score > 0 else "negative"
                desc = f"{name.replace('_', ' ').title()} has a {influence} effect ({score:+.3f})"
                shap_explanations.append({
                    "feature": name,
                    "score": score,
                    "direction": influence,
                    "description": desc
                })
            # Sort by absolute strength
            shap_explanations = sorted(shap_explanations, key=lambda x: abs(x['score']), reverse=True)
        except Exception:
            # Simple heuristic explanation based on model feature importances and raw bounds
            # This handles missing shap package or loading issues on older systems elegantly!
            importances = model.feature_importances_
            attribs = dict(zip(feature_names, importances))
            
            # Bigger discounts and stronger income/credit relative to THIS tenant's own
            # customers drive conversion; the quartiles come from its training data.
            discount = record['discount_pct']
            income = record['annual_income']
            credit = record['credit_score']
            q = lambda col: stats.get(col, {"p25": 0.0, "p75": 0.0})

            shap_explanations = [
                {
                    "feature": "discount_pct",
                    "score": 0.15 if discount > q("discount_pct")["p75"] else (-0.1 if discount < q("discount_pct")["p25"] else 0.02),
                    "direction": "positive" if discount >= q("discount_pct")["p25"] else "negative",
                    "description": f"Discount rate ({discount}%) drives conversion prospects."
                },
                {
                    "feature": "credit_score",
                    "score": 0.22 if credit > q("credit_score")["p75"] else (-0.25 if credit < q("credit_score")["p25"] else 0.05),
                    "direction": "positive" if credit >= q("credit_score")["p25"] else "negative",
                    "description": f"Credit score ({int(credit)}) affects closing eligibility."
                },
                {
                    "feature": "annual_income",
                    "score": 0.12 if income > q("annual_income")["p75"] else (-0.08 if income < q("annual_income")["p25"] else 0.01),
                    "direction": "positive" if income >= q("annual_income")["p25"] else "negative",
                    "description": f"Annual income ({fmt_money(income, compact=False)}) relative to this dealer group's customers."
                }
            ]
            shap_explanations = sorted(shap_explanations, key=lambda x: abs(x['score']), reverse=True)
            
        return {
            "close_probability": prob,
            "explanations": shap_explanations,
            "explainer_used": explainer_used,
        }
    except Exception as e:
        print(f"Prediction error: {e}")
        return {
            "close_probability": 0.5,
            "explainer_used": "none",
            "explanations": []
        }
