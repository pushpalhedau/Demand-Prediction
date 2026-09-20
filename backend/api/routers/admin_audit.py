from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from backend.api.deps import CurrentOperator
from backend.api.serialize import to_jsonable
from backend.services import accounts

router = APIRouter(prefix="/admin/audit", tags=["admin-audit"])


@router.get("")
def audit_trail(
    operator: CurrentOperator,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    account: Annotated[str | None, Query(max_length=62)] = None,
):
    """The append-only operator audit trail, most recent first."""
    return to_jsonable(accounts.audit_trail(limit=limit, account=account))
