"""
Advanced SPC - Statistical Process Control

LegoMCP World-Class Manufacturing System v5.0
Phase 14: Closed-Loop SPC

Advanced SPC with:
- EWMA (Exponentially Weighted Moving Average)
- CUSUM (Cumulative Sum)
- Multivariate T² (Hotelling)
- Automated responses
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class ChartType(str, Enum):
    """Type of control chart."""
    XBAR = "xbar"
    EWMA = "ewma"
    CUSUM = "cusum"
    MULTIVARIATE = "multivariate"
    INDIVIDUAL = "individual"


class SignalType(str, Enum):
    """Type of SPC signal."""
    OOC_UCL = "ooc_ucl"  # Out of control - upper
    OOC_LCL = "ooc_lcl"  # Out of control - lower
    TREND = "trend"  # Trending pattern
    SHIFT = "shift"  # Mean shift
    STRATIFICATION = "stratification"
    MIXTURE = "mixture"
    OSCILLATION = "oscillation"


@dataclass
class SPCSignal:
    """An SPC out-of-control signal."""
    signal_id: str
    signal_type: SignalType
    chart_type: ChartType
    metric_name: str
    timestamp: datetime

    # Values
    value: float
    ucl: float
    lcl: float
    center: float

    # Severity
    sigma_deviation: float = 0.0
    is_critical: bool = False

    # Context
    work_center_id: Optional[str] = None
    part_id: Optional[str] = None
    batch_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'signal_id': self.signal_id,
            'signal_type': self.signal_type.value,
            'chart_type': self.chart_type.value,
            'metric_name': self.metric_name,
            'timestamp': self.timestamp.isoformat(),
            'value': self.value,
            'ucl': self.ucl,
            'lcl': self.lcl,
            'center': self.center,
            'sigma_deviation': self.sigma_deviation,
            'is_critical': self.is_critical,
            'work_center_id': self.work_center_id,
        }


@dataclass
class EWMAChart:
    """EWMA Control Chart."""
    lambda_weight: float = 0.2  # Smoothing parameter
    L: float = 3.0  # Control limit multiplier

    # Statistics
    mean: float = 0.0
    std: float = 1.0
    ewma: float = 0.0
    sample_count: int = 0

    # Control limits
    ucl: float = 0.0
    lcl: float = 0.0

    def update(self, value: float) -> Tuple[float, bool]:
        """
        Update EWMA with new value.

        Returns:
            (ewma_value, is_ooc)
        """
        self.sample_count += 1

        # Update EWMA
        self.ewma = self.lambda_weight * value + (1 - self.lambda_weight) * self.ewma

        # Calculate control limits
        factor = np.sqrt(
            self.lambda_weight / (2 - self.lambda_weight) *
            (1 - (1 - self.lambda_weight) ** (2 * self.sample_count))
        )
        self.ucl = self.mean + self.L * self.std * factor
        self.lcl = self.mean - self.L * self.std * factor

        # Check if out of control
        is_ooc = self.ewma > self.ucl or self.ewma < self.lcl

        return self.ewma, is_ooc

    def initialize(self, data: List[float]) -> None:
        """Initialize with historical data."""
        if data:
            self.mean = np.mean(data)
            self.std = np.std(data)
            self.ewma = self.mean


@dataclass
class CUSUMChart:
    """CUSUM Control Chart."""
    k: float = 0.5  # Slack value (in sigma units)
    h: float = 5.0  # Decision interval (in sigma units)

    # Statistics
    mean: float = 0.0
    std: float = 1.0

    # CUSUM values
    cusum_pos: float = 0.0
    cusum_neg: float = 0.0

    def update(self, value: float) -> Tuple[float, float, bool]:
        """
        Update CUSUM with new value.

        Returns:
            (cusum_pos, cusum_neg, is_ooc)
        """
        # Standardize
        z = (value - self.mean) / (self.std if self.std > 0 else 1)

        # Update CUSUM
        self.cusum_pos = max(0, z - self.k + self.cusum_pos)
        self.cusum_neg = max(0, -z - self.k + self.cusum_neg)

        # Check if out of control
        is_ooc = self.cusum_pos > self.h or self.cusum_neg > self.h

        return self.cusum_pos, self.cusum_neg, is_ooc

    def reset(self) -> None:
        """Reset CUSUM values after intervention."""
        self.cusum_pos = 0.0
        self.cusum_neg = 0.0

    def initialize(self, data: List[float]) -> None:
        """Initialize with historical data."""
        if data:
            self.mean = np.mean(data)
            self.std = np.std(data)


@dataclass
class MultivariateT2:
    """Hotelling's T² Multivariate Control."""
    alpha: float = 0.01  # Significance level
    variables: List[str] = field(default_factory=list)

    # Statistics
    mean_vector: Optional[np.ndarray] = None
    cov_matrix: Optional[np.ndarray] = None
    cov_inv: Optional[np.ndarray] = None
    ucl: float = 0.0

    def initialize(self, data: np.ndarray) -> None:
        """
        Initialize with historical data.

        Args:
            data: n x p matrix (n samples, p variables)
        """
        n, p = data.shape
        self.mean_vector = np.mean(data, axis=0)
        self.cov_matrix = np.cov(data.T)

        if self.cov_matrix.ndim == 0:
            self.cov_matrix = np.array([[self.cov_matrix]])

        try:
            self.cov_inv = np.linalg.inv(self.cov_matrix)
        except np.linalg.LinAlgError:
            self.cov_inv = np.linalg.pinv(self.cov_matrix)

        # Calculate UCL (F distribution approximation)
        from scipy import stats
        f_critical = stats.f.ppf(1 - self.alpha, p, n - p)
        self.ucl = (p * (n - 1) * (n + 1)) / (n * (n - p)) * f_critical

    def calculate_t2(self, observation: np.ndarray) -> float:
        """Calculate T² statistic for an observation."""
        if self.mean_vector is None or self.cov_inv is None:
            return 0.0

        diff = observation - self.mean_vector
        t2 = diff @ self.cov_inv @ diff.T
        return float(t2)

    def check(self, observation: np.ndarray) -> Tuple[float, bool]:
        """
        Check if observation is out of control.

        Returns:
            (t2_value, is_ooc)
        """
        t2 = self.calculate_t2(observation)
        return t2, t2 > self.ucl


class AdvancedSPCService:
    """
    Advanced SPC Service.

    Provides EWMA, CUSUM, and Multivariate control.
    """

    def __init__(
        self,
        event_bus: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.event_bus = event_bus
        self.config = config or {}

        # Charts by metric
        self._ewma_charts: Dict[str, EWMAChart] = {}
        self._cusum_charts: Dict[str, CUSUMChart] = {}
        self._t2_charts: Dict[str, MultivariateT2] = {}

        # Signal history
        self._signals: List[SPCSignal] = []

    def create_ewma_chart(
        self,
        metric_name: str,
        lambda_weight: float = 0.2,
        historical_data: Optional[List[float]] = None,
    ) -> None:
        """Create an EWMA chart for a metric."""
        chart = EWMAChart(lambda_weight=lambda_weight)
        if historical_data:
            chart.initialize(historical_data)
        self._ewma_charts[metric_name] = chart
        logger.info(f"Created EWMA chart for {metric_name}")

    def create_cusum_chart(
        self,
        metric_name: str,
        k: float = 0.5,
        h: float = 5.0,
        historical_data: Optional[List[float]] = None,
    ) -> None:
        """Create a CUSUM chart for a metric."""
        chart = CUSUMChart(k=k, h=h)
        if historical_data:
            chart.initialize(historical_data)
        self._cusum_charts[metric_name] = chart
        logger.info(f"Created CUSUM chart for {metric_name}")

    def create_t2_chart(
        self,
        chart_name: str,
        variables: List[str],
        historical_data: Optional[np.ndarray] = None,
    ) -> None:
        """Create a multivariate T² chart."""
        chart = MultivariateT2(variables=variables)
        if historical_data is not None:
            chart.initialize(historical_data)
        self._t2_charts[chart_name] = chart
        logger.info(f"Created T² chart {chart_name} with {len(variables)} variables")

    def add_measurement(
        self,
        metric_name: str,
        value: float,
        work_center_id: Optional[str] = None,
        part_id: Optional[str] = None,
    ) -> List[SPCSignal]:
        """
        Add a measurement and check for signals.

        Returns list of triggered signals.
        """
        from uuid import uuid4

        signals = []
        timestamp = datetime.utcnow()

        # Check EWMA
        if metric_name in self._ewma_charts:
            chart = self._ewma_charts[metric_name]
            ewma_value, is_ooc = chart.update(value)

            if is_ooc:
                signal_type = (
                    SignalType.OOC_UCL if ewma_value > chart.ucl
                    else SignalType.OOC_LCL
                )
                signal = SPCSignal(
                    signal_id=str(uuid4()),
                    signal_type=signal_type,
                    chart_type=ChartType.EWMA,
                    metric_name=metric_name,
                    timestamp=timestamp,
                    value=ewma_value,
                    ucl=chart.ucl,
                    lcl=chart.lcl,
                    center=chart.mean,
                    sigma_deviation=abs(ewma_value - chart.mean) / chart.std,
                    work_center_id=work_center_id,
                    part_id=part_id,
                )
                signals.append(signal)
                self._signals.append(signal)

        # Check CUSUM
        if metric_name in self._cusum_charts:
            chart = self._cusum_charts[metric_name]
            cusum_pos, cusum_neg, is_ooc = chart.update(value)

            if is_ooc:
                signal_type = (
                    SignalType.OOC_UCL if cusum_pos > chart.h
                    else SignalType.OOC_LCL
                )
                signal = SPCSignal(
                    signal_id=str(uuid4()),
                    signal_type=signal_type,
                    chart_type=ChartType.CUSUM,
                    metric_name=metric_name,
                    timestamp=timestamp,
                    value=max(cusum_pos, cusum_neg),
                    ucl=chart.h,
                    lcl=-chart.h,
                    center=0,
                    work_center_id=work_center_id,
                    part_id=part_id,
                )
                signals.append(signal)
                self._signals.append(signal)

        return signals

    def add_multivariate_measurement(
        self,
        chart_name: str,
        values: Dict[str, float],
        work_center_id: Optional[str] = None,
    ) -> Optional[SPCSignal]:
        """Add a multivariate measurement and check T²."""
        from uuid import uuid4

        chart = self._t2_charts.get(chart_name)
        if not chart:
            return None

        # Build observation vector
        observation = np.array([values.get(v, 0) for v in chart.variables])

        t2, is_ooc = chart.check(observation)

        if is_ooc:
            signal = SPCSignal(
                signal_id=str(uuid4()),
                signal_type=SignalType.OOC_UCL,
                chart_type=ChartType.MULTIVARIATE,
                metric_name=chart_name,
                timestamp=datetime.utcnow(),
                value=t2,
                ucl=chart.ucl,
                lcl=0,
                center=0,
                work_center_id=work_center_id,
            )
            self._signals.append(signal)
            return signal

        return None

    def get_recent_signals(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get recent SPC signals."""
        return [s.to_dict() for s in self._signals[-count:]]

    def get_chart_status(self, metric_name: str) -> Dict[str, Any]:
        """Get current status of a chart."""
        status = {'metric_name': metric_name}

        if metric_name in self._ewma_charts:
            chart = self._ewma_charts[metric_name]
            status['ewma'] = {
                'current_value': chart.ewma,
                'ucl': chart.ucl,
                'lcl': chart.lcl,
                'center': chart.mean,
                'sample_count': chart.sample_count,
            }

        if metric_name in self._cusum_charts:
            chart = self._cusum_charts[metric_name]
            status['cusum'] = {
                'cusum_pos': chart.cusum_pos,
                'cusum_neg': chart.cusum_neg,
                'h': chart.h,
            }

        return status

    def reset_cusum(self, metric_name: str) -> None:
        """Reset CUSUM chart after intervention."""
        if metric_name in self._cusum_charts:
            self._cusum_charts[metric_name].reset()
            logger.info(f"Reset CUSUM for {metric_name}")

    def get_summary(self) -> Dict[str, Any]:
        """Get SPC summary."""
        return {
            'ewma_charts': len(self._ewma_charts),
            'cusum_charts': len(self._cusum_charts),
            't2_charts': len(self._t2_charts),
            'total_signals': len(self._signals),
            'recent_signals': len([
                s for s in self._signals
                if (datetime.utcnow() - s.timestamp).total_seconds() < 3600
            ]),
        }
