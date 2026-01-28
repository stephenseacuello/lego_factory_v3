#!/usr/bin/env python3
"""
Formlabs ROS2 Node
ROS2 interface for Formlabs SLA printers via PreFormServer Local API.
Supports Form 3, Form 3+, Form 3L, Form 3BL printers.

LEGO MCP Manufacturing System v7.0

PreFormServer Local API Documentation:
https://support.formlabs.com/s/article/PreFormServer-Local-API

Requirements:
    pip install aiohttp
"""

import asyncio
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

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
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class PrinterState(Enum):
    """Formlabs printer states."""
    OFFLINE = 'offline'
    IDLE = 'idle'
    PREPARING = 'preparing'
    PRINTING = 'printing'
    PAUSED = 'paused'
    FINISHING = 'finishing'
    COMPLETED = 'completed'
    ERROR = 'error'
    MAINTENANCE = 'maintenance'


@dataclass
class PrintStatus:
    """Current print job status."""
    state: PrinterState = PrinterState.OFFLINE
    job_id: str = ''
    job_name: str = ''
    progress_percent: float = 0.0
    current_layer: int = 0
    total_layers: int = 0
    elapsed_sec: float = 0.0
    remaining_sec: float = 0.0
    resin_ml_used: float = 0.0
    resin_ml_total: float = 0.0


class PreFormClient:
    """
    Client for PreFormServer Local API.
    Provides async interface for printer control.
    """

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 44388
    ):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self._session: Optional['aiohttp.ClientSession'] = None

    async def connect(self) -> bool:
        """Establish connection to PreFormServer."""
        if not AIOHTTP_AVAILABLE:
            return False

        try:
            self._session = aiohttp.ClientSession()
            # Test connection
            async with self._session.get(f"{self.base_url}/discover/") as resp:
                if resp.status == 200:
                    return True
            return False
        except Exception:
            return False

    async def disconnect(self):
        """Close connection."""
        if self._session:
            await self._session.close()
            self._session = None

    @property
    def is_connected(self) -> bool:
        return self._session is not None and not self._session.closed

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
        files: Dict = None
    ) -> Dict:
        """Make API request."""
        if not self.is_connected:
            raise RuntimeError("Not connected to PreFormServer")

        url = f"{self.base_url}{endpoint}"

        try:
            if method == 'GET':
                async with self._session.get(url) as resp:
                    return await resp.json()
            elif method == 'POST':
                if files:
                    form_data = aiohttp.FormData()
                    for key, value in files.items():
                        form_data.add_field(key, value)
                    async with self._session.post(url, data=form_data) as resp:
                        return await resp.json()
                else:
                    async with self._session.post(url, json=data) as resp:
                        return await resp.json()
        except aiohttp.ClientError as e:
            raise RuntimeError(f"API request failed: {e}")

    async def discover_printers(self) -> List[Dict]:
        """Discover available printers."""
        result = await self._request('GET', '/discover/')
        return result.get('printers', [])

    async def get_printer_status(self, printer_id: str = None) -> Dict:
        """Get printer status."""
        endpoint = f'/printer/{printer_id}/status/' if printer_id else '/printer/status/'
        return await self._request('GET', endpoint)

    async def upload_form_file(self, file_path: str) -> str:
        """
        Upload .form file to PreFormServer.
        Returns scene ID.
        """
        with open(file_path, 'rb') as f:
            result = await self._request(
                'POST',
                '/scene/',
                files={'file': f}
            )
        return result.get('id', '')

    async def import_model(
        self,
        file_path: str,
        auto_orient: bool = True,
        auto_support: bool = True,
        auto_layout: bool = True
    ) -> str:
        """
        Import 3D model (STL, OBJ, etc.) and prepare for printing.
        Returns scene ID.
        """
        with open(file_path, 'rb') as f:
            result = await self._request(
                'POST',
                '/scene/import-model/',
                files={'file': f}
            )

        scene_id = result.get('id', '')

        # Auto-orient if requested
        if auto_orient and scene_id:
            await self._request(
                'POST',
                f'/scene/{scene_id}/auto-orient/'
            )

        # Auto-support if requested
        if auto_support and scene_id:
            await self._request(
                'POST',
                f'/scene/{scene_id}/auto-support/'
            )

        # Auto-layout if requested
        if auto_layout and scene_id:
            await self._request(
                'POST',
                f'/scene/{scene_id}/auto-layout/'
            )

        return scene_id

    async def start_print(
        self,
        scene_id: str,
        printer_id: str = None,
        job_name: str = None
    ) -> str:
        """
        Start print job.
        Returns job ID.
        """
        data = {'job_name': job_name} if job_name else {}
        endpoint = f'/scene/{scene_id}/print/'
        if printer_id:
            endpoint += f'?printer={printer_id}'

        result = await self._request('POST', endpoint, data=data)
        return result.get('job_id', '')

    async def get_print_status(self, job_id: str = None) -> Dict:
        """Get current print job status."""
        endpoint = f'/print/{job_id}/status/' if job_id else '/print/status/'
        return await self._request('GET', endpoint)

    async def pause_print(self, job_id: str = None):
        """Pause print job."""
        endpoint = f'/print/{job_id}/pause/' if job_id else '/print/pause/'
        await self._request('POST', endpoint)

    async def resume_print(self, job_id: str = None):
        """Resume paused print job."""
        endpoint = f'/print/{job_id}/resume/' if job_id else '/print/resume/'
        await self._request('POST', endpoint)

    async def cancel_print(self, job_id: str = None):
        """Cancel print job."""
        endpoint = f'/print/{job_id}/cancel/' if job_id else '/print/cancel/'
        await self._request('POST', endpoint)


class FormlabsNode(Node):
    """
    ROS2 node for Formlabs SLA printers.
    Provides action server for print jobs and status publishing.
    """

    def __init__(self):
        super().__init__('formlabs_node')

        # Declare parameters
        self.declare_parameter('api_host', 'localhost')
        self.declare_parameter('api_port', 44388)
        self.declare_parameter('printer_serial', '')
        self.declare_parameter('status_rate_hz', 0.5)
        self.declare_parameter('simulate', False)

        # Get parameters
        self.api_host = self.get_parameter('api_host').value
        self.api_port = self.get_parameter('api_port').value
        self.printer_serial = self.get_parameter('printer_serial').value
        self.status_rate = self.get_parameter('status_rate_hz').value
        self.simulate = self.get_parameter('simulate').value

        # Client
        self._client: Optional[PreFormClient] = None
        self._status = PrintStatus()
        self._current_job_id: Optional[str] = None

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

        # Status timer
        self._status_timer = self.create_timer(
            1.0 / self.status_rate,
            self._poll_status,
            callback_group=self._cb_group
        )

        # Connect
        if not self.simulate:
            asyncio.get_event_loop().run_until_complete(self._connect())
        else:
            self.get_logger().info("Running in simulation mode")

        self.get_logger().info(f"Formlabs node initialized")

    async def _connect(self):
        """Connect to PreFormServer."""
        self._client = PreFormClient(self.api_host, self.api_port)
        try:
            connected = await self._client.connect()
            if connected:
                self.get_logger().info(f"Connected to PreFormServer at {self.api_host}:{self.api_port}")

                # Discover printers
                printers = await self._client.discover_printers()
                for p in printers:
                    self.get_logger().info(f"Found printer: {p.get('name', 'Unknown')} ({p.get('serial', 'N/A')})")
            else:
                self.get_logger().warn("Failed to connect to PreFormServer")
        except Exception as e:
            self.get_logger().error(f"Connection error: {e}")

    def _poll_status(self):
        """Poll printer for status."""
        if self.simulate:
            self._publish_simulated_status()
            return

        asyncio.get_event_loop().run_until_complete(self._async_poll_status())

    async def _async_poll_status(self):
        """Async status polling."""
        if not self._client or not self._client.is_connected:
            return

        try:
            # Get printer status
            printer_status = await self._client.get_printer_status(self.printer_serial)
            self._parse_printer_status(printer_status)

            # Get print status if printing
            if self._current_job_id:
                print_status = await self._client.get_print_status(self._current_job_id)
                self._parse_print_status(print_status)

            self._publish_status()
        except Exception as e:
            self.get_logger().warn(f"Status poll failed: {e}")

    def _parse_printer_status(self, status: Dict):
        """Parse printer status response."""
        state_str = status.get('state', 'offline').lower()
        state_map = {
            'offline': PrinterState.OFFLINE,
            'idle': PrinterState.IDLE,
            'preparing': PrinterState.PREPARING,
            'printing': PrinterState.PRINTING,
            'paused': PrinterState.PAUSED,
            'finishing': PrinterState.FINISHING,
            'completed': PrinterState.COMPLETED,
            'error': PrinterState.ERROR,
        }
        self._status.state = state_map.get(state_str, PrinterState.OFFLINE)

    def _parse_print_status(self, status: Dict):
        """Parse print job status response."""
        self._status.job_id = status.get('job_id', '')
        self._status.job_name = status.get('job_name', '')
        self._status.progress_percent = status.get('progress', 0.0) * 100
        self._status.current_layer = status.get('current_layer', 0)
        self._status.total_layers = status.get('total_layers', 0)
        self._status.elapsed_sec = status.get('elapsed_seconds', 0.0)
        self._status.remaining_sec = status.get('remaining_seconds', 0.0)
        self._status.resin_ml_used = status.get('resin_used_ml', 0.0)
        self._status.resin_ml_total = status.get('resin_total_ml', 0.0)

    def _publish_status(self):
        """Publish current status."""
        # State
        state_msg = String()
        state_msg.data = self._status.state.value
        self.state_pub.publish(state_msg)

        # Full status
        if MSGS_AVAILABLE:
            status_msg = PrintJob()
            status_msg.header.stamp = self.get_clock().now().to_msg()
            status_msg.job_id = self._status.job_id
            status_msg.printer_id = self.get_name()
            status_msg.printer_type = 'sla'

            state_to_num = {
                PrinterState.IDLE: 0,
                PrinterState.PREPARING: 1,
                PrinterState.PRINTING: 2,
                PrinterState.PAUSED: 3,
                PrinterState.COMPLETED: 4,
                PrinterState.ERROR: 5,
            }
            status_msg.status = state_to_num.get(self._status.state, 0)
            status_msg.progress_percent = self._status.progress_percent
            status_msg.current_layer = self._status.current_layer
            status_msg.total_layers = self._status.total_layers
            status_msg.elapsed_time_sec = self._status.elapsed_sec
            status_msg.estimated_remaining_sec = self._status.remaining_sec

            self.status_pub.publish(status_msg)

    def _publish_simulated_status(self):
        """Publish simulated status."""
        state_msg = String()
        state_msg.data = self._status.state.value
        self.state_pub.publish(state_msg)

    def _on_estop(self, msg: Bool):
        """Handle emergency stop."""
        if msg.data:
            self.get_logger().warn("E-STOP activated!")
            asyncio.get_event_loop().run_until_complete(self._pause_print())

    async def _pause_print(self):
        """Pause current print."""
        if self._client and self._current_job_id:
            await self._client.pause_print(self._current_job_id)

    def _goal_callback(self, goal_request):
        """Handle action goal."""
        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle):
        """Handle action cancel."""
        return CancelResponse.ACCEPT

    async def _execute_callback(self, goal_handle):
        """Execute print job."""
        self.get_logger().info("Starting print job")

        request = goal_handle.request
        source_file = request.source_file if hasattr(request, 'source_file') else ''
        sliced_file = request.sliced_file if hasattr(request, 'sliced_file') else ''

        feedback_msg = PrintBrick.Feedback() if MSGS_AVAILABLE else None
        result = PrintBrick.Result() if MSGS_AVAILABLE else None

        try:
            if self.simulate:
                # Simulated print
                total_time = 60  # 60 second simulated print
                for i in range(total_time):
                    if goal_handle.is_cancel_requested:
                        goal_handle.canceled()
                        if result:
                            result.success = False
                            result.message = "Cancelled"
                        return result

                    progress = (i + 1) / total_time * 100
                    self._status.progress_percent = progress
                    self._status.state = PrinterState.PRINTING

                    if feedback_msg:
                        feedback_msg.phase = 3  # Printing
                        feedback_msg.phase_name = "Printing"
                        feedback_msg.progress_percent = progress
                        feedback_msg.current_layer = int(progress)
                        feedback_msg.total_layers = 100
                        feedback_msg.elapsed_sec = float(i)
                        feedback_msg.remaining_sec = float(total_time - i)
                        goal_handle.publish_feedback(feedback_msg)

                    await asyncio.sleep(0.1)  # Speed up simulation

            else:
                # Real print
                if not self._client or not self._client.is_connected:
                    raise RuntimeError("Not connected to PreFormServer")

                # Upload/import file
                if feedback_msg:
                    feedback_msg.phase = 1  # Slicing/preparing
                    feedback_msg.phase_name = "Preparing"
                    goal_handle.publish_feedback(feedback_msg)

                if sliced_file and sliced_file.endswith('.form'):
                    scene_id = await self._client.upload_form_file(sliced_file)
                elif source_file:
                    scene_id = await self._client.import_model(source_file)
                else:
                    raise ValueError("No source or sliced file provided")

                if not scene_id:
                    raise RuntimeError("Failed to upload file")

                # Start print
                self._current_job_id = await self._client.start_print(
                    scene_id,
                    self.printer_serial
                )

                if not self._current_job_id:
                    raise RuntimeError("Failed to start print")

                self.get_logger().info(f"Print started: {self._current_job_id}")

                # Monitor print progress
                while True:
                    if goal_handle.is_cancel_requested:
                        await self._client.cancel_print(self._current_job_id)
                        goal_handle.canceled()
                        if result:
                            result.success = False
                            result.message = "Cancelled"
                        self._current_job_id = None
                        return result

                    # Get status
                    status = await self._client.get_print_status(self._current_job_id)
                    self._parse_print_status(status)

                    state_str = status.get('state', 'printing').lower()

                    # Check completion
                    if state_str == 'completed':
                        break
                    elif state_str == 'error':
                        raise RuntimeError(f"Print failed: {status.get('error_message', 'Unknown error')}")

                    # Publish feedback
                    if feedback_msg:
                        feedback_msg.phase = 3  # Printing
                        feedback_msg.phase_name = "Printing"
                        feedback_msg.progress_percent = self._status.progress_percent
                        feedback_msg.current_layer = self._status.current_layer
                        feedback_msg.total_layers = self._status.total_layers
                        feedback_msg.elapsed_sec = self._status.elapsed_sec
                        feedback_msg.remaining_sec = self._status.remaining_sec
                        goal_handle.publish_feedback(feedback_msg)

                    await asyncio.sleep(5)  # Poll every 5 seconds

            # Success
            goal_handle.succeed()
            self._status.state = PrinterState.COMPLETED

            if result:
                result.success = True
                result.message = "Print completed successfully"
                result.actual_duration_sec = self._status.elapsed_sec
                result.layers_printed = self._status.total_layers

            self._current_job_id = None
            return result

        except Exception as e:
            self.get_logger().error(f"Print failed: {e}")
            goal_handle.abort()
            self._status.state = PrinterState.ERROR

            if result:
                result.success = False
                result.message = str(e)

            self._current_job_id = None
            return result

    def destroy_node(self):
        """Cleanup."""
        if self._client:
            asyncio.get_event_loop().run_until_complete(self._client.disconnect())
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    node = FormlabsNode()

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

class FormlabsLifecycleNode:
    """
    ROS2 Lifecycle wrapper for Formlabs SLA printer node.

    Implements lifecycle states for graceful startup/shutdown:
    - unconfigured -> configuring -> inactive
    - inactive -> activating -> active
    - active -> deactivating -> inactive
    - inactive -> cleaningup -> unconfigured

    Industry 4.0/5.0 Architecture - ISA-95 Level 0 (Field Layer)
    """

    def __init__(self):
        self._node: Optional['LifecycleNode'] = None
        self._client: Optional[PreFormClient] = None
        self._status = PrintStatus()
        self._current_job_id: Optional[str] = None
        self._cb_group = None
        self._status_timer = None
        self._action_server = None

    def create_node(self) -> 'LifecycleNode':
        """Create and return the lifecycle node instance."""
        if not LIFECYCLE_AVAILABLE:
            raise RuntimeError("rclpy.lifecycle not available")

        outer = self

        class _FormlabsLifecycle(LifecycleNode):
            """Inner lifecycle node class."""

            def __init__(self):
                super().__init__('formlabs_node')

                # Declare parameters
                self.declare_parameter('api_host', 'localhost')
                self.declare_parameter('api_port', 44388)
                self.declare_parameter('printer_serial', '')
                self.declare_parameter('status_rate_hz', 0.5)
                self.declare_parameter('simulate', False)

                self.get_logger().info(
                    "FormlabsLifecycleNode created (unconfigured)"
                )

            def on_configure(self, state: State) -> TransitionCallbackReturn:
                """Configure: Initialize resources but don't start."""
                self.get_logger().info(f"Configuring from {state.label}...")

                try:
                    # Get parameters
                    outer._api_host = self.get_parameter('api_host').value
                    outer._api_port = self.get_parameter('api_port').value
                    outer._printer_serial = self.get_parameter('printer_serial').value
                    outer._status_rate = self.get_parameter('status_rate_hz').value
                    outer._simulate = self.get_parameter('simulate').value

                    # Callback group
                    outer._cb_group = ReentrantCallbackGroup()

                    # Create client (but don't connect yet)
                    if not outer._simulate:
                        outer._client = PreFormClient(
                            outer._api_host,
                            outer._api_port
                        )

                    self.get_logger().info("Configuration complete")
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    self.get_logger().error(f"Configuration failed: {e}")
                    return TransitionCallbackReturn.FAILURE

            def on_activate(self, state: State) -> TransitionCallbackReturn:
                """Activate: Start communication and publishing."""
                self.get_logger().info(f"Activating from {state.label}...")

                try:
                    # Connect to PreFormServer
                    if outer._client and not outer._simulate:
                        loop = asyncio.new_event_loop()
                        connected = loop.run_until_complete(
                            outer._client.connect()
                        )
                        if not connected:
                            self.get_logger().warn(
                                "Failed to connect to PreFormServer, "
                                "continuing in degraded mode"
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
                        outer._poll_status,
                        callback_group=outer._cb_group
                    )

                    self.get_logger().info("Activation complete - node active")
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    self.get_logger().error(f"Activation failed: {e}")
                    return TransitionCallbackReturn.FAILURE

            def on_deactivate(self, state: State) -> TransitionCallbackReturn:
                """Deactivate: Stop communication but keep resources."""
                self.get_logger().info(f"Deactivating from {state.label}...")

                try:
                    # Cancel status timer
                    if outer._status_timer:
                        outer._status_timer.cancel()
                        outer._status_timer = None

                    # Cancel any active print
                    if outer._current_job_id and outer._client:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(
                            outer._client.cancel_print(outer._current_job_id)
                        )
                        outer._current_job_id = None

                    self.get_logger().info("Deactivation complete")
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    self.get_logger().error(f"Deactivation failed: {e}")
                    return TransitionCallbackReturn.FAILURE

            def on_cleanup(self, state: State) -> TransitionCallbackReturn:
                """Cleanup: Release all resources."""
                self.get_logger().info(f"Cleaning up from {state.label}...")

                try:
                    # Disconnect from PreFormServer
                    if outer._client:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(outer._client.disconnect())
                        outer._client = None

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
                    # Ensure client disconnected
                    if outer._client:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(outer._client.disconnect())
                        outer._client = None

                    self.get_logger().info("Shutdown complete")
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    self.get_logger().error(f"Shutdown error: {e}")
                    return TransitionCallbackReturn.SUCCESS  # Always succeed

            def on_error(self, state: State) -> TransitionCallbackReturn:
                """Error handling: Attempt recovery."""
                self.get_logger().error(f"Error occurred in {state.label}")

                try:
                    # Emergency stop any print
                    if outer._client and outer._current_job_id:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(
                            outer._client.cancel_print(outer._current_job_id)
                        )
                        outer._current_job_id = None

                    outer._status.state = PrinterState.ERROR

                    self.get_logger().info("Error handled, node in error state")
                    return TransitionCallbackReturn.SUCCESS

                except Exception as e:
                    self.get_logger().error(f"Error handling failed: {e}")
                    return TransitionCallbackReturn.FAILURE

        self._node = _FormlabsLifecycle()
        return self._node

    def _on_estop(self, msg: Bool):
        """Handle emergency stop."""
        if msg.data:
            if self._node:
                self._node.get_logger().warn("E-STOP activated!")
            if self._client and self._current_job_id:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(
                    self._client.pause_print(self._current_job_id)
                )

    def _poll_status(self):
        """Poll printer status."""
        if self._simulate:
            self._publish_simulated_status()
            return

        if not self._client or not self._client.is_connected:
            return

        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._async_poll_status())

    async def _async_poll_status(self):
        """Async status polling."""
        try:
            printer_status = await self._client.get_printer_status(
                self._printer_serial
            )
            self._parse_printer_status(printer_status)

            if self._current_job_id:
                print_status = await self._client.get_print_status(
                    self._current_job_id
                )
                self._parse_print_status(print_status)

            self._publish_status()
        except Exception as e:
            if self._node:
                self._node.get_logger().warn(f"Status poll failed: {e}")

    def _parse_printer_status(self, status: Dict):
        """Parse printer status response."""
        state_str = status.get('state', 'offline').lower()
        state_map = {
            'offline': PrinterState.OFFLINE,
            'idle': PrinterState.IDLE,
            'preparing': PrinterState.PREPARING,
            'printing': PrinterState.PRINTING,
            'paused': PrinterState.PAUSED,
            'finishing': PrinterState.FINISHING,
            'completed': PrinterState.COMPLETED,
            'error': PrinterState.ERROR,
        }
        self._status.state = state_map.get(state_str, PrinterState.OFFLINE)

    def _parse_print_status(self, status: Dict):
        """Parse print job status response."""
        self._status.job_id = status.get('job_id', '')
        self._status.job_name = status.get('job_name', '')
        self._status.progress_percent = status.get('progress', 0.0) * 100
        self._status.current_layer = status.get('current_layer', 0)
        self._status.total_layers = status.get('total_layers', 0)
        self._status.elapsed_sec = status.get('elapsed_seconds', 0.0)
        self._status.remaining_sec = status.get('remaining_seconds', 0.0)

    def _publish_status(self):
        """Publish current status."""
        if not self._node:
            return

        # State
        state_msg = String()
        state_msg.data = self._status.state.value
        self._state_pub.publish(state_msg)

        # Full status
        if MSGS_AVAILABLE:
            status_msg = PrintJob()
            status_msg.header.stamp = self._node.get_clock().now().to_msg()
            status_msg.job_id = self._status.job_id
            status_msg.printer_id = self._node.get_name()
            status_msg.printer_type = 'sla'
            status_msg.progress_percent = self._status.progress_percent
            status_msg.current_layer = self._status.current_layer
            status_msg.total_layers = self._status.total_layers
            status_msg.elapsed_time_sec = self._status.elapsed_sec
            status_msg.estimated_remaining_sec = self._status.remaining_sec
            self._status_pub.publish(status_msg)

    def _publish_simulated_status(self):
        """Publish simulated status."""
        if not self._node:
            return
        state_msg = String()
        state_msg.data = self._status.state.value
        self._state_pub.publish(state_msg)

    def _goal_callback(self, goal_request):
        """Handle action goal."""
        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle):
        """Handle action cancel."""
        return CancelResponse.ACCEPT

    async def _execute_callback(self, goal_handle):
        """Execute print job - delegates to similar logic as FormlabsNode."""
        if self._node:
            self._node.get_logger().info("Starting print job (lifecycle)")

        request = goal_handle.request
        source_file = getattr(request, 'source_file', '')
        sliced_file = getattr(request, 'sliced_file', '')

        feedback_msg = PrintBrick.Feedback() if MSGS_AVAILABLE else None
        result = PrintBrick.Result() if MSGS_AVAILABLE else None

        try:
            if self._simulate:
                # Simulated print
                total_time = 60
                for i in range(total_time):
                    if goal_handle.is_cancel_requested:
                        goal_handle.canceled()
                        if result:
                            result.success = False
                            result.message = "Cancelled"
                        return result

                    progress = (i + 1) / total_time * 100
                    self._status.progress_percent = progress
                    self._status.state = PrinterState.PRINTING

                    if feedback_msg:
                        feedback_msg.phase = 3
                        feedback_msg.phase_name = "Printing"
                        feedback_msg.progress_percent = progress
                        goal_handle.publish_feedback(feedback_msg)

                    await asyncio.sleep(0.1)
            else:
                # Real print logic (same as FormlabsNode)
                if not self._client or not self._client.is_connected:
                    raise RuntimeError("Not connected to PreFormServer")

                if sliced_file and sliced_file.endswith('.form'):
                    scene_id = await self._client.upload_form_file(sliced_file)
                elif source_file:
                    scene_id = await self._client.import_model(source_file)
                else:
                    raise ValueError("No source or sliced file provided")

                self._current_job_id = await self._client.start_print(
                    scene_id,
                    self._printer_serial
                )

                while True:
                    if goal_handle.is_cancel_requested:
                        await self._client.cancel_print(self._current_job_id)
                        goal_handle.canceled()
                        if result:
                            result.success = False
                        self._current_job_id = None
                        return result

                    status = await self._client.get_print_status(
                        self._current_job_id
                    )
                    state_str = status.get('state', '').lower()

                    if state_str == 'completed':
                        break
                    elif state_str == 'error':
                        raise RuntimeError("Print failed")

                    await asyncio.sleep(5)

            goal_handle.succeed()
            self._status.state = PrinterState.COMPLETED

            if result:
                result.success = True
                result.message = "Print completed"

            self._current_job_id = None
            return result

        except Exception as e:
            if self._node:
                self._node.get_logger().error(f"Print failed: {e}")
            goal_handle.abort()
            if result:
                result.success = False
                result.message = str(e)
            self._current_job_id = None
            return result


def main_lifecycle(args=None):
    """
    Main entry point for lifecycle node.

    Usage:
        ros2 run formlabs_ros2 formlabs_node_lifecycle
    """
    rclpy.init(args=args)

    wrapper = FormlabsLifecycleNode()
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
