import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.queries import (
    get_construction_kpis,
    get_construction_project_summary,
    get_milestone_delay_analysis,
    get_contractor_performance,
)
from utils.helpers import (
    render_kpi_card, fmt_aed, fmt_number,
    get_re_colors, plotly_dark_layout, section_header,
)


def render_construction_intelligence(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Construction portfolio intelligence — project health scores, milestone delays,
        budget utilisation, contractor performance and escalation tracking.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        kpis = get_construction_kpis(session)
        df_projects = get_construction_project_summary(session)
        df_milestones = get_milestone_delay_analysis(session)
        df_contractors = get_contractor_performance(session)
    finally:
        session.close()

    # ── KPI Row ───────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        render_kpi_card("Total Projects", f"{kpis['total_projects']:,}")
    with c2:
        render_kpi_card("At-Risk Projects", f"{kpis['at_risk_projects']:,}",
                        is_positive=kpis['at_risk_projects'] == 0)
    with c3:
        render_kpi_card("Avg Health Score", f"{kpis['avg_health_score']:.1f}/100",
                        is_positive=kpis['avg_health_score'] >= 70)
    with c4:
        render_kpi_card("Avg Progress", f"{kpis['avg_progress_pct']:.1f}%")
    with c5:
        render_kpi_card("Avg Delay", f"{kpis['avg_delay_days']:.0f} days",
                        is_positive=kpis['avg_delay_days'] < 15)
    with c6:
        render_kpi_card("Safety Incidents", f"{kpis['safety_incidents']:,}",
                        is_positive=kpis['safety_incidents'] == 0)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Project progress vs planned ────────────────
    section_header("Actual vs Planned Progress by Project")
    if not df_projects.empty:
        top15 = df_projects.head(15).copy()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=top15["planned_progress"],
            y=top15["project_name"],
            name="Planned %",
            orientation="h",
            marker=dict(color=colors["muted"], opacity=0.5, line=dict(width=0)),
        ))
        fig.add_trace(go.Bar(
            x=top15["actual_progress"],
            y=top15["project_name"],
            name="Actual %",
            orientation="h",
            marker=dict(
                color=[colors["success"] if a >= p else colors["danger"]
                       for a, p in zip(top15["actual_progress"], top15["planned_progress"])],
                line=dict(width=0),
            ),
            text=[f"{v:.0f}%" for v in top15["actual_progress"]],
            textposition="outside",
            textfont=dict(size=10, color="#94a3b8"),
        ))
        layout = plotly_dark_layout("", 420)
        layout["barmode"] = "overlay"
        layout["xaxis"]["title"] = "Progress %"
        layout["yaxis"]["autorange"] = "reversed"
        layout["margin"]["l"] = 180
        layout["legend"] = dict(orientation="h", y=-0.12, bgcolor="rgba(0,0,0,0)")
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Budget utilisation + Health score scatter ───
    col_a, col_b = st.columns(2)

    with col_a:
        section_header("Budget Utilisation by Project")
        if not df_projects.empty:
            top12 = df_projects.dropna(subset=["budget_utilization"]).head(12).copy()
            bar_colors = [
                colors["danger"] if v > 100 else (
                    colors["warning"] if v > 85 else colors["primary"]
                )
                for v in top12["budget_utilization"]
            ]
            fig = go.Figure(go.Bar(
                x=top12["budget_utilization"],
                y=top12["project_name"],
                orientation="h",
                marker=dict(color=bar_colors, line=dict(width=0)),
                text=[f"{v:.0f}%" for v in top12["budget_utilization"]],
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 360)
            layout["xaxis"]["title"] = "Budget Utilisation %"
            layout["xaxis"]["range"] = [0, 130]
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 180
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section_header("Health Score vs Cost Overrun")
        if not df_projects.empty:
            df_scatter = df_projects.dropna(subset=["health_score", "avg_cost_overrun"]).copy()
            fig = go.Figure(go.Scatter(
                x=df_scatter["avg_cost_overrun"],
                y=df_scatter["health_score"],
                mode="markers+text",
                text=df_scatter["project_name"].apply(lambda n: n[:18] + "…" if len(n) > 18 else n),
                textposition="top center",
                textfont=dict(size=9, color="#94a3b8"),
                marker=dict(
                    size=df_scatter["max_delay_days"].fillna(0).apply(lambda v: min(max(v / 5, 6), 22)),
                    color=df_scatter["health_score"],
                    colorscale=[[0, colors["danger"]], [0.5, colors["warning"]], [1, colors["success"]]],
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="Health", font=dict(size=10)),
                        thickness=12, tickfont=dict(size=10),
                    ),
                    line=dict(color="rgba(255,255,255,0.15)", width=1),
                    opacity=0.85,
                ),
            ))
            layout = plotly_dark_layout("", 360)
            layout["xaxis"]["title"] = "Avg Cost Overrun %"
            layout["yaxis"]["title"] = "Health Score"
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 3: Milestone delay analysis ───────────────────
    # st.markdown("<br>", unsafe_allow_html=True)
    # section_header("Milestone Delay Analysis")
    # if not df_milestones.empty:
    #     top12_m = df_milestones.head(12).copy()
    #     fig = go.Figure()
    #     fig.add_trace(go.Bar(
    #         x=top12_m["avg_delay"],
    #         y=top12_m["milestone_name"],
    #         orientation="h",
    #         name="Avg Delay (days)",
    #         marker=dict(
    #             color=top12_m["avg_delay"],
    #             colorscale=[[0, colors["primary"]], [1, colors["danger"]]],
    #             line=dict(width=0),
    #         ),
    #         text=[f"{v:.0f}d avg | {int(r)} at risk"
    #               for v, r in zip(top12_m["avg_delay"], top12_m["risk_count"].fillna(0))],
    #         textposition="outside",
    #         textfont=dict(size=10, color="#94a3b8"),
    #     ))
    #     layout = plotly_dark_layout("", 380)
    #     layout["xaxis"]["title"] = "Avg Delay (days)"
    #     layout["yaxis"]["autorange"] = "reversed"
    #     layout["margin"]["l"] = 200
    #     fig.update_layout(**layout)
    #     st.plotly_chart(fig, use_container_width=True)

    # ── Row 4: Contractor performance ─────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Contractor Performance Leaderboard")
    if not df_contractors.empty:
        col_c, col_d = st.columns([3, 2])

        with col_c:
            top10 = df_contractors.head(10).copy()
            fig = go.Figure()
            for metric, col_name in [
                ("avg_quality_score", "Quality"),
                ("avg_delivery_score", "Delivery"),
                ("avg_cost_adherence_score", "Cost Adherence"),
            ]:
                vals = top10[metric].fillna(0)
                fig.add_trace(go.Bar(
                    x=vals,
                    y=top10["contractor_name"],
                    name=col_name,
                    orientation="h",
                    marker=dict(line=dict(width=0)),
                ))
            layout = plotly_dark_layout("", 360)
            layout["barmode"] = "group"
            layout["xaxis"]["title"] = "Score (0-100)"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 160
            layout["legend"] = dict(orientation="h", y=-0.18, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with col_d:
            tbl = df_contractors[[
                "contractor_name", "grade", "overall_performance_score",
                "total_projects_completed", "safety_record_incidents", "preferred_vendor",
            ]].head(15).copy()
            tbl["preferred_vendor"] = tbl["preferred_vendor"].apply(lambda v: "Yes" if v else "No")
            tbl["overall_performance_score"] = tbl["overall_performance_score"].apply(
                lambda v: f"{v:.1f}" if pd.notna(v) else "—"
            )
            st.dataframe(
                tbl.rename(columns={
                    "contractor_name": "Contractor",
                    "grade": "Grade",
                    "overall_performance_score": "Score",
                    "total_projects_completed": "Projects",
                    "safety_record_incidents": "Incidents",
                    "preferred_vendor": "Preferred",
                }),
                use_container_width=True,
                hide_index=True,
            )

    # ── At-risk alert ──────────────────────────────────────
    if kpis["at_risk_projects"] > 0:
        st.markdown(f"""
        <div class="alert-box">
            <b>{kpis['at_risk_projects']} project(s)</b> flagged with delay risk.
            Budget spent to date: <b>{fmt_aed(kpis['total_spent_aed'])}</b> of
            <b>{fmt_aed(kpis['total_budget_aed'])}</b> total budget.
            Immediate review and escalation recommended.
        </div>""", unsafe_allow_html=True)
