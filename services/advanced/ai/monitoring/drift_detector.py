"""
Model Drift Detection Service
LegoMCP PhD-Level Manufacturing Platform

Detects data drift and concept drift in ML models:
- Statistical tests for distribution shifts
- Feature drift monitoring
- Prediction drift tracking
- Automatic alerting

Implements multiple drift detection methods:
- Kolmogorov-Smirnov test
- Chi-squared test
- Population Stability Index (PSI)
- Jensen-Shannon Divergence
- Page-Hinkley test
- ADWIN (Adaptive Windowing)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import json
import hashlib

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class DriftType(Enum):
    DATA = "data"
    CONCEPT = "concept"
    FEATURE = "feature"
    PREDICTION = "prediction"
    LABEL = "label"


class DriftSeverity(Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DriftMethod(Enum):
    KS = "kolmogorov_smirnov"
    CHI2 = "chi_squared"
    PSI = "population_stability_index"
    JS = "jensen_shannon"
    WASSERSTEIN = "wasserstein"
    PAGE_HINKLEY = "page_hinkley"
    ADWIN = "adwin"


@dataclass
class DriftResult:
    """Result of drift detection."""
    drift_type: DriftType
    method: DriftMethod
    feature_name: str
    is_drifted: bool
    drift_score: float
    severity: DriftSeverity
    p_value: Optional[float] = None
    threshold: float = 0.05
    reference_stats: Dict[str, float] = field(default_factory=dict)
    current_stats: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drift_type": self.drift_type.value,
            "method": self.method.value,
            "feature_name": self.feature_name,
            "is_drifted": self.is_drifted,
            "drift_score": self.drift_score,
            "severity": self.severity.value,
            "p_value": self.p_value,
            "threshold": self.threshold,
            "reference_stats": self.reference_stats,
            "current_stats": self.current_stats,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class StatisticalDriftDetector:
    """Statistical tests for drift detection."""

    @staticmethod
    def kolmogorov_smirnov(
        reference: np.ndarray,
        current: np.ndarray,
        threshold: float = 0.05,
    ) -> DriftResult:
        """
        Kolmogorov-Smirnov test for continuous distributions.

        Tests whether two samples come from the same distribution.
        """
        statistic, p_value = stats.ks_2samp(reference, current)

        is_drifted = p_value < threshold
        severity = StatisticalDriftDetector._get_severity(statistic)

        return DriftResult(
            drift_type=DriftType.DATA,
            method=DriftMethod.KS,
            feature_name="",
            is_drifted=is_drifted,
            drift_score=statistic,
            severity=severity,
            p_value=p_value,
            threshold=threshold,
            reference_stats={"mean": float(np.mean(reference)), "std": float(np.std(reference))},
            current_stats={"mean": float(np.mean(current)), "std": float(np.std(current))},
        )

    @staticmethod
    def chi_squared(
        reference: np.ndarray,
        current: np.ndarray,
        n_bins: int = 10,
        threshold: float = 0.05,
    ) -> DriftResult:
        """
        Chi-squared test for categorical or binned continuous data.
        """
        # Bin continuous data if needed
        if len(np.unique(reference)) > n_bins:
            bins = np.histogram_bin_edges(
                np.concatenate([reference, current]), bins=n_bins
            )
            ref_hist, _ = np.histogram(reference, bins=bins)
            cur_hist, _ = np.histogram(current, bins=bins)
        else:
            # Categorical data
            categories = np.unique(np.concatenate([reference, current]))
            ref_hist = np.array([np.sum(reference == c) for c in categories])
            cur_hist = np.array([np.sum(current == c) for c in categories])

        # Normalize
        ref_hist = ref_hist / ref_hist.sum()
        cur_hist = cur_hist / cur_hist.sum()

        # Add small epsilon to avoid division by zero
        epsilon = 1e-10
        ref_hist = ref_hist + epsilon
        cur_hist = cur_hist + epsilon

        # Chi-squared statistic
        statistic, p_value = stats.chisquare(cur_hist, f_exp=ref_hist)

        is_drifted = p_value < threshold
        severity = StatisticalDriftDetector._get_severity(statistic / 100)

        return DriftResult(
            drift_type=DriftType.DATA,
            method=DriftMethod.CHI2,
            feature_name="",
            is_drifted=is_drifted,
            drift_score=float(statistic),
            severity=severity,
            p_value=float(p_value),
            threshold=threshold,
        )

    @staticmethod
    def population_stability_index(
        reference: np.ndarray,
        current: np.ndarray,
        n_bins: int = 10,
    ) -> DriftResult:
        """
        Population Stability Index (PSI) for distribution comparison.

        PSI < 0.1: No significant change
        0.1 <= PSI < 0.25: Moderate change
        PSI >= 0.25: Significant change
        """
        # Create bins from reference distribution
        percentiles = np.percentile(reference, np.linspace(0, 100, n_bins + 1))
        percentiles[0] = -np.inf
        percentiles[-1] = np.inf

        # Calculate proportions in each bin
        ref_counts = np.histogram(reference, bins=percentiles)[0]
        cur_counts = np.histogram(current, bins=percentiles)[0]

        ref_prop = ref_counts / len(reference)
        cur_prop = cur_counts / len(current)

        # Add small epsilon to avoid log(0)
        epsilon = 1e-10
        ref_prop = np.maximum(ref_prop, epsilon)
        cur_prop = np.maximum(cur_prop, epsilon)

        # Calculate PSI
        psi = np.sum((cur_prop - ref_prop) * np.log(cur_prop / ref_prop))

        # Determine severity
        if psi < 0.1:
            severity = DriftSeverity.NONE
            is_drifted = False
        elif psi < 0.25:
            severity = DriftSeverity.MEDIUM
            is_drifted = True
        else:
            severity = DriftSeverity.HIGH
            is_drifted = True

        return DriftResult(
            drift_type=DriftType.DATA,
            method=DriftMethod.PSI,
            feature_name="",
            is_drifted=is_drifted,
            drift_score=float(psi),
            severity=severity,
            threshold=0.1,
            details={"n_bins": n_bins},
        )

    @staticmethod
    def jensen_shannon_divergence(
        reference: np.ndarray,
        current: np.ndarray,
        n_bins: int = 50,
    ) -> DriftResult:
        """
        Jensen-Shannon Divergence for distribution comparison.

        JS divergence is symmetric and bounded between 0 and 1.
        """
        # Create histograms
        bins = np.histogram_bin_edges(
            np.concatenate([reference, current]), bins=n_bins
        )
        ref_hist, _ = np.histogram(reference, bins=bins, density=True)
        cur_hist, _ = np.histogram(current, bins=bins, density=True)

        # Normalize
        ref_hist = ref_hist / (ref_hist.sum() + 1e-10)
        cur_hist = cur_hist / (cur_hist.sum() + 1e-10)

        # Calculate JS divergence
        m = 0.5 * (ref_hist + cur_hist)

        def kl_div(p, q):
            mask = (p > 0) & (q > 0)
            return np.sum(p[mask] * np.log(p[mask] / q[mask]))

        js_div = 0.5 * kl_div(ref_hist, m) + 0.5 * kl_div(cur_hist, m)

        # Determine severity based on JS divergence
        if js_div < 0.05:
            severity = DriftSeverity.NONE
            is_drifted = False
        elif js_div < 0.15:
            severity = DriftSeverity.LOW
            is_drifted = True
        elif js_div < 0.3:
            severity = DriftSeverity.MEDIUM
            is_drifted = True
        else:
            severity = DriftSeverity.HIGH
            is_drifted = True

        return DriftResult(
            drift_type=DriftType.DATA,
            method=DriftMethod.JS,
            feature_name="",
            is_drifted=is_drifted,
            drift_score=float(js_div),
            severity=severity,
            threshold=0.05,
        )

    @staticmethod
    def wasserstein_distance(
        reference: np.ndarray,
        current: np.ndarray,
    ) -> DriftResult:
        """
        Wasserstein distance (Earth Mover's Distance) for distribution comparison.
        """
        distance = stats.wasserstein_distance(reference, current)

        # Normalize by reference range
        ref_range = np.max(reference) - np.min(reference)
        if ref_range > 0:
            normalized_distance = distance / ref_range
        else:
            normalized_distance = distance

        # Determine severity
        if normalized_distance < 0.1:
            severity = DriftSeverity.NONE
            is_drifted = False
        elif normalized_distance < 0.25:
            severity = DriftSeverity.LOW
            is_drifted = True
        elif normalized_distance < 0.5:
            severity = DriftSeverity.MEDIUM
            is_drifted = True
        else:
            severity = DriftSeverity.HIGH
            is_drifted = True

        return DriftResult(
            drift_type=DriftType.DATA,
            method=DriftMethod.WASSERSTEIN,
            feature_name="",
            is_drifted=is_drifted,
            drift_score=float(normalized_distance),
            severity=severity,
            threshold=0.1,
            details={"raw_distance": float(distance)},
        )

    @staticmethod
    def _get_severity(score: float) -> DriftSeverity:
        """Map drift score to severity level."""
        if score < 0.1:
            return DriftSeverity.NONE
        elif score < 0.2:
            return DriftSeverity.LOW
        elif score < 0.4:
            return DriftSeverity.MEDIUM
        elif score < 0.6:
            return DriftSeverity.HIGH
        else:
            return DriftSeverity.CRITICAL


class StreamingDriftDetector:
    """
    Streaming drift detection for real-time monitoring.

    Uses Page-Hinkley and ADWIN algorithms for online detection.
    """

    def __init__(
        self,
        delta: float = 0.005,
        lambda_: float = 50,
        alpha: float = 0.01,
        window_size: int = 1000,
    ):
        self.delta = delta
        self.lambda_ = lambda_
        self.alpha = alpha
        self.window_size = window_size

        # Page-Hinkley state
        self._ph_min = 0
        self._ph_max = 0
        self._ph_sum = 0
        self._ph_n = 0

        # ADWIN state
        self._adwin_window = deque(maxlen=window_size)
        self._adwin_sum = 0.0
        self._adwin_variance = 0.0

        # History
        self._history: List[DriftResult] = []

    def update(self, value: float, feature_name: str = "stream") -> Optional[DriftResult]:
        """
        Update with new observation and check for drift.

        Returns DriftResult if drift is detected, None otherwise.
        """
        # Page-Hinkley test
        ph_result = self._page_hinkley_update(value, feature_name)

        # ADWIN test
        adwin_result = self._adwin_update(value, feature_name)

        # Return the more severe result
        if ph_result and adwin_result:
            if ph_result.drift_score > adwin_result.drift_score:
                return ph_result
            return adwin_result
        return ph_result or adwin_result

    def _page_hinkley_update(self, value: float, feature_name: str) -> Optional[DriftResult]:
        """
        Page-Hinkley test for change detection.

        Detects changes in the mean of a sequence.
        """
        self._ph_n += 1

        # Update cumulative sums
        if self._ph_n == 1:
            self._ph_sum = value
            return None

        mean = self._ph_sum / (self._ph_n - 1)
        self._ph_sum += value

        # Page-Hinkley statistics
        self._ph_min = min(self._ph_min, self._ph_sum - self._ph_n * mean)
        self._ph_max = max(self._ph_max, self._ph_sum - self._ph_n * mean)

        ph_plus = (self._ph_sum - self._ph_n * mean) - self._ph_min
        ph_minus = self._ph_max - (self._ph_sum - self._ph_n * mean)

        # Check for drift
        if ph_plus > self.lambda_ or ph_minus > self.lambda_:
            result = DriftResult(
                drift_type=DriftType.CONCEPT,
                method=DriftMethod.PAGE_HINKLEY,
                feature_name=feature_name,
                is_drifted=True,
                drift_score=max(ph_plus, ph_minus),
                severity=self._get_streaming_severity(max(ph_plus, ph_minus)),
                threshold=self.lambda_,
                details={
                    "ph_plus": float(ph_plus),
                    "ph_minus": float(ph_minus),
                    "n_samples": self._ph_n,
                },
            )
            self._history.append(result)

            # Reset after detection
            self._reset_page_hinkley()

            return result

        return None

    def _adwin_update(self, value: float, feature_name: str) -> Optional[DriftResult]:
        """
        ADWIN (Adaptive Windowing) for change detection.

        Automatically adjusts window size based on detected changes.
        """
        self._adwin_window.append(value)

        if len(self._adwin_window) < 10:
            return None

        # Calculate statistics for window halves
        window = list(self._adwin_window)
        n = len(window)

        for split in range(10, n - 10):
            left = window[:split]
            right = window[split:]

            left_mean = np.mean(left)
            right_mean = np.mean(right)

            # Hoeffding bound
            m = 1.0 / (1.0 / len(left) + 1.0 / len(right))
            delta_mean = abs(left_mean - right_mean)
            epsilon = np.sqrt(np.log(1.0 / self.alpha) / (2 * m))

            if delta_mean > epsilon:
                result = DriftResult(
                    drift_type=DriftType.CONCEPT,
                    method=DriftMethod.ADWIN,
                    feature_name=feature_name,
                    is_drifted=True,
                    drift_score=float(delta_mean),
                    severity=self._get_streaming_severity(delta_mean),
                    threshold=float(epsilon),
                    details={
                        "left_mean": float(left_mean),
                        "right_mean": float(right_mean),
                        "split_point": split,
                        "window_size": n,
                    },
                )
                self._history.append(result)

                # Shrink window
                self._adwin_window = deque(right, maxlen=self.window_size)

                return result

        return None

    def _reset_page_hinkley(self):
        """Reset Page-Hinkley state."""
        self._ph_min = 0
        self._ph_max = 0
        self._ph_sum = 0
        self._ph_n = 0

    def _get_streaming_severity(self, score: float) -> DriftSeverity:
        """Map streaming drift score to severity."""
        if score < self.lambda_ * 0.5:
            return DriftSeverity.LOW
        elif score < self.lambda_ * 1.5:
            return DriftSeverity.MEDIUM
        elif score < self.lambda_ * 3:
            return DriftSeverity.HIGH
        else:
            return DriftSeverity.CRITICAL

    def get_history(self, limit: int = 100) -> List[DriftResult]:
        """Get drift detection history."""
        return self._history[-limit:]


class ModelDriftMonitor:
    """
    High-level drift monitoring for ML models.

    Monitors:
    - Input feature distributions
    - Prediction distributions
    - Model performance metrics
    """

    def __init__(
        self,
        model_name: str,
        reference_data: Optional[np.ndarray] = None,
        reference_predictions: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        methods: List[DriftMethod] = None,
    ):
        self.model_name = model_name
        self.feature_names = feature_names or []
        self.methods = methods or [DriftMethod.KS, DriftMethod.PSI]

        self.reference_data = reference_data
        self.reference_predictions = reference_predictions

        # Streaming detectors for real-time monitoring
        self.streaming_detectors: Dict[str, StreamingDriftDetector] = {}

        # History
        self.drift_history: List[DriftResult] = []

    def set_reference(
        self,
        data: np.ndarray,
        predictions: Optional[np.ndarray] = None,
    ):
        """Set reference data for drift detection."""
        self.reference_data = data
        self.reference_predictions = predictions

    def check_drift(
        self,
        current_data: np.ndarray,
        current_predictions: Optional[np.ndarray] = None,
    ) -> Dict[str, List[DriftResult]]:
        """
        Check for drift in features and predictions.

        Returns dict with drift results per feature.
        """
        if self.reference_data is None:
            raise ValueError("Reference data not set. Call set_reference first.")

        results = {"features": [], "predictions": []}

        # Check feature drift
        if current_data.ndim == 1:
            current_data = current_data.reshape(-1, 1)
        if self.reference_data.ndim == 1:
            ref_data = self.reference_data.reshape(-1, 1)
        else:
            ref_data = self.reference_data

        n_features = min(current_data.shape[1], ref_data.shape[1])

        for i in range(n_features):
            feature_name = self.feature_names[i] if i < len(self.feature_names) else f"feature_{i}"

            for method in self.methods:
                result = self._detect_drift(
                    ref_data[:, i],
                    current_data[:, i],
                    method,
                )
                result.feature_name = feature_name
                result.drift_type = DriftType.FEATURE
                results["features"].append(result)

                if result.is_drifted:
                    self.drift_history.append(result)

        # Check prediction drift
        if current_predictions is not None and self.reference_predictions is not None:
            for method in self.methods:
                result = self._detect_drift(
                    self.reference_predictions,
                    current_predictions,
                    method,
                )
                result.feature_name = "predictions"
                result.drift_type = DriftType.PREDICTION
                results["predictions"].append(result)

                if result.is_drifted:
                    self.drift_history.append(result)

        return results

    def _detect_drift(
        self,
        reference: np.ndarray,
        current: np.ndarray,
        method: DriftMethod,
    ) -> DriftResult:
        """Run drift detection with specified method."""
        detector = StatisticalDriftDetector

        if method == DriftMethod.KS:
            return detector.kolmogorov_smirnov(reference, current)
        elif method == DriftMethod.CHI2:
            return detector.chi_squared(reference, current)
        elif method == DriftMethod.PSI:
            return detector.population_stability_index(reference, current)
        elif method == DriftMethod.JS:
            return detector.jensen_shannon_divergence(reference, current)
        elif method == DriftMethod.WASSERSTEIN:
            return detector.wasserstein_distance(reference, current)
        else:
            raise ValueError(f"Unknown drift method: {method}")

    def get_drift_summary(self) -> Dict[str, Any]:
        """Get summary of drift detection results."""
        if not self.drift_history:
            return {
                "model_name": self.model_name,
                "total_detections": 0,
                "is_drifted": False,
                "features_drifted": [],
                "max_severity": DriftSeverity.NONE.value,
            }

        features_drifted = set()
        max_severity = DriftSeverity.NONE
        severity_order = [
            DriftSeverity.NONE,
            DriftSeverity.LOW,
            DriftSeverity.MEDIUM,
            DriftSeverity.HIGH,
            DriftSeverity.CRITICAL,
        ]

        for result in self.drift_history:
            if result.is_drifted:
                features_drifted.add(result.feature_name)
                if severity_order.index(result.severity) > severity_order.index(max_severity):
                    max_severity = result.severity

        return {
            "model_name": self.model_name,
            "total_detections": len(self.drift_history),
            "is_drifted": len(features_drifted) > 0,
            "features_drifted": list(features_drifted),
            "max_severity": max_severity.value,
            "last_check": self.drift_history[-1].timestamp.isoformat() if self.drift_history else None,
        }


# Global monitors registry
_monitors: Dict[str, ModelDriftMonitor] = {}


def get_or_create_monitor(
    model_name: str,
    **kwargs,
) -> ModelDriftMonitor:
    """Get or create a drift monitor for a model."""
    if model_name not in _monitors:
        _monitors[model_name] = ModelDriftMonitor(model_name, **kwargs)
    return _monitors[model_name]
