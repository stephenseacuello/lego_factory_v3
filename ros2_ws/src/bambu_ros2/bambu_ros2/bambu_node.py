#!/usr/bin/env python3
"""
Bambu Lab ROS2 Node
ROS2 interface for Bambu Lab FDM printers via MQTT + FTP.
Supports A1, A1 Mini, P1S, P1P, X1C, X1E printers.

LEGO MCP Manufacturing System v7.0

Protocol:
    - Status: MQTT subscription to device/{serial}/report (port 8883 TLS)
    - Commands: MQTT publish to device/{serial}/request
    - File upload: FTPS to port 990

Requirements:
    pip install paho-mqtt
"""

import asyncio
import json
import ssl
import ftplib
import threading
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

# Lifecycle support
try:
    from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
    LIFECYCLE_AVAILABLE = True
except ImportError:
    LIFECYCLE_AVAILABLE = False

from std_msgs.msg import String, Bool

try:
    from lego_mcp_msgs.msg import EquipmentStatus, PrintJob
    from lego_mcp_msgs.action import PrintBrick
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False


class PrinterState(Enum):
    """Bambu Lab printer states (from gcode_state)."""
    OFFLINE = 'OFFLINE'
    IDLE = 'IDLE'
    PREPARE = 'PREPARE'
    RUNNING = 'RUNNING'
    PAUSE = 'PAUSE'
    FINISH = 'FINISH'
    FAILED = 'FAILED'
    UNKNOWN = 'UNKNOWN'


@dataclass
class PrintStatus:
    """Current print job status from Bambu Lab MQTT."""
    state: PrinterState = PrinterState.OFFLINE
    gcode_state: str = ''
    subtask_name: str = ''
    gcode_file: str = ''
    print_type: str = ''  # idle, file_timelapse, cloud, local
    mc_percent: int = 0  # Progress 0-100
    mc_remaining_time: int = 0  # Minutes
    layer_num: int = 0
    total_layer_num: int = 0

    # Temperatures
    nozzle_temper: float = 0.0
    nozzle_target_temper: float = 0.0
    bed_temper: float = 0.0
    bed_target_temper: float = 0.0
    chamber_temper: float = 0.0

    # Speeds
    spd_lvl: int = 1  # Speed level 1-4
    spd_mag: int = 100  # Speed percentage

    # AMS info
    ams_exist_bits: str = '0'
    ams_status: int = 0

    # Errors
    print_error: int = 0
    hw_switch_state: int = 0


class BambuMQTTClient:
    """
    MQTT client for Bambu Lab printers.
    Uses TLS on port 8883 with username 'bblp' and LAN access code.
    """

    def __init__(
        self,
        printer_ip: str,
        access_code: str,
        serial_number: str,
        on_status: Optional[Callable[[Dict], None]] = None
    ):
        self.printer_ip = printer_ip
        self.access_code = access_code
        self.serial = serial_number
        self.on_status = on_status

        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._status: Dict[str, Any] = {}
        self._seq_id = 0

    def connect(self) -> bool:
        """Establish MQTT connection to printer."""
        if not MQTT_AVAILABLE:
            return False

        try:
            # Create MQTT client with protocol v3.1.1
            self._client = mqtt.Client(
                client_id=f"lego_mcp_{self.serial[:8]}",
                protocol=mqtt.MQTTv311
            )

            # Set credentials (username is always 'bblp')
            self._client.username_pw_set('bblp', self.access_code)

            # Configure TLS (Bambu uses self-signed certs)
            self._client.tls_set(cert_reqs=ssl.CERT_NONE)
            self._client.tls_insecure_set(True)

            # Set callbacks
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            # Connect to printer (port 8883 for TLS)
            self._client.connect(self.printer_ip, 8883, keepalive=60)

            # Start background thread
            self._client.loop_start()

            return True

        except Exception as e:
            print(f"MQTT connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from printer."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        if rc == 0:
            self._connected = True
            # Subscribe to printer reports
            topic = f"device/{self.serial}/report"
            client.subscribe(topic)

            # Request full status push
            self._request_push_all()
        else:
            self._connected = False
            print(f"MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnect."""
        self._connected = False

    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages."""
        try:
            payload = json.loads(msg.payload.decode())

            # Update status from 'print' field
            if 'print' in payload:
                self._status.update(payload['print'])
                if self.on_status:
                    self.on_status(self._status)

        except json.JSONDecodeError:
            pass

    def _request_push_all(self):
        """Request printer to push all status data."""
        cmd = {
            "pushing": {
                "sequence_id": str(self._seq_id),
                "command": "pushall"
            }
        }
        self._seq_id += 1
        self._publish(cmd)

    def _publish(self, command: Dict):
        """Publish command to printer."""
        if self._client and self._connected:
            topic = f"device/{self.serial}/request"
            self._client.publish(topic, json.dumps(command))

    def start_print(
        self,
        filename: str,
        plate_number: int = 1,
        use_ams: bool = False,
        timelapse: bool = False,
        bed_leveling: bool = True,
        flow_calibration: bool = True,
        layer_inspect: bool = False
    ) -> bool:
        """
        Start a print job.
        File must already be uploaded via FTP.
        """
        cmd = {
            "print": {
                "sequence_id": str(self._seq_id),
                "command": "project_file",
                "param": f"Metadata/plate_{plate_number}.gcode",
                "subtask_name": filename,
                "url": f"ftp://{self.printer_ip}/cache/{filename}",
                "bed_type": "auto",
                "timelapse": timelapse,
                "bed_leveling": bed_leveling,
                "flow_cali": flow_calibration,
                "vibration_cali": True,
                "layer_inspect": layer_inspect,
                "use_ams": use_ams
            }
        }
        self._seq_id += 1
        self._publish(cmd)
        return True

    def pause_print(self) -> bool:
        """Pause current print."""
        cmd = {
            "print": {
                "sequence_id": str(self._seq_id),
                "command": "pause"
            }
        }
        self._seq_id += 1
        self._publish(cmd)
        return True

    def resume_print(self) -> bool:
        """Resume paused print."""
        cmd = {
            "print": {
                "sequence_id": str(self._seq_id),
                "command": "resume"
            }
        }
        self._seq_id += 1
        self._publish(cmd)
        return True

    def stop_print(self) -> bool:
        """Stop/cancel current print."""
        cmd = {
            "print": {
                "sequence_id": str(self._seq_id),
                "command": "stop"
            }
        }
        self._seq_id += 1
        self._publish(cmd)
        return True

    def set_speed_level(self, level: int) -> bool:
        """Set print speed level (1=silent, 2=standard, 3=sport, 4=ludicrous)."""
        if level not in [1, 2, 3, 4]:
            return False
        cmd = {
            "print": {
                "sequence_id": str(self._seq_id),
                "command": "print_speed",
                "param": str(level)
            }
        }
        self._seq_id += 1
        self._publish(cmd)
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get current cached status."""
        return self._status.copy()


class BambuFTPClient:
    """
    FTP client for uploading files to Bambu Lab printers.
    Uses FTPS (FTP over TLS) on port 990.
    """

    def __init__(self, printer_ip: str, access_code: str):
        self.printer_ip = printer_ip
        self.access_code = access_code

    def upload_file(
        self,
        local_path: str,
        remote_filename: Optional[str] = None
    ) -> bool:
        """
        Upload file to printer's /cache/ directory.
        Returns True on success.
        """
        local_file = Path(local_path)
        if not local_file.exists():
            return False

        remote_name = remote_filename or local_file.name

        try:
            # Create implicit TLS FTP connection
            ftp = ftplib.FTP_TLS()
            ftp.connect(self.printer_ip, 990)
            ftp.login('bblp', self.access_code)
            ftp.prot_p()  # Enable data channel encryption

            # Upload to /cache/ directory
            with open(local_path, 'rb') as f:
                ftp.storbinary(f'STOR /cache/{remote_name}', f)

            ftp.quit()
            return True

        except Exception as e:
            print(f"FTP upload error: {e}")
            return False

    def list_files(self, directory: str = '/') -> list:
        """List files in printer directory."""
        try:
            ftp = ftplib.FTP_TLS()
            ftp.connect(self.printer_ip, 990)
            ftp.login('bblp', self.access_code)
            ftp.prot_p()

            files = ftp.nlst(directory)
            ftp.quit()
            return files

        except Exception as e:
            print(f"FTP list error: {e}")
            return []


class BambuNode(Node):
    """
    ROS2 node for Bambu Lab FDM printers.
    Provides action server for print jobs and status publishing.
    """

    def __init__(self):
        super().__init__('bambu_node')

        # Declare parameters
        self.declare_parameter('printer_ip', '192.168.1.100')
        self.declare_parameter('access_code', '')  # 8-digit LAN access code
        self.declare_parameter('serial_number', '')  # Printer serial
        self.declare_parameter('status_rate_hz', 1.0)
        self.declare_parameter('simulate', False)

        # Get parameters
        self.printer_ip = self.get_parameter('printer_ip').value
        self.access_code = self.get_parameter('access_code').value
        self.serial_number = self.get_parameter('serial_number').value
        self.status_rate = self.get_parameter('status_rate_hz').value
        self.simulate = self.get_parameter('simulate').value

        # Clients
        self._mqtt_client: Optional[BambuMQTTClient] = None
        self._ftp_client: Optional[BambuFTPClient] = None
        self._status = PrintStatus()
        self._lock = threading.Lock()

        # Callback group
        self._cb_group = ReentrantCallbackGroup()

        # Publishers
        self.status_pub = self.create_publisher(
            PrintJob if MSGS_AVAILABLE else String,
            '~/status',
            10
        )

        self.state_pub = self.create_publisher(
            String,
            '~/state',
            10
        )

        # Subscribers
        self.estop_sub = self.create_subscription(
            Bool,
            '/safety/estop_status',
            self._on_estop,
            10
        )

        # Action server
        if MSGS_AVAILABLE:
            self._action_server = ActionServer(
                self,
                PrintBrick,
                '~/print',
                execute_callback=self._execute_callback,
                goal_callback=self._goal_callback,
                cancel_callback=self._cancel_callback,
                callback_group=self._cb_group
            )

        # Status publish timer
        self._status_timer = self.create_timer(
            1.0 / self.status_rate,
            self._publish_status,
            callback_group=self._cb_group
        )

        # Connect
        if not self.simulate:
            self._connect()
        else:
            self.get_logger().info("Running in simulation mode")

        self.get_logger().info(
            f"Bambu Lab node initialized for {self.printer_ip}"
        )

    def _connect(self):
        """Connect to printer via MQTT."""
        if not self.access_code:
            self.get_logger().warn(
                "No access code configured - set 'access_code' parameter"
            )
            return

        if not self.serial_number:
            self.get_logger().warn(
                "No serial number configured - set 'serial_number' parameter"
            )
            return

        self._mqtt_client = BambuMQTTClient(
            printer_ip=self.printer_ip,
            access_code=self.access_code,
            serial_number=self.serial_number,
            on_status=self._on_mqtt_status
        )

        self._ftp_client = BambuFTPClient(
            printer_ip=self.printer_ip,
            access_code=self.access_code
        )

        if self._mqtt_client.connect():
            self.get_logger().info(
                f"Connected to Bambu Lab printer at {self.printer_ip}"
            )
        else:
            self.get_logger().error("Failed to connect via MQTT")

    def _on_mqtt_status(self, status: Dict):
        """Handle MQTT status updates."""
        with self._lock:
            self._parse_status(status)

    def _parse_status(self, status: Dict):
        """Parse Bambu Lab MQTT status."""
        # State
        gcode_state = status.get('gcode_state', 'UNKNOWN').upper()
        state_map = {
            'IDLE': PrinterState.IDLE,
            'PREPARE': PrinterState.PREPARE,
            'RUNNING': PrinterState.RUNNING,
            'PAUSE': PrinterState.PAUSE,
            'FINISH': PrinterState.FINISH,
            'FAILED': PrinterState.FAILED,
        }
        self._status.state = state_map.get(gcode_state, PrinterState.UNKNOWN)
        self._status.gcode_state = gcode_state

        # Progress
        self._status.mc_percent = status.get('mc_percent', 0)
        self._status.mc_remaining_time = status.get('mc_remaining_time', 0)
        self._status.layer_num = status.get('layer_num', 0)
        self._status.total_layer_num = status.get('total_layer_num', 0)

        # Job info
        self._status.subtask_name = status.get('subtask_name', '')
        self._status.gcode_file = status.get('gcode_file', '')
        self._status.print_type = status.get('print_type', '')

        # Temperatures
        self._status.nozzle_temper = status.get('nozzle_temper', 0.0)
        self._status.nozzle_target_temper = status.get('nozzle_target_temper', 0.0)
        self._status.bed_temper = status.get('bed_temper', 0.0)
        self._status.bed_target_temper = status.get('bed_target_temper', 0.0)
        self._status.chamber_temper = status.get('chamber_temper', 0.0)

        # Speed
        self._status.spd_lvl = status.get('spd_lvl', 1)
        self._status.spd_mag = status.get('spd_mag', 100)

        # AMS
        self._status.ams_exist_bits = status.get('ams_exist_bits', '0')
        self._status.ams_status = status.get('ams_status', 0)

        # Errors
        self._status.print_error = status.get('print_error', 0)
        self._status.hw_switch_state = status.get('hw_switch_state', 0)

    def _publish_status(self):
        """Publish current status to ROS2 topics."""
        with self._lock:
            # State string
            state_msg = String()
            state_msg.data = self._status.state.value
            self.state_pub.publish(state_msg)

            # Full status message
            if MSGS_AVAILABLE:
                status_msg = PrintJob()
                status_msg.header.stamp = self.get_clock().now().to_msg()
                status_msg.job_id = self._status.subtask_name
                status_msg.printer_id = self.get_name()
                status_msg.printer_type = 'fdm'

                state_to_num = {
                    PrinterState.IDLE: 0,
                    PrinterState.PREPARE: 1,
                    PrinterState.RUNNING: 2,
                    PrinterState.PAUSE: 3,
                    PrinterState.FINISH: 4,
                    PrinterState.FAILED: 5,
                    PrinterState.OFFLINE: 6,
                    PrinterState.UNKNOWN: 7,
                }
                status_msg.status = state_to_num.get(self._status.state, 7)
                status_msg.progress_percent = float(self._status.mc_percent)
                status_msg.current_layer = self._status.layer_num
                status_msg.total_layers = self._status.total_layer_num
                status_msg.estimated_remaining_sec = float(
                    self._status.mc_remaining_time * 60
                )

                self.status_pub.publish(status_msg)

    def _on_estop(self, msg: Bool):
        """Handle emergency stop."""
        if msg.data:
            self.get_logger().warn("E-STOP activated - pausing print!")
            if self._mqtt_client and self._mqtt_client.is_connected:
                self._mqtt_client.pause_print()

    def _goal_callback(self, goal_request):
        """Handle action goal request."""
        self.get_logger().info("Received print goal request")
        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle):
        """Handle action cancel request."""
        self.get_logger().info("Received cancel request")
        return CancelResponse.ACCEPT

    async def _execute_callback(self, goal_handle):
        """Execute print job."""
        self.get_logger().info("Starting print job execution")

        request = goal_handle.request
        source_file = getattr(request, 'source_file', '')
        sliced_file = getattr(request, 'sliced_file', '')

        # Use sliced file (gcode/3mf) preferentially
        file_to_print = sliced_file or source_file

        feedback_msg = PrintBrick.Feedback() if MSGS_AVAILABLE else None
        result = PrintBrick.Result() if MSGS_AVAILABLE else None

        try:
            if self.simulate:
                # Simulated print
                total_steps = 100
                for i in range(total_steps):
                    if goal_handle.is_cancel_requested:
                        goal_handle.canceled()
                        if result:
                            result.success = False
                            result.message = "Cancelled"
                        return result

                    progress = (i + 1) / total_steps * 100
                    with self._lock:
                        self._status.mc_percent = int(progress)
                        self._status.state = PrinterState.RUNNING
                        self._status.layer_num = i + 1
                        self._status.total_layer_num = total_steps

                    if feedback_msg:
                        feedback_msg.phase = 3  # Printing
                        feedback_msg.phase_name = "Printing"
                        feedback_msg.progress_percent = progress
                        feedback_msg.current_layer = i + 1
                        feedback_msg.total_layers = total_steps
                        goal_handle.publish_feedback(feedback_msg)

                    await asyncio.sleep(0.05)  # Fast simulation
            else:
                # Real print
                if not self._mqtt_client or not self._mqtt_client.is_connected:
                    raise RuntimeError("Not connected to printer")

                if not file_to_print:
                    raise ValueError("No file provided for printing")

                # Phase 1: Upload file via FTP
                if feedback_msg:
                    feedback_msg.phase = 1
                    feedback_msg.phase_name = "Uploading"
                    feedback_msg.progress_percent = 0.0
                    goal_handle.publish_feedback(feedback_msg)

                filename = Path(file_to_print).name
                self.get_logger().info(f"Uploading {filename} via FTP...")

                if not self._ftp_client.upload_file(file_to_print, filename):
                    raise RuntimeError(f"Failed to upload {filename}")

                self.get_logger().info(f"Upload complete: {filename}")

                # Phase 2: Start print
                if feedback_msg:
                    feedback_msg.phase = 2
                    feedback_msg.phase_name = "Starting"
                    feedback_msg.progress_percent = 0.0
                    goal_handle.publish_feedback(feedback_msg)

                self._mqtt_client.start_print(filename)
                self.get_logger().info(f"Print started: {filename}")

                # Phase 3: Monitor progress
                while True:
                    if goal_handle.is_cancel_requested:
                        self._mqtt_client.stop_print()
                        goal_handle.canceled()
                        if result:
                            result.success = False
                            result.message = "Cancelled by user"
                        return result

                    with self._lock:
                        state = self._status.state
                        progress = self._status.mc_percent
                        layer = self._status.layer_num
                        total_layers = self._status.total_layer_num
                        remaining = self._status.mc_remaining_time

                    # Check completion
                    if state == PrinterState.FINISH:
                        break
                    elif state == PrinterState.FAILED:
                        raise RuntimeError(
                            f"Print failed (error code: {self._status.print_error})"
                        )

                    # Publish feedback
                    if feedback_msg:
                        feedback_msg.phase = 3
                        feedback_msg.phase_name = "Printing"
                        feedback_msg.progress_percent = float(progress)
                        feedback_msg.current_layer = layer
                        feedback_msg.total_layers = total_layers
                        feedback_msg.remaining_sec = float(remaining * 60)
                        goal_handle.publish_feedback(feedback_msg)

                    await asyncio.sleep(5)  # Poll every 5 seconds

            # Success
            goal_handle.succeed()
            with self._lock:
                self._status.state = PrinterState.FINISH

            if result:
                result.success = True
                result.message = "Print completed successfully"
                result.layers_printed = self._status.total_layer_num

            self.get_logger().info("Print job completed successfully")
            return result

        except Exception as e:
            self.get_logger().error(f"Print failed: {e}")
            goal_handle.abort()

            with self._lock:
                self._status.state = PrinterState.FAILED

            if result:
                result.success = False
                result.message = str(e)

            return result

    def destroy_node(self):
        """Cleanup on shutdown."""
        if self._mqtt_client:
            self._mqtt_client.disconnect()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    node = BambuNode()

    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


# ============================================================================
# LIFECYCLE NODE IMPLEMENTATION (Industry 4.0/5.0 - ISA-95 Compliant)
# ============================================================================

class BambuLifecycleNode:
    """
    ROS2 Lifecycle wrapper for Bambu Lab FDM printer node.

    Implements lifecycle states for graceful startup/shutdown:
    - unconfigured -> configuring -> inactive
    - inactive -> activating -> active
    - active -> deactivating -> inactive
    - inactive -> cleaningup -> unconfigured

    Industry 4.0/5.0 Architecture - ISA-95 Level 0 (Field Layer)
    """

    def __init__(self):
        self._node: Optional['LifecycleNode'] = None
        self._mqtt_client: Optional[BambuMQTTClient] = None
        self._ftp_client: Optional[BambuFTPClient] = None
        self._status = PrintStatus()
        self._lock = threading.Lock()
        self._cb_group = None
        self._status_timer = None
        self._action_server = None

        # Parameters (loaded in configure)
        self._printer_ip = ''
        self._access_code = ''
        self._serial_number = ''
        self._status_rate = 1.0
        self._simulate = False

    def create_node(self) -> 'LifecycleNode':
        """Create and return the lifecycle node instance."""
        if not LIFECYCLE_AVAILABLE:
            raise RuntimeError("rclpy.lifecycle not available")

        outer = self

        class _BambuLifecycle(LifecycleNode):
            """Inner lifecycle node class."""

            def __init__(self):
                super().__init__('bambu_node')

                # Declare parameters
                self.declare_parameter('printer_ip', '192.168.1.100')
                self.declare_parameter('access_code', '')
                self.declare_parameter('serial_number', '')
                self.declare_parameter('status_rate_hz', 1.0)
                self.declare_parameter('simulate', False)

                self.get_logger().info(
                    "BambuLifecycleNode created (unconfigured)"
                )

            def on_configure(self, state: State) -> TransitionCallbackReturn:
                """Configure: Initialize parameters and create clients."""
                self.get_logger().info(f"Configuring from {state.label}...")

                try:
                    # Get parameters
                    outer._printer_ip = self.get_parameter('printer_ip').value
                    outer._access_code = self.get_parameter('access_code').value
                    outer._serial_number = self.get_parameter('serial_number').value
                    outer._status_rate = self.get_parameter('status_rate_hz').value
                    outer._simulate = self.get_parameter('simulate').value

                    # Callback group
                    outer._cb_group = ReentrantCallbackGroup()

                    # Create clients (but don't connect yet)
                    if not outer._simulate:
                        if outer._access_code and outer._serial_number:
                            outer._mqtt_client = BambuMQTTClient(
                                printer_ip=outer._printer_ip,
                                access_code=outer._access_code,
                                serial_number=outer._serial_number,
                                on_status=outer._on_mqtt_status
                            )
                            outer._ftp_client = BambuFTPClient(
                                printer_ip=outer._printer_ip,
                                access_code=outer._access_code
                            )
                        else:
                            self.get_logger().warn(
                                "Missing access_code or serial_number - "
                                "configure parameters for real printer"
                            )

                    self.get_logger().info("Configuration complete")
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    self.get_logger().error(f"Configuration failed: {e}")
                    return TransitionCallbackReturn.FAILURE

            def on_activate(self, state: State) -> TransitionCallbackReturn:
                """Activate: Connect to printer and start publishing."""
                self.get_logger().info(f"Activating from {state.label}...")

                try:
                    # Connect to printer via MQTT
                    if outer._mqtt_client and not outer._simulate:
                        if outer._mqtt_client.connect():
                            self.get_logger().info(
                                f"Connected to Bambu at {outer._printer_ip}"
                            )
                        else:
                            self.get_logger().warn(
                                "MQTT connection failed - continuing in degraded mode"
                            )

                    # Create publishers
                    outer._status_pub = self.create_publisher(
                        PrintJob if MSGS_AVAILABLE else String,
                        '~/status',
                        10
                    )

                    outer._state_pub = self.create_publisher(
                        String,
                        '~/state',
                        10
                    )

                    # Create subscribers
                    outer._estop_sub = self.create_subscription(
                        Bool,
                        '/safety/estop_status',
                        outer._on_estop,
                        10
                    )

                    # Create action server
                    if MSGS_AVAILABLE:
                        outer._action_server = ActionServer(
                            self,
                            PrintBrick,
                            '~/print',
                            execute_callback=outer._execute_callback,
                            goal_callback=outer._goal_callback,
                            cancel_callback=outer._cancel_callback,
                            callback_group=outer._cb_group
                        )

                    # Start status timer
                    outer._status_timer = self.create_timer(
                        1.0 / outer._status_rate,
                        outer._publish_status,
                        callback_group=outer._cb_group
                    )

                    self.get_logger().info("Activation complete - node active")
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    self.get_logger().error(f"Activation failed: {e}")
                    return TransitionCallbackReturn.FAILURE

            def on_deactivate(self, state: State) -> TransitionCallbackReturn:
                """Deactivate: Stop publishing but keep connection."""
                self.get_logger().info(f"Deactivating from {state.label}...")

                try:
                    # Cancel status timer
                    if outer._status_timer:
                        outer._status_timer.cancel()
                        outer._status_timer = None

                    # Pause any active print for safety
                    if outer._mqtt_client and outer._mqtt_client.is_connected:
                        if outer._status.state == PrinterState.RUNNING:
                            outer._mqtt_client.pause_print()
                            self.get_logger().info("Paused active print")

                    self.get_logger().info("Deactivation complete")
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    self.get_logger().error(f"Deactivation failed: {e}")
                    return TransitionCallbackReturn.FAILURE

            def on_cleanup(self, state: State) -> TransitionCallbackReturn:
                """Cleanup: Disconnect from printer."""
                self.get_logger().info(f"Cleaning up from {state.label}...")

                try:
                    # Disconnect MQTT
                    if outer._mqtt_client:
                        outer._mqtt_client.disconnect()
                        outer._mqtt_client = None

                    outer._ftp_client = None
                    outer._status = PrintStatus()

                    self.get_logger().info("Cleanup complete")
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    self.get_logger().error(f"Cleanup failed: {e}")
                    return TransitionCallbackReturn.FAILURE

            def on_shutdown(self, state: State) -> TransitionCallbackReturn:
                """Shutdown: Final cleanup before destruction."""
                self.get_logger().info(f"Shutting down from {state.label}...")

                try:
                    if outer._mqtt_client:
                        outer._mqtt_client.disconnect()
                        outer._mqtt_client = None

                    self.get_logger().info("Shutdown complete")
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    self.get_logger().error(f"Shutdown error: {e}")
                    return TransitionCallbackReturn.SUCCESS

            def on_error(self, state: State) -> TransitionCallbackReturn:
                """Error handling: Pause print and attempt recovery."""
                self.get_logger().error(f"Error occurred in {state.label}")

                try:
                    # Pause any active print for safety
                    if outer._mqtt_client and outer._mqtt_client.is_connected:
                        outer._mqtt_client.pause_print()

                    with outer._lock:
                        outer._status.state = PrinterState.FAILED

                    self.get_logger().info("Error handled")
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    self.get_logger().error(f"Error handling failed: {e}")
                    return TransitionCallbackReturn.FAILURE

        self._node = _BambuLifecycle()
        return self._node

    def _on_mqtt_status(self, status: Dict):
        """Handle MQTT status updates."""
        with self._lock:
            self._parse_status(status)

    def _parse_status(self, status: Dict):
        """Parse Bambu Lab MQTT status."""
        gcode_state = status.get('gcode_state', 'UNKNOWN').upper()
        state_map = {
            'IDLE': PrinterState.IDLE,
            'PREPARE': PrinterState.PREPARE,
            'RUNNING': PrinterState.RUNNING,
            'PAUSE': PrinterState.PAUSE,
            'FINISH': PrinterState.FINISH,
            'FAILED': PrinterState.FAILED,
        }
        self._status.state = state_map.get(gcode_state, PrinterState.UNKNOWN)
        self._status.gcode_state = gcode_state
        self._status.mc_percent = status.get('mc_percent', 0)
        self._status.mc_remaining_time = status.get('mc_remaining_time', 0)
        self._status.layer_num = status.get('layer_num', 0)
        self._status.total_layer_num = status.get('total_layer_num', 0)
        self._status.subtask_name = status.get('subtask_name', '')
        self._status.nozzle_temper = status.get('nozzle_temper', 0.0)
        self._status.bed_temper = status.get('bed_temper', 0.0)

    def _publish_status(self):
        """Publish current status to ROS2 topics."""
        if not self._node:
            return

        with self._lock:
            state_msg = String()
            state_msg.data = self._status.state.value
            self._state_pub.publish(state_msg)

            if MSGS_AVAILABLE:
                status_msg = PrintJob()
                status_msg.header.stamp = self._node.get_clock().now().to_msg()
                status_msg.job_id = self._status.subtask_name
                status_msg.printer_id = self._node.get_name()
                status_msg.printer_type = 'fdm'
                status_msg.progress_percent = float(self._status.mc_percent)
                status_msg.current_layer = self._status.layer_num
                status_msg.total_layers = self._status.total_layer_num
                self._status_pub.publish(status_msg)

    def _on_estop(self, msg: Bool):
        """Handle emergency stop."""
        if msg.data:
            if self._node:
                self._node.get_logger().warn("E-STOP activated!")
            if self._mqtt_client and self._mqtt_client.is_connected:
                self._mqtt_client.pause_print()

    def _goal_callback(self, goal_request):
        """Handle action goal request."""
        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle):
        """Handle action cancel request."""
        return CancelResponse.ACCEPT

    async def _execute_callback(self, goal_handle):
        """Execute print job (simplified for lifecycle node)."""
        if self._node:
            self._node.get_logger().info("Starting print job (lifecycle)")

        request = goal_handle.request
        sliced_file = getattr(request, 'sliced_file', '')
        source_file = getattr(request, 'source_file', '')
        file_to_print = sliced_file or source_file

        feedback_msg = PrintBrick.Feedback() if MSGS_AVAILABLE else None
        result = PrintBrick.Result() if MSGS_AVAILABLE else None

        try:
            if self._simulate:
                # Simulated print
                for i in range(100):
                    if goal_handle.is_cancel_requested:
                        goal_handle.canceled()
                        if result:
                            result.success = False
                        return result

                    with self._lock:
                        self._status.mc_percent = i + 1
                        self._status.state = PrinterState.RUNNING

                    if feedback_msg:
                        feedback_msg.progress_percent = float(i + 1)
                        goal_handle.publish_feedback(feedback_msg)

                    await asyncio.sleep(0.05)
            else:
                # Real print - upload and start
                if not self._mqtt_client or not self._mqtt_client.is_connected:
                    raise RuntimeError("Not connected to printer")

                filename = Path(file_to_print).name
                if self._ftp_client:
                    self._ftp_client.upload_file(file_to_print, filename)
                self._mqtt_client.start_print(filename)

                # Monitor until complete
                while True:
                    if goal_handle.is_cancel_requested:
                        self._mqtt_client.stop_print()
                        goal_handle.canceled()
                        if result:
                            result.success = False
                        return result

                    with self._lock:
                        state = self._status.state

                    if state == PrinterState.FINISH:
                        break
                    elif state == PrinterState.FAILED:
                        raise RuntimeError("Print failed")

                    await asyncio.sleep(5)

            goal_handle.succeed()
            if result:
                result.success = True
                result.message = "Print completed"
            return result

        except Exception as e:
            if self._node:
                self._node.get_logger().error(f"Print failed: {e}")
            goal_handle.abort()
            if result:
                result.success = False
                result.message = str(e)
            return result


def main_lifecycle(args=None):
    """
    Main entry point for lifecycle node.

    Usage:
        ros2 run bambu_ros2 bambu_node_lifecycle
    """
    rclpy.init(args=args)

    wrapper = BambuLifecycleNode()
    node = wrapper.create_node()

    executor = MultiThreadedExecutor()
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
