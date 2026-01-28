#!/usr/bin/env python3
"""
LEGO MCP Quality Bridge Node
Subscribes to quality events and triggers scheduler/orchestrator actions.

LEGO MCP Manufacturing System v7.0
"""

from typing import Dict, List, Any
from datetime import datetime
import json

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String

try:
    from lego_mcp_msgs.msg import QualityEvent
    from lego_mcp_msgs.srv import RescheduleRemaining
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False


class QualityFeedbackNode(Node):
    """
    Subscribes to quality events and triggers scheduler actions.
    """

    def __init__(self):
        super().__init__('quality_feedback')

        # Parameters
        self.declare_parameter('auto_stop_on_critical', True)
        self.declare_parameter('auto_rework_enabled', True)

        self._auto_stop = self.get_parameter('auto_stop_on_critical').value
        self._auto_rework = self.get_parameter('auto_rework_enabled').value

        # Event history
        self._event_history: List[Dict[str, Any]] = []

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Subscribers
        if MSGS_AVAILABLE:
            self.create_subscription(
                QualityEvent,
                '/quality/events',
                self._on_quality_event,
                10,
                callback_group=self._cb_group
            )
        else:
            self.create_subscription(
                String,
                '/quality/events',
                self._on_quality_event_string,
                10,
                callback_group=self._cb_group
            )

        # Publishers
        self._stop_pub = self.create_publisher(
            String,
            '/manufacturing/stop_operation',
            10
        )

        self._rework_pub = self.create_publisher(
            String,
            '/manufacturing/rework_request',
            10
        )

        self._adjustment_pub = self.create_publisher(
            String,
            '/manufacturing/parameter_adjustment',
            10
        )

        # Service clients
        if MSGS_AVAILABLE:
            self._reschedule_client = self.create_client(
                RescheduleRemaining,
                '/scheduling/reschedule_remaining',
                callback_group=self._cb_group
            )

        self.get_logger().info("Quality feedback node initialized")

    def _on_quality_event(self, msg):
        """React to quality events."""
        # Store event
        self._event_history.append({
            'event_type': msg.event_type,
            'severity': msg.severity,
            'action': msg.action,
            'action_name': msg.action_name,
            'description': msg.description,
            'operation_id': msg.operation_id,
            'work_order_id': msg.work_order_id,
            'timestamp': datetime.now().isoformat(),
        })

        # Quality action codes:
        # 1=MONITOR, 2=INSPECT, 3=WARN, 4=ADJUST, 5=STOP, 6=REWORK, 7=SCRAP

        if msg.action == 5:  # STOP
            self.get_logger().error(f"Quality STOP: {msg.description}")
            if self._auto_stop:
                self._stop_current_operation(msg.operation_id, msg.work_order_id)

        elif msg.action == 4:  # ADJUST
            self.get_logger().warn(f"Quality ADJUST: {msg.description}")
            self._request_parameter_adjustment(msg)

        elif msg.action == 6:  # REWORK
            self.get_logger().warn(f"Quality REWORK: {msg.description}")
            if self._auto_rework:
                self._schedule_rework(msg.operation_id, msg.work_order_id)

        elif msg.action == 7:  # SCRAP
            self.get_logger().error(f"Quality SCRAP: {msg.description}")
            self._schedule_replacement(msg.operation_id, msg.work_order_id)

    def _on_quality_event_string(self, msg: String):
        """Handle quality event as JSON string."""
        try:
            data = json.loads(msg.data)
            # Process similar to typed message
            action = data.get('action', 'MONITOR')

            self._event_history.append({
                **data,
                'timestamp': datetime.now().isoformat(),
            })

            if action == 'STOP':
                self._stop_current_operation(
                    data.get('operation_id', ''),
                    data.get('work_order_id', '')
                )
            elif action == 'REWORK':
                self._schedule_rework(
                    data.get('operation_id', ''),
                    data.get('work_order_id', '')
                )

        except json.JSONDecodeError:
            self.get_logger().error(f"Invalid quality event: {msg.data}")

    def _stop_current_operation(self, operation_id: str, work_order_id: str):
        """Stop the current operation."""
        stop_msg = String()
        stop_msg.data = json.dumps({
            'command': 'stop',
            'operation_id': operation_id,
            'work_order_id': work_order_id,
            'reason': 'quality_stop',
            'timestamp': datetime.now().isoformat(),
        })
        self._stop_pub.publish(stop_msg)
        self.get_logger().info(f"Stop command sent for operation {operation_id}")

    def _request_parameter_adjustment(self, event):
        """Request parameter adjustment based on quality event."""
        adjust_msg = String()
        adjust_msg.data = json.dumps({
            'event_type': event.event_type,
            'severity': event.severity,
            'description': event.description,
            'operation_id': event.operation_id,
            'work_order_id': event.work_order_id,
            'suggested_adjustments': self._get_suggested_adjustments(event),
            'timestamp': datetime.now().isoformat(),
        })
        self._adjustment_pub.publish(adjust_msg)

    def _get_suggested_adjustments(self, event) -> Dict[str, Any]:
        """Get suggested parameter adjustments based on event type."""
        # Map event types to adjustments
        adjustments = {
            'over_extrusion': {'flow_rate': -5},
            'under_extrusion': {'flow_rate': 5},
            'warping': {'bed_temp': 5, 'chamber_temp': 5},
            'stringing': {'retraction': 0.5, 'temp': -5},
            'layer_shift': {'speed': -10, 'acceleration': -500},
            'elephant_foot': {'first_layer_height': -0.05},
            'dimensional_deviation': {'scale': 0.5},
        }
        return adjustments.get(event.event_type, {})

    def _schedule_rework(self, operation_id: str, work_order_id: str):
        """Schedule rework for the operation."""
        rework_msg = String()
        rework_msg.data = json.dumps({
            'type': 'rework',
            'operation_id': operation_id,
            'work_order_id': work_order_id,
            'timestamp': datetime.now().isoformat(),
        })
        self._rework_pub.publish(rework_msg)
        self.get_logger().info(f"Rework scheduled for operation {operation_id}")

    def _schedule_replacement(self, operation_id: str, work_order_id: str):
        """Schedule replacement part after scrap."""
        # This would trigger a new operation to be scheduled
        rework_msg = String()
        rework_msg.data = json.dumps({
            'type': 'replacement',
            'original_operation_id': operation_id,
            'work_order_id': work_order_id,
            'reason': 'scrap',
            'timestamp': datetime.now().isoformat(),
        })
        self._rework_pub.publish(rework_msg)
        self.get_logger().info(f"Replacement scheduled for scrapped operation {operation_id}")

    def get_event_statistics(self) -> Dict[str, Any]:
        """Get quality event statistics."""
        by_action = {}
        by_type = {}

        for event in self._event_history:
            action = event.get('action_name', 'UNKNOWN')
            by_action[action] = by_action.get(action, 0) + 1

            event_type = event.get('event_type', 'unknown')
            by_type[event_type] = by_type.get(event_type, 0) + 1

        return {
            'total_events': len(self._event_history),
            'by_action': by_action,
            'by_type': by_type,
        }


def main(args=None):
    rclpy.init(args=args)

    node = QualityFeedbackNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
