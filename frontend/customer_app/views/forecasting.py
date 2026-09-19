import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backend.services import forecasting as forecasting_service
from frontend.shared.i18n import cur, cur_code
from frontend.shared.ui import (
    _HUE_BAND,
    _HUE_DOWN,
    _HUE_FORECAST,
    _HUE_HISTORY,
    _HUE_MARKER,
    _HUE_UP,
    _INK,
    _base_layout,
    _compact,
    _fmt_money,
    _pct_label,
    _section,
)

# ─────────────────────────────────────────────────────────────────────────────
# What-if levers.
#
# Four things a dealer GM can actually reason about, not the macro series a
# manufacturer's economist watches. Each maps to a real column in
# external_factors so the baseline forecast already reflects its history.
# ─────────────────────────────────────────────────────────────────────────────
LEVERS = {
    "crude_oil_price_usd": dict(
        label="Crude oil price", unit="USD/barrel", step=1.0, fmt="{:.0f}",
    ),
    "petrol_price_per_litre": dict(
        label="Petrol price", unit="{cur}/litre", step=None, fmt="{:.2f}",
    ),
    "diesel_price_per_litre": dict(
        label="Diesel price", unit="{cur}/litre", step=None, fmt="{:.2f}",
    ),
    "auto_loan_apr_pct": dict(
        label="Auto-loan APR", unit="%", step=0.10, fmt="{:.1f}",
    ),
}

def render_forecasting(filters: dict):

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
        brand_opts = ["All brands (group total)"] + forecasting_service.brand_options()
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
    factor_stats = forecasting_service.external_factor_stats(region=region)
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
                    hi = lo + max((cfg["step"] or 0.05) * 5, 1.0)
                start = float(st.session_state.fc_overrides.get(col, s["last"]))
                start = min(max(start, lo), hi)
                step = cfg["step"] or max(round(s["last"] * 0.02, 2), 0.01)
                with cols[i]:
                    pending[col] = st.slider(
                        f"{cfg['label']} ({cfg['unit'].format(cur=cur_code())})", lo, hi, start,
                        step=float(step), key=f"fc_{col}",
                    )
                    if col == "auto_loan_apr_pct":
                        loan = forecasting_service.average_loan()
                        base_pay = forecasting_service.monthly_payment(s["last"], loan)
                        new_pay = forecasting_service.monthly_payment(pending[col], loan)
                        delta_pay = new_pay - base_pay
                        sign = "+" if delta_pay >= 0 else "−"
                        cap = (
                            f"approx {_fmt_money(new_pay)}/mo on a {_fmt_money(loan)} loan "
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
        result, err = forecasting_service.train_forecast(
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

    net_pct = forecasting_service.net_response_pct(overrides, factor_stats)
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
    range_str = (f"{_compact(low)} – {_compact(high)}" if is_units
                 else f"{cur()} {_compact(low)} – {_compact(high)}")

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
            mfig = go.Figure(go.Scatter(
                x=pat.index, y=pat.values, mode="lines+markers",
                line=dict(color=_HUE_FORECAST, width=2.5), marker=dict(size=6),
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
            dfig = go.Figure(go.Scatter(
                x=[d[:3] for d in dp.index], y=dp.values, mode="lines+markers",
                line=dict(color=_HUE_FORECAST, width=2.5), marker=dict(size=6),
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
