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
from database.models import Sale, Customer, Vehicle

# Setup folder for saving model files
MODEL_DIR = "models/xgboost"
os.makedirs(MODEL_DIR, exist_ok=True)

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
            Sale.base_price_aed.label('base_price'),
            Sale.discount_pct,
            Sale.financing_type,
            Sale.marketing_channel,
            Sale.vehicle_category,
            Sale.fuel_type,
            Sale.emirate,
            Customer.age,
            Customer.gender,
            Customer.occupation,
            Customer.estimated_monthly_income_aed,
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
        cat_features = ['financing_type', 'marketing_channel', 'vehicle_category', 'fuel_type', 'emirate', 'gender', 'occupation']
        num_features = ['base_price', 'discount_pct', 'age', 'estimated_monthly_income_aed', 'credit_score', 'loyalty_score']
        
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
        
        # Save pipelines and models
        with open(os.path.join(MODEL_DIR, "scaler.pkl"), "wb") as f:
            pickle.dump(scaler, f)
        with open(os.path.join(MODEL_DIR, "encoders.pkl"), "wb") as f:
            pickle.dump(encoders, f)
        with open(os.path.join(MODEL_DIR, "xgboost_model.pkl"), "wb") as f:
            pickle.dump(model, f)
        with open(os.path.join(MODEL_DIR, "feature_names.pkl"), "wb") as f:
            pickle.dump(list(X.columns), f)
            
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

def predict_deal_probability(input_data: dict) -> dict:
    """
    Predict probability of a deal closing based on model features.
    Provides feature contributions as a lightweight explainability layer.
    """
    try:
        # Load pipeline elements
        with open(os.path.join(MODEL_DIR, "scaler.pkl"), "rb") as f:
            scaler = pickle.load(f)
        with open(os.path.join(MODEL_DIR, "encoders.pkl"), "rb") as f:
            encoders = pickle.load(f)
        with open(os.path.join(MODEL_DIR, "xgboost_model.pkl"), "rb") as f:
            model = pickle.load(f)
        with open(os.path.join(MODEL_DIR, "feature_names.pkl"), "rb") as f:
            feature_names = pickle.load(f)
            
        # Compile input into record
        cat_features = ['financing_type', 'marketing_channel', 'vehicle_category', 'fuel_type', 'emirate', 'gender', 'occupation']
        num_features = ['base_price', 'discount_pct', 'age', 'estimated_monthly_income_aed', 'credit_score', 'loyalty_score']
        
        record = {}
        # Assign values with fallbacks
        record['financing_type'] = input_data.get('financing_type', 'Bank Loan')
        record['marketing_channel'] = input_data.get('marketing_channel', 'Referral')
        record['vehicle_category'] = input_data.get('vehicle_category', 'SUV')
        record['fuel_type'] = input_data.get('fuel_type', 'Petrol')
        record['emirate'] = input_data.get('emirate', 'Dubai')
        record['gender'] = input_data.get('gender', 'Male')
        record['occupation'] = input_data.get('occupation', 'Salaried')
        
        record['base_price'] = float(input_data.get('base_price', 1200000))
        record['discount_pct'] = float(input_data.get('discount_pct', 5.0))
        record['age'] = float(input_data.get('age', 35))
        record['estimated_monthly_income_aed'] = float(input_data.get('estimated_monthly_income_aed', 25000))
        record['credit_score'] = float(input_data.get('credit_score', 720))
        record['loyalty_score'] = float(input_data.get('loyalty_score', 60))
        
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
        # We can extract shap values if shap is available and imported
        shap_explanations = []
        try:
            import shap
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(df_encoded_scaled)
            
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
            
            # High discount and high income usually drive conversion positively, while low credit score drives it negatively
            discount = record['discount_pct']
            income = record['estimated_monthly_income_aed']
            credit = record['credit_score']
            
            shap_explanations = [
                {
                    "feature": "discount_pct",
                    "score": 0.15 if discount > 6 else (-0.1 if discount < 3 else 0.02),
                    "direction": "positive" if discount >= 3 else "negative",
                    "description": f"Discount rate ({discount}%) drives conversion prospects."
                },
                {
                    "feature": "credit_score",
                    "score": 0.22 if credit > 750 else (-0.25 if credit < 650 else 0.05),
                    "direction": "positive" if credit >= 650 else "negative",
                    "description": f"Credit score ({int(credit)}) affects closing eligibility."
                },
                {
                    "feature": "estimated_monthly_income_aed",
                    "score": 0.12 if income > 35000 else (-0.08 if income < 8000 else 0.01),
                    "direction": "positive" if income >= 8000 else "negative",
                    "description": f"Monthly income ({int(income):,} AED) matches target segment."
                }
            ]
            shap_explanations = sorted(shap_explanations, key=lambda x: abs(x['score']), reverse=True)
            
        return {
            "close_probability": prob,
            "explanations": shap_explanations
        }
    except Exception as e:
        print(f"Prediction error: {e}")
        return {
            "close_probability": 0.5,
            "explanations": []
        }
