import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.queries import (
    get_executive_kpis,
    get_monthly_revenue_trend,
    get_sales_by_category,
    get_sales_by_fuel_type,
    get_sales_by_store,
    get_top_models,
)
from utils.helpers import (
    render_kpi_card, get_color_palette,
    _fmt_money, _compact, _section, _base_layout,
    _INK, _INK_MUTED, _HUE_HISTORY, _HUE_FORECAST, _HUE_MARKER,
)
from analytics.decision_engine import (
    project_year_end, generate_plays, category_accent, GROSS_PER_NEW_UNIT,
)

_CONF_DOT = {"High": "#10b981", "Medium": "#f59e0b", "Low": "#9ca3af"}


# ═════════════════════════════════════════════════════════════════════════════
# Tab 1 — Overview (the 10-second glance)
# ═════════════════════════════════════════════════════════════════════════════
def _render_glance(session, filters: dict, colors: dict) -> None:
    kpis = get_executive_kpis(session, filters)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        d = kpis["total_sales_delta"]
        render_kpi_card("Vehicles Sold", f"{kpis['total_sales']:,} units",
                        delta=(f"{d:+.1f}% YoY" if d is not None else "N/A"),
                        is_positive=(d is None or d >= 0))
    with c2:
        d = kpis["total_revenue_delta"]
        render_kpi_card("Total Revenue", _fmt_money(kpis["total_revenue"]),
                        delta=(f"{d:+.1f}% YoY" if d is not None else "N/A"),
                        is_positive=(d is None or d >= 0))
    with c3:
        pct = kpis["target_attainment_pct"]
        if pct is None:
            render_kpi_card("Target Attainment (TTM)", "N/A", delta="no targets set", is_positive=False)
        else:
            dd = kpis["target_attainment_delta"]
            sub = f"{kpis['ttm_units']:,} of {kpis['annual_target']:,} units"
            if dd is not None:
                sub = f"{dd:+.1f} pts YoY · " + sub
            render_kpi_card("Target Attainment (TTM)", f"{pct:.0f}%", delta=sub,
                            is_positive=(pct >= 92))
    with c4:
        pen = kpis["finance_lease_penetration"]
        dd = kpis["finance_lease_penetration_delta"]
        render_kpi_card("Finance & Lease Penetration", f"{pen:.0f}%",
                        delta=(f"{dd:+.1f} pts YoY" if dd is not None else None),
                        is_positive=(dd is None or dd >= 0))

    st.markdown("<br>", unsafe_allow_html=True)

    _section("Revenue & unit trend")
    trend_df = get_monthly_revenue_trend(session, filters)
    if not trend_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_df["date"], y=trend_df["revenue"], name="Revenue",
            line=dict(color=colors["primary"], width=3), mode="lines",
            hovertemplate="%{x|%b %Y} · $%{y:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=trend_df["date"], y=trend_df["sales"], name="Units", yaxis="y2",
            marker_color="rgba(6,182,212,0.22)",
            hovertemplate="%{x|%b %Y} · %{y:,} units<extra></extra>",
        ))
        fig.update_layout(**_base_layout(height=340, legend=True))
        fig.update_layout(
            yaxis=dict(title="Revenue", showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            yaxis2=dict(title="Units", overlaying="y", side="right", showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)
    with left:
        _section("Sales mix by category")
        cat_df = get_sales_by_category(session, filters)
        if not cat_df.empty:
            cat_df = cat_df.sort_values("sales")
            tot = cat_df["sales"].sum() or 1
            fig = go.Figure(go.Bar(
                x=cat_df["sales"], y=cat_df["vehicle_category"], orientation="h",
                marker_color=colors["primary"],
                text=[f"{v / tot * 100:.0f}%" for v in cat_df["sales"]],
                textposition="outside", cliponaxis=False,
            ))
            fig.update_layout(**_base_layout(height=260))
            fig.update_xaxes(visible=False, range=[0, cat_df["sales"].max() * 1.18])
            st.plotly_chart(fig, use_container_width=True)
    with right:
        _section("Fuel type mix")
        fuel_df = get_sales_by_fuel_type(session, filters)
        if not fuel_df.empty:
            fuel_df = fuel_df.sort_values("sales")
            tot = fuel_df["sales"].sum() or 1
            fig = go.Figure(go.Bar(
                x=fuel_df["sales"], y=fuel_df["fuel_type"], orientation="h",
                marker_color=colors["secondary"],
                text=[f"{v / tot * 100:.0f}%" for v in fuel_df["sales"]],
                textposition="outside", cliponaxis=False,
            ))
            fig.update_layout(**_base_layout(height=260))
            fig.update_xaxes(visible=False, range=[0, fuel_df["sales"].max() * 1.18])
            st.plotly_chart(fig, use_container_width=True)

    _section("Sales by store")
    store_all = get_sales_by_store(session, filters, limit=500)
    if not store_all.empty:
        grp_avg = float(store_all["units"].mean())
        store_df = store_all.head(15).sort_values("units")
        fig = go.Figure(go.Bar(
            x=store_df["units"], y=store_df["dealer_name"], orientation="h",
            marker_color=colors["primary"],
            text=[f"{u:,.0f}  ·  {_fmt_money(r)}" for u, r in zip(store_df["units"], store_df["revenue"])],
            textposition="outside", cliponaxis=False,
            hovertext=[f"{n} — {c}<br>{u:,.0f} units · {_fmt_money(r)}"
                       for n, c, u, r in zip(store_df["dealer_name"], store_df["city"],
                                             store_df["units"], store_df["revenue"])],
            hoverinfo="text",
        ))
        fig.add_vline(x=grp_avg, line=dict(color=_INK, width=1.4, dash="dash"),
                      annotation_text=f"group avg {grp_avg:,.0f}",
                      annotation_position="top", annotation_yshift=8,
                      annotation_font=dict(color=_INK, size=11))
        fig.update_layout(**_base_layout(height=max(340, 27 * len(store_df) + 30),
                                         margin=dict(l=0, r=12, t=22, b=6)))
        fig.update_xaxes(visible=False, range=[0, store_df["units"].max() * 1.35])
        st.plotly_chart(fig, use_container_width=True)

    _section("Top-selling models")
    models_df = get_top_models(session, filters, limit=8)
    if not models_df.empty:
        models_df["label"] = models_df["brand"] + " " + models_df["model"]
        models_df = models_df.sort_values("units")
        fig = go.Figure(go.Bar(
            x=models_df["units"], y=models_df["label"], orientation="h",
            marker_color=colors["secondary"],
            text=[f"{u:,.0f}" for u in models_df["units"]],
            textposition="outside", cliponaxis=False,
        ))
        fig.update_layout(**_base_layout(height=300))
        fig.update_xaxes(visible=False)
        st.plotly_chart(fig, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# Tab 2 — Recommendations (the decision brief)
# ═════════════════════════════════════════════════════════════════════════════
def _render_play(idx: int, play) -> None:
    accent = category_accent(play.category)
    dot = _CONF_DOT.get(play.confidence, "#9ca3af")
    st.markdown(
        f"""
        <div style="border-left:3px solid {accent};background:rgba(255,255,255,0.03);
                    border-radius:8px;padding:13px 16px;margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;">
            <span style="font-size:10.5px;font-weight:700;letter-spacing:0.7px;
                         text-transform:uppercase;color:{accent};">{play.category}</span>
            <span style="font-size:11px;color:{_INK_MUTED};">
              <span style="color:{dot};">●</span> {play.confidence} confidence · {play.horizon}
            </span>
          </div>
          <div style="font-size:14.5px;font-weight:650;color:{_INK};margin:6px 0 4px;">
            {idx}. {play.title}
          </div>
          <div style="font-size:12.5px;color:{_INK_MUTED};line-height:1.55;">{play.detail}</div>
          <div style="font-size:17px;font-weight:700;color:#10b981;margin-top:9px;">
            {_fmt_money(play.impact_usd)}
            <span style="font-size:11px;color:{_INK_MUTED};font-weight:400;"> modelled impact</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_landing_chart(landing: dict) -> None:
    hist, proj = landing.get("history"), landing.get("projection")
    if hist is None or proj is None or len(hist) == 0:
        return
    target = landing.get("annual_target") or 0
    monthly_target = target / 12 if target else None

    fig = go.Figure()
    fig.add_vrect(x0=hist.index[-1], x1=proj.index[-1],
                  fillcolor="rgba(99,102,241,0.06)", line_width=0, layer="below")
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist.values, name="Actual", mode="lines",
        line=dict(color=_HUE_HISTORY, width=2),
        hovertemplate="%{x|%b %Y} · %{y:,.0f} units<extra></extra>",
    ))
    join = pd.concat([hist.iloc[[-1]], proj])
    fig.add_trace(go.Scatter(
        x=join.index, y=join.values, name="Projected", mode="lines",
        line=dict(color=_HUE_FORECAST, width=2.5, dash="dot"),
        hovertemplate="%{x|%b %Y} · %{y:,.0f} units (projected)<extra></extra>",
    ))
    if monthly_target:
        fig.add_hline(
            y=monthly_target, line=dict(color=_HUE_MARKER, width=1.4, dash="dash"),
            annotation_text=f"plan pace · {monthly_target:,.0f}/mo",
            annotation_position="top right",
            annotation_yshift=9,
            annotation_font=dict(color=_HUE_MARKER, size=11),
        )
    fig.update_layout(**_base_layout(height=280, legend=True,
                                     margin=dict(l=0, r=8, t=24, b=0)))
    fig.update_layout(legend=dict(orientation="h", y=1.14, x=0, xanchor="left"))
    # headroom above the highest series / the plan line so the annotation clears
    y_hi = max(float(hist.max()), float(proj.max()), monthly_target or 0)
    y_lo = min(float(hist.min()), float(proj.min()))
    fig.update_yaxes(title="Units / month", range=[y_lo * 0.95, y_hi * 1.12])
    st.plotly_chart(fig, use_container_width=True)


def _render_recommendations(session, filters: dict) -> None:
    try:
        landing = project_year_end(session, filters)
        plays = generate_plays(session, filters, limit=5)
    except Exception as e:
        landing, plays = {}, []
        st.warning(f"Decision brief unavailable for this scope ({e}).")

    gross_at_stake = sum(p.impact_usd for p in plays)
    att = landing.get("attainment_pct")
    gap = landing.get("unit_gap", 0.0)
    gpm = landing.get("gap_per_store_month", 0.0)

    k1, k2, k3 = st.columns(3)
    with k1:
        if att is None:
            render_kpi_card("12-Month Landing", "N/A", "no plan set", is_positive=False)
        else:
            short = gap > 0
            render_kpi_card(
                "12-Month Landing", f"{att:.0f}% of plan",
                delta=(f"{'−' if short else '+'}{abs(gap):,.0f} units · "
                       f"{_fmt_money(abs(gap) * GROSS_PER_NEW_UNIT)} gross"),
                is_positive=not short,
            )
    with k2:
        render_kpi_card("Gross at Stake", _fmt_money(gross_at_stake),
                        delta=f"across {len(plays)} plays below", is_positive=True)
    with k3:
        if att is None or gap <= 0:
            render_kpi_card("Gap to Close", "On plan", "no shortfall projected", is_positive=True)
        else:
            render_kpi_card("Gap to Close", f"+{gpm:.0f} units",
                            delta="per store, per month", is_positive=False)

    st.markdown("<br>", unsafe_allow_html=True)
    _section("The Decision Brief")
    if plays:
        for i, p in enumerate(plays, 1):
            _render_play(i, p)
    else:
        st.info("No plays surfaced for this scope — the group is tracking to plan "
                "with no stock, margin or pace outliers.")

    st.markdown("<br>", unsafe_allow_html=True)
    _section("Where the year lands")
    _render_landing_chart(landing)


# ═════════════════════════════════════════════════════════════════════════════
def render_overview(filters: dict):
    """Executive Overview — two views of the group: the 10-second performance
    read (Overview) and the ranked list of decisions to act on (Recommendations).
    Everything is the group's own data, no market extrapolation."""
    session = get_db_session()
    colors = get_color_palette()

    try:
        st.markdown(
            "<h2 class='gradient-text' style='margin-bottom:10px;'>Executive Overview</h2>",
            unsafe_allow_html=True,
        )

        tab_glance, tab_recs = st.tabs(["Overview", "Recommendations"])

        with tab_glance:
            _render_glance(session, filters, colors)

        with tab_recs:
            _render_recommendations(session, filters)

    except Exception as e:
        st.error(f"Error rendering Executive Overview: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()
