#!/usr/bin/env python3
"""
ROS2 Runtime Safety Monitor Node

Integrates the SafetyNodeMonitor with ROS2 to provide real-time
verification of safety properties during system operation.

This node:
- Subscribes to safety state topics
- Validates all TLA+ safety invariants at runtime
- Publishes violation alerts
- Logs safety events to audit trail

IEC 61508 SIL 2+ Runtime Verification

Author: LEGO MCP Safety Engineering
"""

import sys
import os

# Add dashboard services to path for monitor imports
# Navigate from scripts/ -> lego_mcp_safety_certified/ -> src/ -> ros2_ws/ -> project_root/
project_root = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..'
))
sys.path.insert(0, project_root)

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from std_msgs.msg import String, Bool
    from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    print("ROS2 not available - running in standalone mode")

from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging

# Import the safety monitor
from dashboard.services.verification.monitors.safety_node_monitor import (
    SafetyNodeMonitor,
    SAFETY_STATES,
    RELAY_STATES,
)
from dashboard.services.verification.monitors import (
    MonitorStatus,
    MonitorSeverity,
    MonitorReport,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SafetyStateMessage:
    """Safety state received from ROS2 topics."""
    safety_state: str
    primary_relay: str
    secondary_relay: str
    heartbeat_counter: int
    heartbeat_received: bool
    hw_estop_pressed: bool
    primary_fault: bool
    secondary_fault: bool
    time: int
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for monitor."""
        return {
            'safety_state': self.safety_state,
            'primary_relay': self.primary_relay,
            'secondary_relay': self.secondary_relay,
            'heartbeat_counter': self.heartbeat_counter,
            'heartbeat_received': self.heartbeat_received,
            'hw_estop_pressed': self.hw_estop_pressed,
            'primary_fault': self.primary_fault,
            'secondary_fault': self.secondary_fault,
            'time': self.time,
        }


class RuntimeMonitorBridge:
    """
    Bridge between ROS2 messages and SafetyNodeMonitor.

    Translates ROS2 safety state into monitor-compatible format
    and publishes violations back to ROS2.
    """

    def __init__(self):
        self.monitor = SafetyNodeMonitor()
        self.last_state: Optional[SafetyStateMessage] = None
        self.check_count = 0
        self.violation_count = 0
        self.last_report: Optional[MonitorReport] = None

    def update_state(
        self,
        safety_state: str,
        primary_relay: str,
        secondary_relay: str,
        heartbeat_counter: int,
        heartbeat_received: bool,
        hw_estop_pressed: bool,
        primary_fault: bool,
        secondary_fault: bool,
        time: int
    ) -> MonitorReport:
        """
        Update state and run all safety checks.

        Returns MonitorReport with check results.
        """
        self.last_state = SafetyStateMessage(
            safety_state=safety_state,
            primary_relay=primary_relay,
            secondary_relay=secondary_relay,
            heartbeat_counter=heartbeat_counter,
            heartbeat_received=heartbeat_received,
            hw_estop_pressed=hw_estop_pressed,
            primary_fault=primary_fault,
            secondary_fault=secondary_fault,
            time=time,
            timestamp=datetime.now(timezone.utc),
        )

        # Run all safety checks
        state_dict = self.last_state.to_dict()
        report = self.monitor.check_all(state_dict)

        self.check_count += 1
        if not report.all_passed:
            self.violation_count += 1

        self.last_report = report
        return report

    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        monitor_stats = self.monitor.get_statistics()
        return {
            **monitor_stats,
            'bridge_check_count': self.check_count,
            'bridge_violation_count': self.violation_count,
            'last_check_timestamp': self.last_state.timestamp.isoformat() if self.last_state else None,
        }


if ROS2_AVAILABLE:
    class RuntimeMonitorNode(Node):
        """
        ROS2 Node for runtime safety monitoring.

        Subscribes to:
        - /safety/state (JSON safety state)
        - /safety/estop_status (Bool)
        - /safety/relay_status (JSON relay states)

        Publishes to:
        - /safety/monitor/status (DiagnosticArray)
        - /safety/monitor/violations (JSON violation details)
        - /safety/monitor/alert (Bool - true on violation)
        """

        def __init__(self):
            super().__init__('runtime_safety_monitor')

            # Initialize bridge
            self.bridge = RuntimeMonitorBridge()

            # QoS for safety-critical topics
            safety_qos = QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
                depth=10,
            )

            # Subscribers
            self.state_sub = self.create_subscription(
                String,
                '/safety/state',
                self.state_callback,
                safety_qos
            )

            # Publishers
            self.diagnostics_pub = self.create_publisher(
                DiagnosticArray,
                '/safety/monitor/status',
                safety_qos
            )

            self.violations_pub = self.create_publisher(
                String,
                '/safety/monitor/violations',
                safety_qos
            )

            self.alert_pub = self.create_publisher(
                Bool,
                '/safety/monitor/alert',
                safety_qos
            )

            # Timer for periodic status publishing
            self.status_timer = self.create_timer(1.0, self.publish_status)

            self.get_logger().info('Runtime Safety Monitor Node initialized')
            self.get_logger().info(f'Monitoring {len(self.bridge.monitor._invariants)} invariants')
            self.get_logger().info(f'Monitoring {len(self.bridge.monitor._safety_properties)} safety properties')

        def state_callback(self, msg: String):
            """Handle incoming safety state."""
            try:
                state = json.loads(msg.data)

                report = self.bridge.update_state(
                    safety_state=state.get('safety_state', 'UNKNOWN'),
                    primary_relay=state.get('primary_relay', 'UNKNOWN'),
                    secondary_relay=state.get('secondary_relay', 'UNKNOWN'),
                    heartbeat_counter=state.get('heartbeat_counter', 0),
                    heartbeat_received=state.get('heartbeat_received', False),
                    hw_estop_pressed=state.get('hw_estop_pressed', False),
                    primary_fault=state.get('primary_fault', False),
                    secondary_fault=state.get('secondary_fault', False),
                    time=state.get('time', 0),
                )

                # Publish alert if violations detected
                alert_msg = Bool()
                alert_msg.data = not report.all_passed
                self.alert_pub.publish(alert_msg)

                # Publish violation details if any
                if not report.all_passed:
                    violations = [
                        r.to_dict() for r in report.results
                        if r.status == MonitorStatus.VIOLATED
                    ]
                    violations_msg = String()
                    violations_msg.data = json.dumps({
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'violations': violations,
                        'state_snapshot': state,
                    })
                    self.violations_pub.publish(violations_msg)

                    self.get_logger().warn(
                        f'Safety violations detected: {len(violations)} properties violated'
                    )

            except json.JSONDecodeError as e:
                self.get_logger().error(f'Failed to parse safety state: {e}')
            except Exception as e:
                self.get_logger().error(f'Error processing safety state: {e}')

        def publish_status(self):
            """Publish diagnostic status."""
            diag_array = DiagnosticArray()
            diag_array.header.stamp = self.get_clock().now().to_msg()

            # Overall status
            status = DiagnosticStatus()
            status.name = 'RuntimeSafetyMonitor'
            status.hardware_id = 'safety_monitor_1'

            stats = self.bridge.get_statistics()
            last_report = self.bridge.last_report

            if last_report is None:
                status.level = DiagnosticStatus.STALE
                status.message = 'No safety state received yet'
            elif last_report.all_passed:
                status.level = DiagnosticStatus.OK
                status.message = f'All {last_report.checks_total} safety checks passed'
            elif last_report.has_safety_critical_failure:
                status.level = DiagnosticStatus.ERROR
                status.message = f'SAFETY CRITICAL: {last_report.checks_failed} violations'
            else:
                status.level = DiagnosticStatus.WARN
                status.message = f'{last_report.checks_failed} checks failed'

            status.values = [
                KeyValue(key='invariant_count', value=str(stats['invariant_count'])),
                KeyValue(key='safety_property_count', value=str(stats['safety_property_count'])),
                KeyValue(key='total_checks', value=str(stats['bridge_check_count'])),
                KeyValue(key='total_violations', value=str(stats['bridge_violation_count'])),
            ]

            diag_array.status.append(status)
            self.diagnostics_pub.publish(diag_array)


def main_ros2():
    """ROS2 main entry point."""
    rclpy.init()
    node = RuntimeMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


def main_standalone():
    """Standalone mode for testing without ROS2."""
    print("Running in standalone mode (ROS2 not available)")

    bridge = RuntimeMonitorBridge()

    # Simulate some state transitions
    test_states = [
        # Normal operation
        {
            'safety_state': 'NORMAL',
            'primary_relay': 'CLOSED',
            'secondary_relay': 'CLOSED',
            'heartbeat_counter': 0,
            'heartbeat_received': True,
            'hw_estop_pressed': False,
            'primary_fault': False,
            'secondary_fault': False,
            'time': 0,
        },
        # E-stop pressed (correct)
        {
            'safety_state': 'ESTOP_ACTIVE',
            'primary_relay': 'OPEN',
            'secondary_relay': 'OPEN',
            'heartbeat_counter': 5,
            'heartbeat_received': False,
            'hw_estop_pressed': True,
            'primary_fault': False,
            'secondary_fault': False,
            'time': 100,
        },
        # E-stop with stuck relay (violation)
        {
            'safety_state': 'ESTOP_ACTIVE',
            'primary_relay': 'CLOSED',
            'secondary_relay': 'OPEN',
            'heartbeat_counter': 10,
            'heartbeat_received': False,
            'hw_estop_pressed': True,
            'primary_fault': False,
            'secondary_fault': False,
            'time': 200,
        },
    ]

    print("\n" + "="*60)
    print("Simulating Safety State Transitions")
    print("="*60)

    for i, state in enumerate(test_states):
        print(f"\n--- State {i+1}: {state['safety_state']} ---")
        report = bridge.update_state(**state)

        print(f"Checks: {report.checks_passed}/{report.checks_total} passed")
        if not report.all_passed:
            print("VIOLATIONS DETECTED:")
            for result in report.results:
                if result.status == MonitorStatus.VIOLATED:
                    print(f"  - {result.property_name}: {result.message}")

    print("\n" + "="*60)
    print("Bridge Statistics")
    print("="*60)
    stats = bridge.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")


def main():
    """Main entry point."""
    if ROS2_AVAILABLE:
        main_ros2()
    else:
        main_standalone()


if __name__ == '__main__':
    main()
