import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from database.connection import get_db_session
from database.queries import (
    get_dealer_performance_leaderboard,
    get_registrations_by_state, get_state_growth_data, get_ev_adoption_trend,
)
from utils.helpers import get_color_palette

# State centroid coordinates for India map
_STATE_COORDS = {
    "Andhra Pradesh": (15.9129, 79.7400), "Arunachal Pradesh": (28.2180, 94.7278),
    "Assam": (26.2006, 92.9376), "Bihar": (25.0961, 85.3131),
    "Chandigarh": (30.7333, 76.7794), "Chhattisgarh": (21.2787, 81.8661),
    "Delhi": (28.7041, 77.1025), "Goa": (15.2993, 74.1240),
    "Gujarat": (22.2587, 71.1924), "Haryana": (29.0588, 76.0856),
    "Himachal Pradesh": (31.1048, 77.1734), "Jammu and Kashmir": (33.7782, 76.5762),
    "Jharkhand": (23.6102, 85.2799), "Karnataka": (15.3173, 75.7139),
    "Kerala": (10.8505, 76.2711), "Ladakh": (34.2268, 77.5619),
    "Madhya Pradesh": (22.9734, 78.6569), "Maharashtra": (19.7515, 75.7139),
    "Manipur": (24.6637, 93.9063), "Meghalaya": (25.4670, 91.3662),
    "Mizoram": (23.1645, 92.9376), "Nagaland": (26.1584, 94.5624),
    "Odisha": (20.9517, 85.0985), "Puducherry": (11.9416, 79.8083),
    "Punjab": (31.1471, 75.3412), "Rajasthan": (27.0238, 74.2179),
    "Sikkim": (27.5330, 88.5122), "Tamil Nadu": (11.1271, 78.6569),
    "Telangana": (18.1124, 79.0193), "Tripura": (23.9408, 91.9882),
    "Uttar Pradesh": (26.8467, 80.9462), "Uttarakhand": (30.0668, 79.0193),
    "West Bengal": (22.9868, 87.8550), "All India": (20.5937, 78.9629),
    "Andaman & Nicobar Island": (11.7401, 92.6586), "Dadra and Nagar Haveli": (20.1809, 73.0169),
    "Daman and Diu": (20.4283, 72.8397), "Lakshadweep": (10.5667, 72.6417),
}


def render_regional(filters: dict):
    """
    Renders the Regional Intelligence Tab.
    """
    session = get_db_session()
    colors = get_color_palette()
    
    try:
        st.markdown("<h2 class='gradient-text' style='margin-bottom: 20px;'>Regional Intelligence</h2>", unsafe_allow_html=True)

        # Detect India vs UAE data
        state_df = get_registrations_by_state(session, filters)
        use_india = not state_df.empty

        if use_india:
            # ── India State Registration Map ─────────────────────────────────
            st.markdown("### State-wise Vehicle Registrations")

            # Attach lat/lon from hardcoded centroid dict
            state_df['lat'] = state_df['state'].map(lambda s: _STATE_COORDS.get(s, (20.5, 78.9))[0])
            state_df['lon'] = state_df['state'].map(lambda s: _STATE_COORDS.get(s, (20.5, 78.9))[1])
            state_df = state_df[state_df['state'] != 'All India']

            fig_map = px.scatter_mapbox(
                state_df,
                lat="lat", lon="lon",
                size="registrations",
                color="registrations",
                hover_name="state",
                hover_data={"registrations": True, "lat": False, "lon": False},
                color_continuous_scale="Viridis",
                zoom=4.0,
                mapbox_style="open-street-map",
                size_max=50,
            )
            fig_map.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                margin=dict(l=0, r=0, t=0, b=0),
                height=480,
            )
            st.plotly_chart(fig_map, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── EV Adoption Trend ────────────────────────────────────────────
            ev_df = get_ev_adoption_trend(session, filters)
            if not ev_df.empty:
                st.markdown("### EV Adoption Trend")
                fig_ev = go.Figure()
                fig_ev.add_trace(go.Scatter(
                    x=ev_df['date'], y=ev_df['ev_share_pct'],
                    name='EV Share (%)', mode='lines+markers',
                    line=dict(color='#10b981', width=2.5),
                    hovertemplate='%{x|%b %Y}<br>EV Share: %{y:.2f}%<extra></extra>',
                ))
                fig_ev.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                    xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title='EV Share (%)'),
                    margin=dict(l=0, r=0, t=10, b=0), height=280,
                )
                st.plotly_chart(fig_ev, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── State Leaderboard ────────────────────────────────────────────
            st.markdown("### State Registration Leaderboard")
            growth_df = get_state_growth_data(session, filters)
            if not growth_df.empty:
                disp = growth_df[['state', 'total_registrations', 'ev_share_pct', 'dominant_fuel', 'top_maker']].copy()
                disp.columns = ['State', 'Total Registrations', 'EV Share %', 'Dominant Fuel', 'Top Maker']
                disp = disp.sort_values('Total Registrations', ascending=False).reset_index(drop=True)
                st.dataframe(disp, use_container_width=True, hide_index=True)
                top = disp.iloc[0]
                st.success(f"**Top State:** {top['State']} — {top['Total Registrations']:,} registrations | Top Maker: {top['Top Maker']} | EV Share: {top['EV Share %']:.1f}%")
            else:
                st.dataframe(state_df.head(20), use_container_width=True, hide_index=True)

        else:
            # ── UAE legacy dealer map ────────────────────────────────────────
            df_dealers = get_dealer_performance_leaderboard(session, filters)
            if df_dealers.empty:
                st.warning("No regional dealer network data available for the active filters.")
                return

            st.markdown("### Dealer Sales Distribution Map")
            gps_df = df_dealers[(df_dealers['units_sold'] > 0) & pd.notnull(df_dealers['latitude']) & pd.notnull(df_dealers['longitude'])]
            if not gps_df.empty:
                fig_map = px.scatter_mapbox(
                    gps_df, lat="latitude", lon="longitude", size="units_sold", color="revenue",
                    hover_name="dealer_name",
                    hover_data={"emirate": True, "tier": True, "units_sold": True, "revenue": True},
                    color_continuous_scale="Viridis", zoom=3.8, mapbox_style="open-street-map",
                )
                fig_map.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                                      font=dict(color='#f3f4f6', family='Plus Jakarta Sans'),
                                      margin=dict(l=0, r=0, t=0, b=0), height=450)
                st.plotly_chart(fig_map, use_container_width=True)

            st.markdown("### Top Performing Dealer Leaderboard")
            disp_df = df_dealers.copy()
            disp_df['Total Revenue (AED)'] = disp_df['revenue'].apply(lambda x: f"AED {x:,.0f}")
            disp_df.rename(columns={'dealer_name': 'Dealer Name', 'emirate': 'Emirate',
                                    'area': 'Area', 'performance_score': 'Performance Score',
                                    'tier': 'Tier', 'units_sold': 'Units Sold'}, inplace=True)
            st.dataframe(disp_df[['Dealer Name', 'Emirate', 'Area', 'Tier', 'Performance Score', 'Units Sold', 'Total Revenue (AED)']],
                         use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"Error rendering Regional Intelligence: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()
