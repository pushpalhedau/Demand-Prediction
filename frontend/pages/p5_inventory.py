"""Tab 5 — Project & Inventory Intelligence"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import frontend.api_client as api
from frontend.components.kpi_cards import (
    kpi_card, render_kpi_row, section_header, alert_card, KPI_CSS, score_badge
)
from frontend.components.charts import bar_chart, pie_chart, monte_carlo_chart
from frontend.components.theme import C_INDIGO, C_EMERALD, C_AMBER, C_RED, themed


def render(filters: dict = None):
    filters      = filters or {}
    default_area = filters.get("area") or "Business Bay"
    st.markdown(KPI_CSS, unsafe_allow_html=True)
    tab1, tab2 = st.tabs([
        "Project Launch Advisor", "Portfolio Overview",
    ])

    # ── Tab 1: Project Launch Advisor ────────────────────────────
    with tab1:
        st.markdown(section_header("AI Project Launch Advisor",
                                    "DLD scoring + live news + Groq LLM launch assessment",
                                    help_text="Hybrid AI viability assessment: DLD transaction data scores demand/pricing/velocity, then Groq LLM + live Google News provides strategic narrative and market signals."),
                    unsafe_allow_html=True)
        with st.form("launch_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                try:
                    _l_areas = api.get_all_areas()
                except Exception:
                    _l_areas = []
                _l_area_opts = [default_area] + [a for a in _l_areas if a != default_area]
                l_area    = st.selectbox("Area", _l_area_opts, key="l_area")
                l_type    = st.selectbox("Property Type",
                                          ["Apartment", "Villa", "Townhouse", "Penthouse", "Commercial"],
                                          key="l_type")
                l_units   = st.number_input("Total Units", 10, 5000, 200, step=10, key="l_units")
            with c2:
                l_psf     = st.number_input("Price/Sqft (AED)", 500, 10000, 1500, step=50, key="l_psf")
                l_sqft    = st.number_input("Avg Unit Size (sqft)", 300, 10000, 1000, step=50, key="l_sqft")
                l_offplan = st.checkbox("Off-Plan Launch", value=True, key="l_offplan")
            with c3:
                l_year    = st.number_input("Launch Year", 2024, 2027, 2025, key="l_year")
                l_month   = st.number_input("Launch Month", 1, 12, 6, key="l_month")
                l_amen    = st.slider("Amenities Score (1-10)", 1, 10, 7, key="l_amen")
            submitted = st.form_submit_button("Run AI Launch Assessment")

        if submitted:
            with st.spinner("Analysing DLD data, fetching market news, running AI assessment…"):
                try:
                    result   = api.launch_advisor_ai(
                        l_area, l_type, l_units, float(l_psf),
                        float(l_sqft), l_year, l_month, l_offplan, l_amen,
                    )
                    success  = result.get("success_probability", 0)
                    inv_risk = result.get("inventory_risk", "Unknown")

                    # ── Hero metrics ─────────────────────────────────────
                    render_kpi_row([
                        kpi_card("Success Probability",
                                  f"{success*100:.1f}",
                                  None, suffix="%",
                                  gradient="emerald" if success > 0.65 else "amber" if success > 0.4 else "rose",
                                  help_text="Model-estimated probability of achieving ≥80% sell-out within 18 months. Based on area demand trends, pricing vs. market average, and comparable DLD project performance."),
                        kpi_card("Expected Revenue",
                                  f"{result.get('expected_revenue_aed',0)/1e6:.1f}M",
                                  None, prefix="AED ", gradient="indigo",
                                  help_text="Projected total revenue = units × price per sqft × avg unit size, scaled by success probability."),
                        kpi_card("Months to Sell-Out",
                                  f"{result.get('months_to_sellout',0):.0f}",
                                  None, gradient="violet",
                                  help_text="Estimated time to sell all units based on the area's current absorption rate adjusted for your pricing premium vs. market."),
                        kpi_card("Inventory Risk",
                                  inv_risk, None,
                                  gradient="emerald" if inv_risk == "Low" else
                                           "amber" if inv_risk == "Medium" else "rose",
                                  help_text="Risk classification based on projected months-to-sellout and area supply competition. Derived from DLD project and listing data."),
                    ], cols=4)

                    col1, col2 = st.columns([1, 1])
                    with col1:
                        st.markdown("**Sub-Score Breakdown**")
                        for s_name, s_val in [
                            ("Demand Score",   result.get("demand_score", 0)),
                            ("Price Score",    result.get("price_score", 0)),
                            ("Velocity Score", result.get("velocity_score", 0)),
                        ]:
                            st.markdown(f"**{s_name}:** {s_val:.0f}/100")
                            st.progress(s_val / 100)

                        st.markdown(f"**Market Avg Price/Sqft:** AED {result.get('market_avg_psf',0):,.0f}")
                        st.markdown(f"**Your Price Premium:** {result.get('price_premium_pct',0):+.1f}%")
                        st.markdown(f"**Area YoY Growth:** {result.get('area_yoy_growth_pct',0):+.1f}%")
                        st.markdown(f"**Rental Yield:** {result.get('rental_yield_pct',0):.1f}%")

                    with col2:
                        rev_dist = result.get("revenue_distribution", {})
                        if rev_dist:
                            labels = ["P10 (Bear)", "P50 (Base)", "P90 (Bull)"]
                            values = [rev_dist.get("p10", 0), rev_dist.get("p50", 0), rev_dist.get("p90", 0)]
                            fig = bar_chart(labels, [v / 1e6 for v in values],
                                            title="Revenue Distribution (AED M)", height=280,
                                            color=C_EMERALD)
                            st.plotly_chart(fig, use_container_width=True)

                    # ── AI Strategic Recommendation ───────────────────────
                    st.markdown(section_header("AI Strategic Recommendation",
                        help_text="Groq LLM synthesis of DLD market scores, comparable project outcomes, and live news signals for this area and property type."),
                        unsafe_allow_html=True)

                    # Confidence + signals row
                    conf       = result.get("confidence", "medium").lower()
                    conf_color = {"high": "#10b981", "medium": "#f59e0b", "low": "#ef4444"}.get(conf, "#64748b")
                    signals    = result.get("key_signals", [])
                    st.markdown(
                        f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:4px 0 8px">'
                        f'<span style="background:{conf_color}22;border:1px solid {conf_color};'
                        f'color:{conf_color};padding:4px 12px;border-radius:20px;'
                        f'font-size:12px;font-weight:600;font-family:Inter,sans-serif">'
                        f'AI Confidence: {conf.title()}</span>' +
                        "".join(
                            f'<span style="background:#0d0d20;border:1px solid #1e1e3f;color:#94a3b8;'
                            f'padding:3px 10px;border-radius:4px;font-size:12px;font-family:Inter,sans-serif">'
                            f'▸ {s}</span>'
                            for s in signals
                        ) +
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    # Main recommendation
                    ai_rec = result.get("ai_recommendation", "")
                    if ai_rec:
                        st.markdown(
                            f'<p style="color:#94a3b8;font-style:italic;font-size:13px;'
                            f'font-family:Inter,sans-serif;margin:4px 0;'
                            f'background:#0d0d20;padding:10px 14px;border-radius:6px;'
                            f'border-left:3px solid #6366f1">{ai_rec}</p>',
                            unsafe_allow_html=True,
                        )

                    # Launch timing + pricing advice inline
                    timing  = result.get("launch_timing", "")
                    pricing = result.get("pricing_advice", "")
                    if timing or pricing:
                        cols = st.columns(2)
                        if timing:
                            cols[0].markdown(
                                f'<div style="background:#0d0d20;border:1px solid #1e1e3f;border-radius:6px;'
                                f'padding:8px 12px;font-size:12px;font-family:Inter,sans-serif">'
                                f'<span style="color:#64748b;text-transform:uppercase;font-size:10px;'
                                f'font-weight:600;letter-spacing:0.06em">Launch Timing</span><br>'
                                f'<span style="color:#f1f5f9">{timing}</span></div>',
                                unsafe_allow_html=True,
                            )
                        if pricing:
                            cols[1].markdown(
                                f'<div style="background:#0d0d20;border:1px solid #1e1e3f;border-radius:6px;'
                                f'padding:8px 12px;font-size:12px;font-family:Inter,sans-serif">'
                                f'<span style="color:#64748b;text-transform:uppercase;font-size:10px;'
                                f'font-weight:600;letter-spacing:0.06em">Pricing Strategy</span><br>'
                                f'<span style="color:#f1f5f9">{pricing}</span></div>',
                                unsafe_allow_html=True,
                            )

                    # ── News table ────────────────────────────────────────
                    news = result.get("news_used", [])
                    if news:
                        st.markdown(
                            '<p style="color:#64748b;font-size:11px;font-family:Inter,sans-serif;'
                            'margin:12px 0 4px;text-transform:uppercase;letter-spacing:0.06em;'
                            'font-weight:600">Market News Used</p>',
                            unsafe_allow_html=True,
                        )
                        df_news = pd.DataFrame(news)[["title", "source", "publishedAt"]]
                        df_news.columns = ["Title", "Source", "Date"]
                        st.dataframe(df_news, use_container_width=True, hide_index=True)

                    # ── Sellout prediction ────────────────────────────────
                    try:
                        sellout = api.predict_sellout(l_area, l_units, float(l_psf))
                        st.info(
                            f"**Sell-Out Prediction:** Monthly absorption of "
                            f"{sellout.get('monthly_absorption', 0):.0f} units → "
                            f"full sell-out in **{sellout.get('months_to_sellout', 0):.0f} months**"
                        )
                    except Exception:
                        pass

                except api.APIError as e:
                    st.error(str(e))

    # ── Tab 2: Portfolio Overview ────────────────────────────────
    with tab2:
        st.markdown(section_header("Project Portfolio Overview",
            help_text="Aggregate view of all projects in the DLD projects database. Covers active, completed, and off-plan developments with sell-through rates and absorption metrics as of 2024."),
            unsafe_allow_html=True)
        try:
            proj = api.get_project_status()
            summary = proj.get("summary", {})
            render_kpi_row([
                kpi_card("Total Projects", str(summary.get("total_projects", 0)), None, gradient="indigo",
                         help_text="Total number of real estate projects registered in the DLD projects database across all developers, areas, and project types."),
                kpi_card("Active Projects", str(summary.get("active_projects", 0)), None, gradient="emerald",
                         help_text="Projects currently in active construction or sales phase based on DLD project status classification. Excludes completed and cancelled projects."),
                kpi_card("Total Units", f"{summary.get('total_units', 0):,}", None, gradient="violet",
                         help_text="Sum of all residential and commercial units across all DLD-tracked projects regardless of current status (active, completed, or off-plan)."),
                kpi_card("Avg Absorption", f"{summary.get('avg_absorption_rate', 0):.1f}", None, suffix="%", gradient="amber",
                         help_text="Average sell-through rate across all active projects: (units sold ÷ total units) × 100. Derived from DLD unit sales and project records up to 2024."),
            ], cols=4)

            col1, col2 = st.columns([1, 1])
            with col1:
                by_status = proj.get("by_status", [])
                if by_status:
                    df_bs = pd.DataFrame(by_status)
                    fig = pie_chart(df_bs["status"].tolist(), df_bs["count"].tolist(),
                                    title="Projects by Status", height=340)
                    st.plotly_chart(fig, use_container_width=True)

            with col2:
                if by_status:
                    fig = bar_chart(df_bs["status"].tolist(), df_bs["avg_absorption"].tolist(),
                                    title="Avg Absorption Rate by Status",
                                    height=340, color=C_INDIGO)
                    st.plotly_chart(fig, use_container_width=True)

            top_proj = proj.get("top_projects", [])
            if top_proj:
                st.markdown(section_header("Top Projects by Unit Count",
                    help_text="Largest projects by total unit count from the DLD projects database. Includes developer, area, current status, units sold percentage, and average price per sqft."),
                    unsafe_allow_html=True)
                df_tp = pd.DataFrame(top_proj)
                disp_cols = ["project_name", "developer", "area", "status",
                              "total_units", "sold_percentage", "avg_price_per_sqft_aed"]
                avail = [c for c in disp_cols if c in df_tp.columns]
                df_tp[avail] = df_tp[avail].fillna(0)
                st.dataframe(df_tp[avail].set_index("project_name").round(1),
                              use_container_width=True, height=400)
        except api.APIError as e:
            st.error(str(e))

    # ── Tab 3: Absorption Analysis — commented out ───────────────
    # with tab3:
    #     st.markdown(section_header("Inventory Absorption Analysis",
    #                                 "How quickly is inventory being absorbed by the market?",
    #                                 help_text="Rate at which units are being sold relative to total supply, broken down by developer, area, and project type. Based on DLD unit sales and project records up to 2024."),
    #                 unsafe_allow_html=True)
    #     try:
    #         abs_data = api.get_absorption_analysis()
    #         tab_d, tab_a, tab_t = st.tabs(["By Developer", "By Area", "By Project Type"])
    #         with tab_d:
    #             by_dev = abs_data.get("by_developer", [])
    #             if by_dev:
    #                 df_dev = pd.DataFrame(by_dev)
    #                 fig = bar_chart(df_dev["developer"].tolist(), df_dev["avg_absorption"].tolist(),
    #                                 title="Avg Absorption Rate by Developer", horizontal=True,
    #                                 height=400, color=C_EMERALD, value_format="%")
    #                 st.plotly_chart(fig, use_container_width=True)
    #         with tab_a:
    #             by_area = abs_data.get("by_area", [])
    #             if by_area:
    #                 df_area = pd.DataFrame(by_area)
    #                 fig = bar_chart(df_area["area"].tolist(), df_area["avg_absorption"].tolist(),
    #                                 title="Avg Absorption Rate by Area", horizontal=True,
    #                                 height=380, color=C_AMBER, value_format="%")
    #                 st.plotly_chart(fig, use_container_width=True)
    #         with tab_t:
    #             by_type = abs_data.get("by_type", [])
    #             if by_type:
    #                 df_type = pd.DataFrame(by_type)
    #                 fig = bar_chart(df_type["project_type"].tolist(), df_type["avg_absorption"].tolist(),
    #                                 title="Avg Absorption Rate by Project Type",
    #                                 height=300, color=C_INDIGO, value_format="%")
    #                 st.plotly_chart(fig, use_container_width=True)
    #     except api.APIError as e:
    #         st.error(str(e))
