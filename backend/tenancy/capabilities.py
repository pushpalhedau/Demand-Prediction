from sqlalchemy import func

from backend.db.connection import get_db_session
from backend.db.models import Customer, Dealer, ExternalFactor, Inventory, Sale
from backend.core.cache import tenant_cache

# Which tab needs which data. A tab a tenant cannot populate is hidden rather than shown broken.
TAB_REQUIRES = {
    "tab.overview": ("sales",),
    "tab.forecasting": ("sales",),
    "tab.comparison": ("sales", "dealers"),
    "tab.regional": ("sales", "dealers"),
    "tab.customers": ("sales", "customers"),
    "tab.inventory": ("inventory", "dealers"),
    "tab.sentiment": (),
}


@tenant_cache(ttl=60)
def get_capabilities() -> dict:
    """What data this tenant has. Cached briefly so an upload shows up within a minute."""
    s = get_db_session()
    try:
        has = lambda col: s.query(col).limit(1).first() is not None
        lo, hi = s.query(func.min(Sale.sale_date), func.max(Sale.sale_date)).one()
        return {
            "sales": lo is not None,
            "dealers": has(Dealer.dealer_id),
            "customers": has(Customer.customer_id),
            "inventory": has(Inventory.inventory_id),
            "external_factors": has(ExternalFactor.id),
            "lease": s.query(Sale.sale_id).filter(Sale.lease_maturity_date.isnot(None)).limit(1).first() is not None,
            "trade_in": s.query(Sale.sale_id).filter(Sale.trade_in_flag.is_(True)).limit(1).first() is not None,
            "first_sale": lo,
            "last_sale": hi,
        }
    finally:
        s.close()


def tab_available(tab_key: str, caps: dict) -> bool:
    return all(caps.get(need) for need in TAB_REQUIRES.get(tab_key, ()))
