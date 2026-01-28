"""
Job Execution Context for Flask CNC SCADA
=========================================
Manages the execution context for G-code jobs with state machine.

Features:
- State machine for job lifecycle (IDLE -> LOADING -> SETUP -> RUNNING -> COMPLETING -> IDLE)
- Sensor data capture during execution
- Progress tracking and time estimation
- Error handling and recovery
- Integration with traceability service

Usage:
    from services.integration.job_context import JobContext, ExecutionState

    async with JobContext(job_id="123", machine_id="tinyg-1") as ctx:
        ctx.start_execution()
        while ctx.state == ExecutionState.RUNNING:
            ctx.update_progress(current_line, total_lines)
            ctx.capture_sensor_snapshot()
"""

import logging
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
import uuid

from config import get_config
from services.integration.event_dispatcher import get_event_dispatcher, EventType

logger = logging.getLogger(__name__)
config = get_config()


class ExecutionState(Enum):
    """Job execution state machine states."""
    IDLE = "idle"
    LOADING = "loading"       # Loading G-code file
    SETUP = "setup"           # Machine setup (tool change, WCS, etc.)
    RUNNING = "running"       # Executing G-code
    PAUSED = "paused"         # Paused by operator or system
    COMPLETING = "completing" # Finishing up, recording metrics
    COMPLETED = "completed"   # Successfully completed
    ERROR = "error"           # Error state, awaiting reset
    CANCELLED = "cancelled"   # Cancelled by operator


# Valid state transitions
STATE_TRANSITIONS = {
    ExecutionState.IDLE: [ExecutionState.LOADING],
    ExecutionState.LOADING: [ExecutionState.SETUP, ExecutionState.ERROR, ExecutionState.CANCELLED],
    ExecutionState.SETUP: [ExecutionState.RUNNING, ExecutionState.ERROR, ExecutionState.CANCELLED],
    ExecutionState.RUNNING: [ExecutionState.PAUSED, ExecutionState.COMPLETING, ExecutionState.ERROR, ExecutionState.CANCELLED],
    ExecutionState.PAUSED: [ExecutionState.RUNNING, ExecutionState.CANCELLED, ExecutionState.ERROR],
    ExecutionState.COMPLETING: [ExecutionState.COMPLETED, ExecutionState.ERROR],
    ExecutionState.COMPLETED: [ExecutionState.IDLE],
    ExecutionState.ERROR: [ExecutionState.IDLE],
    ExecutionState.CANCELLED: [ExecutionState.IDLE],
}


@dataclass
class SensorSnapshot:
    """Snapshot of sensor data during execution."""
    timestamp: float
    gcode_line: int
    position: Dict[str, float]  # x, y, z
    velocity: float
    spindle_speed: float
    feed_rate: float
    motor_currents: Dict[str, float] = field(default_factory=dict)
    imu_data: Dict[str, float] = field(default_factory=dict)
    environmental: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "gcode_line": self.gcode_line,
            "position": self.position,
            "velocity": self.velocity,
            "spindle_speed": self.spindle_speed,
            "feed_rate": self.feed_rate,
            "motor_currents": self.motor_currents,
            "imu_data": self.imu_data,
            "environmental": self.environmental,
        }


@dataclass
class ExecutionMetrics:
    """Metrics collected during job execution."""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    total_lines: int = 0
    lines_executed: int = 0
    paused_duration_sec: float = 0.0
    tool_changes: int = 0
    feed_overrides: List[tuple] = field(default_factory=list)  # (timestamp, value)
    max_velocity: float = 0.0
    max_spindle_speed: float = 0.0
    avg_feed_rate: float = 0.0
    error_count: int = 0

    @property
    def actual_duration_sec(self) -> float:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at - self.paused_duration_sec
        return 0.0

    @property
    def progress_percent(self) -> float:
        if self.total_lines > 0:
            return (self.lines_executed / self.total_lines) * 100
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "actual_duration_sec": self.actual_duration_sec,
            "total_lines": self.total_lines,
            "lines_executed": self.lines_executed,
            "progress_percent": self.progress_percent,
            "paused_duration_sec": self.paused_duration_sec,
            "tool_changes": self.tool_changes,
            "max_velocity": self.max_velocity,
            "max_spindle_speed": self.max_spindle_speed,
            "avg_feed_rate": self.avg_feed_rate,
            "error_count": self.error_count,
        }


class JobContext:
    """
    Execution context for a G-code job.

    Manages the complete lifecycle of job execution including state
    transitions, progress tracking, sensor capture, and metrics collection.
    """

    def __init__(
        self,
        job_id: str,
        machine_id: str,
        gcode_file: str,
        estimated_time_sec: Optional[float] = None,
        operator_id: Optional[str] = None,
        work_order_id: Optional[str] = None,
        operation_id: Optional[str] = None,
    ):
        """
        Initialize job execution context.

        Args:
            job_id: Unique job identifier
            machine_id: Target machine ID
            gcode_file: Path to G-code file
            estimated_time_sec: Estimated execution time
            operator_id: Operator running the job
            work_order_id: Associated work order
            operation_id: Associated operation
        """
        self.id = str(uuid.uuid4())
        self.job_id = job_id
        self.machine_id = machine_id
        self.gcode_file = gcode_file
        self.estimated_time_sec = estimated_time_sec
        self.operator_id = operator_id
        self.work_order_id = work_order_id
        self.operation_id = operation_id

        # State machine
        self._state = ExecutionState.IDLE
        self._state_history: List[tuple] = [(time.time(), ExecutionState.IDLE)]
        self._lock = threading.RLock()

        # Execution data
        self.metrics = ExecutionMetrics()
        self.sensor_snapshots: List[SensorSnapshot] = []
        self.error_message: Optional[str] = None

        # Pause tracking
        self._pause_start: Optional[float] = None

        # Event dispatcher
        self._event_dispatcher = get_event_dispatcher()

        # Callbacks
        self._state_change_callbacks: List[Callable] = []

        logger.info(f"JobContext created for job {job_id} on {machine_id}")

    @property
    def state(self) -> ExecutionState:
        """Current execution state."""
        return self._state

    def can_transition_to(self, new_state: ExecutionState) -> bool:
        """Check if transition to new state is valid."""
        return new_state in STATE_TRANSITIONS.get(self._state, [])

    def transition_to(self, new_state: ExecutionState) -> bool:
        """
        Transition to a new state.

        Args:
            new_state: Target state

        Returns:
            True if transition successful
        """
        with self._lock:
            if not self.can_transition_to(new_state):
                logger.warning(
                    f"Invalid state transition: {self._state.value} -> {new_state.value}"
                )
                return False

            old_state = self._state
            self._state = new_state
            self._state_history.append((time.time(), new_state))

            # Handle state-specific logic
            self._on_state_change(old_state, new_state)

            # Notify callbacks
            for callback in self._state_change_callbacks:
                try:
                    callback(old_state, new_state)
                except Exception as e:
                    logger.error(f"Error in state change callback: {e}")

            logger.info(f"Job {self.job_id} state: {old_state.value} -> {new_state.value}")
            return True

    def _on_state_change(self, old_state: ExecutionState, new_state: ExecutionState):
        """Handle state change logic."""
        # Publish event
        event_type_map = {
            ExecutionState.LOADING: EventType.JOB_STARTED,
            ExecutionState.RUNNING: EventType.JOB_STARTED,
            ExecutionState.PAUSED: EventType.JOB_PAUSED,
            ExecutionState.COMPLETED: EventType.JOB_COMPLETED,
            ExecutionState.ERROR: EventType.JOB_FAILED,
            ExecutionState.CANCELLED: EventType.JOB_CANCELLED,
        }

        event_type = event_type_map.get(new_state)
        if event_type:
            self._event_dispatcher.publish(
                event_type,
                {
                    "job_id": self.job_id,
                    "context_id": self.id,
                    "machine_id": self.machine_id,
                    "old_state": old_state.value,
                    "new_state": new_state.value,
                    "progress": self.metrics.progress_percent,
                },
                source="job_context",
            )

        # State-specific logic
        if new_state == ExecutionState.RUNNING and old_state != ExecutionState.PAUSED:
            self.metrics.started_at = time.time()

        elif new_state == ExecutionState.PAUSED:
            self._pause_start = time.time()

        elif old_state == ExecutionState.PAUSED and new_state == ExecutionState.RUNNING:
            if self._pause_start:
                self.metrics.paused_duration_sec += time.time() - self._pause_start
                self._pause_start = None

        elif new_state in (ExecutionState.COMPLETED, ExecutionState.ERROR, ExecutionState.CANCELLED):
            self.metrics.completed_at = time.time()

    def register_state_callback(self, callback: Callable) -> None:
        """Register callback for state changes."""
        self._state_change_callbacks.append(callback)

    # =========================================================================
    # State Transition Methods
    # =========================================================================

    def start_loading(self) -> bool:
        """Begin loading the G-code file."""
        return self.transition_to(ExecutionState.LOADING)

    def start_setup(self) -> bool:
        """Begin machine setup phase."""
        return self.transition_to(ExecutionState.SETUP)

    def start_execution(self) -> bool:
        """Begin G-code execution."""
        return self.transition_to(ExecutionState.RUNNING)

    def pause(self) -> bool:
        """Pause execution."""
        return self.transition_to(ExecutionState.PAUSED)

    def resume(self) -> bool:
        """Resume from pause."""
        return self.transition_to(ExecutionState.RUNNING)

    def complete(self) -> bool:
        """Begin completion phase."""
        if self.transition_to(ExecutionState.COMPLETING):
            return self.transition_to(ExecutionState.COMPLETED)
        return False

    def fail(self, error_message: str) -> bool:
        """Transition to error state."""
        self.error_message = error_message
        self.metrics.error_count += 1
        return self.transition_to(ExecutionState.ERROR)

    def cancel(self) -> bool:
        """Cancel the job."""
        return self.transition_to(ExecutionState.CANCELLED)

    def reset(self) -> bool:
        """Reset to idle state."""
        return self.transition_to(ExecutionState.IDLE)

    # =========================================================================
    # Progress and Metrics
    # =========================================================================

    def update_progress(
        self,
        current_line: int,
        total_lines: Optional[int] = None,
    ) -> None:
        """
        Update execution progress.

        Args:
            current_line: Current G-code line number
            total_lines: Total lines (optional, uses existing if not provided)
        """
        with self._lock:
            self.metrics.lines_executed = current_line
            if total_lines is not None:
                self.metrics.total_lines = total_lines

        # Publish progress event periodically (every 1%)
        if self.metrics.total_lines > 0:
            progress = (current_line / self.metrics.total_lines) * 100
            if int(progress) > int(self.metrics.progress_percent):
                self._event_dispatcher.publish(
                    EventType.JOB_PROGRESS,
                    {
                        "job_id": self.job_id,
                        "current_line": current_line,
                        "total_lines": self.metrics.total_lines,
                        "progress_percent": progress,
                    },
                    source="job_context",
                )

    def update_machine_state(
        self,
        velocity: float,
        spindle_speed: float,
        feed_rate: float,
    ) -> None:
        """Update machine state metrics."""
        with self._lock:
            self.metrics.max_velocity = max(self.metrics.max_velocity, velocity)
            self.metrics.max_spindle_speed = max(self.metrics.max_spindle_speed, spindle_speed)

            # Running average for feed rate
            n = self.metrics.lines_executed or 1
            self.metrics.avg_feed_rate = (
                (self.metrics.avg_feed_rate * (n - 1) + feed_rate) / n
            )

    def record_tool_change(self, tool_number: int) -> None:
        """Record a tool change."""
        with self._lock:
            self.metrics.tool_changes += 1

    def record_feed_override(self, override_percent: float) -> None:
        """Record feed override change."""
        with self._lock:
            self.metrics.feed_overrides.append((time.time(), override_percent))

    # =========================================================================
    # Sensor Data Capture
    # =========================================================================

    def capture_sensor_snapshot(
        self,
        gcode_line: int,
        position: Dict[str, float],
        velocity: float,
        spindle_speed: float,
        feed_rate: float,
        motor_currents: Optional[Dict[str, float]] = None,
        imu_data: Optional[Dict[str, float]] = None,
        environmental: Optional[Dict[str, float]] = None,
    ) -> SensorSnapshot:
        """
        Capture a sensor snapshot during execution.

        Args:
            gcode_line: Current G-code line
            position: Machine position {x, y, z}
            velocity: Current velocity
            spindle_speed: Spindle RPM
            feed_rate: Feed rate
            motor_currents: Motor current readings
            imu_data: IMU sensor data
            environmental: Environmental sensor data

        Returns:
            The captured snapshot
        """
        snapshot = SensorSnapshot(
            timestamp=time.time(),
            gcode_line=gcode_line,
            position=position,
            velocity=velocity,
            spindle_speed=spindle_speed,
            feed_rate=feed_rate,
            motor_currents=motor_currents or {},
            imu_data=imu_data or {},
            environmental=environmental or {},
        )

        with self._lock:
            self.sensor_snapshots.append(snapshot)

        return snapshot

    def get_sensor_summary(self) -> Dict[str, Any]:
        """Get summary of captured sensor data."""
        with self._lock:
            if not self.sensor_snapshots:
                return {}

            return {
                "snapshot_count": len(self.sensor_snapshots),
                "first_timestamp": self.sensor_snapshots[0].timestamp,
                "last_timestamp": self.sensor_snapshots[-1].timestamp,
                "duration_sec": (
                    self.sensor_snapshots[-1].timestamp -
                    self.sensor_snapshots[0].timestamp
                ),
            }

    # =========================================================================
    # Context Manager
    # =========================================================================

    def __enter__(self) -> "JobContext":
        """Enter context manager."""
        self.start_loading()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit context manager."""
        if exc_type is not None:
            self.fail(str(exc_val))
            return False

        if self._state == ExecutionState.RUNNING:
            self.complete()
        elif self._state not in (ExecutionState.COMPLETED, ExecutionState.ERROR, ExecutionState.CANCELLED):
            self.cancel()

        return False

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "machine_id": self.machine_id,
            "gcode_file": self.gcode_file,
            "state": self._state.value,
            "operator_id": self.operator_id,
            "work_order_id": self.work_order_id,
            "operation_id": self.operation_id,
            "estimated_time_sec": self.estimated_time_sec,
            "metrics": self.metrics.to_dict(),
            "error_message": self.error_message,
            "sensor_snapshot_count": len(self.sensor_snapshots),
            "state_history": [
                {"timestamp": ts, "state": state.value}
                for ts, state in self._state_history
            ],
        }


@contextmanager
def create_job_context(
    job_id: str,
    machine_id: str,
    gcode_file: str,
    **kwargs,
):
    """
    Context manager factory for job execution.

    Usage:
        with create_job_context("job-123", "tinyg-1", "part.nc") as ctx:
            ctx.start_execution()
            # Execute G-code
            ctx.complete()
    """
    ctx = JobContext(job_id, machine_id, gcode_file, **kwargs)
    try:
        yield ctx
    finally:
        if ctx.state == ExecutionState.RUNNING:
            ctx.complete()
        elif ctx.state not in (
            ExecutionState.COMPLETED,
            ExecutionState.ERROR,
            ExecutionState.CANCELLED,
            ExecutionState.IDLE,
        ):
            ctx.cancel()
