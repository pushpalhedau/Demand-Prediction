from __future__ import annotations

from fastapi import APIRouter

from backend.api.deps import CurrentCustomer, Filters
from backend.api.serialize import to_jsonable
from backend.services import inventory

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/stock-health")
def stock_health(caller: CurrentCustomer, filters: Filters, aged_days: int = 90):
    """Stock position, forecast coverage, ageing, and the reorder and aged-stock worklists."""
    return to_jsonable(inventory.stock_health(filters, aged_days))
