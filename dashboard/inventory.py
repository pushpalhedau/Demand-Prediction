"""
Inventory Intelligence.

Structured around inventory *flow* rather than a static stock count. The tab
answers three questions in order: what is on the ground right now, what is
coming in and going out, and what to do about the gap.

  Stock Health         current position, aging, reorder priorities
  Inventory Flow       lease-return book, in/out balance, net order gap
  Trade-In & Acquisition   used-supply intake, true concession, incentive ROI
  Placement Assistant  substitute recommendations when a request is unavailable

A note on the data model that governs every query here: the inventory table
holds month-end snapshots, so one physical car appears once per month it sat on
the lot. Present-day figures therefore come from get_inventory_snapshot(), which
reduces to the latest snapshot per (dealer, vehicle) before aggregating.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database.connection import get_db_session
from database.queries import (
    DAYS_SUPPLY_HEALTHY_HIGH,
    DAYS_SUPPLY_HEALTHY_LOW,
    get_aging_buckets,
    get_dealer_directory,
    get_inventory_snapshot,
    get_inventory_trend,
    get_lease_maturity_recapture,
    get_lease_return_pipeline,
    get_substitution_history,
    get_trade_in_activity,
    get_trade_replacement_flow,
    get_vehicle_catalog,
)
from ml_models.vehicle_placement import recommend_alternatives
from utils.helpers import get_color_palette, render_kpi_card

FONT = "Plus Jakarta Sans"


def _style(fig, height=320, showlegend=True, legend_top=True):
    """Apply the platform chart styling so every figure reads as one system."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f3f4f6", family=FONT, size=12),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
        margin=dict(l=0, r=0, t=10, b=0),
        height=height,
        showlegend=showlegend,
    )
    if showlegend and legend_top:
        fig.update_layout(legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ))
    return fig


def _note(text):
    """Small muted caption used to explain how a number was derived."""
    st.markdown(
        f"<div style='color:#9ca3af;font-size:12px;margin:-6px 0 14px 0;'>{text}</div>",
        unsafe_allow_html=True,
    )


def _section(title, subtitle=None):
    st.markdown(f"### {title}")
    if subtitle:
        _note(subtitle)


# ─────────────────────────────────────────────────────────────────────────────
# Cached loaders. Streamlit reruns the whole script on every widget change, and
# the trade-in view reads the full sales table, so these are cached on the
# filter set rather than re-queried per interaction.
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def _load_snapshot(filters):
    s = get_db_session()
    try:
        return get_inventory_snapshot(s, filters)
    finally:
        s.close()


@st.cache_data(ttl=600, show_spinner=False)
def _load_trend(filters):
    s = get_db_session()
    try:
        return get_inventory_trend(s, filters)
    finally:
        s.close()


@st.cache_data(ttl=600, show_spinner=False)
def _load_lease_returns(filters, months_ahead):
    s = get_db_session()
    try:
        return get_lease_return_pipeline(s, filters, months_ahead=months_ahead)
    finally:
        s.close()


@st.cache_data(ttl=600, show_spinner=False)
def _load_recapture(filters, days_ahead):
    s = get_db_session()
    try:
        return get_lease_maturity_recapture(s, filters, days_ahead=days_ahead)
    finally:
        s.close()


@st.cache_data(ttl=600, show_spinner=False)
def _load_trades(filters):
    s = get_db_session()
    try:
        return get_trade_in_activity(s, filters)
    finally:
        s.close()


@st.cache_data(ttl=600, show_spinner=False)
def _load_replacement_flow(filters):
    s = get_db_session()
    try:
        return get_trade_replacement_flow(s, filters)
    finally:
        s.close()


@st.cache_data(ttl=600, show_spinner=False)
def _load_placement_reference(filters):
    s = get_db_session()
    try:
        return (get_vehicle_catalog(s),
                get_dealer_directory(s),
                get_substitution_history(s, filters))
    finally:
        s.close()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_inventory(filters: dict):
    colors = get_color_palette()

    st.markdown(
        "<h2 class='gradient-text' style='margin-bottom:6px;'>Inventory Intelligence</h2>",
        unsafe_allow_html=True,
    )

    try:
        snapshot = _load_snapshot(filters)
    except Exception as exc:
        st.error(f"Could not load inventory snapshot: {exc}")
        return

    if snapshot.empty:
        st.warning("No inventory records match the current filters.")
        return

    tab_health, tab_flow = st.tabs([
        "Stock Health",
        "Inventory Flow & Lease Returns",
        # "Trade-In & Acquisition",
        # "Placement Assistant",
    ])

    with tab_health:
        _render_stock_health(snapshot, filters, colors)
    with tab_flow:
        _render_flow(snapshot, filters, colors)
    # with tab_trade:
    #     _render_trade_in(filters, colors)
    # with tab_place:
    #     _render_placement(snapshot, filters, colors)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Stock Health
# ─────────────────────────────────────────────────────────────────────────────

def _render_stock_health(snapshot, filters, colors):
    units = int(snapshot["current_stock"].sum())
    transit = int(snapshot["transit_stock"].sum())
    value = float(snapshot["inventory_value_usd"].sum())
    holding = float(snapshot["estimated_holding_cost_usd"].sum())

    # Network days of supply is total stock over total daily demand — not the
    # mean of per-line ratios, which would let a single dead SKU dominate.
    daily_demand = snapshot["demand_forecast_30d"].sum() / 30.0
    net_days_supply = units / daily_demand if daily_demand > 0 else 0

    aged = snapshot[snapshot["days_in_stock"] > 90]
    aged_units = int(aged["current_stock"].sum())
    aged_capital = float(aged["inventory_value_usd"].sum())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("Units in Stock", f"{units:,}",
                        delta=f"{transit:,} inbound in transit", is_positive=True)
    with c2:
        healthy = DAYS_SUPPLY_HEALTHY_LOW <= net_days_supply <= DAYS_SUPPLY_HEALTHY_HIGH
        render_kpi_card("Days of Supply", f"{net_days_supply:,.0f} days",
                        delta=f"healthy band {DAYS_SUPPLY_HEALTHY_LOW}-{DAYS_SUPPLY_HEALTHY_HIGH}",
                        is_positive=healthy)
    with c3:
        render_kpi_card("Inventory at Cost", f"${value/1e6:,.1f}M",
                        delta=f"${holding:,.0f}/mo to floorplan", is_positive=False)
    with c4:
        render_kpi_card("Aged Over 90 Days", f"{aged_units:,} units",
                        delta=f"${aged_capital/1e6:,.1f}M tied up", is_positive=False)

    st.markdown("<br>", unsafe_allow_html=True)

    left, right = st.columns([1, 1])

    with left:
        _section("Inventory Aging Ladder")
        aging = get_aging_buckets(snapshot)
        if not aging.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=aging["bucket"], y=aging["units"],
                marker_color=[colors["success"], colors["secondary"],
                              colors["warning"], colors["danger"]],
                text=[f"{u:,}" for u in aging["units"]],
                textposition="outside",
                customdata=np.stack([aging["capital_usd"] / 1e6, aging["lines"]], axis=-1),
                hovertemplate="<b>%{x}</b><br>%{y:,} units"
                              "<br>$%{customdata[0]:.1f}M capital"
                              "<br>%{customdata[1]} lines<extra></extra>",
            ))
            fig.update_yaxes(title="Units")
            st.plotly_chart(_style(fig, height=300, showlegend=False), use_container_width=True)

    with right:
        _section("Stock vs Demand Quadrant")
        plot_df = snapshot[snapshot["current_stock"] > 0].copy()
        if not plot_df.empty:
            plot_df["Position"] = np.where(
                plot_df["days_of_supply"] > 90, "Overstocked",
                np.where(plot_df["reorder_needed"], "Below reorder point", "Healthy"),
            )
            fig = px.scatter(
                plot_df, x="demand_forecast_30d", y="current_stock",
                color="Position", size="inventory_value_usd", size_max=26,
                hover_data={"brand": True, "model": True, "dealer_name": True,
                            "days_of_supply": ":.0f", "inventory_value_usd": ":,.0f"},
                color_discrete_map={"Healthy": colors["success"],
                                    "Below reorder point": colors["warning"],
                                    "Overstocked": colors["danger"]},
                labels={"demand_forecast_30d": "Forecast 30-day demand (units)",
                        "current_stock": "Units on hand"},
            )
            st.plotly_chart(_style(fig, height=300), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    _section("Network Stock Trend")
    trend = _load_trend(filters)
    if not trend.empty:
        trend["record_date"] = pd.to_datetime(trend["record_date"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend["record_date"], y=trend["units_in_stock"], name="Units on hand",
            mode="lines", line=dict(color=colors["primary"], width=2.5),
            fill="tozeroy", fillcolor="rgba(99,102,241,0.12)",
        ))
        fig.add_trace(go.Scatter(
            x=trend["record_date"], y=trend["units_sold_30d"], name="Units sold (30d)",
            mode="lines", line=dict(color=colors["secondary"], width=2, dash="dot"),
        ))
        fig.update_yaxes(title="Units")
        st.plotly_chart(_style(fig, height=280), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    _section("Reorder Priorities")
    reorder = snapshot[snapshot["reorder_needed"]].copy()
    if reorder.empty:
        st.success("No lines are below their reorder point under the current filters.")
    else:
        reorder["Deficit"] = (reorder["reorder_point"] - reorder["current_stock"]).clip(lower=0)
        # Urgency blends how far below the trigger the line is with how long a
        # replacement takes to arrive.
        reorder["Urgency"] = (
            reorder["stockout_risk_score"] * 0.6
            + (reorder["supplier_lead_time_days"] / 70.0).clip(upper=1) * 0.4
        )
        reorder = reorder.sort_values("Urgency", ascending=False)
        table = pd.DataFrame({
            "Dealer": reorder["dealer_name"],
            "Vehicle": reorder["brand"] + " " + reorder["model"] + " " + reorder["variant"].fillna(""),
            "State": reorder["state"],
            "On Hand": reorder["current_stock"],
            "Reorder Pt": reorder["reorder_point"],
            "Deficit": reorder["Deficit"],
            "In Transit": reorder["transit_stock"],
            "Lead Time": reorder["supplier_lead_time_days"].astype(int).astype(str) + " d",
            "Urgency": (reorder["Urgency"] * 100).round(0),
        })
        st.dataframe(
            table.head(15), use_container_width=True, hide_index=True,
            column_config={"Urgency": st.column_config.ProgressColumn(
                "Urgency", min_value=0, max_value=100, format="%d%%")},
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Inventory Flow & Lease Returns
# ─────────────────────────────────────────────────────────────────────────────

def _render_flow(snapshot, filters, colors):
    horizon = st.select_slider(
        "Forward horizon", options=[3, 6, 9, 12, 18, 24], value=12,
        format_func=lambda m: f"{m} months",
    )
    returns = _load_lease_returns(filters, horizon)

    if returns.empty:
        st.info("No lease contracts mature inside this horizon under the current filters.")
        return

    total_returns = len(returns)
    itm = returns[returns["in_the_money"]]
    itm_equity = float(itm["equity_usd"].sum())
    avg_residual = float(returns["residual_value_usd"].mean())
    next_90 = returns[
        returns["lease_maturity_date"] <= pd.Timestamp.today() + pd.Timedelta(days=90)
    ]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("Scheduled Returns", f"{total_returns:,} units",
                        delta=f"over the next {horizon} months", is_positive=True)
    with c2:
        render_kpi_card("Returning in 90 Days", f"{len(next_90):,} units",
                        delta="near-term inbound supply", is_positive=True)
    with c3:
        render_kpi_card("In-the-Money Returns", f"{len(itm):,} units",
                        delta=f"${itm_equity/1e6:,.1f}M retained equity", is_positive=True)
    with c4:
        render_kpi_card("Avg Buyout (Residual)", f"${avg_residual:,.0f}",
                        delta="contractual purchase price", is_positive=True)

    st.markdown("<br>", unsafe_allow_html=True)

    _section("Lease Return Calendar")
    cal = (returns.groupby(["maturity_month", "in_the_money"]).size()
           .reset_index(name="units"))
    cal["Position"] = np.where(cal["in_the_money"], "In the money", "Under water")
    fig = px.bar(cal, x="maturity_month", y="units", color="Position",
                 color_discrete_map={"In the money": colors["success"],
                                     "Under water": colors["warning"]},
                 labels={"maturity_month": "", "units": "Units returning"})
    fig.update_layout(barmode="stack")
    st.plotly_chart(_style(fig, height=300), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    left, right = st.columns([1.15, 1])

    with left:
        _section("Net Order Gap")
        gap = _net_order_gap(snapshot, returns)
        if gap.empty:
            st.info("No ordering gap under the current filters.")
        else:
            avoided = int(gap["Returns Offset"].sum())
            naive = int(gap["Gross Need"].sum())
            net = int(gap["Net Order"].sum())
            st.markdown(
                f"<div style='background:rgba(16,185,129,0.10);border:1px solid "
                f"rgba(16,185,129,0.30);border-radius:10px;padding:12px 16px;"
                f"margin-bottom:14px;'>"
                f"<span style='color:#10b981;font-weight:700;font-size:15px;'>"
                f"{avoided:,} units</span>"
                f"<span style='color:#d1d5db;font-size:13px;'> of the "
                f"{naive:,}-unit gross requirement are already covered by "
                f"scheduled lease returns. Netting them out cuts the order to "
                f"{net:,} units.</span></div>",
                unsafe_allow_html=True,
            )
            st.dataframe(gap.head(14), use_container_width=True, hide_index=True)

    with right:
        _section("Remarketing Lane")
        lanes = _remarketing_lanes(returns, snapshot)
        fig = px.pie(lanes, values="units", names="lane", hole=0.45,
                     color="lane",
                     color_discrete_map={"Retail on lot": colors["success"],
                                         "Certified pre-owned": colors["secondary"],
                                         "Wholesale / auction": colors["warning"]})
        fig.update_traces(textinfo="label+percent", textfont=dict(family=FONT, size=11))
        st.plotly_chart(_style(fig, height=300, showlegend=False), use_container_width=True)
        st.dataframe(lanes, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)

    _section("Re-Capture Pipeline")
    recapture = _load_recapture(filters, 90)
    if recapture.empty:
        st.info("No lease maturities inside 90 days under the current filters.")
    else:
        r1, r2, r3 = st.columns(3)
        loyal = recapture[recapture["loyalty_score"].fillna(0) >= 0.6]
        at_risk = recapture[recapture["churn_risk_score"].fillna(0) >= 0.6]
        with r1:
            render_kpi_card("Customers Maturing", f"{len(recapture):,}",
                            delta="within 90 days", is_positive=True)
        with r2:
            render_kpi_card("High Loyalty", f"{len(loyal):,}",
                            delta="prime re-lease targets", is_positive=True)
        with r3:
            render_kpi_card("Churn Risk", f"{len(at_risk):,}",
                            delta="need proactive contact", is_positive=False)

        st.markdown("<br>", unsafe_allow_html=True)

        tbl = recapture.sort_values("lease_maturity_date").head(12)
        st.dataframe(
            pd.DataFrame({
                "Customer": tbl["customer_name"],
                "Segment": tbl["customer_segment"],
                "Current Vehicle": tbl["brand"] + " " + tbl["model"],
                "Matures": pd.to_datetime(tbl["lease_maturity_date"]).dt.strftime("%d %b %Y"),
                "Monthly Pmt": tbl["lease_monthly_payment_usd"].apply(
                    lambda v: f"${v:,.0f}" if pd.notnull(v) else "-"),
                "Loyalty": tbl["loyalty_score"].round(2),
                "Churn Risk": tbl["churn_risk_score"].round(2),
                "Dealer": tbl["dealer_name"],
            }),
            use_container_width=True, hide_index=True,
        )


def _net_order_gap(snapshot, returns):
    """
    Requirement over the replenishment pipeline, netted against every inbound
    source including scheduled lease returns.

    Ordering against gross demand while ignoring returns is the single most
    common way a store ends up over-stocked, because the returning units arrive
    regardless.
    """
    df = snapshot.copy()
    df["pipeline_days"] = df["supplier_lead_time_days"].fillna(30) + 30
    daily = df["demand_forecast_30d"].clip(lower=0) / 30.0
    df["required"] = (daily * df["pipeline_days"]).round(0)
    df["gross_need"] = (df["required"] - df["current_stock"] - df["transit_stock"]).clip(lower=0)

    # Returns landing inside each line's own pipeline window. Matched on
    # (dealer, vehicle): a unit coming back to the Dallas store is not supply
    # for the Detroit store, so netting on vehicle alone would wipe out orders
    # the network genuinely needs to place.
    horizon_days = dict(zip(zip(df["dealer_id"], df["vehicle_id"]), df["pipeline_days"]))
    today = pd.Timestamp.today()
    ret = returns.copy()
    ret["days_out"] = (ret["lease_maturity_date"] - today).dt.days
    offsets = {}
    for key, grp in ret.groupby(["dealer_id", "vehicle_id"]):
        window = horizon_days.get(key, 60)
        offsets[key] = int((grp["days_out"] <= window).sum())
    df["returns_offset"] = [
        offsets.get((d, v), 0) for d, v in zip(df["dealer_id"], df["vehicle_id"])
    ]

    df["net_order"] = (df["gross_need"] - df["returns_offset"]).clip(lower=0)
    # Only the portion of the offset that actually cancels a needed order counts
    # as avoided; surplus returns beyond the requirement are not a saving here.
    df["applied_offset"] = np.minimum(df["gross_need"], df["returns_offset"])

    out = df[df["gross_need"] > 0].sort_values("gross_need", ascending=False)
    if out.empty:
        return pd.DataFrame()

    return pd.DataFrame({
        "Dealer": out["dealer_name"],
        "Vehicle": out["brand"] + " " + out["model"] + " " + out["variant"].fillna(""),
        "On Hand": out["current_stock"],
        "In Transit": out["transit_stock"],
        "Pipeline Demand": out["required"].astype(int),
        "Gross Need": out["gross_need"].astype(int),
        "Returns Offset": out["applied_offset"].astype(int),
        "Net Order": out["net_order"].astype(int),
    })


def _remarketing_lanes(returns, snapshot):
    """
    Route each returning unit to retail, CPO or wholesale.

    Units returning with positive equity are worth retailing; negative-equity
    units on slow-turning models are better grounded to auction than parked on
    the lot burning floorplan.
    """
    turn = snapshot.groupby("model")["days_in_stock"].mean().to_dict()
    df = returns.copy()
    df["model_days"] = df["model"].map(turn).fillna(70)

    fast = df["model_days"] <= 60
    equity = df["equity_usd"].fillna(0)

    lane = np.where(
        (equity > 1500) & fast, "Retail on lot",
        np.where(equity > 0, "Certified pre-owned", "Wholesale / auction"),
    )
    df["lane"] = lane
    summary = (df.groupby("lane")
               .agg(units=("sale_id", "size"), avg_equity=("equity_usd", "mean"))
               .reset_index())
    summary["Avg Equity"] = summary["avg_equity"].round(0).apply(lambda v: f"${v:,.0f}")
    return summary[["lane", "units", "Avg Equity"]]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Trade-In & Acquisition
# ─────────────────────────────────────────────────────────────────────────────

def _render_trade_in(filters, colors):
    trades = _load_trades(filters)
    if trades.empty:
        st.warning("No sales records match the current filters.")
        return

    with_trade = trades[trades["trade_in_flag"].fillna(False)]
    attach = len(with_trade) / len(trades) * 100 if len(trades) else 0

    # Acquisition volume is quoted on a trailing-12-month basis. Summing the
    # full filtered history would put a multi-year cumulative figure next to
    # point-in-time metrics, which reads as far larger than the run rate.
    sale_dates = pd.to_datetime(with_trade["sale_date"])
    ttm_cutoff = sale_dates.max() - pd.DateOffset(months=12)
    ttm = with_trade[sale_dates >= ttm_cutoff]
    acquired_value = float(ttm["trade_in_appraised_value_usd"].fillna(0).sum())

    avg_concession = float(trades["true_concession_usd"].mean())
    reported_disc = float(trades["discount_pct"].mean())
    true_disc = float(trades["true_concession_pct"].mean())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("Trade Attach Rate", f"{attach:,.1f}%",
                        delta=f"{len(with_trade):,} deals with a trade", is_positive=True)
    with c2:
        render_kpi_card("Used Supply Acquired", f"${acquired_value/1e6:,.1f}M",
                        delta=f"{len(ttm):,} units, trailing 12 months", is_positive=True)
    with c3:
        render_kpi_card("True Concession / Unit", f"${avg_concession:,.0f}",
                        delta=f"{true_disc:,.1f}% of MSRP", is_positive=False)
    with c4:
        gap = true_disc - reported_disc
        render_kpi_card("Hidden Giveaway", f"{gap:,.1f} pts",
                        delta=f"reported discount is {reported_disc:,.1f}%",
                        is_positive=False)

    _note("Trade-ins are the largest inbound source of used inventory. The "
          "concession figures below combine sticker discount with the "
          "over-allowance credited above appraised value and any trade bonus — "
          "only the first of the three appears in the reported discount rate.")

    st.markdown("<br>", unsafe_allow_html=True)

    left, right = st.columns([1, 1])

    with left:
        _section("True Concession Waterfall",
                 "What the store actually gives away per unit, versus what the "
                 "reported discount rate shows.")
        sticker = float(trades["sticker_discount_usd"].mean())
        over = float(trades["over_allowance_usd"].mean())
        bonus = float(trades["trade_bonus_usd"].mean())
        fig = go.Figure(go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "relative", "total"],
            x=["Sticker discount", "Over-allowance", "Trade bonus", "True concession"],
            y=[sticker, over, bonus, 0],
            text=[f"${sticker:,.0f}", f"${over:,.0f}", f"${bonus:,.0f}",
                  f"${sticker+over+bonus:,.0f}"],
            textposition="outside",
            connector=dict(line=dict(color="rgba(255,255,255,0.20)")),
            increasing=dict(marker=dict(color=colors["warning"])),
            totals=dict(marker=dict(color=colors["danger"])),
        ))
        fig.update_yaxes(title="USD per unit")
        st.plotly_chart(_style(fig, height=320, showlegend=False), use_container_width=True)

    with right:
        _section("Incentive Elasticity",
                 "Whether trade bonus money actually buys deal velocity — and "
                 "where it does not.")
        band = pd.cut(with_trade["trade_bonus_usd"].fillna(0),
                      [-1, 0, 500, 1000, 2000],
                      labels=["No bonus", "$1-500", "$501-1,000", "$1,001-2,000"])
        elas = (with_trade.assign(band=band)
                .groupby(["band", "vehicle_category"], observed=True)["lead_to_close_days"]
                .mean().reset_index())
        top_cats = with_trade["vehicle_category"].value_counts().head(4).index
        elas = elas[elas["vehicle_category"].isin(top_cats)]
        fig = px.line(elas, x="band", y="lead_to_close_days", color="vehicle_category",
                      markers=True, color_discrete_sequence=colors["colors_seq"],
                      labels={"band": "", "lead_to_close_days": "Avg days to close",
                              "vehicle_category": ""})
        st.plotly_chart(_style(fig, height=320), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    left2, right2 = st.columns([1, 1])

    with left2:
        _section("Over-Allowance by Segment",
                 "Slow-turning segments need more help closing, and that shows "
                 "up as money credited above appraised value.")
        seg = (with_trade.groupby("vehicle_category")["over_allowance_usd"]
               .mean().reset_index().sort_values("over_allowance_usd", ascending=True))
        fig = px.bar(seg, x="over_allowance_usd", y="vehicle_category", orientation="h",
                     color="over_allowance_usd", color_continuous_scale="Oranges",
                     labels={"over_allowance_usd": "Avg over-allowance (USD)",
                             "vehicle_category": ""})
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(_style(fig, height=300, showlegend=False), use_container_width=True)

    with right2:
        _section("Used Supply Intake",
                 "What is flowing into used inventory through trade, by make.")
        intake = (with_trade.groupby("trade_in_brand")
                  .agg(units=("sale_id", "size"),
                       value=("trade_in_appraised_value_usd", "sum"))
                  .reset_index().sort_values("units", ascending=False).head(10))
        fig = px.bar(intake, x="trade_in_brand", y="units",
                     color="units", color_continuous_scale="Teal",
                     labels={"trade_in_brand": "", "units": "Units acquired"},
                     hover_data={"value": ":,.0f"})
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(_style(fig, height=300, showlegend=False), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    _section("Trade-In to Replacement Flow",
             "What customers traded against what they drove away in. This is "
             "revealed substitution behaviour, and it feeds the placement engine.")
    flow = _load_replacement_flow(filters)
    if flow.empty:
        st.info("No trade-in flows under the current filters.")
    else:
        _render_sankey(flow, colors)


def _render_sankey(flow, colors, top_pairs=25):
    """Trade-in make on the left, purchased make on the right."""
    pairs = (flow.groupby(["trade_in_brand", "purchased_brand"])["deals"]
             .sum().reset_index().sort_values("deals", ascending=False).head(top_pairs))

    sources = [f"{b} (traded)" for b in pairs["trade_in_brand"]]
    targets = [f"{b} (bought)" for b in pairs["purchased_brand"]]
    labels = sorted(set(sources) | set(targets))
    idx = {label: i for i, label in enumerate(labels)}

    node_colors = [colors["warning"] if "(traded)" in l else colors["primary"] for l in labels]

    fig = go.Figure(go.Sankey(
        node=dict(pad=14, thickness=14,
                  line=dict(color="rgba(255,255,255,0.15)", width=0.5),
                  label=labels, color=node_colors),
        link=dict(source=[idx[s] for s in sources],
                  target=[idx[t] for t in targets],
                  value=pairs["deals"].tolist(),
                  color="rgba(99,102,241,0.20)"),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f3f4f6", family=FONT, size=11),
        margin=dict(l=0, r=0, t=10, b=0), height=430,
    )
    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Placement Assistant
# ─────────────────────────────────────────────────────────────────────────────

def _render_placement(snapshot, filters, colors):
    _section("Alternative Vehicle Placement",
             "When the exact vehicle a customer asked for is unavailable, rank "
             "what the network can actually deliver.")

    catalog, dealers, history = _load_placement_reference(filters)
    if catalog.empty:
        st.warning("Vehicle catalog is empty.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        brand = st.selectbox("Requested brand", sorted(catalog["brand"].unique()))
    brand_models = catalog[catalog["brand"] == brand]
    with c2:
        model = st.selectbox("Requested model", sorted(brand_models["model"].unique()))
    model_trims = brand_models[brand_models["model"] == model]
    with c3:
        trim = st.selectbox("Requested trim", sorted(model_trims["variant"].unique()))

    target_rows = model_trims[model_trims["variant"] == trim]
    if target_rows.empty:
        st.warning("That configuration is not in the catalog.")
        return
    target = target_rows.iloc[0]

    d1, d2 = st.columns([2, 1])
    brand_dealers = dealers[dealers["brand"] == brand]
    dealer_pool = brand_dealers if not brand_dealers.empty else dealers
    with d1:
        dealer_name = st.selectbox("Selling dealer", dealer_pool["dealer_name"].tolist())
    with d2:
        max_miles = st.slider("Search radius (miles)", 25, 400, 150, step=25)

    dealer_row = dealer_pool[dealer_pool["dealer_name"] == dealer_name].iloc[0]
    dealer_id = dealer_row["dealer_id"]

    # Is the requested car actually available where the customer is standing?
    here = snapshot[(snapshot["vehicle_id"] == target["vehicle_id"])
                    & (snapshot["dealer_id"] == dealer_id)
                    & (snapshot["current_stock"] > 0)]
    if not here.empty:
        st.success(
            f"**{brand} {model} {trim} is in stock at {dealer_name}** — "
            f"{int(here['current_stock'].sum())} unit(s) on the lot. "
            f"No substitution needed. The ranking below shows what else would work."
        )
    else:
        st.warning(
            f"**{brand} {model} {trim} is not available at {dealer_name}.** "
            f"Ranked alternatives below."
        )

    returns = _load_lease_returns(filters, 3)
    share = history[history["vehicle_category"] == target["category"]]
    market_share = share.groupby("model")["units"].sum() if not share.empty else None

    recs = recommend_alternatives(
        target, catalog, snapshot, dealers=dealers, dealer_id=dealer_id,
        lease_returns=returns, market_share=market_share, top_n=6,
        max_miles=max_miles,
    )

    if recs.empty:
        st.info("No substitutes are currently available inside this radius. "
                "Widen the search radius or place a factory order.")
        return

    st.markdown("<br>", unsafe_allow_html=True)
    _note(f"Requested: <b>{brand} {model} {trim}</b> — ${target['price_usd']:,} · "
          f"{target['category']} · {target['fuel_type']} · {target['drive_type']} · "
          f"{int(target['horsepower'])} hp · seats {int(target['seating_capacity'])}")

    tier_label = {
        "in_stock_here": ("On your lot", colors["success"]),
        "in_stock_nearby": ("Nearby store", colors["secondary"]),
        "in_transit": ("In transit", colors["warning"]),
        "lease_return_soon": ("Lease return", colors["accent"]),
    }

    for _, r in recs.iterrows():
        label, tone = tier_label.get(r["availability"], ("Unavailable", colors["muted"]))
        delta = r["price_delta_usd"]
        delta_txt = (f"+${delta:,.0f}" if delta > 0 else
                     (f"-${abs(delta):,.0f}" if delta < 0 else "same price"))
        aged_txt = ""
        if pd.notnull(r["days_in_stock"]) and r["days_in_stock"] > 75:
            aged_txt = (f"<span style='color:#f59e0b;'> · {int(r['days_in_stock'])} days "
                        f"on lot — priority to move</span>")

        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.035);border:1px solid rgba(255,255,255,0.09);
                    border-left:3px solid {tone};border-radius:10px;padding:14px 18px;margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;">
            <div style="font-size:15px;font-weight:700;color:#f3f4f6;">
              {r['brand']} {r['model']} <span style="color:#9ca3af;font-weight:500;">{r['variant']}</span>
            </div>
            <div style="text-align:right;white-space:nowrap;">
              <span style="color:{tone};font-weight:700;font-size:15px;">{r['placement_score_pct']:.0f}</span>
              <span style="color:#6b7280;font-size:11px;"> placement score</span>
            </div>
          </div>
          <div style="color:#d1d5db;font-size:12.5px;margin-top:6px;">
            <span style="background:{tone}22;color:{tone};border-radius:5px;padding:2px 8px;
                         font-size:11px;font-weight:600;">{label}</span>
            <span style="color:#9ca3af;"> {r['availability_detail']}</span>
            · ${r['price_usd']:,.0f} ({delta_txt})
            · spec match {r['match_pct']:.0f}%{aged_txt}
          </div>
          <div style="color:#10b981;font-size:12px;margin-top:7px;">Matches: {r['match_reasons']}</div>
          <div style="color:#9ca3af;font-size:12px;margin-top:2px;">Trade-off: {r['tradeoffs']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    _section("Specification Comparison",
             "How each recommendation lines up against the original request.")
    compare = pd.DataFrame({
        "Vehicle": ["REQUESTED: " + f"{target['brand']} {target['model']} {target['variant']}"]
                   + [f"{r['brand']} {r['model']} {r['variant']}" for _, r in recs.iterrows()],
        "Price": [target["price_usd"]] + recs["price_usd"].tolist(),
        "Category": [target["category"]] + recs["category"].tolist(),
        "Fuel": [target["fuel_type"]] + recs["fuel_type"].tolist(),
        "Drive": [target["drive_type"]] + recs["drive_type"].tolist(),
        "HP": [target["horsepower"]] + recs["horsepower"].tolist(),
        "Seats": [target["seating_capacity"]] + recs["seating_capacity"].tolist(),
        "Availability": ["-"] + [tier_label.get(a, ("Unavailable",))[0]
                                 for a in recs["availability"]],
    })
    st.dataframe(compare, use_container_width=True, hide_index=True,
                 column_config={"Price": st.column_config.NumberColumn("Price", format="$%d")})
