import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from database.connection import get_db_session, get_data_mode
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
                hover_data={"state": True, "city": True, "tier": True, "performance_score": True, "units_sold": True, "revenue": True},
                color_continuous_scale="Viridis",
                zoom=3.2,
                center={"lat": 39.0, "lon": -98.0},
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

        disp_df = df_dealers.copy()
        disp_df['Total Revenue (USD)'] = disp_df['revenue'].apply(lambda x: f"${x:,.0f}")

        if get_data_mode() == "real":
            # --- Real mode: replace synthetic Tier + Performance Score with real data ---

            def ev_label(row):
                ev = bool(row.get('ev_charging_station'))
                sc = bool(row.get('service_center'))
                if ev and sc:   return "Full"
                if ev or sc:    return "Partial"
                return "None"

            disp_df['EV Infrastructure'] = disp_df.apply(ev_label, axis=1)
            disp_df['Google Rating'] = disp_df['google_rating'].apply(
                lambda x: f"{x} ★" if pd.notnull(x) and x > 0 else "–"
            )
            # Avg Deal Value: ×17 cancels in numerator/denominator — no extra scaling needed
            disp_df['Avg Deal Value (USD)'] = (disp_df['revenue'] / disp_df['units_sold']).apply(
                lambda x: f"${x:,.0f}" if pd.notnull(x) and x > 0 else "–"
            )
            disp_df['Top Category'] = disp_df['top_category'].fillna('–')
            disp_df.rename(columns={
                'dealer_name': 'Dealer Name',
                'state':       'State',
                'city':        'City',
            }, inplace=True)
            display_cols = ['Dealer Name', 'State', 'City', 'Google Rating', 'EV Infrastructure', 'Avg Deal Value (USD)', 'Top Category']

        else:
            # --- Test mode: keep original synthetic columns unchanged ---
            disp_df.rename(columns={
                'dealer_name':       'Dealer Name',
                'state':             'State',
                'city':              'City',
                'performance_score': 'Performance Score',
                'tier':              'Tier',
                'units_sold':        'Units Sold',
            }, inplace=True)
            display_cols = ['Dealer Name', 'State', 'City', 'Tier', 'Performance Score', 'Units Sold', 'Total Revenue (USD)']

        st.dataframe(
            disp_df[display_cols],
            use_container_width=True,
            hide_index=True
        )
        
        # Print leader insight
        top_dealer = df_dealers.iloc[0]
        st.success(f"**Top Dealer Alert:** **{top_dealer['dealer_name']}** based in **{top_dealer['state']}** is leading this period with **{top_dealer['units_sold']:,} units sold** driving a total revenue of **${top_dealer['revenue']:,.2f}**.")
        
    except Exception as e:
        st.error(f"Error rendering Regional Intelligence: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()
