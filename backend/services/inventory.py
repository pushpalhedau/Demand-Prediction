"""Inventory Intelligence: stock position, ageing, lease returns, trade-ins and vehicle placement."""
import pandas as pd

from backend.core.cache import tenant_cache
from backend.db.session import session_scope
from backend.ml.vehicle_placement import recommend_alternatives
from backend.repositories import dealers as dealers_repo
from backend.repositories import inventory as inv

DAYS_SUPPLY_HEALTHY_LOW = inv.DAYS_SUPPLY_HEALTHY_LOW
DAYS_SUPPLY_HEALTHY_HIGH = inv.DAYS_SUPPLY_HEALTHY_HIGH

__all__ = ["DAYS_SUPPLY_HEALTHY_HIGH", "DAYS_SUPPLY_HEALTHY_LOW", "aging_buckets", "alternatives",
           "lease_recapture", "lease_returns", "placement_reference", "snapshot", "trade_in_activity",
           "trade_replacement_flow", "trend"]


@tenant_cache(ttl=600)
def snapshot(filters: dict) -> pd.DataFrame:
    with session_scope() as s:
        return inv.get_inventory_snapshot(s, filters)


@tenant_cache(ttl=600)
def trend(filters: dict) -> pd.DataFrame:
    with session_scope() as s:
        return inv.get_inventory_trend(s, filters)


@tenant_cache(ttl=600)
def lease_returns(filters: dict, months_ahead: int) -> pd.DataFrame:
    with session_scope() as s:
        return inv.get_lease_return_pipeline(s, filters, months_ahead=months_ahead)


@tenant_cache(ttl=600)
def lease_recapture(filters: dict, days_ahead: int) -> pd.DataFrame:
    with session_scope() as s:
        return inv.get_lease_maturity_recapture(s, filters, days_ahead=days_ahead)


@tenant_cache(ttl=600)
def trade_in_activity(filters: dict) -> pd.DataFrame:
    with session_scope() as s:
        return inv.get_trade_in_activity(s, filters)


@tenant_cache(ttl=600)
def trade_replacement_flow(filters: dict) -> pd.DataFrame:
    with session_scope() as s:
        return inv.get_trade_replacement_flow(s, filters)


@tenant_cache(ttl=600)
def placement_reference(filters: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(vehicle catalogue, dealer directory, substitution history) used to recommend alternatives."""
    with session_scope() as s:
        return (inv.get_vehicle_catalog(s), dealers_repo.get_dealer_directory(s),
                inv.get_substitution_history(s, filters))


def aging_buckets(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    return inv.get_aging_buckets(snapshot_df)


def alternatives(target: pd.Series, catalog: pd.DataFrame, snapshot_df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Rank in-stock substitutes for a vehicle a customer asked for (see ml.vehicle_placement)."""
    return recommend_alternatives(target, catalog, snapshot_df, **kwargs)
