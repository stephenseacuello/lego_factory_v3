#!/usr/bin/env python3
"""
Tool Wear Monitor - Track tool usage and predict wear

Monitors cutting parameters, spindle load, and vibration to estimate tool wear.
Publishes tool wear predictions and replacement recommendations.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List
import json
import numpy as np
from datetime import datetime

from std_msgs.msg import String
from cnc_interfaces.msg import (
    SensorReading,
    MachineStatus,
    ToolWear,
)


@dataclass
class ToolState:
    """State tracking for a single tool"""
    tool_id: str
    tool_number: int
    tool_type: str = "end_mill"
    material: str = "Carbide"
    diameter: float = 6.0
    length: float = 50.0

    # Usage tracking
    cutting_time: float = 0.0  # hours
    cutting_distance: float = 0.0  # meters
    cycle_count: int = 0
    material_removed: float = 0.0  # cm³

    # Wear metrics (estimated)
    flank_wear: float = 0.0
    crater_wear: float = 0.0
    edge_chipping: float = 0.0

    # Thresholds
    max_flank_wear: float = 0.3  # mm
    max_cutting_time: float = 120.0  # hours for carbide

    # Session tracking
    session_start_time: float = 0.0
    session_feed_rate: float = 0.0
    session_spindle_speed: float = 0.0
    is_cutting: bool = False
    last_update: float = 0.0


class ToolWearMonitorNode(Node):
    """Monitor and predict tool wear"""

    def __init__(self):
        super().__init__('tool_wear_monitor')

        # Parameters
        self.declare_parameter('publish_rate', 0.5)
        self.declare_parameter('wear_model', 'taylor')  # taylor, empirical, ml

        self.publish_rate = self.get_parameter('publish_rate').value
        self.wear_model = self.get_parameter('wear_model').value

        # Tool tracking by machine and tool number
        self.tools: Dict[str, Dict[int, ToolState]] = defaultdict(dict)

        # Current machine states
        self.machine_states: Dict[str, MachineStatus] = {}

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscribers
        self.status_sub = self.create_subscription(
            MachineStatus,
            '/machine/status',
            self.status_callback,
            qos
        )

        # Multi-controller support
        for ctrl in ['tinyg', 'grbl']:
            self.create_subscription(
                MachineStatus, f'/{ctrl}/status',
                self.status_callback, qos
            )

        self.sensor_sub = self.create_subscription(
            SensorReading,
            '/sensors/raw',
            self.sensor_callback,
            qos
        )

        # Publishers
        self.wear_pub = self.create_publisher(
            ToolWear,
            '/tool/wear',
            qos
        )

        # Timer
        self.update_timer = self.create_timer(
            1.0 / self.publish_rate,
            self.update_callback
        )

        self.get_logger().info('Tool Wear Monitor started')

    def get_or_create_tool(self, machine_id: str, tool_number: int) -> ToolState:
        """Get or create tool state tracker"""
        if tool_number not in self.tools[machine_id]:
            tool_id = f"{machine_id}_T{tool_number}"
            self.tools[machine_id][tool_number] = ToolState(
                tool_id=tool_id,
                tool_number=tool_number
            )
        return self.tools[machine_id][tool_number]

    def status_callback(self, msg: MachineStatus):
        """Track machine status for tool wear calculation"""
        machine_id = msg.machine_id
        current_time = self.get_clock().now().nanoseconds / 1e9

        # Get current tool (assuming T1 if line_number contains tool info)
        tool_number = 1  # Default, could parse from G-code state
        tool = self.get_or_create_tool(machine_id, tool_number)

        prev_state = self.machine_states.get(machine_id)

        # Detect cutting state
        is_cutting = (
            msg.state == MachineStatus.STATE_RUN and
            msg.spindle_speed > 0 and
            msg.feed_rate > 0
        )

        # Track cutting time
        if is_cutting and not tool.is_cutting:
            # Started cutting
            tool.session_start_time = current_time
            tool.session_feed_rate = msg.feed_rate
            tool.session_spindle_speed = msg.spindle_speed
            tool.is_cutting = True

        elif not is_cutting and tool.is_cutting:
            # Stopped cutting
            if tool.session_start_time > 0:
                session_duration = (current_time - tool.session_start_time) / 3600  # hours
                tool.cutting_time += session_duration

                # Estimate distance
                distance = (tool.session_feed_rate * session_duration * 60) / 1000  # meters
                tool.cutting_distance += distance

                tool.cycle_count += 1
            tool.is_cutting = False

        tool.last_update = current_time
        self.machine_states[machine_id] = msg

    def sensor_callback(self, msg: SensorReading):
        """Use sensor data to refine wear estimation"""
        # Could use vibration, current draw, etc. to improve wear prediction
        pass

    def calculate_wear(self, tool: ToolState) -> Dict:
        """Calculate tool wear using Taylor's equation or empirical model"""
        wear_results = {
            'flank_wear': 0.0,
            'remaining_life': 100.0,
            'condition': ToolWear.CONDITION_NEW,
            'replace': False,
        }

        if self.wear_model == 'taylor':
            # Taylor's Tool Life Equation: VT^n = C
            # V = cutting speed, T = tool life, n = exponent, C = constant
            # For carbide tools: n ≈ 0.25-0.35, C depends on material
            n = 0.3
            C = 300  # Constant for carbide on steel

            # Estimate cutting speed from spindle speed and diameter
            if tool.session_spindle_speed > 0:
                cutting_speed = np.pi * tool.diameter * tool.session_spindle_speed / 1000  # m/min
            else:
                cutting_speed = 100  # Default

            # Expected tool life
            expected_life = (C / cutting_speed) ** (1/n) if cutting_speed > 0 else tool.max_cutting_time

            # Calculate wear progression
            life_used = tool.cutting_time / max(expected_life, 0.1)

            # Flank wear follows S-curve (slow-fast-slow)
            wear_results['flank_wear'] = tool.max_flank_wear * (
                1 / (1 + np.exp(-10 * (life_used - 0.5)))
            )

        else:
            # Empirical linear model
            wear_rate = tool.max_flank_wear / tool.max_cutting_time  # mm/hour
            wear_results['flank_wear'] = wear_rate * tool.cutting_time

        # Calculate remaining life percentage
        wear_ratio = wear_results['flank_wear'] / tool.max_flank_wear
        wear_results['remaining_life'] = max(0, (1 - wear_ratio) * 100)

        # Determine condition
        if wear_ratio < 0.2:
            wear_results['condition'] = ToolWear.CONDITION_NEW
        elif wear_ratio < 0.5:
            wear_results['condition'] = ToolWear.CONDITION_GOOD
        elif wear_ratio < 0.7:
            wear_results['condition'] = ToolWear.CONDITION_FAIR
        elif wear_ratio < 0.9:
            wear_results['condition'] = ToolWear.CONDITION_WORN
            wear_results['replace'] = True
        else:
            wear_results['condition'] = ToolWear.CONDITION_REPLACE
            wear_results['replace'] = True

        return wear_results

    def update_callback(self):
        """Periodic wear calculation and publishing"""
        current_time = self.get_clock().now().nanoseconds / 1e9

        for machine_id, tools in self.tools.items():
            for tool_num, tool in tools.items():
                # Skip stale tools
                if current_time - tool.last_update > 300:  # 5 min
                    continue

                # Calculate wear
                wear = self.calculate_wear(tool)

                # Update tool state
                tool.flank_wear = wear['flank_wear']

                # Publish message
                msg = ToolWear()
                msg.header.stamp = self.get_clock().now().to_msg()
                msg.machine_id = machine_id
                msg.tool_id = tool.tool_id
                msg.tool_type = tool.tool_type
                msg.tool_number = tool.tool_number
                msg.tool_diameter = tool.diameter
                msg.tool_length = tool.length
                msg.material = tool.material

                msg.flank_wear = wear['flank_wear']
                msg.crater_wear = tool.crater_wear
                msg.edge_chipping = tool.edge_chipping

                msg.cutting_time = tool.cutting_time
                msg.cutting_distance = tool.cutting_distance
                msg.cycle_count = tool.cycle_count
                msg.material_removed = tool.material_removed

                msg.remaining_life = wear['remaining_life']
                msg.condition = wear['condition']
                msg.replace_recommended = wear['replace']

                if wear['replace']:
                    msg.replacement_reason = "Flank wear exceeded threshold"

                self.wear_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ToolWearMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
