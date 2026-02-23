"""
LEGO Factory v3 - Anomaly Detection Service
============================================
Machine learning-based anomaly detection for SCADA sensor data.
Uses statistical methods and pattern recognition to identify unusual behavior.
"""

import math
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

from services.scada.alarm_management.alarm_service import (
    AlarmEvent, AlarmStatus, alarm_processor, _emit_alarm_event
)

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of detected anomalies"""
    POINT_ANOMALY = 'point_anomaly'  # Single unusual value
    CONTEXTUAL_ANOMALY = 'contextual_anomaly'  # Unusual given context
    COLLECTIVE_ANOMALY = 'collective_anomaly'  # Unusual pattern/sequence
    LEVEL_SHIFT = 'level_shift'  # Sudden change in baseline
    VARIANCE_CHANGE = 'variance_change'  # Change in variability
    PERIODIC_ANOMALY = 'periodic_anomaly'  # Deviation from expected cycle


@dataclass
class AnomalyDetection:
    """Result of anomaly detection"""
    anomaly_id: str
    tag_id: str
    tag_name: str
    anomaly_type: AnomalyType
    score: float  # 0-1 anomaly score
    confidence: float  # 0-1 confidence
    value: float
    expected_value: float
    deviation: float
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'anomaly_id': self.anomaly_id,
            'tag_id': self.tag_id,
            'tag_name': self.tag_name,
            'anomaly_type': self.anomaly_type.value,
            'score': self.score,
            'confidence': self.confidence,
            'value': self.value,
            'expected_value': self.expected_value,
            'deviation': self.deviation,
            'timestamp': self.timestamp.isoformat(),
            'context': self.context
        }


@dataclass
class SensorProfile:
    """Statistical profile for a sensor"""
    tag_id: str

    # Historical statistics (long-term)
    long_term_mean: float = 0.0
    long_term_std: float = 0.0
    long_term_min: float = float('inf')
    long_term_max: float = float('-inf')

    # Recent statistics (short-term)
    short_term_mean: float = 0.0
    short_term_std: float = 0.0

    # Value history
    values: deque = field(default_factory=lambda: deque(maxlen=1000))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=1000))

    # For CUSUM change detection
    cusum_pos: float = 0.0
    cusum_neg: float = 0.0

    # For EWMA smoothing
    ewma_value: float = 0.0

    # Training status
    is_trained: bool = False
    training_samples: int = 0
    min_training_samples: int = 100


class AnomalyDetectionService:
    """
    Machine learning-based anomaly detection for sensor data.

    Uses multiple detection methods:
    1. Statistical (Z-score, IQR)
    2. CUSUM (Cumulative Sum) for change detection
    3. EWMA (Exponentially Weighted Moving Average) for trend detection
    4. Pattern matching for periodic anomalies
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize service"""
        # Sensor profiles
        self._profiles: Dict[str, SensorProfile] = {}

        # Active anomalies
        self._active_anomalies: Dict[str, AnomalyDetection] = {}

        # Configuration
        self._config = {
            'z_score_threshold': 3.0,  # Standard deviations for point anomaly
            'iqr_multiplier': 1.5,  # IQR multiplier for outlier detection
            'cusum_threshold': 5.0,  # CUSUM detection threshold
            'ewma_alpha': 0.2,  # EWMA smoothing factor
            'min_confidence': 0.7,  # Minimum confidence to report anomaly
            'level_shift_window': 20,  # Window for detecting level shifts
            'variance_change_window': 50,  # Window for detecting variance changes
        }

        logger.info("AnomalyDetectionService initialized")

    def configure(self, config: Dict[str, Any]):
        """Update configuration"""
        self._config.update(config)
        logger.info(f"AnomalyDetectionService configured: {config}")

    def analyze(
        self,
        tag_id: str,
        tag_name: str,
        value: float,
        timestamp: datetime = None
    ) -> List[AnomalyDetection]:
        """
        Analyze a sensor value for anomalies.

        Args:
            tag_id: Sensor identifier
            tag_name: Human-readable name
            value: Current value
            timestamp: Value timestamp

        Returns:
            List of detected anomalies (may be empty)
        """
        timestamp = timestamp or datetime.utcnow()
        anomalies = []

        # Get or create profile
        if tag_id not in self._profiles:
            self._profiles[tag_id] = SensorProfile(tag_id=tag_id)

        profile = self._profiles[tag_id]

        # Add value to history
        profile.values.append(value)
        profile.timestamps.append(timestamp)

        # Update training if not trained
        if not profile.is_trained:
            self._update_training(profile, value)
            if not profile.is_trained:
                return []  # Not enough data yet

        # Run detection methods
        detections = [
            self._detect_point_anomaly(profile, tag_name, value, timestamp),
            self._detect_level_shift(profile, tag_name, value, timestamp),
            self._detect_variance_change(profile, tag_name, value, timestamp),
            self._detect_cusum_change(profile, tag_name, value, timestamp),
        ]

        for detection in detections:
            if detection and detection.confidence >= self._config['min_confidence']:
                anomalies.append(detection)
                self._active_anomalies[detection.anomaly_id] = detection

                # Submit to alarm system as ML alarm
                self._submit_ml_alarm(detection)

        # Update profile statistics
        self._update_statistics(profile, value)

        return anomalies

    def _update_training(self, profile: SensorProfile, value: float):
        """Update training statistics"""
        profile.training_samples += 1

        # Online mean/variance calculation (Welford's algorithm)
        if profile.training_samples == 1:
            profile.long_term_mean = value
            profile.long_term_std = 0.0
        else:
            delta = value - profile.long_term_mean
            profile.long_term_mean += delta / profile.training_samples

            if profile.training_samples > 1:
                delta2 = value - profile.long_term_mean
                m2 = profile.long_term_std ** 2 * (profile.training_samples - 2) + delta * delta2
                profile.long_term_std = math.sqrt(m2 / (profile.training_samples - 1))

        profile.long_term_min = min(profile.long_term_min, value)
        profile.long_term_max = max(profile.long_term_max, value)

        # Initialize EWMA
        if profile.training_samples == 1:
            profile.ewma_value = value

        if profile.training_samples >= profile.min_training_samples:
            profile.is_trained = True
            profile.short_term_mean = profile.long_term_mean
            profile.short_term_std = profile.long_term_std
            logger.info(f"Sensor {profile.tag_id} trained with {profile.training_samples} samples")

    def _update_statistics(self, profile: SensorProfile, value: float):
        """Update running statistics after anomaly detection"""
        # Update EWMA
        alpha = self._config['ewma_alpha']
        profile.ewma_value = alpha * value + (1 - alpha) * profile.ewma_value

        # Update short-term statistics with recent window
        recent = list(profile.values)[-50:]
        if len(recent) >= 10:
            profile.short_term_mean = sum(recent) / len(recent)
            variance = sum((x - profile.short_term_mean) ** 2 for x in recent) / len(recent)
            profile.short_term_std = math.sqrt(variance) if variance > 0 else 0.0

    def _detect_point_anomaly(
        self,
        profile: SensorProfile,
        tag_name: str,
        value: float,
        timestamp: datetime
    ) -> Optional[AnomalyDetection]:
        """Detect point anomalies using Z-score and IQR"""

        if profile.long_term_std == 0:
            return None

        # Z-score method
        z_score = abs(value - profile.long_term_mean) / profile.long_term_std
        z_threshold = self._config['z_score_threshold']

        # IQR method (approximate from std)
        # For normal distribution: IQR ≈ 1.35 * std
        iqr_estimate = 1.35 * profile.long_term_std
        q1 = profile.long_term_mean - 0.675 * profile.long_term_std
        q3 = profile.long_term_mean + 0.675 * profile.long_term_std
        iqr_lower = q1 - self._config['iqr_multiplier'] * iqr_estimate
        iqr_upper = q3 + self._config['iqr_multiplier'] * iqr_estimate

        is_z_anomaly = z_score > z_threshold
        is_iqr_anomaly = value < iqr_lower or value > iqr_upper

        if not (is_z_anomaly or is_iqr_anomaly):
            return None

        # Calculate anomaly score (0-1)
        score = min(z_score / (z_threshold * 2), 1.0)

        # Confidence based on agreement of methods and sample size
        confidence = 0.5
        if is_z_anomaly:
            confidence += 0.25
        if is_iqr_anomaly:
            confidence += 0.25

        return AnomalyDetection(
            anomaly_id=f"point_{profile.tag_id}_{int(timestamp.timestamp())}",
            tag_id=profile.tag_id,
            tag_name=tag_name,
            anomaly_type=AnomalyType.POINT_ANOMALY,
            score=score,
            confidence=confidence,
            value=value,
            expected_value=profile.long_term_mean,
            deviation=z_score,
            timestamp=timestamp,
            context={
                'z_score': z_score,
                'threshold': z_threshold,
                'mean': profile.long_term_mean,
                'std': profile.long_term_std,
                'methods_triggered': {
                    'z_score': is_z_anomaly,
                    'iqr': is_iqr_anomaly
                }
            }
        )

    def _detect_level_shift(
        self,
        profile: SensorProfile,
        tag_name: str,
        value: float,
        timestamp: datetime
    ) -> Optional[AnomalyDetection]:
        """Detect sudden level shifts in the data"""

        window = self._config['level_shift_window']
        values = list(profile.values)

        if len(values) < window * 2:
            return None

        # Compare recent window to previous window
        recent = values[-window:]
        previous = values[-window*2:-window]

        recent_mean = sum(recent) / len(recent)
        previous_mean = sum(previous) / len(previous)

        # Calculate pooled standard deviation
        recent_var = sum((x - recent_mean) ** 2 for x in recent) / len(recent)
        previous_var = sum((x - previous_mean) ** 2 for x in previous) / len(previous)
        pooled_std = math.sqrt((recent_var + previous_var) / 2)

        if pooled_std == 0:
            return None

        # Calculate shift magnitude in standard deviations
        shift_magnitude = abs(recent_mean - previous_mean) / pooled_std

        if shift_magnitude < 2.0:  # Less than 2 std shift
            return None

        # Anomaly score based on shift magnitude
        score = min(shift_magnitude / 4.0, 1.0)

        # Confidence based on consistency within windows
        confidence = 0.8 if shift_magnitude > 3.0 else 0.6

        return AnomalyDetection(
            anomaly_id=f"shift_{profile.tag_id}_{int(timestamp.timestamp())}",
            tag_id=profile.tag_id,
            tag_name=tag_name,
            anomaly_type=AnomalyType.LEVEL_SHIFT,
            score=score,
            confidence=confidence,
            value=value,
            expected_value=previous_mean,
            deviation=shift_magnitude,
            timestamp=timestamp,
            context={
                'previous_mean': previous_mean,
                'recent_mean': recent_mean,
                'shift_std': shift_magnitude,
                'direction': 'increase' if recent_mean > previous_mean else 'decrease'
            }
        )

    def _detect_variance_change(
        self,
        profile: SensorProfile,
        tag_name: str,
        value: float,
        timestamp: datetime
    ) -> Optional[AnomalyDetection]:
        """Detect changes in process variability"""

        window = self._config['variance_change_window']
        values = list(profile.values)

        if len(values) < window * 2:
            return None

        # Compare variance of recent vs previous
        recent = values[-window:]
        previous = values[-window*2:-window]

        recent_mean = sum(recent) / len(recent)
        previous_mean = sum(previous) / len(previous)

        recent_var = sum((x - recent_mean) ** 2 for x in recent) / len(recent)
        previous_var = sum((x - previous_mean) ** 2 for x in previous) / len(previous)

        if previous_var == 0:
            return None

        # F-ratio for variance comparison
        variance_ratio = recent_var / previous_var if previous_var > 0 else 0

        # Significant change if ratio > 2 or < 0.5
        if 0.5 <= variance_ratio <= 2.0:
            return None

        score = min(abs(math.log(variance_ratio)) / 2.0, 1.0)
        confidence = 0.7 if variance_ratio > 3.0 or variance_ratio < 0.33 else 0.6

        return AnomalyDetection(
            anomaly_id=f"variance_{profile.tag_id}_{int(timestamp.timestamp())}",
            tag_id=profile.tag_id,
            tag_name=tag_name,
            anomaly_type=AnomalyType.VARIANCE_CHANGE,
            score=score,
            confidence=confidence,
            value=value,
            expected_value=profile.long_term_mean,
            deviation=variance_ratio,
            timestamp=timestamp,
            context={
                'previous_variance': previous_var,
                'recent_variance': recent_var,
                'variance_ratio': variance_ratio,
                'direction': 'increased' if variance_ratio > 1 else 'decreased'
            }
        )

    def _detect_cusum_change(
        self,
        profile: SensorProfile,
        tag_name: str,
        value: float,
        timestamp: datetime
    ) -> Optional[AnomalyDetection]:
        """Detect changes using CUSUM algorithm"""

        if profile.long_term_std == 0:
            return None

        # Normalize the value
        normalized = (value - profile.long_term_mean) / profile.long_term_std

        # Update CUSUM statistics
        # Detect upward shifts
        profile.cusum_pos = max(0, profile.cusum_pos + normalized - 0.5)
        # Detect downward shifts
        profile.cusum_neg = max(0, profile.cusum_neg - normalized - 0.5)

        threshold = self._config['cusum_threshold']

        if profile.cusum_pos <= threshold and profile.cusum_neg <= threshold:
            return None

        # Determine which direction triggered
        direction = 'upward' if profile.cusum_pos > threshold else 'downward'
        cusum_value = max(profile.cusum_pos, profile.cusum_neg)

        score = min(cusum_value / (threshold * 2), 1.0)
        confidence = 0.75

        # Reset CUSUM after detection
        if profile.cusum_pos > threshold:
            profile.cusum_pos = 0
        if profile.cusum_neg > threshold:
            profile.cusum_neg = 0

        return AnomalyDetection(
            anomaly_id=f"cusum_{profile.tag_id}_{int(timestamp.timestamp())}",
            tag_id=profile.tag_id,
            tag_name=tag_name,
            anomaly_type=AnomalyType.COLLECTIVE_ANOMALY,
            score=score,
            confidence=confidence,
            value=value,
            expected_value=profile.long_term_mean,
            deviation=cusum_value,
            timestamp=timestamp,
            context={
                'cusum_positive': profile.cusum_pos,
                'cusum_negative': profile.cusum_neg,
                'threshold': threshold,
                'direction': direction,
                'method': 'CUSUM'
            }
        )

    def _submit_ml_alarm(self, detection: AnomalyDetection):
        """Submit anomaly detection as ML alarm to the alarm processor"""
        try:
            # Map anomaly severity to alarm priority
            if detection.score >= 0.8:
                priority = 2  # HIGH
            elif detection.score >= 0.5:
                priority = 3  # MEDIUM
            else:
                priority = 4  # LOW

            alarm_event = AlarmEvent(
                instance_id=detection.anomaly_id,
                alarm_id=f"ml_{detection.tag_id}",
                tag_id=detection.tag_id,
                tag_name=detection.tag_name,
                alarm_type='ml_anomaly',
                priority=priority,
                status=AlarmStatus.ACTIVE_UNACKED.value,
                message=(f"ML anomaly detected: {detection.anomaly_type.value}. "
                        f"Score: {detection.score:.2f}, "
                        f"Value: {detection.value:.2f}, "
                        f"Expected: {detection.expected_value:.2f}"),
                value=detection.value,
                limit_value=detection.expected_value,
                timestamp=detection.timestamp,
                consequence=f"Anomaly type: {detection.anomaly_type.value}",
                corrective_action="Investigate sensor and process conditions"
            )

            # Submit to alarm processor
            alarm_processor.submit_ml_alarm(alarm_event)

            logger.info(
                f"ML alarm submitted: {detection.tag_name} - "
                f"{detection.anomaly_type.value} (score: {detection.score:.2f})"
            )

        except Exception as e:
            logger.error(f"Failed to submit ML alarm: {e}")

    def get_active_anomalies(
        self,
        tag_id: str = None,
        anomaly_type: AnomalyType = None,
        min_score: float = None
    ) -> List[AnomalyDetection]:
        """Get active anomalies with optional filtering"""
        anomalies = list(self._active_anomalies.values())

        if tag_id:
            anomalies = [a for a in anomalies if a.tag_id == tag_id]
        if anomaly_type:
            anomalies = [a for a in anomalies if a.anomaly_type == anomaly_type]
        if min_score:
            anomalies = [a for a in anomalies if a.score >= min_score]

        return sorted(anomalies, key=lambda a: a.score, reverse=True)

    def clear_anomaly(self, anomaly_id: str):
        """Clear an anomaly (when resolved)"""
        if anomaly_id in self._active_anomalies:
            anomaly = self._active_anomalies.pop(anomaly_id)

            # Clear corresponding ML alarm
            alarm_processor.clear_ml_alarm(f"ml_{anomaly.tag_id}")

            logger.info(f"Anomaly cleared: {anomaly_id}")

    def get_sensor_profile(self, tag_id: str) -> Optional[Dict[str, Any]]:
        """Get the learned profile for a sensor"""
        if tag_id not in self._profiles:
            return None

        profile = self._profiles[tag_id]
        return {
            'tag_id': tag_id,
            'is_trained': profile.is_trained,
            'training_samples': profile.training_samples,
            'long_term_mean': profile.long_term_mean,
            'long_term_std': profile.long_term_std,
            'long_term_min': profile.long_term_min,
            'long_term_max': profile.long_term_max,
            'short_term_mean': profile.short_term_mean,
            'short_term_std': profile.short_term_std,
            'ewma_value': profile.ewma_value,
            'sample_count': len(profile.values)
        }

    def reset_sensor_profile(self, tag_id: str):
        """Reset learned profile for a sensor"""
        if tag_id in self._profiles:
            del self._profiles[tag_id]
            logger.info(f"Sensor profile reset: {tag_id}")


# Global service instance
anomaly_detection_service = AnomalyDetectionService()


def get_anomaly_detection_service() -> AnomalyDetectionService:
    """Get the anomaly detection service singleton"""
    return anomaly_detection_service
