import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from database.connection import get_db_session
from database.queries import (
    get_executive_kpis,
    get_monthly_revenue_trend,
    get_sales_by_property_type,
    get_sales_by_property_category,
    get_sales_by_city,
    get_sales_by_payment_plan,
    get_sales_by_marketing_channel,
)
from utils.helpers import render_kpi_card, fmt_aed, fmt_number, get_re_colors, plotly_dark_layout, section_header


def render_overview(filters: dict):
    colors = get_re_colors()

    session = get_db_session()
    try:
        kpis = get_executive_kpis(session, filters)
        df_monthly = get_monthly_revenue_trend(session, filters)
        df_types = get_sales_by_property_type(session, filters)
        df_cats = get_sales_by_property_category(session, filters)
        df_cities = get_sales_by_city(session, filters)
        df_payment = get_sales_by_payment_plan(session, filters)
        df_channel = get_sales_by_marketing_channel(session, filters)
    finally:
        session.close()

    # ── KPI Row 1 ────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        d = kpis.get("total_value_delta")
        render_kpi_card("Total Sales Value", fmt_aed(kpis["total_value"]),
                        delta=f"{d:.1f}% YoY" if d is not None else None,
                        is_positive=(d or 0) >= 0)
    with c2:
        d = kpis.get("units_delta")
        render_kpi_card("Units Transacted", f"{kpis['units_sold']:,}",
                        delta=f"{d:.1f}% YoY" if d is not None else None,
                        is_positive=(d or 0) >= 0)
    with c3:
        d = kpis.get("avg_sqft_delta")
        render_kpi_card("Avg Price / Sq.Ft", f"AED {kpis['avg_price_sqft']:,.0f}",
                        delta=f"{d:.1f}% YoY" if d is not None else None,
                        is_positive=(d or 0) >= 0)
    with c4:
        render_kpi_card("Booking Conversion", f"{kpis['conversion_rate']:.1f}%")

    st.markdown("<br>", unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        render_kpi_card("Absorption Rate", f"{kpis['absorption_rate']:.1f}%")
    with c6:
        render_kpi_card("Avg Lead-to-Close", f"{kpis['avg_lead_close']:.0f} days")
    with c7:
        render_kpi_card("Golden Visa Txns", f"{kpis['golden_visa_count']:,}")
    with c8:
        render_kpi_card("Unsold Flags", f"{kpis['unsold_listings']:,}",
                        is_positive=False)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Revenue trend + Category donut ─────────────
    col_a, col_b = st.columns([3, 2])

    with col_a:
        section_header("Monthly Transaction Trend")
        if not df_monthly.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_monthly["date"], y=df_monthly["revenue"] / 1e6,
                name="Revenue (AED M)", marker_color=colors["primary"],
                opacity=0.65, yaxis="y2",
            ))
            fig.add_trace(go.Scatter(
                x=df_monthly["date"], y=df_monthly["units"],
                name="Units", line=dict(color=colors["gold"], width=2.5),
                mode="lines+markers", marker=dict(size=4),
            ))
            layout = plotly_dark_layout("", 360)
            layout["yaxis"] = dict(
                title=dict(text="Units", font=dict(color=colors["gold"])),
                gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=11),
            )
            layout["yaxis2"] = dict(
                title=dict(text="Revenue (AED M)", font=dict(color=colors["primary"])),
                overlaying="y", side="right",
                gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11),
            )
            layout["legend"] = dict(orientation="h", y=-0.18, x=0, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No transaction data for the selected filters.")

    with col_b:
        section_header("Property Category Mix")
        if not df_cats.empty:
            cat_colors = [
                colors["property_category"].get(c, colors["primary"])
                for c in df_cats["property_category"]
            ]
            fig = go.Figure(go.Pie(
                labels=df_cats["property_category"], values=df_cats["units"],
                hole=0.58,
                marker=dict(colors=cat_colors, line=dict(color="#080d18", width=2)),
                textinfo="percent+label", textfont=dict(size=11),
            ))
            layout = plotly_dark_layout("", 360)
            layout["showlegend"] = False
            layout["annotations"] = [dict(
                text=f"<b>{df_cats['units'].sum():,}</b><br>Units",
                x=0.5, y=0.5, font=dict(size=13, color="#f0f4f8", family="Outfit"),
                showarrow=False,
            )]
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Top cities + Payment plan ──────────────────
    col_c, col_d = st.columns([3, 2])

    with col_c:
        section_header("Top Cities by Transaction Value")
        if not df_cities.empty:
            top10 = df_cities.head(10).copy()
            top10["revenue_m"] = top10["revenue"] / 1e6
            city_colors = [colors["city"].get(c, colors["primary"]) for c in top10["city"]]
            fig = go.Figure(go.Bar(
                x=top10["revenue_m"], y=top10["city"], orientation="h",
                marker=dict(color=city_colors, line=dict(width=0)),
                text=[f"AED {v:.0f}M  ({u:,})" for v, u in zip(top10["revenue_m"], top10["units"])],
                textposition="outside", textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 370)
            layout["xaxis"]["title"] = "Revenue (AED Millions)"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 90
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_d:
        section_header("Payment Plan Distribution")
        if not df_payment.empty:
            fig = go.Figure(go.Pie(
                labels=df_payment["payment_plan"], values=df_payment["units"],
                hole=0.52,
                marker=dict(colors=colors["colors_seq"][:len(df_payment)],
                            line=dict(color="#080d18", width=2)),
                textinfo="percent", textfont=dict(size=11),
            ))
            layout = plotly_dark_layout("", 370)
            layout["legend"]["orientation"] = "v"
            layout["legend"]["y"] = 0.5
            layout["legend"]["x"] = 1.02
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 3: Property type + Channel performance ─────────
    col_e, col_f = st.columns(2)

    with col_e:
        section_header("Units by Property Type")
        if not df_types.empty:
            fig = go.Figure(go.Bar(
                x=df_types["property_type"], y=df_types["units"],
                marker=dict(color=colors["colors_seq"][:len(df_types)], line=dict(width=0)),
                text=df_types["units"].apply(lambda v: f"{v:,}"),
                textposition="outside", textfont=dict(size=11, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 320)
            layout["xaxis"]["tickangle"] = -15
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_f:
        section_header("Marketing Channel Efficiency")
        if not df_channel.empty:
            fig = go.Figure(go.Bar(
                x=df_channel["avg_lead_days"], y=df_channel["marketing_channel"],
                orientation="h",
                marker=dict(
                    color=df_channel["units"] / df_channel["units"].max(),
                    colorscale=[[0, "#1a3350"], [1, colors["primary"]]],
                    line=dict(width=0),
                ),
                text=[f"{u:,} units | {d:.0f}d" for u, d in
                      zip(df_channel["units"], df_channel["avg_lead_days"])],
                textposition="outside", textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 320)
            layout["xaxis"]["title"] = "Avg Lead-to-Close (Days)"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 120
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Insight strip ──────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Key Insights")
    ia, ib, ic = st.columns(3)
    top_city = kpis.get("top_city", "N/A")
    top_cat = kpis.get("top_category", "N/A")
    conv = kpis.get("conversion_rate", 0)
    lead_d = kpis.get("avg_lead_close", 0)
    unsold = kpis.get("unsold_listings", 0)
    slow = kpis.get("slow_movers", 0)

    with ia:
        st.markdown(f"""<div class="insight-box">
            <b>Top Market:</b> {top_city} leads in transaction volume.<br>
            <b>Hottest Category:</b> {top_cat} driving peak demand.
        </div>""", unsafe_allow_html=True)
    with ib:
        box = "insight-box" if conv > 50 else "warning-box"
        st.markdown(f"""<div class="{box}">
            <b>Conversion:</b> {conv:.1f}% of leads convert to bookings.<br>
            <b>Sales Velocity:</b> Avg {lead_d:.0f} days to close a deal.
        </div>""", unsafe_allow_html=True)
    with ic:
        box = "alert-box" if unsold > 50 else "warning-box"
        st.markdown(f"""<div class="{box}">
            <b>Unsold Inventory:</b> {unsold:,} projects beyond 6-month mark.<br>
            <b>Slow Movers:</b> {slow:,} projects below city avg velocity.
        </div>""", unsafe_allow_html=True)
