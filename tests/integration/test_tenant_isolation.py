import datetime
import uuid

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.core.request_context import tenant_context
from backend.db.connection import get_admin_session, get_db_session, get_engine, init_all_tables
from backend.db.models import Dealer, Sale, Tenant


@pytest.fixture(scope="module")
def tenants():
    init_all_tables()
    admin = get_admin_session()
    made = []
    for label in ("alpha", "beta"):
        t = Tenant(slug=f"test-{label}-{uuid.uuid4().hex[:8]}", name=f"Test {label}", config={"currency": "EUR"})
        admin.add(t)
        made.append(t)
    admin.commit()
    ids = [t.id for t in made]
    admin.close()

    for i, tid in enumerate(ids):
        with tenant_context(tid):
            s = get_db_session()
            # Identical business keys in both tenants: only legal because tenant_id is part of the PK.
            s.add(Dealer(dealer_id="D1", dealer_name=f"Dealer of tenant {i}"))
            s.flush()
            s.add(Sale(sale_id="S1", sale_date=datetime.date(2025, 1, 1), dealer_id="D1", units_sold=i + 1))
            s.commit()
            s.close()

    yield ids

    admin = get_admin_session()
    for tid in ids:
        admin.query(Tenant).filter(Tenant.id == tid).delete()
    admin.commit()
    admin.close()


def test_each_tenant_sees_only_its_own_rows(tenants):
    for i, tid in enumerate(tenants):
        with tenant_context(tid):
            s = get_db_session()
            sales = s.query(Sale).all()
            dealers = s.query(Dealer).all()
            s.close()
        assert len(sales) == 1 and sales[0].units_sold == i + 1
        assert len(dealers) == 1 and dealers[0].dealer_name == f"Dealer of tenant {i}"


def test_no_tenant_context_fails_closed(tenants):
    s = get_db_session()
    assert s.query(Sale).count() == 0
    assert s.query(Dealer).count() == 0
    s.close()


def test_raw_sql_and_pandas_are_scoped(tenants):
    with tenant_context(tenants[0]):
        df = pd.read_sql(text("SELECT * FROM sales"), get_engine())
    assert len(df) == 1 and int(df.units_sold[0]) == 1


def test_cannot_write_a_row_for_another_tenant(tenants):
    with tenant_context(tenants[0]):
        s = get_db_session()
        with pytest.raises(DBAPIError):
            s.add(Dealer(tenant_id=tenants[1], dealer_id="D-evil", dealer_name="x"))
            s.flush()
        s.rollback()
        s.close()


def test_cannot_update_or_delete_another_tenants_rows(tenants):
    with tenant_context(tenants[0]):
        s = get_db_session()
        s.execute(text("UPDATE sales SET units_sold = 999 WHERE tenant_id = :t"), {"t": str(tenants[1])})
        s.execute(text("DELETE FROM dealers WHERE tenant_id = :t"), {"t": str(tenants[1])})
        s.commit()
        s.close()
    with tenant_context(tenants[1]):
        s = get_db_session()
        assert s.query(Sale).one().units_sold == 2
        assert s.query(Dealer).count() == 1
        s.close()


def test_pooled_connection_does_not_leak_previous_tenant(tenants):
    eng = get_engine()
    for _ in range(5):
        with tenant_context(tenants[0]):
            with eng.connect() as c:
                assert c.execute(text("SELECT count(*) FROM sales")).scalar() == 1
        with eng.connect() as c:  # same physical connection, no tenant now
            assert c.execute(text("SELECT count(*) FROM sales")).scalar() == 0


def test_tenant_cannot_modify_its_own_tenant_row(tenants):
    with tenant_context(tenants[0]):
        s = get_db_session()
        assert s.execute(text("SELECT count(*) FROM tenants")).scalar() == 1   # sees only itself
        with pytest.raises(DBAPIError):
            s.execute(text("UPDATE tenants SET status = 'active'"))
        s.rollback()
        s.close()
