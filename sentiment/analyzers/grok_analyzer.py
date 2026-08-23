"""
Grok AI analyzer for extracting structured demand forecasting signals from news articles.

Uses xAI's Grok API (OpenAI-compatible) to analyze article titles and return:
    sentiment_score, impact_score, affected_vehicle_category,
    economic_risk, demand_direction, estimated_demand_change_pct,
    confidence, summary

Mode selection (automatic):
    LIVE mode  — XAI_API_KEY is set in .env → calls Grok API (grok-3-mini by default)
    MOCK mode  — XAI_API_KEY missing/empty  → keyword-based scoring, no external calls

Both modes produce identical output schemas so the rest of the pipeline is unaffected.
"""

import os
import sys
import json
import logging
import hashlib
import random
from datetime import datetime
from typing import List, Dict, Optional, Tuple

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from database.connection import get_db_session, init_all_tables
from database.models import NewsArticle, SentimentSignal

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

_XAI_API_KEY: str = os.getenv("XAI_API_KEY", "").strip()
_GROK_MODEL: str = os.getenv("GROK_MODEL", "grok-3-mini")
_GROK_BASE_URL: str = "https://api.x.ai/v1"
_BATCH_SIZE: int = 10  # articles per Grok API call

# ─────────────────────────────────────────────────────────────────────────────
# Grok system prompt
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a financial and automotive market intelligence analyst specializing in the North American (US) automobile market.

For each news article title provided, extract structured demand forecasting signals relevant to the US auto market.

Return a JSON object with this exact schema:
{
  "signals": [
    {
      "article_index": <integer, 0-based index matching the input list>,
      "sentiment_score": <float -1.0 to 1.0, where -1=very negative, 0=neutral, 1=very positive>,
      "impact_score": <float 0.0 to 1.0, how much this news could impact US auto demand>,
      "affected_vehicle_category": <one of: "EV", "Luxury", "SUV", "Sedan", "Commercial", "All">,
      "economic_risk": <one of: "low", "medium", "high">,
      "demand_direction": <one of: "up", "down", "neutral">,
      "estimated_demand_change_pct": <float, estimated % change in demand, e.g. 3.5 or -2.1>,
      "confidence": <float 0.0 to 1.0, your confidence in this analysis>,
      "summary": <string, one concise sentence explaining the demand impact>
    }
  ]
}

Rules:
- Consider context: US auto tariffs and Fed rate policy strongly affect financing-led demand; EV adoption growth has slowed since the federal EV tax credit expired in Oct 2025; trucks and SUVs remain the dominant segments.
- Import tariffs (Section 232) raise costs for Japanese/Korean/European brands more than domestic (Big 3 + Tesla) brands → mixed impact by brand origin.
- EV policy/incentive news → positive for EV category when incentives expand, negative when they are cut.
- Gas price drops → positive for gasoline/truck demand, neutral for EV.
- Economic growth / Fed rate cuts → positive for luxury, SUV, and financed purchases.
- Return exactly one signal per input article in the same order.
- Only return valid JSON, nothing else."""

# ─────────────────────────────────────────────────────────────────────────────
# Mock mode: keyword-based signal generator
# ─────────────────────────────────────────────────────────────────────────────

_POSITIVE_WORDS = {
    "rise", "rose", "risen", "growth", "grew", "grow", "surge", "surged", "boost",
    "record", "strong", "strength", "high", "positive", "launch", "new", "demand",
    "popular", "expand", "investment", "recovery", "increase", "improve", "gain",
    "profit", "optimistic", "confident", "rally", "rebounded", "upgrade", "interest",
    "sales", "double", "triple", "peak", "exceed", "outperform", "accelerate",
}

_NEGATIVE_WORDS = {
    "fall", "fell", "fallen", "decline", "declined", "drop", "dropped", "weak",
    "weakness", "low", "cut", "concern", "risk", "crisis", "conflict", "sanction",
    "slow", "slowdown", "shortage", "recession", "inflation", "volatile", "volatility",
    "uncertainty", "war", "attack", "disruption", "protest", "loss", "crash",
    "deteriorate", "slump", "shrink", "contraction", "layoff", "bankrupt",
}

_HIGH_IMPACT_WORDS = {
    "opec", "oil", "war", "sanctions", "sanction", "regulation", "policy",
    "crisis", "emergency", "historic", "government", "ban", "tariff", "embargo",
}

_MEDIUM_IMPACT_WORDS = {
    "concern", "uncertainty", "risk", "slowdown", "inflation", "interest rate",
    "gdp", "economy", "market", "trade",
}

_CATEGORY_KEYWORDS = {
    "EV":         {"electric", "ev", "tesla", "byd", "charging", "battery", "hybrid", "zero-emission"},
    "Luxury":     {"luxury", "mercedes", "bmw", "porsche", "lexus", "rolls", "ferrari", "lamborghini", "premium", "audi"},
    "SUV":        {"suv", "4x4", "land rover", "range rover", "jeep", "pickup", "off-road", "crossover"},
    "Sedan":      {"sedan", "compact", "hatchback", "saloon"},
    "Commercial": {"truck", "van", "commercial", "fleet", "cargo", "logistics"},
}

_HIGH_RISK_WORDS  = {"war", "conflict", "sanction", "crisis", "recession", "crash", "emergency", "attack"}
_MED_RISK_WORDS   = {"concern", "uncertainty", "volatility", "slowdown", "risk", "tension", "threat"}


def _mock_signal_for_title(title: str, article_index: int) -> Dict:
    """
    Generate a plausible deterministic signal from article title keywords.
    Uses a title-seeded RNG so the same title always produces the same output.
    """
    words = set(title.lower().split())
    title_lower = title.lower()

    # Seed RNG from title hash for determinism
    seed = int(hashlib.md5(title.encode()).hexdigest(), 16) % (2 ** 32)
    rng = random.Random(seed)

    # Sentiment score: count positive vs negative keyword hits
    pos_hits = len(words & _POSITIVE_WORDS)
    neg_hits = len(words & _NEGATIVE_WORDS)
    total_hits = pos_hits + neg_hits
    if total_hits == 0:
        base_sentiment = rng.uniform(-0.1, 0.2)          # slight positive bias for neutral news
    else:
        base_sentiment = (pos_hits - neg_hits) / total_hits
    sentiment_score = round(max(-1.0, min(1.0, base_sentiment + rng.uniform(-0.1, 0.1))), 3)

    # Impact score
    if words & _HIGH_IMPACT_WORDS or any(w in title_lower for w in _HIGH_IMPACT_WORDS):
        impact_score = round(rng.uniform(0.55, 0.90), 3)
    elif words & _MEDIUM_IMPACT_WORDS:
        impact_score = round(rng.uniform(0.30, 0.60), 3)
    else:
        impact_score = round(rng.uniform(0.10, 0.40), 3)

    # Affected vehicle category
    affected_category = "All"
    for cat, kw_set in _CATEGORY_KEYWORDS.items():
        if words & kw_set or any(k in title_lower for k in kw_set):
            affected_category = cat
            break

    # Economic risk
    if words & _HIGH_RISK_WORDS or any(w in title_lower for w in _HIGH_RISK_WORDS):
        economic_risk = "high"
    elif words & _MED_RISK_WORDS or any(w in title_lower for w in _MED_RISK_WORDS):
        economic_risk = "medium"
    else:
        economic_risk = "low"

    # Demand direction
    if sentiment_score > 0.15:
        demand_direction = "up"
    elif sentiment_score < -0.15:
        demand_direction = "down"
    else:
        demand_direction = "neutral"

    # Estimated demand change %
    change_magnitude = impact_score * abs(sentiment_score) * rng.uniform(3.0, 8.0)
    estimated_demand_change_pct = round(
        change_magnitude if demand_direction == "up" else -change_magnitude, 2
    )

    # Confidence
    confidence = round(rng.uniform(0.55, 0.80), 3)

    return {
        "article_index":            article_index,
        "sentiment_score":          sentiment_score,
        "impact_score":             impact_score,
        "affected_vehicle_category": affected_category,
        "economic_risk":            economic_risk,
        "demand_direction":         demand_direction,
        "estimated_demand_change_pct": estimated_demand_change_pct,
        "confidence":               confidence,
        "summary":                  f"[MOCK] {demand_direction.capitalize()} signal for {affected_category} — sentiment {sentiment_score:+.2f}",
        "_mock": True,
    }


def _analyze_mock(articles: List[Dict]) -> List[Dict]:
    """Generate mock signals for all articles (no API call)."""
    return [_mock_signal_for_title(art.get("title", ""), i) for i, art in enumerate(articles)]


# ─────────────────────────────────────────────────────────────────────────────
# Live Grok API analysis
# ─────────────────────────────────────────────────────────────────────────────

def _build_grok_client():
    """Return an OpenAI client pointed at xAI's Grok endpoint."""
    try:
        from openai import OpenAI
        return OpenAI(api_key=_XAI_API_KEY, base_url=_GROK_BASE_URL)
    except ImportError:
        raise RuntimeError(
            "The 'openai' package is required for Grok analysis. "
            "Run: pip install openai"
        )


def _analyze_batch_live(client, articles: List[Dict]) -> Tuple[List[Dict], Optional[str]]:
    """
    Send one batch of articles to Grok and parse the response.

    Returns:
        (signals_list, error_message_or_None)
        Falls back to mock signals on any parse/API error.
    """
    numbered_titles = "\n".join(
        f"{i}. {art.get('title', 'No title')}"
        for i, art in enumerate(articles)
    )

    try:
        response = client.chat.completions.create(
            model=_GROK_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"Analyze these {len(articles)} news article titles:\n\n{numbered_titles}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=3000,
        )

        raw_text = response.choices[0].message.content or "{}"
        parsed = json.loads(raw_text)
        signals = parsed.get("signals", [])

        # Validate we got one signal per article
        if len(signals) != len(articles):
            logger.warning(
                "Grok returned %d signals for %d articles — falling back to mock for this batch",
                len(signals), len(articles),
            )
            return _analyze_mock(articles), "Signal count mismatch"

        # Attach raw response to each signal for storage
        for sig in signals:
            sig["_raw_response"] = raw_text
            sig["_mock"] = False

        return signals, None

    except json.JSONDecodeError as e:
        logger.warning("Grok JSON parse error: %s — falling back to mock", e)
        return _analyze_mock(articles), f"JSON parse error: {e}"
    except Exception as e:
        logger.warning("Grok API error: %s — falling back to mock", e)
        return _analyze_mock(articles), f"API error: {e}"


def _analyze_live(articles: List[Dict]) -> List[Dict]:
    """
    Analyze all articles in batches via Grok API.
    Falls back to mock signals for any failed batch.
    """
    client = _build_grok_client()
    all_signals: List[Dict] = []

    for batch_start in range(0, len(articles), _BATCH_SIZE):
        batch = articles[batch_start: batch_start + _BATCH_SIZE]
        signals, err = _analyze_batch_live(client, batch)
        if err:
            logger.warning("Batch %d–%d used mock fallback: %s", batch_start, batch_start + len(batch) - 1, err)
        all_signals.extend(signals)
        logger.info(
            "Grok | batch %d–%d analyzed (mode=%s)",
            batch_start, batch_start + len(batch) - 1,
            "mock" if (signals and signals[0].get("_mock")) else "live",
        )

    return all_signals


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def is_live_mode() -> bool:
    """Return True if XAI_API_KEY is configured and Grok will be called."""
    return bool(_XAI_API_KEY)


def analyze_articles(articles: List[Dict]) -> List[Dict]:
    """
    Analyze a list of article dicts and return signal dicts.

    Each input dict must have at least a 'title' key.
    Each output dict has the signal fields plus:
        '_mock'         : bool — True when mock mode was used
        '_raw_response' : str  — raw Grok JSON (live mode only)

    Auto-selects live vs mock mode based on XAI_API_KEY presence.
    """
    if not articles:
        return []

    if is_live_mode():
        logger.info("Grok analyzer | LIVE mode | model=%s | articles=%d", _GROK_MODEL, len(articles))
        return _analyze_live(articles)
    else:
        logger.info("Grok analyzer | MOCK mode (XAI_API_KEY not set) | articles=%d", len(articles))
        return _analyze_mock(articles)


def save_signals_to_db(
    article_dicts: List[Dict],
    signal_dicts: List[Dict],
) -> Dict[str, int]:
    """
    Persist SentimentSignal records to SQLite.

    Args:
        article_dicts: Original article dicts (must contain 'article_id' key from DB).
        signal_dicts:  Parallel list of signal dicts from analyze_articles().

    Returns:
        {"inserted": N, "skipped": N, "errors": N}
    """
    if len(article_dicts) != len(signal_dicts):
        raise ValueError(
            f"article_dicts ({len(article_dicts)}) and signal_dicts ({len(signal_dicts)}) must be same length"
        )

    init_all_tables()
    session = get_db_session()
    inserted = skipped = errors = 0

    try:
        # Load already-analyzed article IDs to avoid duplicate signals
        existing_article_ids: set = {
            row[0] for row in session.query(SentimentSignal.article_id).all()
        }

        now = datetime.utcnow()
        for art, sig in zip(article_dicts, signal_dicts):
            article_id = art.get("article_id")
            if not article_id:
                errors += 1
                continue
            if article_id in existing_article_ids:
                skipped += 1
                continue

            try:
                record = SentimentSignal(
                    article_id=article_id,
                    analyzed_at=now,
                    sentiment_score=_safe_float(sig.get("sentiment_score")),
                    impact_score=_safe_float(sig.get("impact_score")),
                    affected_vehicle_category=sig.get("affected_vehicle_category"),
                    economic_risk=sig.get("economic_risk"),
                    demand_direction=sig.get("demand_direction"),
                    estimated_demand_change_pct=_safe_float(sig.get("estimated_demand_change_pct")),
                    confidence=_safe_float(sig.get("confidence")),
                    summary=sig.get("summary"),
                    raw_response=sig.get("_raw_response"),
                )
                session.add(record)
                existing_article_ids.add(article_id)
                inserted += 1
            except Exception as e:
                logger.warning("Failed to build SentimentSignal for article_id=%s: %s", article_id, e)
                errors += 1

        session.commit()
        logger.info("Signals saved | inserted=%d skipped=%d errors=%d", inserted, skipped, errors)

    except Exception as e:
        session.rollback()
        logger.error("DB commit failed in save_signals_to_db: %s", e)
        raise
    finally:
        session.close()

    return {"inserted": inserted, "skipped": skipped, "errors": errors}


def get_unanalyzed_articles(limit: int = 100) -> List[Dict]:
    """
    Fetch NewsArticle records that have no corresponding SentimentSignal.
    Returns list of flat dicts with 'article_id' and 'title' keys.
    """
    session = get_db_session()
    try:
        analyzed_ids = {
            row[0] for row in session.query(SentimentSignal.article_id).all()
        }
        q = (
            session.query(NewsArticle.id, NewsArticle.title, NewsArticle.search_query)
            .filter(~NewsArticle.id.in_(analyzed_ids) if analyzed_ids else True)
            .order_by(NewsArticle.published_date.desc())
            .limit(limit)
        )
        return [
            {"article_id": row[0], "title": row[1] or "", "theme": row[2]}
            for row in q.all()
        ]
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Market Briefing Generator
# ─────────────────────────────────────────────────────────────────────────────

_BRIEFING_SYSTEM_PROMPT = """You are a senior North American automobile market intelligence analyst.
Write a concise, data-driven market briefing for automobile dealership executives.
Use the signal data provided. Be specific, actionable, and professional.
Structure your response with exactly three clearly labeled sections:

MARKET SENTIMENT OVERVIEW
[2–3 sentences summarising current market mood and the main drivers]

KEY RISK FACTORS & OPPORTUNITIES
[4–6 bullet points covering the most important risks and opportunities]

RECOMMENDED DEALER ACTIONS
[3 specific, numbered, actionable recommendations]

Use plain text. Do not use markdown formatting."""


def generate_market_briefing(stats: Dict, category_rows: Optional[List[Dict]] = None) -> str:
    """
    Generate a natural-language market briefing using Grok (or a template in mock mode).

    Args:
        stats:         Output of get_overall_sentiment_stats() — KPI dict.
        category_rows: Optional list of per-category dicts for richer context.

    Returns:
        Formatted string briefing ready for display.
    """
    avg_sentiment   = stats.get("avg_sentiment", 0.0)
    avg_impact      = stats.get("avg_impact", 0.0)
    geo_risk        = stats.get("geopolitical_risk", 0.0)
    direction       = stats.get("dominant_direction", "neutral")
    demand_change   = stats.get("avg_demand_change", 0.0)
    total_articles  = stats.get("total_articles", 0)
    positive_pct    = stats.get("positive_pct", 0.0)
    negative_pct    = stats.get("negative_pct", 0.0)
    trend_7d        = stats.get("trend_7d", 0.0)

    # Build category summary text
    cat_summary = ""
    if category_rows:
        lines = []
        for row in category_rows[:5]:
            cat  = row.get("category", "N/A")
            sent = row.get("avg_sentiment", 0.0) or 0.0
            chg  = row.get("avg_demand_change", 0.0) or 0.0
            lines.append(f"  {cat}: sentiment {sent:+.2f}, demand change {chg:+.1f}%")
        cat_summary = "\n".join(lines)

    if is_live_mode():
        # ── Live: call Grok ──────────────────────────────────────────────
        user_msg = (
            f"US Automobile Market Signal Data (last 30 days):\n"
            f"- Average sentiment score: {avg_sentiment:+.3f} (scale: -1 to +1)\n"
            f"- Dominant demand direction: {direction}\n"
            f"- Estimated demand change: {demand_change:+.1f}%\n"
            f"- Geopolitical risk score: {geo_risk:.3f} (scale: 0 to 1)\n"
            f"- Average news impact score: {avg_impact:.3f}\n"
            f"- Articles analysed: {total_articles} ({positive_pct:.0f}% positive, {negative_pct:.0f}% negative)\n"
            f"- 7-day sentiment trend: {trend_7d:+.3f}\n"
        )
        if cat_summary:
            user_msg += f"\nVehicle category breakdown:\n{cat_summary}\n"

        try:
            client = _build_grok_client()
            response = client.chat.completions.create(
                model=_GROK_MODEL,
                messages=[
                    {"role": "system", "content": _BRIEFING_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.4,
                max_tokens=800,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("Grok briefing generation failed: %s — using template", e)
            # Fall through to mock template

    # ── Mock / fallback template ─────────────────────────────────────────
    mood = "positive" if avg_sentiment > 0.1 else ("cautious" if avg_sentiment > -0.1 else "negative")
    risk_level = "elevated" if geo_risk > 0.4 else ("moderate" if geo_risk > 0.2 else "low")
    trend_word = "improving" if trend_7d > 0.05 else ("softening" if trend_7d < -0.05 else "stable")

    top_cat = "EV"
    if category_rows:
        sorted_cats = sorted(category_rows, key=lambda x: abs(x.get("avg_sentiment") or 0), reverse=True)
        top_cat = sorted_cats[0].get("category", "EV") if sorted_cats else "EV"

    briefing = f"""MARKET SENTIMENT OVERVIEW
The US automobile market is displaying {mood} sentiment over the past 30 days, with an average signal score of {avg_sentiment:+.2f} across {total_articles} analysed news sources. Demand signals are {trend_word} week-over-week (7-day trend: {trend_7d:+.3f}), with {positive_pct:.0f}% of coverage carrying constructive signals and {negative_pct:.0f}% flagging headwinds. The dominant demand direction across categories is {direction.upper()}, with an estimated aggregate demand shift of {demand_change:+.1f}%.

KEY RISK FACTORS & OPPORTUNITIES
- Tariff & Trade Risk: {risk_level.upper()} ({geo_risk:.2f}/1.0) — Section 232 auto tariff developments continue to be monitored as a cost and demand moderator, particularly for import-heavy brands.
- Fuel Prices: Gasoline price volatility directly affects consumer spending capacity in truck- and SUV-heavy segments.
- EV Adoption Headwind: The federal EV tax credit's Oct 2025 expiration has cooled EV momentum; charging infrastructure buildout is the remaining structural tailwind.
- Luxury Segment: Resilient high-income consumer spending continues to support Luxury and premium segment performance.
- {top_cat} Category Signal: The {top_cat} segment is showing the strongest news-driven demand signal in the current period.
- Interest Rate Sensitivity: Fed funds rate trajectory directly affects loan APRs, which may dampen financing-led demand in mid-range segments.

RECOMMENDED DEALER ACTIONS
1. Prioritise {top_cat} inventory replenishment at Tier-1 dealerships in California and Texas to capture positive demand momentum before it peaks.
2. {'Offer targeted EV test-drive incentives and highlight remaining state-level EV rebates in marketing campaigns to accelerate conversion in the EV segment.' if direction == 'up' else 'Review current discount strategy in underperforming segments and redirect marketing spend to higher-signal categories.'}
3. Hedge against tariff risk by maintaining a 15–20 day safety stock buffer for import-heavy brands, where supply chain lead times and landed costs are most exposed.

"""

    return briefing


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_float(val) -> Optional[float]:
    """Coerce val to float or return None."""
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CLI smoke-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    print(f"Mode: {'LIVE (Grok API)' if is_live_mode() else 'MOCK (keyword-based)'}")
    print(f"Model: {_GROK_MODEL}\n")

    test_articles = [
        {"article_id": 1, "title": "US Car Sales Surge 15% in April Driven by EV Adoption"},
        {"article_id": 2, "title": "Auto Tariffs Raise Vehicle Price Concerns Across Import Brands"},
        {"article_id": 3, "title": "Luxury Vehicle Registrations Hit Record High in Q1 2025"},
        {"article_id": 4, "title": "Fed Rate Decision Weighs on Consumer Financing Confidence"},
        {"article_id": 5, "title": "Tesla Opens Third Service Center in Texas Amid Growing Demand"},
    ]

    print(f"Analyzing {len(test_articles)} articles...\n")
    signals = analyze_articles(test_articles)

    for art, sig in zip(test_articles, signals):
        title_short = art["title"][:60]
        print(f"Title   : {title_short}")
        print(f"  sentiment={sig['sentiment_score']:+.3f}  impact={sig['impact_score']:.3f}  direction={sig['demand_direction']}")
        print(f"  category={sig['affected_vehicle_category']}  risk={sig['economic_risk']}  change={sig['estimated_demand_change_pct']:+.2f}%")
        print(f"  summary : {sig['summary']}")
        print(f"  mock    : {sig['_mock']}")
        print()

    # Test DB save
    print("Saving signals to DB...")
    result = save_signals_to_db(test_articles, signals)
    print(f"Save result: {result}")

    # Test idempotency
    result2 = save_signals_to_db(test_articles, signals)
    print(f"Idempotency result: {result2}")
