import os
import sys
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import Base, engine, get_db_session
from database.models import Transaction, Buyer, Developer, Property, Listing, MarketFactor
from preprocessing.clean_data import (
    clean_transactions,
    clean_buyers,
    clean_developers,
    clean_properties,
    clean_listings,
    clean_market_factors,
)


def seed_table(session, df, model_class, name):
    print(f"Seeding {name}...")
    start_time = datetime.now()

    valid_cols = {col.name for col in model_class.__table__.columns}
    df_filtered = df[[col for col in df.columns if col in valid_cols]]
    df_filtered = df_filtered.astype(object).where(pd.notnull(df_filtered), None)
    records = df_filtered.to_dict(orient="records")

    session.bulk_insert_mappings(model_class, records)
    session.commit()

    duration = (datetime.now() - start_time).total_seconds()
    print(f"  >> {len(records):,} records into {name} in {duration:.2f}s")


def main():
    print("=" * 60)
    print("Real Estate Demand Intelligence — Database Seeding Pipeline")
    print("=" * 60)

    Base.metadata.create_all(engine)
    print("Database tables created (or verified).")

    dataset_dir = "datasets"
    session = get_db_session()

    try:
        if session.query(Transaction).count() > 0:
            print("Database already seeded (transactions present). Skipping.")
            return

        # Clear any partial data from prior failed runs
        from database.models import Listing
        for model in [Transaction, Listing, Property, Buyer, MarketFactor, Developer]:
            session.query(model).delete()
        session.commit()
        print("Cleared partial data from prior run.")

        # 1. Developers (no FK dependencies)
        df_developers = clean_developers(os.path.join(dataset_dir, "re_developers.csv"))
        seed_table(session, df_developers, Developer, "developers")

        # 2. Properties (depends on developers)
        df_properties = clean_properties(os.path.join(dataset_dir, "re_properties.csv"))
        seed_table(session, df_properties, Property, "properties")

        # 3. Buyers (no FK dependencies)
        df_buyers = clean_buyers(os.path.join(dataset_dir, "re_buyers.csv"))
        seed_table(session, df_buyers, Buyer, "buyers")

        # 4. Market Factors (no FK dependencies)
        df_market = clean_market_factors(os.path.join(dataset_dir, "re_market_factors.csv"))
        seed_table(session, df_market, MarketFactor, "market_factors")

        # 5. Transactions (depends on buyers, developers, properties)
        df_transactions = clean_transactions(os.path.join(dataset_dir, "re_transactions.csv"))
        seed_table(session, df_transactions, Transaction, "transactions")

        # 6. Listings (depends on developers)
        df_listings = clean_listings(os.path.join(dataset_dir, "re_listings.csv"))
        seed_table(session, df_listings, Listing, "listings")

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
