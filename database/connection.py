import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# Active data mode: "test" → automobile_demand.db, "real" → real_demand.db
_data_mode = "real"

_TEST_DB_URL = os.getenv("DATABASE_URL", "sqlite:///./automobile_demand.db")
_REAL_DB_URL = os.getenv("REAL_DATABASE_URL", "sqlite:///./real_demand.db")


def _build_engine(url):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url)


_test_engine = _build_engine(_TEST_DB_URL)
_real_engine = _build_engine(_REAL_DB_URL)

# `engine` stays as test engine alias — backward-compatible with seed_database.py
engine = _test_engine

Base = declarative_base()

_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
_RealSession = sessionmaker(autocommit=False, autoflush=False, bind=_real_engine)


def set_data_mode(mode: str):
    """Switch active data source: 'test' → automobile_demand.db, 'real' → real_demand.db."""
    global _data_mode
    if mode not in ("test", "real"):
        raise ValueError(f"Invalid data mode: {mode!r}. Use 'test' or 'real'.")
    _data_mode = mode


def get_data_mode() -> str:
    return _data_mode


def get_engine():
    return _test_engine if _data_mode == "test" else _real_engine


def get_db_session():
    factory = _TestSession if _data_mode == "test" else _RealSession
    db = factory()
    try:
        return db
    except Exception as e:
        db.close()
        raise e


def init_all_tables():
    """Create all tables in the currently active database (idempotent)."""
    import database.models  # noqa: F401
    Base.metadata.create_all(get_engine())
