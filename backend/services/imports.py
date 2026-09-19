"""
Operator-facing data import: propose a column mapping, dry-run it, then run the import (and retrain)
as a background job for one account.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.errors import IngestError
from backend.ingestion import jobs
from backend.ingestion.catalog import (
    GAL_TO_L,
    HP_TO_KW,
    L100_FROM_MPG,
    LOAD_ORDER,
    MI_TO_KM,
    PS_TO_KW,
    SQFT_TO_SQM,
    TABLES,
)
from backend.ingestion.mapping import AUTO_CONFIDENCE, Proposal, propose_mapping
from backend.ingestion.pipeline import transform_table
from backend.tenancy.capabilities import get_capabilities

__all__ = ["AUTO_CONFIDENCE", "GAL_TO_L", "HP_TO_KW", "IngestError", "L100_FROM_MPG", "LOAD_ORDER", "MI_TO_KM",
           "PS_TO_KW", "SQFT_TO_SQM", "TABLES", "dry_run", "job_status", "propose", "publish_data_changes",
           "recent_jobs", "read_header", "save_upload", "saved_mapping", "start_import", "start_retrain"]

PREVIEW_ROWS = 3000


def save_upload(tenant_id, job_id: str, table: str, content: bytes | memoryview) -> Path:
    """Store an uploaded CSV under the account's own upload folder and return its path."""
    path = jobs.job_dir(tenant_id, job_id) / f"{table}.csv"
    path.write_bytes(bytes(content))
    return path


def read_header(path: str) -> list[str]:
    return list(pd.read_csv(path, nrows=1, dtype=str).columns)


def propose(table: str, columns: list[str]) -> Proposal:
    return propose_mapping(table, columns)


def saved_mapping(tenant_id, table: str) -> dict | None:
    return jobs.load_saved_mapping(tenant_id, table)


def dry_run(table: str, path: str, mapping: dict, units: dict, dayfirst: bool, decimal: str) -> dict:
    """Run the transform on a sample of the file. Raises IngestError on a blocking problem."""
    raw = pd.read_csv(path, nrows=PREVIEW_ROWS, dtype=str, keep_default_na=False, na_values=[""])
    _, report = transform_table(table, raw, mapping, units, dayfirst, decimal)
    return report


def start_import(tenant_id, job_id: str, options: dict[str, Any], created_by: str) -> None:
    jobs.create_job(tenant_id, options, created_by=created_by, job_id=uuid.UUID(job_id))
    jobs.enqueue_job(tenant_id, uuid.UUID(job_id))


def start_retrain(tenant_id, created_by: str) -> str:
    job_id = uuid.uuid4()
    jobs.create_job(tenant_id, {"train_only": True, "train": True}, created_by=created_by, job_id=job_id)
    jobs.enqueue_job(tenant_id, job_id)
    return str(job_id)


def job_status(tenant_id, job_id: str) -> dict | None:
    return jobs.get_job(tenant_id, uuid.UUID(job_id))


def recent_jobs(tenant_id, limit: int = 25) -> list[dict]:
    return jobs.list_jobs(tenant_id, limit=limit)


def publish_data_changes() -> None:
    """Make freshly imported data visible to customers immediately (drops the cached capability check)."""
    get_capabilities.clear()
