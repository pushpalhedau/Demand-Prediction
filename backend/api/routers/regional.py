from __future__ import annotations

from fastapi import APIRouter

from backend.api.deps import CurrentCustomer, Filters
from backend.api.serialize import to_jsonable
from backend.services import stores

router = APIRouter(prefix="/regional", tags=["regional"])


@router.get("/scorecard")
def scorecard(caller: CurrentCustomer, filters: Filters):
    """Every rooftop's units, revenue, pace against its own target, growth and showroom conversion."""
    return to_jsonable(stores.scorecard(filters))
