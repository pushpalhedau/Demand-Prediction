"""Comparative Analytics: year-over-year tracking and what is driving the movement."""
import pandas as pd

from backend.analytics import yoy_attribution as ya
from backend.db.session import with_session
from backend.repositories import sales as sales_repo
from backend.services.overview import project_series

SPECIFIC_LABEL = ya.SPECIFIC_LABEL
movement_sentences = ya.movement_sentences
__all__ = ["SPECIFIC_LABEL", "driver_split", "movement_sentences", "project_series", "scope_monthly_trend",
           "yoy_summary"]


@with_session
def yoy_summary(session, filters: dict, measure: str) -> dict | None:
    return ya.summary(session, filters, measure)


@with_session
def driver_split(session, filters: dict, dimension: str, measure: str) -> pd.DataFrame | None:
    return ya.driver_split(session, filters, dimension, measure)


@with_session
def scope_monthly_trend(session, filters: dict) -> pd.DataFrame:
    return sales_repo.get_scope_monthly_trend(session, filters)
