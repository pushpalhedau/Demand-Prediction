"""Tab 3 — Market & Opportunity Intelligence"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import frontend.api_client as api
from frontend.components.kpi_cards import section_header, alert_card, KPI_CSS, score_badge
from frontend.components.charts import bar_chart, scatter_chart, pie_chart, line_chart
from frontend.components.theme import C_INDIGO, C_EMERALD, C_AMBER, themed


def render(filters: dict = None):
    filters = filters or {}
    area    = filters.get("area")
    st.markdown(KPI_CSS, unsafe_allow_html=True)
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Opportunity Heatmap", "Competitor Intelligence",
        "Infrastructure Impact", "Migration & Demographics", "White Space Analysis"
    ])

    # ── Tab 1: Opportunity Heatmap ────────────────────────────────
    with tab1:
        st.markdown(section_header("Investment Opportunity Map",
                                    "Area-level scoring: demand, price growth, yield, infrastructure",
                                    help_text="Bubble chart: X = price YoY growth %, Y = rental yield %. Bubble size = transaction volume. Colour: green ≥75, amber ≥50, red <50 opportunity score. Based on the last 12 months of DLD data."),
                    unsafe_allow_html=True)
        try:
            opps = api.get_market_opportunities(top_n=20)
            opp_list = opps.get("opportunities", [])
            heatmap  = api.get_opportunity_heatmap()

            if opp_list:
                df_opp = pd.DataFrame(opp_list)

                # Bubble chart: X=price growth, Y=rental yield, Size=tx_volume, Color=opp_score
                fig = go.Figure()
                for _, row in df_opp.iterrows():
                    score = row.get("opportunity_score", 0)
                    color = "#10b981" if score >= 75 else "#f59e0b" if score >= 50 else "#ef4444"
                    fig.add_trace(go.Scatter(
                        x=[row.get("price_yoy_change_pct", 0)],
                        y=[row.get("rental_yield_pct", 0)],
                        mode="markers+text",
                        text=[row.get("area_name", "")],
                        textposition="top center",
                        textfont=dict(color="#94a3b8", size=9),
                        marker=dict(
                            size=max(10, min(row.get("transaction_count", 100) / 100, 50)),
                            color=color, line=dict(color="#07071a", width=1), opacity=0.85,
                        ),
                        name=row.get("area_name", ""),
                        showlegend=False,
                        hovertemplate=(
                            f"<b>{row.get('area_name','')}</b><br>"
                            f"Opportunity Score: {score:.0f}/100<br>"
                            f"Price Growth: {row.get('price_yoy_change_pct',0):.1f}%<br>"
                            f"Rental Yield: {row.get('rental_yield_pct',0):.1f}%<br>"
                            f"Transactions: {row.get('transaction_count',0):,}<extra></extra>"
                        ),
                    ))
                fig.update_layout(**themed(
                    height=480,
                    title="Opportunity Matrix — Price Growth vs Rental Yield",
                    xaxis_title="Price YoY Growth (%)", yaxis_title="Rental Yield (%)",
                ))
                st.plotly_chart(fig, use_container_width=True)

                # Top opportunities table
                st.markdown(section_header("Top Opportunity Areas",
                    help_text="Areas ranked by composite opportunity score (0–100) combining demand momentum, price growth, rental yield, and supply levels. Based on the last 12 months of DLD transaction and project data."),
                    unsafe_allow_html=True)
                display_cols = ["area_name", "opportunity_score", "success_probability",
                                 "expected_roi_pct", "avg_price_sqft", "transaction_count",
                                 "price_yoy_change_pct", "rental_yield_pct"]
                avail = [c for c in display_cols if c in df_opp.columns]
                df_disp = df_opp[avail].head(15).round(2)
                df_disp.columns = [c.replace("_", " ").title() for c in df_disp.columns]
                st.dataframe(df_disp.set_index(df_disp.columns[0]),
                              use_container_width=True, height=400)

                # AI Recommendations
                for opp in opp_list[:3]:
                    rec = opp.get("recommendation", "")
                    score = opp.get("opportunity_score", 0)
                    if rec:
                        sev = "success" if score >= 75 else "info" if score >= 50 else "warning"
                        st.markdown(
                            alert_card(opp.get("area_name", ""), rec, sev),
                            unsafe_allow_html=True,
                        )
        except api.APIError as e:
            st.error(str(e))

    # ── Tab 2: Competitor Intelligence ────────────────────────────
    with tab2:
        st.markdown(section_header("Competitive Intelligence",
                                    "Developer rankings, platform data, area competition",
                                    help_text="Developer market share from DLD project registrations and platform listing analysis from property portals. Identifies dominant players and over-listed vs. under-supplied areas. Data: 2024."),
                    unsafe_allow_html=True)
        try:
            comp = api.get_competitor_analysis()

            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown("**Developer Market Share**")
                dev_ranks = comp.get("developer_rankings", [])
                if dev_ranks:
                    df_dev = pd.DataFrame(dev_ranks)
                    fig = bar_chart(df_dev["developer"].tolist(),
                                    df_dev["market_share_pct"].tolist(),
                                    title="", height=380, horizontal=True,
                                    color=C_INDIGO, value_format="%")
                    st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown("**Platform Listings Breakdown**")
                plat = comp.get("platform_breakdown", [])
                if plat:
                    df_plat = pd.DataFrame(plat)
                    fig = pie_chart(df_plat["platform"].tolist(),
                                    df_plat["listings"].tolist(), height=280)
                    st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(
                        df_plat.set_index("platform").round(0),
                        use_container_width=True, height=180,
                    )

            st.markdown(section_header("Area Competition Intensity",
                help_text="Scatter of active listings vs. average asking price per area from property portal data. Large dot = high listing volume. Identifies over-supplied (competitive) vs. under-supplied (opportunity) markets."),
                unsafe_allow_html=True)
            area_comp = comp.get("area_competition", [])
            if area_comp:
                df_ac = pd.DataFrame(area_comp)
                fig = scatter_chart(
                    df_ac, x="active_listings", y="avg_asking_price",
                    size="active_listings", text="area",
                    title="Listings vs Asking Price by Area", height=380,
                )
                st.plotly_chart(fig, use_container_width=True)
        except api.APIError as e:
            st.error(str(e))

    # ── Tab 3: Infrastructure Impact ──────────────────────────────
    with tab3:
        st.markdown(section_header("Infrastructure Impact Analysis",
                                    "Active projects driving real estate demand",
                                    help_text="UAE infrastructure projects scored by expected real estate impact based on budget size, proximity to residential areas, and project type (metro, road, free zone, etc.). Data as of 2024."),
                    unsafe_allow_html=True)
        try:
            infra = api.get_infrastructure_impact()
            projects = infra.get("projects", [])
            impact_summary = infra.get("impact_summary", [])

            col1, col2 = st.columns([1, 1])
            with col1:
                if impact_summary:
                    df_imp = pd.DataFrame(impact_summary)
                    fig = bar_chart(df_imp["impact_on_real_estate"].tolist(),
                                    df_imp["count"].tolist(),
                                    title="Projects by RE Impact Level", height=280,
                                    color=C_EMERALD)
                    st.plotly_chart(fig, use_container_width=True)
            with col2:
                if impact_summary:
                    fig = pie_chart(df_imp["impact_on_real_estate"].tolist(),
                                    df_imp["total_budget"].tolist(),
                                    title="Budget Allocation by Impact", height=280)
                    st.plotly_chart(fig, use_container_width=True)

            if projects:
                df_proj = pd.DataFrame(projects)
                display_cols = ["project_name", "project_type", "emirate",
                                  "budget_aed_million", "expected_completion_year",
                                  "impact_on_real_estate"]
                avail = [c for c in display_cols if c in df_proj.columns]
                st.dataframe(df_proj[avail].set_index("project_name"),
                              use_container_width=True, height=400)
        except api.APIError as e:
            st.error(str(e))

    # ── Tab 4: Migration & Demographics ───────────────────────────
    with tab4:
        st.markdown(section_header("Migration & Demographic Analysis",
                                    "Population growth, expat demand, nationality trends",
                                    help_text="UAE and Dubai population trends from World Bank data. Buyer nationality distribution from DLD transaction records (2019–2024). Covers annual population figures and international demand segments."),
                    unsafe_allow_html=True)
        try:
            mig = api.get_migration_analysis()
            pop_trend = mig.get("population_trend", [])
            nat_demand = mig.get("nationality_demand", [])

            if pop_trend:
                df_pop = pd.DataFrame(pop_trend)
                col1, col2 = st.columns(2)
                with col1:
                    fig = line_chart(df_pop, "year",
                                      ["total_population", "dubai_population"],
                                      title="UAE & Dubai Population Growth", height=320)
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    if "annual_growth_rate_pct" in df_pop.columns:
                        fig = bar_chart(df_pop["year"].tolist(),
                                        df_pop["annual_growth_rate_pct"].tolist(),
                                        title="Annual Population Growth %",
                                        height=320, color=C_AMBER)
                        st.plotly_chart(fig, use_container_width=True)

            if nat_demand:
                df_nat = pd.DataFrame(nat_demand)
                fig = bar_chart(df_nat["buyer_nationality"].tolist(),
                                df_nat["transactions"].tolist(),
                                title="Transactions by Buyer Nationality",
                                height=320, color=C_INDIGO, horizontal=True)
                st.plotly_chart(fig, use_container_width=True)
        except api.APIError as e:
            st.error(str(e))

    # ── Tab 5: White Space Analysis ───────────────────────────────
    with tab5:
        st.markdown(section_header("White Space Analysis",
                                    "High-demand, low-supply areas = untapped opportunity",
                                    help_text="Areas where transaction demand significantly exceeds available listing supply. White Space Score = demand–supply gap index. High score = strong launch opportunity. Based on 2024 DLD and portal data."),
                    unsafe_allow_html=True)
        try:
            ws = api.get_white_space()
            ws_areas = ws.get("white_space_areas", [])
            if ws_areas:
                df_ws = pd.DataFrame(ws_areas)
                fig = scatter_chart(
                    df_ws, x="demand_count", y="supply_count",
                    size="white_space_score", text="area_name",
                    title="Demand vs Supply by Area — Bigger bubble = higher opportunity", height=420,
                )
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_ws.set_index("area_name").round(1),
                              use_container_width=True, height=320)
        except api.APIError as e:
            st.error(str(e))
