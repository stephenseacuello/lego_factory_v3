"""
Sparkplug B MQTT Protocol Implementation for LEGO MCP

Implements Sparkplug B specification (v3.0) for SCADA/IIoT integration:
- Birth/Death certificates for state awareness
- Metric encoding with Protobuf
- Sequence number management
- Rebirth handling
- Host application support

Industry 4.0/5.0 Architecture - ISA-95 Level 3-4 Integration

Sparkplug B Topic Namespace:
    spBv1.0/GROUP_ID/NBIRTH/EDGE_NODE_ID
    spBv1.0/GROUP_ID/NDEATH/EDGE_NODE_ID
    spBv1.0/GROUP_ID/DBIRTH/EDGE_NODE_ID/DEVICE_ID
    spBv1.0/GROUP_ID/DDEATH/EDGE_NODE_ID/DEVICE_ID
    spBv1.0/GROUP_ID/NDATA/EDGE_NODE_ID
    spBv1.0/GROUP_ID/DDATA/EDGE_NODE_ID/DEVICE_ID
    spBv1.0/GROUP_ID/NCMD/EDGE_NODE_ID
    spBv1.0/GROUP_ID/DCMD/EDGE_NODE_ID/DEVICE_ID
    spBv1.0/GROUP_ID/STATE/HOST_APPLICATION_ID

LEGO MCP Manufacturing System v7.0
"""

import struct
import time
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Union
import threading


class SparkplugDataType(IntEnum):
    """Sparkplug B data types."""
    Unknown = 0
    Int8 = 1
    Int16 = 2
    Int32 = 3
    Int64 = 4
    UInt8 = 5
    UInt16 = 6
    UInt32 = 7
    UInt64 = 8
    Float = 9
    Double = 10
    Boolean = 11
    String = 12
    DateTime = 13
    Text = 14
    UUID = 15
    DataSet = 16
    Bytes = 17
    File = 18
    Template = 19


class SparkplugMetricQuality(IntEnum):
    """Metric quality codes."""
    GOOD = 192
    BAD = 0
    STALE = 24


@dataclass
class SparkplugMetric:
    """Sparkplug B Metric definition."""
    name: str
    alias: Optional[int] = None  # For bandwidth optimization
    timestamp: int = 0  # Milliseconds since epoch
    datatype: SparkplugDataType = SparkplugDataType.String
    is_historical: bool = False
    is_transient: bool = False
    is_null: bool = False
    value: Any = None
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        d = {
            "name": self.name,
            "timestamp": self.timestamp or int(time.time() * 1000),
            "datatype": self.datatype.value,
            "value": self.value,
        }
        if self.alias is not None:
            d["alias"] = self.alias
        if self.is_historical:
            d["is_historical"] = True
        if self.is_transient:
            d["is_transient"] = True
        if self.is_null:
            d["is_null"] = True
        if self.properties:
            d["properties"] = self.properties
        return d


@dataclass
class SparkplugPayload:
    """Sparkplug B Payload."""
    timestamp: int = 0  # Milliseconds since epoch
    metrics: List[SparkplugMetric] = field(default_factory=list)
    seq: int = 0  # Sequence number (0-255)
    uuid: Optional[str] = None
    body: Optional[bytes] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp or int(time.time() * 1000),
            "metrics": [m.to_dict() for m in self.metrics],
            "seq": self.seq,
        }

    def to_json(self) -> str:
        """Serialize to JSON (simplified - production would use Protobuf)."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'SparkplugPayload':
        """Deserialize from JSON."""
        data = json.loads(json_str)
        payload = cls(
            timestamp=data.get("timestamp", 0),
            seq=data.get("seq", 0),
        )
        for m in data.get("metrics", []):
            metric = SparkplugMetric(
                name=m["name"],
                alias=m.get("alias"),
                timestamp=m.get("timestamp", 0),
                datatype=SparkplugDataType(m.get("datatype", 12)),
                value=m.get("value"),
            )
            payload.metrics.append(metric)
        return payload


class SparkplugBEdgeNode:
    """
    Sparkplug B Edge Node.

    Manages:
    - Node birth/death certificates
    - Device birth/death certificates
    - Metric definitions and updates
    - Sequence number management
    - Rebirth handling

    Usage:
        node = SparkplugBEdgeNode(
            group_id="LEGO_MCP",
            edge_node_id="factory_cell_1",
            mqtt_client=mqtt_client,
        )
        node.add_device("bantam_cnc")
        node.add_metric("bantam_cnc", "execution", SparkplugDataType.String, "ACTIVE")
        node.publish_birth()
        node.update_metric("bantam_cnc", "execution", "STOPPED")
    """

    def __init__(
        self,
        group_id: str,
        edge_node_id: str,
        mqtt_client: Any,  # paho.mqtt.client.Client or compatible
        primary_host_id: Optional[str] = None,
        bdseq_persistence_file: Optional[str] = None,
    ):
        """
        Initialize Sparkplug B Edge Node.

        Args:
            group_id: Sparkplug group ID
            edge_node_id: Unique edge node identifier
            mqtt_client: MQTT client instance
            primary_host_id: Primary host application ID
            bdseq_persistence_file: File to persist birth/death sequence
        """
        self.group_id = group_id
        self.edge_node_id = edge_node_id
        self.mqtt = mqtt_client
        self.primary_host_id = primary_host_id

        # Sequence numbers
        self._seq = 0  # 0-255, increments per message
        self._bdseq = 0  # Birth/death sequence
        self._bdseq_file = bdseq_persistence_file

        # Devices and metrics
        self._devices: Dict[str, Dict[str, SparkplugMetric]] = {}  # device_id -> {metric_name -> metric}
        self._node_metrics: Dict[str, SparkplugMetric] = {}  # Node-level metrics
        self._alias_counter = 0
        self._aliases: Dict[str, int] = {}  # metric_name -> alias

        # State
        self._connected = False
        self._born = False
        self._lock = threading.RLock()

        # Callbacks
        self._command_handlers: Dict[str, Callable] = {}

        # Load persisted bdseq
        self._load_bdseq()

    def _load_bdseq(self):
        """Load birth/death sequence from persistence."""
        if self._bdseq_file:
            try:
                with open(self._bdseq_file, 'r') as f:
                    self._bdseq = int(f.read().strip()) + 1
            except Exception:
                self._bdseq = 0

    def _save_bdseq(self):
        """Save birth/death sequence to persistence."""
        if self._bdseq_file:
            try:
                with open(self._bdseq_file, 'w') as f:
                    f.write(str(self._bdseq))
            except Exception:
                pass

    def _next_seq(self) -> int:
        """Get next sequence number (0-255)."""
        with self._lock:
            seq = self._seq
            self._seq = (self._seq + 1) % 256
            return seq

    def _get_alias(self, metric_name: str) -> int:
        """Get or create alias for metric."""
        if metric_name not in self._aliases:
            self._alias_counter += 1
            self._aliases[metric_name] = self._alias_counter
        return self._aliases[metric_name]

    def _topic(self, message_type: str, device_id: Optional[str] = None) -> str:
        """Generate Sparkplug topic."""
        if device_id:
            return f"spBv1.0/{self.group_id}/{message_type}/{self.edge_node_id}/{device_id}"
        return f"spBv1.0/{self.group_id}/{message_type}/{self.edge_node_id}"

    def add_device(self, device_id: str):
        """Add a device to this edge node."""
        with self._lock:
            if device_id not in self._devices:
                self._devices[device_id] = {}

    def remove_device(self, device_id: str):
        """Remove a device (publishes death certificate)."""
        with self._lock:
            if device_id in self._devices:
                self._publish_device_death(device_id)
                del self._devices[device_id]

    def add_metric(
        self,
        device_id: Optional[str],
        name: str,
        datatype: SparkplugDataType,
        initial_value: Any,
        properties: Optional[Dict] = None,
    ):
        """
        Add a metric definition.

        Args:
            device_id: Device ID (None for node-level metric)
            name: Metric name
            datatype: Sparkplug data type
            initial_value: Initial metric value
            properties: Optional metric properties
        """
        metric = SparkplugMetric(
            name=name,
            alias=self._get_alias(f"{device_id or 'node'}_{name}"),
            datatype=datatype,
            value=initial_value,
            timestamp=int(time.time() * 1000),
            properties=properties or {},
        )

        with self._lock:
            if device_id:
                if device_id not in self._devices:
                    self._devices[device_id] = {}
                self._devices[device_id][name] = metric
            else:
                self._node_metrics[name] = metric

    def update_metric(
        self,
        device_id: Optional[str],
        name: str,
        value: Any,
        timestamp: Optional[int] = None,
    ):
        """
        Update a metric value.

        Args:
            device_id: Device ID (None for node-level)
            name: Metric name
            value: New value
            timestamp: Optional timestamp (ms since epoch)
        """
        with self._lock:
            if device_id:
                metrics = self._devices.get(device_id, {})
            else:
                metrics = self._node_metrics

            if name in metrics:
                metrics[name].value = value
                metrics[name].timestamp = timestamp or int(time.time() * 1000)

                # Publish DDATA or NDATA
                if self._born:
                    self._publish_data(device_id, [metrics[name]])

    def _publish_data(self, device_id: Optional[str], metrics: List[SparkplugMetric]):
        """Publish data message."""
        payload = SparkplugPayload(
            timestamp=int(time.time() * 1000),
            seq=self._next_seq(),
            metrics=metrics,
        )

        topic = self._topic("DDATA" if device_id else "NDATA", device_id)
        self.mqtt.publish(topic, payload.to_json(), qos=0, retain=False)

    def publish_birth(self):
        """Publish node birth certificate and all device births."""
        with self._lock:
            self._bdseq += 1
            self._save_bdseq()

            # Node birth
            node_metrics = list(self._node_metrics.values())
            node_metrics.append(SparkplugMetric(
                name="bdSeq",
                datatype=SparkplugDataType.UInt64,
                value=self._bdseq,
            ))

            payload = SparkplugPayload(
                timestamp=int(time.time() * 1000),
                seq=self._next_seq(),
                metrics=node_metrics,
            )

            topic = self._topic("NBIRTH")
            self.mqtt.publish(topic, payload.to_json(), qos=0, retain=False)

            # Device births
            for device_id, metrics in self._devices.items():
                self._publish_device_birth(device_id)

            self._born = True

    def _publish_device_birth(self, device_id: str):
        """Publish device birth certificate."""
        metrics = list(self._devices.get(device_id, {}).values())

        payload = SparkplugPayload(
            timestamp=int(time.time() * 1000),
            seq=self._next_seq(),
            metrics=metrics,
        )

        topic = self._topic("DBIRTH", device_id)
        self.mqtt.publish(topic, payload.to_json(), qos=0, retain=False)

    def _publish_device_death(self, device_id: str):
        """Publish device death certificate."""
        payload = SparkplugPayload(
            timestamp=int(time.time() * 1000),
            seq=self._next_seq(),
        )

        topic = self._topic("DDEATH", device_id)
        self.mqtt.publish(topic, payload.to_json(), qos=0, retain=False)

    def publish_death(self):
        """Publish node death certificate (via LWT)."""
        # Node death is typically set as MQTT Last Will and Testament
        payload = SparkplugPayload(
            timestamp=int(time.time() * 1000),
            seq=0,  # Death doesn't use seq
            metrics=[SparkplugMetric(
                name="bdSeq",
                datatype=SparkplugDataType.UInt64,
                value=self._bdseq,
            )],
        )
        return self._topic("NDEATH"), payload.to_json()

    def get_death_lwt(self) -> tuple[str, str, int, bool]:
        """
        Get Last Will and Testament for MQTT connection.

        Returns:
            Tuple of (topic, payload, qos, retain)
        """
        topic, payload = self.publish_death()
        return topic, payload, 0, False

    def handle_command(self, topic: str, payload_str: str):
        """
        Handle incoming command message.

        Args:
            topic: MQTT topic
            payload_str: Payload JSON string
        """
        # Parse topic
        parts = topic.split("/")
        if len(parts) < 4:
            return

        msg_type = parts[2]  # NCMD or DCMD
        device_id = parts[4] if len(parts) > 4 else None

        payload = SparkplugPayload.from_json(payload_str)

        for metric in payload.metrics:
            handler_key = f"{device_id or 'node'}_{metric.name}"
            if handler_key in self._command_handlers:
                self._command_handlers[handler_key](metric.value)
            elif msg_type == "NCMD" and metric.name == "Node Control/Rebirth":
                if metric.value:
                    self.publish_birth()

    def register_command_handler(
        self,
        device_id: Optional[str],
        metric_name: str,
        handler: Callable[[Any], None],
    ):
        """
        Register a handler for command metrics.

        Args:
            device_id: Device ID (None for node-level)
            metric_name: Metric name to handle
            handler: Callback function
        """
        key = f"{device_id or 'node'}_{metric_name}"
        self._command_handlers[key] = handler

    def get_subscription_topics(self) -> List[str]:
        """Get topics to subscribe to for commands."""
        return [
            f"spBv1.0/{self.group_id}/NCMD/{self.edge_node_id}",
            f"spBv1.0/{self.group_id}/DCMD/{self.edge_node_id}/+",
        ]


class SparkplugBHostApplication:
    """
    Sparkplug B Host Application (SCADA/MES).

    Subscribes to all edge node data and manages state awareness.

    Usage:
        host = SparkplugBHostApplication(
            host_id="lego_mcp_scada",
            group_id="LEGO_MCP",
            mqtt_client=mqtt_client,
        )
        host.set_data_callback(on_data_received)
        host.publish_state(online=True)
    """

    def __init__(
        self,
        host_id: str,
        group_id: str,
        mqtt_client: Any,
    ):
        """
        Initialize Host Application.

        Args:
            host_id: Host application identifier
            group_id: Sparkplug group ID
            mqtt_client: MQTT client instance
        """
        self.host_id = host_id
        self.group_id = group_id
        self.mqtt = mqtt_client

        # State tracking
        self._edge_nodes: Dict[str, Dict] = {}  # edge_node_id -> state
        self._devices: Dict[str, Dict[str, Dict]] = {}  # edge_node_id -> device_id -> metrics
        self._lock = threading.RLock()

        # Callbacks
        self._data_callback: Optional[Callable] = None
        self._birth_callback: Optional[Callable] = None
        self._death_callback: Optional[Callable] = None

    def publish_state(self, online: bool):
        """Publish host application state."""
        state = "ONLINE" if online else "OFFLINE"
        topic = f"spBv1.0/{self.group_id}/STATE/{self.host_id}"
        self.mqtt.publish(topic, state, qos=1, retain=True)

    def get_state_lwt(self) -> tuple[str, str, int, bool]:
        """Get Last Will and Testament for offline state."""
        topic = f"spBv1.0/{self.group_id}/STATE/{self.host_id}"
        return topic, "OFFLINE", 1, True

    def set_data_callback(self, callback: Callable[[str, str, List[SparkplugMetric]], None]):
        """Set callback for data updates."""
        self._data_callback = callback

    def set_birth_callback(self, callback: Callable[[str, Optional[str]], None]):
        """Set callback for birth certificates."""
        self._birth_callback = callback

    def set_death_callback(self, callback: Callable[[str, Optional[str]], None]):
        """Set callback for death certificates."""
        self._death_callback = callback

    def handle_message(self, topic: str, payload_str: str):
        """Handle incoming Sparkplug message."""
        parts = topic.split("/")
        if len(parts) < 4:
            return

        msg_type = parts[2]
        edge_node_id = parts[3]
        device_id = parts[4] if len(parts) > 4 else None

        if msg_type in ("NBIRTH", "DBIRTH"):
            payload = SparkplugPayload.from_json(payload_str)
            self._handle_birth(edge_node_id, device_id, payload)

        elif msg_type in ("NDEATH", "DDEATH"):
            self._handle_death(edge_node_id, device_id)

        elif msg_type in ("NDATA", "DDATA"):
            payload = SparkplugPayload.from_json(payload_str)
            self._handle_data(edge_node_id, device_id, payload)

    def _handle_birth(self, edge_node_id: str, device_id: Optional[str], payload: SparkplugPayload):
        """Handle birth certificate."""
        with self._lock:
            if device_id:
                if edge_node_id not in self._devices:
                    self._devices[edge_node_id] = {}
                self._devices[edge_node_id][device_id] = {
                    m.name: m for m in payload.metrics
                }
            else:
                self._edge_nodes[edge_node_id] = {
                    "born": True,
                    "timestamp": payload.timestamp,
                    "metrics": {m.name: m for m in payload.metrics},
                }

        if self._birth_callback:
            self._birth_callback(edge_node_id, device_id)

    def _handle_death(self, edge_node_id: str, device_id: Optional[str]):
        """Handle death certificate."""
        with self._lock:
            if device_id:
                if edge_node_id in self._devices and device_id in self._devices[edge_node_id]:
                    del self._devices[edge_node_id][device_id]
            else:
                if edge_node_id in self._edge_nodes:
                    self._edge_nodes[edge_node_id]["born"] = False
                # Also mark all devices as dead
                if edge_node_id in self._devices:
                    del self._devices[edge_node_id]

        if self._death_callback:
            self._death_callback(edge_node_id, device_id)

    def _handle_data(self, edge_node_id: str, device_id: Optional[str], payload: SparkplugPayload):
        """Handle data message."""
        with self._lock:
            if device_id:
                if edge_node_id in self._devices and device_id in self._devices[edge_node_id]:
                    for m in payload.metrics:
                        self._devices[edge_node_id][device_id][m.name] = m
            else:
                if edge_node_id in self._edge_nodes:
                    for m in payload.metrics:
                        self._edge_nodes[edge_node_id]["metrics"][m.name] = m

        if self._data_callback:
            self._data_callback(edge_node_id, device_id, payload.metrics)

    def get_subscription_topics(self) -> List[str]:
        """Get topics to subscribe to."""
        return [
            f"spBv1.0/{self.group_id}/NBIRTH/+",
            f"spBv1.0/{self.group_id}/NDEATH/+",
            f"spBv1.0/{self.group_id}/DBIRTH/+/+",
            f"spBv1.0/{self.group_id}/DDEATH/+/+",
            f"spBv1.0/{self.group_id}/NDATA/+",
            f"spBv1.0/{self.group_id}/DDATA/+/+",
        ]

    def request_rebirth(self, edge_node_id: str):
        """Request rebirth from an edge node."""
        payload = SparkplugPayload(
            timestamp=int(time.time() * 1000),
            seq=0,
            metrics=[SparkplugMetric(
                name="Node Control/Rebirth",
                datatype=SparkplugDataType.Boolean,
                value=True,
            )],
        )
        topic = f"spBv1.0/{self.group_id}/NCMD/{edge_node_id}"
        self.mqtt.publish(topic, payload.to_json(), qos=0, retain=False)

    def get_edge_node_state(self, edge_node_id: str) -> Optional[Dict]:
        """Get state of an edge node."""
        return self._edge_nodes.get(edge_node_id)

    def get_device_metrics(self, edge_node_id: str, device_id: str) -> Optional[Dict]:
        """Get metrics for a device."""
        devices = self._devices.get(edge_node_id, {})
        return devices.get(device_id)
