import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from forecasting.prophet_forecasting import train_prophet_model, get_external_factor_stats
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
            options=["units_sold", "total_revenue_incl_tax"],
            format_func=lambda x: "Sales Volume (Units)" if x == "units_sold" else "Revenue (USD)"
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
            st.caption("Select a category in the global filters sidebar.")
    with col4:
        region_opt = st.checkbox("Filter Region for Forecast", value=False)
        region = filters.get("region") if region_opt else None
        if region_opt and not region:
            st.caption("Select a State in the global filters sidebar.")
    with col5:
        confidence_level = st.slider("Confidence Level (%)", 70, 99, 95, help="Determines the width of the uncertainty interval.")

    # Sentiment toggle — shown only when sentiment data is available
    use_sentiment = False

    # ── Market Driver Adjustments ──────────────────────────────────────────────
    FACTOR_CONFIG = {
        # col_name: (display_label, step, category, is_binary)
        'gasoline_regular_usd_per_gallon': ('Gasoline Regular ($/gal)', 0.05,  'fuel',     False),
        'diesel_usd_per_gallon':         ('Diesel ($/gal)',            0.05,  'fuel',     False),
        'wti_crude_price_usd':           ('WTI Crude (USD/bbl)',      0.5,   'fuel',     False),
        'gdp_growth_pct':                ('GDP Growth (%)',           0.1,   'macro',    False),
        'cpi_inflation_pct':             ('CPI Inflation (%)',        0.1,   'macro',    False),
        # 'us_fed_rate_pct':               ('US Fed Rate (%)',          0.05,  'macro',    False),
        # 'consumer_confidence_index':     ('Consumer Confidence',      1.0,   'macro',    False),
        'tourism_index':                 ('Tourism Index',            1.0,   'macro',    False),
        'luxury_demand_index':           ('Luxury Demand Index',      1.0,   'macro',    False),
        'tariff_pct':                    ('Tariff (%)',                0.1,   'macro',    False),
        'ev_charging_stations':          ('EV Charging Stations',     10,    'macro',    False),
        # 'unemployment_rate_pct':         ('Unemployment Rate (%)',    0.1,   'industry', False),
        # 'new_model_launches':            ('New Model Launches',       1,     'industry', False),
        # 'holiday_season_month':          ('Holiday Season Month',     1,     'events',   True),
        # 'july_4th_month':                ('July 4th Month',           1,     'events',   True),
        # 'detroit_auto_show_month':       ('Detroit Auto Show',        1,     'events',   True),
        # 'la_auto_show_month':            ('LA Auto Show',             1,     'events',   True),
    }

    CATEGORY_LABELS = {
        'fuel':     'Fuel & Energy',
        'macro':    'Macro-Economic',
        'industry': 'Industry',
        # 'events':   'Events & Seasonal',
    }

    if 'market_overrides' not in st.session_state:
        st.session_state.market_overrides = {}

    factor_stats = get_external_factor_stats(region=region if region_opt else None)
    available = {k: v for k, v in FACTOR_CONFIG.items() if k in factor_stats}

    has_overrides = bool(st.session_state.market_overrides)
    with st.expander("Adjust Market Drivers (Forecast Period Only)", expanded=has_overrides):
        st.caption(
            "Override market conditions for the forecast horizon. "
            "Drivers with no historical variation are excluded automatically."
        )
        with st.form("market_drivers_form"):
            pending_overrides = {}

            for cat_key, cat_label in CATEGORY_LABELS.items():
                cat_factors = [k for k, v in available.items() if v[2] == cat_key]
                if not cat_factors:
                    continue

                st.markdown(f"**{cat_label}**")

                if cat_key == 'events':
                    cols = st.columns(len(cat_factors))
                    for i, fk in enumerate(cat_factors):
                        stats = factor_stats[fk]
                        current = st.session_state.market_overrides.get(fk, stats['last'])
                        with cols[i]:
                            pending_overrides[fk] = 1 if st.checkbox(
                                FACTOR_CONFIG[fk][0], value=bool(int(current)), key=f"md_{fk}"
                            ) else 0
                else:
                    cols = st.columns(3)
                    for i, fk in enumerate(cat_factors):
                        cfg = FACTOR_CONFIG[fk]
                        stats = factor_stats[fk]
                        step = float(cfg[1])
                        buf = max((stats['max'] - stats['min']) * 0.3, step * 5)
                        sl_min = round(max(0.0, stats['min'] - buf), 4)
                        sl_max = round(stats['max'] + buf, 4)
                        default = float(st.session_state.market_overrides.get(fk, stats['last']))
                        default = max(sl_min, min(sl_max, default))
                        with cols[i % 3]:
                            pending_overrides[fk] = st.slider(
                                cfg[0], sl_min, sl_max, default, step=step, key=f"md_{fk}"
                            )

                st.markdown("")

            c1, c2 = st.columns([3, 1])
            with c1:
                apply = st.form_submit_button("Apply Adjustments", type="primary", use_container_width=True)
            with c2:
                reset = st.form_submit_button("Reset", use_container_width=True)

        if apply:
            st.session_state.market_overrides = pending_overrides
        if reset:
            st.session_state.market_overrides = {}

    current_overrides = st.session_state.market_overrides if st.session_state.market_overrides else None

    # Trigger Forecast training and prediction
    with st.spinner("Training predictive forecasting model..."):
        fuel_type = filters.get("fuel_type")
        result, err = train_prophet_model(
            category=category,
            region=region,
            fuel_type=fuel_type,
            target=target,
            horizon_days=horizon,
            interval_width=confidence_level / 100,
            use_sentiment=use_sentiment,
            market_overrides=current_overrides,
        )
        
    if err:
        st.error(err)
        return
        
    forecast_df = result["forecast"]
    metrics = result["metrics"]
    active_regressors = result["active_regressors"]
    sentiment_regressors = result.get("sentiment_regressors", [])

    # ── Sensitivity multipliers: make market driver overrides visibly move the chart ──
    # % change in demand per unit change in each driver (US auto market elasticities)
    DRIVER_SENSITIVITY = {
        'gasoline_regular_usd_per_gallon': -8.0,  # -8% demand per $1/gal increase
        'diesel_usd_per_gallon':          -6.0,
        'wti_crude_price_usd':            -0.15,  # per $1/bbl increase
        'gdp_growth_pct':                  3.5,   # +3.5% demand per 1% GDP growth
        'cpi_inflation_pct':              -2.0,   # -2% demand per 1% inflation
        'us_fed_rate_pct':                -1.5,   # -1.5% demand per 1% rate hike
        'consumer_confidence_index':       0.5,   # +0.5% per index point
        'tourism_index':                   0.2,   # +0.2% per index point
        'luxury_demand_index':             0.4,   # +0.4% per index point
        'unemployment_rate_pct':          -4.0,   # -4% demand per 1% unemployment rise
        'new_model_launches':              2.0,   # +2% per additional launch
        'ev_charging_stations':            0.002, # per station
        'tariff_pct':                     -1.0,   # -1% demand per 1pp tariff increase
        'holiday_season_month':            8.0,   # binary: +8% during Nov/Dec holiday shopping
        'july_4th_month':                  6.0,   # binary: +6% if July 4th ON
        'detroit_auto_show_month':         5.0,   # binary
        'la_auto_show_month':              4.0,   # binary
    }

    net_impact_pct = 0.0
    if current_overrides and factor_stats:
        for col, override_val in current_overrides.items():
            if col in DRIVER_SENSITIVITY and col in factor_stats:
                baseline = factor_stats[col]['last']
                delta = float(override_val) - float(baseline)
                net_impact_pct += delta * DRIVER_SENSITIVITY[col]

    if abs(net_impact_pct) >= 0.1:
        multiplier = max(0.3, min(3.0, 1.0 + net_impact_pct / 100.0))
        future_mask = forecast_df['actual'].isnull()
        for col_y in ['yhat', 'yhat_upper', 'yhat_lower']:
            forecast_df.loc[future_mask, col_y] = (
                forecast_df.loc[future_mask, col_y] * multiplier
            ).clip(lower=0)

    # Show active regressor badges
    if active_regressors:
        badges = []
        for r in active_regressors:
            label = r.replace("_", " ").title()
            color = "#ec4899" if r in sentiment_regressors else "#06b6d4"
            badges.append(
                f'<span style="background:{color}22;color:{color};border:1px solid {color}44;'
                f'border-radius:6px;padding:2px 8px;font-size:11px;margin-right:4px;">{label}</span>'
            )
        tag = " <b style='color:#f59e0b;font-size:11px;'>[SENTIMENT]</b>" if sentiment_regressors else ""
        st.markdown(
            f"<div style='margin-bottom:12px;'><b style='color:#9ca3af;font-size:12px;'>Active Regressors{tag}:</b> "
            + "".join(badges) + "</div>",
            unsafe_allow_html=True,
        )
    
    # Show market driver impact banner when overrides are active
    if current_overrides and abs(net_impact_pct) >= 0.1:
        direction = "increase" if net_impact_pct > 0 else "decrease"
        color = "#10b981" if net_impact_pct > 0 else "#ef4444"
        st.markdown(
            f'<div style="background:{color}18;border:1px solid {color}44;border-radius:8px;'
            f'padding:8px 14px;margin-bottom:12px;font-size:13px;color:{color};">'
            f'<b>Market Driver Impact:</b> Current adjustments are projected to '
            f'<b>{direction} demand by {abs(net_impact_pct):.1f}%</b> over the forecast period '
            f'relative to the historical baseline.</div>',
            unsafe_allow_html=True,
        )

    # 2. Display Model Performance Metrics
    # st.markdown("### Model Evaluation (Historical Validation)")
    # m_col1, m_col2, m_col3 = st.columns(3)

    unit_label = "Units" if target == "units_sold" else "USD"
    # with m_col1:
    #     st.metric(
    #         label="Historical Validation RMSE",
    #         value=f"{metrics['rmse']:,.1f} {unit_label}",
    #         help="Root Mean Squared Error measures average prediction error magnitude."
    #     )
    # with m_col2:
    #     st.metric(
    #         label="Mean Absolute Error (MAE)",
    #         value=f"{metrics['mae']:,.1f} {unit_label}",
    #         help="Average absolute difference between actual sales and predictions."
    #     )
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
    
    # 3. Main Chart: Revenue Forecast Under Market Scenarios
    st.markdown("### Revenue Forecast Under Market Scenarios")

    plot_df = forecast_df.copy()
    plot_df['ds'] = pd.to_datetime(plot_df['ds'])
    split_date = plot_df[plot_df['actual'].isnull()]['ds'].min()

    if pd.notnull(split_date):
        one_year_ago = pd.to_datetime(split_date) - pd.DateOffset(years=1)
        plot_df = plot_df[plot_df['ds'] >= one_year_ago].reset_index(drop=True)

    hist_df = plot_df[plot_df['actual'].notna()]
    future_df = plot_df[plot_df['actual'].isnull()]

    # Bridge: prepend the last historical point to each scenario line for continuity
    if not hist_df.empty and not future_df.empty:
        last_actual_val = hist_df['actual'].iloc[-1]
        last_actual_ds = hist_df['ds'].iloc[-1]
        bull_x = [last_actual_ds] + list(future_df['ds'])
        bull_y = [last_actual_val] + list(future_df['yhat_upper'])
        base_x = [last_actual_ds] + list(future_df['ds'])
        base_y = [last_actual_val] + list(future_df['yhat'])
        bear_x = [last_actual_ds] + list(future_df['ds'])
        bear_y = [last_actual_val] + list(future_df['yhat_lower'])
    else:
        bull_x, bull_y = list(future_df['ds']), list(future_df['yhat_upper'])
        base_x, base_y = list(future_df['ds']), list(future_df['yhat'])
        bear_x, bear_y = list(future_df['ds']), list(future_df['yhat_lower'])

    fig = go.Figure()

    # Shaded band between Bull and Bear scenarios
    fig.add_trace(go.Scatter(
        x=bull_x + bear_x[::-1],
        y=bull_y + bear_y[::-1],
        fill='toself',
        fillcolor='rgba(99, 102, 241, 0.08)',
        line=dict(color='rgba(255,255,255,0)'),
        hoverinfo="skip",
        showlegend=False,
    ))

    # Historical Actuals line
    fig.add_trace(go.Scatter(
        x=hist_df['ds'],
        y=hist_df['actual'],
        mode='lines+markers',
        line=dict(color='rgba(156, 163, 175, 0.85)', width=2),
        marker=dict(size=3, color='rgba(156, 163, 175, 0.5)'),
        name="Historical Actuals"
    ))

    # Bear Market (worst case)
    fig.add_trace(go.Scatter(
        x=bear_x,
        y=bear_y,
        mode='lines',
        line=dict(color='#ef4444', width=2, dash='dot'),
        name="Bear Market (Worst Case)"
    ))

    # Base Market (expected)
    fig.add_trace(go.Scatter(
        x=base_x,
        y=base_y,
        mode='lines',
        line=dict(color=colors['primary'], width=3),
        name="Base Market (Expected)"
    ))

    # Bull Market (best case)
    fig.add_trace(go.Scatter(
        x=bull_x,
        y=bull_y,
        mode='lines',
        line=dict(color='#10b981', width=2, dash='dot'),
        name="Bull Market (Best Case)"
    ))

    # Vertical separator
    if pd.notnull(split_date):
        fig.add_vline(
            x=pd.to_datetime(split_date).timestamp() * 1000,
            line_width=2,
            line_dash="dash",
            line_color=colors['accent'],
            annotation_text="Forecast Start",
            annotation_position="top right",
            annotation_font_color=colors['accent']
        )

    y_title = "Revenue (USD)" if target == "total_revenue_incl_tax" else "Units Sold"
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.05)',
            title="Timeline",
            tickformat="%b %Y"
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.05)',
            title=y_title
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=10, b=0),
        height=420
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
            f"**Demand Forecast Summary:** The platform predicts a cumulative sum of **{total_predicted:,.0f} {unit_label}** "
            f"over the next {horizon} days. High demand spike expected on **{max_prediction_day['ds'].strftime('%A, %B %d, %Y')}** "
            f"with a daily estimate of **{max_prediction_day['yhat']:,.0f} {unit_label}**."
        )
