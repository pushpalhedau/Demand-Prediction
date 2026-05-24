import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from database.connection import get_db_session
from database.queries import get_executive_kpis, get_monthly_revenue_trend, get_sales_by_category, get_sales_by_fuel_type, get_sales_by_region
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
            render_kpi_card("Total Sales Volume", f"{kpis['total_sales']:,} units", delta="12% YoY", is_positive=True)
        with col2:
            render_kpi_card("Total Revenue", f"₹{kpis['total_revenue'] / 10_000_000:.2f} Cr", delta="8.4% YoY", is_positive=True)
        with col3:
            render_kpi_card("Average Discount", f"{kpis['avg_discount']:.2f}%", delta="1.2% discount increase", is_positive=False)
        with col4:
            render_kpi_card("Avg Closing Velocity", f"{kpis['avg_lead_close']:.1f} Days", delta="4 days faster", is_positive=True)
            
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
                name='Revenue (INR)',
                line=dict(color=colors['primary'], width=3.5),
                mode='lines+markers',
                marker=dict(size=8, color=colors['secondary']),
                hovertemplate='Date: %{x|%B %Y}<br>Revenue: ₹%{y:,.0f}'
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
                    title=dict(text="Monthly Revenue (INR)", font=dict(color=colors['primary'])),
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
            else:
                st.info("No fuel data available.")
                
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 4. Regional distribution
        st.markdown("### Regional Sales Analytics")
        reg_df = get_sales_by_region(session, filters)
        if not reg_df.empty:
            fig = px.bar(
                reg_df, 
                x='region', 
                y='revenue', 
                color='revenue',
                color_continuous_scale='Viridis',
                labels={'revenue': 'Revenue (INR)'}
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
