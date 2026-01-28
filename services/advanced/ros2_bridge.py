"""
ROS2 Bridge - Flask to ROS2 Communication Layer
LEGO MCP Manufacturing System v7.0

Provides WebSocket-based communication between Flask dashboard and ROS2 network
via rosbridge_suite. Enables:
- Service calls from Flask to ROS2 services
- Topic publishing from Flask to ROS2
- Topic subscription (ROS2 to Flask via callbacks)
- Action client interface for long-running operations

Requirements:
    pip install roslibpy>=1.4.0

Usage:
    from services.ros2_bridge import ros2_bridge

    # Call a service
    result = await ros2_bridge.call_service(
        '/manufacturing/create_work_order',
        'lego_mcp_msgs/srv/CreateWorkOrder',
        {'part_id': 'brick-2x4', 'quantity': 100}
    )

    # Publish to topic
    await ros2_bridge.publish(
        '/manufacturing/commands',
        'std_msgs/msg/String',
        {'data': 'START'}
    )

    # Subscribe to topic
    def on_twin_state(msg):
        print(f"Twin state: {msg}")

    ros2_bridge.subscribe(
        '/lego_mcp/twin_state',
        'lego_mcp_msgs/msg/TwinState',
        on_twin_state
    )
"""

import asyncio
import json
import logging
import threading
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import asynccontextmanager

try:
    import roslibpy
    ROSLIBPY_AVAILABLE = True
except ImportError:
    ROSLIBPY_AVAILABLE = False
    roslibpy = None

logger = logging.getLogger(__name__)


@dataclass
class ActionGoalHandle:
    """Handle for tracking action goal progress."""
    goal_id: str
    action_name: str
    action_type: str
    status: str = 'pending'  # pending, active, succeeded, failed, cancelled
    result: Optional[Dict] = None
    feedback_callback: Optional[Callable] = None
    feedback_history: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class ROS2Bridge:
    """
    Bridge between Flask dashboard and ROS2 network.
    Uses rosbridge_suite WebSocket protocol for communication.
    """

    def __init__(
        self,
        rosbridge_host: str = 'localhost',
        rosbridge_port: int = 9090,
        auto_connect: bool = True,
        reconnect_interval: float = 5.0
    ):
        """
        Initialize ROS2 Bridge.

        Args:
            rosbridge_host: rosbridge WebSocket server host
            rosbridge_port: rosbridge WebSocket server port
            auto_connect: Automatically connect on initialization
            reconnect_interval: Seconds between reconnection attempts
        """
        self.host = rosbridge_host
        self.port = rosbridge_port
        self.reconnect_interval = reconnect_interval

        self._client: Optional['roslibpy.Ros'] = None
        self._connected = False
        self._subscriptions: Dict[str, 'roslibpy.Topic'] = {}
        self._publishers: Dict[str, 'roslibpy.Topic'] = {}
        self._action_goals: Dict[str, ActionGoalHandle] = {}
        self._lock = threading.Lock()
        self._reconnect_task: Optional[asyncio.Task] = None

        if not ROSLIBPY_AVAILABLE:
            logger.warning(
                "roslibpy not installed. ROS2 bridge will operate in mock mode. "
                "Install with: pip install roslibpy"
            )

        if auto_connect and ROSLIBPY_AVAILABLE:
            self._connect()

    def _connect(self) -> bool:
        """Establish connection to rosbridge server."""
        if not ROSLIBPY_AVAILABLE:
            return False

        try:
            self._client = roslibpy.Ros(host=self.host, port=self.port)
            self._client.on_ready(self._on_connected)
            self._client.on('close', self._on_disconnected)
            self._client.run()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to rosbridge: {e}")
            self._connected = False
            return False

    def _on_connected(self):
        """Callback when connection is established."""
        logger.info(f"Connected to rosbridge at {self.host}:{self.port}")
        self._connected = True

        # Resubscribe to all topics
        with self._lock:
            for topic_name, topic in self._subscriptions.items():
                if not topic.is_subscribed:
                    topic.subscribe(topic._callback)

    def _on_disconnected(self, *args):
        """Callback when connection is lost."""
        logger.warning("Disconnected from rosbridge")
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to rosbridge."""
        if not ROSLIBPY_AVAILABLE:
            return False
        return self._connected and self._client is not None and self._client.is_connected

    async def ensure_connected(self) -> bool:
        """Ensure connection is established, attempting reconnect if needed."""
        if self.is_connected:
            return True

        if not ROSLIBPY_AVAILABLE:
            logger.warning("roslibpy not available, using mock mode")
            return False

        return await asyncio.to_thread(self._connect)

    # =========================================================================
    # SERVICE CALLS
    # =========================================================================

    async def call_service(
        self,
        service_name: str,
        service_type: str,
        request: Dict[str, Any],
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Call a ROS2 service.

        Args:
            service_name: Full service name (e.g., '/manufacturing/create_work_order')
            service_type: Service type (e.g., 'lego_mcp_msgs/srv/CreateWorkOrder')
            request: Request message as dictionary
            timeout: Timeout in seconds

        Returns:
            Response message as dictionary

        Raises:
            TimeoutError: If service call times out
            RuntimeError: If not connected to rosbridge
        """
        if not ROSLIBPY_AVAILABLE:
            logger.info(f"[MOCK] Service call: {service_name}")
            return self._mock_service_response(service_name, request)

        if not await self.ensure_connected():
            raise RuntimeError("Not connected to rosbridge")

        service = roslibpy.Service(self._client, service_name, service_type)
        request_msg = roslibpy.ServiceRequest(request)

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(service.call, request_msg),
                timeout=timeout
            )
            return dict(result)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Service call to {service_name} timed out")
        finally:
            service.unadvertise()

    def _mock_service_response(self, service_name: str, request: Dict) -> Dict:
        """Generate mock response for testing without ROS2."""
        if 'CreateWorkOrder' in service_name:
            return {
                'success': True,
                'message': 'Mock work order created',
                'work_order_id': f'WO-MOCK-{datetime.now().strftime("%H%M%S")}',
                'status': 'planned',
                'operation_ids': ['OP-001', 'OP-002'],
                'estimated_duration_min': 45.0,
            }
        elif 'ScheduleJob' in service_name:
            return {
                'success': True,
                'message': 'Mock job scheduled',
                'schedule_id': f'SCH-MOCK-{datetime.now().strftime("%H%M%S")}',
                'total_duration_min': 30.0,
            }
        elif 'GetTwinState' in service_name:
            return {
                'success': True,
                'is_synchronized': True,
                'sync_latency_ms': 12.5,
            }
        return {'success': True, 'message': 'Mock response'}

    # =========================================================================
    # TOPIC PUBLISHING
    # =========================================================================

    async def publish(
        self,
        topic_name: str,
        msg_type: str,
        message: Dict[str, Any]
    ) -> bool:
        """
        Publish a message to a ROS2 topic.

        Args:
            topic_name: Topic name (e.g., '/manufacturing/commands')
            msg_type: Message type (e.g., 'std_msgs/msg/String')
            message: Message content as dictionary

        Returns:
            True if published successfully
        """
        if not ROSLIBPY_AVAILABLE:
            logger.info(f"[MOCK] Publish to {topic_name}: {message}")
            return True

        if not await self.ensure_connected():
            return False

        with self._lock:
            if topic_name not in self._publishers:
                self._publishers[topic_name] = roslibpy.Topic(
                    self._client, topic_name, msg_type
                )
                self._publishers[topic_name].advertise()

        publisher = self._publishers[topic_name]
        msg = roslibpy.Message(message)

        await asyncio.to_thread(publisher.publish, msg)
        return True

    # =========================================================================
    # TOPIC SUBSCRIPTION
    # =========================================================================

    def subscribe(
        self,
        topic_name: str,
        msg_type: str,
        callback: Callable[[Dict], None],
        throttle_rate: int = 0,
        queue_length: int = 1
    ) -> bool:
        """
        Subscribe to a ROS2 topic.

        Args:
            topic_name: Topic name to subscribe to
            msg_type: Message type
            callback: Function to call with each message
            throttle_rate: Minimum time between messages (ms), 0 = no throttle
            queue_length: Message queue length

        Returns:
            True if subscription successful
        """
        if not ROSLIBPY_AVAILABLE:
            logger.info(f"[MOCK] Subscribe to {topic_name}")
            return True

        if not self.is_connected:
            logger.warning(f"Cannot subscribe to {topic_name}: not connected")
            return False

        with self._lock:
            if topic_name in self._subscriptions:
                # Already subscribed, just update callback
                return True

            topic = roslibpy.Topic(
                self._client,
                topic_name,
                msg_type,
                throttle_rate=throttle_rate,
                queue_length=queue_length
            )

            def wrapped_callback(msg):
                try:
                    callback(dict(msg))
                except Exception as e:
                    logger.error(f"Error in subscription callback for {topic_name}: {e}")

            topic._callback = wrapped_callback
            topic.subscribe(wrapped_callback)
            self._subscriptions[topic_name] = topic

        return True

    def unsubscribe(self, topic_name: str) -> bool:
        """Unsubscribe from a topic."""
        with self._lock:
            if topic_name in self._subscriptions:
                self._subscriptions[topic_name].unsubscribe()
                del self._subscriptions[topic_name]
                return True
        return False

    # =========================================================================
    # ACTION CLIENT
    # =========================================================================

    async def send_action_goal(
        self,
        action_name: str,
        action_type: str,
        goal: Dict[str, Any],
        feedback_callback: Optional[Callable[[Dict], None]] = None,
        timeout: Optional[float] = None
    ) -> ActionGoalHandle:
        """
        Send an action goal and optionally wait for completion.

        Args:
            action_name: Action server name (e.g., '/formlabs/print')
            action_type: Action type (e.g., 'lego_mcp_msgs/action/PrintBrick')
            goal: Goal message as dictionary
            feedback_callback: Optional callback for feedback messages
            timeout: Optional timeout in seconds (None = don't wait)

        Returns:
            ActionGoalHandle for tracking progress
        """
        import uuid
        goal_id = str(uuid.uuid4())[:8]

        handle = ActionGoalHandle(
            goal_id=goal_id,
            action_name=action_name,
            action_type=action_type,
            feedback_callback=feedback_callback
        )

        self._action_goals[goal_id] = handle

        if not ROSLIBPY_AVAILABLE:
            logger.info(f"[MOCK] Action goal sent: {action_name}")
            handle.status = 'active'
            # Simulate completion after short delay
            asyncio.create_task(self._mock_action_completion(handle))
            return handle

        if not await self.ensure_connected():
            handle.status = 'failed'
            handle.result = {'success': False, 'message': 'Not connected to rosbridge'}
            return handle

        # Use roslibpy ActionClient
        action_client = roslibpy.actionlib.ActionClient(
            self._client,
            action_name,
            action_type
        )

        def on_feedback(feedback):
            handle.feedback_history.append(dict(feedback))
            if feedback_callback:
                feedback_callback(dict(feedback))

        def on_result(result):
            handle.status = 'succeeded' if result.get('success', False) else 'failed'
            handle.result = dict(result)
            handle.completed_at = datetime.now()

        goal_msg = roslibpy.actionlib.Goal(action_client, roslibpy.Message(goal))
        goal_msg.on('feedback', on_feedback)
        goal_msg.on('result', on_result)
        goal_msg.send()

        handle.status = 'active'

        if timeout:
            try:
                await asyncio.wait_for(
                    self._wait_for_action_completion(handle),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                handle.status = 'failed'
                handle.result = {'success': False, 'message': 'Action timed out'}

        return handle

    async def _wait_for_action_completion(self, handle: ActionGoalHandle):
        """Wait for action to complete."""
        while handle.status == 'active':
            await asyncio.sleep(0.1)

    async def _mock_action_completion(self, handle: ActionGoalHandle):
        """Simulate action completion for mock mode."""
        await asyncio.sleep(2.0)
        handle.status = 'succeeded'
        handle.result = {'success': True, 'message': 'Mock action completed'}
        handle.completed_at = datetime.now()

    def cancel_action(self, goal_id: str) -> bool:
        """Cancel a running action."""
        if goal_id in self._action_goals:
            handle = self._action_goals[goal_id]
            handle.status = 'cancelled'
            handle.completed_at = datetime.now()
            return True
        return False

    def get_action_status(self, goal_id: str) -> Optional[ActionGoalHandle]:
        """Get status of an action goal."""
        return self._action_goals.get(goal_id)

    # =========================================================================
    # CONVENIENCE METHODS FOR LEGO MCP
    # =========================================================================

    async def create_work_order(
        self,
        part_id: str,
        quantity: int,
        priority: int = 2,
        auto_schedule: bool = True
    ) -> Dict[str, Any]:
        """Create a manufacturing work order via ROS2 service."""
        return await self.call_service(
            '/manufacturing/create_work_order',
            'lego_mcp_msgs/srv/CreateWorkOrder',
            {
                'part_id': part_id,
                'quantity': quantity,
                'priority': priority,
                'auto_schedule': auto_schedule,
            }
        )

    async def schedule_job(
        self,
        work_order_id: str,
        strategy: str = 'cp_sat'
    ) -> Dict[str, Any]:
        """Schedule a job via ROS2 service."""
        return await self.call_service(
            '/scheduling/schedule_job',
            'lego_mcp_msgs/srv/ScheduleJob',
            {
                'work_order_id': work_order_id,
                'scheduling_strategy': strategy,
            }
        )

    async def start_print_job(
        self,
        brick_id: str,
        printer_id: str = '',
        feedback_callback: Optional[Callable] = None
    ) -> ActionGoalHandle:
        """Start a print job via ROS2 action."""
        return await self.send_action_goal(
            '/formlabs/print',
            'lego_mcp_msgs/action/PrintBrick',
            {
                'brick_id': brick_id,
                'printer_id': printer_id,
            },
            feedback_callback=feedback_callback
        )

    async def start_assembly(
        self,
        assembly_id: str,
        robot_id: str = '',
        enable_ar: bool = True,
        feedback_callback: Optional[Callable] = None
    ) -> ActionGoalHandle:
        """Start LEGO assembly via ROS2 action."""
        return await self.send_action_goal(
            '/ned2/assemble' if robot_id == 'ned2' else '/xarm/assemble',
            'lego_mcp_msgs/action/AssembleLego',
            {
                'assembly_id': assembly_id,
                'robot_id': robot_id,
                'enable_ar_guidance': enable_ar,
            },
            feedback_callback=feedback_callback
        )

    async def execute_gcode(
        self,
        machine_id: str,
        gcode: str,
        feedback_callback: Optional[Callable] = None
    ) -> ActionGoalHandle:
        """Execute G-code on CNC/Laser via ROS2 action."""
        namespace = 'cnc' if 'cnc' in machine_id.lower() else 'laser'
        return await self.send_action_goal(
            f'/{namespace}/execute',
            'lego_mcp_msgs/action/MachineOperation',
            {
                'machine_id': machine_id,
                'gcode': gcode,
            },
            feedback_callback=feedback_callback
        )

    async def emergency_stop(self, equipment_id: str = '') -> Dict[str, Any]:
        """Trigger emergency stop via ROS2 service."""
        return await self.call_service(
            '/safety/emergency_stop',
            'std_srvs/srv/Trigger',
            {}
        )

    async def get_twin_state(self) -> Dict[str, Any]:
        """Get current digital twin state."""
        return await self.call_service(
            '/lego_mcp/get_twin_state',
            'lego_mcp_msgs/srv/GetTwinState',
            {
                'include_equipment_details': True,
                'include_spatial_data': True,
                'include_predictions': True,
            }
        )

    def subscribe_twin_state(self, callback: Callable[[Dict], None]) -> bool:
        """Subscribe to digital twin state updates."""
        return self.subscribe(
            '/lego_mcp/twin_state',
            'lego_mcp_msgs/msg/TwinState',
            callback,
            throttle_rate=100  # Max 10 Hz
        )

    def subscribe_quality_events(self, callback: Callable[[Dict], None]) -> bool:
        """Subscribe to quality events."""
        return self.subscribe(
            '/quality/events',
            'lego_mcp_msgs/msg/QualityEvent',
            callback
        )

    def subscribe_equipment_status(
        self,
        equipment_id: str,
        callback: Callable[[Dict], None]
    ) -> bool:
        """Subscribe to specific equipment status updates."""
        return self.subscribe(
            f'/{equipment_id}/status',
            'lego_mcp_msgs/msg/EquipmentStatus',
            callback
        )

    # =========================================================================
    # CLEANUP
    # =========================================================================

    def close(self):
        """Close connection and cleanup resources."""
        with self._lock:
            for topic in self._subscriptions.values():
                topic.unsubscribe()
            self._subscriptions.clear()

            for topic in self._publishers.values():
                topic.unadvertise()
            self._publishers.clear()

        if self._client:
            self._client.terminate()
            self._client = None

        self._connected = False
        logger.info("ROS2 bridge closed")


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Global bridge instance
ros2_bridge = ROS2Bridge(auto_connect=False)


def init_ros2_bridge(
    host: str = 'localhost',
    port: int = 9090
) -> ROS2Bridge:
    """
    Initialize the global ROS2 bridge instance.
    Call this from Flask app initialization.
    """
    global ros2_bridge
    ros2_bridge = ROS2Bridge(
        rosbridge_host=host,
        rosbridge_port=port,
        auto_connect=True
    )
    return ros2_bridge


def get_ros2_bridge() -> ROS2Bridge:
    """Get the global ROS2 bridge instance."""
    return ros2_bridge
