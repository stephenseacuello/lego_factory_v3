#!/usr/bin/env python3
"""
Machine Health Monitor Node
===========================
Specialized node for monitoring CNC machine health, detecting issues,
and tracking operational metrics.

Features:
- State transition monitoring
- Alarm frequency tracking
- OEE component tracking (availability)
- Feed rate and spindle anomaly detection
"""

from collections import deque
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Dict, Optional

import rclpy
from rclpy.node import Node

from cnc_interfaces.msg import MachineStatus, GrblStatus, Alarm


class MachineState(IntEnum):
    """Machine state codes matching cnc_interfaces."""
    DISCONNECTED = 0
    IDLE = 1
    RUN = 2
    HOLD = 3
    ALARM = 4
    HOMING = 5
    JOG = 6
    PROBE = 7
    RESET = 8


class MachineMonitorNode(Node):
    """
    Monitors CNC machine health and operational metrics.

    Subscribes to:
        - /tinyg/status: TinyG machine status
        - /grbl/status: GRBL machine status

    Publishes:
        - /system/alarms: Machine-related alarms
    """

    def __init__(self):
        super().__init__('machine_monitor')

        # Parameters
        self.declare_parameter('alarm_threshold', 3)  # Alarms in window
        self.declare_parameter('alarm_window_sec', 300)  # 5 minutes
        self.declare_parameter('idle_warning_sec', 600)  # 10 minutes
        self.declare_parameter('feed_anomaly_percent', 50)  # % deviation

        self.alarm_threshold = self.get_parameter('alarm_threshold').value
        self.alarm_window_sec = self.get_parameter('alarm_window_sec').value
        self.idle_warning_sec = self.get_parameter('idle_warning_sec').value
        self.feed_anomaly_percent = self.get_parameter('feed_anomaly_percent').value

        # Machine tracking
        self.machines: Dict[str, Dict] = {}

        # Subscriptions
        self.tinyg_sub = self.create_subscription(
            MachineStatus,
            '/tinyg/status',
            self._tinyg_callback,
            10
        )

        self.grbl_sub = self.create_subscription(
            GrblStatus,
            '/grbl/status',
            self._grbl_callback,
            10
        )

        # Publishers
        self.alarm_pub = self.create_publisher(Alarm, '/system/alarms', 10)

        # Timer for periodic checks
        self.check_timer = self.create_timer(10.0, self._periodic_check)

        self.get_logger().info('Machine Monitor Node started')
        self.get_logger().info(f'  Alarm threshold: {self.alarm_threshold} in {self.alarm_window_sec}s')
        self.get_logger().info(f'  Idle warning: {self.idle_warning_sec}s')

    def _get_or_create_machine(self, machine_id: str, machine_type: str) -> Dict:
        """Get or create machine tracking data."""
        if machine_id not in self.machines:
            self.machines[machine_id] = {
                'type': machine_type,
                'last_state': None,
                'current_state': MachineState.DISCONNECTED,
                'state_entered': datetime.now(),
                'alarm_history': deque(maxlen=100),
                'run_time': timedelta(),
                'idle_time': timedelta(),
                'alarm_time': timedelta(),
                'last_update': datetime.now(),
                'expected_feed_rate': None,
                'state_transitions': 0
            }
        return self.machines[machine_id]

    def _tinyg_callback(self, msg: MachineStatus):
        """Process TinyG status update."""
        machine_id = msg.machine_id or 'tinyg'
        machine = self._get_or_create_machine(machine_id, 'tinyg')

        self._update_machine_state(
            machine_id,
            machine,
            MachineState(msg.state),
            msg.feed_rate,
            msg.spindle_speed
        )

    def _grbl_callback(self, msg: GrblStatus):
        """Process GRBL status update."""
        machine_id = msg.machine_id or 'grbl'
        machine = self._get_or_create_machine(machine_id, 'grbl')

        self._update_machine_state(
            machine_id,
            machine,
            MachineState(msg.state),
            msg.feed_rate,
            msg.spindle_speed
        )

    def _update_machine_state(
        self,
        machine_id: str,
        machine: Dict,
        new_state: MachineState,
        feed_rate: float,
        spindle_speed: float
    ):
        """Update machine state and track metrics."""
        now = datetime.now()
        old_state = machine['current_state']

        # Update time accumulation
        elapsed = now - machine['last_update']
        if old_state == MachineState.RUN:
            machine['run_time'] += elapsed
        elif old_state == MachineState.IDLE:
            machine['idle_time'] += elapsed
        elif old_state == MachineState.ALARM:
            machine['alarm_time'] += elapsed

        machine['last_update'] = now

        # Handle state transition
        if new_state != old_state:
            machine['last_state'] = old_state
            machine['current_state'] = new_state
            machine['state_entered'] = now
            machine['state_transitions'] += 1

            self.get_logger().info(
                f'{machine_id}: State transition {old_state.name} -> {new_state.name}'
            )

            # Track alarm events
            if new_state == MachineState.ALARM:
                machine['alarm_history'].append(now)
                self._check_alarm_frequency(machine_id, machine)

            # Warn on unexpected state transitions
            if old_state == MachineState.RUN and new_state == MachineState.ALARM:
                self._publish_alarm(
                    machine_id,
                    'UNEXPECTED_ALARM',
                    Alarm.SEVERITY_ERROR,
                    'Machine alarmed during operation'
                )

        # Check feed rate anomaly during run
        if new_state == MachineState.RUN:
            if machine['expected_feed_rate'] is None and feed_rate > 0:
                machine['expected_feed_rate'] = feed_rate
            elif machine['expected_feed_rate'] is not None and feed_rate > 0:
                deviation = abs(feed_rate - machine['expected_feed_rate']) / machine['expected_feed_rate'] * 100
                if deviation > self.feed_anomaly_percent:
                    self._publish_alarm(
                        machine_id,
                        'FEED_RATE_ANOMALY',
                        Alarm.SEVERITY_WARNING,
                        f'Feed rate deviation: {deviation:.1f}% (expected {machine["expected_feed_rate"]:.0f}, actual {feed_rate:.0f})'
                    )

    def _check_alarm_frequency(self, machine_id: str, machine: Dict):
        """Check if alarm frequency exceeds threshold."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.alarm_window_sec)

        # Count alarms in window
        recent_alarms = sum(1 for t in machine['alarm_history'] if t > cutoff)

        if recent_alarms >= self.alarm_threshold:
            self._publish_alarm(
                machine_id,
                'EXCESSIVE_ALARMS',
                Alarm.SEVERITY_ERROR,
                f'{recent_alarms} alarms in last {self.alarm_window_sec}s - investigate root cause'
            )

    def _periodic_check(self):
        """Periodic health checks for all machines."""
        now = datetime.now()

        for machine_id, machine in self.machines.items():
            # Check for extended idle time
            if machine['current_state'] == MachineState.IDLE:
                idle_duration = (now - machine['state_entered']).total_seconds()
                if idle_duration > self.idle_warning_sec:
                    self._publish_alarm(
                        machine_id,
                        'EXTENDED_IDLE',
                        Alarm.SEVERITY_INFO,
                        f'Machine idle for {idle_duration / 60:.1f} minutes'
                    )
                    # Reset to avoid repeated alarms
                    machine['state_entered'] = now

            # Log availability metrics
            total = machine['run_time'] + machine['idle_time'] + machine['alarm_time']
            if total.total_seconds() > 0:
                availability = machine['run_time'] / total * 100
                self.get_logger().debug(
                    f'{machine_id} Availability: {availability:.1f}% '
                    f'(Run: {machine["run_time"]}, Idle: {machine["idle_time"]}, Alarm: {machine["alarm_time"]})'
                )

    def _publish_alarm(
        self,
        source_id: str,
        alarm_type: str,
        severity: int,
        message: str
    ):
        """Publish an alarm notification."""
        alarm = Alarm()
        alarm.alarm_id = f'{source_id}_{alarm_type}_{datetime.now().timestamp()}'
        alarm.source = source_id
        alarm.alarm_type = alarm_type
        alarm.severity = severity
        alarm.message = message
        alarm.timestamp = self.get_clock().now().to_msg()
        alarm.acknowledged = False

        self.alarm_pub.publish(alarm)
        self.get_logger().warn(f'MACHINE ALARM [{alarm_type}] {source_id}: {message}')


def main(args=None):
    rclpy.init(args=args)
    node = MachineMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down machine monitor...')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
