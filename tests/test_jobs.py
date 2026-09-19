import time
import uuid

import pytest
from sqlalchemy import text

from database.connection import get_admin_session, get_db_session, init_all_tables
from database.models import Tenant
from database.tenant_context import tenant_context
from ingestion.jobs import (
    create_job, enqueue_job, get_job, job_dir, load_saved_mapping, process_job,
)
from ingestion.mapping import propose_mapping
from ingestion.pipeline import read_csv


@pytest.fixture
def tenant(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.delenv("REDIS_URL", raising=False)
    init_all_tables()
    admin = get_admin_session()
    t = Tenant(slug=f"job-{uuid.uuid4().hex[:8]}", name="Job test", config={})
    admin.add(t)
    admin.commit()
    tid = t.id
    admin.close()
    yield tid
    admin = get_admin_session()
    admin.query(Tenant).filter(Tenant.id == tid).delete()
    admin.commit()
    admin.close()


def _options(tid, job_id, sales_csv: str, **extra):
    path = job_dir(tid, job_id) / "sales.csv"
    path.write_text(sales_csv, encoding="utf-8")
    mapping = propose_mapping("sales", list(read_csv(path).columns)).to_mapping()
    return {"files": {"sales": str(path)}, "mappings": {"sales": mapping}, "units": {"distance": "km"},
            "replace": True, "train": False, **extra}


GOOD = "sale_id,sale_date,selling_price\nS1,2025-01-01,10\nS2,2025-01-02,20\n"


def test_successful_job_records_progress_report_and_saves_the_mapping(tenant):
    jid = uuid.uuid4()
    create_job(tenant, _options(tenant, jid, GOOD), created_by="me@example.com", job_id=jid)
    assert get_job(tenant, jid)["status"] == "queued"

    process_job(tenant, jid)

    job = get_job(tenant, jid)
    assert job["status"] == "succeeded" and job["progress"] == 1.0
    assert job["report"]["loaded"]["sales"] == 2
    saved = load_saved_mapping(tenant, "sales")
    assert saved["columns"]["selling_price"]["source"] == "selling_price"


def test_failed_job_reports_a_readable_reason_and_changes_nothing(tenant):
    ok = uuid.uuid4()
    create_job(tenant, _options(tenant, ok, GOOD), job_id=ok)
    process_job(tenant, ok)

    bad = uuid.uuid4()
    create_job(tenant, _options(tenant, bad, "sale_date,selling_price\nnot-a-date,5\n"), job_id=bad)
    process_job(tenant, bad)

    job = get_job(tenant, bad)
    assert job["status"] == "failed" and "no usable rows" in job["message"]
    with tenant_context(tenant):
        s = get_db_session()
        assert s.execute(text("select count(*) from sales")).scalar() == 2   # the earlier good data is intact
        s.close()


def test_enqueue_without_redis_runs_in_a_background_thread(tenant):
    jid = uuid.uuid4()
    create_job(tenant, _options(tenant, jid, GOOD), job_id=jid)
    assert enqueue_job(tenant, jid) == "thread"
    deadline = time.time() + 60
    while time.time() < deadline and get_job(tenant, jid)["status"] in ("queued", "running"):
        time.sleep(0.3)
    assert get_job(tenant, jid)["status"] == "succeeded"


def test_a_tenant_cannot_see_another_tenants_job(tenant):
    admin = get_admin_session()
    other = Tenant(slug=f"job-{uuid.uuid4().hex[:8]}", name="Other", config={})
    admin.add(other)
    admin.commit()
    other_id = other.id
    try:
        jid = uuid.uuid4()
        create_job(tenant, _options(tenant, jid, GOOD), job_id=jid)
        assert get_job(other_id, jid) is None
        assert load_saved_mapping(other_id, "sales") is None
    finally:
        admin.query(Tenant).filter(Tenant.id == other_id).delete()
        admin.commit()
        admin.close()


def test_a_job_can_only_read_files_from_its_own_tenant_folder(tenant, tmp_path):
    outside = tmp_path / "elsewhere.csv"
    outside.write_text(GOOD, encoding="utf-8")
    jid = uuid.uuid4()
    opts = _options(tenant, jid, GOOD)
    opts["files"]["sales"] = str(outside)
    create_job(tenant, opts, job_id=jid)
    process_job(tenant, jid)
    assert get_job(tenant, jid)["status"] == "failed"
