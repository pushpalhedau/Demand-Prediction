"""
Google News RSS fetcher for local auto-demand news (any country, free, no API key).

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
import threading
import time
from datetime import datetime, timezone, date
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests

from utils.i18n import tenant_config

from sentiment.fetchers.gdelt_fetcher import (
    DE_AUTO_QUERIES,
    _is_relevant,
    _title_key,
    _timespan_days,
)

logger = logging.getLogger(__name__)

_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PredictaX/1.0; +demand-advisory)"}

# One German-language Google-News search string per theme in
# DE_AUTO_QUERIES, keyed by its
# `name`. Plain Google News query syntax (space = AND, OR = or, "" = phrase);
# a `when:<N>d` recency clause is appended per call.
_RSS_QUERIES: Dict[str, str] = {
    "de_auto_demand":    'Neuzulassungen OR Autohaus OR "Auto Absatz" OR Autohandel OR KBA',
    "ev_market_de":      'Elektroauto OR "E-Auto" OR Ladesäule OR Ladeinfrastruktur OR Batteriefabrik',
    "tax_policy":        '"Kfz-Steuer" OR Dienstwagen OR "CO2-Preis" OR Autopreise OR Zulassungskosten',
    "fuel_prices":       'Spritpreise OR Benzinpreis OR Dieselpreis OR Strompreis OR Tankstelle',
    "de_macro_economy":  'EZB OR Leitzins OR Inflation OR Konjunktur OR Rezession Deutschland',
    "auto_industry_de":  'Autoindustrie OR Werkschließung OR Stellenabbau Automobil OR "IG Metall" OR Autoproduktion',
    "auto_financing":    'Autokredit OR Autofinanzierung OR Leasing Auto OR Restwert OR Leasingrate',
    "incentives_offers": 'Neuwagen Rabatt OR "0 Prozent Finanzierung" OR Umweltbonus OR Kaufprämie OR Inzahlungnahme',
}

# The same eight themes for an English-language edition. Keys are the internal theme ids
# (kept from the original German build); only the search text changes per edition.
_RSS_QUERIES_EN: Dict[str, str] = {
    "de_auto_demand":    '("new car sales" OR "car registrations" OR "auto sales" OR "car market") {country}',
    "ev_market_de":      '("electric vehicle" OR "EV charging" OR "electric car" OR "battery plant") {country}',
    "tax_policy":        '("vehicle tax" OR "car prices" OR "registration fee" OR "import duty" OR "car tariffs") {country}',
    "fuel_prices":       '("fuel prices" OR "petrol prices" OR "gas prices" OR "diesel prices") {country}',
    "de_macro_economy":  '("interest rates" OR inflation OR "central bank" OR recession OR "consumer confidence") {country}',
    "auto_industry_de":  '("auto industry" OR "car production" OR "plant closure" OR "automaker") {country}',
    "auto_financing":    '("car loan" OR "auto financing" OR "car lease" OR "auto loan rates") {country}',
    "incentives_offers": '("new car deals" OR "car incentives" OR "0% financing" OR "car rebate") {country}',
}

_GDELT_DATE_FMT = "%Y%m%dT%H%M%SZ"
_CACHE_TTL_S = 1800
_cache: Dict[tuple, tuple] = {}
_cache_lock = threading.Lock()


def _edition() -> Dict:
    """
    The news edition for the CURRENT tenant: Google News language/country and which
    query pack to use. Explicit tenant config wins; otherwise it follows the tenant's UI language.
    """
    cfg = tenant_config()
    lang = (cfg.get("language") or "en").lower()
    hl = cfg.get("news_hl") or lang
    gl = cfg.get("news_gl") or ("DE" if lang == "de" else "US")
    return {
        "hl": hl, "gl": gl, "ceid": f"{gl}:{hl.split('-')[0]}",
        "pack": "de" if hl.lower().startswith("de") else "en",
        "country": cfg.get("country_name") or "",
    }


def _q_by_name(name: str) -> Optional[Dict]:
    return next((q for q in DE_AUTO_QUERIES if q["name"] == name), None)


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


def _fetch_one(rss_query: str, days: int, max_records: int, ed: Dict) -> List[Dict]:
    params = {
        "q": f"{rss_query.replace('{country}', ed['country'])} when:{days}d",
        "hl": ed["hl"], "gl": ed["gl"], "ceid": ed["ceid"],
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
            "language": "german" if ed["pack"] == "de" else "english",
            "sourcecountry": ed["country"] or ed["gl"],
            "socialimage": None,
        })
    return out


def fetch_all_themes_rss(
    timespan: str = "30d",
    max_records_per_query: int = 40,
    one_per_day: bool = True,
) -> List[Dict]:
    """
    Fetch recent German auto-market news for every theme via Google News RSS and
    return a flat, deduplicated, relevance-gated list of article dicts shaped
    like ``gdelt_fetcher.fetch_all_themes``.
    """
    ed = _edition()
    days = _timespan_days(timespan)
    # News is public and identical for everyone on the same edition, so fetch it once per
    # (country, language) and share it across tenants: request volume scales with editions, not tenants.
    key = (ed["hl"], ed["gl"], ed["country"], days, max_records_per_query, one_per_day)
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < _CACHE_TTL_S:
            return [dict(a) for a in hit[1]]
    articles = _fetch_edition(ed, days, max_records_per_query, one_per_day)
    with _cache_lock:
        _cache[key] = (time.time(), articles)
    return [dict(a) for a in articles]


def _fetch_edition(ed: Dict, days: int, max_records_per_query: int, one_per_day: bool) -> List[Dict]:
    queries = _RSS_QUERIES if ed["pack"] == "de" else _RSS_QUERIES_EN
    seen_urls: set = set()
    seen_titles: set = set()
    seen_days: set = set()
    all_articles: List[Dict] = []
    dropped_noise = 0

    for name, rss_query in queries.items():
        q = _q_by_name(name)
        if q is None:
            continue
        try:
            raw = _fetch_one(rss_query, days, max_records_per_query, ed)
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
