"""Customer Intelligence: the customer book, segments and lead scoring."""
import pandas as pd

from backend.analytics.benchmarks import gross_series
from backend.db.session import with_session
from backend.ml.lead_scoring import get_lead_form_context, predict_deal_probability
from backend.repositories import customers as customers_repo
from backend.repositories import dealers as dealers_repo

__all__ = ["customer_book", "dealer_directory", "estimated_gross", "lead_form_context", "repeat_contribution",
           "score_lead", "segment_data"]


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


def lead_form_context() -> dict | None:
    """Option lists and numeric ranges the trained lead model was fitted on (None until it is trained)."""
    return get_lead_form_context()


def score_lead(lead: dict) -> dict:
    return predict_deal_probability(lead)
