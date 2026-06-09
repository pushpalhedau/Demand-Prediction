"""Tab 4 — Customer & Pricing Intelligence"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import frontend.api_client as api
from frontend.components.kpi_cards import (
    kpi_card, render_kpi_row, section_header, alert_card, KPI_CSS, score_badge
)
from frontend.components.charts import (
    bar_chart, scatter_chart, pie_chart, line_chart
)
from frontend.components.theme import C_INDIGO, C_EMERALD, C_AMBER, C_RED, themed


def render(filters: dict = None):
    filters       = filters or {}
    default_area  = filters.get("area")  or "Business Bay"
    default_ptype = filters.get("property_type") or "Apartment"
    st.markdown(KPI_CSS, unsafe_allow_html=True)
    tab1, tab2 = st.tabs([
        "Buyer Segmentation", "Price Intelligence",
    ])

    # ── Tab 1: Buyer Segmentation ────────────────────────────────
    with tab1:
        st.markdown(section_header("AI Buyer Segmentation",
                                    "KMeans clustering on DLD transaction profiles",
                                    help_text="KMeans clustering on DLD transaction profiles (value, area, property type, nationality, bedroom count). 6 buyer segments derived from 456,000 transactions spanning 2019–2024."),
                    unsafe_allow_html=True)
        try:
            seg_data = api.get_buyer_segments()
            segments = seg_data.get("segments", [])
            if segments:
                colors = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"]
                for i, seg in enumerate(segments):
                    with st.expander(
                        f"**{seg['label']}** — {seg['pct']:.1f}% of market  |  "
                        f"Avg Value: AED {seg['avg_transaction_value_aed']:,.0f}",
                        expanded=(i == 0),
                    ):
                        c1, c2, c3 = st.columns(3)
                        c1.markdown(f"**Top Areas:** {', '.join(seg.get('top_areas', []))}")
                        c2.markdown(f"**Top Nationalities:** {', '.join(seg.get('top_nationalities', []))}")
                        c3.markdown(f"**Property Types:** {', '.join(seg.get('top_prop_types', []))}")

                # Segment distribution chart
                df_seg = pd.DataFrame(segments)
                fig = pie_chart(df_seg["label"].tolist(), df_seg["count"].tolist(),
                                title="Market Segment Distribution", height=380)
                st.plotly_chart(fig, use_container_width=True)

            # 2D Projection — commented out for now
            # st.markdown(section_header("Segment 2D Map (PCA)", "Visual cluster separation",
            #     help_text="PCA projection of buyer transaction feature vectors into 2D space. Each dot = one buyer transaction; colours = assigned segment. A sample of 2,000 records is shown for visual clarity."),
            #     unsafe_allow_html=True)
            # try:
            #     map_data = api.get_segment_map(sample=2000)
            #     if map_data.get("x"):
            #         df_map = pd.DataFrame(map_data)
            #         segment_labels = df_map["segment"].unique()
            #         cluster_colors = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"]
            #         fig = go.Figure()
            #         for i, seg_label in enumerate(segment_labels):
            #             mask = df_map["segment"] == seg_label
            #             fig.add_trace(go.Scatter(
            #                 x=df_map[mask]["x"], y=df_map[mask]["y"],
            #                 mode="markers", name=seg_label,
            #                 marker=dict(color=cluster_colors[i % 6], size=4, opacity=0.6,
            #                              line=dict(color="#07071a", width=0.5)),
            #             ))
            #         fig.update_layout(**themed(
            #                            height=420,
            #                            title="Buyer Segments in 2D Feature Space",
            #                            xaxis_title="PCA Component 1",
            #                            yaxis_title="PCA Component 2"))
            #         st.plotly_chart(fig, use_container_width=True)
            # except Exception:
            #     pass
        except api.APIError as e:
            st.error(str(e))

    # ── Tab 2: Price Intelligence ────────────────────────────────
    with tab2:
        st.markdown(section_header("Dynamic Price Intelligence",
                                    "AI-powered price prediction and elasticity analysis",
                                    help_text="Price predictor trained on DLD transaction data (2019–2024). Enter property specs to get a market-calibrated price per sqft and total price recommendation with confidence score."),
                    unsafe_allow_html=True)

        # Price predictor (AI hybrid: DLD anchor + Groq + live news)
        with st.form("price_form"):
            st.markdown("**AI Price Predictor** — DLD data + live news + Groq LLM")
            c1, c2, c3 = st.columns(3)
            with c1:
                try:
                    _p_areas = api.get_all_areas()
                except Exception:
                    _p_areas = []
                _p_area_opts = [default_area] + [a for a in _p_areas if a != default_area]
                p_area = st.selectbox("Area", _p_area_opts, key="p_area")
                p_type = st.selectbox("Property Type",
                                       ["Apartment", "Villa", "Townhouse", "Penthouse", "Studio", "Commercial"],
                                       key="p_type")
            with c2:
                p_beds = st.number_input("Bedrooms", 0, 10, 2, key="p_beds")
                p_sqft = st.number_input("Area (sqft)", 300, 20000, 1200, step=50, key="p_sqft")
            with c3:
                p_offplan = st.checkbox("Off-Plan", key="p_offplan")
                p_year    = st.number_input("Year", 2023, 2027, 2026, key="p_year")
                p_month   = st.number_input("Month", 1, 12, 6, key="p_month")
            submitted = st.form_submit_button("Analyse & Predict Price")

        if submitted:
            with st.spinner("Fetching DLD data, market news, and AI analysis…"):
                try:
                    r = api.predict_price_ai(
                        p_area, p_type, p_beds, p_sqft, p_offplan, p_year, p_month
                    )

                    # Price cards
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Recommended Price/Sqft",
                               f"AED {r.get('recommended_price_per_sqft_aed', 0):,.0f}")
                    c2.metric("Recommended Total",
                               f"AED {r.get('recommended_total_price_aed', 0)/1e6:.2f}M")
                    c3.metric("Premium Ceiling",
                               f"AED {r.get('premium_ceiling_aed', 0)/1e6:.2f}M")
                    c4.metric("Discount Floor",
                               f"AED {r.get('discount_floor_aed', 0)/1e6:.2f}M")

                    # AI Adjustment badge
                    anchor  = r.get("anchor_price_per_sqft_aed", 0)
                    final   = r.get("recommended_price_per_sqft_aed", 0)
                    adj     = r.get("price_adjustment_pct", 0)
                    adj_col = "#10b981" if adj >= 0 else "#ef4444"
                    adj_sign = "+" if adj >= 0 else ""
                    conf    = r.get("confidence", "medium").lower()
                    conf_color = {"high": "#10b981", "medium": "#f59e0b", "low": "#ef4444"}.get(conf, "#64748b")
                    st.markdown(
                        f'<div style="display:flex;gap:12px;align-items:center;margin:8px 0 4px">'
                        f'<span style="background:#1e1e3f;padding:6px 14px;border-radius:6px;'
                        f'font-size:13px;font-family:Inter,sans-serif;color:#94a3b8">'
                        f'DLD Anchor: <b style="color:#f1f5f9">AED {anchor:,.0f}/sqft</b> → '
                        f'<b style="color:{adj_col}">AED {final:,.0f}/sqft ({adj_sign}{adj:.1f}%)</b></span>'
                        f'<span style="background:{conf_color}22;border:1px solid {conf_color};'
                        f'color:{conf_color};padding:4px 12px;border-radius:20px;'
                        f'font-size:12px;font-weight:600;font-family:Inter,sans-serif">'
                        f'Confidence: {conf.title()}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    # Key signals
                    signals = r.get("key_signals", [])
                    if signals:
                        st.markdown(
                            "<div style='margin:8px 0 4px'>" +
                            "".join(
                                f'<span style="display:inline-block;background:#0d0d20;border:1px solid #1e1e3f;'
                                f'color:#94a3b8;padding:3px 10px;border-radius:4px;'
                                f'font-size:12px;font-family:Inter,sans-serif;margin:2px 4px 2px 0">'
                                f'▸ {s}</span>'
                                for s in signals
                            ) + "</div>",
                            unsafe_allow_html=True,
                        )

                    # LLM reasoning
                    reasoning = r.get("reasoning", "")
                    if reasoning:
                        st.markdown(
                            f'<p style="color:#94a3b8;font-style:italic;font-size:13px;'
                            f'font-family:Inter,sans-serif;margin:8px 0 4px;'
                            f'background:#0d0d20;padding:10px 14px;border-radius:6px;'
                            f'border-left:3px solid #6366f1">{reasoning}</p>',
                            unsafe_allow_html=True,
                        )

                    # News table
                    news = r.get("news_used", [])
                    if news:
                        st.markdown(
                            '<p style="color:#64748b;font-size:11px;font-family:Inter,'
                            'sans-serif;margin:12px 0 4px;text-transform:uppercase;'
                            'letter-spacing:0.06em;font-weight:600">Market News Used</p>',
                            unsafe_allow_html=True,
                        )
                        df_news = pd.DataFrame(news)[["title", "source", "publishedAt"]]
                        df_news.columns = ["Title", "Source", "Date"]
                        st.dataframe(df_news, use_container_width=True, hide_index=True)
                    else:
                        st.info("No recent news found for this area. Price based on DLD anchor only.")

                except api.APIError as e:
                    st.error(str(e))

        # Price trends by area
        st.markdown(section_header("Price Trends by Area",
            help_text="Average AED per sqft per quarter for the top 8 areas by transaction volume. Derived from DLD transaction records from 2019 through 2024. Useful for spotting area-level price cycles."),
            unsafe_allow_html=True)
        try:
            pt = api.get_price_trends_by_area(top_areas=8)
            trends = pt.get("trends", [])
            if trends:
                df_pt = pd.DataFrame(trends)
                if not df_pt.empty and "area_name" in df_pt.columns:
                    areas_in = df_pt["area_name"].unique()
                    fig = go.Figure()
                    colors = ["#6366f1","#10b981","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#f97316","#ec4899"]
                    for i, area in enumerate(areas_in):
                        df_a = df_pt[df_pt["area_name"] == area].sort_values("period")
                        fig.add_trace(go.Scatter(
                            x=df_a["period"], y=df_a["avg_price_sqft"],
                            name=area, line=dict(color=colors[i % 8], width=2), mode="lines",
                        ))
                    fig.update_layout(**themed(
                                       height=380, title="",
                                       yaxis_title="AED / Sqft", hovermode="x unified"))
                    st.plotly_chart(fig, use_container_width=True)
        except api.APIError as e:
            st.warning(str(e))

        # Price elasticity
        st.markdown(section_header("Price Elasticity by Area",
                                    "Negative elasticity = price-sensitive demand",
                                    help_text="Demand elasticity per area: how much demand changes (%) for a 1% price change. Negative = price-sensitive buyers. Estimated via log-log regression on DLD transaction data (2019–2024)."),
                    unsafe_allow_html=True)
        try:
            elast = api.get_price_elasticity()
            if elast:
                df_el = pd.DataFrame(elast)
                color = ["#10b981" if e < 0 else "#ef4444" for e in df_el["elasticity"]]
                fig = go.Figure(go.Bar(
                    x=df_el["elasticity"], y=df_el["area"],
                    orientation="h", marker_color=color,
                    text=[f"{e:.2f}" for e in df_el["elasticity"]],
                    textposition="outside",
                ))
                fig.update_layout(**themed(
                                   height=400,
                                   title="", xaxis_title="Elasticity Coefficient",
                                   showlegend=False))
                st.plotly_chart(fig, use_container_width=True)
        except api.APIError as e:
            st.warning(str(e))

    # ── Tab 3: Rental Analysis — commented out ───────────────────
    # with tab3:
    #     st.markdown(section_header("Rental Market Intelligence",
    #         help_text="Summary metrics from the DLD rental contract database covering all registered residential leases across Dubai from 2019 to 2024."),
    #         unsafe_allow_html=True)
    #     try:
    #         rent = api.get_rental_analysis()
    #         summary = rent.get("summary", {})
    #         render_kpi_row([
    #             kpi_card("Total Contracts", f"{summary.get('total_contracts',0):,}", None, gradient="indigo",
    #                      help_text="Total DLD-registered rental contracts for the selected year."),
    #             kpi_card("Avg Annual Rent", f"{summary.get('avg_annual_rent',0)/1000:.0f}K",
    #                       None, prefix="AED ", gradient="emerald"),
    #             kpi_card("Median Annual Rent", f"{summary.get('median_annual_rent',0)/1000:.0f}K",
    #                       None, prefix="AED ", gradient="violet"),
    #             kpi_card("Renewal Rate", f"{summary.get('renewal_rate_pct',0):.1f}",
    #                       None, suffix="%", gradient="amber"),
    #         ], cols=4)
    #         col1, col2 = st.columns(2)
    #         with col1:
    #             by_area = rent.get("by_area", [])
    #             if by_area:
    #                 df_ra = pd.DataFrame(by_area)
    #                 fig = bar_chart(df_ra["area"].tolist(), df_ra["avg_annual_rent"].tolist(),
    #                                 title="Avg Annual Rent by Area", horizontal=True, height=380, color=C_INDIGO)
    #                 st.plotly_chart(fig, use_container_width=True)
    #         with col2:
    #             by_type = rent.get("by_type", [])
    #             if by_type:
    #                 df_rt = pd.DataFrame(by_type)
    #                 fig = bar_chart(df_rt["property_type"].tolist(), df_rt["avg_annual_rent"].tolist(),
    #                                 title="Avg Annual Rent by Property Type", height=380, color=C_EMERALD)
    #                 st.plotly_chart(fig, use_container_width=True)
    #     except api.APIError as e:
    #         st.error(str(e))

    # ── Tab 4: Nationality Demand — commented out ────────────────
    # with tab4:
    #     st.markdown(section_header("Buyer Nationality Intelligence",
    #         help_text="Top 15 nationalities by DLD transaction count."),
    #         unsafe_allow_html=True)
    #     try:
    #         nat = api.get_nationality_demand(top_n=15)
    #         data = nat.get("data", [])
    #         year = nat.get("year", 2024)
    #         if data:
    #             df_nat = pd.DataFrame(data)
    #             col1, col2 = st.columns(2)
    #             with col1:
    #                 fig = bar_chart(df_nat["nationality"].tolist(), df_nat["transactions_curr"].tolist(),
    #                                 title=f"Transactions by Nationality ({year})",
    #                                 horizontal=True, height=420, color=C_INDIGO)
    #                 st.plotly_chart(fig, use_container_width=True)
    #             with col2:
    #                 colors = ["#10b981" if x >= 0 else "#ef4444" for x in df_nat["yoy_change_pct"]]
    #                 fig = go.Figure(go.Bar(
    #                     x=df_nat["yoy_change_pct"], y=df_nat["nationality"],
    #                     orientation="h", marker_color=colors,
    #                     text=[f"{x:+.1f}%" for x in df_nat["yoy_change_pct"]],
    #                     textposition="outside",
    #                 ))
    #                 fig.update_layout(**themed(height=420, title="YoY Change by Nationality",
    #                                            xaxis_title="Change %", showlegend=False))
    #                 st.plotly_chart(fig, use_container_width=True)
    #             prefs = api.get_property_preferences()
    #             st.markdown(section_header("Market-Wide Preferences"), unsafe_allow_html=True)
    #             c1, c2, c3 = st.columns(3)
    #             c1.metric("Off-Plan Share", f"{prefs.get('off_plan_share', 0):.1f}%")
    #             c2.metric("Avg Transaction", f"AED {prefs.get('avg_transaction_value', 0):,.0f}")
    #             c3.metric("Median Transaction", f"AED {prefs.get('median_transaction_value', 0):,.0f}")
    #             col1, col2 = st.columns(2)
    #             with col1:
    #                 type_pref = prefs.get("by_type", {})
    #                 if type_pref:
    #                     fig = pie_chart(list(type_pref.keys()), list(type_pref.values()),
    #                                     title="Demand by Property Type", height=300)
    #                     st.plotly_chart(fig, use_container_width=True)
    #             with col2:
    #                 bed_pref = prefs.get("by_bedrooms", {})
    #                 if bed_pref:
    #                     fig = pie_chart(list(bed_pref.keys()), list(bed_pref.values()),
    #                                     title="Demand by Bedrooms", height=300)
    #                     st.plotly_chart(fig, use_container_width=True)
    #     except api.APIError as e:
    #         st.error(str(e))
