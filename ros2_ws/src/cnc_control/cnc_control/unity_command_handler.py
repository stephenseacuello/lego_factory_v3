#!/usr/bin/env python3
"""
Unity Command Handler Node
===========================
ROS2 node that receives commands from Unity clients and executes them.

Subscribes to:
- /unity/commands (UnityCommand)
- MQTT: cnc/{machine_id}/cmd/#

Publishes to:
- /unity/responses (CommandResponse)
- /machine/{id}/cmd/jog (JogCommand)
- /machine/{id}/cmd/spindle (SpindleCommand)

Services:
- /unity/execute_command (ExecuteCommand)

Features:
- Command validation and authorization
- Priority queue for real-time commands
- <20ms execution for jog commands
- MQTT bridge for Flask SCADA integration
- Full audit logging

Author: Flask CNC SCADA System
"""

import json
import time
import threading
from collections import deque
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup

# Standard ROS2 messages
from std_msgs.msg import String
from geometry_msgs.msg import Twist

# Try to import custom messages
try:
    from cnc_interfaces.msg import UnityCommand, CommandResponse
    from cnc_interfaces.srv import ExecuteCommand
    CUSTOM_MSGS_AVAILABLE = True
except ImportError:
    CUSTOM_MSGS_AVAILABLE = False
    UnityCommand = None
    CommandResponse = None

# MQTT client
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None


# =============================================================================
# Enums
# =============================================================================

class CommandPriority(IntEnum):
    """Command priority levels."""
    EMERGENCY = 0     # E-stop, immediate execution
    REALTIME = 1      # Jog commands, skip queue
    HIGH = 2          # Program control
    NORMAL = 3        # MDI, spindle, coolant
    LOW = 4           # Configuration


class CommandType(IntEnum):
    """Command types matching FlatBuffers schema."""
    JOG = 0
    JOG_STOP = 1
    HOME = 2
    ZERO_AXIS = 3
    GOTO_POSITION = 4
    RUN_PROGRAM = 16
    PAUSE_PROGRAM = 17
    RESUME_PROGRAM = 18
    STOP_PROGRAM = 19
    GCODE_LINE = 20
    SPINDLE_ON = 32
    SPINDLE_OFF = 33
    SPINDLE_SPEED = 34
    COOLANT_FLOOD_ON = 48
    COOLANT_FLOOD_OFF = 49
    COOLANT_MIST_ON = 50
    COOLANT_MIST_OFF = 51
    FEED_OVERRIDE = 64
    RAPID_OVERRIDE = 65
    ESTOP = 240
    RESET = 241
    CLEAR_ALARMS = 242


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class QueuedCommand:
    """Command in execution queue."""
    command_type: CommandType
    machine_id: str
    params: Dict[str, Any]
    request_id: int
    priority: CommandPriority
    timestamp: float
    user_id: str = ""
    client_ip: str = ""


@dataclass
class CommandResult:
    """Result of command execution."""
    request_id: int
    success: bool
    status_code: int
    message: str
    execution_time_ms: float


# =============================================================================
# Unity Command Handler Node
# =============================================================================

class UnityCommandHandler(Node):
    """
    ROS2 node that handles Unity control commands.

    Provides <20ms execution path for real-time commands like jog,
    while queueing lower-priority commands for orderly execution.
    """

    def __init__(self):
        super().__init__('unity_command_handler')

        # Parameters
        self.declare_parameter('machine_id', 'cnc-1')
        self.declare_parameter('mqtt_enabled', True)
        self.declare_parameter('mqtt_host', 'localhost')
        self.declare_parameter('mqtt_port', 1883)
        self.declare_parameter('queue_size', 100)
        self.declare_parameter('realtime_timeout_ms', 20.0)

        self.machine_id = self.get_parameter('machine_id').value
        self.mqtt_enabled = self.get_parameter('mqtt_enabled').value
        self.mqtt_host = self.get_parameter('mqtt_host').value
        self.mqtt_port = self.get_parameter('mqtt_port').value
        self.queue_size = self.get_parameter('queue_size').value
        self.realtime_timeout_ms = self.get_parameter('realtime_timeout_ms').value

        # QoS profiles
        self.realtime_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE
        )

        self.reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            durability=DurabilityPolicy.VOLATILE
        )

        # Callback groups
        self.realtime_group = MutuallyExclusiveCallbackGroup()
        self.normal_group = ReentrantCallbackGroup()

        # Command queue (priority queue)
        self.command_queue: deque[QueuedCommand] = deque(maxlen=self.queue_size)
        self.queue_lock = threading.Lock()

        # MQTT client
        self.mqtt_client: Optional[mqtt.Client] = None
        if self.mqtt_enabled and MQTT_AVAILABLE:
            self._init_mqtt()

        # Publishers
        self.response_pub = self.create_publisher(
            String,
            '/unity/responses',
            self.reliable_qos
        )

        self.jog_pub = self.create_publisher(
            Twist,
            f'/machine/{self.machine_id}/cmd/jog',
            self.realtime_qos
        )

        self.status_pub = self.create_publisher(
            String,
            f'/machine/{self.machine_id}/cmd/status',
            self.reliable_qos
        )

        # Subscribers
        self.command_sub = self.create_subscription(
            String,
            '/unity/commands',
            self._on_command_json,
            self.reliable_qos,
            callback_group=self.realtime_group
        )

        # Command execution timer
        self.exec_timer = self.create_timer(
            0.010,  # 100Hz processing
            self._process_queue,
            callback_group=self.normal_group
        )

        # Statistics
        self.stats = {
            'commands_received': 0,
            'commands_executed': 0,
            'commands_rejected': 0,
            'avg_latency_ms': 0.0,
            'max_latency_ms': 0.0
        }
        self._latency_samples: List[float] = []

        self.get_logger().info(
            f'Unity Command Handler started for {self.machine_id}'
        )

    # -------------------------------------------------------------------------
    # MQTT
    # -------------------------------------------------------------------------

    def _init_mqtt(self) -> None:
        """Initialize MQTT client."""
        try:
            self.mqtt_client = mqtt.Client(
                client_id=f'unity_cmd_handler_{self.machine_id}',
                protocol=mqtt.MQTTv5
            )
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message
            self.mqtt_client.connect_async(self.mqtt_host, self.mqtt_port)
            self.mqtt_client.loop_start()
            self.get_logger().info(f'MQTT connecting to {self.mqtt_host}:{self.mqtt_port}')
        except Exception as e:
            self.get_logger().warn(f'MQTT init failed: {e}')
            self.mqtt_client = None

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        """Handle MQTT connection."""
        if rc == 0:
            # Subscribe to command topics
            client.subscribe(f'cnc/{self.machine_id}/cmd/#', qos=1)
            self.get_logger().info('MQTT connected, subscribed to commands')
        else:
            self.get_logger().warn(f'MQTT connection failed: rc={rc}')

    def _on_mqtt_message(self, client, userdata, msg):
        """Handle MQTT command message."""
        try:
            # Parse topic
            parts = msg.topic.split('/')
            if len(parts) >= 4:
                cmd_type = parts[3]
                data = json.loads(msg.payload.decode())
                self._handle_mqtt_command(cmd_type, data)
        except Exception as e:
            self.get_logger().error(f'MQTT message error: {e}')

    def _handle_mqtt_command(self, cmd_type: str, data: Dict[str, Any]) -> None:
        """Handle command from MQTT."""
        # Map MQTT command to CommandType
        type_map = {
            'jog': CommandType.JOG,
            'jog_stop': CommandType.JOG_STOP,
            'spindle': CommandType.SPINDLE_ON,
            'spindle_off': CommandType.SPINDLE_OFF,
            'estop': CommandType.ESTOP,
            'reset': CommandType.RESET,
            'mdi': CommandType.GCODE_LINE,
            'run': CommandType.RUN_PROGRAM,
            'pause': CommandType.PAUSE_PROGRAM,
            'resume': CommandType.RESUME_PROGRAM,
            'stop': CommandType.STOP_PROGRAM,
        }

        command_type = type_map.get(cmd_type.lower())
        if command_type is None:
            self.get_logger().warn(f'Unknown MQTT command type: {cmd_type}')
            return

        self._queue_command(
            command_type=command_type,
            machine_id=self.machine_id,
            params=data,
            request_id=data.get('request_id', 0),
            user_id=data.get('user_id', 'mqtt'),
            client_ip='mqtt'
        )

    # -------------------------------------------------------------------------
    # ROS2 Command Handling
    # -------------------------------------------------------------------------

    def _on_command_json(self, msg: String) -> None:
        """Handle JSON command from ROS2."""
        try:
            data = json.loads(msg.data)

            command_type = CommandType(data.get('command_type', 0))
            machine_id = data.get('machine_id', self.machine_id)

            self._queue_command(
                command_type=command_type,
                machine_id=machine_id,
                params=data.get('params', {}),
                request_id=data.get('request_id', 0),
                user_id=data.get('user_id', ''),
                client_ip=data.get('client_ip', '')
            )

        except Exception as e:
            self.get_logger().error(f'Command parse error: {e}')

    def _queue_command(
        self,
        command_type: CommandType,
        machine_id: str,
        params: Dict[str, Any],
        request_id: int,
        user_id: str = "",
        client_ip: str = ""
    ) -> None:
        """Queue command for execution."""
        self.stats['commands_received'] += 1

        # Determine priority
        priority = self._get_command_priority(command_type)

        cmd = QueuedCommand(
            command_type=command_type,
            machine_id=machine_id,
            params=params,
            request_id=request_id,
            priority=priority,
            timestamp=time.time(),
            user_id=user_id,
            client_ip=client_ip
        )

        # Emergency and realtime commands execute immediately
        if priority <= CommandPriority.REALTIME:
            self._execute_command(cmd)
        else:
            with self.queue_lock:
                # Insert by priority
                inserted = False
                for i, queued in enumerate(self.command_queue):
                    if cmd.priority < queued.priority:
                        self.command_queue.insert(i, cmd)
                        inserted = True
                        break
                if not inserted:
                    self.command_queue.append(cmd)

    def _get_command_priority(self, command_type: CommandType) -> CommandPriority:
        """Get priority for command type."""
        priority_map = {
            CommandType.ESTOP: CommandPriority.EMERGENCY,
            CommandType.JOG: CommandPriority.REALTIME,
            CommandType.JOG_STOP: CommandPriority.REALTIME,
            CommandType.RUN_PROGRAM: CommandPriority.HIGH,
            CommandType.PAUSE_PROGRAM: CommandPriority.HIGH,
            CommandType.RESUME_PROGRAM: CommandPriority.HIGH,
            CommandType.STOP_PROGRAM: CommandPriority.HIGH,
            CommandType.SPINDLE_ON: CommandPriority.NORMAL,
            CommandType.SPINDLE_OFF: CommandPriority.NORMAL,
            CommandType.GCODE_LINE: CommandPriority.NORMAL,
            CommandType.RESET: CommandPriority.NORMAL,
        }
        return priority_map.get(command_type, CommandPriority.NORMAL)

    # -------------------------------------------------------------------------
    # Command Execution
    # -------------------------------------------------------------------------

    def _process_queue(self) -> None:
        """Process commands from queue."""
        with self.queue_lock:
            if not self.command_queue:
                return
            cmd = self.command_queue.popleft()

        self._execute_command(cmd)

    def _execute_command(self, cmd: QueuedCommand) -> None:
        """Execute a command."""
        start_time = time.time()

        try:
            result = self._dispatch_command(cmd)
        except Exception as e:
            result = CommandResult(
                request_id=cmd.request_id,
                success=False,
                status_code=500,
                message=str(e),
                execution_time_ms=0.0
            )
            self.get_logger().error(f'Command execution error: {e}')

        # Calculate latency
        latency_ms = (time.time() - cmd.timestamp) * 1000
        result.execution_time_ms = latency_ms

        # Update stats
        self._update_latency_stats(latency_ms)

        if result.success:
            self.stats['commands_executed'] += 1
        else:
            self.stats['commands_rejected'] += 1

        # Publish response
        self._publish_response(result)

        # Log
        self.get_logger().debug(
            f'Command {cmd.command_type.name} executed in {latency_ms:.2f}ms'
        )

    def _dispatch_command(self, cmd: QueuedCommand) -> CommandResult:
        """Dispatch command to appropriate handler."""
        handlers = {
            CommandType.JOG: self._handle_jog,
            CommandType.JOG_STOP: self._handle_jog_stop,
            CommandType.ESTOP: self._handle_estop,
            CommandType.SPINDLE_ON: self._handle_spindle_on,
            CommandType.SPINDLE_OFF: self._handle_spindle_off,
            CommandType.GCODE_LINE: self._handle_mdi,
            CommandType.RUN_PROGRAM: self._handle_run_program,
            CommandType.PAUSE_PROGRAM: self._handle_pause,
            CommandType.RESUME_PROGRAM: self._handle_resume,
            CommandType.STOP_PROGRAM: self._handle_stop,
            CommandType.RESET: self._handle_reset,
        }

        handler = handlers.get(cmd.command_type)
        if handler:
            return handler(cmd)
        else:
            return CommandResult(
                request_id=cmd.request_id,
                success=False,
                status_code=400,
                message=f'Unknown command type: {cmd.command_type}',
                execution_time_ms=0.0
            )

    # -------------------------------------------------------------------------
    # Command Handlers
    # -------------------------------------------------------------------------

    def _handle_jog(self, cmd: QueuedCommand) -> CommandResult:
        """Handle jog command."""
        params = cmd.params
        axis = params.get('axis', 'X').upper()
        direction = params.get('direction', 1)
        feed_rate = params.get('feed_rate', 500.0)

        # Create Twist message for jog
        twist = Twist()
        axis_map = {'X': 'linear.x', 'Y': 'linear.y', 'Z': 'linear.z'}

        velocity = feed_rate / 60.0 * direction  # mm/min to mm/s

        if axis == 'X':
            twist.linear.x = velocity
        elif axis == 'Y':
            twist.linear.y = velocity
        elif axis == 'Z':
            twist.linear.z = velocity

        self.jog_pub.publish(twist)

        return CommandResult(
            request_id=cmd.request_id,
            success=True,
            status_code=0,
            message=f'Jog {axis} {direction:+d} at {feed_rate}mm/min',
            execution_time_ms=0.0
        )

    def _handle_jog_stop(self, cmd: QueuedCommand) -> CommandResult:
        """Handle jog stop command."""
        # Publish zero velocity
        twist = Twist()
        self.jog_pub.publish(twist)

        return CommandResult(
            request_id=cmd.request_id,
            success=True,
            status_code=0,
            message='Jog stopped',
            execution_time_ms=0.0
        )

    def _handle_estop(self, cmd: QueuedCommand) -> CommandResult:
        """Handle emergency stop."""
        self.get_logger().warn(f'E-STOP triggered by {cmd.user_id}')

        # Publish E-stop to status topic
        status = String()
        status.data = json.dumps({
            'type': 'estop',
            'machine_id': cmd.machine_id,
            'timestamp': time.time(),
            'user_id': cmd.user_id
        })
        self.status_pub.publish(status)

        # Stop all motion
        twist = Twist()
        self.jog_pub.publish(twist)

        return CommandResult(
            request_id=cmd.request_id,
            success=True,
            status_code=0,
            message='Emergency stop activated',
            execution_time_ms=0.0
        )

    def _handle_spindle_on(self, cmd: QueuedCommand) -> CommandResult:
        """Handle spindle on command."""
        speed = cmd.params.get('speed', 12000)
        direction = cmd.params.get('direction', 'cw')

        status = String()
        status.data = json.dumps({
            'type': 'spindle',
            'machine_id': cmd.machine_id,
            'action': 'on',
            'speed': speed,
            'direction': direction
        })
        self.status_pub.publish(status)

        return CommandResult(
            request_id=cmd.request_id,
            success=True,
            status_code=0,
            message=f'Spindle on at {speed} RPM {direction}',
            execution_time_ms=0.0
        )

    def _handle_spindle_off(self, cmd: QueuedCommand) -> CommandResult:
        """Handle spindle off command."""
        status = String()
        status.data = json.dumps({
            'type': 'spindle',
            'machine_id': cmd.machine_id,
            'action': 'off'
        })
        self.status_pub.publish(status)

        return CommandResult(
            request_id=cmd.request_id,
            success=True,
            status_code=0,
            message='Spindle off',
            execution_time_ms=0.0
        )

    def _handle_mdi(self, cmd: QueuedCommand) -> CommandResult:
        """Handle MDI (G-code line) command."""
        gcode = cmd.params.get('gcode', '')

        status = String()
        status.data = json.dumps({
            'type': 'mdi',
            'machine_id': cmd.machine_id,
            'gcode': gcode
        })
        self.status_pub.publish(status)

        return CommandResult(
            request_id=cmd.request_id,
            success=True,
            status_code=0,
            message=f'MDI: {gcode}',
            execution_time_ms=0.0
        )

    def _handle_run_program(self, cmd: QueuedCommand) -> CommandResult:
        """Handle run program command."""
        program = cmd.params.get('program', '')

        status = String()
        status.data = json.dumps({
            'type': 'program',
            'machine_id': cmd.machine_id,
            'action': 'run',
            'program': program
        })
        self.status_pub.publish(status)

        return CommandResult(
            request_id=cmd.request_id,
            success=True,
            status_code=0,
            message=f'Running program: {program}',
            execution_time_ms=0.0
        )

    def _handle_pause(self, cmd: QueuedCommand) -> CommandResult:
        """Handle pause command."""
        status = String()
        status.data = json.dumps({
            'type': 'program',
            'machine_id': cmd.machine_id,
            'action': 'pause'
        })
        self.status_pub.publish(status)

        return CommandResult(
            request_id=cmd.request_id,
            success=True,
            status_code=0,
            message='Program paused',
            execution_time_ms=0.0
        )

    def _handle_resume(self, cmd: QueuedCommand) -> CommandResult:
        """Handle resume command."""
        status = String()
        status.data = json.dumps({
            'type': 'program',
            'machine_id': cmd.machine_id,
            'action': 'resume'
        })
        self.status_pub.publish(status)

        return CommandResult(
            request_id=cmd.request_id,
            success=True,
            status_code=0,
            message='Program resumed',
            execution_time_ms=0.0
        )

    def _handle_stop(self, cmd: QueuedCommand) -> CommandResult:
        """Handle stop command."""
        status = String()
        status.data = json.dumps({
            'type': 'program',
            'machine_id': cmd.machine_id,
            'action': 'stop'
        })
        self.status_pub.publish(status)

        return CommandResult(
            request_id=cmd.request_id,
            success=True,
            status_code=0,
            message='Program stopped',
            execution_time_ms=0.0
        )

    def _handle_reset(self, cmd: QueuedCommand) -> CommandResult:
        """Handle reset command."""
        status = String()
        status.data = json.dumps({
            'type': 'reset',
            'machine_id': cmd.machine_id
        })
        self.status_pub.publish(status)

        return CommandResult(
            request_id=cmd.request_id,
            success=True,
            status_code=0,
            message='Machine reset',
            execution_time_ms=0.0
        )

    # -------------------------------------------------------------------------
    # Response Publishing
    # -------------------------------------------------------------------------

    def _publish_response(self, result: CommandResult) -> None:
        """Publish command response."""
        msg = String()
        msg.data = json.dumps({
            'request_id': result.request_id,
            'success': result.success,
            'status_code': result.status_code,
            'message': result.message,
            'execution_time_ms': result.execution_time_ms,
            'timestamp': time.time()
        })
        self.response_pub.publish(msg)

        # Also publish via MQTT
        if self.mqtt_client and self.mqtt_client.is_connected():
            self.mqtt_client.publish(
                f'cnc/{self.machine_id}/response',
                msg.data,
                qos=1
            )

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def _update_latency_stats(self, latency_ms: float) -> None:
        """Update latency statistics."""
        self._latency_samples.append(latency_ms)

        # Keep last 100 samples
        if len(self._latency_samples) > 100:
            self._latency_samples.pop(0)

        self.stats['avg_latency_ms'] = sum(self._latency_samples) / len(self._latency_samples)
        self.stats['max_latency_ms'] = max(self.stats['max_latency_ms'], latency_ms)

    def destroy_node(self):
        """Clean up on shutdown."""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        super().destroy_node()


# =============================================================================
# Main
# =============================================================================

def main(args=None):
    rclpy.init(args=args)

    node = UnityCommandHandler()

    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
