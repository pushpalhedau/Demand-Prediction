import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.queries import (
    get_project_portfolio_kpis,
    get_project_portfolio,
    get_project_status_breakdown,
    get_project_health_scores,
)
from utils.helpers import (
    render_kpi_card, fmt_aed, fmt_number,
    get_re_colors, plotly_dark_layout, section_header,
)


def render_project_performance(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Project portfolio overview — unit absorption, construction progress,
        health scores, holding costs and completion status across all active developments.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        kpis = get_project_portfolio_kpis(session)
        df_portfolio = get_project_portfolio(session)
        df_status = get_project_status_breakdown(session)
        df_health = get_project_health_scores(session)
    finally:
        session.close()

    # ── KPI Row ───────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        render_kpi_card("Total Projects", f"{kpis['total_projects']:,}")
    with c2:
        render_kpi_card("Total Units", fmt_number(kpis['total_units']))
    with c3:
        render_kpi_card("Booked Units", fmt_number(kpis['booked_units']), is_positive=True)
    with c4:
        render_kpi_card("Available Units", fmt_number(kpis['available_units']))
    with c5:
        render_kpi_card("Avg Construction", f"{kpis['avg_construction_progress']:.1f}%")
    with c6:
        render_kpi_card("Holding Cost", fmt_aed(kpis['total_holding_cost']),
                        is_positive=False)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Status breakdown + Health scores ────────────
    col_a, col_b = st.columns([2, 3])

    with col_a:
        section_header("Portfolio by Completion Status")
        if not df_status.empty:
            fig = go.Figure(go.Pie(
                labels=df_status["completion_status"],
                values=df_status["projects"],
                hole=0.55,
                marker=dict(
                    colors=colors["colors_seq"][:len(df_status)],
                    line=dict(color="#080d18", width=2),
                ),
                textinfo="label+percent",
                textfont=dict(size=11),
            ))
            layout = plotly_dark_layout("", 360)
            layout["showlegend"] = False
            layout["annotations"] = [dict(
                text=f"<b>{df_status['projects'].sum()}</b><br>Projects",
                x=0.5, y=0.5, font=dict(size=13, color="#f0f4f8"),
                showarrow=False,
            )]
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section_header("Project Health Scores (Top 10)")
        if not df_health.empty:
            df_h = df_health.head(10).copy()
            df_h["color"] = df_h["health_score"].apply(
                lambda v: colors["success"] if v >= 75 else (
                    colors["warning"] if v >= 50 else colors["danger"]
                )
            )
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_h["health_score"],
                y=df_h["project_name"],
                orientation="h",
                name="Health Score",
                marker=dict(color=df_h["color"], line=dict(width=0)),
                text=[f"{v:.0f}" for v in df_h["health_score"]],
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            ))
            fig.add_trace(go.Bar(
                x=df_h["progress_pct"],
                y=df_h["project_name"],
                orientation="h",
                name="Progress %",
                marker=dict(color=colors["indigo"], opacity=0.45, line=dict(width=0)),
                text=[f"{v:.0f}%" for v in df_h["progress_pct"]],
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 360)
            layout["barmode"] = "group"
            layout["xaxis"]["title"] = "Score / Progress %"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 160
            layout["legend"] = dict(orientation="h", y=-0.2, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Absorption by project ──────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Unit Absorption by Project (Top 20)")
    if not df_portfolio.empty:
        top20 = df_portfolio.head(20).copy()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=top20["booked_units"] + top20["registered_units"],
            y=top20["project_name"],
            name="Sold/Registered",
            orientation="h",
            marker=dict(color=colors["primary"], line=dict(width=0)),
        ))
        fig.add_trace(go.Bar(
            x=top20["available_units"],
            y=top20["project_name"],
            name="Available",
            orientation="h",
            marker=dict(color=colors["muted"], opacity=0.45, line=dict(width=0)),
        ))
        layout = plotly_dark_layout("", 480)
        layout["barmode"] = "stack"
        layout["xaxis"]["title"] = "Units"
        layout["yaxis"]["autorange"] = "reversed"
        layout["margin"]["l"] = 180
        layout["legend"] = dict(orientation="h", y=-0.1, bgcolor="rgba(0,0,0,0)")
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)

    # ── Row 3: Status KPI table + absorption scatter ───────
    col_c, col_d = st.columns(2)

    with col_c:
        section_header("Status Breakdown Detail")
        if not df_status.empty:
            tbl = df_status.copy()
            tbl["avg_progress"] = tbl["avg_progress"].apply(
                lambda v: f"{v:.1f}%" if pd.notna(v) else "—"
            )
            tbl["total_units"] = tbl["total_units"].apply(
                lambda v: f"{int(v):,}" if pd.notna(v) else "—"
            )
            st.dataframe(
                tbl.rename(columns={
                    "completion_status": "Status",
                    "projects": "Projects",
                    "total_units": "Total Units",
                    "avg_progress": "Avg Progress",
                }),
                use_container_width=True,
                hide_index=True,
            )

    with col_d:
        section_header("Absorption Rate Distribution")
        if not df_portfolio.empty:
            fig = go.Figure(go.Histogram(
                x=df_portfolio["absorption_pct"],
                nbinsx=20,
                marker=dict(
                    color=colors["primary"],
                    opacity=0.75,
                    line=dict(color="#080d18", width=0.5),
                ),
                name="Projects",
            ))
            layout = plotly_dark_layout("", 300)
            layout["xaxis"]["title"] = "Absorption Rate %"
            layout["yaxis"]["title"] = "# Projects"
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── At-risk alert strip ───────────────────────────────
    unsold_count = kpis["unsold_projects"]
    if unsold_count > 0:
        st.markdown(f"""
        <div class="alert-box">
            <b>Attention:</b> {unsold_count} project(s) flagged as unsold (beyond 6-month mark).
            Total holding cost exposure: <b>{fmt_aed(kpis['total_holding_cost'])}</b>.
            Review pricing strategy and marketing push for slow-moving inventory.
        </div>""", unsafe_allow_html=True)
