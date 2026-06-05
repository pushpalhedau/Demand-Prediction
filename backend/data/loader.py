"""
Master data loader — reads all UAE Real Estate Data Lake CSVs into pandas DataFrames.
All data is loaded once at startup and kept in memory.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional
import pandas as pd
import numpy as np

from backend.core.config import settings

log = logging.getLogger(__name__)


class DataLoader:
    """Loads every relevant dataset and exposes them as clean DataFrames."""

    def __init__(self):
        self._data: Dict[str, pd.DataFrame] = {}
        self._loaded = False

    # ── Public API ─────────────────────────────────────────────────────

    def load_all(self) -> None:
        if self._loaded:
            return
        log.info("Loading UAE Real Estate Data Lake …")
        self._data["transactions"]        = self._transactions()
        self._data["rentals"]             = self._rentals()
        self._data["projects"]            = self._projects()
        self._data["buildings"]           = self._buildings()
        self._data["units"]               = self._units()
        self._data["areas"]               = self._areas()
        self._data["gdp"]                 = self._gdp()
        self._data["population"]          = self._population()
        self._data["interest_rates"]      = self._interest_rates()
        self._data["cpi"]                 = self._cpi()
        self._data["employment"]          = self._employment()
        self._data["tourism"]             = self._tourism()
        self._data["oil_prices"]          = self._oil_prices()
        self._data["gold_prices"]         = self._gold_prices()
        self._data["fdi"]                 = self._fdi()
        self._data["infrastructure"]      = self._infrastructure()
        self._data["listings"]            = self._listings()
        self._data["developer_share"]     = self._developer_share()
        self._data["price_index"]         = self._price_index()
        self._data["sentiment_index"]     = self._sentiment_index()
        self._data["gdelt_sentiment"]     = self._gdelt_sentiment()
        self._loaded = True
        log.info("All datasets loaded. Keys: %s", list(self._data.keys()))

    def get(self, name: str) -> pd.DataFrame:
        """Always returns a DataFrame — empty if the key is not loaded."""
        result = self._data.get(name)
        return result if result is not None else pd.DataFrame()

    def all(self) -> Dict[str, pd.DataFrame]:
        return self._data

    # ── Real Estate ────────────────────────────────────────────────────

    def _transactions(self) -> pd.DataFrame:
        df = pd.read_csv(settings.real_estate_dir / "dld_transactions_2019_2024.csv", low_memory=False)
        df["transaction_date"] = pd.to_datetime(df["transaction_date"])
        df["year"]  = df["transaction_date"].dt.year
        df["month"] = df["transaction_date"].dt.month
        df["quarter"] = df["transaction_date"].dt.quarter
        df["transaction_value_aed"] = pd.to_numeric(df["transaction_value_aed"], errors="coerce")
        df["price_per_sqft_aed"]    = pd.to_numeric(df["price_per_sqft_aed"],    errors="coerce")
        df["area_sqft"]             = pd.to_numeric(df["area_sqft"],             errors="coerce")
        df["is_off_plan"] = df["is_off_plan"].astype(bool)
        return df

    def _rentals(self) -> pd.DataFrame:
        df = pd.read_csv(settings.real_estate_dir / "dld_rental_contracts_2019_2024.csv", low_memory=False)
        df["contract_date"] = pd.to_datetime(df["contract_date"])
        df["annual_rent_aed"]   = pd.to_numeric(df["annual_rent_aed"],   errors="coerce")
        df["monthly_rent_aed"]  = pd.to_numeric(df["monthly_rent_aed"],  errors="coerce")
        return df

    def _projects(self) -> pd.DataFrame:
        df = pd.read_csv(settings.real_estate_dir / "dld_projects_data.csv", low_memory=False)
        df["avg_price_per_sqft_aed"] = pd.to_numeric(df["avg_price_per_sqft_aed"], errors="coerce")
        df["sold_percentage"]        = pd.to_numeric(df["sold_percentage"],        errors="coerce")
        return df

    def _buildings(self) -> pd.DataFrame:
        return pd.read_csv(settings.real_estate_dir / "dld_buildings_data.csv", low_memory=False)

    def _units(self) -> pd.DataFrame:
        df = pd.read_csv(settings.real_estate_dir / "dld_units_data.csv", low_memory=False)
        df["last_sale_price_aed"] = pd.to_numeric(df["last_sale_price_aed"], errors="coerce")
        return df

    def _areas(self) -> pd.DataFrame:
        df = pd.read_csv(settings.real_estate_dir / "dld_areas_lookup.csv", low_memory=False)
        df["avg_price_per_sqft_2024"] = pd.to_numeric(df["avg_price_per_sqft_2024"], errors="coerce")
        return df

    # ── Macroeconomic ──────────────────────────────────────────────────

    def _gdp(self) -> pd.DataFrame:
        df = pd.read_csv(settings.macro_dir / "uae_gdp_annual.csv", low_memory=False)
        for col in ["gdp_usd_billion", "gdp_growth_rate_pct", "per_capita_gdp_usd"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _population(self) -> pd.DataFrame:
        df = pd.read_csv(settings.macro_dir / "uae_population_demographics.csv", low_memory=False)
        for col in ["total_population", "dubai_population", "annual_growth_rate_pct"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _interest_rates(self) -> pd.DataFrame:
        df = pd.read_csv(settings.macro_dir / "uae_interest_mortgage_rates.csv", low_memory=False)
        df["date"] = pd.to_datetime(df["date"])
        for col in ["uae_base_rate_pct", "avg_mortgage_rate_pct", "eibor_3m_pct"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _cpi(self) -> pd.DataFrame:
        df = pd.read_csv(settings.macro_dir / "uae_cpi_inflation_monthly.csv", low_memory=False)
        df["date"] = pd.to_datetime(df["date"])
        for col in ["overall_cpi", "housing_cpi", "yoy_inflation_pct"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _employment(self) -> pd.DataFrame:
        try:
            return pd.read_csv(settings.macro_dir / "uae_employment_statistics.csv", low_memory=False)
        except Exception:
            return pd.DataFrame()

    def _tourism(self) -> pd.DataFrame:
        try:
            return pd.read_csv(settings.macro_dir / "uae_tourism_statistics.csv", low_memory=False)
        except Exception:
            return pd.DataFrame()

    def _oil_prices(self) -> pd.DataFrame:
        df = pd.read_csv(settings.macro_dir / "oil_prices_brent.csv", low_memory=False)
        return df

    def _gold_prices(self) -> pd.DataFrame:
        df = pd.read_csv(settings.macro_dir / "gold_prices.csv", low_memory=False)
        return df

    def _fdi(self) -> pd.DataFrame:
        try:
            return pd.read_csv(settings.macro_dir / "uae_fdi_statistics.csv", low_memory=False)
        except Exception:
            return pd.DataFrame()

    # ── Infrastructure ─────────────────────────────────────────────────

    def _infrastructure(self) -> pd.DataFrame:
        df = pd.read_csv(settings.infra_dir / "uae_infrastructure_projects.csv", low_memory=False)
        df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        df["budget_aed_million"] = pd.to_numeric(df["budget_aed_million"], errors="coerce")
        return df

    # ── Competitive Intelligence ───────────────────────────────────────

    def _listings(self) -> pd.DataFrame:
        df = pd.read_csv(settings.competitive_dir / "property_listings_2024.csv", low_memory=False)
        df["listing_date"]  = pd.to_datetime(df["listing_date"])
        df["price_aed"]     = pd.to_numeric(df["price_aed"],     errors="coerce")
        df["price_per_sqft"] = pd.to_numeric(df["price_per_sqft"], errors="coerce")
        df["days_on_market"] = pd.to_numeric(df["days_on_market"], errors="coerce")
        return df

    def _developer_share(self) -> pd.DataFrame:
        df = pd.read_csv(settings.competitive_dir / "developer_market_share.csv", low_memory=False)
        for col in ["market_share_pct", "units_launched", "units_sold", "avg_price_per_sqft"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _price_index(self) -> pd.DataFrame:
        df = pd.read_csv(settings.competitive_dir / "dubai_price_index_by_area_quarter.csv", low_memory=False)
        for col in ["avg_sale_price_per_sqft_aed", "price_yoy_change_pct", "rental_yield_pct", "avg_days_to_sell"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    # ── News / Sentiment ───────────────────────────────────────────────

    def _sentiment_index(self) -> pd.DataFrame:
        df = pd.read_csv(settings.news_dir / "uae_realestate_sentiment_index.csv", low_memory=False)
        df["date"] = pd.to_datetime(df["date"])
        for col in ["real_estate_sentiment_index", "buyer_confidence_index", "seller_confidence_index",
                    "media_sentiment_score", "search_volume_index"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _gdelt_sentiment(self) -> pd.DataFrame:
        df = pd.read_csv(settings.news_dir / "gdelt_monthly_sentiment_aggregated.csv", low_memory=False)
        for col in ["event_count", "avg_tone", "positive_pct", "negative_pct"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df


# Singleton
data_store = DataLoader()
