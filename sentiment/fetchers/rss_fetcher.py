"""
Google News RSS fallback fetcher for UAE auto-demand news.

Why this exists
---------------
GDELT's free Doc API rate-limits an entire source IP aggressively (HTTP 429) and
often refuses to serve at all from office / cloud address ranges. When that
happens the Sentiment tab has nothing to show and a refresh looks broken.

Google News' RSS search endpoint needs no API key, has no meaningful rate limit,
and returns exactly what the pipeline needs: a title, a link, a publish date and
a source for recent articles matching a query. It is the automatic fallback the
signal processor reaches for when GDELT returns nothing.

Output contract
---------------
Every dict returned here matches the shape ``gdelt_fetcher.fetch_all_themes``
produces, so ``save_articles_to_db`` and everything downstream is unchanged:

    {url, title, domain, seendate ("%Y%m%dT%H%M%SZ"), language, sourcecountry,
     socialimage, _theme, _query_name, _query_label, _affected_category}
"""

import logging
import re
from datetime import datetime, timezone, date
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests

from sentiment.fetchers.gdelt_fetcher import (
    UAE_AUTO_QUERIES,
    _is_relevant,
    _title_key,
    _timespan_days,
)

logger = logging.getLogger(__name__)

_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PredictaX/1.0; +demand-advisory)"}

# One Google-News search string per theme in UAE_AUTO_QUERIES, keyed by its
# `name`. Plain Google News query syntax (space = AND, OR = or, "" = phrase);
# a `when:<N>d` recency clause is appended per call.
_RSS_QUERIES: Dict[str, str] = {
    "uae_auto_demand":   'UAE ("car sales" OR "auto sales" OR "vehicle sales" OR dealership OR showroom)',
    "ev_market_uae":     'UAE ("electric vehicle" OR "EV charging" OR "electric car" OR "green plate")',
    "customs_vat":       'UAE ("car prices" OR "customs duty" OR "vehicle import" OR "VAT" OR "registration fee")',
    "fuel_prices":       'UAE ("petrol price" OR "fuel price" OR "diesel price" OR "oil price")',
    "uae_macro_economy": 'UAE ("interest rate" OR inflation OR "Central Bank" OR EIBOR OR "non-oil economy")',
    "luxury_suv_uae":    'UAE ("luxury car" OR "premium SUV" OR "4x4" OR "sports car" OR "Land Cruiser" OR Patrol)',
    "auto_financing":    'UAE ("car loan" OR "auto finance" OR "car finance rate" OR "Islamic finance" OR Murabaha)',
    "incentives_offers": 'UAE ("car offers" OR "0% finance" OR "Ramadan offer" OR "trade-in offer" OR "auto promotion")',
}

_GDELT_DATE_FMT = "%Y%m%dT%H%M%SZ"


def _q_by_name(name: str) -> Optional[Dict]:
    return next((q for q in UAE_AUTO_QUERIES if q["name"] == name), None)


def _to_seendate(pub_raw: str) -> Optional[str]:
    """RFC-822 'Sat, 15 Aug 2026 07:00:00 GMT' -> GDELT '20260815T070000Z'."""
    if not pub_raw:
        return None
    try:
        dt = parsedate_to_datetime(pub_raw)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.strftime(_GDELT_DATE_FMT)
    except Exception:
        return None


def _domain_from(source_url: Optional[str], source_name: Optional[str]) -> Optional[str]:
    if source_url:
        host = urlparse(source_url).netloc.lower()
        if host:
            return host[4:] if host.startswith("www.") else host
    if source_name:
        return re.sub(r"[^a-z0-9]+", "", source_name.lower()) or None
    return None


def _split_title(raw_title: str) -> str:
    """Google News appends ' - <Source>' to every headline — drop it."""
    if not raw_title:
        return ""
    return raw_title.rsplit(" - ", 1)[0].strip() if " - " in raw_title else raw_title.strip()


def _fetch_one(rss_query: str, days: int, max_records: int) -> List[Dict]:
    params = {
        "q": f"{rss_query} when:{days}d",
        "hl": "en-AE", "gl": "AE", "ceid": "AE:en",
    }
    resp = requests.get(_GOOGLE_NEWS_RSS, params=params, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    ns = {"gn": "http://news.google.com/rss"}
    out: List[Dict] = []
    for item in root.findall(".//item")[:max_records]:
        link = (item.findtext("link") or "").strip()
        if not link:
            continue
        src_el = item.find("gn:source", ns) if item.find("gn:source", ns) is not None else item.find("source")
        src_name = src_el.text.strip() if (src_el is not None and src_el.text) else None
        src_url = src_el.get("url") if src_el is not None else None
        out.append({
            "url": link,
            "title": _split_title(item.findtext("title") or ""),
            "domain": _domain_from(src_url, src_name),
            "seendate": _to_seendate(item.findtext("pubDate") or ""),
            "language": "english",
            "sourcecountry": "United Arab Emirates",
            "socialimage": None,
        })
    return out


def fetch_all_themes_rss(
    timespan: str = "30d",
    max_records_per_query: int = 40,
    one_per_day: bool = True,
) -> List[Dict]:
    """
    Fetch recent UAE auto-market news for every theme via Google News RSS and
    return a flat, deduplicated, relevance-gated list of article dicts shaped
    like ``gdelt_fetcher.fetch_all_themes``.
    """
    days = _timespan_days(timespan)
    seen_urls: set = set()
    seen_titles: set = set()
    seen_days: set = set()
    all_articles: List[Dict] = []
    dropped_noise = 0

    for name, rss_query in _RSS_QUERIES.items():
        q = _q_by_name(name)
        if q is None:
            continue
        try:
            raw = _fetch_one(rss_query, days, max_records_per_query)
        except Exception as e:
            logger.warning("Google News RSS | theme '%s' failed: %s", name, e)
            continue

        kept = 0
        for art in raw:
            url = (art.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            if not _is_relevant(art):
                dropped_noise += 1
                continue
            tkey = _title_key(art)
            if tkey and tkey in seen_titles:
                continue
            if one_per_day:
                day = art.get("seendate", "")[:8] or None
                day_key = (q["theme"], day)
                if day is None or day_key in seen_days:
                    continue
                seen_days.add(day_key)

            seen_urls.add(url)
            if tkey:
                seen_titles.add(tkey)
            art["_theme"] = q["theme"]
            art["_query_name"] = q["name"]
            art["_query_label"] = q["label"]
            art["_affected_category"] = q["affected_category"]
            all_articles.append(art)
            kept += 1

        logger.info("Google News RSS | theme='%s' | fetched=%d | kept=%d", q["label"], len(raw), kept)

    logger.info(
        "Google News RSS | total kept=%d | off-topic dropped=%d",
        len(all_articles), dropped_noise,
    )
    return all_articles


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    arts = fetch_all_themes_rss(timespan="30d")
    print(f"\n{len(arts)} articles\n")
    for a in arts[:15]:
        print(f"  {a['seendate']}  [{a['_query_name']}]  {a['domain']}")
        print(f"      {a['title']}")
