"""
LEGO Factory v3 - Cell Orchestrator
====================================
Multi-robot cell coordination and task sequencing.
"""

import logging
import asyncio
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from queue import PriorityQueue
import uuid
import json

from services.robotics.ros2_bridge import get_ros2_bridge, ROS2Bridge

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    """Task execution states."""
    PENDING = 'pending'
    QUEUED = 'queued'
    EXECUTING = 'executing'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class TaskType(str, Enum):
    """Standard task types."""
    PICK_PLACE = 'pick_place'
    ASSEMBLY = 'assembly'
    INSPECTION = 'inspection'
    TRANSPORT = 'transport'
    CUSTOM = 'custom'


@dataclass
class RobotTask:
    """Task for robot execution."""
    task_id: str
    task_type: TaskType
    robot_id: str
    priority: int = 5  # 1=highest, 10=lowest
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # Task IDs that must complete first
    state: TaskState = TaskState.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ''
    retry_count: int = 0
    max_retries: int = 3

    def __lt__(self, other):
        """For priority queue ordering."""
        return self.priority < other.priority

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'task_type': self.task_type.value,
            'robot_id': self.robot_id,
            'priority': self.priority,
            'parameters': self.parameters,
            'dependencies': self.dependencies,
            'state': self.state.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result': self.result,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
        }


@dataclass
class WorkCell:
    """Factory work cell definition."""
    cell_id: str
    name: str
    robots: List[str]
    fixtures: List[str] = field(default_factory=list)
    stations: List[str] = field(default_factory=list)
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'cell_id': self.cell_id,
            'name': self.name,
            'robots': self.robots,
            'fixtures': self.fixtures,
            'stations': self.stations,
            'active': self.active,
        }


class CellOrchestrator:
    """
    Orchestrates multi-robot operations in a work cell.

    Features:
    - Task queuing and prioritization
    - Dependency management
    - Collision avoidance coordination
    - Robot load balancing
    - Error recovery
    """

    def __init__(self, ros2_bridge: ROS2Bridge = None):
        self.ros2_bridge = ros2_bridge or get_ros2_bridge()

        # Task management
        self.tasks: Dict[str, RobotTask] = {}
        self.task_queue: PriorityQueue = PriorityQueue()
        self._task_lock = threading.Lock()

        # Work cells
        self.work_cells: Dict[str, WorkCell] = {
            'cell_1': WorkCell(
                cell_id='cell_1',
                name='LEGO Assembly Cell',
                robots=['niryo_ned2', 'xarm_lite6'],
                fixtures=['brick_feeder', 'build_plate'],
                stations=['station_a', 'station_b'],
            )
        }

        # Robot availability
        self.robot_busy: Dict[str, bool] = {}
        self.robot_current_task: Dict[str, str] = {}

        # Execution control
        self._running = False
        self._executor_thread: Optional[threading.Thread] = None
        self._paused = False

        # Callbacks
        self._task_callbacks: List[callable] = []

    def start(self):
        """Start the orchestrator."""
        if self._running:
            return

        self._running = True
        self._executor_thread = threading.Thread(target=self._execution_loop, daemon=True)
        self._executor_thread.start()
        logger.info("Cell orchestrator started")

    def stop(self):
        """Stop the orchestrator."""
        self._running = False
        if self._executor_thread:
            self._executor_thread.join(timeout=5.0)
        logger.info("Cell orchestrator stopped")

    def pause(self):
        """Pause task execution."""
        self._paused = True
        logger.info("Cell orchestrator paused")

    def resume(self):
        """Resume task execution."""
        self._paused = False
        logger.info("Cell orchestrator resumed")

    def submit_task(
        self,
        task_type: str,
        robot_id: str = None,
        parameters: Dict[str, Any] = None,
        priority: int = 5,
        dependencies: List[str] = None
    ) -> str:
        """Submit a task for execution."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        # Auto-assign robot if not specified
        if not robot_id:
            robot_id = self._select_best_robot(task_type, parameters)

        task = RobotTask(
            task_id=task_id,
            task_type=TaskType(task_type),
            robot_id=robot_id,
            priority=priority,
            parameters=parameters or {},
            dependencies=dependencies or [],
        )

        with self._task_lock:
            self.tasks[task_id] = task

        logger.info(f"Task submitted: {task_id} ({task_type}) for robot {robot_id}")
        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or queued task."""
        with self._task_lock:
            if task_id not in self.tasks:
                return False

            task = self.tasks[task_id]
            if task.state in (TaskState.PENDING, TaskState.QUEUED):
                task.state = TaskState.CANCELLED
                logger.info(f"Task cancelled: {task_id}")
                return True

        return False

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status."""
        if task_id in self.tasks:
            return self.tasks[task_id].to_dict()
        return None

    def get_all_tasks(self, state: str = None) -> List[Dict[str, Any]]:
        """Get all tasks, optionally filtered by state."""
        tasks = list(self.tasks.values())
        if state:
            tasks = [t for t in tasks if t.state.value == state]
        return [t.to_dict() for t in tasks]

    def get_robot_queue(self, robot_id: str) -> List[Dict[str, Any]]:
        """Get queued tasks for a specific robot."""
        tasks = [
            t for t in self.tasks.values()
            if t.robot_id == robot_id and t.state in (TaskState.PENDING, TaskState.QUEUED)
        ]
        return sorted([t.to_dict() for t in tasks], key=lambda x: x['priority'])

    def _select_best_robot(self, task_type: str, parameters: Dict[str, Any]) -> str:
        """Select the best available robot for a task."""
        # Get available robots from default cell
        cell = self.work_cells.get('cell_1')
        if not cell:
            raise ValueError("No work cell configured")

        available_robots = [
            r for r in cell.robots
            if not self.robot_busy.get(r, False)
        ]

        if not available_robots:
            # All busy, assign to least loaded
            robot_loads = {}
            for robot_id in cell.robots:
                load = len([
                    t for t in self.tasks.values()
                    if t.robot_id == robot_id and t.state in (TaskState.PENDING, TaskState.QUEUED)
                ])
                robot_loads[robot_id] = load

            return min(robot_loads, key=robot_loads.get)

        # Prefer niryo for precision, xarm for speed
        if task_type == 'assembly' and 'niryo_ned2' in available_robots:
            return 'niryo_ned2'
        elif task_type == 'transport' and 'xarm_lite6' in available_robots:
            return 'xarm_lite6'

        return available_robots[0]

    def _execution_loop(self):
        """Main execution loop."""
        while self._running:
            if self._paused:
                asyncio.sleep(0.1)
                continue

            try:
                self._process_pending_tasks()
                self._execute_ready_tasks()
            except Exception as e:
                logger.error(f"Execution loop error: {e}")

            # Small delay to prevent busy-waiting
            import time
            time.sleep(0.1)

    def _process_pending_tasks(self):
        """Move pending tasks to queue when dependencies are met."""
        with self._task_lock:
            for task in list(self.tasks.values()):
                if task.state != TaskState.PENDING:
                    continue

                # Check dependencies
                deps_met = all(
                    self.tasks.get(dep_id, RobotTask('', TaskType.CUSTOM, '')).state == TaskState.COMPLETED
                    for dep_id in task.dependencies
                )

                if deps_met:
                    task.state = TaskState.QUEUED
                    self.task_queue.put((task.priority, task.task_id))
                    logger.debug(f"Task {task.task_id} queued")

    def _execute_ready_tasks(self):
        """Execute tasks that are ready to run."""
        # Get tasks from queue for available robots
        with self._task_lock:
            # Find available robots
            available_robots = set()
            for cell in self.work_cells.values():
                for robot_id in cell.robots:
                    if not self.robot_busy.get(robot_id, False):
                        available_robots.add(robot_id)

            # Try to assign tasks to available robots
            tasks_to_execute = []
            temp_queue = []

            while not self.task_queue.empty():
                priority, task_id = self.task_queue.get()
                task = self.tasks.get(task_id)

                if not task or task.state != TaskState.QUEUED:
                    continue

                if task.robot_id in available_robots:
                    tasks_to_execute.append(task)
                    available_robots.remove(task.robot_id)
                else:
                    temp_queue.append((priority, task_id))

            # Put unexecuted tasks back
            for item in temp_queue:
                self.task_queue.put(item)

        # Execute tasks (outside lock)
        for task in tasks_to_execute:
            self._execute_task(task)

    def _execute_task(self, task: RobotTask):
        """Execute a single task."""
        task.state = TaskState.EXECUTING
        task.started_at = datetime.utcnow()
        self.robot_busy[task.robot_id] = True
        self.robot_current_task[task.robot_id] = task.task_id

        logger.info(f"Executing task {task.task_id} on robot {task.robot_id}")

        try:
            # Build command based on task type
            command_type, command_params = self._build_command(task)

            # Execute via ROS2 bridge
            result = self.ros2_bridge.execute_command(
                task.robot_id,
                command_type,
                command_params
            )

            if result['success']:
                task.state = TaskState.COMPLETED
                task.result = result.get('result', {})
                logger.info(f"Task {task.task_id} completed successfully")
            else:
                raise Exception(result.get('message', 'Command failed'))

        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}")
            task.error_message = str(e)
            task.retry_count += 1

            if task.retry_count < task.max_retries:
                task.state = TaskState.QUEUED
                self.task_queue.put((task.priority, task.task_id))
                logger.info(f"Task {task.task_id} queued for retry ({task.retry_count}/{task.max_retries})")
            else:
                task.state = TaskState.FAILED
                logger.error(f"Task {task.task_id} failed after {task.max_retries} retries")

        finally:
            task.completed_at = datetime.utcnow()
            self.robot_busy[task.robot_id] = False
            self.robot_current_task.pop(task.robot_id, None)
            self._notify_task_update(task)

    def _build_command(self, task: RobotTask) -> tuple:
        """Build ROS2 command from task."""
        params = task.parameters.copy()

        if task.task_type == TaskType.PICK_PLACE:
            return 'pick_place', {
                'pick_pose': params.get('pick_pose'),
                'place_pose': params.get('place_pose'),
                'approach_height': params.get('approach_height', 0.05),
                'grip_force': params.get('grip_force', 50),
            }

        elif task.task_type == TaskType.ASSEMBLY:
            return 'assembly', {
                'components': params.get('components', []),
                'assembly_pose': params.get('assembly_pose'),
                'sequence': params.get('sequence'),
            }

        elif task.task_type == TaskType.INSPECTION:
            return 'inspection', {
                'inspection_pose': params.get('inspection_pose'),
                'camera_id': params.get('camera_id'),
            }

        elif task.task_type == TaskType.TRANSPORT:
            return 'move_pose', {
                'target_pose': params.get('target_pose'),
                'velocity_scale': params.get('velocity_scale', 0.5),
            }

        else:
            return 'custom', params

    def _notify_task_update(self, task: RobotTask):
        """Notify callbacks of task state change."""
        for callback in self._task_callbacks:
            try:
                callback(task.to_dict())
            except Exception as e:
                logger.error(f"Task callback error: {e}")

    def register_task_callback(self, callback: callable):
        """Register a callback for task state changes."""
        self._task_callbacks.append(callback)

    def get_cell_status(self, cell_id: str = 'cell_1') -> Dict[str, Any]:
        """Get work cell status."""
        cell = self.work_cells.get(cell_id)
        if not cell:
            return {'error': 'Cell not found'}

        robot_states = []
        for robot_id in cell.robots:
            state = self.ros2_bridge.get_robot_state(robot_id)
            if state:
                state['busy'] = self.robot_busy.get(robot_id, False)
                state['current_task'] = self.robot_current_task.get(robot_id)
                robot_states.append(state)

        pending_tasks = len([t for t in self.tasks.values() if t.state == TaskState.PENDING])
        queued_tasks = len([t for t in self.tasks.values() if t.state == TaskState.QUEUED])
        executing_tasks = len([t for t in self.tasks.values() if t.state == TaskState.EXECUTING])

        return {
            'cell': cell.to_dict(),
            'robots': robot_states,
            'tasks': {
                'pending': pending_tasks,
                'queued': queued_tasks,
                'executing': executing_tasks,
            },
            'paused': self._paused,
            'running': self._running,
        }


# Global orchestrator instance
_orchestrator: Optional[CellOrchestrator] = None


def get_orchestrator() -> CellOrchestrator:
    """Get or create orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CellOrchestrator()
    return _orchestrator


def start_orchestrator():
    """Start the cell orchestrator."""
    orchestrator = get_orchestrator()
    orchestrator.start()


def stop_orchestrator():
    """Stop the cell orchestrator."""
    global _orchestrator
    if _orchestrator:
        _orchestrator.stop()
        _orchestrator = None
