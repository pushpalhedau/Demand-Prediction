import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backend.services import overview as overview_service
from frontend.shared.errors import report_error, report_warning
from frontend.shared.i18n import fmt_num, fmt_pct, hover_money, hover_month, t, tv, tv_series
from frontend.shared.ui import (
    _HUE_FORECAST,
    _HUE_HISTORY,
    _HUE_MARKER,
    _INK,
    _INK_MUTED,
    _base_layout,
    _fmt_money,
    _section,
    get_color_palette,
    render_kpi_card,
)

_CONF_DOT = {"High": "#10b981", "Medium": "#f59e0b", "Low": "#9ca3af"}


def _yoy(delta) -> str:
    """'+8.1% YoY' / '+8,1 % ggü. Vorjahr', or the language's N/A."""
    if delta is None:
        return t("val.na")
    return t("val.yoy_pct", v=fmt_pct(delta, 1, signed=True).rstrip(" %").rstrip("%"))


def _yoy_pts(delta) -> str:
    if delta is None:
        return None
    return t("val.yoy_pts", v=fmt_pct(delta, 1, signed=True).rstrip(" %").rstrip("%"))


# ═════════════════════════════════════════════════════════════════════════════
# Tab 1 — Overview (the 10-second glance)
# ═════════════════════════════════════════════════════════════════════════════
def _render_glance(filters: dict, colors: dict) -> None:
    kpis = overview_service.executive_kpis(filters)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        d = kpis["total_sales_delta"]
        render_kpi_card(t("ov.kpi.units"),
                        t("val.units", v=fmt_num(kpis["total_sales"])),
                        delta=_yoy(d),
                        is_positive=(d is None or d >= 0))
    with c2:
        d = kpis["total_revenue_delta"]
        render_kpi_card(t("ov.kpi.revenue"), _fmt_money(kpis["total_revenue"]),
                        delta=_yoy(d),
                        is_positive=(d is None or d >= 0))
    with c3:
        pct = kpis["target_attainment_pct"]
        if pct is None:
            render_kpi_card(t("ov.kpi.attainment"), t("val.na"),
                            delta=t("ov.kpi.no_targets"), is_positive=False)
        else:
            dd = kpis["target_attainment_delta"]
            sub = t("ov.kpi.attainment_sub",
                    actual=fmt_num(kpis["ttm_units"]),
                    target=fmt_num(kpis["annual_target"]))
            if dd is not None:
                sub = f"{_yoy_pts(dd)} · {sub}"
            render_kpi_card(t("ov.kpi.attainment"), fmt_pct(pct, 0), delta=sub,
                            is_positive=(pct >= 92))
    with c4:
        pen = kpis["finance_lease_penetration"]
        dd = kpis["finance_lease_penetration_delta"]
        render_kpi_card(t("ov.kpi.penetration"), fmt_pct(pen, 0),
                        delta=_yoy_pts(dd),
                        is_positive=(dd is None or dd >= 0))

    st.markdown("<br>", unsafe_allow_html=True)

    _section(t("ov.trend.title"), t("ov.trend.caption"))
    trend_df = overview_service.monthly_revenue_trend(filters)
    if not trend_df.empty:
        td = trend_df.sort_values("date").set_index("date")
        rev = td["revenue"].astype(float)
        units = td["sales"].astype(float)

        # drop a trailing partial month so the projection isn't anchored to it
        if len(rev) >= 14 and rev.iloc[-1] < 0.55 * rev.iloc[-13:-1].mean():
            rev, units = rev.iloc[:-1], units.iloc[:-1]

        rev, units = rev.tail(36), units.tail(36)          # 3 years of history
        rev_fc = overview_service.project_series(rev, 6)                   # 6-month projection
        units_fc = overview_service.project_series(units, 6)
        rev_join = pd.concat([rev.iloc[[-1]], rev_fc])

        _mo = hover_month()
        _units_lbl = t("ov.trend.units")
        _proj_lbl = t("ov.trend.projection")

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=units.index, y=units.values, name=_units_lbl, yaxis="y2",
            marker_color="rgba(6,182,212,0.22)",
            hovertemplate=f"{_mo} · %{{y:,}} {_units_lbl}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=units_fc.index, y=units_fc.values, name=_units_lbl, yaxis="y2",
            marker_color="rgba(6,182,212,0.09)", showlegend=False,
            hovertemplate=f"{_mo} · %{{y:,.0f}} {_units_lbl} ({_proj_lbl})<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=rev.index, y=rev.values, name=t("ov.trend.revenue"),
            line=dict(color=colors["primary"], width=3), mode="lines",
            hovertemplate=f"{_mo} · {hover_money()}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=rev_join.index, y=rev_join.values, name=t("ov.trend.revenue_proj"),
            line=dict(color=colors["primary"], width=2.5, dash="dot"), mode="lines",
            hovertemplate=f"{_mo} · {hover_money()} ({_proj_lbl})<extra></extra>",
        ))
        fig.add_vrect(x0=rev.index[-1], x1=rev_fc.index[-1],
                      fillcolor="rgba(99,102,241,0.06)", line_width=0, layer="below",
                      annotation_text=_proj_lbl, annotation_position="top left",
                      annotation_font=dict(color=_INK_MUTED, size=10))
        fig.update_layout(**_base_layout(height=340, legend=True))
        fig.update_layout(
            barmode="overlay",
            yaxis=dict(title=t("ov.trend.revenue"), showgrid=True,
                       gridcolor="rgba(255,255,255,0.05)"),
            yaxis2=dict(title=_units_lbl, overlaying="y", side="right", showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)
    with left:
        _section(t("ov.mix.category"))
        cat_df = overview_service.sales_by_category(filters)
        if not cat_df.empty:
            # Translate the category labels ONLY here, at the render boundary —
            # the aggregation above ran on the canonical English values.
            fig = go.Figure(go.Pie(
                labels=tv_series(cat_df["vehicle_category"]), values=cat_df["sales"],
                hole=0.45, sort=True, direction="clockwise",
                marker=dict(colors=colors["colors_seq"],
                            line=dict(color="#0b0f19", width=2)),
                textposition="inside", textinfo="percent",
                hovertemplate=(f"%{{label}} · %{{value:,}} {t('ov.trend.units')} "
                               "(%{percent})<extra></extra>"),
            ))
            fig.update_layout(**_base_layout(height=300, legend=True))
            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="v", yanchor="middle", y=0.5,
                            xanchor="left", x=1.0),
            )
            st.plotly_chart(fig, use_container_width=True)
    with right:
        _section(t("ov.mix.fuel"))
        fuel_df = overview_service.sales_by_fuel_type(filters)
        if not fuel_df.empty:
            fuel_df = fuel_df.sort_values("sales", ascending=False)
            seq = colors["colors_seq"]
            fig = go.Figure()
            for i, row in enumerate(fuel_df.itertuples(index=False)):
                label = tv(row.fuel_type)   # display only
                fig.add_trace(go.Bar(
                    x=[label], y=[row.sales], name=label,
                    marker_color=seq[i % len(seq)],
                    hovertemplate=f"%{{x}} · %{{y:,}} {t('ov.trend.units')}<extra></extra>",
                ))
            fig.update_layout(**_base_layout(height=300, legend=True))
            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                yaxis=dict(title=t("ov.trend.units"), showgrid=True,
                           gridcolor="rgba(255,255,255,0.05)"),
            )
            st.plotly_chart(fig, use_container_width=True)

    _section(t("ov.store.title"), t("ov.store.caption"))
    store_all = overview_service.sales_by_store(filters, limit=500)
    if not store_all.empty:
        grp_avg = float(store_all["units"].mean())
        store_df = store_all.head(5).sort_values("units")
        fig = go.Figure(go.Bar(
            x=store_df["units"], y=store_df["dealer_name"], orientation="h",
            marker_color=colors["primary"], width=0.45,
            text=[f"{fmt_num(u)}  ·  {_fmt_money(r)}"
                  for u, r in zip(store_df["units"], store_df["revenue"])],
            textposition="outside", cliponaxis=False,
            hovertext=[f"{n} — {c}<br>{fmt_num(u)} {t('ov.trend.units')} · {_fmt_money(r)}"
                       for n, c, u, r in zip(store_df["dealer_name"], store_df["city"],
                                             store_df["units"], store_df["revenue"])],
            hoverinfo="text",
        ))
        fig.add_vline(x=grp_avg, line=dict(color=_INK, width=1.4, dash="dash"),
                      annotation_text=t("ov.store.group_avg", v=fmt_num(grp_avg)),
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
    accent = overview_service.category_accent(play.category)
    dot = _CONF_DOT.get(play.confidence, "#9ca3af")
    conf = t("ov.rec.confidence", level=t(f"conf.{play.confidence}"))
    st.markdown(
        f"""
        <div style="border-left:3px solid {accent};background:rgba(255,255,255,0.03);
                    border-radius:8px;padding:13px 16px;margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;">
            <span style="font-size:10.5px;font-weight:700;letter-spacing:0.7px;
                         text-transform:uppercase;color:{accent};">{play.category}</span>
            <span style="font-size:11px;color:{_INK_MUTED};">
              <span style="color:{dot};">●</span> {conf} · {play.horizon}
            </span>
          </div>
          <div style="font-size:15px;font-weight:650;color:{_INK};margin:7px 0 5px;">
            {idx}. {play.title}
          </div>
          <div style="font-size:13px;color:{_INK_MUTED};line-height:1.7;">{play.detail}</div>
          <div style="font-size:17px;font-weight:700;color:#10b981;margin-top:10px;">
            {_fmt_money(play.impact_amt)}
            <span style="font-size:11px;color:{_INK_MUTED};font-weight:400;"> {t("ov.rec.est_value")}</span>
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

    _mo = hover_month()
    _units = t("ov.trend.units")
    _proj_lbl = t("ov.rec.chart.projected")

    fig = go.Figure()
    fig.add_vrect(x0=hist.index[-1], x1=proj.index[-1],
                  fillcolor="rgba(99,102,241,0.06)", line_width=0, layer="below")
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist.values, name=t("ov.rec.chart.actual"), mode="lines",
        line=dict(color=_HUE_HISTORY, width=2),
        hovertemplate=f"{_mo} · %{{y:,.0f}} {_units}<extra></extra>",
    ))
    join = pd.concat([hist.iloc[[-1]], proj])
    fig.add_trace(go.Scatter(
        x=join.index, y=join.values, name=_proj_lbl, mode="lines",
        line=dict(color=_HUE_FORECAST, width=2.5, dash="dot"),
        hovertemplate=f"{_mo} · %{{y:,.0f}} {_units} ({_proj_lbl})<extra></extra>",
    ))
    if monthly_target:
        fig.add_hline(
            y=monthly_target, line=dict(color=_HUE_MARKER, width=1.4, dash="dash"),
            annotation_text=t("ov.rec.chart.plan_pace", v=fmt_num(monthly_target)),
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
    fig.update_yaxes(title=t("ov.rec.chart.yaxis"), range=[y_lo * 0.95, y_hi * 1.12])
    st.plotly_chart(fig, use_container_width=True)


def _render_recommendations(filters: dict) -> None:
    try:
        landing = overview_service.year_end_projection(filters)
        plays = overview_service.recommended_plays(filters, limit=5)
    except Exception as e:
        landing, plays = {}, []
        report_warning(t("ov.rec.unavailable"), e)

    gross_at_stake = sum(p.impact_amt for p in plays)
    att = landing.get("attainment_pct")
    gap = landing.get("unit_gap", 0.0)
    gpm = landing.get("gap_per_store_month", 0.0)

    k1, k2, k3 = st.columns(3)
    with k1:
        if att is None:
            render_kpi_card(t("ov.rec.landing"), t("val.na"),
                            t("ov.kpi.no_targets"), is_positive=False)
        else:
            short = gap > 0
            render_kpi_card(
                t("ov.rec.landing"),
                t("ov.rec.landing_pct", v=fmt_num(att)),
                delta=t("ov.rec.landing_delta",
                        sign=("−" if short else "+"),
                        units=fmt_num(abs(gap)),
                        money=_fmt_money(abs(gap) * overview_service.gross_per_unit())),
                is_positive=not short,
            )
    with k2:
        render_kpi_card(t("ov.rec.value_total"), _fmt_money(gross_at_stake),
                        delta=t("ov.rec.value_sub", n=len(plays)), is_positive=True)
    with k3:
        if att is None or gap <= 0:
            render_kpi_card(t("ov.rec.extra_needed"), t("ov.rec.extra_none"),
                            t("ov.rec.on_track"), is_positive=True)
        else:
            render_kpi_card(t("ov.rec.extra_needed"),
                            t("ov.rec.extra_val", v=fmt_num(gpm)),
                            delta=t("ov.rec.extra_sub"), is_positive=False)

    st.markdown("<br>", unsafe_allow_html=True)
    _section(t("ov.rec.next.title"), t("ov.rec.next.caption"))
    if plays:
        for i, p in enumerate(plays, 1):
            _render_play(i, p)
    else:
        st.info(t("ov.rec.none"))

    st.markdown("<br>", unsafe_allow_html=True)
    _section(t("ov.rec.chart.title"), t("ov.rec.chart.caption"))
    _render_landing_chart(landing)


# ═════════════════════════════════════════════════════════════════════════════
def render_overview(filters: dict):
    """Executive Overview — two views of the group: the 10-second performance
    read (Overview) and the ranked list of decisions to act on (Recommendations).
    Everything is the group's own data, no market extrapolation."""
    colors = get_color_palette()

    try:
        st.markdown(
            f"<h2 class='gradient-text' style='margin-bottom:10px;'>{t('ov.title')}</h2>",
            unsafe_allow_html=True,
        )

        tab_glance, tab_recs = st.tabs([t("ov.tab_glance"), t("ov.tab_recs")])

        with tab_glance:
            _render_glance(filters, colors)

        with tab_recs:
            _render_recommendations(filters)

    except Exception as e:
        report_error(t("ov.err.render"), e)
