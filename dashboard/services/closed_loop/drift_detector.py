"""
Drift Detector - Detect model and data drift.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 4: Closed-Loop Learning System
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import numpy as np
import logging
from collections import deque

logger = logging.getLogger(__name__)


class DriftType(Enum):
    """Types of drift."""
    CONCEPT_DRIFT = "concept_drift"    # Relationship between X and Y changes
    DATA_DRIFT = "data_drift"          # Input distribution changes
    PREDICTION_DRIFT = "prediction_drift"  # Output distribution changes
    PERFORMANCE_DRIFT = "performance_drift"  # Model accuracy degrades


@dataclass
class DriftAlert:
    """Alert for detected drift."""
    alert_id: str
    model_id: str
    drift_type: DriftType
    severity: str  # low, medium, high
    score: float
    threshold: float
    detected_at: datetime
    details: Dict[str, Any] = field(default_factory=dict)


class DriftDetector:
    """
    Detect various types of drift in ML models.

    Features:
    - Statistical drift detection
    - Performance monitoring
    - Rolling window analysis
    - Multi-model tracking
    """

    def __init__(self,
                 window_size: int = 100,
                 performance_threshold: float = 0.1,
                 data_drift_threshold: float = 0.05):
        self.window_size = window_size
        self.performance_threshold = performance_threshold
        self.data_drift_threshold = data_drift_threshold

        self._model_stats: Dict[str, Dict] = {}
        self._error_windows: Dict[str, deque] = {}
        self._feature_stats: Dict[str, Dict] = {}
        self._alerts: List[DriftAlert] = []

    def register_model(self, model_id: str, baseline_metrics: Dict[str, float]) -> None:
        """Register a model for drift monitoring."""
        self._model_stats[model_id] = {
            'baseline': baseline_metrics,
            'current': {},
            'samples_seen': 0
        }
        self._error_windows[model_id] = deque(maxlen=self.window_size)
        self._feature_stats[model_id] = {
            'baseline_mean': {},
            'baseline_std': {},
            'current_mean': {},
            'current_std': {}
        }

        logger.info(f"Registered model {model_id} for drift monitoring")

    async def check(self,
                   model_id: str,
                   error: float,
                   features: Dict[str, Any],
                   prediction: Optional[float] = None,
                   actual: Optional[float] = None) -> Dict[str, Any]:
        """
        Check for drift based on new observation.

        Args:
            model_id: Model identifier
            error: Prediction error (|predicted - actual|)
            features: Input features
            prediction: Model prediction
            actual: Actual value

        Returns:
            Dict with drift detection results
        """
        if model_id not in self._model_stats:
            return {'drift_detected': False, 'reason': 'Model not registered'}

        results = {
            'drift_detected': False,
            'model_id': model_id,
            'checks': []
        }

        # Add error to window
        self._error_windows[model_id].append(error)
        self._model_stats[model_id]['samples_seen'] += 1

        # Check performance drift
        perf_result = self._check_performance_drift(model_id)
        results['checks'].append(perf_result)
        if perf_result['drift_detected']:
            results['drift_detected'] = True

        # Check data drift
        data_result = self._check_data_drift(model_id, features)
        results['checks'].append(data_result)
        if data_result['drift_detected']:
            results['drift_detected'] = True

        # Generate alert if drift detected
        if results['drift_detected']:
            alert = self._create_alert(model_id, results)
            self._alerts.append(alert)
            results['alert'] = alert

        return results

    def _check_performance_drift(self, model_id: str) -> Dict[str, Any]:
        """Check for performance drift using error window."""
        errors = list(self._error_windows[model_id])

        if len(errors) < self.window_size // 2:
            return {'drift_detected': False, 'reason': 'Insufficient samples'}

        # Compare recent errors to baseline
        baseline = self._model_stats[model_id]['baseline']
        baseline_error = baseline.get('mae', baseline.get('rmse', 0))

        recent_errors = errors[-self.window_size//2:]
        current_mae = np.mean(recent_errors)

        # Check if error has increased significantly
        if baseline_error > 0:
            relative_change = (current_mae - baseline_error) / baseline_error
        else:
            relative_change = current_mae

        drift_detected = relative_change > self.performance_threshold

        return {
            'drift_detected': drift_detected,
            'drift_type': DriftType.PERFORMANCE_DRIFT.value,
            'baseline_error': baseline_error,
            'current_error': current_mae,
            'relative_change': relative_change,
            'threshold': self.performance_threshold
        }

    def _check_data_drift(self, model_id: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """Check for data drift in input features."""
        stats = self._feature_stats[model_id]

        # Update current statistics
        for key, value in features.items():
            if not isinstance(value, (int, float)):
                continue

            if key not in stats['current_mean']:
                stats['current_mean'][key] = []
            stats['current_mean'][key].append(value)

        # Need enough samples
        if not stats['current_mean'] or len(next(iter(stats['current_mean'].values()))) < 50:
            return {'drift_detected': False, 'reason': 'Insufficient samples'}

        # Calculate drift score using simple mean comparison
        drift_scores = []
        for key in stats['current_mean']:
            if key in stats['baseline_mean']:
                baseline = stats['baseline_mean'][key]
                current = np.mean(stats['current_mean'][key][-50:])
                baseline_std = stats['baseline_std'].get(key, 1)

                if baseline_std > 0:
                    z_score = abs(current - baseline) / baseline_std
                    drift_scores.append(z_score)

        if not drift_scores:
            return {'drift_detected': False, 'reason': 'No comparable features'}

        max_drift = max(drift_scores)
        drift_detected = max_drift > 2.0  # 2 standard deviations

        return {
            'drift_detected': drift_detected,
            'drift_type': DriftType.DATA_DRIFT.value,
            'max_drift_score': max_drift,
            'threshold': 2.0
        }

    def _create_alert(self, model_id: str, results: Dict[str, Any]) -> DriftAlert:
        """Create drift alert."""
        import uuid

        # Determine severity
        max_score = 0
        for check in results['checks']:
            if 'relative_change' in check:
                max_score = max(max_score, abs(check['relative_change']))
            if 'max_drift_score' in check:
                max_score = max(max_score, check['max_drift_score'])

        if max_score > 0.5:
            severity = 'high'
        elif max_score > 0.2:
            severity = 'medium'
        else:
            severity = 'low'

        # Get drift type
        drift_types = [
            c['drift_type'] for c in results['checks']
            if c.get('drift_detected')
        ]
        drift_type = DriftType(drift_types[0]) if drift_types else DriftType.CONCEPT_DRIFT

        return DriftAlert(
            alert_id=str(uuid.uuid4())[:8],
            model_id=model_id,
            drift_type=drift_type,
            severity=severity,
            score=max_score,
            threshold=self.performance_threshold,
            detected_at=datetime.utcnow(),
            details=results['checks']
        )

    def set_baseline(self, model_id: str, features: Dict[str, List[float]]) -> None:
        """Set baseline feature statistics."""
        if model_id not in self._feature_stats:
            self._feature_stats[model_id] = {}

        stats = self._feature_stats[model_id]
        for key, values in features.items():
            stats['baseline_mean'][key] = np.mean(values)
            stats['baseline_std'][key] = np.std(values)

    def get_alerts(self,
                  model_id: Optional[str] = None,
                  since: Optional[datetime] = None) -> List[DriftAlert]:
        """Get drift alerts."""
        alerts = self._alerts

        if model_id:
            alerts = [a for a in alerts if a.model_id == model_id]

        if since:
            alerts = [a for a in alerts if a.detected_at >= since]

        return alerts

    def get_statistics(self, model_id: str) -> Dict[str, Any]:
        """Get drift statistics for a model."""
        if model_id not in self._model_stats:
            return {}

        stats = self._model_stats[model_id]
        errors = list(self._error_windows[model_id])

        return {
            'model_id': model_id,
            'samples_seen': stats['samples_seen'],
            'baseline_metrics': stats['baseline'],
            'current_error_mean': np.mean(errors) if errors else 0,
            'current_error_std': np.std(errors) if errors else 0,
            'alerts_count': len([a for a in self._alerts if a.model_id == model_id])
        }
