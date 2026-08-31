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

# Economic assumptions used to turn unit positions into money. Kept here so every
# card and table on the tab sizes capital and risk the same way.
INVOICE_COST_FACTOR = 0.93        # MSRP -> approximate dealer invoice / floorplan basis
FLOORPLAN_APR = 0.075             # matches the rate used to seed holding cost
NEW_VEHICLE_GROSS_MARGIN = 0.08   # front-end + F&I, for sizing lost-sale exposure
AGED_THRESHOLD_DEFAULT = 90


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


def _download(df, filename, key):
    """Explicit CSV export for a worklist table."""
    st.download_button(
        "Download CSV", df.to_csv(index=False), file_name=filename,
        mime="text/csv", key=key,
    )


def _pill(color, label, value, sub):
    """One coloured tile in the Stock Health alert strip."""
    return (
        f"<div style='flex:1;background:{color}1a;border:1px solid {color}55;"
        f"border-radius:10px;padding:10px 14px;'>"
        f"<div style='color:{color};font-weight:700;font-size:13px;'>{label}</div>"
        f"<div style='color:#f3f4f6;font-size:20px;font-weight:700;margin:2px 0;'>{value}</div>"
        f"<div style='color:#9ca3af;font-size:12px;'>{sub}</div></div>"
    )


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

    # Only Stock Health is exposed for now — the remaining subtabs render below
    # a single-tab bar, which reads as empty on load. Re-enable by restoring the
    # full st.tabs([...]) list and the matching `with` blocks.
    # tab_health, tab_flow, tab_trade, tab_place = st.tabs([
    #     "Stock Health",
    #     "Inventory Flow & Lease Returns",
    #     "Trade-In & Acquisition",
    #     "Placement Assistant",
    # ])
    #
    # with tab_health:
    #     _render_stock_health(snapshot, filters, colors)
    # with tab_flow:
    #     _render_flow(snapshot, filters, colors)
    # with tab_trade:
    #     _render_trade_in(filters, colors)
    # with tab_place:
    #     _render_placement(snapshot, filters, colors)

    _render_stock_health(snapshot, filters, colors)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Stock Health
# ─────────────────────────────────────────────────────────────────────────────

def _stock_health_frame(snapshot):
    """
    Derive every position column the tab needs, once, so the KPI cards, the
    alert strip and both worklists agree.

      _daily_demand   30-day forecast reduced to a daily rate
      _inbound        in transit + on order
      _net_position   on hand + inbound
      _net_deficit    reorder trigger minus net position (>= 0)
      _surplus_units  on-hand stock above the 75-day healthy line
      _cost_value     units valued at ~invoice, not MSRP
      _gp_at_risk     expected gross given up over the refill lead time
    """
    df = snapshot.copy()
    daily = (df["demand_forecast_30d"].clip(lower=0) / 30.0)
    df["_daily_demand"] = daily
    df["_inbound"] = df["transit_stock"].fillna(0) + df["units_ordered"].fillna(0)
    df["_net_position"] = df["current_stock"] + df["_inbound"]
    df["_net_deficit"] = (df["reorder_point"] - df["_net_position"]).clip(lower=0)
    df["_healthy_stock"] = np.ceil(daily * DAYS_SUPPLY_HEALTHY_HIGH)
    df["_surplus_units"] = (df["current_stock"] - df["_healthy_stock"]).clip(lower=0).astype(int)
    df["_cost_value"] = df["current_stock"] * df["price_usd"].fillna(0) * INVOICE_COST_FACTOR
    df["_gp_at_risk"] = (
        daily * df["supplier_lead_time_days"].fillna(30)
        * df["price_usd"].fillna(0) * NEW_VEHICLE_GROSS_MARGIN
        * df["stockout_risk_score"].fillna(0)
    )
    return df


def _render_stock_health(snapshot, filters, colors):
    aged_days = st.select_slider(
        "Aged-stock threshold", options=[45, 60, 75, 90, 120],
        value=AGED_THRESHOLD_DEFAULT, format_func=lambda d: f"{d} days",
    )

    snap = _stock_health_frame(snapshot)

    units = int(snap["current_stock"].sum())
    transit = int(snap["transit_stock"].fillna(0).sum())
    on_order = int(snap["units_ordered"].fillna(0).sum())

    daily_demand = snap["demand_forecast_30d"].clip(lower=0).sum() / 30.0
    net_days_supply = units / daily_demand if daily_demand > 0 else 0

    cost_value = float(snap["_cost_value"].sum())
    total_holding = float(snap["estimated_holding_cost_usd"].sum())
    floorplan_mo = cost_value * FLOORPLAN_APR / 12.0
    fixed_mo = max(total_holding - floorplan_mo, 0.0)

    aged = snap[snap["days_in_stock"] > aged_days]
    aged_units = int(aged["current_stock"].sum())
    aged_capital = float(aged["_cost_value"].sum())
    aged_burn = float(aged["estimated_holding_cost_usd"].sum())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("Units in Stock", f"{units:,}",
                        delta=f"{transit:,} in transit · {on_order:,} on order",
                        is_positive=True)
    with c2:
        healthy = DAYS_SUPPLY_HEALTHY_LOW <= net_days_supply <= DAYS_SUPPLY_HEALTHY_HIGH
        if net_days_supply < DAYS_SUPPLY_HEALTHY_LOW:
            band_txt = f"{DAYS_SUPPLY_HEALTHY_LOW - net_days_supply:,.0f} days below healthy"
        elif net_days_supply > DAYS_SUPPLY_HEALTHY_HIGH:
            band_txt = f"{net_days_supply - DAYS_SUPPLY_HEALTHY_HIGH:,.0f} days above healthy"
        else:
            band_txt = f"inside the {DAYS_SUPPLY_HEALTHY_LOW}-{DAYS_SUPPLY_HEALTHY_HIGH} band"
        render_kpi_card("Net Days of Supply", f"{net_days_supply:,.0f} days",
                        delta=band_txt, is_positive=healthy)
    with c3:
        render_kpi_card("Inventory at Cost", f"${cost_value/1e6:,.1f}M",
                        delta=f"${(floorplan_mo + fixed_mo)/1e3:,.0f}K/mo carry "
                              f"(${floorplan_mo/1e3:,.0f}K floorplan)",
                        is_positive=False)
    with c4:
        render_kpi_card(f"Aged Over {aged_days} Days", f"{aged_units:,} units",
                        delta=f"${aged_capital/1e6:,.1f}M capital · "
                              f"${aged_burn/1e3:,.0f}K/mo burn",
                        is_positive=False)

    # ── Alert strip: the three positions that need action, sized in money ────
    # Commented out for now — re-enable to surface stockouts / below-reorder /
    # overstock as a triage row under the KPI cards.
    # stockouts = snap[snap["stockout_flag"].fillna(False)]
    # so_exposure = float(
    #     (stockouts["_daily_demand"] * 30 * stockouts["price_usd"].fillna(0)
    #      * NEW_VEHICLE_GROSS_MARGIN).sum()
    # )
    # below = snap[snap["reorder_needed"].fillna(False)]
    # below_units = int((below["reorder_point"] - below["current_stock"]).clip(lower=0).sum())
    # over = snap[snap["days_of_supply"] > DAYS_SUPPLY_HEALTHY_HIGH]
    # over_capital = float(over["_cost_value"].sum())
    #
    # st.markdown(
    #     "<div style='display:flex;gap:12px;margin:6px 0 4px 0;'>"
    #     + _pill(colors["danger"], "Stocked Out", f"{len(stockouts):,} lines",
    #             f"~${so_exposure/1e6:,.1f}M 30-day GP exposure")
    #     + _pill(colors["warning"], "Below Reorder", f"{len(below):,} lines",
    #             f"{below_units:,} units short of trigger")
    #     + _pill(colors["secondary"], "Overstocked", f"{len(over):,} lines",
    #             f"${over_capital/1e6:,.1f}M capital over the "
    #             f"{DAYS_SUPPLY_HEALTHY_HIGH}-day line")
    #     + "</div>",
    #     unsafe_allow_html=True,
    # )

    st.markdown("<br>", unsafe_allow_html=True)

    left, right = st.columns([1, 1])

    with left:
        _section("Inventory Aging Ladder")
        metric = st.radio("Aging ladder metric", ["Units", "Capital"], horizontal=True,
                          label_visibility="collapsed", key="aging_metric")
        aging = get_aging_buckets(snapshot)
        if not aging.empty:
            if metric == "Units":
                y = aging["units"]
                ytext = [f"{u:,}" for u in aging["units"]]
                ytitle = "Units"
            else:
                y = aging["capital_usd"] / 1e6
                ytext = [f"${v:,.1f}M" for v in y]
                ytitle = "Capital (USD, millions)"
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=aging["bucket"], y=y,
                marker_color=[colors["success"], colors["secondary"],
                              colors["warning"], colors["danger"]],
                text=ytext, textposition="outside",
                customdata=np.stack([aging["units"], aging["capital_usd"] / 1e6,
                                     aging["lines"]], axis=-1),
                hovertemplate="<b>%{x}</b><br>%{customdata[0]:,} units"
                              "<br>$%{customdata[1]:.1f}M capital"
                              "<br>%{customdata[2]} lines<extra></extra>",
            ))
            fig.update_yaxes(title=ytitle)
            st.plotly_chart(_style(fig, height=300, showlegend=False), use_container_width=True)

    with right:
        _section("Stock vs Demand")
        plot_df = snap

        pos_df = plot_df[plot_df["current_stock"] > 0].copy()
        if not pos_df.empty:
            pos_df["Position"] = np.where(
                pos_df["days_of_supply"] > 90, "Overstocked",
                np.where(pos_df["reorder_needed"], "Below reorder point", "Healthy"),
            )
            fig = px.scatter(
                pos_df, x="demand_forecast_30d", y="current_stock",
                color="Position", size="inventory_value_usd", size_max=26,
                hover_data={"brand": True, "model": True, "dealer_name": True,
                            "days_of_supply": ":.0f", "inventory_value_usd": ":,.0f"},
                color_discrete_map={"Healthy": colors["success"],
                                    "Below reorder point": colors["warning"],
                                    "Overstocked": colors["danger"]},
                labels={"demand_forecast_30d": "Forecast 30-day demand (units)",
                        "current_stock": "Units on hand"},
            )
            xmax = float(pos_df["demand_forecast_30d"].max())
            if not np.isfinite(xmax) or xmax <= 0:
                xmax = 1.0
            for days, dash in [(DAYS_SUPPLY_HEALTHY_LOW, "dot"),
                               (DAYS_SUPPLY_HEALTHY_HIGH, "dash")]:
                fig.add_shape(type="line", x0=0, y0=0, x1=xmax, y1=xmax * days / 30.0,
                              line=dict(color="rgba(255,255,255,0.35)", width=1, dash=dash))
                fig.add_annotation(x=xmax, y=xmax * days / 30.0, text=f"{days}d supply",
                                   showarrow=False, xanchor="right", yanchor="bottom",
                                   font=dict(color="#9ca3af", size=10))
            so = plot_df[(plot_df["current_stock"] == 0)
                         & (plot_df["demand_forecast_30d"] > 0)]
            if not so.empty:
                fig.add_trace(go.Scatter(
                    x=so["demand_forecast_30d"], y=[0] * len(so), mode="markers",
                    name="Stocked out",
                    marker=dict(symbol="x", size=9, color=colors["danger"]),
                    hovertext=(so["brand"] + " " + so["model"] + " — "
                               + so["dealer_name"]),
                    hoverinfo="text",
                ))
            st.plotly_chart(_style(fig, height=300), use_container_width=True)
        _note("Lines between the dotted (45-day) and dashed (75-day) guides sit in "
              "the healthy supply band; above the dashed guide is overstocked.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Network trend charts: commented out for now. Re-enable to show month-end
    # stock vs sales and the network days-of-supply trend with the healthy band.
    # trend = _load_trend(filters)
    # if not trend.empty:
    #     trend["record_date"] = pd.to_datetime(trend["record_date"])
    #     tl, tr = st.columns([1, 1])
    #     with tl:
    #         _section("Network Stock vs Sales")
    #         fig = go.Figure()
    #         fig.add_trace(go.Scatter(
    #             x=trend["record_date"], y=trend["units_in_stock"], name="Units on hand",
    #             mode="lines", line=dict(color=colors["primary"], width=2.5),
    #             fill="tozeroy", fillcolor="rgba(99,102,241,0.12)",
    #         ))
    #         fig.add_trace(go.Scatter(
    #             x=trend["record_date"], y=trend["units_sold_30d"], name="Units sold (30d)",
    #             mode="lines", line=dict(color=colors["secondary"], width=2, dash="dot"),
    #         ))
    #         fig.update_yaxes(title="Units")
    #         st.plotly_chart(_style(fig, height=280), use_container_width=True)
    #     with tr:
    #         _section("Network Days of Supply Trend")
    #         sold_daily = (trend["units_sold_30d"] / 30.0).replace(0, np.nan)
    #         dos = (trend["units_in_stock"] / sold_daily).clip(upper=999)
    #         fig = go.Figure()
    #         fig.add_hrect(y0=DAYS_SUPPLY_HEALTHY_LOW, y1=DAYS_SUPPLY_HEALTHY_HIGH,
    #                       fillcolor="rgba(16,185,129,0.10)", line_width=0)
    #         fig.add_trace(go.Scatter(
    #             x=trend["record_date"], y=dos, name="Days of supply",
    #             mode="lines+markers", line=dict(color=colors["accent"], width=2.5),
    #         ))
    #         fig.update_yaxes(title="Days of supply")
    #         st.plotly_chart(_style(fig, height=280, showlegend=False), use_container_width=True)
    #
    # st.markdown("<br>", unsafe_allow_html=True)

    _section("Reorder Priorities")

    # Sister-store surplus, matched on vehicle: a Dallas surplus is not cover for
    # a Detroit shortage, so netting on vehicle alone is not enough.
    surplus_by_vehicle = {}
    for vid, grp in snap[snap["_surplus_units"] > 0].groupby("vehicle_id"):
        best = grp.loc[grp["_surplus_units"].idxmax()]
        surplus_by_vehicle[vid] = (best["dealer_name"], int(best["_surplus_units"]))

    reorder = snap[snap["reorder_needed"].fillna(False)].copy()
    if reorder.empty:
        st.success("No lines are below their reorder point under the current filters.")
    else:
        reorder["_deficit"] = (reorder["reorder_point"] - reorder["current_stock"]).clip(lower=0)
        reorder["_urgency"] = (
            reorder["stockout_risk_score"].fillna(0) * 0.5
            + (reorder["supplier_lead_time_days"].fillna(30) / 70.0).clip(upper=1) * 0.3
            + (reorder["_net_deficit"] / reorder["reorder_point"].replace(0, np.nan))
              .fillna(0).clip(upper=1) * 0.2
        )

        def _coverage(r):
            if r["_net_deficit"] <= 0:
                return f"Inbound covers ({int(r['_inbound'])}u)"
            cover = surplus_by_vehicle.get(r["vehicle_id"])
            if cover and cover[0] != r["dealer_name"]:
                return f"Dealer trade ← {cover[0]} ({cover[1]}u)"
            return "Factory order"

        reorder["_coverage"] = reorder.apply(_coverage, axis=1)
        reorder = reorder.sort_values("_urgency", ascending=False)

        table = pd.DataFrame({
            "Dealer": reorder["dealer_name"],
            "Vehicle": (reorder["brand"] + " " + reorder["model"] + " "
                        + reorder["variant"].fillna("")).str.strip(),
            "State": reorder["state"],
            "On Hand": reorder["current_stock"].astype(int),
            "Inbound": reorder["_inbound"].astype(int),
            "Reorder Pt": reorder["reorder_point"].astype(int),
            "Net Short": reorder["_net_deficit"].astype(int),
            "Lead Time": reorder["supplier_lead_time_days"].fillna(30).astype(int).astype(str) + " d",
            "GP at Risk": reorder["_gp_at_risk"].round(-2).apply(lambda v: f"${v:,.0f}"),
            "Coverage": reorder["_coverage"],
            "Urgency": (reorder["_urgency"] * 100).round(0),
        })
        st.dataframe(
            table.head(15), use_container_width=True, hide_index=True,
            column_config={"Urgency": st.column_config.ProgressColumn(
                "Urgency", min_value=0, max_value=100, format="%d%%")},
        )
        _download(table, "reorder_priorities.csv", "dl_reorder")

    st.markdown("<br>", unsafe_allow_html=True)

    _section(f"Aged Inventory Action List (> {aged_days} days)")

    short_by_vehicle = {}
    for vid, grp in snap[snap["reorder_needed"].fillna(False)].groupby("vehicle_id"):
        best = grp.loc[grp["_net_deficit"].idxmax()]
        short_by_vehicle[vid] = best["dealer_name"]

    aged_tbl = snap[(snap["days_in_stock"] > aged_days) & (snap["current_stock"] > 0)].copy()
    if aged_tbl.empty:
        st.success(f"No lines are older than {aged_days} days under the current filters.")
    else:
        aged_tbl["_pressure"] = aged_tbl["_cost_value"] * aged_tbl["days_in_stock"]

        def _action(r):
            short_at = short_by_vehicle.get(r["vehicle_id"])
            if r["_daily_demand"] < 0.05 or r["days_of_supply"] >= 120 or r["days_in_stock"] >= 150:
                return "Wholesale / auction"
            if short_at and short_at != r["dealer_name"]:
                return f"Dealer trade → {short_at}"
            if r["days_of_supply"] <= DAYS_SUPPLY_HEALTHY_LOW:
                return "Hold — demand recovered, re-merchandise"
            return "Retail markdown + incentive"

        aged_tbl["_action"] = aged_tbl.apply(_action, axis=1)
        aged_tbl = aged_tbl.sort_values("_pressure", ascending=False)

        table = pd.DataFrame({
            "Dealer": aged_tbl["dealer_name"],
            "Vehicle": (aged_tbl["brand"] + " " + aged_tbl["model"] + " "
                        + aged_tbl["variant"].fillna("")).str.strip(),
            "State": aged_tbl["state"],
            "Units": aged_tbl["current_stock"].astype(int),
            "Days on Lot": aged_tbl["days_in_stock"].astype(int),
            "Days of Supply": aged_tbl["days_of_supply"].astype(int),
            "Capital": (aged_tbl["_cost_value"] / 1e3).round(0).apply(lambda v: f"${v:,.0f}K"),
            "Monthly Burn": aged_tbl["estimated_holding_cost_usd"].round(-1).apply(lambda v: f"${v:,.0f}"),
            "Suggested Action": aged_tbl["_action"],
        })
        st.dataframe(table.head(15), use_container_width=True, hide_index=True)
        _download(table, "aged_inventory_actions.csv", "dl_aged")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Inventory Flow & Lease Returns
# ─────────────────────────────────────────────────────────────────────────────

def _render_flow(snapshot, filters, colors):
    horizon = st.select_slider(
        "Forward horizon", options=[3, 6, 9, 12, 18, 24], value=6,
        format_func=lambda m: f"{m} months",
    )
    returns = _load_lease_returns(filters, horizon)

    if returns.empty:
        st.info("No lease contracts mature inside this horizon under the current filters.")
        return

    itm = returns[returns["in_the_money"]]
    uw = returns[~returns["in_the_money"]]
    itm_equity = float(itm["equity_usd"].sum())
    next_90 = returns[
        returns["lease_maturity_date"] <= pd.Timestamp.today() + pd.Timedelta(days=90)
    ]
    share_90 = len(next_90) / len(returns) if len(returns) else 0

    totals, order_table = _order_plan(snapshot, returns)
    gross = totals["gross_need"]
    offset = totals["returns_offset"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("Scheduled Lease Returns", f"{len(returns):,} units",
                        delta=f"{len(itm):,} in the money · {len(uw):,} under water",
                        is_positive=True)
    with c2:
        render_kpi_card("Returning in 90 Days", f"{len(next_90):,} units",
                        delta=f"{share_90:.0%} of the {horizon}-month book",
                        is_positive=True)
    with c3:
        render_kpi_card("Equity to Capture", f"${itm_equity/1e6:,.1f}M",
                        delta=f"across {len(itm):,} units returning above buyout",
                        is_positive=True)
    with c4:
        if gross > 0:
            render_kpi_card("Order Offset from Returns", f"{offset:,} units",
                            delta=f"{offset/gross:.0%} of a {gross:,}-unit gross need",
                            is_positive=True)
        else:
            render_kpi_card("Order Offset from Returns", "—",
                            delta="no ordering gap in this horizon", is_positive=True)

    _note("A lease return is supply the group already owns on a date-certain "
          "contract — unlike a forecast. Equity is estimated resale value minus "
          "the customer's contractual buyout.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Return calendar: forward supply curve, with the run-rate order need ──
    _section("Lease Return Calendar",
             "Units maturing each month, split by equity position. The dashed "
             "line is the average monthly order need — where the bars clear it, "
             "returns alone more than cover the run rate.")
    cal = (returns.groupby(["maturity_month", "in_the_money"]).size()
           .reset_index(name="units"))
    cal["Position"] = np.where(cal["in_the_money"], "In the money", "Under water")
    fig = px.bar(cal, x="maturity_month", y="units", color="Position",
                 color_discrete_map={"In the money": colors["success"],
                                     "Under water": colors["warning"]},
                 labels={"maturity_month": "", "units": "Units returning"})
    fig.update_layout(barmode="stack")
    if gross > 0:
        monthly_need = gross / horizon
        fig.add_hline(y=monthly_need, line=dict(color="#e5e7eb", width=1.5, dash="dash"),
                      annotation_text=f"avg monthly order need · {monthly_need:,.0f} units",
                      annotation_position="bottom right",
                      annotation_font=dict(color="#e5e7eb", size=10))
    st.plotly_chart(_style(fig, height=300), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if gross <= 0:
        _section("Returns-Adjusted Order Plan")
        st.info("No ordering gap in this horizon under the current filters.")
    else:
        _section("Returns-Adjusted Order Plan",
                 "The horizon's procurement number after netting scheduled "
                 "returns. The per-line reorder worklist lives on the Stock "
                 "Health tab.")
        st.markdown(
            f"<div style='background:rgba(16,185,129,0.10);border:1px solid "
            f"rgba(16,185,129,0.30);border-radius:10px;padding:12px 16px;"
            f"margin-bottom:14px;'>"
            f"<span style='color:#10b981;font-weight:700;font-size:15px;'>"
            f"{offset:,} units</span>"
            f"<span style='color:#d1d5db;font-size:13px;'> of the "
            f"{gross:,}-unit need are covered by scheduled lease returns — "
            f"netting them out cuts the order to "
            f"{totals['net_order']:,} units.</span></div>",
            unsafe_allow_html=True,
        )
        cwf, ctab = st.columns([1, 2])
        with cwf:
            wf = go.Figure(go.Waterfall(
                orientation="v",
                measure=["absolute", "relative", "total"],
                x=["Need after stock<br>& inbound", "Lease returns", "Order to place"],
                y=[gross, -offset, 0],
                text=[f"{gross:,}", f"−{offset:,}", f"{totals['net_order']:,}"],
                textposition="outside",
                connector=dict(line=dict(color="rgba(255,255,255,0.20)")),
                decreasing=dict(marker=dict(color=colors["success"])),
                increasing=dict(marker=dict(color=colors["warning"])),
                totals=dict(marker=dict(color=colors["primary"])),
            ))
            wf.update_yaxes(title="Units")
            st.plotly_chart(_style(wf, height=300, showlegend=False), use_container_width=True)
        with ctab:
            st.dataframe(order_table.head(12), use_container_width=True, hide_index=True)
            _download(order_table, "returns_adjusted_order_plan.csv", "dl_orderplan")

    st.markdown("<br>", unsafe_allow_html=True)

    _section("Remarketing Disposition",
             "Where each returning unit should go, and what the book is worth.")
    lanes = _remarketing_lanes(returns, snapshot)
    lane_color = {"Retail on lot": colors["success"],
                  "Certified pre-owned": colors["secondary"],
                  "Wholesale / auction": colors["warning"]}
    cbar, ctab2 = st.columns([1.5, 1])
    with cbar:
        fig = go.Figure(go.Bar(
            x=lanes["units"], y=lanes["lane"], orientation="h",
            marker_color=[lane_color.get(l, colors["muted"]) for l in lanes["lane"]],
            text=[f"{u:,.0f}" for u in lanes["units"]],
            textposition="auto",
        ))
        fig.update_xaxes(title="Units returning")
        fig.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(_style(fig, height=220, showlegend=False), use_container_width=True)
    with ctab2:
        st.dataframe(
            pd.DataFrame({
                "Lane": lanes["lane"],
                "Units": lanes["units"].astype(int),
                "Est. Value": (lanes["est_value"] / 1e6).apply(lambda v: f"${v:,.1f}M"),
                "Avg Equity": lanes["avg_equity"].round(0).apply(lambda v: f"${v:,.0f}"),
            }),
            use_container_width=True, hide_index=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    _section("Re-Capture Pipeline",
             "Every maturing lease is both a returning vehicle and a shopper who "
             "needs a replacement this quarter.")
    recapture = _load_recapture(filters, 90)
    if recapture.empty:
        st.info("No lease maturities inside 90 days under the current filters.")
    else:
        # loyalty_score is on a 0-100 scale; churn_risk_score is 0-1.
        loyal = recapture[recapture["loyalty_score"].fillna(0) >= 60]
        at_risk = recapture[recapture["churn_risk_score"].fillna(0) >= 0.6]
        st.markdown(
            f"<div style='background:rgba(99,102,241,0.10);border:1px solid "
            f"rgba(99,102,241,0.30);border-radius:10px;padding:10px 14px;"
            f"margin-bottom:12px;'>"
            f"<span style='color:#818cf8;font-weight:700;'>{len(recapture):,} customers</span>"
            f"<span style='color:#d1d5db;'> mature within 90 days — "
            f"<b style='color:#10b981;'>{len(loyal):,}</b> high-loyalty re-lease "
            f"targets, <b style='color:#f59e0b;'>{len(at_risk):,}</b> at churn "
            f"risk and worth a proactive call.</span></div>",
            unsafe_allow_html=True,
        )
        tbl = recapture.sort_values("lease_maturity_date").head(12)
        rc_table = pd.DataFrame({
            "Customer": tbl["customer_name"],
            "Segment": tbl["customer_segment"],
            "Current Vehicle": tbl["brand"] + " " + tbl["model"],
            "Matures": pd.to_datetime(tbl["lease_maturity_date"]).dt.strftime("%d %b %Y"),
            "Monthly Pmt": tbl["lease_monthly_payment_usd"].apply(
                lambda v: f"${v:,.0f}" if pd.notnull(v) else "-"),
            "Loyalty /100": tbl["loyalty_score"].apply(
                lambda v: f"{v:,.0f}" if pd.notnull(v) else "-"),
            "Churn Risk": tbl["churn_risk_score"].apply(
                lambda v: f"{v*100:,.0f}%" if pd.notnull(v) else "-"),
            "Dealer": tbl["dealer_name"],
        })
        st.dataframe(rc_table, use_container_width=True, hide_index=True)
        _download(rc_table, "lease_recapture_pipeline.csv", "dl_recapture")


def _order_plan(snapshot, returns):
    """
    Forward procurement requirement over the replenishment pipeline, netted
    against on-hand stock, the inbound pipeline (transit + on order) and
    scheduled lease returns.

    Returns (totals dict, per-line DataFrame). Ordering against gross demand
    while ignoring the returns that arrive regardless is the most common way a
    store ends up over-stocked.
    """
    df = snapshot.copy()
    df["pipeline_days"] = df["supplier_lead_time_days"].fillna(30) + 30
    daily = df["demand_forecast_30d"].clip(lower=0) / 30.0
    df["required"] = (daily * df["pipeline_days"]).round(0)
    df["inbound"] = df["transit_stock"].fillna(0) + df["units_ordered"].fillna(0)
    df["gross_need"] = (df["required"] - df["current_stock"] - df["inbound"]).clip(lower=0)

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
    # Only the portion of the offset that cancels a needed order is a saving;
    # surplus returns beyond the requirement are not counted here.
    df["applied_offset"] = np.minimum(df["gross_need"], df["returns_offset"])
    df["net_order"] = (df["gross_need"] - df["returns_offset"]).clip(lower=0)

    need = df[df["gross_need"] > 0]
    totals = {
        "gross_need": int(need["gross_need"].sum()),
        "returns_offset": int(need["applied_offset"].sum()),
        "net_order": int(need["net_order"].sum()),
    }
    out = need.sort_values("net_order", ascending=False)
    table = pd.DataFrame({
        "Dealer": out["dealer_name"],
        "Vehicle": (out["brand"] + " " + out["model"] + " "
                    + out["variant"].fillna("")).str.strip(),
        "On Hand": out["current_stock"].astype(int),
        "Inbound": out["inbound"].astype(int),
        "Gross Need": out["gross_need"].astype(int),
        "Returns Coming": out["applied_offset"].astype(int),
        "Net Order": out["net_order"].astype(int),
    })
    return totals, table


def _remarketing_lanes(returns, snapshot):
    """
    Route each returning unit to retail, CPO or wholesale, with the units and
    money in each lane.

    Positive-equity units on fast-turning models are worth retailing; negative-
    equity units on slow metal are better grounded to auction than parked on the
    lot burning floorplan.
    """
    turn = snapshot.groupby("model")["days_in_stock"].mean().to_dict()
    df = returns.copy()
    df["model_days"] = df["model"].map(turn).fillna(70)

    fast = df["model_days"] <= 60
    equity = df["equity_usd"].fillna(0)
    df["lane"] = np.where(
        (equity > 1500) & fast, "Retail on lot",
        np.where(equity > 0, "Certified pre-owned", "Wholesale / auction"),
    )
    order = ["Retail on lot", "Certified pre-owned", "Wholesale / auction"]
    summary = (df.groupby("lane")
               .agg(units=("sale_id", "size"),
                    est_value=("est_market_value_usd", "sum"),
                    avg_equity=("equity_usd", "mean"))
               .reindex(order).dropna(how="all").reset_index())
    return summary


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
