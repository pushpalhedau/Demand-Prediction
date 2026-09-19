"""Operator audit trail. Append-only; not tenant-scoped and never readable by the customer-facing role."""
from sqlalchemy import BigInteger, Column, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB

from backend.db.connection import Base
from backend.db.models.base import utcnow


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    at = Column(DateTime, nullable=False, default=utcnow, index=True)
    actor = Column(Text, nullable=False)                    # operator email, or "system"
    action = Column(Text, nullable=False, index=True)       # e.g. account.create, operator.sign_in
    target_tenant = Column(Text, nullable=True, index=True) # tenant slug (text so it outlives the tenant)
    outcome = Column(Text, nullable=False, default="ok")    # ok | denied | failed
    detail = Column(JSONB, nullable=True)                   # small, non-secret context (never passwords/tokens)
