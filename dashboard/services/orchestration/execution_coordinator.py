"""
Execution Coordinator Service
=============================

Coordinates action execution across multiple systems:
- ROS2 equipment control
- Database updates
- External integrations
- Rollback handling

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


class ExecutionTarget(Enum):
    """Execution target systems"""
    ROS2 = "ros2"
    DATABASE = "database"
    MCP_SERVER = "mcp_server"
    EXTERNAL_API = "external_api"
    WEBHOOK = "webhook"


class StepStatus(Enum):
    """Execution step status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"


@dataclass
class ExecutionStep:
    """Single execution step"""
    id: str
    name: str
    target: ExecutionTarget
    command: str
    parameters: Dict[str, Any]
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    rollback_command: Optional[str] = None
    timeout_seconds: float = 30.0
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "target": self.target.value,
            "command": self.command,
            "parameters": self.parameters,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "rollback_command": self.rollback_command,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count
        }


@dataclass
class ExecutionPlan:
    """Complete execution plan with multiple steps"""
    id: str
    name: str
    description: str
    steps: List[ExecutionStep]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, running, completed, failed, rolled_back
    current_step_index: int = 0
    parallel_execution: bool = False
    stop_on_error: bool = True
    auto_rollback: bool = True
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "current_step_index": self.current_step_index,
            "parallel_execution": self.parallel_execution,
            "stop_on_error": self.stop_on_error,
            "auto_rollback": self.auto_rollback,
            "progress": self.progress
        }

    @property
    def progress(self) -> float:
        """Calculate execution progress"""
        if not self.steps:
            return 0.0
        completed = sum(
            1 for s in self.steps
            if s.status in [StepStatus.COMPLETED, StepStatus.SKIPPED]
        )
        return (completed / len(self.steps)) * 100


class ExecutionCoordinator:
    """
    Coordinates multi-system execution plans.

    Handles sequential and parallel step execution,
    error handling, and automatic rollback.
    """

    def __init__(self):
        """Initialize coordinator"""
        self._plans: Dict[str, ExecutionPlan] = {}
        self._executors: Dict[ExecutionTarget, Callable] = {}
        self._callbacks: List[Callable[[ExecutionPlan], None]] = []

        # Register default executors
        self._register_default_executors()

    def _register_default_executors(self):
        """Register default target executors"""
        self.register_executor(ExecutionTarget.ROS2, self._execute_ros2)
        self.register_executor(ExecutionTarget.DATABASE, self._execute_database)
        self.register_executor(ExecutionTarget.MCP_SERVER, self._execute_mcp)
        self.register_executor(ExecutionTarget.EXTERNAL_API, self._execute_api)
        self.register_executor(ExecutionTarget.WEBHOOK, self._execute_webhook)

    def register_executor(
        self,
        target: ExecutionTarget,
        executor: Callable[[ExecutionStep], Dict[str, Any]]
    ):
        """Register an executor for a target"""
        self._executors[target] = executor

    def create_plan(
        self,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
        parallel: bool = False,
        stop_on_error: bool = True,
        auto_rollback: bool = True,
        context: Dict[str, Any] = None
    ) -> ExecutionPlan:
        """
        Create an execution plan.

        Args:
            name: Plan name
            description: Plan description
            steps: List of step definitions
            parallel: Execute steps in parallel
            stop_on_error: Stop on first error
            auto_rollback: Auto-rollback on failure
            context: Shared execution context

        Returns:
            ExecutionPlan object
        """
        execution_steps = []
        for step_def in steps:
            step = ExecutionStep(
                id=str(uuid.uuid4()),
                name=step_def.get("name", "Unnamed Step"),
                target=ExecutionTarget(step_def.get("target", "database")),
                command=step_def.get("command", ""),
                parameters=step_def.get("parameters", {}),
                rollback_command=step_def.get("rollback_command"),
                timeout_seconds=step_def.get("timeout", 30.0),
                max_retries=step_def.get("max_retries", 3)
            )
            execution_steps.append(step)

        plan = ExecutionPlan(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            steps=execution_steps,
            created_at=datetime.now(),
            parallel_execution=parallel,
            stop_on_error=stop_on_error,
            auto_rollback=auto_rollback,
            context=context or {}
        )

        self._plans[plan.id] = plan
        logger.info(f"Execution plan created: {plan.id} - {name}")

        return plan

    async def execute_plan(self, plan_id: str) -> ExecutionPlan:
        """
        Execute a plan.

        Args:
            plan_id: Plan ID to execute

        Returns:
            Updated ExecutionPlan
        """
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")

        plan.status = "running"
        plan.started_at = datetime.now()

        try:
            if plan.parallel_execution:
                await self._execute_parallel(plan)
            else:
                await self._execute_sequential(plan)

            # Check for failures
            failed_steps = [s for s in plan.steps if s.status == StepStatus.FAILED]
            if failed_steps:
                plan.status = "failed"
                if plan.auto_rollback:
                    await self._rollback_plan(plan)
            else:
                plan.status = "completed"

        except Exception as e:
            logger.error(f"Plan execution error: {e}")
            plan.status = "failed"
            if plan.auto_rollback:
                await self._rollback_plan(plan)

        plan.completed_at = datetime.now()

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(plan)
            except Exception as e:
                logger.error(f"Plan callback error: {e}")

        return plan

    async def _execute_sequential(self, plan: ExecutionPlan):
        """Execute steps sequentially"""
        for i, step in enumerate(plan.steps):
            plan.current_step_index = i

            success = await self._execute_step(step, plan.context)

            if not success and plan.stop_on_error:
                logger.warning(f"Stopping plan at step {i} due to error")
                break

    async def _execute_parallel(self, plan: ExecutionPlan):
        """Execute steps in parallel"""
        tasks = [
            self._execute_step(step, plan.context)
            for step in plan.steps
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_step(
        self,
        step: ExecutionStep,
        context: Dict[str, Any]
    ) -> bool:
        """Execute a single step with retry logic"""
        executor = self._executors.get(step.target)
        if not executor:
            step.status = StepStatus.FAILED
            step.error = f"No executor for target: {step.target}"
            return False

        step.status = StepStatus.RUNNING
        step.started_at = datetime.now()

        while step.retry_count <= step.max_retries:
            try:
                # Inject context into parameters
                params = {**step.parameters, "_context": context}

                # Execute with timeout
                if asyncio.iscoroutinefunction(executor):
                    result = await asyncio.wait_for(
                        executor(step),
                        timeout=step.timeout_seconds
                    )
                else:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, executor, step),
                        timeout=step.timeout_seconds
                    )

                step.result = result
                step.status = StepStatus.COMPLETED
                step.completed_at = datetime.now()

                # Update context with result
                context[f"step_{step.id}_result"] = result

                logger.info(f"Step completed: {step.name}")
                return True

            except asyncio.TimeoutError:
                step.error = f"Step timed out after {step.timeout_seconds}s"
                step.retry_count += 1
                logger.warning(f"Step timeout: {step.name} (retry {step.retry_count})")

            except Exception as e:
                step.error = str(e)
                step.retry_count += 1
                logger.warning(f"Step error: {step.name} - {e} (retry {step.retry_count})")

        step.status = StepStatus.FAILED
        step.completed_at = datetime.now()
        return False

    async def _rollback_plan(self, plan: ExecutionPlan):
        """Rollback completed steps in reverse order"""
        logger.info(f"Rolling back plan: {plan.id}")

        # Get completed steps in reverse order
        completed_steps = [
            s for s in reversed(plan.steps)
            if s.status == StepStatus.COMPLETED and s.rollback_command
        ]

        for step in completed_steps:
            try:
                # Create rollback step
                rollback_step = ExecutionStep(
                    id=f"rollback_{step.id}",
                    name=f"Rollback: {step.name}",
                    target=step.target,
                    command=step.rollback_command,
                    parameters=step.parameters,
                    timeout_seconds=step.timeout_seconds
                )

                await self._execute_step(rollback_step, plan.context)
                step.status = StepStatus.ROLLED_BACK

            except Exception as e:
                logger.error(f"Rollback failed for step {step.name}: {e}")

        plan.status = "rolled_back"

    # Default executor implementations

    async def _execute_ros2(self, step: ExecutionStep) -> Dict[str, Any]:
        """Execute ROS2 command"""
        logger.info(f"Executing ROS2 command: {step.command}")
        try:
            from services.ros2_bridge import ROS2Bridge
            bridge = ROS2Bridge()

            # Parse command type
            if step.command.startswith("publish:"):
                topic = step.command.replace("publish:", "")
                bridge.publish(topic, step.parameters)
            elif step.command.startswith("service:"):
                service = step.command.replace("service:", "")
                return bridge.call_service(service, step.parameters)
            elif step.command.startswith("action:"):
                action = step.command.replace("action:", "")
                return bridge.send_goal(action, step.parameters)

            return {"status": "executed", "command": step.command}
        except Exception as e:
            logger.error(f"ROS2 execution error: {e}")
            raise

    async def _execute_database(self, step: ExecutionStep) -> Dict[str, Any]:
        """Execute database operation"""
        logger.info(f"Executing database command: {step.command}")
        try:
            from models.base import db

            if step.command == "insert":
                # Would execute insert
                return {"status": "inserted", "id": "new_id"}
            elif step.command == "update":
                # Would execute update
                return {"status": "updated", "count": 1}
            elif step.command == "delete":
                # Would execute delete
                return {"status": "deleted", "count": 1}

            return {"status": "executed"}
        except Exception as e:
            logger.error(f"Database execution error: {e}")
            raise

    async def _execute_mcp(self, step: ExecutionStep) -> Dict[str, Any]:
        """Execute MCP server command"""
        logger.info(f"Executing MCP command: {step.command}")
        try:
            from services.mcp_bridge import MCPBridge
            bridge = MCPBridge()
            return bridge.call_tool(step.command, step.parameters)
        except Exception as e:
            logger.error(f"MCP execution error: {e}")
            raise

    async def _execute_api(self, step: ExecutionStep) -> Dict[str, Any]:
        """Execute external API call"""
        logger.info(f"Executing API call: {step.command}")
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                method = step.parameters.get("method", "GET")
                url = step.command
                data = step.parameters.get("data")
                headers = step.parameters.get("headers", {})

                async with session.request(method, url, json=data, headers=headers) as response:
                    return {
                        "status_code": response.status,
                        "data": await response.json()
                    }
        except Exception as e:
            logger.error(f"API execution error: {e}")
            raise

    async def _execute_webhook(self, step: ExecutionStep) -> Dict[str, Any]:
        """Execute webhook call"""
        logger.info(f"Executing webhook: {step.command}")
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(step.command, json=step.parameters) as response:
                    return {
                        "status_code": response.status,
                        "success": response.status < 400
                    }
        except Exception as e:
            logger.error(f"Webhook execution error: {e}")
            raise

    def get_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Get plan by ID"""
        return self._plans.get(plan_id)

    def add_callback(self, callback: Callable[[ExecutionPlan], None]):
        """Add callback for plan completion"""
        self._callbacks.append(callback)


# Singleton instance
_coordinator: Optional[ExecutionCoordinator] = None


def get_execution_coordinator() -> ExecutionCoordinator:
    """Get or create the singleton coordinator instance"""
    global _coordinator
    if _coordinator is None:
        _coordinator = ExecutionCoordinator()
    return _coordinator
