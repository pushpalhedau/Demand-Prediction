from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database.connection import get_db_session
from database.queries import (
    get_customer_segments_data, get_customer_book, get_repeat_contribution,
    get_dealer_directory,
)
from ml_models.xgboost_model import predict_deal_probability
from utils.helpers import (
    _section, _base_layout, _compact, _fmt_money,
    _INK, _INK_MUTED, _HUE_UP, _HUE_DOWN, _HUE_FORECAST, _HUE_MARKER,
)

# ─────────────────────────────────────────────────────────────────────────────
# Customer Intelligence — the dealer GROUP's own CRM / buyer base, not "the
# market". Tab 1 is a retention worklist (who to call now + is the base leaking);
# Tab 2 is a per-lead close score. `nationality` is gone from every view
# (fair-lending / ECOA). See docs/changelog/2026-08-29-customer-intelligence-
# dealer-positioning.md.
# ─────────────────────────────────────────────────────────────────────────────

_SEG_ORDER = [
    "High-Value / Prime", "Loyal Repeat", "Core Mainstream",
    "Value Buyers", "Lapsed / At-Risk",
]

# Benchmark gross per new unit (front-end + F&I) by franchise origin — the same
# figures Store Performance uses for "Est. gross" (NADA 2024 / Presidio-NCM
# FY2024). Used only to size the *identified* opportunity on the action queue.
_ORIGIN_GROSS = {"luxury": 8_100, "import": 3_750, "domestic": 4_050}
_LUX_BRANDS = {"BMW", "Mercedes-Benz", "Lexus"}
_IMPORT_BRANDS = {"Toyota", "Honda", "Nissan", "Subaru", "Hyundai", "Kia", "Volkswagen"}

_REASON_PRIORITY = [
    "Lease maturing",
    "Overdue for next vehicle",
    "Lapsed high-value",
    "Churn-risk spike",
]
_REASON_PLAY = {
    "Lease maturing": "Lease pull-ahead offer",
    "Overdue for next vehicle": "Trade-cycle call",
    "Lapsed high-value": "GM win-back call",
    "Churn-risk spike": "Retention save call",
}

# Lead-form option lists — MUST match the values the model was trained on
# (unseen labels are silently coerced to the encoder's first class).
_CHANNELS = ["Showroom Walk-in", "Referral", "Email Campaign", "TV/Radio",
             "Search Engine", "Online Ad", "Social Media"]
_CATEGORIES = ["SUV", "Sedan", "Pickup", "Hatchback", "Minivan", "Luxury", "Coupe"]
_FUELS = ["Gasoline", "Hybrid", "Electric", "Diesel"]
_OCCUPATIONS = ["Salaried", "Self-Employed", "Business Owner", "Retired",
                "Government Employee", "Contract Worker"]
_RELATIONSHIP = {
    "Brand-new lead": 22.0,
    "Prior service customer": 46.0,
    "Repeat buyer with the group": 72.0,
}


def _origin(brand: str) -> str:
    if brand in _LUX_BRANDS:
        return "luxury"
    if brand in _IMPORT_BRANDS:
        return "import"
    return "domestic"


def _segment_panel(df: pd.DataFrame) -> pd.DataFrame:
    """One row per segment — for the campaign-planning expander."""
    rows = []
    total = len(df)
    for seg in _SEG_ORDER:
        g = df[df["customer_segment"] == seg]
        if g.empty:
            continue
        deals = g["lifetime_deals"].sum()
        buyers = g[g["lifetime_deals"] > 0]
        rows.append({
            "Segment": seg,
            "Customers": len(g),
            "% of base": round(100 * len(g) / total, 1),
            "Lifetime revenue ($M)": round(g["lifetime_revenue"].sum() / 1e6, 1),
            "Avg deal value": round(buyers["avg_deal_value"].mean() or 0),
            "Repeat rate %": round(100 * (buyers["number_of_past_purchases"] >= 2).mean(), 0) if len(buyers) else 0,
            "Lease %": round(100 * g["lease_deals"].sum() / deals, 0) if deals else 0,
            "Median income": round(g["estimated_annual_income_usd"].median() or 0),
            "Avg credit": round(g["credit_score"].mean() or 0),
            "Mo. since deal": round(buyers["months_since_last_deal"].median(), 0) if len(buyers) else None,
        })
    return pd.DataFrame(rows)


def _build_action_queue(book: pd.DataFrame) -> pd.DataFrame:
    """
    Every customer who should be contacted now, one row each, with the reason,
    the store that should own the outreach, the play, and the identified gross
    opportunity (benchmark same-origin gross on a like-for-like replacement).
    """
    today = pd.Timestamp(date.today())
    b = book[book["n_deals"] > 0].copy()
    m = b["months_since_last_deal"]
    lm_days = (pd.to_datetime(b["next_lease_maturity"]) - today).dt.days

    lease_due = lm_days.between(0, 120)
    overdue = (
        (b["n_deals"] >= 2)
        & b["cadence_months"].notna()
        & (m >= b["cadence_months"] + 3)
        & (m <= b["cadence_months"] + 30)
    )
    hv_cut = b["lifetime_revenue"].quantile(0.70)
    lapsed_hv = (
        (b["customer_segment"] == "Lapsed / At-Risk")
        & (b["lifetime_revenue"] >= hv_cut)
        & (m >= 36)
    )
    churn = (b["churn_risk_score"].fillna(0) >= 0.62) & m.between(18, 48)

    # Assign one reason per customer, lowest-priority first so the most
    # actionable reason wins.
    b["reason"] = pd.NA
    b.loc[churn, "reason"] = "Churn-risk spike"
    b.loc[lapsed_hv, "reason"] = "Lapsed high-value"
    b.loc[overdue, "reason"] = "Overdue for next vehicle"
    b.loc[lease_due, "reason"] = "Lease maturing"

    q = b[b["reason"].notna()].copy()
    if q.empty:
        return q

    is_lease = q["reason"] == "Lease maturing"
    q["store"] = q["lease_store"].where(is_lease, q["last_store"])
    q["vehicle"] = q["lease_vehicle"].where(
        is_lease, (q["last_brand"].astype(str) + " " + q["last_model"].astype(str))
    )
    q["opportunity_usd"] = (
        q["last_brand"].map(_origin).map(_ORIGIN_GROSS).fillna(_ORIGIN_GROSS["domestic"])
    )
    q["_lm_days"] = lm_days.reindex(q.index)
    q["when"] = np.where(
        is_lease, "in " + q["_lm_days"].fillna(0).astype(int).astype(str) + " days", "now"
    )
    q["play"] = q["reason"].map(_REASON_PLAY)
    q["_prio"] = q["reason"].map({r: i for i, r in enumerate(_REASON_PRIORITY)})
    # Within lease maturities, soonest first; within the rest, biggest gross first.
    q["_sort2"] = np.where(is_lease, q["_lm_days"].fillna(999), -q["opportunity_usd"])
    q = q.sort_values(["_prio", "_sort2"], ascending=[True, True])
    return q


# Where a buyer sits in the ownership cycle, by months since their last deal
# (or an active lease). Fixed, present-tense buckets — no cohort censoring.
_BOOK_BANDS = [
    ("Active", 0, 24, _HUE_UP,
     "bought in the last 2 years or on a running lease"),
    ("In cycle — due back", 24, 48, _HUE_FORECAST,
     "past the typical replacement point; this is the queue's target"),
    ("Going quiet", 48, 84, _HUE_MARKER,
     "no deal in 4–7 years; winnable with a real effort"),
    ("Likely lost", 84, 10_000, _HUE_DOWN,
     "no deal in 7+ years; probably bought elsewhere"),
]


def _book_state(book: pd.DataFrame) -> pd.DataFrame:
    b = book[book["n_deals"] > 0].copy()
    if b.empty:
        return pd.DataFrame()
    m = b["months_since_last_deal"].fillna(9999)
    has_lease = pd.to_datetime(b["next_lease_maturity"], errors="coerce").notna()
    rows = []
    for name, lo, hi, hue, note in _BOOK_BANDS:
        sel = (m >= lo) & (m < hi)
        if name == "Active":
            sel = sel | has_lease
        else:
            sel = sel & ~has_lease
        rows.append({
            "band": name, "hue": hue, "note": note,
            "customers": int(sel.sum()),
            "lifetime_value": float(b.loc[sel, "lifetime_revenue"].sum()),
        })
    return pd.DataFrame(rows)


def render_customers(filters: dict):
    """
    Customer Intelligence — the dealer group's own buyer base. Tab 1: a retention
    action queue (who to contact now, ranked by identified gross) plus whether the
    base is leaking. Tab 2: a per-lead close score for the sales desk.
    """
    session = get_db_session()
    try:
        st.markdown(
            "<h2 class='gradient-text' style='margin-bottom:18px;'>Customer Intelligence</h2>",
            unsafe_allow_html=True,
        )

        tab1, tab2 = st.tabs(["Retention & Actions", "Lead Close Score"])

        # ================================================================
        # TAB 1 — Retention & Actions
        # ================================================================
        with tab1:
            book = get_customer_book(session, filters)
            if book.empty:
                st.warning("No customer records found. Please seed the database first.")
            else:
                rc = get_repeat_contribution(session, filters)
                buyers = book[book["n_deals"] > 0]
                repeat_rate = 100 * (buyers["n_deals"] >= 2).mean() if len(buyers) else 0
                queue = _build_action_queue(book)

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Buyers on file", f"{len(buyers):,}",
                          help=f"{len(book):,} customer records; the rest are prospects who "
                               "have not bought yet.")
                c2.metric("Repeat rate", f"{repeat_rate:.0f}%",
                          help="Share of buyers with two or more lifetime deals with the group.")
                c3.metric("Repeat share of sales", f"{rc['all_pct']:.0f}%",
                          help="Share of the group's booked deals that went to a customer "
                               "who had bought from the group before.")
                c4.metric("Flagged for outreach", f"{len(queue):,}",
                          help="Customers on the action queue below.")

                st.markdown("<br>", unsafe_allow_html=True)

                # ── 1. Retention action queue (HERO) ──────────────────────
                _section("Retention action queue")
                if queue.empty:
                    st.info("No customers fall into an outreach window for the active filters.")
                else:
                    fc1, fc2 = st.columns([1, 1])
                    stores = ["All stores"] + sorted(queue["store"].dropna().unique().tolist())
                    store_sel = fc1.selectbox("Store", options=stores)
                    reasons = sorted(queue["reason"].unique().tolist())
                    reason_sel = fc2.multiselect("Reason", options=reasons, default=reasons)

                    view = queue.copy()
                    if store_sel != "All stores":
                        view = view[view["store"] == store_sel]
                    view = view[view["reason"].isin(reason_sel)]

                    disp = pd.DataFrame({
                        "Customer": view["name"],
                        "Store": view["store"],
                        "Reason": view["reason"],
                        "Play": view["play"],
                        "Contact": view["when"],
                        "Vehicle": view["vehicle"],
                        "Mo. since deal": view["months_since_last_deal"].round(0),
                        "Identified gross ($)": view["opportunity_usd"].round(0).astype(int),
                        "Email OK": view["email_opt_in"].fillna(False).map({True: "yes", False: "no"}),
                    })
                    st.dataframe(
                        disp, use_container_width=True, hide_index=True, height=430,
                        column_config={
                            "Mo. since deal": st.column_config.NumberColumn(format="%.0f"),
                            "Identified gross ($)": st.column_config.NumberColumn(format="%d"),
                        },
                    )
                    dl1, _dl = st.columns([1, 3])
                    dl1.download_button(
                        "Download this list (CSV)",
                        data=disp.to_csv(index=False).encode("utf-8"),
                        file_name="retention_action_queue.csv",
                        mime="text/csv",
                    )

                st.markdown("<br>", unsafe_allow_html=True)

                # ── 2. Where the book stands ──────────────────────────────
                _section("Where the book stands")
                bs = _book_state(book)
                if bs.empty:
                    st.info("Not enough purchase history.")
                else:
                    bs = bs[bs["customers"] > 0]
                    fig = px.bar(bs, x="customers", y="band", orientation="h")
                    fig.update_traces(
                        marker_color=list(bs["hue"]),
                        text=[f"{_compact(c)}  ·  {_fmt_money(v)} lifetime"
                              for c, v in zip(bs["customers"], bs["lifetime_value"])],
                        textposition="outside", cliponaxis=False,
                        customdata=bs[["note"]],
                        hovertemplate="<b>%{y}</b><br>%{customdata[0]}<extra></extra>",
                    )
                    fig.update_layout(**_base_layout(
                        height=250, margin=dict(l=0, r=140, t=6, b=0)))
                    fig.update_xaxes(title="Buyers", showgrid=True,
                                     gridcolor="rgba(255,255,255,0.06)")
                    fig.update_yaxes(title="", categoryorder="array",
                                     categoryarray=list(bs["band"])[::-1])
                    st.plotly_chart(fig, use_container_width=True)

                # ── 3. Segment detail (expander) ──────────────────────────
                with st.expander("Segment detail — for campaign planning"):
                    seg_df = get_customer_segments_data(session, filters)
                    if seg_df.empty:
                        st.info("No customer data.")
                    else:
                        st.dataframe(
                            _segment_panel(seg_df), use_container_width=True, hide_index=True,
                            column_config={
                                "Customers": st.column_config.NumberColumn(format="%d"),
                                "% of base": st.column_config.NumberColumn(format="%.1f%%"),
                                "Lifetime revenue ($M)": st.column_config.NumberColumn(format="%.1f"),
                                "Avg deal value": st.column_config.NumberColumn(format="$%d"),
                                "Repeat rate %": st.column_config.NumberColumn(format="%.0f%%"),
                                "Lease %": st.column_config.NumberColumn(format="%.0f%%"),
                                "Median income": st.column_config.NumberColumn(format="$%d"),
                                "Avg credit": st.column_config.NumberColumn(format="%d"),
                                "Mo. since deal": st.column_config.NumberColumn(format="%.0f"),
                            },
                        )

        # ================================================================
        # TAB 2 — Lead close score
        # ================================================================
        with tab2:
            _section(
                "Lead Close Score",
                "Score a showroom or BDC lead for one of the group's stores — the "
                "closing probability, what is moving it, and the next action.",
            )

            dealers = get_dealer_directory(session)
            dealers = dealers.sort_values(["state", "city", "dealer_name"])
            store_opts = {
                f"{r.dealer_name} — {r.city}, {r.state}": (r.state, r.dealer_name, r.brand)
                for r in dealers.itertuples()
            }
            store_pick = st.selectbox("Store handling this lead", options=list(store_opts.keys()))
            pick_state, pick_store, pick_brand = store_opts[store_pick]

            f1, f2, f3 = st.columns(3)
            with f1:
                age = st.slider("Customer age", 21, 75, 38)
                occupation = st.selectbox("Occupation", options=_OCCUPATIONS)
                income = st.number_input("Annual income (USD)", 20000, 300000, 75000, step=5000)
            with f2:
                credit_score = st.slider("Credit score", 400, 850, 710)
                vehicle_category = st.selectbox("Vehicle category", options=_CATEGORIES)
                fuel_type = st.selectbox("Fuel type", options=_FUELS)
            with f3:
                marketing_channel = st.selectbox("Lead source", options=_CHANNELS)
                relationship = st.selectbox("Prior relationship", options=list(_RELATIONSHIP.keys()))
                discount_pct = st.slider("Discount you can offer (%)", 0.0, 20.0, 6.0, step=0.5)
                base_price = st.number_input("Vehicle base price (USD)", 15000, 250000, 42000, step=1000)

            if st.button("Score this lead", type="primary"):
                lead = {
                    "age": age,
                    "occupation": occupation,
                    "estimated_annual_income_usd": income,
                    "credit_score": credit_score,
                    "loyalty_score": _RELATIONSHIP[relationship],
                    "vehicle_category": vehicle_category,
                    "fuel_type": fuel_type,
                    "marketing_channel": marketing_channel,
                    "discount_pct": discount_pct,
                    "base_price": base_price,
                    "state": pick_state,
                }
                res = predict_deal_probability(lead)
                prob = res["close_probability"]
                explanations = res.get("explanations", [])
                explainer = res.get("explainer_used", "none")

                st.markdown("<br>", unsafe_allow_html=True)
                g_col, d_col = st.columns([1, 2])

                with g_col:
                    _section("Closing probability", None)
                    band = ("green — work it now" if prob >= 0.70
                            else "amber — structured follow-up" if prob >= 0.45
                            else "red — long shot")
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=prob * 100,
                        number={"suffix": "%", "font": {"size": 40}},
                        gauge={
                            "axis": {"range": [0, 100], "tickvals": [0, 25, 50, 75, 100],
                                     "tickfont": {"size": 10, "color": _INK_MUTED}},
                            "bar": {"color": _HUE_FORECAST, "thickness": 0.28},
                            "bgcolor": "rgba(0,0,0,0)",
                            "borderwidth": 0,
                            "steps": [
                                {"range": [0, 45], "color": "rgba(239,68,68,0.18)"},
                                {"range": [45, 70], "color": "rgba(245,158,11,0.18)"},
                                {"range": [70, 100], "color": "rgba(16,185,129,0.18)"},
                            ],
                        },
                    ))
                    fig.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(color=_INK, family="Plus Jakarta Sans"),
                        margin=dict(l=30, r=30, t=10, b=0), height=210,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption(f"Zone: **{band}**")

                with d_col:
                    _section(
                        "What's moving this score",
                        "Per-lead SHAP attribution." if explainer == "shap"
                        else "Quick estimate — SHAP unavailable, three fields only.",
                    )
                    if explanations:
                        ex = pd.DataFrame(explanations).head(6).sort_values("score")
                        ex["attr"] = ex["feature"].str.replace("_", " ").str.title()
                        fig = px.bar(
                            ex, x="score", y="attr", orientation="h",
                            color="direction",
                            color_discrete_map={"positive": _HUE_UP, "negative": _HUE_DOWN},
                        )
                        fig.update_layout(**_base_layout(height=240, legend=False,
                                                         margin=dict(l=0, r=0, t=6, b=0)))
                        fig.update_xaxes(title="Push on closing probability", zeroline=True,
                                         zerolinecolor="rgba(255,255,255,0.25)")
                        fig.update_yaxes(title="")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Attribution unavailable for this lead.")

                _lead_recommendation(prob, pick_store, marketing_channel)

    except Exception as e:  # pragma: no cover - surfaced in the UI
        st.error(f"Error rendering Customer Intelligence: {e}")
        import traceback
        st.code(traceback.format_exc())
    finally:
        session.close()


def _lead_recommendation(prob: float, store: str, channel: str):
    """Plain-language next action tied to the store, a cadence and a lever."""
    if prob >= 0.70:
        st.success(
            f"**Hot lead — work it now.** Call from {store} within the hour and book a "
            "same-day or next-day appointment. Confirm with a text now and a reminder two "
            "hours before the visit (a three-touch confirm lifts show rates toward 80%). "
            "Have F&I pre-qualify before they arrive. No extra discount is needed to hold this one."
        )
    elif prob >= 0.45:
        st.warning(
            f"**Warm lead — structured follow-up.** Assign to {store}'s BDC for 6–8 touches "
            "across call, text and email over the next 14–21 days, leading with an "
            "appointment rather than a price. If they stall, the lever that moves this "
            "deal is a stronger trade allowance or a rate buy-down that lowers the monthly "
            "payment — not sticker discount. Re-score once the appointment is set."
        )
    else:
        extra = ""
        if channel in ("Online Ad", "Social Media", "Search Engine"):
            extra = " Internet leads at this score rarely close — keep the spend low."
        st.error(
            f"**Long-shot lead.** One well-timed call and one email from {store}, then move "
            f"to the monthly nurture list.{extra} Before a desk manager spends time on it, "
            "check whether a lower trim or a different segment fits the payment the customer "
            "can carry. Escalate to the manager only if they book and show."
        )
