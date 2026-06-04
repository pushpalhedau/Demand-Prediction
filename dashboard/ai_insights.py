import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from database.connection import get_db_session
from database.queries import get_market_factor_trend, get_market_factor_stats
from forecasting.prophet_forecasting import train_prophet_model, get_market_factor_stats as get_prophet_stats
from utils.helpers import get_re_colors, plotly_dark_layout, section_header, fmt_aed


def render_ai_insights(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Market intelligence & scenario simulation — analyze UAE economic drivers, model what-if scenarios
        (UAE CB rate changes, Golden Visa activity, mortgage rates, Expo effect), and identify investment signals.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        city_filter = filters.get("city") if filters else None
        df_market = get_market_factor_trend(session, city=city_filter)
        factor_stats = get_market_factor_stats(session, city=city_filter)
    finally:
        session.close()

    tab_eco, tab_sim, tab_invest = st.tabs([
        "Economic Indicators", "Scenario Simulator", "Investment Signals"
    ])

    # ══ TAB 1: Economic Indicators ═════════════════════════
    with tab_eco:
        if df_market.empty:
            st.info("Market factor data not available.")
        else:
            mf = df_market.copy()
            if not city_filter:
                mf = mf.groupby("date").mean(numeric_only=True).reset_index()

            # ── UAE CB Rate + Mortgage Rate ────────────────
            section_header("Interest Rate Environment", icon="🏦")
            col_a, col_b = st.columns(2)

            with col_a:
                if "uae_central_bank_base_rate_pct" in mf.columns and "mortgage_rate_avg_pct" in mf.columns:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=mf["date"], y=mf["uae_central_bank_base_rate_pct"],
                        name="UAE CB Base Rate", mode="lines",
                        line=dict(color=colors["danger"], width=2.5),
                    ))
                    fig.add_trace(go.Scatter(
                        x=mf["date"], y=mf["mortgage_rate_avg_pct"],
                        name="Avg Mortgage Rate", mode="lines",
                        line=dict(color=colors["gold"], width=2.5),
                    ))
                    layout = plotly_dark_layout("UAE Central Bank Rate vs Mortgage Rate", 300)
                    layout["yaxis"]["title"] = "Rate (%)"
                    layout["hovermode"] = "x unified"
                    layout["legend"] = dict(orientation="h", y=-0.2, x=0, bgcolor="rgba(0,0,0,0)")
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

            with col_b:
                if "consumer_confidence_index" in mf.columns and "gdp_growth_pct" in mf.columns:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=mf["date"], y=mf["consumer_confidence_index"],
                        name="Consumer Confidence", mode="lines",
                        line=dict(color=colors["primary"], width=2.5),
                        fill="tozeroy", fillcolor="rgba(16,185,129,0.08)",
                    ))
                    fig.add_trace(go.Scatter(
                        x=mf["date"], y=mf["gdp_growth_pct"] * 10,
                        name="GDP Growth (×10)", mode="lines",
                        line=dict(color=colors["indigo"], width=2, dash="dot"),
                        yaxis="y2",
                    ))
                    layout = plotly_dark_layout("Consumer Confidence & GDP Growth", 300)
                    layout["yaxis"] = dict(title="CCI", gridcolor="rgba(255,255,255,0.04)")
                    layout["yaxis2"] = dict(
                        title="GDP % (×10)", overlaying="y", side="right",
                        gridcolor="rgba(0,0,0,0)",
                    )
                    layout["hovermode"] = "x unified"
                    layout["legend"] = dict(orientation="h", y=-0.2, x=0, bgcolor="rgba(0,0,0,0)")
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

            # ── Inflation + DLD Registration Fee ───────────
            col_c, col_d = st.columns(2)

            with col_c:
                if "cpi_inflation_pct" in mf.columns:
                    fig = go.Figure(go.Scatter(
                        x=mf["date"], y=mf["cpi_inflation_pct"],
                        mode="lines",
                        line=dict(color=colors["warning"], width=2),
                        fill="tozeroy", fillcolor="rgba(245,158,11,0.08)",
                        name="CPI Inflation",
                    ))
                    layout = plotly_dark_layout("CPI Inflation Rate (%)", 280)
                    layout["showlegend"] = False
                    layout["yaxis"]["title"] = "CPI (%)"
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

            with col_d:
                if "property_registration_fee_pct" in mf.columns:
                    fig = go.Figure(go.Scatter(
                        x=mf["date"], y=mf["property_registration_fee_pct"],
                        mode="lines+markers",
                        line=dict(color=colors["cyan"], width=2),
                        marker=dict(size=5),
                        name="DLD Registration Fee",
                    ))
                    layout = plotly_dark_layout("DLD Property Registration Fee (%)", 280)
                    layout["showlegend"] = False
                    layout["yaxis"]["title"] = "Fee (%)"
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

            # ── New project launches + Golden Visa ──────────
            col_e, col_f = st.columns(2)
            with col_e:
                if "new_project_launches" in mf.columns:
                    fig = go.Figure(go.Bar(
                        x=mf["date"], y=mf["new_project_launches"],
                        marker_color=colors["indigo"], opacity=0.7,
                        name="New Launches",
                    ))
                    layout = plotly_dark_layout("Monthly New DLD/RERA Project Launches", 280)
                    layout["showlegend"] = False
                    layout["yaxis"]["title"] = "Projects"
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

            with col_f:
                if "golden_visa_applications" in mf.columns:
                    fig = go.Figure(go.Scatter(
                        x=mf["date"], y=mf["golden_visa_applications"],
                        mode="lines",
                        line=dict(color=colors["gold"], width=2),
                        fill="tozeroy", fillcolor="rgba(245,158,11,0.08)",
                        name="Golden Visa Applications",
                    ))
                    layout = plotly_dark_layout("Monthly Golden Visa Applications", 280)
                    layout["showlegend"] = False
                    layout["yaxis"]["title"] = "Applications"
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

    # ══ TAB 2: Scenario Simulator ══════════════════════════
    with tab_sim:
        st.markdown("""<div class="insight-box">
            Adjust economic levers below and run a what-if forecast to see how demand shifts
            with changes to UAE CB rate, mortgage rates, Golden Visa activity, and Expo/market events.
        </div>""", unsafe_allow_html=True)

        prophet_stats = get_prophet_stats(city=filters.get("city") if filters else None)

        if not prophet_stats:
            st.warning("Run the database seeding and model training first to enable the simulator.")
        else:
            col_s1, col_s2 = st.columns(2)
            overrides = {}

            def _safe_slider(label, stat, step, **kwargs):
                lo, hi, val = float(stat["min"]), float(stat["max"]), float(stat["last"])
                if lo >= hi:
                    lo, hi = min(lo, val) - step, max(hi, val) + step
                val = max(lo, min(hi, val))
                return st.slider(label, lo, hi, val, step, **kwargs)

            with col_s1:
                section_header("Monetary Policy", icon="🏛")
                if "uae_central_bank_base_rate_pct" in prophet_stats:
                    overrides["uae_central_bank_base_rate_pct"] = _safe_slider(
                        "UAE CB Base Rate (%)", prophet_stats["uae_central_bank_base_rate_pct"], 0.1,
                        help="Lower rate → cheaper mortgages → demand surge",
                    )
                if "mortgage_rate_avg_pct" in prophet_stats:
                    overrides["mortgage_rate_avg_pct"] = _safe_slider(
                        "Avg Mortgage Rate (%)", prophet_stats["mortgage_rate_avg_pct"], 0.1,
                    )
                if "property_registration_fee_pct" in prophet_stats:
                    overrides["property_registration_fee_pct"] = _safe_slider(
                        "DLD Registration Fee (%)", prophet_stats["property_registration_fee_pct"], 0.25,
                        help="Fee changes affect transaction cost and volume",
                    )

            with col_s2:
                section_header("Market & Demand Signals", icon="📊")
                if "consumer_confidence_index" in prophet_stats:
                    overrides["consumer_confidence_index"] = _safe_slider(
                        "Consumer Confidence Index", prophet_stats["consumer_confidence_index"], 0.5,
                    )
                if "expo_effect" in prophet_stats:
                    overrides["expo_effect"] = int(st.checkbox(
                        "Dubai Expo Effect Active", value=bool(prophet_stats["expo_effect"]["last"]),
                        help="Expo effect → tourism and investment surge → demand boost",
                    ))
                if "ramadan_month" in prophet_stats:
                    overrides["ramadan_month"] = int(st.checkbox(
                        "Ramadan Month",
                        value=bool(prophet_stats["ramadan_month"]["last"]),
                        help="Ramadan typically slows transactions; post-Ramadan surge follows",
                    ))

            sim_horizon = st.select_slider("Simulation Horizon", [30, 60, 90], value=90, key="sim_h")

            if st.button("Run Scenario Simulation", type="primary", use_container_width=True):
                with st.spinner("Simulating scenario with overridden market levers..."):
                    result_base, _ = train_prophet_model(
                        city=filters.get("city") if filters else None,
                        target="units", horizon_days=sim_horizon,
                    )
                    result_sim, err = train_prophet_model(
                        city=filters.get("city") if filters else None,
                        target="units", horizon_days=sim_horizon,
                        market_overrides=overrides,
                    )

                if err:
                    st.error(f"Simulation error: {err}")
                elif result_base and result_sim:
                    fc_base = result_base["forecast"]
                    fc_sim = result_sim["forecast"]
                    last_hist = fc_base[fc_base["actual"].notna()]["ds"].max()
                    fut_base = fc_base[fc_base["ds"] > last_hist]
                    fut_sim = fc_sim[fc_sim["ds"] > last_hist]

                    base_total = fut_base["yhat"].sum()
                    sim_total = fut_sim["yhat"].sum()
                    delta_pct = ((sim_total - base_total) / max(base_total, 1)) * 100

                    res_col1, res_col2, res_col3 = st.columns(3)
                    res_col1.metric("Baseline Forecast", f"{int(base_total):,} units")
                    res_col2.metric(
                        "Scenario Forecast",
                        f"{int(sim_total):,} units",
                        delta=f"{delta_pct:+.1f}%",
                    )
                    res_col3.metric(
                        "Demand Impact",
                        f"{abs(sim_total - base_total):,.0f} units",
                        delta="Increase" if delta_pct > 0 else "Decrease",
                    )

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=fut_base["ds"], y=fut_base["yhat"],
                        name="Baseline", mode="lines",
                        line=dict(color=colors["indigo"], width=2, dash="dot"),
                    ))
                    fig.add_trace(go.Scatter(
                        x=fut_sim["ds"], y=fut_sim["yhat"],
                        name="Scenario",
                        mode="lines",
                        line=dict(color=colors["primary"], width=2.5),
                        fill="tonexty" if delta_pct > 0 else None,
                        fillcolor="rgba(16,185,129,0.10)",
                    ))
                    layout = plotly_dark_layout("Baseline vs Scenario Demand Forecast", 380)
                    layout["yaxis"]["title"] = "Units/Day"
                    layout["legend"] = dict(orientation="h", y=-0.15, x=0, bgcolor="rgba(0,0,0,0)")
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

                    if delta_pct > 0:
                        st.markdown(f"""<div class="insight-box">
                            The scenario generates <b>{delta_pct:+.1f}%</b> more demand over {sim_horizon} days.
                            Key levers: lower mortgage rates boost affordability; Expo and Golden Visa activity
                            drive foreign and high-value buyer segments.
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""<div class="alert-box">
                            The scenario reduces demand by <b>{abs(delta_pct):.1f}%</b> over {sim_horizon} days.
                            Higher rates or Ramadan slowdown constrain purchasing power and transaction volumes.
                        </div>""", unsafe_allow_html=True)

    # ══ TAB 3: Investment Signals ══════════════════════════
    with tab_invest:
        if df_market.empty:
            st.info("Market factor data not available.")
            return

        mf_inv = df_market.copy()
        if not city_filter:
            mf_inv = mf_inv.groupby("date").mean(numeric_only=True).reset_index()

        section_header("Foreign & Institutional Investment Flows", icon="💹")
        col_i1, col_i2 = st.columns(2)

        with col_i1:
            if "foreign_investment_inflow_bn_aed" in mf_inv.columns:
                fi = mf_inv[["date", "foreign_investment_inflow_bn_aed"]].dropna()
                if not fi.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=fi["date"], y=fi["foreign_investment_inflow_bn_aed"],
                        marker_color=colors["gold"], opacity=0.8,
                        name="Foreign Inflows",
                    ))
                    fig.add_trace(go.Scatter(
                        x=fi["date"],
                        y=fi["foreign_investment_inflow_bn_aed"].rolling(3).mean(),
                        name="3-Month MA",
                        line=dict(color=colors["primary"], width=2),
                        mode="lines",
                    ))
                    layout = plotly_dark_layout("Foreign Investment Inflows (AED Billion)", 320)
                    layout["yaxis"]["title"] = "AED Billion"
                    layout["legend"] = dict(orientation="h", y=-0.2, x=0, bgcolor="rgba(0,0,0,0)")
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

        with col_i2:
            if "institutional_investment_bn_aed" in mf_inv.columns:
                inst = mf_inv[["date", "institutional_investment_bn_aed", "reit_activity_index"]].dropna()
                if not inst.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=inst["date"], y=inst["institutional_investment_bn_aed"],
                        marker_color=colors["indigo"], opacity=0.8,
                        name="Institutional (AED Bn)", yaxis="y",
                    ))
                    fig.add_trace(go.Scatter(
                        x=inst["date"], y=inst["reit_activity_index"],
                        name="REIT Activity Index",
                        line=dict(color=colors["cyan"], width=2),
                        mode="lines", yaxis="y2",
                    ))
                    layout = plotly_dark_layout("Institutional Investment & REIT Activity", 320)
                    layout["yaxis"] = dict(title="AED Billion", gridcolor="rgba(255,255,255,0.04)")
                    layout["yaxis2"] = dict(
                        title="REIT Index", overlaying="y", side="right",
                        gridcolor="rgba(0,0,0,0)",
                    )
                    layout["legend"] = dict(orientation="h", y=-0.2, x=0, bgcolor="rgba(0,0,0,0)")
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

        # ── Tourism + Golden Visa ──────────────────────────
        section_header("Tourism & Off-Plan Demand Signals", icon="✈️")
        col_j1, col_j2 = st.columns(2)

        with col_j1:
            if "tourism_arrivals_index" in mf_inv.columns:
                tourism = mf_inv[["date", "tourism_arrivals_index"]].dropna()
                if not tourism.empty:
                    fig = go.Figure(go.Scatter(
                        x=tourism["date"], y=tourism["tourism_arrivals_index"],
                        mode="lines",
                        line=dict(color=colors["cyan"], width=2),
                        fill="tozeroy", fillcolor="rgba(6,182,212,0.08)",
                    ))
                    layout = plotly_dark_layout("Tourism Arrivals Index (Dubai/UAE)", 300)
                    layout["showlegend"] = False
                    layout["yaxis"]["title"] = "Arrivals Index"
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

        with col_j2:
            if "off_plan_sales_share_pct" in mf_inv.columns:
                op = mf_inv[["date", "off_plan_sales_share_pct"]].dropna()
                if not op.empty:
                    fig = go.Figure(go.Bar(
                        x=op["date"], y=op["off_plan_sales_share_pct"],
                        marker_color=colors["primary"], opacity=0.8,
                    ))
                    layout = plotly_dark_layout("Off-Plan Sales Share (% of Total)", 300)
                    layout["showlegend"] = False
                    layout["yaxis"]["title"] = "Off-Plan Share (%)"
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

        # ── Key signals summary ────────────────────────────
        section_header("Current Market Signal Scorecard", icon="📋")
        if factor_stats:
            signals = []
            def get_signal(key, label, good_low=True, unit=""):
                if key not in factor_stats:
                    return
                stat = factor_stats[key]
                val = stat["last"]
                mid = (stat["min"] + stat["max"]) / 2
                is_good = val < mid if good_low else val > mid
                signals.append({
                    "Signal": label,
                    "Current": f"{val:.2f}{unit}",
                    "Status": "🟢 Positive" if is_good else "🔴 Caution",
                })

            get_signal("uae_central_bank_base_rate_pct", "UAE CB Base Rate", good_low=True, unit="%")
            get_signal("mortgage_rate_avg_pct", "Avg Mortgage Rate", good_low=True, unit="%")
            get_signal("consumer_confidence_index", "Consumer Confidence", good_low=False)
            get_signal("tourism_arrivals_index", "Tourism Arrivals Index", good_low=False)
            get_signal("foreign_investment_inflow_bn_aed", "Foreign Investment Inflows", good_low=False, unit=" Bn")
            get_signal("cpi_inflation_pct", "CPI Inflation", good_low=True, unit="%")
            get_signal("property_registration_fee_pct", "DLD Registration Fee", good_low=True, unit="%")
            get_signal("off_plan_sales_share_pct", "Off-Plan Sales Share", good_low=False, unit="%")

            if signals:
                st.dataframe(
                    pd.DataFrame(signals),
                    use_container_width=True,
                    hide_index=True,
                )
