import os
import sys
import time

# Add the project root to python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from preprocessing.seed_database import main as seed_db
from ml_models.customer_segmentation import train_customer_segmentation
from ml_models.xgboost_model import train_xgboost_pipeline
from forecasting.prophet_forecasting import train_prophet_model

def main():
    print("====================================================")
    print("      AUTOMOBILE DEMAND PLATFORM PIPELINE RUNNER     ")
    print("====================================================")
    
    start_time = time.time()
    
    # 1. Seed Database
    print("\n--- Step 1: Database Setup and Ingestion ---")
    try:
        seed_db()
    except Exception as e:
        print(f"Database seeding failed: {e}")
        sys.exit(1)
        
    # 2. Train KMeans Customer Segmentation
    print("\n--- Step 2: Training Customer Segmentation Model (KMeans) ---")
    try:
        seg_res, err = train_customer_segmentation(n_clusters=5)
        if err:
            print(f"Customer segmentation failed: {err}")
        else:
            print(f"Customer segmentation trained. Mapped segments: {list(seg_res['cluster_mapping'].values())}")
    except Exception as e:
        print(f"Customer segmentation failed: {e}")
        
    # 3. Train XGBoost Conversion Model
    print("\n--- Step 3: Training Lead Close Classifier (XGBoost) ---")
    try:
        xgb_res, err = train_xgboost_pipeline()
        if err:
            print(f"XGBoost training failed: {err}")
        else:
            print(f"XGBoost model trained. Evaluation Accuracy: {xgb_res['accuracy']*100:.2f}%")
            print("Top features influencing closes:")
            print(xgb_res['feature_importance'].head(5))
    except Exception as e:
        print(f"XGBoost training failed: {e}")
        
    # 4. Verify Prophet Forecasting Pipeline
    print("\n--- Step 4: Verifying Prophet Forecasting Pipeline ---")
    try:
        # Run a default category forecast for verification
        fore_res, err = train_prophet_model(category="SUV", region=None, horizon_days=30)
        if err:
            print(f"Prophet verification failed: {err}")
        else:
            metrics = fore_res["metrics"]
            print(f"Prophet forecasting pipeline verified successfully.")
            print(f"SUV Forecast Model evaluation - RMSE: {metrics['rmse']:.2f}, Accuracy: {metrics['accuracy']:.2f}%")
    except Exception as e:
        print(f"Prophet verification failed: {e}")
        
    duration = time.time() - start_time
    print("\n====================================================")
    print(f" Pipeline run completed successfully in {duration:.1f} seconds! ")
    print("====================================================")

if __name__ == "__main__":
    main()
