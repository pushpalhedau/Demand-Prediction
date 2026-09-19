import uuid

import pytest
from sqlalchemy import text

from database.connection import get_admin_session, get_db_session, init_all_tables
from database.models import Tenant
from database.tenant_context import tenant_context
from ingestion.mapping import propose_mapping
from ingestion.pipeline import IngestError, read_csv, run_ingest


@pytest.fixture
def make_tenant():
    init_all_tables()
    made = []

    def _make():
        admin = get_admin_session()
        t = Tenant(slug=f"ing-{uuid.uuid4().hex[:8]}", name="Ingest test", config={})
        admin.add(t)
        admin.commit()
        made.append(t.id)
        admin.close()
        return t.id

    yield _make
    admin = get_admin_session()
    for tid in made:
        admin.query(Tenant).filter(Tenant.id == tid).delete()
    admin.commit()
    admin.close()


def _ingest(tid, tmp_path, texts: dict, replace=True, units=None, decimal="."):
    files = {}
    for table, body in texts.items():
        p = tmp_path / f"{table}_{uuid.uuid4().hex[:6]}.csv"
        p.write_text(body, encoding="utf-8")
        files[table] = str(p)
    mappings = {t: propose_mapping(t, list(read_csv(p).columns)).to_mapping() for t, p in files.items()}
    return run_ingest(tid, files, mappings, replace=replace, units=units or {"distance": "km"}, decimal=decimal)


def _q(tid, sql):
    with tenant_context(tid):
        s = get_db_session()
        try:
            return s.execute(text(sql)).all()
        finally:
            s.close()


SALES_ONLY = """Date,Make,Model,Dealer,State,Price,Qty
2025-01-05,Toyota,Corolla,North Motors,Texas,20000,1
2025-01-06,Toyota,Corolla,North Motors,Texas,21000,2
2025-02-01,Ford,Focus,South Auto,Ohio,18000,1
"""


def test_sales_only_upload_builds_dealers_and_vehicles_and_revenue(make_tenant, tmp_path):
    tid = make_tenant()
    r = _ingest(tid, tmp_path, {"sales": SALES_ONLY})
    assert r["loaded"]["sales"] == 3
    assert r["loaded"]["dealers"] == 2 and r["loaded"]["vehicles"] == 2
    rows = _q(tid, "select selling_price, units_sold, total_revenue_incl_tax, year, quarter, day_of_week, region "
                   "from sales order by sale_date, selling_price")
    assert rows[1] == (21000.0, 2, 42000.0, 2025, "Q1", "Monday", "Texas")
    assert {n for (n,) in _q(tid, "select dealer_name from dealers")} == {"North Motors", "South Auto"}


def test_dangling_references_are_repaired_not_rejected(make_tenant, tmp_path):
    tid = make_tenant()
    sales = "sale_id,sale_date,selling_price,customer_id,dealer_id\nS1,2025-01-01,100,C-MISSING,D-NEW\n"
    r = _ingest(tid, tmp_path, {"sales": sales})
    assert r["loaded"]["sales"] == 1
    assert _q(tid, "select customer_id from sales") == [(None,)]
    assert _q(tid, "select dealer_id from dealers") == [("D-NEW",)]
    assert any("unknown customer" in n for n in r["notes"])


def test_unit_conversions_land_in_metric(make_tenant, tmp_path):
    tid = make_tenant()
    vehicles = "vehicle_id,brand,mpg,range_miles,horsepower,price_usd\nV1,Ford,30,200,200,25000\n"
    _ingest(tid, tmp_path, {"vehicles": vehicles, "sales": "sale_date,selling_price\n2025-01-01,1\n"})
    (l100, km, kw, price), = _q(tid, "select consumption_l_per_100km, range_km, power_kw, price from vehicles where vehicle_id='V1'")
    assert l100 == pytest.approx(235.214583 / 30, rel=1e-6)
    assert km == round(200 * 1.609344)
    assert kw == round(200 * 0.7456999)
    assert price == 25000.0


def test_decimal_comma_needs_the_explicit_option(make_tenant, tmp_path):
    tid = make_tenant()
    body = 'sale_date,selling_price\n2025-01-01,"1.234,50"\n'
    _ingest(tid, tmp_path, {"sales": body}, decimal=",")
    assert _q(tid, "select selling_price from sales") == [(1234.5,)]


def test_duplicates_and_blank_required_rows_are_dropped_with_a_warning(make_tenant, tmp_path):
    tid = make_tenant()
    body = "sale_id,sale_date,selling_price\nS1,2025-01-01,10\nS1,2025-01-01,11\nS2,,12\nS3,2025-01-03,13\n"
    r = _ingest(tid, tmp_path, {"sales": body})
    assert r["loaded"]["sales"] == 2
    assert len(r["tables"]["sales"]["warnings"]) == 2


def test_unmapped_columns_are_kept_in_extras(make_tenant, tmp_path):
    tid = make_tenant()
    _ingest(tid, tmp_path, {"sales": "sale_date,selling_price,ramadan_bonus\n2025-01-01,10,yes\n"})
    assert _q(tid, "select extras->>'ramadan_bonus' from sales") == [("yes",)]


def test_a_file_with_no_usable_dates_is_rejected_and_loads_nothing(make_tenant, tmp_path):
    tid = make_tenant()
    with pytest.raises(IngestError):
        _ingest(tid, tmp_path, {"sales": "sale_date,selling_price\nnot-a-date,10\n"})
    assert _q(tid, "select count(*) from sales") == [(0,)]


def test_a_sales_file_is_required(make_tenant, tmp_path):
    tid = make_tenant()
    with pytest.raises(IngestError, match="sales"):
        _ingest(tid, tmp_path, {"dealers": "dealer_id\nD1\n"})


def test_tenants_ingesting_the_same_ids_stay_separate(make_tenant, tmp_path):
    a, b = make_tenant(), make_tenant()
    body = "sale_id,sale_date,selling_price\nS1,2025-01-01,10\nS2,2025-01-02,20\n"
    _ingest(a, tmp_path, {"sales": body})
    _ingest(b, tmp_path, {"sales": "sale_id,sale_date,selling_price\nS1,2025-03-01,999\n"})
    assert _q(a, "select count(*), sum(selling_price) from sales") == [(2, 30.0)]
    assert _q(b, "select count(*), sum(selling_price) from sales") == [(1, 999.0)]


def test_append_mode_adds_new_rows_and_skips_ones_already_loaded(make_tenant, tmp_path):
    tid = make_tenant()
    _ingest(tid, tmp_path, {"sales": "sale_id,sale_date,selling_price\nS1,2025-01-01,10\n"})
    _ingest(tid, tmp_path, {"sales": "sale_id,sale_date,selling_price\nS1,2025-01-01,10\nS2,2025-01-02,20\n"}, replace=False)
    assert _q(tid, "select count(*) from sales") == [(2,)]


def test_replace_mode_swaps_everything(make_tenant, tmp_path):
    tid = make_tenant()
    _ingest(tid, tmp_path, {"sales": "sale_id,sale_date,selling_price\nS1,2025-01-01,10\nS2,2025-01-02,20\n"})
    _ingest(tid, tmp_path, {"sales": "sale_id,sale_date,selling_price\nS9,2025-05-01,5\n"}, replace=True)
    assert _q(tid, "select sale_id from sales") == [("S9",)]
