"""
Sentiment Analysis Dashboard — 5 sub-tabs.

Tab 1: Sentiment Intelligence   — news timeline, sentiment trend, article feed
Tab 2: Geopolitical Risk        — risk gauge, event timeline, high-impact articles
Tab 3: Economic Signals         — economic tone trends, category heatmap
Tab 4: Forecast Comparison      — baseline Prophet vs sentiment-enhanced (Step 6 integration point)
Tab 5: AI Insights              — Grok-generated market briefing
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date, timedelta

from utils.helpers import render_kpi_card, get_color_palette
from sentiment.signal_processor import (
    run_full_pipeline,
    get_daily_summaries,
    get_overall_sentiment_stats,
    get_category_sentiment_summary,
)
from sentiment.fetchers.gdelt_fetcher import get_stored_articles, get_article_stats, TIMESPAN_OPTIONS
from sentiment.analyzers.grok_analyzer import is_live_mode, generate_market_briefing


# ─────────────────────────────────────────────────────────────────────────────
# Chart styling helpers (mirrors existing dashboard style)
# ─────────────────────────────────────────────────────────────────────────────

_GRID = dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)")

def _layout(**overrides) -> dict:
    """
    Build a Plotly update_layout dict with the shared dark-theme base styles.
    Per-chart overrides are deep-merged for nested keys (xaxis, yaxis, etc.)
    so that callers can pass yaxis=dict(title=...) without a duplicate-key error.
    """
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f3f4f6", family="Plus Jakarta Sans"),
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(**_GRID),
        yaxis=dict(**_GRID),
    )
    for key, val in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            base[key] = {**base[key], **val}   # merge nested dict (e.g. yaxis)
        else:
            base[key] = val
    return base

_DIRECTION_COLORS = {"up": "#10b981", "down": "#ef4444", "neutral": "#9ca3af"}
_RISK_COLORS      = {"low": "#10b981",  "medium": "#f59e0b", "high": "#ef4444"}


def _glass_card(html: str):
    st.markdown(
        f"""<div style="background:rgba(17,24,39,0.7);backdrop-filter:blur(12px);
        border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:20px;
        margin-bottom:12px;">{html}</div>""",
        unsafe_allow_html=True,
    )


def _badge(label: str, color: str) -> str:
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}44;'
        f'border-radius:6px;padding:2px 8px;font-size:12px;font-weight:600;">{label}</span>'
    )


def _mode_banner():
    live = is_live_mode()
    color = "#10b981" if live else "#f59e0b"
    label = "LIVE  —  Grok AI analysis enabled" if live else "MOCK  —  Keyword-based scoring  |  Set XAI_API_KEY in .env to enable Grok AI"
    st.markdown(
        f'<div style="background:{color}18;border-left:4px solid {color};border-radius:8px;'
        f'padding:10px 16px;margin-bottom:18px;color:{color};font-size:13px;">'
        f'<b>Mode:</b> {label}</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_sentiment_analysis(filters: dict):
    colors = get_color_palette()

    st.markdown(
        "<h2 class='gradient-text' style='margin-bottom:8px;'>Sentiment Intelligence Platform</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#9ca3af;font-size:14px;margin-bottom:20px;'>"
        "Real-time geopolitical, economic & social sentiment signals for UAE automobile demand forecasting.</p>",
        unsafe_allow_html=True,
    )

    _mode_banner()

    # ── Refresh controls ──────────────────────────────────────────────────
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 2, 4])
    with ctrl_col1:
        timespan_label = st.selectbox(
            "Fetch window",
            options=list(TIMESPAN_OPTIONS.keys()),
            index=1,
            key="sentiment_timespan",
        )
        timespan = TIMESPAN_OPTIONS[timespan_label]

    with ctrl_col2:
        st.markdown("<div style='margin-top:28px;'>", unsafe_allow_html=True)
        refresh = st.button("Refresh Data", type="primary", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if refresh:
        with st.spinner("Fetching news from GDELT and analysing signals..."):
            status = run_full_pipeline(
                timespan=timespan,
                max_articles_per_query=50,
                analyze_limit=200,
            )
        st.session_state["sentiment_pipeline_status"] = status
        _show_pipeline_status(status)
        st.rerun()

    if "sentiment_pipeline_status" in st.session_state:
        _show_pipeline_status(st.session_state["sentiment_pipeline_status"])

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 4 Sub-tabs ────────────────────────────────────────────────────────
    tab2, tab3, tab4, tab5 = st.tabs([
        # "Sentiment Intelligence",
        "Geopolitical Risk",
        "Economic Signals",
        "Forecast Comparison",
        "AI Insights",
    ])

    # with tab1:
    #     _render_sentiment_intelligence(colors)

    with tab2:
        _render_geopolitical_risk(colors)

    with tab3:
        _render_economic_signals(colors)

    with tab4:
        _render_forecast_comparison(filters, colors)

    with tab5:
        _render_ai_insights(colors)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 1 — Sentiment Intelligence
# ─────────────────────────────────────────────────────────────────────────────

def _render_sentiment_intelligence(colors: dict):
    st.markdown("### Sentiment Intelligence")

    stats = get_overall_sentiment_stats()
    art_stats = get_article_stats()

    # KPI Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        sent_val = stats.get("avg_sentiment", 0.0)
        trend    = stats.get("trend_7d", 0.0)
        render_kpi_card(
            "Avg Sentiment Score",
            f"{sent_val:+.3f}",
            delta=f"{trend:+.3f} vs prior week",
            is_positive=trend >= 0,
        )
    with c2:
        total  = art_stats.get("total_articles", 0)
        pending = art_stats.get("pending_analysis", 0)
        render_kpi_card(
            "Articles Analysed",
            f"{total - pending:,}",
            delta=f"{pending} pending analysis",
            is_positive=pending == 0,
        )
    with c3:
        direction = stats.get("dominant_direction", "neutral").upper()
        pos_pct   = stats.get("positive_pct", 0.0)
        render_kpi_card(
            "Demand Direction",
            direction,
            delta=f"{pos_pct:.0f}% positive signals",
            is_positive=direction == "UP",
        )
    with c4:
        geo = stats.get("geopolitical_risk", 0.0)
        risk_label = "HIGH" if geo > 0.4 else ("MEDIUM" if geo > 0.2 else "LOW")
        render_kpi_card(
            "Geopolitical Risk",
            f"{geo:.3f}",
            delta=risk_label,
            is_positive=geo <= 0.2,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Sentiment timeline
    st.markdown("#### Daily Sentiment Score by Vehicle Category")
    df_all = get_daily_summaries(days_back=90, vehicle_category=None)
    cat_df  = get_category_sentiment_summary(days_back=90)

    if not cat_df.empty:
        cat_df["date"] = pd.to_datetime(cat_df["date"])
        fig = go.Figure()
        for i, cat in enumerate(cat_df["category"].unique()):
            sub = cat_df[cat_df["category"] == cat].sort_values("date")
            fig.add_trace(go.Scatter(
                x=sub["date"], y=sub["sentiment"],
                name=cat, mode="lines+markers",
                line=dict(color=colors["colors_seq"][i % len(colors["colors_seq"])], width=2),
                marker=dict(size=6),
                hovertemplate=f"<b>{cat}</b><br>Date: %{{x|%d %b %Y}}<br>Sentiment: %{{y:+.3f}}<extra></extra>",
            ))
        # Neutral band
        fig.add_hrect(y0=-0.15, y1=0.15, fillcolor="rgba(156,163,175,0.08)",
                      line_width=0, annotation_text="Neutral Zone", annotation_position="right")
        fig.add_hline(y=0, line_dash="dot", line_color="rgba(156,163,175,0.3)")
        fig.update_layout(**_layout(
            height=340,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="Sentiment Score", range=[-1.1, 1.1]),
        ))
        st.plotly_chart(fig, use_container_width=True)
    elif not df_all.empty:
        # Fallback: show "All" category line
        df_all["summary_date"] = pd.to_datetime(df_all["summary_date"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_all["summary_date"], y=df_all["avg_sentiment_score"],
            name="Overall Sentiment", mode="lines+markers",
            line=dict(color=colors["primary"], width=2.5),
            fill="tozeroy", fillcolor="rgba(99,102,241,0.08)",
        ))
        fig.update_layout(**_layout(height=300))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No sentiment data available. Click **Refresh Data** to fetch the latest news.")

    st.markdown("<br>", unsafe_allow_html=True)

    # Sentiment distribution + top categories side by side
    left, right = st.columns(2)
    with left:
        st.markdown("#### Signal Distribution (Last 30 Days)")
        if stats.get("total_articles", 0) > 0:
            total = stats["total_articles"]
            pos_p = stats["positive_pct"]
            neg_p = stats["negative_pct"]
            neu_p = max(0.0, 100.0 - pos_p - neg_p)
            dist_fig = go.Figure(go.Pie(
                labels=["Positive", "Neutral", "Negative"],
                values=[pos_p, neu_p, neg_p],
                hole=0.5,
                marker_colors=["#10b981", "#9ca3af", "#ef4444"],
                textinfo="label+percent",
                hovertemplate="%{label}: %{value:.1f}%<extra></extra>",
            ))
            dist_fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#f3f4f6", family="Plus Jakarta Sans"),
                margin=dict(l=0, r=0, t=10, b=0),
                height=260,
                showlegend=False,
            )
            st.plotly_chart(dist_fig, use_container_width=True)
        else:
            st.info("Run a refresh to see signal distribution.")

    with right:
        st.markdown("#### Average Sentiment by Category")
        if not cat_df.empty:
            cat_agg = (
                cat_df.groupby("category")[["sentiment", "demand_change"]]
                .mean()
                .reset_index()
                .sort_values("sentiment", ascending=True)
            )
            bar_fig = go.Figure(go.Bar(
                x=cat_agg["sentiment"],
                y=cat_agg["category"],
                orientation="h",
                marker_color=[
                    "#10b981" if v >= 0.1 else ("#ef4444" if v <= -0.1 else "#9ca3af")
                    for v in cat_agg["sentiment"]
                ],
                hovertemplate="<b>%{y}</b><br>Sentiment: %{x:+.3f}<extra></extra>",
            ))
            bar_fig.update_layout(**_layout(
                height=260,
                xaxis=dict(title="Avg Sentiment Score", range=[-1, 1]),
                yaxis=dict(showgrid=False),
            ))
            st.plotly_chart(bar_fig, use_container_width=True)
        else:
            st.info("No category data yet.")

    st.markdown("<br>", unsafe_allow_html=True)

    # News feed table
    st.markdown("#### Recent News Articles")
    articles = get_stored_articles(days_back=90, analyzed_only=False, limit=50)
    if articles:
        rows = []
        for a in articles:
            d = a.get("demand_direction") or "—"
            d_color = _DIRECTION_COLORS.get(d, "#9ca3af")
            s = a.get("sentiment_score")
            rows.append({
                "Date":      str(a.get("published_date") or "—"),
                "Title":     a.get("title", "")[:90],
                "Domain":    a.get("domain") or "—",
                "Direction": d.upper() if d != "—" else "—",
                "Sentiment": f"{s:+.2f}" if s is not None else "—",
                "Category":  a.get("affected_category") or "—",
                "URL":       a.get("url") or "",
            })
        df_feed = pd.DataFrame(rows)
        st.dataframe(
            df_feed.drop(columns=["URL"]),
            use_container_width=True,
            height=300,
            hide_index=True,
        )
    else:
        st.info("No articles stored yet. Click **Refresh Data** to fetch news.")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 2 — Geopolitical Risk
# ─────────────────────────────────────────────────────────────────────────────

def _render_geopolitical_risk(colors: dict):
    st.markdown("### Geopolitical Risk Monitor")

    stats  = get_overall_sentiment_stats()
    df_all = get_daily_summaries(days_back=90, vehicle_category=None)

    geo_risk = stats.get("geopolitical_risk", 0.0)
    risk_label = "HIGH" if geo_risk > 0.4 else ("MEDIUM" if geo_risk > 0.2 else "LOW")
    risk_color = _RISK_COLORS.get(risk_label.lower(), "#9ca3af")

    kc1, kc2, kc3 = st.columns(3)
    with kc1:
        render_kpi_card("Geopolitical Risk Index", f"{geo_risk:.3f}", delta=risk_label, is_positive=geo_risk <= 0.2)
    with kc2:
        neg_pct = stats.get("negative_pct", 0.0)
        render_kpi_card("Negative Signal Rate", f"{neg_pct:.1f}%", delta="Last 30 days", is_positive=neg_pct < 20)
    with kc3:
        avg_impact = stats.get("avg_impact", 0.0)
        render_kpi_card("Avg News Impact Score", f"{avg_impact:.3f}", delta="0=low  1=high", is_positive=avg_impact < 0.5)

    st.markdown("<br>", unsafe_allow_html=True)

    # Risk gauge + timeline
    gauge_col, timeline_col = st.columns([1, 2])

    with gauge_col:
        st.markdown("#### Current Risk Level")
        gauge_fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=round(geo_risk * 100, 1),
            delta={"reference": 20, "suffix": "%"},
            number={"suffix": "%", "font": {"size": 36, "color": "#f3f4f6"}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#9ca3af"},
                "bar":  {"color": risk_color},
                "steps": [
                    {"range": [0,  30],  "color": "rgba(16,185,129,0.15)"},
                    {"range": [30, 60],  "color": "rgba(245,158,11,0.15)"},
                    {"range": [60, 100], "color": "rgba(239,68,68,0.15)"},
                ],
                "threshold": {
                    "line": {"color": "#ef4444", "width": 3},
                    "thickness": 0.75,
                    "value": 60,
                },
                "bgcolor": "rgba(0,0,0,0)",
            },
            title={"text": "Geopolitical Risk", "font": {"color": "#9ca3af", "size": 14}},
        ))
        gauge_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f3f4f6", family="Plus Jakarta Sans"),
            margin=dict(l=20, r=20, t=40, b=20),
            height=280,
        )
        st.plotly_chart(gauge_fig, use_container_width=True)

    with timeline_col:
        st.markdown("#### Geopolitical Risk Timeline (Last 90 Days)")
        if not df_all.empty:
            df_all["summary_date"] = pd.to_datetime(df_all["summary_date"])
            bar_colors = [
                "#ef4444" if v > 0.4 else ("#f59e0b" if v > 0.2 else "#10b981")
                for v in df_all["geopolitical_risk_score"].fillna(0)
            ]
            risk_fig = go.Figure(go.Bar(
                x=df_all["summary_date"],
                y=df_all["geopolitical_risk_score"].fillna(0),
                marker_color=bar_colors,
                hovertemplate="Date: %{x|%d %b %Y}<br>Risk: %{y:.3f}<extra></extra>",
            ))
            risk_fig.update_layout(**_layout(
                height=260,
                yaxis=dict(title="Risk Score"),
            ))
            st.plotly_chart(risk_fig, use_container_width=True)
        else:
            st.info("No timeline data. Click **Refresh Data** to load news.")

    st.markdown("<br>", unsafe_allow_html=True)

    # High-impact articles
    st.markdown("#### High-Impact Events (Impact Score > 0.4)")
    articles = get_stored_articles(days_back=90, analyzed_only=True, limit=200)
    high_impact = [a for a in articles if (a.get("impact_score") or 0) > 0.4]
    high_impact.sort(key=lambda x: x.get("impact_score") or 0, reverse=True)

    if high_impact:
        rows = []
        for a in high_impact[:20]:
            risk = a.get("economic_risk") or "—"
            rows.append({
                "Date":       str(a.get("published_date") or "—"),
                "Title":      (a.get("title") or "")[:85],
                "Impact":     f"{a.get('impact_score', 0):.2f}",
                "Sentiment":  f"{a.get('sentiment_score', 0):+.2f}" if a.get("sentiment_score") is not None else "—",
                "Econ. Risk": risk.upper(),
                "Direction":  (a.get("demand_direction") or "—").upper(),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=280, hide_index=True)
    else:
        st.info("No high-impact articles detected in the current period.")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 3 — Economic Signals
# ─────────────────────────────────────────────────────────────────────────────

def _render_economic_signals(colors: dict):
    st.markdown("### Economic Signal Tracker")

    cat_df = get_category_sentiment_summary(days_back=90)
    df_all = get_daily_summaries(days_back=90, vehicle_category=None)

    if cat_df.empty and df_all.empty:
        st.info("No economic signal data available. Click **Refresh Data** to load news.")
        return

    # KPIs from the "All" aggregate
    stats = get_overall_sentiment_stats()
    ec1, ec2, ec3, ec4 = st.columns(4)
    with ec1:
        render_kpi_card("Avg Demand Change", f"{stats.get('avg_demand_change', 0):+.2f}%",
                        delta="Estimated % shift", is_positive=stats.get("avg_demand_change", 0) >= 0)
    with ec2:
        render_kpi_card("Avg News Impact", f"{stats.get('avg_impact', 0):.3f}",
                        delta="0=negligible  1=critical", is_positive=stats.get("avg_impact", 0) < 0.4)
    with ec3:
        render_kpi_card("Avg Sentiment", f"{stats.get('avg_sentiment', 0):+.3f}",
                        delta="Economic mood", is_positive=stats.get("avg_sentiment", 0) >= 0)
    with ec4:
        render_kpi_card("Total Articles", f"{stats.get('total_articles', 0):,}",
                        delta=f"{stats.get('positive_pct', 0):.0f}% positive", is_positive=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Demand change per category (bar chart)
    if not cat_df.empty:
        st.markdown("#### Estimated Demand Change (%) by Vehicle Category")
        cat_df["date"] = pd.to_datetime(cat_df["date"])
        cat_agg = (
            cat_df.groupby("category")[["demand_change", "sentiment", "impact"]]
            .mean().reset_index().sort_values("demand_change", ascending=True)
        )
        dem_fig = go.Figure(go.Bar(
            x=cat_agg["demand_change"],
            y=cat_agg["category"],
            orientation="h",
            marker_color=[
                "#10b981" if v >= 0 else "#ef4444" for v in cat_agg["demand_change"]
            ],
            text=[f"{v:+.1f}%" for v in cat_agg["demand_change"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Demand change: %{x:+.2f}%<extra></extra>",
        ))
        dem_fig.update_layout(**_layout(
            height=280,
            xaxis=dict(title="Avg Estimated Demand Change (%)"),
            yaxis=dict(showgrid=False),
        ))
        st.plotly_chart(dem_fig, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Heatmap: date × category, colour = sentiment
    if not cat_df.empty and cat_df["date"].nunique() > 1:
        st.markdown("#### Sentiment Heatmap — Category × Date")
        pivot = cat_df.pivot_table(
            index="category", columns="date", values="sentiment", aggfunc="mean"
        )
        pivot.columns = [c.strftime("%d %b") for c in pivot.columns]

        hm_fig = go.Figure(go.Heatmap(
            z=pivot.values.tolist(),
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale=[
                [0.0, "#ef4444"], [0.4, "#f59e0b"],
                [0.5, "#4b5563"], [0.6, "#06b6d4"], [1.0, "#10b981"],
            ],
            zmid=0,
            zmin=-1, zmax=1,
            colorbar=dict(title="Sentiment", tickfont=dict(color="#9ca3af")),
            hovertemplate="Category: %{y}<br>Date: %{x}<br>Sentiment: %{z:+.3f}<extra></extra>",
        ))
        hm_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f3f4f6", family="Plus Jakarta Sans"),
            margin=dict(l=0, r=0, t=10, b=0),
            height=280,
            xaxis=dict(side="bottom"),
        )
        st.plotly_chart(hm_fig, use_container_width=True)

    # Economic risk distribution
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Economic Risk Distribution (Analysed Articles)")
    articles = get_stored_articles(days_back=90, analyzed_only=True, limit=500)
    if articles:
        risk_counts = {"low": 0, "medium": 0, "high": 0}
        for a in articles:
            r = (a.get("economic_risk") or "low").lower()
            if r in risk_counts:
                risk_counts[r] += 1
        risk_fig = go.Figure(go.Bar(
            x=list(risk_counts.keys()),
            y=list(risk_counts.values()),
            marker_color=["#10b981", "#f59e0b", "#ef4444"],
            text=list(risk_counts.values()),
            textposition="outside",
            hovertemplate="Risk: %{x}<br>Articles: %{y}<extra></extra>",
        ))
        risk_fig.update_layout(**_layout(
            height=220,
            yaxis=dict(title="Number of Articles"),
            xaxis=dict(showgrid=False),
        ))
        st.plotly_chart(risk_fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 4 — Forecast Comparison
# ─────────────────────────────────────────────────────────────────────────────

def _render_forecast_comparison(filters: dict, colors: dict):
    st.markdown("### Sentiment-Enhanced Forecast Comparison")
    st.markdown(
        "<p style='color:#9ca3af;font-size:13px;margin-bottom:16px;'>"
        "Runs two predictive models side-by-side: one with economic regressors only (baseline), "
        "and one that additionally uses <b style='color:#ec4899;'>avg_sentiment_score</b> and "
        "<b style='color:#ec4899;'>geopolitical_risk_score</b> from the sentiment pipeline.</p>",
        unsafe_allow_html=True,
    )

    try:
        from forecasting.prophet_forecasting import train_prophet_model

        # ── Controls ─────────────────────────────────────────────────────
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            horizon = st.selectbox("Forecast Horizon", [30, 60, 90, 180], index=2, key="cmp_horizon")
        with fc2:
            target = st.selectbox(
                "Forecast Target",
                ["units_sold", "total_revenue_incl_vat"],
                format_func=lambda x: "Sales Volume (Units)" if x == "units_sold" else "Revenue (AED)",
                key="cmp_target",
            )
        with fc3:
            st.markdown("<div style='margin-top:28px;'>", unsafe_allow_html=True)
            run_cmp = st.button("Run Comparison", type="primary", use_container_width=True, key="run_cmp_btn")
            st.markdown("</div>", unsafe_allow_html=True)

        category_filter = filters.get("vehicle_category")
        region_filter   = filters.get("emirate")
        fuel_filter     = filters.get("fuel_type")

        if run_cmp:
            with st.spinner("Training baseline model..."):
                base_result, base_err = train_prophet_model(
                    category=category_filter, region=region_filter, fuel_type=fuel_filter,
                    target=target, horizon_days=horizon, use_sentiment=False,
                )
            with st.spinner("Training sentiment-enhanced model..."):
                sent_result, sent_err = train_prophet_model(
                    category=category_filter, region=region_filter, fuel_type=fuel_filter,
                    target=target, horizon_days=horizon, use_sentiment=True,
                )
            st.session_state["fc_cmp_base"] = (base_result, base_err)
            st.session_state["fc_cmp_sent"] = (sent_result, sent_err)
            st.session_state["fc_cmp_target"] = target
            st.session_state["fc_cmp_horizon"] = horizon

        if "fc_cmp_base" not in st.session_state:
            st.info("Click **Run Comparison** to train and compare both forecast models.")
            return

        base_result, base_err = st.session_state["fc_cmp_base"]
        sent_result, sent_err = st.session_state["fc_cmp_sent"]
        _target  = st.session_state.get("fc_cmp_target", target)
        _horizon = st.session_state.get("fc_cmp_horizon", horizon)

        if base_err:
            st.error(f"Baseline forecast error: {base_err}")
            return

        # ── Metrics comparison ────────────────────────────────────────────
        st.markdown("#### Model Metrics Comparison")
        bm = base_result["metrics"]
        sm = sent_result["metrics"] if sent_result else None

        mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
        with mc1:
            render_kpi_card("RMSE — Baseline", f"{bm['rmse']:.2f}", delta="Baseline", is_positive=True)
        with mc2:
            if sm:
                delta_rmse = bm["rmse"] - sm["rmse"]
                render_kpi_card("RMSE — Sentiment", f"{sm['rmse']:.2f}",
                                delta=f"{delta_rmse:+.2f} vs baseline",
                                is_positive=delta_rmse >= 0)
            else:
                render_kpi_card("RMSE — Sentiment", "N/A", delta="No sentiment data", is_positive=False)
        with mc3:
            render_kpi_card("MAE — Baseline", f"{bm['mae']:.2f}", delta="Baseline", is_positive=True)
        with mc4:
            if sm:
                delta_mae = bm["mae"] - sm["mae"]
                render_kpi_card("MAE — Sentiment", f"{sm['mae']:.2f}",
                                delta=f"{delta_mae:+.2f} vs baseline",
                                is_positive=delta_mae >= 0)
            else:
                render_kpi_card("MAE — Sentiment", "N/A", delta="No sentiment data", is_positive=False)
        with mc5:
            render_kpi_card("Accuracy — Baseline", f"{bm['accuracy']:.1f}%", delta="Baseline", is_positive=True)
        with mc6:
            if sm:
                delta_acc = sm["accuracy"] - bm["accuracy"]
                render_kpi_card("Accuracy — Sentiment", f"{sm['accuracy']:.1f}%",
                                delta=f"{delta_acc:+.1f}% vs baseline",
                                is_positive=delta_acc >= 0)
            else:
                render_kpi_card("Accuracy — Sentiment", "N/A", delta="No sentiment data", is_positive=False)

        # Active regressor badges
        base_regs = base_result.get("active_regressors", [])
        sent_regs_active = sent_result.get("sentiment_regressors", []) if sent_result else []
        if base_regs or sent_regs_active:
            badges_html = ""
            for r in base_regs:
                if r not in sent_regs_active:
                    badges_html += (
                        f'<span style="background:#06b6d422;color:#06b6d4;border:1px solid #06b6d444;'
                        f'border-radius:6px;padding:2px 8px;font-size:11px;margin-right:4px;">{r.replace("_"," ").title()}</span>'
                    )
            for r in sent_regs_active:
                badges_html += (
                    f'<span style="background:#ec489922;color:#ec4899;border:1px solid #ec489944;'
                    f'border-radius:6px;padding:2px 8px;font-size:11px;margin-right:4px;">{r.replace("_"," ").title()} ✦</span>'
                )
            st.markdown(
                f"<div style='margin:10px 0 16px;'><b style='color:#9ca3af;font-size:12px;'>Regressors:</b> "
                + badges_html +
                "<span style='color:#9ca3af;font-size:11px;margin-left:8px;'>✦ = sentiment regressor</span></div>",
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Overlay forecast chart ────────────────────────────────────────
        st.markdown("#### Forecast Overlay — Baseline vs Sentiment-Enhanced")
        unit_label = "Units" if _target == "units_sold" else "AED"

        base_fc = base_result["forecast"]
        base_fc["ds"] = pd.to_datetime(base_fc["ds"])
        split_date = base_fc[base_fc["actual"].isnull()]["ds"].min()
        one_year_ago = pd.to_datetime(split_date) - pd.DateOffset(years=1) if pd.notnull(split_date) else base_fc["ds"].min()
        plot_base = base_fc[base_fc["ds"] >= one_year_ago]

        fig = go.Figure()

        # Actuals
        actuals = plot_base[plot_base["actual"].notna()]
        fig.add_trace(go.Scatter(
            x=actuals["ds"], y=actuals["actual"],
            name="Actuals", mode="markers",
            marker=dict(color="rgba(6,182,212,0.5)", size=4),
        ))

        # Baseline forecast + CI
        fig.add_trace(go.Scatter(
            x=plot_base["ds"], y=plot_base["yhat"],
            name="Baseline Forecast", mode="lines",
            line=dict(color=colors["primary"], width=2.5),
        ))
        fut_base = plot_base[plot_base["actual"].isna()]
        if not fut_base.empty:
            fig.add_trace(go.Scatter(
                x=pd.concat([fut_base["ds"], fut_base["ds"].iloc[::-1]]),
                y=pd.concat([fut_base["yhat_upper"], fut_base["yhat_lower"].iloc[::-1]]),
                fill="toself", fillcolor="rgba(99,102,241,0.08)",
                line=dict(color="rgba(255,255,255,0)"),
                name="Baseline CI", showlegend=True,
            ))

        # Sentiment-enhanced forecast
        if sent_result and not sent_err:
            sent_fc = sent_result["forecast"]
            sent_fc["ds"] = pd.to_datetime(sent_fc["ds"])
            plot_sent = sent_fc[sent_fc["ds"] >= one_year_ago]
            fig.add_trace(go.Scatter(
                x=plot_sent["ds"], y=plot_sent["yhat"],
                name="Sentiment-Enhanced Forecast", mode="lines",
                line=dict(color=colors["accent"], width=2.5, dash="dot"),
            ))
            fut_sent = plot_sent[plot_sent["actual"].isna()]
            if not fut_sent.empty:
                fig.add_trace(go.Scatter(
                    x=pd.concat([fut_sent["ds"], fut_sent["ds"].iloc[::-1]]),
                    y=pd.concat([fut_sent["yhat_upper"], fut_sent["yhat_lower"].iloc[::-1]]),
                    fill="toself", fillcolor="rgba(236,72,153,0.06)",
                    line=dict(color="rgba(255,255,255,0)"),
                    name="Sentiment CI", showlegend=True,
                ))

        # Forecast horizon marker
        if pd.notnull(split_date):
            fig.add_vline(
                x=pd.to_datetime(split_date).timestamp() * 1000,
                line_dash="dash", line_color="rgba(245,158,11,0.6)",
                annotation_text="Forecast start",
                annotation_font_color="#f59e0b",
            )

        fig.update_layout(**_layout(
            height=400,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title=f"{_target.replace('_', ' ').title()} ({unit_label})"),
        ))
        st.plotly_chart(fig, use_container_width=True)

        # ── Forecast delta chart ──────────────────────────────────────────
        # if sent_result and not sent_err:
        #     st.markdown("#### Sentiment Adjustment (Enhanced − Baseline)")
        #     sent_fc = sent_result["forecast"]
        #     sent_fc["ds"] = pd.to_datetime(sent_fc["ds"])
        #     merged = base_fc[["ds", "yhat"]].merge(sent_fc[["ds", "yhat"]], on="ds", suffixes=("_base", "_sent"))
        #     merged["delta"] = merged["yhat_sent"] - merged["yhat_base"]
        #     fut_merged = merged[merged["ds"] >= split_date] if pd.notnull(split_date) else merged
        #
        #     if not fut_merged.empty:
        #         delta_fig = go.Figure(go.Bar(
        #             x=fut_merged["ds"],
        #             y=fut_merged["delta"],
        #             marker_color=["#10b981" if v >= 0 else "#ef4444" for v in fut_merged["delta"]],
        #             hovertemplate="Date: %{x|%d %b %Y}<br>Δ: %{y:+.2f}<extra></extra>",
        #             name="Sentiment Adjustment",
        #         ))
        #         delta_fig.add_hline(y=0, line_dash="dot", line_color="rgba(156,163,175,0.3)")
        #         delta_fig.update_layout(**_layout(
        #             height=220,
        #             yaxis=dict(title=f"Δ {unit_label}"),
        #         ))
        #         st.plotly_chart(delta_fig, use_container_width=True)

        # Note when no sentiment data added regressors
        if not sent_regs_active:
            st.info(
                "No sentiment regressors were active in the enhanced model — sentiment data may be "
                "all-constant (needs more variance) or not yet fetched. Go to the **Sentiment Intelligence** "
                "tab and click **Refresh Data** to load articles and generate signals."
            )

    except Exception as e:
        st.warning(f"Could not run forecast comparison: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 5 — AI Insights
# ─────────────────────────────────────────────────────────────────────────────

def _render_ai_insights(colors: dict):
    st.markdown("### AI Market Intelligence Briefing")

    mode_label = "Grok AI (Live)" if is_live_mode() else "Template Engine (Mock)"
    st.markdown(
        f'<p style="color:#9ca3af;font-size:13px;margin-bottom:18px;">'
        f'Powered by: <b style="color:#f3f4f6;">{mode_label}</b> — '
        f'generates a structured demand intelligence briefing from current signals.</p>',
        unsafe_allow_html=True,
    )

    # Briefing controls
    gen_col1, gen_col2 = st.columns([3, 1])
    with gen_col2:
        generate = st.button("Generate Briefing", type="primary", use_container_width=True)

    if generate or "sentiment_briefing" in st.session_state:
        if generate:
            with st.spinner("Generating market briefing..."):
                stats    = get_overall_sentiment_stats()
                cat_df   = get_category_sentiment_summary(days_back=30)
                cat_rows = []
                if not cat_df.empty:
                    cat_agg = (
                        cat_df.groupby("category")[["sentiment", "impact", "demand_change"]]
                        .mean().reset_index()
                        .sort_values("sentiment", ascending=False)
                    )
                    cat_rows = cat_agg.to_dict("records")
                    cat_rows = [
                        {"category": r["category"],
                         "avg_sentiment": r["sentiment"],
                         "avg_demand_change": r["demand_change"]}
                        for r in cat_rows
                    ]
                briefing = generate_market_briefing(stats, cat_rows)
                st.session_state["sentiment_briefing"] = briefing
                st.session_state["sentiment_briefing_stats"] = stats

        briefing = st.session_state.get("sentiment_briefing", "")
        stats    = st.session_state.get("sentiment_briefing_stats", {})

        if briefing:
            _glass_card(f"""
                <div style="color:#a5b4fc;font-size:11px;font-weight:600;letter-spacing:1px;margin-bottom:10px;">
                  UAE AUTOMOBILE MARKET INTELLIGENCE BRIEFING
                </div>
                <div style="color:#f3f4f6;font-size:14px;line-height:1.8;white-space:pre-wrap;">{briefing}</div>
            """)

            # Signal summary cards below briefing
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("#### Signal Summary")
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                render_kpi_card("Market Sentiment", f"{stats.get('avg_sentiment', 0):+.3f}",
                                delta="30-day avg", is_positive=stats.get("avg_sentiment", 0) >= 0)
            with sc2:
                render_kpi_card("Demand Direction", stats.get("dominant_direction", "neutral").upper(),
                                delta=f"Change: {stats.get('avg_demand_change', 0):+.1f}%",
                                is_positive=stats.get("dominant_direction", "neutral") == "up")
            with sc3:
                render_kpi_card("Geo Risk", f"{stats.get('geopolitical_risk', 0):.3f}",
                                delta="LOW" if stats.get("geopolitical_risk", 0) < 0.2 else "ELEVATED",
                                is_positive=stats.get("geopolitical_risk", 0) < 0.2)
            with sc4:
                render_kpi_card("7-Day Trend", f"{stats.get('trend_7d', 0):+.3f}",
                                delta="Sentiment delta", is_positive=stats.get("trend_7d", 0) >= 0)

            # Top signals table
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("#### Top Signals by Impact")
            articles = get_stored_articles(days_back=30, analyzed_only=True, limit=200)
            if articles:
                top_sigs = sorted(articles, key=lambda x: x.get("impact_score") or 0, reverse=True)[:10]
                rows = [{
                    "Title":       (a.get("title") or "")[:75],
                    "Category":    a.get("affected_category") or "—",
                    "Sentiment":   f"{a.get('sentiment_score', 0):+.2f}" if a.get("sentiment_score") is not None else "—",
                    "Impact":      f"{a.get('impact_score', 0):.2f}" if a.get("impact_score") is not None else "—",
                    "Direction":   (a.get("demand_direction") or "—").upper(),
                    "Summary":     (a.get("signal_summary") or "")[:60],
                } for a in top_sigs]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, height=280, hide_index=True)
    else:
        _glass_card("""
            <div style="text-align:center;padding:30px 0;">
              <div style="font-size:36px;margin-bottom:12px;">🤖</div>
              <div style="color:#f3f4f6;font-size:16px;font-weight:600;margin-bottom:8px;">
                Ready to Generate Briefing
              </div>
              <div style="color:#9ca3af;font-size:13px;">
                Click <b>Generate Briefing</b> above to produce a data-driven
                UAE automobile market intelligence report from current sentiment signals.
              </div>
            </div>
        """)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline status display
# ─────────────────────────────────────────────────────────────────────────────

def _show_pipeline_status(status: dict):
    fetch   = status.get("fetch", {})
    analyze = status.get("analyze", {})
    summ    = status.get("summarize", {})
    errors  = status.get("errors", [])
    mode    = status.get("mode", "mock")

    parts = [
        f"Fetched **{fetch.get('fetched_from_gdelt', 0)}** articles "
        f"({fetch.get('inserted', 0)} new)",
        f"Analysed **{analyze.get('articles_found', 0)}** articles "
        f"({analyze.get('inserted', 0)} signals saved)",
        f"Daily summaries: **{summ.get('rows_computed', 0)}** rows",
        f"Mode: **{mode.upper()}**",
    ]
    msg = "  |  ".join(parts)

    if errors:
        st.warning(f"Pipeline completed with warnings: {'; '.join(errors)}\n\n{msg}")
    else:
        st.success(f"Pipeline complete — {msg}")
