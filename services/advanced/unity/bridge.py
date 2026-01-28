"""
Unity WebSocket Bridge
======================

Real-time bi-directional communication bridge between the Digital Twin Engine
and Unity 3D clients (WebGL, Desktop, VR, AR).

Features:
- Multi-client support with room-based subscriptions
- Delta updates for bandwidth efficiency
- Client-side prediction support
- Animation triggering
- Command routing from Unity to physical equipment
- Heartbeat and connection monitoring

Protocol:
- Binary messages for high-frequency sensor data
- JSON messages for commands and state updates
- Message compression for large payloads

Author: LegoMCP Team
Version: 2.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid
import logging
import json
import time
import threading
import queue
import zlib
from collections import defaultdict

logger = logging.getLogger(__name__)


class ClientType(Enum):
    """Types of Unity client connections."""
    WEBGL = "webgl"
    DESKTOP = "desktop"
    VR_QUEST = "vr_quest"
    VR_VIVE = "vr_vive"
    AR_HOLOLENS = "ar_hololens"
    AR_IOS = "ar_ios"
    AR_ANDROID = "ar_android"
    UNKNOWN = "unknown"


class MessageType(Enum):
    """WebSocket message types for Unity protocol."""
    # Connection
    HANDSHAKE = "handshake"
    HANDSHAKE_ACK = "handshake_ack"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    DISCONNECT = "disconnect"

    # Subscriptions
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SUBSCRIBE_ACK = "subscribe_ack"

    # State updates
    FULL_STATE = "full_state"
    DELTA_STATE = "delta_state"
    STATE_REQUEST = "state_request"

    # Equipment updates
    EQUIPMENT_UPDATE = "equipment_update"
    SENSOR_DATA = "sensor_data"
    ALARM = "alarm"
    MAINTENANCE_ALERT = "maintenance_alert"

    # Production
    JOB_UPDATE = "job_update"
    OEE_UPDATE = "oee_update"
    QUALITY_EVENT = "quality_event"

    # Predictions
    PREDICTION = "prediction"
    RUL_UPDATE = "rul_update"
    FAILURE_ALERT = "failure_alert"

    # Commands (Unity -> Physical)
    COMMAND = "command"
    COMMAND_ACK = "command_ack"
    COMMAND_RESULT = "command_result"

    # Simulation
    SIMULATION_START = "simulation_start"
    SIMULATION_STEP = "simulation_step"
    SIMULATION_END = "simulation_end"

    # Visualization
    HIGHLIGHT = "highlight"
    CAMERA_SYNC = "camera_sync"
    ANNOTATION = "annotation"
    HEATMAP_DATA = "heatmap_data"

    # Robotic Arm (ISO 10218 / ISO/TS 15066)
    ARM_STATE = "arm_state"
    ARM_JOINT_UPDATE = "arm_joint_update"
    ARM_TRAJECTORY = "arm_trajectory"
    ARM_COMMAND = "arm_command"
    ARM_COMMAND_ACK = "arm_command_ack"
    ARM_GRIPPER_STATE = "arm_gripper_state"
    ARM_COLLISION_ALERT = "arm_collision_alert"
    ARM_ZONE_VIOLATION = "arm_zone_violation"

    # AR/VR specific
    SPATIAL_ANCHOR = "spatial_anchor"
    HAND_TRACKING = "hand_tracking"
    VOICE_COMMAND = "voice_command"
    GAZE_TARGET = "gaze_target"

    # Error
    ERROR = "error"


class SubscriptionRoom(Enum):
    """Subscription rooms for filtering updates."""
    ALL = "all"
    EQUIPMENT = "equipment"
    PRODUCTION = "production"
    QUALITY = "quality"
    MAINTENANCE = "maintenance"
    PREDICTIONS = "predictions"
    SIMULATION = "simulation"
    SCHEDULING = "scheduling"
    ENERGY = "energy"
    ALARMS = "alarms"
    ROBOTIC_ARMS = "robotic_arms"  # Arm state, joint positions, trajectories


@dataclass
class UnityClient:
    """Represents a connected Unity client."""
    client_id: str
    client_type: ClientType
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Connection state
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    is_connected: bool = True

    # Subscriptions
    subscribed_rooms: Set[SubscriptionRoom] = field(default_factory=set)
    subscribed_equipment: Set[str] = field(default_factory=set)  # Specific OME IDs

    # Client capabilities
    supports_binary: bool = True
    supports_compression: bool = True
    max_update_rate_hz: float = 60.0  # Client's requested max update rate
    preferred_lod: int = 0  # Level of detail preference

    # Client state
    last_state_timestamp: Optional[datetime] = None
    viewport_position: Dict[str, float] = field(default_factory=lambda: {'x': 0, 'y': 0, 'z': 0})
    viewport_rotation: Dict[str, float] = field(default_factory=lambda: {'x': 0, 'y': 0, 'z': 0})

    # Metrics
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    latency_ms: float = 0.0

    # AR/VR specific
    device_info: Dict[str, Any] = field(default_factory=dict)
    spatial_anchors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'client_id': self.client_id,
            'client_type': self.client_type.value,
            'session_id': self.session_id,
            'connected_at': self.connected_at.isoformat(),
            'last_heartbeat': self.last_heartbeat.isoformat(),
            'is_connected': self.is_connected,
            'subscribed_rooms': [r.value for r in self.subscribed_rooms],
            'subscribed_equipment': list(self.subscribed_equipment),
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received,
            'latency_ms': self.latency_ms
        }


@dataclass
class UnityMessage:
    """Message structure for Unity WebSocket protocol."""
    type: MessageType
    payload: Dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None  # For request-response patterns
    priority: int = 0  # Higher = more important

    def to_json(self, compress: bool = False) -> str:
        data = {
            'type': self.type.value,
            'payload': self.payload,
            'messageId': self.message_id,
            'timestamp': self.timestamp.isoformat(),
            'correlationId': self.correlation_id
        }
        json_str = json.dumps(data)

        if compress and len(json_str) > 1024:
            # Compress large messages
            compressed = zlib.compress(json_str.encode())
            return f"__compressed__{compressed.hex()}"

        return json_str

    @classmethod
    def from_json(cls, json_str: str) -> 'UnityMessage':
        # Handle compressed messages
        if json_str.startswith("__compressed__"):
            hex_data = json_str[14:]
            json_str = zlib.decompress(bytes.fromhex(hex_data)).decode()

        data = json.loads(json_str)
        return cls(
            type=MessageType(data['type']),
            payload=data.get('payload', {}),
            message_id=data.get('messageId', str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.utcnow(),
            correlation_id=data.get('correlationId')
        )


class MessageQueue:
    """Priority queue for outgoing messages with rate limiting."""

    def __init__(self, max_size: int = 10000):
        self._queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=max_size)
        self._sequence: int = 0

    def put(self, message: UnityMessage, priority: int = 0):
        """Add message to queue. Lower priority number = higher priority."""
        self._sequence += 1
        # Negative priority so higher priority values are processed first
        self._queue.put((-priority, self._sequence, message))

    def get(self, timeout: float = 0.1) -> Optional[UnityMessage]:
        """Get next message from queue."""
        try:
            _, _, message = self._queue.get(timeout=timeout)
            return message
        except queue.Empty:
            return None

    def size(self) -> int:
        return self._queue.qsize()


class UnityBridge:
    """
    Central bridge for Unity client communication.

    Manages:
    - Client connections and sessions
    - Message routing and delivery
    - State synchronization
    - Rate limiting and bandwidth management
    - Room-based subscriptions
    """

    def __init__(self):
        # Client management
        self._clients: Dict[str, UnityClient] = {}
        self._room_members: Dict[SubscriptionRoom, Set[str]] = defaultdict(set)

        # Message handling
        self._message_handlers: Dict[MessageType, List[Callable]] = defaultdict(list)
        self._message_queue: MessageQueue = MessageQueue()
        self._outgoing_queues: Dict[str, MessageQueue] = {}  # Per-client queues

        # State caching
        self._last_full_state: Optional[Dict[str, Any]] = None
        self._last_state_time: Optional[datetime] = None
        self._state_version: int = 0

        # Rate limiting
        self._rate_limits: Dict[str, float] = {}  # client_id -> last_send_time
        self._min_send_interval_ms: float = 16.67  # ~60 FPS max

        # Background worker
        self._worker_thread: Optional[threading.Thread] = None
        self._running: bool = False

        # Metrics
        self._metrics = {
            'clients_connected': 0,
            'total_messages_sent': 0,
            'total_messages_received': 0,
            'total_bytes_sent': 0,
            'total_bytes_received': 0,
            'queue_depth': 0
        }

        # Register default handlers
        self._register_default_handlers()

        logger.info("UnityBridge initialized")

    def _register_default_handlers(self):
        """Register default message handlers."""
        self.register_handler(MessageType.HANDSHAKE, self._handle_handshake)
        self.register_handler(MessageType.HEARTBEAT, self._handle_heartbeat)
        self.register_handler(MessageType.SUBSCRIBE, self._handle_subscribe)
        self.register_handler(MessageType.UNSUBSCRIBE, self._handle_unsubscribe)
        self.register_handler(MessageType.STATE_REQUEST, self._handle_state_request)
        self.register_handler(MessageType.COMMAND, self._handle_command)
        self.register_handler(MessageType.DISCONNECT, self._handle_disconnect)

    # ================== Client Management ==================

    def connect_client(
        self,
        client_id: str,
        client_type: ClientType = ClientType.UNKNOWN,
        capabilities: Dict[str, Any] = None
    ) -> UnityClient:
        """Register a new Unity client connection."""
        client = UnityClient(
            client_id=client_id,
            client_type=client_type,
            supports_binary=capabilities.get('binary', True) if capabilities else True,
            supports_compression=capabilities.get('compression', True) if capabilities else True,
            max_update_rate_hz=capabilities.get('max_fps', 60.0) if capabilities else 60.0,
            device_info=capabilities.get('device', {}) if capabilities else {}
        )

        self._clients[client_id] = client
        self._outgoing_queues[client_id] = MessageQueue()
        self._rate_limits[client_id] = 0.0

        # Subscribe to ALL by default
        self._subscribe_to_room(client_id, SubscriptionRoom.ALL)

        self._metrics['clients_connected'] = len(self._clients)

        logger.info(f"Unity client connected: {client_id} ({client_type.value})")

        # Send handshake acknowledgment
        self.send_to_client(client_id, UnityMessage(
            type=MessageType.HANDSHAKE_ACK,
            payload={
                'session_id': client.session_id,
                'server_time': datetime.utcnow().isoformat(),
                'protocol_version': '2.0.0',
                'capabilities': {
                    'compression': True,
                    'binary': True,
                    'max_update_rate': 60,
                    'rooms': [r.value for r in SubscriptionRoom]
                }
            }
        ))

        return client

    def disconnect_client(self, client_id: str):
        """Disconnect a Unity client."""
        if client_id not in self._clients:
            return

        client = self._clients[client_id]
        client.is_connected = False

        # Remove from all rooms
        for room in list(client.subscribed_rooms):
            self._unsubscribe_from_room(client_id, room)

        # Clean up
        del self._clients[client_id]
        if client_id in self._outgoing_queues:
            del self._outgoing_queues[client_id]
        if client_id in self._rate_limits:
            del self._rate_limits[client_id]

        self._metrics['clients_connected'] = len(self._clients)

        logger.info(f"Unity client disconnected: {client_id}")

    def get_client(self, client_id: str) -> Optional[UnityClient]:
        """Get client by ID."""
        return self._clients.get(client_id)

    def get_all_clients(self) -> List[UnityClient]:
        """Get all connected clients."""
        return list(self._clients.values())

    def get_clients_by_type(self, client_type: ClientType) -> List[UnityClient]:
        """Get clients of specific type (e.g., all VR clients)."""
        return [c for c in self._clients.values() if c.client_type == client_type]

    # ================== Subscriptions ==================

    def _subscribe_to_room(self, client_id: str, room: SubscriptionRoom):
        """Subscribe client to a room."""
        if client_id not in self._clients:
            return

        client = self._clients[client_id]
        client.subscribed_rooms.add(room)
        self._room_members[room].add(client_id)

    def _unsubscribe_from_room(self, client_id: str, room: SubscriptionRoom):
        """Unsubscribe client from a room."""
        if client_id not in self._clients:
            return

        client = self._clients[client_id]
        client.subscribed_rooms.discard(room)
        self._room_members[room].discard(client_id)

    def subscribe_to_equipment(self, client_id: str, equipment_ids: List[str]):
        """Subscribe client to specific equipment updates."""
        if client_id not in self._clients:
            return

        client = self._clients[client_id]
        client.subscribed_equipment.update(equipment_ids)

    # ================== Message Handling ==================

    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register a handler for a message type."""
        self._message_handlers[message_type].append(handler)

    def process_message(self, client_id: str, message_json: str) -> Optional[UnityMessage]:
        """Process incoming message from Unity client."""
        try:
            message = UnityMessage.from_json(message_json)

            client = self._clients.get(client_id)
            if client:
                client.messages_received += 1
                client.bytes_received += len(message_json)
                self._metrics['total_messages_received'] += 1
                self._metrics['total_bytes_received'] += len(message_json)

            # Call registered handlers
            handlers = self._message_handlers.get(message.type, [])
            for handler in handlers:
                try:
                    handler(client_id, message)
                except Exception as e:
                    logger.error(f"Handler error for {message.type}: {e}")

            return message

        except Exception as e:
            logger.error(f"Message processing error: {e}")
            self.send_to_client(client_id, UnityMessage(
                type=MessageType.ERROR,
                payload={'error': str(e)}
            ))
            return None

    # ================== Message Sending ==================

    def send_to_client(
        self,
        client_id: str,
        message: UnityMessage,
        compress: bool = None
    ) -> bool:
        """Send message to specific client."""
        client = self._clients.get(client_id)
        if not client or not client.is_connected:
            return False

        # Rate limiting
        current_time = time.time() * 1000
        last_send = self._rate_limits.get(client_id, 0)
        if current_time - last_send < self._min_send_interval_ms:
            # Queue for later
            self._outgoing_queues[client_id].put(message, message.priority)
            return True

        # Determine compression
        if compress is None:
            compress = client.supports_compression

        json_str = message.to_json(compress=compress)

        # Track metrics
        client.messages_sent += 1
        client.bytes_sent += len(json_str)
        self._metrics['total_messages_sent'] += 1
        self._metrics['total_bytes_sent'] += len(json_str)
        self._rate_limits[client_id] = current_time

        # Actual send would be implemented by WebSocket handler
        # This returns the JSON to be sent
        return True

    def broadcast_to_room(
        self,
        room: SubscriptionRoom,
        message: UnityMessage,
        exclude_clients: List[str] = None
    ):
        """Broadcast message to all clients in a room."""
        exclude = set(exclude_clients or [])
        client_ids = self._room_members.get(room, set()) | self._room_members.get(SubscriptionRoom.ALL, set())

        for client_id in client_ids:
            if client_id not in exclude:
                self.send_to_client(client_id, message)

    def broadcast_all(self, message: UnityMessage):
        """Broadcast to all connected clients."""
        for client_id in self._clients:
            self.send_to_client(client_id, message)

    def broadcast_equipment_update(
        self,
        equipment_id: str,
        update_data: Dict[str, Any]
    ):
        """Broadcast equipment state update to subscribed clients."""
        message = UnityMessage(
            type=MessageType.EQUIPMENT_UPDATE,
            payload={
                'equipment_id': equipment_id,
                'data': update_data,
                'timestamp': datetime.utcnow().isoformat()
            }
        )

        # Send to equipment room and clients subscribed to this equipment
        self.broadcast_to_room(SubscriptionRoom.EQUIPMENT, message)

        # Also send to clients specifically subscribed to this equipment
        for client_id, client in self._clients.items():
            if equipment_id in client.subscribed_equipment:
                self.send_to_client(client_id, message)

    # ================== State Synchronization ==================

    def send_full_state(self, client_id: str, state: Dict[str, Any]):
        """Send full scene state to client."""
        self._last_full_state = state
        self._last_state_time = datetime.utcnow()
        self._state_version += 1

        message = UnityMessage(
            type=MessageType.FULL_STATE,
            payload={
                'state': state,
                'version': self._state_version,
                'timestamp': self._last_state_time.isoformat()
            }
        )

        self.send_to_client(client_id, message)

        client = self._clients.get(client_id)
        if client:
            client.last_state_timestamp = self._last_state_time

    def send_delta_state(
        self,
        client_id: str,
        changes: Dict[str, Any],
        base_version: int
    ):
        """Send delta (changes only) to client."""
        message = UnityMessage(
            type=MessageType.DELTA_STATE,
            payload={
                'changes': changes,
                'base_version': base_version,
                'new_version': self._state_version,
                'timestamp': datetime.utcnow().isoformat()
            }
        )

        self.send_to_client(client_id, message)

    # ================== Default Handlers ==================

    def _handle_handshake(self, client_id: str, message: UnityMessage):
        """Handle client handshake."""
        payload = message.payload
        client = self._clients.get(client_id)

        if client:
            # Update client info from handshake
            client.client_type = ClientType(payload.get('client_type', 'unknown'))
            client.supports_binary = payload.get('supports_binary', True)
            client.supports_compression = payload.get('supports_compression', True)
            client.max_update_rate_hz = payload.get('max_fps', 60.0)
            client.device_info = payload.get('device_info', {})

            logger.info(f"Handshake from {client_id}: {client.client_type.value}")

    def _handle_heartbeat(self, client_id: str, message: UnityMessage):
        """Handle heartbeat ping."""
        client = self._clients.get(client_id)
        if client:
            now = datetime.utcnow()
            client.last_heartbeat = now

            # Calculate latency if client sent timestamp
            client_time = message.payload.get('client_time')
            if client_time:
                try:
                    client_dt = datetime.fromisoformat(client_time)
                    client.latency_ms = (now - client_dt).total_seconds() * 1000 / 2
                except ValueError:
                    pass

            # Send heartbeat ack
            self.send_to_client(client_id, UnityMessage(
                type=MessageType.HEARTBEAT_ACK,
                payload={
                    'server_time': now.isoformat(),
                    'latency_ms': client.latency_ms
                },
                correlation_id=message.message_id
            ))

    def _handle_subscribe(self, client_id: str, message: UnityMessage):
        """Handle subscription request."""
        rooms = message.payload.get('rooms', [])
        equipment_ids = message.payload.get('equipment_ids', [])

        for room_name in rooms:
            try:
                room = SubscriptionRoom(room_name)
                self._subscribe_to_room(client_id, room)
            except ValueError:
                logger.warning(f"Unknown room: {room_name}")

        if equipment_ids:
            self.subscribe_to_equipment(client_id, equipment_ids)

        self.send_to_client(client_id, UnityMessage(
            type=MessageType.SUBSCRIBE_ACK,
            payload={
                'rooms': rooms,
                'equipment_ids': equipment_ids
            },
            correlation_id=message.message_id
        ))

    def _handle_unsubscribe(self, client_id: str, message: UnityMessage):
        """Handle unsubscription request."""
        rooms = message.payload.get('rooms', [])

        for room_name in rooms:
            try:
                room = SubscriptionRoom(room_name)
                self._unsubscribe_from_room(client_id, room)
            except ValueError:
                pass

    def _handle_state_request(self, client_id: str, message: UnityMessage):
        """Handle state request from client."""
        request_type = message.payload.get('type', 'full')
        since_version = message.payload.get('since_version')

        if request_type == 'full' or not since_version or since_version < self._state_version - 100:
            # Send full state
            if self._last_full_state:
                self.send_full_state(client_id, self._last_full_state)
        else:
            # Client is relatively up-to-date, send delta
            # This would need to track changes since version
            pass

    def _handle_command(self, client_id: str, message: UnityMessage):
        """Handle command from Unity to physical equipment."""
        command = message.payload.get('command')
        target_id = message.payload.get('target_id')

        logger.info(f"Command from {client_id} to {target_id}: {command}")

        # Acknowledge receipt
        self.send_to_client(client_id, UnityMessage(
            type=MessageType.COMMAND_ACK,
            payload={
                'command_id': message.message_id,
                'status': 'received',
                'target_id': target_id
            },
            correlation_id=message.message_id
        ))

        # Command execution would be handled by TwinEngine
        # Results sent back via COMMAND_RESULT message

    def _handle_disconnect(self, client_id: str, message: UnityMessage):
        """Handle graceful disconnect."""
        reason = message.payload.get('reason', 'client_requested')
        logger.info(f"Client {client_id} disconnecting: {reason}")
        self.disconnect_client(client_id)

    # ================== Specialized Broadcasts ==================

    def broadcast_alarm(
        self,
        equipment_id: str,
        alarm_type: str,
        severity: str,
        message_text: str
    ):
        """Broadcast alarm to all subscribed clients."""
        message = UnityMessage(
            type=MessageType.ALARM,
            payload={
                'equipment_id': equipment_id,
                'alarm_type': alarm_type,
                'severity': severity,
                'message': message_text,
                'timestamp': datetime.utcnow().isoformat()
            },
            priority=10  # High priority
        )
        self.broadcast_to_room(SubscriptionRoom.ALARMS, message)

    def broadcast_oee_update(
        self,
        equipment_id: str,
        oee_data: Dict[str, float]
    ):
        """Broadcast OEE update."""
        message = UnityMessage(
            type=MessageType.OEE_UPDATE,
            payload={
                'equipment_id': equipment_id,
                'oee': oee_data.get('oee', 0),
                'availability': oee_data.get('availability', 0),
                'performance': oee_data.get('performance', 0),
                'quality': oee_data.get('quality', 0),
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        self.broadcast_to_room(SubscriptionRoom.PRODUCTION, message)

    def broadcast_job_update(
        self,
        job_id: str,
        equipment_id: str,
        status: str,
        progress: float
    ):
        """Broadcast job status update."""
        message = UnityMessage(
            type=MessageType.JOB_UPDATE,
            payload={
                'job_id': job_id,
                'equipment_id': equipment_id,
                'status': status,
                'progress': progress,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        self.broadcast_to_room(SubscriptionRoom.PRODUCTION, message)

    def broadcast_prediction(
        self,
        equipment_id: str,
        prediction_type: str,
        value: Any,
        confidence: float
    ):
        """Broadcast prediction result."""
        message = UnityMessage(
            type=MessageType.PREDICTION,
            payload={
                'equipment_id': equipment_id,
                'prediction_type': prediction_type,
                'value': value,
                'confidence': confidence,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        self.broadcast_to_room(SubscriptionRoom.PREDICTIONS, message)

    def broadcast_heatmap(
        self,
        heatmap_type: str,
        data: List[Dict[str, Any]]
    ):
        """Broadcast heatmap data for 3D visualization."""
        message = UnityMessage(
            type=MessageType.HEATMAP_DATA,
            payload={
                'heatmap_type': heatmap_type,
                'data': data,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        self.broadcast_to_room(SubscriptionRoom.QUALITY, message)

    def trigger_highlight(
        self,
        equipment_id: str,
        highlight_type: str = "pulse",
        color: str = "#FF0000",
        duration_seconds: float = 3.0
    ):
        """Trigger equipment highlight in Unity."""
        message = UnityMessage(
            type=MessageType.HIGHLIGHT,
            payload={
                'equipment_id': equipment_id,
                'highlight_type': highlight_type,
                'color': color,
                'duration': duration_seconds
            }
        )
        self.broadcast_to_room(SubscriptionRoom.ALL, message)

    # ================== Robotic Arm Visualization ==================

    def broadcast_arm_state(
        self,
        arm_id: str,
        state: str,
        joint_positions: List[float],
        tcp_position: Dict[str, float] = None,
        tcp_orientation: Dict[str, float] = None,
        velocity_scale: float = 1.0
    ):
        """
        Broadcast full arm state for Unity visualization.

        Args:
            arm_id: OME ID of the robotic arm
            state: Current state (idle, moving, error, etc.)
            joint_positions: List of joint angles in radians [j1, j2, j3, j4, j5, j6]
            tcp_position: Tool Center Point position {x, y, z} in mm
            tcp_orientation: TCP orientation as quaternion or euler {x, y, z, w} or {rx, ry, rz}
            velocity_scale: Current velocity as fraction of max (0-1)
        """
        message = UnityMessage(
            type=MessageType.ARM_STATE,
            payload={
                'arm_id': arm_id,
                'state': state,
                'joint_positions': joint_positions,
                'tcp_position': tcp_position or {'x': 0, 'y': 0, 'z': 0},
                'tcp_orientation': tcp_orientation or {'x': 0, 'y': 0, 'z': 0, 'w': 1},
                'velocity_scale': velocity_scale,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        self.broadcast_to_room(SubscriptionRoom.ROBOTIC_ARMS, message)

    def broadcast_arm_joint_update(
        self,
        arm_id: str,
        joint_positions: List[float],
        joint_velocities: List[float] = None,
        joint_torques: List[float] = None
    ):
        """
        Broadcast high-frequency joint position updates (for 60fps animation).

        This is a lightweight message for smooth Unity animation.
        """
        message = UnityMessage(
            type=MessageType.ARM_JOINT_UPDATE,
            payload={
                'arm_id': arm_id,
                'positions': joint_positions,
                'velocities': joint_velocities,
                'torques': joint_torques,
                'timestamp': datetime.utcnow().isoformat()
            },
            priority=5  # High priority for smooth animation
        )
        self.broadcast_to_room(SubscriptionRoom.ROBOTIC_ARMS, message)

    def broadcast_arm_trajectory(
        self,
        arm_id: str,
        trajectory_points: List[Dict[str, Any]],
        duration_seconds: float,
        interpolation: str = "linear"
    ):
        """
        Broadcast planned trajectory for Unity preview/execution.

        Args:
            arm_id: OME ID of the robotic arm
            trajectory_points: List of waypoints [{positions: [...], time: float}, ...]
            duration_seconds: Total trajectory duration
            interpolation: Interpolation mode (linear, cubic, quintic)
        """
        message = UnityMessage(
            type=MessageType.ARM_TRAJECTORY,
            payload={
                'arm_id': arm_id,
                'trajectory': trajectory_points,
                'duration': duration_seconds,
                'interpolation': interpolation,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        self.broadcast_to_room(SubscriptionRoom.ROBOTIC_ARMS, message)

    def broadcast_arm_gripper_state(
        self,
        arm_id: str,
        gripper_id: str,
        position: float,
        force: float = 0.0,
        is_gripping: bool = False,
        object_detected: bool = False
    ):
        """
        Broadcast gripper/end-effector state.

        Args:
            arm_id: Parent arm OME ID
            gripper_id: Gripper OME ID
            position: Gripper position (0=closed, 1=fully open)
            force: Current grip force in Newtons
            is_gripping: Whether gripper is actively gripping
            object_detected: Whether object is detected between fingers
        """
        message = UnityMessage(
            type=MessageType.ARM_GRIPPER_STATE,
            payload={
                'arm_id': arm_id,
                'gripper_id': gripper_id,
                'position': position,
                'force': force,
                'is_gripping': is_gripping,
                'object_detected': object_detected,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        self.broadcast_to_room(SubscriptionRoom.ROBOTIC_ARMS, message)

    def broadcast_arm_collision_alert(
        self,
        arm_id: str,
        collision_type: str,
        affected_joints: List[int],
        collision_point: Dict[str, float] = None,
        force_magnitude: float = 0.0
    ):
        """
        Broadcast collision detection alert (ISO/TS 15066 safety).

        Args:
            arm_id: OME ID of the arm
            collision_type: Type of collision (obstacle, self, human, workspace_limit)
            affected_joints: List of joint indices involved
            collision_point: 3D point of collision in world coords
            force_magnitude: Force detected at collision in Newtons
        """
        message = UnityMessage(
            type=MessageType.ARM_COLLISION_ALERT,
            payload={
                'arm_id': arm_id,
                'collision_type': collision_type,
                'affected_joints': affected_joints,
                'collision_point': collision_point,
                'force_magnitude': force_magnitude,
                'timestamp': datetime.utcnow().isoformat()
            },
            priority=10  # Critical priority
        )
        self.broadcast_to_room(SubscriptionRoom.ROBOTIC_ARMS, message)
        self.broadcast_to_room(SubscriptionRoom.ALARMS, message)

    def broadcast_arm_zone_violation(
        self,
        arm_id: str,
        zone_id: str,
        zone_type: str,
        violation_severity: str
    ):
        """
        Broadcast safety zone violation (ISO 10218).

        Args:
            arm_id: OME ID of the arm
            zone_id: ID of the violated zone
            zone_type: Type of zone (restricted, collaborative, stop)
            violation_severity: Severity level (warning, critical, emergency_stop)
        """
        message = UnityMessage(
            type=MessageType.ARM_ZONE_VIOLATION,
            payload={
                'arm_id': arm_id,
                'zone_id': zone_id,
                'zone_type': zone_type,
                'violation_severity': violation_severity,
                'timestamp': datetime.utcnow().isoformat()
            },
            priority=10  # Critical priority
        )
        self.broadcast_to_room(SubscriptionRoom.ROBOTIC_ARMS, message)
        self.broadcast_to_room(SubscriptionRoom.ALARMS, message)

    def send_arm_command(
        self,
        arm_id: str,
        command_type: str,
        parameters: Dict[str, Any],
        client_id: str = None
    ):
        """
        Send command to robotic arm from Unity.

        Args:
            arm_id: Target arm OME ID
            command_type: Type of command (move_joint, move_linear, home, stop, etc.)
            parameters: Command-specific parameters
            client_id: Optional - if provided, sends acknowledgment to specific client
        """
        command_id = str(uuid.uuid4())

        message = UnityMessage(
            type=MessageType.ARM_COMMAND,
            payload={
                'command_id': command_id,
                'arm_id': arm_id,
                'command_type': command_type,
                'parameters': parameters,
                'timestamp': datetime.utcnow().isoformat()
            }
        )

        # Broadcast command to all arm subscribers (for monitoring)
        self.broadcast_to_room(SubscriptionRoom.ROBOTIC_ARMS, message)

        # If client specified, send acknowledgment
        if client_id:
            ack_message = UnityMessage(
                type=MessageType.ARM_COMMAND_ACK,
                payload={
                    'command_id': command_id,
                    'arm_id': arm_id,
                    'status': 'received',
                    'timestamp': datetime.utcnow().isoformat()
                },
                correlation_id=command_id
            )
            self.send_to_client(client_id, ack_message)

        return command_id

    # ================== AR/VR Specific ==================

    def sync_spatial_anchor(
        self,
        anchor_id: str,
        position: Dict[str, float],
        rotation: Dict[str, float],
        equipment_id: str = None
    ):
        """Sync spatial anchor for AR clients."""
        message = UnityMessage(
            type=MessageType.SPATIAL_ANCHOR,
            payload={
                'anchor_id': anchor_id,
                'position': position,
                'rotation': rotation,
                'equipment_id': equipment_id,
                'timestamp': datetime.utcnow().isoformat()
            }
        )

        # Send to AR/VR clients only
        for client in self._clients.values():
            if client.client_type in [
                ClientType.AR_HOLOLENS,
                ClientType.AR_IOS,
                ClientType.AR_ANDROID,
                ClientType.VR_QUEST,
                ClientType.VR_VIVE
            ]:
                self.send_to_client(client.client_id, message)

    def handle_voice_command(self, client_id: str, command_text: str):
        """Handle voice command from AR/VR client."""
        logger.info(f"Voice command from {client_id}: {command_text}")
        # Would parse and route command
        pass

    # ================== Metrics ==================

    def get_metrics(self) -> Dict[str, Any]:
        """Get bridge performance metrics."""
        self._metrics['queue_depth'] = sum(
            q.size() for q in self._outgoing_queues.values()
        )

        return {
            **self._metrics,
            'clients_by_type': {
                ct.value: len([c for c in self._clients.values() if c.client_type == ct])
                for ct in ClientType if any(c.client_type == ct for c in self._clients.values())
            },
            'room_sizes': {
                room.value: len(members)
                for room, members in self._room_members.items()
                if members
            },
            'state_version': self._state_version,
            'uptime_seconds': (datetime.utcnow() - min(
                (c.connected_at for c in self._clients.values()),
                default=datetime.utcnow()
            )).total_seconds() if self._clients else 0
        }

    # ================== Background Processing ==================

    def start(self):
        """Start background worker for queue processing."""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        logger.info("UnityBridge started")

    def stop(self):
        """Stop background worker."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)

        logger.info("UnityBridge stopped")

    def _worker_loop(self):
        """Background loop for processing message queues."""
        while self._running:
            try:
                # Process outgoing queues
                for client_id, queue in list(self._outgoing_queues.items()):
                    message = queue.get(timeout=0.001)
                    if message:
                        self.send_to_client(client_id, message)

                # Check for disconnected clients (no heartbeat)
                now = datetime.utcnow()
                for client_id, client in list(self._clients.items()):
                    if (now - client.last_heartbeat).total_seconds() > 30:
                        logger.warning(f"Client {client_id} heartbeat timeout")
                        self.disconnect_client(client_id)

                time.sleep(0.01)  # 10ms loop

            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(1.0)


# Singleton instance
_bridge_instance: Optional[UnityBridge] = None


def get_unity_bridge() -> UnityBridge:
    """Get the global UnityBridge instance."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = UnityBridge()
    return _bridge_instance
