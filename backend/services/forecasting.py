"""Demand Forecasting: model training, market-factor statistics and the what-if response model."""
from sqlalchemy import func

from backend.analytics.what_if import monthly_payment, net_response_pct
from backend.core.cache import tenant_cache
from backend.db.models import Sale
from backend.db.session import session_scope
from backend.ml.demand_forecast import get_external_factor_stats, train_prophet_model

__all__ = ["average_loan", "brand_options", "external_factor_stats", "monthly_payment", "net_response_pct",
           "train_forecast"]


def external_factor_stats(region: str | None = None) -> dict:
    return get_external_factor_stats(region=region)


def train_forecast(**kwargs):
    """Fit a Prophet model on the tenant's sales. Returns (result, error_message)."""
    return train_prophet_model(**kwargs)


@tenant_cache(ttl=600)
def average_loan() -> float:
    """Typical financed amount for this tenant, for the monthly-payment translation."""
    with session_scope() as s:
        value = s.query(func.avg(Sale.loan_amount)).filter(Sale.loan_amount > 0).scalar()
        return float(value or 0.0)


@tenant_cache(ttl=600)
def brand_options() -> list[str]:
    with session_scope() as s:
        return sorted(b[0] for b in s.query(Sale.brand).distinct().all() if b[0])
