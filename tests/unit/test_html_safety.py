"""Values that come from data or an external feed must never become live HTML."""
import pytest
from streamlit.testing.v1 import AppTest

from frontend.shared.safe import esc, safe_url

HOSTILE = "<img src=x onerror=alert(1)>"


def test_esc_neutralises_markup_and_quotes():
    assert esc(HOSTILE) == "&lt;img src=x onerror=alert(1)&gt;"
    assert esc("a\"b'c") == "a&quot;b&#x27;c"
    assert esc(None) == "" and esc(42) == "42"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,<script>",
                                 "vbscript:x", "//evil.example/x", "ftp://x/y", "", None, "not a url"])
def test_only_plain_http_links_survive(url):
    assert safe_url(url) == ""


def test_http_links_are_kept_and_attribute_escaped():
    assert safe_url("https://news.example.com/a?b=1") == "https://news.example.com/a?b=1"
    assert "'" not in safe_url("https://x.example/a'onmouseover='alert(1)")


def _render_signal_card(article: dict):
    import pandas as _pd

    from frontend.customer_app.views.sentiment import _signal_card
    _signal_card(_pd.Series(article))


def _markdown_of(article: dict) -> str:
    at = AppTest.from_function(_render_signal_card, args=(article,), default_timeout=60).run()
    assert not at.exception, [e.value for e in at.exception]
    return "\n".join(m.value for m in at.markdown)


def test_a_hostile_news_headline_and_link_cannot_inject_html():
    html = _markdown_of({
        "title": HOSTILE, "url": "javascript:alert(document.cookie)", "domain": "<script>x</script>",
        "published_date": "2026-01-01", "theme": "fuel_prices", "affected_category": "<b>SUV</b>",
        "demand_direction": "down", "demand_change_pct": -1.5,
        "signal_summary": "<iframe src=//evil.example></iframe>",
    })
    assert "<img" not in html and "<script" not in html and "<iframe" not in html
    assert "javascript:" not in html and "&lt;img" in html


def test_a_normal_https_link_still_renders_as_a_safe_link():
    html = _markdown_of({"title": "Fuel prices fall", "url": "https://news.example.com/x", "domain": "news.example.com",
                         "demand_direction": "up", "demand_change_pct": 2.0})
    assert "href='https://news.example.com/x'" in html and "rel='noopener noreferrer'" in html


def _render_kpi():
    from frontend.shared.ui import render_kpi_card
    render_kpi_card("<b>Title</b>", "<script>1</script>", delta="<i>+3</i>")


def test_kpi_cards_escape_their_text():
    at = AppTest.from_function(_render_kpi, default_timeout=60).run()
    html = "\n".join(m.value for m in at.markdown)
    assert "<script" not in html and "<b>Title" not in html and "&lt;b&gt;Title" in html


def _render_play_card():
    from types import SimpleNamespace

    from frontend.customer_app.views.overview import _render_play
    _render_play(1, SimpleNamespace(category="Margin", confidence="High", horizon="ongoing",
                                    title="Store <img src=x onerror=alert(1)> is discounting",
                                    detail="<script>alert(1)</script> detail", impact_amt=1234.0))


def test_generated_plays_escape_store_names_from_uploaded_data():
    at = AppTest.from_function(_render_play_card, default_timeout=60).run()
    assert not at.exception, [e.value for e in at.exception]
    html = "\n".join(m.value for m in at.markdown)
    assert "<img" not in html and "<script" not in html and "&lt;img" in html
