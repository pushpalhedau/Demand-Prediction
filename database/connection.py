import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./real_estate_demand.db")

# Create engine
# For SQLite, we want to allow multithreaded access from Streamlit
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base
Base = declarative_base()

def get_db_session():
    """
    Context manager or utility to get database session.
    """
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        raise e


def init_all_tables():
    """
    Create all tables registered with Base (idempotent — safe to call multiple times).
    Called by the sentiment module at startup to ensure new tables exist even when
    train_models.py has not been re-run after adding the sentiment models.
    """
    # Import models here to ensure all ORM classes are registered with Base
    import database.models  # noqa: F401
    Base.metadata.create_all(engine)
