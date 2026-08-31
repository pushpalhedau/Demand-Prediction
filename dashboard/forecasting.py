import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from database.connection import get_db_session
from database.models import Sale
from forecasting.prophet_forecasting import train_prophet_model, get_external_factor_stats
from utils.helpers import (
    get_color_palette,
    _section,
    _base_layout,
    _fmt_money,
    _compact,
    _pct_label,
    _INK,
    _INK_MUTED,
    _HUE_HISTORY,
    _HUE_FORECAST,
    _HUE_BAND,
    _HUE_UP,
    _HUE_DOWN,
    _HUE_MARKER,
)

# ─────────────────────────────────────────────────────────────────────────────
# What-if levers.
#
# Four things a dealer GM can actually reason about, not the macro series a
# manufacturer's economist watches. Each maps to a real column in
# external_factors so the baseline forecast already reflects its history.
# ─────────────────────────────────────────────────────────────────────────────
LEVERS = {
    "gasoline_regular_usd_per_gallon": dict(
        label="Pump price", unit="$/gal", step=0.05, fmt="{:.2f}",
    ),
    "auto_loan_apr_pct": dict(
        label="Auto-loan APR", unit="%", step=0.10, fmt="{:.1f}",
    ),
    "incentive_pct_of_atp": dict(
        label="Incentive spend", unit="% of price", step=0.20, fmt="{:.1f}",
    ),
    "inventory_days_supply": dict(
        label="Inventory on hand", unit="days' supply", step=2.0, fmt="{:.0f}",
    ),
}

# Group demand response to each lever, held one-at-a-time, relative to the
# recent baseline. Calibrated to published US auto-retail elasticities (sources
# in docs/changelog/2026-08-27-demand-forecasting-dealer-positioning.md):
#   pump price  ~ -4% units per +$1/gal   (Resources for the Future / NBER)
#   loan APR    ~ -3% units per +1pt      (Fed FEDS Notes 2024; KBB)
#   incentives  ~ +2% units per +1pt ATP  (Cox Automotive / KBB)
# Inventory is handled separately below — a shortfall loses sales, a glut does
# not add them.
GROUP_DEMAND_RESPONSE = {
    "gasoline_regular_usd_per_gallon": -4.0,
    "auto_loan_apr_pct": -3.0,
    "incentive_pct_of_atp": +2.0,
}

_AVG_LOAN = 42000      # $ financed, for the monthly-payment translation
_LOAN_MONTHS = 72


def _supply_drag_pct(days_supply: float) -> float:
    """Percent of demand the group loses to thin stock. Zero at/above ~55 days'
    supply; roughly -1.1%/day below that as shoppers can't find the car."""
    if days_supply >= 55:
        return 0.0
    return (days_supply - 55) * 1.1


def _monthly_payment(apr_pct: float) -> float:
    r = apr_pct / 100 / 12
    if r <= 0:
        return _AVG_LOAN / _LOAN_MONTHS
    return _AVG_LOAN * r / (1 - (1 + r) ** -_LOAN_MONTHS)


@st.cache_data(ttl=600, show_spinner=False)
def _brand_options():
    s = get_db_session()
    try:
        rows = s.query(Sale.brand).distinct().all()
        return sorted(b[0] for b in rows if b[0])
    finally:
        s.close()


def _net_response_pct(overrides: dict, factor_stats: dict) -> float:
    """Combine the active levers into one % shift vs the recent baseline."""
    if not overrides or not factor_stats:
        return 0.0
    pct = 0.0
    for col, val in overrides.items():
        if col not in factor_stats:
            continue
        base = factor_stats[col]["last"]
        if col == "inventory_days_supply":
            pct += _supply_drag_pct(float(val)) - _supply_drag_pct(float(base))
        elif col in GROUP_DEMAND_RESPONSE:
            pct += (float(val) - float(base)) * GROUP_DEMAND_RESPONSE[col]
    return pct


def render_forecasting(filters: dict):
    colors = get_color_palette()

    st.markdown(
        "<h2 class='gradient-text' style='margin-bottom:16px;'>Demand Forecast</h2>",
        unsafe_allow_html=True,
    )

    # Fixed 80% confidence band; not a user knob.
    confidence_level = 80

    # ── Controls ─────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        target = st.selectbox(
            "Forecast", ["units_sold", "total_revenue_incl_tax"],
            format_func=lambda x: "Units Sold" if x == "units_sold" else "Revenue",
        )
    with c2:
        horizon_months = st.selectbox("Looking ahead", [3, 6, 12], index=0,
                                      format_func=lambda m: f"{m} months")
        # over-shoot Prophet's horizon; the view is trimmed to whole calendar
        # months below so the chart total matches the headline number exactly.
        horizon = horizon_months * 31 + 15
    with c3:
        brand_opts = ["All brands (group total)"] + _brand_options()
        default_ix = brand_opts.index(filters["brand"]) if filters.get("brand") in brand_opts else 0
        brand_pick = st.selectbox("Brand", brand_opts, index=default_ix)
        brand = None if brand_pick.startswith("All brands") else brand_pick

    region = filters.get("region")
    category = filters.get("vehicle_category")
    fuel_type = filters.get("fuel_type")
    scope_bits = [b for b in [
        brand,
        f"{category} segment" if category else None,
        f"{region} stores" if region else None,
        f"{fuel_type} only" if fuel_type else None,
    ] if b]
    if scope_bits:
        st.caption("Scope: " + " · ".join(scope_bits))

    is_units = target == "units_sold"
    unit_word = "units" if is_units else "revenue"

    # ── What-if levers ───────────────────────────────────────────────────────
    factor_stats = get_external_factor_stats(region=region)
    available = {k: v for k, v in LEVERS.items() if k in factor_stats}

    if "fc_overrides" not in st.session_state:
        st.session_state.fc_overrides = {}
    has_overrides = bool(st.session_state.fc_overrides)

    with st.expander("What-if: change the conditions for the forecast window", expanded=has_overrides):
        st.caption(
            "Set where these land over the forecast window and the projection re-prices. "
            "Leave them alone to forecast on current conditions."
        )
        with st.form("fc_levers"):
            pending = {}
            cols = st.columns(len(available)) if available else []
            for i, (col, cfg) in enumerate(available.items()):
                s = factor_stats[col]
                lo = round(max(0.0, s["min"] - (s["max"] - s["min"]) * 0.2), 2)
                hi = round(s["max"] + (s["max"] - s["min"]) * 0.2, 2)
                if hi <= lo:
                    hi = lo + max(cfg["step"] * 5, 1.0)
                cur = float(st.session_state.fc_overrides.get(col, s["last"]))
                cur = min(max(cur, lo), hi)
                with cols[i]:
                    pending[col] = st.slider(
                        f"{cfg['label']} ({cfg['unit']})", lo, hi, cur,
                        step=float(cfg["step"]), key=f"fc_{col}",
                    )
                    if col == "auto_loan_apr_pct":
                        base_pay = _monthly_payment(s["last"])
                        new_pay = _monthly_payment(pending[col])
                        delta_pay = new_pay - base_pay
                        sign = "+" if delta_pay >= 0 else "−"
                        cap = (
                            f"approx {_fmt_money(new_pay)}/mo on a {_fmt_money(_AVG_LOAN)} loan "
                            f"({sign}{_fmt_money(abs(delta_pay))}/mo vs now)"
                        ).replace("$", "\\$")
                        st.caption(cap)
            b1, b2 = st.columns([3, 1])
            with b1:
                apply = st.form_submit_button("Apply", type="primary", use_container_width=True)
            with b2:
                reset = st.form_submit_button("Reset", use_container_width=True)
        if apply:
            st.session_state.fc_overrides = {
                k: v for k, v in pending.items()
                if abs(v - factor_stats[k]["last"]) > 1e-6
            }
        if reset:
            st.session_state.fc_overrides = {}

    overrides = st.session_state.fc_overrides or None

    # ── Train (baseline; levers are applied as a documented response, below) ──
    with st.spinner("Training the forecast on the group's sales history…"):
        result, err = train_prophet_model(
            category=category, region=region, fuel_type=fuel_type, brand=brand,
            target=target, horizon_days=horizon,
            interval_width=confidence_level / 100, use_sentiment=False,
            market_overrides=None,
        )
    if err:
        if "No data" in err:
            st.info(
                f"No booked sales for this scope — the group may not carry "
                f"{brand or 'that mix'} in {region or 'the selected market'}. "
                "Widen the brand or market filter."
            )
        else:
            st.info(f"Not enough sales history for this scope to build a forecast. ({err})")
        return

    fc = result["forecast"].copy()
    fc["ds"] = pd.to_datetime(fc["ds"])

    net_pct = _net_response_pct(overrides, factor_stats)
    future_mask = fc["actual"].isnull()
    if abs(net_pct) >= 0.1:
        mult = float(np.clip(1 + net_pct / 100.0, 0.4, 2.5))
        for c in ["yhat", "yhat_lower", "yhat_upper"]:
            fc.loc[future_mask, c] = (fc.loc[future_mask, c] * mult).clip(lower=0)

    hist = fc[fc["actual"].notna()].copy()
    future = fc[fc["actual"].isnull()].copy()
    if future.empty or hist.empty:
        st.warning("Not enough history for this scope to build a forecast.")
        return

    # The forecast window is whole calendar months. It begins with the first
    # month that is not already fully booked — so if today is 21 Aug, the window
    # opens on 1 Aug and that month's total is (what's booked so far) + (the
    # projection for the rest of the month). This keeps the chart, the headline
    # number and the "next N months" label in agreement, and puts the
    # history/forecast divider exactly on the month the projection takes over.
    data_end = hist["ds"].max()
    month_end = (data_end + pd.offsets.MonthEnd(0)).normalize()
    if data_end >= month_end:                       # data ends exactly on a month-end
        win_start = (data_end + pd.Timedelta(days=1)).normalize()
    else:                                           # current month only partly booked
        win_start = data_end.normalize().replace(day=1)
    win_end = win_start + pd.DateOffset(months=horizon_months) - pd.Timedelta(days=1)

    fut_win = future[(future["ds"] >= win_start) & (future["ds"] <= win_end)].copy()
    act_win = hist[(hist["ds"] >= win_start) & (hist["ds"] <= win_end)].copy()
    if fut_win.empty:
        st.info("Not enough forecast horizon for this scope. Try a shorter window.")
        return

    def _win_month_sum(col):
        """Monthly totals over the window = actuals already booked + projection."""
        a = act_win.set_index("ds")["actual"].resample("MS").sum() if not act_win.empty else pd.Series(dtype=float)
        f = fut_win.set_index("ds")[col].resample("MS").sum()
        return f.add(a, fill_value=0.0)

    # Summing Prophet's daily bounds over a month assumes every day's error moves
    # the same way — it doesn't. Day-to-day errors partly cancel, so the monthly
    # total is far less uncertain than that sum implies. Shrink the half-width
    # toward the (more correct) sqrt-of-N scaling.
    _BAND_SHRINK = 0.55
    _mid = _win_month_sum("yhat")
    _lo = _win_month_sum("yhat_lower")
    _hi = _win_month_sum("yhat_upper")
    win_monthly = pd.DataFrame({
        "yhat": _mid,
        "yhat_lower": (_mid - (_mid - _lo) * _BAND_SHRINK).clip(lower=0),
        "yhat_upper": _mid + (_hi - _mid) * _BAND_SHRINK,
    })
    expected = float(win_monthly["yhat"].sum())
    low = float(win_monthly["yhat_lower"].sum())
    high = float(win_monthly["yhat_upper"].sum())

    ly_start = win_start - pd.DateOffset(years=1)
    ly_end = win_end - pd.DateOffset(years=1)
    last_year = float(hist[(hist["ds"] >= ly_start) & (hist["ds"] <= ly_end)]["actual"].sum())
    yoy = (expected / last_year - 1) * 100 if last_year > 0 else None

    ttm = float(hist[hist["ds"] >= win_start - pd.DateOffset(months=12)]["actual"].sum())
    ttm_rate = ttm / 12
    exp_rate = expected / horizon_months
    rate_delta = (exp_rate / ttm_rate - 1) * 100 if ttm_rate > 0 else None

    fmt = _fmt_money if not is_units else (lambda v: f"{_compact(v)}")
    # A metric value with two "$" is parsed as LaTeX by st.metric, so the range
    # card carries a single leading "$" and lets the unit ride on the compact M/K.
    range_str = (f"{_compact(low)} – {_compact(high)}" if is_units
                 else f"${_compact(low)} – {_compact(high)}")

    # ── Lever impact banner ─────────────────────────────────────────────────
    if overrides and abs(net_pct) >= 0.1:
        hue = _HUE_UP if net_pct > 0 else _HUE_DOWN
        st.markdown(
            f"<div style='background:{hue}18;border:1px solid {hue}44;border-radius:8px;"
            f"padding:8px 14px;margin-bottom:14px;font-size:13px;color:{hue};'>"
            f"<b>With these conditions</b> the group's projected {unit_word} shift "
            f"<b>{_pct_label(net_pct, 1)}</b> over the window — about "
            f"<b>{fmt(abs(expected - expected / (1 + net_pct/100)))}</b>.</div>",
            unsafe_allow_html=True,
        )

    # ── Headline row ────────────────────────────────────────────────────────
    # Lay each metric card out as: label on top, then value and delta on one
    # row with the delta pushed to the right edge. This keeps all three cards
    # the same height even though the middle one has no delta.
    st.markdown(
        """
        <style>
        /* Streamlit wraps label / value / delta in one inner div — make that
           the flex row: label spans the top, value + delta share the line, and
           the delta is pushed to the right edge. */
        div[data-testid="stMetric"] > div {
            display: flex; flex-wrap: wrap; align-items: center; column-gap: 12px;
        }
        div[data-testid="stMetric"] > div > label[data-testid="stMetricLabel"] {
            flex: 1 1 100%;
        }
        div[data-testid="stMetric"] > div > div[data-testid="stMetricValue"] {
            flex: 0 1 auto;
        }
        div[data-testid="stMetric"] > div > div:last-child:not([data-testid="stMetricValue"]):not([data-testid="stMetricLabel"]) {
            flex: 0 0 auto; margin-left: auto; align-self: center; white-space: nowrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    h1, h2, h3 = st.columns(3)
    with h1:
        st.metric(
            f"Expected {unit_word} · next {horizon_months} mo",
            fmt(expected),
            delta=(f"{yoy:+.0f}% vs last year" if yoy is not None else None),
        )
    with h2:
        st.metric("Confidence range", range_str,
                  help=f"{confidence_level}% model confidence band, summed over the window.")
    with h3:
        st.metric(
            "Implied monthly run-rate", fmt(exp_rate),
            delta=(f"{rate_delta:+.0f}% vs trailing 12-mo" if rate_delta is not None else None),
        )

    # ── Main chart ─────────────────────────────────────────────────────────
    _section("History vs forecast")

    # History: monthly totals through the last fully-booked month.
    h_m = hist.set_index("ds")["actual"].resample("MS").sum()
    h_m = h_m[h_m.index < win_start].tail(13)
    f_m_full = win_monthly                   # blended: actuals-to-date + projection
    f_m = f_m_full["yhat"]                   # also drives the "strongest month" call-out

    last_hx = [h_m.index[-1]] if len(h_m) else []
    last_hy = [h_m.values[-1]] if len(h_m) else []

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(f_m_full.index) + list(f_m_full.index[::-1]),
        y=list(f_m_full["yhat_upper"]) + list(f_m_full["yhat_lower"][::-1]),
        fill="toself", fillcolor=_HUE_BAND, line=dict(color="rgba(0,0,0,0)"),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=h_m.index, y=h_m.values, mode="lines+markers", name="Booked",
        line=dict(color=_HUE_HISTORY, width=2.5), marker=dict(size=6),
        hovertemplate="%{x|%b %Y}<br>%{y:,.0f}<extra>Booked</extra>", showlegend=False,
    ))
    # Conservative / Optimistic bounds as thin dashed lines, Expected solid —
    # all bridged from the last booked point (standard forecast-chart convention)
    for col, hue, dash, wid, tag in [
        ("yhat_upper", _HUE_UP, "dot", 1.5, "Optimistic"),
        ("yhat_lower", _HUE_DOWN, "dot", 1.5, "Conservative"),
        ("yhat", _HUE_FORECAST, "solid", 3, "Expected"),
    ]:
        fig.add_trace(go.Scatter(
            x=last_hx + list(f_m_full.index),
            y=last_hy + list(f_m_full[col]),
            mode="lines+markers" if col == "yhat" else "lines",
            line=dict(color=hue, width=wid, dash=dash),
            marker=dict(size=6),
            hovertemplate=f"%{{x|%b %Y}}<br>%{{y:,.0f}}<extra>{tag}</extra>",
            showlegend=False,
        ))

    # direct end-labels (glance-first: read the line, not a legend)
    total = {"Optimistic": high, "Expected": expected, "Conservative": low}
    ycol = {"Optimistic": "yhat_upper", "Expected": "yhat", "Conservative": "yhat_lower"}
    hcol = {"Optimistic": _HUE_UP, "Expected": _HUE_FORECAST, "Conservative": _HUE_DOWN}
    for tag in ("Optimistic", "Expected", "Conservative"):
        fig.add_annotation(
            x=f_m_full.index[-1], y=float(f_m_full[ycol[tag]].iloc[-1]),
            xshift=8, xanchor="left", yanchor="middle", showarrow=False,
            text=f"{tag}  ({fmt(total[tag])})",
            font=dict(color=hcol[tag], size=11),
        )

    # divider sits between the last booked month and the first forecast month,
    # so it reads as the boundary rather than landing on a data point
    if len(h_m):
        divider = h_m.index[-1] + (f_m_full.index[0] - h_m.index[-1]) / 2
    else:
        divider = win_start
    fig.add_vline(x=divider.timestamp() * 1000, line_width=1.5, line_dash="dot",
                  line_color=_HUE_MARKER)
    fig.add_annotation(x=divider, y=1, yref="paper", yanchor="bottom", xanchor="center",
                       text="forecast →", showarrow=False,
                       font=dict(color=_HUE_MARKER, size=11))

    headline = (
        f"{fmt(expected)} {unit_word} expected over the next {horizon_months} months"
        + (f"  ·  {_pct_label(yoy,0)} vs last year" if yoy is not None else "")
    )
    fig.add_annotation(
        x=0, y=1.16, xref="paper", yref="paper", xanchor="left", showarrow=False,
        text=f"<b>{headline}</b>", font=dict(color=_INK, size=14),
    )
    fig.update_layout(**_base_layout(height=440, legend=False,
                                     margin=dict(l=0, r=120, t=60, b=0)))
    fig.update_yaxes(title=("Units / month" if is_units else "Revenue / month"))
    x_lo = h_m.index[0] if len(h_m) else f_m_full.index[0]
    fig.update_xaxes(range=[x_lo, f_m_full.index[-1] + pd.Timedelta(days=20)])
    st.plotly_chart(fig, use_container_width=True)

    # ── Seasonality ───────────────────────────────────────────────────────
    left, right = st.columns(2)
    with left:
        _section("When the group sells — by month")
        if "yearly" in fc.columns:
            fc["m"] = fc["ds"].dt.strftime("%b")
            order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            pat = fc.groupby("m")["yearly"].mean().reindex(order)
            mcol = [_HUE_UP if v >= 0 else _HUE_DOWN for v in pat.values]
            mfig = go.Figure(go.Bar(x=pat.index, y=pat.values, marker_color=mcol,
                                    hovertemplate="%{x}<br>%{y:.2f}<extra></extra>"))
            mfig.update_layout(**_base_layout(height=240))
            mfig.add_hline(y=0, line_color="rgba(255,255,255,0.2)")
            st.plotly_chart(mfig, use_container_width=True)
        else:
            st.info("Yearly pattern not available for this scope.")
    with right:
        _section("Busiest day of the week")
        if "weekly" in fc.columns:
            fc["d"] = fc["ds"].dt.day_name()
            dorder = ["Monday", "Tuesday", "Wednesday", "Thursday",
                      "Friday", "Saturday", "Sunday"]
            dp = fc.groupby("d")["weekly"].mean().reindex(dorder)
            dcol = [_HUE_UP if v >= 0 else _HUE_DOWN for v in dp.values]
            dfig = go.Figure(go.Bar(x=[d[:3] for d in dp.index], y=dp.values,
                                    marker_color=dcol,
                                    hovertemplate="%{x}<br>%{y:.2f}<extra></extra>"))
            dfig.update_layout(**_base_layout(height=240))
            dfig.add_hline(y=0, line_color="rgba(255,255,255,0.2)")
            st.plotly_chart(dfig, use_container_width=True)
        else:
            st.info("Weekly pattern not available for this scope.")

    # ── Plain-language takeaway ───────────────────────────────────────────
    strongest = f_m.idxmax().strftime("%B") if len(f_m) else None
    plan_word = "stock and order toward" if is_units else "plan for"
    noun = f" {unit_word}" if is_units else " in front-end + F&I revenue"
    msg = f"**Plan:** {plan_word} **{fmt(expected)}**{noun} across the group over the next {horizon_months} months"
    if strongest:
        msg += f"; the busiest month in that window is expected to be **{strongest}**"
    if yoy is not None:
        msg += f". That's **{_pct_label(yoy,0)}** against the same window last year"
    st.success((msg + ".").replace("$", "\\$"))
