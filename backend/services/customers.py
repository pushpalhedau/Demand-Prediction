"""Customer Intelligence: the customer book, segments and lead scoring."""
import pandas as pd

from backend.analytics import retention
from backend.analytics.benchmarks import gross_series
from backend.core.cache import tenant_cache
from backend.db.session import with_session
from backend.ml.lead_scoring import get_lead_form_context, get_lead_status, predict_deal_probability
from backend.repositories import customers as customers_repo
from backend.repositories import dealers as dealers_repo

__all__ = ["customer_book", "dealer_directory", "estimated_gross", "lead_form_context", "lead_status", "lead_stores",
           "queue_page", "repeat_contribution", "retention_overview", "score_lead", "segment_data"]

# How a lead's prior relationship with the group maps to the model's loyalty score.
RELATIONSHIP_LOYALTY = {"new": 22.0, "service": 46.0, "repeat": 72.0}


@with_session
def customer_book(session, filters: dict) -> pd.DataFrame:
    return customers_repo.get_customer_book(session, filters)


@with_session
def repeat_contribution(session, filters: dict) -> dict:
    return customers_repo.get_repeat_contribution(session, filters)


@with_session
def segment_data(session, filters: dict) -> pd.DataFrame:
    return customers_repo.get_customer_segments_data(session, filters)


@with_session
def dealer_directory(session) -> pd.DataFrame:
    return dealers_repo.get_dealer_directory(session)


def estimated_gross(brands: pd.Series) -> pd.Series:
    return gross_series(brands)


QUEUE_COLUMNS = ["name", "store", "reason", "play", "when_days", "vehicle", "months_since_last_deal",
                 "opportunity_amt", "email_opt_in"]


@tenant_cache(ttl=300)
def _queue(filters: dict) -> pd.DataFrame:
    book = customer_book(filters)
    if book.empty:
        return pd.DataFrame(columns=QUEUE_COLUMNS)
    q = retention.action_queue(book)
    return q[QUEUE_COLUMNS] if not q.empty else pd.DataFrame(columns=QUEUE_COLUMNS)


def retention_overview(filters: dict) -> dict:
    """Headline counts, what the outreach queue holds, where the book stands, and the segment panel."""
    book = customer_book(filters)
    if book.empty:
        return {"status": "no_customers"}
    buyers = book[book["n_deals"] > 0]
    queue = _queue(filters)
    segments = segment_data(filters)
    return {
        "status": "ok",
        "records": int(len(book)),
        "buyers": int(len(buyers)),
        "repeat_rate_pct": float(100 * (buyers["n_deals"] >= 2).mean()) if len(buyers) else 0.0,
        "repeat_share_pct": float(repeat_contribution(filters)["all_pct"]),
        "queue_total": int(len(queue)),
        "queue_stores": sorted(queue["store"].dropna().unique().tolist()),
        "queue_reasons": queue["reason"].value_counts().to_dict(),
        "book": retention.book_state(book),
        "segments": retention.segment_panel(segments) if not segments.empty else [],
    }


def queue_page(filters: dict, *, store: str | None, reasons: list[str] | None, offset: int, limit: int | None) -> dict:
    """A slice of the outreach queue (`limit=None` returns everything that matches, for export)."""
    q = _queue(filters)
    if store:
        q = q[q["store"] == store]
    if reasons:
        q = q[q["reason"].isin(reasons)]
    total = int(len(q))
    page = q.iloc[offset:] if limit is None else q.iloc[offset:offset + limit]
    return {"total": total, "rows": page}


def lead_stores() -> list[dict]:
    """The group's stores a lead can be handled by."""
    d = dealer_directory().sort_values(["region", "city", "dealer_name"])
    return [{"store": r.dealer_name, "city": r.city, "region": r.region, "brand": r.brand} for r in d.itertuples()]


def lead_form_context() -> dict | None:
    """Option lists and numeric ranges the trained lead model was fitted on (None until it is trained)."""
    return get_lead_form_context()


def lead_status() -> dict:
    """Whether this account's lead-close model is trained, and if not, exactly why."""
    return get_lead_status()


def score_lead(lead: dict) -> dict:
    return predict_deal_probability(lead)
