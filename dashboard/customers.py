import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from database.connection import get_db_session
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
        
        # 1. Fetch Customer Segmentation data
        df_cust = get_customer_segments_data(session)
        
        if df_cust.empty:
            st.warning("No customer records found. Please seed the database first.")
            return
            
        # Create tab sub-sections
        tab1, tab2 = st.tabs(["👥 Customer Segmentation (KMeans)", "🎯 Lead Close Score (XGBoost + Explainable AI)"])
        
        with tab1:
            st.markdown("### KMeans Clustering Analysis")
            
            # Segment distribution pie
            seg_dist = df_cust['customer_segment'].value_counts().reset_index()
            seg_dist.columns = ['customer_segment', 'count']
            
            sub_col1, sub_col2 = st.columns([2, 1])
            with sub_col2:
                st.markdown("#### Segment Distribution")
                fig_pie = px.pie(
                    seg_dist,
                    values='count',
                    names='customer_segment',
                    hole=0.4,
                    color_discrete_sequence=colors['colors_seq']
                )
                fig_pie.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=280
                )
                st.plotly_chart(fig_pie, use_container_width=True)
                
            with sub_col1:
                st.markdown("#### Segment Profile Scatter (Income vs Loyalty)")
                # Sample 2000 customers for high-performance plotting
                sampled_df = df_cust.sample(min(2000, len(df_cust)), random_state=42)
                fig_scat = px.scatter(
                    sampled_df,
                    x='estimated_annual_income',
                    y='loyalty_score',
                    color='customer_segment',
                    size='number_of_past_purchases',
                    hover_name='customer_id',
                    color_discrete_sequence=colors['colors_seq'],
                    labels={'estimated_annual_income': 'Annual Income (INR)', 'loyalty_score': 'Loyalty Index'}
                )
                fig_scat.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                    xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=300
                )
                st.plotly_chart(fig_scat, use_container_width=True)
                
            # Customer Age vs Spending Bubble Chart
            st.markdown("### Age vs Churn Risk Profile")
            fig_bubble = px.scatter(
                sampled_df,
                x='age',
                y='churn_risk_score',
                size='estimated_annual_income',
                color='customer_segment',
                hover_data={'credit_score': True},
                color_discrete_sequence=colors['colors_seq']
            )
            fig_bubble.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Customer Age"),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Churn Probability"),
                margin=dict(l=0, r=0, t=10, b=0),
                height=300
            )
            st.plotly_chart(fig_bubble, use_container_width=True)
            
        with tab2:
            st.markdown("### Live Lead Conversion Prediction")
            st.write("Input a lead profile below to calculate closing probability and explain features dynamically using SHAP.")
            
            # Interactive form parameters
            form_col1, form_col2, form_col3 = st.columns(3)
            
            with form_col1:
                age = st.slider("Customer Age", min_value=21, max_value=75, value=38)
                gender = st.selectbox("Gender", options=["Male", "Female", "Other"])
                occupation = st.selectbox("Occupation", options=["Salaried", "Business Owner", "Self-Employed", "Government Employee"])
                income = st.number_input("Annual Income (INR)", min_value=100000, max_value=10000000, value=950000, step=50000)
                
            with form_col2:
                credit_score = st.slider("Credit Score", min_value=400, max_value=850, value=710)
                loyalty_score = st.slider("Loyalty Rating", min_value=0, max_value=100, value=65)
                vehicle_category = st.selectbox("Vehicle Category", options=["SUV", "Sedan", "Hatchback", "Luxury", "EV", "Commercial"])
                fuel_type = st.selectbox("Fuel Type", options=["Petrol", "Diesel", "CNG", "Electric", "Hybrid"])
                
            with form_col3:
                discount_pct = st.slider("Applied Discount (%)", min_value=0.0, max_value=25.0, value=6.5, step=0.5)
                financing_type = st.selectbox("Financing Type", options=["Bank Loan", "Cash", "Dealer Finance", "Lease"])
                marketing_channel = st.selectbox("Lead Source Channel", options=["Referral", "Digital", "Showroom Walk-in", "Auto Expo", "TV"])
                base_price = st.number_input("Vehicle Base Price (INR)", min_value=200000, max_value=15000000, value=1250000, step=50000)
                
            if st.button("Evaluate Conversion Probability", type="primary"):
                # Call prediction pipeline
                lead_data = {
                    "age": age,
                    "gender": gender,
                    "occupation": occupation,
                    "estimated_annual_income": income,
                    "credit_score": credit_score,
                    "loyalty_score": loyalty_score,
                    "vehicle_category": vehicle_category,
                    "fuel_type": fuel_type,
                    "discount_pct": discount_pct,
                    "financing_type": financing_type,
                    "marketing_channel": marketing_channel,
                    "base_price": base_price
                }
                
                results = predict_deal_probability(lead_data)
                prob = results["close_probability"]
                explanations = results["explanations"]
                
                # Render results nicely
                st.markdown("<br>", unsafe_allow_html=True)
                r_col1, r_col2 = st.columns([1, 2])
                
                with r_col1:
                    # Circular Gauge for conversion
                    fig_gauge = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = prob * 100,
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        title = {'text': "Closing Score", 'font': {'size': 20}},
                        gauge = {
                            'axis': {'range': [0, 100], 'tickwidth': 1},
                            'bar': {'color': colors['primary']},
                            'bgcolor': "rgba(0,0,0,0)",
                            'borderwidth': 2,
                            'bordercolor': "gray",
                            'steps': [
                                {'range': [0, 40], 'color': 'rgba(239, 68, 68, 0.2)'},
                                {'range': [40, 75], 'color': 'rgba(245, 158, 11, 0.2)'},
                                {'range': [75, 100], 'color': 'rgba(16, 185, 129, 0.2)'}
                            ]
                        }
                    ))
                    fig_gauge.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                        margin=dict(l=20, r=20, t=40, b=20),
                        height=250
                    )
                    st.plotly_chart(fig_gauge, use_container_width=True)
                    
                with r_col2:
                    st.markdown("#### Feature Attributions (SHAP explainers)")
                    if explanations:
                        # Draw bar chart of explainers
                        exp_df = pd.DataFrame(explanations)
                        # Standardize name for display
                        exp_df['feature_clean'] = exp_df['feature'].apply(lambda x: x.replace('_', ' ').title())
                        
                        fig_shap = px.bar(
                            exp_df,
                            x='score',
                            y='feature_clean',
                            color='direction',
                            color_discrete_map={'positive': colors['success'], 'negative': colors['danger']},
                            orientation='h',
                            labels={'score': 'Contribution Strength', 'feature_clean': 'Attribute', 'direction': 'Influence'}
                        )
                        fig_shap.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                            xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                            yaxis=dict(showgrid=False),
                            margin=dict(l=0, r=0, t=10, b=0),
                            height=250
                        )
                        st.plotly_chart(fig_shap, use_container_width=True)
                    else:
                        st.info("SHAP attribution model not trained yet.")
                        
                # Provide recommendation based on scores
                if prob >= 0.75:
                    st.success("🎯 **Smart Action Recommendation:** This is a **High-Conversion Lead**. Fast track scheduling showroom VIP visit, offer finance approvals immediately, and secure downpayment within 48 hours.")
                elif prob >= 0.4:
                    st.warning("⚠️ **Smart Action Recommendation:** Moderate Close Probability. **Action:** Consider offering an additional **1.5% to 2% discount** or shifting financing to Bank Loan to increase closing prospects to over 80%.")
                else:
                    st.error("🚨 **Smart Action Recommendation:** High risk of lead drop. **Action:** Low conversion score. Target a different vehicle category that matches their budget profile, or contact customer to review downpayment capacity.")
                    
    except Exception as e:
        st.error(f"Error rendering Customer Intelligence: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()
