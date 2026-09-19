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
from utils.tenant_cache import tenant_cache_data
import plotly.graph_objects as go
import pandas as pd

from database.connection import get_db_session
from database.models import Sale
from sentiment.signal_processor import (
    run_full_pipeline,
    ensure_recent_articles_analyzed,
    compute_live_overall_stats,
)
from sentiment.fetchers.gdelt_fetcher import get_stored_articles, TIMESPAN_OPTIONS
from sentiment.group_briefing import build_briefing_context, generate_group_briefing
from utils.i18n import t, tv, tseg, fmt_num, fmt_pct, is_de
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

# Segment and theme labels are resolved through the catalog at RENDER time, so
# they follow the language toggle. `_SEGMENT_LABEL` / `_THEME_LABEL` are kept as
# callables with a dict-like .get() so the existing call sites are unchanged.
_THEME_NAMES = [
    "de_auto_demand", "ev_market_de", "tax_policy", "fuel_prices",
    "de_macro_economy", "auto_industry_de", "auto_financing", "incentives_offers",
]


class _Lookup:
    """dict-like façade that resolves through t() on every access, so a
    language switch is picked up without rebuilding any module-level map."""

    def __init__(self, prefix, keys, fallback=None):
        self._prefix, self._keys, self._fallback = prefix, set(keys), fallback

    def get(self, key, default=None):
        if key in self._keys:
            return t(f"{self._prefix}{key}")
        if self._fallback is not None:
            return self._fallback(key)
        return default if default is not None else key

    def __getitem__(self, key):
        return self.get(key)

    def __contains__(self, key):
        return key in self._keys

    # Callable so `Series.map(_THEME_LABEL)` works: pandas accepts a dict or a
    # callable, and this is deliberately neither a real dict nor a static one.
    def __call__(self, key):
        return self.get(key)


# Segment names as they read inside a sentence ("lands on the group's Kombi
# demand"), which is a different casing from the title-case VALUE_MAP.
_SEGMENT_LABEL = _Lookup("", [], fallback=tseg)
_THEME_LABEL = _Lookup("sa.theme.", _THEME_NAMES)
_THEME_EXPOSURE = _Lookup(
    "sa.exp.",
    ["tax_policy", "auto_financing", "de_macro_economy", "fuel_prices",
     "incentives_offers", "ev_market_de", "auto_industry_de"],
    fallback=lambda k: None,
)

_DIR_ARROW = {"up": "▲", "down": "▼", "neutral": "■"}


# ─────────────────────────────────────────────────────────────────────────────
# Small helpers
# ─────────────────────────────────────────────────────────────────────────────

@tenant_cache_data(ttl=600, show_spinner=False)
def _cached_briefing_context(filters_key: str, _filters, _stats, _articles):
    """The context build sweeps every module's queries (~10s). Cache it on the
    filter set so re-clicking 'Generate read' in the same session is instant."""
    return build_briefing_context(_filters, sentiment_stats=_stats,
                                  sentiment_articles=_articles)


@tenant_cache_data(ttl=600, show_spinner=False)
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
        return t("sa.word.tailwind"), _HUE_UP
    if net_pct < -0.75:
        return t("sa.word.headwind"), _HUE_DOWN
    return t("sa.word.flat"), _INK_MUTED


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_sentiment_analysis(filters: dict):
    st.markdown(
        f"<h2 class='gradient-text' style='margin-bottom:12px;'>{t('sa.title')}</h2>",
        unsafe_allow_html=True,
    )

    # ── Refresh controls ─────────────────────────────────────────────────
    c1, c2, _ = st.columns([2, 2, 4])
    with c1:
        timespan_label = st.selectbox(
            t("sa.window"), options=list(TIMESPAN_OPTIONS.keys()), index=1,
            key="sentiment_timespan"
        )
        timespan = TIMESPAN_OPTIONS[timespan_label]
    running = st.session_state.get("sentiment_pipeline_running", False)
    with c2:
        st.markdown("<div style='margin-top:28px;'>", unsafe_allow_html=True)
        refresh = st.button(t("sa.refresh"), type="primary", use_container_width=True,
                            disabled=running)
        st.markdown("</div>", unsafe_allow_html=True)

    if refresh and not running:
        st.session_state["sentiment_pipeline_running"] = True
        try:
            with st.spinner(t("sa.fetching")):
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
        _empty_state(t("sa.empty"))
        return

    _headline_block(stats)
    st.markdown("<br>", unsafe_allow_html=True)
    _bottom_line(stats, articles)
    st.markdown("<br>", unsafe_allow_html=True)

    tab_watch, tab_fc = st.tabs([t("sa.tab_watch"), t("sa.tab_fc")])
    with tab_watch:
        _render_demand_watch(stats, articles, filters)
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
            f"text-transform:uppercase;margin-bottom:2px;'>{t('sa.headline.label')}</div>"
            f"<div style='font-size:44px;font-weight:800;color:{color};line-height:1.1;'>"
            f"{_pct_label(net, 1)}</div>"
            f"<div style='color:{_INK};font-size:14px;margin-top:2px;'>"
            f"{word}"
            + (" &nbsp;·&nbsp; " + t("sa.headline.units",
                                     v=fmt_pct(unit_est, 0, signed=True).rstrip(" %").rstrip("%"))
               if runrate else "")
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
            f"{t('sa.gauge.scale').replace(' · ', ' &nbsp;·&nbsp; ')}</div>",
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
        body = t("sa.bl.none")
    elif abs(net) < 0.5:
        color = _INK_MUTED
        _t = df.assign(_t=df["theme"].map(_THEME_LABEL).fillna(df["theme"]))
        # Do NOT lowercase in German — every one of these theme labels is a
        # noun ("Kraftstoffpreise", "Rabatte"), and German capitalises nouns
        # mid-sentence.
        def _join_themes(direction, fallback_key):
            names = sorted(_t[_t["_dir"] == direction]["_t"].dropna().unique())[:2]
            if not names:
                return t(fallback_key)
            joined = ", ".join(names)
            return joined if is_de() else joined.lower()

        up_theme = _join_themes("up", "sa.bl.supportive_news")
        dn_theme = _join_themes("down", "sa.bl.headwind_news")
        body = t("sa.bl.mixed", up_n=up_n, up_theme=up_theme,
                 dn_n=dn_n, dn_theme=dn_theme)
    else:
        word = t("sa.word.headwind") if net < 0 else t("sa.word.tailwind")
        color = _HUE_DOWN if net < 0 else _HUE_UP
        rr = _group_monthly_runrate()
        _u = round(rr * net / 100.0)
        unit_hint = (t("sa.bl.units_hint",
                        v=fmt_pct(_u, 0, signed=True).rstrip(" %").rstrip("%"))
                     if rr else "")
        parts = [t("sa.bl.net", word=word, pct=_pct_label(net, 1), units=unit_hint)]
        if drivers:
            d_theme, d_val = drivers[0]
            exp = _THEME_EXPOSURE.get(d_theme)
            d_lbl = _THEME_LABEL.get(d_theme, d_theme)
            parts.append(
                t("sa.bl.driver", label=d_lbl)
                + (f" — {exp}." if exp else f" ({_pct_label(d_val, 1)}).")
            )
        if segs:
            parts.append(
                t("sa.bl.exposed")
                + ", ".join(f"{_SEGMENT_LABEL.get(s, s)} ({_pct_label(v, 1)})" for s, v in segs)
                + "."
            )
        if net < 0:
            dn = (_SEGMENT_LABEL.get(segs[0][0]) if segs and segs[0][1] < 0
                  else t("sa.bl.seg_affected"))
            parts.append(f"<b>{t('sa.bl.week')}</b> " + t("sa.bl.week_down", seg=dn))
        else:
            up = (_SEGMENT_LABEL.get(segs[0][0]) if segs and segs[0][1] > 0
                  else t("sa.bl.seg_favour"))
            parts.append(f"<b>{t('sa.bl.week')}</b> " + t("sa.bl.week_up", seg=up))
        body = " ".join(parts)

    st.markdown(
        f"""<div style="border:1px solid {color}44;border-left:4px solid {color};
        background:{color}12;border-radius:12px;padding:16px 18px;">
          <div style="color:{color};font-size:12px;font-weight:700;letter-spacing:.4px;
          text-transform:uppercase;margin-bottom:6px;">{t('sa.bottom_line')}</div>
          <div style="color:{_INK};font-size:13.5px;line-height:1.65;">{body}</div>
        </div>""",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Demand Watch
# ─────────────────────────────────────────────────────────────────────────────

def _render_demand_watch(stats: dict, articles: list, filters: dict):
    df = pd.DataFrame(articles)
    df["demand_change_pct"] = pd.to_numeric(df.get("demand_change_pct"), errors="coerce")
    df["impact_score"] = pd.to_numeric(df.get("impact_score"), errors="coerce")
    df["_dir"] = df["demand_direction"].fillna("neutral")

    quiet = (df["_dir"] != "neutral").sum() == 0

    if not quiet:
        # ── Drivers: mean signal by news theme ────────────────────────
        _section(t("sa.drivers.title"))
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
        _section(t("sa.segment.title"), t("sa.segment.caption"))
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
        _section(t("sa.latest.title"), t("sa.latest.caption"))
        for _, a in df.sort_values("published_date", ascending=False).head(5).iterrows():
            _signal_card(a)
    else:
        _section(t("sa.signals.title"))
        for _, a in actionable.iterrows():
            _signal_card(a)

    # ── This week's read (full cross-module briefing) ─────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    _section(t("sa.read.title"))
    if st.button(t("sa.read.button"), key="gen_briefing"):
        with st.spinner(t("sa.read.spinner")):
            import json
            from utils.i18n import get_lang
            fk = json.dumps({k: str(v) for k, v in (filters or {}).items()},
                            sort_keys=True) + f"|lang={get_lang()}"
            ctx = _cached_briefing_context(fk, filters, stats, articles)
            st.session_state["sentiment_briefing"] = generate_group_briefing(ctx)
    if st.session_state.get("sentiment_briefing"):
        # st.text (not markdown) so "1." / "-" line starts render literally,
        # not as auto-numbered / bulleted lists.
        st.text(st.session_state["sentiment_briefing"])


def _signal_card(a: pd.Series):
    direction = (a.get("demand_direction") or "neutral")
    chg = a.get("demand_change_pct")
    color = _HUE_UP if direction == "up" else (_HUE_DOWN if direction == "down" else _INK_MUTED)
    seg = a.get("affected_category") or "All"
    theme = a.get("theme")
    exposure = _THEME_EXPOSURE.get(theme)
    if not exposure:
        if seg in ("All", None):
            exposure = t("sa.card.exposure_all")
        else:
            exposure = t("sa.card.exposure_seg", seg=_SEGMENT_LABEL.get(seg, seg))
    title = (a.get("title") or t("sa.card.untitled"))[:150]
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
    _section(t("sa.fc.title"))

    try:
        from forecasting.prophet_forecasting import train_prophet_model
    except Exception as e:
        _empty_state(t("sa.fc.unavailable", e=e))
        return

    c1, c2, _ = st.columns([2, 2, 4])
    with c1:
        horizon = st.selectbox(t("sa.fc.horizon"), [30, 60, 90, 180], index=2, key="fc_v_horizon",
                               format_func=lambda d: f"{d} days")
    with c2:
        target = st.selectbox(t("sa.fc.measure"), ["units_sold", "total_revenue_incl_tax"],
                              format_func=lambda x: t("sa.fc.units") if x == "units_sold" else t("sa.fc.revenue"),
                              key="fc_v_target")
    with c1:
        run = st.button(t("sa.fc.run"), type="primary", key="fc_v_run")

    if run:
        with st.spinner(t("sa.fc.training")):
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
        st.info(t("sa.fc.prompt"))
        return

    base_res, base_err, sent_res, sent_err, _target = st.session_state["fc_v"]
    if base_err or not base_res:
        st.error(t("sa.fc.base_failed", e=base_err))
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
    fig.add_trace(go.Scatter(x=act["m"], y=act["actual"], name=t("sa.fc.actual"), mode="lines+markers",
                             line=dict(color=_HUE_HISTORY, width=2), marker=dict(size=5)))
    fig.add_trace(go.Scatter(x=fc["m"], y=fc["yhat"], name=t("sa.fc.standard"), mode="lines",
                             line=dict(color=_HUE_FORECAST, width=2.5)))
    if sent_res and not sent_err:
        sfc = _monthly(sent_res["forecast"])
        sfc = sfc[sfc["m"] >= start]
        fig.add_trace(go.Scatter(x=sfc["m"], y=sfc["yhat"], name=t("sa.fc.news_aware"), mode="lines",
                                 line=dict(color="#ec4899", width=2.5, dash="dot")))
    if split is not None:
        fig.add_vline(x=split.timestamp() * 1000, line_dash="dash",
                      line_color=_HUE_MARKER, annotation_text="forecast starts",
                      annotation_font_color=_HUE_MARKER)
    fig.update_layout(**_base_layout(height=360, legend=True,
                                     yaxis=dict(title=t("sa.fc.yaxis_units") if _target == "units_sold"
                                                else t("sa.fc.yaxis_revenue", cur=cur_code()))))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline status
# ─────────────────────────────────────────────────────────────────────────────

def _show_pipeline_status(status: dict):
    fetch = status.get("fetch", {})
    analyze = status.get("analyze", {})
    summ = status.get("summarize", {})
    errors = list(status.get("errors", []))
    mode = status.get("mode", "mock")
    source = fetch.get("source", "GDELT")
    msg = (
        f"Fetched **{fetch.get('fetched_from_gdelt', 0)}** headlines from **{source}** "
        f"({fetch.get('inserted', 0)} new) · scored **{analyze.get('articles_found', 0)}** "
        f"· {summ.get('rows_computed', 0)} daily rows · scorer: **{mode.upper()}**"
    )

    # A GDELT→RSS fallback is expected behaviour, not a failure — show it as a
    # note so it doesn't read like the refresh broke.
    notes = [e for e in errors if "Google News RSS" in e]
    hard = [e for e in errors if "Google News RSS" not in e]

    if hard:
        st.warning(t("sa.status.warn", msg="; ".join(hard)) + f"\n\n{msg}")
    else:
        st.success(f"Refresh complete — {msg}")
    for n in notes:
        st.caption(f"ℹ️ {n}")
