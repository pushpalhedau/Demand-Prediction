import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.queries import (
    get_rental_market_kpis,
    get_rental_yield_by_city,
    get_rental_trend_over_time,
    get_rental_yield_by_type_bedroom,
    get_short_term_rental_stats,
)
from utils.helpers import (
    render_kpi_card, fmt_aed, fmt_number,
    get_re_colors, plotly_dark_layout, section_header,
)


def render_rental_trends(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Rental market intelligence — yield benchmarks, occupancy rates, rent trends,
        short-term rental performance and price-to-rent ratios across UAE cities.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        kpis = get_rental_market_kpis(session)
        df_city_yield = get_rental_yield_by_city(session)
        df_trend = get_rental_trend_over_time(session)
        df_type_bed = get_rental_yield_by_type_bedroom(session)
        df_str = get_short_term_rental_stats(session)
    finally:
        session.close()

    # ── KPI Row ───────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        render_kpi_card("Avg Gross Yield", f"{kpis['avg_gross_yield']:.2f}%",
                        is_positive=kpis['avg_gross_yield'] > 5)
    with c2:
        render_kpi_card("Avg Occupancy", f"{kpis['avg_occupancy']:.1f}%",
                        is_positive=kpis['avg_occupancy'] > 80)
    with c3:
        render_kpi_card("Avg Annual Rent", fmt_aed(kpis['avg_annual_rent']))
    with c4:
        d = kpis['avg_rent_yoy_change']
        render_kpi_card("Rent YoY Change", f"{d:+.1f}%", is_positive=d >= 0)
    with c5:
        render_kpi_card("Avg Vacancy", f"{kpis['avg_vacancy']:.1f}%",
                        is_positive=kpis['avg_vacancy'] < 10)
    with c6:
        render_kpi_card("Ejari Registrations", fmt_number(kpis['ejari_registrations']))

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Yield by city + trend ──────────────────────
    col_a, col_b = st.columns([2, 3])

    with col_a:
        section_header("Gross Yield by City")
        if not df_city_yield.empty:
            city_colors = [colors["city"].get(c, colors["primary"]) for c in df_city_yield["city"]]
            fig = go.Figure(go.Bar(
                x=df_city_yield["gross_yield"],
                y=df_city_yield["city"],
                orientation="h",
                marker=dict(color=city_colors, line=dict(width=0)),
                text=[f"{v:.2f}%" for v in df_city_yield["gross_yield"]],
                textposition="outside",
                textfont=dict(size=11, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 360)
            layout["xaxis"]["title"] = "Gross Yield %"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 100
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section_header("Rent & Yield Trend Over Time")
        if not df_trend.empty:
            top_cities = df_trend["city"].value_counts().head(4).index.tolist()
            df_top = df_trend[df_trend["city"].isin(top_cities)]
            fig = go.Figure()
            for city in top_cities:
                sub = df_top[df_top["city"] == city].sort_values("period_date")
                fig.add_trace(go.Scatter(
                    x=sub["period_date"], y=sub["gross_yield"],
                    name=city,
                    mode="lines",
                    line=dict(width=2, color=colors["city"].get(city, colors["primary"])),
                ))
            layout = plotly_dark_layout("", 360)
            layout["yaxis"]["title"] = "Gross Yield %"
            layout["legend"] = dict(orientation="h", y=-0.18, x=0, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Occupancy by city ───────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Occupancy & Vacancy Rates by City")
    if not df_city_yield.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_city_yield["city"], y=df_city_yield["occupancy"],
            name="Occupancy %",
            marker=dict(color=colors["primary"], opacity=0.85, line=dict(width=0)),
        ))
        fig.add_trace(go.Bar(
            x=df_city_yield["city"], y=df_city_yield["vacancy"],
            name="Vacancy %",
            marker=dict(color=colors["danger"], opacity=0.75, line=dict(width=0)),
        ))
        fig.add_trace(go.Scatter(
            x=df_city_yield["city"], y=df_city_yield["price_to_rent"],
            name="Price-to-Rent Ratio",
            yaxis="y2",
            line=dict(color=colors["gold"], width=2.5),
            mode="lines+markers", marker=dict(size=6),
        ))
        layout = plotly_dark_layout("", 340)
        layout["barmode"] = "group"
        layout["yaxis2"] = dict(
            title=dict(text="Price-to-Rent Ratio", font=dict(color=colors["gold"])),
            overlaying="y", side="right",
            gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11),
        )
        layout["legend"] = dict(orientation="h", y=-0.18, x=0, bgcolor="rgba(0,0,0,0)")
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)

    # ── Row 3: Yield by property type & bedroom ───────────
    col_c, col_d = st.columns(2)

    with col_c:
        section_header("Gross Yield by Property Type")
        if not df_type_bed.empty:
            by_type = df_type_bed.groupby("property_type").agg(
                gross_yield=("gross_yield", "mean"),
                occupancy=("occupancy", "mean"),
            ).reset_index().sort_values("gross_yield", ascending=False)
            fig = go.Figure(go.Bar(
                x=by_type["property_type"], y=by_type["gross_yield"],
                marker=dict(color=colors["colors_seq"][:len(by_type)], line=dict(width=0)),
                text=[f"{v:.2f}%" for v in by_type["gross_yield"]],
                textposition="outside",
                textfont=dict(size=11, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 320)
            layout["yaxis"]["title"] = "Gross Yield %"
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_d:
        section_header("Yield by Bedroom Configuration")
        if not df_type_bed.empty:
            by_bed = df_type_bed.groupby("bedrooms").agg(
                gross_yield=("gross_yield", "mean"),
                avg_annual_rent=("avg_annual_rent", "mean"),
            ).reset_index().sort_values("gross_yield", ascending=False)
            fig = go.Figure(go.Bar(
                x=by_bed["bedrooms"], y=by_bed["gross_yield"],
                marker=dict(color=colors["colors_seq"][:len(by_bed)], line=dict(width=0)),
                text=[f"{v:.2f}%" for v in by_bed["gross_yield"]],
                textposition="outside",
                textfont=dict(size=11, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 320)
            layout["yaxis"]["title"] = "Gross Yield %"
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 4: Short-term rental ──────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Short-Term Rental Performance by City")
    if not df_str.empty:
        col_e, col_f = st.columns([3, 2])

        with col_e:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_str["city"], y=df_str["adr"],
                name="Avg Daily Rate (AED)",
                marker=dict(color=colors["gold"], opacity=0.85, line=dict(width=0)),
            ))
            fig.add_trace(go.Scatter(
                x=df_str["city"], y=df_str["str_occupancy"],
                name="STR Occupancy %",
                yaxis="y2",
                line=dict(color=colors["primary"], width=2.5),
                mode="lines+markers", marker=dict(size=7),
            ))
            layout = plotly_dark_layout("", 320)
            layout["yaxis"]["title"] = "Avg Daily Rate (AED)"
            layout["yaxis2"] = dict(
                title=dict(text="STR Occupancy %", font=dict(color=colors["primary"])),
                overlaying="y", side="right",
                gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11),
            )
            layout["legend"] = dict(orientation="h", y=-0.2, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with col_f:
            tbl = df_str[[
                "city", "str_share", "adr", "str_occupancy", "str_annual_revenue"
            ]].copy()
            tbl["str_share"] = tbl["str_share"].apply(lambda v: f"{v:.1f}%" if pd.notna(v) else "—")
            tbl["adr"] = tbl["adr"].apply(lambda v: f"AED {v:,.0f}" if pd.notna(v) else "—")
            tbl["str_occupancy"] = tbl["str_occupancy"].apply(
                lambda v: f"{v:.1f}%" if pd.notna(v) else "—"
            )
            tbl["str_annual_revenue"] = tbl["str_annual_revenue"].apply(
                lambda v: fmt_aed(v) if pd.notna(v) else "—"
            )
            st.dataframe(
                tbl.rename(columns={
                    "city": "City",
                    "str_share": "STR Share",
                    "adr": "Avg Daily Rate",
                    "str_occupancy": "Occupancy",
                    "str_annual_revenue": "Annual Revenue",
                }),
                use_container_width=True,
                hide_index=True,
            )
