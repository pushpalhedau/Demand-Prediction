import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.core.tenant_context import current_tenant_id

load_dotenv()

Base = declarative_base()

_DEFAULT_APP_URL = "postgresql+psycopg2://predictax_app:predictax_app_dev@localhost:5432/predictax"
_DEFAULT_ADMIN_URL = "postgresql+psycopg2://predictax_owner:predictax_owner_dev@localhost:5432/predictax"

_APP_URL = os.getenv("DATABASE_URL") or _DEFAULT_APP_URL
_ADMIN_URL = os.getenv("ADMIN_DATABASE_URL") or _DEFAULT_ADMIN_URL


def _build_engine(url: str):
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        pool_recycle=1800,
    )


# App engine: restricted role, row-level security enforced.
_app_engine = _build_engine(_APP_URL)
# Admin engine: table owner. Migrations and tenant provisioning ONLY.
_admin_engine = _build_engine(_ADMIN_URL)

# Kept so `from database.connection import engine` in scripts still resolves.
engine = _app_engine


@event.listens_for(_app_engine, "begin")
def _bind_tenant_to_transaction(conn):
    """
    Pin the transaction to the active tenant. set_config(..., true) is
    transaction-local, so it is safe with pooled/PgBouncer connections: it can
    never leak to the next borrower of the same physical connection.
    """
    tid = current_tenant_id()
    if tid is not None:
        conn.exec_driver_sql("SELECT set_config('app.current_tenant_id', %s, true)", (str(tid),))


_AppSession = sessionmaker(autocommit=False, autoflush=False, bind=_app_engine)
_AdminSession = sessionmaker(autocommit=False, autoflush=False, bind=_admin_engine)


def get_engine():
    """Tenant-scoped engine (RLS enforced). Use for pd.read_sql and raw SQL."""
    return _app_engine


def get_admin_engine():
    return _admin_engine


def get_db_session():
    """Tenant-scoped session. The tenant comes from tenant_context() or the logged-in Streamlit session."""
    return _AppSession()


def get_admin_session():
    """Owner session for provisioning. Bypasses RLS on `tenants`; still subject to it on data tables."""
    return _AdminSession()


def init_all_tables():
    """Create all tables and (re)apply row-level security (idempotent). Runs as the table owner."""
    import backend.db.models  # noqa: F401
    from backend.db.rls import apply_rls
    Base.metadata.create_all(_admin_engine)
    apply_rls(_admin_engine)
