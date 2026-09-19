"""News, per-article signals and daily sentiment aggregates (tenant-scoped, one news edition each)."""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.db.connection import Base
from backend.db.models.base import tenant_col


class NewsArticle(Base):
    """Raw articles fetched from Google News RSS, in the tenant's news edition."""
    __tablename__ = "news_articles"
    __table_args__ = (UniqueConstraint("tenant_id", "url", name="uq_news_tenant_url"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = tenant_col()
    url = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    source_domain = Column(Text, nullable=True)
    source_country = Column(Text, nullable=True)
    published_date = Column(Date, nullable=True)
    fetched_at = Column(DateTime, nullable=False)
    search_query = Column(Text, nullable=True)
    language = Column(Text, nullable=True)
    social_image_url = Column(Text, nullable=True)

    # Relationship to AI-extracted signal (one article → one signal)
    sentiment_signal = relationship("SentimentSignal", back_populates="article", uselist=False)


class SentimentSignal(Base):
    """Forecasting signals extracted for each news article."""
    __tablename__ = "sentiment_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = tenant_col()
    article_id = Column(Integer, ForeignKey("news_articles.id"), nullable=False, unique=True)
    analyzed_at = Column(DateTime, nullable=False)

    sentiment_score = Column(Float, nullable=True)             # -1.0 (very negative) to +1.0 (very positive)
    impact_score = Column(Float, nullable=True)                # 0.0 (no impact) to 1.0 (high impact)
    affected_vehicle_category = Column(Text, nullable=True)    # SUV, EV, Luxury, All, etc.
    economic_risk = Column(Text, nullable=True)                # low | medium | high
    demand_direction = Column(Text, nullable=True)             # up | down | neutral
    estimated_demand_change_pct = Column(Float, nullable=True) # e.g. +3.5 or -2.1
    confidence = Column(Float, nullable=True)                  # 0.0 to 1.0
    summary = Column(Text, nullable=True)                      # one-sentence summary (English)
    summary_de = Column(Text, nullable=True)                   # German rendering for the DE toggle
    raw_response = Column(Text, nullable=True)                 # full model JSON (for debugging)

    article = relationship("NewsArticle", back_populates="sentiment_signal")


class DailySentimentSummary(Base):
    """
    Daily aggregated sentiment scores per vehicle category, used as external
    regressors in Prophet forecasting. One row per (summary_date, vehicle_category);
    NULL vehicle_category = aggregate across all categories.
    """
    __tablename__ = "daily_sentiment_summary"
    __table_args__ = (
        UniqueConstraint("tenant_id", "summary_date", "vehicle_category", name="uq_daily_sentiment"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = tenant_col()
    summary_date = Column(Date, nullable=False, index=True)
    vehicle_category = Column(Text, nullable=True)

    avg_sentiment_score = Column(Float, nullable=True)
    avg_impact_score = Column(Float, nullable=True)
    avg_demand_change_pct = Column(Float, nullable=True)
    geopolitical_risk_score = Column(Float, nullable=True)     # derived: avg_impact * negative_ratio

    positive_signals = Column(Integer, nullable=True)
    negative_signals = Column(Integer, nullable=True)
    neutral_signals = Column(Integer, nullable=True)
    total_articles = Column(Integer, nullable=True)
    dominant_demand_direction = Column(Text, nullable=True)    # up | down | neutral

    computed_at = Column(DateTime, nullable=False)
