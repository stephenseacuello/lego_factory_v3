"""
Job Executor for Flask CNC SCADA
================================
Main execution engine that orchestrates G-code execution with full lifecycle management.

Features:
- Complete job execution lifecycle management
- Integration with TinyG controller
- Progress tracking and ETA calculation
- Sensor data capture during execution
- Event publishing for real-time updates
- Error handling and recovery

Usage:
    from services.execution.job_executor import get_job_executor

    executor = get_job_executor()
    result = executor.execute_job(job_id, machine_id="tinyg-1")
"""

import logging
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from config import get_config
from services.integration.job_context import (
    JobContext,
    ExecutionState,
    create_job_context,
)
from services.integration.event_dispatcher import get_event_dispatcher, EventType
from services.execution.gcode_streamer import GCodeStreamer, StreamerState
from services.execution.execution_monitor import get_execution_monitor

logger = logging.getLogger(__name__)
config = get_config()


@dataclass
class ExecutionResult:
    """Result of job execution."""
    success: bool
    job_id: str
    started_at: float
    completed_at: float
    actual_time_sec: float
    total_lines: int
    lines_executed: int
    sensor_snapshots: int = 0
    error_message: Optional[str] = None
    final_state: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "job_id": self.job_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "actual_time_sec": round(self.actual_time_sec, 2),
            "total_lines": self.total_lines,
            "lines_executed": self.lines_executed,
            "sensor_snapshots": self.sensor_snapshots,
            "error_message": self.error_message,
            "final_state": self.final_state,
        }


class JobExecutor:
    """
    Main job execution engine.

    Coordinates:
    - TinyG controller for G-code execution
    - GCodeStreamer for line-by-line streaming
    - ExecutionMonitor for sensor data capture
    - JobContext for state management
    - Event publishing for real-time updates
    """

    def __init__(self):
        """Initialize job executor."""
        self._lock = threading.RLock()

        # Controller reference (set externally)
        self._tinyg_controller = None

        # Active executions
        self._active_jobs: Dict[str, JobContext] = {}

        # Services
        self._gcode_service = None
        self._event_dispatcher = get_event_dispatcher()
        self._monitor = get_execution_monitor()

        logger.info("JobExecutor initialized")

    def set_tinyg_controller(self, controller):
        """Set TinyG controller reference."""
        self._tinyg_controller = controller
        self._monitor.set_tinyg_controller(controller)

    @property
    def gcode_service(self):
        """Get G-code service instance."""
        if self._gcode_service is None:
            from services.gcode_service import get_gcode_service
            self._gcode_service = get_gcode_service()
        return self._gcode_service

    def can_execute(self, machine_id: str) -> Tuple[bool, str]:
        """
        Check if executor can run a job.

        Args:
            machine_id: Machine to check

        Returns:
            Tuple of (can_execute, reason)
        """
        # Check TinyG connection
        if not self._tinyg_controller:
            return False, "TinyG controller not configured"

        if not self._tinyg_controller.connected:
            return False, "TinyG not connected"

        # Check if already executing on this machine
        with self._lock:
            for ctx in self._active_jobs.values():
                if ctx.machine_id == machine_id and ctx.state == ExecutionState.RUNNING:
                    return False, f"Already executing job on {machine_id}"

        return True, "Ready"

    def execute_job(
        self,
        job_id: str,
        machine_id: str = "tinyg-1",
        operator_id: Optional[str] = None,
        work_order_id: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a job from the queue.

        Args:
            job_id: Job ID to execute
            machine_id: Target machine
            operator_id: Operator ID
            work_order_id: Associated work order
            operation_id: Associated operation

        Returns:
            ExecutionResult with execution details
        """
        started_at = time.time()
        error_message = None
        final_state = ExecutionState.IDLE.value

        try:
            # Validate execution
            can_exec, reason = self.can_execute(machine_id)
            if not can_exec:
                return ExecutionResult(
                    success=False,
                    job_id=job_id,
                    started_at=started_at,
                    completed_at=time.time(),
                    actual_time_sec=0,
                    total_lines=0,
                    lines_executed=0,
                    error_message=reason,
                    final_state="error",
                )

            # Get job from queue
            job = self.gcode_service.get_job(job_id)
            if not job:
                return ExecutionResult(
                    success=False,
                    job_id=job_id,
                    started_at=started_at,
                    completed_at=time.time(),
                    actual_time_sec=0,
                    total_lines=0,
                    lines_executed=0,
                    error_message="Job not found",
                    final_state="error",
                )

            # Create execution context
            ctx = JobContext(
                job_id=job_id,
                machine_id=machine_id,
                gcode_file=job.filepath,
                estimated_time_sec=job.metadata.estimated_time_sec,
                operator_id=operator_id,
                work_order_id=work_order_id,
                operation_id=operation_id,
            )

            # Register context
            with self._lock:
                self._active_jobs[job_id] = ctx

            # Update job status
            from services.gcode_service import JobStatus
            self.gcode_service.update_job_status(job_id, JobStatus.RUNNING)

            # Execute the job
            result = self._execute_with_context(ctx, job)
            final_state = ctx.state.value

            return result

        except Exception as e:
            logger.error(f"Job execution error: {e}")
            error_message = str(e)
            final_state = "error"

            return ExecutionResult(
                success=False,
                job_id=job_id,
                started_at=started_at,
                completed_at=time.time(),
                actual_time_sec=time.time() - started_at,
                total_lines=0,
                lines_executed=0,
                error_message=error_message,
                final_state=final_state,
            )

        finally:
            # Cleanup
            with self._lock:
                if job_id in self._active_jobs:
                    del self._active_jobs[job_id]

    def _execute_with_context(self, ctx: JobContext, job) -> ExecutionResult:
        """Execute job with full context management."""
        started_at = time.time()

        try:
            # Phase 1: Loading
            ctx.start_loading()
            logger.info(f"Loading G-code file: {job.filepath}")

            # Create streamer
            streamer = GCodeStreamer(self._tinyg_controller)

            # Register progress callback
            def on_progress(progress):
                ctx.update_progress(progress.current_line, progress.total_lines)
                ctx.update_machine_state(
                    velocity=progress.feed_rate,  # Approximate
                    spindle_speed=progress.spindle_speed,
                    feed_rate=progress.feed_rate,
                )

            streamer.register_progress_callback(on_progress)

            # Load G-code
            ok, msg = streamer.load_file(job.filepath)
            if not ok:
                ctx.fail(msg)
                return ExecutionResult(
                    success=False,
                    job_id=ctx.job_id,
                    started_at=started_at,
                    completed_at=time.time(),
                    actual_time_sec=time.time() - started_at,
                    total_lines=0,
                    lines_executed=0,
                    error_message=msg,
                    final_state=ctx.state.value,
                )

            ctx.metrics.total_lines = streamer.progress.total_lines

            # Phase 2: Setup
            ctx.start_setup()
            logger.info(f"Setup phase for job {ctx.job_id}")

            # Verify machine is ready
            if not self._verify_machine_ready():
                ctx.fail("Machine not ready")
                return ExecutionResult(
                    success=False,
                    job_id=ctx.job_id,
                    started_at=started_at,
                    completed_at=time.time(),
                    actual_time_sec=time.time() - started_at,
                    total_lines=streamer.progress.total_lines,
                    lines_executed=0,
                    error_message="Machine not ready",
                    final_state=ctx.state.value,
                )

            # Phase 3: Running
            ctx.start_execution()
            logger.info(f"Starting execution of job {ctx.job_id}")

            # Start monitoring
            self._monitor.start_monitoring(ctx)

            # Start streaming
            ok, msg = streamer.start()
            if not ok:
                ctx.fail(msg)
                self._monitor.stop_monitoring()
                return ExecutionResult(
                    success=False,
                    job_id=ctx.job_id,
                    started_at=started_at,
                    completed_at=time.time(),
                    actual_time_sec=time.time() - started_at,
                    total_lines=streamer.progress.total_lines,
                    lines_executed=0,
                    error_message=msg,
                    final_state=ctx.state.value,
                )

            # Wait for streaming to complete
            while streamer.state in (StreamerState.STREAMING, StreamerState.PAUSED):
                time.sleep(0.1)

                # Update job progress in gcode service
                self.gcode_service.update_job_progress(
                    ctx.job_id,
                    streamer.progress.current_line
                )

                # Check for pause/cancel from context
                if ctx.state == ExecutionState.PAUSED:
                    streamer.pause()
                elif ctx.state == ExecutionState.CANCELLED:
                    streamer.cancel()
                    break

            # Stop monitoring
            self._monitor.stop_monitoring()

            # Phase 4: Completing
            if streamer.state == StreamerState.COMPLETED:
                ctx.complete()

                # Update job status
                from services.gcode_service import JobStatus
                self.gcode_service.update_job_status(ctx.job_id, JobStatus.COMPLETED)

                return ExecutionResult(
                    success=True,
                    job_id=ctx.job_id,
                    started_at=started_at,
                    completed_at=time.time(),
                    actual_time_sec=ctx.metrics.actual_duration_sec,
                    total_lines=streamer.progress.total_lines,
                    lines_executed=streamer.progress.lines_sent,
                    sensor_snapshots=len(ctx.sensor_snapshots),
                    final_state=ctx.state.value,
                )

            elif streamer.state == StreamerState.CANCELLED:
                from services.gcode_service import JobStatus
                self.gcode_service.update_job_status(ctx.job_id, JobStatus.CANCELLED)

                return ExecutionResult(
                    success=False,
                    job_id=ctx.job_id,
                    started_at=started_at,
                    completed_at=time.time(),
                    actual_time_sec=time.time() - started_at,
                    total_lines=streamer.progress.total_lines,
                    lines_executed=streamer.progress.lines_sent,
                    sensor_snapshots=len(ctx.sensor_snapshots),
                    error_message="Job cancelled",
                    final_state=ctx.state.value,
                )

            else:
                # Error state
                ctx.fail("Streaming failed")
                from services.gcode_service import JobStatus
                self.gcode_service.update_job_status(ctx.job_id, JobStatus.FAILED)

                return ExecutionResult(
                    success=False,
                    job_id=ctx.job_id,
                    started_at=started_at,
                    completed_at=time.time(),
                    actual_time_sec=time.time() - started_at,
                    total_lines=streamer.progress.total_lines,
                    lines_executed=streamer.progress.lines_sent,
                    sensor_snapshots=len(ctx.sensor_snapshots),
                    error_message="Streaming failed",
                    final_state=ctx.state.value,
                )

        except Exception as e:
            logger.error(f"Execution error: {e}")
            ctx.fail(str(e))

            from services.gcode_service import JobStatus
            self.gcode_service.update_job_status(ctx.job_id, JobStatus.FAILED)

            return ExecutionResult(
                success=False,
                job_id=ctx.job_id,
                started_at=started_at,
                completed_at=time.time(),
                actual_time_sec=time.time() - started_at,
                total_lines=ctx.metrics.total_lines,
                lines_executed=ctx.metrics.lines_executed,
                sensor_snapshots=len(ctx.sensor_snapshots),
                error_message=str(e),
                final_state=ctx.state.value,
            )

    def _verify_machine_ready(self) -> bool:
        """Verify machine is ready for execution."""
        if not self._tinyg_controller:
            return False

        status = self._tinyg_controller.status()
        if not status.get('connected'):
            return False

        # Check machine state (0 = init, 1 = ready, 2 = alarm, etc.)
        last_status = status.get('last_status', {})
        stat = last_status.get('stat', 0)

        # Accept init (0) or ready (1) states
        return stat in (0, 1, 3)  # 3 = stop

    def pause_job(self, job_id: str) -> Tuple[bool, str]:
        """Pause a running job."""
        with self._lock:
            ctx = self._active_jobs.get(job_id)
            if not ctx:
                return False, "Job not found"

            if ctx.state != ExecutionState.RUNNING:
                return False, f"Cannot pause job in state: {ctx.state.value}"

            ctx.pause()
            return True, "Job paused"

    def resume_job(self, job_id: str) -> Tuple[bool, str]:
        """Resume a paused job."""
        with self._lock:
            ctx = self._active_jobs.get(job_id)
            if not ctx:
                return False, "Job not found"

            if ctx.state != ExecutionState.PAUSED:
                return False, f"Cannot resume job in state: {ctx.state.value}"

            ctx.resume()
            return True, "Job resumed"

    def cancel_job(self, job_id: str) -> Tuple[bool, str]:
        """Cancel a running or paused job."""
        with self._lock:
            ctx = self._active_jobs.get(job_id)
            if not ctx:
                return False, "Job not found"

            if ctx.state not in (ExecutionState.RUNNING, ExecutionState.PAUSED):
                return False, f"Cannot cancel job in state: {ctx.state.value}"

            ctx.cancel()
            return True, "Job cancelled"

    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """Get list of active jobs."""
        with self._lock:
            return [ctx.to_dict() for ctx in self._active_jobs.values()]

    def get_job_context(self, job_id: str) -> Optional[JobContext]:
        """Get context for a specific job."""
        with self._lock:
            return self._active_jobs.get(job_id)


# Global executor instance
_job_executor: Optional[JobExecutor] = None


def get_job_executor() -> JobExecutor:
    """Get global job executor instance."""
    global _job_executor
    if _job_executor is None:
        _job_executor = JobExecutor()
    return _job_executor


def initialize_job_executor(tinyg_controller=None) -> JobExecutor:
    """Initialize job executor with controller."""
    executor = get_job_executor()
    if tinyg_controller:
        executor.set_tinyg_controller(tinyg_controller)
    return executor
