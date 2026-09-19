"""
The scalable path: web enqueues a job in Redis and a separate worker container runs it.
  docker compose up -d db redis worker
Skipped when Redis or the worker container is not running.
"""
import subprocess
import time
import uuid

import pytest

from database.connection import get_admin_session, init_all_tables
from database.models import Tenant
from ingestion.jobs import create_job, enqueue_job, get_job

REDIS_URL = "redis://localhost:6379/0"


def _up() -> bool:
    try:
        import redis
        redis.from_url(REDIS_URL, socket_connect_timeout=1).ping()
        out = subprocess.run(["docker", "compose", "ps", "--status", "running", "-q", "worker"],
                             capture_output=True, text=True, timeout=20)
        return bool(out.stdout.strip())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _up(), reason="redis and the worker container are not running")


def _docker(*args):
    return subprocess.run(["docker", "compose", *args], capture_output=True, text=True, timeout=60, check=True)


@pytest.fixture
def tenant():
    init_all_tables()
    admin = get_admin_session()
    t = Tenant(slug=f"queue-{uuid.uuid4().hex[:8]}", name="Queue test", config={})
    admin.add(t)
    admin.commit()
    tid = t.id
    admin.close()
    yield tid
    admin = get_admin_session()
    admin.query(Tenant).filter(Tenant.id == tid).delete()
    admin.commit()
    admin.close()


def test_worker_container_runs_a_job_queued_through_redis(tenant, tmp_path, monkeypatch):
    monkeypatch.setenv("REDIS_URL", REDIS_URL)
    jid = uuid.uuid4()
    remote_dir = f"/data/uploads/{tenant}/{jid}"
    local = tmp_path / "sales.csv"
    local.write_text("sale_id,sale_date,selling_price\nQ1,2025-01-01,10\nQ2,2025-01-02,20\nQ3,2025-01-03,30\n", encoding="utf-8")
    _docker("exec", "-T", "worker", "mkdir", "-p", remote_dir)
    _docker("cp", str(local), f"worker:{remote_dir}/sales.csv")

    from ingestion.mapping import propose_mapping
    mapping = propose_mapping("sales", ["sale_id", "sale_date", "selling_price"]).to_mapping()
    create_job(tenant, {"files": {"sales": f"{remote_dir}/sales.csv"}, "mappings": {"sales": mapping},
                        "units": {"distance": "km"}, "replace": True, "train": False}, job_id=jid)

    assert enqueue_job(tenant, jid) == "queue"

    deadline = time.time() + 90
    while time.time() < deadline and get_job(tenant, jid)["status"] in ("queued", "running"):
        time.sleep(1)
    job = get_job(tenant, jid)
    assert job["status"] == "succeeded", job
    assert job["report"]["loaded"]["sales"] == 3
