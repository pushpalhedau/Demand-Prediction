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
        try:
            _areas = api.get_all_areas()
        except Exception:
            _areas = []
        _area_opts = ["All Areas"] + _areas
        _area_sel  = st.selectbox("Filter by Area", _area_opts, key="fc_area")
        area_filter = "" if _area_sel == "All Areas" else _area_sel
    # show_all = st.checkbox("Compare all models", key="fc_all", value=False)
    show_all = False

    # ── Forecast ─────────────────────────────────────────────────
    with st.spinner("Running forecast models …"):
        try:
            fc_data = api.predict_demand(
                target=target, horizon=horizon,
                area=area_filter if area_filter else None,
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
                 help_text="Coefficient of determination on the validation set. Negative R² means the model's error variance exceeds the validation set's own variance — typically caused by a market regime shift between training and validation periods. A low MAPE alongside negative R² is not a contradiction: MAPE measures percentage closeness, while R² measures variance explained."),
    ], cols=4)

    drift = fc_data.get("drift_info", {})
    if drift.get("drift_detected"):
        st.warning(
            f"**Distribution Drift Detected** — Training mean: {drift.get('train_mean', 0):,.0f} units "
            f"→ Validation mean: {drift.get('val_mean', 0):,.0f} units "
            f"({drift.get('mean_shift_pct', 0):.0f}% shift). "
            "This is a real structural market shift (UAE rate hike 2022 → sustained demand plateau). "
            "Mitigations applied: detrended targets (model predicts ±deviation from trailing 12-month mean), "
            "exponential time-decay sample weights (recent months weighted up to 10× more), "
            "and 6-month validation window including 2024 plateau data. "
            "Negative R² is expected when validation variance is narrower than model RMSE — MAPE is the reliable accuracy metric here."
        )

    # ── Main Forecast Chart ──────────────────────────────────────
    st.markdown(section_header(
        f"{'Transaction Volume' if target=='units' else 'Revenue'} Forecast — {horizon} Days",
        f"Model: {fc_data.get('model','').upper()} | Area: {area_filter or 'All UAE'}",
        help_text="Historical DLD transaction data (solid line) with the model's forecast (dashed) for the selected horizon. Confidence bands show the 90% prediction interval. Historical period: 2019–2024."
    ), unsafe_allow_html=True)

    unit_label = "Transactions / Day" if target == "units" else "AED / Day"
    fig = forecast_chart(
        fc_data.get("historical", {}), fc_data.get("forecast", {}),
        historical_daily=fc_data.get("historical_daily"),
        forecast_daily=fc_data.get("forecast_daily"),
        title="", unit=unit_label, height=480,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Forecast summary stats strip (values are monthly totals)
    fc_vals = fc_data.get("forecast", {}).get("values", [])
    if fc_vals:
        peak      = max(fc_vals)
        trough    = min(fc_vals)
        trend_pct = ((fc_vals[-1] - fc_vals[0]) / fc_vals[0] * 100) if fc_vals[0] else 0
        trend_dir = "↑" if trend_pct >= 0 else "↓"
        trend_col = "#10b981" if trend_pct >= 0 else "#ef4444"
        hist_last = (fc_data.get("historical", {}).get("values") or [None])[-1]
        vs_now_html = (
            f"<span style='color:{trend_col};font-size:15px;font-family:Inter,sans-serif;"
            f"font-weight:700;margin-top:2px'>"
            f"{trend_dir} {abs((fc_vals[-1]-hist_last)/hist_last*100):.1f}%</span>"
        ) if hist_last else ""
        _unit_short = "txns" if target == "units" else "AED"
        st.markdown(f"""
<div style="display:flex;gap:0;margin-top:2px;margin-bottom:8px;background:#0d0d20;border:1px solid #1e1e3f;border-radius:8px;overflow:hidden;flex-wrap:wrap">
  <div style="display:flex;flex-direction:column;padding:10px 20px;border-right:1px solid #1e1e3f;min-width:130px">
    <span style="color:#64748b;font-size:10px;font-family:Inter,sans-serif;text-transform:uppercase;letter-spacing:0.07em;font-weight:600">Peak Month</span>
    <span style="color:#f1f5f9;font-size:15px;font-family:Inter,sans-serif;font-weight:700;margin-top:2px">{peak:,.0f} <span style="color:#475569;font-size:11px">{_unit_short}</span></span>
  </div>
  <div style="display:flex;flex-direction:column;padding:10px 20px;border-right:1px solid #1e1e3f;min-width:130px">
    <span style="color:#64748b;font-size:10px;font-family:Inter,sans-serif;text-transform:uppercase;letter-spacing:0.07em;font-weight:600">Low Month</span>
    <span style="color:#f1f5f9;font-size:15px;font-family:Inter,sans-serif;font-weight:700;margin-top:2px">{trough:,.0f} <span style="color:#475569;font-size:11px">{_unit_short}</span></span>
  </div>
  <div style="display:flex;flex-direction:column;padding:10px 20px;border-right:1px solid #1e1e3f;min-width:160px">
    <span style="color:#64748b;font-size:10px;font-family:Inter,sans-serif;text-transform:uppercase;letter-spacing:0.07em;font-weight:600">Trend over horizon</span>
    <span style="color:{trend_col};font-size:15px;font-family:Inter,sans-serif;font-weight:700;margin-top:2px">{trend_dir} {abs(trend_pct):.1f}%</span>
  </div>
  {'<div style="display:flex;flex-direction:column;padding:10px 20px;border-right:1px solid #1e1e3f;min-width:160px"><span style="color:#64748b;font-size:10px;font-family:Inter,sans-serif;text-transform:uppercase;letter-spacing:0.07em;font-weight:600">vs Current</span>' + vs_now_html + '</div>' if vs_now_html else ""}
  <div style="display:flex;flex-direction:column;padding:10px 20px;min-width:110px">
    <span style="color:#64748b;font-size:10px;font-family:Inter,sans-serif;text-transform:uppercase;letter-spacing:0.07em;font-weight:600">Horizon</span>
    <span style="color:#f1f5f9;font-size:15px;font-family:Inter,sans-serif;font-weight:700;margin-top:2px">{horizon} <span style="color:#475569;font-size:11px">days</span></span>
  </div>
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
    # col1, col2 = st.columns([1, 1])
    # with col1:
    #     st.markdown(section_header("Demand Drivers (SHAP)",
    #         help_text="SHAP (SHapley Additive exPlanations) values showing which features most influence the model's predictions. Longer bars = stronger impact. Derived from the full DLD training dataset (2019–2024)."),
    #         unsafe_allow_html=True)
    #     try:
    #         drivers = api.get_demand_drivers(target=target)
    #         fi = drivers.get("feature_importance", [])
    #         if fi:
    #             fig = feature_importance_chart(fi, height=380)
    #             st.plotly_chart(fig, use_container_width=True)
    #         else:
    #             st.info("Train models to view SHAP feature importance.")
    #     except api.APIError as e:
    #         st.warning(str(e))

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
