import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.queries import (
    get_document_kpis,
    get_document_type_summary,
    get_document_expiry_summary,
    get_document_by_project,
)
from utils.helpers import (
    render_kpi_card, fmt_number,
    get_re_colors, plotly_dark_layout, section_header,
)


def render_document_intelligence(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Document registry intelligence — compliance status, expiry tracking,
        DLD registration rates, notarisation coverage and document volume by project.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        kpis = get_document_kpis(session)
        df_types = get_document_type_summary(session)
        df_expiry = get_document_expiry_summary(session)
        df_projects = get_document_by_project(session)
    finally:
        session.close()

    # ── KPI Row ───────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        render_kpi_card("Total Documents", fmt_number(kpis["total_documents"]))
    with c2:
        render_kpi_card("DLD Registered", f"{kpis['dld_registration_pct']:.1f}%",
                        is_positive=kpis["dld_registration_pct"] > 80)
    with c3:
        render_kpi_card("Notarised", f"{kpis['notarized_pct']:.1f}%",
                        is_positive=kpis["notarized_pct"] > 70)
    with c4:
        render_kpi_card("Expiring Soon", f"{kpis['expiring_soon']:,}",
                        is_positive=kpis["expiring_soon"] == 0)
    with c5:
        render_kpi_card("Expired", f"{kpis['expired']:,}",
                        is_positive=kpis["expired"] == 0)
    with c6:
        render_kpi_card("With AI Summary", fmt_number(kpis["with_ai_summary"]))

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Document types + Expiry status ─────────────
    col_a, col_b = st.columns([3, 2])

    with col_a:
        section_header("Document Volume by Type")
        if not df_types.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_types["count"],
                y=df_types["document_type"],
                orientation="h",
                name="Total",
                marker=dict(color=colors["primary"], opacity=0.8, line=dict(width=0)),
            ))
            fig.add_trace(go.Bar(
                x=df_types["dld_registered"].fillna(0),
                y=df_types["document_type"],
                orientation="h",
                name="DLD Registered",
                marker=dict(color=colors["gold"], opacity=0.7, line=dict(width=0)),
            ))
            fig.add_trace(go.Bar(
                x=df_types["notarized"].fillna(0),
                y=df_types["document_type"],
                orientation="h",
                name="Notarised",
                marker=dict(color=colors["indigo"], opacity=0.65, line=dict(width=0)),
            ))
            layout = plotly_dark_layout("", 420)
            layout["barmode"] = "group"
            layout["xaxis"]["title"] = "Document Count"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 160
            layout["legend"] = dict(orientation="h", y=-0.14, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section_header("Expiry Status Breakdown")
        if not df_expiry.empty:
            expiry_colors = {
                "Valid": colors["success"],
                "Expiring Soon": colors["warning"],
                "Expired": colors["danger"],
                "No Expiry": colors["muted"],
            }
            fig = go.Figure(go.Pie(
                labels=df_expiry["expiry_status"],
                values=df_expiry["count"],
                hole=0.55,
                marker=dict(
                    colors=[expiry_colors.get(s, colors["primary"]) for s in df_expiry["expiry_status"]],
                    line=dict(color="#080d18", width=2),
                ),
                textinfo="label+percent",
                textfont=dict(size=11),
            ))
            layout = plotly_dark_layout("", 420)
            layout["showlegend"] = False
            layout["annotations"] = [dict(
                text=f"<b>{df_expiry['count'].sum():,}</b><br>Docs",
                x=0.5, y=0.5, font=dict(size=13, color="#f0f4f8"),
                showarrow=False,
            )]
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Compliance gauges ──────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Compliance Coverage")
    col_c, col_d, col_e = st.columns(3)

    def _gauge(value, title, color):
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=value,
            number=dict(suffix="%", font=dict(size=26, color=color)),
            title=dict(text=title, font=dict(size=13, color="#94a3b8")),
            gauge=dict(
                axis=dict(range=[0, 100], tickfont=dict(size=10), tickcolor="#4b5563"),
                bar=dict(color=color, thickness=0.28),
                bgcolor="rgba(255,255,255,0.04)",
                bordercolor="rgba(255,255,255,0.06)",
                steps=[
                    dict(range=[0, 50], color="rgba(239,68,68,0.12)"),
                    dict(range=[50, 80], color="rgba(245,158,11,0.10)"),
                    dict(range=[80, 100], color="rgba(16,185,129,0.10)"),
                ],
                threshold=dict(
                    line=dict(color=colors["gold"], width=2),
                    value=80,
                ),
            ),
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=220, margin=dict(l=20, r=20, t=30, b=10),
            font=dict(family="Plus Jakarta Sans", color="#94a3b8"),
        )
        return fig

    with col_c:
        st.plotly_chart(_gauge(kpis["dld_registration_pct"], "DLD Registration", colors["primary"]),
                        use_container_width=True)
    with col_d:
        st.plotly_chart(_gauge(kpis["notarized_pct"], "Notarisation", colors["indigo"]),
                        use_container_width=True)
    with col_e:
        ai_pct = (kpis["with_ai_summary"] / kpis["total_documents"] * 100) if kpis["total_documents"] else 0
        st.plotly_chart(_gauge(ai_pct, "AI Summary Coverage", colors["gold"]),
                        use_container_width=True)

    # ── Row 3: Documents by project ───────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Document Volume by Project (Top 15)")
    if not df_projects.empty:
        col_f, col_g = st.columns([3, 2])

        with col_f:
            fig = go.Figure(go.Bar(
                x=df_projects["doc_count"],
                y=df_projects["project_name"],
                orientation="h",
                marker=dict(
                    color=df_projects["dld_registered"].fillna(0) / df_projects["doc_count"],
                    colorscale=[[0, "#1a3350"], [0.5, colors["primary"]], [1, colors["gold"]]],
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="DLD Reg %", font=dict(size=10)),
                        thickness=12, tickfont=dict(size=10),
                    ),
                    line=dict(width=0),
                ),
                text=[f"{c:,} docs" for c in df_projects["doc_count"]],
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 380)
            layout["xaxis"]["title"] = "Document Count"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 180
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with col_g:
            tbl = df_projects.copy()
            tbl["dld_registered"] = tbl["dld_registered"].fillna(0).apply(lambda v: f"{int(v):,}")
            tbl["penalty_clauses"] = tbl["penalty_clauses"].fillna(0).apply(lambda v: f"{int(v):,}")
            st.dataframe(
                tbl.rename(columns={
                    "project_name": "Project",
                    "emirate": "Emirate",
                    "doc_count": "Docs",
                    "dld_registered": "DLD Reg",
                    "penalty_clauses": "Penalty",
                }),
                use_container_width=True,
                hide_index=True,
            )

    # ── Expiry alert ───────────────────────────────────────
    if kpis["expiring_soon"] > 0 or kpis["expired"] > 0:
        st.markdown(f"""
        <div class="alert-box">
            <b>Compliance Alert:</b> {kpis['expiring_soon']} document(s) expire within 30 days
            and {kpis['expired']} have already expired.
            Immediate review and renewal required to maintain compliance.
        </div>""", unsafe_allow_html=True)
