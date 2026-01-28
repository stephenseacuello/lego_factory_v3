"""
V8 Workflow Manager
===================

Unified workflow management system integrating:
- Decision engine for AI recommendations
- Execution coordination
- Event correlation
- Approval workflows
- State machine transitions

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ============================================
# Workflow Enums
# ============================================

class WorkflowState(Enum):
    """Workflow lifecycle states."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowType(Enum):
    """Types of workflows."""
    PRODUCTION = "production"
    QUALITY = "quality"
    MAINTENANCE = "maintenance"
    LOGISTICS = "logistics"
    EMERGENCY = "emergency"
    CUSTOM = "custom"


class StepType(Enum):
    """Types of workflow steps."""
    TASK = "task"
    DECISION = "decision"
    PARALLEL = "parallel"
    APPROVAL = "approval"
    NOTIFICATION = "notification"
    DELAY = "delay"
    EQUIPMENT_CONTROL = "equipment_control"
    API_CALL = "api_call"


class ApprovalLevel(Enum):
    """Approval authority levels."""
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"
    MANAGER = "manager"
    DIRECTOR = "director"
    EXECUTIVE = "executive"


# ============================================
# Data Classes
# ============================================

@dataclass
class WorkflowStep:
    """Individual step in a workflow."""
    step_id: str
    name: str
    step_type: StepType
    description: str = ""
    executor: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 3600
    retry_count: int = 0
    max_retries: int = 3
    required_approval: Optional[ApprovalLevel] = None
    depends_on: List[str] = field(default_factory=list)
    state: WorkflowState = WorkflowState.DRAFT
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "step_type": self.step_type.value,
            "description": self.description,
            "executor": self.executor,
            "parameters": self.parameters,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "required_approval": self.required_approval.value if self.required_approval else None,
            "depends_on": self.depends_on,
            "state": self.state.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class WorkflowDefinition:
    """Template for creating workflows."""
    definition_id: str
    name: str
    workflow_type: WorkflowType
    description: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)
    parameters_schema: Dict[str, Any] = field(default_factory=dict)
    required_approval: Optional[ApprovalLevel] = None
    estimated_duration_minutes: int = 60
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "definition_id": self.definition_id,
            "name": self.name,
            "workflow_type": self.workflow_type.value,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "parameters_schema": self.parameters_schema,
            "required_approval": self.required_approval.value if self.required_approval else None,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "version": self.version,
        }


@dataclass
class WorkflowInstance:
    """Running instance of a workflow."""
    instance_id: str
    definition_id: str
    name: str
    workflow_type: WorkflowType
    state: WorkflowState = WorkflowState.DRAFT
    parameters: Dict[str, Any] = field(default_factory=dict)
    steps: List[WorkflowStep] = field(default_factory=list)
    current_step_index: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    created_by: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    job_id: Optional[str] = None
    parent_workflow_id: Optional[str] = None
    child_workflow_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    priority: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "definition_id": self.definition_id,
            "name": self.name,
            "workflow_type": self.workflow_type.value,
            "state": self.state.value,
            "parameters": self.parameters,
            "steps": [s.to_dict() for s in self.steps],
            "current_step_index": self.current_step_index,
            "context": self.context,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "job_id": self.job_id,
            "parent_workflow_id": self.parent_workflow_id,
            "child_workflow_ids": self.child_workflow_ids,
            "tags": self.tags,
            "priority": self.priority,
            "progress_percent": self._calculate_progress(),
        }

    def _calculate_progress(self) -> float:
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.state == WorkflowState.COMPLETED)
        return round((completed / len(self.steps)) * 100, 1)


@dataclass
class WorkflowEvent:
    """Event in workflow history."""
    event_id: str
    workflow_id: str
    event_type: str
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    user: str = "system"
    step_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "workflow_id": self.workflow_id,
            "event_type": self.event_type,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "user": self.user,
            "step_id": self.step_id,
            "data": self.data,
        }


# ============================================
# Workflow Manager
# ============================================

class WorkflowManager:
    """
    Unified workflow management system.

    Provides:
    - Workflow definition management
    - Workflow instance lifecycle
    - Step execution coordination
    - Approval workflows
    - Event tracking
    """

    def __init__(self):
        self._definitions: Dict[str, WorkflowDefinition] = {}
        self._instances: Dict[str, WorkflowInstance] = {}
        self._events: Dict[str, List[WorkflowEvent]] = {}
        self._lock = threading.RLock()
        self._step_executors: Dict[str, Callable] = {}
        self._event_handlers: List[Callable] = []

        # Register built-in step executors
        self._register_default_executors()

        # Register built-in workflow definitions
        self._register_default_definitions()

        logger.info("WorkflowManager initialized")

    def _register_default_executors(self):
        """Register default step executors."""
        self._step_executors = {
            "task": self._execute_task_step,
            "decision": self._execute_decision_step,
            "approval": self._execute_approval_step,
            "notification": self._execute_notification_step,
            "delay": self._execute_delay_step,
            "equipment_control": self._execute_equipment_step,
            "api_call": self._execute_api_step,
        }

    def _register_default_definitions(self):
        """Register built-in workflow definitions."""
        # Production workflow
        production_def = WorkflowDefinition(
            definition_id="wf-production-standard",
            name="Standard Production Workflow",
            workflow_type=WorkflowType.PRODUCTION,
            description="Standard workflow for manufacturing production jobs",
            steps=[
                WorkflowStep(
                    step_id="step-1",
                    name="Validate Job Parameters",
                    step_type=StepType.TASK,
                    executor="job_validator",
                ),
                WorkflowStep(
                    step_id="step-2",
                    name="Check Material Availability",
                    step_type=StepType.TASK,
                    executor="inventory_checker",
                    depends_on=["step-1"],
                ),
                WorkflowStep(
                    step_id="step-3",
                    name="Production Approval",
                    step_type=StepType.APPROVAL,
                    required_approval=ApprovalLevel.SUPERVISOR,
                    depends_on=["step-2"],
                ),
                WorkflowStep(
                    step_id="step-4",
                    name="Start Production",
                    step_type=StepType.EQUIPMENT_CONTROL,
                    executor="production_controller",
                    depends_on=["step-3"],
                ),
                WorkflowStep(
                    step_id="step-5",
                    name="Quality Inspection",
                    step_type=StepType.TASK,
                    executor="quality_inspector",
                    depends_on=["step-4"],
                ),
                WorkflowStep(
                    step_id="step-6",
                    name="Completion Notification",
                    step_type=StepType.NOTIFICATION,
                    depends_on=["step-5"],
                ),
            ],
            required_approval=ApprovalLevel.SUPERVISOR,
            estimated_duration_minutes=120,
            tags=["production", "manufacturing"],
        )
        self._definitions[production_def.definition_id] = production_def

        # Quality workflow
        quality_def = WorkflowDefinition(
            definition_id="wf-quality-inspection",
            name="Quality Inspection Workflow",
            workflow_type=WorkflowType.QUALITY,
            description="Comprehensive quality inspection workflow",
            steps=[
                WorkflowStep(
                    step_id="step-1",
                    name="Initialize Inspection",
                    step_type=StepType.TASK,
                    executor="inspection_initializer",
                ),
                WorkflowStep(
                    step_id="step-2",
                    name="Visual Inspection",
                    step_type=StepType.TASK,
                    executor="visual_inspector",
                    depends_on=["step-1"],
                ),
                WorkflowStep(
                    step_id="step-3",
                    name="Dimensional Check",
                    step_type=StepType.TASK,
                    executor="dimension_checker",
                    depends_on=["step-1"],
                ),
                WorkflowStep(
                    step_id="step-4",
                    name="Generate Report",
                    step_type=StepType.TASK,
                    executor="report_generator",
                    depends_on=["step-2", "step-3"],
                ),
            ],
            estimated_duration_minutes=45,
            tags=["quality", "inspection"],
        )
        self._definitions[quality_def.definition_id] = quality_def

        # Emergency workflow
        emergency_def = WorkflowDefinition(
            definition_id="wf-emergency-response",
            name="Emergency Response Workflow",
            workflow_type=WorkflowType.EMERGENCY,
            description="Emergency response and recovery workflow",
            steps=[
                WorkflowStep(
                    step_id="step-1",
                    name="Emergency Stop",
                    step_type=StepType.EQUIPMENT_CONTROL,
                    executor="emergency_controller",
                    timeout_seconds=30,
                ),
                WorkflowStep(
                    step_id="step-2",
                    name="Alert Notifications",
                    step_type=StepType.NOTIFICATION,
                    depends_on=["step-1"],
                ),
                WorkflowStep(
                    step_id="step-3",
                    name="Incident Assessment",
                    step_type=StepType.TASK,
                    executor="incident_assessor",
                    depends_on=["step-1"],
                ),
                WorkflowStep(
                    step_id="step-4",
                    name="Recovery Planning",
                    step_type=StepType.DECISION,
                    depends_on=["step-3"],
                ),
            ],
            required_approval=ApprovalLevel.MANAGER,
            estimated_duration_minutes=30,
            tags=["emergency", "safety"],
        )
        self._definitions[emergency_def.definition_id] = emergency_def

    # ============================================
    # Definition Management
    # ============================================

    def register_definition(self, definition: WorkflowDefinition) -> bool:
        """Register a workflow definition."""
        with self._lock:
            self._definitions[definition.definition_id] = definition
            logger.info(f"Registered workflow definition: {definition.name}")
            return True

    def get_definition(self, definition_id: str) -> Optional[WorkflowDefinition]:
        """Get a workflow definition by ID."""
        return self._definitions.get(definition_id)

    def list_definitions(
        self,
        workflow_type: Optional[WorkflowType] = None,
        tags: Optional[List[str]] = None,
    ) -> List[WorkflowDefinition]:
        """List workflow definitions with optional filtering."""
        definitions = list(self._definitions.values())

        if workflow_type:
            definitions = [d for d in definitions if d.workflow_type == workflow_type]

        if tags:
            definitions = [
                d for d in definitions
                if any(t in d.tags for t in tags)
            ]

        return definitions

    # ============================================
    # Instance Management
    # ============================================

    def create_workflow(
        self,
        definition_id: str,
        name: str,
        parameters: Dict[str, Any],
        created_by: str = "system",
        job_id: Optional[str] = None,
        priority: int = 5,
    ) -> Optional[WorkflowInstance]:
        """Create a new workflow instance."""
        definition = self._definitions.get(definition_id)
        if not definition:
            logger.error(f"Workflow definition not found: {definition_id}")
            return None

        with self._lock:
            instance_id = f"wfi-{uuid.uuid4().hex[:12]}"

            # Deep copy steps from definition
            steps = []
            for step in definition.steps:
                new_step = WorkflowStep(
                    step_id=step.step_id,
                    name=step.name,
                    step_type=step.step_type,
                    description=step.description,
                    executor=step.executor,
                    parameters=step.parameters.copy(),
                    timeout_seconds=step.timeout_seconds,
                    max_retries=step.max_retries,
                    required_approval=step.required_approval,
                    depends_on=step.depends_on.copy(),
                )
                steps.append(new_step)

            instance = WorkflowInstance(
                instance_id=instance_id,
                definition_id=definition_id,
                name=name,
                workflow_type=definition.workflow_type,
                state=WorkflowState.DRAFT,
                parameters=parameters,
                steps=steps,
                created_by=created_by,
                job_id=job_id,
                priority=priority,
                tags=definition.tags.copy(),
            )

            self._instances[instance_id] = instance
            self._events[instance_id] = []

            self._record_event(
                instance_id,
                "workflow_created",
                f"Workflow '{name}' created",
                created_by,
            )

            logger.info(f"Created workflow instance: {instance_id}")
            return instance

    def get_workflow(self, instance_id: str) -> Optional[WorkflowInstance]:
        """Get a workflow instance by ID."""
        return self._instances.get(instance_id)

    def list_workflows(
        self,
        state: Optional[WorkflowState] = None,
        workflow_type: Optional[WorkflowType] = None,
        job_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[WorkflowInstance]:
        """List workflow instances with optional filtering."""
        instances = list(self._instances.values())

        if state:
            instances = [i for i in instances if i.state == state]

        if workflow_type:
            instances = [i for i in instances if i.workflow_type == workflow_type]

        if job_id:
            instances = [i for i in instances if i.job_id == job_id]

        # Sort by priority (higher first) then by creation time
        instances.sort(key=lambda x: (-x.priority, x.created_at))

        return instances[:limit]

    # ============================================
    # Workflow Lifecycle
    # ============================================

    def submit_for_approval(
        self,
        instance_id: str,
        user: str,
    ) -> bool:
        """Submit workflow for approval."""
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        if instance.state != WorkflowState.DRAFT:
            logger.warning(f"Cannot submit workflow {instance_id}: invalid state {instance.state}")
            return False

        with self._lock:
            instance.state = WorkflowState.PENDING_APPROVAL
            self._record_event(
                instance_id,
                "submitted_for_approval",
                f"Workflow submitted for approval by {user}",
                user,
            )

        return True

    def approve_workflow(
        self,
        instance_id: str,
        user: str,
        note: str = "",
    ) -> bool:
        """Approve a workflow."""
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        if instance.state != WorkflowState.PENDING_APPROVAL:
            logger.warning(f"Cannot approve workflow {instance_id}: invalid state {instance.state}")
            return False

        with self._lock:
            instance.state = WorkflowState.APPROVED
            instance.approved_by = user
            instance.approved_at = datetime.now()

            self._record_event(
                instance_id,
                "workflow_approved",
                f"Workflow approved by {user}" + (f": {note}" if note else ""),
                user,
            )

        return True

    def reject_workflow(
        self,
        instance_id: str,
        user: str,
        reason: str,
    ) -> bool:
        """Reject a workflow."""
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        if instance.state != WorkflowState.PENDING_APPROVAL:
            return False

        with self._lock:
            instance.state = WorkflowState.REJECTED

            self._record_event(
                instance_id,
                "workflow_rejected",
                f"Workflow rejected by {user}: {reason}",
                user,
            )

        return True

    def start_workflow(
        self,
        instance_id: str,
        user: str = "system",
    ) -> bool:
        """Start executing a workflow."""
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        valid_states = [WorkflowState.APPROVED, WorkflowState.SCHEDULED, WorkflowState.DRAFT]
        if instance.state not in valid_states:
            logger.warning(f"Cannot start workflow {instance_id}: invalid state {instance.state}")
            return False

        with self._lock:
            instance.state = WorkflowState.RUNNING
            instance.started_at = datetime.now()

            self._record_event(
                instance_id,
                "workflow_started",
                f"Workflow execution started by {user}",
                user,
            )

            # Execute first ready steps
            self._execute_ready_steps(instance)

        return True

    def pause_workflow(
        self,
        instance_id: str,
        user: str,
        reason: str = "",
    ) -> bool:
        """Pause a running workflow."""
        instance = self._instances.get(instance_id)
        if not instance or instance.state != WorkflowState.RUNNING:
            return False

        with self._lock:
            instance.state = WorkflowState.PAUSED

            self._record_event(
                instance_id,
                "workflow_paused",
                f"Workflow paused by {user}" + (f": {reason}" if reason else ""),
                user,
            )

        return True

    def resume_workflow(
        self,
        instance_id: str,
        user: str,
    ) -> bool:
        """Resume a paused workflow."""
        instance = self._instances.get(instance_id)
        if not instance or instance.state != WorkflowState.PAUSED:
            return False

        with self._lock:
            instance.state = WorkflowState.RUNNING

            self._record_event(
                instance_id,
                "workflow_resumed",
                f"Workflow resumed by {user}",
                user,
            )

            self._execute_ready_steps(instance)

        return True

    def cancel_workflow(
        self,
        instance_id: str,
        user: str,
        reason: str,
    ) -> bool:
        """Cancel a workflow."""
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        terminal_states = [WorkflowState.COMPLETED, WorkflowState.CANCELLED]
        if instance.state in terminal_states:
            return False

        with self._lock:
            instance.state = WorkflowState.CANCELLED
            instance.completed_at = datetime.now()

            self._record_event(
                instance_id,
                "workflow_cancelled",
                f"Workflow cancelled by {user}: {reason}",
                user,
            )

        return True

    # ============================================
    # Step Execution
    # ============================================

    def _execute_ready_steps(self, instance: WorkflowInstance):
        """Execute all steps that are ready to run."""
        for step in instance.steps:
            if step.state != WorkflowState.DRAFT:
                continue

            # Check dependencies
            deps_complete = all(
                self._get_step_by_id(instance, dep_id).state == WorkflowState.COMPLETED
                for dep_id in step.depends_on
                if self._get_step_by_id(instance, dep_id)
            )

            if deps_complete:
                self._execute_step(instance, step)

    def _get_step_by_id(
        self,
        instance: WorkflowInstance,
        step_id: str,
    ) -> Optional[WorkflowStep]:
        """Get step by ID from instance."""
        for step in instance.steps:
            if step.step_id == step_id:
                return step
        return None

    def _execute_step(self, instance: WorkflowInstance, step: WorkflowStep):
        """Execute a single step."""
        step.state = WorkflowState.RUNNING
        step.started_at = datetime.now()

        self._record_event(
            instance.instance_id,
            "step_started",
            f"Step '{step.name}' started",
            "system",
            step.step_id,
        )

        try:
            executor = self._step_executors.get(step.step_type.value)
            if executor:
                result = executor(instance, step)
                step.result = result
                step.state = WorkflowState.COMPLETED
                step.completed_at = datetime.now()

                self._record_event(
                    instance.instance_id,
                    "step_completed",
                    f"Step '{step.name}' completed",
                    "system",
                    step.step_id,
                )
            else:
                step.state = WorkflowState.COMPLETED
                step.completed_at = datetime.now()

        except Exception as e:
            step.retry_count += 1
            if step.retry_count < step.max_retries:
                step.state = WorkflowState.DRAFT  # Retry
                logger.warning(f"Step {step.name} failed, retrying ({step.retry_count}/{step.max_retries})")
            else:
                step.state = WorkflowState.FAILED
                step.error = str(e)
                instance.state = WorkflowState.FAILED
                instance.completed_at = datetime.now()

                self._record_event(
                    instance.instance_id,
                    "step_failed",
                    f"Step '{step.name}' failed: {str(e)}",
                    "system",
                    step.step_id,
                )
                return

        # Check if workflow is complete
        self._check_workflow_completion(instance)

        # Execute next ready steps
        if instance.state == WorkflowState.RUNNING:
            self._execute_ready_steps(instance)

    def _check_workflow_completion(self, instance: WorkflowInstance):
        """Check if all steps are complete."""
        all_complete = all(
            step.state == WorkflowState.COMPLETED
            for step in instance.steps
        )

        if all_complete:
            instance.state = WorkflowState.COMPLETED
            instance.completed_at = datetime.now()

            self._record_event(
                instance.instance_id,
                "workflow_completed",
                "Workflow completed successfully",
                "system",
            )

    # ============================================
    # Step Executors
    # ============================================

    def _execute_task_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
    ) -> Dict[str, Any]:
        """Execute a task step."""
        return {
            "status": "completed",
            "executor": step.executor,
            "timestamp": datetime.now().isoformat(),
        }

    def _execute_decision_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
    ) -> Dict[str, Any]:
        """Execute a decision step."""
        return {
            "status": "completed",
            "decision": "proceed",
            "timestamp": datetime.now().isoformat(),
        }

    def _execute_approval_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
    ) -> Dict[str, Any]:
        """Execute an approval step - auto-approve for now."""
        return {
            "status": "approved",
            "approver": "auto",
            "timestamp": datetime.now().isoformat(),
        }

    def _execute_notification_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
    ) -> Dict[str, Any]:
        """Execute a notification step."""
        logger.info(f"Notification: Workflow {instance.name} - {step.name}")
        return {
            "status": "sent",
            "channels": ["log"],
            "timestamp": datetime.now().isoformat(),
        }

    def _execute_delay_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
    ) -> Dict[str, Any]:
        """Execute a delay step."""
        delay_seconds = step.parameters.get("delay_seconds", 0)
        return {
            "status": "completed",
            "delay_seconds": delay_seconds,
            "timestamp": datetime.now().isoformat(),
        }

    def _execute_equipment_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
    ) -> Dict[str, Any]:
        """Execute an equipment control step."""
        return {
            "status": "completed",
            "equipment": step.parameters.get("equipment_id", "unknown"),
            "action": step.parameters.get("action", "control"),
            "timestamp": datetime.now().isoformat(),
        }

    def _execute_api_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
    ) -> Dict[str, Any]:
        """Execute an API call step."""
        return {
            "status": "completed",
            "endpoint": step.parameters.get("endpoint", "unknown"),
            "timestamp": datetime.now().isoformat(),
        }

    # ============================================
    # Event Tracking
    # ============================================

    def _record_event(
        self,
        workflow_id: str,
        event_type: str,
        description: str,
        user: str,
        step_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        """Record a workflow event."""
        event = WorkflowEvent(
            event_id=f"evt-{uuid.uuid4().hex[:8]}",
            workflow_id=workflow_id,
            event_type=event_type,
            description=description,
            user=user,
            step_id=step_id,
            data=data or {},
        )

        if workflow_id not in self._events:
            self._events[workflow_id] = []

        self._events[workflow_id].append(event)

        # Notify handlers
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    def get_workflow_events(
        self,
        instance_id: str,
        limit: int = 100,
    ) -> List[WorkflowEvent]:
        """Get events for a workflow."""
        events = self._events.get(instance_id, [])
        return events[-limit:]

    def register_event_handler(self, handler: Callable[[WorkflowEvent], None]):
        """Register an event handler."""
        self._event_handlers.append(handler)

    # ============================================
    # Statistics
    # ============================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get workflow statistics."""
        instances = list(self._instances.values())

        state_counts = {}
        for state in WorkflowState:
            state_counts[state.value] = sum(1 for i in instances if i.state == state)

        type_counts = {}
        for wf_type in WorkflowType:
            type_counts[wf_type.value] = sum(1 for i in instances if i.workflow_type == wf_type)

        return {
            "total_definitions": len(self._definitions),
            "total_instances": len(instances),
            "by_state": state_counts,
            "by_type": type_counts,
            "active": state_counts.get("running", 0) + state_counts.get("pending_approval", 0),
            "completed": state_counts.get("completed", 0),
            "failed": state_counts.get("failed", 0),
        }


# ============================================
# Singleton Instance
# ============================================

_workflow_manager: Optional[WorkflowManager] = None
_manager_lock = threading.Lock()


def get_workflow_manager() -> WorkflowManager:
    """Get or create the workflow manager singleton."""
    global _workflow_manager

    if _workflow_manager is None:
        with _manager_lock:
            if _workflow_manager is None:
                _workflow_manager = WorkflowManager()

    return _workflow_manager


__all__ = [
    'WorkflowState',
    'WorkflowType',
    'StepType',
    'ApprovalLevel',
    'WorkflowStep',
    'WorkflowDefinition',
    'WorkflowInstance',
    'WorkflowEvent',
    'WorkflowManager',
    'get_workflow_manager',
]
