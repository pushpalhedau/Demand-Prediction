import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from database.connection import get_db_session
from database.queries import get_customer_segments_data, get_state_growth_data
from ml_models.xgboost_model import predict_deal_probability, predict_india_demand_growth
from utils.helpers import get_color_palette, render_kpi_card

_SEGMENT_COLORS = {
    "EV Pioneer Markets": "#10b981",
    "High Growth Markets": "#6366f1",
    "Metro Premium Markets": "#f59e0b",
    "Diesel-Dominant States": "#ef4444",
    "Mass Market States": "#9ca3af",
}


def render_customers(filters: dict):
    """
    Renders Market Segment Intelligence (India) or Customer Intelligence (UAE legacy).
    """
    session = get_db_session()
    colors = get_color_palette()

    try:
        # Detect India vs UAE data
        state_df = get_state_growth_data(session, filters)
        use_india = not state_df.empty

        if use_india:
            _render_market_segments(state_df, filters, colors)
        else:
            _render_customers_legacy(session, filters, colors)

    except Exception as e:
        st.error(f"Error rendering Intelligence tab: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()


def _render_market_segments(state_df: pd.DataFrame, filters: dict, colors: dict):
    st.markdown("<h2 class='gradient-text' style='margin-bottom: 20px;'>Market Segment Intelligence</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#9ca3af;font-size:14px;margin-bottom:20px;'>State-level market clusters derived from VAHAN registration patterns.</p>", unsafe_allow_html=True)

    # ── Summary KPIs ────────────────────────────────────────────────────────
    total_states = len(state_df)
    ev_leaders = len(state_df[state_df.get('ev_share_pct', pd.Series(0)).gt(5)]) if 'ev_share_pct' in state_df.columns else 0
    avg_ev = state_df['ev_share_pct'].mean() if 'ev_share_pct' in state_df.columns else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("States Analysed", str(total_states), delta="VAHAN data", is_positive=True)
    with k2: render_kpi_card("Avg EV Share", f"{avg_ev:.2f}%", delta="Across all states", is_positive=avg_ev > 2)
    with k3: render_kpi_card("EV-Leading States", str(ev_leaders), delta="EV share > 5%", is_positive=ev_leaders > 0)
    with k4:
        top_state = state_df.loc[state_df['total_registrations'].idxmax(), 'state'] if not state_df.empty else "N/A"
        render_kpi_card("Highest Volume State", top_state, delta="Most registrations", is_positive=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Load segment labels (from DB or train on demand) ─────────────────
    try:
        from ml_models.customer_segmentation import train_market_segmentation
        result, err = train_market_segmentation()
        if result:
            state_df = result["states_df"]
        else:
            # Assign simple segments based on EV share if model not trained
            def _simple_segment(row):
                if row.get('ev_share_pct', 0) > 5: return "EV Pioneer Markets"
                if row.get('total_registrations', 0) > state_df['total_registrations'].quantile(0.75): return "Metro Premium Markets"
                if row.get('dominant_fuel', '') == 'Diesel': return "Diesel-Dominant States"
                return "Mass Market States"
            state_df['market_segment'] = state_df.apply(_simple_segment, axis=1)
    except Exception:
        state_df['market_segment'] = "Mass Market States"

    seg_col = 'market_segment' if 'market_segment' in state_df.columns else None

    # ── Scatter: EV share vs Total Registrations, colour = segment ────────
    st.markdown("### State Market Cluster Map (EV Share vs Volume)")
    if 'ev_share_pct' in state_df.columns and 'total_registrations' in state_df.columns:
        scatter_df = state_df[state_df['state'] != 'All India'].copy()
        color_arg = seg_col if seg_col else 'total_registrations'
        color_map = _SEGMENT_COLORS if seg_col else None

        fig = px.scatter(
            scatter_df, x='total_registrations', y='ev_share_pct',
            color=color_arg, text='state',
            color_discrete_map=color_map,
            hover_data={'total_registrations': True, 'ev_share_pct': True, 'dominant_fuel': True, 'top_maker': True},
            labels={'total_registrations': 'Total Registrations', 'ev_share_pct': 'EV Share (%)'},
        )
        fig.update_traces(textposition='top center', textfont_size=9, marker_size=12)
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
            xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title='EV Share (%)'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=20, b=0), height=420,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Segment summary table ─────────────────────────────────────────────
    st.markdown("### State Market Segments")
    if seg_col:
        seg_summary = (
            state_df.groupby(seg_col)
            .agg(
                num_states=('state', 'count'),
                avg_ev_share=('ev_share_pct', 'mean'),
                total_registrations=('total_registrations', 'sum'),
            )
            .reset_index()
            .rename(columns={seg_col: 'Segment', 'num_states': 'States', 'avg_ev_share': 'Avg EV Share %', 'total_registrations': 'Total Registrations'})
        )
        seg_summary['Avg EV Share %'] = seg_summary['Avg EV Share %'].round(2)
        seg_summary['Total Registrations'] = seg_summary['Total Registrations'].apply(lambda x: f"{x:,}")
        st.dataframe(seg_summary, use_container_width=True, hide_index=True)

    # ── Demand Growth Predictor ───────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Regional Demand Growth Predictor")
    st.markdown("<p style='color:#9ca3af;font-size:13px;'>Predict whether a state × vehicle class will see >10% YoY growth.</p>", unsafe_allow_html=True)

    p1, p2 = st.columns(2)
    with p1:
        pred_state = st.selectbox("Select State", options=sorted(state_df['state'].unique().tolist()), key="pred_state")
    with p2:
        pred_class = st.selectbox("Select Vehicle Class", options=["Motor Car", "Motor Cycle", "Three Wheeler", "Goods Vehicle", "Bus/Minibus"], key="pred_class")

    if st.button("Predict Growth", type="primary"):
        pred_result = predict_india_demand_growth(pred_state, pred_class, 2026)
        prob = pred_result.get("growth_probability", 0.5)
        verdict = "HIGH GROWTH LIKELY" if prob > 0.6 else ("MODERATE" if prob > 0.4 else "LOW GROWTH")
        color = "#10b981" if prob > 0.6 else ("#f59e0b" if prob > 0.4 else "#ef4444")
        st.markdown(
            f'<div style="background:rgba(17,24,39,0.7);border:1px solid {color}44;border-radius:14px;padding:20px;margin-top:12px;">'
            f'<div style="color:{color};font-size:18px;font-weight:700;">{verdict}</div>'
            f'<div style="color:#f3f4f6;font-size:28px;font-weight:800;margin:8px 0;">{prob:.1%}</div>'
            f'<div style="color:#9ca3af;font-size:13px;">Probability of >10% YoY growth for {pred_class} in {pred_state}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        fi = pred_result.get("feature_importance", {})
        if fi:
            fi_df = pd.DataFrame(list(fi.items()), columns=['Feature', 'Importance']).sort_values('Importance', ascending=True)
            fig_fi = go.Figure(go.Bar(x=fi_df['Importance'], y=fi_df['Feature'], orientation='h',
                                      marker_color='#6366f1'))
            fig_fi.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title='Importance'),
                yaxis=dict(showgrid=False), margin=dict(l=0, r=0, t=10, b=0), height=260,
            )
            st.plotly_chart(fig_fi, use_container_width=True)


def _render_customers_legacy(session, filters: dict, colors: dict):
    """Original UAE Customer Intelligence rendering (kept for fallback)."""
    st.markdown("<h2 class='gradient-text' style='margin-bottom: 20px;'>Customer Intelligence & Lead Optimization</h2>", unsafe_allow_html=True)

    # 1. Fetch Customer Segmentation data
    df_cust = get_customer_segments_data(session)

    if df_cust.empty:
        st.warning("No customer records found. Please seed the database first.")
        return

    # Create tab sub-sections
    tab1, tab2 = st.tabs(["Customer Segmentation (KMeans)", "Lead Close Score (XGBoost)"])
        
    with tab1:
        st.markdown("### KMeans Clustering Analysis")
        seg_dist = df_cust['customer_segment'].value_counts().reset_index()
        seg_dist.columns = ['customer_segment', 'count']
        sub_col1, sub_col2 = st.columns([2, 1])
        with sub_col2:
            st.markdown("#### Segment Distribution")
            fig_pie = px.pie(seg_dist, values='count', names='customer_segment', hole=0.4,
                             color_discrete_sequence=colors['colors_seq'])
            fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                                  font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                                  margin=dict(l=0, r=0, t=10, b=0), height=280)
            st.plotly_chart(fig_pie, use_container_width=True)
        with sub_col1:
            st.markdown("#### Segment Characteristic Analysis")
            metrics_map = {
                'loyalty_score': 'Loyalty Score', 'credit_score': 'Credit Score',
                'age': 'Average Age', 'number_of_past_purchases': 'Past Purchases',
                'estimated_monthly_income_aed': 'Monthly Income (AED)', 'churn_risk_score': 'Churn Risk',
            }
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                sel_metrics = st.multiselect("Select Metrics", options=list(metrics_map.keys()),
                                             default=['loyalty_score', 'credit_score'],
                                             format_func=lambda x: metrics_map[x])
            with f_col2:
                sel_segments = st.multiselect("Filter Segments", options=df_cust['customer_segment'].unique(),
                                              default=list(df_cust['customer_segment'].unique()))
            if sel_metrics and sel_segments:
                agg_df = df_cust[df_cust['customer_segment'].isin(sel_segments)].groupby('customer_segment')[sel_metrics].mean().reset_index()
                melted_df = agg_df.melt(id_vars='customer_segment', var_name='Metric', value_name='Value')
                melted_df['Metric Name'] = melted_df['Metric'].map(metrics_map)
                fig_bar = px.bar(melted_df, x='customer_segment', y='Value', color='Metric Name',
                                 barmode='group', color_discrete_sequence=colors['colors_seq'],
                                 labels={'Value': 'Average Value', 'customer_segment': 'Segment'})
                fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                      font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                                      xaxis=dict(showgrid=False),
                                      yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                      margin=dict(l=0, r=0, t=10, b=0), height=350)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Select metrics and segments to visualize.")

        st.markdown("### Age vs Churn Risk Profile")
        sampled_df = df_cust.sample(min(2000, len(df_cust)), random_state=42)
        fig_bubble = px.scatter(sampled_df, x='age', y='churn_risk_score',
                                size='estimated_monthly_income_aed', color='customer_segment',
                                hover_data={'credit_score': True}, color_discrete_sequence=colors['colors_seq'])
        fig_bubble.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                 font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                                 xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Customer Age"),
                                 yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Churn Probability"),
                                 margin=dict(l=0, r=0, t=10, b=0), height=300)
        st.plotly_chart(fig_bubble, use_container_width=True)

    with tab2:
        st.markdown("### Live Lead Conversion Prediction")
        form_col1, form_col2, form_col3 = st.columns(3)
        with form_col1:
            age = st.slider("Customer Age", 21, 75, 38)
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            occupation = st.selectbox("Occupation", ["Salaried", "Business Owner", "Self-Employed", "Government Employee"])
            income = st.number_input("Monthly Income (AED)", 2000, 200000, 25000, 1000)
        with form_col2:
            credit_score = st.slider("Credit Score", 400, 850, 710)
            loyalty_score = st.slider("Loyalty Rating", 0, 100, 65)
            vehicle_category = st.selectbox("Vehicle Category", ["SUV", "Sedan", "Hatchback", "Luxury", "EV", "Commercial"])
            fuel_type = st.selectbox("Fuel Type", ["Petrol", "Diesel", "CNG", "Electric", "Hybrid"])
        with form_col3:
            discount_pct = st.slider("Applied Discount (%)", 0.0, 25.0, 6.5, 0.5)
            financing_type = st.selectbox("Financing Type", ["Bank Loan", "Cash", "Dealer Finance", "Lease"])
            marketing_channel = st.selectbox("Lead Source", ["Referral", "Digital", "Showroom Walk-in", "Auto Expo", "TV"])
            base_price = st.number_input("Vehicle Base Price (INR)", 200000, 15000000, 1250000, 50000)

        if st.button("Evaluate Conversion Probability", type="primary"):
            results = predict_deal_probability({
                "age": age, "gender": gender, "occupation": occupation,
                "estimated_monthly_income_aed": income, "credit_score": credit_score,
                "loyalty_score": loyalty_score, "vehicle_category": vehicle_category,
                "fuel_type": fuel_type, "discount_pct": discount_pct,
                "financing_type": financing_type, "marketing_channel": marketing_channel,
                "base_price": base_price,
            })
            prob = results["close_probability"]
            explanations = results["explanations"]
            st.markdown("<br>", unsafe_allow_html=True)
            r_col1, r_col2 = st.columns([1, 2])
            with r_col1:
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number", value=prob * 100,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': "Closing Score", 'font': {'size': 20}},
                    gauge={'axis': {'range': [0, 100]}, 'bar': {'color': colors['primary']},
                           'bgcolor': "rgba(0,0,0,0)",
                           'steps': [{'range': [0, 40], 'color': 'rgba(239,68,68,0.2)'},
                                     {'range': [40, 75], 'color': 'rgba(245,158,11,0.2)'},
                                     {'range': [75, 100], 'color': 'rgba(16,185,129,0.2)'}]}
                ))
                fig_gauge.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                                        font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                                        margin=dict(l=20, r=20, t=40, b=20), height=250)
                st.plotly_chart(fig_gauge, use_container_width=True)
            with r_col2:
                st.markdown("#### Feature Attributions")
                if explanations:
                    exp_df = pd.DataFrame(explanations)
                    exp_df['feature_clean'] = exp_df['feature'].apply(lambda x: x.replace('_', ' ').title())
                    fig_shap = px.bar(exp_df, x='score', y='feature_clean', color='direction',
                                     color_discrete_map={'positive': colors.get('success', '#10b981'), 'negative': colors.get('danger', '#ef4444')},
                                     orientation='h')
                    fig_shap.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                           font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                                           xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                                           yaxis=dict(showgrid=False), margin=dict(l=0, r=0, t=10, b=0), height=250)
                    st.plotly_chart(fig_shap, use_container_width=True)
            if prob >= 0.75:
                st.success("High-Conversion Lead — fast-track the VIP showroom visit.")
            elif prob >= 0.4:
                st.warning("Moderate probability — consider a small additional discount or better financing terms.")
            else:
                st.error("Low conversion score — revisit vehicle category or budget fit.")
