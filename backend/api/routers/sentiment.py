from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import CurrentCustomer, Filters
from backend.api.serialize import to_jsonable
from backend.services import sentiment

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


class RefreshRequest(BaseModel):
    timespan: Annotated[str, Field(max_length=32)]


class ForecastCheckRequest(BaseModel):
    target: Literal["units_sold", "total_revenue_incl_tax"] = "units_sold"
    horizon_days: Literal[30, 60, 90, 180] = 90


@router.get("/overview")
def overview(caller: CurrentCustomer):
    """The current demand signal, the scored articles behind it, and the windows a refresh can cover."""
    return to_jsonable({**sentiment.overview(), "timespans": sentiment.TIMESPAN_OPTIONS})


@router.post("/refresh")
def refresh(body: RefreshRequest, caller: CurrentCustomer):
    """Fetch the latest news for the account's market and score it."""
    if body.timespan not in sentiment.TIMESPAN_OPTIONS.values():
        raise HTTPException(status_code=422, detail="Unknown time window.")
    return to_jsonable(sentiment.refresh_news(body.timespan))


@router.post("/briefing")
def briefing(caller: CurrentCustomer, filters: Filters):
    """A plain-language read across every module, for the current filters."""
    data = sentiment.overview()
    key = json.dumps({k: str(v) for k, v in filters.items()}, sort_keys=True)
    context = sentiment.briefing_context(f"{key}|lang={caller.language}", filters, data["stats"], data["articles"])
    return {"text": sentiment.generate_briefing(context)}


@router.post("/forecast-check")
def forecast_check(body: ForecastCheckRequest, caller: CurrentCustomer, filters: Filters):
    """Does adding news signals improve the demand forecast? Baseline against news-aware, monthly."""
    return to_jsonable(sentiment.forecast_check(filters, target=body.target, horizon_days=body.horizon_days))
