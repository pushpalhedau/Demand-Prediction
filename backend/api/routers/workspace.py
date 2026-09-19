from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from backend.api.deps import CurrentCustomer
from backend.api.serialize import to_jsonable
from backend.core.request_context import current_profile
from backend.services import workspace

router = APIRouter(tags=["workspace"])

TABS = ("tab.overview", "tab.forecasting", "tab.comparison", "tab.regional", "tab.customers", "tab.inventory",
        "tab.sentiment")


@router.get("/me")
def me(caller: CurrentCustomer):
    """Who is signed in, how to present their numbers, and which tabs their data supports."""
    profile = current_profile()
    caps = workspace.get_capabilities()
    return to_jsonable({
        "user": {"email": caller.identity.email, "role": caller.identity.role},
        "organisation": {
            "name": profile.name, "currency": profile.currency, "currency_symbol": profile.currency_symbol,
            "symbol_position": profile.symbol_position, "language": caller.language,
            "region_label": profile.region_label, "country": profile.country_name,
        },
        "ready": bool(caps["sales"]),
        "tabs": [t for t in TABS if workspace.tab_available(t, caps)],
        "data_range": {"from": caps["first_sale"], "to": caps["last_sale"]},
        "has": {k: caps[k] for k in ("sales", "dealers", "customers", "inventory", "lease", "trade_in")},
    })


@router.get("/workspace/filters")
def filter_options(caller: CurrentCustomer):
    return to_jsonable(workspace.filter_options())


@router.get("/workspace/cities")
def cities(caller: CurrentCustomer, region: Annotated[str, Query(max_length=120)]):
    return to_jsonable(workspace.cities_in_region(region))
