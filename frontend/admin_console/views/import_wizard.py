"""
Import screen for one customer account: upload CSVs -> confirm column mapping -> import.

The import runs as a background job (ingestion/jobs.py); this page collects the files and
mapping, then follows the job's progress. It is driven by an explicit tenant_id (the account
the operator selected), never by a customer session.
"""
import time
import uuid

import pandas as pd
import streamlit as st

from backend.services import imports as imports_service
from backend.services.imports import (
    AUTO_CONFIDENCE, GAL_TO_L, HP_TO_KW, L100_FROM_MPG, LOAD_ORDER, MI_TO_KM, PS_TO_KW, SQFT_TO_SQM, TABLES,
    IngestError,
)

_NOT_MAPPED = "(not mapped)"

_TABLE_HELP = {
    "sales": "Required. One row per sale: a date, a price or revenue, and ideally brand, model, dealer and region.",
    "dealers": "Optional. Their stores. Built from the sales file if skipped.",
    "vehicles": "Optional. Their model catalogue. Built from the sales file if skipped.",
    "customers": "Optional. Unlocks Customer Intelligence.",
    "inventory": "Optional. Stock snapshots. Unlocks Inventory & Placement.",
    "external_factors": "Optional. Monthly fuel prices, rates, indices. Sharpens the forecast.",
}

_UNIT_OPTIONS = {
    "none": None,
    "x 12  (monthly to annual)": ("mul", 12),
    "x 0.7457  (horsepower to kW)": ("mul", HP_TO_KW),
    "x 0.7355  (PS to kW)": ("mul", PS_TO_KW),
    "100 / x  (km per litre to l/100km)": ("inv", 100.0),
    "235.2 / x  (mpg to l/100km)": ("inv", L100_FROM_MPG),
    "x 1.609  (miles to km)": ("mul", MI_TO_KM),
    "x 0.0929  (sq ft to sq m)": ("mul", SQFT_TO_SQM),
    "x 0.264  (per gallon to per litre)": ("mul", 1 / GAL_TO_L),
}


def _unit_label(transform):
    if not transform:
        return "none"
    for label, t in _UNIT_OPTIONS.items():
        if t and t[0] == transform[0] and abs(t[1] - transform[1]) <= 1e-6 * max(1.0, abs(t[1])):
            return label
    return "none"


def _key(tenant_id) -> str:
    return f"dw_{tenant_id}"


def _state(tenant_id) -> dict:
    return st.session_state.setdefault(_key(tenant_id), {"job": str(uuid.uuid4()), "files": {}, "props": {},
                                                          "sizes": {}, "started": False})


def _reset(tenant_id):
    st.session_state.pop(_key(tenant_id), None)
    for k in [k for k in st.session_state if str(k).startswith((f"up_{tenant_id}_", f"map_{tenant_id}_"))]:
        st.session_state.pop(k, None)


def _templates(tenant_id):
    with st.expander("Template CSVs to send the customer"):
        cols = st.columns(3)
        for i, table in enumerate(LOAD_ORDER):
            header = ",".join(f.name for f in TABLES[table] if not f.derived)
            cols[i % 3].download_button(f"{table}.csv template", header + "\n", file_name=f"{table}_template.csv",
                                        key=f"tpl_{tenant_id}_{table}")
        st.caption("Their own column names are fine: the next step matches them automatically.")


def _step_upload(ds, tenant_id):
    st.subheader("1. Upload the customer's files")
    st.caption("CSV files, up to 500 MB each. Only the sales file is required.")
    for table in LOAD_ORDER:
        up = st.file_uploader(table.replace("_", " ").title() + (" *" if table == "sales" else ""),
                              type=["csv"], key=f"up_{tenant_id}_{table}", help=_TABLE_HELP[table])
        if up is None:
            ds["files"].pop(table, None)
            ds["props"].pop(table, None)
            continue
        sig = (up.name, up.size)
        if ds["sizes"].get(table) != sig:
            path = imports_service.save_upload(tenant_id, ds["job"], table, up.getbuffer())
            ds["files"][table] = str(path)
            ds["sizes"][table] = sig
            ds["props"].pop(table, None)
        st.caption(_TABLE_HELP[table])


def _proposal(ds, tenant_id, table):
    if table not in ds["props"]:
        cols = imports_service.read_header(ds["files"][table])
        prop = imports_service.propose(table, cols)
        saved = imports_service.saved_mapping(tenant_id, table)
        if saved and all(c["source"] in cols for c in saved["columns"].values()):
            ds["props"][table] = {"prop": prop, "cols": cols, "saved": saved["columns"]}
        else:
            ds["props"][table] = {"prop": prop, "cols": cols, "saved": None}
    return ds["props"][table]


def _mapping_grid(ds, tenant_id, table):
    info = _proposal(ds, tenant_id, table)
    prop, cols, saved = info["prop"], info["cols"], info["saved"]
    rows = []
    for f in TABLES[table]:
        if saved is not None:
            c = saved.get(f.name)
            src = c["source"] if c else _NOT_MAPPED
            tf = tuple(c["transform"]) if c and c.get("transform") else None
            how = "saved from the last import" if c else ""
        else:
            ch = prop.choices.get(f.name)
            src, tf = (ch.source, ch.transform) if ch else (_NOT_MAPPED, None)
            how = ch.confidence if ch else ""
        rows.append({"Field": f.name + ("  *" if f.required else ""), "Their column": src,
                     "Unit conversion": _unit_label(tf), "Match": how})
    st.caption(f"{len(cols)} columns found. Anything left unmapped is kept as an extra field, not lost.")
    edited = st.data_editor(
        pd.DataFrame(rows), key=f"map_{tenant_id}_{table}", hide_index=True, use_container_width=True,
        height=min(420, 40 + 35 * len(rows)), disabled=["Field", "Match"],
        column_config={
            "Their column": st.column_config.SelectboxColumn(options=[_NOT_MAPPED] + cols, required=True),
            "Unit conversion": st.column_config.SelectboxColumn(options=list(_UNIT_OPTIONS), required=True),
        },
    )
    fuzzy = [f.name for f in TABLES[table]
             if saved is None and f.name in prop.choices and prop.choices[f.name].confidence not in AUTO_CONFIDENCE]
    if fuzzy:
        st.warning("Please double-check these guesses (spelling was close but not exact): " + ", ".join(fuzzy))
    columns = {}
    for f, (_, r) in zip(TABLES[table], edited.iterrows()):
        if r["Their column"] != _NOT_MAPPED:
            tf = _UNIT_OPTIONS[r["Unit conversion"]]
            columns[f.name] = {"source": r["Their column"], "transform": list(tf) if tf else None}
    return {"columns": columns, "extras": True}, prop


def _step_map(ds, tenant_id):
    st.subheader("2. Check the column matching")
    mappings, imperial = {}, False
    for table in [t for t in LOAD_ORDER if t in ds["files"]]:
        with st.expander(table.replace("_", " ").title(), expanded=(table == "sales")):
            mappings[table], prop = _mapping_grid(ds, tenant_id, table)
            imperial = imperial or prop.imperial_hint

    c1, c2, c3, c4 = st.columns(4)
    dayfirst = c1.selectbox("Dates are written", ["Year-Month-Day (or auto)", "Day/Month/Year"]) == "Day/Month/Year"
    decimal = c2.selectbox("Decimal separator", [". (1,234.50)", ", (1.234,50)"])[0]
    distance = c3.selectbox("Distances (mileage) are in", ["km", "miles"], index=1 if imperial else 0)
    replace = c4.selectbox("Import mode", ["Replace all their data", "Add to their existing data"]) == "Replace all their data"
    units = {"distance": "mi" if distance == "miles" else "km"}

    ok = True
    if st.button("Check the data"):
        for table, mp in mappings.items():
            try:
                rep = imports_service.dry_run(table, ds["files"][table], mp, units, dayfirst, decimal)
                bad = rep["coercion_failures"]
                msg = f"{table}: looks good ({rep['rows_out']:,} of {rep['rows_in']:,} sample rows usable)"
                if bad:
                    msg += " | values that could not be read: " + ", ".join(f"{k} ({v})" for k, v in bad.items())
                (st.warning if bad or rep["warnings"] else st.success)(msg)
                for w in rep["warnings"]:
                    st.caption(w)
            except IngestError as e:
                ok = False
                st.error(str(e))
    return mappings, units, dayfirst, decimal, replace, ok


def _render_progress(ds, tenant_id):
    job = imports_service.job_status(tenant_id, ds["job"])
    if job is None:
        _reset(tenant_id)
        st.rerun()
    st.subheader("Importing")
    if job["status"] in ("queued", "running"):
        st.progress(float(job["progress"]), text=job["stage"] or "Working")
        st.caption("You can keep this page open. Large files take a few minutes.")
        time.sleep(1.5)
        st.rerun()
    elif job["status"] == "succeeded":
        rep = job["report"] or {}
        st.success("Import complete. The account's dashboards are live.")
        st.write({t: f"{n:,} rows" for t, n in rep.get("loaded", {}).items()})
        for n in rep.get("notes", []):
            st.info(n)
        for t, r in (rep.get("tables") or {}).items():
            for w in r.get("warnings", []):
                st.caption(f"{t}: {w}")
        if st.button("Done", type="primary", key=f"done_{tenant_id}"):
            imports_service.publish_data_changes()
            _reset(tenant_id)
            st.rerun()
    else:
        st.error(job["message"] or "The import failed.")
        if st.button("Go back and fix", key=f"back_{tenant_id}"):
            ds["started"] = False
            ds["job"] = str(uuid.uuid4())     # a retry is a new job; uploaded files stay where they were saved
            st.rerun()


def render_import(tenant_id, operator_email: str):
    ds = _state(tenant_id)
    if ds["started"]:
        _render_progress(ds, tenant_id)
        return
    _templates(tenant_id)
    _step_upload(ds, tenant_id)
    if "sales" not in ds["files"]:
        st.info("Upload the sales file to continue.")
        return

    mappings, units, dayfirst, decimal, replace, ok = _step_map(ds, tenant_id)
    st.subheader("3. Import")
    st.caption("Models retrain automatically once the data is loaded.")
    if st.button("Import and train", type="primary", disabled=not ok, key=f"go_{tenant_id}"):
        imports_service.start_import(tenant_id, ds["job"], {
            "files": ds["files"], "mappings": mappings, "units": units, "dayfirst": dayfirst,
            "decimal": decimal, "replace": replace, "train": True,
        }, created_by=operator_email)
        ds["started"] = True
        st.rerun()
