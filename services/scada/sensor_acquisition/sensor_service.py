"""
LEGO Factory v3 - Sensor Data Acquisition Service
==================================================
Collects real-time sensor data from machines and stores in historian.

Supports:
- Machine position sensors (X, Y, Z, A, B, C axes)
- Temperature sensors (spindle, bed, nozzle, ambient)
- Vibration sensors (accelerometer data)
- Current/voltage sensors (spindle motor)
- Pressure sensors (coolant, pneumatic)
- Tool sensors (touch probe, tool setter)
- Custom/generic sensors
"""

import asyncio
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Tuple

logger = logging.getLogger(__name__)


class SensorType(Enum):
    """Types of sensors."""
    POSITION = 'position'
    TEMPERATURE = 'temperature'
    VIBRATION = 'vibration'
    CURRENT = 'current'
    VOLTAGE = 'voltage'
    PRESSURE = 'pressure'
    FLOW = 'flow'
    FORCE = 'force'
    SPEED = 'speed'  # RPM, feed rate
    PROXIMITY = 'proximity'
    PROBE = 'probe'
    ENCODER = 'encoder'
    STRAIN = 'strain'
    HUMIDITY = 'humidity'
    ACOUSTIC = 'acoustic'  # Sound/ultrasonic
    GENERIC = 'generic'


class DataQuality(Enum):
    """OPC UA inspired data quality."""
    GOOD = 'good'
    GOOD_LOCAL_OVERRIDE = 'good_local_override'
    UNCERTAIN = 'uncertain'
    UNCERTAIN_SENSOR_CAL = 'uncertain_sensor_cal'
    BAD = 'bad'
    BAD_SENSOR_FAILURE = 'bad_sensor_failure'
    BAD_COMMUNICATION = 'bad_communication'
    BAD_OUT_OF_SERVICE = 'bad_out_of_service'


class AggregationType(Enum):
    """Time-series aggregation methods."""
    RAW = 'raw'
    AVERAGE = 'average'
    MIN = 'min'
    MAX = 'max'
    SUM = 'sum'
    COUNT = 'count'
    FIRST = 'first'
    LAST = 'last'
    RANGE = 'range'
    DELTA = 'delta'
    STDDEV = 'stddev'


@dataclass
class SensorConfig:
    """Sensor configuration."""
    sensor_id: str
    name: str
    sensor_type: SensorType
    machine_id: str
    unit: str
    description: str = ""

    # Sampling
    sample_rate_hz: float = 10.0  # Samples per second
    enabled: bool = True

    # Scaling
    raw_min: float = 0.0
    raw_max: float = 4095.0  # 12-bit ADC
    eng_min: float = 0.0
    eng_max: float = 100.0

    # Alarm limits
    alarm_high_high: Optional[float] = None
    alarm_high: Optional[float] = None
    alarm_low: Optional[float] = None
    alarm_low_low: Optional[float] = None
    deadband: float = 0.0

    # Historian
    log_to_historian: bool = True
    compression_deviation: float = 0.0  # % change to log
    max_time_between_logs: float = 60.0  # seconds

    def scale_value(self, raw_value: float) -> float:
        """Scale raw value to engineering units."""
        if self.raw_max == self.raw_min:
            return self.eng_min
        ratio = (raw_value - self.raw_min) / (self.raw_max - self.raw_min)
        return self.eng_min + ratio * (self.eng_max - self.eng_min)


@dataclass
class SensorReading:
    """A single sensor reading."""
    sensor_id: str
    timestamp: datetime
    value: float
    quality: DataQuality = DataQuality.GOOD
    raw_value: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'sensor_id': self.sensor_id,
            'timestamp': self.timestamp.isoformat(),
            'value': self.value,
            'quality': self.quality.value,
            'raw_value': self.raw_value,
        }


@dataclass
class SensorStatistics:
    """Rolling statistics for a sensor."""
    sensor_id: str
    count: int = 0
    sum_value: float = 0.0
    sum_squared: float = 0.0
    min_value: float = float('inf')
    max_value: float = float('-inf')
    last_value: float = 0.0
    last_timestamp: Optional[datetime] = None
    window_start: Optional[datetime] = None

    @property
    def mean(self) -> float:
        return self.sum_value / self.count if self.count > 0 else 0.0

    @property
    def variance(self) -> float:
        if self.count < 2:
            return 0.0
        return (self.sum_squared - (self.sum_value ** 2 / self.count)) / (self.count - 1)

    @property
    def stddev(self) -> float:
        return self.variance ** 0.5

    @property
    def range(self) -> float:
        return self.max_value - self.min_value if self.count > 0 else 0.0

    def update(self, value: float, timestamp: datetime):
        """Update statistics with new value."""
        if self.window_start is None:
            self.window_start = timestamp

        self.count += 1
        self.sum_value += value
        self.sum_squared += value ** 2
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)
        self.last_value = value
        self.last_timestamp = timestamp

    def reset(self):
        """Reset statistics."""
        self.count = 0
        self.sum_value = 0.0
        self.sum_squared = 0.0
        self.min_value = float('inf')
        self.max_value = float('-inf')
        self.window_start = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'sensor_id': self.sensor_id,
            'count': self.count,
            'mean': self.mean,
            'min': self.min_value if self.count > 0 else None,
            'max': self.max_value if self.count > 0 else None,
            'stddev': self.stddev,
            'range': self.range,
            'last_value': self.last_value,
            'last_timestamp': self.last_timestamp.isoformat() if self.last_timestamp else None,
        }


class SensorService:
    """
    Central sensor data acquisition service.

    Collects data from all registered sensors and:
    - Buffers readings for batch processing
    - Calculates rolling statistics
    - Logs to historian with compression
    - Triggers alarms on threshold violations
    - Publishes to real-time subscribers
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Sensor configurations
        self._sensors: Dict[str, SensorConfig] = {}

        # Current readings
        self._readings: Dict[str, SensorReading] = {}

        # Statistics
        self._statistics: Dict[str, SensorStatistics] = {}

        # Buffers for historian logging
        self._log_buffer: Dict[str, deque] = {}
        self._last_logged: Dict[str, Tuple[float, datetime]] = {}

        # Subscribers
        self._subscribers: List[Callable[[SensorReading], None]] = []
        self._alarm_callbacks: List[Callable[[str, str, float], None]] = []

        # Collection threads
        self._running = False
        self._collection_threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

        # Historian reference
        self._historian = None

        self._initialized = True
        logger.info("SensorService initialized")

    def register_sensor(self, config: SensorConfig) -> None:
        """Register a sensor for data collection."""
        with self._lock:
            self._sensors[config.sensor_id] = config
            self._statistics[config.sensor_id] = SensorStatistics(sensor_id=config.sensor_id)
            self._log_buffer[config.sensor_id] = deque(maxlen=1000)

        logger.info(f"Registered sensor: {config.sensor_id} ({config.sensor_type.value})")

    def unregister_sensor(self, sensor_id: str) -> None:
        """Unregister a sensor."""
        with self._lock:
            self._sensors.pop(sensor_id, None)
            self._statistics.pop(sensor_id, None)
            self._readings.pop(sensor_id, None)
            self._log_buffer.pop(sensor_id, None)

    def get_sensor(self, sensor_id: str) -> Optional[SensorConfig]:
        """Get sensor configuration."""
        return self._sensors.get(sensor_id)

    def list_sensors(self, machine_id: str = None) -> List[Dict[str, Any]]:
        """List all registered sensors."""
        sensors = []
        for sensor_id, config in self._sensors.items():
            if machine_id and config.machine_id != machine_id:
                continue
            sensors.append({
                'sensor_id': config.sensor_id,
                'name': config.name,
                'sensor_type': config.sensor_type.value,
                'machine_id': config.machine_id,
                'unit': config.unit,
                'enabled': config.enabled,
                'sample_rate_hz': config.sample_rate_hz,
            })
        return sensors

    def record_reading(
        self,
        sensor_id: str,
        value: float,
        timestamp: datetime = None,
        quality: DataQuality = DataQuality.GOOD,
        raw_value: float = None
    ) -> None:
        """Record a sensor reading."""
        config = self._sensors.get(sensor_id)
        if not config or not config.enabled:
            return

        ts = timestamp or datetime.now()

        # Scale if raw value provided
        if raw_value is not None:
            value = config.scale_value(raw_value)

        reading = SensorReading(
            sensor_id=sensor_id,
            timestamp=ts,
            value=value,
            quality=quality,
            raw_value=raw_value
        )

        with self._lock:
            # Store current reading
            self._readings[sensor_id] = reading

            # Update statistics
            self._statistics[sensor_id].update(value, ts)

            # Check if should log to historian
            if config.log_to_historian:
                self._check_and_log(config, reading)

        # Check alarms
        self._check_alarms(config, value)

        # Notify subscribers
        for subscriber in self._subscribers:
            try:
                subscriber(reading)
            except Exception as e:
                logger.error(f"Subscriber error: {e}")

    def _check_and_log(self, config: SensorConfig, reading: SensorReading) -> None:
        """Check if reading should be logged to historian (swinging door compression)."""
        sensor_id = config.sensor_id
        last = self._last_logged.get(sensor_id)

        should_log = False

        if last is None:
            # First reading
            should_log = True
        else:
            last_value, last_time = last
            time_diff = (reading.timestamp - last_time).total_seconds()

            # Log if max time exceeded
            if time_diff >= config.max_time_between_logs:
                should_log = True
            # Log if value changed beyond deviation threshold
            elif config.compression_deviation > 0:
                if last_value != 0:
                    pct_change = abs(reading.value - last_value) / abs(last_value) * 100
                else:
                    pct_change = 100 if reading.value != 0 else 0

                if pct_change >= config.compression_deviation:
                    should_log = True
            else:
                # No compression, log everything
                should_log = True

        if should_log:
            self._log_buffer[sensor_id].append(reading)
            self._last_logged[sensor_id] = (reading.value, reading.timestamp)

    def _check_alarms(self, config: SensorConfig, value: float) -> None:
        """Check alarm thresholds."""
        alarms = []

        if config.alarm_high_high is not None and value >= config.alarm_high_high:
            alarms.append(('high_high', config.alarm_high_high))
        elif config.alarm_high is not None and value >= config.alarm_high:
            alarms.append(('high', config.alarm_high))

        if config.alarm_low_low is not None and value <= config.alarm_low_low:
            alarms.append(('low_low', config.alarm_low_low))
        elif config.alarm_low is not None and value <= config.alarm_low:
            alarms.append(('low', config.alarm_low))

        for alarm_type, setpoint in alarms:
            for callback in self._alarm_callbacks:
                try:
                    callback(config.sensor_id, alarm_type, value)
                except Exception as e:
                    logger.error(f"Alarm callback error: {e}")

    def get_reading(self, sensor_id: str) -> Optional[SensorReading]:
        """Get latest reading for a sensor."""
        return self._readings.get(sensor_id)

    def get_all_readings(self, machine_id: str = None) -> Dict[str, Dict]:
        """Get all current readings."""
        readings = {}
        for sensor_id, reading in self._readings.items():
            config = self._sensors.get(sensor_id)
            if machine_id and config and config.machine_id != machine_id:
                continue
            readings[sensor_id] = reading.to_dict()
        return readings

    def get_statistics(self, sensor_id: str) -> Optional[SensorStatistics]:
        """Get statistics for a sensor."""
        return self._statistics.get(sensor_id)

    def get_all_statistics(self) -> Dict[str, Dict]:
        """Get all sensor statistics."""
        return {sid: stats.to_dict() for sid, stats in self._statistics.items()}

    def reset_statistics(self, sensor_id: str = None) -> None:
        """Reset statistics for one or all sensors."""
        if sensor_id:
            if sensor_id in self._statistics:
                self._statistics[sensor_id].reset()
        else:
            for stats in self._statistics.values():
                stats.reset()

    def subscribe(self, callback: Callable[[SensorReading], None]) -> None:
        """Subscribe to real-time sensor updates."""
        self._subscribers.append(callback)

    def on_alarm(self, callback: Callable[[str, str, float], None]) -> None:
        """Register alarm callback (sensor_id, alarm_type, value)."""
        self._alarm_callbacks.append(callback)

    def flush_to_historian(self) -> int:
        """Flush buffered readings to historian."""
        if not self._historian:
            try:
                from services.scada.historian import get_historian_service
                self._historian = get_historian_service()
            except Exception as e:
                logger.warning(f"Historian not available: {e}")
                return 0

        total_logged = 0

        for sensor_id, buffer in self._log_buffer.items():
            if not buffer:
                continue

            readings = list(buffer)
            buffer.clear()

            try:
                # Log to historian
                for reading in readings:
                    self._historian.log_tag_value(
                        tag_name=sensor_id,
                        value=reading.value,
                        timestamp=reading.timestamp,
                        quality=reading.quality.value
                    )
                    total_logged += 1
            except Exception as e:
                logger.error(f"Failed to log {sensor_id} to historian: {e}")
                # Put readings back in buffer
                buffer.extend(readings)

        return total_logged

    # =========================================================================
    # Machine Integration
    # =========================================================================

    def register_machine_sensors(self, machine_id: str, machine_config: Dict) -> None:
        """
        Automatically register standard sensors for a machine.

        Creates sensors for position, feed rate, spindle, etc.
        """
        machine_type = machine_config.get('machine_type', 'generic')
        controller_type = machine_config.get('controller_type', 'generic')

        # Position sensors (all CNC machines)
        for axis in ['x', 'y', 'z']:
            self.register_sensor(SensorConfig(
                sensor_id=f"{machine_id}.pos_{axis}",
                name=f"{axis.upper()} Position",
                sensor_type=SensorType.POSITION,
                machine_id=machine_id,
                unit='mm',
                sample_rate_hz=50.0,
                alarm_high=machine_config.get(f'work_envelope_{axis}', 1000),
                alarm_low=0,
            ))

        # Feed rate sensor
        self.register_sensor(SensorConfig(
            sensor_id=f"{machine_id}.feed_rate",
            name="Feed Rate",
            sensor_type=SensorType.SPEED,
            machine_id=machine_id,
            unit='mm/min',
            sample_rate_hz=10.0,
            alarm_high=machine_config.get('max_feed_rate', 5000),
        ))

        # Spindle speed sensor (if applicable)
        if machine_type in ['cnc_mill', 'cnc_router', 'cnc_lathe']:
            self.register_sensor(SensorConfig(
                sensor_id=f"{machine_id}.spindle_speed",
                name="Spindle Speed",
                sensor_type=SensorType.SPEED,
                machine_id=machine_id,
                unit='RPM',
                sample_rate_hz=10.0,
                alarm_high=machine_config.get('max_spindle_rpm', 24000),
            ))

            # Spindle load/current
            self.register_sensor(SensorConfig(
                sensor_id=f"{machine_id}.spindle_load",
                name="Spindle Load",
                sensor_type=SensorType.CURRENT,
                machine_id=machine_id,
                unit='%',
                sample_rate_hz=50.0,
                alarm_high=90.0,
                alarm_high_high=100.0,
            ))

        # Temperature sensors for 3D printers
        if machine_type == 'printer_3d':
            self.register_sensor(SensorConfig(
                sensor_id=f"{machine_id}.temp_nozzle",
                name="Nozzle Temperature",
                sensor_type=SensorType.TEMPERATURE,
                machine_id=machine_id,
                unit='°C',
                sample_rate_hz=1.0,
                alarm_high=300.0,
                alarm_high_high=320.0,
            ))

            self.register_sensor(SensorConfig(
                sensor_id=f"{machine_id}.temp_bed",
                name="Bed Temperature",
                sensor_type=SensorType.TEMPERATURE,
                machine_id=machine_id,
                unit='°C',
                sample_rate_hz=1.0,
                alarm_high=120.0,
            ))

        # Robot arm sensors
        if machine_type == 'robot_arm':
            for joint in range(1, 7):  # 6-axis robot
                self.register_sensor(SensorConfig(
                    sensor_id=f"{machine_id}.joint_{joint}_pos",
                    name=f"Joint {joint} Position",
                    sensor_type=SensorType.ENCODER,
                    machine_id=machine_id,
                    unit='deg',
                    sample_rate_hz=100.0,
                ))

                self.register_sensor(SensorConfig(
                    sensor_id=f"{machine_id}.joint_{joint}_torque",
                    name=f"Joint {joint} Torque",
                    sensor_type=SensorType.FORCE,
                    machine_id=machine_id,
                    unit='Nm',
                    sample_rate_hz=100.0,
                ))

        logger.info(f"Registered standard sensors for {machine_id} ({machine_type})")

    def update_from_machine_status(self, machine_id: str, status: Dict) -> None:
        """
        Update sensors from machine status report.

        Called when machine controller reports new status.
        """
        timestamp = datetime.now()

        # Position
        if 'position' in status:
            pos = status['position']
            if 'x' in pos:
                self.record_reading(f"{machine_id}.pos_x", pos['x'], timestamp)
            if 'y' in pos:
                self.record_reading(f"{machine_id}.pos_y", pos['y'], timestamp)
            if 'z' in pos:
                self.record_reading(f"{machine_id}.pos_z", pos['z'], timestamp)

        # Feed rate
        if 'feed_rate' in status:
            self.record_reading(f"{machine_id}.feed_rate", status['feed_rate'], timestamp)

        # Spindle
        if 'spindle_speed' in status:
            self.record_reading(f"{machine_id}.spindle_speed", status['spindle_speed'], timestamp)

        if 'spindle_load' in status:
            self.record_reading(f"{machine_id}.spindle_load", status['spindle_load'], timestamp)

        # Temperatures (3D printer)
        if 'nozzle_temp' in status:
            self.record_reading(f"{machine_id}.temp_nozzle", status['nozzle_temp'], timestamp)

        if 'bed_temp' in status:
            self.record_reading(f"{machine_id}.temp_bed", status['bed_temp'], timestamp)

        # Joint positions (robot)
        if 'joint_positions' in status:
            for i, pos in enumerate(status['joint_positions'], 1):
                self.record_reading(f"{machine_id}.joint_{i}_pos", pos, timestamp)

        if 'joint_torques' in status:
            for i, torque in enumerate(status['joint_torques'], 1):
                self.record_reading(f"{machine_id}.joint_{i}_torque", torque, timestamp)

    # =========================================================================
    # Background Collection
    # =========================================================================

    def start_collection(self) -> None:
        """Start background data collection."""
        self._running = True

        # Start historian flush thread
        flush_thread = threading.Thread(target=self._historian_flush_loop, daemon=True)
        flush_thread.start()

        logger.info("Sensor collection started")

    def stop_collection(self) -> None:
        """Stop background data collection."""
        self._running = False
        logger.info("Sensor collection stopped")

    def _historian_flush_loop(self) -> None:
        """Background thread to periodically flush to historian."""
        while self._running:
            try:
                count = self.flush_to_historian()
                if count > 0:
                    logger.debug(f"Flushed {count} readings to historian")
            except Exception as e:
                logger.error(f"Historian flush error: {e}")

            time.sleep(1.0)  # Flush every second


# Global instance
_sensor_service: Optional[SensorService] = None


def get_sensor_service() -> SensorService:
    """Get the global sensor service instance."""
    global _sensor_service
    if _sensor_service is None:
        _sensor_service = SensorService()
    return _sensor_service
