import os
import sys
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import Base, engine, get_db_session
from database.models import (
    Transaction, Buyer, Developer, Property, Listing, MarketFactor,
    LeadPipeline, ConstructionTracker, Contractor, Financial,
    CompetitorMarket, RentalMarket, DocumentRegistry,
)
from preprocessing.clean_data import (
    clean_transactions,
    clean_buyers,
    clean_developers,
    clean_properties,
    clean_listings,
    clean_market_factors,
    clean_leads_pipeline,
    clean_construction_tracker,
    clean_contractors,
    clean_financials,
    clean_competitor_market,
    clean_rental_market,
    clean_documents_registry,
)


def seed_table(session, df, model_class, name, ignore_duplicates=False):
    print(f"Seeding {name}...")
    start_time = datetime.now()

    valid_cols = {col.name for col in model_class.__table__.columns}
    df_filtered = df[[col for col in df.columns if col in valid_cols]]
    df_filtered = df_filtered.astype(object).where(pd.notnull(df_filtered), None)
    records = df_filtered.to_dict(orient="records")

    if ignore_duplicates:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        stmt = sqlite_insert(model_class.__table__).prefix_with("OR IGNORE")
        session.execute(stmt, records)
    else:
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
        txn_count = session.query(Transaction).count()
        new_tables_empty = session.query(Financial).count() == 0

        if txn_count > 0 and not new_tables_empty:
            print("Database already fully seeded (13 tables). Skipping.")
            return

        if txn_count > 0 and new_tables_empty:
            print("Existing 6 tables found. Seeding only the 7 new tables...")
            Base.metadata.create_all(engine)
            seed_table(session, clean_leads_pipeline(os.path.join(dataset_dir, "re_leads_pipeline.csv")), LeadPipeline, "leads_pipeline", ignore_duplicates=True)
            seed_table(session, clean_construction_tracker(os.path.join(dataset_dir, "re_construction_tracker.csv")), ConstructionTracker, "construction_tracker", ignore_duplicates=True)
            seed_table(session, clean_contractors(os.path.join(dataset_dir, "re_contractors.csv")), Contractor, "contractors", ignore_duplicates=True)
            seed_table(session, clean_financials(os.path.join(dataset_dir, "re_financials.csv")), Financial, "financials", ignore_duplicates=True)
            seed_table(session, clean_competitor_market(os.path.join(dataset_dir, "re_competitor_market.csv")), CompetitorMarket, "competitor_market", ignore_duplicates=True)
            seed_table(session, clean_rental_market(os.path.join(dataset_dir, "re_rental_market.csv")), RentalMarket, "rental_market", ignore_duplicates=True)
            seed_table(session, clean_documents_registry(os.path.join(dataset_dir, "re_documents_registry.csv")), DocumentRegistry, "documents_registry", ignore_duplicates=True)
            print("\n7 new tables seeded successfully!")
            return

        # Clear any partial data from prior failed runs
        for model in [
            Transaction, Listing, Property, Buyer, MarketFactor, Developer,
            LeadPipeline, ConstructionTracker, Contractor, Financial,
            CompetitorMarket, RentalMarket, DocumentRegistry,
        ]:
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

        # 7-13. New tables (no FK dependencies on existing tables)
        seed_table(session, clean_leads_pipeline(os.path.join(dataset_dir, "re_leads_pipeline.csv")), LeadPipeline, "leads_pipeline")
        seed_table(session, clean_construction_tracker(os.path.join(dataset_dir, "re_construction_tracker.csv")), ConstructionTracker, "construction_tracker")
        seed_table(session, clean_contractors(os.path.join(dataset_dir, "re_contractors.csv")), Contractor, "contractors")
        seed_table(session, clean_financials(os.path.join(dataset_dir, "re_financials.csv")), Financial, "financials")
        seed_table(session, clean_competitor_market(os.path.join(dataset_dir, "re_competitor_market.csv")), CompetitorMarket, "competitor_market")
        seed_table(session, clean_rental_market(os.path.join(dataset_dir, "re_rental_market.csv")), RentalMarket, "rental_market")
        seed_table(session, clean_documents_registry(os.path.join(dataset_dir, "re_documents_registry.csv")), DocumentRegistry, "documents_registry")

        print("\nAll 13 datasets seeded successfully!")

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
