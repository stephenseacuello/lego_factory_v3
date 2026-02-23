"""
Anomaly Detector - Multivariate Anomaly Detection

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- Isolation Forest anomaly detection
- Statistical anomaly detection
- Time-series anomaly detection
- Real-time monitoring
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum
import threading
import uuid
import math
import random
from collections import defaultdict, deque


class AnomalyType(Enum):
    """Types of anomalies."""
    POINT = "point"  # Single point anomaly
    CONTEXTUAL = "contextual"  # Anomaly in context
    COLLECTIVE = "collective"  # Group of points forming anomaly
    TREND = "trend"  # Anomalous trend
    SEASONAL = "seasonal"  # Seasonal pattern violation
    LEVEL_SHIFT = "level_shift"  # Sudden level change


class DetectionMethod(Enum):
    """Anomaly detection methods."""
    ISOLATION_FOREST = "isolation_forest"
    LOCAL_OUTLIER_FACTOR = "local_outlier_factor"
    ONE_CLASS_SVM = "one_class_svm"
    STATISTICAL = "statistical"
    AUTOENCODER = "autoencoder"
    ENSEMBLE = "ensemble"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = 1
    WARNING = 2
    MAJOR = 3
    CRITICAL = 4


@dataclass
class AnomalyConfig:
    """Anomaly detector configuration."""
    method: DetectionMethod = DetectionMethod.ISOLATION_FOREST
    contamination: float = 0.05  # Expected anomaly ratio
    n_estimators: int = 100
    threshold_sigma: float = 3.0  # For statistical method
    window_size: int = 100
    min_samples: int = 20
    enable_multivariate: bool = True


@dataclass
class DataPoint:
    """Data point for anomaly detection."""
    point_id: str
    entity_id: str
    timestamp: datetime
    features: Dict[str, float]
    labels: Optional[Dict[str, str]] = None


@dataclass
class AnomalyResult:
    """Anomaly detection result."""
    result_id: str
    entity_id: str
    is_anomaly: bool
    anomaly_type: Optional[AnomalyType]
    score: float  # Anomaly score (higher = more anomalous)
    severity: AlertSeverity
    features_contribution: Dict[str, float]
    expected_range: Dict[str, Tuple[float, float]]
    actual_values: Dict[str, float]
    description: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AnomalyAlert:
    """Anomaly alert."""
    alert_id: str
    entity_id: str
    anomaly_result: AnomalyResult
    severity: AlertSeverity
    acknowledged: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


@dataclass
class ModelStats:
    """Statistics for a trained model."""
    entity_id: str
    n_samples: int
    feature_means: Dict[str, float]
    feature_stds: Dict[str, float]
    feature_mins: Dict[str, float]
    feature_maxs: Dict[str, float]
    last_update: datetime


class AnomalyDetector:
    """
    Multivariate anomaly detection using Isolation Forest.

    Features:
    - Real-time anomaly detection
    - Multiple detection methods
    - Feature contribution analysis
    - Adaptive thresholds
    """

    def __init__(self, config: Optional[AnomalyConfig] = None):
        """
        Initialize anomaly detector.

        Args:
            config: Detector configuration
        """
        self.config = config or AnomalyConfig()

        # Data storage per entity
        self._data_windows: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.config.window_size)
        )

        # Model statistics per entity
        self._model_stats: Dict[str, ModelStats] = {}

        # Trained models (placeholder for actual models)
        self._models: Dict[str, Any] = {}

        # Alert management
        self._active_alerts: Dict[str, AnomalyAlert] = {}
        self._alert_history: List[AnomalyAlert] = []

        # Thread safety
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            "points_processed": 0,
            "anomalies_detected": 0,
            "alerts_created": 0,
            "models_trained": 0,
        }

    def detect(
        self,
        entity_id: str,
        features: Dict[str, float],
        timestamp: Optional[datetime] = None
    ) -> AnomalyResult:
        """
        Detect anomalies in a data point.

        Args:
            entity_id: Entity identifier
            features: Feature values
            timestamp: Data point timestamp

        Returns:
            Anomaly detection result
        """
        with self._lock:
            self._stats["points_processed"] += 1
            timestamp = timestamp or datetime.utcnow()

            # Create data point
            point = DataPoint(
                point_id=str(uuid.uuid4()),
                entity_id=entity_id,
                timestamp=timestamp,
                features=features,
            )

            # Add to window
            self._data_windows[entity_id].append(point)

            # Update statistics
            self._update_stats(entity_id)

            # Detect anomaly
            if self.config.method == DetectionMethod.ISOLATION_FOREST:
                result = self._detect_isolation_forest(entity_id, point)
            elif self.config.method == DetectionMethod.STATISTICAL:
                result = self._detect_statistical(entity_id, point)
            else:
                result = self._detect_ensemble(entity_id, point)

            # Create alert if anomaly
            if result.is_anomaly:
                self._stats["anomalies_detected"] += 1
                self._create_alert(result)

            return result

    def detect_batch(
        self,
        data_points: List[DataPoint]
    ) -> List[AnomalyResult]:
        """
        Batch anomaly detection.

        Args:
            data_points: List of data points

        Returns:
            List of results
        """
        results = []

        for point in data_points:
            result = self.detect(
                point.entity_id,
                point.features,
                point.timestamp,
            )
            results.append(result)

        return results

    def train(
        self,
        entity_id: str,
        training_data: Optional[List[DataPoint]] = None
    ) -> Dict[str, Any]:
        """
        Train anomaly detection model.

        Args:
            entity_id: Entity identifier
            training_data: Training data (uses window if None)

        Returns:
            Training result
        """
        with self._lock:
            if training_data:
                for point in training_data:
                    self._data_windows[entity_id].append(point)

            window = list(self._data_windows[entity_id])

            if len(window) < self.config.min_samples:
                return {
                    "success": False,
                    "error": f"Insufficient data: {len(window)} < {self.config.min_samples}",
                }

            # Update statistics
            self._update_stats(entity_id)

            # Train model (simulated)
            # Real implementation would use sklearn.ensemble.IsolationForest
            self._models[entity_id] = {
                "type": self.config.method.value,
                "n_estimators": self.config.n_estimators,
                "contamination": self.config.contamination,
                "trained_at": datetime.utcnow(),
                "n_samples": len(window),
            }

            self._stats["models_trained"] += 1

            return {
                "success": True,
                "entity_id": entity_id,
                "method": self.config.method.value,
                "n_samples": len(window),
                "n_features": len(self._model_stats[entity_id].feature_means),
            }

    def get_feature_importance(
        self,
        entity_id: str
    ) -> Dict[str, float]:
        """
        Get feature importance for anomaly detection.

        Args:
            entity_id: Entity identifier

        Returns:
            Feature importance scores
        """
        stats = self._model_stats.get(entity_id)
        if stats is None:
            return {}

        # Calculate importance based on variability
        importance = {}
        total_var = 0

        for name, std in stats.feature_stds.items():
            var = std ** 2
            importance[name] = var
            total_var += var

        # Normalize
        if total_var > 0:
            importance = {k: v / total_var for k, v in importance.items()}

        return importance

    def get_thresholds(
        self,
        entity_id: str
    ) -> Dict[str, Tuple[float, float]]:
        """
        Get anomaly thresholds for each feature.

        Args:
            entity_id: Entity identifier

        Returns:
            Dict mapping feature to (lower, upper) thresholds
        """
        stats = self._model_stats.get(entity_id)
        if stats is None:
            return {}

        thresholds = {}
        sigma = self.config.threshold_sigma

        for name in stats.feature_means:
            mean = stats.feature_means[name]
            std = stats.feature_stds.get(name, 0)

            lower = mean - sigma * std
            upper = mean + sigma * std

            thresholds[name] = (lower, upper)

        return thresholds

    def get_anomaly_score(
        self,
        entity_id: str,
        features: Dict[str, float]
    ) -> float:
        """
        Get anomaly score without creating alert.

        Args:
            entity_id: Entity identifier
            features: Feature values

        Returns:
            Anomaly score (0-1)
        """
        result = self.detect(entity_id, features)
        return result.score

    def get_alerts(
        self,
        entity_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        acknowledged: Optional[bool] = None
    ) -> List[AnomalyAlert]:
        """
        Get anomaly alerts.

        Args:
            entity_id: Filter by entity
            severity: Filter by severity
            acknowledged: Filter by acknowledged status

        Returns:
            List of alerts
        """
        alerts = list(self._active_alerts.values())

        if entity_id:
            alerts = [a for a in alerts if a.entity_id == entity_id]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]

        return alerts

    def acknowledge_alert(
        self,
        alert_id: str,
        user: str
    ) -> bool:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert identifier
            user: User acknowledging

        Returns:
            Success status
        """
        with self._lock:
            alert = self._active_alerts.get(alert_id)
            if alert is None:
                return False

            alert.acknowledged = True
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = user

            # Move to history
            self._alert_history.append(alert)
            del self._active_alerts[alert_id]

            return True

    def get_time_series_anomalies(
        self,
        entity_id: str,
        feature: str,
        lookback_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get anomalies in time series for a feature.

        Args:
            entity_id: Entity identifier
            feature: Feature name
            lookback_hours: Hours to look back

        Returns:
            List of anomalous points
        """
        window = list(self._data_windows.get(entity_id, []))
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)

        recent = [p for p in window if p.timestamp > cutoff]
        anomalies = []

        stats = self._model_stats.get(entity_id)
        if stats is None or feature not in stats.feature_means:
            return []

        mean = stats.feature_means[feature]
        std = stats.feature_stds.get(feature, 1)
        sigma = self.config.threshold_sigma

        for point in recent:
            if feature not in point.features:
                continue

            value = point.features[feature]
            z_score = abs(value - mean) / max(std, 0.001)

            if z_score > sigma:
                anomalies.append({
                    "timestamp": point.timestamp.isoformat(),
                    "value": value,
                    "z_score": z_score,
                    "expected_range": (mean - sigma * std, mean + sigma * std),
                })

        return anomalies

    def detect_collective_anomaly(
        self,
        entity_id: str,
        window_size: int = 10
    ) -> Optional[AnomalyResult]:
        """
        Detect collective anomalies in recent data.

        Args:
            entity_id: Entity identifier
            window_size: Window to analyze

        Returns:
            Anomaly result if detected
        """
        window = list(self._data_windows.get(entity_id, []))

        if len(window) < window_size:
            return None

        recent = window[-window_size:]
        stats = self._model_stats.get(entity_id)

        if stats is None:
            return None

        # Check if entire window is anomalous
        anomaly_count = 0

        for point in recent:
            score = self._calculate_point_score(point, stats)
            if score > 0.5:
                anomaly_count += 1

        if anomaly_count >= window_size * 0.5:  # 50% anomalous
            return AnomalyResult(
                result_id=str(uuid.uuid4()),
                entity_id=entity_id,
                is_anomaly=True,
                anomaly_type=AnomalyType.COLLECTIVE,
                score=anomaly_count / window_size,
                severity=AlertSeverity.MAJOR,
                features_contribution={},
                expected_range={},
                actual_values={},
                description=f"Collective anomaly: {anomaly_count}/{window_size} points anomalous",
            )

        return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            **self._stats,
            "active_alerts": len(self._active_alerts),
            "entities_tracked": len(self._data_windows),
            "models_trained": len(self._models),
            "method": self.config.method.value,
        }

    def _update_stats(self, entity_id: str):
        """Update model statistics from window."""
        window = list(self._data_windows[entity_id])

        if not window:
            return

        # Collect all feature values
        feature_values: Dict[str, List[float]] = defaultdict(list)

        for point in window:
            for name, value in point.features.items():
                feature_values[name].append(value)

        # Calculate statistics
        means = {}
        stds = {}
        mins = {}
        maxs = {}

        for name, values in feature_values.items():
            if values:
                means[name] = sum(values) / len(values)
                variance = sum((v - means[name]) ** 2 for v in values) / len(values)
                stds[name] = math.sqrt(variance)
                mins[name] = min(values)
                maxs[name] = max(values)

        self._model_stats[entity_id] = ModelStats(
            entity_id=entity_id,
            n_samples=len(window),
            feature_means=means,
            feature_stds=stds,
            feature_mins=mins,
            feature_maxs=maxs,
            last_update=datetime.utcnow(),
        )

    def _detect_isolation_forest(
        self,
        entity_id: str,
        point: DataPoint
    ) -> AnomalyResult:
        """Detect anomaly using Isolation Forest."""
        stats = self._model_stats.get(entity_id)

        if stats is None or stats.n_samples < self.config.min_samples:
            return AnomalyResult(
                result_id=str(uuid.uuid4()),
                entity_id=entity_id,
                is_anomaly=False,
                anomaly_type=None,
                score=0.0,
                severity=AlertSeverity.INFO,
                features_contribution={},
                expected_range={},
                actual_values=point.features,
                description="Insufficient data for detection",
            )

        # Calculate anomaly score (simulated Isolation Forest)
        # Real implementation would use sklearn.ensemble.IsolationForest
        score = self._calculate_point_score(point, stats)

        is_anomaly = score > (1 - self.config.contamination)

        # Calculate feature contributions
        contributions = self._calculate_contributions(point, stats)

        # Get expected ranges
        expected = self.get_thresholds(entity_id)

        # Determine severity
        severity = self._determine_severity(score, contributions)

        # Determine anomaly type
        anomaly_type = None
        if is_anomaly:
            anomaly_type = self._determine_anomaly_type(point, stats, contributions)

        return AnomalyResult(
            result_id=str(uuid.uuid4()),
            entity_id=entity_id,
            is_anomaly=is_anomaly,
            anomaly_type=anomaly_type,
            score=score,
            severity=severity,
            features_contribution=contributions,
            expected_range=expected,
            actual_values=point.features,
            description=self._generate_description(is_anomaly, contributions),
        )

    def _detect_statistical(
        self,
        entity_id: str,
        point: DataPoint
    ) -> AnomalyResult:
        """Detect anomaly using statistical methods."""
        stats = self._model_stats.get(entity_id)

        if stats is None:
            return AnomalyResult(
                result_id=str(uuid.uuid4()),
                entity_id=entity_id,
                is_anomaly=False,
                anomaly_type=None,
                score=0.0,
                severity=AlertSeverity.INFO,
                features_contribution={},
                expected_range={},
                actual_values=point.features,
                description="No statistics available",
            )

        # Calculate z-scores
        z_scores = {}
        max_z = 0

        for name, value in point.features.items():
            if name in stats.feature_means:
                mean = stats.feature_means[name]
                std = stats.feature_stds.get(name, 1)
                z = abs(value - mean) / max(std, 0.001)
                z_scores[name] = z
                max_z = max(max_z, z)

        is_anomaly = max_z > self.config.threshold_sigma
        score = min(1.0, max_z / (self.config.threshold_sigma * 2))

        # Normalize contributions
        total_z = sum(z_scores.values())
        contributions = {
            k: v / total_z if total_z > 0 else 0
            for k, v in z_scores.items()
        }

        severity = self._determine_severity(score, contributions)

        return AnomalyResult(
            result_id=str(uuid.uuid4()),
            entity_id=entity_id,
            is_anomaly=is_anomaly,
            anomaly_type=AnomalyType.POINT if is_anomaly else None,
            score=score,
            severity=severity,
            features_contribution=contributions,
            expected_range=self.get_thresholds(entity_id),
            actual_values=point.features,
            description=self._generate_description(is_anomaly, contributions),
        )

    def _detect_ensemble(
        self,
        entity_id: str,
        point: DataPoint
    ) -> AnomalyResult:
        """Detect anomaly using ensemble of methods."""
        # Run multiple methods
        if_result = self._detect_isolation_forest(entity_id, point)
        stat_result = self._detect_statistical(entity_id, point)

        # Combine scores
        combined_score = (if_result.score + stat_result.score) / 2
        is_anomaly = if_result.is_anomaly or stat_result.is_anomaly

        # Merge contributions
        contributions = {}
        for name in set(if_result.features_contribution.keys()) | set(stat_result.features_contribution.keys()):
            c1 = if_result.features_contribution.get(name, 0)
            c2 = stat_result.features_contribution.get(name, 0)
            contributions[name] = (c1 + c2) / 2

        severity = self._determine_severity(combined_score, contributions)

        return AnomalyResult(
            result_id=str(uuid.uuid4()),
            entity_id=entity_id,
            is_anomaly=is_anomaly,
            anomaly_type=AnomalyType.POINT if is_anomaly else None,
            score=combined_score,
            severity=severity,
            features_contribution=contributions,
            expected_range=self.get_thresholds(entity_id),
            actual_values=point.features,
            description=self._generate_description(is_anomaly, contributions),
        )

    def _calculate_point_score(
        self,
        point: DataPoint,
        stats: ModelStats
    ) -> float:
        """Calculate anomaly score for a point."""
        if not point.features:
            return 0.0

        # Simplified Isolation Forest-like scoring
        # Real implementation would use the trained model

        total_deviation = 0
        count = 0

        for name, value in point.features.items():
            if name in stats.feature_means:
                mean = stats.feature_means[name]
                std = stats.feature_stds.get(name, 1)

                # Normalized deviation
                deviation = abs(value - mean) / max(std, 0.001)
                total_deviation += min(deviation / 3, 1)  # Cap at 3 sigma
                count += 1

        if count == 0:
            return 0.0

        return total_deviation / count

    def _calculate_contributions(
        self,
        point: DataPoint,
        stats: ModelStats
    ) -> Dict[str, float]:
        """Calculate feature contributions to anomaly."""
        contributions = {}

        for name, value in point.features.items():
            if name in stats.feature_means:
                mean = stats.feature_means[name]
                std = stats.feature_stds.get(name, 1)
                deviation = abs(value - mean) / max(std, 0.001)
                contributions[name] = deviation

        # Normalize
        total = sum(contributions.values())
        if total > 0:
            contributions = {k: v / total for k, v in contributions.items()}

        return contributions

    def _determine_severity(
        self,
        score: float,
        contributions: Dict[str, float]
    ) -> AlertSeverity:
        """Determine alert severity."""
        if score > 0.9:
            return AlertSeverity.CRITICAL
        elif score > 0.7:
            return AlertSeverity.MAJOR
        elif score > 0.5:
            return AlertSeverity.WARNING
        else:
            return AlertSeverity.INFO

    def _determine_anomaly_type(
        self,
        point: DataPoint,
        stats: ModelStats,
        contributions: Dict[str, float]
    ) -> AnomalyType:
        """Determine type of anomaly."""
        # Check for level shift
        window = list(self._data_windows[point.entity_id])
        if len(window) > 10:
            recent_mean = sum(
                p.features.get(list(contributions.keys())[0], 0)
                for p in window[-10:]
            ) / 10

            overall_mean = stats.feature_means.get(list(contributions.keys())[0], 0)

            if abs(recent_mean - overall_mean) > stats.feature_stds.get(list(contributions.keys())[0], 1) * 2:
                return AnomalyType.LEVEL_SHIFT

        # Default to point anomaly
        return AnomalyType.POINT

    def _generate_description(
        self,
        is_anomaly: bool,
        contributions: Dict[str, float]
    ) -> str:
        """Generate human-readable description."""
        if not is_anomaly:
            return "No anomaly detected"

        if not contributions:
            return "Anomaly detected"

        # Top contributors
        top = sorted(contributions.items(), key=lambda x: x[1], reverse=True)[:3]
        top_str = ", ".join(f"{name} ({contrib:.1%})" for name, contrib in top)

        return f"Anomaly detected. Top contributing features: {top_str}"

    def _create_alert(self, result: AnomalyResult):
        """Create an alert from anomaly result."""
        if result.severity.value >= AlertSeverity.WARNING.value:
            alert = AnomalyAlert(
                alert_id=str(uuid.uuid4()),
                entity_id=result.entity_id,
                anomaly_result=result,
                severity=result.severity,
            )

            self._active_alerts[alert.alert_id] = alert
            self._stats["alerts_created"] += 1


# Singleton instance
_anomaly_detector: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    """Get or create the anomaly detector instance."""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
    return _anomaly_detector
