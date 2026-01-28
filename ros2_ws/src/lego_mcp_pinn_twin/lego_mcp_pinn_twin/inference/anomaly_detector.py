"""
Physics-Based Anomaly Detection

Detects anomalies by identifying physics violations:
- Conservation law violations
- Impossible state transitions
- Unrealistic dynamics
- Sensor inconsistencies

Key insight: Real systems obey physics laws. Anomalies violate these laws.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from collections import deque
import logging

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of detected anomalies."""
    PHYSICS_VIOLATION = "physics_violation"
    SENSOR_FAULT = "sensor_fault"
    EQUIPMENT_FAULT = "equipment_fault"
    PROCESS_DEVIATION = "process_deviation"
    UNKNOWN = "unknown"


class SeverityLevel(Enum):
    """Anomaly severity levels."""
    INFO = 0
    WARNING = 1
    CRITICAL = 2
    EMERGENCY = 3


@dataclass
class Anomaly:
    """
    Detected anomaly record.

    Attributes:
        timestamp: Detection time
        anomaly_type: Type of anomaly
        severity: Severity level
        location: Where anomaly was detected
        value: Anomalous value
        expected: Expected value
        residual: Physics residual
        confidence: Detection confidence
        description: Human-readable description
    """
    timestamp: float
    anomaly_type: AnomalyType
    severity: SeverityLevel
    location: str
    value: float
    expected: float
    residual: float
    confidence: float
    description: str


@dataclass
class AnomalyDetectorConfig:
    """
    Anomaly detector configuration.

    Attributes:
        physics_threshold: Threshold for physics residual
        sensor_threshold: Threshold for sensor deviation
        history_window: Window size for trend detection
        min_confidence: Minimum confidence for alert
        enable_learning: Adapt thresholds online
    """
    physics_threshold: float = 0.1
    sensor_threshold: float = 3.0  # Standard deviations
    history_window: int = 100
    min_confidence: float = 0.8
    enable_learning: bool = True


class PhysicsAnomalyDetector:
    """
    Physics-based anomaly detector for manufacturing systems.

    Uses PINN physics residuals to detect anomalies:
    - High residual = physics violation = potential anomaly
    - Tracks residual distribution over time
    - Adapts thresholds based on normal operation

    Key Features:
    - Multi-physics constraint checking
    - Sensor cross-validation
    - Temporal consistency checks
    - Root cause hints from physics

    Usage:
        >>> detector = PhysicsAnomalyDetector(pinn_model, config)
        >>> anomalies = detector.check(sensor_data)
        >>> for a in anomalies:
        ...     print(f"{a.severity}: {a.description}")
    """

    def __init__(
        self,
        model: Any,
        config: Optional[AnomalyDetectorConfig] = None
    ):
        """
        Initialize anomaly detector.

        Args:
            model: PINN model for physics residual computation
            config: Detector configuration
        """
        self.model = model
        self.config = config or AnomalyDetectorConfig()

        # Residual history for baseline
        self._residual_history: deque = deque(maxlen=1000)
        self._baseline_mean: Optional[float] = None
        self._baseline_std: Optional[float] = None

        # Detection history
        self._detection_history: List[Anomaly] = []
        self._false_positive_count: int = 0

        logger.info("PhysicsAnomalyDetector initialized")

    def check(
        self,
        x: np.ndarray,
        y_measured: Optional[np.ndarray] = None
    ) -> List[Anomaly]:
        """
        Check for anomalies in current data.

        Args:
            x: Current state/input data
            y_measured: Optional measured outputs for cross-validation

        Returns:
            List of detected anomalies
        """
        anomalies = []
        timestamp = self._get_timestamp()

        # 1. Check physics residuals
        physics_anomalies = self._check_physics_residuals(x, timestamp)
        anomalies.extend(physics_anomalies)

        # 2. Check prediction vs measurement (if available)
        if y_measured is not None:
            measurement_anomalies = self._check_measurements(x, y_measured, timestamp)
            anomalies.extend(measurement_anomalies)

        # 3. Check temporal consistency
        temporal_anomalies = self._check_temporal_consistency(x, timestamp)
        anomalies.extend(temporal_anomalies)

        # Filter by confidence
        anomalies = [a for a in anomalies if a.confidence >= self.config.min_confidence]

        # Store for history
        self._detection_history.extend(anomalies)

        return anomalies

    def _check_physics_residuals(
        self,
        x: np.ndarray,
        timestamp: float
    ) -> List[Anomaly]:
        """
        Check physics constraint residuals.

        High residuals indicate potential anomalies.
        """
        anomalies = []

        # Get physics residuals from model
        y_pred = self.model.forward(x)
        residuals = self.model.compute_physics_residual(x, y_pred)

        for name, residual in residuals.items():
            residual_magnitude = float(np.mean(np.abs(residual)))

            # Update baseline
            self._residual_history.append(residual_magnitude)
            self._update_baseline()

            # Check against threshold
            if self._baseline_mean is not None and self._baseline_std is not None:
                z_score = (residual_magnitude - self._baseline_mean) / (self._baseline_std + 1e-10)
                threshold = self.config.physics_threshold * 3  # 3-sigma default

                if z_score > threshold:
                    severity = self._severity_from_zscore(z_score)
                    confidence = self._confidence_from_zscore(z_score)

                    anomaly = Anomaly(
                        timestamp=timestamp,
                        anomaly_type=AnomalyType.PHYSICS_VIOLATION,
                        severity=severity,
                        location=f"physics:{name}",
                        value=residual_magnitude,
                        expected=self._baseline_mean,
                        residual=z_score * self._baseline_std,
                        confidence=confidence,
                        description=f"Physics constraint '{name}' violated: "
                                   f"residual={residual_magnitude:.4f}, z={z_score:.2f}"
                    )
                    anomalies.append(anomaly)

        return anomalies

    def _check_measurements(
        self,
        x: np.ndarray,
        y_measured: np.ndarray,
        timestamp: float
    ) -> List[Anomaly]:
        """
        Check prediction vs actual measurements.

        Large discrepancies indicate sensor faults or model errors.
        """
        anomalies = []

        # Get model prediction
        y_pred = self.model.forward(x)

        # Prediction error
        error = np.abs(y_pred - y_measured)
        relative_error = error / (np.abs(y_measured) + 1e-10)

        for i in range(error.shape[1]):
            if np.any(relative_error[:, i] > self.config.sensor_threshold):
                max_error_idx = np.argmax(relative_error[:, i])
                max_error = float(relative_error[max_error_idx, i])

                severity = SeverityLevel.WARNING
                if max_error > self.config.sensor_threshold * 2:
                    severity = SeverityLevel.CRITICAL

                anomaly = Anomaly(
                    timestamp=timestamp,
                    anomaly_type=AnomalyType.SENSOR_FAULT,
                    severity=severity,
                    location=f"sensor:{i}",
                    value=float(y_measured[max_error_idx, i]),
                    expected=float(y_pred[max_error_idx, i]),
                    residual=float(error[max_error_idx, i]),
                    confidence=min(1.0, max_error / self.config.sensor_threshold),
                    description=f"Sensor {i} deviation: measured={y_measured[max_error_idx, i]:.4f}, "
                               f"expected={y_pred[max_error_idx, i]:.4f}"
                )
                anomalies.append(anomaly)

        return anomalies

    def _check_temporal_consistency(
        self,
        x: np.ndarray,
        timestamp: float
    ) -> List[Anomaly]:
        """
        Check temporal consistency of state evolution.

        Detects physically impossible jumps or oscillations.
        """
        anomalies = []

        # Would need state history for full implementation
        # Placeholder for temporal checks

        return anomalies

    def _update_baseline(self) -> None:
        """Update baseline statistics from history."""
        if len(self._residual_history) < 10:
            return

        data = np.array(self._residual_history)
        self._baseline_mean = float(np.mean(data))
        self._baseline_std = float(np.std(data))

    def _severity_from_zscore(self, z: float) -> SeverityLevel:
        """Map z-score to severity level."""
        if z > 6:
            return SeverityLevel.EMERGENCY
        elif z > 4:
            return SeverityLevel.CRITICAL
        elif z > 3:
            return SeverityLevel.WARNING
        else:
            return SeverityLevel.INFO

    def _confidence_from_zscore(self, z: float) -> float:
        """Compute detection confidence from z-score."""
        # Sigmoid-like mapping
        return 1.0 / (1.0 + np.exp(-0.5 * (z - 3)))

    def _get_timestamp(self) -> float:
        """Get current timestamp."""
        import time
        return time.time()

    def get_recent_anomalies(
        self,
        minutes: float = 60.0,
        min_severity: SeverityLevel = SeverityLevel.INFO
    ) -> List[Anomaly]:
        """
        Get recent anomalies above severity threshold.

        Args:
            minutes: Time window in minutes
            min_severity: Minimum severity level

        Returns:
            List of recent anomalies
        """
        import time
        cutoff = time.time() - minutes * 60

        return [
            a for a in self._detection_history
            if a.timestamp >= cutoff and a.severity.value >= min_severity.value
        ]

    def get_anomaly_summary(self) -> Dict[str, Any]:
        """Get summary of detected anomalies."""
        if not self._detection_history:
            return {
                "total": 0,
                "by_type": {},
                "by_severity": {},
                "baseline_mean": self._baseline_mean,
                "baseline_std": self._baseline_std
            }

        by_type = {}
        by_severity = {}

        for a in self._detection_history:
            by_type[a.anomaly_type.value] = by_type.get(a.anomaly_type.value, 0) + 1
            by_severity[a.severity.name] = by_severity.get(a.severity.name, 0) + 1

        return {
            "total": len(self._detection_history),
            "by_type": by_type,
            "by_severity": by_severity,
            "baseline_mean": self._baseline_mean,
            "baseline_std": self._baseline_std
        }

    def reset(self) -> None:
        """Reset detector state."""
        self._residual_history.clear()
        self._detection_history.clear()
        self._baseline_mean = None
        self._baseline_std = None
        logger.info("Anomaly detector reset")
