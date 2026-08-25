"""
GDELT Doc v2 API fetcher for North American automobile market intelligence.

GDELT (Global Database of Events, Language, and Tone) is a free, real-time
global news database with no API key required.

Two data products used here:
  1. ArtList  — list of matching news articles (title, url, date, domain, country)
  2. TimelineTone — daily average tone time-series for a search query

Flow:
  fetch_all_themes()
      └─→ fetch_articles_for_query()  [for each NA_AUTO_QUERIES entry]
  save_articles_to_db()               [deduplicates by URL, persists to SQLite]
  fetch_tone_timeline()               [used by the dashboard for trend charts]
  get_stored_articles()               [loads persisted articles + signals for rendering]
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional

import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from database.connection import get_db_session, init_all_tables
from database.models import NewsArticle, SentimentSignal
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


class GdeltUnavailableError(RuntimeError):
    """
    Raised when GDELT could not be reached after all retries (rate limiting,
    timeouts, network errors). Distinct from GdeltQueryError: the query is
    fine, the API just would not serve it right now. Surfaced rather than
    swallowed so a rate-limited refresh doesn't look identical to "no news".
    """


class GdeltQueryError(RuntimeError):
    """
    Raised when GDELT rejects a query outright.

    GDELT signals a malformed query with HTTP 200 and a plain-text body (e.g.
    "Parentheses may only be used around OR'd statements.") rather than an
    error status. Without this, resp.json() just raises ValueError, the retry
    loop swallows it, and the caller sees an empty article list that is
    indistinguishable from "no news matched" — which is how a hard syntax
    error silently surfaced as "0 articles fetched".
    """

# ─────────────────────────────────────────────────────────────────────────────
# GDELT API endpoint
# ─────────────────────────────────────────────────────────────────────────────
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# ─────────────────────────────────────────────────────────────────────────────
# North American automobile market themed search queries
# Each entry maps to a thematic bucket used later for per-theme aggregation.
# ─────────────────────────────────────────────────────────────────────────────
NA_AUTO_QUERIES: List[Dict] = [
    {
        "name": "na_auto_demand",
        "label": "US Auto Demand",
        # GDELT syntax notes:
        #   - Space-separated words are an implicit AND, so a bare list of 5
        #     words matches almost nothing. Use explicit OR of short phrases.
        #   - Parentheses are ONLY legal around OR'd statements. Putting an
        #     implicit-AND group in parens makes GDELT reject the whole query
        #     with "Parentheses may only be used around OR'd statements."
        #   - Scope to the US with sourcecountry: rather than a "US" keyword.
        # "keywords" is used by _infer_theme() for bucketing combined-query
        # results; it must stay plain words (no quotes/OR) for that matching.
        "query": '("car sales" OR "auto sales" OR "vehicle sales" OR dealership) sourcecountry:US',
        "keywords": ["car", "sales", "auto", "vehicle", "dealership"],
        "theme": "auto_demand",
        "affected_category": "All",
    },
    {
        "name": "ev_market_na",
        "label": "EV Market US",
        "query": '("electric vehicle" OR "EV tax credit" OR "electric car") sourcecountry:US',
        "keywords": ["electric", "vehicle", "credit"],
        "theme": "ev_market",
        "affected_category": "EV",
    },
    {
        "name": "tariff_trade",
        "label": "Auto Tariffs & Trade",
        "query": '("auto tariff" OR "car tariffs" OR "vehicle imports") sourcecountry:US',
        "keywords": ["tariff", "tariffs", "import", "imports", "trade"],
        "theme": "tariff_trade",
        "affected_category": "All",
    },
    {
        "name": "fuel_oil_prices",
        "label": "Fuel & Oil Prices",
        "query": '("gas prices" OR "oil prices" OR "crude oil" OR "fuel prices") sourcecountry:US',
        "keywords": ["gas", "oil", "crude", "fuel", "prices"],
        "theme": "fuel_economic",
        "affected_category": "All",
    },
    {
        "name": "us_macro_economy",
        "label": "US Economy",
        "query": '("interest rates" OR inflation OR "Federal Reserve") sourcecountry:US',
        "keywords": ["interest", "rates", "inflation", "federal", "reserve", "economy"],
        "theme": "macro_economic",
        "affected_category": "All",
    },
    {
        "name": "luxury_suv_na",
        "label": "Luxury & SUV US",
        "query": '("luxury SUV" OR "pickup truck" OR "luxury car") sourcecountry:US',
        "keywords": ["luxury", "truck", "pickup", "mercedes"],
        "theme": "luxury_suv",
        "affected_category": "Luxury",
    },
]

# Flat OR-list covering every theme above, used by fetch_all_themes(combine_queries=True).
# Kept flat (no nested parens) because GDELT rejects nested/AND-grouped parentheses.
COMBINED_QUERY = (
    '("car sales" OR "auto sales" OR dealership OR "electric vehicle" '
    'OR "auto tariff" OR "gas prices" OR inflation OR "luxury SUV" '
    'OR "pickup truck") sourcecountry:US'
)


# GDELT seendate format
_GDELT_DATE_FMT = "%Y%m%dT%H%M%SZ"

# Supported timespan values for GDELT API
TIMESPAN_OPTIONS = {
    "Last 7 days": "7d",
    "Last 30 days": "30d",
    "Last 90 days": "90d",
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_gdelt_date(raw: str) -> Optional[date]:
    """Parse GDELT seendate '20240115T120000Z' → Python date. Returns None on failure."""
    try:
        return datetime.strptime(raw, _GDELT_DATE_FMT).date()
    except Exception:
        return None


# GDELT requires at least 1 request per 5 seconds (free tier policy).
# The documented limit is one request per 5 seconds, but in practice GDELT
# still returns 429 at much wider gaps for large (250-record) responses, so
# 10s is the floor here — a multi-slice refresh needs the headroom.
_GDELT_MIN_INTERVAL = 10.0
_last_request_time: float = 0.0

# GDELT's limit is global (per source IP), not per-thread. Two concurrent
# callers (e.g. two browser sessions both clicking "Refresh Data") can each
# pass the "has enough time elapsed?" check before either updates
# _last_request_time, then both fire within the same window and both get
# 429'd together. Holding this lock for the full throttle+request+backoff
# cycle serializes all outbound GDELT calls process-wide so that can't happen.
_gdelt_lock = threading.Lock()


def _throttle():
    """Block until at least _GDELT_MIN_INTERVAL seconds have passed since the last request."""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    gap = _GDELT_MIN_INTERVAL - elapsed
    if gap > 0:
        time.sleep(gap)
    _last_request_time = time.monotonic()


def _get(url: str, params: Dict, retries: int = 3):
    """
    Rate-limited GET with exponential backoff on 429/timeout.
    Enforces ≥6s between all GDELT requests, serialized across threads/sessions
    via _gdelt_lock. Returns parsed JSON or None.
    """
    base_wait = 10.0  # start with 10s backoff on error (safe margin above GDELT's 5s limit)

    with _gdelt_lock:
        for attempt in range(retries):
            _throttle()
            try:
                resp = requests.get(url, params=params, timeout=30)

                if resp.status_code == 429:
                    # GDELT says "one every 5 seconds" — wait longer before retry
                    retry_after = float(resp.headers.get("Retry-After", base_wait * (2 ** attempt)))
                    logger.warning(
                        "GDELT 429 (attempt %d/%d) — waiting %.0fs before retry",
                        attempt + 1, retries, retry_after,
                    )
                    if attempt < retries - 1:
                        time.sleep(retry_after)
                    continue

                resp.raise_for_status()
                return resp.json()

            except requests.exceptions.Timeout:
                logger.warning("GDELT timeout (attempt %d/%d)", attempt + 1, retries)
            except requests.exceptions.HTTPError as e:
                logger.warning("GDELT HTTP error %s (attempt %d/%d)", e, attempt + 1, retries)
            except ValueError:
                # A 200 that isn't JSON means GDELT rejected the query itself.
                # Retrying is pointless — the query will be rejected identically
                # every time — so fail loudly with the API's own message.
                body = (resp.text or "").strip()
                if resp.status_code == 200 and body:
                    raise GdeltQueryError(body[:300])
                logger.warning("GDELT non-JSON response (attempt %d/%d)", attempt + 1, retries)
            except requests.exceptions.RequestException as e:
                logger.warning("GDELT request error: %s (attempt %d/%d)", e, attempt + 1, retries)

            if attempt < retries - 1:
                time.sleep(base_wait * (2 ** attempt))

    raise GdeltUnavailableError(
        f"GDELT did not return data after {retries} attempts "
        "(rate limited, timed out, or unreachable)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_articles_for_query(
    query: str,
    timespan: str = "30d",
    max_records: int = 75,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[Dict]:
    """
    Fetch English-language news articles from GDELT Doc v2 ArtList for one query.

    Args:
        query:       GDELT query string (supports OR, AND, quoted phrases).
        timespan:    e.g. "7d", "30d", "90d". Ignored when start/end are given.
        max_records: 1-250 (GDELT hard cap is 250).
        start, end:  Explicit window. Used instead of `timespan` so callers can
            walk backwards in slices — see fetch_all_themes(slice_days=...).

    Returns:
        List of raw article dicts from GDELT, English only.
    """
    params = {
        "query": query,
        "mode": "ArtList",
        "maxrecords": min(max_records, 250),
        "format": "json",
        "sort": "DateDesc",
    }
    if start and end:
        params["startdatetime"] = start.strftime("%Y%m%d%H%M%S")
        params["enddatetime"] = end.strftime("%Y%m%d%H%M%S")
    else:
        params["timespan"] = timespan

    data = _get(GDELT_DOC_API, params)

    if not data:
        return []

    articles = data.get("articles") or []
    # Keep English articles only (GDELT returns multi-language results)
    return [a for a in articles if (a.get("language") or "").lower() == "english"]


def _timespan_days(timespan: str) -> int:
    """'30d' -> 30. Falls back to 30 for anything unparseable."""
    try:
        return int("".join(ch for ch in timespan if ch.isdigit())) or 30
    except Exception:
        return 30


def _infer_theme(article: Dict) -> Dict:
    """
    Best-effort mapping of a combined-query article back to one of our
    NA_AUTO_QUERIES themes, by keyword overlap against the article title.
    Falls back to the first (general) theme when nothing scores.
    """
    title = (article.get("title") or "").lower()
    best, best_score = NA_AUTO_QUERIES[0], -1
    for q in NA_AUTO_QUERIES:
        # Match against the curated "keywords" list, NOT q["query"] — the query
        # string now contains GDELT syntax (quotes, OR, sourcecountry:) that
        # would otherwise be treated as matchable words.
        score = sum(1 for w in q["keywords"] if w in title)
        if score > best_score:
            best, best_score = q, score
    return best


def fetch_all_themes(
    timespan: str = "30d",
    max_records_per_query: int = 50,
    delay_between_queries: float = 5.0,
    one_per_day: bool = True,
    combine_queries: bool = True,
    slice_days: int = 0,
) -> List[Dict]:
    """
    Fetch articles for all NA auto-market themes and return a deduplicated list.

    Each article dict is enriched with:
        _theme, _query_name, _query_label, _affected_category

    Args:
        timespan:               GDELT timespan string.
        max_records_per_query:  Articles to request per theme (max 250).
        delay_between_queries:  Seconds to wait between GDELT calls (be polite).
            Ignored when combine_queries=True since there's only one call.
        one_per_day:            Quick volume-control switch. When True (default),
            keeps only the single most-recent article per (theme, calendar day)
            instead of every match. This cuts what the analyze step has to
            process way down, so a full fetch -> analyze -> summarize pipeline
            run reliably finishes in one go instead of leaving articles stuck
            in `pending_analysis` and the KPI cards at zero. Each day's signal
            becomes one article's read rather than an average across several.
        combine_queries:        When True (default), issues ONE GDELT call
            covering all themes via an OR'd query instead of one call per
            theme — 6x fewer requests, much faster, and far less likely to
            trip GDELT's 429 rate limit. Each returned article is tagged with
            its best-matching theme afterward via keyword overlap against the
            title (see _infer_theme). Set False to fall back to the slower,
            more precisely-bucketed per-theme querying.
        slice_days:             Window size, in days, for walking the timespan
            backwards. GDELT returns at most 250 DateDesc records per call, so
            one call to a busy query only reaches ~2 days back regardless of
            timespan. Slicing is OFF by default (0 = one call, ~2 days back)
            because GDELT's free tier rate-limits a multi-slice refresh hard:
            a 30d/2d run is 15 calls and most get 429'd, so it is slow AND
            returns less than the single call. Since articles are persisted
            and deduplicated by URL, coverage accumulates across daily
            refreshes anyway. Set slice_days=2 for a deliberate backfill when
            you can tolerate several minutes and partial results.

    Returns:
        Flat, deduplicated list of article dicts.
    """
    seen_urls: set = set()
    seen_days: set = set()
    all_articles: List[Dict] = []

    if combine_queries:
        # GDELT caps every response at 250 records and sorts DateDesc, so for a
        # high-volume query a single 30d call only ever reaches ~2 days back --
        # the timespan selector was effectively cosmetic. Walk backwards in
        # slice_days-sized windows instead so each window's 250 records cover
        # its own days. Costs one request per slice, which the _gdelt_lock
        # throttle serializes.
        raw: List[Dict] = []
        if slice_days and slice_days > 0:
            total_days = _timespan_days(timespan)
            window_end = datetime.utcnow()
            slices = max(1, -(-total_days // slice_days))  # ceil
            failed_slices = 0
            for i in range(slices):
                window_start = window_end - timedelta(days=slice_days)
                try:
                    chunk = fetch_articles_for_query(
                        query=COMBINED_QUERY,
                        max_records=250,
                        start=window_start,
                        end=window_end,
                    )
                except GdeltUnavailableError as e:
                    # A refresh spanning many slices will sometimes lose one to
                    # rate limiting. Partial coverage beats losing the whole
                    # run, so record it and keep going; only a total wipeout
                    # (below) is treated as a failure.
                    failed_slices += 1
                    logger.warning(
                        "GDELT | slice %d/%d (%s..%s) failed: %s",
                        i + 1, slices, window_start.date(), window_end.date(), e,
                    )
                    window_end = window_start
                    continue
                logger.info(
                    "GDELT | slice %d/%d | %s..%s | %d articles",
                    i + 1, slices, window_start.date(), window_end.date(), len(chunk),
                )
                raw.extend(chunk)
                window_end = window_start

            if failed_slices == slices:
                raise GdeltUnavailableError(
                    f"all {slices} GDELT slices failed (rate limited or unreachable)"
                )
            if failed_slices:
                logger.warning(
                    "GDELT | %d/%d slices failed - coverage is partial",
                    failed_slices, slices,
                )
        else:
            raw = fetch_articles_for_query(
                query=COMBINED_QUERY,
                timespan=timespan,
                max_records=min(max_records_per_query * len(NA_AUTO_QUERIES), 250),
            )

        for article in raw:
            url = (article.get("url") or "").strip()
            if not url or url in seen_urls:
                continue

            q = _infer_theme(article)
            if one_per_day:
                day = _parse_gdelt_date(article.get("seendate", ""))
                day_key = (q["theme"], day)
                if day is None or day_key in seen_days:
                    continue
                seen_days.add(day_key)

            seen_urls.add(url)
            article["_theme"] = q["theme"]
            article["_query_name"] = q["name"]
            article["_query_label"] = q["label"]
            article["_affected_category"] = q["affected_category"]
            all_articles.append(article)

        logger.info(
            "GDELT | combined query | fetched=%d | unique=%d",
            len(raw), len(all_articles),
        )
        return all_articles

    # ── Fallback: original slower per-theme path (one GDELT call per theme) ──
    for q in NA_AUTO_QUERIES:
        raw = fetch_articles_for_query(
            query=q["query"],
            timespan=timespan,
            max_records=max_records_per_query,
        )

        new_for_theme = 0
        # raw is already sorted DateDesc, so the first hit per (theme, day)
        # is that day's most recent article.
        for article in raw:
            url = (article.get("url") or "").strip()
            if not url or url in seen_urls:
                continue

            if one_per_day:
                day = _parse_gdelt_date(article.get("seendate", ""))
                day_key = (q["theme"], day)
                if day is None or day_key in seen_days:
                    continue
                seen_days.add(day_key)

            seen_urls.add(url)
            article["_theme"] = q["theme"]
            article["_query_name"] = q["name"]
            article["_query_label"] = q["label"]
            article["_affected_category"] = q["affected_category"]
            all_articles.append(article)
            new_for_theme += 1

        logger.info(
            "GDELT | theme='%s' | fetched=%d | new_unique=%d",
            q["label"], len(raw), new_for_theme,
        )

        if delay_between_queries > 0:
            time.sleep(delay_between_queries)

    logger.info("GDELT | total unique articles fetched: %d", len(all_articles))
    return all_articles


def save_articles_to_db(articles: List[Dict]) -> Dict[str, int]:
    """
    Persist raw GDELT article dicts to the news_articles table.
    Skips any URL already present (idempotent).

    Returns:
        {"inserted": N, "skipped": N, "errors": N}
    """
    init_all_tables()
    session = get_db_session()
    inserted = skipped = errors = 0

    try:
        # One query to load all existing URLs — avoids per-row SELECT
        existing_urls: set = {
            row[0] for row in session.query(NewsArticle.url).all()
        }

        now = datetime.utcnow()
        for art in articles:
            url = (art.get("url") or "").strip()
            if not url:
                errors += 1
                continue
            if url in existing_urls:
                skipped += 1
                continue

            try:
                record = NewsArticle(
                    url=url,
                    title=(art.get("title") or "").strip() or None,
                    source_domain=art.get("domain"),
                    source_country=art.get("sourcecountry"),
                    published_date=_parse_gdelt_date(art.get("seendate", "")),
                    fetched_at=now,
                    search_query=art.get("_query_name"),
                    language=art.get("language"),
                    social_image_url=art.get("socialimage"),
                )
                session.add(record)
                existing_urls.add(url)
                inserted += 1
            except Exception as e:
                logger.warning("Failed to build NewsArticle for '%s': %s", url, e)
                errors += 1

        session.commit()
        logger.info("DB save | inserted=%d skipped=%d errors=%d", inserted, skipped, errors)

    except Exception as e:
        session.rollback()
        logger.error("DB commit failed in save_articles_to_db: %s", e)
        raise
    finally:
        session.close()

    return {"inserted": inserted, "skipped": skipped, "errors": errors}


def fetch_tone_timeline(
    query: str,
    timespan: str = "90d",
) -> List[Dict]:
    """
    Fetch GDELT's daily average tone timeline for a query.
    Positive values = positive tone; negative = negative/alarming news.

    Returns:
        List of {"date": date, "tone": float} sorted ascending by date.
    """
    try:
        data = _get(GDELT_DOC_API, {
            "query": query,
            "mode": "TimelineTone",
            "format": "json",
            "timespan": timespan,
        })
    except (GdeltUnavailableError, GdeltQueryError) as e:
        # Timelines only feed trend charts — a missing one shouldn't abort a
        # refresh the way a failed article fetch should.
        logger.warning("Tone timeline unavailable for '%s': %s", query, e)
        return []

    if not data:
        return []

    # GDELT TimelineTone returns:
    # {"timeline": [{"date": "20240101T000000Z", "value": -1.45}, ...]}
    # OR nested under a key like "data" — handle both
    raw_timeline = data.get("timeline") or data.get("data") or []

    result = []
    for point in raw_timeline:
        parsed_date = _parse_gdelt_date(point.get("date", ""))
        tone = point.get("value") or point.get("tone")
        if parsed_date and tone is not None:
            result.append({"date": parsed_date, "tone": float(tone)})

    return sorted(result, key=lambda x: x["date"])


def fetch_all_tone_timelines(timespan: str = "90d") -> Dict[str, List[Dict]]:
    """
    Fetch tone timelines for all NA auto themes.
    Returns dict: {theme_name: [{"date": date, "tone": float}, ...]}
    """
    timelines: Dict[str, List[Dict]] = {}
    for q in NA_AUTO_QUERIES:
        tl = fetch_tone_timeline(q["query"], timespan=timespan)
        timelines[q["name"]] = tl
        logger.info("Tone timeline | theme='%s' | points=%d", q["label"], len(tl))
        time.sleep(1.0)
    return timelines


def get_stored_articles(
    days_back: int = 30,
    theme: Optional[str] = None,
    analyzed_only: bool = False,
    limit: int = 500,
) -> List[Dict]:
    """
    Load stored NewsArticle records (with joined SentimentSignal) from SQLite.
    Used by the dashboard to render the news feed and sentiment charts.

    Args:
        days_back:     How many calendar days back to include.
        theme:         Filter by search_query name (e.g. 'ev_market_na').
        analyzed_only: If True, return only articles that have a SentimentSignal.
        limit:         Max rows to return.

    Returns:
        List of flat dicts ready for a Pandas DataFrame or Streamlit table.
    """
    session = get_db_session()
    try:
        cutoff = date.today() - timedelta(days=days_back)
        q = (
            session.query(NewsArticle)
            .options(joinedload(NewsArticle.sentiment_signal))
            .filter(NewsArticle.published_date >= cutoff)
        )
        if theme:
            q = q.filter(NewsArticle.search_query == theme)
        if analyzed_only:
            q = q.join(SentimentSignal, NewsArticle.id == SentimentSignal.article_id)

        q = q.order_by(NewsArticle.published_date.desc()).limit(limit)

        rows = []
        for art in q.all():
            sig = art.sentiment_signal
            rows.append({
                "article_id":        art.id,
                "title":             art.title or "Untitled",
                "url":               art.url,
                "domain":            art.source_domain,
                "country":           art.source_country,
                "published_date":    art.published_date,
                "theme":             art.search_query,
                # sentiment signal fields (None if not yet analyzed)
                "sentiment_score":        sig.sentiment_score if sig else None,
                "impact_score":           sig.impact_score if sig else None,
                "demand_direction":       sig.demand_direction if sig else None,
                "affected_category":      sig.affected_vehicle_category if sig else None,
                "economic_risk":          sig.economic_risk if sig else None,
                "demand_change_pct":      sig.estimated_demand_change_pct if sig else None,
                "confidence":             sig.confidence if sig else None,
                "signal_summary":         sig.summary if sig else None,
                "analyzed":               sig is not None,
            })
        return rows
    finally:
        session.close()


def get_article_stats() -> Dict:
    """
    Quick summary stats on stored articles — used for dashboard KPI cards.

    Returns:
        {"total_articles": N, "analyzed_articles": N, "oldest_date": date, "newest_date": date}
    """
    session = get_db_session()
    try:
        from sqlalchemy import func
        total = session.query(func.count(NewsArticle.id)).scalar() or 0
        analyzed = session.query(func.count(SentimentSignal.id)).scalar() or 0
        oldest = session.query(func.min(NewsArticle.published_date)).scalar()
        newest = session.query(func.max(NewsArticle.published_date)).scalar()
        return {
            "total_articles": total,
            "analyzed_articles": analyzed,
            "pending_analysis": total - analyzed,
            "oldest_date": oldest,
            "newest_date": newest,
        }
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# CLI smoke-test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    print("Fetching NA auto market articles from GDELT (last 7 days)...")
    articles = fetch_all_themes(timespan="7d", max_records_per_query=10, delay_between_queries=5.0)
    print(f"Fetched {len(articles)} unique articles")

    if articles:
        print("\nSample article:")
        a = articles[0]
        print(f"  Title   : {a.get('title')}")
        print(f"  Domain  : {a.get('domain')}")
        print(f"  Country : {a.get('sourcecountry')}")
        print(f"  Date    : {a.get('seendate')}")
        print(f"  Theme   : {a.get('_theme')}")

    result = save_articles_to_db(articles)
    print(f"\nDB save result: {result}")

    stats = get_article_stats()
    print(f"DB stats: {stats}")
