import numpy as np
from sqlalchemy import func

from database.connection import get_db_session
from database.models import Sale
from utils.tenant_cache import tenant_cache_data

# Share of a brand's average selling price kept as front-end + F&I gross, by price tier.
# Front-end gross is thin on mass brands and fatter on luxury; the tiers are ranked within
# THIS tenant's own brands, so it works in any currency and for any brand mix.
_GROSS_PCT = {"luxury": 0.09, "premium": 0.06, "mass": 0.04}


@tenant_cache_data(ttl=600, show_spinner=False)
def gross_per_unit_by_brand() -> dict:
    """{brand: estimated gross per new unit, in the tenant's currency}. A benchmark, not booked gross."""
    s = get_db_session()
    try:
        rows = s.query(Sale.brand, func.avg(Sale.selling_price)).group_by(Sale.brand).all()
    finally:
        s.close()
    asp = {b: float(p) for b, p in rows if b and p}
    if not asp:
        return {}
    q80, q40 = np.percentile(list(asp.values()), [80, 40])
    tier = lambda p: "luxury" if p >= q80 else ("premium" if p >= q40 else "mass")
    return {b: p * _GROSS_PCT[tier(p)] for b, p in asp.items()}


def gross_series(brands):
    """Map a Series of brand names to estimated gross per unit (unknown brands get the tenant mean)."""
    table = gross_per_unit_by_brand()
    fallback = float(np.mean(list(table.values()))) if table else 0.0
    return brands.map(table).fillna(fallback)
