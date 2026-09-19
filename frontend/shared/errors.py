"""
Show failures to users without leaking internals.

Exception text and stack traces reveal table names, file paths and library versions, so they never reach
the browser. Unexpected errors are logged in full with a short reference the user can quote to support;
expected, user-actionable errors (AppError subclasses) show their own safe message.
"""
from __future__ import annotations

import uuid

import streamlit as st

from backend.core.errors import AppError
from backend.core.log import get_logger

_log = get_logger("predictax.ui")


def report_error(context: str, exc: BaseException) -> str | None:
    """Render `context` as an error box. Returns the support reference for unexpected errors."""
    if isinstance(exc, AppError):
        st.error(f"{context}: {exc}")
        return None
    reference = uuid.uuid4().hex[:8]
    _log.error("%s [ref=%s]", context, reference, exc_info=exc)
    st.error(f"{context}. Something went wrong on our side. Reference: {reference}")
    return reference


def report_warning(context: str, exc: BaseException) -> str | None:
    """Like report_error but as a warning, for non-blocking failures."""
    if isinstance(exc, AppError):
        st.warning(f"{context}: {exc}")
        return None
    reference = uuid.uuid4().hex[:8]
    _log.warning("%s [ref=%s]", context, reference, exc_info=exc)
    st.warning(f"{context} (reference {reference}).")
    return reference
