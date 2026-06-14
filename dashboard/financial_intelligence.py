import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.queries import (
    get_financial_kpis,
    get_financial_pl_trend,
    get_overdue_aging_summary,
    get_sales_vs_target,
    get_revenue_collections_trend,
    get_forecast_chart_data,
)
from utils.helpers import (
    render_kpi_card, fmt_aed, fmt_number,
    get_re_colors, plotly_dark_layout, section_header,
)


def render_financial_intelligence(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Financial intelligence — revenue, gross profit, EBITDA, net margins,
        collections efficiency, overdue aging and 3-month revenue forecast.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        kpis = get_financial_kpis(session)
        df_pl = get_financial_pl_trend(session)
        overdue = get_overdue_aging_summary(session)
        df_target = get_sales_vs_target(session)
        df_collections = get_revenue_collections_trend(session)
        df_forecast = get_forecast_chart_data(session)
    finally:
        session.close()

    if not kpis:
        st.info("No financial data available.")
        return

    # ── KPI Row 1 ──────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        d = kpis.get("revenue_mom_delta", 0)
        render_kpi_card("Revenue (Period)", fmt_aed(kpis["revenue"]),
                        delta=f"{d:+.1f}% MoM", is_positive=d >= 0)
    with c2:
        render_kpi_card("Gross Profit", fmt_aed(kpis["gross_profit"]),
                        delta=f"{kpis['gross_margin']:.1f}% margin",
                        is_positive=kpis["gross_margin"] > 20)
    with c3:
        render_kpi_card("EBITDA", fmt_aed(kpis["ebitda"]),
                        delta=f"{kpis['ebitda_margin']:.1f}% margin",
                        is_positive=kpis["ebitda_margin"] > 15)
    with c4:
        render_kpi_card("Net Profit", fmt_aed(kpis["net_profit"]),
                        delta=f"{kpis['net_margin']:.1f}% margin",
                        is_positive=kpis["net_margin"] > 0)

    st.markdown("<br>", unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        render_kpi_card("Collections", fmt_aed(kpis["collections"]))
    with c6:
        render_kpi_card("Escrow Balance", fmt_aed(kpis["escrow_balance"]))
    with c7:
        render_kpi_card("3M Forecast", fmt_aed(kpis["forecast_3m"]))
    with c8:
        render_kpi_card("Sales Achievement", f"{kpis['sales_achievement']:.1f}%",
                        is_positive=kpis["sales_achievement"] >= 90)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Revenue + Collections trend ────────────────
    section_header("Revenue vs Collections Trend")
    if not df_collections.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_collections["period_date"], y=df_collections["revenue_booked_aed"] / 1e6,
            name="Revenue Booked (AED M)", marker_color=colors["primary"], opacity=0.7,
        ))
        fig.add_trace(go.Bar(
            x=df_collections["period_date"], y=df_collections["collections_received_aed"] / 1e6,
            name="Collections Received (AED M)", marker_color=colors["indigo"], opacity=0.7,
        ))
        fig.add_trace(go.Scatter(
            x=df_collections["period_date"], y=df_collections["net_cash_flow_aed"] / 1e6,
            name="Net Cash Flow (AED M)", yaxis="y",
            line=dict(color=colors["gold"], width=2.5),
            mode="lines+markers", marker=dict(size=5),
        ))
        layout = plotly_dark_layout("", 360)
        layout["barmode"] = "group"
        layout["yaxis"]["title"] = "AED Millions"
        layout["legend"] = dict(orientation="h", y=-0.18, x=0, bgcolor="rgba(0,0,0,0)")
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: P&L margins trend + Sales vs Target ────────
    col_a, col_b = st.columns(2)

    with col_a:
        section_header("P&L Margin Trends")
        if not df_pl.empty:
            fig = go.Figure()
            for metric, label, col in [
                ("gross_margin_pct", "Gross Margin %", colors["primary"]),
                ("ebitda", "EBITDA (AED M)", colors["gold"]),
                ("net_margin_pct", "Net Margin %", colors["cyan"]),
            ]:
                if metric == "ebitda":
                    y = df_pl[metric] / 1e6
                    yaxis = "y2"
                else:
                    y = df_pl[metric]
                    yaxis = "y"
                fig.add_trace(go.Scatter(
                    x=df_pl["period_date"], y=y,
                    name=label, yaxis=yaxis,
                    line=dict(color=col, width=2),
                    mode="lines",
                ))
            layout = plotly_dark_layout("", 340)
            layout["yaxis"]["title"] = "Margin %"
            layout["yaxis2"] = dict(
                title=dict(text="EBITDA (AED M)", font=dict(color=colors["gold"])),
                overlaying="y", side="right",
                gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11),
            )
            layout["legend"] = dict(orientation="h", y=-0.2, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section_header("Sales Achievement vs Target")
        if not df_target.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_target["period_date"], y=df_target["target"] / 1e6,
                name="Target (AED M)",
                marker=dict(color=colors["muted"], opacity=0.5, line=dict(width=0)),
            ))
            fig.add_trace(go.Bar(
                x=df_target["period_date"], y=df_target["actual"] / 1e6,
                name="Actual (AED M)",
                marker=dict(color=colors["primary"], opacity=0.85, line=dict(width=0)),
            ))
            fig.add_trace(go.Scatter(
                x=df_target["period_date"], y=df_target["achievement_pct"],
                name="Achievement %", yaxis="y2",
                line=dict(color=colors["gold"], width=2.5, dash="dot"),
                mode="lines+markers", marker=dict(size=5),
            ))
            layout = plotly_dark_layout("", 340)
            layout["barmode"] = "overlay"
            layout["yaxis"]["title"] = "AED Millions"
            layout["yaxis2"] = dict(
                title=dict(text="Achievement %", font=dict(color=colors["gold"])),
                overlaying="y", side="right",
                gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11),
            )
            layout["legend"] = dict(orientation="h", y=-0.2, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 3: Overdue Aging + Forecast ───────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_c, col_d = st.columns([2, 3])

    with col_c:
        section_header("Overdue Collections Aging")
        aging_labels = ["30–60 Days", "60–90 Days", "90+ Days", "Bad Debt Provision"]
        aging_values = [
            overdue["overdue_30_60"] / 1e6,
            overdue["overdue_60_90"] / 1e6,
            overdue["overdue_90_plus"] / 1e6,
            overdue["bad_debt"] / 1e6,
        ]
        aging_colors = [colors["warning"], colors["gold"], colors["danger"], colors["rose"]]
        fig = go.Figure(go.Bar(
            x=aging_values, y=aging_labels,
            orientation="h",
            marker=dict(color=aging_colors, line=dict(width=0)),
            text=[f"AED {v:.1f}M" for v in aging_values],
            textposition="outside",
            textfont=dict(size=11, color="#94a3b8"),
        ))
        layout = plotly_dark_layout("", 300)
        layout["xaxis"]["title"] = "AED Millions"
        layout["margin"]["l"] = 120
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)

        coll_eff = overdue["collection_efficiency"]
        box_class = "insight-box" if coll_eff >= 85 else ("warning-box" if coll_eff >= 70 else "alert-box")
        st.markdown(f"""<div class="{box_class}">
            <b>Collection Efficiency:</b> {coll_eff:.1f}%<br>
            <b>Total Overdue:</b> {fmt_aed(overdue['total_overdue'])}
        </div>""", unsafe_allow_html=True)

    with col_d:
        section_header("Revenue Forecast (3M & 12M)")
        if not df_forecast.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_forecast["period_date"],
                y=df_forecast["revenue_actual_aed"] / 1e6,
                name="Actual Revenue (AED M)",
                line=dict(color=colors["primary"], width=2.5),
                mode="lines+markers", marker=dict(size=5),
            ))
            fig.add_trace(go.Scatter(
                x=df_forecast["period_date"],
                y=df_forecast["forecast_next_3m_aed"] / 1e6,
                name="3M Forecast (AED M)",
                line=dict(color=colors["gold"], width=2, dash="dash"),
                mode="lines",
            ))
            fig.add_trace(go.Scatter(
                x=df_forecast["period_date"],
                y=df_forecast["forecast_next_12m_aed"] / 1e6,
                name="12M Forecast (AED M)",
                line=dict(color=colors["indigo"], width=2, dash="dot"),
                mode="lines",
            ))
            layout = plotly_dark_layout("", 300)
            layout["yaxis"]["title"] = "AED Millions"
            layout["legend"] = dict(orientation="h", y=-0.2, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)
