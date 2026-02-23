"""
Action Console Service
======================

Algorithm-to-Action execution pipeline with:
- Action queue management
- Approval workflows
- Execution tracking
- Audit logging

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import threading
import uuid

logger = logging.getLogger(__name__)


class ActionCategory(Enum):
    """Action categories with different approval requirements"""
    INFORMATIONAL = "informational"      # No action needed, just logging
    PREVENTIVE = "preventive"            # Preventive maintenance
    CORRECTIVE = "corrective"            # Fix an issue
    OPTIMIZATION = "optimization"        # Improve performance
    QUALITY = "quality"                  # Quality adjustment
    SCHEDULING = "scheduling"            # Schedule change
    INVENTORY = "inventory"              # Inventory adjustment
    EQUIPMENT = "equipment"              # Equipment control
    SAFETY = "safety"                    # Safety-related
    EMERGENCY = "emergency"              # Emergency action


class ActionStatus(Enum):
    """Action lifecycle status"""
    PENDING = "pending"                  # Awaiting approval
    APPROVED = "approved"                # Approved, ready to execute
    REJECTED = "rejected"                # Rejected by approver
    EXECUTING = "executing"              # Currently executing
    COMPLETED = "completed"              # Successfully completed
    FAILED = "failed"                    # Execution failed
    CANCELLED = "cancelled"              # Cancelled before execution
    EXPIRED = "expired"                  # Approval window expired


class ActionPriority(Enum):
    """Action priority levels"""
    CRITICAL = "critical"    # Immediate execution
    HIGH = "high"            # Execute soon
    NORMAL = "normal"        # Standard queue
    LOW = "low"              # Execute when convenient


class ApprovalType(Enum):
    """Types of approval required"""
    AUTO = "auto"                        # Automatic approval
    HUMAN = "human"                      # Requires human approval
    MULTI = "multi"                      # Multiple approvers required
    ESCALATED = "escalated"              # Escalated for approval


@dataclass
class ActionResult:
    """Result of action execution"""
    success: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class Action:
    """Action record"""
    id: str
    title: str
    description: str
    category: ActionCategory
    priority: ActionPriority
    status: ActionStatus
    approval_type: ApprovalType
    source: str                          # What generated this action (AI, rule, etc)
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    executor: str = ""                   # What executes this action
    target_entity_type: str = ""         # Target entity type
    target_entity_id: str = ""           # Target entity ID
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Optional[ActionResult] = None
    related_alert_id: Optional[str] = None
    estimated_impact: Dict[str, Any] = field(default_factory=dict)
    risk_assessment: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    approvers_required: List[str] = field(default_factory=list)
    approvers_completed: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "approval_type": self.approval_type.value,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "approved_by": self.approved_by,
            "rejected_by": self.rejected_by,
            "rejection_reason": self.rejection_reason,
            "executor": self.executor,
            "target_entity_type": self.target_entity_type,
            "target_entity_id": self.target_entity_id,
            "parameters": self.parameters,
            "result": {
                "success": self.result.success,
                "message": self.result.message,
                "details": self.result.details,
                "error": self.result.error,
                "execution_time_ms": self.result.execution_time_ms
            } if self.result else None,
            "related_alert_id": self.related_alert_id,
            "estimated_impact": self.estimated_impact,
            "risk_assessment": self.risk_assessment,
            "tags": self.tags,
            "approvers_required": self.approvers_required,
            "approvers_completed": self.approvers_completed
        }


@dataclass
class ActionQueueStats:
    """Action queue statistics"""
    pending_count: int
    executing_count: int
    completed_today: int
    failed_today: int
    avg_approval_time: float  # seconds
    avg_execution_time: float  # seconds
    by_category: Dict[str, int]
    by_priority: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pending_count": self.pending_count,
            "executing_count": self.executing_count,
            "completed_today": self.completed_today,
            "failed_today": self.failed_today,
            "avg_approval_time": self.avg_approval_time,
            "avg_execution_time": self.avg_execution_time,
            "by_category": self.by_category,
            "by_priority": self.by_priority
        }


class ActionConsole:
    """
    Action queue management and execution system.

    Handles the algorithm-to-action pipeline from creation
    through approval and execution.
    """

    # Auto-approval rules by category and conditions
    AUTO_APPROVAL_RULES = {
        ActionCategory.INFORMATIONAL: {"always": True},
        ActionCategory.PREVENTIVE: {"cost_limit": 1000.0},
        ActionCategory.QUALITY: {"minor_only": True},
        ActionCategory.SCHEDULING: {"impact_hours": 1.0},
        ActionCategory.EMERGENCY: {"safety": True},  # Emergency safety auto-approves
    }

    # Default expiration times by priority (seconds)
    EXPIRATION_TIMES = {
        ActionPriority.CRITICAL: 300,      # 5 minutes
        ActionPriority.HIGH: 3600,         # 1 hour
        ActionPriority.NORMAL: 86400,      # 24 hours
        ActionPriority.LOW: 604800,        # 7 days
    }

    def __init__(self, process_interval: float = 5.0):
        """
        Initialize action console.

        Args:
            process_interval: Seconds between queue processing
        """
        self._actions: Dict[str, Action] = {}
        self._completed_actions: List[Action] = []
        self._executors: Dict[str, Callable[[Action], ActionResult]] = {}
        self._process_interval = process_interval
        self._running = False
        self._lock = threading.RLock()
        self._callbacks: Dict[str, List[Callable[[Action], None]]] = {
            "created": [],
            "approved": [],
            "rejected": [],
            "executed": [],
            "completed": [],
            "failed": []
        }
        self._max_history = 1000

        # Register default executors
        self._register_default_executors()

    def _register_default_executors(self):
        """Register default action executors"""
        self.register_executor("schedule_adjustment", self._execute_schedule_adjustment)
        self.register_executor("quality_parameter", self._execute_quality_parameter)
        self.register_executor("maintenance_request", self._execute_maintenance_request)
        self.register_executor("inventory_reorder", self._execute_inventory_reorder)
        self.register_executor("equipment_command", self._execute_equipment_command)

    def register_executor(
        self,
        executor_name: str,
        executor: Callable[[Action], ActionResult]
    ):
        """
        Register an action executor.

        Args:
            executor_name: Name of the executor
            executor: Function that executes the action
        """
        with self._lock:
            self._executors[executor_name] = executor

    def create_action(
        self,
        title: str,
        description: str,
        category: ActionCategory,
        executor: str,
        parameters: Dict[str, Any] = None,
        priority: ActionPriority = ActionPriority.NORMAL,
        source: str = "manual",
        target_entity_type: str = "",
        target_entity_id: str = "",
        related_alert_id: str = None,
        estimated_impact: Dict[str, Any] = None,
        risk_assessment: Dict[str, Any] = None,
        tags: List[str] = None,
        expires_in_seconds: int = None
    ) -> Action:
        """
        Create a new action.

        Args:
            title: Action title
            description: Detailed description
            category: Action category
            executor: Name of executor to use
            parameters: Parameters for execution
            priority: Action priority
            source: What generated this action
            target_entity_type: Target entity type
            target_entity_id: Target entity ID
            related_alert_id: Related alert if any
            estimated_impact: Expected impact
            risk_assessment: Risk evaluation
            tags: Action tags
            expires_in_seconds: Custom expiration time

        Returns:
            Created Action object
        """
        now = datetime.now()

        # Determine approval type
        approval_type = self._determine_approval_type(
            category, parameters or {}, risk_assessment or {}
        )

        # Calculate expiration
        if expires_in_seconds:
            expires_at = now + timedelta(seconds=expires_in_seconds)
        else:
            expires_at = now + timedelta(
                seconds=self.EXPIRATION_TIMES.get(priority, 86400)
            )

        action = Action(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            category=category,
            priority=priority,
            status=ActionStatus.PENDING,
            approval_type=approval_type,
            source=source,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            executor=executor,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            parameters=parameters or {},
            related_alert_id=related_alert_id,
            estimated_impact=estimated_impact or {},
            risk_assessment=risk_assessment or {},
            tags=tags or []
        )

        with self._lock:
            self._actions[action.id] = action

        # Auto-approve if eligible
        if approval_type == ApprovalType.AUTO:
            self._auto_approve(action)

        self._notify("created", action)
        logger.info(f"Action created: {action.id} - {title} [{category.value}]")

        return action

    def _determine_approval_type(
        self,
        category: ActionCategory,
        parameters: Dict[str, Any],
        risk_assessment: Dict[str, Any]
    ) -> ApprovalType:
        """Determine what type of approval is needed"""
        rules = self.AUTO_APPROVAL_RULES.get(category)

        if not rules:
            return ApprovalType.HUMAN

        # Check always auto-approve
        if rules.get("always"):
            return ApprovalType.AUTO

        # Check cost limit
        cost_limit = rules.get("cost_limit")
        if cost_limit:
            estimated_cost = parameters.get("estimated_cost", 0)
            if estimated_cost <= cost_limit:
                return ApprovalType.AUTO

        # Check minor only
        if rules.get("minor_only"):
            if parameters.get("severity") == "minor":
                return ApprovalType.AUTO

        # Check impact hours
        impact_limit = rules.get("impact_hours")
        if impact_limit:
            impact_hours = parameters.get("impact_hours", 0)
            if impact_hours <= impact_limit:
                return ApprovalType.AUTO

        # Check safety emergency
        if rules.get("safety") and category == ActionCategory.EMERGENCY:
            return ApprovalType.AUTO

        # Check risk level
        risk_level = risk_assessment.get("level", "medium")
        if risk_level == "high":
            return ApprovalType.MULTI

        return ApprovalType.HUMAN

    def _auto_approve(self, action: Action):
        """Auto-approve an action"""
        with self._lock:
            action.status = ActionStatus.APPROVED
            action.approved_at = datetime.now()
            action.approved_by = "SYSTEM_AUTO"
            action.updated_at = datetime.now()

        self._notify("approved", action)
        logger.info(f"Action auto-approved: {action.id}")

    def approve_action(
        self,
        action_id: str,
        approver: str,
        note: str = ""
    ) -> Optional[Action]:
        """
        Approve an action for execution.

        Args:
            action_id: Action ID
            approver: User approving
            note: Optional note

        Returns:
            Updated Action or None
        """
        with self._lock:
            action = self._actions.get(action_id)
            if not action:
                return None

            if action.status != ActionStatus.PENDING:
                logger.warning(f"Cannot approve action {action_id} in status {action.status}")
                return None

            # For multi-approval, track approvers
            if action.approval_type == ApprovalType.MULTI:
                if approver not in action.approvers_completed:
                    action.approvers_completed.append(approver)

                # Check if all required approvers have approved
                if len(action.approvers_completed) < len(action.approvers_required):
                    action.updated_at = datetime.now()
                    return action

            action.status = ActionStatus.APPROVED
            action.approved_at = datetime.now()
            action.approved_by = approver
            action.updated_at = datetime.now()

            if note:
                action.parameters["approval_note"] = note

        self._notify("approved", action)
        logger.info(f"Action approved: {action_id} by {approver}")
        return action

    def reject_action(
        self,
        action_id: str,
        rejector: str,
        reason: str = ""
    ) -> Optional[Action]:
        """
        Reject an action.

        Args:
            action_id: Action ID
            rejector: User rejecting
            reason: Rejection reason

        Returns:
            Updated Action or None
        """
        with self._lock:
            action = self._actions.get(action_id)
            if not action:
                return None

            action.status = ActionStatus.REJECTED
            action.rejected_by = rejector
            action.rejection_reason = reason
            action.updated_at = datetime.now()

            # Move to completed
            self._completed_actions.append(action)
            del self._actions[action_id]

        self._notify("rejected", action)
        logger.info(f"Action rejected: {action_id} by {rejector}")
        return action

    async def execute_action(self, action_id: str) -> Optional[ActionResult]:
        """
        Execute an approved action.

        Args:
            action_id: Action ID

        Returns:
            ActionResult or None
        """
        with self._lock:
            action = self._actions.get(action_id)
            if not action:
                return None

            if action.status != ActionStatus.APPROVED:
                logger.warning(f"Cannot execute action {action_id} in status {action.status}")
                return None

            executor = self._executors.get(action.executor)
            if not executor:
                logger.error(f"No executor found for: {action.executor}")
                return ActionResult(
                    success=False,
                    message="Executor not found",
                    error=f"Unknown executor: {action.executor}"
                )

            action.status = ActionStatus.EXECUTING
            action.executed_at = datetime.now()
            action.updated_at = datetime.now()

        self._notify("executed", action)

        # Execute the action
        try:
            import time
            start_time = time.time()

            if asyncio.iscoroutinefunction(executor):
                result = await executor(action)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, executor, action)

            result.execution_time_ms = (time.time() - start_time) * 1000

        except Exception as e:
            logger.error(f"Action execution failed: {action_id} - {e}")
            result = ActionResult(
                success=False,
                message="Execution failed",
                error=str(e)
            )

        # Update action with result
        with self._lock:
            action.result = result
            action.completed_at = datetime.now()
            action.updated_at = datetime.now()

            if result.success:
                action.status = ActionStatus.COMPLETED
                self._notify("completed", action)
            else:
                action.status = ActionStatus.FAILED
                self._notify("failed", action)

            # Move to completed
            self._completed_actions.append(action)
            del self._actions[action_id]

            # Trim history
            if len(self._completed_actions) > self._max_history:
                self._completed_actions = self._completed_actions[-self._max_history:]

        return result

    def get_action(self, action_id: str) -> Optional[Action]:
        """Get action by ID"""
        with self._lock:
            return self._actions.get(action_id)

    def get_pending_actions(
        self,
        category: ActionCategory = None,
        priority: ActionPriority = None,
        limit: int = 100
    ) -> List[Action]:
        """Get pending actions requiring approval"""
        with self._lock:
            pending = [
                a for a in self._actions.values()
                if a.status == ActionStatus.PENDING
            ]

            if category:
                pending = [a for a in pending if a.category == category]
            if priority:
                pending = [a for a in pending if a.priority == priority]

            # Sort by priority and creation time
            priority_order = {
                ActionPriority.CRITICAL: 0,
                ActionPriority.HIGH: 1,
                ActionPriority.NORMAL: 2,
                ActionPriority.LOW: 3
            }
            pending.sort(key=lambda a: (priority_order[a.priority], a.created_at))

            return pending[:limit]

    def get_approved_actions(self) -> List[Action]:
        """Get actions approved and ready for execution"""
        with self._lock:
            return [
                a for a in self._actions.values()
                if a.status == ActionStatus.APPROVED
            ]

    def get_queue_stats(self) -> ActionQueueStats:
        """Get action queue statistics"""
        with self._lock:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            pending = [a for a in self._actions.values() if a.status == ActionStatus.PENDING]
            executing = [a for a in self._actions.values() if a.status == ActionStatus.EXECUTING]
            completed_today = [
                a for a in self._completed_actions
                if a.completed_at and a.completed_at >= today and a.status == ActionStatus.COMPLETED
            ]
            failed_today = [
                a for a in self._completed_actions
                if a.completed_at and a.completed_at >= today and a.status == ActionStatus.FAILED
            ]

            # Average times
            approval_times = [
                (a.approved_at - a.created_at).total_seconds()
                for a in self._completed_actions
                if a.approved_at
            ]
            execution_times = [
                a.result.execution_time_ms / 1000
                for a in self._completed_actions
                if a.result
            ]

            by_category = {}
            for cat in ActionCategory:
                count = sum(1 for a in pending if a.category == cat)
                if count > 0:
                    by_category[cat.value] = count

            by_priority = {}
            for pri in ActionPriority:
                count = sum(1 for a in pending if a.priority == pri)
                if count > 0:
                    by_priority[pri.value] = count

            return ActionQueueStats(
                pending_count=len(pending),
                executing_count=len(executing),
                completed_today=len(completed_today),
                failed_today=len(failed_today),
                avg_approval_time=sum(approval_times) / len(approval_times) if approval_times else 0,
                avg_execution_time=sum(execution_times) / len(execution_times) if execution_times else 0,
                by_category=by_category,
                by_priority=by_priority
            )

    def add_callback(self, event: str, callback: Callable[[Action], None]):
        """Add callback for action events"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _notify(self, event: str, action: Action):
        """Notify callbacks for an event"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(action)
            except Exception as e:
                logger.error(f"Action callback error: {e}")

    async def _process_queue(self):
        """Process approved actions in the queue"""
        approved = self.get_approved_actions()

        # Sort by priority
        priority_order = {
            ActionPriority.CRITICAL: 0,
            ActionPriority.HIGH: 1,
            ActionPriority.NORMAL: 2,
            ActionPriority.LOW: 3
        }
        approved.sort(key=lambda a: priority_order[a.priority])

        for action in approved:
            try:
                await self.execute_action(action.id)
            except Exception as e:
                logger.error(f"Queue processing error for {action.id}: {e}")

    async def _check_expirations(self):
        """Check for expired actions"""
        now = datetime.now()

        with self._lock:
            expired_ids = [
                aid for aid, action in self._actions.items()
                if action.expires_at and action.expires_at <= now
                and action.status == ActionStatus.PENDING
            ]

            for action_id in expired_ids:
                action = self._actions[action_id]
                action.status = ActionStatus.EXPIRED
                action.updated_at = now
                self._completed_actions.append(action)
                del self._actions[action_id]
                logger.warning(f"Action expired: {action_id}")

    async def start_processing(self):
        """Start background action processing"""
        self._running = True
        while self._running:
            try:
                await self._process_queue()
                await self._check_expirations()
            except Exception as e:
                logger.error(f"Action processing error: {e}")
            await asyncio.sleep(self._process_interval)

    def stop_processing(self):
        """Stop background processing"""
        self._running = False

    # Default executor implementations

    def _execute_schedule_adjustment(self, action: Action) -> ActionResult:
        """Execute schedule adjustment"""
        try:
            # Would integrate with scheduling service
            logger.info(f"Executing schedule adjustment: {action.parameters}")
            return ActionResult(
                success=True,
                message="Schedule adjusted successfully",
                details={"changes": action.parameters}
            )
        except Exception as e:
            return ActionResult(success=False, message="Failed", error=str(e))

    def _execute_quality_parameter(self, action: Action) -> ActionResult:
        """Execute quality parameter change"""
        try:
            logger.info(f"Executing quality parameter change: {action.parameters}")
            return ActionResult(
                success=True,
                message="Quality parameters updated",
                details={"updated": action.parameters}
            )
        except Exception as e:
            return ActionResult(success=False, message="Failed", error=str(e))

    def _execute_maintenance_request(self, action: Action) -> ActionResult:
        """Execute maintenance request"""
        try:
            logger.info(f"Creating maintenance request: {action.parameters}")
            return ActionResult(
                success=True,
                message="Maintenance request created",
                details={"work_order_id": f"WO-{action.id[:8]}"}
            )
        except Exception as e:
            return ActionResult(success=False, message="Failed", error=str(e))

    def _execute_inventory_reorder(self, action: Action) -> ActionResult:
        """Execute inventory reorder"""
        try:
            logger.info(f"Creating purchase order: {action.parameters}")
            return ActionResult(
                success=True,
                message="Purchase order created",
                details={"po_id": f"PO-{action.id[:8]}"}
            )
        except Exception as e:
            return ActionResult(success=False, message="Failed", error=str(e))

    def _execute_equipment_command(self, action: Action) -> ActionResult:
        """Execute equipment command"""
        try:
            # This would send command to ROS2
            logger.info(f"Sending equipment command: {action.parameters}")
            return ActionResult(
                success=True,
                message="Equipment command sent",
                details={"command": action.parameters.get("command")}
            )
        except Exception as e:
            return ActionResult(success=False, message="Failed", error=str(e))


# Singleton instance
_action_console: Optional[ActionConsole] = None


def get_action_console() -> ActionConsole:
    """Get or create the singleton action console instance"""
    global _action_console
    if _action_console is None:
        _action_console = ActionConsole()
    return _action_console
