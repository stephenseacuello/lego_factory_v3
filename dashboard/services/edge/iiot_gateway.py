"""
IIoT Gateway - Edge Computing & Protocol Integration

LegoMCP World-Class Manufacturing System v5.0
Phase 25: Edge Computing & IIoT Gateway

Edge processing and protocol translation:
- OPC-UA, MQTT, MTConnect, Modbus support
- Local edge processing
- Offline operation
- Cloud synchronization
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class Protocol(str, Enum):
    """Supported IIoT protocols."""
    OPCUA = "opcua"
    MQTT = "mqtt"
    MTCONNECT = "mtconnect"
    MODBUS = "modbus"
    HTTP = "http"


class ConnectionStatus(str, Enum):
    """Device connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"


@dataclass
class DeviceConnection:
    """Connection to an IIoT device."""
    connection_id: str
    device_id: str
    device_name: str
    protocol: Protocol

    # Connection details
    host: str
    port: int
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED

    # Timestamps
    connected_at: Optional[datetime] = None
    last_data_at: Optional[datetime] = None

    # Statistics
    messages_received: int = 0
    errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'connection_id': self.connection_id,
            'device_id': self.device_id,
            'device_name': self.device_name,
            'protocol': self.protocol.value,
            'host': self.host,
            'port': self.port,
            'status': self.status.value,
            'connected_at': self.connected_at.isoformat() if self.connected_at else None,
            'last_data_at': self.last_data_at.isoformat() if self.last_data_at else None,
            'messages_received': self.messages_received,
        }


@dataclass
class UnifiedDataPoint:
    """Unified data model for all protocols."""
    data_id: str
    device_id: str
    timestamp: datetime
    source_protocol: Protocol

    # Data
    tag_name: str
    value: Any
    unit: str = ""
    quality: str = "good"  # good, uncertain, bad

    # Metadata
    raw_value: Optional[Any] = None
    raw_timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'data_id': self.data_id,
            'device_id': self.device_id,
            'timestamp': self.timestamp.isoformat(),
            'tag_name': self.tag_name,
            'value': self.value,
            'unit': self.unit,
            'quality': self.quality,
        }


class IIoTGateway:
    """
    IIoT Gateway Service.

    Universal protocol gateway for industrial devices.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # Connections
        self._connections: Dict[str, DeviceConnection] = {}

        # Data buffer for offline/sync
        self._data_buffer: List[UnifiedDataPoint] = []
        self._buffer_limit = config.get('buffer_limit', 10000) if config else 10000

        # Callbacks
        self._data_callbacks: List[Callable[[UnifiedDataPoint], None]] = []

        # Offline mode
        self._is_offline = False
        self._cloud_connected = True

    def register_device(
        self,
        device_id: str,
        device_name: str,
        protocol: Protocol,
        host: str,
        port: int,
    ) -> DeviceConnection:
        """Register a device for connection."""
        connection = DeviceConnection(
            connection_id=str(uuid4()),
            device_id=device_id,
            device_name=device_name,
            protocol=protocol,
            host=host,
            port=port,
        )

        self._connections[device_id] = connection
        logger.info(f"Registered device: {device_name} ({protocol.value})")

        return connection

    def connect(self, device_id: str) -> bool:
        """Connect to a device."""
        connection = self._connections.get(device_id)
        if not connection:
            return False

        # Simulate connection (would use actual protocol libraries)
        connection.status = ConnectionStatus.CONNECTING
        logger.info(f"Connecting to {connection.device_name}...")

        # In production, would use:
        # - opcua: asyncua or python-opcua
        # - mqtt: paho-mqtt
        # - mtconnect: mtconnect-adapter
        # - modbus: pymodbus

        connection.status = ConnectionStatus.CONNECTED
        connection.connected_at = datetime.utcnow()
        logger.info(f"Connected to {connection.device_name}")

        return True

    def disconnect(self, device_id: str) -> bool:
        """Disconnect from a device."""
        connection = self._connections.get(device_id)
        if not connection:
            return False

        connection.status = ConnectionStatus.DISCONNECTED
        logger.info(f"Disconnected from {connection.device_name}")

        return True

    def process_data(
        self,
        device_id: str,
        tag_name: str,
        value: Any,
        unit: str = "",
        raw_data: Optional[Dict[str, Any]] = None,
    ) -> UnifiedDataPoint:
        """Process incoming data from a device."""
        connection = self._connections.get(device_id)
        protocol = connection.protocol if connection else Protocol.HTTP

        data_point = UnifiedDataPoint(
            data_id=str(uuid4()),
            device_id=device_id,
            timestamp=datetime.utcnow(),
            source_protocol=protocol,
            tag_name=tag_name,
            value=value,
            unit=unit,
        )

        if connection:
            connection.messages_received += 1
            connection.last_data_at = datetime.utcnow()

        # Buffer data
        self._data_buffer.append(data_point)
        if len(self._data_buffer) > self._buffer_limit:
            self._data_buffer = self._data_buffer[-self._buffer_limit:]

        # Notify callbacks
        for callback in self._data_callbacks:
            try:
                callback(data_point)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        return data_point

    def on_data(self, callback: Callable[[UnifiedDataPoint], None]) -> None:
        """Register a data callback."""
        self._data_callbacks.append(callback)

    def get_buffered_data(
        self,
        device_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[UnifiedDataPoint]:
        """Get buffered data points."""
        data = self._data_buffer

        if device_id:
            data = [d for d in data if d.device_id == device_id]

        return data[-limit:]

    def sync_to_cloud(self) -> Dict[str, Any]:
        """Sync buffered data to cloud."""
        if not self._cloud_connected:
            return {'status': 'offline', 'buffered': len(self._data_buffer)}

        # In production, would send to cloud endpoint
        synced_count = len(self._data_buffer)
        self._data_buffer = []

        logger.info(f"Synced {synced_count} data points to cloud")

        return {
            'status': 'success',
            'synced': synced_count,
        }

    def enter_offline_mode(self) -> None:
        """Enter offline operation mode."""
        self._is_offline = True
        self._cloud_connected = False
        logger.warning("Entered offline mode")

    def exit_offline_mode(self) -> None:
        """Exit offline mode and sync."""
        self._is_offline = False
        self._cloud_connected = True
        self.sync_to_cloud()
        logger.info("Exited offline mode")

    def get_connection_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get connection status for a device."""
        connection = self._connections.get(device_id)
        return connection.to_dict() if connection else None

    def get_all_connections(self) -> List[Dict[str, Any]]:
        """Get all device connections."""
        return [c.to_dict() for c in self._connections.values()]

    def get_summary(self) -> Dict[str, Any]:
        """Get gateway summary."""
        connected = sum(
            1 for c in self._connections.values()
            if c.status == ConnectionStatus.CONNECTED
        )

        return {
            'total_devices': len(self._connections),
            'connected_devices': connected,
            'buffered_data_points': len(self._data_buffer),
            'is_offline': self._is_offline,
            'cloud_connected': self._cloud_connected,
            'by_protocol': {
                p.value: sum(
                    1 for c in self._connections.values()
                    if c.protocol == p
                )
                for p in Protocol
            },
        }
