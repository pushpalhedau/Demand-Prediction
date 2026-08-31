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

_SYSTEM_PROMPT = """You advise a US automobile dealer group — 24 rooftops across California, Texas, Florida, New York, Illinois, Georgia, Ohio and Michigan. About 56% of the group's units are import franchises (Toyota, Honda, Hyundai, Kia, Subaru, Nissan, VW, BMW, Mercedes-Benz, Lexus); the rest are domestic (Chevrolet, Ford, Ram, GMC, Jeep, Tesla). Segment mix is roughly SUV 49%, Pickup 23%, Sedan 16%, Luxury 9%.

For each news headline, score its effect on RETAIL new-vehicle demand at the group's showrooms and on day-to-day dealership operations (what to stock, how to price, whether to pull forward or hold incentives, and financing / F&I talk-tracks).

Return a JSON object with this exact schema:
{
  "signals": [
    {
      "article_index": <integer, 0-based index matching the input list>,
      "sentiment_score": <float -1.0 to 1.0, where -1=very negative for retail demand, 0=neutral, 1=very positive>,
      "impact_score": <float 0.0 to 1.0, how much this news could move the group's showroom demand over the next ~30 days>,
      "affected_vehicle_category": <one of: "EV", "Luxury", "SUV", "Sedan", "Pickup", "Commercial", "All">,
      "economic_risk": <one of: "low", "medium", "high">,
      "demand_direction": <one of: "up", "down", "neutral">,
      "estimated_demand_change_pct": <float, estimated % change in the group's retail demand, typically between -6 and +6; reserve larger values for genuine shocks>,
      "confidence": <float 0.0 to 1.0, your confidence in this analysis>,
      "summary": <string, one sentence — name the affected segment and the dealership action it implies>
    }
  ]
}

Rules:
- Financing cost is the strongest single lever: a higher auto-loan APR or Fed rate raises monthly payments and cuts financed demand within weeks (~-3% units per +1 point of APR); rate cuts help luxury, SUV and financed purchases.
- Pump price: a higher gas price shifts mix away from SUV/Pickup toward Sedan (~-4% truck/SUV per +$1/gal) with a smaller drag on total volume; a gas price drop does the reverse.
- Section 232 import tariffs raise vehicle cost for the group's import rooftops much more than its domestic ones (~+$5,000+ per imported unit vs ~+$1,800 domestic) — treat tariff news mainly as a cost / margin / pricing signal with a modest demand tilt against import segments.
- OEM incentive / rebate / lease-deal news → supports demand when programs expand, drags when they are cut (~+2% per +1 point of incentive spend).
- EV: adoption growth slowed after the federal EV tax credit expired Oct 2025; state rebates and charging buildout are the remaining tailwinds.
- Consumer-sentiment / confidence news is a leading, low-magnitude signal (cap around ±2%).
- Return exactly one signal per input article in the same order.
- Only return valid JSON, nothing else."""

# ─────────────────────────────────────────────────────────────────────────────
# Mock mode: keyword-based signal generator
# ─────────────────────────────────────────────────────────────────────────────

# Deliberately conservative — tokens that are ambiguous in a headline ("rally
# allies" vs "stocks rally", "interest rate", "new bill", "record deaths") are
# left out. The keyword scorer only leans when the wording is unambiguous.
_POSITIVE_WORDS = {
    "rose", "risen", "growth", "grew", "surge", "surged", "boost", "boosted",
    "strong", "strength", "rebound", "rebounded", "recovery", "improve", "improved",
    "gains", "optimistic", "upbeat", "affordable", "cheaper", "discount", "incentives",
    "rebate", "rebates", "0%", "outperform", "accelerating",
}

# "cut" is left out on purpose — "rate cut" is good for auto demand, "job cuts"
# is bad; the token alone tells us nothing.
_NEGATIVE_WORDS = {
    "falls", "fell", "declines", "declined", "slump", "slumped", "weak", "weakness",
    "concern", "concerns", "crisis", "recession", "downturn", "shortage",
    "unaffordable", "pricey", "expensive", "hike", "hikes", "surcharge",
    "slowdown", "slowing", "plunge", "plunged", "layoffs", "bankruptcy",
    "delinquencies", "repossessions", "pullback",
}

_HIGH_IMPACT_WORDS = {
    "tariff", "interest rate", "rate cut", "rate hike", "apr", "fed", "federal reserve",
    "incentive", "incentives", "rebate", "financing", "recall", "strike", "gas price",
    "gasoline", "affordability", "auto loan", "policy", "ban", "crisis",
}

_MEDIUM_IMPACT_WORDS = {
    "concern", "uncertainty", "risk", "slowdown", "inflation", "economy",
    "demand", "inventory", "prices", "trade", "consumer", "confidence", "lease",
}

_CATEGORY_KEYWORDS = {
    "EV":         {"electric", "ev", "tesla", "charging", "battery", "hybrid", "zero-emission", "plug-in"},
    "Luxury":     {"luxury", "mercedes", "bmw", "porsche", "lexus", "premium", "audi", "cadillac"},
    "Pickup":     {"pickup", "truck", "f-150", "silverado", "ram 1500", "sierra", "full-size"},
    "SUV":        {"suv", "4x4", "crossover", "off-road", "jeep", "grand cherokee"},
    "Sedan":      {"sedan", "compact car", "hatchback", "camry", "civic", "corolla"},
    "Commercial": {"van", "commercial", "fleet", "cargo", "logistics"},
}

_HIGH_RISK_WORDS  = {"war", "conflict", "sanction", "crisis", "recession", "crash", "emergency", "attack"}
_MED_RISK_WORDS   = {"concern", "uncertainty", "volatility", "slowdown", "risk", "tension", "threat"}

# Headlines that are events, not demand signals — a fatal crash that mentions a
# "truck" is not a truck-demand story. Force these to a neutral, low-impact read
# rather than letting a stray positive/negative keyword set a direction.
_NON_SIGNAL_WORDS = {
    "dead", "killed", "fatal", "collision", "crash", "injured", "wreck",
    "arrested", "charged", "sentenced", "lawsuit", "stolen", "theft", "fire",
    "obituary", "died", "death",
}

# "the number went up" / "the number went down" — used only inside the
# theme-aware read below, where the direction of a price/rate/tariff move has a
# known effect on retail demand.
_RISE_WORDS = {
    "soar", "soared", "surge", "surged", "surging", "jump", "jumps", "jumped",
    "spike", "spiked", "spiking", "climb", "climbs", "climbing", "climbed",
    "rise", "rises", "rising", "rose", "higher", "elevated", "hike", "hikes",
    "hiked", "increase", "increased", "increases", "record", "up", "raise", "raised",
}
_FALL_WORDS = {
    "fall", "falls", "falling", "fell", "drop", "drops", "dropped", "plunge",
    "plunged", "tumble", "tumbled", "slide", "slid", "ease", "eased", "easing",
    "lower", "lowered", "cheaper", "decline", "declined", "declines", "relief",
    "cool", "cools", "cooled", "cooling", "down", "cut", "cuts", "slashed", "drops",
}


def _theme_directional_read(theme, tl: str, words: set):
    """
    For themes whose demand mechanism is well established (fuel price, financing
    cost, tariffs, incentives), read whether the headline is about that lever
    moving up or down and translate it to a demand direction + affected segment.
    Returns (direction, category) or None to fall back to the generic path.
    """
    rise, fall = bool(words & _RISE_WORDS), bool(words & _FALL_WORDS)
    if rise == fall:  # neither, or ambiguous (both) → no call
        return None

    if theme == "fuel_oil_prices" and any(k in tl for k in ("gas", "fuel", "oil", "pump", "gasoline", "diesel")):
        seg = "Pickup" if any(k in tl for k in ("truck", "pickup", "f-150", "silverado", "ram")) else "SUV"
        return ("down", seg) if rise else ("up", seg)   # dearer fuel = truck/SUV headwind

    if theme in ("auto_financing", "us_macro_economy") and any(k in tl for k in ("rate", "apr", "loan", "financ", "fed", "borrow", "mortgage")):
        return ("down", "All") if rise else ("up", "All")   # dearer credit = demand headwind

    if theme == "tariff_trade" and any(k in tl for k in ("tariff", "duty", "duties", "import", "232")):
        relief = fall or any(k in tl for k in ("refund", "exempt", "pause", "remove", "repeal", "roll back", "rollback", "relief"))
        return ("up", "All") if relief else ("down", "All")   # duty on = cost headwind on imports

    if theme == "incentives_rebates":
        expand = any(k in tl for k in ("expand", "boost", "return", "0%", "zero percent", "add")) or (rise and any(k in tl for k in ("incentive", "rebate", "deal")))
        cut = fall or any(k in tl for k in ("end", "reduce", "pull", "expire", "scale back"))
        if expand and not cut:
            return ("up", "All")
        if cut and not expand:
            return ("down", "All")
    return None


def _mock_signal_for_title(title: str, article_index: int, theme: Optional[str] = None) -> Dict:
    """
    Generate a plausible deterministic signal from article title keywords.
    Uses a title-seeded RNG so the same title always produces the same output.
    """
    words = set(title.lower().split())
    title_lower = title.lower()

    # Seed RNG from title hash for determinism
    seed = int(hashlib.md5(title.encode()).hexdigest(), 16) % (2 ** 32)
    rng = random.Random(seed)

    # An "event, not a signal" headline (fatal crash, lawsuit, theft) gets a
    # flat, low-impact read — the keyword scorer has no business calling a
    # direction on it.
    non_signal = bool(words & _NON_SIGNAL_WORDS)

    # Sentiment score: count positive vs negative keyword hits. Default is a
    # true 0 (neutral) — the keyword heuristic is unreliable on a bare
    # headline, so it should not lean unless the words clearly do.
    pos_hits = len(words & _POSITIVE_WORDS)
    neg_hits = len(words & _NEGATIVE_WORDS)
    total_hits = pos_hits + neg_hits
    if total_hits == 0 or non_signal:
        base_sentiment = 0.0
    else:
        base_sentiment = (pos_hits - neg_hits) / total_hits
    sentiment_score = round(max(-1.0, min(1.0, base_sentiment + rng.uniform(-0.05, 0.05))), 3)

    # Impact score
    if non_signal:
        impact_score = round(rng.uniform(0.05, 0.20), 3)
    elif words & _HIGH_IMPACT_WORDS or any(w in title_lower for w in _HIGH_IMPACT_WORDS):
        impact_score = round(rng.uniform(0.50, 0.85), 3)
    elif words & _MEDIUM_IMPACT_WORDS:
        impact_score = round(rng.uniform(0.25, 0.55), 3)
    else:
        impact_score = round(rng.uniform(0.08, 0.30), 3)

    # Affected vehicle category. Single-word keywords must match a whole token
    # (so "ev" doesn't fire on "elEVated"); multi-word keywords match as a phrase.
    affected_category = "All"
    for cat, kw_set in _CATEGORY_KEYWORDS.items():
        if (words & kw_set) or any(" " in k and k in title_lower for k in kw_set):
            affected_category = cat
            break

    # Economic risk
    if words & _HIGH_RISK_WORDS or any(w in title_lower for w in _HIGH_RISK_WORDS):
        economic_risk = "high"
    elif words & _MED_RISK_WORDS or any(w in title_lower for w in _MED_RISK_WORDS):
        economic_risk = "medium"
    else:
        economic_risk = "low"

    # Demand direction.
    #  1. Theme-aware read first: for fuel / financing / tariff / incentive
    #     headlines the demand mechanism is known, so the direction of the move
    #     (prices soar / rates cut / tariff refunded) maps straight to a demand
    #     direction. This is deterministic and grounded, not sentiment-guessing.
    #  2. Otherwise the generic keyword lean, which only fires on an unambiguous
    #     positive/negative word + real impact — most headlines stay "neutral".
    directional = None if non_signal else _theme_directional_read(theme, title_lower, words)
    if directional:
        demand_direction, forced_cat = directional
        if affected_category == "All" and forced_cat != "All":
            affected_category = forced_cat
        sentiment_score = round((0.45 if demand_direction == "up" else -0.45) + rng.uniform(-0.08, 0.08), 3)
        impact_score = max(impact_score, round(rng.uniform(0.45, 0.65), 3))
    elif not non_signal and sentiment_score >= 0.30 and impact_score >= 0.40:
        demand_direction = "up"
    elif not non_signal and sentiment_score <= -0.30 and impact_score >= 0.40:
        demand_direction = "down"
    else:
        demand_direction = "neutral"

    # Estimated demand change %. Zero unless a direction was called. Calibrated
    # so a single headline moves demand by at most a couple of points —
    # published US auto-retail elasticities put a +1pt APR move at ~-3% units
    # and a +$1/gal gas move at ~-4% on truck/SUV mix, and those are sustained
    # shifts, not one news item. (Fed FEDS Notes 2024; Resources for the Future
    # WP 23-33 / Brandeis WP94 — see the sentiment-analysis changelog.)
    if demand_direction == "neutral":
        estimated_demand_change_pct = 0.0
    else:
        change_magnitude = impact_score * abs(sentiment_score) * rng.uniform(1.5, 3.5)
        change_magnitude = min(change_magnitude, 5.0)
        estimated_demand_change_pct = round(
            change_magnitude if demand_direction == "up" else -change_magnitude, 2
        )

    # Confidence — the mock is a keyword heuristic, so it never claims high
    # certainty; the UI badges the view as "demo model" regardless.
    confidence = round(rng.uniform(0.45, 0.68), 3)

    return {
        "article_index":            article_index,
        "sentiment_score":          sentiment_score,
        "impact_score":             impact_score,
        "affected_vehicle_category": affected_category,
        "economic_risk":            economic_risk,
        "demand_direction":         demand_direction,
        "estimated_demand_change_pct": estimated_demand_change_pct,
        "confidence":               confidence,
        "summary":                  _mock_summary(demand_direction, affected_category, estimated_demand_change_pct),
        "_mock": True,
    }


_SEGMENT_PHRASE = {
    "EV": "EV demand", "Luxury": "luxury demand", "Pickup": "pickup demand",
    "SUV": "SUV demand", "Sedan": "sedan demand", "Commercial": "commercial demand",
    "All": "showroom traffic across segments",
}


def _mock_summary(direction: str, category: str, change_pct: float) -> str:
    """One plain dealer-facing sentence — no model internals on the card."""
    seg = _SEGMENT_PHRASE.get(category, "showroom demand")
    if direction != "neutral" and abs(change_pct) < 0.5:
        return f"Some read on {seg}, but too small to act on — monitor."
    if direction == "up":
        return f"Supports {seg} (~{change_pct:+.1f}%) — hold stock and protect margin on that segment."
    if direction == "down":
        return f"Headwind for {seg} (~{change_pct:+.1f}%) — watch days'-supply and be ready to lean on incentives or trade allowance."
    return f"No clear demand read for {seg} — monitor, no action yet."


def _analyze_mock(articles: List[Dict]) -> List[Dict]:
    """Generate mock signals for all articles (no API call)."""
    return [
        _mock_signal_for_title(art.get("title", ""), i, art.get("theme") or art.get("_theme"))
        for i, art in enumerate(articles)
    ]


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

_BRIEFING_SYSTEM_PROMPT = """You advise the leadership of a US automobile dealer group (24 rooftops, ~56% import franchises, segment mix SUV 49% / Pickup 23% / Sedan 16% / Luxury 9%).
Write a short weekly read for the group's GMs and the F&I / used-car desks, using only the signal data provided.
Talk about the group's own showroom demand, stocking, pricing, incentives and financing — not "the market".
Structure your response with exactly three clearly labeled sections:

WHAT'S MOVING DEMAND
[2–3 sentences: the net direction over the next ~30 days and the one or two drivers behind it]

WHERE THE GROUP IS EXPOSED
[4–6 bullet points: which segments / rooftops the current signals help or hurt, and by roughly how much]

WHAT TO DO THIS WEEK
[3 specific, numbered actions — stocking, pricing, incentive timing, or a financing talk-track]

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

    net_signal = stats.get("net_demand_signal_pct", demand_change)

    if is_live_mode():
        # ── Live: call Grok ──────────────────────────────────────────────
        user_msg = (
            f"Dealer-group demand signal data (news, last 30 days):\n"
            f"- Net demand signal, next ~30 days: {net_signal:+.1f}% (sales-mix weighted)\n"
            f"- Average sentiment score: {avg_sentiment:+.3f} (scale: -1 to +1)\n"
            f"- Dominant demand direction: {direction}\n"
            f"- Demand-pressure score: {geo_risk:.3f} (0 = calm, 1 = heavy)\n"
            f"- Average news impact score: {avg_impact:.3f}\n"
            f"- Headlines analysed: {total_articles} ({positive_pct:.0f}% supportive, {negative_pct:.0f}% headwind)\n"
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
    net_word = (
        "a tailwind" if net_signal > 0.75
        else ("a headwind" if net_signal < -0.75 else "roughly flat")
    )
    trend_word = "improving" if trend_7d > 0.05 else ("softening" if trend_7d < -0.05 else "steady")
    pressure_word = "heavy" if geo_risk > 0.35 else ("some" if geo_risk > 0.18 else "light")

    # Rank segments by their own demand-change signal
    seg_up, seg_down = [], []
    if category_rows:
        for row in sorted(category_rows, key=lambda x: x.get("avg_demand_change") or 0, reverse=True):
            chg = row.get("avg_demand_change") or 0.0
            cat = row.get("category", "All")
            if chg >= 0.3:
                seg_up.append((cat, chg))
            elif chg <= -0.3:
                seg_down.append((cat, chg))
    top_up = seg_up[0][0] if seg_up else "SUV"
    top_down = seg_down[0][0] if seg_down else None

    exposure_lines = []
    for cat, chg in (seg_up[:2] + seg_down[:2]):
        exposure_lines.append(f"- {cat}: news is running {chg:+.1f}% — {'stock and hold margin' if chg > 0 else 'watch days-supply, be ready with incentives'}.")
    if not exposure_lines:
        exposure_lines = ["- No segment is showing a clear news-driven move this period — nothing to act on yet."]

    action_2 = (
        f"Pull forward incentive spend on {top_down} — the news is against that segment and moving the metal matters more than holding gross right now."
        if top_down else
        f"Hold incentive spend where it is; no segment needs a defensive push this week."
    )

    briefing = f"""WHAT'S MOVING DEMAND
Over the next ~30 days the group's news signal is {net_word} ({net_signal:+.1f}%, sales-mix weighted) across {total_articles} headlines, {trend_word} week-over-week. {positive_pct:.0f}% of coverage is supportive, {negative_pct:.0f}% is a headwind, and demand pressure from cost/financing news is {pressure_word}. Dominant read across segments: {direction.upper()}.

WHERE THE GROUP IS EXPOSED
{chr(10).join(exposure_lines)}
- Import franchises carry ~56% of the group's units, so tariff and exchange-rate headlines hit cost and price on more than half the book.
- Financing news moves faster than anything else — a rate change shows up in showroom traffic within a few weeks.

WHAT TO DO THIS WEEK
1. Keep {top_up} stock full at the higher-volume rooftops; that is where the supportive signal is concentrated.
2. {action_2}
3. Brief the desk on the current financing talk-track: lead with monthly payment and trade equity, not sticker discount, while rate news is the dominant driver.
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
