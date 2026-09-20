from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sqlalchemy import func
from xgboost import XGBClassifier

from backend.core.errors import AppError
from backend.core.formatting import fmt_money
from backend.core.log import get_logger
from backend.db.connection import get_db_session
from backend.db.models import Customer, Sale, Vehicle
from backend.ml.artifacts import load_artifact, model_dir, save_artifact

log = get_logger(__name__)



MIN_ROWS = 100            # sales linked to customers needed to fit anything meaningful
MIN_CLASS = 10            # and at least this many won AND lost test drives
COVERAGE_MIN = 0.05       # a feature with data on fewer rows than this is treated as absent
WEAK_AUC = 0.60           # below this the score barely ranks leads better than chance
MODEL_FILES = ("scaler", "encoders", "xgboost_model", "feature_names", "lead_stats")
STATUS_FILE = "lead_status"
CAT_FEATURES = ['marketing_channel', 'vehicle_category', 'fuel_type', 'region', 'occupation']
NUM_FEATURES = ['base_price', 'discount_pct', 'age', 'annual_income', 'credit_score', 'loyalty_score']


def _model_dir() -> Path:
    """Per-tenant artifact directory."""
    return model_dir("xgboost")


def training_problem(rows: int, converted: int, sales_rows: int) -> str | None:
    """A specific, actionable reason this account's data cannot train a lead-close model, or None if it can."""
    if rows == 0 and sales_rows:
        return ("None of this account's sales are linked to a customer, so there is nothing to learn from. "
                "Sales need a customer_id that matches the customers file.")
    if rows == 0:
        return "This account has no sales linked to customers yet, so the lead-close model cannot be trained."
    if rows < MIN_ROWS:
        return f"Only {rows} sales are linked to customers; at least {MIN_ROWS} are needed to train the lead-close model."
    lost = rows - converted
    if min(converted, lost) < MIN_CLASS:
        return (f"The lead-close model needs both won and lost test drives to learn from: found {converted} converted "
                f"and {lost} not converted (at least {MIN_CLASS} of each are required). "
                "Check the test-drive converted column in the sales file.")
    return None


def _write_status(mdir: Path, state: str, **fields) -> None:
    save_artifact(mdir, STATUS_FILE, {"state": state, "trained_at": datetime.now(UTC).isoformat(timespec="seconds"), **fields})


def _clear_model(mdir: Path) -> None:
    """Drop a previous model so a failed retrain can never leave stale scores running on new data."""
    for name in MODEL_FILES:
        (mdir / f"{name}.pkl").unlink(missing_ok=True)


def get_lead_status() -> dict:
    """Outcome of this account's last lead-close training: not_trained, trained, or cannot_train (with the reason)."""
    try:
        return load_artifact(_model_dir(), STATUS_FILE)
    except Exception:  # noqa: BLE001 - no (or unreadable) status file simply means it has not been trained
        return {"state": "not_trained"}

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

        # Target column: test_drive_converted (binary classification)
        df['test_drive_converted'] = df['test_drive_converted'].fillna(False).astype(int)

        problem = training_problem(len(df), int(df['test_drive_converted'].sum()),
                                   session.query(func.count(Sale.sale_id)).scalar() or 0)
        if problem:
            mdir = _model_dir()
            _clear_model(mdir)
            _write_status(mdir, "cannot_train", message=problem)
            return None, problem

        # How much real data each feature has (measured before gaps are filled), so the app can say so honestly.
        coverage = {c: float(df[c].notna().mean()) for c in CAT_FEATURES + NUM_FEATURES}
        missing_features = [c for c, v in coverage.items() if v < COVERAGE_MIN]

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
        cat_features, num_features = CAT_FEATURES, NUM_FEATURES

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
        save_artifact(mdir, "scaler", scaler)
        save_artifact(mdir, "encoders", encoders)
        save_artifact(mdir, "xgboost_model", model)
        save_artifact(mdir, "feature_names", list(X.columns))
        save_artifact(mdir, "lead_stats", lead_stats)

        holdout = float(model.score(X_test_scaled, y_test))
        baseline = float(max(y_test.mean(), 1 - y_test.mean()))
        # Ranking quality on unseen leads (0.5 = coin flip, 1.0 = perfect): what matters for prioritising leads.
        auc = float(roc_auc_score(y_test, model.predict_proba(X_test_scaled)[:, 1]))
        _write_status(mdir, "trained", rows=int(len(df)), converted=int(y.sum()), holdout_accuracy=holdout,
                      baseline_accuracy=baseline, holdout_auc=auc, weak=auc < WEAK_AUC, coverage=coverage,
                      missing_features=missing_features)

        # Get feature importances
        importances = model.feature_importances_
        feature_importance_df = pd.DataFrame({
            'Feature': X.columns,
            'Importance': importances
        }).sort_values(by='Importance', ascending=False)

        log.info("XGBoost classifier pipeline completed successfully.")
        return {
            "feature_importance": feature_importance_df,
            "accuracy": holdout,
            "auc": auc,
            "train_size": len(X_train),
            "test_size": len(X_test)
        }, None

    except Exception:
        log.exception("The lead-scoring model could not be trained")
        return None, "The lead-scoring model could not be trained. Please contact support."
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
        encoders = load_artifact(mdir, "encoders")
        stats = load_artifact(mdir, "lead_stats")
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
        scaler = load_artifact(mdir, "scaler")
        encoders = load_artifact(mdir, "encoders")
        model = load_artifact(mdir, "xgboost_model")
        feature_names = load_artifact(mdir, "feature_names")

        # Compile input into record
        # Must mirror the training feature set exactly (financing_type excluded).
        cat_features, num_features = CAT_FEATURES, NUM_FEATURES

        stats = load_artifact(mdir, "lead_stats")

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
            def q(col):
                return stats.get(col, {"p25": 0.0, "p75": 0.0})


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
    except Exception:
        log.warning("Prediction failed", exc_info=True)
        raise AppError("The lead-close model is not available for this account right now. "
                       "Ask your administrator to retrain the models.") from None
