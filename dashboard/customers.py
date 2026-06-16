import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from database.connection import get_db_session, get_data_mode
from database.queries import get_customer_segments_data
from ml_models.xgboost_model import predict_deal_probability
from utils.helpers import get_color_palette

def render_customers(filters: dict):
    """
    Renders the Customer Intelligence tab.
    """
    session = get_db_session()
    colors = get_color_palette()

    try:
        st.markdown("<h2 class='gradient-text' style='margin-bottom: 20px;'>Customer Intelligence & Lead Optimization</h2>", unsafe_allow_html=True)

        df_cust = get_customer_segments_data(session)

        if df_cust.empty:
            st.warning("No customer records found. Please seed the database first.")
            return

        is_real = get_data_mode() == "real"

        tab1, tab2 = st.tabs(["Customer Segmentation", "Lead Close Score"])

        with tab1:

            # ----------------------------------------------------------------
            # Section header
            # ----------------------------------------------------------------
            if is_real:
                st.markdown("### Nationality & Demographics Analysis")
            else:
                st.markdown("### Clustering Analysis")

            sub_col1, sub_col2 = st.columns([2, 1])

            # ----------------------------------------------------------------
            # Right column — pie chart
            # ----------------------------------------------------------------
            with sub_col2:
                if is_real:
                    # Nationality distribution — REAL (FCSC 2023 census)
                    st.markdown("#### Nationality Distribution")
                    nat_counts = df_cust["nationality"].value_counts()
                    top10      = nat_counts.head(10)
                    other_sum  = nat_counts.iloc[10:].sum()
                    if other_sum > 0:
                        top10["Other"] = other_sum
                    pie_df    = top10.reset_index()
                    pie_df.columns = ["label", "count"]
                    pie_name_col = "label"
                else:
                    # Synthetic segment distribution
                    st.markdown("#### Segment Distribution")
                    pie_df = df_cust["customer_segment"].value_counts().reset_index()
                    pie_df.columns = ["label", "count"]
                    pie_name_col = "label"

                fig_pie = px.pie(
                    pie_df,
                    values="count",
                    names=pie_name_col,
                    hole=0.4,
                    color_discrete_sequence=colors["colors_seq"]
                )
                fig_pie.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#f3f4f6", family="Plus Jakarta Sans"),
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=280
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            # ----------------------------------------------------------------
            # Left column — characteristic analysis bar chart
            # ----------------------------------------------------------------
            with sub_col1:
                if is_real:
                    st.markdown("#### Nationality Characteristic Analysis")
                    metrics_map = {
                        "estimated_monthly_income_aed": "Monthly Income (AED)",
                        "age":                          "Average Age",
                        "number_of_past_purchases":     "Past Purchases",
                    }
                    group_col       = "nationality"
                    group_label     = "Nationality"
                    default_metrics = ["estimated_monthly_income_aed", "number_of_past_purchases"]
                    # Default to top 8 nationalities to keep chart readable
                    top8_nations    = df_cust["nationality"].value_counts().head(8).index.tolist()
                    filter_options  = df_cust["nationality"].value_counts().index.tolist()
                    filter_label    = "Filter Nationalities"
                    default_filter  = top8_nations
                else:
                    st.markdown("#### Segment Characteristic Analysis")
                    metrics_map = {
                        "loyalty_score":               "Loyalty Score",
                        "credit_score":                "Credit Score",
                        "age":                         "Average Age",
                        "number_of_past_purchases":    "Past Purchases",
                        "estimated_monthly_income_aed":"Monthly Income (AED)",
                        "churn_risk_score":            "Churn Risk",
                    }
                    group_col      = "customer_segment"
                    group_label    = "Segment"
                    default_metrics= ["loyalty_score", "credit_score"]
                    filter_options = df_cust["customer_segment"].unique().tolist()
                    filter_label   = "Filter Segments"
                    default_filter = filter_options

                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    sel_metrics = st.multiselect(
                        "Select Metrics",
                        options=list(metrics_map.keys()),
                        default=default_metrics,
                        format_func=lambda x: metrics_map[x]
                    )
                with f_col2:
                    sel_groups = st.multiselect(
                        filter_label,
                        options=filter_options,
                        default=default_filter
                    )

                if sel_metrics and sel_groups:
                    agg_df = (
                        df_cust[df_cust[group_col].isin(sel_groups)]
                        .groupby(group_col)[sel_metrics]
                        .mean()
                        .reset_index()
                    )
                    melted_df = agg_df.melt(id_vars=group_col, var_name="Metric", value_name="Value")
                    melted_df["Metric Name"] = melted_df["Metric"].map(metrics_map)

                    fig_bar = px.bar(
                        melted_df,
                        x=group_col,
                        y="Value",
                        color="Metric Name",
                        barmode="group",
                        color_discrete_sequence=colors["colors_seq"],
                        labels={"Value": "Average Value", group_col: group_label}
                    )
                    fig_bar.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#f3f4f6", family="Plus Jakarta Sans"),
                        xaxis=dict(showgrid=False),
                        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        margin=dict(l=0, r=0, t=10, b=0),
                        height=350
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("Select metrics and groups to visualize the comparison.")

            # ----------------------------------------------------------------
            # Bottom scatter / bubble chart
            # ----------------------------------------------------------------
            sampled_df = df_cust.sample(min(2000, len(df_cust)), random_state=42).copy()

            if is_real:
                st.markdown("### Age vs Income Profile by Nationality")

                # Limit scatter legend to top 8 nationalities; rest → "Other"
                top8 = df_cust["nationality"].value_counts().head(8).index
                sampled_df["nationality_grp"] = sampled_df["nationality"].where(
                    sampled_df["nationality"].isin(top8), other="Other"
                )
                # Shift size by +1 so 0-purchase customers still show a small dot
                sampled_df["bubble_size"] = sampled_df["number_of_past_purchases"] + 1

                fig_bubble = px.scatter(
                    sampled_df,
                    x="age",
                    y="estimated_monthly_income_aed",
                    size="bubble_size",
                    color="nationality_grp",
                    hover_data={
                        "nationality":             True,
                        "number_of_past_purchases":True,
                        "bubble_size":             False,
                        "nationality_grp":         False,
                    },
                    color_discrete_sequence=colors["colors_seq"],
                    size_max=14
                )
                fig_bubble.update_traces(marker=dict(opacity=0.65))
                fig_bubble.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#f3f4f6", family="Plus Jakarta Sans"),
                    xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="Customer Age"),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="Monthly Income (AED)"),
                    legend_title_text="Nationality",
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=300
                )
            else:
                st.markdown("### Age vs Churn Risk Profile")
                fig_bubble = px.scatter(
                    sampled_df,
                    x="age",
                    y="churn_risk_score",
                    size="estimated_monthly_income_aed",
                    color="customer_segment",
                    hover_data={"credit_score": True},
                    color_discrete_sequence=colors["colors_seq"]
                )
                fig_bubble.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#f3f4f6", family="Plus Jakarta Sans"),
                    xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="Customer Age"),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="Churn Probability"),
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=300
                )

            st.plotly_chart(fig_bubble, use_container_width=True)

        # --------------------------------------------------------------------
        # Tab 2 — Lead Close Score (unchanged in both modes)
        # --------------------------------------------------------------------
        with tab2:
            st.markdown("### Live Lead Conversion Prediction")
            st.write("Input a lead profile below to calculate closing probability and explain features dynamically using SHAP.")

            form_col1, form_col2, form_col3 = st.columns(3)

            with form_col1:
                age        = st.slider("Customer Age", min_value=21, max_value=75, value=38)
                gender     = st.selectbox("Gender", options=["Male", "Female", "Other"])
                occupation = st.selectbox("Occupation", options=["Salaried", "Business Owner", "Self-Employed", "Government Employee"])
                income     = st.number_input("Monthly Income (AED)", min_value=2000, max_value=200000, value=25000, step=1000)

            with form_col2:
                credit_score     = st.slider("Credit Score", min_value=400, max_value=850, value=710)
                loyalty_score    = st.slider("Loyalty Rating", min_value=0, max_value=100, value=65)
                vehicle_category = st.selectbox("Vehicle Category", options=["SUV", "Sedan", "Hatchback", "Luxury", "EV", "Commercial"])
                fuel_type        = st.selectbox("Fuel Type", options=["Petrol", "Diesel", "CNG", "Electric", "Hybrid"])

            with form_col3:
                discount_pct      = st.slider("Applied Discount (%)", min_value=0.0, max_value=25.0, value=6.5, step=0.5)
                financing_type    = st.selectbox("Financing Type", options=["Bank Loan", "Cash", "Dealer Finance", "Lease"])
                marketing_channel = st.selectbox("Lead Source Channel", options=["Referral", "Digital", "Showroom Walk-in", "Auto Expo", "TV"])
                base_price        = st.number_input("Vehicle Base Price (INR)", min_value=200000, max_value=15000000, value=1250000, step=50000)

            if st.button("Evaluate Conversion Probability", type="primary"):
                lead_data = {
                    "age":                          age,
                    "gender":                       gender,
                    "occupation":                   occupation,
                    "estimated_monthly_income_aed": income,
                    "credit_score":                 credit_score,
                    "loyalty_score":                loyalty_score,
                    "vehicle_category":             vehicle_category,
                    "fuel_type":                    fuel_type,
                    "discount_pct":                 discount_pct,
                    "financing_type":               financing_type,
                    "marketing_channel":            marketing_channel,
                    "base_price":                   base_price
                }

                results      = predict_deal_probability(lead_data)
                prob         = results["close_probability"]
                explanations = results["explanations"]

                st.markdown("<br>", unsafe_allow_html=True)
                r_col1, r_col2 = st.columns([1, 2])

                with r_col1:
                    fig_gauge = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=prob * 100,
                        domain={"x": [0, 1], "y": [0, 1]},
                        title={"text": "Closing Score", "font": {"size": 20}},
                        gauge={
                            "axis":        {"range": [0, 100], "tickwidth": 1},
                            "bar":         {"color": colors["primary"]},
                            "bgcolor":     "rgba(0,0,0,0)",
                            "borderwidth": 2,
                            "bordercolor": "gray",
                            "steps": [
                                {"range": [0, 40],  "color": "rgba(239, 68, 68, 0.2)"},
                                {"range": [40, 75], "color": "rgba(245, 158, 11, 0.2)"},
                                {"range": [75, 100],"color": "rgba(16, 185, 129, 0.2)"},
                            ]
                        }
                    ))
                    fig_gauge.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#f3f4f6", family="Plus Jakarta Sans"),
                        margin=dict(l=20, r=20, t=40, b=20),
                        height=250
                    )
                    st.plotly_chart(fig_gauge, use_container_width=True)

                with r_col2:
                    st.markdown("#### Feature Attributions (SHAP explainers)")
                    if explanations:
                        exp_df = pd.DataFrame(explanations)
                        exp_df["feature_clean"] = exp_df["feature"].apply(lambda x: x.replace("_", " ").title())
                        fig_shap = px.bar(
                            exp_df,
                            x="score",
                            y="feature_clean",
                            color="direction",
                            color_discrete_map={"positive": colors["success"], "negative": colors["danger"]},
                            orientation="h",
                            labels={"score": "Contribution Strength", "feature_clean": "Attribute", "direction": "Influence"}
                        )
                        fig_shap.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#f3f4f6", family="Plus Jakarta Sans"),
                            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                            yaxis=dict(showgrid=False),
                            margin=dict(l=0, r=0, t=10, b=0),
                            height=250
                        )
                        st.plotly_chart(fig_shap, use_container_width=True)
                    else:
                        st.info("SHAP attribution model not trained yet.")

                if prob >= 0.75:
                    st.success("**Smart Action Recommendation:** This is a **High-Conversion Lead**. Fast track scheduling showroom VIP visit, offer finance approvals immediately, and secure downpayment within 48 hours.")
                elif prob >= 0.4:
                    st.warning("**Smart Action Recommendation:** Moderate Close Probability. **Action:** Consider offering an additional **1.5% to 2% discount** or shifting financing to Bank Loan to increase closing prospects to over 80%.")
                else:
                    st.error("**Smart Action Recommendation:** High risk of lead drop. **Action:** Low conversion score. Target a different vehicle category that matches their budget profile, or contact customer to review downpayment capacity.")

    except Exception as e:
        st.error(f"Error rendering Customer Intelligence: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()
