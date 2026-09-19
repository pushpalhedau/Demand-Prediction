import re
import time
import uuid

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from frontend.customer_app.auth import _load_active_tenant
from backend.auth.client import Identity
from backend.db.connection import get_admin_session, init_all_tables
from backend.db.models import Tenant
from backend.core.request_context import tenant_context
from backend.ingestion.mapping import propose_mapping
from backend.ingestion.pipeline import read_csv, run_ingest
from backend.tenancy.capabilities import get_capabilities, tab_available
from backend.tenancy.provision import get_tenant_id

ALL_TABS = ["tab.overview", "tab.forecasting", "tab.comparison", "tab.regional",
            "tab.customers", "tab.inventory", "tab.sentiment"]
DEMO = ["germany-demo", "uae-demo", "na-demo"]
# A market's own currency must never show up in another market's dashboards.
EURO = "€"
FOREIGN = {"germany-demo": ("AED", "$", "USD"), "uae-demo": (EURO, "EUR", "$", "USD"),
           "na-demo": (EURO, "EUR", "AED")}


def _login(tenant_id, role="tenant_admin", page=None):
    """Same session state a real login produces (see auth.gate._establish_session)."""
    tenant = _load_active_tenant(tenant_id)
    at = AppTest.from_file("frontend/customer_app/main.py", default_timeout=240)
    ss = at.session_state
    ss["identity"] = Identity("u1", "user@example.com", tenant_id, role)
    ss["tenant_id"] = str(tenant_id)
    ss["tenant_name"] = tenant.name
    ss["tenant_config"] = dict(tenant.config or {})
    ss["auth_refresh_token"] = "x"
    ss["auth_exp"] = time.time() + 3600
    if tenant.config.get("language") in ("en", "de"):
        ss["lang"] = tenant.config["language"]
    if page:
        ss["active_page"] = page
    return at


def _visible_text(at) -> str:
    parts = []
    for group in (at.markdown, at.caption, at.text, at.info, at.warning, at.success, at.subheader, at.header, at.title):
        parts += [e.value for e in group]
    for m in at.metric:
        parts += [m.label, str(m.value), str(m.delta)]
    return re.sub(r"<style.*?</style>", "", "\n".join(str(p) for p in parts), flags=re.S)


def test_logged_out_visitor_only_sees_login(monkeypatch):
    monkeypatch.setenv("AUTH_BASE_URL", "http://localhost:9999")
    at = AppTest.from_file("frontend/customer_app/main.py", default_timeout=60).run()
    assert not at.exception
    assert [t.label for t in at.text_input] == ["Email", "Password"]
    assert len(at.selectbox) == 0   # no dashboard filters rendered


def test_empty_account_is_told_it_is_being_set_up():
    init_all_tables()
    db = get_admin_session()
    t = Tenant(slug=f"empty-{uuid.uuid4().hex[:8]}", name="Empty", config={"currency": "USD", "language": "en"})
    db.add(t)
    db.commit()
    tid = t.id
    try:
        at = _login(tid).run()
        assert not at.exception, [e.value for e in at.exception]
        text = _visible_text(at)
        assert "Your account is being set up" in text
        assert "Upload" not in text           # customers never see an upload surface
        assert not at.sidebar.selectbox       # and no dashboard filters
    finally:
        db.query(Tenant).filter(Tenant.id == tid).delete()
        db.commit()
        db.close()


@pytest.mark.parametrize("slug", DEMO)
@pytest.mark.parametrize("page", ALL_TABS)
def test_every_page_renders_and_stays_in_its_own_market(slug, page):
    at = _login(get_tenant_id(slug), page=page).run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    text = _visible_text(at)
    assert "{cur" not in text and "cur()" not in text
    for token in FOREIGN[slug]:
        assert token not in text, f"{slug}/{page} shows {token!r}"


def test_customer_app_has_no_data_upload_tab():
    for slug in DEMO:
        at = _login(get_tenant_id(slug), page="tab.overview").run()
        labels = [b.label for b in at.sidebar.button]
        assert not any("Data" == l or "Upload" in l for l in labels)
        assert "Upload your files" not in _visible_text(at)


def test_region_label_follows_the_tenant():
    for slug, label in (("uae-demo", "Emirate"), ("na-demo", "State"), ("germany-demo", "Bundesland")):
        at = _login(get_tenant_id(slug), page="tab.overview").run()
        assert label in [s.label for s in at.sidebar.selectbox], slug


@pytest.fixture(scope="module")
def sales_only_tenant():
    """A tenant that uploaded nothing but one sales file (no dealers, vehicles, customers or inventory)."""
    init_all_tables()
    db = get_admin_session()
    t = Tenant(slug=f"salesonly-{uuid.uuid4().hex[:8]}", name="Sales Only Motors",
               config={"currency": "GBP", "currency_symbol": "£", "language": "en", "region_label": "County"})
    db.add(t)
    db.commit()
    tid = t.id
    rng = np.random.default_rng(7)
    days = pd.date_range("2024-01-01", "2025-06-30", freq="D")
    rows = []
    for d in days:
        for _ in range(int(rng.integers(2, 6))):
            brand = rng.choice(["Ford", "Nissan", "BMW"])
            rows.append({"Date": d.date().isoformat(), "Make": brand, "Model": f"{brand}-{rng.integers(1, 4)}",
                         "Dealer": rng.choice(["Leeds", "Bristol"]), "County": rng.choice(["Yorkshire", "Avon"]),
                         "Price": int(rng.integers(12000, 60000)), "Qty": 1})
    import tempfile, os
    path = os.path.join(tempfile.mkdtemp(), "sales.csv")
    pd.DataFrame(rows).to_csv(path, index=False)
    mapping = propose_mapping("sales", list(read_csv(path).columns)).to_mapping()
    run_ingest(tid, {"sales": path}, {"sales": mapping})
    yield tid
    db.query(Tenant).filter(Tenant.id == tid).delete()
    db.commit()
    db.close()


def test_sales_only_tenant_gets_only_the_tabs_it_can_populate(sales_only_tenant):
    with tenant_context(sales_only_tenant):
        caps = get_capabilities()
        visible = [k for k in ALL_TABS if tab_available(k, caps)]
    assert not caps["customers"] and not caps["inventory"]
    assert "tab.customers" not in visible and "tab.inventory" not in visible
    assert {"tab.overview", "tab.forecasting", "tab.sentiment"} <= set(visible)


def test_every_available_tab_renders_for_a_sales_only_tenant(sales_only_tenant):
    with tenant_context(sales_only_tenant):
        visible = [k for k in ALL_TABS if tab_available(k, get_capabilities())]
    for page in visible:
        at = _login(sales_only_tenant, page=page).run()
        assert not at.exception, (page, [e.value for e in at.exception])
        assert not at.error, (page, [e.value for e in at.error])
        text = _visible_text(at)
        assert not any(tok in text for tok in (EURO, "AED", "$", "USD", "EUR")), (page, "shows another market's currency")
