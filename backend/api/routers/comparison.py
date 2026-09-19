from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from backend.api.deps import CurrentCustomer, Filters
from backend.api.serialize import to_jsonable
from backend.services import comparison

router = APIRouter(prefix="/comparison", tags=["comparison"])

Measure = Annotated[Literal["units", "revenue"], Query()]
Dimension = Annotated[Literal["store", "brand", "category"], Query()]


@router.get("/tracking")
def tracking(caller: CurrentCustomer, filters: Filters, measure: Measure = "units"):
    """This year against last, month by month, with a seasonal forecast for the rest of the year."""
    return to_jsonable(comparison.tracking(filters, measure))


@router.get("/drivers")
def drivers(
    caller: CurrentCustomer,
    filters: Filters,
    measure: Measure = "units",
    dimension: Dimension = "store",
    only_significant: bool = False,
):
    """What moved the year-over-year change, split into the group-wide part and each entity's own part."""
    # The franchise split is meaningless once the view is already narrowed to one franchise.
    if filters.get("brand"):
        dimension = "store"
    return to_jsonable(comparison.drivers(filters, dimension, measure, only_significant))
