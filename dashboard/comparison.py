import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from database.connection import get_db_session
from database.queries import get_yoy_comparison, get_sales_by_category, get_sales_by_region
from utils.helpers import get_color_palette

def render_comparison(filters: dict):
    """
    Renders the Comparative Analytics tab.
    """
    session = get_db_session()
    colors = get_color_palette()
    
    try:
        st.markdown("<h2 class='gradient-text' style='margin-bottom: 20px;'>Comparative Analytics Dashboard</h2>", unsafe_allow_html=True)
        
        # 1. Fetch YoY Data
        df_yoy = get_yoy_comparison(session, filters)
        
        if not df_yoy.empty:
            st.markdown("### Year-over-Year (YoY) Overlap Analysis")
            
            # Map month numbers to short names for plotting
            months_map = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 
                          7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
            df_yoy['month_name'] = df_yoy['month'].map(months_map)
            df_yoy['year'] = df_yoy['year'].astype(str) # category line coloring
            
            # Reorder months
            months_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            
            target_metric = st.radio(
                "Compare Metric",
                options=["revenue", "sales"],
                format_func=lambda x: "Revenue (INR)" if x == "revenue" else "Sales Volume (Units)",
                horizontal=True
            )
            
            fig = px.line(
                df_yoy,
                x='month_name',
                y=target_metric,
                color='year',
                markers=True,
                category_orders={'month_name': months_order},
                color_discrete_sequence=colors['colors_seq'],
                labels={'month_name': 'Month', 'revenue': 'Revenue (INR)', 'sales': 'Sales Volume', 'year': 'Year'}
            )
            
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                margin=dict(l=0, r=0, t=10, b=0),
                height=350
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Print simple growth summary
            recent_years = df_yoy['year'].unique()
            if len(recent_years) >= 2:
                # Find sum for top two years
                top_years = sorted(list(recent_years), reverse=True)[:2]
                y1 = df_yoy[df_yoy['year'] == top_years[0]][target_metric].sum()
                y2 = df_yoy[df_yoy['year'] == top_years[1]][target_metric].sum()
                
                if y2 > 0:
                    pct_growth = ((y1 - y2) / y2) * 100
                    st.info(f"📊 **YoY Performance Summary:** Total {target_metric.replace('_', ' ').title()} in **{top_years[0]}** compared to **{top_years[1]}** is **{pct_growth:+.2f}%**.")
        else:
            st.warning("Insufficient time-series data for Year-over-Year comparison.")
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 2. Side-by-Side Category and Region Market Shares
        left_col, right_col = st.columns(2)
        
        with left_col:
            st.markdown("### Vehicle Category Growth comparison")
            cat_df = get_sales_by_category(session, filters)
            if not cat_df.empty:
                # Create a horizontal bar chart
                fig_cat = px.bar(
                    cat_df,
                    y='vehicle_category',
                    x='sales',
                    orientation='h',
                    color='vehicle_category',
                    color_discrete_sequence=colors['colors_seq']
                )
                fig_cat.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                    xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Units Sold"),
                    yaxis=dict(showgrid=False, title="", categoryorder='total ascending'),
                    showlegend=False,
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=300
                )
                st.plotly_chart(fig_cat, use_container_width=True)
            else:
                st.info("No category data.")
                
        with right_col:
            st.markdown("### Regional Growth Matrix")
            reg_df = get_sales_by_region(session, filters)
            if not reg_df.empty:
                # Group by region and plot a bar chart comparing revenue share
                fig_reg = px.bar(
                    reg_df,
                    x='emirate',
                    y='revenue',
                    color='emirate',
                    color_discrete_sequence=colors['colors_seq']
                )
                fig_reg.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                    xaxis=dict(showgrid=False, title=""),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Revenue (INR)"),
                    showlegend=False,
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=300
                )
                st.plotly_chart(fig_reg, use_container_width=True)
            else:
                st.info("No regional data.")
                
    except Exception as e:
        st.error(f"Error rendering Comparative Analytics: {e}")
    finally:
        session.close()
