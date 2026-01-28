#!/usr/bin/env python3
"""
LEGO MCP Failure Detector Node
Detects and classifies equipment failures from ROS2 topics.

Monitors:
- Robot faults (joint errors, collisions, e-stop)
- Print failures
- Quality rejections
- Equipment going offline
- Material stockouts

LEGO MCP Manufacturing System v7.0
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
import json

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String, Bool
from sensor_msgs.msg import JointState

try:
    from lego_mcp_msgs.msg import (
        EquipmentStatus, PrintJob, QualityEvent, FailureEvent
    )
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class FailureType(Enum):
    """Types of failures detected."""
    ROBOT_FAULT = "robot_fault"
    ROBOT_COLLISION = "robot_collision"
    PRINT_FAILED = "print_failed"
    QUALITY_REJECT = "quality_reject"
    EQUIPMENT_OFFLINE = "equipment_offline"
    EQUIPMENT_ERROR = "equipment_error"
    MATERIAL_STOCKOUT = "material_stockout"
    COMMUNICATION_LOST = "communication_lost"
    SAFETY_VIOLATION = "safety_violation"


class FailureSeverity(Enum):
    """Severity of failures."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class DetectedFailure:
    """Details of a detected failure."""
    failure_id: str
    failure_type: FailureType
    severity: FailureSeverity
    equipment_id: str
    operation_id: str = ''
    work_order_id: str = ''
    description: str = ''
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution: str = ''


class FailureDetectorNode(Node):
    """
    Detects and classifies equipment failures from ROS2 topics.
    """

    def __init__(self):
        super().__init__('failure_detector')

        # Parameters
        self.declare_parameter('heartbeat_timeout', 5.0)  # seconds
        self.declare_parameter('joint_torque_threshold', 50.0)  # Nm
        self.declare_parameter('position_error_threshold', 0.1)  # radians

        self._heartbeat_timeout = self.get_parameter('heartbeat_timeout').value
        self._torque_threshold = self.get_parameter('joint_torque_threshold').value
        self._position_error_threshold = self.get_parameter('position_error_threshold').value

        # State tracking
        self._equipment_last_seen: Dict[str, datetime] = {}
        self._equipment_status: Dict[str, str] = {}
        self._active_failures: Dict[str, DetectedFailure] = {}
        self._failure_history: List[DetectedFailure] = []
        self._failure_count = 0
        self._lock = threading.Lock()

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Publishers
        if MSGS_AVAILABLE:
            self._failure_pub = self.create_publisher(
                FailureEvent,
                '/manufacturing/failures',
                10
            )
        else:
            self._failure_pub = self.create_publisher(
                String,
                '/manufacturing/failures',
                10
            )

        # Equipment monitoring subscriptions
        equipment_list = ['ned2', 'xarm', 'formlabs', 'cnc', 'laser']
        for equipment in equipment_list:
            # Status subscription
            self.create_subscription(
                EquipmentStatus if MSGS_AVAILABLE else String,
                f'/{equipment}/status',
                lambda msg, eq=equipment: self._on_equipment_status(eq, msg),
                10
            )

            # Robot joint states for collision detection
            if equipment in ['ned2', 'xarm']:
                self.create_subscription(
                    JointState,
                    f'/{equipment}/joint_states',
                    lambda msg, eq=equipment: self._on_joint_states(eq, msg),
                    10
                )

        # Print job status
        if MSGS_AVAILABLE:
            self.create_subscription(
                PrintJob,
                '/formlabs/job_status',
                self._on_print_status,
                10
            )

        # Quality events
        if MSGS_AVAILABLE:
            self.create_subscription(
                QualityEvent,
                '/quality/events',
                self._on_quality_event,
                10
            )

        # E-stop status
        self.create_subscription(
            Bool,
            '/safety/estop_status',
            self._on_estop,
            10
        )

        # Heartbeat checker timer
        self._heartbeat_timer = self.create_timer(
            1.0,
            self._check_heartbeats,
            callback_group=self._cb_group
        )

        self.get_logger().info("Failure detector node initialized")

    def _on_equipment_status(self, equipment_id: str, msg):
        """Monitor equipment status for failures."""
        with self._lock:
            self._equipment_last_seen[equipment_id] = datetime.now()

            if MSGS_AVAILABLE and hasattr(msg, 'state'):
                old_status = self._equipment_status.get(equipment_id)
                new_status = self._state_to_string(msg.state)
                self._equipment_status[equipment_id] = new_status

                # Check for error state
                if msg.state == 3:  # Error state
                    self._detect_failure(
                        FailureType.EQUIPMENT_ERROR,
                        FailureSeverity.HIGH,
                        equipment_id,
                        f"Equipment {equipment_id} entered error state",
                        {'error_code': msg.error_code if hasattr(msg, 'error_code') else 0}
                    )

                # Check for disconnect
                if old_status and old_status != 'disconnected' and not msg.connected:
                    self._detect_failure(
                        FailureType.EQUIPMENT_OFFLINE,
                        FailureSeverity.MEDIUM,
                        equipment_id,
                        f"Equipment {equipment_id} disconnected",
                        {}
                    )

                # Resolve if back online
                if msg.connected and msg.state == 1:  # Idle
                    self._resolve_failures(equipment_id, [
                        FailureType.EQUIPMENT_OFFLINE,
                        FailureType.EQUIPMENT_ERROR
                    ])

    def _on_joint_states(self, robot_id: str, msg: JointState):
        """Monitor robot joints for collision/fault detection."""
        # Check for excessive torque (potential collision)
        if msg.effort:
            max_torque = max(abs(t) for t in msg.effort)
            if max_torque > self._torque_threshold:
                self._detect_failure(
                    FailureType.ROBOT_COLLISION,
                    FailureSeverity.CRITICAL,
                    robot_id,
                    f"High torque detected on {robot_id}: {max_torque:.2f} Nm",
                    {
                        'max_torque': max_torque,
                        'joint_efforts': list(msg.effort),
                        'joint_names': list(msg.name),
                    }
                )

    def _on_print_status(self, msg):
        """Monitor print job status for failures."""
        if hasattr(msg, 'status'):
            status = msg.status if isinstance(msg.status, str) else self._print_status_to_string(msg.status)

            if status == 'FAILED':
                self._detect_failure(
                    FailureType.PRINT_FAILED,
                    FailureSeverity.HIGH,
                    msg.printer_id if hasattr(msg, 'printer_id') else 'formlabs',
                    f"Print job {msg.job_id if hasattr(msg, 'job_id') else 'unknown'} failed",
                    {
                        'job_id': msg.job_id if hasattr(msg, 'job_id') else '',
                        'layer': msg.current_layer if hasattr(msg, 'current_layer') else 0,
                        'error': msg.error_message if hasattr(msg, 'error_message') else '',
                    }
                )

    def _on_quality_event(self, msg):
        """Monitor quality events for rejections."""
        # Action codes: 5=STOP, 6=REWORK, 7=SCRAP
        if hasattr(msg, 'action') and msg.action in [6, 7]:
            severity = FailureSeverity.HIGH if msg.action == 7 else FailureSeverity.MEDIUM
            self._detect_failure(
                FailureType.QUALITY_REJECT,
                severity,
                msg.equipment_id if hasattr(msg, 'equipment_id') else 'vision',
                msg.description if hasattr(msg, 'description') else 'Quality rejection',
                {
                    'event_type': msg.event_type if hasattr(msg, 'event_type') else '',
                    'operation_id': msg.operation_id if hasattr(msg, 'operation_id') else '',
                    'work_order_id': msg.work_order_id if hasattr(msg, 'work_order_id') else '',
                }
            )

    def _on_estop(self, msg: Bool):
        """Handle emergency stop activation."""
        if msg.data:
            self._detect_failure(
                FailureType.SAFETY_VIOLATION,
                FailureSeverity.CRITICAL,
                'safety_system',
                "Emergency stop activated",
                {'estop_active': True}
            )

    def _check_heartbeats(self):
        """Check for equipment that hasn't been seen recently."""
        with self._lock:
            now = datetime.now()
            timeout = timedelta(seconds=self._heartbeat_timeout)

            for equipment_id, last_seen in list(self._equipment_last_seen.items()):
                if now - last_seen > timeout:
                    # Only report if not already failed
                    existing = [f for f in self._active_failures.values()
                               if f.equipment_id == equipment_id and
                               f.failure_type == FailureType.COMMUNICATION_LOST]
                    if not existing:
                        self._detect_failure(
                            FailureType.COMMUNICATION_LOST,
                            FailureSeverity.MEDIUM,
                            equipment_id,
                            f"No heartbeat from {equipment_id} for {self._heartbeat_timeout}s",
                            {}
                        )

    def _detect_failure(
        self,
        failure_type: FailureType,
        severity: FailureSeverity,
        equipment_id: str,
        description: str,
        context: Dict[str, Any]
    ):
        """Detect and publish a failure."""
        # Check for duplicate active failure
        for failure in self._active_failures.values():
            if (failure.equipment_id == equipment_id and
                failure.failure_type == failure_type and
                not failure.resolved):
                return  # Already tracking this failure

        self._failure_count += 1
        failure_id = f"FAIL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._failure_count:04d}"

        failure = DetectedFailure(
            failure_id=failure_id,
            failure_type=failure_type,
            severity=severity,
            equipment_id=equipment_id,
            description=description,
            context=context,
            operation_id=context.get('operation_id', ''),
            work_order_id=context.get('work_order_id', ''),
        )

        self._active_failures[failure_id] = failure
        self._failure_history.append(failure)

        # Log failure
        log_level = {
            FailureSeverity.LOW: self.get_logger().info,
            FailureSeverity.MEDIUM: self.get_logger().warn,
            FailureSeverity.HIGH: self.get_logger().error,
            FailureSeverity.CRITICAL: self.get_logger().error,
        }
        log_level[severity](f"FAILURE DETECTED: {failure_type.value} on {equipment_id}: {description}")

        # Publish failure event
        self._publish_failure(failure)

    def _publish_failure(self, failure: DetectedFailure):
        """Publish failure event to ROS2."""
        if MSGS_AVAILABLE:
            msg = FailureEvent()
            msg.failure_id = failure.failure_id
            msg.failure_type = failure.failure_type.value
            msg.failure_type_name = failure.failure_type.name
            msg.severity = failure.severity.value
            msg.equipment_id = failure.equipment_id
            msg.operation_id = failure.operation_id
            msg.work_order_id = failure.work_order_id
            msg.description = failure.description
            msg.timestamp = self.get_clock().now().to_msg()
            msg.context_json = json.dumps(failure.context)
            self._failure_pub.publish(msg)
        else:
            msg = String()
            msg.data = json.dumps({
                'failure_id': failure.failure_id,
                'failure_type': failure.failure_type.value,
                'severity': failure.severity.value,
                'equipment_id': failure.equipment_id,
                'operation_id': failure.operation_id,
                'work_order_id': failure.work_order_id,
                'description': failure.description,
                'timestamp': failure.timestamp.isoformat(),
                'context': failure.context,
            })
            self._failure_pub.publish(msg)

    def _resolve_failures(self, equipment_id: str, failure_types: List[FailureType]):
        """Mark failures as resolved."""
        for failure_id, failure in list(self._active_failures.items()):
            if (failure.equipment_id == equipment_id and
                failure.failure_type in failure_types and
                not failure.resolved):
                failure.resolved = True
                failure.resolution = 'auto_resolved'
                self.get_logger().info(f"Failure {failure_id} resolved")
                del self._active_failures[failure_id]

    def _state_to_string(self, state_code: int) -> str:
        """Convert equipment state code to string."""
        state_map = {
            0: 'disconnected',
            1: 'idle',
            2: 'busy',
            3: 'error',
            4: 'estop',
        }
        return state_map.get(state_code, 'unknown')

    def _print_status_to_string(self, status_code: int) -> str:
        """Convert print status code to string."""
        status_map = {
            0: 'IDLE',
            1: 'PRINTING',
            2: 'PAUSED',
            3: 'COMPLETE',
            4: 'FAILED',
            5: 'CANCELLED',
        }
        return status_map.get(status_code, 'UNKNOWN')

    def get_active_failures(self) -> List[DetectedFailure]:
        """Get list of active failures."""
        with self._lock:
            return list(self._active_failures.values())

    def get_failure_statistics(self) -> Dict[str, Any]:
        """Get failure statistics."""
        with self._lock:
            by_type = {}
            by_equipment = {}
            by_severity = {}

            for failure in self._failure_history:
                by_type[failure.failure_type.value] = by_type.get(failure.failure_type.value, 0) + 1
                by_equipment[failure.equipment_id] = by_equipment.get(failure.equipment_id, 0) + 1
                by_severity[failure.severity.name] = by_severity.get(failure.severity.name, 0) + 1

            return {
                'total_failures': len(self._failure_history),
                'active_failures': len(self._active_failures),
                'by_type': by_type,
                'by_equipment': by_equipment,
                'by_severity': by_severity,
            }


def main(args=None):
    rclpy.init(args=args)

    node = FailureDetectorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
