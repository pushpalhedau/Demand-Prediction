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
from database.models import Sale, ExternalFactor

def train_prophet_model(
    category: str = None, 
    region: str = None, 
    fuel_type: str = None, 
    target: str = "units_sold", 
    horizon_days: int = 90
):
    """
    Train a Prophet model using aggregated sales data and monthly external factors as regressors.
    Generates dynamic forecasts for 30/60/90/180/365 days.
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
            
        # Ensure we have enough data to train (at least 30 historical days)
        if len(data) < 30:
            return None, "Insufficient historical data (minimum 30 days) to train the forecasting model."
            
        # 3. Model setup
        model = Prophet(
            yearly_seasonality=True, 
            weekly_seasonality=True, 
            daily_seasonality=False,
            interval_width=0.95  # 95% confidence intervals
        )
        
        # Add external regressors if they exist in dataframe
        regressors = [
            'petrol_95_price_aed_per_litre', 
            'diesel_price_aed_per_litre', 
            'gdp_growth_pct', 
            'cpi_inflation_pct', 
            'consumer_confidence_index', 
            'ramadan_month'
        ]
        
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
            interval_width=0.95
        )
        for reg in active_regressors:
            full_model.add_regressor(reg)
        full_model.fit(data)
        
        # Create future dataframe
        future = full_model.make_future_dataframe(periods=horizon_days)
        
        # Map/populate external regressors for future dates
        if active_regressors:
            # We merge the future dataframe with our upsampled external factors df
            future = pd.merge(future, ext_df[['ds'] + active_regressors], on='ds', how='left')
            # For the dates beyond our dataset, forward-fill the last available economic indicators
            future = future.ffill().bfill()
            
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
            "historical_data": data
        }, None
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"Forecasting pipeline error: {str(e)}"
    finally:
        session.close()
