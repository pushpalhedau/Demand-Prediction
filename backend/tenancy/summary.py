from sqlalchemy import func

from backend.core.request_context import tenant_context
from backend.db.connection import get_db_session
from backend.db.models import Customer, Dealer, Inventory, Sale
from backend.ml.artifacts import artifact_exists


def models_trained(tenant_id) -> bool:
    return artifact_exists("xgboost", tenant_id, "xgboost_model")


def account_summary(tenant_id) -> dict:
    """Row counts and date range for one account (RLS-scoped to that tenant)."""
    with tenant_context(tenant_id):
        s = get_db_session()
        try:
            lo, hi = s.query(func.min(Sale.sale_date), func.max(Sale.sale_date)).one()
            return {
                "sales": s.query(func.count(Sale.sale_id)).scalar() or 0,
                "dealers": s.query(func.count(Dealer.dealer_id)).scalar() or 0,
                "customers": s.query(func.count(Customer.customer_id)).scalar() or 0,
                "inventory": s.query(func.count(Inventory.inventory_id)).scalar() or 0,
                "first_sale": lo, "last_sale": hi,
                "models": models_trained(tenant_id),
            }
        finally:
            s.close()
