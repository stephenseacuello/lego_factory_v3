"""
Manufacturing Orchestrator

Coordinates workflows across manufacturing services.
Implements ISA-95 compatible workflow patterns.

Reference: ISA-95, BPMN 2.0, IEC 62264
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import threading
import json

from .service_registry import ServiceRegistry, ServiceStatus, get_registry

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Individual step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """Single step in a workflow."""
    id: str
    name: str
    service: str  # Service to execute on
    action: str   # Action to perform
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # Step IDs
    timeout_seconds: int = 300
    retry_count: int = 3
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class WorkflowContext:
    """Workflow execution context."""
    workflow_id: str
    name: str
    description: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    tags: Set[str] = field(default_factory=set)


class ManufacturingOrchestrator:
    """
    Manufacturing Workflow Orchestrator.

    Coordinates complex manufacturing workflows across
    multiple services with dependency resolution.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._registry = get_registry()
        self._workflows: Dict[str, WorkflowContext] = {}
        self._action_handlers: Dict[str, Callable] = {}
        self._running_workflows: Set[str] = set()

        # Register default action handlers
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register default action handlers."""
        self._action_handlers.update({
            # Production operations
            "create_job": self._handle_create_job,
            "start_production": self._handle_start_production,
            "quality_check": self._handle_quality_check,
            "complete_job": self._handle_complete_job,

            # Material operations
            "reserve_material": self._handle_reserve_material,
            "release_material": self._handle_release_material,
            "update_inventory": self._handle_update_inventory,

            # Equipment operations
            "configure_machine": self._handle_configure_machine,
            "start_machine": self._handle_start_machine,
            "stop_machine": self._handle_stop_machine,

            # Data operations
            "collect_metrics": self._handle_collect_metrics,
            "generate_report": self._handle_generate_report,
            "send_notification": self._handle_send_notification,
        })

    def register_handler(
        self,
        action: str,
        handler: Callable[[Dict[str, Any]], Any]
    ) -> None:
        """Register action handler."""
        self._action_handlers[action] = handler

    def create_workflow(
        self,
        name: str,
        description: str = "",
        steps: Optional[List[WorkflowStep]] = None,
        tags: Optional[Set[str]] = None
    ) -> WorkflowContext:
        """Create a new workflow."""
        workflow = WorkflowContext(
            workflow_id=str(uuid.uuid4()),
            name=name,
            description=description,
            steps=steps or [],
            tags=tags or set()
        )

        self._workflows[workflow.workflow_id] = workflow
        logger.info(f"Created workflow: {workflow.workflow_id} - {name}")

        return workflow

    def add_step(
        self,
        workflow_id: str,
        name: str,
        service: str,
        action: str,
        parameters: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None
    ) -> Optional[WorkflowStep]:
        """Add a step to a workflow."""
        if workflow_id not in self._workflows:
            logger.error(f"Workflow not found: {workflow_id}")
            return None

        step = WorkflowStep(
            id=str(uuid.uuid4()),
            name=name,
            service=service,
            action=action,
            parameters=parameters or {},
            dependencies=dependencies or []
        )

        self._workflows[workflow_id].steps.append(step)
        return step

    async def execute_workflow(self, workflow_id: str) -> WorkflowContext:
        """Execute a workflow."""
        if workflow_id not in self._workflows:
            raise ValueError(f"Workflow not found: {workflow_id}")

        workflow = self._workflows[workflow_id]

        if workflow_id in self._running_workflows:
            raise RuntimeError(f"Workflow already running: {workflow_id}")

        self._running_workflows.add(workflow_id)
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now()

        logger.info(f"Starting workflow: {workflow.name} ({workflow_id})")

        try:
            await self._execute_steps(workflow)

            # Check if all steps completed
            failed = [s for s in workflow.steps if s.status == StepStatus.FAILED]
            if failed:
                workflow.status = WorkflowStatus.FAILED
                workflow.error = f"Steps failed: {[s.name for s in failed]}"
            else:
                workflow.status = WorkflowStatus.COMPLETED

        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.error = str(e)
            logger.error(f"Workflow failed: {e}")

        finally:
            workflow.completed_at = datetime.now()
            self._running_workflows.discard(workflow_id)

        return workflow

    async def _execute_steps(self, workflow: WorkflowContext) -> None:
        """Execute workflow steps with dependency resolution."""
        completed = set()
        pending = {s.id: s for s in workflow.steps}

        while pending:
            # Find steps whose dependencies are met
            ready = []
            for step_id, step in pending.items():
                deps_met = all(d in completed for d in step.dependencies)
                if deps_met:
                    ready.append(step)

            if not ready:
                if pending:
                    raise RuntimeError("Circular dependency or unresolvable steps")
                break

            # Execute ready steps in parallel
            tasks = [self._execute_step(step, workflow) for step in ready]
            await asyncio.gather(*tasks)

            # Update tracking
            for step in ready:
                if step.status == StepStatus.COMPLETED:
                    completed.add(step.id)
                del pending[step.id]

    async def _execute_step(
        self,
        step: WorkflowStep,
        workflow: WorkflowContext
    ) -> None:
        """Execute a single step."""
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now()

        logger.info(f"Executing step: {step.name} ({step.action})")

        # Check if service is healthy
        service = self._registry.get_service(step.service)
        if service and service.health.status != ServiceStatus.HEALTHY:
            logger.warning(f"Service {step.service} is not healthy")

        # Get action handler
        handler = self._action_handlers.get(step.action)
        if not handler:
            step.status = StepStatus.FAILED
            step.error = f"Unknown action: {step.action}"
            return

        # Execute with retry
        for attempt in range(step.retry_count):
            try:
                # Resolve parameter variables
                params = self._resolve_variables(step.parameters, workflow.variables)

                # Execute action
                result = await asyncio.wait_for(
                    self._run_handler(handler, params),
                    timeout=step.timeout_seconds
                )

                step.result = result
                step.status = StepStatus.COMPLETED
                step.completed_at = datetime.now()

                # Store result in workflow variables if needed
                if isinstance(result, dict):
                    workflow.variables.update(result)

                logger.info(f"Step completed: {step.name}")
                return

            except asyncio.TimeoutError:
                step.error = f"Timeout after {step.timeout_seconds}s"
                logger.warning(f"Step timeout: {step.name} (attempt {attempt + 1})")

            except Exception as e:
                step.error = str(e)
                logger.warning(f"Step error: {step.name} - {e} (attempt {attempt + 1})")

            if attempt < step.retry_count - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        step.status = StepStatus.FAILED
        step.completed_at = datetime.now()

    async def _run_handler(
        self,
        handler: Callable,
        params: Dict[str, Any]
    ) -> Any:
        """Run action handler (sync or async)."""
        if asyncio.iscoroutinefunction(handler):
            return await handler(params)
        else:
            return await asyncio.get_event_loop().run_in_executor(
                None, handler, params
            )

    def _resolve_variables(
        self,
        params: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve variable references in parameters."""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$"):
                var_name = value[1:]
                resolved[key] = variables.get(var_name, value)
            else:
                resolved[key] = value
        return resolved

    def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a running workflow."""
        if workflow_id in self._workflows:
            self._workflows[workflow_id].status = WorkflowStatus.PAUSED
            return True
        return False

    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a workflow."""
        if workflow_id in self._workflows:
            self._workflows[workflow_id].status = WorkflowStatus.CANCELLED
            self._running_workflows.discard(workflow_id)
            return True
        return False

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowContext]:
        """Get workflow by ID."""
        return self._workflows.get(workflow_id)

    def get_active_workflows(self) -> List[WorkflowContext]:
        """Get all active workflows."""
        return [
            w for w in self._workflows.values()
            if w.status in (WorkflowStatus.PENDING, WorkflowStatus.RUNNING, WorkflowStatus.PAUSED)
        ]

    # Default action handlers
    async def _handle_create_job(self, params: Dict[str, Any]) -> Dict[str, Any]:
        job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        return {"job_id": job_id, "status": "created"}

    async def _handle_start_production(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "started", "timestamp": datetime.now().isoformat()}

    async def _handle_quality_check(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"passed": True, "score": 0.98, "checks": ["visual", "dimensional"]}

    async def _handle_complete_job(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "completed", "timestamp": datetime.now().isoformat()}

    async def _handle_reserve_material(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"reserved": True, "material_id": params.get("material_id")}

    async def _handle_release_material(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"released": True}

    async def _handle_update_inventory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"updated": True}

    async def _handle_configure_machine(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"configured": True, "machine_id": params.get("machine_id")}

    async def _handle_start_machine(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"started": True}

    async def _handle_stop_machine(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"stopped": True}

    async def _handle_collect_metrics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"metrics_collected": True, "count": 10}

    async def _handle_generate_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"report_id": f"RPT-{uuid.uuid4().hex[:8]}", "generated": True}

    async def _handle_send_notification(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"sent": True, "recipient": params.get("recipient")}


def get_orchestrator() -> ManufacturingOrchestrator:
    """Get global orchestrator instance."""
    return ManufacturingOrchestrator()


# Pre-built workflow templates

def create_production_workflow(
    job_name: str,
    product_id: str,
    quantity: int
) -> WorkflowContext:
    """Create standard production workflow."""
    orchestrator = get_orchestrator()

    workflow = orchestrator.create_workflow(
        name=f"Production: {job_name}",
        description=f"Produce {quantity} units of {product_id}",
        tags={"production", "automated"}
    )

    # Step 1: Create job
    step1 = orchestrator.add_step(
        workflow.workflow_id,
        name="Create Production Job",
        service="mes",
        action="create_job",
        parameters={"product_id": product_id, "quantity": quantity}
    )

    # Step 2: Reserve materials
    step2 = orchestrator.add_step(
        workflow.workflow_id,
        name="Reserve Materials",
        service="inventory",
        action="reserve_material",
        parameters={"product_id": product_id, "quantity": quantity},
        dependencies=[step1.id] if step1 else []
    )

    # Step 3: Configure machine
    step3 = orchestrator.add_step(
        workflow.workflow_id,
        name="Configure Machine",
        service="cnc",
        action="configure_machine",
        parameters={"product_id": product_id},
        dependencies=[step2.id] if step2 else []
    )

    # Step 4: Start production
    step4 = orchestrator.add_step(
        workflow.workflow_id,
        name="Start Production",
        service="mes",
        action="start_production",
        parameters={"job_id": "$job_id"},
        dependencies=[step3.id] if step3 else []
    )

    # Step 5: Quality check
    step5 = orchestrator.add_step(
        workflow.workflow_id,
        name="Quality Inspection",
        service="quality",
        action="quality_check",
        parameters={"job_id": "$job_id"},
        dependencies=[step4.id] if step4 else []
    )

    # Step 6: Complete job
    orchestrator.add_step(
        workflow.workflow_id,
        name="Complete Job",
        service="mes",
        action="complete_job",
        parameters={"job_id": "$job_id"},
        dependencies=[step5.id] if step5 else []
    )

    return workflow
