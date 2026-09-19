from datetime import date

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from backend.db.connection import get_db_session
from backend.repositories.queries import get_scope_monthly_trend
from backend.analytics import yoy_attribution as ya
from backend.analytics.decision_engine import _project_series
from frontend.shared.ui import (
    _section,
    _base_layout,
    _fmt_money,
    _compact,
    _pct_label,
    _INK,
    _HUE_HISTORY,
    _HUE_FORECAST,
    _HUE_MARKER,
    _HUE_UP,
    _HUE_DOWN,
)

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _signed(value, fmt) -> str:
    """'+1.2K' / '−340' — a real minus glyph, formatted by the active measure."""
    return ("+" if value >= 0 else "−") + fmt(abs(value))


def render_comparison(filters: dict):
    session = get_db_session()

    try:
        st.markdown(
            "<h2 class='gradient-text' style='margin-bottom:14px;'>Comparative Analytics</h2>",
            unsafe_allow_html=True,
        )
        _render_tracking(session, filters)

    except Exception as e:  # noqa: BLE001 — surface, don't crash the tab
        st.error(f"Error rendering Comparative Analytics: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# How we're tracking vs last year
#
# There is deliberately no import-vs-domestic tariff view in this build. It
# would be possible for Germany (domestic industry, plus EU duties on Chinese
# the retail price. The old "Tariff exposure by franchise" subtab was
# removed in the UAE conversion, so this tab is a single view.
# ─────────────────────────────────────────────────────────────────────────────
def _render_tracking(session, filters: dict):
    measure = st.radio(
        "Measure", ["Units", "Revenue"], horizontal=True, key="cmp_measure",
    )
    is_units = measure == "Units"
    m_key = "units" if is_units else "revenue"
    vcol = "units" if is_units else "revenue"
    vword = "units" if is_units else "revenue"
    fmt = _compact if is_units else _fmt_money

    # "How are we tracking vs last year" is a trailing-12-month question, not a
    # whole-sidebar-window one: the attribution module anchors to the window's
    # end date and always compares the last 12 whole calendar months to the 12
    # before.
    summ = ya.summary(session, filters, m_key)
    if summ is None:
        st.info("No booked sales in the last 12 months for this scope.")
        return
    to_label = summ["windows"]["cur_label"]

    if not summ["comparable"]:
        st.warning(
            f"The 12 months before {to_label} reach past where booked data for this scope "
            "begins — treat the year-on-year percentages below as indicative only."
        )

    # ── Trend: last calendar year vs the current year on a Jan–Dec axis, with
    #    the rest of the current year filled in as a seasonal forecast ────────
    mt = get_scope_monthly_trend(session, filters)
    if mt.empty:
        st.info("No booked sales history for this scope.")
        return
    s_all = mt.set_index("date")[vcol].astype(float).sort_index()

    # drop a trailing partial month so neither the booked line nor the forecast
    # is anchored to a half-booked month
    if len(s_all) >= 14 and s_all.iloc[-1] < 0.55 * s_all.iloc[-13:-1].mean():
        s_all = s_all.iloc[:-1]

    cur_year = int(s_all.index[-1].year)
    ly = s_all[s_all.index.year == cur_year - 1]
    cy = s_all[s_all.index.year == cur_year]

    n_ahead = 12 - len(cy)
    fc = _project_series(s_all, n_ahead) if n_ahead > 0 else pd.Series(dtype=float)
    fc = fc[fc.index.year == cur_year]

    def _by_month(s):
        return {d.strftime("%b"): float(v) for d, v in s.items()}
    ly_m, cy_m, fc_m = _by_month(ly), _by_month(cy), _by_month(fc)

    ly_y = [ly_m.get(m) for m in _MONTHS]
    cy_y = [cy_m.get(m) for m in _MONTHS]
    # bridge the forecast line back to the last booked month so it connects
    fc_y = [None] * 12
    if cy_m:
        last_ix = max(i for i, m in enumerate(_MONTHS) if cy_m.get(m) is not None)
        fc_y[last_ix] = cy_m[_MONTHS[last_ix]]
    for i, m in enumerate(_MONTHS):
        if fc_m.get(m) is not None:
            fc_y[i] = fc_m[m]

    ly_total = float(ly.sum())
    cy_proj_total = float(cy.sum() + fc.sum())
    proj_yoy = (cy_proj_total / ly_total - 1) * 100 if ly_total else None

    _section(
        f"Last year vs this year  ·  {cur_year} monthly {vword}",
        (f"Solid = booked. Dashed = seasonal forecast for the rest of {cur_year}."
         if fc_m else f"Booked {vword} by calendar month, this year against last."),
    )
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=_MONTHS, y=ly_y, name=f"{cur_year - 1}", mode="lines+markers",
        line=dict(color=_HUE_HISTORY, width=2, dash="dot"), marker=dict(size=5),
        connectgaps=True,
        hovertemplate="%{x} " + str(cur_year - 1) + "<br>%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=_MONTHS, y=cy_y, name=f"{cur_year} (booked)", mode="lines+markers",
        line=dict(color=_HUE_FORECAST, width=3), marker=dict(size=6),
        connectgaps=True,
        hovertemplate="%{x} " + str(cur_year) + "<br>%{y:,.0f}<extra></extra>",
    ))
    if fc_m:
        fig.add_trace(go.Scatter(
            x=_MONTHS, y=fc_y, name=f"{cur_year} (forecast)", mode="lines+markers",
            line=dict(color=_HUE_MARKER, width=2.5, dash="dash"), marker=dict(size=5),
            connectgaps=True,
            hovertemplate="%{x} " + str(cur_year) + " (forecast)<br>%{y:,.0f}<extra></extra>",
        ))
    if proj_yoy is not None:
        if fc_m:
            head = f"{fmt(cy_proj_total)} {vword} projected for {cur_year}"
        elif len(cy) >= 12:
            head = f"{fmt(cy_proj_total)} {vword} in {cur_year}"
        else:
            head = f"{fmt(cy_proj_total)} {vword} in {cur_year} to date"
        fig.add_annotation(
            x=0, y=1.16, xref="paper", yref="paper", xanchor="left", showarrow=False,
            text=f"<b>{head}  ·  {_pct_label(proj_yoy, 1)} vs {cur_year - 1}</b>",
            font=dict(color=_INK, size=14),
        )
    fig.update_layout(**_base_layout(height=360, legend=True,
                                     margin=dict(l=0, r=0, t=54, b=0)))
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=_MONTHS)
    fig.update_yaxes(title=("Units / month" if is_units else "Revenue / month"))
    st.plotly_chart(fig, use_container_width=True)

    _render_drivers(session, filters, m_key, is_units, fmt, vword)


# ─────────────────────────────────────────────────────────────────────────────
# Driver split (structural vs specific) + significance
# ─────────────────────────────────────────────────────────────────────────────
def _render_drivers(session, filters, m_key, is_units, fmt, vword):
    dim_label = st.radio(
        "Break the change down by", ["Store", "Franchise", "Segment"],
        horizontal=True, key="cmp_dim",
        disabled=(filters.get("brand") is not None),
    )
    if filters.get("brand"):
        dim_label = "Store"
    dim = {"Store": "store", "Franchise": "brand", "Segment": "category"}[dim_label]

    split = ya.driver_split(session, filters, dim, m_key)
    if split is None or split.empty:
        st.info("No comparable prior-year period for this scope.")
        return

    n_sig = int(split["significant"].sum())
    only_sig = False
    if n_sig >= 3:
        only_sig = st.checkbox(
            f"Only the {n_sig} {dim_label.lower()}s outside their normal year-to-year range",
            value=True, key="cmp_only_sig",
        )

    d = split.copy()
    if only_sig:
        d = d[d["significant"]]
    d = d.reindex(d["specific"].abs().sort_values(ascending=False).index)
    cap = 16 if dim == "store" else 12
    d = d.head(cap).sort_values("specific")

    spec_label = ya.SPECIFIC_LABEL.get(dim, "Specific")
    _section(
        f"What moved it — by {dim_label.lower()}",
        "★ = unusual move for that {}".format(dim_label.lower()) if n_sig else None,
    )

    names = [f"{'★ ' if s else ''}{n}" for n, s in zip(d["name"], d["significant"])]
    opac = [1.0 if s else 0.6 for s in d["significant"]] if n_sig else [0.92] * len(d)
    tpos = ["inside" if v < 0 else "outside" for v in d["specific"]]

    fig = go.Figure(go.Bar(
        y=names, x=d["specific"], orientation="h",
        marker=dict(color=[_HUE_UP if v >= 0 else _HUE_DOWN for v in d["specific"]],
                    opacity=opac),
        text=[_signed(v, fmt) for v in d["specific"]],
        textposition=tpos, insidetextanchor="start", cliponaxis=False,
        textfont=dict(size=11, color=_INK),
        hovertemplate=("%{y}<br>" + spec_label.lower() + ": %{x:,.0f}"
                       "<br>total change vs last year: %{customdata:,.0f}<extra></extra>"),
        customdata=d["total"],
    ))
    fig.add_vline(x=0, line_color="rgba(255,255,255,0.25)", line_width=1.5)
    fig.update_layout(**_base_layout(
        height=max(260, 30 * len(d) + 60),
        margin=dict(l=10, r=70, t=10, b=10),
    ))
    fig.update_xaxes(title=f"{spec_label} change in {vword} (group-wide move removed)",
                     zeroline=False, showgrid=True, gridcolor="rgba(255,255,255,0.06)")
    fig.update_yaxes(title="")
    st.plotly_chart(fig, use_container_width=True)

    for line in ya.movement_sentences(split, dim, m_key, fmt, limit=3):
        st.markdown(f"- {line}")
