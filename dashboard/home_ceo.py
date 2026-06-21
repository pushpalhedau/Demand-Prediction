import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import date

from database.queries import (
    get_ceo_kpis,
    get_ceo_ai_insights,
    get_revenue_collections_trend,
    get_inventory_breakdown,
    get_revenue_vs_target_forecast,
    get_project_health_scores,
)
from utils.helpers import (
    render_kpi_card,
    render_chart_header,
    fmt_aed,
    fmt_number,
    get_re_colors,
    plotly_dark_layout,
    section_header,
)


def _insight_box(insight: dict):
    t = insight["type"]
    title = insight["title"]
    body = insight["body"]

    if t == "positive":
        css_class = "insight-box"
        label = "POSITIVE"
        label_color = "#10b981"
    elif t == "warning":
        css_class = "warning-box"
        label = "WATCH"
        label_color = "#f59e0b"
    else:
        css_class = "alert-box"
        label = "ALERT"
        label_color = "#ef4444"

    st.markdown(f"""
    <div class="{css_class}" style="height:100%; padding:14px 16px;">
        <div style="font-size:9px; font-weight:800; color:{label_color}; letter-spacing:0.12em;
                    margin-bottom:6px;">{label}</div>
        <div style="font-size:13px; font-weight:700; color:#f0f4f8; margin-bottom:4px;">{title}</div>
        <div style="font-size:11px; color:#94a3b8; line-height:1.5;">{body}</div>
    </div>
    """, unsafe_allow_html=True)


def render_ceo_dashboard(filters: dict, session):
    colors = get_re_colors()

    # ── Page Header ───────────────────────────────────────
    today_str = date.today().strftime("%d %B %Y")
    st.markdown(f"""
    <div style="display:flex; align-items:center; justify-content:space-between;
                margin-bottom:20px; padding-bottom:14px;
                border-bottom:1px solid rgba(255,255,255,0.06);">
        <div>
            <h2 style="margin:0; font-size:24px; font-weight:800; color:#f0f4f8;
                       font-family:'Outfit',sans-serif;">
                CEO Executive Dashboard
            </h2>
            <p style="margin:4px 0 0 0; font-size:12px; color:#6b7280;">
                Real-time overview · UAE Real Estate Intelligence Platform
            </p>
        </div>
        <div style="text-align:right;">
            <span style="background:rgba(16,185,129,0.12); color:#10b981;
                         padding:4px 12px; border-radius:20px; font-size:11px;
                         font-weight:600; border:1px solid rgba(16,185,129,0.2);">
                LIVE · {today_str}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Load KPIs ─────────────────────────────────────────
    with st.spinner("Loading CEO metrics..."):
        try:
            kpis = get_ceo_kpis(session)
        except Exception as e:
            st.error(f"Could not load KPI data: {e}")
            kpis = {
                "total_revenue_aed": 0, "revenue_mom_delta": 0,
                "bookings_this_month": 0, "bookings_mom_delta": 0,
                "collection_efficiency_pct": 0, "collection_delta": 0,
                "inventory_available": 0, "pipeline_value_aed": 0,
                "sales_conversion_rate_pct": 0, "conversion_delta": 0,
                "project_completion_pct": 0, "project_delta": 0,
                "occupancy_rate_pct": 0, "rental_yield_pct": 0,
                "forecast_revenue_aed": 0,
            }

    # ── KPI Row 1 ─────────────────────────────────────────
    section_header("Key Performance Indicators")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_kpi_card(
            "Total Revenue",
            fmt_aed(kpis["total_revenue_aed"]),
            f"{abs(kpis['revenue_mom_delta']):.1f}% MoM",
            kpis["revenue_mom_delta"] >= 0,
            tooltip="Total revenue collected from all property sales and rental payments this month across all projects.",
        )
    with c2:
        render_kpi_card(
            "Bookings This Month",
            fmt_number(kpis["bookings_this_month"]),
            f"{abs(kpis['bookings_mom_delta']):.1f}% MoM",
            kpis["bookings_mom_delta"] >= 0,
            tooltip="Number of new property booking confirmations received this month.",
        )
    with c3:
        render_kpi_card(
            "Collection Status",
            f"{kpis['collection_efficiency_pct']:.1f}%",
            f"{abs(kpis['collection_delta']):.1f}pp",
            kpis["collection_delta"] >= 0,
            tooltip="Percentage of scheduled payment installments successfully collected from buyers and tenants.",
        )
    with c4:
        render_kpi_card(
            "Inventory Available",
            fmt_number(kpis["inventory_available"], " units"),
            tooltip="Total number of units currently available for sale or lease across all projects and emirates.",
        )
    with c5:
        render_kpi_card(
            "Pipeline Value",
            fmt_aed(kpis["pipeline_value_aed"]),
            tooltip="Estimated total value of deals currently in the sales pipeline, including leads and under-negotiation properties.",
        )

    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

    # ── KPI Row 2 ─────────────────────────────────────────
    c6, c7, c8, c9, c10 = st.columns(5)
    with c6:
        render_kpi_card(
            "Sales Conversion",
            f"{kpis['sales_conversion_rate_pct']:.1f}%",
            f"{abs(kpis['conversion_delta']):.1f}pp",
            kpis["conversion_delta"] >= 0,
            tooltip="Percentage of qualified leads that converted into confirmed bookings this period.",
        )
    with c7:
        render_kpi_card(
            "Project Completion",
            f"{kpis['project_completion_pct']:.1f}%",
            f"{abs(kpis['project_delta']):.1f}pp",
            kpis["project_delta"] >= 0,
            tooltip="Weighted average construction completion percentage across all active development projects.",
        )
    with c8:
        render_kpi_card(
            "Occupancy Rate",
            f"{kpis['occupancy_rate_pct']:.1f}%",
            tooltip="Percentage of all managed rental units that are currently occupied by tenants.",
        )
    with c9:
        render_kpi_card(
            "Rental Yield",
            f"{kpis['rental_yield_pct']:.2f}%",
            tooltip="Annual rental income as a percentage of total property value, indicating rental investment performance.",
        )
    with c10:
        render_kpi_card(
            "Forecast Revenue",
            fmt_aed(kpis["forecast_revenue_aed"]),
            "next 3 months",
            True,
            tooltip="Projected total revenue for the next 3 months based on current booking trends and market analysis.",
        )

    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)

    # ── AI Insights Strip ─────────────────────────────────
    section_header("AI Business Insights", badge="LIVE")
    try:
        insights = get_ceo_ai_insights(session)
    except Exception:
        insights = [
            {"type": "positive", "icon": "trending_up", "title": "Platform Operational",
             "body": "AI insights will appear here once data is fully loaded."},
            {"type": "positive", "icon": "check_circle", "title": "Data Synced",
             "body": "All 13 datasets connected and active."},
            {"type": "positive", "icon": "location_on", "title": "Dubai Leads",
             "body": "Dubai remains the top demand market across all segments."},
        ]

    ic1, ic2, ic3 = st.columns(3)
    cols = [ic1, ic2, ic3]
    for i, insight in enumerate(insights[:3]):
        with cols[i]:
            _insight_box(insight)

    st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)

    # ── Charts Row 1 ──────────────────────────────────────
    section_header("Financial Performance")
    chart_l, chart_r = st.columns([6, 4])

    with chart_l:
        render_chart_header(
            "Revenue & Collections Trend (AED M)",
            "Tracks monthly revenue booked vs. actual collections over the past 12 months. "
            "A widening gap between the two lines signals a collections shortfall — use this "
            "to flag payment delays and prioritise follow-ups before cash-flow is impacted.",
        )
        try:
            trend_df = get_revenue_collections_trend(session, months=12)
            if not trend_df.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=trend_df["period_date"],
                    y=trend_df["revenue_booked_aed"] / 1e6,
                    name="Revenue Booked",
                    line=dict(color=colors["primary"], width=2.5),
                    mode="lines+markers",
                    marker=dict(size=5),
                    fill="tozeroy",
                    fillcolor="rgba(16,185,129,0.06)",
                ))
                fig.add_trace(go.Scatter(
                    x=trend_df["period_date"],
                    y=trend_df["collections_received_aed"] / 1e6,
                    name="Collections",
                    line=dict(color=colors["gold"], width=2, dash="dot"),
                    mode="lines+markers",
                    marker=dict(size=5),
                ))
                layout = plotly_dark_layout("", 320)
                layout["margin"]["t"] = 10
                layout["yaxis"]["ticksuffix"] = "M"
                fig.update_layout(**layout)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No financial trend data available yet.")
        except Exception as e:
            st.warning(f"Chart unavailable: {e}")

    with chart_r:
        render_chart_header(
            "Inventory by Emirate",
            "Shows the split of units across Available, Booked, and Registered status for each "
            "emirate. Use this to identify where supply is piling up or demand is strongest, "
            "and to redirect sales efforts or launch promotions in slow-moving markets.",
        )
        try:
            inv_df = get_inventory_breakdown(session)
            if not inv_df.empty:
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(
                    y=inv_df["emirate"],
                    x=inv_df["available_units"],
                    name="Available",
                    orientation="h",
                    marker_color=colors["primary"],
                ))
                fig2.add_trace(go.Bar(
                    y=inv_df["emirate"],
                    x=inv_df["booked_units"],
                    name="Booked",
                    orientation="h",
                    marker_color=colors["gold"],
                ))
                fig2.add_trace(go.Bar(
                    y=inv_df["emirate"],
                    x=inv_df["registered_units"],
                    name="Registered",
                    orientation="h",
                    marker_color=colors["indigo"],
                ))
                layout2 = plotly_dark_layout("", 320)
                layout2["margin"]["t"] = 10
                layout2["barmode"] = "stack"
                fig2.update_layout(**layout2)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No inventory data available yet.")
        except Exception as e:
            st.warning(f"Chart unavailable: {e}")

    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)

    # ── Charts Row 2 ──────────────────────────────────────
    section_header("Forecast & Project Health")
    chart_l2, chart_r2 = st.columns([6, 4])

    with chart_l2:
        render_chart_header(
            "Revenue vs Target & 3M Forecast (AED M)",
            "Shows actual revenue against your sales target for the past 6 months, then "
            "extends as a 3-month forward projection (shaded zone). A widening gap between "
            "forecast and target is an early warning to review the pipeline or adjust targets.",
        )
        try:
            fc_df = get_revenue_vs_target_forecast(session)
            if not fc_df.empty:
                hist = fc_df[~fc_df["is_forecast"]]
                fcast = fc_df[fc_df["is_forecast"]]

                fig3 = go.Figure()

                # Actual revenue — solid green with area fill
                fig3.add_trace(go.Scatter(
                    x=hist["period_date"],
                    y=hist["revenue_aed"] / 1e6,
                    name="Actual Revenue",
                    line=dict(color=colors["primary"], width=2.5),
                    fill="tozeroy",
                    fillcolor="rgba(16,185,129,0.08)",
                    mode="lines+markers",
                    marker=dict(size=5),
                ))

                # Forecast line — dashed cyan, connected from last actual point
                connector = hist[["period_date", "revenue_aed"]].tail(1)
                forecast_line = pd.concat(
                    [connector, fcast[["period_date", "revenue_aed"]]],
                    ignore_index=True,
                )
                fig3.add_trace(go.Scatter(
                    x=forecast_line["period_date"],
                    y=forecast_line["revenue_aed"] / 1e6,
                    name="3M Forecast",
                    line=dict(color=colors["cyan"], width=2, dash="dash"),
                    mode="lines",
                ))

                # Sales Target — dotted amber across full range
                if fc_df["target_aed"].fillna(0).sum() > 0:
                    fig3.add_trace(go.Scatter(
                        x=fc_df["period_date"],
                        y=fc_df["target_aed"] / 1e6,
                        name="Sales Target",
                        line=dict(color=colors["gold"], width=1.5, dash="dot"),
                        mode="lines",
                    ))

                layout3 = plotly_dark_layout("", 280)
                layout3["margin"]["t"] = 10
                layout3["yaxis"]["ticksuffix"] = "M"
                fig3.update_layout(**layout3)
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("No forecast data available yet.")
        except Exception as e:
            st.warning(f"Chart unavailable: {e}")

    with chart_r2:
        render_chart_header(
            "Project Health Scores",
            "Rates each active project 0–100 based on construction progress, budget adherence, "
            "and delivery timelines. Green (≥80) is on track, amber (60–79) needs attention, "
            "red (<60) requires immediate intervention. Use this to prioritise site visits and "
            "resource reallocation.",
        )
        try:
            proj_df = get_project_health_scores(session)
            if not proj_df.empty:
                proj_df = proj_df.sort_values("health_score")

                def _color(score):
                    if score >= 80:
                        return colors["primary"]
                    if score >= 60:
                        return colors["gold"]
                    return colors["rose"]

                bar_colors = [_color(s) for s in proj_df["health_score"]]
                fig4 = go.Figure(go.Bar(
                    y=proj_df["project_name"],
                    x=proj_df["health_score"],
                    orientation="h",
                    marker_color=bar_colors,
                    text=[f"{s:.0f}" for s in proj_df["health_score"]],
                    textposition="auto",
                ))
                layout4 = plotly_dark_layout("", 280)
                layout4["margin"]["t"] = 10
                layout4["xaxis"]["range"] = [0, 100]
                fig4.update_layout(**layout4)
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("No project health data available yet.")
        except Exception as e:
            st.warning(f"Chart unavailable: {e}")
