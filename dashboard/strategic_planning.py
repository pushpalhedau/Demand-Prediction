import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.queries import (
    get_macro_indicators_latest,
    get_market_factor_trend,
    get_competitor_overview,
    get_competitor_by_city,
    get_forecast_chart_data,
)
from utils.helpers import (
    render_kpi_card, fmt_aed, fmt_number,
    get_re_colors, plotly_dark_layout, section_header,
)


def render_strategic_planning(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Strategic planning intelligence — macro-economic indicators, competitor landscape,
        market demand drivers, revenue forecast and scenario positioning.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        macro = get_macro_indicators_latest(session)
        df_mf = get_market_factor_trend(session)
        df_competitors = get_competitor_overview(session)
        df_comp_city = get_competitor_by_city(session)
        df_forecast = get_forecast_chart_data(session)
    finally:
        session.close()

    # ── Macro KPI Row ──────────────────────────────────────
    section_header("Macro-Economic Snapshot", badge=macro.get("date", ""))
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        render_kpi_card("Base Rate", f"{macro.get('base_rate', 0):.2f}%")
    with c2:
        render_kpi_card("Mortgage Rate", f"{macro.get('mortgage_rate', 0):.2f}%",
                        is_positive=macro.get("mortgage_rate", 5) < 5)
    with c3:
        g = macro.get("gdp_growth", 0)
        render_kpi_card("GDP Growth", f"{g:.1f}%", is_positive=g > 0)
    with c4:
        cpi = macro.get("cpi_inflation", 0)
        render_kpi_card("CPI Inflation", f"{cpi:.1f}%", is_positive=cpi < 3)
    with c5:
        render_kpi_card("Consumer Confidence", f"{macro.get('consumer_confidence', 0):.1f}")
    with c6:
        render_kpi_card("Oil Price", f"${macro.get('oil_price', 0):.1f}/bbl")

    st.markdown("<br>", unsafe_allow_html=True)

    c7, c8, c9, c10 = st.columns(4)
    with c7:
        render_kpi_card("RE Price Index", f"{macro.get('price_index', 0):.1f}")
    with c8:
        render_kpi_card("Rental Yield Avg", f"{macro.get('rental_yield', 0):.2f}%")
    with c9:
        render_kpi_card("Off-Plan Share", f"{macro.get('off_plan_share', 0):.1f}%")
    with c10:
        render_kpi_card("Foreign Investment",
                        f"AED {macro.get('foreign_investment', 0):.1f}B")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Market factor trends ───────────────────────
    section_header("Key Market Factor Trends")
    if not df_mf.empty:
        df_agg = df_mf.groupby("date").agg(
            consumer_confidence=("consumer_confidence_index", "mean"),
            price_index=("real_estate_price_index", "mean"),
            mortgage_rate=("mortgage_rate_avg_pct", "mean"),
            off_plan_share=("off_plan_sales_share_pct", "mean"),
            foreign_investment=("foreign_investment_inflow_bn_aed", "mean"),
        ).reset_index()
        df_agg["date"] = pd.to_datetime(df_agg["date"])
        df_agg = df_agg.sort_values("date")

        col_a, col_b = st.columns(2)
        with col_a:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_agg["date"], y=df_agg["consumer_confidence"],
                name="Consumer Confidence", line=dict(color=colors["primary"], width=2),
            ))
            fig.add_trace(go.Scatter(
                x=df_agg["date"], y=df_agg["price_index"],
                name="RE Price Index", line=dict(color=colors["gold"], width=2),
            ))
            layout = plotly_dark_layout("", 300)
            layout["legend"] = dict(orientation="h", y=-0.22, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_agg["date"], y=df_agg["mortgage_rate"],
                name="Mortgage Rate %", line=dict(color=colors["danger"], width=2),
            ))
            fig.add_trace(go.Bar(
                x=df_agg["date"], y=df_agg["off_plan_share"],
                name="Off-Plan Share %",
                marker=dict(color=colors["indigo"], opacity=0.5, line=dict(width=0)),
            ))
            layout = plotly_dark_layout("", 300)
            layout["barmode"] = "overlay"
            layout["legend"] = dict(orientation="h", y=-0.22, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Competitor landscape ───────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Competitor Landscape")
    if not df_competitors.empty:
        col_c, col_d = st.columns([3, 2])

        with col_c:
            top15 = df_competitors.head(15).copy()
            tier_colors = {
                "Tier 1": colors["gold"], "Tier 2": colors["primary"],
                "Tier 3": colors["indigo"], "Boutique": colors["cyan"],
            }
            fig = go.Figure()
            for tier in top15["builder_tier"].unique():
                sub = top15[top15["builder_tier"] == tier]
                fig.add_trace(go.Bar(
                    x=sub["total_units"],
                    y=sub["builder_name"],
                    orientation="h",
                    name=tier,
                    marker=dict(
                        color=tier_colors.get(tier, colors["primary"]),
                        opacity=0.8, line=dict(width=0),
                    ),
                    text=[f"{u:,} units | {a:.0f}% abs"
                          for u, a in zip(sub["total_units"], sub["absorption_pct"])],
                    textposition="outside",
                    textfont=dict(size=10, color="#94a3b8"),
                ))
            layout = plotly_dark_layout("", 420)
            layout["barmode"] = "stack"
            layout["xaxis"]["title"] = "Total Units"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 170
            layout["legend"] = dict(orientation="h", y=-0.12, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with col_d:
            section_header("Competitor City Presence")
            if not df_comp_city.empty:
                fig = go.Figure(go.Pie(
                    labels=df_comp_city["city"],
                    values=df_comp_city["total_units"],
                    hole=0.52,
                    marker=dict(
                        colors=colors["colors_seq"][:len(df_comp_city)],
                        line=dict(color="#080d18", width=2),
                    ),
                    textinfo="label+percent",
                    textfont=dict(size=10),
                ))
                layout = plotly_dark_layout("", 420)
                layout["showlegend"] = False
                fig.update_layout(**layout)
                st.plotly_chart(fig, use_container_width=True)

    # ── Row 3: Competitor price comparison ────────────────
    if not df_competitors.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        section_header("Competitor Price Range Comparison")
        top10 = df_competitors.head(10).copy()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=top10["builder_name"], y=top10["min_price_sqft"],
            name="Min AED/sq.ft",
            marker=dict(color=colors["primary"], opacity=0.7, line=dict(width=0)),
        ))
        fig.add_trace(go.Bar(
            x=top10["builder_name"], y=top10["max_price_sqft"],
            name="Max AED/sq.ft",
            marker=dict(color=colors["gold"], opacity=0.7, line=dict(width=0)),
        ))
        layout = plotly_dark_layout("", 320)
        layout["barmode"] = "group"
        layout["yaxis"]["title"] = "Price per Sq.Ft (AED)"
        layout["xaxis"]["tickangle"] = -20
        layout["legend"] = dict(orientation="h", y=-0.22, bgcolor="rgba(0,0,0,0)")
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)

    # ── Row 4: Revenue forecast ────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Revenue Forecast vs Actuals")
    if not df_forecast.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_forecast["period_date"], y=df_forecast["revenue_actual_aed"] / 1e6,
            name="Actual (AED M)", line=dict(color=colors["primary"], width=2.5),
            mode="lines+markers", marker=dict(size=6),
        ))
        fig.add_trace(go.Scatter(
            x=df_forecast["period_date"], y=df_forecast["forecast_next_3m_aed"] / 1e6,
            name="3M Forecast (AED M)", line=dict(color=colors["gold"], width=2, dash="dash"),
        ))
        fig.add_trace(go.Scatter(
            x=df_forecast["period_date"], y=df_forecast["forecast_next_12m_aed"] / 1e6,
            name="12M Forecast (AED M)", line=dict(color=colors["indigo"], width=2, dash="dot"),
        ))
        layout = plotly_dark_layout("", 300)
        layout["yaxis"]["title"] = "AED Millions"
        layout["legend"] = dict(orientation="h", y=-0.18, bgcolor="rgba(0,0,0,0)")
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)
