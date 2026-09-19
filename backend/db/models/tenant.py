"""Tenancy and job-tracking tables: tenants, saved column mappings and ingest jobs."""
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from backend.db.connection import Base
from backend.db.models.base import tenant_col, utcnow


class Tenant(Base):
    """
    One row per customer account. `config` replaces what used to be per-market
    code branches: currency, currency_symbol, symbol_position, language,
    region_label, country, news_hl/news_gl (news edition).
    """
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="active")     # active | suspended
    plan = Column(Text, nullable=True)
    config = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ColumnMapping(Base):
    """A tenant's saved source-column -> canonical-field mapping for one table, reused on re-uploads."""
    __tablename__ = "column_mappings"

    tenant_id = tenant_col(pk=True)
    table_name = Column(Text, primary_key=True)
    mapping = Column(JSONB, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=utcnow)


class IngestJob(Base):
    """One upload-and-load run, executed by the background worker."""
    __tablename__ = "ingest_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = tenant_col()
    status = Column(Text, nullable=False, default="queued")     # queued | running | succeeded | failed
    stage = Column(Text, nullable=True)
    progress = Column(Float, nullable=False, default=0.0)       # 0..1
    message = Column(Text, nullable=True)
    options = Column(JSONB, nullable=True)                      # files, mappings, replace, units
    report = Column(JSONB, nullable=True)                       # row counts, warnings, errors
    created_by = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
