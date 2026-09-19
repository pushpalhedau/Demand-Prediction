"""Customer analytics queries: segments, the customer book and repeat-buyer contribution."""
from datetime import date

import pandas as pd
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from backend.db.models import Customer, Dealer, Sale


def get_customer_segments_data(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    One row per customer in the group's CRM, with the KMeans `customer_segment`
    label and each customer's real booked history (lifetime deals, revenue,
    average deal value, financing mix, months since last deal) joined from the
    sales table — everything the Customer Intelligence tab needs to describe a
    segment as an actionable group rather than a scatter cluster.

    `nationality` is selected here purely to DESCRIBE a segment's mix (~15% of
    German residents hold a non-German nationality). It is deliberately NOT a
    KMeans feature and NOT an input to the per-lead XGBoost close score:
    scoring an individual on nationality is a direct AGG
    (Allgemeines Gleichbehandlungsgesetz) exposure with no defensible
    predictive justification. `years_at_address` carries tenure instead.
    `filters['region']` optionally scopes the view to customers whose home
    Bundesland matches the sidebar filter.
    """
    cust = pd.read_sql(
        session.query(
            Customer.customer_id,
            Customer.age,
            Customer.nationality,
            Customer.region,
            Customer.income_bracket,
            Customer.annual_income,
            Customer.credit_score,
            Customer.number_of_past_purchases,
            Customer.loyalty_score,
            Customer.churn_risk_score,
            Customer.customer_segment,
            Customer.last_activity_date,
        ).statement,
        session.bind,
    )
    if filters and filters.get("region"):
        cust = cust[cust["region"] == filters["region"]]

    deals = pd.read_sql(
        session.query(
            Sale.customer_id.label("customer_id"),
            func.count(Sale.sale_id).label("lifetime_deals"),
            func.sum(Sale.total_revenue_incl_tax).label("lifetime_revenue"),
            func.avg(Sale.total_revenue_incl_tax).label("avg_deal_value"),
            func.max(Sale.sale_date).label("last_deal_date"),
            func.sum(case((Sale.financing_type == "Lease", 1), else_=0)).label("lease_deals"),
            func.sum(case((Sale.financing_type == "Cash", 1), else_=0)).label("cash_deals"),
        ).group_by(Sale.customer_id).statement,
        session.bind,
    )

    df = cust.merge(deals, on="customer_id", how="left")
    for c in ["lifetime_deals", "lifetime_revenue", "lease_deals", "cash_deals"]:
        df[c] = df[c].fillna(0)
    df["finance_deals"] = (df["lifetime_deals"] - df["lease_deals"] - df["cash_deals"]).clip(lower=0)

    ref = pd.Timestamp(date.today())
    last_deal = pd.to_datetime(df["last_deal_date"], errors="coerce")
    df["months_since_last_deal"] = ((ref - last_deal).dt.days / 30.44).round(1)

    return df


def get_customer_book(session: Session, filters: dict = None) -> pd.DataFrame:
    """
    One row per CRM customer, shaped for the Retention & Actions view: identity +
    segment + credit/income, and — joined from the sales table — first & last
    deal dates, lifetime deals/revenue, the store and vehicle of the most recent
    deal, the customer's own average months-between-purchases (cadence), and the
    nearest upcoming lease maturity (date + vehicle + store). `filters['region']`
    scopes to customers whose home state matches the sidebar filter.

    Customer counts are raw.
    """
    cust = pd.read_sql(
        session.query(
            Customer.customer_id,
            Customer.name,
            Customer.age,
            Customer.nationality,
            Customer.region,
            Customer.city,
            Customer.income_bracket,
            Customer.annual_income,
            Customer.credit_score,
            Customer.customer_segment,
            Customer.churn_risk_score,
            Customer.email_opt_in,
        ).statement,
        session.bind,
    )
    if filters and filters.get("region"):
        cust = cust[cust["region"] == filters["region"]]

    sales = pd.read_sql(
        session.query(
            Sale.customer_id.label("customer_id"),
            Sale.sale_date,
            Sale.brand,
            Sale.model,
            Sale.vehicle_category,
            Sale.financing_type,
            Sale.lease_maturity_date,
            Sale.total_revenue_incl_tax.label("deal_revenue"),
            Dealer.dealer_name.label("store"),
        ).join(Dealer, Sale.dealer_id == Dealer.dealer_id).statement,
        session.bind,
    )
    sales = sales[sales["customer_id"].isin(set(cust["customer_id"]))]
    sales["sale_date"] = pd.to_datetime(sales["sale_date"], errors="coerce")
    sales = sales.sort_values("sale_date")

    g = sales.groupby("customer_id")
    agg = g.agg(
        n_deals=("sale_date", "size"),
        first_deal=("sale_date", "min"),
        last_deal=("sale_date", "max"),
        lifetime_revenue=("deal_revenue", "sum"),
    )

    last_row = sales.drop_duplicates("customer_id", keep="last").set_index("customer_id")
    agg["last_store"] = last_row["store"]
    agg["last_brand"] = last_row["brand"]
    agg["last_model"] = last_row["model"]
    agg["last_category"] = last_row["vehicle_category"]

    # Average months between consecutive purchases, per repeat buyer — the mean
    # gap is just the span divided by the number of gaps.
    span_days = (agg["last_deal"] - agg["first_deal"]).dt.days
    agg["cadence_months"] = (span_days / (agg["n_deals"] - 1).where(agg["n_deals"] > 1) / 30.44).round(1)

    # Nearest lease maturity still ahead of us.
    ref = pd.Timestamp(date.today())
    lm = sales[
        (sales["financing_type"] == "Lease")
        & sales["lease_maturity_date"].notna()
    ].copy()
    lm["lease_maturity_date"] = pd.to_datetime(lm["lease_maturity_date"], errors="coerce")
    lm = lm[lm["lease_maturity_date"] >= ref].sort_values("lease_maturity_date")
    lm_first = lm.drop_duplicates("customer_id", keep="first").set_index("customer_id")
    agg["next_lease_maturity"] = lm_first["lease_maturity_date"]
    agg["lease_store"] = lm_first["store"]
    agg["lease_vehicle"] = (lm_first["brand"].astype(str) + " " + lm_first["model"].astype(str))

    df = cust.merge(agg, on="customer_id", how="left")
    df["n_deals"] = df["n_deals"].fillna(0).astype(int)
    df["lifetime_revenue"] = df["lifetime_revenue"].fillna(0)
    df["months_since_last_deal"] = ((ref - pd.to_datetime(df["last_deal"])).dt.days / 30.44).round(1)
    df["first_deal_year"] = pd.to_datetime(df["first_deal"]).dt.year
    return df


def get_repeat_contribution(session: Session, filters: dict = None) -> dict:
    """
    How much of the group's recent volume is repeat business: the share of the
    last 12 months' deals that went to a customer who had bought from the group
    before, plus the all-time share. `filters['region']` scopes by the store's
    state (same as the other Sale-based queries)."""
    q = session.query(Sale.customer_id, Sale.sale_date, Sale.region)
    df = pd.read_sql(q.statement, session.bind)
    if filters and filters.get("region"):
        df = df[df["region"] == filters["region"]]
    if df.empty:
        return {"ttm_total": 0, "ttm_repeat": 0, "ttm_pct": 0.0, "all_pct": 0.0}

    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    df = df.sort_values("sale_date")
    df["first_dt"] = df.groupby("customer_id")["sale_date"].transform("min")
    df["is_repeat_txn"] = df["sale_date"] > df["first_dt"]

    ref = df["sale_date"].max()
    ttm = df[df["sale_date"] >= ref - pd.Timedelta(days=365)]
    return {
        "ttm_total": int(len(ttm)),
        "ttm_repeat": int(ttm["is_repeat_txn"].sum()),
        "ttm_pct": float(100 * ttm["is_repeat_txn"].mean()) if len(ttm) else 0.0,
        "all_pct": float(100 * df["is_repeat_txn"].mean()),
    }
