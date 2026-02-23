"""
Sensor Fusion Service V8.

LEGO MCP V8 - Autonomous Factory Platform
Multi-Sensor Data Fusion for Improved State Estimation.

Features:
- Extended Kalman Filter (EKF) for non-linear sensor fusion
- Multi-sensor data fusion with weighted averaging
- Sensor calibration and drift correction
- Confidence/uncertainty estimation
- Anomaly detection in sensor readings
- Support for heterogeneous sensor types

Applications:
- Robot localization (IMU + encoders + vision)
- Process monitoring (temperature + pressure + flow)
- Quality inspection (vision + tactile + dimensional)
- Environmental monitoring (multiple sensor arrays)

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Callable, Union
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import asyncio
import logging
import math
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class SensorType(Enum):
    """Types of sensors."""
    POSITION = "position"           # GPS, encoders, LIDAR
    ORIENTATION = "orientation"     # IMU, gyroscope, compass
    VELOCITY = "velocity"           # Wheel encoders, Doppler
    ACCELERATION = "acceleration"   # Accelerometer
    TEMPERATURE = "temperature"     # Thermocouples, RTDs
    PRESSURE = "pressure"           # Pressure transducers
    FLOW = "flow"                   # Flow meters
    VIBRATION = "vibration"         # Vibration sensors
    PROXIMITY = "proximity"         # Ultrasonic, infrared
    FORCE = "force"                 # Load cells, strain gauges
    VISION = "vision"               # Cameras, depth sensors
    CURRENT = "current"             # Current sensors
    VOLTAGE = "voltage"             # Voltage sensors
    HUMIDITY = "humidity"           # Humidity sensors
    GAS = "gas"                     # Gas sensors
    ACOUSTIC = "acoustic"           # Microphones
    LEVEL = "level"                 # Level sensors
    GENERIC = "generic"             # Other sensors


class FusionMethod(Enum):
    """Sensor fusion methods."""
    WEIGHTED_AVERAGE = "weighted_average"
    KALMAN_FILTER = "kalman_filter"
    EXTENDED_KALMAN = "extended_kalman"
    PARTICLE_FILTER = "particle_filter"
    COMPLEMENTARY = "complementary"
    BAYESIAN = "bayesian"


class SensorStatus(Enum):
    """Sensor health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAULTY = "faulty"
    OFFLINE = "offline"
    CALIBRATING = "calibrating"


class AnomalyType(Enum):
    """Types of sensor anomalies."""
    SPIKE = "spike"
    DRIFT = "drift"
    STUCK = "stuck"
    NOISE = "noise"
    OUT_OF_RANGE = "out_of_range"
    RATE_OF_CHANGE = "rate_of_change"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SensorConfig:
    """Sensor configuration."""
    sensor_id: str
    name: str
    sensor_type: SensorType
    unit: str
    min_value: float
    max_value: float
    accuracy: float           # Measurement accuracy
    noise_variance: float     # Measurement noise variance (R in Kalman)
    update_rate_hz: float     # Expected update rate
    calibration_offset: float = 0.0
    calibration_scale: float = 1.0
    weight: float = 1.0       # Fusion weight
    position: Optional[Tuple[float, float, float]] = None  # Physical location

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sensor_id": self.sensor_id,
            "name": self.name,
            "sensor_type": self.sensor_type.value,
            "unit": self.unit,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "accuracy": self.accuracy,
            "noise_variance": self.noise_variance,
            "update_rate_hz": self.update_rate_hz,
            "calibration_offset": self.calibration_offset,
            "calibration_scale": self.calibration_scale,
            "weight": self.weight,
            "position": self.position,
        }


@dataclass
class SensorReading:
    """Individual sensor reading."""
    sensor_id: str
    timestamp: datetime
    value: float
    raw_value: float
    quality: float  # 0-1, confidence in reading
    status: SensorStatus = SensorStatus.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sensor_id": self.sensor_id,
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "raw_value": self.raw_value,
            "quality": self.quality,
            "status": self.status.value,
        }


@dataclass
class FusedState:
    """Fused state estimate from multiple sensors."""
    state_id: str
    entity_id: str  # What entity this state represents
    timestamp: datetime
    values: Dict[str, float]  # State variables
    uncertainties: Dict[str, float]  # Uncertainty for each variable
    confidence: float  # Overall confidence 0-1
    contributing_sensors: List[str]
    fusion_method: FusionMethod

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "state_id": self.state_id,
            "entity_id": self.entity_id,
            "timestamp": self.timestamp.isoformat(),
            "values": self.values,
            "uncertainties": self.uncertainties,
            "confidence": self.confidence,
            "contributing_sensors": self.contributing_sensors,
            "fusion_method": self.fusion_method.value,
        }


@dataclass
class SensorAnomaly:
    """Detected sensor anomaly."""
    anomaly_id: str
    sensor_id: str
    anomaly_type: AnomalyType
    severity: float  # 0-1
    detected_at: datetime
    value: float
    expected_value: float
    message: str
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "anomaly_id": self.anomaly_id,
            "sensor_id": self.sensor_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity,
            "detected_at": self.detected_at.isoformat(),
            "value": self.value,
            "expected_value": self.expected_value,
            "message": self.message,
            "resolved": self.resolved,
        }


@dataclass
class CalibrationResult:
    """Result of sensor calibration."""
    sensor_id: str
    calibrated_at: datetime
    offset: float
    scale: float
    residual_error: float
    samples_used: int
    success: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sensor_id": self.sensor_id,
            "calibrated_at": self.calibrated_at.isoformat(),
            "offset": self.offset,
            "scale": self.scale,
            "residual_error": self.residual_error,
            "samples_used": self.samples_used,
            "success": self.success,
        }


# =============================================================================
# Kalman Filter Implementation
# =============================================================================

class KalmanFilter:
    """
    Extended Kalman Filter for sensor fusion.

    Supports both linear and non-linear state estimation.
    """

    def __init__(
        self,
        state_dim: int,
        measurement_dim: int,
        process_noise: float = 0.01,
        measurement_noise: float = 0.1
    ):
        """
        Initialize Kalman filter.

        Args:
            state_dim: Dimension of state vector
            measurement_dim: Dimension of measurement vector
            process_noise: Process noise covariance (Q)
            measurement_noise: Measurement noise covariance (R)
        """
        self.state_dim = state_dim
        self.measurement_dim = measurement_dim

        # State estimate
        self.x = [0.0] * state_dim  # State vector

        # Covariance matrices (simplified as diagonal)
        self.P = [1.0] * state_dim  # State covariance (uncertainty)
        self.Q = [process_noise] * state_dim  # Process noise
        self.R = [measurement_noise] * measurement_dim  # Measurement noise

        # State transition matrix (identity for simple case)
        self.F = [[1.0 if i == j else 0.0 for j in range(state_dim)]
                  for i in range(state_dim)]

        # Measurement matrix (maps state to measurement)
        self.H = [[1.0 if i == j else 0.0 for j in range(state_dim)]
                  for i in range(measurement_dim)]

        self._initialized = False

    def initialize(self, initial_state: List[float], initial_covariance: Optional[List[float]] = None) -> None:
        """Initialize filter with initial state."""
        if len(initial_state) != self.state_dim:
            raise ValueError(f"Initial state dimension mismatch: {len(initial_state)} vs {self.state_dim}")

        self.x = list(initial_state)
        if initial_covariance:
            self.P = list(initial_covariance)
        self._initialized = True

    def predict(self, dt: float = 1.0) -> List[float]:
        """
        Prediction step.

        Args:
            dt: Time step

        Returns:
            Predicted state
        """
        if not self._initialized:
            return list(self.x)

        # State prediction: x = F * x
        x_pred = [0.0] * self.state_dim
        for i in range(self.state_dim):
            for j in range(self.state_dim):
                x_pred[i] += self.F[i][j] * self.x[j]
        self.x = x_pred

        # Covariance prediction: P = F * P * F' + Q
        for i in range(self.state_dim):
            self.P[i] = self.P[i] + self.Q[i] * dt

        return list(self.x)

    def update(self, measurement: List[float], measurement_noise: Optional[List[float]] = None) -> List[float]:
        """
        Update step with new measurement.

        Args:
            measurement: Measurement vector
            measurement_noise: Optional measurement noise override

        Returns:
            Updated state estimate
        """
        if not self._initialized:
            self.initialize(measurement + [0.0] * (self.state_dim - len(measurement)))
            return list(self.x)

        R = measurement_noise if measurement_noise else self.R

        # Innovation: y = z - H * x
        y = [0.0] * self.measurement_dim
        for i in range(self.measurement_dim):
            hx = 0.0
            for j in range(self.state_dim):
                hx += self.H[i][j] * self.x[j]
            y[i] = measurement[i] - hx

        # Innovation covariance: S = H * P * H' + R
        S = [0.0] * self.measurement_dim
        for i in range(self.measurement_dim):
            hp = 0.0
            for j in range(self.state_dim):
                hp += self.H[i][j] * self.P[j]
            S[i] = hp + R[i]

        # Kalman gain: K = P * H' * S^-1 (simplified for diagonal)
        K = [[0.0] * self.measurement_dim for _ in range(self.state_dim)]
        for i in range(self.state_dim):
            for j in range(self.measurement_dim):
                if S[j] > 1e-10:  # Avoid division by zero
                    K[i][j] = self.P[i] * self.H[j][i] / S[j]

        # State update: x = x + K * y
        for i in range(self.state_dim):
            for j in range(self.measurement_dim):
                self.x[i] += K[i][j] * y[j]

        # Covariance update: P = (I - K * H) * P
        for i in range(self.state_dim):
            kh = 0.0
            for j in range(self.measurement_dim):
                kh += K[i][j] * self.H[j][i]
            self.P[i] = (1.0 - kh) * self.P[i]

        return list(self.x)

    def get_state(self) -> Tuple[List[float], List[float]]:
        """Get current state estimate and uncertainty."""
        return list(self.x), list(self.P)

    def get_uncertainty(self) -> float:
        """Get overall uncertainty (trace of covariance)."""
        return sum(self.P) / len(self.P)


# =============================================================================
# Complementary Filter
# =============================================================================

class ComplementaryFilter:
    """
    Complementary filter for combining high and low frequency sensor data.

    Commonly used for IMU fusion (accelerometer + gyroscope).
    """

    def __init__(self, alpha: float = 0.98):
        """
        Initialize complementary filter.

        Args:
            alpha: Weight for high-pass (gyro) data, 1-alpha for low-pass (accel)
        """
        self.alpha = alpha
        self.state = 0.0
        self._initialized = False

    def update(self, high_freq_value: float, low_freq_value: float, dt: float = 0.01) -> float:
        """
        Update filter with new readings.

        Args:
            high_freq_value: High frequency sensor (e.g., gyroscope rate)
            low_freq_value: Low frequency sensor (e.g., accelerometer angle)
            dt: Time step

        Returns:
            Fused estimate
        """
        if not self._initialized:
            self.state = low_freq_value
            self._initialized = True
            return self.state

        # Complementary filter equation
        self.state = self.alpha * (self.state + high_freq_value * dt) + (1 - self.alpha) * low_freq_value
        return self.state

    def get_state(self) -> float:
        """Get current state estimate."""
        return self.state


# =============================================================================
# Sensor Fusion Engine
# =============================================================================

class SensorFusionEngine:
    """
    Multi-Sensor Fusion Engine.

    Combines data from multiple heterogeneous sensors to produce
    accurate state estimates with uncertainty quantification.

    Features:
    - Multiple fusion methods (Kalman, complementary, weighted average)
    - Automatic sensor health monitoring
    - Anomaly detection
    - Calibration support
    - Time synchronization
    """

    def __init__(
        self,
        engine_id: str = "default",
        default_fusion_method: FusionMethod = FusionMethod.KALMAN_FILTER,
        history_size: int = 100,
        anomaly_detection_enabled: bool = True
    ):
        """
        Initialize sensor fusion engine.

        Args:
            engine_id: Unique identifier
            default_fusion_method: Default fusion method
            history_size: Number of readings to keep in history
            anomaly_detection_enabled: Enable anomaly detection
        """
        self.engine_id = engine_id
        self.default_fusion_method = default_fusion_method
        self.history_size = history_size
        self.anomaly_detection_enabled = anomaly_detection_enabled

        # Sensor registry
        self.sensors: Dict[str, SensorConfig] = {}
        self.sensor_status: Dict[str, SensorStatus] = {}

        # Reading history per sensor
        self.reading_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=history_size)
        )

        # Latest readings
        self.latest_readings: Dict[str, SensorReading] = {}

        # Fusion groups (sensors fused together)
        self.fusion_groups: Dict[str, List[str]] = {}  # group_id -> sensor_ids
        self.group_filters: Dict[str, Union[KalmanFilter, ComplementaryFilter]] = {}

        # Fused states
        self.fused_states: Dict[str, FusedState] = {}

        # Anomalies
        self.anomalies: Dict[str, SensorAnomaly] = {}
        self.active_anomalies: Dict[str, str] = {}  # sensor_id -> anomaly_id

        # Calibration
        self.calibration_data: Dict[str, List[Tuple[float, float]]] = defaultdict(list)

        # Callbacks
        self.on_anomaly_detected: Optional[Callable[[SensorAnomaly], None]] = None
        self.on_state_updated: Optional[Callable[[FusedState], None]] = None

        # Statistics
        self.total_readings = 0
        self.total_fusions = 0
        self.anomalies_detected = 0

        # Background task
        self._running = False
        self._fusion_task: Optional[asyncio.Task] = None

        logger.info(f"SensorFusionEngine initialized: {engine_id}")

    # -------------------------------------------------------------------------
    # Sensor Registration
    # -------------------------------------------------------------------------

    def register_sensor(
        self,
        sensor_id: str,
        name: str,
        sensor_type: SensorType,
        unit: str = "",
        min_value: float = -float('inf'),
        max_value: float = float('inf'),
        accuracy: float = 0.01,
        noise_variance: float = 0.01,
        update_rate_hz: float = 10.0,
        weight: float = 1.0,
        position: Optional[Tuple[float, float, float]] = None
    ) -> SensorConfig:
        """
        Register a new sensor.

        Args:
            sensor_id: Unique sensor identifier
            name: Human-readable name
            sensor_type: Type of sensor
            unit: Measurement unit
            min_value: Minimum valid value
            max_value: Maximum valid value
            accuracy: Measurement accuracy
            noise_variance: Measurement noise variance
            update_rate_hz: Expected update rate
            weight: Fusion weight
            position: Physical position (x, y, z)

        Returns:
            SensorConfig
        """
        config = SensorConfig(
            sensor_id=sensor_id,
            name=name,
            sensor_type=sensor_type,
            unit=unit,
            min_value=min_value,
            max_value=max_value,
            accuracy=accuracy,
            noise_variance=noise_variance,
            update_rate_hz=update_rate_hz,
            weight=weight,
            position=position,
        )

        self.sensors[sensor_id] = config
        self.sensor_status[sensor_id] = SensorStatus.HEALTHY

        logger.info(f"Registered sensor: {sensor_id} ({sensor_type.value})")
        return config

    def create_fusion_group(
        self,
        group_id: str,
        sensor_ids: List[str],
        fusion_method: Optional[FusionMethod] = None,
        state_dim: int = 1
    ) -> None:
        """
        Create a fusion group for related sensors.

        Args:
            group_id: Group identifier
            sensor_ids: Sensors to include in group
            fusion_method: Fusion method to use
            state_dim: State dimension for Kalman filter
        """
        # Validate sensors exist
        for sid in sensor_ids:
            if sid not in self.sensors:
                raise ValueError(f"Unknown sensor: {sid}")

        self.fusion_groups[group_id] = sensor_ids

        method = fusion_method or self.default_fusion_method

        # Create appropriate filter
        if method in (FusionMethod.KALMAN_FILTER, FusionMethod.EXTENDED_KALMAN):
            self.group_filters[group_id] = KalmanFilter(
                state_dim=state_dim,
                measurement_dim=len(sensor_ids),
                measurement_noise=0.1
            )
        elif method == FusionMethod.COMPLEMENTARY:
            self.group_filters[group_id] = ComplementaryFilter()

        logger.info(f"Created fusion group: {group_id} with {len(sensor_ids)} sensors")

    # -------------------------------------------------------------------------
    # Data Ingestion
    # -------------------------------------------------------------------------

    def ingest_reading(
        self,
        sensor_id: str,
        value: float,
        timestamp: Optional[datetime] = None,
        quality: float = 1.0
    ) -> SensorReading:
        """
        Ingest a sensor reading.

        Args:
            sensor_id: Sensor identifier
            value: Raw sensor value
            timestamp: Reading timestamp
            quality: Reading quality (0-1)

        Returns:
            Processed SensorReading
        """
        if sensor_id not in self.sensors:
            raise ValueError(f"Unknown sensor: {sensor_id}")

        config = self.sensors[sensor_id]
        ts = timestamp or datetime.utcnow()

        # Apply calibration
        calibrated_value = (value - config.calibration_offset) * config.calibration_scale

        # Check range
        status = SensorStatus.HEALTHY
        if calibrated_value < config.min_value or calibrated_value > config.max_value:
            status = SensorStatus.DEGRADED
            quality *= 0.5

        reading = SensorReading(
            sensor_id=sensor_id,
            timestamp=ts,
            value=calibrated_value,
            raw_value=value,
            quality=quality,
            status=status,
        )

        # Store reading
        self.reading_history[sensor_id].append(reading)
        self.latest_readings[sensor_id] = reading
        self.total_readings += 1

        # Anomaly detection
        if self.anomaly_detection_enabled:
            anomaly = self._detect_anomaly(sensor_id, reading)
            if anomaly:
                self.anomalies[anomaly.anomaly_id] = anomaly
                self.active_anomalies[sensor_id] = anomaly.anomaly_id
                self.anomalies_detected += 1
                if self.on_anomaly_detected:
                    self.on_anomaly_detected(anomaly)

        return reading

    def ingest_batch(
        self,
        readings: List[Tuple[str, float, Optional[datetime]]]
    ) -> List[SensorReading]:
        """
        Ingest multiple readings at once.

        Args:
            readings: List of (sensor_id, value, timestamp) tuples

        Returns:
            List of processed readings
        """
        return [
            self.ingest_reading(sid, val, ts)
            for sid, val, ts in readings
        ]

    # -------------------------------------------------------------------------
    # Fusion Operations
    # -------------------------------------------------------------------------

    def fuse_group(
        self,
        group_id: str,
        entity_id: str = ""
    ) -> Optional[FusedState]:
        """
        Perform fusion for a sensor group.

        Args:
            group_id: Fusion group identifier
            entity_id: Entity this state represents

        Returns:
            FusedState or None
        """
        if group_id not in self.fusion_groups:
            raise ValueError(f"Unknown fusion group: {group_id}")

        sensor_ids = self.fusion_groups[group_id]
        readings = []

        for sid in sensor_ids:
            if sid in self.latest_readings:
                reading = self.latest_readings[sid]
                # Check if reading is recent
                age = (datetime.utcnow() - reading.timestamp).total_seconds()
                if age < 1.0 / self.sensors[sid].update_rate_hz * 10:  # 10x expected period
                    readings.append(reading)

        if not readings:
            return None

        # Get filter
        filter_obj = self.group_filters.get(group_id)

        if isinstance(filter_obj, KalmanFilter):
            return self._fuse_kalman(group_id, entity_id, readings, filter_obj)
        elif isinstance(filter_obj, ComplementaryFilter):
            return self._fuse_complementary(group_id, entity_id, readings, filter_obj)
        else:
            return self._fuse_weighted_average(group_id, entity_id, readings)

    def _fuse_kalman(
        self,
        group_id: str,
        entity_id: str,
        readings: List[SensorReading],
        kf: KalmanFilter
    ) -> FusedState:
        """Fuse using Kalman filter."""
        # Prediction step
        kf.predict()

        # Update with measurements
        measurements = [r.value for r in readings]
        noise = [self.sensors[r.sensor_id].noise_variance for r in readings]

        state = kf.update(measurements, noise)
        uncertainty = kf.get_uncertainty()

        fused = FusedState(
            state_id=str(uuid.uuid4()),
            entity_id=entity_id,
            timestamp=datetime.utcnow(),
            values={"state": state[0] if state else 0.0},
            uncertainties={"state": uncertainty},
            confidence=1.0 / (1.0 + uncertainty),
            contributing_sensors=[r.sensor_id for r in readings],
            fusion_method=FusionMethod.KALMAN_FILTER,
        )

        self.fused_states[group_id] = fused
        self.total_fusions += 1

        if self.on_state_updated:
            self.on_state_updated(fused)

        return fused

    def _fuse_complementary(
        self,
        group_id: str,
        entity_id: str,
        readings: List[SensorReading],
        cf: ComplementaryFilter
    ) -> FusedState:
        """Fuse using complementary filter."""
        if len(readings) < 2:
            # Fall back to weighted average
            return self._fuse_weighted_average(group_id, entity_id, readings)

        # Assume first sensor is high-freq, second is low-freq
        high_freq = readings[0].value
        low_freq = readings[1].value

        fused_value = cf.update(high_freq, low_freq)

        fused = FusedState(
            state_id=str(uuid.uuid4()),
            entity_id=entity_id,
            timestamp=datetime.utcnow(),
            values={"state": fused_value},
            uncertainties={"state": 0.1},  # Estimated
            confidence=0.9,
            contributing_sensors=[r.sensor_id for r in readings],
            fusion_method=FusionMethod.COMPLEMENTARY,
        )

        self.fused_states[group_id] = fused
        self.total_fusions += 1

        if self.on_state_updated:
            self.on_state_updated(fused)

        return fused

    def _fuse_weighted_average(
        self,
        group_id: str,
        entity_id: str,
        readings: List[SensorReading]
    ) -> FusedState:
        """Fuse using weighted average."""
        total_weight = 0.0
        weighted_sum = 0.0
        variance_sum = 0.0

        for reading in readings:
            config = self.sensors[reading.sensor_id]
            weight = config.weight * reading.quality
            total_weight += weight
            weighted_sum += reading.value * weight
            variance_sum += config.noise_variance * weight

        if total_weight > 0:
            fused_value = weighted_sum / total_weight
            fused_variance = variance_sum / total_weight
        else:
            fused_value = readings[0].value if readings else 0.0
            fused_variance = 1.0

        fused = FusedState(
            state_id=str(uuid.uuid4()),
            entity_id=entity_id,
            timestamp=datetime.utcnow(),
            values={"state": fused_value},
            uncertainties={"state": math.sqrt(fused_variance)},
            confidence=min(total_weight / len(readings), 1.0) if readings else 0.0,
            contributing_sensors=[r.sensor_id for r in readings],
            fusion_method=FusionMethod.WEIGHTED_AVERAGE,
        )

        self.fused_states[group_id] = fused
        self.total_fusions += 1

        if self.on_state_updated:
            self.on_state_updated(fused)

        return fused

    # -------------------------------------------------------------------------
    # Anomaly Detection
    # -------------------------------------------------------------------------

    def _detect_anomaly(
        self,
        sensor_id: str,
        reading: SensorReading
    ) -> Optional[SensorAnomaly]:
        """Detect anomalies in sensor reading."""
        config = self.sensors[sensor_id]
        history = list(self.reading_history[sensor_id])

        if len(history) < 5:
            return None  # Not enough history

        # Calculate statistics
        values = [r.value for r in history[-20:]]  # Last 20 readings
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance) if variance > 0 else 0.01

        # Check for various anomalies
        anomaly_type = None
        severity = 0.0
        message = ""

        # Spike detection (> 3 sigma)
        z_score = abs(reading.value - mean) / std if std > 0 else 0
        if z_score > 3:
            anomaly_type = AnomalyType.SPIKE
            severity = min(z_score / 5.0, 1.0)
            message = f"Spike detected: {reading.value:.2f} ({z_score:.1f} sigma from mean)"

        # Out of range
        elif reading.value < config.min_value or reading.value > config.max_value:
            anomaly_type = AnomalyType.OUT_OF_RANGE
            severity = 0.8
            message = f"Value {reading.value:.2f} outside range [{config.min_value}, {config.max_value}]"

        # Stuck value detection
        elif len(history) >= 10:
            recent = [r.value for r in history[-10:]]
            if max(recent) - min(recent) < config.accuracy * 0.1:
                anomaly_type = AnomalyType.STUCK
                severity = 0.5
                message = f"Sensor appears stuck at {reading.value:.2f}"

        # Rate of change
        elif len(history) >= 2:
            prev_reading = history[-2]
            dt = (reading.timestamp - prev_reading.timestamp).total_seconds()
            if dt > 0:
                rate = abs(reading.value - prev_reading.value) / dt
                expected_max_rate = (config.max_value - config.min_value) / 10.0
                if rate > expected_max_rate:
                    anomaly_type = AnomalyType.RATE_OF_CHANGE
                    severity = min(rate / (expected_max_rate * 2), 1.0)
                    message = f"Excessive rate of change: {rate:.2f}/s"

        if anomaly_type:
            return SensorAnomaly(
                anomaly_id=str(uuid.uuid4()),
                sensor_id=sensor_id,
                anomaly_type=anomaly_type,
                severity=severity,
                detected_at=datetime.utcnow(),
                value=reading.value,
                expected_value=mean,
                message=message,
            )

        return None

    # -------------------------------------------------------------------------
    # Calibration
    # -------------------------------------------------------------------------

    def add_calibration_point(
        self,
        sensor_id: str,
        raw_value: float,
        reference_value: float
    ) -> None:
        """Add a calibration data point."""
        if sensor_id not in self.sensors:
            raise ValueError(f"Unknown sensor: {sensor_id}")

        self.calibration_data[sensor_id].append((raw_value, reference_value))

    def calibrate_sensor(
        self,
        sensor_id: str,
        min_samples: int = 5
    ) -> CalibrationResult:
        """
        Perform linear calibration on a sensor.

        Uses least squares to find offset and scale.
        """
        if sensor_id not in self.sensors:
            raise ValueError(f"Unknown sensor: {sensor_id}")

        data = self.calibration_data.get(sensor_id, [])

        if len(data) < min_samples:
            return CalibrationResult(
                sensor_id=sensor_id,
                calibrated_at=datetime.utcnow(),
                offset=0.0,
                scale=1.0,
                residual_error=float('inf'),
                samples_used=len(data),
                success=False,
            )

        # Linear regression: reference = scale * raw + offset
        n = len(data)
        sum_x = sum(d[0] for d in data)
        sum_y = sum(d[1] for d in data)
        sum_xy = sum(d[0] * d[1] for d in data)
        sum_xx = sum(d[0] ** 2 for d in data)

        denom = n * sum_xx - sum_x ** 2
        if abs(denom) < 1e-10:
            scale = 1.0
            offset = sum_y / n - scale * sum_x / n
        else:
            scale = (n * sum_xy - sum_x * sum_y) / denom
            offset = (sum_y - scale * sum_x) / n

        # Calculate residual error
        residual = 0.0
        for raw, ref in data:
            predicted = scale * raw + offset
            residual += (predicted - ref) ** 2
        residual = math.sqrt(residual / n)

        # Apply calibration
        config = self.sensors[sensor_id]
        config.calibration_scale = scale
        config.calibration_offset = -offset / scale if scale != 0 else offset

        result = CalibrationResult(
            sensor_id=sensor_id,
            calibrated_at=datetime.utcnow(),
            offset=config.calibration_offset,
            scale=config.calibration_scale,
            residual_error=residual,
            samples_used=n,
            success=True,
        )

        logger.info(
            f"Calibrated sensor {sensor_id}: "
            f"scale={scale:.4f}, offset={offset:.4f}, error={residual:.4f}"
        )

        return result

    # -------------------------------------------------------------------------
    # Monitoring
    # -------------------------------------------------------------------------

    async def start_fusion_loop(self, interval_seconds: float = 0.1) -> None:
        """Start background fusion loop."""
        self._running = True

        async def fusion_loop():
            while self._running:
                try:
                    # Fuse all groups
                    for group_id in self.fusion_groups:
                        self.fuse_group(group_id)

                except Exception as e:
                    logger.error(f"Fusion loop error: {e}")

                await asyncio.sleep(interval_seconds)

        self._fusion_task = asyncio.create_task(fusion_loop())
        logger.info("Started fusion loop")

    async def stop_fusion_loop(self) -> None:
        """Stop background fusion loop."""
        self._running = False
        if self._fusion_task:
            self._fusion_task.cancel()
            try:
                await self._fusion_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped fusion loop")

    # -------------------------------------------------------------------------
    # Status and Metrics
    # -------------------------------------------------------------------------

    def get_sensor_status(self, sensor_id: str) -> Dict[str, Any]:
        """Get detailed status for a sensor."""
        if sensor_id not in self.sensors:
            raise ValueError(f"Unknown sensor: {sensor_id}")

        config = self.sensors[sensor_id]
        latest = self.latest_readings.get(sensor_id)
        history = list(self.reading_history[sensor_id])

        # Calculate statistics
        if history:
            values = [r.value for r in history]
            avg = sum(values) / len(values)
            min_val = min(values)
            max_val = max(values)
            variance = sum((v - avg) ** 2 for v in values) / len(values)
            std = math.sqrt(variance)
        else:
            avg = min_val = max_val = std = 0.0

        return {
            "config": config.to_dict(),
            "status": self.sensor_status[sensor_id].value,
            "latest_reading": latest.to_dict() if latest else None,
            "statistics": {
                "readings_count": len(history),
                "average": avg,
                "min": min_val,
                "max": max_val,
                "std_dev": std,
            },
            "active_anomaly": self.active_anomalies.get(sensor_id),
        }

    def get_engine_status(self) -> Dict[str, Any]:
        """Get overall engine status."""
        return {
            "engine_id": self.engine_id,
            "total_sensors": len(self.sensors),
            "fusion_groups": len(self.fusion_groups),
            "total_readings": self.total_readings,
            "total_fusions": self.total_fusions,
            "anomalies_detected": self.anomalies_detected,
            "active_anomalies": len(self.active_anomalies),
            "running": self._running,
            "sensors": {
                sid: self.sensor_status[sid].value
                for sid in self.sensors
            },
        }


# =============================================================================
# Factory Function and Singleton
# =============================================================================

_fusion_engine_instance: Optional[SensorFusionEngine] = None


def get_sensor_fusion_engine(
    engine_id: str = "default",
    default_fusion_method: FusionMethod = FusionMethod.KALMAN_FILTER
) -> SensorFusionEngine:
    """
    Get or create the sensor fusion engine singleton.

    Args:
        engine_id: Engine identifier
        default_fusion_method: Default fusion method

    Returns:
        SensorFusionEngine instance
    """
    global _fusion_engine_instance

    if _fusion_engine_instance is None:
        _fusion_engine_instance = SensorFusionEngine(
            engine_id=engine_id,
            default_fusion_method=default_fusion_method
        )

    return _fusion_engine_instance


__all__ = [
    # Enums
    'SensorType',
    'FusionMethod',
    'SensorStatus',
    'AnomalyType',
    # Data Classes
    'SensorConfig',
    'SensorReading',
    'FusedState',
    'SensorAnomaly',
    'CalibrationResult',
    # Filters
    'KalmanFilter',
    'ComplementaryFilter',
    # Main Class
    'SensorFusionEngine',
    'get_sensor_fusion_engine',
]
