import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from database.connection import get_db_session
from database.queries import get_inventory_status
from utils.helpers import render_kpi_card, get_color_palette

def render_inventory(filters: dict):
    """
    Renders the Inventory Intelligence tab.
    """
    session = get_db_session()
    colors = get_color_palette()
    
    try:
        st.markdown("<h2 class='gradient-text' style='margin-bottom: 20px;'>Inventory & Stock Intelligence</h2>", unsafe_allow_html=True)
        
        # 1. Fetch Inventory Status
        df_inv = get_inventory_status(session, filters)
        
        if df_inv.empty:
            st.warning("No inventory status records available in database.")
            return
            
        # 2. Headline KPIs
        total_stock = df_inv['current_stock'].sum()
        total_transit = df_inv['transit_stock'].sum()
        total_holding = df_inv['estimated_holding_cost_aed'].sum()
        stockouts_cnt = df_inv[df_inv['current_stock'] == 0].shape[0]
        reorders_cnt = df_inv[df_inv['reorder_needed'] == True].shape[0]
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            render_kpi_card("Current Stock", f"{total_stock:,} Units", delta=f"{total_transit:,} in transit", is_positive=True)
        with col2:
            render_kpi_card("Active Stockouts", f"{stockouts_cnt} Models", delta="Needs restocking", is_positive=False)
        with col3:
            render_kpi_card("Reorder Triggers", f"{reorders_cnt} Alerts", delta="Below threshold", is_positive=False)
        with col4:
            render_kpi_card("Est. Holding Cost", f"AED {total_holding:,.0f}", delta="Holding cost/month", is_positive=False)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 3. Critical Restock Alerts Leaderboard
        st.markdown("### 🚨 Urgent Restock & Reorder Requirements")
        reorder_df = df_inv[df_inv['reorder_needed'] == True].copy()
        
        if not reorder_df.empty:
            reorder_df['Deficit'] = reorder_df['reorder_point'] - reorder_df['current_stock']
            reorder_df['Urgency Score'] = (reorder_df['stockout_risk_score'] * 100).apply(lambda x: f"{x:.1f}%")
            reorder_df.rename(columns={
                'brand': 'Brand',
                'model': 'Model',
                'emirate': 'Emirate',
                'current_stock': 'Current Stock',
                'reorder_point': 'Reorder Point',
                'days_in_stock': 'Days in Stock'
            }, inplace=True)
            
            st.dataframe(
                reorder_df[['Brand', 'Model', 'Emirate', 'Current Stock', 'Reorder Point', 'Deficit', 'Urgency Score', 'Days in Stock']]
                .sort_values(by='Urgency Score', ascending=False)
                .head(10),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("✅ All stock levels are currently healthy! No active reorder alerts.")
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 4. Charts: Demand vs Stock Level by Category
        st.markdown("### Stock Level vs 30-Day Predicted Demand by Category")
        
        # Group by category
        cat_group = df_inv.groupby('vehicle_category')[['current_stock', 'demand_forecast_30d']].sum().reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=cat_group['vehicle_category'],
            y=cat_group['current_stock'],
            name='Current Stock Level',
            marker_color=colors['primary']
        ))
        fig.add_trace(go.Bar(
            x=cat_group['vehicle_category'],
            y=cat_group['demand_forecast_30d'],
            name='Predicted 30D Demand',
            marker_color='rgba(6, 182, 212, 0.4)',
            marker_line_color=colors['secondary'],
            marker_line_width=1.5
        ))
        
        fig.update_layout(
            barmode='group',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
            xaxis=dict(showgrid=False, title=""),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Units"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=10, b=0),
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 5. Slow-moving and Warehouse Distribution Subplots
        sub_col1, sub_col2 = st.columns(2)
        
        with sub_col1:
            st.markdown("### Slow-Moving Inventory (Longest in Lot)")
            slow_df = df_inv[df_inv['current_stock'] > 0].sort_values(by='days_in_stock', ascending=False).head(8)
            if not slow_df.empty:
                slow_df['Model Label'] = slow_df['brand'] + " " + slow_df['model'] + " (" + slow_df['emirate'] + ")"
                fig_slow = px.bar(
                    slow_df,
                    y='Model Label',
                    x='days_in_stock',
                    orientation='h',
                    color='days_in_stock',
                    color_continuous_scale='Oranges',
                    labels={'days_in_stock': 'Avg Days in Lot', 'Model Label': ''}
                )
                fig_slow.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                    xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                    yaxis=dict(showgrid=False),
                    coloraxis_showscale=False,
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=280
                )
                st.plotly_chart(fig_slow, use_container_width=True)
            else:
                st.info("No slow-moving inventory data.")
                
        with sub_col2:
            st.markdown("### Warehouse Stock Allocation")
            wh_df = df_inv.groupby('warehouse_zone')['current_stock'].sum().reset_index()
            if not wh_df.empty:
                fig_wh = px.pie(
                    wh_df,
                    values='current_stock',
                    names='warehouse_zone',
                    hole=0.4,
                    color_discrete_sequence=colors['colors_seq']
                )
                fig_wh.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=280
                )
                st.plotly_chart(fig_wh, use_container_width=True)
            else:
                st.info("No warehouse data.")
                
    except Exception as e:
        st.error(f"Error rendering Inventory Intelligence: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()
