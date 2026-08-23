import os
import sys
import pandas as pd
from datetime import datetime

# Add the project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import Base, engine, get_db_session, set_data_mode
from database.models import Customer, Vehicle, Dealer, Sale, Inventory, ExternalFactor
from preprocessing.clean_data import (
    clean_customers,
    clean_vehicles,
    clean_dealers,
    clean_sales,
    clean_inventory,
    clean_external_factors
)

def seed_table(session, df, model_class, name):
    """
    Seeds a table using bulk_insert_mappings for maximum performance.
    """
    print(f"Seeding {name}...")
    start_time = datetime.now()
    
    # Drop columns that are not in the model_class columns
    valid_cols = {col.name for col in model_class.__table__.columns}
    df_filtered = df[[col for col in df.columns if col in valid_cols]]
    
    # Replace NaN or NaT with None for SQL compatibility
    df_filtered = df_filtered.astype(object).where(pd.notnull(df_filtered), None)
    
    # Convert records to dictionary mappings
    records = df_filtered.to_dict(orient="records")
    
    # Bulk insert
    session.bulk_insert_mappings(model_class, records)
    session.commit()
    
    duration = (datetime.now() - start_time).total_seconds()
    print(f"Successfully seeded {len(records)} records into {name} in {duration:.2f} seconds.")

def main():
    print("Initializing Database Seeding Pipeline...")
    set_data_mode("test")  # ensure get_db_session() targets automobile_demand.db, not real_demand.db

    # Create all tables in database
    print("Creating all tables in the database if they don't exist...")
    Base.metadata.create_all(engine)
    
    # Paths to the CSV files
    dataset_dir = "automobile_datasets"
    
    customers_path = os.path.join(dataset_dir, "customers.csv")
    vehicles_path = os.path.join(dataset_dir, "vehicles.csv")
    dealers_path = os.path.join(dataset_dir, "dealers.csv")
    sales_path = os.path.join(dataset_dir, "sales.csv")
    inventory_path = os.path.join(dataset_dir, "inventory.csv")
    external_factors_path = os.path.join(dataset_dir, "external_factors.csv")
    
    # Start Session
    session = get_db_session()
    
    try:
        # Check if already seeded (simple count check)
        if session.query(Sale).count() > 0:
            print("Database already seeded! Skipping seeding process.")
            return
        
        # 1. Vehicles
        df_vehicles = clean_vehicles(vehicles_path)
        seed_table(session, df_vehicles, Vehicle, "vehicles")
        
        # 2. Dealers
        df_dealers = clean_dealers(dealers_path)
        seed_table(session, df_dealers, Dealer, "dealers")
        
        # 3. Customers
        df_customers = clean_customers(customers_path)
        seed_table(session, df_customers, Customer, "customers")
        
        # 4. External Factors
        df_ext = clean_external_factors(external_factors_path)
        seed_table(session, df_ext, ExternalFactor, "external_factors")
        
        # 5. Sales (transactions)
        df_sales = clean_sales(sales_path)
        seed_table(session, df_sales, Sale, "sales")
        
        # 6. Inventory
        df_inv = clean_inventory(inventory_path)
        seed_table(session, df_inv, Inventory, "inventory")
        
        print("\nAll datasets seeded successfully!")
        
    except Exception as e:
        session.rollback()
        print(f"Error seeding database: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    main()
