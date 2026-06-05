import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from database.connection import get_db_session
from database.queries import get_buyer_segments_data, get_buyer_segment_summary, get_lead_conversion_data
from ml_models.customer_segmentation import train_buyer_segmentation, predict_buyer_segment
from ml_models.xgboost_model import train_xgboost_pipeline, predict_booking_probability
from utils.helpers import get_re_colors, plotly_dark_layout, section_header, fmt_aed


SEGMENT_COLORS = {
    "Portfolio Investor": "#f43f5e",
    "Upgrader": "#06b6d4",
    "Golden Visa Seeker": "#f59e0b",
    "First-Home Buyer": "#10b981",
    "End User": "#6366f1",
    "Rental Investor": "#0ea5e9",
}


def render_customers(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        KMeans buyer segmentation + XGBoost lead scoring — understand your buyer personas,
        predict booking conversion probability, and identify high-value leads.
    </p>""", unsafe_allow_html=True)

    tab_seg, tab_lead = st.tabs(["Buyer Segmentation", "Lead Scoring"])

    # ══ TAB 1: Buyer Segmentation ══════════════════════════
    with tab_seg:
        session = get_db_session()
        try:
            df_buyers = get_buyer_segments_data(session)
            df_seg_summary = get_buyer_segment_summary(session)
        finally:
            session.close()

        col_train, col_info = st.columns([1, 3])
        with col_train:
            if st.button("Train Segmentation Model", type="primary", use_container_width=True):
                with st.spinner("Running KMeans clustering..."):
                    result, err = train_buyer_segmentation(n_clusters=6)
                if err:
                    st.error(err)
                else:
                    st.success("Segmentation complete! Reload to see updated clusters.")

        with col_info:
            st.markdown("""<div class="insight-box">
                KMeans clusters buyers into 6 segments based on annual income (AED),
                past purchases, budget ceiling, loyalty score, Golden Visa intent and off-plan preference.
                Segments: <b>Portfolio Investor | Golden Visa Seeker | Upgrader |
                First-Home Buyer | Rental Investor | End User</b>
            </div>""", unsafe_allow_html=True)

        if not df_buyers.empty and "customer_segment" in df_buyers.columns:
            # ── KPI strip ─────────────────────────────────
            seg_counts = df_buyers["customer_segment"].value_counts()
            k_cols = st.columns(min(len(seg_counts), 6))
            for i, (seg, cnt) in enumerate(seg_counts.items()):
                with k_cols[i % 6]:
                    seg_color = SEGMENT_COLORS.get(seg, colors["primary"])
                    st.markdown(f"""<div class="kpi-card" style="border-top-color:{seg_color}">
                        <div class="kpi-title" style="color:{seg_color}">{seg}</div>
                        <div class="kpi-value">{cnt:,}</div>
                        <div class="kpi-delta neutral">{cnt/len(df_buyers)*100:.1f}% of buyers</div>
                    </div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── 2D scatter ───────────────────────────────
            col_scatter, col_profile = st.columns([3, 2])

            with col_scatter:
                section_header("Buyer Segment Scatter (Income vs Loyalty)")
                plot_df = df_buyers.dropna(subset=["estimated_annual_income_aed", "loyalty_score"]).copy()
                if not plot_df.empty:
                    sample = plot_df.sample(min(3000, len(plot_df)), random_state=42)
                    fig = go.Figure()
                    for seg in sample["customer_segment"].unique():
                        sub = sample[sample["customer_segment"] == seg]
                        fig.add_trace(go.Scatter(
                            x=sub["estimated_annual_income_aed"] / 1e3,
                            y=sub["loyalty_score"],
                            mode="markers",
                            name=seg,
                            marker=dict(
                                size=6, opacity=0.7,
                                color=SEGMENT_COLORS.get(seg, colors["primary"]),
                                line=dict(width=0),
                            ),
                        ))
                    layout = plotly_dark_layout("", 400)
                    layout["xaxis"]["title"] = "Annual Income (AED '000)"
                    layout["yaxis"]["title"] = "Loyalty Score"
                    layout["legend"] = dict(orientation="v", y=0.5, bgcolor="rgba(0,0,0,0)")
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

            with col_profile:
                section_header("Segment Distribution")
                if not df_seg_summary.empty:
                    fig = go.Figure(go.Pie(
                        labels=df_seg_summary["customer_segment"],
                        values=df_seg_summary["count"],
                        hole=0.52,
                        marker=dict(
                            colors=[SEGMENT_COLORS.get(s, colors["primary"])
                                    for s in df_seg_summary["customer_segment"]],
                            line=dict(color="#080d18", width=2),
                        ),
                        textinfo="percent",
                        textfont=dict(size=11),
                    ))
                    layout = plotly_dark_layout("", 400)
                    layout["legend"] = dict(
                        orientation="v", x=1.02, y=0.5,
                        bgcolor="rgba(0,0,0,0)", font=dict(size=10),
                    )
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

            # ── Segment profile table ────────────────────
            section_header("Segment Profile Benchmarks")
            if not df_seg_summary.empty:
                profile = df_seg_summary.copy()
                profile["avg_income"] = profile["avg_income"].apply(
                    lambda v: f"AED {v/1e3:.0f}K" if v else "—"
                )
                profile["avg_budget"] = profile["avg_budget"].apply(
                    lambda v: fmt_aed(v) if v else "—"
                )
                profile["avg_loyalty"] = profile["avg_loyalty"].apply(lambda v: f"{v:.1f}/100" if v else "—")
                profile["avg_churn_risk"] = profile["avg_churn_risk"].apply(
                    lambda v: f"{v:.0%}" if v else "—"
                )
                st.dataframe(
                    profile.rename(columns={
                        "customer_segment": "Segment",
                        "count": "Buyers",
                        "avg_income": "Avg Income",
                        "avg_budget": "Avg Budget",
                        "avg_loyalty": "Loyalty",
                        "avg_churn_risk": "Churn Risk",
                    })[["Segment", "Buyers", "Avg Income", "Avg Budget", "Loyalty", "Churn Risk"]],
                    use_container_width=True,
                    hide_index=True,
                )

            # ── Budget distribution by segment ───────────
            st.markdown("<br>", unsafe_allow_html=True)
            section_header("Budget Range by Segment (AED)")
            plot_df2 = df_buyers.dropna(subset=["budget_max_aed", "customer_segment"])
            if not plot_df2.empty:
                fig = go.Figure()
                for seg in plot_df2["customer_segment"].unique():
                    sub = plot_df2[plot_df2["customer_segment"] == seg]
                    fig.add_trace(go.Box(
                        x=sub["customer_segment"],
                        y=sub["budget_max_aed"] / 1e6,
                        name=seg,
                        marker_color=SEGMENT_COLORS.get(seg, colors["primary"]),
                        boxmean=True,
                        line=dict(width=1.5),
                    ))
                layout = plotly_dark_layout("", 360)
                layout["yaxis"]["title"] = "Max Budget (AED Millions)"
                layout["showlegend"] = False
                layout["xaxis"]["tickangle"] = -20
                fig.update_layout(**layout)
                st.plotly_chart(fig, use_container_width=True)

    # ══ TAB 2: Lead Scoring ════════════════════════════════
    with tab_lead:
        col_train2, col_info2 = st.columns([1, 3])
        with col_train2:
            if st.button("Train Lead Scoring Model", type="primary", use_container_width=True):
                with st.spinner("Training XGBoost booking conversion model..."):
                    result, err = train_xgboost_pipeline()
                if err:
                    st.error(err)
                else:
                    st.success(f"Model trained! Accuracy: {result['accuracy']:.1%}")
                    feat_df = result["feature_importance"].head(10)
                    section_header("Feature Importance")
                    fig = go.Figure(go.Bar(
                        x=feat_df["Importance"],
                        y=feat_df["Feature"],
                        orientation="h",
                        marker=dict(
                            color=feat_df["Importance"],
                            colorscale=[[0, "#1a3350"], [1, colors["gold"]]],
                            line=dict(width=0),
                        ),
                        text=[f"{v:.3f}" for v in feat_df["Importance"]],
                        textposition="outside",
                        textfont=dict(size=10, color="#94a3b8"),
                    ))
                    layout = plotly_dark_layout("", 340)
                    layout["xaxis"]["title"] = "Feature Importance"
                    layout["yaxis"]["autorange"] = "reversed"
                    layout["margin"]["l"] = 150
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

        with col_info2:
            st.markdown("""<div class="insight-box">
                XGBoost predicts <b>booking conversion probability</b> using buyer profile features:
                site visit, annual income (AED), property preferences, Golden Visa intent,
                expat status, off-plan preference, and marketing channel.
                <br><b>Top drivers:</b> Site Visit > Income > Buyer Type > Golden Visa Intent > Lead Source
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        section_header("Lead Conversion Probability Predictor")

        c1, c2, c3 = st.columns(3)
        with c1:
            age = st.slider("Age", 21, 75, 35, key="ls_age")
            income = st.number_input("Annual Income (AED)", 60000, 5000000, 300000, 50000, key="ls_income")
            loyalty = st.slider("Loyalty Score", 0, 100, 60, key="ls_loyalty")
        with c2:
            site_visit = st.toggle("Site Visit Taken", value=True, key="ls_visit")
            expat = st.toggle("Expat Status", value=True, key="ls_expat")
            golden_visa = st.toggle("Golden Visa Intent", value=False, key="ls_gv")
            off_plan = st.toggle("Off-Plan Preference", value=False, key="ls_offplan")
            mortgage = st.toggle("Mortgage Preferred", value=True, key="ls_mortgage")
        with c3:
            buyer_type = st.selectbox("Buyer Type", ["End User", "Investor", "Off-Plan Investor", "Portfolio Investor", "HNI"], key="ls_btype")
            prop_cat = st.selectbox("Property Category", ["Affordable", "Mid-Market", "Premium", "Luxury", "Ultra-Luxury"], key="ls_pcat")
            channel = st.selectbox("Lead Source", ["Property Finder", "Bayut", "Referral", "Digital", "Property Expo", "Walk-in", "WhatsApp", "Social Media"], key="ls_ch")
            city = st.selectbox("City", ["Dubai", "Abu Dhabi", "Sharjah", "Ras Al Khaimah", "Ajman", "Fujairah", "Umm Al Quwain"], key="ls_city")

        if st.button("Predict Booking Probability", type="primary", use_container_width=True):
            result = predict_booking_probability({
                "age": age,
                "estimated_annual_income_aed": income,
                "site_visit_taken": site_visit,
                "expat_status": expat,
                "golden_visa_intent": golden_visa,
                "off_plan_preference": off_plan,
                "mortgage_preferred": mortgage,
                "buyer_type": buyer_type,
                "property_category": prop_cat,
                "marketing_channel": channel,
                "city": city,
                "discount_pct": 2.0,
                "area_sqft": 1000.0,
                "lead_to_close_days": 30.0,
                "loyalty_score": float(loyalty),
            })

            prob = result["booking_probability"]
            explanations = result.get("explanations", [])

            p1, p2 = st.columns([1, 2])
            with p1:
                color = colors["success"] if prob > 0.65 else (colors["warning"] if prob > 0.40 else colors["danger"])
                label = "High Intent" if prob > 0.65 else ("Moderate Intent" if prob > 0.40 else "Low Intent")
                st.markdown(f"""
                <div class="kpi-card" style="text-align:center; border-top-color:{color}">
                    <div class="kpi-title">Booking Probability</div>
                    <div class="kpi-value" style="color:{color}; font-size:42px">{prob:.0%}</div>
                    <div class="kpi-delta" style="justify-content:center; color:{color}">{label}</div>
                </div>""", unsafe_allow_html=True)

            with p2:
                section_header("Key Conversion Drivers (SHAP)")
                if explanations:
                    for exp in explanations[:5]:
                        bar_color = colors["success"] if exp["direction"] == "positive" else colors["danger"]
                        pct = min(abs(exp["score"]) * 200, 100)
                        st.markdown(f"""
                        <div style="margin-bottom:10px">
                            <div style="font-size:12px; color:#94a3b8; margin-bottom:3px">{exp['description']}</div>
                            <div style="background:rgba(255,255,255,0.05); border-radius:4px; height:8px; overflow:hidden">
                                <div style="background:{bar_color}; width:{pct:.0f}%; height:100%; border-radius:4px; opacity:0.8"></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
