import uuid

from streamlit.testing.v1 import AppTest


def _script(csv_path: str, tenant_id: str):
    import uuid as _uuid

    import streamlit as st

    from frontend.admin_console.views import import_wizard as u

    ds = {"job": "j", "files": {"sales": csv_path}, "props": {}, "sizes": {}, "started": False}
    mappings, units, dayfirst, decimal, replace, ok = u._step_map(ds, _uuid.UUID(tenant_id))
    st.session_state["out"] = {"mappings": mappings, "units": units, "replace": replace, "ok": ok}


def _run(tmp_path, body):
    p = tmp_path / "sales.csv"
    p.write_text(body, encoding="utf-8")
    return AppTest.from_function(_script, args=(str(p), str(uuid.uuid4())), default_timeout=60).run()


def test_mapping_step_pre_fills_from_the_customers_own_column_names(tmp_path):
    at = _run(tmp_path, "Date,Make,Model,Dealer,State,Price_EUR,Qty\n2025-01-01,Ford,Focus,Leeds,Ohio,100,1\n")
    assert not at.exception, [e.value for e in at.exception]
    cols = at.session_state["out"]["mappings"]["sales"]["columns"]
    assert cols["sale_date"]["source"] == "Date"
    assert cols["brand"]["source"] == "Make"
    assert cols["region"]["source"] == "State"
    assert cols["selling_price"]["source"] == "Price_EUR"
    assert cols["units_sold"]["source"] == "Qty"
    assert at.session_state["out"]["units"] == {"distance": "km"}
    assert at.session_state["out"]["replace"] is True


def test_check_my_data_reports_success_for_a_good_file(tmp_path):
    at = _run(tmp_path, "sale_date,selling_price\n2025-01-01,100\n2025-01-02,200\n")
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("looks good" in s.value for s in at.success)


def test_check_my_data_flags_unreadable_values(tmp_path):
    at = _run(tmp_path, "sale_date,selling_price\n2025-01-01,100\n2025-01-02,abc\n")
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("selling_price" in w.value for w in at.warning)


def test_check_my_data_errors_when_there_are_no_usable_dates(tmp_path):
    at = _run(tmp_path, "sale_date,selling_price\nsoon,100\n")
    at.button[0].click().run()
    assert any("no usable rows" in e.value for e in at.error)
