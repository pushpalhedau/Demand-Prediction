"""
Seed real_demand.db from the realdata-datasets folder.

Column differences between realdata-datasets and the UAE ORM schema are resolved
by renaming columns in-memory (via StringIO) before passing to the existing
clean_* functions in clean_data.py. No temp files are written to disk.
"""

import io
import os
import sys
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

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


def _to_buf(df: pd.DataFrame) -> io.StringIO:
    """Serialize a DataFrame to a StringIO CSV buffer (pd.read_csv-compatible)."""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


def _prep_vehicles(path: str) -> io.StringIO:
    df = pd.read_csv(path)
    df = df.rename(columns={
        "ex_showroom_price_aed": "price_aed",
        "safety_rating_ncap": "safety_rating",
    })
    for col, default in [
        ("drive_type", "2WD"),
        ("horsepower", None),
        ("vat_inclusive_price", 0),
        ("service_contract_available", False),
        ("gcc_spec", True),
    ]:
        if col not in df.columns:
            df[col] = default
    return _to_buf(df)


def _prep_customers(path: str) -> io.StringIO:
    df = pd.read_csv(path)
    df = df.rename(columns={
        "region": "emirate",
        "city": "area",
        "annual_income_bracket_aed": "monthly_income_bracket",
        "estimated_annual_income_aed": "estimated_monthly_income_aed",
    })
    for col, default in [
        ("emirates_id", None),
        ("resident_type", "Resident"),
        ("years_in_uae", 5),
        ("visa_expiry_year", 2030),
    ]:
        if col not in df.columns:
            df[col] = default
    return _to_buf(df)


def _prep_dealers(path: str) -> io.StringIO:
    df = pd.read_csv(path)
    df = df.rename(columns={
        "region": "emirate",
        "city": "area",
        "rating": "google_rating",
    })
    for col, default in [
        ("address", None),
        ("po_box", None),
        ("vat_registered", True),
        ("trn_number", None),
    ]:
        if col not in df.columns:
            df[col] = default
    return _to_buf(df)


def _prep_sales(path: str) -> io.StringIO:
    df = pd.read_csv(path)
    df = df.rename(columns={
        "region": "emirate",
        "city": "area",
    })
    if "vat_amount_aed" not in df.columns:
        df["vat_amount_aed"] = (df["selling_price_aed"] * 0.05).round().astype(int)
    if "total_revenue_excl_vat" not in df.columns:
        df["total_revenue_excl_vat"] = (
            df["selling_price_aed"]
            + df.get("accessories_revenue_aed", pd.Series(0, index=df.index))
            + df.get("insurance_revenue_aed", pd.Series(0, index=df.index))
            + df.get("extended_warranty_aed", pd.Series(0, index=df.index))
        ).astype(int)
    if "total_revenue_incl_vat" not in df.columns:
        df["total_revenue_incl_vat"] = (
            df["total_revenue_excl_vat"] + df["vat_amount_aed"]
        ).astype(int)
    for col, default in [("gcc_spec", True), ("export_sale", False)]:
        if col not in df.columns:
            df[col] = default
    return _to_buf(df)


def _prep_inventory(path: str) -> io.StringIO:
    df = pd.read_csv(path)
    df = df.rename(columns={
        "region": "emirate",
        "city": "area",
        "warehouse_location": "warehouse_zone",
    })
    for col, default in [("port_of_entry", "Port of Entry"), ("customs_cleared", True)]:
        if col not in df.columns:
            df[col] = default
    return _to_buf(df)


def _prep_external_factors(path: str) -> io.StringIO:
    df = pd.read_csv(path)
    df = df.rename(columns={
        "region": "emirate",
        "petrol_super98_aed": "petrol_98_price_aed_per_litre",
        "petrol_special95_aed": "petrol_95_price_aed_per_litre",
        "diesel_aed": "diesel_price_aed_per_litre",
        "brent_crude_usd": "crude_oil_price_usd",
        "uae_base_rate_pct": "us_fed_rate_pct",
        "festival_month": "ramadan_month",
        "vehicle_registration_tax_vat_pct": "import_duty_pct",
        "road_cess_pct": "vat_rate_pct",
    })
    # Add UAE-specific columns that are absent from the real dataset
    for col, default in [
        ("tourism_index", 50.0),
        ("dubai_re_price_index", 100.0),
        ("luxury_demand_index", 50.0),
        ("expo_2020_active", 0),
        ("national_day_month", 0),
        ("dubai_motor_show", 0),
        ("abu_dhabi_motor_show", 0),
        ("population_millions", 3.5),
        ("ev_charging_stations_uae", 0),
    ]:
        if col not in df.columns:
            df[col] = default
    return _to_buf(df)


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
        _seed_table(session, clean_vehicles(_prep_vehicles(os.path.join(base, "vehicles.csv"))), Vehicle, "vehicles")

        # 2. Dealers
        print("[2/6] Dealers")
        _seed_table(session, clean_dealers(_prep_dealers(os.path.join(base, "dealers.csv"))), Dealer, "dealers")

        # 3. Customers
        print("[3/6] Customers")
        _seed_table(session, clean_customers(_prep_customers(os.path.join(base, "customers.csv"))), Customer, "customers")

        # 4. External Factors
        print("[4/6] External Factors")
        _seed_table(session, clean_external_factors(_prep_external_factors(os.path.join(base, "external_factors.csv"))), ExternalFactor, "external_factors")

        # 5. Sales
        print("[5/6] Sales")
        _seed_table(session, clean_sales(_prep_sales(os.path.join(base, "sales.csv"))), Sale, "sales")

        # 6. Inventory
        print("[6/6] Inventory")
        _seed_table(session, clean_inventory(_prep_inventory(os.path.join(base, "inventory.csv"))), Inventory, "inventory")

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
