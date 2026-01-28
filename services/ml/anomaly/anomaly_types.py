"""
LEGO Factory v3 - Anomaly Types and Definitions
================================================
Type definitions for anomaly detection including severity levels,
categories, and configuration structures.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Optional, Dict, Any, List
import uuid


class AnomalySeverity(IntEnum):
    """
    Anomaly severity levels aligned with ISA-18.2 alarm priorities.

    Higher values indicate more severe anomalies that require
    immediate attention.
    """
    INFO = 1           # Informational - pattern deviation detected
    LOW = 2            # Low severity - minor deviation from normal
    MEDIUM = 3         # Medium severity - significant deviation
    HIGH = 4           # High severity - major anomaly requiring attention
    CRITICAL = 5       # Critical - immediate action required

    @property
    def alarm_priority(self) -> int:
        """Map to ISA-18.2 alarm priority (1=Emergency, 4=Low)."""
        mapping = {
            AnomalySeverity.INFO: 4,      # LOW priority alarm
            AnomalySeverity.LOW: 4,       # LOW priority alarm
            AnomalySeverity.MEDIUM: 3,    # MEDIUM priority alarm
            AnomalySeverity.HIGH: 2,      # HIGH priority alarm
            AnomalySeverity.CRITICAL: 1,  # EMERGENCY priority alarm
        }
        return mapping[self]

    @classmethod
    def from_score(cls, score: float) -> 'AnomalySeverity':
        """Determine severity from anomaly score (0-1)."""
        if score >= 0.95:
            return cls.CRITICAL
        elif score >= 0.85:
            return cls.HIGH
        elif score >= 0.70:
            return cls.MEDIUM
        elif score >= 0.50:
            return cls.LOW
        else:
            return cls.INFO


class AnomalyCategory(str, Enum):
    """
    Categories of anomalies based on the pattern detected.

    Each category represents a different type of abnormal behavior
    in the sensor data.
    """
    SPIKE = "spike"              # Sudden sharp increase/decrease
    DRIFT = "drift"              # Gradual shift from baseline
    FLATLINE = "flatline"        # Unexpected constant value
    OUT_OF_RANGE = "out_of_range"  # Value outside valid range
    OSCILLATION = "oscillation"  # Abnormal oscillation pattern
    NOISE = "noise"              # Unusual noise level
    RATE_OF_CHANGE = "rate_of_change"  # Abnormal rate of change
    PATTERN = "pattern"          # ML-detected pattern anomaly
    CORRELATION = "correlation"  # Unexpected correlation break
    MISSING_DATA = "missing_data"  # Data gaps or missing values

    @property
    def description(self) -> str:
        """Human-readable description of the anomaly category."""
        descriptions = {
            AnomalyCategory.SPIKE: "Sudden sharp change in value",
            AnomalyCategory.DRIFT: "Gradual shift from normal baseline",
            AnomalyCategory.FLATLINE: "Unexpected constant value",
            AnomalyCategory.OUT_OF_RANGE: "Value outside expected range",
            AnomalyCategory.OSCILLATION: "Abnormal oscillation pattern",
            AnomalyCategory.NOISE: "Unusual noise or variance level",
            AnomalyCategory.RATE_OF_CHANGE: "Value changing too quickly",
            AnomalyCategory.PATTERN: "ML model detected abnormal pattern",
            AnomalyCategory.CORRELATION: "Break in expected correlations",
            AnomalyCategory.MISSING_DATA: "Missing or invalid data points",
        }
        return descriptions.get(self, "Unknown anomaly type")

    @property
    def recommended_action(self) -> str:
        """Suggested action for this anomaly type."""
        actions = {
            AnomalyCategory.SPIKE: "Check for sensor malfunction or process upset",
            AnomalyCategory.DRIFT: "Investigate gradual process degradation or calibration drift",
            AnomalyCategory.FLATLINE: "Verify sensor is functioning; check for frozen readings",
            AnomalyCategory.OUT_OF_RANGE: "Verify sensor calibration and process limits",
            AnomalyCategory.OSCILLATION: "Check control loop tuning and mechanical issues",
            AnomalyCategory.NOISE: "Inspect sensor wiring and signal conditioning",
            AnomalyCategory.RATE_OF_CHANGE: "Investigate rapid process changes",
            AnomalyCategory.PATTERN: "Review ML model insights for root cause",
            AnomalyCategory.CORRELATION: "Check related equipment and sensors",
            AnomalyCategory.MISSING_DATA: "Check communication links and data collection",
        }
        return actions.get(self, "Investigate the anomaly")


class AnomalyType(str, Enum):
    """
    Specific types of anomaly detection methods.
    """
    # Statistical methods
    ZSCORE = "zscore"                  # Z-score based detection
    IQR = "iqr"                        # Interquartile range detection
    MODIFIED_ZSCORE = "modified_zscore"  # MAD-based robust z-score
    GRUBBS = "grubbs"                  # Grubbs test for outliers

    # Threshold methods
    THRESHOLD_HIGH = "threshold_high"  # Value above high threshold
    THRESHOLD_LOW = "threshold_low"    # Value below low threshold
    THRESHOLD_BAND = "threshold_band"  # Value outside band

    # Pattern methods
    ISOLATION_FOREST = "isolation_forest"  # Isolation forest anomaly
    ML_MODEL = "ml_model"              # Neural network based detection
    AUTOENCODER = "autoencoder"        # Reconstruction error based

    # Time-series methods
    SEASONAL = "seasonal"              # Seasonal pattern violation
    TREND = "trend"                    # Trend deviation
    CHANGEPOINT = "changepoint"        # Change point detection


@dataclass
class AnomalyResult:
    """
    Result of anomaly detection for a single data point or window.
    """
    # Identification
    anomaly_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tag_id: str = ""
    tag_name: str = ""

    # Detection results
    is_anomaly: bool = False
    anomaly_score: float = 0.0  # 0-1, higher = more anomalous
    severity: AnomalySeverity = AnomalySeverity.INFO
    category: AnomalyCategory = AnomalyCategory.PATTERN
    detection_type: AnomalyType = AnomalyType.ZSCORE

    # Value information
    value: float = 0.0
    expected_value: Optional[float] = None
    deviation: Optional[float] = None
    threshold_violated: Optional[float] = None

    # Temporal information
    timestamp: datetime = field(default_factory=datetime.utcnow)
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Context
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0  # 0-1, confidence in detection

    # Related data
    related_tags: List[str] = field(default_factory=list)
    context_values: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'anomaly_id': self.anomaly_id,
            'tag_id': self.tag_id,
            'tag_name': self.tag_name,
            'is_anomaly': self.is_anomaly,
            'anomaly_score': self.anomaly_score,
            'severity': self.severity.name,
            'severity_value': self.severity.value,
            'category': self.category.value,
            'category_description': self.category.description,
            'detection_type': self.detection_type.value,
            'value': self.value,
            'expected_value': self.expected_value,
            'deviation': self.deviation,
            'threshold_violated': self.threshold_violated,
            'timestamp': self.timestamp.isoformat(),
            'window_start': self.window_start.isoformat() if self.window_start else None,
            'window_end': self.window_end.isoformat() if self.window_end else None,
            'duration_seconds': self.duration_seconds,
            'message': self.message,
            'details': self.details,
            'confidence': self.confidence,
            'related_tags': self.related_tags,
            'context_values': self.context_values,
            'recommended_action': self.category.recommended_action,
        }


@dataclass
class ThresholdConfig:
    """
    Configuration for threshold-based anomaly detection.
    """
    # Absolute thresholds
    high_high: Optional[float] = None  # Critical high
    high: Optional[float] = None       # Warning high
    low: Optional[float] = None        # Warning low
    low_low: Optional[float] = None    # Critical low

    # Statistical thresholds
    zscore_threshold: float = 3.0      # Standard deviations for z-score
    iqr_multiplier: float = 1.5        # IQR multiplier for outlier detection

    # Rate of change thresholds
    max_rate_of_change: Optional[float] = None  # Max allowed change per second

    # Flatline detection
    flatline_threshold: float = 0.001  # Minimum variance to detect flatline
    flatline_duration_seconds: float = 60.0  # Duration to trigger flatline

    # Spike detection
    spike_threshold: float = 5.0       # Z-score threshold for spike detection
    spike_duration_seconds: float = 5.0  # Max duration to consider a spike

    # Deadband
    deadband: float = 0.0              # Value change below this is ignored

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'high_high': self.high_high,
            'high': self.high,
            'low': self.low,
            'low_low': self.low_low,
            'zscore_threshold': self.zscore_threshold,
            'iqr_multiplier': self.iqr_multiplier,
            'max_rate_of_change': self.max_rate_of_change,
            'flatline_threshold': self.flatline_threshold,
            'flatline_duration_seconds': self.flatline_duration_seconds,
            'spike_threshold': self.spike_threshold,
            'spike_duration_seconds': self.spike_duration_seconds,
            'deadband': self.deadband,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ThresholdConfig':
        """Create from dictionary."""
        return cls(
            high_high=data.get('high_high'),
            high=data.get('high'),
            low=data.get('low'),
            low_low=data.get('low_low'),
            zscore_threshold=data.get('zscore_threshold', 3.0),
            iqr_multiplier=data.get('iqr_multiplier', 1.5),
            max_rate_of_change=data.get('max_rate_of_change'),
            flatline_threshold=data.get('flatline_threshold', 0.001),
            flatline_duration_seconds=data.get('flatline_duration_seconds', 60.0),
            spike_threshold=data.get('spike_threshold', 5.0),
            spike_duration_seconds=data.get('spike_duration_seconds', 5.0),
            deadband=data.get('deadband', 0.0),
        )


@dataclass
class AnomalyConfig:
    """
    Complete configuration for anomaly detection service.
    """
    # General settings
    enabled: bool = True
    detection_interval_seconds: float = 1.0

    # Window settings for statistical detection
    window_size: int = 100             # Number of samples in sliding window
    min_samples: int = 30              # Minimum samples before detection

    # ML model settings
    ml_threshold: float = 0.7          # Threshold for ML-based detection
    use_ml_detection: bool = True
    ml_model_name: str = "mm_dtae_lstm"

    # Statistical settings
    use_statistical_detection: bool = True
    zscore_threshold: float = 3.0
    iqr_multiplier: float = 1.5

    # Threshold-based settings
    use_threshold_detection: bool = True

    # Pattern detection
    use_pattern_detection: bool = True
    pattern_sequence_length: int = 64

    # Severity thresholds
    severity_thresholds: Dict[str, float] = field(default_factory=lambda: {
        'critical': 0.95,
        'high': 0.85,
        'medium': 0.70,
        'low': 0.50,
    })

    # Per-tag configurations
    tag_configs: Dict[str, ThresholdConfig] = field(default_factory=dict)

    # Alarm generation
    generate_alarms: bool = True
    alarm_cooldown_seconds: float = 60.0  # Minimum time between alarms for same anomaly

    def get_tag_config(self, tag_id: str) -> ThresholdConfig:
        """Get threshold config for a specific tag, or default."""
        if tag_id in self.tag_configs:
            return self.tag_configs[tag_id]
        return ThresholdConfig(zscore_threshold=self.zscore_threshold)

    def set_tag_config(self, tag_id: str, config: ThresholdConfig):
        """Set threshold config for a specific tag."""
        self.tag_configs[tag_id] = config

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'enabled': self.enabled,
            'detection_interval_seconds': self.detection_interval_seconds,
            'window_size': self.window_size,
            'min_samples': self.min_samples,
            'ml_threshold': self.ml_threshold,
            'use_ml_detection': self.use_ml_detection,
            'ml_model_name': self.ml_model_name,
            'use_statistical_detection': self.use_statistical_detection,
            'zscore_threshold': self.zscore_threshold,
            'iqr_multiplier': self.iqr_multiplier,
            'use_threshold_detection': self.use_threshold_detection,
            'use_pattern_detection': self.use_pattern_detection,
            'pattern_sequence_length': self.pattern_sequence_length,
            'severity_thresholds': self.severity_thresholds,
            'tag_configs': {k: v.to_dict() for k, v in self.tag_configs.items()},
            'generate_alarms': self.generate_alarms,
            'alarm_cooldown_seconds': self.alarm_cooldown_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnomalyConfig':
        """Create from dictionary."""
        tag_configs = {}
        for tag_id, cfg in data.get('tag_configs', {}).items():
            tag_configs[tag_id] = ThresholdConfig.from_dict(cfg)

        return cls(
            enabled=data.get('enabled', True),
            detection_interval_seconds=data.get('detection_interval_seconds', 1.0),
            window_size=data.get('window_size', 100),
            min_samples=data.get('min_samples', 30),
            ml_threshold=data.get('ml_threshold', 0.7),
            use_ml_detection=data.get('use_ml_detection', True),
            ml_model_name=data.get('ml_model_name', 'mm_dtae_lstm'),
            use_statistical_detection=data.get('use_statistical_detection', True),
            zscore_threshold=data.get('zscore_threshold', 3.0),
            iqr_multiplier=data.get('iqr_multiplier', 1.5),
            use_threshold_detection=data.get('use_threshold_detection', True),
            use_pattern_detection=data.get('use_pattern_detection', True),
            pattern_sequence_length=data.get('pattern_sequence_length', 64),
            severity_thresholds=data.get('severity_thresholds', {
                'critical': 0.95, 'high': 0.85, 'medium': 0.70, 'low': 0.50
            }),
            tag_configs=tag_configs,
            generate_alarms=data.get('generate_alarms', True),
            alarm_cooldown_seconds=data.get('alarm_cooldown_seconds', 60.0),
        )


# Type aliases for common use
AnomalyResults = List[AnomalyResult]
TagThresholds = Dict[str, ThresholdConfig]
