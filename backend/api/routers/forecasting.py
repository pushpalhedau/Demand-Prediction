from __future__ import annotations

import math
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from backend.api.deps import CurrentCustomer, Filters
from backend.api.serialize import to_jsonable
from backend.services import forecasting

router = APIRouter(prefix="/forecasting", tags=["forecasting"])

LEVER_KEYS = {"crude_oil_price_usd", "petrol_price_per_litre", "diesel_price_per_litre", "auto_loan_apr_pct"}


class ForecastRequest(BaseModel):
    target: Literal["units_sold", "total_revenue_incl_tax"] = "units_sold"
    horizon_months: Literal[3, 6, 12] = 3
    brand: Annotated[str | None, Field(max_length=120)] = None
    overrides: dict[str, float] | None = None

    @field_validator("overrides")
    @classmethod
    def only_known_levers(cls, value):
        if value is None:
            return None
        for key, number in value.items():
            if key not in LEVER_KEYS or not math.isfinite(number) or abs(number) > 1e6:
                raise ValueError("Unknown or out-of-range market condition.")
        return value


@router.get("/options")
def options(caller: CurrentCustomer, filters: Filters):
    """Brands the forecast can be narrowed to, and the market conditions the what-if can change."""
    return to_jsonable({"brands": forecasting.brand_options(), "levers": forecasting.levers(filters.get("region")),
                        "average_loan": forecasting.average_loan()})


@router.post("/report")
def report(body: ForecastRequest, caller: CurrentCustomer, filters: Filters):
    """Train on the account's sales and return the forecast window, headline numbers and seasonality."""
    return to_jsonable(forecasting.forecast(filters, target=body.target, horizon_months=body.horizon_months,
                                            brand=body.brand or None, overrides=body.overrides or None))
