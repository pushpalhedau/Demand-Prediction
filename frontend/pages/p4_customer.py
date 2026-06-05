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


def render():
    st.markdown(KPI_CSS, unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs([
        "Buyer Segmentation", "Price Intelligence", "Rental Analysis", "Nationality Demand"
    ])

    # ── Tab 1: Buyer Segmentation ────────────────────────────────
    with tab1:
        st.markdown(section_header("AI Buyer Segmentation",
                                    "KMeans clustering on DLD transaction profiles"),
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

            # 2D Projection
            st.markdown(section_header("Segment 2D Map (PCA)", "Visual cluster separation"), unsafe_allow_html=True)
            try:
                map_data = api.get_segment_map(sample=2000)
                if map_data.get("x"):
                    df_map = pd.DataFrame(map_data)
                    segment_labels = df_map["segment"].unique()
                    cluster_colors = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"]
                    fig = go.Figure()
                    for i, seg_label in enumerate(segment_labels):
                        mask = df_map["segment"] == seg_label
                        fig.add_trace(go.Scatter(
                            x=df_map[mask]["x"], y=df_map[mask]["y"],
                            mode="markers", name=seg_label,
                            marker=dict(color=cluster_colors[i % 6], size=4, opacity=0.6,
                                         line=dict(color="#07071a", width=0.5)),
                        ))
                    fig.update_layout(**themed(
                                       height=420,
                                       title="Buyer Segments in 2D Feature Space",
                                       xaxis_title="PCA Component 1",
                                       yaxis_title="PCA Component 2"))
                    st.plotly_chart(fig, use_container_width=True)
            except Exception:
                pass
        except api.APIError as e:
            st.error(str(e))

    # ── Tab 2: Price Intelligence ────────────────────────────────
    with tab2:
        st.markdown(section_header("Dynamic Price Intelligence",
                                    "AI-powered price prediction and elasticity analysis"),
                    unsafe_allow_html=True)

        # Price predictor
        with st.form("price_form"):
            st.markdown("**Price Predictor**")
            c1, c2, c3 = st.columns(3)
            with c1:
                p_area = st.text_input("Area", value="Business Bay", key="p_area")
                p_type = st.selectbox("Property Type",
                                       ["Apartment", "Villa", "Townhouse", "Penthouse", "Studio", "Commercial"],
                                       key="p_type")
            with c2:
                p_beds = st.number_input("Bedrooms", 0, 10, 2, key="p_beds")
                p_sqft = st.number_input("Area (sqft)", 300, 20000, 1200, step=50, key="p_sqft")
            with c3:
                p_offplan = st.checkbox("Off-Plan", key="p_offplan")
                p_year    = st.number_input("Year", 2023, 2026, 2024, key="p_year")
                p_month   = st.number_input("Month", 1, 12, 6, key="p_month")
            submitted = st.form_submit_button("Predict Optimal Price")

        if submitted:
            try:
                price_result = api.predict_price(
                    p_area, p_type, p_beds, p_sqft, p_offplan, p_year, p_month
                )
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Recommended Price/Sqft", f"AED {price_result.get('recommended_price_per_sqft_aed',0):,.0f}")
                c2.metric("Recommended Total",      f"AED {price_result.get('recommended_total_price_aed',0)/1e6:.2f}M")
                c3.metric("Premium Ceiling",        f"AED {price_result.get('premium_ceiling_aed',0)/1e6:.2f}M")
                c4.metric("Discount Floor",         f"AED {price_result.get('discount_floor_aed',0)/1e6:.2f}M")
                conf = price_result.get("confidence", 0)
                st.progress(conf, text=f"Model Confidence: {conf*100:.0f}%")
            except api.APIError as e:
                st.error(str(e))

        # Price trends by area
        st.markdown(section_header("Price Trends by Area"), unsafe_allow_html=True)
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
                                    "Negative elasticity = price-sensitive demand"),
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

    # ── Tab 3: Rental Analysis ───────────────────────────────────
    with tab3:
        st.markdown(section_header("Rental Market Intelligence"), unsafe_allow_html=True)
        try:
            rent = api.get_rental_analysis()
            summary = rent.get("summary", {})
            render_kpi_row([
                kpi_card("Total Contracts",   f"{summary.get('total_contracts',0):,}", None, "📄", gradient="indigo"),
                kpi_card("Avg Annual Rent",   f"{summary.get('avg_annual_rent',0)/1000:.0f}K",
                          None, "💰", prefix="AED ", gradient="emerald"),
                kpi_card("Median Annual Rent", f"{summary.get('median_annual_rent',0)/1000:.0f}K",
                          None, "📊", prefix="AED ", gradient="violet"),
                kpi_card("Renewal Rate",      f"{summary.get('renewal_rate_pct',0):.1f}",
                          None, "🔄", suffix="%", gradient="amber"),
            ], cols=4)

            col1, col2 = st.columns(2)
            with col1:
                by_area = rent.get("by_area", [])
                if by_area:
                    df_ra = pd.DataFrame(by_area)
                    fig = bar_chart(df_ra["area"].tolist(), df_ra["avg_annual_rent"].tolist(),
                                    title="Avg Annual Rent by Area", horizontal=True, height=380,
                                    color=C_INDIGO)
                    st.plotly_chart(fig, use_container_width=True)
            with col2:
                by_type = rent.get("by_type", [])
                if by_type:
                    df_rt = pd.DataFrame(by_type)
                    fig = bar_chart(df_rt["property_type"].tolist(), df_rt["avg_annual_rent"].tolist(),
                                    title="Avg Annual Rent by Property Type", height=380,
                                    color=C_EMERALD)
                    st.plotly_chart(fig, use_container_width=True)
        except api.APIError as e:
            st.error(str(e))

    # ── Tab 4: Nationality Demand ────────────────────────────────
    with tab4:
        st.markdown(section_header("Buyer Nationality Intelligence"), unsafe_allow_html=True)
        try:
            nat = api.get_nationality_demand(top_n=15)
            data = nat.get("data", [])
            year = nat.get("year", 2024)
            if data:
                df_nat = pd.DataFrame(data)
                col1, col2 = st.columns(2)
                with col1:
                    fig = bar_chart(df_nat["nationality"].tolist(),
                                    df_nat["transactions_curr"].tolist(),
                                    title=f"Transactions by Nationality ({year})",
                                    horizontal=True, height=420, color=C_INDIGO)
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    colors = ["#10b981" if x >= 0 else "#ef4444" for x in df_nat["yoy_change_pct"]]
                    fig = go.Figure(go.Bar(
                        x=df_nat["yoy_change_pct"], y=df_nat["nationality"],
                        orientation="h", marker_color=colors,
                        text=[f"{x:+.1f}%" for x in df_nat["yoy_change_pct"]],
                        textposition="outside",
                    ))
                    fig.update_layout(**themed(
                                       height=420, title="YoY Change by Nationality",
                                       xaxis_title="Change %", showlegend=False))
                    st.plotly_chart(fig, use_container_width=True)

                # Preferences
                prefs = api.get_property_preferences()
                st.markdown(section_header("Market-Wide Preferences"), unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                c1.metric("Off-Plan Share", f"{prefs.get('off_plan_share', 0):.1f}%")
                c2.metric("Avg Transaction", f"AED {prefs.get('avg_transaction_value', 0):,.0f}")
                c3.metric("Median Transaction", f"AED {prefs.get('median_transaction_value', 0):,.0f}")

                col1, col2 = st.columns(2)
                with col1:
                    type_pref = prefs.get("by_type", {})
                    if type_pref:
                        fig = pie_chart(list(type_pref.keys()), list(type_pref.values()),
                                        title="Demand by Property Type", height=300)
                        st.plotly_chart(fig, use_container_width=True)
                with col2:
                    bed_pref = prefs.get("by_bedrooms", {})
                    if bed_pref:
                        fig = pie_chart(list(bed_pref.keys()), list(bed_pref.values()),
                                        title="Demand by Bedrooms", height=300)
                        st.plotly_chart(fig, use_container_width=True)
        except api.APIError as e:
            st.error(str(e))
