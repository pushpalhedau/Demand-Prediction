import streamlit as st
import plotly.graph_objects as go

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
        render_kpi_card(
            "Total Projects", f"{kpis['total_projects']:,}",
            tooltip="Total number of active development projects in the portfolio across all stages — planning, under construction, and near-completion.",
        )
    with c2:
        render_kpi_card(
            "Total Units", fmt_number(kpis['total_units']),
            tooltip="Cumulative number of residential and commercial units across all projects in the portfolio.",
        )
    with c3:
        render_kpi_card(
            "Booked Units", fmt_number(kpis['booked_units']), is_positive=True,
            tooltip="Units with a confirmed buyer booking or sales agreement, pending final registration with the land department.",
        )
    with c4:
        render_kpi_card(
            "Available Units", fmt_number(kpis['available_units']),
            tooltip="Units actively available for sale or lease with no current booking or registration. High counts in mature projects signal a sales push is needed.",
        )
    with c5:
        render_kpi_card(
            "Avg Construction", f"{kpis['avg_construction_progress']:.1f}%",
            tooltip="Weighted average construction progress percentage across all active development sites. Compare against booking rates to spot projects where sales lag physical progress.",
        )
    with c6:
        render_kpi_card(
            "Holding Cost", fmt_aed(kpis['total_holding_cost']), is_positive=False,
            tooltip="Total accumulated cost of carrying unsold inventory — financing, maintenance, and opportunity cost. Rising values signal urgency to clear slow-moving stock.",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Status breakdown + Health scores ────────────
    col_a, col_b = st.columns([2, 3])

    with col_a:
        section_header(
            "Portfolio by Completion Status",
            tooltip="Distributes all projects by their current completion stage. A heavy weight in early stages signals future revenue potential; too many stalled projects may indicate execution risk or resource bottlenecks.",
        )
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
        section_header(
            "Project Health Scores (Top 10)",
            tooltip="Dual-bar view comparing each project's overall health score (budget + timeline adherence) against its physical construction progress. Where health score lags progress, investigate cost overruns or delivery delays and reallocate resources.",
        )
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
    section_header(
        "Unit Absorption by Project (Top 20)",
        tooltip="Stacked bars showing sold/registered units vs. remaining available units per project. Projects with a large grey (available) portion are slow-moving — consider pricing adjustments, incentive schemes, or targeted marketing campaigns to accelerate absorption.",
    )
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
    # col_c, col_d = st.columns(2)

    # with col_c:
    #     section_header(
    #         "Status Breakdown Detail",
    #         tooltip="Tabular breakdown of how many projects and units sit in each completion status, with average construction progress per group. Use this alongside the pie chart to identify which pipeline stages are accumulating backlogs.",
    #     )
    #     if not df_status.empty:
    #         tbl = df_status.copy()
    #         tbl["avg_progress"] = tbl["avg_progress"].apply(
    #             lambda v: f"{v:.1f}%" if pd.notna(v) else "—"
    #         )
    #         tbl["total_units"] = tbl["total_units"].apply(
    #             lambda v: f"{int(v):,}" if pd.notna(v) else "—"
    #         )
    #         st.dataframe(
    #             tbl.rename(columns={
    #                 "completion_status": "Status",
    #                 "projects": "Projects",
    #                 "total_units": "Total Units",
    #                 "avg_progress": "Avg Progress",
    #             }),
    #             use_container_width=True,
    #             hide_index=True,
    #         )

    # with col_d:
    #     section_header(
    #         "Unit Sell-Through Distribution (%)",
    #         tooltip="Histogram showing what percentage of each project's total units have been sold (booked + registered). A left-skewed curve (many projects below 50%) signals a broad sales challenge; a right skew means the portfolio is selling well. Outlier spikes reveal specific projects needing attention.",
    #     )
    #     if not df_portfolio.empty:
    #         proj_hist = (
    #             df_portfolio.groupby("project_name", as_index=False)
    #             .agg(
    #                 booked_units=("booked_units", "sum"),
    #                 registered_units=("registered_units", "sum"),
    #                 total_units=("total_units", "max"),
    #             )
    #         )
    #         proj_hist["sellthrough_pct"] = (
    #             (proj_hist["booked_units"] + proj_hist["registered_units"])
    #             / proj_hist["total_units"].replace(0, 1) * 100
    #         ).fillna(0).clip(0, 100)
    #         fig = go.Figure(go.Histogram(
    #             x=proj_hist["sellthrough_pct"],
    #             nbinsx=20,
    #             marker=dict(
    #                 color=colors["primary"],
    #                 opacity=0.75,
    #                 line=dict(color="#080d18", width=0.5),
    #             ),
    #             name="Projects",
    #         ))
    #         layout = plotly_dark_layout("", 300)
    #         layout["xaxis"]["title"] = "Sell-Through %"
    #         layout["yaxis"]["title"] = "# Projects"
    #         fig.update_layout(**layout)
    #         st.plotly_chart(fig, use_container_width=True)

    # ── At-risk alert strip ───────────────────────────────
    unsold_count = kpis["unsold_projects"]
    if unsold_count > 0:
        st.markdown(f"""
        <div class="alert-box">
            <b>Attention:</b> {unsold_count} project(s) flagged as unsold (beyond 6-month mark).
            Total holding cost exposure: <b>{fmt_aed(kpis['total_holding_cost'])}</b>.
            Review pricing strategy and marketing push for slow-moving inventory.
        </div>""", unsafe_allow_html=True)
