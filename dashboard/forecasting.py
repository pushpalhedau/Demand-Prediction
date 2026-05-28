import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from forecasting.prophet_forecasting import train_prophet_model
from utils.helpers import render_kpi_card, get_color_palette

def render_forecasting(filters: dict):
    """
    Renders the Prophet Forecasting Tab.
    """
    colors = get_color_palette()
    st.markdown("<h2 class='gradient-text' style='margin-bottom: 20px;'>Powered Demand Forecasting</h2>", unsafe_allow_html=True)
    
    # 1. Inputs for Forecasting
    st.markdown("### Forecast Configurations")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        target = st.selectbox(
            "Forecast Target",
            options=["units_sold", "total_revenue_incl_vat"],
            format_func=lambda x: "Sales Volume (Units)" if x == "units_sold" else "Revenue (AED)"
        )
    with col2:
        horizon = st.selectbox(
            "Forecast Horizon",
            options=[30, 60, 90, 180, 365],
            format_func=lambda x: f"{x} Days ({'1 Month' if x==30 else '2 Months' if x==60 else '3 Months' if x==90 else '6 Months' if x==180 else '1 Year'})",
            index=2 # 90 days default
        )
    with col3:
        category_opt = st.checkbox("Filter Category for Forecast", value=False)
        category = filters.get("vehicle_category") if category_opt else None
        if category_opt and not category:
            st.caption("⚠️ Select a category in the global filters sidebar.")
    with col4:
        region_opt = st.checkbox("Filter Region for Forecast", value=False)
        region = filters.get("emirate") if region_opt else None
        if region_opt and not region:
            st.caption("⚠️ Select an Emirate in the global filters sidebar.")
    with col5:
        # Added dynamic confidence level selection
        confidence_level = st.slider("Confidence Level (%)", 70, 99, 95, help="Determines the width of the uncertainty interval.")
            
    # Trigger Forecast training and prediction
    with st.spinner("Training predictive Prophet forecasting model..."):
        fuel_type = filters.get("fuel_type")
        result, err = train_prophet_model(
            category=category,
            region=region,
            fuel_type=fuel_type,
            target=target,
            horizon_days=horizon,
            interval_width=confidence_level / 100
        )
        
    if err:
        st.error(err)
        return
        
    forecast_df = result["forecast"]
    metrics = result["metrics"]
    active_regressors = result["active_regressors"]
    
    # 2. Display Model Performance Metrics
    st.markdown("### Model Evaluation (Historical Validation)")
    m_col1, m_col2, m_col3 = st.columns(3)
    
    unit_label = "Units" if target == "units_sold" else "AED"
    with m_col1:
        st.metric(
            label="Historical Validation RMSE", 
            value=f"{metrics['rmse']:,.1f} {unit_label}",
            help="Root Mean Squared Error measures average prediction error magnitude."
        )
    with m_col2:
        st.metric(
            label="Mean Absolute Error (MAE)", 
            value=f"{metrics['mae']:,.1f} {unit_label}",
            help="Average absolute difference between actual sales and predictions."
        )
    # with m_col3:
    #     st.metric(
    #         label="Average Forecast Accuracy", 
    #         value=f"{metrics['accuracy']:.2f}%",
    #         help="Percentage accuracy metric calculated based on mean absolute error relative to average sales."
    #     )
        
    # Active Regressors Alert
    # if active_regressors:
    #     st.info(f"💡 **Explainable Regressors Active:** Prophet model utilizes real-time correlations with economic inputs: *{', '.join(active_regressors).replace('_', ' ')}*.")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 3. Main Chart: Historical vs Forecast
    st.markdown("### Historical Sales vs Forecast Horizon")
    
    # Filter to show only the last 1 year of historical data plus the forecast for the main chart
    plot_df = forecast_df.copy()
    split_date = plot_df[plot_df['actual'].isnull()]['ds'].min()
    if pd.notnull(split_date):
        plot_df['ds'] = pd.to_datetime(plot_df['ds'])
        one_year_ago = pd.to_datetime(split_date) - pd.DateOffset(years=1)
        plot_df = plot_df[plot_df['ds'] >= one_year_ago].reset_index(drop=True)

    # We want to display actuals, forecast, and lower/upper bounds
    fig = go.Figure()
    
    # Shaded confidence interval band
    fig.add_trace(go.Scatter(
        x=pd.concat([plot_df['ds'], plot_df['ds'][::-1]]),
        y=pd.concat([plot_df['yhat_upper'], plot_df['yhat_lower'][::-1]]),
        fill='toself',
        fillcolor='rgba(99, 102, 241, 0.1)',
        line=dict(color='rgba(255,255,255,0)'),
        hoverinfo="skip",
        showlegend=True,
        name=f"{confidence_level}% Confidence Interval"
    ))
    
    # Forecast line
    fig.add_trace(go.Scatter(
        x=plot_df['ds'],
        y=plot_df['yhat'],
        mode='lines',
        line=dict(color=colors['primary'], width=3),
        name="Prophet Forecast"
    ))
    
    # Actuals scatter markers
    fig.add_trace(go.Scatter(
        x=plot_df['ds'],
        y=plot_df['actual'],
        mode='markers',
        marker=dict(color='rgba(6, 182, 212, 0.6)', size=5),
        name="Historical Actuals"
    ))
    
    # Vertical line separating historical and future
    split_date = plot_df[plot_df['actual'].isnull()]['ds'].min()
    if pd.notnull(split_date):
        fig.add_vline(
            x=pd.to_datetime(split_date).timestamp() * 1000, 
            line_width=2, 
            line_dash="dash", 
            line_color=colors['accent'],
            annotation_text="Forecast Horizon Start", 
            annotation_position="top right",
            annotation_font_color=colors['accent']
        )
        
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Timeline"),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title=f"Value ({unit_label})"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=10, b=0),
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 4. Seasonal Decomposition
    st.markdown("### Trend & Seasonality Decomposition")
    
    # We can plot Weekly or Yearly seasonality from the forecast_df
    # In Prophet, forecast has weekly, yearly columns
    s_col1, s_col2 = st.columns(2)
    
    with s_col1:
        if 'weekly' in forecast_df.columns:
            st.markdown("#### Weekly Seasonality Pattern")
            # Prophet forecast gives weekly effects daily, let's take average per day of week
            forecast_df['day_name'] = pd.to_datetime(forecast_df['ds']).dt.day_name()
            # Order days of week
            days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            weekly_pattern = forecast_df.groupby('day_name')['weekly'].mean().reindex(days_order).reset_index()
            
            fig_week = px.line(
                weekly_pattern, 
                x='day_name', 
                y='weekly',
                markers=True,
                color_discrete_sequence=[colors['secondary']]
            )
            fig_week.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Demand Impact Shift"),
                margin=dict(l=0, r=0, t=10, b=0),
                height=260
            )
            st.plotly_chart(fig_week, use_container_width=True)
        else:
            st.info("Weekly seasonality not active.")
            
    with s_col2:
        if 'yearly' in forecast_df.columns:
            st.markdown("#### Monthly / Yearly Seasonality Pattern")
            forecast_df['month_name'] = pd.to_datetime(forecast_df['ds']).dt.strftime('%b')
            months_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            yearly_pattern = forecast_df.groupby('month_name')['yearly'].mean().reindex(months_order).reset_index()
            
            fig_year = px.line(
                yearly_pattern, 
                x='month_name', 
                y='yearly',
                markers=True,
                color_discrete_sequence=[colors['accent']]
            )
            fig_year.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Demand Impact Shift"),
                margin=dict(l=0, r=0, t=10, b=0),
                height=260
            )
            st.plotly_chart(fig_year, use_container_width=True)
        else:
            st.info("Yearly seasonality not active.")
            
    # Print simple business insight based on prediction
    future_only = forecast_df[forecast_df['actual'].isnull()]
    if not future_only.empty:
        total_predicted = future_only['yhat'].sum()
        max_prediction_day = future_only.loc[future_only['yhat'].idxmax()]
        
        st.success(
            f"📈 **Demand Forecast Summary:** The platform predicts a cumulative sum of **{total_predicted:,.0f} {unit_label}** "
            f"over the next {horizon} days. High demand spike expected on **{max_prediction_day['ds'].strftime('%A, %B %d, %Y')}** "
            f"with a daily estimate of **{max_prediction_day['yhat']:,.0f} {unit_label}**."
        )
