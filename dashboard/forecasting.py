import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from forecasting.prophet_forecasting import train_prophet_model, get_market_factor_stats
from database.connection import get_db_session
from database.queries import get_unique_filter_options
from utils.helpers import get_re_colors, plotly_dark_layout, section_header, fmt_aed


def render_forecasting(filters: dict):
    colors = get_re_colors()

    st.markdown("""
        <p class="subtitle-text">AI-powered demand forecasting using Prophet with UAE real estate market regressors —
        UAE Central Bank rate, mortgage rates, Ramadan cycles, Golden Visa applications, Expo effect & oil prices.</p>
    """, unsafe_allow_html=True)

    # ── Filter controls ───────────────────────────────────
    session = get_db_session()
    try:
        opts = get_unique_filter_options(session)
    finally:
        session.close()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        f_city = st.selectbox("City", ["All Cities"] + opts["cities"], key="fc_city")
    with col2:
        f_ptype = st.selectbox("Property Type", ["All Types"] + opts["property_types"], key="fc_ptype")
    with col3:
        f_pcat = st.selectbox("Category", ["All Categories"] + opts["property_categories"], key="fc_cat")
    with col4:
        target = st.selectbox("Forecast Target", ["Units Transacted", "Transaction Value (AED)"], key="fc_target")

    col5, col6, col7 = st.columns(3)
    with col5:
        horizon = st.select_slider("Forecast Horizon", [30, 60, 90, 180, 365], value=90, key="fc_horizon")
    with col6:
        confidence = st.slider("Confidence Interval", 0.80, 0.99, 0.95, 0.01, key="fc_ci")
    with col7:
        run_btn = st.button("Run Forecast", type="primary", use_container_width=True)

    if not run_btn:
        st.markdown("""<div class="insight-box">
            Select your filters above and click <b>Run Forecast</b> to generate a Prophet demand forecast
            with real estate economic regressors.
        </div>""", unsafe_allow_html=True)
        return

    with st.spinner("Training Prophet model with market regressors..."):
        result, err = train_prophet_model(
            property_type=None if f_ptype == "All Types" else f_ptype,
            property_category=None if f_pcat == "All Categories" else f_pcat,
            city=None if f_city == "All Cities" else f_city,
            target="units" if "Units" in target else "revenue",
            horizon_days=horizon,
            interval_width=confidence,
        )

    if err:
        st.error(f"Forecasting error: {err}")
        return

    forecast = result["forecast"]
    metrics = result["metrics"]
    historical = result["historical_data"]
    active_regs = result["active_regressors"]
    target_label = "Units" if "Units" in target else "Revenue (AED)"

    # ── Metrics strip ─────────────────────────────────────
    section_header("Model Performance", icon="🎯")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Forecast Accuracy", f"{metrics['accuracy']:.1f}%")
    m2.metric("MAE", f"{metrics['mae']:.1f}")
    m3.metric("RMSE", f"{metrics['rmse']:.1f}")
    m4.metric("Regressors Active", str(len(active_regs)))

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Main forecast chart ───────────────────────────────
    section_header(f"{target_label} Forecast — Next {horizon} Days", icon="🔮")

    hist = forecast[forecast["actual"].notna()].copy()
    fut = forecast[forecast["actual"].isna()].copy()

    fig = go.Figure()

    # Confidence band
    fig.add_trace(go.Scatter(
        x=pd.concat([forecast["ds"], forecast["ds"].iloc[::-1]]),
        y=pd.concat([forecast["yhat_upper"], forecast["yhat_lower"].iloc[::-1]]),
        fill="toself",
        fillcolor="rgba(16, 185, 129, 0.10)",
        line=dict(color="rgba(0,0,0,0)"),
        name=f"{int(confidence*100)}% Confidence",
        showlegend=True,
        hoverinfo="skip",
    ))

    # Historical actuals
    fig.add_trace(go.Scatter(
        x=hist["ds"], y=hist["actual"],
        mode="lines",
        name="Historical Actual",
        line=dict(color=colors["gold"], width=1.8),
    ))

    # Historical prediction line
    fig.add_trace(go.Scatter(
        x=hist["ds"], y=hist["yhat"],
        mode="lines",
        name="Model Fit",
        line=dict(color=colors["primary"], width=1.5, dash="dot"),
    ))

    # Future forecast
    fig.add_trace(go.Scatter(
        x=fut["ds"], y=fut["yhat"],
        mode="lines",
        name=f"{horizon}-Day Forecast",
        line=dict(color=colors["primary"], width=2.5),
    ))

    # Vertical cutoff marker
    last_hist_date = hist["ds"].max() if not hist.empty else forecast["ds"].min()
    fig.add_vline(
        x=last_hist_date.isoformat(), line_width=1.5,
        line_dash="dash", line_color="rgba(255,255,255,0.3)",
    )
    fig.add_annotation(
        x=last_hist_date.isoformat(), y=1, yref="paper",
        text="Forecast Start", showarrow=False, xanchor="left",
        font=dict(color="#94a3b8", size=11),
    )

    layout = plotly_dark_layout("", 480)
    layout["yaxis"]["title"] = target_label
    layout["legend"] = dict(orientation="h", y=-0.12, x=0, bgcolor="rgba(0,0,0,0)")
    layout["hovermode"] = "x unified"
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)

    # ── 30/60/90-day summary ──────────────────────────────
    section_header("Forecast Summary", icon="📋")
    future_only = forecast[forecast["ds"] > last_hist_date].copy()

    if not future_only.empty:
        milestones = [30, 60, 90, 180, 365]
        cols = st.columns(min(len(milestones), 5))
        for i, days in enumerate(milestones):
            if days > horizon:
                break
            chunk = future_only.head(days)
            total = chunk["yhat"].sum()
            label = f"Next {days}d"
            with cols[i]:
                if "Units" in target:
                    st.metric(label, f"{int(total):,} units")
                else:
                    st.metric(label, fmt_aed(total))

    # ── Seasonal decomposition ────────────────────────────
    if "trend" in forecast.columns and "yearly" in forecast.columns:
        st.markdown("<br>", unsafe_allow_html=True)
        section_header("Trend & Seasonality Decomposition", icon="📊")
        col_t, col_s = st.columns(2)

        with col_t:
            fig_t = go.Figure(go.Scatter(
                x=forecast["ds"], y=forecast["trend"],
                mode="lines", name="Trend",
                line=dict(color=colors["indigo"], width=2),
            ))
            layout_t = plotly_dark_layout("Long-Term Trend", 280)
            layout_t["yaxis"]["title"] = target_label
            fig_t.update_layout(**layout_t)
            st.plotly_chart(fig_t, use_container_width=True)

        with col_s:
            fig_s = go.Figure(go.Scatter(
                x=forecast["ds"], y=forecast["yearly"],
                mode="lines", name="Yearly Pattern",
                line=dict(color=colors["gold"], width=2),
                fill="tozeroy", fillcolor="rgba(245, 158, 11, 0.08)",
            ))
            layout_s = plotly_dark_layout("Yearly Seasonality", 280)
            layout_s["yaxis"]["title"] = "Seasonal Effect"
            fig_s.update_layout(**layout_s)
            st.plotly_chart(fig_s, use_container_width=True)

    # ── Active regressors info ────────────────────────────
    if active_regs:
        st.markdown("<br>", unsafe_allow_html=True)
        reg_display = {
            "uae_central_bank_base_rate_pct": "UAE Central Bank Base Rate",
            "mortgage_rate_avg_pct": "Avg Mortgage Rate",
            "consumer_confidence_index": "Consumer Confidence Index",
            "tourism_arrivals_index": "Tourism Arrivals Index",
            "ramadan_month": "Ramadan Month Cycle",
            "expo_effect": "Dubai Expo Effect",
            "golden_visa_applications": "Golden Visa Applications",
            "property_registration_fee_pct": "DLD Registration Fee",
            "foreign_investment_inflow_bn_aed": "Foreign Investment Inflows",
            "gdp_growth_pct": "GDP Growth Rate",
            "cpi_inflation_pct": "CPI Inflation Rate",
            "new_project_launches": "New Project Launches",
            "oil_price_usd_bbl": "Oil Price (USD/bbl)",
            "event_demand_multiplier": "Market Event Multiplier",
        }
        labels = [reg_display.get(r, r.replace("_", " ").title()) for r in active_regs]
        st.markdown(f"""<div class="insight-box">
            <b>Active Regressors ({len(active_regs)}):</b> {', '.join(labels)}
        </div>""", unsafe_allow_html=True)
