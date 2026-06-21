import streamlit as st
import plotly.graph_objects as go

from database.connection import get_db_session

from database.queries import (
    get_lead_kpis,
    get_lead_funnel_detail,
    get_lead_source_breakdown,
    get_lead_temperature_distribution,
    get_lead_monthly_trend,
    get_demand_supply_gap,
    get_project_risk_pipeline,
    get_lead_budget_vs_market,
)
from utils.helpers import (
    render_kpi_card, fmt_aed, fmt_number,
    get_re_colors, plotly_dark_layout, section_header,
)


def render_lead_intelligence(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Lead funnel analytics — pipeline value, source performance, conversion rates,
        lead scoring and velocity across the full sales funnel.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        kpis = get_lead_kpis(session)
        df_funnel = get_lead_funnel_detail(session)
        df_source = get_lead_source_breakdown(session)
        df_temp = get_lead_temperature_distribution(session)
        df_monthly = get_lead_monthly_trend(session)
        df_demand_supply = get_demand_supply_gap(session)
        df_risk = get_project_risk_pipeline(session)
        df_budget = get_lead_budget_vs_market(session)
    finally:
        session.close()

    # ── KPI Row ───────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        render_kpi_card("Total Leads", f"{kpis['total_leads']:,}")
    with c2:
        render_kpi_card("Converted", f"{kpis['converted']:,}", is_positive=True)
    with c3:
        render_kpi_card("Conversion Rate", f"{kpis['conversion_rate']:.1f}%",
                        is_positive=kpis['conversion_rate'] > 20)
    with c4:
        render_kpi_card("Pipeline Value", fmt_aed(kpis['pipeline_value']))
    with c5:
        render_kpi_card("Avg Lead Score", f"{kpis['avg_lead_score']:.0f}/100")
    with c6:
        render_kpi_card("Hot Leads", f"{kpis['hot_leads']:,}", is_positive=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Funnel + Temperature ───────────────────────
    col_a, col_b = st.columns([3, 2])

    with col_a:
        section_header("Lead Funnel by Stage")
        if not df_funnel.empty:
            fig = go.Figure(go.Funnel(
                y=df_funnel["lead_stage"],
                x=df_funnel["count"],
                textinfo="value+percent initial",
                textfont=dict(size=11, color="#f0f4f8"),
                marker=dict(
                    color=colors["colors_seq"][:len(df_funnel)],
                    line=dict(color="#080d18", width=1),
                ),
                connector=dict(line=dict(color="rgba(255,255,255,0.08)", width=1)),
            ))
            layout = plotly_dark_layout("", 400)
            layout["margin"] = dict(l=120, r=20, t=20, b=20)
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section_header("Lead Temperature Mix")
        if not df_temp.empty:
            temp_colors = {
                "Hot": colors["danger"], "Warm": colors["warning"],
                "Cold": colors["indigo"], "Neutral": colors["muted"],
            }
            fig = go.Figure(go.Pie(
                labels=df_temp["lead_temperature"],
                values=df_temp["count"],
                hole=0.55,
                marker=dict(
                    colors=[temp_colors.get(t, colors["primary"]) for t in df_temp["lead_temperature"]],
                    line=dict(color="#080d18", width=2),
                ),
                textinfo="percent+label",
                textfont=dict(size=11),
            ))
            layout = plotly_dark_layout("", 400)
            layout["showlegend"] = False
            layout["annotations"] = [dict(
                text=f"<b>{df_temp['count'].sum():,}</b><br>Leads",
                x=0.5, y=0.5, font=dict(size=13, color="#f0f4f8"),
                showarrow=False,
            )]
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Monthly trend ──────────────────────────────
    section_header("Monthly Lead Volume & Conversion Trend")
    if not df_monthly.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_monthly["month"], y=df_monthly["total_leads"],
            name="Total Leads", marker_color=colors["indigo"], opacity=0.65,
        ))
        fig.add_trace(go.Bar(
            x=df_monthly["month"], y=df_monthly["converted"],
            name="Converted", marker_color=colors["primary"], opacity=0.85,
        ))
        fig.add_trace(go.Scatter(
            x=df_monthly["month"], y=df_monthly["conversion_rate"],
            name="Conv. Rate %", yaxis="y2",
            line=dict(color=colors["gold"], width=2.5),
            mode="lines+markers", marker=dict(size=5),
        ))
        layout = plotly_dark_layout("", 340)
        layout["barmode"] = "overlay"
        layout["yaxis2"] = dict(
            title=dict(text="Conversion Rate %", font=dict(color=colors["gold"])),
            overlaying="y", side="right",
            gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11),
        )
        layout["legend"] = dict(orientation="h", y=-0.18, x=0, bgcolor="rgba(0,0,0,0)")
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 3: Source performance ─────────────────────────
    section_header("Lead Source Performance")
    if not df_source.empty:
        col_c, col_d = st.columns([3, 2])

        with col_c:
            fig = go.Figure(go.Bar(
                x=df_source["total_leads"],
                y=df_source["lead_source"],
                orientation="h",
                marker=dict(
                    color=df_source["conversion_rate"],
                    colorscale=[[0, "#1a3350"], [0.5, colors["primary"]], [1, colors["gold"]]],
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="Conv %", font=dict(size=10)),
                        thickness=12, tickfont=dict(size=10),
                    ),
                    line=dict(width=0),
                ),
                text=[f"{t:,} leads | {c:.1f}% conv"
                      for t, c in zip(df_source["total_leads"], df_source["conversion_rate"])],
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 360)
            layout["xaxis"]["title"] = "Total Leads"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 140
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with col_d:
            section_header("Source Summary Table")
            display = df_source[[
                "lead_source", "total_leads", "conversion_rate", "avg_cpl", "avg_funnel_days"
            ]].copy()
            display["conversion_rate"] = display["conversion_rate"].apply(lambda v: f"{v:.1f}%")
            display["avg_cpl"] = display["avg_cpl"].apply(lambda v: f"AED {v:,.0f}")
            display["avg_funnel_days"] = display["avg_funnel_days"].apply(lambda v: f"{v:.0f}d")
            st.dataframe(
                display.rename(columns={
                    "lead_source": "Source",
                    "total_leads": "Leads",
                    "conversion_rate": "Conv %",
                    "avg_cpl": "Cost/Lead",
                    "avg_funnel_days": "Avg Days",
                }),
                use_container_width=True,
                hide_index=True,
            )

    # ── Row 5 & 6: Cross-Domain Intelligence ─────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Cross-Domain Intelligence", badge="UNIQUE")

    # ── 5a: Demand vs Supply Gap ──────────────────────────
    section_header("Demand vs Available Inventory")
    if not df_demand_supply.empty:
        BED_ORDER = ["Studio", "1BR", "2BR", "3BR", "4BR", "5BR", "5+BR"]
        pivot_d = df_demand_supply.pivot_table(
            index="emirate", columns="bedrooms", values="lead_count",
            aggfunc="sum", fill_value=0,
        )
        pivot_s = df_demand_supply.pivot_table(
            index="emirate", columns="bedrooms", values="available_units",
            aggfunc="sum", fill_value=0,
        )
        cols_sorted = [c for c in BED_ORDER if c in pivot_d.columns] + \
                      [c for c in pivot_d.columns if c not in BED_ORDER]
        pivot_d = pivot_d.reindex(columns=cols_sorted, fill_value=0)
        pivot_s = pivot_s.reindex(columns=cols_sorted, fill_value=0)

        annotations = [
            [f"{int(pivot_d.iloc[r, c])}d / {int(pivot_s.iloc[r, c])}u"
             for c in range(len(pivot_d.columns))]
            for r in range(len(pivot_d.index))
        ]
        fig5 = go.Figure(go.Heatmap(
            z=pivot_d.values.tolist(),
            x=pivot_d.columns.tolist(),
            y=pivot_d.index.tolist(),
            text=annotations,
            texttemplate="%{text}",
            textfont=dict(size=11, color="#f0f4f8"),
            colorscale=[
                [0.0, "rgba(16,185,129,0.15)"],
                [0.5, "rgba(245,158,11,0.70)"],
                [1.0, "rgba(239,68,68,0.90)"],
            ],
            showscale=True,
            colorbar=dict(
                title=dict(text="Leads", font=dict(size=10)),
                thickness=10, tickfont=dict(size=10),
            ),
        ))
        layout5 = plotly_dark_layout("", 320)
        layout5["xaxis"]["title"] = "Bedroom Preference"
        layout5["yaxis"]["title"] = "Emirate"
        layout5["margin"] = dict(l=110, r=70, t=20, b=60)
        fig5.update_layout(**layout5)
        st.plotly_chart(fig5, use_container_width=True)
        st.caption("Each cell: **Xd** = leads demanding this type · **Yu** = units available. Red = high demand, low supply.")
    else:
        st.info("No demand/supply data available.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 5b: Project Risk × Late-Stage Leads ──────────────
    col_risk, col_budget = st.columns([5, 5])

    with col_risk:
        section_header("Pipeline at Construction Risk")
        if not df_risk.empty:
            def _hc(score):
                if score >= 80: return colors["primary"]
                if score >= 60: return colors["gold"]
                return colors["rose"]

            fig6 = go.Figure(go.Bar(
                y=df_risk["project_name"],
                x=df_risk["late_stage_leads"],
                orientation="h",
                marker_color=[_hc(s) for s in df_risk["health_score"]],
                text=[
                    f"{int(r.late_stage_leads)} leads · {fmt_aed(r.at_risk_value_aed)} · {int(r.delay_days)}d delay"
                    for _, r in df_risk.iterrows()
                ],
                textposition="outside",
                textfont=dict(size=9, color="#94a3b8"),
            ))
            layout6 = plotly_dark_layout("", 320)
            layout6["xaxis"]["title"] = "Late-Stage Leads"
            layout6["margin"] = dict(l=150, r=20, t=20, b=40)
            layout6["yaxis"]["autorange"] = "reversed"
            fig6.update_layout(**layout6)
            st.plotly_chart(fig6, use_container_width=True)
            st.caption("Bar color: green ≥ 80 health · amber 60–79 · red < 60. Shows leads at risk of cancellation due to construction delays.")
        else:
            st.info("No late-stage leads found.")

    # ── 5c: Lead Budget vs Market Reality ─────────────────
    with col_budget:
        section_header("Lead Budget vs Market Price")
        if not df_budget.empty:
            fig7 = go.Figure(go.Bar(
                y=df_budget["label"],
                x=df_budget["budget_gap_pct"],
                orientation="h",
                marker_color=[
                    colors["primary"] if g >= 0 else colors["rose"]
                    for g in df_budget["budget_gap_pct"]
                ],
                text=[
                    f"{'+' if g >= 0 else ''}{g:.1f}%  ({int(r.lead_count)} leads)"
                    for g, (_, r) in zip(df_budget["budget_gap_pct"], df_budget.iterrows())
                ],
                textposition="outside",
                textfont=dict(size=9, color="#94a3b8"),
            ))
            fig7.add_vline(x=0, line_color="rgba(255,255,255,0.15)", line_width=1)
            layout7 = plotly_dark_layout("", 320)
            layout7["xaxis"]["title"] = "Budget Gap vs Market (%)"
            layout7["xaxis"]["ticksuffix"] = "%"
            layout7["margin"] = dict(l=160, r=80, t=20, b=40)
            layout7["yaxis"]["autorange"] = "reversed"
            fig7.update_layout(**layout7)
            st.plotly_chart(fig7, use_container_width=True)
            st.caption("Green = leads can afford market prices. Red = budget below market — deals will stall at Proposal regardless of sales effort.")
        else:
            st.info("No budget vs market data available.")

    # ── Row 4: Stage detail table ─────────────────────────
    # st.markdown("<br>", unsafe_allow_html=True)
    # section_header("Funnel Stage Detail")
    # if not df_funnel.empty:
    #     tbl = df_funnel[[
    #         "lead_stage", "count", "avg_score", "avg_days_in_stage", "pipeline_value"
    #     ]].copy()
    #     tbl["avg_score"] = tbl["avg_score"].apply(lambda v: f"{v:.0f}/100" if pd.notna(v) else "—")
    #     tbl["avg_days_in_stage"] = tbl["avg_days_in_stage"].apply(
    #         lambda v: f"{v:.0f}d" if pd.notna(v) else "—"
    #     )
    #     tbl["pipeline_value"] = tbl["pipeline_value"].apply(
    #         lambda v: fmt_aed(v) if pd.notna(v) and v else "—"
    #     )
    #     st.dataframe(
    #         tbl.rename(columns={
    #             "lead_stage": "Stage",
    #             "count": "Count",
    #             "avg_score": "Avg Score",
    #             "avg_days_in_stage": "Avg Days",
    #             "pipeline_value": "Pipeline Value",
    #         }),
    #         use_container_width=True,
    #         hide_index=True,
    #     )
