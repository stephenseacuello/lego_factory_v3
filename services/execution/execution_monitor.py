"""
Execution Monitor for Flask CNC SCADA
=====================================
Monitors job execution with real-time sensor capture and MQTT publishing.

Features:
- Real-time position and status monitoring
- Sensor data aggregation during execution
- MQTT publishing at configurable rates
- InfluxDB logging of execution data
- Anomaly detection hooks

Usage:
    from services.execution.execution_monitor import get_execution_monitor

    monitor = get_execution_monitor()
    monitor.start_monitoring(job_context)
"""

import logging
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from collections import deque

from config import get_config

logger = logging.getLogger(__name__)
config = get_config()


@dataclass
class MonitorData:
    """Aggregated monitoring data."""
    timestamp: float
    # Position
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    # Motion
    velocity: float = 0.0
    feed_rate: float = 0.0
    spindle_speed: float = 0.0
    # Machine state
    machine_state: int = 0  # TinyG stat code
    motion_mode: int = 0    # TinyG momo
    current_line: int = 0
    # Motor currents
    spindle_current: float = 0.0
    x_motor_current: float = 0.0
    y_motor_current: float = 0.0
    z_motor_current: float = 0.0
    # IMU
    vibration_rms: float = 0.0
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    # Environmental
    temperature: float = 0.0
    pressure: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "position": {
                "x": self.position_x,
                "y": self.position_y,
                "z": self.position_z,
            },
            "velocity": self.velocity,
            "feed_rate": self.feed_rate,
            "spindle_speed": self.spindle_speed,
            "machine_state": self.machine_state,
            "current_line": self.current_line,
            "motor_currents": {
                "spindle": self.spindle_current,
                "x": self.x_motor_current,
                "y": self.y_motor_current,
                "z": self.z_motor_current,
            },
            "vibration_rms": self.vibration_rms,
            "temperature": self.temperature,
        }


# Callback type for monitor data
MonitorCallback = Callable[[MonitorData], None]


class ExecutionMonitor:
    """
    Monitors CNC execution with sensor data aggregation.

    Collects data from:
    - TinyG status reports (position, velocity, state)
    - MCC DAQ (motor currents)
    - Arduino sensors (IMU, environmental)

    Publishes to:
    - MQTT for real-time dashboards
    - InfluxDB for historical analysis
    """

    def __init__(self):
        """Initialize execution monitor."""
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Data collection
        self._current_data = MonitorData(timestamp=time.time())
        self._data_history: deque = deque(maxlen=1000)  # Keep last 1000 samples

        # Publish rates
        self._mqtt_rate_hz = 1.0  # 1 Hz for MQTT
        self._influx_rate_hz = 0.1  # 0.1 Hz for InfluxDB (every 10 sec)

        # Callbacks
        self._callbacks: List[MonitorCallback] = []

        # Service references (lazy loaded)
        self._mqtt_service = None
        self._influxdb_service = None
        self._tinyg_controller = None

        # Job context reference
        self._job_context = None

        logger.info("ExecutionMonitor initialized")

    @property
    def mqtt_service(self):
        """Get MQTT service instance."""
        if self._mqtt_service is None:
            try:
                from services.mqtt_service import get_mqtt_service
                self._mqtt_service = get_mqtt_service()
            except ImportError:
                pass
        return self._mqtt_service

    def set_tinyg_controller(self, controller):
        """Set TinyG controller reference."""
        self._tinyg_controller = controller

    def register_callback(self, callback: MonitorCallback):
        """Register callback for monitor data updates."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback: MonitorCallback):
        """Unregister callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def start_monitoring(self, job_context=None) -> tuple:
        """
        Start execution monitoring.

        Args:
            job_context: Optional JobContext to capture data for

        Returns:
            Tuple of (success, message)
        """
        with self._lock:
            if self._running:
                return False, "Already monitoring"

            self._running = True
            self._stop_event.clear()
            self._job_context = job_context
            self._data_history.clear()

        # Start monitor thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_worker,
            daemon=True,
            name="ExecutionMonitor"
        )
        self._monitor_thread.start()

        logger.info("Execution monitoring started")
        return True, "Monitoring started"

    def stop_monitoring(self) -> tuple:
        """Stop execution monitoring."""
        with self._lock:
            if not self._running:
                return False, "Not monitoring"

            self._running = False
            self._stop_event.set()

        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)

        logger.info("Execution monitoring stopped")
        return True, "Monitoring stopped"

    def _monitor_worker(self):
        """Main monitoring loop."""
        last_mqtt_publish = 0
        last_influx_write = 0

        try:
            while not self._stop_event.is_set():
                now = time.time()

                # Collect data from all sources
                self._collect_data()

                # MQTT publishing
                if (now - last_mqtt_publish) >= (1.0 / self._mqtt_rate_hz):
                    self._publish_mqtt()
                    last_mqtt_publish = now

                # InfluxDB writing
                if (now - last_influx_write) >= (1.0 / self._influx_rate_hz):
                    self._write_influxdb()
                    last_influx_write = now

                # Notify callbacks
                self._notify_callbacks()

                # Store in history
                with self._lock:
                    self._data_history.append(self._current_data)

                # Capture sensor snapshot to job context if available
                if self._job_context:
                    self._capture_to_context()

                # Sleep to target ~20Hz internal rate
                time.sleep(0.05)

        except Exception as e:
            logger.error(f"Monitor worker error: {e}")

    def _collect_data(self):
        """Collect data from all sources."""
        now = time.time()
        data = MonitorData(timestamp=now)

        # TinyG status
        if self._tinyg_controller and self._tinyg_controller.connected:
            status = self._tinyg_controller._last_status
            if status:
                data.position_x = status.get('wx', 0) or 0
                data.position_y = status.get('wy', 0) or 0
                data.position_z = status.get('wz', 0) or 0
                data.velocity = status.get('vel', 0) or 0
                data.feed_rate = status.get('feed', 0) or 0
                data.spindle_speed = status.get('sps', 0) or 0
                data.machine_state = status.get('stat', 0) or 0
                data.motion_mode = status.get('momo', 0) or 0
                data.current_line = status.get('line', 0) or 0

        # MCC DAQ currents (if available)
        # This would integrate with MCC service
        # data.spindle_current = mcc_data.get('spindle', 0)
        # etc.

        # Arduino sensors (if available)
        # This would integrate with sensor service
        # data.vibration_rms = sensor_data.get('rms', 0)
        # etc.

        with self._lock:
            self._current_data = data

    def _publish_mqtt(self):
        """Publish current data to MQTT."""
        if not self.mqtt_service or not self.mqtt_service.connected:
            return

        try:
            # Publish execution status
            payload = {
                "timestamp": self._current_data.timestamp,
                "position": {
                    "x": self._current_data.position_x,
                    "y": self._current_data.position_y,
                    "z": self._current_data.position_z,
                },
                "velocity": self._current_data.velocity,
                "feed_rate": self._current_data.feed_rate,
                "spindle_speed": self._current_data.spindle_speed,
                "machine_state": self._current_data.machine_state,
                "current_line": self._current_data.current_line,
            }

            self.mqtt_service.publish("cnc/execution/status", payload)

        except Exception as e:
            logger.error(f"MQTT publish error: {e}")

    def _write_influxdb(self):
        """Write current data to InfluxDB."""
        # This would integrate with InfluxDB service
        pass

    def _notify_callbacks(self):
        """Notify registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(self._current_data)
            except Exception as e:
                logger.error(f"Monitor callback error: {e}")

    def _capture_to_context(self):
        """Capture sensor snapshot to job context."""
        if not self._job_context:
            return

        try:
            from services.integration.job_context import ExecutionState
            if self._job_context.state == ExecutionState.RUNNING:
                self._job_context.capture_sensor_snapshot(
                    gcode_line=self._current_data.current_line,
                    position={
                        "x": self._current_data.position_x,
                        "y": self._current_data.position_y,
                        "z": self._current_data.position_z,
                    },
                    velocity=self._current_data.velocity,
                    spindle_speed=self._current_data.spindle_speed,
                    feed_rate=self._current_data.feed_rate,
                    motor_currents={
                        "spindle": self._current_data.spindle_current,
                        "x": self._current_data.x_motor_current,
                        "y": self._current_data.y_motor_current,
                        "z": self._current_data.z_motor_current,
                    },
                    imu_data={
                        "rms": self._current_data.vibration_rms,
                        "ax": self._current_data.accel_x,
                        "ay": self._current_data.accel_y,
                        "az": self._current_data.accel_z,
                    },
                    environmental={
                        "temperature": self._current_data.temperature,
                        "pressure": self._current_data.pressure,
                    },
                )
        except Exception as e:
            logger.error(f"Context capture error: {e}")

    def get_current_data(self) -> MonitorData:
        """Get current monitor data."""
        with self._lock:
            return self._current_data

    def get_history(self, limit: int = 100) -> List[MonitorData]:
        """Get recent monitor data history."""
        with self._lock:
            return list(self._data_history)[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        with self._lock:
            if not self._data_history:
                return {}

            history = list(self._data_history)

        velocities = [d.velocity for d in history if d.velocity > 0]
        vibrations = [d.vibration_rms for d in history if d.vibration_rms > 0]

        return {
            "sample_count": len(history),
            "duration_sec": history[-1].timestamp - history[0].timestamp if len(history) > 1 else 0,
            "max_velocity": max(velocities) if velocities else 0,
            "avg_velocity": sum(velocities) / len(velocities) if velocities else 0,
            "max_vibration": max(vibrations) if vibrations else 0,
            "avg_vibration": sum(vibrations) / len(vibrations) if vibrations else 0,
        }


# Global monitor instance
_execution_monitor: Optional[ExecutionMonitor] = None


def get_execution_monitor() -> ExecutionMonitor:
    """Get global execution monitor instance."""
    global _execution_monitor
    if _execution_monitor is None:
        _execution_monitor = ExecutionMonitor()
    return _execution_monitor
