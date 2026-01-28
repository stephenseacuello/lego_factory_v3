"""
Sparkplug B MQTT Client - Industrial MQTT Protocol Implementation
LEGO MCP Manufacturing System v7.0

MQTT Sparkplug B client for industrial IoT communication:
- Birth/Death certificates (NBIRTH, NDEATH, DBIRTH, DDEATH)
- Sparkplug B topic namespace
- Metric encoding per Sparkplug B specification
- ROS2 bridge integration for equipment data

Requirements:
    pip install paho-mqtt>=2.0.0 protobuf>=4.0.0

Standards Compliance:
    - Sparkplug B Specification v3.0
    - Eclipse Tahu Sparkplug B
    - MQTT 5.0 / 3.1.1 compatible
"""

import asyncio
import logging
import struct
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import threading
import json

logger = logging.getLogger(__name__)

# =============================================================================
# SPARKPLUG B CONSTANTS & TYPES
# =============================================================================

# Sparkplug B Topic Namespace
# spBv1.0/group_id/message_type/edge_node_id/[device_id]

class SparkplugMessageType(IntEnum):
    """Sparkplug B message types."""
    NBIRTH = 0   # Node Birth Certificate
    NDEATH = 1   # Node Death Certificate
    DBIRTH = 2   # Device Birth Certificate
    DDEATH = 3   # Device Death Certificate
    NDATA = 4    # Node Data
    DDATA = 5    # Device Data
    NCMD = 6     # Node Command
    DCMD = 7     # Device Command
    STATE = 8    # SCADA Host State


class SparkplugDataType(IntEnum):
    """Sparkplug B data types."""
    UNKNOWN = 0
    INT8 = 1
    INT16 = 2
    INT32 = 3
    INT64 = 4
    UINT8 = 5
    UINT16 = 6
    UINT32 = 7
    UINT64 = 8
    FLOAT = 9
    DOUBLE = 10
    BOOLEAN = 11
    STRING = 12
    DATETIME = 13
    TEXT = 14
    UUID = 15
    DATASET = 16
    BYTES = 17
    FILE = 18
    TEMPLATE = 19


# Python type to Sparkplug data type mapping
PYTHON_TO_SPARKPLUG = {
    bool: SparkplugDataType.BOOLEAN,
    int: SparkplugDataType.INT64,
    float: SparkplugDataType.DOUBLE,
    str: SparkplugDataType.STRING,
    bytes: SparkplugDataType.BYTES,
    datetime: SparkplugDataType.DATETIME,
}


@dataclass
class SparkplugMetric:
    """
    Sparkplug B Metric.

    Represents a single data point per Sparkplug B specification.
    """
    name: str
    alias: Optional[int] = None
    timestamp: int = 0  # milliseconds since epoch
    datatype: SparkplugDataType = SparkplugDataType.UNKNOWN
    is_historical: bool = False
    is_transient: bool = False
    is_null: bool = False
    metadata: Optional[Dict[str, Any]] = None
    properties: Optional[Dict[str, Any]] = None

    # Value (only one should be set based on datatype)
    int_value: Optional[int] = None
    long_value: Optional[int] = None
    float_value: Optional[float] = None
    double_value: Optional[float] = None
    boolean_value: Optional[bool] = None
    string_value: Optional[str] = None
    bytes_value: Optional[bytes] = None

    @property
    def value(self) -> Any:
        """Get the metric value based on datatype."""
        if self.is_null:
            return None
        if self.datatype in (SparkplugDataType.INT8, SparkplugDataType.INT16,
                            SparkplugDataType.INT32, SparkplugDataType.UINT8,
                            SparkplugDataType.UINT16, SparkplugDataType.UINT32):
            return self.int_value
        if self.datatype in (SparkplugDataType.INT64, SparkplugDataType.UINT64):
            return self.long_value
        if self.datatype == SparkplugDataType.FLOAT:
            return self.float_value
        if self.datatype == SparkplugDataType.DOUBLE:
            return self.double_value
        if self.datatype == SparkplugDataType.BOOLEAN:
            return self.boolean_value
        if self.datatype in (SparkplugDataType.STRING, SparkplugDataType.TEXT,
                            SparkplugDataType.UUID):
            return self.string_value
        if self.datatype == SparkplugDataType.BYTES:
            return self.bytes_value
        if self.datatype == SparkplugDataType.DATETIME:
            return self.long_value
        return None

    @value.setter
    def value(self, val: Any) -> None:
        """Set the metric value and auto-detect datatype."""
        if val is None:
            self.is_null = True
            return

        self.is_null = False

        if isinstance(val, bool):
            self.datatype = SparkplugDataType.BOOLEAN
            self.boolean_value = val
        elif isinstance(val, int):
            if -2147483648 <= val <= 2147483647:
                self.datatype = SparkplugDataType.INT32
                self.int_value = val
            else:
                self.datatype = SparkplugDataType.INT64
                self.long_value = val
        elif isinstance(val, float):
            self.datatype = SparkplugDataType.DOUBLE
            self.double_value = val
        elif isinstance(val, str):
            self.datatype = SparkplugDataType.STRING
            self.string_value = val
        elif isinstance(val, bytes):
            self.datatype = SparkplugDataType.BYTES
            self.bytes_value = val
        elif isinstance(val, datetime):
            self.datatype = SparkplugDataType.DATETIME
            self.long_value = int(val.timestamp() * 1000)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'alias': self.alias,
            'timestamp': self.timestamp,
            'datatype': self.datatype.name,
            'value': self.value,
            'is_historical': self.is_historical,
            'is_transient': self.is_transient,
            'is_null': self.is_null,
        }

    @classmethod
    def from_value(
        cls,
        name: str,
        value: Any,
        alias: Optional[int] = None,
        timestamp: Optional[int] = None
    ) -> 'SparkplugMetric':
        """Create metric from name and value."""
        metric = cls(
            name=name,
            alias=alias,
            timestamp=timestamp or int(time.time() * 1000),
        )
        metric.value = value
        return metric


@dataclass
class SparkplugPayload:
    """
    Sparkplug B Payload.

    Contains the metrics and metadata for a Sparkplug message.
    """
    timestamp: int = 0  # milliseconds since epoch
    metrics: List[SparkplugMetric] = field(default_factory=list)
    seq: int = 0  # Sequence number (0-255)
    uuid: str = ""
    body: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'seq': self.seq,
            'uuid': self.uuid,
            'metrics': [m.to_dict() for m in self.metrics],
        }

    def to_json(self) -> str:
        """Serialize to JSON (for debugging/non-protobuf mode)."""
        return json.dumps(self.to_dict())

    def to_protobuf(self) -> bytes:
        """
        Serialize to Sparkplug B protobuf.

        In production, use sparkplug_b_pb2 generated from sparkplug_b.proto
        """
        try:
            # Try to use protobuf if available
            from . import sparkplug_b_pb2
            payload = sparkplug_b_pb2.Payload()
            payload.timestamp = self.timestamp
            payload.seq = self.seq

            for metric in self.metrics:
                m = payload.metrics.add()
                m.name = metric.name
                if metric.alias is not None:
                    m.alias = metric.alias
                m.timestamp = metric.timestamp
                m.datatype = metric.datatype.value
                m.is_historical = metric.is_historical
                m.is_transient = metric.is_transient
                m.is_null = metric.is_null

                if not metric.is_null:
                    if metric.datatype == SparkplugDataType.BOOLEAN:
                        m.boolean_value = metric.boolean_value
                    elif metric.datatype in (SparkplugDataType.INT8, SparkplugDataType.INT16,
                                            SparkplugDataType.INT32, SparkplugDataType.UINT8,
                                            SparkplugDataType.UINT16, SparkplugDataType.UINT32):
                        m.int_value = metric.int_value
                    elif metric.datatype in (SparkplugDataType.INT64, SparkplugDataType.UINT64,
                                            SparkplugDataType.DATETIME):
                        m.long_value = metric.long_value
                    elif metric.datatype == SparkplugDataType.FLOAT:
                        m.float_value = metric.float_value
                    elif metric.datatype == SparkplugDataType.DOUBLE:
                        m.double_value = metric.double_value
                    elif metric.datatype in (SparkplugDataType.STRING, SparkplugDataType.TEXT,
                                            SparkplugDataType.UUID):
                        m.string_value = metric.string_value
                    elif metric.datatype == SparkplugDataType.BYTES:
                        m.bytes_value = metric.bytes_value

            return payload.SerializeToString()

        except ImportError:
            # Fallback to JSON encoding
            return self.to_json().encode('utf-8')

    @classmethod
    def from_protobuf(cls, data: bytes) -> 'SparkplugPayload':
        """Deserialize from Sparkplug B protobuf."""
        try:
            from . import sparkplug_b_pb2
            pb_payload = sparkplug_b_pb2.Payload()
            pb_payload.ParseFromString(data)

            payload = cls(
                timestamp=pb_payload.timestamp,
                seq=pb_payload.seq,
            )

            for m in pb_payload.metrics:
                metric = SparkplugMetric(
                    name=m.name,
                    alias=m.alias if m.HasField('alias') else None,
                    timestamp=m.timestamp,
                    datatype=SparkplugDataType(m.datatype),
                    is_historical=m.is_historical,
                    is_transient=m.is_transient,
                    is_null=m.is_null,
                )

                if not metric.is_null:
                    if metric.datatype == SparkplugDataType.BOOLEAN:
                        metric.boolean_value = m.boolean_value
                    elif metric.datatype in (SparkplugDataType.INT8, SparkplugDataType.INT16,
                                            SparkplugDataType.INT32):
                        metric.int_value = m.int_value
                    elif metric.datatype in (SparkplugDataType.INT64, SparkplugDataType.UINT64,
                                            SparkplugDataType.DATETIME):
                        metric.long_value = m.long_value
                    elif metric.datatype == SparkplugDataType.FLOAT:
                        metric.float_value = m.float_value
                    elif metric.datatype == SparkplugDataType.DOUBLE:
                        metric.double_value = m.double_value
                    elif metric.datatype in (SparkplugDataType.STRING, SparkplugDataType.TEXT):
                        metric.string_value = m.string_value
                    elif metric.datatype == SparkplugDataType.BYTES:
                        metric.bytes_value = m.bytes_value

                payload.metrics.append(metric)

            return payload

        except ImportError:
            # Fallback from JSON
            data_dict = json.loads(data.decode('utf-8'))
            payload = cls(
                timestamp=data_dict.get('timestamp', 0),
                seq=data_dict.get('seq', 0),
                uuid=data_dict.get('uuid', ''),
            )
            for m_dict in data_dict.get('metrics', []):
                metric = SparkplugMetric(
                    name=m_dict['name'],
                    alias=m_dict.get('alias'),
                    timestamp=m_dict.get('timestamp', 0),
                    datatype=SparkplugDataType[m_dict.get('datatype', 'UNKNOWN')],
                )
                metric.value = m_dict.get('value')
                payload.metrics.append(metric)

            return payload


# =============================================================================
# SPARKPLUG B DEVICE
# =============================================================================

@dataclass
class SparkplugDevice:
    """
    Sparkplug B Device.

    Represents an EoN (Edge of Network) device with its metrics.
    """
    device_id: str
    display_name: str = ""
    description: str = ""
    is_online: bool = False
    birth_time: Optional[datetime] = None
    death_time: Optional[datetime] = None

    # Metrics
    metrics: Dict[str, SparkplugMetric] = field(default_factory=dict)
    metric_aliases: Dict[int, str] = field(default_factory=dict)

    # ROS2 topic mappings
    ros2_topics: Dict[str, str] = field(default_factory=dict)

    # Equipment type for bridging
    equipment_type: str = "generic"

    def add_metric(
        self,
        name: str,
        value: Any,
        alias: Optional[int] = None,
        **kwargs
    ) -> SparkplugMetric:
        """Add or update a metric."""
        metric = SparkplugMetric.from_value(name, value, alias)
        self.metrics[name] = metric
        if alias is not None:
            self.metric_aliases[alias] = name
        return metric

    def get_metric(self, name_or_alias: Union[str, int]) -> Optional[SparkplugMetric]:
        """Get metric by name or alias."""
        if isinstance(name_or_alias, int):
            name = self.metric_aliases.get(name_or_alias)
            if name:
                return self.metrics.get(name)
            return None
        return self.metrics.get(name_or_alias)

    def get_birth_metrics(self) -> List[SparkplugMetric]:
        """Get all metrics for birth certificate."""
        return list(self.metrics.values())

    def get_changed_metrics(
        self,
        since_timestamp: int
    ) -> List[SparkplugMetric]:
        """Get metrics that changed since timestamp."""
        return [
            m for m in self.metrics.values()
            if m.timestamp > since_timestamp
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'device_id': self.device_id,
            'display_name': self.display_name,
            'description': self.description,
            'is_online': self.is_online,
            'birth_time': self.birth_time.isoformat() if self.birth_time else None,
            'death_time': self.death_time.isoformat() if self.death_time else None,
            'metric_count': len(self.metrics),
            'metrics': {n: m.to_dict() for n, m in self.metrics.items()},
        }


# =============================================================================
# SPARKPLUG B CLIENT
# =============================================================================

class SparkplugBClient:
    """
    Sparkplug B MQTT Client.

    Implements the Sparkplug B specification for industrial MQTT communication.

    Features:
        - Birth/Death certificates (NBIRTH, NDEATH, DBIRTH, DDEATH)
        - Sparkplug B topic namespace
        - Metric encoding per specification
        - ROS2 bridge integration
        - State management per SCADA host

    Topic Structure:
        spBv1.0/{group_id}/NBIRTH/{edge_node_id}
        spBv1.0/{group_id}/NDEATH/{edge_node_id}
        spBv1.0/{group_id}/DBIRTH/{edge_node_id}/{device_id}
        spBv1.0/{group_id}/DDEATH/{edge_node_id}/{device_id}
        spBv1.0/{group_id}/NDATA/{edge_node_id}
        spBv1.0/{group_id}/DDATA/{edge_node_id}/{device_id}
        spBv1.0/{group_id}/NCMD/{edge_node_id}
        spBv1.0/{group_id}/DCMD/{edge_node_id}/{device_id}
    """

    SPARKPLUG_VERSION = "spBv1.0"

    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        group_id: str = "LegoMCP",
        edge_node_id: str = "EdgeNode1",
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = False,
        client_id: Optional[str] = None,
        ros2_bridge: Optional[Any] = None,
    ):
        """
        Initialize Sparkplug B Client.

        Args:
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
            group_id: Sparkplug group ID
            edge_node_id: Edge node identifier
            username: MQTT username
            password: MQTT password
            use_tls: Enable TLS
            client_id: MQTT client ID
            ros2_bridge: ROS2 bridge for equipment data
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.group_id = group_id
        self.edge_node_id = edge_node_id
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.client_id = client_id or f"sparkplug-{edge_node_id}-{uuid.uuid4().hex[:8]}"
        self.ros2_bridge = ros2_bridge

        # MQTT client
        self._client = None
        self._connected = False
        self._running = False

        # Sparkplug state
        self._seq = 0  # Sequence number (0-255)
        self._bd_seq = 0  # Birth/Death sequence
        self._devices: Dict[str, SparkplugDevice] = {}
        self._node_online = False

        # Node metrics
        self._node_metrics: Dict[str, SparkplugMetric] = {}

        # Callbacks
        self._on_command_callbacks: List[Callable[[str, str, SparkplugMetric], None]] = []
        self._on_state_callbacks: List[Callable[[str, bool], None]] = []

        # Update task
        self._update_task: Optional[asyncio.Task] = None
        self._update_interval: float = 1.0

        # Thread lock
        self._lock = threading.Lock()

        logger.info(
            f"Sparkplug B Client initialized: {self.SPARKPLUG_VERSION}/{group_id}/{edge_node_id}"
        )

    # =========================================================================
    # TOPIC HELPERS
    # =========================================================================

    def _get_topic(
        self,
        message_type: SparkplugMessageType,
        device_id: Optional[str] = None
    ) -> str:
        """Build Sparkplug B topic."""
        base = f"{self.SPARKPLUG_VERSION}/{self.group_id}/{message_type.name}/{self.edge_node_id}"
        if device_id:
            return f"{base}/{device_id}"
        return base

    def _get_state_topic(self) -> str:
        """Get STATE topic for SCADA host."""
        return f"{self.SPARKPLUG_VERSION}/STATE/{self.edge_node_id}"

    def _increment_seq(self) -> int:
        """Increment and return sequence number (wraps at 256)."""
        self._seq = (self._seq + 1) % 256
        return self._seq

    def _increment_bd_seq(self) -> int:
        """Increment birth/death sequence."""
        self._bd_seq = (self._bd_seq + 1) % 256
        return self._bd_seq

    # =========================================================================
    # CONNECTION
    # =========================================================================

    async def connect(self) -> bool:
        """
        Connect to MQTT broker.

        Establishes connection with Last Will (NDEATH) configured.
        """
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.error("paho-mqtt not installed. Install with: pip install paho-mqtt")
            return await self._connect_simulation()

        try:
            # Configure client with protocol version
            self._client = mqtt.Client(
                client_id=self.client_id,
                protocol=mqtt.MQTTv5,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            )

            # Set callbacks
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            # Configure credentials
            if self.username:
                self._client.username_pw_set(self.username, self.password)

            # Configure TLS
            if self.use_tls:
                self._client.tls_set()

            # Configure Last Will (NDEATH)
            death_payload = self._create_death_payload()
            death_topic = self._get_topic(SparkplugMessageType.NDEATH)
            self._client.will_set(
                death_topic,
                death_payload.to_protobuf(),
                qos=1,
                retain=False
            )

            # Connect
            self._client.connect(self.broker_host, self.broker_port, keepalive=60)
            self._client.loop_start()

            # Wait for connection
            for _ in range(50):  # 5 second timeout
                if self._connected:
                    break
                await asyncio.sleep(0.1)

            if not self._connected:
                logger.error("Failed to connect to MQTT broker")
                return False

            return True

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return await self._connect_simulation()

    async def _connect_simulation(self) -> bool:
        """Connect in simulation mode without MQTT."""
        logger.warning("Running Sparkplug B client in simulation mode")
        self._connected = True
        self._running = True
        return True

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """MQTT connection callback."""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            self._connected = True

            # Subscribe to commands
            cmd_topic = self._get_topic(SparkplugMessageType.NCMD) + "/#"
            client.subscribe(cmd_topic, qos=1)

            # Subscribe to STATE
            state_topic = f"{self.SPARKPLUG_VERSION}/STATE/#"
            client.subscribe(state_topic, qos=1)

        else:
            logger.error(f"Connection failed with code: {rc}")
            self._connected = False

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """MQTT disconnection callback."""
        logger.warning(f"Disconnected from MQTT broker: {rc}")
        self._connected = False
        self._node_online = False

    def _on_message(self, client, userdata, msg):
        """MQTT message callback."""
        try:
            topic_parts = msg.topic.split('/')
            if len(topic_parts) < 4:
                return

            message_type = topic_parts[2]

            if message_type == 'NCMD':
                self._handle_node_command(msg.payload)
            elif message_type == 'DCMD':
                device_id = topic_parts[4] if len(topic_parts) > 4 else None
                if device_id:
                    self._handle_device_command(device_id, msg.payload)
            elif message_type == 'STATE':
                scada_id = topic_parts[2] if len(topic_parts) > 2 else None
                self._handle_state(scada_id, msg.payload)

        except Exception as e:
            logger.error(f"Message handling error: {e}")

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        self._running = False

        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        # Send NDEATH
        if self._connected and self._node_online:
            await self._send_node_death()

        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

        self._connected = False
        self._node_online = False
        logger.info("Sparkplug B client disconnected")

    # =========================================================================
    # BIRTH/DEATH CERTIFICATES
    # =========================================================================

    def _create_death_payload(self) -> SparkplugPayload:
        """Create NDEATH payload."""
        payload = SparkplugPayload(
            timestamp=int(time.time() * 1000),
            seq=0,  # NDEATH always has seq=0
        )

        # Add bdSeq metric
        bd_seq_metric = SparkplugMetric.from_value(
            "bdSeq",
            self._bd_seq,
            alias=0
        )
        payload.metrics.append(bd_seq_metric)

        return payload

    async def send_node_birth(self) -> bool:
        """
        Send Node Birth Certificate (NBIRTH).

        NBIRTH contains all node-level metrics and announces the edge node.
        """
        if not self._connected:
            return False

        self._bd_seq = self._increment_bd_seq()
        self._seq = 0  # Reset sequence on birth

        payload = SparkplugPayload(
            timestamp=int(time.time() * 1000),
            seq=self._seq,
        )

        # Add bdSeq metric (required)
        payload.metrics.append(SparkplugMetric.from_value("bdSeq", self._bd_seq, alias=0))

        # Add node metrics
        payload.metrics.append(SparkplugMetric.from_value(
            "Node Control/Rebirth", False, alias=1
        ))
        payload.metrics.append(SparkplugMetric.from_value(
            "Properties/Hardware Make", "LegoMCP", alias=2
        ))
        payload.metrics.append(SparkplugMetric.from_value(
            "Properties/Hardware Model", "EdgeController v1.0", alias=3
        ))
        payload.metrics.append(SparkplugMetric.from_value(
            "Properties/Software Version", "7.0.0", alias=4
        ))

        # Add any custom node metrics
        for name, metric in self._node_metrics.items():
            payload.metrics.append(metric)

        # Publish
        topic = self._get_topic(SparkplugMessageType.NBIRTH)
        success = self._publish(topic, payload)

        if success:
            self._node_online = True
            logger.info("Node Birth Certificate sent")

        return success

    async def _send_node_death(self) -> bool:
        """Send Node Death Certificate (NDEATH) on graceful shutdown."""
        payload = self._create_death_payload()
        topic = self._get_topic(SparkplugMessageType.NDEATH)
        return self._publish(topic, payload)

    async def send_device_birth(self, device_id: str) -> bool:
        """
        Send Device Birth Certificate (DBIRTH).

        DBIRTH contains all device-level metrics.
        """
        device = self._devices.get(device_id)
        if not device or not self._connected:
            return False

        payload = SparkplugPayload(
            timestamp=int(time.time() * 1000),
            seq=self._increment_seq(),
        )

        # Add all device metrics
        for metric in device.get_birth_metrics():
            payload.metrics.append(metric)

        # Publish
        topic = self._get_topic(SparkplugMessageType.DBIRTH, device_id)
        success = self._publish(topic, payload)

        if success:
            device.is_online = True
            device.birth_time = datetime.now(timezone.utc)
            logger.info(f"Device Birth Certificate sent: {device_id}")

        return success

    async def send_device_death(self, device_id: str) -> bool:
        """
        Send Device Death Certificate (DDEATH).
        """
        device = self._devices.get(device_id)
        if not device or not self._connected:
            return False

        payload = SparkplugPayload(
            timestamp=int(time.time() * 1000),
            seq=self._increment_seq(),
        )

        # Publish
        topic = self._get_topic(SparkplugMessageType.DDEATH, device_id)
        success = self._publish(topic, payload)

        if success:
            device.is_online = False
            device.death_time = datetime.now(timezone.utc)
            logger.info(f"Device Death Certificate sent: {device_id}")

        return success

    # =========================================================================
    # DATA PUBLISHING
    # =========================================================================

    async def send_node_data(
        self,
        metrics: List[SparkplugMetric]
    ) -> bool:
        """
        Send Node Data (NDATA).

        Used to publish changed node-level metrics.
        """
        if not self._connected or not self._node_online:
            return False

        payload = SparkplugPayload(
            timestamp=int(time.time() * 1000),
            seq=self._increment_seq(),
        )
        payload.metrics = metrics

        topic = self._get_topic(SparkplugMessageType.NDATA)
        return self._publish(topic, payload)

    async def send_device_data(
        self,
        device_id: str,
        metrics: Optional[List[SparkplugMetric]] = None
    ) -> bool:
        """
        Send Device Data (DDATA).

        If metrics not provided, sends all changed metrics since last publish.
        """
        device = self._devices.get(device_id)
        if not device or not self._connected or not device.is_online:
            return False

        payload = SparkplugPayload(
            timestamp=int(time.time() * 1000),
            seq=self._increment_seq(),
        )

        if metrics:
            payload.metrics = metrics
        else:
            # Get all metrics (in production, track changes)
            payload.metrics = list(device.metrics.values())

        if not payload.metrics:
            return True  # Nothing to send

        topic = self._get_topic(SparkplugMessageType.DDATA, device_id)
        return self._publish(topic, payload)

    def _publish(self, topic: str, payload: SparkplugPayload) -> bool:
        """Publish payload to topic."""
        if self._client is None:
            # Simulation mode
            logger.debug(f"[SIM] Publish to {topic}: {len(payload.metrics)} metrics")
            return True

        try:
            data = payload.to_protobuf()
            result = self._client.publish(topic, data, qos=1)
            return result.rc == 0
        except Exception as e:
            logger.error(f"Publish error: {e}")
            return False

    # =========================================================================
    # DEVICE MANAGEMENT
    # =========================================================================

    def register_device(
        self,
        device_id: str,
        display_name: str = "",
        description: str = "",
        equipment_type: str = "generic",
        ros2_topics: Optional[Dict[str, str]] = None,
    ) -> SparkplugDevice:
        """
        Register a device with the Sparkplug client.

        Args:
            device_id: Unique device identifier
            display_name: Human-readable name
            description: Device description
            equipment_type: Type for ROS2 bridging
            ros2_topics: ROS2 topic mappings

        Returns:
            SparkplugDevice instance
        """
        device = SparkplugDevice(
            device_id=device_id,
            display_name=display_name or device_id,
            description=description,
            equipment_type=equipment_type,
            ros2_topics=ros2_topics or {},
        )

        # Add standard metrics
        device.add_metric("Properties/Name", display_name, alias=100)
        device.add_metric("Properties/Description", description, alias=101)
        device.add_metric("Properties/Type", equipment_type, alias=102)

        self._devices[device_id] = device
        logger.info(f"Registered Sparkplug device: {device_id}")

        return device

    def unregister_device(self, device_id: str) -> bool:
        """Unregister a device."""
        if device_id in self._devices:
            # Send death if online
            if self._devices[device_id].is_online and self._connected:
                asyncio.create_task(self.send_device_death(device_id))
            del self._devices[device_id]
            logger.info(f"Unregistered device: {device_id}")
            return True
        return False

    def get_device(self, device_id: str) -> Optional[SparkplugDevice]:
        """Get device by ID."""
        return self._devices.get(device_id)

    def get_all_devices(self) -> List[SparkplugDevice]:
        """Get all registered devices."""
        return list(self._devices.values())

    def update_device_metric(
        self,
        device_id: str,
        metric_name: str,
        value: Any,
        alias: Optional[int] = None
    ) -> bool:
        """Update a device metric value."""
        device = self._devices.get(device_id)
        if not device:
            return False

        metric = device.get_metric(metric_name)
        if metric:
            metric.value = value
            metric.timestamp = int(time.time() * 1000)
        else:
            device.add_metric(metric_name, value, alias)

        return True

    # =========================================================================
    # ROS2 BRIDGE INTEGRATION
    # =========================================================================

    async def start_ros2_bridge(self) -> bool:
        """Start bridging ROS2 topics to Sparkplug."""
        if not self.ros2_bridge:
            logger.warning("No ROS2 bridge configured")
            return False

        for device_id, device in self._devices.items():
            for metric_name, ros2_topic in device.ros2_topics.items():
                try:
                    self.ros2_bridge.subscribe(
                        ros2_topic,
                        'std_msgs/msg/String',  # Generic
                        lambda msg, d=device_id, m=metric_name: self._on_ros2_data(d, m, msg)
                    )
                    logger.info(f"Subscribed {ros2_topic} -> {device_id}/{metric_name}")
                except Exception as e:
                    logger.error(f"Failed to subscribe to {ros2_topic}: {e}")

        return True

    def _on_ros2_data(
        self,
        device_id: str,
        metric_name: str,
        msg: Dict[str, Any]
    ) -> None:
        """Handle ROS2 data and update Sparkplug metric."""
        value = msg.get('data', msg)
        self.update_device_metric(device_id, metric_name, value)

    # =========================================================================
    # COMMAND HANDLING
    # =========================================================================

    def _handle_node_command(self, payload_data: bytes) -> None:
        """Handle NCMD message."""
        try:
            payload = SparkplugPayload.from_protobuf(payload_data)

            for metric in payload.metrics:
                # Handle rebirth request
                if metric.name == "Node Control/Rebirth" and metric.value:
                    logger.info("Rebirth requested")
                    asyncio.create_task(self._rebirth())

                # Notify callbacks
                for callback in self._on_command_callbacks:
                    try:
                        callback(None, metric.name, metric)
                    except Exception as e:
                        logger.error(f"Command callback error: {e}")

        except Exception as e:
            logger.error(f"Failed to handle NCMD: {e}")

    def _handle_device_command(self, device_id: str, payload_data: bytes) -> None:
        """Handle DCMD message."""
        try:
            payload = SparkplugPayload.from_protobuf(payload_data)

            for metric in payload.metrics:
                # Update device metric if writable
                self.update_device_metric(device_id, metric.name, metric.value)

                # Notify callbacks
                for callback in self._on_command_callbacks:
                    try:
                        callback(device_id, metric.name, metric)
                    except Exception as e:
                        logger.error(f"Command callback error: {e}")

                # Forward to ROS2 if configured
                device = self._devices.get(device_id)
                if device and self.ros2_bridge:
                    ros2_topic = device.ros2_topics.get(f"{metric.name}/cmd")
                    if ros2_topic:
                        asyncio.create_task(
                            self.ros2_bridge.publish(
                                ros2_topic,
                                'std_msgs/msg/String',
                                {'data': str(metric.value)}
                            )
                        )

        except Exception as e:
            logger.error(f"Failed to handle DCMD: {e}")

    def _handle_state(self, scada_id: str, payload: bytes) -> None:
        """Handle STATE message from SCADA host."""
        try:
            state = payload.decode('utf-8')
            is_online = state.upper() == "ONLINE"

            logger.info(f"SCADA host {scada_id} state: {state}")

            # Notify callbacks
            for callback in self._on_state_callbacks:
                try:
                    callback(scada_id, is_online)
                except Exception as e:
                    logger.error(f"State callback error: {e}")

            # If SCADA comes online, send rebirth
            if is_online:
                asyncio.create_task(self._rebirth())

        except Exception as e:
            logger.error(f"Failed to handle STATE: {e}")

    async def _rebirth(self) -> None:
        """Perform rebirth sequence."""
        logger.info("Performing rebirth sequence")

        # Send node death (graceful)
        self._node_online = False

        # Send device deaths
        for device in self._devices.values():
            if device.is_online:
                await self.send_device_death(device.device_id)

        await asyncio.sleep(0.1)

        # Send node birth
        await self.send_node_birth()

        # Send device births
        for device in self._devices.values():
            await self.send_device_birth(device.device_id)

    # =========================================================================
    # CALLBACKS
    # =========================================================================

    def on_command(
        self,
        callback: Callable[[Optional[str], str, SparkplugMetric], None]
    ) -> None:
        """
        Register command callback.

        Args:
            callback: Function(device_id, metric_name, metric)
                      device_id is None for node commands
        """
        self._on_command_callbacks.append(callback)

    def on_state(self, callback: Callable[[str, bool], None]) -> None:
        """Register SCADA state callback."""
        self._on_state_callbacks.append(callback)

    # =========================================================================
    # RUNTIME
    # =========================================================================

    async def start(self) -> bool:
        """
        Start the Sparkplug B client.

        Connects, sends births, and starts update loop.
        """
        if self._running:
            return True

        # Connect to broker
        if not await self.connect():
            return False

        self._running = True

        # Send node birth
        await self.send_node_birth()

        # Send device births
        for device in self._devices.values():
            await self.send_device_birth(device.device_id)

        # Start ROS2 bridge
        if self.ros2_bridge:
            await self.start_ros2_bridge()

        # Start update loop
        self._update_task = asyncio.create_task(self._update_loop())

        logger.info("Sparkplug B client started")
        return True

    async def stop(self) -> None:
        """Stop the Sparkplug B client."""
        await self.disconnect()
        logger.info("Sparkplug B client stopped")

    async def _update_loop(self) -> None:
        """Periodic update loop for publishing data."""
        while self._running:
            try:
                # Publish device data
                for device_id in self._devices:
                    await self.send_device_data(device_id)
            except Exception as e:
                logger.error(f"Update loop error: {e}")

            await asyncio.sleep(self._update_interval)

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get client status summary."""
        return {
            'broker_host': self.broker_host,
            'broker_port': self.broker_port,
            'group_id': self.group_id,
            'edge_node_id': self.edge_node_id,
            'connected': self._connected,
            'node_online': self._node_online,
            'seq': self._seq,
            'bd_seq': self._bd_seq,
            'device_count': len(self._devices),
            'devices': [d.to_dict() for d in self._devices.values()],
            'topic_prefix': f"{self.SPARKPLUG_VERSION}/{self.group_id}",
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_sparkplug_client: Optional[SparkplugBClient] = None


def get_sparkplug_client() -> SparkplugBClient:
    """Get or create the Sparkplug B client instance."""
    global _sparkplug_client
    if _sparkplug_client is None:
        _sparkplug_client = SparkplugBClient()
    return _sparkplug_client


async def init_sparkplug_client(
    broker_host: str = "localhost",
    broker_port: int = 1883,
    group_id: str = "LegoMCP",
    edge_node_id: str = "EdgeNode1",
    ros2_bridge: Optional[Any] = None,
    auto_register_devices: bool = True,
) -> SparkplugBClient:
    """
    Initialize and start the Sparkplug B client.

    Args:
        broker_host: MQTT broker hostname
        broker_port: MQTT broker port
        group_id: Sparkplug group ID
        edge_node_id: Edge node identifier
        ros2_bridge: ROS2 bridge for equipment data
        auto_register_devices: Auto-register default devices

    Returns:
        Started SparkplugBClient instance
    """
    global _sparkplug_client
    _sparkplug_client = SparkplugBClient(
        broker_host=broker_host,
        broker_port=broker_port,
        group_id=group_id,
        edge_node_id=edge_node_id,
        ros2_bridge=ros2_bridge,
    )

    # Auto-register devices
    if auto_register_devices:
        # GRBL CNC
        grbl = _sparkplug_client.register_device(
            device_id='grbl_cnc_1',
            display_name='GRBL CNC Router',
            description='3-axis CNC router with GRBL controller',
            equipment_type='CNC',
            ros2_topics={
                'Position/X': '/grbl/grbl_cnc_1/position_x',
                'Position/Y': '/grbl/grbl_cnc_1/position_y',
                'Position/Z': '/grbl/grbl_cnc_1/position_z',
                'Status': '/grbl/grbl_cnc_1/status',
                'FeedRate': '/grbl/grbl_cnc_1/feed_rate',
                'SpindleSpeed': '/grbl/grbl_cnc_1/spindle_speed',
            }
        )
        grbl.add_metric('Position/X', 0.0, alias=200)
        grbl.add_metric('Position/Y', 0.0, alias=201)
        grbl.add_metric('Position/Z', 0.0, alias=202)
        grbl.add_metric('Status', 'Idle', alias=203)
        grbl.add_metric('FeedRate', 0.0, alias=204)
        grbl.add_metric('SpindleSpeed', 0.0, alias=205)

        # Bambu Lab Printer
        bambu = _sparkplug_client.register_device(
            device_id='bambu_x1c_1',
            display_name='Bambu Lab X1 Carbon',
            description='High-speed 3D printer',
            equipment_type='3DPrinter',
            ros2_topics={
                'NozzleTemp': '/bambu/bambu_x1c_1/nozzle_temp',
                'BedTemp': '/bambu/bambu_x1c_1/bed_temp',
                'PrintProgress': '/bambu/bambu_x1c_1/progress',
                'Status': '/bambu/bambu_x1c_1/status',
            }
        )
        bambu.add_metric('NozzleTemp', 0.0, alias=300)
        bambu.add_metric('BedTemp', 0.0, alias=301)
        bambu.add_metric('PrintProgress', 0.0, alias=302)
        bambu.add_metric('Status', 'Idle', alias=303)
        bambu.add_metric('CurrentLayer', 0, alias=304)
        bambu.add_metric('TotalLayers', 0, alias=305)

        # Robot
        robot = _sparkplug_client.register_device(
            device_id='ned2_1',
            display_name='Niryo Ned2 Robot',
            description='6-axis collaborative robot',
            equipment_type='Robot',
            ros2_topics={
                'Joint1': '/ned2/joint_states/j1',
                'Joint2': '/ned2/joint_states/j2',
                'Joint3': '/ned2/joint_states/j3',
                'Joint4': '/ned2/joint_states/j4',
                'Joint5': '/ned2/joint_states/j5',
                'Joint6': '/ned2/joint_states/j6',
                'Status': '/ned2/robot_state',
            }
        )
        for i in range(1, 7):
            robot.add_metric(f'Joint{i}', 0.0, alias=400 + i)
        robot.add_metric('Status', 'Idle', alias=407)
        robot.add_metric('GripperState', 'Open', alias=408)

    await _sparkplug_client.start()
    return _sparkplug_client
