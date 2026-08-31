from datetime import date

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.queries import (
    get_period_trend,
    get_tariff_exposure,
    get_import_mix_monthly,
    get_price_gap_by_segment,
    get_franchise_footprint,
)
from analytics import yoy_attribution as ya
from utils.helpers import (
    _section,
    _base_layout,
    _fmt_money,
    _compact,
    _pct_label,
    _INK,
    _HUE_HISTORY,
    _HUE_FORECAST,
    _HUE_UP,
    _HUE_DOWN,
    _HUE_MARKER,
)

# One hue per job. The up/down greens and reds are reserved for "ahead of / behind
# last year"; the tariff section needs its own pair that can't be confused with
# them, so import vs domestic franchises read as amber vs sky.
_HUE_IMPORT = "#f59e0b"     # the group's import-brand rooftops (tariff-exposed)
_HUE_DOMESTIC = "#38bdf8"   # the group's domestic-brand rooftops


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

        tab_track, tab_tariff = st.tabs([
            "How we're tracking vs last year",
            "Tariff exposure by franchise",
        ])
        with tab_track:
            _render_tracking(session, filters)
        with tab_tariff:
            _render_tariff(session, filters)

    except Exception as e:  # noqa: BLE001 — surface, don't crash the tab
        st.error(f"Error rendering Comparative Analytics: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — How we're tracking vs last year
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
    # before. (The sidebar start date still drives the tariff section.)
    summ = ya.summary(session, filters, m_key)
    if summ is None:
        st.info("No booked sales in the last 12 months for this scope.")
        return
    to_label = summ["windows"]["cur_label"]
    win_start, win_end = summ["windows"]["cur"]
    ttm = {**filters, "start_date": win_start, "end_date": win_end}

    if not summ["comparable"]:
        st.warning(
            f"The 12 months before {to_label} reach past where booked data for this scope "
            "begins — treat the year-on-year percentages below as indicative only."
        )

    total_yoy = summ["total_yoy_pct"]

    # ── Trend: last 12 months vs the 12 before, on a calendar-month axis ────
    # (The x-axis is month names, not dates: the grey line is the *same months a
    # year earlier*, so plotting real dates put 2024 data under 2025 labels and
    # read as confusing. Month names + explicit ranges in the caption make the
    # month-over-month comparison unambiguous.)
    trend = get_period_trend(session, ttm)
    tcur = trend[trend["period"] == "This period"].sort_values("date")
    tprev = trend[trend["period"] == "Prior year"].sort_values("date")

    month_order = list(tcur["date"].dt.strftime("%b")) if not tcur.empty else []

    _section(f"How we're tracking vs last year  ·  12 months to {to_label}")
    fig = go.Figure()
    if not tprev.empty:
        fig.add_trace(go.Scatter(
            x=tprev["date"].dt.strftime("%b"), y=tprev[vcol],
            name="Prior 12 months", mode="lines",
            line=dict(color=_HUE_HISTORY, width=2, dash="dot"),
            customdata=(tprev["date"] - pd.DateOffset(years=1)).dt.strftime("%b %Y"),
            hovertemplate="%{customdata}<br>%{y:,.0f}<extra>Prior 12 months</extra>",
        ))
    fig.add_trace(go.Scatter(
        x=tcur["date"].dt.strftime("%b"), y=tcur[vcol],
        name="Last 12 months", mode="lines",
        line=dict(color=_HUE_FORECAST, width=3),
        fill="tonexty" if not tprev.empty else None,
        fillcolor="rgba(99,102,241,0.08)",
        customdata=tcur["date"].dt.strftime("%b %Y"),
        hovertemplate="%{customdata}<br>%{y:,.0f}<extra>Last 12 months</extra>",
    ))
    if total_yoy is not None:
        fig.add_annotation(
            x=0, y=1.16, xref="paper", yref="paper", xanchor="left", showarrow=False,
            text=(f"<b>{fmt(summ['total_end'])} {vword} in the last 12 months  ·  "
                  f"{_pct_label(total_yoy, 1)} vs the 12 before</b>"),
            font=dict(color=_INK, size=14),
        )
    fig.update_layout(**_base_layout(height=360, legend=True,
                                     margin=dict(l=0, r=0, t=54, b=0)))
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=month_order)
    fig.update_yaxes(title=("Units / month" if is_units else "Revenue / month"))
    st.plotly_chart(fig, use_container_width=True)

    _render_drivers(session, filters, m_key, is_units, fmt, vword)


# ─────────────────────────────────────────────────────────────────────────────
# Feature 1 + Feature 5 — driver split (structural vs specific) + significance
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
    # negative bars grow left into the y-label gutter — keep their text inside
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
        st.markdown(f"- {line}".replace("$", "\\$"))


# ─────────────────────────────────────────────────────────────────────────────
# Section 2 — Tariff Exposure by Franchise
# ─────────────────────────────────────────────────────────────────────────────
def _render_tariff(session, filters: dict):
    foot = get_franchise_footprint(session, filters)
    n_import = n_total = 0
    if not foot.empty:
        is_imp = foot["origin"].isin(["Japanese", "Korean", "European"])
        n_import = int(foot.loc[is_imp, "rooftops"].sum())
        n_total = int(foot["rooftops"].sum())

    exp = get_tariff_exposure(session, filters)
    if exp.empty:
        st.info(
            "No booked sales on or after April 2025 in the selected window — "
            "widen the date range to see tariff exposure."
        )
        return

    total_units = float(exp["units"].sum())
    imp = exp[exp["is_import"]]
    dom = exp[exp["origin"] == "Domestic"]

    imp_units = float(imp["units"].sum())
    imp_tariff = float(imp["tariff_total"].sum())
    dom_units = float(dom["units"].sum())
    dom_tariff = float(dom["tariff_total"].sum())

    if imp_units == 0:
        st.info(
            "No imported units in this scope since April 2025 — the group's rooftops "
            "here are domestic-brand, so there's no Section 232 exposure to show."
        )
        return

    per_imp = imp_tariff / imp_units if imp_units else 0.0
    per_dom = dom_tariff / dom_units if dom_units else 0.0
    imp_share = (imp_units / total_units * 100) if total_units else 0.0

    # forward run-rate: import tariff dollars ÷ whole months the duty has been in
    # effect within the window, annualised
    end_d = filters.get("end_date") or date.today()
    months_active = max((end_d.year - 2025) * 12 + (end_d.month - 4) + 1, 1)
    annual_imp = imp_tariff / months_active * 12

    dollars = lambda v: f"${v:,.0f}"

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric(
            "Volume exposed to the duty", f"{imp_share:.0f}%",
            delta=f"{n_import} of {n_total} rooftops are import franchises"
            if n_total else "import-brand rooftops",
            delta_color="off",
        )
    with m2:
        st.metric(
            "Tariff carried into import prices", _fmt_money(imp_tariff),
            delta=f"≈ {_fmt_money(annual_imp)}/yr at this run-rate", delta_color="off",
        )
    with m3:
        st.metric(
            "Added cost per imported unit", dollars(per_imp),
            delta=f"+{dollars(per_imp - per_dom)} vs a domestic unit", delta_color="off",
        )

    # ── Chart A: did the tariff shift the group's import↔domestic mix? ───────
    mix = get_import_mix_monthly(session, filters)
    shift_pts = None
    if not mix.empty and len(mix) >= 6:
        cut = pd.Timestamp(2025, 4, 1)
        pre = mix.loc[mix["date"] < cut, "import_share_pct"]
        post = mix.loc[mix["date"] >= cut, "import_share_pct"]
        pre_avg = float(pre.mean()) if not pre.empty else None
        post_avg = float(post.mean()) if not post.empty else None
        if pre_avg is not None and post_avg is not None:
            shift_pts = post_avg - pre_avg

        _section("Did the tariff shift our mix?")

        smooth = mix["import_share_pct"].rolling(3, center=True, min_periods=2).mean()
        x0, x1 = mix["date"].min(), mix["date"].max()
        figA = go.Figure()
        figA.add_trace(go.Scatter(
            x=mix["date"], y=mix["import_share_pct"], mode="markers", name="Monthly",
            marker=dict(size=4, color=_HUE_IMPORT, opacity=0.35),
            hovertemplate="%{x|%b %Y}<br>%{y:.0f}% import (that month)<extra></extra>",
        ))
        figA.add_trace(go.Scatter(
            x=mix["date"], y=smooth, mode="lines", name="3-month average",
            line=dict(color=_HUE_IMPORT, width=3),
            hovertemplate="%{x|%b %Y}<br>%{y:.1f}% import (3-mo avg)<extra></extra>",
        ))
        if pre_avg is not None:
            figA.add_trace(go.Scatter(
                x=[x0, x1], y=[pre_avg, pre_avg], mode="lines",
                name=f"Before Apr 2025 · {pre_avg:.1f}%",
                line=dict(color=_HUE_HISTORY, width=1, dash="dot"), hoverinfo="skip",
            ))
        if post_avg is not None:
            figA.add_trace(go.Scatter(
                x=[x0, x1], y=[post_avg, post_avg], mode="lines",
                name=f"Since Apr 2025 · {post_avg:.1f}%",
                line=dict(color=_HUE_DOMESTIC, width=1, dash="dot"), hoverinfo="skip",
            ))
        cut_ts = pd.Timestamp(2025, 4, 1)
        figA.add_vline(
            x=cut_ts.timestamp() * 1000, line_width=1.5, line_dash="dot",
            line_color=_HUE_MARKER, annotation_text="25% duty starts",
            annotation_position="bottom right",
            annotation_font=dict(color=_HUE_MARKER, size=11),
        )
        figA.update_layout(**_base_layout(height=320, legend=True,
                                          margin=dict(l=0, r=0, t=30, b=0)))
        figA.update_yaxes(title="% of units · import rooftops", ticksuffix="%")
        st.plotly_chart(figA, use_container_width=True)

    # ── Chart B: import vs domestic price, with the tariff slice called out ──
    gap = get_price_gap_by_segment(session, filters)
    top_tariff_seg, top_tariff_amt = None, None
    if not gap.empty:
        w = gap[gap["group"].isin(["Import franchises", "Domestic franchises"])].copy()
        # Only segments with real volume on BOTH sides — a genuine cross-shop, not
        # a thin cell (this drops Luxury, where the group's one domestic-luxury
        # nameplate is Tesla and the comparison isn't like-for-like).
        w = w[w["units"] >= 150]
        piv = w.pivot_table(index="vehicle_category", columns="group",
                            values=["avg_price", "avg_tariff"], aggfunc="first")
        need = {("avg_price", "Import franchises"), ("avg_price", "Domestic franchises")}
        if need.issubset(set(piv.columns)):
            both = [c for c in piv.index
                    if not pd.isna(piv.loc[c, ("avg_price", "Import franchises")])
                    and not pd.isna(piv.loc[c, ("avg_price", "Domestic franchises")])]
            piv = piv.loc[both]
        else:
            piv = piv.iloc[0:0]
        if not piv.empty:
            imp_price = piv[("avg_price", "Import franchises")]
            imp_duty = piv[("avg_tariff", "Import franchises")]
            dom_price = piv[("avg_price", "Domestic franchises")]
            order = imp_price.sort_values().index.tolist()
            piv = piv.loc[order]
            imp_price, imp_duty, dom_price = imp_price[order], imp_duty[order], dom_price[order]

            _im = imp_duty.idxmax()
            top_tariff_seg, top_tariff_amt = _im, float(imp_duty.loc[_im])

            y_imp = [f"{c}  ·  Import" for c in order]
            y_dom = [f"{c}  ·  Domestic" for c in order]
            y_all = [v for pair in zip(y_dom, y_imp) for v in pair]  # domestic under import

            _section("What a shopper pays — and the tariff inside it, by segment")
            figB = go.Figure()
            figB.add_trace(go.Bar(
                y=y_dom, x=dom_price.values, orientation="h",
                name="Domestic — vehicle price", marker_color=_HUE_DOMESTIC,
                text=[dollars(v) for v in dom_price.values],
                textposition="outside", cliponaxis=False, textfont=dict(color=_INK),
                hovertemplate="%{y}<br>%{x:$,.0f}<extra></extra>",
            ))
            figB.add_trace(go.Bar(
                y=y_imp, x=(imp_price - imp_duty).values, orientation="h",
                name="Import — vehicle price", marker_color=_HUE_IMPORT,
                hovertemplate="%{y}<br>price ex-duty %{x:$,.0f}<extra></extra>",
            ))
            figB.add_trace(go.Bar(
                y=y_imp, x=imp_duty.values, orientation="h",
                name="Import — Section 232 duty", marker_color=_HUE_DOWN,
                text=[dollars(v) for v in imp_price.values],
                textposition="outside", cliponaxis=False, textfont=dict(color=_INK),
                hovertemplate="%{y}<br>duty in price %{x:$,.0f}<extra></extra>",
            ))
            figB.update_layout(**_base_layout(
                height=max(320, 40 * len(y_all) + 90), legend=True, barmode="stack",
                margin=dict(l=10, r=95, t=64, b=10),
            ))
            figB.update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=1.06,
                            xanchor="left", x=0),
                yaxis=dict(categoryorder="array", categoryarray=y_all,
                           showgrid=False, title=""),
            )
            figB.update_xaxes(title="Average selling price", tickprefix="$",
                              showgrid=True, gridcolor="rgba(255,255,255,0.06)")
            st.plotly_chart(figB, use_container_width=True)

    # ── Plain-language takeaway ────────────────────────────────────────────
    msg = (
        f"**Since April 2025**, {imp_share:.0f}% of the group's sales carry the duty — "
        f"**{_fmt_money(imp_tariff)}** of tariff cost in import prices (≈ {_fmt_money(annual_imp)}/yr), "
        f"about **{dollars(per_imp)} per imported unit** vs {dollars(per_dom)} on a domestic one"
    )
    if top_tariff_seg is not None:
        msg += f"; heaviest on imported **{top_tariff_seg}** (~{dollars(top_tariff_amt)}/unit)"
    if shift_pts is not None:
        if abs(shift_pts) < 1.0:
            msg += ". The import share of the group's mix has held steady"
        else:
            moved = "toward the group's domestic rooftops" if shift_pts < 0 else "toward import"
            msg += f". The mix has moved **{abs(shift_pts):.1f} pts {moved}** since the duty"
    st.success((msg + ".").replace("$", "\\$"))
