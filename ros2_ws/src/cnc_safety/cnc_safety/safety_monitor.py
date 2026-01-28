#!/usr/bin/env python3
"""
Safety Monitor - Comprehensive safety system monitoring

Monitors E-stops, interlocks, limits, and thermal conditions.
Publishes safety state and triggers alarms when conditions are violated.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from typing import Dict
from dataclasses import dataclass, field

from std_msgs.msg import Bool
from cnc_interfaces.msg import MachineStatus, SafetyState, Alarm, SensorReading
from cnc_interfaces.srv import SafetyReset, EmergencyStop


@dataclass
class MachineSetaState:
    """Safety state for a single machine"""
    machine_id: str
    estop_hardware: bool = False
    estop_software: bool = False
    door_interlock: bool = True  # True = closed/safe
    guard_interlock: bool = True
    x_limit_min: bool = False
    x_limit_max: bool = False
    y_limit_min: bool = False
    y_limit_max: bool = False
    z_limit_min: bool = False
    z_limit_max: bool = False
    spindle_temp: float = 25.0
    thermal_warning: bool = False
    last_update: float = 0.0


class SafetyMonitorNode(Node):
    """Comprehensive safety monitoring"""

    def __init__(self):
        super().__init__('safety_monitor')

        # Parameters
        self.declare_parameter('publish_rate', 10.0)
        self.declare_parameter('thermal_warning_temp', 60.0)
        self.declare_parameter('thermal_shutdown_temp', 80.0)

        self.publish_rate = self.get_parameter('publish_rate').value
        self.thermal_warning = self.get_parameter('thermal_warning_temp').value
        self.thermal_shutdown = self.get_parameter('thermal_shutdown_temp').value

        # Safety states per machine
        self.states: Dict[str, MachineSetaState] = {}

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscribers
        self.status_sub = self.create_subscription(
            MachineStatus, '/machine/status', self.status_callback, qos)

        self.sensor_sub = self.create_subscription(
            SensorReading, '/sensors/raw', self.sensor_callback, qos)

        self.estop_sub = self.create_subscription(
            Bool, '/safety/estop_hardware', self.estop_callback, qos)

        self.door_sub = self.create_subscription(
            Bool, '/safety/door_interlock', self.door_callback, qos)

        # Publishers
        self.safety_pub = self.create_publisher(SafetyState, '/safety/state', qos)
        self.alarm_pub = self.create_publisher(Alarm, '/safety/alarms', qos)
        self.estop_cmd_pub = self.create_publisher(Bool, '/safety/estop_command', qos)

        # Services
        self.reset_srv = self.create_service(
            SafetyReset, '/safety/reset', self.reset_callback)

        self.estop_srv = self.create_service(
            EmergencyStop, '/safety/emergency_stop', self.estop_service_callback)

        # Timer
        self.timer = self.create_timer(1.0 / self.publish_rate, self.publish_callback)

        self.get_logger().info('Safety Monitor started')

    def get_state(self, machine_id: str) -> MachineSetaState:
        if machine_id not in self.states:
            self.states[machine_id] = MachineSetaState(machine_id=machine_id)
        return self.states[machine_id]

    def status_callback(self, msg: MachineStatus):
        """Update safety state from machine status"""
        state = self.get_state(msg.machine_id)
        state.last_update = self.get_clock().now().nanoseconds / 1e9

        # Check for alarm state
        if msg.state == MachineStatus.STATE_ALARM:
            self.publish_alarm(msg.machine_id, 1001, "Machine in ALARM state", 2)

    def sensor_callback(self, msg: SensorReading):
        """Monitor temperature sensors for thermal safety"""
        if 'temperature' in msg.sensor_type.lower():
            machine_id = msg.sensor_id.split('_')[0] if '_' in msg.sensor_id else 'default'
            state = self.get_state(machine_id)

            if 'spindle' in msg.sensor_id.lower():
                state.spindle_temp = msg.value

                if msg.value >= self.thermal_shutdown:
                    state.thermal_warning = True
                    self.trigger_estop(machine_id, "Thermal shutdown - spindle overtemp")
                elif msg.value >= self.thermal_warning:
                    state.thermal_warning = True
                    self.publish_alarm(machine_id, 1002,
                        f"Spindle temperature warning: {msg.value:.1f}°C", 1)

    def estop_callback(self, msg: Bool):
        """Handle hardware E-stop signal"""
        for machine_id in self.states:
            state = self.states[machine_id]
            state.estop_hardware = msg.data

            if msg.data:
                self.publish_alarm(machine_id, 1000, "Hardware E-STOP activated", 3)

    def door_callback(self, msg: Bool):
        """Handle door interlock signal"""
        for machine_id in self.states:
            state = self.states[machine_id]
            prev = state.door_interlock
            state.door_interlock = msg.data

            if prev and not msg.data:  # Door opened
                self.publish_alarm(machine_id, 1003, "Door interlock opened", 1)

    def trigger_estop(self, machine_id: str, reason: str):
        """Trigger software E-stop"""
        state = self.get_state(machine_id)
        state.estop_software = True

        # Publish E-stop command
        cmd = Bool()
        cmd.data = True
        self.estop_cmd_pub.publish(cmd)

        self.publish_alarm(machine_id, 1010, f"Software E-STOP: {reason}", 3)
        self.get_logger().error(f"E-STOP triggered for {machine_id}: {reason}")

    def publish_alarm(self, machine_id: str, code: int, message: str, severity: int):
        """Publish safety alarm"""
        alarm = Alarm()
        alarm.header.stamp = self.get_clock().now().to_msg()
        alarm.machine_id = machine_id
        alarm.alarm_code = code
        alarm.message = message
        alarm.severity = severity
        self.alarm_pub.publish(alarm)

    def publish_callback(self):
        """Publish current safety state"""
        for machine_id, state in self.states.items():
            msg = SafetyState()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.machine_id = machine_id

            # E-stop states
            msg.estop_hardware = state.estop_hardware
            msg.estop_software = state.estop_software

            # Interlocks
            msg.door_interlock = state.door_interlock
            msg.guard_interlock = state.guard_interlock

            # Limits
            msg.x_limit_min = state.x_limit_min
            msg.x_limit_max = state.x_limit_max
            msg.y_limit_min = state.y_limit_min
            msg.y_limit_max = state.y_limit_max
            msg.z_limit_min = state.z_limit_min
            msg.z_limit_max = state.z_limit_max

            # Thermal
            msg.spindle_temperature = state.spindle_temp
            msg.thermal_warning = state.thermal_warning

            # Overall safety level
            if state.estop_hardware or state.estop_software:
                msg.safety_level = SafetyState.SAFETY_EMERGENCY
            elif not state.door_interlock or state.thermal_warning:
                msg.safety_level = SafetyState.SAFETY_CRITICAL
            elif any([state.x_limit_min, state.x_limit_max,
                     state.y_limit_min, state.y_limit_max,
                     state.z_limit_min, state.z_limit_max]):
                msg.safety_level = SafetyState.SAFETY_WARNING
            else:
                msg.safety_level = SafetyState.SAFETY_OK

            msg.reset_required = (msg.safety_level >= SafetyState.SAFETY_CRITICAL)

            self.safety_pub.publish(msg)

    def reset_callback(self, request, response):
        """Handle safety reset request"""
        machine_id = request.machine_id
        state = self.get_state(machine_id)

        # Check if reset is allowed
        conditions = []

        if state.estop_hardware:
            conditions.append("Release hardware E-stop")
        if not state.door_interlock:
            conditions.append("Close safety door")
        if state.spindle_temp >= self.thermal_shutdown:
            conditions.append("Wait for spindle to cool")

        if conditions:
            response.success = False
            response.message = "Cannot reset - conditions not met"
            response.remaining_conditions = conditions
            response.machine_ready = False
        else:
            state.estop_software = False
            state.thermal_warning = False

            response.success = True
            response.message = "Safety reset successful"
            response.remaining_conditions = []
            response.machine_ready = True

            self.get_logger().info(f"Safety reset for {machine_id}")

        response.current_state = self.create_safety_msg(machine_id, state)
        return response

    def estop_service_callback(self, request, response):
        """Handle E-stop service request"""
        machine_id = request.machine_id
        self.trigger_estop(machine_id, "Service request")
        response.success = True
        response.message = "E-stop activated"
        return response

    def create_safety_msg(self, machine_id: str, state: MachineSetaState) -> SafetyState:
        """Create SafetyState message from internal state"""
        msg = SafetyState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.machine_id = machine_id
        msg.estop_hardware = state.estop_hardware
        msg.estop_software = state.estop_software
        msg.door_interlock = state.door_interlock
        msg.spindle_temperature = state.spindle_temp
        msg.thermal_warning = state.thermal_warning
        return msg


def main(args=None):
    rclpy.init(args=args)
    node = SafetyMonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
