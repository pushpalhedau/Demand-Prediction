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
)
from utils.helpers import (
    render_kpi_card, get_color_palette,
    _fmt_money, _compact, _section, _base_layout,
    _INK, _INK_MUTED, _HUE_HISTORY, _HUE_FORECAST, _HUE_MARKER,
)
from analytics.decision_engine import (
    project_year_end, generate_plays, category_accent, GROSS_PER_NEW_UNIT,
    _project_series,
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

    _section("Revenue & unit trend",
             "Last 3 years of booked revenue and units, plus a 6-month projection (dashed / faded).")
    trend_df = get_monthly_revenue_trend(session, filters)
    if not trend_df.empty:
        td = trend_df.sort_values("date").set_index("date")
        rev = td["revenue"].astype(float)
        units = td["sales"].astype(float)

        # drop a trailing partial month so the projection isn't anchored to it
        if len(rev) >= 14 and rev.iloc[-1] < 0.55 * rev.iloc[-13:-1].mean():
            rev, units = rev.iloc[:-1], units.iloc[:-1]

        rev, units = rev.tail(36), units.tail(36)          # 3 years of history
        rev_fc = _project_series(rev, 6)                   # 6-month projection
        units_fc = _project_series(units, 6)
        rev_join = pd.concat([rev.iloc[[-1]], rev_fc])

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=units.index, y=units.values, name="Units", yaxis="y2",
            marker_color="rgba(6,182,212,0.22)",
            hovertemplate="%{x|%b %Y} · %{y:,} units<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=units_fc.index, y=units_fc.values, name="Units", yaxis="y2",
            marker_color="rgba(6,182,212,0.09)", showlegend=False,
            hovertemplate="%{x|%b %Y} · %{y:,.0f} units (projected)<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=rev.index, y=rev.values, name="Revenue",
            line=dict(color=colors["primary"], width=3), mode="lines",
            hovertemplate="%{x|%b %Y} · AED %{y:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=rev_join.index, y=rev_join.values, name="Revenue (projected)",
            line=dict(color=colors["primary"], width=2.5, dash="dot"), mode="lines",
            hovertemplate="%{x|%b %Y} · AED %{y:,.0f} (projected)<extra></extra>",
        ))
        fig.add_vrect(x0=rev.index[-1], x1=rev_fc.index[-1],
                      fillcolor="rgba(99,102,241,0.06)", line_width=0, layer="below",
                      annotation_text="projection", annotation_position="top left",
                      annotation_font=dict(color=_INK_MUTED, size=10))
        fig.update_layout(**_base_layout(height=340, legend=True))
        fig.update_layout(
            barmode="overlay",
            yaxis=dict(title="Revenue", showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            yaxis2=dict(title="Units", overlaying="y", side="right", showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)
    with left:
        _section("Sales mix by category")
        cat_df = get_sales_by_category(session, filters)
        if not cat_df.empty:
            fig = go.Figure(go.Pie(
                labels=cat_df["vehicle_category"], values=cat_df["sales"], hole=0.45,
                sort=True, direction="clockwise",
                marker=dict(colors=colors["colors_seq"],
                            line=dict(color="#0b0f19", width=2)),
                textposition="inside", textinfo="percent",
                hovertemplate="%{label} · %{value:,} units (%{percent})<extra></extra>",
            ))
            fig.update_layout(**_base_layout(height=300, legend=True))
            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="v", yanchor="middle", y=0.5,
                            xanchor="left", x=1.0),
            )
            st.plotly_chart(fig, use_container_width=True)
    with right:
        _section("Fuel type mix")
        fuel_df = get_sales_by_fuel_type(session, filters)
        if not fuel_df.empty:
            fuel_df = fuel_df.sort_values("sales", ascending=False)
            seq = colors["colors_seq"]
            fig = go.Figure()
            for i, row in enumerate(fuel_df.itertuples(index=False)):
                fig.add_trace(go.Bar(
                    x=[row.fuel_type], y=[row.sales], name=row.fuel_type,
                    marker_color=seq[i % len(seq)],
                    hovertemplate="%{x} · %{y:,} units<extra></extra>",
                ))
            fig.update_layout(**_base_layout(height=300, legend=True))
            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                yaxis=dict(title="Units", showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            )
            st.plotly_chart(fig, use_container_width=True)

    _section("Sales by store", "Top 5 rooftops by units; dashed line is the group average.")
    store_all = get_sales_by_store(session, filters, limit=500)
    if not store_all.empty:
        grp_avg = float(store_all["units"].mean())
        store_df = store_all.head(5).sort_values("units")
        fig = go.Figure(go.Bar(
            x=store_df["units"], y=store_df["dealer_name"], orientation="h",
            marker_color=colors["primary"], width=0.45,
            text=[f"{u:,.0f}  ·  {_fmt_money(r)}" for u, r in zip(store_df["units"], store_df["revenue"])],
            textposition="outside", cliponaxis=False,
            hovertext=[f"{n} — {c}<br>{u:,.0f} units · {_fmt_money(r)}"
                       for n, c, u, r in zip(store_df["dealer_name"], store_df["area"],
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
          <div style="font-size:15px;font-weight:650;color:{_INK};margin:7px 0 5px;">
            {idx}. {play.title}
          </div>
          <div style="font-size:13px;color:{_INK_MUTED};line-height:1.7;">{play.detail}</div>
          <div style="font-size:17px;font-weight:700;color:#10b981;margin-top:10px;">
            {_fmt_money(play.impact_usd)}
            <span style="font-size:11px;color:{_INK_MUTED};font-weight:400;"> estimated value if acted on</span>
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
            render_kpi_card("Where the year ends up", "N/A", "no plan set", is_positive=False)
        else:
            short = gap > 0
            render_kpi_card(
                "Where the year ends up", f"{att:.0f}% of plan",
                delta=(f"{'−' if short else '+'}{abs(gap):,.0f} units · "
                       f"{_fmt_money(abs(gap) * GROSS_PER_NEW_UNIT)} in profit"),
                is_positive=not short,
            )
    with k2:
        render_kpi_card("Total value in the actions below", _fmt_money(gross_at_stake),
                        delta=f"across {len(plays)} actions", is_positive=True)
    with k3:
        if att is None or gap <= 0:
            render_kpi_card("Extra sales needed", "None", "on track to hit plan", is_positive=True)
        else:
            render_kpi_card("Extra sales needed", f"+{gpm:.0f} cars",
                            delta="per store, each month", is_positive=False)

    st.markdown("<br>", unsafe_allow_html=True)
    _section("What to do next",
             "Plain-language actions, ranked by the estimated value of acting on each.")
    if plays:
        for i, p in enumerate(plays, 1):
            _render_play(i, p)
    else:
        st.info("Nothing to flag for this selection — the group is on track to plan, "
                "with no stock, discounting or sales-pace problems standing out.")

    st.markdown("<br>", unsafe_allow_html=True)
    _section("Where the year lands",
             "Monthly sales so far, and where the current pace takes the group by year-end.")
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
