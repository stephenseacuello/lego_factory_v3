"""
Predictive Analytics

Time-series forecasting, trend analysis, and predictive
modeling for manufacturing operations.

Reference: ISO 22400 (Manufacturing KPIs), Six Sigma
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import math
import statistics

logger = logging.getLogger(__name__)


class ForecastMethod(Enum):
    """Forecasting method types."""
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    HOLT_WINTERS = "holt_winters"
    LINEAR_REGRESSION = "linear_regression"
    ARIMA = "arima"


class TrendDirection(Enum):
    """Trend direction indicators."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


@dataclass
class ForecastResult:
    """Forecast prediction result."""
    method: ForecastMethod
    predictions: List[Dict[str, Any]]
    confidence_interval: float
    lower_bound: List[float]
    upper_bound: List[float]
    mape: float  # Mean Absolute Percentage Error
    rmse: float  # Root Mean Square Error
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method.value,
            "predictions": self.predictions,
            "confidence_interval": self.confidence_interval,
            "accuracy": {
                "mape": round(self.mape, 4),
                "rmse": round(self.rmse, 4)
            },
            "generated_at": self.generated_at
        }


@dataclass
class TrendAnalysis:
    """Trend analysis result."""
    direction: TrendDirection
    slope: float
    r_squared: float
    change_rate: float
    volatility: float
    seasonality_detected: bool
    period: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction.value,
            "slope": round(self.slope, 6),
            "r_squared": round(self.r_squared, 4),
            "change_rate_percent": round(self.change_rate * 100, 2),
            "volatility": round(self.volatility, 4),
            "seasonality": {
                "detected": self.seasonality_detected,
                "period": self.period
            }
        }


@dataclass
class SeasonalDecomposition:
    """Seasonal decomposition result."""
    trend: List[float]
    seasonal: List[float]
    residual: List[float]
    period: int
    strength_trend: float
    strength_seasonal: float


class PredictiveModel:
    """
    Predictive Analytics Model.
    
    Provides forecasting and trend analysis for:
    - Demand forecasting
    - Production planning
    - Quality prediction
    - Equipment failure prediction
    - Resource optimization
    
    Usage:
        >>> model = PredictiveModel()
        >>> forecast = model.forecast(
        ...     data=historical_values,
        ...     periods=7,
        ...     method=ForecastMethod.EXPONENTIAL_SMOOTHING
        ... )
    """
    
    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        logger.info("PredictiveModel initialized")
    
    def forecast(
        self,
        data: List[float],
        periods: int,
        method: ForecastMethod = ForecastMethod.EXPONENTIAL_SMOOTHING,
        alpha: float = 0.3,
        beta: float = 0.1,
        gamma: float = 0.1,
        seasonal_period: int = 7
    ) -> ForecastResult:
        """
        Generate forecast predictions.
        
        Args:
            data: Historical time series data
            periods: Number of periods to forecast
            method: Forecasting method
            alpha: Level smoothing factor
            beta: Trend smoothing factor
            gamma: Seasonal smoothing factor
            seasonal_period: Period for seasonal patterns
        """
        if len(data) < 3:
            raise ValueError("Need at least 3 data points for forecasting")
        
        if method == ForecastMethod.MOVING_AVERAGE:
            predictions = self._moving_average_forecast(data, periods)
        elif method == ForecastMethod.EXPONENTIAL_SMOOTHING:
            predictions = self._exponential_smoothing(data, periods, alpha)
        elif method == ForecastMethod.HOLT_WINTERS:
            predictions = self._holt_winters(
                data, periods, alpha, beta, gamma, seasonal_period
            )
        elif method == ForecastMethod.LINEAR_REGRESSION:
            predictions = self._linear_regression_forecast(data, periods)
        else:
            predictions = self._exponential_smoothing(data, periods, alpha)
        
        # Calculate confidence intervals
        std_error = self._calculate_std_error(data, predictions[:len(data)])
        z_score = 1.96  # 95% confidence
        
        lower_bound = [p - z_score * std_error for p in predictions]
        upper_bound = [p + z_score * std_error for p in predictions]
        
        # Calculate accuracy metrics
        mape = self._calculate_mape(data[-periods:], predictions[:periods]) if len(data) > periods else 0
        rmse = self._calculate_rmse(data[-periods:], predictions[:periods]) if len(data) > periods else 0
        
        # Format predictions
        pred_dicts = [
            {"period": i + 1, "value": round(p, 4)}
            for i, p in enumerate(predictions[-periods:])
        ]
        
        return ForecastResult(
            method=method,
            predictions=pred_dicts,
            confidence_interval=self.confidence_level,
            lower_bound=[round(x, 4) for x in lower_bound[-periods:]],
            upper_bound=[round(x, 4) for x in upper_bound[-periods:]],
            mape=mape,
            rmse=rmse
        )
    
    def analyze_trend(self, data: List[float]) -> TrendAnalysis:
        """Analyze trend in time series data."""
        if len(data) < 3:
            return TrendAnalysis(
                direction=TrendDirection.STABLE,
                slope=0, r_squared=0, change_rate=0,
                volatility=0, seasonality_detected=False
            )
        
        # Linear regression for trend
        n = len(data)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(data) / n
        
        numerator = sum((x[i] - x_mean) * (data[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean
        
        # R-squared
        predictions = [slope * x[i] + intercept for i in range(n)]
        ss_res = sum((data[i] - predictions[i]) ** 2 for i in range(n))
        ss_tot = sum((data[i] - y_mean) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # Change rate
        if data[0] != 0:
            change_rate = (data[-1] - data[0]) / data[0]
        else:
            change_rate = 0
        
        # Volatility (coefficient of variation)
        volatility = statistics.stdev(data) / y_mean if y_mean != 0 else 0
        
        # Determine direction
        if abs(slope) < 0.001:
            direction = TrendDirection.STABLE
        elif volatility > 0.5:
            direction = TrendDirection.VOLATILE
        elif slope > 0:
            direction = TrendDirection.INCREASING
        else:
            direction = TrendDirection.DECREASING
        
        # Detect seasonality (autocorrelation)
        seasonality_detected, period = self._detect_seasonality(data)
        
        return TrendAnalysis(
            direction=direction,
            slope=slope,
            r_squared=max(0, r_squared),
            change_rate=change_rate,
            volatility=volatility,
            seasonality_detected=seasonality_detected,
            period=period
        )
    
    def decompose_seasonal(
        self,
        data: List[float],
        period: int
    ) -> SeasonalDecomposition:
        """Decompose time series into trend, seasonal, and residual."""
        n = len(data)
        if n < period * 2:
            raise ValueError(f"Need at least {period * 2} data points")
        
        # Moving average for trend
        trend = self._centered_moving_average(data, period)
        
        # Detrended series
        detrended = []
        for i in range(n):
            if trend[i] is not None:
                detrended.append(data[i] - trend[i])
            else:
                detrended.append(None)
        
        # Seasonal factors
        seasonal = [0.0] * n
        for i in range(period):
            season_vals = [
                detrended[j] for j in range(i, n, period)
                if detrended[j] is not None
            ]
            if season_vals:
                avg = sum(season_vals) / len(season_vals)
                for j in range(i, n, period):
                    seasonal[j] = avg
        
        # Residual
        residual = []
        for i in range(n):
            if trend[i] is not None:
                residual.append(data[i] - trend[i] - seasonal[i])
            else:
                residual.append(0)
        
        # Calculate strength
        var_residual = statistics.variance(residual) if len(residual) > 1 else 0
        var_detrended = statistics.variance([d for d in detrended if d is not None]) if detrended else 1
        var_seasonal = statistics.variance(seasonal) if seasonal else 0
        
        strength_seasonal = max(0, 1 - var_residual / (var_seasonal + var_residual + 0.001))
        strength_trend = max(0, 1 - var_residual / (var_detrended + 0.001))
        
        return SeasonalDecomposition(
            trend=[t if t is not None else 0 for t in trend],
            seasonal=seasonal,
            residual=residual,
            period=period,
            strength_trend=round(strength_trend, 4),
            strength_seasonal=round(strength_seasonal, 4)
        )
    
    def _moving_average_forecast(
        self,
        data: List[float],
        periods: int,
        window: int = 3
    ) -> List[float]:
        """Simple moving average forecast."""
        predictions = list(data)
        for _ in range(periods):
            ma = sum(predictions[-window:]) / window
            predictions.append(ma)
        return predictions
    
    def _exponential_smoothing(
        self,
        data: List[float],
        periods: int,
        alpha: float
    ) -> List[float]:
        """Simple exponential smoothing."""
        predictions = [data[0]]
        for i in range(1, len(data)):
            pred = alpha * data[i] + (1 - alpha) * predictions[-1]
            predictions.append(pred)
        
        # Forecast future
        for _ in range(periods):
            predictions.append(predictions[-1])
        
        return predictions
    
    def _holt_winters(
        self,
        data: List[float],
        periods: int,
        alpha: float,
        beta: float,
        gamma: float,
        season_length: int
    ) -> List[float]:
        """Holt-Winters triple exponential smoothing."""
        n = len(data)
        if n < season_length * 2:
            return self._exponential_smoothing(data, periods, alpha)
        
        # Initialize
        level = sum(data[:season_length]) / season_length
        trend = (sum(data[season_length:2*season_length]) - sum(data[:season_length])) / (season_length ** 2)
        
        seasonal = []
        for i in range(season_length):
            seasonal.append(data[i] / level if level != 0 else 1)
        
        predictions = []
        
        for i in range(n + periods):
            if i < n:
                val = data[i]
                last_level = level
                level = alpha * (val / seasonal[i % season_length]) + (1 - alpha) * (level + trend)
                trend = beta * (level - last_level) + (1 - beta) * trend
                seasonal[i % season_length] = gamma * (val / level) + (1 - gamma) * seasonal[i % season_length]
                predictions.append(level * seasonal[i % season_length])
            else:
                m = i - n + 1
                predictions.append((level + m * trend) * seasonal[i % season_length])
        
        return predictions
    
    def _linear_regression_forecast(
        self,
        data: List[float],
        periods: int
    ) -> List[float]:
        """Linear regression forecast."""
        n = len(data)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(data) / n
        
        numerator = sum((x[i] - x_mean) * (data[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean
        
        predictions = [slope * i + intercept for i in range(n + periods)]
        return predictions
    
    def _centered_moving_average(
        self,
        data: List[float],
        period: int
    ) -> List[Optional[float]]:
        """Calculate centered moving average."""
        n = len(data)
        result: List[Optional[float]] = [None] * n
        half = period // 2
        
        for i in range(half, n - half):
            if period % 2 == 0:
                result[i] = (
                    sum(data[i-half:i+half]) + (data[i-half-1] + data[i+half]) / 2
                ) / period
            else:
                result[i] = sum(data[i-half:i+half+1]) / period
        
        return result
    
    def _detect_seasonality(
        self,
        data: List[float],
        max_period: int = 30
    ) -> Tuple[bool, Optional[int]]:
        """Detect seasonality using autocorrelation."""
        n = len(data)
        if n < max_period * 2:
            return False, None
        
        mean = sum(data) / n
        variance = sum((x - mean) ** 2 for x in data)
        
        if variance == 0:
            return False, None
        
        best_period = None
        best_correlation = 0.3  # Threshold
        
        for lag in range(2, min(max_period, n // 2)):
            correlation = sum(
                (data[i] - mean) * (data[i + lag] - mean)
                for i in range(n - lag)
            ) / variance
            
            if correlation > best_correlation:
                best_correlation = correlation
                best_period = lag
        
        return best_period is not None, best_period
    
    def _calculate_std_error(
        self,
        actual: List[float],
        predicted: List[float]
    ) -> float:
        """Calculate standard error of predictions."""
        n = min(len(actual), len(predicted))
        if n < 2:
            return 0
        
        errors = [(actual[i] - predicted[i]) ** 2 for i in range(n)]
        return math.sqrt(sum(errors) / n)
    
    def _calculate_mape(
        self,
        actual: List[float],
        predicted: List[float]
    ) -> float:
        """Calculate Mean Absolute Percentage Error."""
        n = min(len(actual), len(predicted))
        if n == 0:
            return 0
        
        total = 0
        count = 0
        for i in range(n):
            if actual[i] != 0:
                total += abs((actual[i] - predicted[i]) / actual[i])
                count += 1
        
        return (total / count) * 100 if count > 0 else 0
    
    def _calculate_rmse(
        self,
        actual: List[float],
        predicted: List[float]
    ) -> float:
        """Calculate Root Mean Square Error."""
        n = min(len(actual), len(predicted))
        if n == 0:
            return 0
        
        mse = sum((actual[i] - predicted[i]) ** 2 for i in range(n)) / n
        return math.sqrt(mse)
