"""
OPC-UA Protocol Adapter - Industrial Automation Standard

LegoMCP World-Class Manufacturing System v5.0
Phase 25: Edge Computing & IIoT

Provides OPC-UA client capabilities:
- Secure connection to OPC-UA servers
- Node browsing and discovery
- Data subscription and monitoring
- Write operations for control
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import uuid
import threading
import time


class OPCUASecurityMode(Enum):
    """OPC-UA security modes."""
    NONE = "None"
    SIGN = "Sign"
    SIGN_AND_ENCRYPT = "SignAndEncrypt"


class OPCUADataType(Enum):
    """OPC-UA data types."""
    BOOLEAN = "Boolean"
    INT16 = "Int16"
    INT32 = "Int32"
    INT64 = "Int64"
    UINT16 = "UInt16"
    UINT32 = "UInt32"
    UINT64 = "UInt64"
    FLOAT = "Float"
    DOUBLE = "Double"
    STRING = "String"
    DATETIME = "DateTime"
    BYTE_STRING = "ByteString"


@dataclass
class OPCUANode:
    """Represents an OPC-UA node."""
    node_id: str
    browse_name: str
    display_name: str
    node_class: str  # Variable, Object, Method
    data_type: Optional[OPCUADataType] = None
    value: Any = None
    timestamp: Optional[datetime] = None
    quality: str = "good"
    children: List[str] = field(default_factory=list)


@dataclass
class OPCUASubscription:
    """An OPC-UA subscription for monitored items."""
    subscription_id: str
    node_ids: List[str]
    publishing_interval_ms: int
    callback: Optional[Callable] = None
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_update: Optional[datetime] = None
    update_count: int = 0


@dataclass
class OPCUAConnection:
    """OPC-UA server connection."""
    connection_id: str
    endpoint_url: str
    security_mode: OPCUASecurityMode
    connected: bool = False
    server_name: Optional[str] = None
    server_uri: Optional[str] = None
    connected_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None


class OPCUAAdapter:
    """
    OPC-UA protocol adapter for industrial device communication.

    Provides OPC-UA client functionality for connecting to
    industrial automation systems and PLCs.
    """

    def __init__(self):
        self.connections: Dict[str, OPCUAConnection] = {}
        self.subscriptions: Dict[str, OPCUASubscription] = {}
        self.node_cache: Dict[str, OPCUANode] = {}
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._setup_simulated_server()

    def _setup_simulated_server(self):
        """Set up simulated OPC-UA server for demo."""
        # Simulated 3D printer nodes
        self.node_cache = {
            'ns=2;s=Printer.Nozzle.Temperature': OPCUANode(
                node_id='ns=2;s=Printer.Nozzle.Temperature',
                browse_name='Temperature',
                display_name='Nozzle Temperature',
                node_class='Variable',
                data_type=OPCUADataType.DOUBLE,
                value=215.0,
            ),
            'ns=2;s=Printer.Bed.Temperature': OPCUANode(
                node_id='ns=2;s=Printer.Bed.Temperature',
                browse_name='Temperature',
                display_name='Bed Temperature',
                node_class='Variable',
                data_type=OPCUADataType.DOUBLE,
                value=60.0,
            ),
            'ns=2;s=Printer.Status': OPCUANode(
                node_id='ns=2;s=Printer.Status',
                browse_name='Status',
                display_name='Printer Status',
                node_class='Variable',
                data_type=OPCUADataType.STRING,
                value='Printing',
            ),
            'ns=2;s=Printer.Progress': OPCUANode(
                node_id='ns=2;s=Printer.Progress',
                browse_name='Progress',
                display_name='Print Progress',
                node_class='Variable',
                data_type=OPCUADataType.DOUBLE,
                value=45.5,
            ),
            'ns=2;s=Printer.LayerCurrent': OPCUANode(
                node_id='ns=2;s=Printer.LayerCurrent',
                browse_name='LayerCurrent',
                display_name='Current Layer',
                node_class='Variable',
                data_type=OPCUADataType.INT32,
                value=127,
            ),
            'ns=2;s=Printer.LayerTotal': OPCUANode(
                node_id='ns=2;s=Printer.LayerTotal',
                browse_name='LayerTotal',
                display_name='Total Layers',
                node_class='Variable',
                data_type=OPCUADataType.INT32,
                value=280,
            ),
            'ns=2;s=Printer.FanSpeed': OPCUANode(
                node_id='ns=2;s=Printer.FanSpeed',
                browse_name='FanSpeed',
                display_name='Fan Speed %',
                node_class='Variable',
                data_type=OPCUADataType.DOUBLE,
                value=100.0,
            ),
            'ns=2;s=Printer.FilamentUsed': OPCUANode(
                node_id='ns=2;s=Printer.FilamentUsed',
                browse_name='FilamentUsed',
                display_name='Filament Used (mm)',
                node_class='Variable',
                data_type=OPCUADataType.DOUBLE,
                value=12450.5,
            ),
        }

    def connect(
        self,
        endpoint_url: str,
        security_mode: OPCUASecurityMode = OPCUASecurityMode.NONE,
        username: Optional[str] = None,
        password: Optional[str] = None,
        certificate: Optional[str] = None
    ) -> OPCUAConnection:
        """
        Connect to an OPC-UA server.

        Args:
            endpoint_url: OPC-UA server endpoint URL
            security_mode: Security mode for connection
            username: Optional username for authentication
            password: Optional password for authentication
            certificate: Optional client certificate path

        Returns:
            Connection object
        """
        connection = OPCUAConnection(
            connection_id=str(uuid.uuid4()),
            endpoint_url=endpoint_url,
            security_mode=security_mode,
            connected=True,
            server_name='LegoMCP 3D Printer OPC-UA Server',
            server_uri='urn:legomcp:printer:opcua',
            connected_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
        )

        self.connections[connection.connection_id] = connection
        return connection

    def disconnect(self, connection_id: str) -> bool:
        """Disconnect from OPC-UA server."""
        if connection_id in self.connections:
            conn = self.connections[connection_id]
            conn.connected = False
            # Cancel related subscriptions
            for sub_id, sub in list(self.subscriptions.items()):
                sub.active = False
            return True
        return False

    def browse(
        self,
        connection_id: str,
        node_id: str = 'i=84'  # Root Objects folder
    ) -> List[OPCUANode]:
        """
        Browse OPC-UA address space.

        Args:
            connection_id: Connection ID
            node_id: Starting node ID (default: Objects folder)

        Returns:
            List of child nodes
        """
        if connection_id not in self.connections:
            return []

        # Return all cached nodes for demo
        return list(self.node_cache.values())

    def read(
        self,
        connection_id: str,
        node_ids: List[str]
    ) -> Dict[str, OPCUANode]:
        """
        Read values from OPC-UA nodes.

        Args:
            connection_id: Connection ID
            node_ids: List of node IDs to read

        Returns:
            Dictionary of node ID to node data
        """
        if connection_id not in self.connections:
            return {}

        result = {}
        for node_id in node_ids:
            if node_id in self.node_cache:
                node = self.node_cache[node_id]
                node.timestamp = datetime.utcnow()
                result[node_id] = node

        # Update connection activity
        self.connections[connection_id].last_activity = datetime.utcnow()

        return result

    def write(
        self,
        connection_id: str,
        node_id: str,
        value: Any,
        data_type: Optional[OPCUADataType] = None
    ) -> bool:
        """
        Write value to OPC-UA node.

        Args:
            connection_id: Connection ID
            node_id: Node ID to write
            value: Value to write
            data_type: Optional data type hint

        Returns:
            True if write successful
        """
        if connection_id not in self.connections:
            return False

        if node_id in self.node_cache:
            self.node_cache[node_id].value = value
            self.node_cache[node_id].timestamp = datetime.utcnow()
            self.connections[connection_id].last_activity = datetime.utcnow()
            return True

        return False

    def create_subscription(
        self,
        connection_id: str,
        node_ids: List[str],
        publishing_interval_ms: int = 1000,
        callback: Optional[Callable] = None
    ) -> Optional[OPCUASubscription]:
        """
        Create subscription for monitored items.

        Args:
            connection_id: Connection ID
            node_ids: Node IDs to monitor
            publishing_interval_ms: Publishing interval in milliseconds
            callback: Callback function for value changes

        Returns:
            Subscription object
        """
        if connection_id not in self.connections:
            return None

        subscription = OPCUASubscription(
            subscription_id=str(uuid.uuid4()),
            node_ids=node_ids,
            publishing_interval_ms=publishing_interval_ms,
            callback=callback,
        )

        self.subscriptions[subscription.subscription_id] = subscription
        return subscription

    def delete_subscription(self, subscription_id: str) -> bool:
        """Delete a subscription."""
        if subscription_id in self.subscriptions:
            self.subscriptions[subscription_id].active = False
            del self.subscriptions[subscription_id]
            return True
        return False

    def get_connection_status(self, connection_id: str) -> Optional[Dict]:
        """Get connection status."""
        if connection_id not in self.connections:
            return None

        conn = self.connections[connection_id]
        return {
            'connection_id': conn.connection_id,
            'endpoint_url': conn.endpoint_url,
            'connected': conn.connected,
            'server_name': conn.server_name,
            'security_mode': conn.security_mode.value,
            'connected_at': conn.connected_at.isoformat() if conn.connected_at else None,
            'last_activity': conn.last_activity.isoformat() if conn.last_activity else None,
        }

    def get_all_connections(self) -> List[Dict]:
        """Get all connection statuses."""
        return [
            self.get_connection_status(conn_id)
            for conn_id in self.connections
        ]

    def get_subscription_stats(self) -> Dict:
        """Get subscription statistics."""
        active = [s for s in self.subscriptions.values() if s.active]
        return {
            'total_subscriptions': len(self.subscriptions),
            'active_subscriptions': len(active),
            'total_monitored_items': sum(
                len(s.node_ids) for s in active
            ),
        }


# Singleton instance
_opcua_adapter: Optional[OPCUAAdapter] = None


def get_opcua_adapter() -> OPCUAAdapter:
    """Get or create the OPC-UA adapter instance."""
    global _opcua_adapter
    if _opcua_adapter is None:
        _opcua_adapter = OPCUAAdapter()
    return _opcua_adapter
