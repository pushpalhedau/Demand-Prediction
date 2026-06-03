import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.queries import get_yoy_comparison, get_sales_by_city, get_sales_by_property_category, get_unique_filter_options
from utils.helpers import get_re_colors, plotly_dark_layout, section_header, fmt_aed


def render_comparison(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Year-over-year and multi-dimensional comparisons — track growth momentum across cities,
        property segments, and seasonal patterns.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        df_yoy = get_yoy_comparison(session, filters)
        df_cities = get_sales_by_city(session, filters)
        df_cats = get_sales_by_property_category(session, filters)
        opts = get_unique_filter_options(session)
    finally:
        session.close()

    # ── YoY Monthly Volume ────────────────────────────────
    section_header("Year-on-Year Monthly Transaction Volume", icon="📅")
    if not df_yoy.empty:
        years = sorted(df_yoy["year"].unique())
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        tab_units, tab_rev, tab_sqft = st.tabs(["Units Transacted", "Revenue (AED M)", "Avg Price/Sq.Ft"])

        with tab_units:
            fig = go.Figure()
            palette = [colors["primary"], colors["gold"], colors["indigo"],
                       colors["cyan"], colors["rose"]]
            for i, yr in enumerate(years):
                yr_df = df_yoy[df_yoy["year"] == yr].sort_values("month")
                fig.add_trace(go.Scatter(
                    x=[month_names[m - 1] for m in yr_df["month"]],
                    y=yr_df["units"], name=str(yr), mode="lines+markers",
                    line=dict(color=palette[i % len(palette)], width=2.5),
                    marker=dict(size=5),
                ))
            layout = plotly_dark_layout("", 380)
            layout["yaxis"]["title"] = "Units Transacted"
            layout["hovermode"] = "x unified"
            layout["legend"] = dict(orientation="h", y=-0.15, x=0, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with tab_rev:
            fig = go.Figure()
            for i, yr in enumerate(years):
                yr_df = df_yoy[df_yoy["year"] == yr].sort_values("month")
                fig.add_trace(go.Bar(
                    x=[month_names[m - 1] for m in yr_df["month"]],
                    y=yr_df["revenue"] / 1e6, name=str(yr),
                    marker_color=palette[i % len(palette)],
                    opacity=0.8,
                ))
            layout = plotly_dark_layout("", 380)
            layout["yaxis"]["title"] = "Revenue (AED Millions)"
            layout["barmode"] = "group"
            layout["legend"] = dict(orientation="h", y=-0.15, x=0, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with tab_sqft:
            fig = go.Figure()
            for i, yr in enumerate(years):
                yr_df = df_yoy[df_yoy["year"] == yr].sort_values("month")
                fig.add_trace(go.Scatter(
                    x=[month_names[m - 1] for m in yr_df["month"]],
                    y=yr_df["avg_price_sqft"], name=str(yr), mode="lines+markers",
                    line=dict(color=palette[i % len(palette)], width=2),
                    marker=dict(size=5),
                ))
            layout = plotly_dark_layout("", 380)
            layout["yaxis"]["title"] = "Avg Price/Sq.Ft (AED)"
            layout["hovermode"] = "x unified"
            layout["legend"] = dict(orientation="h", y=-0.15, x=0, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── City comparison ───────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        section_header("City Performance Comparison", icon="🏙")
        if not df_cities.empty:
            top_cities = df_cities.head(10)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Units",
                x=top_cities["city"],
                y=top_cities["units"],
                marker_color=colors["primary"],
                yaxis="y",
            ))
            fig.add_trace(go.Scatter(
                name="Avg Price/Sq.Ft (AED)",
                x=top_cities["city"],
                y=top_cities["avg_price_sqft"],
                mode="markers",
                marker=dict(
                    size=top_cities["units"] / top_cities["units"].max() * 24 + 8,
                    color=colors["gold"],
                    line=dict(color="#080d18", width=1.5),
                ),
                yaxis="y2",
            ))
            layout = plotly_dark_layout("", 380)
            layout["yaxis"] = dict(title="Units", gridcolor="rgba(255,255,255,0.04)")
            layout["yaxis2"] = dict(
                title="Avg Price/Sq.Ft (AED)", overlaying="y", side="right",
                gridcolor="rgba(0,0,0,0)",
            )
            layout["xaxis"]["tickangle"] = -20
            layout["legend"] = dict(orientation="h", y=-0.2, x=0, bgcolor="rgba(0,0,0,0)")
            layout["barmode"] = "overlay"
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section_header("Category Revenue Share", icon="🏷")
        if not df_cats.empty:
            # Waterfall chart
            df_cats_sorted = df_cats.sort_values("revenue", ascending=False)
            cat_colors = [
                colors["property_category"].get(c, colors["primary"])
                for c in df_cats_sorted["property_category"]
            ]
            fig = go.Figure(go.Bar(
                x=df_cats_sorted["property_category"],
                y=df_cats_sorted["revenue"] / 1e6,
                marker=dict(color=cat_colors, line=dict(width=0)),
                text=[f"AED {v:.0f}M<br>{u:,} units" for v, u in
                      zip(df_cats_sorted["revenue"] / 1e6, df_cats_sorted["units"])],
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 380)
            layout["yaxis"]["title"] = "Revenue (AED Millions)"
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Quarter seasonality heatmap ───────────────────────
    section_header("Quarterly Demand Pattern (Units)", icon="🌡")
    if not df_yoy.empty and "quarter" not in df_yoy.columns:
        df_yoy["quarter"] = df_yoy["month"].apply(
            lambda m: f"Q{(m - 1) // 3 + 1}"
        )

    if not df_yoy.empty:
        qtr_heatmap = df_yoy.groupby(["year", "quarter"])["units"].sum().reset_index()
        pivot = qtr_heatmap.pivot(index="year", columns="quarter", values="units")
        pivot = pivot.reindex(columns=["Q1", "Q2", "Q3", "Q4"])

        fig = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=[str(y) for y in pivot.index.tolist()],
            colorscale=[[0, "#0a1628"], [0.5, colors["primary"]], [1, colors["gold"]]],
            text=[[f"{v:,.0f}" if v == v else "—" for v in row] for row in pivot.values],
            texttemplate="%{text}",
            textfont=dict(size=13, color="white"),
            colorbar=dict(title="Units", thickness=14, tickfont=dict(size=10)),
            hoverongaps=False,
        ))
        layout = plotly_dark_layout("", 280)
        layout["margin"]["l"] = 60
        layout["xaxis"]["title"] = "Quarter"
        layout["yaxis"]["title"] = "Year"
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)

    # ── Festival period impact ─────────────────────────────
    section_header("Festival vs Non-Festival Transaction Volume", icon="🎉")
    if not df_yoy.empty:
        # Approximate: Q3 (Jul-Sep) has Navratri/Diwali season beginning, Q4 has Diwali
        festival_months = [3, 4, 9, 10, 12]  # Ramadan (varies), post-Ramadan, Cityscape, Q4 push
        df_yoy["is_festival"] = df_yoy["month"].isin(festival_months)
        fest_agg = df_yoy.groupby("is_festival")["units"].mean().reset_index()
        fest_agg["label"] = fest_agg["is_festival"].map({True: "Festival Months", False: "Regular Months"})

        col_f1, col_f2, col_f3 = st.columns([1, 2, 1])
        with col_f2:
            fig = go.Figure(go.Bar(
                x=fest_agg["label"],
                y=fest_agg["units"],
                marker_color=[colors["gold"], colors["indigo"]],
                text=[f"{v:,.0f} avg units/month" for v in fest_agg["units"]],
                textposition="outside",
                textfont=dict(size=12, color="#94a3b8"),
                width=0.5,
            ))
            layout = plotly_dark_layout("Avg Monthly Transactions: Festival vs Regular", 300)
            layout["yaxis"]["title"] = "Avg Units/Month"
            layout["showlegend"] = False
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        if len(fest_agg) == 2:
            fest_val = fest_agg[fest_agg["is_festival"]]["units"].values[0]
            reg_val = fest_agg[~fest_agg["is_festival"]]["units"].values[0]
            uplift = ((fest_val - reg_val) / reg_val) * 100 if reg_val > 0 else 0
            st.markdown(f"""<div class="insight-box" style="text-align:center">
                Festival months generate <b>{uplift:+.1f}%</b> more transactions than regular months.
                Key drivers: Diwali, Navratri, Akshaya Tritiya, Gudi Padwa booking surges.
            </div>""", unsafe_allow_html=True)
