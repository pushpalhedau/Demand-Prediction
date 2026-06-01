import os
import sys
import pandas as pd
from datetime import datetime

# Add the project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import Base, engine, get_db_session
from database.models import Customer, Vehicle, Dealer, Sale, Inventory, ExternalFactor, Registration, StateProfile, IndiaExternalFactor
from preprocessing.clean_data import (
    clean_customers,
    clean_vehicles,
    clean_dealers,
    clean_sales,
    clean_inventory,
    clean_external_factors,
    clean_registrations,
    clean_state_profiles,
    clean_india_external_factors,
    clean_india_vehicles,
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

def seed_india(session):
    """Seed India/VAHAN tables from automobile_datasets/india/."""
    india_dir = os.path.join("automobile_datasets", "india")

    registrations_path = os.path.join(india_dir, "registrations.csv")
    ext_factors_path = os.path.join(india_dir, "india_external_factors.csv")
    vehicles_path = os.path.join(india_dir, "india_vehicles.csv")
    state_profiles_path = os.path.join(india_dir, "state_profiles.csv")

    # 1. India vehicles (reuse Vehicle model)
    if os.path.exists(vehicles_path) and session.query(Vehicle).filter(Vehicle.gcc_spec == False).count() == 0:
        df_v = clean_india_vehicles(vehicles_path)
        seed_table(session, df_v, Vehicle, "india_vehicles")

    # 2. State profiles (if CSV present; otherwise skip)
    if os.path.exists(state_profiles_path) and session.query(StateProfile).count() == 0:
        df_sp = clean_state_profiles(state_profiles_path)
        seed_table(session, df_sp, StateProfile, "state_profiles")

    # 3. India external factors
    if os.path.exists(ext_factors_path) and session.query(IndiaExternalFactor).count() == 0:
        df_ext = clean_india_external_factors(ext_factors_path)
        seed_table(session, df_ext, IndiaExternalFactor, "india_external_factors")

    # 4. VAHAN registrations (largest table — only if extracted)
    if os.path.exists(registrations_path) and session.query(Registration).count() == 0:
        df_reg = clean_registrations(registrations_path)
        seed_table(session, df_reg, Registration, "registrations")
    elif not os.path.exists(registrations_path):
        print(
            "registrations.csv not found — run automobile_datasets/india/vahan_extractor.py first.",
            file=sys.stderr,
        )


def main():
    print("Initializing Database Seeding Pipeline...")

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
        # ── UAE legacy seeding (skip if already done) ─────────────────────
        if session.query(Sale).count() > 0:
            print("UAE tables already seeded, skipping UAE seed.")
        else:
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

            print("UAE datasets seeded successfully!")

        # ── India / VAHAN seeding ─────────────────────────────────────────
        print("\nSeeding India/VAHAN tables...")
        seed_india(session)
        print("India seeding complete!")

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
