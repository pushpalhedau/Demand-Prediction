import os
import sys
import pandas as pd
import numpy as np
from datetime import timedelta, date
from prophet import Prophet
from sklearn.metrics import mean_squared_error, mean_absolute_error

# Add the project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import get_db_session
from database.models import Sale, ExternalFactor, Registration, IndiaExternalFactor

def train_prophet_model(
    category: str = None,
    region: str = None,
    fuel_type: str = None,
    target: str = "units_sold",
    horizon_days: int = 90,
    interval_width: float = 0.95,
    use_sentiment: bool = False,
):
    """
    Train a Prophet model using aggregated sales data and external factors as regressors.
    Generates dynamic forecasts for 30/60/90/180/365 days.

    Args:
        use_sentiment: When True, merges avg_sentiment_score and geopolitical_risk_score
                       from DailySentimentSummary as additional Prophet regressors.
                       Falls back gracefully if no sentiment data is available.
    """
    session = get_db_session()
    try:
        # 1. Fetch sales transactions and aggregate daily
        sale_query = session.query(
            Sale.sale_date,
            Sale.units_sold,
            Sale.total_revenue_incl_vat
        )
        if category:
            sale_query = sale_query.filter(Sale.vehicle_category == category)
        if region:
            sale_query = sale_query.filter(Sale.emirate == region)
        if fuel_type:
            sale_query = sale_query.filter(Sale.fuel_type == fuel_type)
            
        sales_df = pd.read_sql(sale_query.statement, session.bind)
        if sales_df.empty:
            return None, "No data available for the selected filters."
            
        # Parse date and group daily
        sales_df['sale_date'] = pd.to_datetime(sales_df['sale_date'])
        if target == "units_sold":
            daily_series = sales_df.groupby('sale_date')['units_sold'].sum().reset_index()
            daily_series.columns = ['ds', 'y']
        else:
            daily_series = sales_df.groupby('sale_date')['total_revenue_incl_vat'].sum().reset_index()
            daily_series.columns = ['ds', 'y']
            
        # Complete missing dates with zero sales/revenue
        min_date = daily_series['ds'].min()
        max_date = daily_series['ds'].max()
        all_dates = pd.date_range(start=min_date, end=max_date, freq='D')
        daily_series = daily_series.set_index('ds').reindex(all_dates, fill_value=0).reset_index()
        daily_series.columns = ['ds', 'y']
        
        # 2. Fetch external factors
        ext_query = session.query(
            ExternalFactor.date,
            ExternalFactor.petrol_95_price_aed_per_litre,
            ExternalFactor.diesel_price_aed_per_litre,
            ExternalFactor.gdp_growth_pct,
            ExternalFactor.cpi_inflation_pct,
            ExternalFactor.consumer_confidence_index,
            ExternalFactor.ramadan_month
        )
        if region:
            ext_query = ext_query.filter(ExternalFactor.emirate == region)
            
        ext_df = pd.read_sql(ext_query.statement, session.bind)
        if not ext_df.empty:
            ext_df['date'] = pd.to_datetime(ext_df['date'])
            
            # Group by date and take mean of numerical factors if multiple regions are present (global view)
            if not region:
                # Grouping by date ensures unique date index for resampling
                ext_df = ext_df.groupby('date').mean(numeric_only=True).reset_index()
                
            # We want to resample/upsample monthly external factors to daily
            ext_df = ext_df.set_index('date').resample('D').ffill().reset_index()
            ext_df.rename(columns={'date': 'ds'}, inplace=True)
            
            # Merge with sales daily series
            data = pd.merge(daily_series, ext_df, on='ds', how='left')
            # Fill remaining NaNs with forward/backward fills
            data = data.ffill().bfill()
        else:
            data = daily_series
            
        # 2a. Optionally merge sentiment regressors from DailySentimentSummary
        sentiment_regressor_candidates = []
        sent_df_for_future = None

        if use_sentiment:
            try:
                from sentiment.signal_processor import get_daily_summaries
                sent_df = get_daily_summaries(days_back=3650, vehicle_category=None)
                if not sent_df.empty:
                    sent_cols = ["avg_sentiment_score", "geopolitical_risk_score"]
                    sent_df = sent_df[["summary_date"] + sent_cols].copy()
                    sent_df.rename(columns={"summary_date": "ds"}, inplace=True)
                    sent_df["ds"] = pd.to_datetime(sent_df["ds"])
                    # Merge into daily data
                    data = pd.merge(data, sent_df, on="ds", how="left")
                    # Forward-fill / backward-fill gaps; fill remaining with 0
                    for col in sent_cols:
                        data[col] = data[col].ffill().bfill().fillna(0.0)
                    sentiment_regressor_candidates = sent_cols
                    sent_df_for_future = sent_df  # saved for future-dataframe merge below
            except Exception:
                pass  # sentiment module not yet available — skip silently

        # Ensure we have enough data to train (at least 30 historical days)
        if len(data) < 30:
            return None, "Insufficient historical data (minimum 30 days) to train the forecasting model."

        # 3. Model setup
        model = Prophet(
            yearly_seasonality=True, 
            weekly_seasonality=True, 
            daily_seasonality=False,
            interval_width=interval_width
        )
        
        # Add external regressors if they exist in dataframe
        regressors = [
            'petrol_95_price_aed_per_litre',
            'diesel_price_aed_per_litre',
            'gdp_growth_pct',
            'cpi_inflation_pct',
            'consumer_confidence_index',
            'ramadan_month',
        ] + sentiment_regressor_candidates  # appended when use_sentiment=True

        active_regressors = []
        for reg in regressors:
            if reg in data.columns and data[reg].nunique() > 1:
                model.add_regressor(reg)
                active_regressors.append(reg)
                
        # Split into train / test for validation (use last 30 days for testing)
        train_size = len(data) - 30
        train_data = data.iloc[:train_size]
        test_data = data.iloc[train_size:]
        
        # Fit the model
        model.fit(train_data)
        
        # Evaluate on test set
        forecast_test = model.predict(test_data)
        y_true = test_data['y'].values
        y_pred = forecast_test['yhat'].values
        # Prophet can predict negative values in low-sales scenarios, floor to 0
        y_pred = np.clip(y_pred, 0, None)
        
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        mae = mean_absolute_error(y_true, y_pred)
        
        # Calculate baseline accuracy
        mean_y = np.mean(y_true)
        accuracy = 1.0 - (mae / mean_y) if mean_y > 0 else 0.0
        accuracy = max(0.0, min(1.0, accuracy)) * 100 # percentage
        
        metrics = {
            "rmse": rmse,
            "mae": mae,
            "accuracy": accuracy,
            "historical_mean": mean_y
        }
        
        # Retrain model on full dataset for future forecast
        full_model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=interval_width
        )
        for reg in active_regressors:
            full_model.add_regressor(reg)
        full_model.fit(data)

        # Create future dataframe
        future = full_model.make_future_dataframe(periods=horizon_days)

        # Populate macro-economic regressors for future dates
        econ_active = [r for r in active_regressors if r not in sentiment_regressor_candidates]
        if econ_active and not ext_df.empty:
            future = pd.merge(future, ext_df[['ds'] + econ_active], on='ds', how='left')
            future = future.ffill().bfill()

        # Populate sentiment regressors for future dates (forward-fill last known value)
        sent_active = [r for r in active_regressors if r in sentiment_regressor_candidates]
        if sent_active and sent_df_for_future is not None:
            future = pd.merge(
                future,
                sent_df_for_future[['ds'] + sent_active],
                on='ds', how='left',
            )
            for col in sent_active:
                future[col] = future[col].ffill().bfill().fillna(0.0)
            
        forecast = full_model.predict(future)
        
        # Clip negative predictions to 0
        for col in ['yhat', 'yhat_lower', 'yhat_upper']:
            forecast[col] = np.clip(forecast[col], 0, None)
            
        # Merge actuals back
        forecast = pd.merge(forecast, data[['ds', 'y']], on='ds', how='left')
        forecast.rename(columns={'y': 'actual'}, inplace=True)
        
        return {
            "forecast": forecast,
            "metrics": metrics,
            "active_regressors": active_regressors,
            "sentiment_regressors": [r for r in active_regressors if r in sentiment_regressor_candidates],
            "historical_data": data,
        }, None
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"Forecasting pipeline error: {str(e)}"
    finally:
        session.close()


def train_india_prophet_model(
    state: str = None,
    maker: str = None,
    fuel_type: str = None,
    vehicle_class: str = None,
    target: str = "registrations_count",
    horizon_days: int = 90,
    interval_width: float = 0.95,
    use_sentiment: bool = False,
):
    """
    Train a Prophet model using VAHAN registration data and Indian macro regressors.
    Mirrors train_prophet_model() but queries Registration + IndiaExternalFactor tables.
    """
    session = get_db_session()
    try:
        # 1. Fetch and aggregate daily registration counts
        reg_query = session.query(
            Registration.reg_date,
            Registration.registrations_count,
        )
        if state:
            reg_query = reg_query.filter(Registration.state == state)
        if maker:
            reg_query = reg_query.filter(Registration.maker == maker)
        if fuel_type:
            reg_query = reg_query.filter(Registration.fuel_type == fuel_type)
        if vehicle_class:
            reg_query = reg_query.filter(Registration.vehicle_class == vehicle_class)

        reg_df = pd.read_sql(reg_query.statement, session.bind)
        if reg_df.empty:
            return None, "No India registration data for the selected filters. Run vahan_extractor.py first."

        reg_df['reg_date'] = pd.to_datetime(reg_df['reg_date'])
        daily = reg_df.groupby('reg_date')['registrations_count'].sum().reset_index()
        daily.columns = ['ds', 'y']

        # Fill missing dates with zero
        all_dates = pd.date_range(start=daily['ds'].min(), end=daily['ds'].max(), freq='D')
        daily = daily.set_index('ds').reindex(all_dates, fill_value=0).reset_index()
        daily.columns = ['ds', 'y']

        # 2. Fetch India external factors
        ext_query = session.query(
            IndiaExternalFactor.date,
            IndiaExternalFactor.petrol_price_inr,
            IndiaExternalFactor.diesel_price_inr,
            IndiaExternalFactor.rbi_repo_rate_pct,
            IndiaExternalFactor.india_gdp_growth_pct,
            IndiaExternalFactor.india_cpi_pct,
            IndiaExternalFactor.consumer_confidence_index,
            IndiaExternalFactor.diwali_month,
            IndiaExternalFactor.financial_year_end,
            IndiaExternalFactor.bs6_norms_active,
            IndiaExternalFactor.ev_subsidy_active,
        )
        if state:
            ext_query = ext_query.filter(IndiaExternalFactor.state == state)

        ext_df = pd.read_sql(ext_query.statement, session.bind)
        if not ext_df.empty:
            ext_df['date'] = pd.to_datetime(ext_df['date'])
            if not state:
                ext_df = ext_df.groupby('date').mean(numeric_only=True).reset_index()
            ext_df = ext_df.set_index('date').resample('D').ffill().reset_index()
            ext_df.rename(columns={'date': 'ds'}, inplace=True)
            data = pd.merge(daily, ext_df, on='ds', how='left').ffill().bfill()
        else:
            data = daily

        # 2a. Optionally merge sentiment regressors
        sentiment_regressor_candidates = []
        sent_df_for_future = None
        if use_sentiment:
            try:
                from sentiment.signal_processor import get_daily_summaries
                sent_df = get_daily_summaries(days_back=3650, vehicle_category=None)
                if not sent_df.empty:
                    sent_cols = ["avg_sentiment_score", "geopolitical_risk_score"]
                    sent_df = sent_df[["summary_date"] + sent_cols].copy()
                    sent_df.rename(columns={"summary_date": "ds"}, inplace=True)
                    sent_df["ds"] = pd.to_datetime(sent_df["ds"])
                    data = pd.merge(data, sent_df, on="ds", how="left")
                    for col in sent_cols:
                        data[col] = data[col].ffill().bfill().fillna(0.0)
                    sentiment_regressor_candidates = sent_cols
                    sent_df_for_future = sent_df
            except Exception:
                pass

        if len(data) < 30:
            return None, "Insufficient data (minimum 30 days) to train model."

        # 3. Build and train Prophet model
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=interval_width,
        )

        india_regressors = [
            'petrol_price_inr', 'diesel_price_inr',
            'rbi_repo_rate_pct', 'india_gdp_growth_pct', 'india_cpi_pct',
            'consumer_confidence_index', 'diwali_month',
            'financial_year_end', 'bs6_norms_active', 'ev_subsidy_active',
        ] + sentiment_regressor_candidates

        active_regressors = []
        for reg in india_regressors:
            if reg in data.columns and data[reg].nunique() > 1:
                model.add_regressor(reg)
                active_regressors.append(reg)

        # Train/test split (last 30 days = test)
        train_size = len(data) - 30
        train_data = data.iloc[:train_size]
        test_data = data.iloc[train_size:]

        model.fit(train_data)

        forecast_test = model.predict(test_data)
        y_true = test_data['y'].values
        y_pred = np.clip(forecast_test['yhat'].values, 0, None)

        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        mae = mean_absolute_error(y_true, y_pred)
        mean_y = np.mean(y_true)
        accuracy = max(0.0, min(1.0, 1.0 - (mae / mean_y) if mean_y > 0 else 0.0)) * 100

        metrics = {"rmse": rmse, "mae": mae, "accuracy": accuracy, "historical_mean": mean_y}

        # Retrain on full data
        full_model = Prophet(
            yearly_seasonality=True, weekly_seasonality=True,
            daily_seasonality=False, interval_width=interval_width,
        )
        for reg in active_regressors:
            full_model.add_regressor(reg)
        full_model.fit(data)

        future = full_model.make_future_dataframe(periods=horizon_days)

        econ_active = [r for r in active_regressors if r not in sentiment_regressor_candidates]
        if econ_active and not ext_df.empty:
            future = pd.merge(future, ext_df[['ds'] + econ_active], on='ds', how='left')
            future = future.ffill().bfill()

        sent_active = [r for r in active_regressors if r in sentiment_regressor_candidates]
        if sent_active and sent_df_for_future is not None:
            future = pd.merge(future, sent_df_for_future[['ds'] + sent_active], on='ds', how='left')
            for col in sent_active:
                future[col] = future[col].ffill().bfill().fillna(0.0)

        forecast = full_model.predict(future)
        for col in ['yhat', 'yhat_lower', 'yhat_upper']:
            forecast[col] = np.clip(forecast[col], 0, None)

        forecast = pd.merge(forecast, data[['ds', 'y']], on='ds', how='left')
        forecast.rename(columns={'y': 'actual'}, inplace=True)

        return {
            "forecast": forecast,
            "metrics": metrics,
            "active_regressors": active_regressors,
            "sentiment_regressors": [r for r in active_regressors if r in sentiment_regressor_candidates],
            "historical_data": data,
        }, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"India forecasting pipeline error: {str(e)}"
    finally:
        session.close()
