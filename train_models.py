import os
import sys
import time

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from preprocessing.seed_database import main as seed_db
from ml_models.customer_segmentation import train_buyer_segmentation
from ml_models.xgboost_model import train_xgboost_pipeline
from forecasting.prophet_forecasting import train_prophet_model


def main():
    print("=" * 60)
    print("  Real Estate Demand Intelligence — Pipeline Runner")
    print("=" * 60)

    start_time = time.time()

    # 1. Seed Database
    print("\n[Step 1] Database Setup & Data Ingestion")
    try:
        seed_db()
    except Exception as e:
        print(f"Database seeding failed: {e}")
        sys.exit(1)

    # 2. Train KMeans Buyer Segmentation
    print("\n[Step 2] Training Buyer Segmentation Model (KMeans — 6 segments)")
    try:
        seg_res, err = train_buyer_segmentation(n_clusters=6)
        if err:
            print(f"  Buyer segmentation failed: {err}")
        else:
            seg_map = seg_res["cluster_mapping"]
            print(f"  Segments mapped: {list(seg_map.values())}")
    except Exception as e:
        print(f"  Buyer segmentation failed: {e}")

    # 3. Train XGBoost Booking Conversion Model
    print("\n[Step 3] Training Lead Scoring Model (XGBoost — booking_converted)")
    try:
        xgb_res, err = train_xgboost_pipeline()
        if err:
            print(f"  XGBoost training failed: {err}")
        else:
            print(f"  Accuracy: {xgb_res['accuracy']*100:.2f}%")
            print(f"  Top 5 features:\n{xgb_res['feature_importance'].head(5).to_string(index=False)}")
    except Exception as e:
        print(f"  XGBoost training failed: {e}")

    # 4. Verify Prophet Forecasting
    print("\n[Step 4] Verifying Prophet Demand Forecasting Pipeline")
    try:
        fore_res, err = train_prophet_model(
            property_category="Mid-Market",
            target="units",
            horizon_days=30,
        )
        if err:
            print(f"  Prophet verification failed: {err}")
        else:
            m = fore_res["metrics"]
            print(f"  Mid-Market forecast verified — Accuracy: {m['accuracy']:.1f}%, "
                  f"MAE: {m['mae']:.2f}, RMSE: {m['rmse']:.2f}")
            print(f"  Active regressors: {fore_res['active_regressors']}")
    except Exception as e:
        print(f"  Prophet verification failed: {e}")

    duration = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"  Pipeline complete in {duration:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
