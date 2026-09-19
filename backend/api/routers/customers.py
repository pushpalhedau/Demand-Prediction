from __future__ import annotations

import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.api.deps import CurrentCustomer, Filters
from backend.api.serialize import to_jsonable
from backend.services import customers

router = APIRouter(prefix="/customers", tags=["customers"])

Text = Annotated[str, Field(min_length=1, max_length=120)]


class LeadRequest(BaseModel):
    region: Text
    age: Annotated[int, Field(ge=16, le=110)]
    occupation: Text
    annual_income: Annotated[float, Field(ge=0, le=1e9)]
    credit_score: Annotated[int, Field(ge=0, le=1000)]
    vehicle_category: Text
    fuel_type: Text
    marketing_channel: Text
    relationship: Literal["new", "service", "repeat"]
    discount_pct: Annotated[float, Field(ge=0, le=30)]
    base_price: Annotated[float, Field(gt=0, le=1e8)]


@router.get("/retention")
def retention(caller: CurrentCustomer, filters: Filters):
    """The outreach queue, where the buyer base stands, and the segment panel."""
    return to_jsonable(customers.retention_overview(filters))


@router.get("/queue")
def queue(
    caller: CurrentCustomer,
    filters: Filters,
    store: Annotated[str | None, Query(max_length=160)] = None,
    reason: Annotated[list[str] | None, Query(max_length=8)] = None,
    page: Annotated[int, Query(ge=0, le=10_000)] = 0,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
):
    """One page of the outreach queue, filtered by owning store and reason."""
    return to_jsonable(customers.queue_page(filters, store=store, reasons=reason, offset=page * page_size,
                                            limit=page_size))


_CSV_FORMULA_PREFIXES = ('=', '+', '-', '@', chr(9), chr(13))


def _csv_cell(value):
    """Stop spreadsheet formula injection: a customer-supplied name must never execute when the file is opened."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_CSV_FORMULA_PREFIXES) else text


@router.get("/queue.csv")
def queue_csv(
    caller: CurrentCustomer,
    filters: Filters,
    store: Annotated[str | None, Query(max_length=160)] = None,
    reason: Annotated[list[str] | None, Query(max_length=8)] = None,
):
    """The whole filtered queue as a CSV download."""
    rows = customers.queue_page(filters, store=store, reasons=reason, offset=0, limit=None)["rows"]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(list(rows.columns))
    for record in rows.itertuples(index=False):
        writer.writerow([_csv_cell(v) for v in record])
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="retention_action_queue.csv"'})


@router.get("/lead-form")
def lead_form(caller: CurrentCustomer):
    """Stores a lead can be handled by, plus the option lists and ranges the lead model was trained on."""
    return to_jsonable({"stores": customers.lead_stores(), "model": customers.lead_form_context(),
                        "relationships": list(customers.RELATIONSHIP_LOYALTY)})


@router.post("/score-lead")
def score_lead(body: LeadRequest, caller: CurrentCustomer):
    lead = body.model_dump(exclude={"relationship"})
    lead["loyalty_score"] = customers.RELATIONSHIP_LOYALTY[body.relationship]
    return to_jsonable(customers.score_lead(lead))
