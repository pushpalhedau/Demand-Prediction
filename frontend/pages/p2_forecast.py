"""Tab 2 — Forecast & Demand Intelligence"""
from __future__ import annotations

import streamlit as st
import pandas as pd

import frontend.api_client as api
from frontend.components.kpi_cards import (
    kpi_card, render_kpi_row, alert_card, section_header, KPI_CSS
)
from frontend.components.charts import (
    forecast_chart, bar_chart, feature_importance_chart, line_chart
)
from frontend.components.theme import C_INDIGO, C_EMERALD, C_AMBER


def render(filters: dict):
    st.markdown(KPI_CSS, unsafe_allow_html=True)

    # ── Controls ─────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    with c1:
        target  = st.selectbox("Forecast Target", ["units", "revenue"], key="fc_target")
    with c2:
        horizon = st.selectbox("Horizon", [30, 60, 90, 180, 365],
                                index=2, format_func=lambda x: f"{x} days",
                                key="fc_horizon")
    with c3:
        area_filter = st.text_input("Filter by Area (optional)", key="fc_area",
                                     placeholder="e.g. Dubai South")
    with c4:
        show_all = st.checkbox("Compare all models", key="fc_all", value=False)

    # ── Forecast ─────────────────────────────────────────────────
    with st.spinner("Running forecast models …"):
        try:
            fc_data = api.predict_demand(
                target=target, horizon=horizon,
                area=area_filter if area_filter.strip() else None,
            )
        except api.APIError as e:
            st.error(str(e))
            return

    metrics = fc_data.get("metrics", {})
    render_kpi_row([
        kpi_card("Best Model",   fc_data.get("model", "N/A").upper(), None, "🤖", gradient="indigo"),
        kpi_card("RMSE",  f"{metrics.get('rmse', 0):,.1f}",   None, "📉", gradient="violet"),
        kpi_card("MAPE",  f"{metrics.get('mape', 0):.1f}",    None, "🎯", suffix="%", gradient="amber"),
        kpi_card("R²",    f"{metrics.get('r2', 0):.4f}",      None, "📊", gradient="emerald"),
    ], cols=4)

    # ── Main Forecast Chart ──────────────────────────────────────
    st.markdown(section_header(
        f"{'Transaction Volume' if target=='units' else 'Revenue'} Forecast — {horizon} Days",
        f"Model: {fc_data.get('model','').upper()} | Area: {area_filter or 'All UAE'}"
    ), unsafe_allow_html=True)

    unit_label = "Transactions / Month" if target == "units" else "AED / Month"
    fig = forecast_chart(
        fc_data.get("historical", {}), fc_data.get("forecast", {}),
        title="", unit=unit_label, height=430,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Model Comparison ─────────────────────────────────────────
    if show_all:
        st.markdown(section_header("Model Comparison"), unsafe_allow_html=True)
        with st.spinner("Running all models …"):
            try:
                all_models = api.predict_all_models(target=target, horizon=horizon)
                metrics_rows = [
                    {"Model": name.upper(),
                     "RMSE": d.get("metrics", {}).get("rmse", 0),
                     "MAE":  d.get("metrics", {}).get("mae", 0),
                     "MAPE %": d.get("metrics", {}).get("mape", 0),
                     "R²":   d.get("metrics", {}).get("r2", 0)}
                    for name, d in all_models.items()
                ]
                if metrics_rows:
                    df_m = pd.DataFrame(metrics_rows).sort_values("MAPE %")
                    st.dataframe(df_m.set_index("Model"), use_container_width=True)
            except api.APIError as e:
                st.warning(str(e))

    # ── Feature Importance / Demand Drivers ──────────────────────
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(section_header("Demand Drivers (SHAP)"), unsafe_allow_html=True)
        try:
            drivers = api.get_demand_drivers(target=target)
            fi = drivers.get("feature_importance", [])
            if fi:
                fig = feature_importance_chart(fi, height=380)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Train models to view SHAP feature importance.")
        except api.APIError as e:
            st.warning(str(e))

    with col2:
        st.markdown(section_header("Area-Level Forecast Trend"), unsafe_allow_html=True)
        try:
            area_fc = api.get_forecast_by_area(target=target, horizon=horizon, top_n=8)
            if area_fc:
                rows = [{"Area": a, "Model": v.get("model","").upper(),
                          "MAPE %": v.get("mape",0), "Trend": "↑" if v.get("trend")=="up" else "↓"}
                         for a, v in area_fc.items()]
                df_a = pd.DataFrame(rows).sort_values("MAPE %")
                st.dataframe(df_a.set_index("Area"), use_container_width=True, height=380)
        except api.APIError as e:
            st.warning(str(e))

    # ── Early Warning Signals ─────────────────────────────────────
    st.markdown(section_header("Early Warning Signals"), unsafe_allow_html=True)
    try:
        ew = api.get_early_warnings()
        warnings = ew.get("warnings", [])
        if not warnings:
            st.markdown(
                '<div style="color:#10b981;font-size:14px;padding:12px">✓ No early warning signals detected. Market conditions appear stable.</div>',
                unsafe_allow_html=True,
            )
        for w in warnings:
            st.markdown(
                alert_card(w["signal"], w["description"], w.get("severity","warning"), w.get("action","")),
                unsafe_allow_html=True,
            )
    except api.APIError as e:
        st.warning(str(e))
