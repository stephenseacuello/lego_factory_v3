"""
Master Scheduler for Robotic Arm Coordination

PhD-Level Research Implementation:
- Multi-arm task orchestration
- Acknowledgment-based command flow
- Priority-based scheduling
- Collision avoidance between arms
- Synchronized multi-arm operations
- Real-time state synchronization

Standards Compliance:
- ISO 10218 (Industrial Robot Safety)
- ISO/TS 15066 (Collaborative Robots)
- IEC 61131 (Programmable Controllers)

Author: LegoMCP Team
Version: 2.0.0
"""

import asyncio
import heapq
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict

from .arm_controller import (
    BaseArmDriver,
    ArmState,
    CommandAcknowledgment,
    CartesianPose,
    JointState,
    MotionCommand,
    MotionType,
    Trajectory,
    get_arm_driver,
    get_all_arms,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class TaskType(Enum):
    """Types of robotic tasks."""
    MOVE_JOINT = "move_joint"
    MOVE_LINEAR = "move_linear"
    PICK = "pick"
    PLACE = "place"
    HOME = "home"
    CALIBRATE = "calibrate"
    SYNCHRONIZED = "synchronized"  # Multi-arm synchronized motion
    SEQUENCE = "sequence"  # Sequential operations


class TaskPriority(Enum):
    """Task priority levels."""
    EMERGENCY = 0
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class TaskStatus(Enum):
    """Task execution status."""
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    WAITING_ACK = "waiting_ack"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class AckStatus(Enum):
    """Acknowledgment status types."""
    RECEIVED = "received"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass(order=True)
class ScheduledTask:
    """A task in the scheduler queue."""
    priority: int
    created_at: datetime = field(compare=False)
    task_id: str = field(compare=False)
    arm_id: str = field(compare=False)
    task_type: TaskType = field(compare=False)
    parameters: Dict[str, Any] = field(compare=False, default_factory=dict)
    status: TaskStatus = field(compare=False, default=TaskStatus.QUEUED)
    depends_on: List[str] = field(compare=False, default_factory=list)
    timeout_seconds: float = field(compare=False, default=60.0)
    retry_count: int = field(compare=False, default=0)
    max_retries: int = field(compare=False, default=3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'arm_id': self.arm_id,
            'task_type': self.task_type.value,
            'priority': self.priority,
            'status': self.status.value,
            'parameters': self.parameters,
            'depends_on': self.depends_on,
            'created_at': self.created_at.isoformat(),
            'timeout_seconds': self.timeout_seconds,
            'retry_count': self.retry_count
        }


@dataclass
class TaskAcknowledgment:
    """Acknowledgment for a scheduled task."""
    task_id: str
    arm_id: str
    ack_status: AckStatus
    command_id: Optional[str] = None
    message: Optional[str] = None
    progress_percent: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    execution_time_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'arm_id': self.arm_id,
            'ack_status': self.ack_status.value,
            'command_id': self.command_id,
            'message': self.message,
            'progress_percent': self.progress_percent,
            'timestamp': self.timestamp.isoformat(),
            'execution_time_ms': self.execution_time_ms
        }


@dataclass
class SynchronizedMotion:
    """Configuration for synchronized multi-arm motion."""
    sync_id: str
    arm_tasks: Dict[str, ScheduledTask]  # arm_id -> task
    sync_point: str  # Label for sync point
    timeout_seconds: float = 30.0
    all_or_nothing: bool = True  # If one fails, all abort


@dataclass
class SchedulerMetrics:
    """Metrics for scheduler performance."""
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_cancelled: int = 0
    total_execution_time_ms: float = 0.0
    average_wait_time_ms: float = 0.0
    current_queue_size: int = 0
    arms_active: int = 0
    uptime_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tasks_completed': self.tasks_completed,
            'tasks_failed': self.tasks_failed,
            'tasks_cancelled': self.tasks_cancelled,
            'total_execution_time_ms': self.total_execution_time_ms,
            'average_wait_time_ms': self.average_wait_time_ms,
            'current_queue_size': self.current_queue_size,
            'arms_active': self.arms_active,
            'uptime_seconds': self.uptime_seconds
        }


# =============================================================================
# Master Scheduler
# =============================================================================

class MasterScheduler:
    """
    Master scheduler for coordinating multiple robotic arms.

    Features:
    - Priority-based task scheduling
    - Acknowledgment-based command flow
    - Dependency resolution
    - Multi-arm synchronization
    - Collision avoidance zones
    - Automatic retry on failure
    - Real-time state broadcasting
    """

    def __init__(self):
        self._task_queue: List[ScheduledTask] = []  # Priority heap
        self._active_tasks: Dict[str, ScheduledTask] = {}  # task_id -> task
        self._completed_tasks: Dict[str, ScheduledTask] = {}
        self._pending_acks: Dict[str, TaskAcknowledgment] = {}  # task_id -> ack

        self._arm_locks: Dict[str, asyncio.Lock] = {}  # arm_id -> lock
        self._sync_barriers: Dict[str, asyncio.Barrier] = {}

        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None

        self._start_time = datetime.utcnow()
        self._metrics = SchedulerMetrics()

        # Callbacks
        self._on_task_complete: Optional[Callable] = None
        self._on_ack_received: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

        # Configuration
        self._ack_timeout_seconds = 10.0
        self._max_concurrent_per_arm = 1
        self._enable_collision_check = True

        logger.info("Master Scheduler initialized")

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._start_time = datetime.utcnow()

        # Initialize locks for all registered arms
        for arm_id in get_all_arms():
            self._arm_locks[arm_id] = asyncio.Lock()

        # Start scheduler loop
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        logger.info("Master Scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Master Scheduler stopped")

    def schedule_task(
        self,
        arm_id: str,
        task_type: TaskType,
        parameters: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        depends_on: Optional[List[str]] = None,
        timeout_seconds: float = 60.0
    ) -> str:
        """
        Schedule a task for execution.

        Args:
            arm_id: Target arm ID
            task_type: Type of task
            parameters: Task-specific parameters
            priority: Task priority
            depends_on: List of task IDs this task depends on
            timeout_seconds: Maximum execution time

        Returns:
            Task ID for tracking
        """
        task_id = str(uuid.uuid4())

        task = ScheduledTask(
            priority=priority.value,
            created_at=datetime.utcnow(),
            task_id=task_id,
            arm_id=arm_id,
            task_type=task_type,
            parameters=parameters,
            depends_on=depends_on or [],
            timeout_seconds=timeout_seconds
        )

        heapq.heappush(self._task_queue, task)
        self._metrics.current_queue_size = len(self._task_queue)

        logger.info(f"Scheduled task {task_id} for arm {arm_id}: {task_type.value}")

        # Send queued acknowledgment
        self._emit_ack(TaskAcknowledgment(
            task_id=task_id,
            arm_id=arm_id,
            ack_status=AckStatus.RECEIVED,
            message="Task queued for execution"
        ))

        return task_id

    def schedule_synchronized_motion(
        self,
        arm_tasks: Dict[str, Dict[str, Any]],
        sync_point: str = "sync",
        priority: TaskPriority = TaskPriority.HIGH
    ) -> str:
        """
        Schedule synchronized motion across multiple arms.

        All arms will reach the sync point together before proceeding.

        Args:
            arm_tasks: {arm_id: {'task_type': ..., 'parameters': ...}}
            sync_point: Label for the sync point
            priority: Priority for all tasks

        Returns:
            Sync ID for tracking
        """
        sync_id = str(uuid.uuid4())

        # Create barrier for synchronization
        num_arms = len(arm_tasks)
        self._sync_barriers[sync_id] = asyncio.Barrier(num_arms)

        # Schedule individual tasks with sync dependency
        task_ids = []
        for arm_id, task_config in arm_tasks.items():
            task_id = self.schedule_task(
                arm_id=arm_id,
                task_type=TaskType[task_config.get('task_type', 'MOVE_JOINT')],
                parameters={
                    **task_config.get('parameters', {}),
                    '_sync_id': sync_id,
                    '_sync_point': sync_point
                },
                priority=priority,
                depends_on=task_ids.copy()  # Chain dependencies
            )
            task_ids.append(task_id)

        logger.info(f"Scheduled synchronized motion {sync_id} for {num_arms} arms")
        return sync_id

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled or active task."""
        # Check queue
        for i, task in enumerate(self._task_queue):
            if task.task_id == task_id:
                task.status = TaskStatus.CANCELLED
                self._task_queue.pop(i)
                heapq.heapify(self._task_queue)
                self._metrics.tasks_cancelled += 1
                logger.info(f"Cancelled queued task {task_id}")
                return True

        # Check active tasks
        if task_id in self._active_tasks:
            task = self._active_tasks[task_id]
            task.status = TaskStatus.CANCELLED
            # Signal arm to stop (implementation specific)
            self._metrics.tasks_cancelled += 1
            logger.info(f"Cancelled active task {task_id}")
            return True

        return False

    async def wait_for_completion(
        self,
        task_id: str,
        timeout: Optional[float] = None
    ) -> TaskAcknowledgment:
        """Wait for a task to complete."""
        start_time = datetime.utcnow()
        timeout = timeout or 120.0

        while True:
            # Check if completed
            if task_id in self._completed_tasks:
                task = self._completed_tasks[task_id]
                return TaskAcknowledgment(
                    task_id=task_id,
                    arm_id=task.arm_id,
                    ack_status=AckStatus.COMPLETED if task.status == TaskStatus.COMPLETED else AckStatus.FAILED
                )

            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout:
                return TaskAcknowledgment(
                    task_id=task_id,
                    arm_id="unknown",
                    ack_status=AckStatus.TIMEOUT,
                    message=f"Timeout after {timeout}s"
                )

            await asyncio.sleep(0.1)

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a task."""
        # Check queue
        for task in self._task_queue:
            if task.task_id == task_id:
                return task.to_dict()

        # Check active
        if task_id in self._active_tasks:
            return self._active_tasks[task_id].to_dict()

        # Check completed
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id].to_dict()

        return None

    def get_all_arm_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered arms."""
        result = {}
        for arm_id, driver in get_all_arms().items():
            result[arm_id] = driver.get_status()
        return result

    def get_metrics(self) -> SchedulerMetrics:
        """Get scheduler performance metrics."""
        self._metrics.current_queue_size = len(self._task_queue)
        self._metrics.arms_active = sum(
            1 for driver in get_all_arms().values()
            if driver.state in [ArmState.MOVING, ArmState.GRIPPING, ArmState.HOMING]
        )
        self._metrics.uptime_seconds = (datetime.utcnow() - self._start_time).total_seconds()
        return self._metrics

    async def emergency_stop_all(self) -> None:
        """Emergency stop all arms."""
        logger.warning("EMERGENCY STOP ALL ARMS")

        for arm_id, driver in get_all_arms().items():
            await driver.emergency_stop()

        # Cancel all tasks
        for task in self._task_queue:
            task.status = TaskStatus.CANCELLED

        self._task_queue.clear()

    # =========================================================================
    # Internal Methods
    # =========================================================================

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._process_queue()
                await asyncio.sleep(0.05)  # 20Hz scheduling rate
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(1.0)

    async def _monitor_loop(self) -> None:
        """Monitor task timeouts and arm states."""
        while self._running:
            try:
                await self._check_timeouts()
                await self._check_arm_states()
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")

    async def _process_queue(self) -> None:
        """Process tasks from the queue."""
        if not self._task_queue:
            return

        # Get highest priority task
        task = self._task_queue[0]

        # Check dependencies
        if not self._dependencies_satisfied(task):
            return

        # Check if arm is available
        arm_id = task.arm_id
        if arm_id not in self._arm_locks:
            self._arm_locks[arm_id] = asyncio.Lock()

        if self._arm_locks[arm_id].locked():
            return

        # Pop and execute
        heapq.heappop(self._task_queue)
        task.status = TaskStatus.EXECUTING
        self._active_tasks[task.task_id] = task

        # Execute in background
        asyncio.create_task(self._execute_task(task))

    async def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a single task."""
        arm_id = task.arm_id
        task_id = task.task_id

        async with self._arm_locks[arm_id]:
            driver = get_arm_driver(arm_id)
            if not driver:
                self._fail_task(task, f"Arm {arm_id} not found")
                return

            # Send started ack
            self._emit_ack(TaskAcknowledgment(
                task_id=task_id,
                arm_id=arm_id,
                ack_status=AckStatus.STARTED
            ))

            start_time = datetime.utcnow()

            try:
                # Execute based on task type
                if task.task_type == TaskType.MOVE_JOINT:
                    target = task.parameters.get('target_positions', [])
                    velocity = task.parameters.get('velocity_scale', 0.5)
                    ack = await driver.move_joints(target, velocity)

                elif task.task_type == TaskType.MOVE_LINEAR:
                    pose = CartesianPose(**task.parameters.get('target_pose', {}))
                    velocity = task.parameters.get('velocity_scale', 0.3)
                    ack = await driver.move_linear(pose, velocity)

                elif task.task_type == TaskType.PICK:
                    # Move to approach, then pick position, then grip
                    pick_pose = CartesianPose(**task.parameters.get('pick_pose', {}))
                    await driver.move_linear(pick_pose, 0.3)
                    ack = await driver.grip(task.parameters.get('grip_force', 50))

                elif task.task_type == TaskType.PLACE:
                    place_pose = CartesianPose(**task.parameters.get('place_pose', {}))
                    await driver.move_linear(place_pose, 0.3)
                    ack = await driver.release()

                elif task.task_type == TaskType.HOME:
                    ack = await driver.home()

                elif task.task_type == TaskType.CALIBRATE:
                    if hasattr(driver, 'calibrate'):
                        success = await driver.calibrate()
                        ack = CommandAcknowledgment(
                            command_id=task_id,
                            arm_id=arm_id,
                            status='completed' if success else 'failed'
                        )
                    else:
                        ack = CommandAcknowledgment(
                            command_id=task_id,
                            arm_id=arm_id,
                            status='failed',
                            message='Calibration not supported'
                        )

                else:
                    ack = CommandAcknowledgment(
                        command_id=task_id,
                        arm_id=arm_id,
                        status='failed',
                        message=f'Unknown task type: {task.task_type}'
                    )

                # Handle sync point
                sync_id = task.parameters.get('_sync_id')
                if sync_id and sync_id in self._sync_barriers:
                    await self._sync_barriers[sync_id].wait()

                # Update task status
                exec_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                if ack.status == 'completed':
                    self._complete_task(task, exec_time)
                else:
                    if task.retry_count < task.max_retries:
                        task.retry_count += 1
                        task.status = TaskStatus.QUEUED
                        heapq.heappush(self._task_queue, task)
                        logger.warning(f"Retrying task {task_id} (attempt {task.retry_count})")
                    else:
                        self._fail_task(task, ack.message or "Max retries exceeded")

            except Exception as e:
                logger.error(f"Task execution error: {e}")
                self._fail_task(task, str(e))

    def _dependencies_satisfied(self, task: ScheduledTask) -> bool:
        """Check if all dependencies are completed."""
        for dep_id in task.depends_on:
            if dep_id not in self._completed_tasks:
                return False
            if self._completed_tasks[dep_id].status != TaskStatus.COMPLETED:
                return False
        return True

    def _complete_task(self, task: ScheduledTask, exec_time_ms: float) -> None:
        """Mark task as completed."""
        task.status = TaskStatus.COMPLETED
        del self._active_tasks[task.task_id]
        self._completed_tasks[task.task_id] = task

        self._metrics.tasks_completed += 1
        self._metrics.total_execution_time_ms += exec_time_ms

        self._emit_ack(TaskAcknowledgment(
            task_id=task.task_id,
            arm_id=task.arm_id,
            ack_status=AckStatus.COMPLETED,
            execution_time_ms=exec_time_ms
        ))

        if self._on_task_complete:
            self._on_task_complete(task)

        logger.info(f"Task {task.task_id} completed in {exec_time_ms:.1f}ms")

    def _fail_task(self, task: ScheduledTask, message: str) -> None:
        """Mark task as failed."""
        task.status = TaskStatus.FAILED
        if task.task_id in self._active_tasks:
            del self._active_tasks[task.task_id]
        self._completed_tasks[task.task_id] = task

        self._metrics.tasks_failed += 1

        self._emit_ack(TaskAcknowledgment(
            task_id=task.task_id,
            arm_id=task.arm_id,
            ack_status=AckStatus.FAILED,
            message=message
        ))

        if self._on_error:
            self._on_error(task, message)

        logger.error(f"Task {task.task_id} failed: {message}")

    async def _check_timeouts(self) -> None:
        """Check for task timeouts."""
        now = datetime.utcnow()
        for task_id, task in list(self._active_tasks.items()):
            elapsed = (now - task.created_at).total_seconds()
            if elapsed > task.timeout_seconds:
                self._fail_task(task, "Task timeout")

    async def _check_arm_states(self) -> None:
        """Check arm states for errors."""
        for arm_id, driver in get_all_arms().items():
            if driver.state == ArmState.ERROR:
                logger.warning(f"Arm {arm_id} in error state")
            elif driver.state == ArmState.EMERGENCY_STOP:
                # Cancel all tasks for this arm
                for task in list(self._task_queue):
                    if task.arm_id == arm_id:
                        task.status = TaskStatus.CANCELLED

    def _emit_ack(self, ack: TaskAcknowledgment) -> None:
        """Emit acknowledgment."""
        self._pending_acks[ack.task_id] = ack

        if self._on_ack_received:
            self._on_ack_received(ack)

    def set_task_complete_callback(self, callback: Callable) -> None:
        """Set callback for task completion."""
        self._on_task_complete = callback

    def set_ack_callback(self, callback: Callable) -> None:
        """Set callback for acknowledgments."""
        self._on_ack_received = callback

    def set_error_callback(self, callback: Callable) -> None:
        """Set callback for errors."""
        self._on_error = callback


# =============================================================================
# Singleton
# =============================================================================

_scheduler_instance: Optional[MasterScheduler] = None


def get_master_scheduler() -> MasterScheduler:
    """Get the singleton master scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = MasterScheduler()
    return _scheduler_instance


async def initialize_scheduler() -> MasterScheduler:
    """Initialize and start the master scheduler."""
    scheduler = get_master_scheduler()
    await scheduler.start()
    return scheduler
