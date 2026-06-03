import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.queries import (
    get_sales_by_city,
    get_sales_by_region,
    get_developer_performance,
    get_locality_hotspots,
)
from utils.helpers import get_re_colors, plotly_dark_layout, section_header, fmt_aed


def render_regional(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Regional demand intelligence — city hotspots, locality micro-markets,
        developer geographic distribution and regional performance benchmarks.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        df_cities = get_sales_by_city(session, filters)
        df_regions = get_sales_by_region(session, filters)
        df_devs = get_developer_performance(session, filters)
        df_localities = get_locality_hotspots(session, filters)
    finally:
        session.close()

    # ── City bubble chart ─────────────────────────────────
    section_header("City-Level Demand Heatmap", icon="🗺")

    # City coordinates (approximate centroids)
    city_coords = {
        "Dubai": (25.2048, 55.2708),
        "Abu Dhabi": (24.4539, 54.3773),
        "Sharjah": (25.3463, 55.4209),
        "Ras Al Khaimah": (25.7895, 55.9432),
        "Ajman": (25.4052, 55.5136),
        "Fujairah": (25.1288, 56.3265),
        "Umm Al Quwain": (25.5647, 55.5553),
    }

    if not df_cities.empty:
        df_cities["lat"] = df_cities["city"].map(lambda c: city_coords.get(c, (25.2048, 55.2708))[0])
        df_cities["lon"] = df_cities["city"].map(lambda c: city_coords.get(c, (25.2048, 55.2708))[1])

        col_map, col_rank = st.columns([2, 1])

        with col_map:
            fig = go.Figure(go.Scattergeo(
                lat=df_cities["lat"],
                lon=df_cities["lon"],
                text=df_cities["city"],
                customdata=df_cities[["units", "revenue", "avg_price_sqft"]].values,
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Units: %{customdata[0]:,}<br>"
                    "Revenue: AED %{customdata[1]:.2e}<br>"
                    "Avg Price/Sq.Ft: AED %{customdata[2]:,.0f}"
                    "<extra></extra>"
                ),
                mode="markers+text",
                textposition="top center",
                textfont=dict(size=10, color="#94a3b8"),
                marker=dict(
                    size=df_cities["units"] / df_cities["units"].max() * 40 + 10,
                    color=df_cities["avg_price_sqft"],
                    colorscale=[[0, "#0e4a3a"], [0.5, colors["primary"]], [1, colors["gold"]]],
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="AED/sq.ft", font=dict(size=10)),
                        thickness=12,
                        tickfont=dict(size=10),
                        x=1.02,
                    ),
                    line=dict(color="rgba(255,255,255,0.2)", width=1),
                    opacity=0.85,
                ),
            ))
            fig.update_geos(
                visible=False,
                resolution=50,
                scope="asia",
                showcountries=True,
                countrycolor="rgba(255,255,255,0.1)",
                showsubunits=True,
                subunitcolor="rgba(255,255,255,0.08)",
                center=dict(lat=24.5, lon=55.0),
                projection_scale=12.0,
                bgcolor="rgba(0,0,0,0)",
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=450,
                margin=dict(l=0, r=0, t=10, b=10),
                font=dict(color="#94a3b8"),
                geo=dict(bgcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_rank:
            section_header("City Rankings", icon="🏆")
            st.dataframe(
                df_cities[["city", "units", "avg_price_sqft"]].rename(columns={
                    "city": "City",
                    "units": "Units",
                    "avg_price_sqft": "AED/sq.ft",
                }).assign(**{"AED/sq.ft": df_cities["avg_price_sqft"].apply(lambda x: f"AED {x:,.0f}")})
                .head(12),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Regional distribution ──────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        section_header("Demand by Region", icon="🧭")
        if not df_regions.empty:
            fig = go.Figure(go.Pie(
                labels=df_regions["region"],
                values=df_regions["units"],
                hole=0.50,
                marker=dict(
                    colors=colors["colors_seq"][:len(df_regions)],
                    line=dict(color="#080d18", width=2),
                ),
                textinfo="label+percent",
                textfont=dict(size=12),
            ))
            layout = plotly_dark_layout("", 340)
            layout["showlegend"] = False
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section_header("Top Locality Hotspots", icon="📍")
        if not df_localities.empty:
            top15 = df_localities.head(15)
            fig = go.Figure(go.Bar(
                x=top15["transactions"],
                y=top15["locality"] + ", " + top15["city"],
                orientation="h",
                marker=dict(
                    color=top15["avg_price_sqft"],
                    colorscale=[[0, "#1a3350"], [0.5, colors["primary"]], [1, colors["gold"]]],
                    line=dict(width=0),
                ),
                text=[f"{t:,} txns | AED {p:,.0f}/sq.ft" for t, p in
                      zip(top15["transactions"], top15["avg_price_sqft"])],
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 340)
            layout["xaxis"]["title"] = "Transactions"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 170
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Developer leaderboard ──────────────────────────────
    section_header("Developer Performance Leaderboard", icon="🏗")
    if not df_devs.empty:
        col_c, col_d = st.columns([2, 3])

        with col_c:
            top10_devs = df_devs.head(10)
            rera_icon = lambda x: "✅" if x else "❌"
            display_df = top10_devs[[
                "developer_name", "primary_city", "tier", "units_sold",
                "rating", "rera_registered"
            ]].copy()
            display_df["revenue_cr"] = (df_devs.head(10)["revenue"] / 1e6).apply(
                lambda v: f"AED {v:.1f}M"
            )
            display_df["rera_registered"] = display_df["rera_registered"].apply(
                lambda x: "✅" if x else "❌"
            )
            display_df["rating"] = display_df["rating"].apply(lambda v: f"{v:.1f} ⭐")
            display_df = display_df.rename(columns={
                "developer_name": "Developer",
                "primary_city": "City",
                "tier": "Tier",
                "units_sold": "Units",
                "rating": "Rating",
                "rera_registered": "RERA",
                "revenue_cr": "Revenue",
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)

        with col_d:
            top15_devs = df_devs.head(15)
            fig = go.Figure(go.Bar(
                x=top15_devs["units_sold"],
                y=top15_devs["developer_name"],
                orientation="h",
                marker=dict(
                    color=top15_devs["performance_score"],
                    colorscale=[[0, "#1a3350"], [0.5, colors["primary"]], [1, colors["gold"]]],
                    line=dict(width=0),
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="Score", font=dict(size=10)),
                        thickness=12,
                        tickfont=dict(size=10),
                    ),
                ),
                text=[f"{u:,} units | {t}" for u, t in
                      zip(top15_devs["units_sold"], top15_devs["tier"])],
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 440)
            layout["xaxis"]["title"] = "Units Sold"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 160
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Developer geo scatter ──────────────────────────────
    if not df_devs.empty and "latitude" in df_devs.columns:
        section_header("Developer Network Distribution", icon="🌐")
        valid_devs = df_devs[(df_devs["latitude"].notna()) & (df_devs["latitude"] != 0)]
        if not valid_devs.empty:
            tier_colors = {"Tier 1": colors["gold"], "Tier 2": colors["primary"], "Tier 3": colors["indigo"]}
            fig = go.Figure()
            for tier, grp in valid_devs.groupby("tier"):
                fig.add_trace(go.Scattergeo(
                    lat=grp["latitude"], lon=grp["longitude"],
                    mode="markers",
                    name=tier,
                    marker=dict(
                        size=grp["units_sold"] / grp["units_sold"].max() * 20 + 6,
                        color=tier_colors.get(tier, colors["primary"]),
                        line=dict(color="rgba(255,255,255,0.2)", width=1),
                        opacity=0.85,
                    ),
                    text=grp["developer_name"],
                    hovertemplate="<b>%{text}</b><br>Tier: " + tier + "<br>Units: %{customdata[0]:,}<extra></extra>",
                    customdata=grp[["units_sold"]].values,
                ))
            fig.update_geos(
                visible=False, resolution=50, scope="asia",
                showcountries=True, countrycolor="rgba(255,255,255,0.1)",
                center=dict(lat=24.5, lon=55.0), projection_scale=12.0,
                bgcolor="rgba(0,0,0,0)",
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", height=400,
                margin=dict(l=0, r=0, t=10, b=10),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8")),
                font=dict(color="#94a3b8"),
            )
            st.plotly_chart(fig, use_container_width=True)
