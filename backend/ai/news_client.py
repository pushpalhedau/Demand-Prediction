"""
News client — fetches recent UAE real estate news via Google News RSS.
No API key required. Results are cached for 1 hour.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import feedparser

from backend.data.cache import cache

log = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

TEMPLATE_QUERIES: dict[str, str] = {
    "Rate Hike Impact":      "UAE interest rate mortgage real estate",
    "Golden Visa Expansion": "UAE golden visa residency property",
    "Supply Surge":          "UAE real estate new projects supply",
    "Oil Price Boom":        "oil price UAE economy real estate",
    "Infrastructure Boom":   "UAE infrastructure investment property",
}

NEWS_CATEGORIES: dict[str, str] = {
    "Market Overview":     "UAE Dubai real estate property market",
    "Mortgage & Rates":    "UAE Dubai mortgage interest rates home loan",
    "New Developments":    "UAE Dubai Abu Dhabi property project launch offplan",
    "Policy & Regulation": "UAE Dubai real estate regulation RERA DLD visa",
    "Investment & ROI":    "UAE Dubai property investment rental yield returns",
    "Infrastructure":      "UAE Dubai metro road infrastructure real estate",
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _struct_to_iso(t) -> str:
    try:
        dt = datetime(*t[:6], tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return ""


def _parse_iso(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


class NewsClient:

    @property
    def available(self) -> bool:
        return True

    def fetch_recent_news(self, template_name: str, area: str, days: int = 7) -> list[dict]:
        """Fetch via Google News RSS for lever calibration, filtered to last `days` days."""
        base_query = TEMPLATE_QUERIES.get(template_name, "UAE real estate market")
        area_tag   = "" if area in ("All UAE", "UAE", "") else area
        query      = f"{base_query} {area_tag}".strip()

        cache_key = {"gnews_query": query, "days": days}
        cached = cache.get("gnews_rss", cache_key)
        if cached is not None:
            return cached

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        all_articles, _ = self._fetch_google_news_rss(query, max_results=50)
        articles = [a for a in all_articles if _parse_iso(a["publishedAt"]) >= cutoff][:10]
        if not articles:
            # No articles within the window — fall back to most recent available
            articles = sorted(all_articles, key=lambda a: a.get("publishedAt", ""), reverse=True)[:10]

        if articles:
            cache.set("gnews_rss", cache_key, articles, ttl=3600)
        return articles

    def _fetch_google_news_rss(self, query: str, max_results: int = 10) -> tuple[list[dict], str]:
        url = GOOGLE_NEWS_RSS.format(query=query.replace(" ", "+"))
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                return [], "Google News returned no articles for this query."
            articles = []
            for entry in feed.entries[:max_results]:
                pub    = _struct_to_iso(entry.get("published_parsed") or entry.get("updated_parsed"))
                source = (entry.get("source") or {}).get("title", "") or entry.get("author", "")
                articles.append({
                    "title":       entry.get("title", ""),
                    "description": _strip_html(entry.get("summary", "")),
                    "publishedAt": pub,
                    "source":      source,
                    "url":         entry.get("link", ""),
                })
            log.info("Google News RSS: fetched %d articles for '%s'", len(articles), query)
            return articles, ""
        except Exception as exc:
            log.warning("Google News RSS fetch failed: %s", exc)
            return [], str(exc)

    def fetch_news_by_category(self, category: str, days: int = 7) -> tuple[list[dict], str]:
        """Returns (articles, error_message) filtered to last `days` days."""
        query     = NEWS_CATEGORIES.get(category, "UAE Dubai real estate property market")
        from_day  = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        cache_key = {"gnews_category": category, "from": from_day}

        cached = cache.get("gnews_cat", cache_key)
        if cached is not None:
            return cached, ""

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        all_articles, error = self._fetch_google_news_rss(query, max_results=50)
        articles = [a for a in all_articles if _parse_iso(a["publishedAt"]) >= cutoff][:10]

        if not articles and not error:
            error = f"No articles found in the last {days} days for this category."
        if articles:
            cache.set("gnews_cat", cache_key, articles, ttl=3600)
        return articles, error


news_client = NewsClient()
