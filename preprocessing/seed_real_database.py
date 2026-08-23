"""
Seed real_demand.db from the realdata-datasets folder.

realdata-datasets and automobile_datasets share the same NA column schema,
so this simply cleans and loads each CSV directly (no column renaming needed).
"""

import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.models import Customer, Vehicle, Dealer, Sale, Inventory, ExternalFactor
from preprocessing.clean_data import (
    clean_customers,
    clean_vehicles,
    clean_dealers,
    clean_sales,
    clean_inventory,
    clean_external_factors,
)

REAL_DB_URL = os.getenv("REAL_DATABASE_URL", "sqlite:///./real_demand.db")
REALDATA_DIR = os.path.join(os.path.dirname(__file__), "..", "realdata-datasets")


def _build_engine():
    if REAL_DB_URL.startswith("sqlite"):
        return create_engine(REAL_DB_URL, connect_args={"check_same_thread": False})
    return create_engine(REAL_DB_URL)


def _seed_table(session, df: pd.DataFrame, model_class, name: str):
    print(f"  Seeding {name}...")
    start = datetime.now()
    valid_cols = {col.name for col in model_class.__table__.columns}
    df_f = df[[c for c in df.columns if c in valid_cols]]
    df_f = df_f.astype(object).where(pd.notnull(df_f), None)
    records = df_f.to_dict(orient="records")
    session.bulk_insert_mappings(model_class, records)
    session.commit()
    elapsed = (datetime.now() - start).total_seconds()
    print(f"  > {len(records):,} records in {elapsed:.2f}s")


def main():
    print("=" * 52)
    print("   Real Database Seeding Pipeline (realdata-datasets)")
    print("=" * 52)

    real_engine = _build_engine()
    Base.metadata.create_all(real_engine)
    RealSession = sessionmaker(autocommit=False, autoflush=False, bind=real_engine)
    session = RealSession()

    try:
        if session.query(Sale).count() > 0:
            print("Dropping existing data for fresh reseed...")
            session.query(Sale).delete()
            session.query(Inventory).delete()
            session.query(ExternalFactor).delete()
            session.query(Customer).delete()
            session.query(Dealer).delete()
            session.query(Vehicle).delete()
            session.commit()

        base = REALDATA_DIR

        # 1. Vehicles
        print("\n[1/6] Vehicles")
        _seed_table(session, clean_vehicles(os.path.join(base, "vehicles.csv")), Vehicle, "vehicles")

        # 2. Dealers
        print("[2/6] Dealers")
        _seed_table(session, clean_dealers(os.path.join(base, "dealers.csv")), Dealer, "dealers")

        # 3. Customers
        print("[3/6] Customers")
        _seed_table(session, clean_customers(os.path.join(base, "customers.csv")), Customer, "customers")

        # 4. External Factors
        print("[4/6] External Factors")
        _seed_table(session, clean_external_factors(os.path.join(base, "external_factors.csv")), ExternalFactor, "external_factors")

        # 5. Sales
        print("[5/6] Sales")
        _seed_table(session, clean_sales(os.path.join(base, "sales.csv")), Sale, "sales")

        # 6. Inventory
        print("[6/6] Inventory")
        _seed_table(session, clean_inventory(os.path.join(base, "inventory.csv")), Inventory, "inventory")

        print("\nReal database seeded successfully!")

    except Exception as e:
        session.rollback()
        print(f"Error seeding real database: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
