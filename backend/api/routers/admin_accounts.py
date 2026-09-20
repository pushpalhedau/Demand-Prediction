"""
Operator-facing account management: create and configure customer accounts, their logins and status.

Every route here requires an operator session (see backend/api/deps.py); a customer token is refused the
same way a wrong password would be. Upload, mapping and dry-run live in admin_imports.py; the jobs and
retrain routes below are shared by both the import wizard and the plain "retrain now" button.
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from backend.api.deps import CurrentOperator
from backend.api.serialize import to_jsonable
from backend.core.errors import AppError
from backend.services import accounts, imports

router = APIRouter(prefix="/admin/accounts", tags=["admin-accounts"])

Slug = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{1,61}$")]
Text = Annotated[str, Field(min_length=1, max_length=120)]
OptionalText = Annotated[str | None, Field(default=None, max_length=64)]


class AccountConfig(BaseModel):
    currency: OptionalText = None
    currency_symbol: OptionalText = None
    symbol_position: Literal["prefix", "suffix"] | None = None
    language: Literal["en", "de"] | None = None
    region_label: OptionalText = None
    country_name: OptionalText = None
    news_gl: OptionalText = None
    news_hl: OptionalText = None


class CreateAccountRequest(BaseModel):
    name: Text
    slug: Annotated[str, Field(default="", max_length=62)] = ""
    admin_email: Annotated[str, Field(min_length=3, max_length=254)]
    admin_password: Annotated[str | None, Field(default=None, max_length=256)] = None
    config: AccountConfig = AccountConfig()


class UpdateSettingsRequest(AccountConfig):
    pass


class SetStatusRequest(BaseModel):
    status: Literal["active", "suspended"]


class AddLoginRequest(BaseModel):
    email: Annotated[str, Field(min_length=3, max_length=254)]
    password: Annotated[str | None, Field(default=None, max_length=256)] = None
    role: Literal["tenant_admin", "tenant_user"] = "tenant_user"


def _account_or_404(slug: str) -> dict:
    try:
        return accounts.get_account(slug)
    except Exception:  # noqa: BLE001 - any lookup failure means "no such account" to the caller
        raise HTTPException(status_code=404, detail="That account no longer exists.") from None


@router.get("")
def list_accounts(operator: CurrentOperator):
    return to_jsonable(accounts.list_accounts())


@router.post("", status_code=201)
def create_account(body: CreateAccountRequest, operator: CurrentOperator):
    try:
        created = accounts.create_account(body.name, body.slug.strip(), body.admin_email, body.admin_password,
                                          body.config.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    return to_jsonable(created)


@router.get("/{slug}")
def get_account(slug: Slug, operator: CurrentOperator):
    account = _account_or_404(slug)
    summary = accounts.account_summary(account["id"])
    return to_jsonable({**account, "summary": summary})


@router.patch("/{slug}/settings")
def update_settings(slug: Slug, body: UpdateSettingsRequest, operator: CurrentOperator):
    _account_or_404(slug)
    updated = accounts.update_account_settings(slug, body.model_dump(exclude_none=True))
    return to_jsonable(updated)


@router.post("/{slug}/status")
def set_status(slug: Slug, body: SetStatusRequest, operator: CurrentOperator):
    _account_or_404(slug)
    accounts.set_account_status(slug, body.status)
    return {"status": body.status}


@router.get("/{slug}/logins")
def list_logins(slug: Slug, operator: CurrentOperator):
    account = _account_or_404(slug)
    return to_jsonable(accounts.list_logins(account["id"]))


@router.post("/{slug}/logins", status_code=201)
def add_login(slug: Slug, body: AddLoginRequest, operator: CurrentOperator):
    _account_or_404(slug)
    try:
        created = accounts.add_login(slug, body.email, body.password, body.role)
    except (AppError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    return to_jsonable(created)


@router.post("/logins/{user_id}/reset-password")
def reset_login_password(user_id: Annotated[str, Path(max_length=64)], operator: CurrentOperator):
    new_password = accounts.reset_login_password(user_id)
    return {"password": new_password}


@router.get("/{slug}/jobs")
def list_jobs(slug: Slug, operator: CurrentOperator, limit: Annotated[int, Query(ge=1, le=100)] = 25):
    account = _account_or_404(slug)
    return to_jsonable(imports.recent_jobs(account["id"], limit=limit))


@router.get("/{slug}/jobs/{job_id}")
def job_status(slug: Slug, job_id: Annotated[str, Path(max_length=64)], operator: CurrentOperator):
    account = _account_or_404(slug)
    job = imports.job_status(account["id"], job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No such job.")
    return to_jsonable(job)


@router.post("/{slug}/retrain", status_code=202)
def retrain(slug: Slug, operator: CurrentOperator):
    account = _account_or_404(slug)
    job_id = imports.start_retrain(account["id"], operator.email)
    return {"job_id": job_id}
