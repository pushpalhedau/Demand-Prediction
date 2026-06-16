import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from database.connection import get_db_session
from database.queries import get_executive_kpis, get_monthly_revenue_trend, get_sales_by_category, get_sales_by_fuel_type, get_sales_by_region, get_uae_base_rate_kpi, get_top_brand_kpi
from database.connection import get_data_mode
from utils.helpers import render_kpi_card, get_color_palette

def render_overview(filters: dict):
    """
    Renders the Executive Overview tab.
    """
    session = get_db_session()
    colors = get_color_palette()
    
    try:
        # 1. Fetch KPIs
        kpis = get_executive_kpis(session, filters)
        
        st.markdown("<h2 class='gradient-text' style='margin-bottom: 25px;'>Executive Business Overview</h2>", unsafe_allow_html=True)
        
        # Display KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            sales_delta_str = "N/A"
            is_positive_sales = True
            if kpis['total_sales_delta'] is not None:
                is_positive_sales = kpis['total_sales_delta'] >= 0
                sales_delta_str = f"{kpis['total_sales_delta']:.2f}% YoY"
            render_kpi_card("Total Sales Volume", f"{kpis['total_sales']:,} units", delta=sales_delta_str, is_positive=is_positive_sales)
        with col2:
            revenue_delta_str = "N/A"
            is_positive_revenue = True
            if kpis['total_revenue_delta'] is not None:
                is_positive_revenue = kpis['total_revenue_delta'] >= 0
                revenue_delta_str = f"{kpis['total_revenue_delta']:.2f}% YoY"
            render_kpi_card("Total Revenue", f"AED {kpis['total_revenue'] / 1_000_000:.2f}M", delta=revenue_delta_str, is_positive=is_positive_revenue)
        with col3:
            if get_data_mode() == "real":
                base_rate_kpi = get_uae_base_rate_kpi(session, filters)
                rate_delta_str = "N/A"
                is_positive_rate = True
                if base_rate_kpi['delta'] is not None:
                    bps = round(base_rate_kpi['delta'] * 100)
                    sign = "+" if bps > 0 else ""
                    rate_delta_str = f"{sign}{bps} bps YoY"
                    is_positive_rate = bps <= 0  # lower rate = cheaper financing = positive
                render_kpi_card("UAE Base Rate (CBUAE)", f"{base_rate_kpi['rate']:.2f}%", delta=rate_delta_str, is_positive=is_positive_rate)
            else:
                discount_delta_str = "N/A"
                is_positive_discount = False
                if kpis['avg_discount_delta'] is not None:
                    sign = "+" if kpis['avg_discount_delta'] > 0 else ""
                    discount_delta_str = f"{sign}{kpis['avg_discount_delta']:.2f}% discount {'increase' if kpis['avg_discount_delta'] > 0 else 'decrease'}"
                    is_positive_discount = kpis['avg_discount_delta'] < 0
                render_kpi_card("Average Discount", f"{kpis['avg_discount']:.2f}%", delta=discount_delta_str, is_positive=is_positive_discount)
        with col4:
            if get_data_mode() == "real":
                brand_kpi = get_top_brand_kpi(session, filters)
                brand_delta_str = "N/A"
                is_positive_brand = True
                if brand_kpi['delta'] is not None:
                    sign = "+" if brand_kpi['delta'] > 0 else ""
                    brand_delta_str = f"{sign}{brand_kpi['delta']:.1f}pp share YoY"
                    is_positive_brand = brand_kpi['delta'] >= 0
                render_kpi_card(f"#1 Brand — {brand_kpi['brand']}", f"{brand_kpi['share']:.1f}% market share", delta=brand_delta_str, is_positive=is_positive_brand)
            else:
                lead_close_delta_str = "N/A"
                is_positive_lead_close = True
                if kpis['avg_lead_close_delta'] is not None:
                    sign = "+" if kpis['avg_lead_close_delta'] > 0 else ""
                    lead_close_delta_str = f"{abs(kpis['avg_lead_close_delta']):.0f} days {'faster' if kpis['avg_lead_close_delta'] > 0 else 'slower'}"
                    is_positive_lead_close = kpis['avg_lead_close_delta'] >= 0
                render_kpi_card("Avg Closing Velocity", f"{kpis['avg_lead_close']:.1f} Days", delta=lead_close_delta_str, is_positive=is_positive_lead_close)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 2. Main Revenue Trend Chart
        st.markdown("### Revenue & Sales Growth Trend")
        trend_df = get_monthly_revenue_trend(session, filters)
        
        if not trend_df.empty:
            fig = go.Figure()
            # Revenue line
            fig.add_trace(go.Scatter(
                x=trend_df['date'], 
                y=trend_df['revenue'],
                name='Revenue (AED)',
                line=dict(color=colors['primary'], width=3.5),
                mode='lines+markers',
                marker=dict(size=8, color=colors['secondary']),
                hovertemplate='Date: %{x|%B %Y}<br>Revenue: AED %{y:,.0f}'
            ))
            
            # Sales bars on secondary Y axis
            fig.add_trace(go.Bar(
                x=trend_df['date'], 
                y=trend_df['sales'],
                name='Sales (Units)',
                marker_color='rgba(6, 182, 212, 0.2)',
                marker_line_color=colors['secondary'],
                marker_line_width=1.5,
                yaxis='y2',
                hovertemplate='Date: %{x|%B %Y}<br>Units: %{y:,}'
            ))
            
            # Layout
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                hovermode='x unified',
                xaxis=dict(
                    showgrid=True, 
                    gridcolor='rgba(255,255,255,0.05)',
                    title=""
                ),
                yaxis=dict(
                    title=dict(text="Monthly Revenue (AED)", font=dict(color=colors['primary'])),
                    showgrid=True, 
                    gridcolor='rgba(255,255,255,0.05)',
                    tickfont=dict(color=colors['primary'])
                ),
                yaxis2=dict(
                    title=dict(text="Units Sold", font=dict(color=colors['secondary'])),
                    overlaying='y', 
                    side='right',
                    tickfont=dict(color=colors['secondary'])
                ),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=0, r=0, t=10, b=0),
                height=380
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No time-series data available for the active filters.")
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 3. Two columns for breakdown charts
        left_col, right_col = st.columns(2)
        
        with left_col:
            st.markdown("### Vehicle Category Share")
            cat_df = get_sales_by_category(session, filters)
            if not cat_df.empty:
                fig = px.pie(
                    cat_df, 
                    values='revenue', 
                    names='vehicle_category', 
                    hole=0.45,
                    color_discrete_sequence=colors['colors_seq']
                )
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                    margin=dict(l=0, r=0, t=20, b=0),
                    height=300
                )
                fig.update_traces(
                    textposition='inside', 
                    textinfo='percent+label',
                    marker=dict(line=dict(color='#0b0f19', width=2))
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No category data available.")
                
        with right_col:
            st.markdown("### Fuel Type Distribution")
            fuel_df = get_sales_by_fuel_type(session, filters)
            if not fuel_df.empty:
                fig = px.bar(
                    fuel_df,
                    x='fuel_type',
                    y='sales',
                    color='fuel_type',
                    color_discrete_sequence=colors['colors_seq']
                )
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                    xaxis=dict(showgrid=False, title=""),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Units Sold"),
                    showlegend=False,
                    margin=dict(l=0, r=0, t=20, b=0),
                    height=300
                )
                st.plotly_chart(fig, use_container_width=True)
                if get_data_mode() == "real":
                    st.caption(
                        "**Electric** — Focus2move UAE market data (2023–2024 confirmed) · IEA Global EV Outlook 2025  |  "
                        "**Hybrid** — Calibrated to Toyota UAE electrified-sales reports + IEA total electrified (HEV = total electrified − BEV)  |  "
                        "**Petrol / Diesel** — Derived from OEM vehicle specifications and Focus2move confirmed model volumes"
                    )
            else:
                st.info("No fuel data available.")
                
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 4. Regional distribution
        st.markdown("### Regional Sales Analytics")
        reg_df = get_sales_by_region(session, filters)
        if not reg_df.empty:
            fig = px.bar(
                reg_df, 
                x='emirate', 
                y='revenue', 
                color='revenue',
                color_continuous_scale='Viridis',
                labels={'revenue': 'Revenue (AED)'}
            )
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Total Revenue"),
                margin=dict(l=0, r=0, t=20, b=0),
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No regional data available.")
            
    except Exception as e:
        st.error(f"Error rendering Overview Dashboard: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()
