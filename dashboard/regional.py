import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from database.connection import get_db_session
from database.queries import get_dealer_performance_leaderboard
from utils.helpers import get_color_palette

def render_regional(filters: dict):
    """
    Renders the Regional Intelligence Tab.
    """
    session = get_db_session()
    colors = get_color_palette()
    
    try:
        st.markdown("<h2 class='gradient-text' style='margin-bottom: 20px;'>Regional Intelligence & Dealer Analytics</h2>", unsafe_allow_html=True)
        
        # 1. Fetch Dealer Performance Leaderboard
        df_dealers = get_dealer_performance_leaderboard(session, filters)
        
        if df_dealers.empty:
            st.warning("No regional dealer network data available for the active filters.")
            return
            
        # 2. Geo Bubble Map
        # Plot dealers on map using latitude/longitude if available
        st.markdown("### Interactive Dealer Sales Distribution Map")
        
        # Filter dealers with valid GPS coordinates
        gps_df = df_dealers[
            (df_dealers['units_sold'] > 0) & 
            (pd.notnull(df_dealers['latitude'])) & 
            (pd.notnull(df_dealers['longitude']))
        ]
        
        if not gps_df.empty:
            # We can use px.scatter_mapbox to display dealers in the region
            fig_map = px.scatter_mapbox(
                gps_df,
                lat="latitude",
                lon="longitude",
                size="units_sold",
                color="revenue",
                hover_name="dealer_name",
                hover_data={"city": True, "tier": True, "performance_score": True, "units_sold": True, "revenue": True},
                color_continuous_scale="Viridis",
                zoom=3.8,
                mapbox_style="open-street-map"
            )
            fig_map.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                margin=dict(l=0, r=0, t=0, b=0),
                height=450
            )
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            # Fallback to standard 3D bubble chart or simple bar chart if GPS coordinates are missing
            st.info("dealer network coordinates not mapped. Visualizing via regional bubble chart instead.")
            fig_bubble = px.scatter(
                df_dealers,
                x="performance_score",
                y="units_sold",
                size="revenue",
                color="tier",
                hover_name="dealer_name",
                color_discrete_sequence=colors['colors_seq']
            )
            fig_bubble.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Dealer Rating Index"),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Units Sold"),
                margin=dict(l=0, r=0, t=10, b=0),
                height=350
            )
            st.plotly_chart(fig_bubble, use_container_width=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 3. Sortable Leaderboard Table
        st.markdown("### Top Performing Dealer Leaderboard")
        
        # Format columns for displays
        disp_df = df_dealers.copy()
        disp_df['Total Revenue (INR)'] = disp_df['revenue'].apply(lambda x: f"₹{x:,.0f}")
        disp_df.rename(columns={
            'dealer_name': 'Dealer Name',
            'city': 'City',
            'region': 'Region',
            'performance_score': 'Performance Score',
            'tier': 'Tier',
            'units_sold': 'Units Sold'
        }, inplace=True)
        
        # Display table
        st.dataframe(
            disp_df[['Dealer Name', 'City', 'Region', 'Tier', 'Performance Score', 'Units Sold', 'Total Revenue (INR)']],
            use_container_width=True,
            hide_index=True
        )
        
        # Print leader insight
        top_dealer = df_dealers.iloc[0]
        st.success(f"🏆 **Top Dealer Alert:** **{top_dealer['dealer_name']}** based in **{top_dealer['city']}** is leading this period with **{top_dealer['units_sold']:,} units sold** driving a total revenue of **₹{top_dealer['revenue']:,.2f}**.")
        
    except Exception as e:
        st.error(f"Error rendering Regional Intelligence: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()
