from __future__ import annotations

from fastapi import APIRouter

from backend.api.deps import CurrentCustomer, Filters
from backend.api.serialize import to_jsonable
from backend.services import overview

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("/glance")
def glance(caller: CurrentCustomer, filters: Filters):
    """Headline KPIs, the revenue trend with its projection, mix breakdowns and the top stores."""
    trend = overview.monthly_revenue_trend(filters)
    series = {}
    if not trend.empty:
        td = trend.sort_values("date").set_index("date")
        rev, units = td["revenue"].astype(float), td["sales"].astype(float)
        if len(rev) >= 14 and rev.iloc[-1] < 0.55 * rev.iloc[-13:-1].mean():      # drop a trailing partial month
            rev, units = rev.iloc[:-1], units.iloc[:-1]
        rev, units = rev.tail(36), units.tail(36)
        series = {"revenue": rev, "units": units,
                  "revenue_projection": overview.project_series(rev, 6),
                  "units_projection": overview.project_series(units, 6)}
    stores = overview.sales_by_store(filters, limit=500)
    return to_jsonable({
        "kpis": overview.executive_kpis(filters),
        "trend": series,
        "by_category": overview.sales_by_category(filters),
        "by_fuel": overview.sales_by_fuel_type(filters),
        "stores": stores.head(5),
        "store_average_units": float(stores["units"].mean()) if not stores.empty else None,
    })


@router.get("/recommendations")
def recommendations(caller: CurrentCustomer, filters: Filters):
    landing = overview.year_end_projection(filters)
    plays = overview.recommended_plays(filters, limit=5)
    return to_jsonable({
        "landing": landing,
        "plays": [{**p.__dict__, "accent": overview.category_accent(p.category)} for p in plays],
        "gross_per_unit": overview.gross_per_unit(),
    })
