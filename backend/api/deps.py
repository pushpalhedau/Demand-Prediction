"""Request dependencies: who is calling, which tenant they are pinned to, and the dashboard filters."""
from __future__ import annotations

import datetime as dt
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from backend.api import cookies
from backend.core.errors import AuthError
from backend.core.request_context import TenantProfile, bind_actor, bind_request, clear_request
from backend.services import identity, workspace

SUPPORTED_LANGUAGES = ("en", "de")


@dataclass(frozen=True)
class Caller:
    identity: identity.Identity
    profile: TenantProfile
    language: str


async def customer(request: Request) -> AsyncIterator[Caller]:
    """
    Authenticate the request from its session cookie and pin the rest of it to that user's tenant.

    This is an async dependency on purpose: the tenant is bound in the request's own task context, which the
    threadpool copies for the (sync) endpoint that follows. It is cleared afterwards so nothing can leak into
    the next request handled on the same worker thread.
    """
    token = cookies.access_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in.")
    try:
        session = await run_in_threadpool(identity.customer_from_access_token, token)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None
    profile = TenantProfile.from_config(session.identity.tenant_id, session.tenant_name, session.tenant_config)
    lang = request.headers.get("x-lang", "")
    language = lang if lang in SUPPORTED_LANGUAGES else profile.language
    bind_request(profile, language)
    try:
        yield Caller(session.identity, profile, language)
    finally:
        clear_request()


CurrentCustomer = Annotated[Caller, Depends(customer)]


def dashboard_filters(
    caller: CurrentCustomer,
    start_date: Annotated[dt.date | None, Query()] = None,
    end_date: Annotated[dt.date | None, Query()] = None,
    region: Annotated[str | None, Query(max_length=120)] = None,
    city: Annotated[str | None, Query(max_length=120)] = None,
    brand: Annotated[str | None, Query(max_length=120)] = None,
    vehicle_category: Annotated[str | None, Query(max_length=120)] = None,
    fuel_type: Annotated[str | None, Query(max_length=120)] = None,
) -> dict:
    """The global filters as the services expect them. Dates default to the tenant's whole sales history."""
    caps = workspace.get_capabilities()
    return {
        "start_date": start_date or caps["first_sale"],
        "end_date": end_date or caps["last_sale"],
        "region": region or None,
        "city": city or None,
        "brand": brand or None,
        "vehicle_category": vehicle_category or None,
        "fuel_type": fuel_type or None,
    }


Filters = Annotated[dict, Depends(dashboard_filters)]


async def operator(request: Request) -> AsyncIterator[identity.Operator]:
    """
    Authenticate an admin-console request from its (separate) session cookie. Every audited action taken while
    this dependency is active is attributed to this operator; the attribution is cleared afterwards.
    """
    token = cookies.admin_access_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in.")
    try:
        op = await run_in_threadpool(identity.operator_from_access_token, token)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None
    bind_actor(op.email)
    try:
        yield op
    finally:
        clear_request()


CurrentOperator = Annotated[identity.Operator, Depends(operator)]
