"""Append-only operator audit trail (written with the owner role; the customer-facing role cannot touch it)."""
from __future__ import annotations

from typing import Any

from backend.core.log import get_logger
from backend.core.request_context import current_actor
from backend.db.connection import get_admin_session
from backend.db.models import AuditEvent

log = get_logger(__name__)

# Never store these, even by accident: the trail records what happened, not secrets.
_FORBIDDEN_KEYS = {"password", "token", "access_token", "refresh_token", "secret", "authorization"}


def _clean(detail: dict[str, Any] | None) -> dict[str, Any] | None:
    if not detail:
        return None
    return {k: v for k, v in detail.items() if k.lower() not in _FORBIDDEN_KEYS}


def record(action: str, *, tenant: str | None = None, detail: dict[str, Any] | None = None,
           outcome: str = "ok", actor: str | None = None) -> None:
    """Best effort: a failure to write the trail is logged loudly but never blocks the operator's action."""
    try:
        db = get_admin_session()
        try:
            db.add(AuditEvent(actor=actor or current_actor(), action=action, target_tenant=tenant,
                              outcome=outcome, detail=_clean(detail)))
            db.commit()
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        log.error("Could not write audit event %s", action, exc_info=True)


def recent_events(limit: int = 200, tenant: str | None = None) -> list[dict[str, Any]]:
    db = get_admin_session()
    try:
        q = db.query(AuditEvent).order_by(AuditEvent.id.desc())
        if tenant:
            q = q.filter(AuditEvent.target_tenant == tenant)
        return [{"at": e.at, "actor": e.actor, "action": e.action, "account": e.target_tenant or "",
                 "outcome": e.outcome, "detail": e.detail or {}} for e in q.limit(limit)]
    finally:
        db.close()
