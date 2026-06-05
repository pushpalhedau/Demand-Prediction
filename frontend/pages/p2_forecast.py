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
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        target  = st.selectbox("Forecast Target", ["units", "revenue"], key="fc_target")
    with c2:
        horizon = st.selectbox("Horizon", [30, 60, 90, 180, 365],
                                index=2, format_func=lambda x: f"{x} days",
                                key="fc_horizon")
    with c3:
        area_filter = st.text_input("Filter by Area (optional)", key="fc_area",
                                     placeholder="e.g. Dubai South")
    # show_all = st.checkbox("Compare all models", key="fc_all", value=False)
    show_all = False

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
        kpi_card("Best Model", fc_data.get("model", "N/A").upper(), None, gradient="indigo",
                 help_text="ML model with the lowest MAPE on the 20% holdout test set. Candidates: CatBoost, Prophet (time-series), and LightGBM. Retrained on the full DLD transaction history."),
        kpi_card("RMSE", f"{metrics.get('rmse', 0):,.1f}", None, gradient="violet",
                 help_text="Root Mean Square Error on the test set. Measures average prediction error in the same unit as the forecast target (transactions or AED). Lower values indicate a more accurate model."),
        kpi_card("MAPE", f"{metrics.get('mape', 0):.1f}", None, suffix="%", gradient="amber",
                 help_text="Mean Absolute Percentage Error on the 20% holdout test set. Measures average % deviation from actual values. Under 10% is considered strong for real estate demand forecasting."),
        kpi_card("R²", f"{metrics.get('r2', 0):.4f}", None, gradient="emerald",
                 help_text="Coefficient of determination on the test set. Measures how much of the variance in actuals is explained by the model. Values above 0.85 indicate strong predictive power."),
    ], cols=4)

    # ── Main Forecast Chart ──────────────────────────────────────
    st.markdown(section_header(
        f"{'Transaction Volume' if target=='units' else 'Revenue'} Forecast — {horizon} Days",
        f"Model: {fc_data.get('model','').upper()} | Area: {area_filter or 'All UAE'}",
        help_text="Historical DLD transaction data (solid line) with the model's forecast (dashed) for the selected horizon. Confidence bands show the 90% prediction interval. Historical period: 2019–2024."
    ), unsafe_allow_html=True)

    unit_label = "Transactions / Month" if target == "units" else "AED / Month"
    fig = forecast_chart(
        fc_data.get("historical", {}), fc_data.get("forecast", {}),
        title="", unit=unit_label, height=460,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Forecast summary stats strip
    fc_vals = fc_data.get("forecast", {}).get("values", [])
    if fc_vals:
        peak      = max(fc_vals)
        trough    = min(fc_vals)
        trend_pct = ((fc_vals[-1] - fc_vals[0]) / fc_vals[0] * 100) if fc_vals[0] else 0
        trend_dir = "↑" if trend_pct >= 0 else "↓"
        trend_col = "#10b981" if trend_pct >= 0 else "#ef4444"
        hist_last = (fc_data.get("historical", {}).get("values") or [None])[-1]
        vs_now    = f" vs now: <b style='color:{trend_col}'>{trend_dir} {abs((fc_vals[-1]-hist_last)/hist_last*100):.1f}%</b>" if hist_last else ""
        st.markdown(f"""
<div style="display:flex;gap:24px;padding:10px 4px 2px;border-top:1px solid #1e1e3f;margin-top:-4px;flex-wrap:wrap">
  <span style="color:#64748b;font-size:12px;font-family:Inter,sans-serif">Peak: <b style="color:#f1f5f9">{peak:,.0f}</b></span>
  <span style="color:#64748b;font-size:12px;font-family:Inter,sans-serif">Low: <b style="color:#f1f5f9">{trough:,.0f}</b></span>
  <span style="color:#64748b;font-size:12px;font-family:Inter,sans-serif">Trend over horizon: <b style="color:{trend_col}">{trend_dir} {abs(trend_pct):.1f}%</b></span>{vs_now}
  <span style="color:#64748b;font-size:12px;font-family:Inter,sans-serif">Horizon: <b style="color:#f1f5f9">{horizon} days</b></span>
</div>""", unsafe_allow_html=True)

    # ── Model Comparison ─────────────────────────────────────────
    if show_all:
        st.markdown(section_header("Model Comparison",
            help_text="Side-by-side accuracy metrics for all available models (CatBoost, Prophet, LightGBM) evaluated on the same 20% holdout test set. Sorted by MAPE ascending."),
            unsafe_allow_html=True)
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
        st.markdown(section_header("Demand Drivers (SHAP)",
            help_text="SHAP (SHapley Additive exPlanations) values showing which features most influence the model's predictions. Longer bars = stronger impact. Derived from the full DLD training dataset (2019–2024)."),
            unsafe_allow_html=True)
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
        st.markdown(section_header("Area-Level Forecast Trend",
            help_text="Per-area sub-model accuracy and demand direction for the selected target and horizon. MAPE reflects each area's individual forecast quality. Trend arrow = projected direction vs. current period."),
            unsafe_allow_html=True)
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
    st.markdown(section_header("Early Warning Signals",
        help_text="Anomaly detection alerts flagging areas or time periods where demand is diverging significantly from historical seasonal norms. Reviewed monthly using DLD and GDELT data."),
        unsafe_allow_html=True)
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
