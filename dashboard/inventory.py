import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from database.connection import get_db_session
from database.queries import get_inventory_status, get_inventory_summary_by_city
from utils.helpers import get_re_colors, plotly_dark_layout, section_header, fmt_aed


def render_inventory(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Inventory intelligence — track unsold units, slow-moving projects, absorption rates,
        holding costs and construction pipeline across emirates and property segments.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        df_inv = get_inventory_status(session, filters)
        df_city_inv = get_inventory_summary_by_city(session)
    finally:
        session.close()

    if df_inv.empty:
        st.info("No inventory data available for the selected filters.")
        return

    # ── KPI strip ──────────────────────────────────────────
    total_available = df_inv["available_units"].sum()
    total_booked = df_inv["booked_units"].sum()
    unsold_projects = df_inv["unsold_flag"].sum()
    slow_movers = df_inv["slow_moving_flag"].sum()
    total_holding_cost = df_inv["estimated_holding_cost_aed"].sum()
    avg_days_market = df_inv["days_on_market"].mean()
    absorption_rate = (df_inv["units_sold_last_30d"].sum() /
                       max(df_inv["available_units"].sum(), 1)) * 100

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Available Units", f"{total_available:,}")
    k2.metric("Booked Units", f"{total_booked:,}")
    k3.metric("Absorption Rate", f"{absorption_rate:.1f}%")
    k4.metric("Unsold Projects", f"{unsold_projects:,}")
    k5.metric("Total Holding Cost", fmt_aed(total_holding_cost))

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: City inventory + Absorption ────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        section_header("Inventory by City (Available vs Booked)")
        if not df_city_inv.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Available", x=df_city_inv["city"], y=df_city_inv["available"],
                marker_color=colors["primary"], opacity=0.85,
            ))
            fig.add_trace(go.Bar(
                name="Booked", x=df_city_inv["city"], y=df_city_inv["booked"],
                marker_color=colors["gold"], opacity=0.85,
            ))
            fig.add_trace(go.Bar(
                name="Registered", x=df_city_inv["city"], y=df_city_inv["registered"],
                marker_color=colors["indigo"], opacity=0.85,
            ))
            layout = plotly_dark_layout("", 360)
            layout["barmode"] = "group"
            layout["xaxis"]["tickangle"] = -20
            layout["legend"] = dict(orientation="h", y=-0.2, x=0, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section_header("Avg Days on Market by City")
        if not df_city_inv.empty:
            df_sort = df_city_inv.sort_values("avg_days_on_market", ascending=True)
            bar_colors = [
                colors["danger"] if d > 180 else (colors["warning"] if d > 90 else colors["primary"])
                for d in df_sort["avg_days_on_market"]
            ]
            fig = go.Figure(go.Bar(
                x=df_sort["avg_days_on_market"],
                y=df_sort["city"],
                orientation="h",
                marker=dict(color=bar_colors, line=dict(width=0)),
                text=[f"{d:.0f} days" for d in df_sort["avg_days_on_market"]],
                textposition="outside",
                textfont=dict(size=11, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 360)
            layout["xaxis"]["title"] = "Avg Days on Market"
            layout["margin"]["l"] = 90
            layout["yaxis"]["autorange"] = "reversed"
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Holding cost + Construction pipeline ────────
    col_c, col_d = st.columns(2)

    with col_c:
        section_header("Holding Cost by City (AED M)")
        if not df_city_inv.empty:
            df_hc = df_city_inv.sort_values("total_holding_cost", ascending=False).head(10)
            fig = go.Figure(go.Bar(
                x=df_hc["total_holding_cost"] / 1e6,
                y=df_hc["city"],
                orientation="h",
                marker=dict(
                    color=df_hc["total_holding_cost"],
                    colorscale=[[0, "#1a2540"], [0.5, colors["warning"]], [1, colors["danger"]]],
                    line=dict(width=0),
                ),
                text=[f"AED {v:.1f}M" for v in df_hc["total_holding_cost"] / 1e6],
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 340)
            layout["xaxis"]["title"] = "Holding Cost (AED Millions)"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 90
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_d:
        section_header("Construction Progress Distribution")
        if "construction_progress_pct" in df_inv.columns:
            uc_only = df_inv[df_inv["completion_status"] == "Off-Plan"]
            if not uc_only.empty:
                bins = [0, 25, 50, 75, 100]
                labels = ["0-25%", "26-50%", "51-75%", "76-100%"]
                uc_only = uc_only.copy()
                uc_only["progress_band"] = pd.cut(
                    uc_only["construction_progress_pct"], bins=bins, labels=labels, right=True
                )
                band_counts = uc_only["progress_band"].value_counts().sort_index()
                fig = go.Figure(go.Bar(
                    x=band_counts.index.tolist(),
                    y=band_counts.values,
                    marker=dict(
                        color=[colors["danger"], colors["warning"], colors["indigo"], colors["primary"]],
                        line=dict(width=0),
                    ),
                    text=band_counts.values,
                    textposition="outside",
                    textfont=dict(size=12, color="#94a3b8"),
                ))
                layout = plotly_dark_layout("Off-Plan Projects by Completion %", 340)
                layout["xaxis"]["title"] = "Construction Progress"
                layout["yaxis"]["title"] = "Projects"
                layout["showlegend"] = False
                fig.update_layout(**layout)
                st.plotly_chart(fig, use_container_width=True)

    # ── Slow-moving inventory table ────────────────────────
    section_header("Slow-Moving Inventory Alert")
    slow_df = df_inv[df_inv["slow_moving_flag"] == True].copy()
    if not slow_df.empty:
        slow_display = slow_df.sort_values("days_on_market", ascending=False).head(20)
        slow_display = slow_display[[
            "project_name", "city", "locality", "property_category",
            "bedrooms", "available_units", "days_on_market",
            "holding_cost_per_day_aed", "estimated_holding_cost_aed",
        ]].copy()
        slow_display["holding_cost_per_day_aed"] = slow_display["holding_cost_per_day_aed"].apply(
            lambda v: f"AED {v:,.0f}/day"
        )
        slow_display["estimated_holding_cost_aed"] = slow_display["estimated_holding_cost_aed"].apply(
            lambda v: fmt_aed(v)
        )
        st.dataframe(
            slow_display.rename(columns={
                "project_name": "Project",
                "city": "City",
                "locality": "Locality",
                "property_category": "Category",
                "bedrooms": "Config",
                "available_units": "Avail. Units",
                "days_on_market": "Days Listed",
                "holding_cost_per_day_aed": "Daily Cost",
                "estimated_holding_cost_aed": "Total Holding Cost",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.markdown("""<div class="insight-box">
            No slow-moving inventory flags detected for current filters.
        </div>""", unsafe_allow_html=True)

    # ── Absorption rate vs demand forecast scatter ─────────
    section_header("Absorption Rate vs 30-Day Demand Forecast")
    if "units_sold_last_30d" in df_inv.columns and "demand_forecast_30d" in df_inv.columns:
        scatter_df = df_inv.dropna(subset=["units_sold_last_30d", "demand_forecast_30d"]).copy()
        scatter_df["absorption_rate"] = (
            scatter_df["units_sold_last_30d"] /
            scatter_df["available_units"].clip(lower=1)
        ) * 100
        if not scatter_df.empty:
            sample = scatter_df.sample(min(2000, len(scatter_df)), random_state=42)
            city_color_map = {
                c: colors["city"].get(c, colors["primary"])
                for c in sample["city"].unique()
            }
            fig = go.Figure()
            for city, grp in sample.groupby("city"):
                fig.add_trace(go.Scatter(
                    x=grp["demand_forecast_30d"],
                    y=grp["absorption_rate"],
                    mode="markers",
                    name=city,
                    marker=dict(
                        size=7, opacity=0.7,
                        color=city_color_map.get(city, colors["primary"]),
                        line=dict(width=0),
                    ),
                ))
            layout = plotly_dark_layout("", 380)
            layout["xaxis"]["title"] = "30-Day Demand Forecast (Units)"
            layout["yaxis"]["title"] = "Absorption Rate (%)"
            layout["legend"] = dict(orientation="v", bgcolor="rgba(0,0,0,0)", font=dict(size=10))
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)
