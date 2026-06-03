import os
import sys
import pandas as pd
import numpy as np
from prophet import Prophet
from sklearn.metrics import mean_squared_error, mean_absolute_error

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import get_db_session
from database.models import Transaction, MarketFactor


def get_market_factor_stats(city: str = None) -> dict:
    """Return last/min/max for each market factor column — used by simulator UI."""
    session = get_db_session()
    try:
        query = session.query(MarketFactor)
        if city:
            query = query.filter(MarketFactor.city == city)
        df = pd.read_sql(query.statement, session.bind)
        if df.empty:
            return {}

        numeric_cols = [
            "uae_central_bank_base_rate_pct", "mortgage_rate_avg_pct", "gdp_growth_pct",
            "cpi_inflation_pct", "consumer_confidence_index", "real_estate_price_index",
            "tourism_arrivals_index", "foreign_investment_inflow_bn_aed",
            "institutional_investment_bn_aed", "property_registration_fee_pct",
            "usd_aed_rate", "rental_yield_avg_pct", "construction_cost_index",
            "oil_price_usd_bbl", "off_plan_sales_share_pct",
        ]
        binary_cols = ["ramadan_month", "expo_effect"]

        stats = {}
        for col in numeric_cols + binary_cols:
            if col in df.columns:
                series = df[col].dropna()
                if len(series) > 0:
                    stats[col] = {
                        "last": float(series.iloc[-1]),
                        "min": float(series.min()),
                        "max": float(series.max()),
                        "is_binary": col in binary_cols,
                    }
        return stats
    finally:
        session.close()


def train_prophet_model(
    property_type: str = None,
    property_category: str = None,
    city: str = None,
    target: str = "units",        # "units" or "revenue"
    horizon_days: int = 90,
    interval_width: float = 0.95,
    market_overrides: dict = None,
):
    """
    Train Prophet on daily transaction aggregations with UAE real estate market regressors.

    Args:
        target: "units" = count of transactions per day; "revenue" = total_transaction_value_aed
        market_overrides: dict of {column_name: override_value} applied to forecast-period dates
    """
    session = get_db_session()
    try:
        # 1. Build daily transaction series
        txn_q = session.query(
            Transaction.transaction_date,
            Transaction.total_transaction_value_aed,
        )
        if property_type:
            txn_q = txn_q.filter(Transaction.property_type == property_type)
        if property_category:
            txn_q = txn_q.filter(Transaction.property_category == property_category)
        if city:
            txn_q = txn_q.filter(Transaction.city == city)

        txn_df = pd.read_sql(txn_q.statement, session.bind)
        if txn_df.empty:
            return None, "No transaction data for the selected filters."

        txn_df["transaction_date"] = pd.to_datetime(txn_df["transaction_date"])

        if target == "units":
            daily = txn_df.groupby("transaction_date").size().reset_index()
            daily.columns = ["ds", "y"]
        else:
            daily = txn_df.groupby("transaction_date")["total_transaction_value_aed"].sum().reset_index()
            daily.columns = ["ds", "y"]

        # Fill missing dates
        date_range = pd.date_range(daily["ds"].min(), daily["ds"].max(), freq="D")
        daily = daily.set_index("ds").reindex(date_range, fill_value=0).reset_index()
        daily.columns = ["ds", "y"]

        # 2. Fetch market factors and upsample monthly → daily
        mf_q = session.query(
            MarketFactor.date,
            MarketFactor.uae_central_bank_base_rate_pct,
            MarketFactor.mortgage_rate_avg_pct,
            MarketFactor.gdp_growth_pct,
            MarketFactor.cpi_inflation_pct,
            MarketFactor.consumer_confidence_index,
            MarketFactor.tourism_arrivals_index,
            MarketFactor.foreign_investment_inflow_bn_aed,
            MarketFactor.ramadan_month,
            MarketFactor.expo_effect,
            MarketFactor.golden_visa_applications,
            MarketFactor.new_project_launches,
            MarketFactor.property_registration_fee_pct,
            MarketFactor.oil_price_usd_bbl,
            MarketFactor.event_demand_multiplier,
        )
        if city:
            mf_q = mf_q.filter(MarketFactor.city == city)

        mf_df = pd.read_sql(mf_q.statement, session.bind)
        ext_df = None

        if not mf_df.empty:
            mf_df["date"] = pd.to_datetime(mf_df["date"])
            if not city:
                mf_df = mf_df.groupby("date").mean(numeric_only=True).reset_index()
            ext_df = mf_df.set_index("date").resample("D").ffill().reset_index()
            ext_df.rename(columns={"date": "ds"}, inplace=True)
            data = pd.merge(daily, ext_df, on="ds", how="left").ffill().bfill()
        else:
            data = daily

        if len(data) < 30:
            return None, "Insufficient historical data (minimum 30 days required)."

        # 3. Configure Prophet with UAE real estate regressors
        candidate_regressors = [
            "uae_central_bank_base_rate_pct", "mortgage_rate_avg_pct", "gdp_growth_pct",
            "cpi_inflation_pct", "consumer_confidence_index", "tourism_arrivals_index",
            "foreign_investment_inflow_bn_aed", "ramadan_month", "expo_effect",
            "golden_visa_applications", "new_project_launches",
            "property_registration_fee_pct", "oil_price_usd_bbl", "event_demand_multiplier",
        ]
        active_regressors = [
            r for r in candidate_regressors
            if r in data.columns and data[r].nunique() > 1
        ]

        # Train/test split: hold out last 30 days
        train_data = data.iloc[:-30]
        test_data = data.iloc[-30:]

        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=interval_width,
            changepoint_prior_scale=0.05,
        )
        for reg in active_regressors:
            model.add_regressor(reg)
        model.fit(train_data)

        forecast_test = model.predict(test_data)
        y_true = test_data["y"].values
        y_pred = np.clip(forecast_test["yhat"].values, 0, None)

        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        mae = float(mean_absolute_error(y_true, y_pred))
        mean_y = float(np.mean(y_true))
        accuracy = max(0.0, min(100.0, (1.0 - mae / mean_y) * 100)) if mean_y > 0 else 0.0

        # 4. Retrain on full data, forecast future
        full_model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=interval_width,
            changepoint_prior_scale=0.05,
        )
        for reg in active_regressors:
            full_model.add_regressor(reg)
        full_model.fit(data)

        future = full_model.make_future_dataframe(periods=horizon_days)

        if active_regressors and ext_df is not None:
            future = pd.merge(future, ext_df[["ds"] + active_regressors], on="ds", how="left")
            future = future.ffill().bfill()

            if market_overrides:
                last_hist = data["ds"].max()
                future_mask = future["ds"] > last_hist
                for col, val in market_overrides.items():
                    if col in future.columns:
                        future.loc[future_mask, col] = float(val)

        forecast = full_model.predict(future)
        for col in ["yhat", "yhat_lower", "yhat_upper"]:
            forecast[col] = np.clip(forecast[col], 0, None)

        forecast = pd.merge(forecast, data[["ds", "y"]], on="ds", how="left")
        forecast.rename(columns={"y": "actual"}, inplace=True)

        return {
            "forecast": forecast,
            "metrics": {
                "rmse": rmse,
                "mae": mae,
                "accuracy": accuracy,
                "historical_mean": mean_y,
            },
            "active_regressors": active_regressors,
            "historical_data": data,
        }, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"Forecasting error: {str(e)}"
    finally:
        session.close()
