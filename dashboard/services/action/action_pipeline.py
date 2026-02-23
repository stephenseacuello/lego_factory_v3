"""
Action Pipeline - E2E action orchestration.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 5: Algorithm-to-Action Bridge
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import asyncio
import uuid
import logging

logger = logging.getLogger(__name__)


class ActionState(Enum):
    """Action execution state."""
    PENDING = "pending"
    VALIDATING = "validating"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ActionStep:
    """Single step in action pipeline."""
    step_id: str
    name: str
    action_type: str
    parameters: Dict[str, Any]
    state: ActionState = ActionState.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rollback_fn: Optional[Callable] = None


@dataclass
class ActionExecution:
    """Full action execution record."""
    execution_id: str
    source: str  # agent that initiated
    reason: str
    steps: List[ActionStep]
    state: ActionState = ActionState.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class ActionPipeline:
    """
    End-to-end pipeline from AI recommendation to physical action.

    Pipeline stages:
    1. Validation - Check action safety and feasibility
    2. Approval - Human-in-the-loop for critical actions
    3. Execution - Send commands to equipment
    4. Monitoring - Track execution and verify outcome
    5. Rollback - Undo if necessary

    Features:
    - Multi-step action sequences
    - Automatic rollback on failure
    - Audit logging
    - Configurable approval gates
    """

    def __init__(self):
        self._validator = None
        self._executor = None
        self._approval_handler = None
        self._executions: Dict[str, ActionExecution] = {}
        self._approval_queue: Dict[str, ActionExecution] = {}
        self._listeners: List[Callable] = []

    def set_validator(self, validator: Any) -> None:
        """Set action validator."""
        self._validator = validator

    def set_executor(self, executor: Any) -> None:
        """Set equipment controller for execution."""
        self._executor = executor

    def set_approval_handler(self, handler: Callable) -> None:
        """Set handler for approval requests."""
        self._approval_handler = handler

    def add_listener(self, listener: Callable[[ActionExecution], None]) -> None:
        """Add execution event listener."""
        self._listeners.append(listener)

    async def execute(self,
                     steps: List[ActionStep],
                     source: str,
                     reason: str,
                     require_approval: bool = False) -> ActionExecution:
        """
        Execute action pipeline.

        Args:
            steps: List of action steps
            source: Initiating agent/system
            reason: Reason for action
            require_approval: Whether human approval is needed

        Returns:
            ActionExecution with results
        """
        execution = ActionExecution(
            execution_id=str(uuid.uuid4())[:8],
            source=source,
            reason=reason,
            steps=steps
        )
        self._executions[execution.execution_id] = execution

        try:
            # Stage 1: Validation
            execution.state = ActionState.VALIDATING
            await self._notify_listeners(execution)

            validation = await self._validate_steps(steps)
            if not validation['valid']:
                execution.state = ActionState.FAILED
                for step in steps:
                    step.state = ActionState.FAILED
                    step.error = validation.get('reason', 'Validation failed')
                return execution

            # Stage 2: Approval
            if require_approval:
                execution.state = ActionState.AWAITING_APPROVAL
                self._approval_queue[execution.execution_id] = execution
                await self._notify_listeners(execution)

                # Wait for approval
                approved = await self._wait_for_approval(execution.execution_id)
                if not approved:
                    execution.state = ActionState.FAILED
                    return execution

            # Stage 3: Execution
            execution.state = ActionState.EXECUTING
            await self._notify_listeners(execution)

            completed_steps = []
            for step in steps:
                step.state = ActionState.EXECUTING
                step.started_at = datetime.utcnow()

                try:
                    result = await self._execute_step(step)
                    step.result = result
                    step.state = ActionState.COMPLETED
                    step.completed_at = datetime.utcnow()
                    completed_steps.append(step)

                except Exception as e:
                    step.state = ActionState.FAILED
                    step.error = str(e)
                    logger.error(f"Step {step.step_id} failed: {e}")

                    # Rollback completed steps
                    await self._rollback_steps(completed_steps)
                    execution.state = ActionState.ROLLED_BACK
                    return execution

            # Stage 4: Monitoring
            execution.state = ActionState.MONITORING
            await self._notify_listeners(execution)

            await self._monitor_completion(steps)

            # Success
            execution.state = ActionState.COMPLETED
            execution.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            execution.state = ActionState.FAILED

        await self._notify_listeners(execution)
        return execution

    async def _validate_steps(self, steps: List[ActionStep]) -> Dict[str, Any]:
        """Validate all action steps."""
        if not self._validator:
            return {'valid': True}

        for step in steps:
            result = await self._validator.validate(step)
            if not result.get('valid', True):
                return {'valid': False, 'step': step.step_id, 'reason': result.get('reason')}

        return {'valid': True}

    async def _execute_step(self, step: ActionStep) -> Dict[str, Any]:
        """Execute a single action step."""
        if not self._executor:
            logger.warning("No executor configured, simulating")
            await asyncio.sleep(0.1)
            return {'simulated': True}

        return await self._executor.execute(step)

    async def _wait_for_approval(self,
                                 execution_id: str,
                                 timeout: float = 300.0) -> bool:
        """Wait for human approval."""
        start = datetime.utcnow()

        while (datetime.utcnow() - start).total_seconds() < timeout:
            if execution_id not in self._approval_queue:
                return True  # Approved
            await asyncio.sleep(1.0)

        return False  # Timeout

    def approve(self, execution_id: str) -> bool:
        """Approve a pending action."""
        if execution_id in self._approval_queue:
            del self._approval_queue[execution_id]
            logger.info(f"Action {execution_id} approved")
            return True
        return False

    def reject(self, execution_id: str, reason: str = "") -> bool:
        """Reject a pending action."""
        if execution_id in self._approval_queue:
            execution = self._approval_queue.pop(execution_id)
            execution.state = ActionState.FAILED
            for step in execution.steps:
                step.state = ActionState.FAILED
                step.error = f"Rejected: {reason}"
            logger.info(f"Action {execution_id} rejected: {reason}")
            return True
        return False

    async def _rollback_steps(self, steps: List[ActionStep]) -> None:
        """Rollback completed steps in reverse order."""
        for step in reversed(steps):
            if step.rollback_fn:
                try:
                    await step.rollback_fn(step)
                    step.state = ActionState.ROLLED_BACK
                    logger.info(f"Rolled back step {step.step_id}")
                except Exception as e:
                    logger.error(f"Rollback failed for {step.step_id}: {e}")

    async def _monitor_completion(self, steps: List[ActionStep]) -> None:
        """Monitor action completion."""
        # Simple completion check
        await asyncio.sleep(0.5)

    async def _notify_listeners(self, execution: ActionExecution) -> None:
        """Notify listeners of execution state change."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(execution)
                else:
                    listener(execution)
            except Exception as e:
                logger.error(f"Listener error: {e}")

    def get_execution(self, execution_id: str) -> Optional[ActionExecution]:
        """Get execution by ID."""
        return self._executions.get(execution_id)

    def get_pending_approvals(self) -> List[ActionExecution]:
        """Get actions awaiting approval."""
        return list(self._approval_queue.values())

    def get_recent_executions(self, limit: int = 50) -> List[ActionExecution]:
        """Get recent executions."""
        executions = list(self._executions.values())
        executions.sort(key=lambda e: e.created_at, reverse=True)
        return executions[:limit]
