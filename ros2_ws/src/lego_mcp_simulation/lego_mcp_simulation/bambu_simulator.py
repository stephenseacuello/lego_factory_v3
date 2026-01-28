#!/usr/bin/env python3
"""
LEGO MCP Bambu Lab FDM Printer Simulator Node

Simulates Bambu Lab FDM printer for testing without real hardware.
Responds to MQTT-style commands and publishes simulated status.

LEGO MCP Manufacturing System v7.0
Industry 4.0/5.0 Architecture
"""

import json
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import QoSProfile, QoSReliabilityPolicy

from std_msgs.msg import String, Bool


class PrinterState(Enum):
    """Bambu printer states."""
    OFFLINE = 0
    IDLE = 1
    PREPARING = 2
    PRINTING = 3
    PAUSED = 4
    FINISHING = 5
    COMPLETED = 6
    FAILED = 7
    CALIBRATING = 8
    LEVELING = 9


class AMSState(Enum):
    """AMS (Automatic Material System) states."""
    IDLE = 0
    LOADING = 1
    UNLOADING = 2
    SWITCHING = 3
    ERROR = 4


@dataclass
class SimulatedPrintJob:
    """Simulated print job state."""
    job_id: str
    filename: str
    total_layers: int
    current_layer: int = 0
    progress_percent: float = 0.0
    time_remaining_min: float = 0.0
    total_time_min: float = 60.0
    start_time: float = 0.0
    filament_used_mm: float = 0.0
    total_filament_mm: float = 1000.0


@dataclass
class PrinterTemperatures:
    """Printer temperature readings."""
    nozzle_current: float = 25.0
    nozzle_target: float = 0.0
    bed_current: float = 25.0
    bed_target: float = 0.0
    chamber_current: float = 25.0
    chamber_target: float = 0.0


@dataclass
class PrinterPosition:
    """Printer head position."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    e: float = 0.0  # Extruder


class BambuSimulatorNode(Node):
    """
    Simulates Bambu Lab FDM printer for testing.

    Features:
    - Simulates MQTT-style command interface
    - Publishes realistic status updates
    - Supports print job simulation with layer progress
    - Simulates temperature changes
    - Configurable fault injection
    """

    def __init__(self):
        super().__init__('bambu_simulator')

        # Declare parameters
        self.declare_parameter('sim_speed', 1.0)
        self.declare_parameter('enable_faults', False)
        self.declare_parameter('fault_probability', 0.001)
        self.declare_parameter('status_rate', 1.0)
        self.declare_parameter('printer_model', 'A1')
        self.declare_parameter('has_ams', True)

        # Get parameters
        self._sim_speed = self.get_parameter('sim_speed').value
        self._enable_faults = self.get_parameter('enable_faults').value
        self._fault_probability = self.get_parameter('fault_probability').value
        self._status_rate = self.get_parameter('status_rate').value
        self._printer_model = self.get_parameter('printer_model').value
        self._has_ams = self.get_parameter('has_ams').value

        # Printer state
        self._state = PrinterState.IDLE
        self._ams_state = AMSState.IDLE
        self._temperatures = PrinterTemperatures()
        self._position = PrinterPosition()
        self._current_job: Optional[SimulatedPrintJob] = None
        self._error_message = ""
        self._wifi_signal = -45  # dBm

        # Callback group
        self._callback_group = ReentrantCallbackGroup()

        # QoS
        reliable_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            depth=10
        )

        # Publishers
        self._status_pub = self.create_publisher(
            String,
            '/lego_mcp/sim/bambu/status',
            reliable_qos
        )

        self._heartbeat_pub = self.create_publisher(
            String,
            '/lego_mcp/heartbeats',
            reliable_qos
        )

        self._event_pub = self.create_publisher(
            String,
            '/lego_mcp/sim/bambu/events',
            10
        )

        # Subscribers
        self._command_sub = self.create_subscription(
            String,
            '/lego_mcp/sim/bambu/command',
            self._command_callback,
            reliable_qos
        )

        # Timers
        self._status_timer = self.create_timer(
            1.0 / self._status_rate,
            self._publish_status,
            callback_group=self._callback_group
        )

        self._heartbeat_timer = self.create_timer(
            1.0,
            self._publish_heartbeat,
            callback_group=self._callback_group
        )

        self._simulation_timer = self.create_timer(
            0.1,  # 10Hz simulation update
            self._update_simulation,
            callback_group=self._callback_group
        )

        self.get_logger().info(
            f'Bambu Simulator started - Model: {self._printer_model}, '
            f'AMS: {self._has_ams}, Faults: {self._enable_faults}'
        )

    def _command_callback(self, msg: String):
        """Process incoming commands."""
        try:
            cmd = json.loads(msg.data)
            command = cmd.get('command', '')

            if command == 'start_print':
                self._start_print(cmd)
            elif command == 'pause':
                self._pause_print()
            elif command == 'resume':
                self._resume_print()
            elif command == 'cancel':
                self._cancel_print()
            elif command == 'set_temperature':
                self._set_temperature(cmd)
            elif command == 'home':
                self._home_axes()
            elif command == 'calibrate':
                self._start_calibration()
            elif command == 'load_filament':
                self._load_filament(cmd)
            elif command == 'unload_filament':
                self._unload_filament()
            else:
                self.get_logger().warning(f'Unknown command: {command}')

        except json.JSONDecodeError:
            self.get_logger().error(f'Invalid JSON command: {msg.data[:100]}')

    def _start_print(self, cmd: dict):
        """Start a simulated print job."""
        if self._state != PrinterState.IDLE:
            self.get_logger().warning('Cannot start print - printer not idle')
            return

        filename = cmd.get('filename', 'unknown.gcode')
        total_time = cmd.get('estimated_time_min', 60.0)
        layers = cmd.get('total_layers', 100)
        filament = cmd.get('total_filament_mm', 1000.0)

        self._current_job = SimulatedPrintJob(
            job_id=f'job_{int(time.time())}',
            filename=filename,
            total_layers=layers,
            total_time_min=total_time,
            total_filament_mm=filament,
            start_time=time.time(),
        )

        self._state = PrinterState.PREPARING
        self._temperatures.nozzle_target = cmd.get('nozzle_temp', 220.0)
        self._temperatures.bed_target = cmd.get('bed_temp', 60.0)

        self._publish_event('print_started', {'filename': filename})
        self.get_logger().info(f'Starting print: {filename}')

    def _pause_print(self):
        """Pause current print."""
        if self._state == PrinterState.PRINTING:
            self._state = PrinterState.PAUSED
            self._publish_event('print_paused', {})
            self.get_logger().info('Print paused')

    def _resume_print(self):
        """Resume paused print."""
        if self._state == PrinterState.PAUSED:
            self._state = PrinterState.PRINTING
            self._publish_event('print_resumed', {})
            self.get_logger().info('Print resumed')

    def _cancel_print(self):
        """Cancel current print."""
        if self._state in [PrinterState.PRINTING, PrinterState.PAUSED, PrinterState.PREPARING]:
            self._state = PrinterState.IDLE
            self._current_job = None
            self._temperatures.nozzle_target = 0
            self._temperatures.bed_target = 0
            self._publish_event('print_cancelled', {})
            self.get_logger().info('Print cancelled')

    def _set_temperature(self, cmd: dict):
        """Set target temperatures."""
        if 'nozzle' in cmd:
            self._temperatures.nozzle_target = cmd['nozzle']
        if 'bed' in cmd:
            self._temperatures.bed_target = cmd['bed']
        if 'chamber' in cmd:
            self._temperatures.chamber_target = cmd['chamber']

    def _home_axes(self):
        """Home all axes."""
        self._position = PrinterPosition()
        self._publish_event('homing_complete', {})

    def _start_calibration(self):
        """Start calibration routine."""
        if self._state == PrinterState.IDLE:
            self._state = PrinterState.CALIBRATING
            self._publish_event('calibration_started', {})

    def _load_filament(self, cmd: dict):
        """Load filament from AMS slot."""
        if self._has_ams:
            self._ams_state = AMSState.LOADING
            self._publish_event('filament_loading', {'slot': cmd.get('slot', 0)})

    def _unload_filament(self):
        """Unload current filament."""
        if self._has_ams:
            self._ams_state = AMSState.UNLOADING
            self._publish_event('filament_unloading', {})

    def _update_simulation(self):
        """Update simulation state."""
        dt = 0.1 * self._sim_speed

        # Update temperatures (thermal simulation)
        self._update_temperatures(dt)

        # Update print progress
        if self._state == PrinterState.PREPARING:
            self._update_preparing()
        elif self._state == PrinterState.PRINTING:
            self._update_printing(dt)
        elif self._state == PrinterState.CALIBRATING:
            self._update_calibrating()

        # Update AMS state
        self._update_ams()

        # Fault injection
        if self._enable_faults and self._state == PrinterState.PRINTING:
            self._check_faults()

    def _update_temperatures(self, dt: float):
        """Simulate temperature changes."""
        # Nozzle (faster response)
        temp_diff = self._temperatures.nozzle_target - self._temperatures.nozzle_current
        self._temperatures.nozzle_current += temp_diff * 0.1 * dt

        # Bed (slower response)
        temp_diff = self._temperatures.bed_target - self._temperatures.bed_current
        self._temperatures.bed_current += temp_diff * 0.05 * dt

        # Chamber (very slow)
        if self._temperatures.chamber_target > 0:
            temp_diff = self._temperatures.chamber_target - self._temperatures.chamber_current
            self._temperatures.chamber_current += temp_diff * 0.02 * dt

    def _update_preparing(self):
        """Update preparing phase (heating)."""
        nozzle_ready = abs(self._temperatures.nozzle_current - self._temperatures.nozzle_target) < 3
        bed_ready = abs(self._temperatures.bed_current - self._temperatures.bed_target) < 3

        if nozzle_ready and bed_ready:
            self._state = PrinterState.PRINTING
            self._publish_event('heating_complete', {})

    def _update_printing(self, dt: float):
        """Update printing progress."""
        if self._current_job is None:
            return

        job = self._current_job
        elapsed = time.time() - job.start_time
        progress = min(100.0, (elapsed / (job.total_time_min * 60)) * 100 * self._sim_speed)

        job.progress_percent = progress
        job.current_layer = int((progress / 100) * job.total_layers)
        job.time_remaining_min = max(0, job.total_time_min - (elapsed / 60 * self._sim_speed))
        job.filament_used_mm = (progress / 100) * job.total_filament_mm

        # Simulate position changes
        self._position.z = (job.current_layer * 0.2)  # 0.2mm layer height
        self._position.x = 125 + 100 * math.sin(elapsed)  # Simulated movement
        self._position.y = 125 + 100 * math.cos(elapsed)

        # Check completion
        if progress >= 100:
            self._state = PrinterState.FINISHING
            self._publish_event('print_finishing', {})
            # Brief finishing phase
            self._state = PrinterState.COMPLETED
            self._publish_event('print_completed', {
                'filename': job.filename,
                'total_time_min': elapsed / 60,
                'filament_used_mm': job.filament_used_mm,
            })
            self._current_job = None
            self._temperatures.nozzle_target = 0
            self._temperatures.bed_target = 0
            self._state = PrinterState.IDLE

    def _update_calibrating(self):
        """Update calibration progress."""
        # Simple timeout-based calibration
        if random.random() < 0.01 * self._sim_speed:
            self._state = PrinterState.IDLE
            self._publish_event('calibration_complete', {})

    def _update_ams(self):
        """Update AMS state."""
        if self._ams_state == AMSState.LOADING:
            if random.random() < 0.05 * self._sim_speed:
                self._ams_state = AMSState.IDLE
                self._publish_event('filament_loaded', {})
        elif self._ams_state == AMSState.UNLOADING:
            if random.random() < 0.05 * self._sim_speed:
                self._ams_state = AMSState.IDLE
                self._publish_event('filament_unloaded', {})

    def _check_faults(self):
        """Check for random fault injection."""
        if random.random() < self._fault_probability:
            fault_type = random.choice([
                'filament_runout',
                'nozzle_clog',
                'bed_adhesion_failure',
                'power_loss_simulation',
            ])

            self._state = PrinterState.FAILED
            self._error_message = f'Simulated fault: {fault_type}'
            self._publish_event('print_failed', {
                'reason': fault_type,
                'layer': self._current_job.current_layer if self._current_job else 0,
            })
            self.get_logger().warning(f'Injected fault: {fault_type}')

    def _publish_status(self):
        """Publish printer status."""
        status = {
            'timestamp': time.time(),
            'state': self._state.name,
            'printer_model': self._printer_model,
            'temperatures': {
                'nozzle': {
                    'current': round(self._temperatures.nozzle_current, 1),
                    'target': self._temperatures.nozzle_target,
                },
                'bed': {
                    'current': round(self._temperatures.bed_current, 1),
                    'target': self._temperatures.bed_target,
                },
                'chamber': {
                    'current': round(self._temperatures.chamber_current, 1),
                    'target': self._temperatures.chamber_target,
                },
            },
            'position': {
                'x': round(self._position.x, 2),
                'y': round(self._position.y, 2),
                'z': round(self._position.z, 2),
            },
            'wifi_signal': self._wifi_signal,
            'ams_state': self._ams_state.name if self._has_ams else None,
        }

        if self._current_job:
            status['job'] = {
                'id': self._current_job.job_id,
                'filename': self._current_job.filename,
                'progress': round(self._current_job.progress_percent, 1),
                'current_layer': self._current_job.current_layer,
                'total_layers': self._current_job.total_layers,
                'time_remaining_min': round(self._current_job.time_remaining_min, 1),
                'filament_used_mm': round(self._current_job.filament_used_mm, 1),
            }

        if self._error_message:
            status['error'] = self._error_message

        msg = String()
        msg.data = json.dumps(status)
        self._status_pub.publish(msg)

    def _publish_heartbeat(self):
        """Publish heartbeat for supervision."""
        heartbeat = {
            'node_id': 'bambu_simulator',
            'node_name': self.get_name(),
            'namespace': self.get_namespace(),
            'timestamp': time.time(),
            'state': 'running' if self._state != PrinterState.FAILED else 'error',
            'cpu_percent': random.uniform(5, 15),
            'memory_mb': random.uniform(50, 100),
            'error_count': 1 if self._state == PrinterState.FAILED else 0,
        }

        msg = String()
        msg.data = json.dumps(heartbeat)
        self._heartbeat_pub.publish(msg)

    def _publish_event(self, event_type: str, data: dict):
        """Publish event."""
        event = {
            'timestamp': time.time(),
            'event': event_type,
            'data': data,
        }

        msg = String()
        msg.data = json.dumps(event)
        self._event_pub.publish(msg)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = BambuSimulatorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
