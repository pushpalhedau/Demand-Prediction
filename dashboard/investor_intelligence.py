import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.queries import (
    get_rental_yield_by_city,
    get_investor_roi_data,
    get_golden_visa_stats,
    get_investor_segment_breakdown,
    get_sales_by_property_category,
)
from utils.helpers import (
    render_kpi_card, fmt_aed, fmt_number,
    get_re_colors, plotly_dark_layout, section_header,
)


def render_investor_intelligence(filters: dict):
    colors = get_re_colors()

    st.markdown("""<p class="subtitle-text">
        Investor intelligence — rental yields, ROI benchmarks, capital appreciation,
        Golden Visa transactions and investor segment profiling across UAE markets.
    </p>""", unsafe_allow_html=True)

    session = get_db_session()
    try:
        df_city_yield = get_rental_yield_by_city(session)
        df_roi = get_investor_roi_data(session, filters)
        gv_stats = get_golden_visa_stats(session, filters)
        df_segments = get_investor_segment_breakdown(session)
        df_cats = get_sales_by_property_category(session, filters)
    finally:
        session.close()

    # ── KPI Row ───────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    avg_yield = df_city_yield["gross_yield"].mean() if not df_city_yield.empty else 0
    avg_roi = df_roi["roi"].mean() if not df_roi.empty else 0
    avg_cap = df_roi["capital_appreciation"].mean() if not df_roi.empty else 0

    with c1:
        render_kpi_card("Avg Gross Yield", f"{avg_yield:.2f}%",
                        is_positive=avg_yield > 5)
    with c2:
        render_kpi_card("Avg ROI", f"{avg_roi:.2f}%", is_positive=avg_roi > 8)
    with c3:
        render_kpi_card("Avg Capital Appreciation", f"{avg_cap:.2f}%",
                        is_positive=avg_cap > 0)
    with c4:
        render_kpi_card("Golden Visa Txns", f"{gv_stats.get('golden_visa_transactions', 0):,}",
                        delta=f"{gv_stats.get('golden_visa_share_pct', 0):.1f}% of all",
                        is_positive=True)
    with c5:
        render_kpi_card("GV Buyer Intent", f"{gv_stats.get('buyers_with_intent', 0):,}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Yield by city + ROI by category ────────────
    col_a, col_b = st.columns(2)

    with col_a:
        section_header("Gross & Net Yield by City")
        if not df_city_yield.empty:
            fig = go.Figure()
            city_colors = [colors["city"].get(c, colors["primary"]) for c in df_city_yield["city"]]
            fig.add_trace(go.Bar(
                x=df_city_yield["city"], y=df_city_yield["gross_yield"],
                name="Gross Yield %", marker=dict(color=city_colors, opacity=0.85, line=dict(width=0)),
                text=[f"{v:.2f}%" for v in df_city_yield["gross_yield"]],
                textposition="outside", textfont=dict(size=10, color="#94a3b8"),
            ))
            fig.add_trace(go.Bar(
                x=df_city_yield["city"], y=df_city_yield["net_yield"],
                name="Net Yield %", marker=dict(color=colors["indigo"], opacity=0.65, line=dict(width=0)),
                text=[f"{v:.2f}%" for v in df_city_yield["net_yield"]],
                textposition="outside", textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 360)
            layout["barmode"] = "group"
            layout["yaxis"]["title"] = "Yield %"
            layout["legend"] = dict(orientation="h", y=-0.18, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section_header("ROI & Capital Appreciation by Category")
        if not df_roi.empty:
            by_cat = df_roi.groupby("property_category").agg(
                roi=("roi", "mean"),
                capital_appreciation=("capital_appreciation", "mean"),
                rental_yield=("rental_yield", "mean"),
            ).reset_index().sort_values("roi", ascending=False)
            cat_colors = [
                colors["property_category"].get(c, colors["primary"])
                for c in by_cat["property_category"]
            ]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=by_cat["property_category"], y=by_cat["roi"],
                name="ROI %", marker=dict(color=cat_colors, opacity=0.85, line=dict(width=0)),
            ))
            fig.add_trace(go.Scatter(
                x=by_cat["property_category"], y=by_cat["capital_appreciation"],
                name="Capital Appreciation %",
                line=dict(color=colors["gold"], width=2.5),
                mode="lines+markers", marker=dict(size=8),
            ))
            layout = plotly_dark_layout("", 360)
            layout["yaxis"]["title"] = "% Return"
            layout["legend"] = dict(orientation="h", y=-0.18, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Investor segment breakdown ─────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_header("Investor Segment Profile")
    if not df_segments.empty:
        col_c, col_d = st.columns([3, 2])

        with col_c:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_segments["buyer_type"], y=df_segments["count"],
                name="Count",
                marker=dict(color=colors["colors_seq"][:len(df_segments)], line=dict(width=0)),
            ))
            fig.add_trace(go.Scatter(
                x=df_segments["buyer_type"], y=df_segments["avg_budget"] / 1e6,
                name="Avg Budget (AED M)", yaxis="y2",
                line=dict(color=colors["gold"], width=2.5),
                mode="lines+markers", marker=dict(size=8),
            ))
            layout = plotly_dark_layout("", 340)
            layout["yaxis"]["title"] = "Buyer Count"
            layout["yaxis2"] = dict(
                title=dict(text="Avg Budget (AED M)", font=dict(color=colors["gold"])),
                overlaying="y", side="right",
                gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11),
            )
            layout["legend"] = dict(orientation="h", y=-0.2, bgcolor="rgba(0,0,0,0)")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)

        with col_d:
            tbl = df_segments[[
                "buyer_type", "count", "avg_budget", "gv_intent", "off_plan"
            ]].copy()
            tbl["avg_budget"] = tbl["avg_budget"].apply(lambda v: fmt_aed(v) if pd.notna(v) else "—")
            tbl["gv_intent"] = tbl["gv_intent"].apply(lambda v: f"{int(v):,}" if pd.notna(v) else "0")
            tbl["off_plan"] = tbl["off_plan"].apply(lambda v: f"{int(v):,}" if pd.notna(v) else "0")
            st.dataframe(
                tbl.rename(columns={
                    "buyer_type": "Buyer Type",
                    "count": "Count",
                    "avg_budget": "Avg Budget",
                    "gv_intent": "GV Intent",
                    "off_plan": "Off-Plan",
                }),
                use_container_width=True,
                hide_index=True,
            )

    # ── Row 3: Golden Visa + Top ROI localities ────────────
    col_e, col_f = st.columns(2)

    with col_e:
        section_header("Golden Visa Transaction Split")
        gv_txns = gv_stats.get("golden_visa_transactions", 0)
        total_txns = gv_stats.get("total_transactions", 1)
        non_gv = total_txns - gv_txns
        fig = go.Figure(go.Pie(
            labels=["Golden Visa Eligible", "Standard Transactions"],
            values=[gv_txns, non_gv],
            hole=0.58,
            marker=dict(
                colors=[colors["gold"], colors["muted"]],
                line=dict(color="#080d18", width=2),
            ),
            textinfo="percent+label",
            textfont=dict(size=11),
        ))
        layout = plotly_dark_layout("", 320)
        layout["showlegend"] = False
        layout["annotations"] = [dict(
            text=f"<b>{gv_stats.get('golden_visa_share_pct', 0):.1f}%</b><br>GV Share",
            x=0.5, y=0.5, font=dict(size=13, color=colors["gold"]),
            showarrow=False,
        )]
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)

    with col_f:
        section_header("Top ROI Property Type × City")
        if not df_roi.empty:
            top = df_roi.head(12).copy()
            fig = go.Figure(go.Bar(
                x=top["roi"],
                y=top["city"] + " · " + top["property_type"],
                orientation="h",
                marker=dict(
                    color=top["roi"],
                    colorscale=[[0, "#1a3350"], [0.5, colors["primary"]], [1, colors["gold"]]],
                    line=dict(width=0),
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="ROI %", font=dict(size=10)),
                        thickness=12, tickfont=dict(size=10),
                    ),
                ),
                text=[f"{v:.1f}%" for v in top["roi"]],
                textposition="outside",
                textfont=dict(size=10, color="#94a3b8"),
            ))
            layout = plotly_dark_layout("", 320)
            layout["xaxis"]["title"] = "ROI %"
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 160
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)
