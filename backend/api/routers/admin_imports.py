"""
Operator-facing data import: upload CSVs for one account, confirm the column mapping, dry-run it, then run
the import (and retrain) as a background job. The job itself is polled through the existing
GET /admin/accounts/{slug}/jobs/{job_id} route in admin_accounts.py; this router only covers the wizard steps
that lead up to starting it.

The job id is a UUID the caller generates and reuses across every step of one wizard session; it doubles as
the upload folder key (backend/services/imports.upload_path), so files from an abandoned session never
collide with a later one.
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, Path, UploadFile
from pydantic import BaseModel, Field

from backend.api.deps import CurrentOperator
from backend.api.serialize import to_jsonable
from backend.core.errors import IngestError
from backend.services import accounts, imports

router = APIRouter(prefix="/admin", tags=["admin-imports"])

Slug = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{1,61}$")]
JobId = Annotated[str, Path(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]
TableName = Literal["vehicles", "dealers", "customers", "external_factors", "sales", "inventory"]


class Transform(BaseModel):
    op: Literal["mul", "inv"]
    k: float


class MappingColumn(BaseModel):
    source: str
    transform: Transform | None = None


class TableMapping(BaseModel):
    columns: dict[str, MappingColumn] = Field(default_factory=dict)
    extras: bool = True

    def to_pipeline(self) -> dict:
        columns = {name: {"source": c.source, "transform": [c.transform.op, c.transform.k] if c.transform else None}
                   for name, c in self.columns.items()}
        return {"columns": columns, "extras": self.extras}


class DryRunRequest(BaseModel):
    mapping: TableMapping
    units: dict[str, str] = Field(default_factory=dict)
    dayfirst: bool = False
    decimal: Literal[".", ","] = "."


class StartImportRequest(BaseModel):
    tables: list[TableName]
    mappings: dict[str, TableMapping]
    units: dict[str, str] = Field(default_factory=dict)
    dayfirst: bool = False
    decimal: Literal[".", ","] = "."
    replace: bool = True
    train: bool = True


def _account_or_404(slug: str) -> dict:
    try:
        return accounts.get_account(slug)
    except Exception:  # noqa: BLE001 - any lookup failure means "no such account" to the caller
        raise HTTPException(status_code=404, detail="That account no longer exists.") from None


@router.get("/imports/schema")
def import_schema(operator: CurrentOperator):
    """Table order, fields and unit-conversion constants the wizard renders itself from."""
    return imports.schema()


@router.post("/accounts/{slug}/imports/{job_id}/files/{table}", status_code=204)
def upload_file(slug: Slug, job_id: JobId, table: TableName, operator: CurrentOperator, file: Annotated[UploadFile, File()]):
    account = _account_or_404(slug)
    content = file.file.read()
    try:
        imports.save_upload(account["id"], job_id, table, content)
    except IngestError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/accounts/{slug}/imports/{job_id}/{table}/mapping")
def get_mapping(slug: Slug, job_id: JobId, table: TableName, operator: CurrentOperator):
    account = _account_or_404(slug)
    try:
        return to_jsonable(imports.mapping_proposal(account["id"], job_id, table))
    except IngestError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/accounts/{slug}/imports/{job_id}/{table}/dry-run")
def dry_run(slug: Slug, job_id: JobId, table: TableName, body: DryRunRequest, operator: CurrentOperator):
    account = _account_or_404(slug)
    path = imports.upload_path(account["id"], job_id, table)
    if not path.exists():
        raise HTTPException(status_code=422, detail=f"{table}: upload the file first.")
    try:
        report = imports.dry_run(table, str(path), body.mapping.to_pipeline(), body.units, body.dayfirst, body.decimal)
    except IngestError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    return to_jsonable(report)


@router.post("/accounts/{slug}/imports/{job_id}/start", status_code=202)
def start(slug: Slug, job_id: JobId, body: StartImportRequest, operator: CurrentOperator):
    account = _account_or_404(slug)
    files = {}
    for table in body.tables:
        path = imports.upload_path(account["id"], job_id, table)
        if not path.exists():
            raise HTTPException(status_code=422, detail=f"{table}: upload the file first.")
        files[table] = str(path)
    options = {
        "files": files,
        "mappings": {table: mapping.to_pipeline() for table, mapping in body.mappings.items()},
        "units": body.units, "dayfirst": body.dayfirst, "decimal": body.decimal,
        "replace": body.replace, "train": body.train,
    }
    try:
        imports.start_import(account["id"], job_id, options, created_by=operator.email)
    except IngestError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    return {"job_id": job_id}


@router.post("/accounts/{slug}/imports/{job_id}/done", status_code=204)
def done(slug: Slug, job_id: JobId, operator: CurrentOperator):
    """Called once the operator dismisses a finished import: makes the new data visible immediately."""
    _account_or_404(slug)
    imports.publish_data_changes()
