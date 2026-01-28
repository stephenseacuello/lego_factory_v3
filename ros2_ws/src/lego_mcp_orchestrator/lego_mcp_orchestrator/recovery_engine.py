#!/usr/bin/env python3
"""
LEGO MCP Recovery Engine Node
Determines and executes recovery actions based on failure type and context.

Recovery Policies:
- Robot faults: Clear error → Retry → Reassign → Manual
- Print failures: Retry → Different printer → Escalate
- Quality rejects: Rework → Scrap and requeue
- Communication lost: Reconnect → Restart → Manual

LEGO MCP Manufacturing System v7.0
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String, Bool

try:
    from lego_mcp_msgs.msg import FailureEvent
    from lego_mcp_msgs.srv import RescheduleRemaining
    from lego_mcp_msgs.action import MachineOperation
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class RecoveryAction(Enum):
    """Available recovery actions."""
    CLEAR_ERROR_RETRY = "clear_error_retry"
    REASSIGN_EQUIPMENT = "reassign_equipment"
    RETRY_SAME_EQUIPMENT = "retry_same_equipment"
    REWORK = "rework"
    SCRAP_AND_REQUEUE = "scrap_and_requeue"
    RECONNECT = "reconnect"
    RESTART_EQUIPMENT = "restart_equipment"
    QUEUE_FOR_MANUAL = "queue_for_manual"
    ESCALATE = "escalate"
    NO_ACTION = "no_action"


class RecoveryStatus(Enum):
    """Status of recovery attempt."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ESCALATED = "escalated"


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt."""
    attempt_id: str
    failure_id: str
    action: RecoveryAction
    status: RecoveryStatus
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    result: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0


@dataclass
class RecoveryPolicy:
    """Recovery policy for a failure type."""
    actions: List[tuple]  # (RecoveryAction, max_retries)
    priority: int = 2
    auto_execute: bool = True
    require_approval: bool = False


class RecoveryEngineNode(Node):
    """
    Determines recovery action based on failure type and context.

    Implements configurable recovery policies with retry logic
    and automatic escalation.
    """

    def __init__(self):
        super().__init__('recovery_engine')

        # Parameters
        self.declare_parameter('auto_recovery_enabled', True)
        self.declare_parameter('max_recovery_time', 300.0)  # 5 minutes
        self.declare_parameter('human_escalation_enabled', True)

        self._auto_recovery = self.get_parameter('auto_recovery_enabled').value
        self._max_recovery_time = self.get_parameter('max_recovery_time').value
        self._human_escalation = self.get_parameter('human_escalation_enabled').value

        # Recovery state
        self._active_recoveries: Dict[str, RecoveryAttempt] = {}
        self._recovery_history: List[RecoveryAttempt] = []
        self._recovery_count = 0

        # Recovery policies per failure type
        self._policies = self._init_policies()

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Subscribers
        if MSGS_AVAILABLE:
            self.create_subscription(
                FailureEvent,
                '/manufacturing/failures',
                self._on_failure_event,
                10,
                callback_group=self._cb_group
            )
        else:
            self.create_subscription(
                String,
                '/manufacturing/failures',
                self._on_failure_event_string,
                10,
                callback_group=self._cb_group
            )

        # Publishers
        self._recovery_status_pub = self.create_publisher(
            String,
            '/manufacturing/recovery_status',
            10
        )

        self._human_intervention_pub = self.create_publisher(
            String,
            '/manufacturing/human_intervention_required',
            10
        )

        # Service clients
        if MSGS_AVAILABLE:
            self._reschedule_client = self.create_client(
                RescheduleRemaining,
                '/scheduling/reschedule_remaining',
                callback_group=self._cb_group
            )

        # Equipment control publishers (for clear error, restart)
        self._equipment_cmd_pubs: Dict[str, Any] = {}
        for equipment in ['ned2', 'xarm', 'formlabs', 'cnc', 'laser']:
            self._equipment_cmd_pubs[equipment] = self.create_publisher(
                String,
                f'/{equipment}/command',
                10
            )

        self.get_logger().info("Recovery engine node initialized")

    def _init_policies(self) -> Dict[str, RecoveryPolicy]:
        """Initialize recovery policies for each failure type."""
        return {
            'robot_fault': RecoveryPolicy(
                actions=[
                    (RecoveryAction.CLEAR_ERROR_RETRY, 3),
                    (RecoveryAction.REASSIGN_EQUIPMENT, 1),
                    (RecoveryAction.QUEUE_FOR_MANUAL, 1),
                ],
                priority=1
            ),
            'robot_collision': RecoveryPolicy(
                actions=[
                    (RecoveryAction.QUEUE_FOR_MANUAL, 1),  # Safety - always manual
                ],
                priority=0,
                require_approval=True
            ),
            'print_failed': RecoveryPolicy(
                actions=[
                    (RecoveryAction.RETRY_SAME_EQUIPMENT, 2),
                    (RecoveryAction.REASSIGN_EQUIPMENT, 1),
                    (RecoveryAction.ESCALATE, 1),
                ],
                priority=2
            ),
            'quality_reject': RecoveryPolicy(
                actions=[
                    (RecoveryAction.REWORK, 1),
                    (RecoveryAction.SCRAP_AND_REQUEUE, 1),
                ],
                priority=2
            ),
            'equipment_offline': RecoveryPolicy(
                actions=[
                    (RecoveryAction.RECONNECT, 3),
                    (RecoveryAction.RESTART_EQUIPMENT, 1),
                    (RecoveryAction.REASSIGN_EQUIPMENT, 1),
                ],
                priority=2
            ),
            'equipment_error': RecoveryPolicy(
                actions=[
                    (RecoveryAction.CLEAR_ERROR_RETRY, 2),
                    (RecoveryAction.RESTART_EQUIPMENT, 1),
                    (RecoveryAction.QUEUE_FOR_MANUAL, 1),
                ],
                priority=1
            ),
            'communication_lost': RecoveryPolicy(
                actions=[
                    (RecoveryAction.RECONNECT, 5),
                    (RecoveryAction.RESTART_EQUIPMENT, 1),
                    (RecoveryAction.QUEUE_FOR_MANUAL, 1),
                ],
                priority=2
            ),
            'safety_violation': RecoveryPolicy(
                actions=[
                    (RecoveryAction.QUEUE_FOR_MANUAL, 1),  # Always manual for safety
                ],
                priority=0,
                require_approval=True
            ),
            'material_stockout': RecoveryPolicy(
                actions=[
                    (RecoveryAction.QUEUE_FOR_MANUAL, 1),
                ],
                priority=3
            ),
        }

    def _on_failure_event(self, msg):
        """Handle failure event from failure detector."""
        if not self._auto_recovery:
            return

        asyncio.create_task(self._process_failure(
            failure_id=msg.failure_id,
            failure_type=msg.failure_type,
            equipment_id=msg.equipment_id,
            operation_id=msg.operation_id,
            work_order_id=msg.work_order_id,
            severity=msg.severity,
            context=json.loads(msg.context_json) if msg.context_json else {}
        ))

    def _on_failure_event_string(self, msg: String):
        """Handle failure event as JSON string."""
        if not self._auto_recovery:
            return

        try:
            data = json.loads(msg.data)
            asyncio.create_task(self._process_failure(
                failure_id=data.get('failure_id', ''),
                failure_type=data.get('failure_type', ''),
                equipment_id=data.get('equipment_id', ''),
                operation_id=data.get('operation_id', ''),
                work_order_id=data.get('work_order_id', ''),
                severity=data.get('severity', 2),
                context=data.get('context', {})
            ))
        except json.JSONDecodeError:
            self.get_logger().error(f"Invalid failure event: {msg.data}")

    async def _process_failure(
        self,
        failure_id: str,
        failure_type: str,
        equipment_id: str,
        operation_id: str,
        work_order_id: str,
        severity: int,
        context: Dict[str, Any]
    ):
        """Process a failure and execute recovery policy."""
        self.get_logger().info(f"Processing failure {failure_id}: {failure_type} on {equipment_id}")

        # Get recovery policy
        policy = self._policies.get(failure_type)
        if not policy:
            self.get_logger().warn(f"No recovery policy for failure type: {failure_type}")
            await self._escalate_to_human(failure_id, failure_type, equipment_id, "No recovery policy")
            return

        # Check if approval required
        if policy.require_approval:
            await self._request_approval(failure_id, failure_type, equipment_id)
            return

        # Execute recovery actions
        for action, max_retries in policy.actions:
            for attempt in range(max_retries):
                self._recovery_count += 1
                attempt_id = f"REC-{datetime.now().strftime('%H%M%S')}-{self._recovery_count:04d}"

                recovery = RecoveryAttempt(
                    attempt_id=attempt_id,
                    failure_id=failure_id,
                    action=action,
                    status=RecoveryStatus.IN_PROGRESS,
                    retry_count=attempt
                )
                self._active_recoveries[attempt_id] = recovery

                self.get_logger().info(f"Attempting recovery: {action.value} (attempt {attempt + 1}/{max_retries})")

                # Execute the recovery action
                success = await self._execute_recovery_action(
                    action,
                    equipment_id,
                    operation_id,
                    work_order_id,
                    context
                )

                recovery.completed_at = datetime.now()
                if success:
                    recovery.status = RecoveryStatus.SUCCESS
                    recovery.result = {'message': 'Recovery successful'}
                    self._recovery_history.append(recovery)
                    del self._active_recoveries[attempt_id]

                    self._publish_recovery_status(recovery)
                    self.get_logger().info(f"Recovery successful: {action.value}")
                    return
                else:
                    recovery.status = RecoveryStatus.FAILED
                    recovery.result = {'message': 'Recovery failed'}

                await asyncio.sleep(1.0)  # Brief delay between retries

        # All recovery attempts failed - escalate
        await self._escalate_to_human(
            failure_id, failure_type, equipment_id,
            "All recovery actions exhausted"
        )

    async def _execute_recovery_action(
        self,
        action: RecoveryAction,
        equipment_id: str,
        operation_id: str,
        work_order_id: str,
        context: Dict[str, Any]
    ) -> bool:
        """Execute a single recovery action."""
        try:
            if action == RecoveryAction.CLEAR_ERROR_RETRY:
                return await self._clear_error_and_retry(equipment_id)

            elif action == RecoveryAction.REASSIGN_EQUIPMENT:
                return await self._reassign_to_other_equipment(
                    equipment_id, operation_id, work_order_id
                )

            elif action == RecoveryAction.RETRY_SAME_EQUIPMENT:
                return await self._retry_on_same_equipment(equipment_id, operation_id)

            elif action == RecoveryAction.REWORK:
                return await self._schedule_rework(operation_id, work_order_id)

            elif action == RecoveryAction.SCRAP_AND_REQUEUE:
                return await self._scrap_and_requeue(operation_id, work_order_id)

            elif action == RecoveryAction.RECONNECT:
                return await self._reconnect_equipment(equipment_id)

            elif action == RecoveryAction.RESTART_EQUIPMENT:
                return await self._restart_equipment(equipment_id)

            elif action == RecoveryAction.QUEUE_FOR_MANUAL:
                # This always "succeeds" as it's the final fallback
                await self._escalate_to_human(
                    context.get('failure_id', ''),
                    context.get('failure_type', ''),
                    equipment_id,
                    "Queued for manual intervention"
                )
                return True

            elif action == RecoveryAction.ESCALATE:
                await self._escalate_to_human(
                    context.get('failure_id', ''),
                    context.get('failure_type', ''),
                    equipment_id,
                    "Escalated after failed recovery"
                )
                return True

            else:
                self.get_logger().warn(f"Unknown recovery action: {action}")
                return False

        except Exception as e:
            self.get_logger().error(f"Recovery action {action.value} failed: {e}")
            return False

    async def _clear_error_and_retry(self, equipment_id: str) -> bool:
        """Clear equipment error and retry operation."""
        # Send clear error command
        cmd = String()
        cmd.data = json.dumps({'command': 'clear_error'})

        if equipment_id in self._equipment_cmd_pubs:
            self._equipment_cmd_pubs[equipment_id].publish(cmd)
            await asyncio.sleep(2.0)  # Wait for error to clear

            # Check if error cleared (would need status feedback)
            return True  # Simplified - assume success

        return False

    async def _reassign_to_other_equipment(
        self,
        failed_equipment_id: str,
        operation_id: str,
        work_order_id: str
    ) -> bool:
        """Reassign operation to different equipment."""
        if not MSGS_AVAILABLE or not self._reschedule_client:
            return False

        # Request rescheduling excluding failed equipment
        request = RescheduleRemaining.Request()
        request.work_order_id = work_order_id
        request.failed_equipment_id = failed_equipment_id
        request.urgent = True

        try:
            if self._reschedule_client.wait_for_service(timeout_sec=5.0):
                response = await self._reschedule_client.call_async(request)
                return response.success
        except Exception as e:
            self.get_logger().error(f"Reschedule service call failed: {e}")

        return False

    async def _retry_on_same_equipment(self, equipment_id: str, operation_id: str) -> bool:
        """Retry the operation on the same equipment."""
        # Send retry command
        cmd = String()
        cmd.data = json.dumps({
            'command': 'retry',
            'operation_id': operation_id
        })

        if equipment_id in self._equipment_cmd_pubs:
            self._equipment_cmd_pubs[equipment_id].publish(cmd)
            await asyncio.sleep(1.0)
            return True

        return False

    async def _schedule_rework(self, operation_id: str, work_order_id: str) -> bool:
        """Schedule rework for the failed part."""
        self.get_logger().info(f"Scheduling rework for operation {operation_id}")

        # In production, would call scheduling service
        # For now, publish rework request
        rework_msg = String()
        rework_msg.data = json.dumps({
            'type': 'rework_request',
            'operation_id': operation_id,
            'work_order_id': work_order_id,
            'timestamp': datetime.now().isoformat()
        })
        self._recovery_status_pub.publish(rework_msg)

        return True

    async def _scrap_and_requeue(self, operation_id: str, work_order_id: str) -> bool:
        """Scrap the part and queue a new one."""
        self.get_logger().info(f"Scrapping and requeuing operation {operation_id}")

        scrap_msg = String()
        scrap_msg.data = json.dumps({
            'type': 'scrap_and_requeue',
            'operation_id': operation_id,
            'work_order_id': work_order_id,
            'timestamp': datetime.now().isoformat()
        })
        self._recovery_status_pub.publish(scrap_msg)

        return True

    async def _reconnect_equipment(self, equipment_id: str) -> bool:
        """Attempt to reconnect to equipment."""
        cmd = String()
        cmd.data = json.dumps({'command': 'reconnect'})

        if equipment_id in self._equipment_cmd_pubs:
            self._equipment_cmd_pubs[equipment_id].publish(cmd)
            await asyncio.sleep(5.0)  # Wait for reconnection
            return True

        return False

    async def _restart_equipment(self, equipment_id: str) -> bool:
        """Restart equipment."""
        cmd = String()
        cmd.data = json.dumps({'command': 'restart'})

        if equipment_id in self._equipment_cmd_pubs:
            self._equipment_cmd_pubs[equipment_id].publish(cmd)
            await asyncio.sleep(10.0)  # Wait for restart
            return True

        return False

    async def _request_approval(
        self,
        failure_id: str,
        failure_type: str,
        equipment_id: str
    ):
        """Request human approval before recovery."""
        msg = String()
        msg.data = json.dumps({
            'type': 'approval_required',
            'failure_id': failure_id,
            'failure_type': failure_type,
            'equipment_id': equipment_id,
            'message': f"Recovery requires approval for {failure_type} on {equipment_id}",
            'timestamp': datetime.now().isoformat()
        })
        self._human_intervention_pub.publish(msg)
        self.get_logger().warn(f"Human approval required for {failure_id}")

    async def _escalate_to_human(
        self,
        failure_id: str,
        failure_type: str,
        equipment_id: str,
        reason: str
    ):
        """Escalate to human intervention."""
        if not self._human_escalation:
            return

        msg = String()
        msg.data = json.dumps({
            'type': 'human_intervention_required',
            'failure_id': failure_id,
            'failure_type': failure_type,
            'equipment_id': equipment_id,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        })
        self._human_intervention_pub.publish(msg)
        self.get_logger().error(f"HUMAN INTERVENTION REQUIRED: {reason}")

    def _publish_recovery_status(self, recovery: RecoveryAttempt):
        """Publish recovery status update."""
        msg = String()
        msg.data = json.dumps({
            'attempt_id': recovery.attempt_id,
            'failure_id': recovery.failure_id,
            'action': recovery.action.value,
            'status': recovery.status.value,
            'retry_count': recovery.retry_count,
            'started_at': recovery.started_at.isoformat(),
            'completed_at': recovery.completed_at.isoformat() if recovery.completed_at else None,
            'result': recovery.result
        })
        self._recovery_status_pub.publish(msg)

    def get_recovery_statistics(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        by_action = {}
        by_status = {}

        for recovery in self._recovery_history:
            by_action[recovery.action.value] = by_action.get(recovery.action.value, 0) + 1
            by_status[recovery.status.value] = by_status.get(recovery.status.value, 0) + 1

        success_count = by_status.get('success', 0)
        total = len(self._recovery_history)

        return {
            'total_recoveries': total,
            'active_recoveries': len(self._active_recoveries),
            'success_rate': success_count / total if total > 0 else 0,
            'by_action': by_action,
            'by_status': by_status,
        }


def main(args=None):
    rclpy.init(args=args)

    node = RecoveryEngineNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
