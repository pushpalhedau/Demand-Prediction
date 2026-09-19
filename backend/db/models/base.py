"""Shared column helpers for the models."""
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    ForeignKey,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from backend.db.rls import TENANT_EXPR


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def tenant_col(pk: bool = False):
    """
    Owner tenant of a row. Defaults from the transaction's app.current_tenant_id,
    so application inserts never pass it, and the RLS WITH CHECK rejects any
    attempt to write a row for a different tenant.
    """
    return Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=pk,
        nullable=False,
        server_default=text(TENANT_EXPR),
        index=not pk,
    )
