"""
The scalable path: the app enqueues a job in Redis and a separate `rq worker` process runs it. There is no worker
container any more, so this spins one up as a plain subprocess against the same REDIS_URL/UPLOAD_DIR the test
itself uses (both share this machine's filesystem directly -- nothing needs to be copied into a container).
Skipped when Redis is not reachable.
"""
import os
import subprocess
import sys
import time
import uuid

import pytest

from backend.db.connection import get_admin_session, init_all_tables
from backend.db.models import Tenant
from backend.ingestion.jobs import create_job, enqueue_job, get_job, job_dir

REDIS_URL = os.getenv("REDIS_URL") or f"redis://:{os.getenv('REDIS_PASSWORD', 'predictax_redis_dev')}@localhost:6379/0"


def _redis_up() -> bool:
    try:
        import redis
        return bool(redis.from_url(REDIS_URL, socket_connect_timeout=1).ping())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _redis_up(), reason="Redis is not reachable")


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


@pytest.fixture
def worker():
    """A real `rq worker ingest` process, inheriting this process's environment (so it reads/writes the same
    database and UPLOAD_DIR/MODEL_DIR the test does)."""
    env = {**os.environ, "REDIS_URL": REDIS_URL}
    proc = subprocess.Popen([sys.executable, "-m", "rq", "worker", "ingest", "--url", REDIS_URL],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(1)  # let it connect before jobs are enqueued
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_worker_process_runs_a_job_queued_through_redis(tenant, worker, tmp_path, monkeypatch):
    monkeypatch.setenv("REDIS_URL", REDIS_URL)
    jid = uuid.uuid4()

    staged = job_dir(tenant, jid)  # the same helper the upload endpoint itself uses to stage a file
    (staged / "sales.csv").write_text("sale_id,sale_date,selling_price\nQ1,2025-01-01,10\nQ2,2025-01-02,20\nQ3,2025-01-03,30\n",
                                      encoding="utf-8")

    from backend.ingestion.mapping import propose_mapping
    mapping = propose_mapping("sales", ["sale_id", "sale_date", "selling_price"]).to_mapping()
    create_job(tenant, {"files": {"sales": str(staged / "sales.csv")}, "mappings": {"sales": mapping},
                        "units": {"distance": "km"}, "replace": True, "train": False}, job_id=jid)

    assert enqueue_job(tenant, jid) == "queue"

    deadline = time.time() + 90
    while time.time() < deadline and get_job(tenant, jid)["status"] in ("queued", "running"):
        time.sleep(1)
    job = get_job(tenant, jid)
    assert job["status"] == "succeeded", (job, worker.stdout.read() if worker.poll() is not None else "")
    assert job["report"]["loaded"]["sales"] == 3
