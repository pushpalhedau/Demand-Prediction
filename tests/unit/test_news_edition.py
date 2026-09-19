import pytest

from backend.sentiment.fetchers import rss_fetcher as rss


@pytest.fixture(autouse=True)
def _clear_cache():
    rss._cache.clear()
    yield
    rss._cache.clear()


def _as_tenant(monkeypatch, cfg):
    monkeypatch.setattr(rss, "_settings", lambda: cfg)


def test_explicit_tenant_settings_pick_the_edition(monkeypatch):
    _as_tenant(monkeypatch, {"language": "en", "news_hl": "en", "news_gl": "AE", "country_name": "United Arab Emirates"})
    ed = rss._edition()
    assert (ed["hl"], ed["gl"], ed["ceid"], ed["pack"]) == ("en", "AE", "AE:en", "en")
    assert ed["country"] == "United Arab Emirates"


def test_german_tenant_gets_the_german_edition_and_pack(monkeypatch):
    _as_tenant(monkeypatch, {"language": "de", "news_hl": "de", "news_gl": "DE"})
    ed = rss._edition()
    assert (ed["hl"], ed["gl"], ed["ceid"], ed["pack"]) == ("de", "DE", "DE:de", "de")


def test_edition_falls_back_to_the_ui_language(monkeypatch):
    _as_tenant(monkeypatch, {"language": "de"})
    assert (rss._edition()["gl"], rss._edition()["pack"]) == ("DE", "de")
    _as_tenant(monkeypatch, {"language": "en"})
    assert (rss._edition()["gl"], rss._edition()["pack"]) == ("US", "en")


def test_query_carries_the_tenants_country_and_edition(monkeypatch):
    seen = {}

    class R:
        content = b"<rss><channel></channel></rss>"
        def raise_for_status(self): pass

    def fake_get(url, params, headers, timeout):
        seen.update(params)
        return R()

    monkeypatch.setattr(rss.requests, "get", fake_get)
    ed = {"hl": "en", "gl": "AE", "ceid": "AE:en", "pack": "en", "country": "United Arab Emirates"}
    rss._fetch_one(rss._RSS_QUERIES_EN["de_macro_economy"], 30, 10, ed)
    assert "United Arab Emirates" in seen["q"] and "{country}" not in seen["q"]
    assert (seen["hl"], seen["gl"], seen["ceid"]) == ("en", "AE", "AE:en")


def test_news_is_fetched_once_per_edition_and_shared_across_tenants(monkeypatch):
    calls = []

    def fake_fetch(ed, days, max_records, one_per_day):
        calls.append((ed["hl"], ed["gl"]))
        return [{"url": "u1", "title": "car sales up"}]

    monkeypatch.setattr(rss, "_fetch_edition", fake_fetch)
    for _ in range(50):                      # fifty different tenants on the US English edition
        _as_tenant(monkeypatch, {"language": "en", "news_gl": "US"})
        rss.fetch_all_themes_rss()
    _as_tenant(monkeypatch, {"language": "de", "news_hl": "de", "news_gl": "DE"})
    rss.fetch_all_themes_rss()
    assert calls == [("en", "US"), ("de", "DE")]


def test_one_tenant_mutating_its_articles_does_not_affect_the_next(monkeypatch):
    monkeypatch.setattr(rss, "_fetch_edition", lambda *a: [{"url": "u1", "title": "t"}])
    _as_tenant(monkeypatch, {"language": "en"})
    first = rss.fetch_all_themes_rss()
    first[0]["_theme"] = "tampered"
    assert "_theme" not in rss.fetch_all_themes_rss()[0]


def test_paid_scoring_is_off_unless_explicitly_enabled(monkeypatch):
    from backend.sentiment.analyzers import grok_analyzer as g
    monkeypatch.setenv("XAI_API_KEY", "xai-something")
    monkeypatch.delenv("ALLOW_PAID_SENTIMENT", raising=False)
    assert g.is_live_mode() is False
    monkeypatch.setenv("ALLOW_PAID_SENTIMENT", "1")
    assert g.is_live_mode() is True


def test_hostile_feed_xml_is_rejected(monkeypatch):
    """A 'billion laughs' / external-entity payload from the network must not be expanded."""
    bomb = (b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>'
            b'<rss><channel><item><title>&lol2;</title><link>http://x</link></item></channel></rss>')

    class Resp:
        content = bomb
        def raise_for_status(self): pass

    monkeypatch.setattr(rss.requests, "get", lambda *a, **k: Resp())
    ed = {"hl": "en", "gl": "US", "ceid": "US:en", "pack": "en", "country": ""}
    with pytest.raises(Exception, match="(?i)entit|forbidden"):
        rss._fetch_one("q", 7, 10, ed)
