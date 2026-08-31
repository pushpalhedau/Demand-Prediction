"""
Sentiment Analysis — a demand advisory for the dealer group.

Not a geopolitical-risk desk. The question this tab answers is: what's in the
news right now that will move showroom traffic, demand mix, vehicle cost and
financing over the next few weeks — and what should the group do about it?

Two sub-tabs:
  Demand Watch                  — the net demand signal, its drivers, and a
                                  scannable list of signals with a dealer action
  Does news improve our forecast? — baseline Prophet vs a news-aware model,
                                  answered in plain language
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.models import Sale
from sentiment.signal_processor import (
    run_full_pipeline,
    ensure_recent_articles_analyzed,
    compute_live_overall_stats,
    compute_live_category_summary,
)
from sentiment.fetchers.gdelt_fetcher import get_stored_articles, TIMESPAN_OPTIONS
from sentiment.analyzers.grok_analyzer import generate_market_briefing
from utils.helpers import (
    _section,
    _base_layout,
    _pct_label,
    _INK,
    _INK_MUTED,
    _HUE_UP,
    _HUE_DOWN,
    _HUE_FORECAST,
    _HUE_HISTORY,
    _HUE_MARKER,
)

# ─────────────────────────────────────────────────────────────────────────────
# Framing constants
# ─────────────────────────────────────────────────────────────────────────────

# The group's own book — used to express each signal as the group's exposure.
# Kept in sync with the dealer-positioning changelogs.
_IMPORT_UNIT_SHARE = 0.56
_SEGMENT_LABEL = {
    "SUV": "SUV", "Pickup": "pickup", "Sedan": "sedan", "Luxury": "luxury",
    "EV": "EV", "Commercial": "commercial", "All": "all segments",
}

# get_stored_articles() returns `theme` = the GDELT query name.
_THEME_LABEL = {
    "na_auto_demand": "Auto demand",
    "ev_market_na": "EV market",
    "tariff_trade": "Tariffs & trade",
    "fuel_oil_prices": "Fuel prices",
    "us_macro_economy": "Economy & rates",
    "luxury_suv_na": "Luxury / SUV / pickup",
    "auto_financing": "Auto financing",
    "incentives_rebates": "Incentives & rebates",
}

# What a signal on this theme is mostly about, for the exposure line.
_THEME_EXPOSURE = {
    "tariff_trade": f"hits the group's import franchises — about {_IMPORT_UNIT_SHARE*100:.0f}% of units",
    "auto_financing": "moves financed demand across the whole book — fastest-acting driver",
    "us_macro_economy": "moves financed demand across the whole book",
    "fuel_oil_prices": "shifts mix between pickup/SUV and sedan",
    "incentives_rebates": "changes the incentive backdrop the desk is working against",
    "ev_market_na": "affects the group's EV rooftops (Tesla + import BEVs)",
}

_DIR_ARROW = {"up": "▲", "down": "▼", "neutral": "■"}


# ─────────────────────────────────────────────────────────────────────────────
# Small helpers
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def _group_monthly_runrate() -> float:
    """Group's average booked units per month over the last 12 months of data —
    so the headline % can be expressed as a rough unit count."""
    s = get_db_session()
    try:
        rows = s.query(Sale.sale_date, Sale.units_sold).all()
        if not rows:
            return 0.0
        df = pd.DataFrame(rows, columns=["sale_date", "units"])
        df["sale_date"] = pd.to_datetime(df["sale_date"])
        cutoff = df["sale_date"].max() - pd.DateOffset(months=12)
        last12 = df[df["sale_date"] >= cutoff]["units"].sum()
        return float(last12) / 12.0
    except Exception:
        return 0.0
    finally:
        s.close()


def _empty_state(msg: str):
    st.markdown(
        f"<div style='background:rgba(148,163,184,0.08);border:1px solid rgba(148,163,184,0.2);"
        f"border-radius:12px;padding:26px;text-align:center;color:{_INK_MUTED};font-size:14px;'>{msg}</div>",
        unsafe_allow_html=True,
    )


def _signal_word(net_pct: float) -> tuple:
    if net_pct > 0.75:
        return "tailwind", _HUE_UP
    if net_pct < -0.75:
        return "headwind", _HUE_DOWN
    return "roughly flat", _INK_MUTED


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_sentiment_analysis(filters: dict):
    st.markdown(
        "<h2 class='gradient-text' style='margin-bottom:12px;'>Sentiment Analysis</h2>",
        unsafe_allow_html=True,
    )

    # ── Refresh controls ─────────────────────────────────────────────────
    c1, c2, _ = st.columns([2, 2, 4])
    with c1:
        timespan_label = st.selectbox(
            "News window", options=list(TIMESPAN_OPTIONS.keys()), index=1, key="sentiment_timespan"
        )
        timespan = TIMESPAN_OPTIONS[timespan_label]
    running = st.session_state.get("sentiment_pipeline_running", False)
    with c2:
        st.markdown("<div style='margin-top:28px;'>", unsafe_allow_html=True)
        refresh = st.button("Refresh news", type="primary", use_container_width=True, disabled=running)
        st.markdown("</div>", unsafe_allow_html=True)

    if refresh and not running:
        st.session_state["sentiment_pipeline_running"] = True
        try:
            with st.spinner("Fetching news from GDELT and scoring signals…"):
                status = run_full_pipeline(timespan=timespan, max_articles_per_query=50, analyze_limit=200)
            st.session_state["sentiment_pipeline_status"] = status
        finally:
            st.session_state["sentiment_pipeline_running"] = False
        st.rerun()

    if "sentiment_pipeline_status" in st.session_state:
        _show_pipeline_status(st.session_state["sentiment_pipeline_status"])

    # ── Pull the current signal picture ─────────────────────────────────
    ensure_recent_articles_analyzed(limit=30)
    stats = compute_live_overall_stats(days_back=30)
    articles = get_stored_articles(days_back=45, analyzed_only=True, limit=400)

    st.markdown("<br>", unsafe_allow_html=True)

    if stats.get("total_articles", 0) == 0 or not articles:
        _empty_state(
            "No recent signals yet.<br>Click <b>Refresh news</b> above to pull the latest "
            "US auto headlines and score them for the group's demand."
        )
        return

    _headline_block(stats)
    st.markdown("<br>", unsafe_allow_html=True)
    _bottom_line(stats, articles)
    st.markdown("<br>", unsafe_allow_html=True)

    tab_watch, tab_fc = st.tabs(["Demand Watch", "Does news improve our forecast?"])
    with tab_watch:
        _render_demand_watch(stats, articles)
    with tab_fc:
        _render_forecast_verdict(filters)


# ─────────────────────────────────────────────────────────────────────────────
# Headline
# ─────────────────────────────────────────────────────────────────────────────

def _headline_block(stats: dict):
    net = float(stats.get("net_demand_signal_pct", 0.0))
    word, color = _signal_word(net)
    runrate = _group_monthly_runrate()
    unit_est = round(runrate * net / 100.0)

    left, right = st.columns([3, 2])
    with left:
        st.markdown(
            f"<div style='color:{_INK_MUTED};font-size:12px;letter-spacing:.4px;"
            f"text-transform:uppercase;margin-bottom:2px;'>Expected demand impact · next ~30 days</div>"
            f"<div style='font-size:44px;font-weight:800;color:{color};line-height:1.1;'>"
            f"{_pct_label(net, 1)}</div>"
            f"<div style='color:{_INK};font-size:14px;margin-top:2px;'>"
            f"{word.capitalize()}"
            + (f" &nbsp;·&nbsp; about {unit_est:+,} units vs a normal month" if runrate else "")
            + "</div>",
            unsafe_allow_html=True,
        )
    with right:
        g = go.Figure(go.Indicator(
            mode="gauge+number",
            value=net,
            number={"suffix": "%", "font": {"size": 26, "color": color}},
            gauge={
                "axis": {"range": [-6, 6], "tickvals": [-3, 0, 3], "ticks": "",
                         "tickfont": {"size": 10, "color": _INK_MUTED}},
                "bar": {"color": color, "thickness": 0.28},
                "borderwidth": 0,
                "steps": [
                    {"range": [-6, -0.75], "color": "rgba(239,68,68,0.16)"},
                    {"range": [-0.75, 0.75], "color": "rgba(148,163,184,0.16)"},
                    {"range": [0.75, 6], "color": "rgba(16,185,129,0.16)"},
                ],
            },
        ))
        g.update_layout(**_base_layout(height=180, margin=dict(l=24, r=24, t=16, b=0)))
        st.plotly_chart(g, use_container_width=True, config={"displayModeBar": False})
        st.markdown(
            f"<div style='text-align:center;color:{_INK_MUTED};font-size:11px;margin-top:-8px;'>"
            "headwind &nbsp;·&nbsp; flat &nbsp;·&nbsp; tailwind</div>",
            unsafe_allow_html=True,
        )


def _bottom_line(stats: dict, articles: list):
    """
    Always-visible plain-language conclusion synthesised from the current
    signals — direction + size + horizon, the leading driver, the segments most
    exposed, and the one call for the week. Deterministic (no Grok); this is the
    "so what" the earlier tabs each close with.
    """
    net = float(stats.get("net_demand_signal_pct", 0.0))
    df = pd.DataFrame(articles)
    df["demand_change_pct"] = pd.to_numeric(df.get("demand_change_pct"), errors="coerce")
    df["_dir"] = df["demand_direction"].fillna("neutral")
    n_signal = int((df["_dir"] != "neutral").sum())

    tmean = (
        df.dropna(subset=["demand_change_pct"])
        .groupby("theme")["demand_change_pct"].mean()
    )
    drivers = sorted(
        [(t, v) for t, v in tmean.items() if abs(v) >= 0.1],
        key=lambda x: abs(x[1]), reverse=True,
    )
    segs = sorted(
        [(k, v) for k, v in (stats.get("segment_changes") or {}).items()
         if k != "All" and abs(v) >= 0.05],
        key=lambda x: abs(x[1]), reverse=True,
    )[:2]

    up_n = int((df["_dir"] == "up").sum())
    dn_n = int((df["_dir"] == "down").sum())

    if n_signal == 0:
        color = _INK_MUTED
        body = (
            "No single story is moving the group's demand right now — the news nets out "
            "<b>roughly neutral</b> over the next ~30 days. Nothing here calls for a change "
            "to stocking or pricing; run the standard demand forecast and keep scanning the "
            "feed for a rate move, a tariff change, or a gas-price swing that would."
        )
    elif abs(net) < 0.5:
        color = _INK_MUTED
        _t = df.assign(_t=df["theme"].map(_THEME_LABEL).fillna(df["theme"]))
        up_theme = ", ".join(sorted(_t[_t["_dir"] == "up"]["_t"].dropna().unique())[:2]).lower() or "supportive news"
        dn_theme = ", ".join(sorted(_t[_t["_dir"] == "down"]["_t"].dropna().unique())[:2]).lower() or "headwind news"
        body = (
            f"The news is <b>mixed and nets out roughly flat</b> over the next ~30 days — "
            f"{up_n} supportive signal{'s' if up_n != 1 else ''} ({up_theme}) roughly offset "
            f"{dn_n} headwind{'s' if dn_n != 1 else ''} ({dn_theme}). No net stocking or "
            "pricing call for the group; work the individual signals below on their own merits."
        )
    else:
        word = "headwind" if net < 0 else "tailwind"
        color = _HUE_DOWN if net < 0 else _HUE_UP
        rr = _group_monthly_runrate()
        _u = round(rr * net / 100.0)
        unit_hint = f", roughly {f'{_u:+,}'.replace('-', '−')} units against a normal month" if rr else ""
        parts = [
            f"The news adds up to a mild <b>{word}</b> ({_pct_label(net, 1)}{unit_hint}) for "
            "the group's showroom demand over the next ~30 days."
        ]
        if drivers:
            d_theme, d_val = drivers[0]
            exp = _THEME_EXPOSURE.get(d_theme)
            d_lbl = _THEME_LABEL.get(d_theme, d_theme)
            parts.append(
                f"The leading driver is <b>{d_lbl.lower()}</b>"
                + (f" — {exp}." if exp else f" ({_pct_label(d_val, 1)}).")
            )
        if segs:
            parts.append(
                "Most exposed: "
                + " and ".join(f"{_SEGMENT_LABEL.get(s, s)} ({_pct_label(v, 1)})" for s, v in segs)
                + "."
            )
        if net < 0:
            dn = _SEGMENT_LABEL.get(segs[0][0], "the affected segments") if segs and segs[0][1] < 0 else "the affected segments"
            parts.append(
                f"<b>This week:</b> protect days'-supply on {dn}, keep the desk leading with "
                "monthly-payment and trade-equity talk-tracks, and be ready to pull incentive "
                "spend forward if showroom traffic softens."
            )
        else:
            up = _SEGMENT_LABEL.get(segs[0][0], "the segments in favour") if segs and segs[0][1] > 0 else "the segments in favour"
            parts.append(
                f"<b>This week:</b> keep {up} stock full at the higher-volume rooftops and hold "
                "margin — you shouldn't need extra discount while this holds."
            )
        body = " ".join(parts)

    st.markdown(
        f"""<div style="border:1px solid {color}44;border-left:4px solid {color};
        background:{color}12;border-radius:12px;padding:16px 18px;">
          <div style="color:{color};font-size:12px;font-weight:700;letter-spacing:.4px;
          text-transform:uppercase;margin-bottom:6px;">Bottom line</div>
          <div style="color:{_INK};font-size:13.5px;line-height:1.65;">{body}</div>
        </div>""",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Demand Watch
# ─────────────────────────────────────────────────────────────────────────────

def _render_demand_watch(stats: dict, articles: list):
    df = pd.DataFrame(articles)
    df["demand_change_pct"] = pd.to_numeric(df.get("demand_change_pct"), errors="coerce")
    df["impact_score"] = pd.to_numeric(df.get("impact_score"), errors="coerce")
    df["_dir"] = df["demand_direction"].fillna("neutral")

    quiet = (df["_dir"] != "neutral").sum() == 0

    if not quiet:
        # ── Drivers: mean signal by news theme ────────────────────────
        _section("What's driving the signal")
        by_theme = (
            df.dropna(subset=["demand_change_pct"])
            .assign(theme_label=df["theme"].map(_THEME_LABEL).fillna(df["theme"]))
            .groupby("theme_label")["demand_change_pct"].mean()
            .sort_values()
        )
        fig = go.Figure(go.Bar(
            x=by_theme.values, y=by_theme.index, orientation="h",
            marker_color=[_HUE_UP if v >= 0 else _HUE_DOWN for v in by_theme.values],
            text=[_pct_label(v, 1) for v in by_theme.values],
            textposition="outside",
            hovertemplate="%{y}: %{x:+.1f}%<extra></extra>",
        ))
        tspan = max(abs(by_theme.min()), abs(by_theme.max()), 0.5) * 1.3
        fig.add_vline(x=0, line_color="rgba(148,163,184,0.35)")
        fig.update_layout(**_base_layout(height=max(200, 42 * len(by_theme)),
                                         xaxis=dict(title="", showgrid=False, zeroline=False,
                                                    range=[-tspan, tspan])))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Segment view: mix-weighted ─────────────────────────────────────
    seg_changes = {k: v for k, v in (stats.get("segment_changes") or {}).items() if k != "All"}
    if seg_changes and max(abs(v) for v in seg_changes.values()) >= 0.05:
        _section(
            "By segment",
            "News-driven demand change per vehicle segment. The headline weights these by the group's own sales mix.",
        )
        ser = pd.Series(seg_changes).sort_values()
        span = max(abs(ser.min()), abs(ser.max()), 0.5) * 1.25
        fig = go.Figure(go.Bar(
            x=ser.values, y=[_SEGMENT_LABEL.get(s, s) for s in ser.index], orientation="h",
            marker_color=[_HUE_UP if v >= 0 else _HUE_DOWN for v in ser.values],
            text=[_pct_label(v, 1) for v in ser.values], textposition="outside",
            hovertemplate="%{y}: %{x:+.1f}%<extra></extra>",
        ))
        fig.add_vline(x=0, line_color="rgba(148,163,184,0.35)")
        fig.update_layout(**_base_layout(height=max(180, 42 * len(ser)),
                                         xaxis=dict(title="", showgrid=False, zeroline=False,
                                                    range=[-span, span])))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Signal list ───────────────────────────────────────────────────
    df["rank"] = (df["impact_score"].fillna(0) * df["demand_change_pct"].abs().fillna(0))
    actionable = df[df["_dir"] != "neutral"].sort_values("rank", ascending=False).head(8)
    if actionable.empty:
        _section(
            "Latest headlines scanned",
            "None carry a clear demand read this window — shown so you can see what's in the feed.",
        )
        for _, a in df.sort_values("published_date", ascending=False).head(5).iterrows():
            _signal_card(a)
    else:
        _section("Signals to work")
        for _, a in actionable.iterrows():
            _signal_card(a)

    # ── This week's read (briefing) ───────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    _section("This week's read for the group")
    if st.button("Generate read", key="gen_briefing"):
        with st.spinner("Writing…"):
            cat_df = compute_live_category_summary(days_back=30)
            cat_rows = []
            if not cat_df.empty:
                agg = (cat_df.groupby("category")[["sentiment", "demand_change"]]
                       .mean().reset_index())
                cat_rows = [
                    {"category": r["category"], "avg_sentiment": r["sentiment"],
                     "avg_demand_change": r["demand_change"]}
                    for _, r in agg.iterrows()
                ]
            st.session_state["sentiment_briefing"] = generate_market_briefing(stats, cat_rows)
    if st.session_state.get("sentiment_briefing"):
        st.markdown(
            f"<div style='background:rgba(17,24,39,0.6);border:1px solid rgba(255,255,255,0.08);"
            f"border-radius:12px;padding:18px 20px;color:{_INK};font-size:13.5px;line-height:1.7;"
            f"white-space:pre-wrap;'>{st.session_state['sentiment_briefing']}</div>",
            unsafe_allow_html=True,
        )


def _signal_card(a: pd.Series):
    direction = (a.get("demand_direction") or "neutral")
    chg = a.get("demand_change_pct")
    color = _HUE_UP if direction == "up" else (_HUE_DOWN if direction == "down" else _INK_MUTED)
    seg = a.get("affected_category") or "All"
    theme = a.get("theme")
    exposure = _THEME_EXPOSURE.get(theme)
    if not exposure:
        if seg in ("All", None):
            exposure = "affects showroom traffic across the whole book"
        else:
            exposure = f"lands on the group's {_SEGMENT_LABEL.get(seg, seg)} demand"
    title = (a.get("title") or "Untitled")[:150]
    url = a.get("url") or ""
    title_html = f"<a href='{url}' target='_blank' style='color:{_INK};text-decoration:none;'>{title}</a>" if url else title
    chg_txt = f"{_DIR_ARROW.get(direction,'■')} {_pct_label(chg,1)}" if pd.notna(chg) else _DIR_ARROW.get(direction, "■")
    action = a.get("signal_summary") or ""

    st.markdown(
        f"""<div style="border:1px solid rgba(255,255,255,0.08);border-left:3px solid {color};
        border-radius:10px;padding:12px 14px;margin-bottom:10px;background:rgba(17,24,39,0.45);">
          <div style="display:flex;justify-content:space-between;gap:12px;">
            <div style="font-size:13.5px;font-weight:600;color:{_INK};">{title_html}</div>
            <div style="color:{color};font-weight:700;font-size:13px;white-space:nowrap;">{chg_txt}</div>
          </div>
          <div style="color:{_INK_MUTED};font-size:11.5px;margin-top:4px;">
            {a.get('domain') or '—'} &nbsp;·&nbsp; {a.get('published_date') or '—'}
            &nbsp;·&nbsp; {_THEME_LABEL.get(theme, theme or '—')}
            &nbsp;·&nbsp; <span style="color:{color};">{_SEGMENT_LABEL.get(seg, seg)}</span> — {exposure}
          </div>
          <div style="color:{_INK};font-size:12.5px;margin-top:6px;">{action}</div>
        </div>""",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Does news improve our forecast?
# ─────────────────────────────────────────────────────────────────────────────

def _render_forecast_verdict(filters: dict):
    _section("Does watching the news actually improve our forecast?")

    try:
        from forecasting.prophet_forecasting import train_prophet_model
    except Exception as e:
        _empty_state(f"Forecast engine unavailable: {e}")
        return

    c1, c2, _ = st.columns([2, 2, 4])
    with c1:
        horizon = st.selectbox("Look ahead", [30, 60, 90, 180], index=2, key="fc_v_horizon",
                               format_func=lambda d: f"{d} days")
    with c2:
        target = st.selectbox("Measure", ["units_sold", "total_revenue_incl_tax"],
                              format_func=lambda x: "Units" if x == "units_sold" else "Revenue",
                              key="fc_v_target")
    with c1:
        run = st.button("Run check", type="primary", key="fc_v_run")

    if run:
        with st.spinner("Training both models…"):
            base_res, base_err = train_prophet_model(
                category=filters.get("vehicle_category"), region=filters.get("region"),
                fuel_type=filters.get("fuel_type"), brand=filters.get("brand"),
                target=target, horizon_days=horizon, use_sentiment=False,
            )
            sent_res, sent_err = train_prophet_model(
                category=filters.get("vehicle_category"), region=filters.get("region"),
                fuel_type=filters.get("fuel_type"), brand=filters.get("brand"),
                target=target, horizon_days=horizon, use_sentiment=True,
            )
        st.session_state["fc_v"] = (base_res, base_err, sent_res, sent_err, target)

    if "fc_v" not in st.session_state:
        st.info("Click **Run check** to compare.")
        return

    base_res, base_err, sent_res, sent_err, _target = st.session_state["fc_v"]
    if base_err or not base_res:
        st.error(f"Baseline forecast failed: {base_err}")
        return

    # ── One chart (monthly, to match the Demand Forecasting tab) ─────
    def _monthly(df):
        d = df.copy()
        d["ds"] = pd.to_datetime(d["ds"])
        d["m"] = d["ds"].dt.to_period("M").dt.to_timestamp()
        g = d.groupby("m").agg(yhat=("yhat", "sum"),
                               actual=("actual", "sum"),
                               n=("yhat", "size"),
                               act_n=("actual", "count")).reset_index()
        # drop partial edge months so the line doesn't dip artificially
        g = g[g["n"] >= 20]
        g.loc[g["act_n"] < 20, "actual"] = pd.NA
        return g

    fc = _monthly(base_res["forecast"])
    split_raw = pd.to_datetime(base_res["forecast"]["ds"])[
        base_res["forecast"]["actual"].isnull()
    ].min()
    split = pd.to_datetime(split_raw).to_period("M").to_timestamp() if pd.notnull(split_raw) else None
    start = (split - pd.DateOffset(months=12)) if split is not None else fc["m"].min()
    fc = fc[fc["m"] >= start]

    fig = go.Figure()
    act = fc[fc["actual"].notna()]
    fig.add_trace(go.Scatter(x=act["m"], y=act["actual"], name="Actual", mode="lines+markers",
                             line=dict(color=_HUE_HISTORY, width=2), marker=dict(size=5)))
    fig.add_trace(go.Scatter(x=fc["m"], y=fc["yhat"], name="Standard forecast", mode="lines",
                             line=dict(color=_HUE_FORECAST, width=2.5)))
    if sent_res and not sent_err:
        sfc = _monthly(sent_res["forecast"])
        sfc = sfc[sfc["m"] >= start]
        fig.add_trace(go.Scatter(x=sfc["m"], y=sfc["yhat"], name="News-aware forecast", mode="lines",
                                 line=dict(color="#ec4899", width=2.5, dash="dot")))
    if split is not None:
        fig.add_vline(x=split.timestamp() * 1000, line_dash="dash",
                      line_color=_HUE_MARKER, annotation_text="forecast starts",
                      annotation_font_color=_HUE_MARKER)
    fig.update_layout(**_base_layout(height=360, legend=True,
                                     yaxis=dict(title="Units / month" if _target == "units_sold" else "Revenue / month (USD)")))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline status
# ─────────────────────────────────────────────────────────────────────────────

def _show_pipeline_status(status: dict):
    fetch = status.get("fetch", {})
    analyze = status.get("analyze", {})
    summ = status.get("summarize", {})
    errors = status.get("errors", [])
    mode = status.get("mode", "mock")
    msg = (
        f"Fetched **{fetch.get('fetched_from_gdelt', 0)}** headlines "
        f"({fetch.get('inserted', 0)} new) · scored **{analyze.get('articles_found', 0)}** "
        f"· {summ.get('rows_computed', 0)} daily rows · scorer: **{mode.upper()}**"
    )
    if errors:
        st.warning(f"Refresh finished with warnings: {'; '.join(errors)}\n\n{msg}")
    else:
        st.success(f"Refresh complete — {msg}")
