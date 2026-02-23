"""
Demand Service - Demand forecasting and planning.

Handles:
- Demand forecasting (moving average, exponential smoothing)
- Demand history analysis
- Seasonality detection
- Forecast accuracy tracking
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging
import math

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Part, WorkOrder
from models.inventory import InventoryTransaction

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    """Result of demand forecast."""
    part_id: str
    period: str
    forecast_quantity: float
    confidence_low: float
    confidence_high: float
    method: str


class DemandService:
    """Demand forecasting service."""

    def __init__(self, session: Session):
        self.session = session

    def get_demand_history(
        self,
        part_id: str,
        periods: int = 12,
        period_type: str = 'month'
    ) -> List[Dict[str, Any]]:
        """
        Get historical demand for a part.

        Args:
            part_id: Part ID
            periods: Number of periods to retrieve
            period_type: 'day', 'week', or 'month'

        Returns:
            List of demand by period
        """
        now = datetime.utcnow()

        if period_type == 'day':
            delta = timedelta(days=1)
            date_format = '%Y-%m-%d'
        elif period_type == 'week':
            delta = timedelta(weeks=1)
            date_format = '%Y-W%W'
        else:  # month
            delta = timedelta(days=30)
            date_format = '%Y-%m'

        history = []
        for i in range(periods - 1, -1, -1):
            period_end = now - (delta * i)
            period_start = period_end - delta

            # Get demand from work orders completed in period
            demand = self.session.query(
                func.sum(WorkOrder.quantity_completed)
            ).filter(
                WorkOrder.part_id == part_id,
                WorkOrder.actual_end >= period_start,
                WorkOrder.actual_end < period_end
            ).scalar() or 0

            # Also check inventory issues
            issues = self.session.query(
                func.sum(InventoryTransaction.quantity)
            ).filter(
                InventoryTransaction.part_id == part_id,
                InventoryTransaction.transaction_type == 'issue',
                InventoryTransaction.created_at >= period_start,
                InventoryTransaction.created_at < period_end
            ).scalar() or 0

            total_demand = demand + issues

            history.append({
                'period': period_start.strftime(date_format),
                'start_date': period_start.isoformat(),
                'end_date': period_end.isoformat(),
                'demand': total_demand
            })

        return history

    def forecast_moving_average(
        self,
        part_id: str,
        periods_ahead: int = 3,
        window_size: int = 3
    ) -> List[ForecastResult]:
        """
        Simple Moving Average forecast.

        Args:
            part_id: Part ID
            periods_ahead: Number of periods to forecast
            window_size: Number of periods for moving average

        Returns:
            List of ForecastResults
        """
        history = self.get_demand_history(part_id, periods=window_size + 6)

        if len(history) < window_size:
            raise ValueError(f"Insufficient history: need {window_size} periods, have {len(history)}")

        # Get recent demands
        recent_demands = [h['demand'] for h in history[-window_size:]]
        avg = sum(recent_demands) / len(recent_demands)

        # Calculate standard deviation for confidence interval
        if len(recent_demands) > 1:
            variance = sum((x - avg) ** 2 for x in recent_demands) / len(recent_demands)
            std_dev = math.sqrt(variance)
        else:
            std_dev = avg * 0.2  # Default 20% variation

        forecasts = []
        for i in range(periods_ahead):
            # Confidence interval widens with forecast horizon
            confidence_factor = 1.96 * (1 + i * 0.1)

            forecasts.append(ForecastResult(
                part_id=part_id,
                period=f"P+{i + 1}",
                forecast_quantity=round(avg, 1),
                confidence_low=max(0, round(avg - confidence_factor * std_dev, 1)),
                confidence_high=round(avg + confidence_factor * std_dev, 1),
                method='moving_average'
            ))

        return forecasts

    def forecast_exponential_smoothing(
        self,
        part_id: str,
        periods_ahead: int = 3,
        alpha: float = 0.3
    ) -> List[ForecastResult]:
        """
        Exponential Smoothing forecast.

        Ft = α × At-1 + (1-α) × Ft-1

        Args:
            part_id: Part ID
            periods_ahead: Number of periods to forecast
            alpha: Smoothing factor (0-1, higher = more weight on recent)

        Returns:
            List of ForecastResults
        """
        history = self.get_demand_history(part_id, periods=12)

        if len(history) < 3:
            raise ValueError("Insufficient history for exponential smoothing")

        demands = [h['demand'] for h in history]

        # Initialize with first value
        forecast = demands[0]
        forecasts_history = [forecast]

        # Calculate smoothed values
        for actual in demands[1:]:
            forecast = alpha * actual + (1 - alpha) * forecast
            forecasts_history.append(forecast)

        # Calculate forecast error for confidence interval
        errors = [abs(a - f) for a, f in zip(demands[1:], forecasts_history[:-1])]
        mae = sum(errors) / len(errors) if errors else forecast * 0.2

        forecasts = []
        for i in range(periods_ahead):
            confidence_factor = 1.96 * (1 + i * 0.15)

            forecasts.append(ForecastResult(
                part_id=part_id,
                period=f"P+{i + 1}",
                forecast_quantity=round(forecast, 1),
                confidence_low=max(0, round(forecast - confidence_factor * mae, 1)),
                confidence_high=round(forecast + confidence_factor * mae, 1),
                method='exponential_smoothing'
            ))

        return forecasts

    def detect_seasonality(
        self,
        part_id: str,
        periods: int = 24
    ) -> Dict[str, Any]:
        """
        Detect seasonal patterns in demand.

        Args:
            part_id: Part ID
            periods: Number of periods to analyze

        Returns:
            Seasonality analysis
        """
        history = self.get_demand_history(part_id, periods=periods, period_type='month')

        if len(history) < 12:
            return {
                'seasonal': False,
                'message': 'Insufficient data for seasonality analysis'
            }

        demands = [h['demand'] for h in history]

        # Calculate seasonal indices
        # Group by month
        monthly_avg = {}
        for i, h in enumerate(history):
            month = datetime.fromisoformat(h['start_date']).month
            if month not in monthly_avg:
                monthly_avg[month] = []
            monthly_avg[month].append(h['demand'])

        # Calculate average for each month
        seasonal_indices = {}
        overall_avg = sum(demands) / len(demands) if demands else 1

        for month, values in monthly_avg.items():
            month_avg = sum(values) / len(values) if values else 0
            seasonal_indices[month] = round(month_avg / overall_avg, 2) if overall_avg > 0 else 1.0

        # Determine if seasonal
        index_values = list(seasonal_indices.values())
        index_variance = sum((x - 1) ** 2 for x in index_values) / len(index_values)
        is_seasonal = index_variance > 0.05  # More than 5% variance suggests seasonality

        return {
            'seasonal': is_seasonal,
            'seasonal_indices': seasonal_indices,
            'variance': round(index_variance, 4),
            'interpretation': 'Significant seasonality detected' if is_seasonal else 'No significant seasonality',
            'periods_analyzed': len(history)
        }

    def generate_demand_plan(
        self,
        part_id: str,
        horizon_months: int = 6,
        method: str = 'exponential_smoothing'
    ) -> Dict[str, Any]:
        """
        Generate a complete demand plan.

        Args:
            part_id: Part ID
            horizon_months: Planning horizon in months
            method: Forecast method to use

        Returns:
            Complete demand plan
        """
        part = self.session.query(Part).filter(Part.id == part_id).first()

        if not part:
            raise ValueError(f"Part {part_id} not found")

        # Get history
        history = self.get_demand_history(part_id, periods=12)

        # Generate forecast
        if method == 'moving_average':
            forecasts = self.forecast_moving_average(
                part_id, periods_ahead=horizon_months
            )
        else:
            forecasts = self.forecast_exponential_smoothing(
                part_id, periods_ahead=horizon_months
            )

        # Check seasonality
        seasonality = self.detect_seasonality(part_id)

        # Adjust forecasts for seasonality if detected
        if seasonality['seasonal']:
            now = datetime.utcnow()
            for i, f in enumerate(forecasts):
                future_month = (now.month + i) % 12 or 12
                index = seasonality['seasonal_indices'].get(future_month, 1.0)
                f.forecast_quantity = round(f.forecast_quantity * index, 1)
                f.confidence_low = round(f.confidence_low * index, 1)
                f.confidence_high = round(f.confidence_high * index, 1)

        return {
            'part_id': str(part_id),
            'part_number': part.part_number,
            'part_name': part.name,
            'generated_at': datetime.utcnow().isoformat(),
            'method': method,
            'horizon_months': horizon_months,
            'history': history,
            'seasonality': seasonality,
            'forecasts': [
                {
                    'period': f.period,
                    'forecast': f.forecast_quantity,
                    'confidence_low': f.confidence_low,
                    'confidence_high': f.confidence_high
                }
                for f in forecasts
            ],
            'summary': {
                'average_historical_demand': round(
                    sum(h['demand'] for h in history) / len(history), 1
                ) if history else 0,
                'total_forecast_demand': sum(f.forecast_quantity for f in forecasts),
                'seasonal_adjustment_applied': seasonality['seasonal']
            }
        }

    def calculate_forecast_accuracy(
        self,
        part_id: str,
        periods_back: int = 6
    ) -> Dict[str, Any]:
        """
        Calculate forecast accuracy metrics.

        Returns MAPE, MAE, and bias for past forecasts.
        """
        # This would compare actual vs forecast from stored forecasts
        # For now, simulate with holdout validation
        history = self.get_demand_history(part_id, periods=periods_back + 6)

        if len(history) < periods_back + 3:
            return {
                'error': 'Insufficient history',
                'message': f'Need at least {periods_back + 3} periods'
            }

        # Split into training and test
        train = history[:-periods_back]
        test = history[-periods_back:]

        # Generate "historical" forecast using training data
        train_demands = [h['demand'] for h in train]
        if not train_demands:
            return {'error': 'No training data'}

        forecast = sum(train_demands) / len(train_demands)

        # Calculate accuracy metrics
        actuals = [h['demand'] for h in test]
        errors = [actual - forecast for actual in actuals]
        abs_errors = [abs(e) for e in errors]

        mae = sum(abs_errors) / len(abs_errors)
        bias = sum(errors) / len(errors)

        # MAPE (avoid division by zero)
        mapes = []
        for actual, error in zip(actuals, abs_errors):
            if actual > 0:
                mapes.append(error / actual * 100)
        mape = sum(mapes) / len(mapes) if mapes else 0

        return {
            'part_id': part_id,
            'periods_evaluated': periods_back,
            'mae': round(mae, 2),
            'mape': round(mape, 1),
            'bias': round(bias, 2),
            'interpretation': self._interpret_mape(mape)
        }

    def _interpret_mape(self, mape: float) -> str:
        """Interpret MAPE value."""
        if mape < 10:
            return "Highly accurate forecasting"
        elif mape < 20:
            return "Good forecasting"
        elif mape < 30:
            return "Reasonable forecasting"
        elif mape < 50:
            return "Inaccurate forecasting - consider alternative methods"
        else:
            return "Very inaccurate - demand may be unpredictable"
