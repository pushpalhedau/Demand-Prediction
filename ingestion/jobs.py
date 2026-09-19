"""
Ingest jobs: one row in `ingest_jobs` per upload-and-load run.

process_job() does the work and is safe to run anywhere: in a background thread
(no infrastructure, dev default) or on a Redis/RQ worker (set REDIS_URL). The
queue message carries only (tenant_id, job_id); the worker re-scopes itself to
that tenant, so it never needs cross-tenant database access.
"""
import os
import pathlib
import threading
import traceback
import uuid
from datetime import datetime, timezone

from database.connection import get_db_session
from database.models import ColumnMapping, IngestJob
from database.tenant_context import tenant_context
from ingestion.pipeline import IngestError, run_ingest
from tenancy.training import train_tenant_models


def upload_root() -> pathlib.Path:
    return pathlib.Path(os.getenv("UPLOAD_DIR", "./data/uploads")).resolve()


def job_dir(tenant_id, job_id) -> pathlib.Path:
    d = upload_root() / str(tenant_id) / str(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_job(tenant_id, options: dict, created_by: str = None, job_id=None) -> uuid.UUID:
    job_id = job_id or uuid.uuid4()
    with tenant_context(tenant_id):
        s = get_db_session()
        try:
            s.add(IngestJob(id=job_id, status="queued", stage="Queued", progress=0.0,
                            options=options, created_by=created_by))
            s.commit()
        finally:
            s.close()
    return job_id


def get_job(tenant_id, job_id) -> dict:
    with tenant_context(tenant_id):
        s = get_db_session()
        try:
            j = s.query(IngestJob).filter(IngestJob.id == job_id).one_or_none()
            if j is None:
                return None
            return {"id": str(j.id), "status": j.status, "stage": j.stage, "progress": j.progress,
                    "message": j.message, "report": j.report, "options": j.options}
        finally:
            s.close()


def list_jobs(tenant_id, limit: int = 20) -> list:
    with tenant_context(tenant_id):
        s = get_db_session()
        try:
            rows = s.query(IngestJob).order_by(IngestJob.created_at.desc()).limit(limit).all()
            return [{"id": str(j.id), "status": j.status, "stage": j.stage, "progress": j.progress,
                     "message": j.message, "created_by": j.created_by, "created_at": j.created_at,
                     "finished_at": j.finished_at, "kind": "retrain" if (j.options or {}).get("train_only") else "import",
                     "loaded": (j.report or {}).get("loaded", {}), "notes": (j.report or {}).get("notes", [])}
                    for j in rows]
        finally:
            s.close()


def _update(tenant_id, job_id, **fields) -> None:
    with tenant_context(tenant_id):
        s = get_db_session()
        try:
            s.query(IngestJob).filter(IngestJob.id == job_id).update(fields)
            s.commit()
        finally:
            s.close()


def _save_mappings(tenant_id, mappings: dict) -> None:
    with tenant_context(tenant_id):
        s = get_db_session()
        try:
            for table, mapping in mappings.items():
                row = s.query(ColumnMapping).filter(ColumnMapping.table_name == table).one_or_none()
                if row is None:
                    s.add(ColumnMapping(table_name=table, mapping=mapping))
                else:
                    row.mapping, row.updated_at = mapping, _now()
            s.commit()
        finally:
            s.close()


def load_saved_mapping(tenant_id, table: str):
    with tenant_context(tenant_id):
        s = get_db_session()
        try:
            row = s.query(ColumnMapping).filter(ColumnMapping.table_name == table).one_or_none()
            return row.mapping if row else None
        finally:
            s.close()


def process_job(tenant_id, job_id) -> None:
    """Run one ingest job to completion, recording progress and the outcome on its row."""
    tenant_id, job_id = uuid.UUID(str(tenant_id)), uuid.UUID(str(job_id))
    job = get_job(tenant_id, job_id)
    if job is None:
        return
    opts = job["options"]
    _update(tenant_id, job_id, status="running", started_at=_now(), stage="Starting", progress=0.02)

    def progress(stage, fraction):
        _update(tenant_id, job_id, stage=stage, progress=float(min(max(fraction, 0.0), 0.99)))

    try:
        if opts.get("train_only"):
            result = {"tables": {}, "loaded": {}, "notes": []}
        else:
            root = (upload_root() / str(tenant_id)).resolve()
            files = {}
            for table, raw in opts["files"].items():
                path = pathlib.Path(raw).resolve()
                if root not in path.parents:
                    raise IngestError("An uploaded file could not be found. Please upload it again.")
                files[table] = str(path)
            result = run_ingest(
                tenant_id, files, opts["mappings"], replace=opts.get("replace", True), units=opts.get("units"),
                dayfirst=opts.get("dayfirst", False), decimal=opts.get("decimal", "."), progress=progress,
            )
            _save_mappings(tenant_id, opts["mappings"])

        notes = list(result["notes"])
        if opts.get("train", True):
            progress("Training models", 0.96)
            try:
                trained = train_tenant_models(tenant_id, log=lambda *_: None)
                for name, status in trained.items():
                    if status != "ok":
                        notes.append(f"{name.replace('_', ' ')} model not trained: {status}")
            except Exception as e:                                       # never fail an import over training
                notes.append(f"Models could not be trained: {e}")

        report = {"tables": result["tables"], "loaded": result["loaded"], "notes": notes}
        _update(tenant_id, job_id, status="succeeded", stage="Done", progress=1.0, report=report,
                message=None, finished_at=_now())
    except IngestError as e:
        _update(tenant_id, job_id, status="failed", stage="Failed", message=str(e), finished_at=_now())
    except Exception:
        traceback.print_exc()
        _update(tenant_id, job_id, status="failed", stage="Failed", finished_at=_now(),
                message="Something went wrong while importing your data. Nothing was changed.")


def enqueue_job(tenant_id, job_id) -> str:
    """Hand the job to a Redis/RQ worker if REDIS_URL is set, else run it in a background thread."""
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        import redis
        from rq import Queue
        Queue("ingest", connection=redis.from_url(redis_url)).enqueue(
            process_job, str(tenant_id), str(job_id), job_timeout=3600)
        return "queue"
    threading.Thread(target=process_job, args=(str(tenant_id), str(job_id)), daemon=True).start()
    return "thread"
