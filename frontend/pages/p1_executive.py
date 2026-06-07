"""Tab 1 — Executive Command Center"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import frontend.api_client as api
from frontend.components.kpi_cards import (
    kpi_card, render_kpi_row, alert_card, ai_insight_panel, section_header, KPI_CSS
)
from frontend.components.charts import (
    line_chart, bar_chart, pie_chart, area_chart, gauge_chart
)
from frontend.components.theme import C_INDIGO, C_EMERALD, C_AMBER, C_RED, C_CYAN, themed


def _safe(future, default):
    try:
        return future.result()
    except Exception:
        return default


def render(filters: dict = None):
    filters = filters or {}
    year    = filters.get("year")
    area    = filters.get("area")

    st.markdown(KPI_CSS, unsafe_allow_html=True)

    # ── Fetch all data in parallel ──────────────────────────────────
    with st.spinner(""):
        with ThreadPoolExecutor(max_workers=6) as pool:
            f_ai       = pool.submit(api.get_ai_executive_summary)
            f_kpis     = pool.submit(api.get_executive_kpis, year)
            f_opps     = pool.submit(api.get_top_opportunities, 8)
            f_risks    = pool.submit(api.get_risk_summary)
            f_overview = pool.submit(api.get_market_overview)
            f_sent     = pool.submit(api.get_sentiment_summary)

            ai_data  = _safe(f_ai,       {"summary": "Market data is loading …"})
            kpis     = _safe(f_kpis,     {})
            opps     = _safe(f_opps,     [])
            risks    = _safe(f_risks,    {})
            overview = _safe(f_overview, {})
            sent     = _safe(f_sent,     {})

    summary_text = ai_data.get("summary", "Market data is loading …")
    st.markdown(ai_insight_panel(summary_text, "AI Executive Intelligence Briefing"),
                unsafe_allow_html=True)

    # ── KPI Row ─────────────────────────────────────────────────────
    try:
        if not kpis:
            raise api.APIError("KPI data unavailable")
        k = kpis.get("kpis", {})
        render_kpi_row([
            kpi_card("Transaction Volume", f"{k.get('total_transactions',{}).get('value',0):,}",
                     k.get("total_transactions",{}).get("change_pct"), gradient="indigo",
                     help_text="Total DLD-registered transactions across all property types. Covers apartments, villas, off-plan, and secondary market sales. Reflects the selected year vs. previous year."),
            kpi_card("Market Value", f"{k.get('total_value_aed_bn',{}).get('value',0):.1f}B",
                     k.get("total_value_aed_bn",{}).get("change_pct"), prefix="AED ", gradient="emerald",
                     help_text="Aggregate AED value of all DLD-registered transactions for the selected year. Includes both off-plan and secondary market sales with YoY comparison."),
            kpi_card("Avg Price / Sqft", f"{k.get('avg_price_sqft',{}).get('value',0):,.0f}",
                     k.get("avg_price_sqft",{}).get("change_pct"), prefix="AED ", gradient="violet",
                     help_text="Mean price per square foot across all registered transactions in the selected year. Calculated as total transaction value divided by total transacted area in sqft."),
            kpi_card("Rental Yield", f"{k.get('avg_rental_yield',{}).get('value',0):.1f}",
                     None, suffix="%", gradient="amber",
                     help_text="Gross rental yield derived from DLD rental contracts and transaction prices. Calculated as annual rent ÷ property value. Based on the latest available rental and sales data."),
        ], cols=4)
        render_kpi_row([
            kpi_card("Off-Plan Share", f"{k.get('off_plan_pct',{}).get('value',0):.1f}",
                     None, suffix="%", gradient="cyan",
                     help_text="Percentage of total transactions classified as off-plan (pre-construction) vs. ready/secondary market. Higher values indicate a developer-driven market cycle. Covers the selected year."),
            kpi_card("Active Market Areas", str(k.get("active_areas",{}).get("value",0)),
                     None, gradient="indigo",
                     help_text="Number of distinct geographic areas in Dubai recording at least one DLD transaction in the selected year. Reflects the breadth of market activity across the emirate."),
        ], cols=2)
    except api.APIError as e:
        st.error(f"Failed to load KPIs: {e}")
        return

    # ── Revenue Trend + Market Mix ────────────────────────────────
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(section_header("Revenue & Transaction Trend", "Last 24 months",
            help_text="Monthly DLD revenue (AED, left axis) and units sold (right axis) over the last 24 months. Revenue = sum of all transaction values per month. Units = count of registered transactions."),
            unsafe_allow_html=True)
        trend = kpis.get("monthly_trend", [])
        if trend:
            df_trend = pd.DataFrame(trend)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_trend["month"], y=df_trend["transactions"],
                name="Sales (Units)", marker_color=C_CYAN, opacity=0.78,
                yaxis="y2",
            ))
            fig.add_trace(go.Scatter(
                x=df_trend["month"], y=df_trend["value"] / 1e6,
                name="Revenue (AED)",
                mode="lines+markers",
                line=dict(color=C_INDIGO, width=2.5),
                marker=dict(size=5, color=C_INDIGO, symbol="circle"),
                yaxis="y1",
            ))
            fig.update_layout(**themed())
            fig.update_layout(
                height=360,
                yaxis=dict(
                    title="Monthly Revenue (AED)",
                    color="#64748b", side="left",
                    gridcolor="#1e1e3f",
                    tickfont=dict(color="#64748b", size=11),
                    ticksuffix="M",
                ),
                yaxis2=dict(
                    title="Units Sold",
                    color="#64748b", side="right",
                    overlaying="y", showgrid=False,
                    tickfont=dict(color="#64748b", size=11),
                ),
                hovermode="x unified",
                legend=dict(orientation="h", y=1.08),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown(section_header("Property Mix", help_text="Distribution of total DLD transactions by property type (apartments, villas, townhouses, etc.) for the selected year. Shows which property types dominate buyer demand."), unsafe_allow_html=True)
        mix = kpis.get("property_mix", [])
        if mix:
            df_mix = pd.DataFrame(mix)
            fig = pie_chart(df_mix["property_type"].tolist(), df_mix["pct"].tolist(),
                            title="", height=360)
            st.plotly_chart(fig, use_container_width=True)

    # ── Top Opportunities + Risks ────────────────────────────────
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(section_header("Top Investment Opportunities",
            help_text="Areas scored 0–100 by a composite index combining demand growth, price appreciation, rental yield, and infrastructure access. Based on the last 12 months of DLD transaction and project data."),
            unsafe_allow_html=True)
        try:
            if opps:
                df_opps = pd.DataFrame(opps)
                fig = bar_chart(
                    df_opps["area_name"].tolist(),
                    df_opps["opportunity_score"].tolist(),
                    title="", height=340, color=C_EMERALD, horizontal=True
                )
                st.plotly_chart(fig, use_container_width=True)
        except api.APIError as e:
            st.warning(str(e))

    with col2:
        st.markdown(section_header("Risk Alerts & Early Warnings",
            help_text="Market risk score (0–100) derived from price volatility, supply-demand imbalance, macroeconomic indicators, and GDELT news sentiment. Alerts are updated monthly."),
            unsafe_allow_html=True)
        try:
            overall = risks.get("overall_risk_score", 0)
            col_g, col_a = st.columns([1, 1])
            with col_g:
                fig = gauge_chart(overall, "Overall Market Risk", height=200)
                st.plotly_chart(fig, use_container_width=True)
            with col_a:
                st.markdown(f"**Severity:** `{risks.get('severity','N/A').upper()}`")
                st.markdown(f"**Active Alerts:** {risks.get('total_alerts', 0)}")
                st.markdown(f"**Critical:** {risks.get('critical_count', 0)}")
            for rf in risks.get("risk_factors", [])[:4]:
                st.markdown(
                    alert_card(rf["factor"], rf["description"],
                                rf["severity"], rf.get("action", "")),
                    unsafe_allow_html=True,
                )
        except api.APIError as e:
            st.warning(str(e))

    # ── Nationality Demand + Developer Rankings ──────────────────
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(section_header("Buyer Nationality Mix",
            help_text="Share of total DLD transactions by buyer nationality for the selected year. Identifies dominant international buyer groups and tracks shifts in cross-border demand."),
            unsafe_allow_html=True)
        nat_mix = kpis.get("nationality_mix", [])
        if nat_mix:
            df_nat = pd.DataFrame(nat_mix)
            fig = bar_chart(df_nat["nationality"].tolist(), df_nat["pct"].tolist(),
                            title="", height=300, color=C_AMBER, horizontal=True, value_format="%")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown(section_header("Market Overview",
            help_text="Supply-side snapshot from DLD project and unit records. Shows active project count, total unit pipeline, average absorption rate, and total rental contract volume across Dubai."),
            unsafe_allow_html=True)
        try:
            st.metric("Active Projects",     overview.get("active_projects", 0))
            st.metric("Total Supply Units",  f"{overview.get('total_supply_units', 0):,}")
            st.metric("Avg Absorption Rate", f"{overview.get('absorption_rate_pct', 0):.1f}%")
            st.metric("Rental Contracts",    f"{overview.get('rental_contracts', 0):,}")
            top_devs = overview.get("top_developers", [])
            if top_devs:
                st.markdown("**Top Developers by Market Share**")
                df_dev = pd.DataFrame(top_devs)
                st.dataframe(
                    df_dev[["developer", "market_share_pct"]].rename(
                        columns={"developer": "Developer", "market_share_pct": "Share %"}
                    ).set_index("Developer"),
                    use_container_width=True, height=180,
                )
        except api.APIError as e:
            st.warning(str(e))

    # ── Sentiment Gauge ──────────────────────────────────────────
    st.markdown(section_header("Market Sentiment Intelligence",
        help_text="Composite sentiment index (0–100) derived from GDELT news events, media tone, and transaction momentum. Score >60 = positive market mood. 24-month trend shown."),
        unsafe_allow_html=True)
    try:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sentiment Index",    f"{sent.get('current_score', 0):.1f}",
                   delta=f"{sent.get('trend_direction', 0):+.1f}")
        c2.metric("Buyer Confidence",   f"{sent.get('buyer_confidence', 0):.1f}")
        c3.metric("Seller Confidence",  f"{sent.get('seller_confidence', 0):.1f}")
        c4.metric("Media Sentiment",    f"{sent.get('media_score', 0):.1f}")

        history = sent.get("monthly_history", [])
        if history:
            df_hist = pd.DataFrame(history)
            fig = area_chart(df_hist["date"].tolist(), df_hist["score"].tolist(),
                              title="Sentiment Index (24 months)", height=220)
            st.plotly_chart(fig, use_container_width=True)

        if sent.get("alert"):
            st.markdown(
                alert_card("Sentiment Alert", sent["alert"]["message"], sent["alert"]["severity"]),
                unsafe_allow_html=True,
            )
    except api.APIError as e:
        st.warning(str(e))
