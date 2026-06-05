import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

from database.connection import get_db_session
from database.queries import (
    get_price_trends_by_city,
    get_price_by_locality,
    get_price_by_category_type,
    get_market_factor_trend,
    get_unique_filter_options,
)
from utils.helpers import get_re_colors, plotly_dark_layout, section_header, fmt_aed


def render_price_intelligence(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Price per sq.ft intelligence — track appreciation trends, benchmark localities,
        and understand the impact of mortgage rates & UAE Central Bank rate on real estate pricing.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        opts = get_unique_filter_options(session)
        df_price_city = get_price_trends_by_city(session, filters)
        df_locality = get_price_by_locality(session, filters, top_n=25)
        df_cat_type = get_price_by_category_type(session, filters)
        df_market = get_market_factor_trend(session,
                                            city=filters.get("city") if filters else None)
    finally:
        session.close()

    # ── KPI strip ──────────────────────────────────────────
    if not df_price_city.empty:
        avg_sqft = df_price_city["avg_price_sqft"].mean()
        max_city = df_price_city.groupby("city")["avg_price_sqft"].mean().idxmax()
        min_city = df_price_city.groupby("city")["avg_price_sqft"].mean().idxmin()
        top_val = df_price_city.groupby("city")["avg_price_sqft"].mean().max()
        bot_val = df_price_city.groupby("city")["avg_price_sqft"].mean().min()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Overall Avg Price/Sq.Ft", f"AED {avg_sqft:,.0f}")
        k2.metric("Most Expensive City", max_city, f"AED {top_val:,.0f}/sq.ft")
        k3.metric("Most Affordable City", min_city, f"AED {bot_val:,.0f}/sq.ft")
        if not df_market.empty and "mortgage_rate_avg_pct" in df_market.columns:
            latest_rate = df_market["mortgage_rate_avg_pct"].dropna().iloc[-1]
            k4.metric("Current Avg Mortgage Rate", f"{latest_rate:.2f}%")
        else:
            k4.metric("Localities Tracked", f"{df_locality.shape[0]}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Price trend by city (line) ─────────────────
    col_a, col_b = st.columns([3, 2])

    with col_a:
        section_header("Price/Sq.Ft Trend by City")
        if not df_price_city.empty:
            cities_list = df_price_city["city"].unique().tolist()
            sel_cities = st.multiselect(
                "Select cities to compare",
                cities_list,
                default=cities_list[:5],
                key="pi_cities",
            )
            filtered = df_price_city[df_price_city["city"].isin(sel_cities)] if sel_cities else df_price_city

            fig = go.Figure()
            for i, city in enumerate(filtered["city"].unique()):
                city_df = filtered[filtered["city"] == city].sort_values("date")
                fig.add_trace(go.Scatter(
                    x=city_df["date"], y=city_df["avg_price_sqft"],
                    mode="lines", name=city,
                    line=dict(
                        color=colors["city"].get(city, colors["colors_seq"][i % 8]),
                        width=2,
                    ),
                ))
            layout = plotly_dark_layout("", 380)
            layout["yaxis"]["title"] = "Price per Sq.Ft (AED)"
            layout["hovermode"] = "x unified"
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section_header("Avg Price by Property Category")
        if not df_cat_type.empty:
            cat_agg = df_cat_type.groupby("property_category")["avg_price_sqft"].mean().reset_index()
            cat_agg = cat_agg.sort_values("avg_price_sqft", ascending=True)
            cat_colors_list = [
                colors["property_category"].get(c, colors["primary"])
                for c in cat_agg["property_category"]
            ]
            fig = go.Figure(go.Bar(
                x=cat_agg["avg_price_sqft"],
                y=cat_agg["property_category"],
                orientation="h",
                marker=dict(color=cat_colors_list, line=dict(width=0)),
                text=[f"AED {v:,.0f}/sqft" for v in cat_agg["avg_price_sqft"]],
                textposition="outside",
                textfont=dict(size=11, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 380)
            layout["xaxis"]["title"] = "Avg Price (AED/Sq.Ft)"
            layout["margin"]["l"] = 130
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Locality heatmap + Repo rate correlation ───
    col_c, col_d = st.columns([3, 2])

    with col_c:
        section_header("Top Localities by Price/Sq.Ft")
        if not df_locality.empty:
            df_loc = df_locality.sort_values("avg_price_sqft", ascending=True).head(20)
            fig = go.Figure(go.Bar(
                x=df_loc["avg_price_sqft"],
                y=df_loc["locality"] + " (" + df_loc["city"] + ")",
                orientation="h",
                marker=dict(
                    color=df_loc["avg_price_sqft"],
                    colorscale=[[0, "#1a3350"], [0.5, colors["primary"]], [1, colors["gold"]]],
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="AED/sq.ft", font=dict(size=11)),
                        thickness=12,
                        tickfont=dict(size=10),
                    ),
                    line=dict(width=0),
                ),
                text=[f"AED {v:,.0f}" for v in df_loc["avg_price_sqft"]],
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 500)
            layout["xaxis"]["title"] = "Avg Price (AED/Sq.Ft)"
            layout["margin"]["l"] = 200
            layout["yaxis"]["autorange"] = "reversed"
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_d:
        section_header("Mortgage Rate vs Price Index")
        if not df_market.empty and "mortgage_rate_avg_pct" in df_market.columns:
            mf = df_market.dropna(subset=["mortgage_rate_avg_pct", "real_estate_price_index"])
            if not mf.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=mf["date"], y=mf["mortgage_rate_avg_pct"],
                    mode="lines", name="Mortgage Rate (%)",
                    line=dict(color=colors["danger"], width=2),
                    yaxis="y2",
                ))
                fig.add_trace(go.Scatter(
                    x=mf["date"], y=mf["real_estate_price_index"],
                    mode="lines", name="RE Price Index",
                    line=dict(color=colors["primary"], width=2),
                    fill="tozeroy", fillcolor="rgba(16,185,129,0.07)",
                ))
                layout = plotly_dark_layout("", 500)
                layout["yaxis"] = dict(
                    title="RE Price Index", gridcolor="rgba(255,255,255,0.04)",
                    tickfont=dict(size=11),
                )
                layout["yaxis2"] = dict(
                    title="Mortgage Rate (%)", overlaying="y", side="right",
                    gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11),
                )
                layout["legend"] = dict(orientation="h", y=-0.15, x=0, bgcolor="rgba(0,0,0,0)")
                layout["hovermode"] = "x unified"
                fig.update_layout(**layout)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Market factor data not available.")

    # ── Row 3: Category × Type price matrix ───────────────
    section_header("Price Intelligence Matrix: Category × Property Type")
    if not df_cat_type.empty:
        pivot = df_cat_type.pivot_table(
            index="property_category",
            columns="property_type",
            values="avg_price_sqft",
            aggfunc="mean",
        )
        cat_order = ["Affordable", "Mid-Market", "Premium", "Luxury", "Ultra-Luxury"]
        pivot = pivot.reindex([c for c in cat_order if c in pivot.index])

        fig = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[[0, "#0a1628"], [0.3, "#0e4a3a"], [0.6, colors["primary"]], [1, colors["gold"]]],
            text=[[f"AED {v:,.0f}" if not np.isnan(v) else "—" for v in row] for row in pivot.values],
            texttemplate="%{text}",
            textfont=dict(size=11, color="white"),
            colorbar=dict(
                title=dict(text="AED/sq.ft", font=dict(size=11)),
                thickness=14,
                tickfont=dict(size=10),
            ),
            hoverongaps=False,
        ))
        layout = plotly_dark_layout("", 320)
        layout["xaxis"]["tickangle"] = -15
        layout["margin"]["l"] = 120
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)

    # ── Investment metrics ─────────────────────────────────
    if not df_market.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        section_header("Investment & Economic Signals")
        col_e, col_f, col_g = st.columns(3)

        with col_e:
            if "foreign_investment_inflow_bn_aed" in df_market.columns:
                fi = df_market[["date", "foreign_investment_inflow_bn_aed"]].dropna()
                if not fi.empty:
                    fig = go.Figure(go.Scatter(
                        x=fi["date"], y=fi["foreign_investment_inflow_bn_aed"],
                        mode="lines",
                        line=dict(color=colors["indigo"], width=2),
                        fill="tozeroy", fillcolor="rgba(99,102,241,0.1)",
                        name="Foreign Inflows (AED Bn)",
                    ))
                    layout = plotly_dark_layout("Foreign Investment Inflows (AED Bn)", 260)
                    layout["showlegend"] = False
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

        with col_f:
            if "tourism_arrivals_index" in df_market.columns:
                tourism = df_market[["date", "city", "tourism_arrivals_index"]].dropna()
                if not tourism.empty:
                    t_agg = tourism.groupby("date")["tourism_arrivals_index"].mean().reset_index()
                    fig = go.Figure(go.Scatter(
                        x=t_agg["date"], y=t_agg["tourism_arrivals_index"],
                        mode="lines",
                        line=dict(color=colors["cyan"], width=2),
                        fill="tozeroy", fillcolor="rgba(6,182,212,0.1)",
                        name="Tourism Arrivals Index",
                    ))
                    layout = plotly_dark_layout("Tourism Arrivals Index", 260)
                    layout["showlegend"] = False
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)

        with col_g:
            if "uae_central_bank_base_rate_pct" in df_market.columns:
                cbr = df_market[["date", "uae_central_bank_base_rate_pct"]].drop_duplicates("date").dropna()
                if not cbr.empty:
                    fig = go.Figure(go.Scatter(
                        x=cbr["date"], y=cbr["uae_central_bank_base_rate_pct"],
                        mode="lines+markers",
                        line=dict(color=colors["gold"], width=2),
                        marker=dict(size=5),
                        name="UAE CB Base Rate",
                    ))
                    layout = plotly_dark_layout("UAE Central Bank Base Rate (%)", 260)
                    layout["showlegend"] = False
                    fig.update_layout(**layout)
                    st.plotly_chart(fig, use_container_width=True)
