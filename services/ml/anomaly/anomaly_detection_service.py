"""
LEGO Factory v3 - Anomaly Detection Service
============================================
Comprehensive anomaly detection for manufacturing sensor data using
statistical methods, threshold-based detection, and ML pattern recognition.
"""

from __future__ import annotations
import logging
import threading
import asyncio
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Deque
from dataclasses import dataclass, field

import numpy as np

from services.ml.anomaly.anomaly_types import (
    AnomalySeverity,
    AnomalyCategory,
    AnomalyType,
    AnomalyResult,
    AnomalyConfig,
    ThresholdConfig,
    AnomalyResults,
)

logger = logging.getLogger(__name__)


@dataclass
class SlidingWindow:
    """
    Efficient sliding window for real-time anomaly detection.

    Maintains a fixed-size buffer of recent values with O(1) operations
    for common statistics.
    """
    max_size: int = 100
    values: Deque[float] = field(default_factory=deque)
    timestamps: Deque[datetime] = field(default_factory=deque)

    # Running statistics for O(1) access
    _sum: float = 0.0
    _sum_sq: float = 0.0
    _sorted_values: List[float] = field(default_factory=list)
    _needs_sort: bool = True

    def __post_init__(self):
        self.values = deque(maxlen=self.max_size)
        self.timestamps = deque(maxlen=self.max_size)
        self._sorted_values = []

    def add(self, value: float, timestamp: datetime = None):
        """Add a new value to the window."""
        timestamp = timestamp or datetime.utcnow()

        # Remove oldest value from running stats if at capacity
        if len(self.values) >= self.max_size:
            old_value = self.values[0]
            self._sum -= old_value
            self._sum_sq -= old_value * old_value

        # Add new value
        self.values.append(value)
        self.timestamps.append(timestamp)
        self._sum += value
        self._sum_sq += value * value
        self._needs_sort = True

    def clear(self):
        """Clear the window."""
        self.values.clear()
        self.timestamps.clear()
        self._sum = 0.0
        self._sum_sq = 0.0
        self._sorted_values = []
        self._needs_sort = True

    @property
    def count(self) -> int:
        """Number of values in window."""
        return len(self.values)

    @property
    def mean(self) -> float:
        """Calculate mean of values in window."""
        if not self.values:
            return 0.0
        return self._sum / len(self.values)

    @property
    def variance(self) -> float:
        """Calculate variance of values in window."""
        n = len(self.values)
        if n < 2:
            return 0.0
        mean = self._sum / n
        return (self._sum_sq / n) - (mean * mean)

    @property
    def std(self) -> float:
        """Calculate standard deviation of values in window."""
        return np.sqrt(max(0, self.variance))

    @property
    def sorted_values(self) -> List[float]:
        """Get sorted values (lazy evaluation)."""
        if self._needs_sort:
            self._sorted_values = sorted(self.values)
            self._needs_sort = False
        return self._sorted_values

    @property
    def median(self) -> float:
        """Calculate median of values in window."""
        if not self.values:
            return 0.0
        sorted_vals = self.sorted_values
        n = len(sorted_vals)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
        return sorted_vals[mid]

    @property
    def q1(self) -> float:
        """Calculate first quartile."""
        if len(self.values) < 4:
            return self.median
        sorted_vals = self.sorted_values
        n = len(sorted_vals)
        idx = n // 4
        return sorted_vals[idx]

    @property
    def q3(self) -> float:
        """Calculate third quartile."""
        if len(self.values) < 4:
            return self.median
        sorted_vals = self.sorted_values
        n = len(sorted_vals)
        idx = (3 * n) // 4
        return sorted_vals[idx]

    @property
    def iqr(self) -> float:
        """Calculate interquartile range."""
        return self.q3 - self.q1

    @property
    def mad(self) -> float:
        """Calculate Median Absolute Deviation."""
        if not self.values:
            return 0.0
        med = self.median
        deviations = [abs(v - med) for v in self.values]
        return float(np.median(deviations))

    @property
    def min_value(self) -> float:
        """Get minimum value."""
        return min(self.values) if self.values else 0.0

    @property
    def max_value(self) -> float:
        """Get maximum value."""
        return max(self.values) if self.values else 0.0

    def get_recent(self, n: int = 10) -> List[Tuple[datetime, float]]:
        """Get n most recent values with timestamps."""
        n = min(n, len(self.values))
        return list(zip(
            list(self.timestamps)[-n:],
            list(self.values)[-n:]
        ))

    def to_numpy(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array(list(self.values))


class StatisticalDetector:
    """
    Statistical anomaly detection methods.
    """

    @staticmethod
    def zscore(value: float, mean: float, std: float) -> float:
        """Calculate z-score for a value."""
        if std < 1e-10:
            return 0.0
        return (value - mean) / std

    @staticmethod
    def modified_zscore(value: float, median: float, mad: float) -> float:
        """
        Calculate modified z-score using MAD (more robust to outliers).

        Uses the standard scale factor of 0.6745 for consistency with
        normal distribution.
        """
        if mad < 1e-10:
            return 0.0
        return 0.6745 * (value - median) / mad

    @staticmethod
    def iqr_bounds(q1: float, q3: float, multiplier: float = 1.5) -> Tuple[float, float]:
        """Calculate IQR-based bounds for outlier detection."""
        iqr = q3 - q1
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr
        return lower, upper

    @staticmethod
    def is_iqr_outlier(value: float, q1: float, q3: float, multiplier: float = 1.5) -> bool:
        """Check if value is an IQR outlier."""
        lower, upper = StatisticalDetector.iqr_bounds(q1, q3, multiplier)
        return value < lower or value > upper

    @staticmethod
    def detect_spike(
        values: np.ndarray,
        threshold: float = 5.0,
        window_size: int = 5
    ) -> List[int]:
        """
        Detect spikes in the data using a rolling window approach.

        Returns indices of detected spikes.
        """
        if len(values) < window_size + 1:
            return []

        spikes = []
        for i in range(window_size, len(values)):
            window = values[i - window_size:i]
            window_mean = np.mean(window)
            window_std = np.std(window)

            if window_std > 1e-10:
                z = abs(values[i] - window_mean) / window_std
                if z > threshold:
                    spikes.append(i)

        return spikes

    @staticmethod
    def detect_drift(
        values: np.ndarray,
        window_size: int = 50,
        drift_threshold: float = 2.0
    ) -> Tuple[bool, float]:
        """
        Detect drift by comparing early window to late window means.

        Returns (is_drift, drift_magnitude).
        """
        if len(values) < window_size * 2:
            return False, 0.0

        early_window = values[:window_size]
        late_window = values[-window_size:]

        early_mean = np.mean(early_window)
        early_std = np.std(early_window)

        late_mean = np.mean(late_window)

        if early_std < 1e-10:
            early_std = 1.0

        drift_z = abs(late_mean - early_mean) / early_std
        return drift_z > drift_threshold, drift_z

    @staticmethod
    def detect_flatline(
        values: np.ndarray,
        variance_threshold: float = 0.001
    ) -> bool:
        """Detect flatline (constant values)."""
        if len(values) < 10:
            return False
        return np.var(values) < variance_threshold


class ThresholdDetector:
    """
    Threshold-based anomaly detection.
    """

    @staticmethod
    def check_thresholds(
        value: float,
        config: ThresholdConfig
    ) -> Optional[Tuple[AnomalyCategory, AnomalySeverity, float]]:
        """
        Check value against configured thresholds.

        Returns (category, severity, threshold_violated) or None if normal.
        """
        # Critical high (high-high)
        if config.high_high is not None and value >= config.high_high:
            return (
                AnomalyCategory.OUT_OF_RANGE,
                AnomalySeverity.CRITICAL,
                config.high_high
            )

        # Critical low (low-low)
        if config.low_low is not None and value <= config.low_low:
            return (
                AnomalyCategory.OUT_OF_RANGE,
                AnomalySeverity.CRITICAL,
                config.low_low
            )

        # Warning high
        if config.high is not None and value >= config.high:
            return (
                AnomalyCategory.OUT_OF_RANGE,
                AnomalySeverity.HIGH,
                config.high
            )

        # Warning low
        if config.low is not None and value <= config.low:
            return (
                AnomalyCategory.OUT_OF_RANGE,
                AnomalySeverity.HIGH,
                config.low
            )

        return None

    @staticmethod
    def check_rate_of_change(
        current_value: float,
        previous_value: float,
        time_delta_seconds: float,
        max_rate: float
    ) -> Optional[Tuple[float, float]]:
        """
        Check if rate of change exceeds threshold.

        Returns (actual_rate, max_rate) if exceeded, None otherwise.
        """
        if time_delta_seconds <= 0:
            return None

        rate = abs(current_value - previous_value) / time_delta_seconds

        if rate > max_rate:
            return rate, max_rate

        return None


class PatternDetector:
    """
    ML-based pattern anomaly detection.
    """

    def __init__(self):
        self._model = None
        self._encoder = None

    def load_model(self, model_name: str = 'mm_dtae_lstm'):
        """Load ML model for pattern detection."""
        try:
            from services.ml.inference.inference_service import model_registry
            self._model = model_registry.get(model_name)
            if self._model:
                logger.info(f"Loaded ML model '{model_name}' for pattern detection")
        except Exception as e:
            logger.warning(f"Could not load ML model for pattern detection: {e}")

    def detect_pattern_anomaly(
        self,
        values: np.ndarray,
        threshold: float = 0.7
    ) -> Tuple[bool, float]:
        """
        Detect pattern anomalies using ML model.

        Returns (is_anomaly, anomaly_score).
        """
        if self._model is None:
            return False, 0.0

        try:
            import torch

            # Prepare input
            if values.ndim == 1:
                values = values.reshape(1, -1, 1)
            elif values.ndim == 2:
                values = values[np.newaxis, ...]

            tensor = torch.from_numpy(values).float()
            lengths = torch.tensor([tensor.size(1)])

            with torch.no_grad():
                outputs = self._model([tensor], lengths)
                anomaly_score = torch.sigmoid(outputs['anom']).item()

            return anomaly_score > threshold, anomaly_score

        except Exception as e:
            logger.error(f"Pattern detection error: {e}")
            return False, 0.0


class AnomalyDetectionService:
    """
    Comprehensive anomaly detection service for manufacturing sensor data.

    Combines statistical methods, threshold-based detection, and ML
    pattern recognition for robust anomaly detection.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._config = AnomalyConfig()
        self._windows: Dict[str, SlidingWindow] = {}
        self._pattern_detector = PatternDetector()
        self._last_alarm_times: Dict[str, datetime] = {}
        self._anomaly_history: Deque[AnomalyResult] = deque(maxlen=10000)
        self._lock = threading.Lock()
        self._subscribers: List[asyncio.Queue] = []

        self._initialized = True
        logger.info("Anomaly detection service initialized")

    def configure(self, config: AnomalyConfig):
        """Update service configuration."""
        with self._lock:
            self._config = config
            logger.info("Anomaly detection configuration updated")

    @property
    def config(self) -> AnomalyConfig:
        """Get current configuration."""
        return self._config

    def get_window(self, tag_id: str) -> SlidingWindow:
        """Get or create sliding window for a tag."""
        if tag_id not in self._windows:
            self._windows[tag_id] = SlidingWindow(max_size=self._config.window_size)
        return self._windows[tag_id]

    def clear_window(self, tag_id: str):
        """Clear the sliding window for a tag."""
        if tag_id in self._windows:
            self._windows[tag_id].clear()

    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to anomaly events."""
        queue = asyncio.Queue(maxsize=1000)
        self._subscribers.append(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from anomaly events."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def _notify_subscribers(self, result: AnomalyResult):
        """Notify subscribers of detected anomaly."""
        for queue in self._subscribers:
            try:
                queue.put_nowait(result)
            except asyncio.QueueFull:
                logger.warning("Anomaly subscriber queue full, dropping event")

    def detect_realtime(
        self,
        tag_id: str,
        value: float,
        timestamp: datetime = None,
        tag_name: str = None
    ) -> Optional[AnomalyResult]:
        """
        Real-time anomaly detection for a single value.

        This is the main entry point for real-time detection when new
        tag values arrive. It's designed to be efficient and low-latency.
        """
        if not self._config.enabled:
            return None

        timestamp = timestamp or datetime.utcnow()
        tag_name = tag_name or tag_id
        window = self.get_window(tag_id)
        tag_config = self._config.get_tag_config(tag_id)

        results = []

        # Check thresholds first (fastest check)
        if self._config.use_threshold_detection:
            threshold_result = self._check_threshold_anomaly(
                tag_id, tag_name, value, timestamp, tag_config
            )
            if threshold_result:
                results.append(threshold_result)

        # Check rate of change
        if tag_config.max_rate_of_change is not None and window.count > 0:
            roc_result = self._check_rate_of_change_anomaly(
                tag_id, tag_name, value, timestamp, window, tag_config
            )
            if roc_result:
                results.append(roc_result)

        # Add value to window
        window.add(value, timestamp)

        # Statistical detection (requires sufficient data)
        if self._config.use_statistical_detection and window.count >= self._config.min_samples:
            stat_result = self._check_statistical_anomaly(
                tag_id, tag_name, value, timestamp, window, tag_config
            )
            if stat_result:
                results.append(stat_result)

        # Check for flatline
        if window.count >= self._config.min_samples:
            flatline_result = self._check_flatline_anomaly(
                tag_id, tag_name, value, timestamp, window, tag_config
            )
            if flatline_result:
                results.append(flatline_result)

        # Return most severe anomaly if any
        if results:
            results.sort(key=lambda r: r.severity.value, reverse=True)
            most_severe = results[0]

            # Store in history
            self._anomaly_history.append(most_severe)

            # Generate alarm if configured
            if self._config.generate_alarms:
                self._try_generate_alarm(most_severe)

            return most_severe

        return None

    def _check_threshold_anomaly(
        self,
        tag_id: str,
        tag_name: str,
        value: float,
        timestamp: datetime,
        config: ThresholdConfig
    ) -> Optional[AnomalyResult]:
        """Check for threshold-based anomalies."""
        result = ThresholdDetector.check_thresholds(value, config)

        if result:
            category, severity, threshold = result

            return AnomalyResult(
                tag_id=tag_id,
                tag_name=tag_name,
                is_anomaly=True,
                anomaly_score=min(1.0, abs(value - threshold) / (abs(threshold) + 1e-6) + 0.5),
                severity=severity,
                category=category,
                detection_type=AnomalyType.THRESHOLD_HIGH if value > threshold else AnomalyType.THRESHOLD_LOW,
                value=value,
                threshold_violated=threshold,
                timestamp=timestamp,
                message=f"{tag_name} value {value} exceeded threshold {threshold}",
                confidence=1.0,  # Threshold violations are certain
            )

        return None

    def _check_rate_of_change_anomaly(
        self,
        tag_id: str,
        tag_name: str,
        value: float,
        timestamp: datetime,
        window: SlidingWindow,
        config: ThresholdConfig
    ) -> Optional[AnomalyResult]:
        """Check for rate of change anomalies."""
        if window.count < 1:
            return None

        prev_value = list(window.values)[-1]
        prev_time = list(window.timestamps)[-1]
        time_delta = (timestamp - prev_time).total_seconds()

        if time_delta <= 0:
            return None

        roc_result = ThresholdDetector.check_rate_of_change(
            value, prev_value, time_delta, config.max_rate_of_change
        )

        if roc_result:
            actual_rate, max_rate = roc_result
            score = min(1.0, actual_rate / max_rate)

            return AnomalyResult(
                tag_id=tag_id,
                tag_name=tag_name,
                is_anomaly=True,
                anomaly_score=score,
                severity=AnomalySeverity.from_score(score),
                category=AnomalyCategory.RATE_OF_CHANGE,
                detection_type=AnomalyType.THRESHOLD_BAND,
                value=value,
                expected_value=prev_value,
                deviation=actual_rate,
                threshold_violated=max_rate,
                timestamp=timestamp,
                message=f"{tag_name} rate of change {actual_rate:.2f}/s exceeds {max_rate}/s",
                confidence=0.95,
                details={'actual_rate': actual_rate, 'max_rate': max_rate},
            )

        return None

    def _check_statistical_anomaly(
        self,
        tag_id: str,
        tag_name: str,
        value: float,
        timestamp: datetime,
        window: SlidingWindow,
        config: ThresholdConfig
    ) -> Optional[AnomalyResult]:
        """Check for statistical anomalies using z-score and IQR."""
        # Z-score check
        zscore = StatisticalDetector.zscore(value, window.mean, window.std)

        if abs(zscore) > config.zscore_threshold:
            score = min(1.0, abs(zscore) / (config.zscore_threshold * 2))

            return AnomalyResult(
                tag_id=tag_id,
                tag_name=tag_name,
                is_anomaly=True,
                anomaly_score=score,
                severity=AnomalySeverity.from_score(score),
                category=AnomalyCategory.SPIKE if abs(zscore) > config.spike_threshold else AnomalyCategory.PATTERN,
                detection_type=AnomalyType.ZSCORE,
                value=value,
                expected_value=window.mean,
                deviation=zscore,
                timestamp=timestamp,
                message=f"{tag_name} z-score {zscore:.2f} exceeds threshold {config.zscore_threshold}",
                confidence=0.85,
                details={
                    'zscore': zscore,
                    'mean': window.mean,
                    'std': window.std,
                    'threshold': config.zscore_threshold,
                },
            )

        # IQR check
        if StatisticalDetector.is_iqr_outlier(value, window.q1, window.q3, config.iqr_multiplier):
            lower, upper = StatisticalDetector.iqr_bounds(window.q1, window.q3, config.iqr_multiplier)
            deviation = (value - upper) if value > upper else (lower - value)
            score = min(1.0, abs(deviation) / (window.iqr + 1e-6) * 0.3 + 0.5)

            return AnomalyResult(
                tag_id=tag_id,
                tag_name=tag_name,
                is_anomaly=True,
                anomaly_score=score,
                severity=AnomalySeverity.from_score(score),
                category=AnomalyCategory.OUT_OF_RANGE,
                detection_type=AnomalyType.IQR,
                value=value,
                expected_value=window.median,
                deviation=deviation,
                timestamp=timestamp,
                message=f"{tag_name} IQR outlier: value {value} outside [{lower:.2f}, {upper:.2f}]",
                confidence=0.80,
                details={
                    'q1': window.q1,
                    'q3': window.q3,
                    'iqr': window.iqr,
                    'lower_bound': lower,
                    'upper_bound': upper,
                },
            )

        return None

    def _check_flatline_anomaly(
        self,
        tag_id: str,
        tag_name: str,
        value: float,
        timestamp: datetime,
        window: SlidingWindow,
        config: ThresholdConfig
    ) -> Optional[AnomalyResult]:
        """Check for flatline anomalies."""
        if StatisticalDetector.detect_flatline(window.to_numpy(), config.flatline_threshold):
            # Check duration
            if window.count >= config.flatline_duration_seconds:
                return AnomalyResult(
                    tag_id=tag_id,
                    tag_name=tag_name,
                    is_anomaly=True,
                    anomaly_score=0.6,
                    severity=AnomalySeverity.MEDIUM,
                    category=AnomalyCategory.FLATLINE,
                    detection_type=AnomalyType.THRESHOLD_BAND,
                    value=value,
                    expected_value=None,
                    timestamp=timestamp,
                    message=f"{tag_name} flatline detected: variance {window.variance:.6f}",
                    confidence=0.9,
                    details={
                        'variance': window.variance,
                        'threshold': config.flatline_threshold,
                    },
                )

        return None

    def detect_batch(
        self,
        tag_id: str,
        values: np.ndarray,
        timestamps: List[datetime] = None,
        tag_name: str = None
    ) -> AnomalyResults:
        """
        Batch anomaly detection on a time series.

        Useful for historical data analysis.
        """
        if not self._config.enabled:
            return []

        tag_name = tag_name or tag_id
        tag_config = self._config.get_tag_config(tag_id)
        results = []

        if timestamps is None:
            timestamps = [datetime.utcnow() - timedelta(seconds=i) for i in range(len(values) - 1, -1, -1)]

        # Clear window for batch processing
        window = SlidingWindow(max_size=self._config.window_size)

        for i, (value, ts) in enumerate(zip(values, timestamps)):
            # Add to window
            window.add(value, ts)

            if window.count < self._config.min_samples:
                continue

            # Check for anomalies
            anomalies = []

            # Threshold check
            if self._config.use_threshold_detection:
                threshold_result = self._check_threshold_anomaly(
                    tag_id, tag_name, value, ts, tag_config
                )
                if threshold_result:
                    anomalies.append(threshold_result)

            # Statistical check
            if self._config.use_statistical_detection:
                stat_result = self._check_statistical_anomaly(
                    tag_id, tag_name, value, ts, window, tag_config
                )
                if stat_result:
                    anomalies.append(stat_result)

            # Keep most severe
            if anomalies:
                anomalies.sort(key=lambda r: r.severity.value, reverse=True)
                results.append(anomalies[0])

        # Pattern detection on full sequence
        if self._config.use_pattern_detection and len(values) >= self._config.pattern_sequence_length:
            pattern_results = self._detect_pattern_anomalies(
                tag_id, tag_name, values, timestamps, tag_config
            )
            results.extend(pattern_results)

        # Drift detection
        if len(values) >= self._config.window_size * 2:
            is_drift, drift_magnitude = StatisticalDetector.detect_drift(
                values, self._config.window_size
            )
            if is_drift:
                results.append(AnomalyResult(
                    tag_id=tag_id,
                    tag_name=tag_name,
                    is_anomaly=True,
                    anomaly_score=min(1.0, drift_magnitude / 5.0),
                    severity=AnomalySeverity.from_score(min(1.0, drift_magnitude / 5.0)),
                    category=AnomalyCategory.DRIFT,
                    detection_type=AnomalyType.TREND,
                    value=values[-1],
                    expected_value=np.mean(values[:self._config.window_size]),
                    deviation=drift_magnitude,
                    timestamp=timestamps[-1],
                    window_start=timestamps[0],
                    window_end=timestamps[-1],
                    message=f"{tag_name} drift detected: magnitude {drift_magnitude:.2f}",
                    confidence=0.75,
                ))

        return results

    def _detect_pattern_anomalies(
        self,
        tag_id: str,
        tag_name: str,
        values: np.ndarray,
        timestamps: List[datetime],
        config: ThresholdConfig
    ) -> AnomalyResults:
        """Detect pattern-based anomalies using ML model."""
        results = []

        if self._pattern_detector._model is None:
            self._pattern_detector.load_model(self._config.ml_model_name)

        if self._pattern_detector._model is None:
            return results

        seq_len = self._config.pattern_sequence_length
        stride = seq_len // 2

        for i in range(0, len(values) - seq_len + 1, stride):
            seq = values[i:i + seq_len]
            is_anomaly, score = self._pattern_detector.detect_pattern_anomaly(
                seq, self._config.ml_threshold
            )

            if is_anomaly:
                results.append(AnomalyResult(
                    tag_id=tag_id,
                    tag_name=tag_name,
                    is_anomaly=True,
                    anomaly_score=score,
                    severity=AnomalySeverity.from_score(score),
                    category=AnomalyCategory.PATTERN,
                    detection_type=AnomalyType.ML_MODEL,
                    value=values[i + seq_len - 1],
                    timestamp=timestamps[i + seq_len - 1],
                    window_start=timestamps[i],
                    window_end=timestamps[i + seq_len - 1],
                    message=f"{tag_name} ML pattern anomaly: score {score:.3f}",
                    confidence=0.70,
                    details={'ml_score': score, 'sequence_start': i},
                ))

        return results

    def _try_generate_alarm(self, result: AnomalyResult):
        """Generate ISA-18.2 alarm if cooldown period has passed."""
        alarm_key = f"{result.tag_id}:{result.category.value}"
        now = datetime.utcnow()

        # Check cooldown
        last_alarm = self._last_alarm_times.get(alarm_key)
        if last_alarm:
            elapsed = (now - last_alarm).total_seconds()
            if elapsed < self._config.alarm_cooldown_seconds:
                return

        # Generate alarm
        try:
            from services.ml.anomaly.alarm_integration import generate_alarm_from_anomaly
            generate_alarm_from_anomaly(result)
            self._last_alarm_times[alarm_key] = now
            logger.info(f"Generated alarm for {result.tag_name}: {result.category.value}")
        except Exception as e:
            logger.error(f"Failed to generate alarm: {e}")

    def get_recent_anomalies(
        self,
        tag_id: str = None,
        limit: int = 100,
        min_severity: AnomalySeverity = None
    ) -> AnomalyResults:
        """Get recent anomalies from history."""
        results = list(self._anomaly_history)

        if tag_id:
            results = [r for r in results if r.tag_id == tag_id]

        if min_severity:
            results = [r for r in results if r.severity >= min_severity]

        results.sort(key=lambda r: r.timestamp, reverse=True)
        return results[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            'enabled': self._config.enabled,
            'active_windows': len(self._windows),
            'anomalies_in_history': len(self._anomaly_history),
            'config': self._config.to_dict(),
        }


# Global service instance
anomaly_detection_service = AnomalyDetectionService()


# Convenience functions
def detect_anomalies(
    tag_id: str,
    values: np.ndarray,
    timestamps: List[datetime] = None,
    tag_name: str = None
) -> AnomalyResults:
    """Batch detect anomalies in sensor data."""
    return anomaly_detection_service.detect_batch(tag_id, values, timestamps, tag_name)


def detect_realtime(
    tag_id: str,
    value: float,
    timestamp: datetime = None,
    tag_name: str = None
) -> Optional[AnomalyResult]:
    """Real-time anomaly detection for a single value."""
    return anomaly_detection_service.detect_realtime(tag_id, value, timestamp, tag_name)


def get_detection_config() -> AnomalyConfig:
    """Get current detection configuration."""
    return anomaly_detection_service.config


def update_detection_config(config: AnomalyConfig):
    """Update detection configuration."""
    anomaly_detection_service.configure(config)
