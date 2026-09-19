"""
Escaping for the few places the UI builds HTML by hand.

Streamlit renders `st.markdown(..., unsafe_allow_html=True)` as real HTML, so any value that came from data
(uploaded CSVs, news feeds, model output) must go through `esc()` first, and any link from outside through
`safe_url()`. Static text and numbers formatted by our own code do not need it.
"""
from __future__ import annotations

import html
from urllib.parse import urlparse


def esc(value) -> str:
    """HTML-escape a value for use in element text or a quoted attribute."""
    return html.escape("" if value is None else str(value), quote=True)


def safe_url(url) -> str:
    """The URL, escaped for an attribute, only if it is a plain http(s) link; otherwise an empty string."""
    text = "" if url is None else str(url).strip()
    parsed = urlparse(text)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return html.escape(text, quote=True)
    return ""
