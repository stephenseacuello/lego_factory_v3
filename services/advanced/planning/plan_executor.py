"""
Plan Executor - Execute HTN plans with monitoring.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 1: Multi-Agent Orchestration Framework
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import logging

from .htn_planner import Plan, Task

logger = logging.getLogger(__name__)


class ExecutionState(Enum):
    """Task execution states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED = "paused"


@dataclass
class TaskExecution:
    """Execution record for a task."""
    task: Task
    state: ExecutionState = ExecutionState.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retries: int = 0


@dataclass
class PlanExecution:
    """Full plan execution state."""
    plan: Plan
    task_executions: List[TaskExecution]
    current_index: int = 0
    state: ExecutionState = ExecutionState.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    world_state: Dict[str, Any] = field(default_factory=dict)


class PlanExecutor:
    """
    Execute HTN plans with real-time monitoring.

    Features:
    - Step-by-step execution
    - Pause/resume capability
    - Error handling and retry
    - State tracking
    - Event callbacks
    """

    def __init__(self,
                 task_executor: Callable[[Task, Dict[str, Any]], Dict[str, Any]],
                 max_retries: int = 3):
        self.task_executor = task_executor
        self.max_retries = max_retries
        self._active_executions: Dict[str, PlanExecution] = {}
        self._callbacks: Dict[str, List[Callable]] = {
            'task_started': [],
            'task_completed': [],
            'task_failed': [],
            'plan_completed': [],
            'plan_failed': [],
        }

    def on(self, event: str, callback: Callable) -> None:
        """Register event callback."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _emit(self, event: str, *args, **kwargs) -> None:
        """Emit event to callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def execute(self, plan: Plan) -> PlanExecution:
        """
        Execute a complete plan.

        Args:
            plan: Plan to execute

        Returns:
            PlanExecution with results
        """
        execution = PlanExecution(
            plan=plan,
            task_executions=[TaskExecution(task=t) for t in plan.tasks],
            world_state=plan.initial_state.copy(),
            started_at=datetime.utcnow()
        )

        self._active_executions[plan.plan_id] = execution
        execution.state = ExecutionState.RUNNING

        try:
            while execution.current_index < len(plan.tasks):
                if execution.state == ExecutionState.PAUSED:
                    await asyncio.sleep(0.1)
                    continue

                task_exec = execution.task_executions[execution.current_index]
                success = await self._execute_task(task_exec, execution.world_state)

                if success:
                    # Apply effects to world state
                    execution.world_state = task_exec.task.apply_effects(
                        execution.world_state
                    )
                    execution.current_index += 1
                else:
                    if task_exec.retries >= self.max_retries:
                        execution.state = ExecutionState.FAILED
                        self._emit('plan_failed', execution, task_exec.error)
                        break
                    task_exec.retries += 1
                    logger.warning(f"Retrying task {task_exec.task.name}")

            if execution.state == ExecutionState.RUNNING:
                execution.state = ExecutionState.COMPLETED
                execution.completed_at = datetime.utcnow()
                self._emit('plan_completed', execution)

        except Exception as e:
            execution.state = ExecutionState.FAILED
            logger.error(f"Plan execution failed: {e}")
            self._emit('plan_failed', execution, str(e))

        return execution

    async def _execute_task(self,
                           task_exec: TaskExecution,
                           world_state: Dict[str, Any]) -> bool:
        """Execute a single task."""
        task = task_exec.task

        # Check preconditions
        if not task.check_preconditions(world_state):
            task_exec.state = ExecutionState.FAILED
            task_exec.error = "Preconditions not satisfied"
            self._emit('task_failed', task_exec)
            return False

        task_exec.state = ExecutionState.RUNNING
        task_exec.started_at = datetime.utcnow()
        self._emit('task_started', task_exec)

        try:
            # Execute task
            if asyncio.iscoroutinefunction(self.task_executor):
                result = await self.task_executor(task, world_state)
            else:
                result = self.task_executor(task, world_state)

            if result.get('success', True):
                task_exec.state = ExecutionState.COMPLETED
                task_exec.result = result
                task_exec.completed_at = datetime.utcnow()
                self._emit('task_completed', task_exec)
                return True
            else:
                task_exec.state = ExecutionState.FAILED
                task_exec.error = result.get('error', 'Unknown error')
                self._emit('task_failed', task_exec)
                return False

        except Exception as e:
            task_exec.state = ExecutionState.FAILED
            task_exec.error = str(e)
            self._emit('task_failed', task_exec)
            return False

    def pause(self, plan_id: str) -> bool:
        """Pause plan execution."""
        if plan_id in self._active_executions:
            self._active_executions[plan_id].state = ExecutionState.PAUSED
            return True
        return False

    def resume(self, plan_id: str) -> bool:
        """Resume paused execution."""
        if plan_id in self._active_executions:
            execution = self._active_executions[plan_id]
            if execution.state == ExecutionState.PAUSED:
                execution.state = ExecutionState.RUNNING
                return True
        return False

    def get_status(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get execution status."""
        if plan_id not in self._active_executions:
            return None

        execution = self._active_executions[plan_id]
        return {
            'plan_id': plan_id,
            'state': execution.state.value,
            'progress': f"{execution.current_index}/{len(execution.plan.tasks)}",
            'current_task': (
                execution.plan.tasks[execution.current_index].name
                if execution.current_index < len(execution.plan.tasks)
                else None
            ),
            'elapsed': (
                (datetime.utcnow() - execution.started_at).total_seconds()
                if execution.started_at else 0
            )
        }
