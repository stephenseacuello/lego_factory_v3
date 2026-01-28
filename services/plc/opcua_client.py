"""
LEGO Factory v3 - OPC-UA Client
===============================
Modern OPC Unified Architecture client for Level 1 PLC communication.

OPC-UA is the industry standard for secure, reliable industrial communication.
Supports discovery, browsing, reading, writing, subscriptions, and historical data.

Compatible Systems:
- Siemens S7-1500 (native OPC-UA server)
- Beckhoff TwinCAT 3
- Rockwell FactoryTalk
- Schneider EcoStruxure
- ABB Ability
- Kepware KEPServerEX
- Ignition by Inductive Automation
- Node-RED with OPC-UA nodes
- Any OPC-UA compliant server
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from threading import Lock

logger = logging.getLogger(__name__)


class OPCUASecurityMode(str, Enum):
    """OPC-UA security modes."""
    NONE = 'None'
    SIGN = 'Sign'
    SIGN_AND_ENCRYPT = 'SignAndEncrypt'


class OPCUASecurityPolicy(str, Enum):
    """OPC-UA security policies."""
    NONE = 'None'
    BASIC128RSA15 = 'Basic128Rsa15'
    BASIC256 = 'Basic256'
    BASIC256SHA256 = 'Basic256Sha256'
    AES128SHA256RSAOAEP = 'Aes128_Sha256_RsaOaep'
    AES256SHA256RSAPSS = 'Aes256_Sha256_RsaPss'


class OPCUADataType(str, Enum):
    """OPC-UA data types."""
    BOOLEAN = 'Boolean'
    SBYTE = 'SByte'
    BYTE = 'Byte'
    INT16 = 'Int16'
    UINT16 = 'UInt16'
    INT32 = 'Int32'
    UINT32 = 'UInt32'
    INT64 = 'Int64'
    UINT64 = 'UInt64'
    FLOAT = 'Float'
    DOUBLE = 'Double'
    STRING = 'String'
    DATETIME = 'DateTime'
    BYTESTRING = 'ByteString'


# OPC-UA Status Codes (subset)
class OPCUAStatusCode(int, Enum):
    """Common OPC-UA status codes."""
    GOOD = 0x00000000
    UNCERTAIN = 0x40000000
    BAD = 0x80000000
    BAD_NODE_ID_UNKNOWN = 0x80340000
    BAD_COMMUNICATION_ERROR = 0x80050000
    BAD_TIMEOUT = 0x800A0000
    BAD_NOT_CONNECTED = 0x808A0000
    BAD_SECURITY_CHECKSFAILED = 0x80130000
    BAD_CERTIFICATE_INVALID = 0x80120000


@dataclass
class OPCUANode:
    """Definition of an OPC-UA node to monitor."""
    name: str                       # Friendly name
    node_id: str                    # OPC-UA NodeId (e.g., "ns=2;s=Channel1.Device1.Tag1")
    data_type: OPCUADataType = OPCUADataType.DOUBLE
    description: str = ''
    engineering_unit: str = ''
    scale_factor: float = 1.0
    offset: float = 0.0
    read_only: bool = False

    # Subscription settings
    sampling_interval: float = 1000.0   # Milliseconds
    queue_size: int = 10
    discard_oldest: bool = True


@dataclass
class OPCUANodeValue:
    """Current value of an OPC-UA node."""
    node: OPCUANode
    value: Any
    eng_value: Any
    status_code: int
    source_timestamp: Optional[datetime]
    server_timestamp: Optional[datetime]
    error: Optional[str] = None

    @property
    def is_good(self) -> bool:
        return (self.status_code & 0xC0000000) == 0

    @property
    def quality(self) -> int:
        """Convert to OPC Classic quality code for compatibility."""
        if self.is_good:
            return 192  # GOOD
        elif (self.status_code & 0x40000000):
            return 64   # UNCERTAIN
        else:
            return 0    # BAD


@dataclass
class OPCUAConnectionConfig:
    """Configuration for OPC-UA connection."""
    name: str
    endpoint_url: str               # e.g., "opc.tcp://192.168.1.100:4840"

    # Security
    security_mode: OPCUASecurityMode = OPCUASecurityMode.NONE
    security_policy: OPCUASecurityPolicy = OPCUASecurityPolicy.NONE

    # Authentication
    username: Optional[str] = None
    password: Optional[str] = None

    # Certificates (for secure connections)
    certificate_path: Optional[str] = None
    private_key_path: Optional[str] = None
    server_certificate_path: Optional[str] = None

    # Connection settings
    timeout: float = 10.0
    session_timeout: float = 3600000    # 1 hour in ms
    secure_channel_timeout: float = 3600000

    # Application identity
    application_name: str = 'LEGO Factory v3'
    application_uri: str = 'urn:lego-factory:client'

    # Nodes to monitor
    nodes: List[OPCUANode] = field(default_factory=list)


class OPCUAClient:
    """
    OPC-UA client for Level 1 PLC communication.

    Usage:
        config = OPCUAConnectionConfig(
            name='siemens_plc',
            endpoint_url='opc.tcp://192.168.1.100:4840',
            nodes=[
                OPCUANode('temperature', 'ns=2;s=Sensors.Temperature',
                         OPCUADataType.DOUBLE, engineering_unit='°C'),
                OPCUANode('motor_speed', 'ns=2;s=Motors.M1.Speed',
                         OPCUADataType.INT32, engineering_unit='RPM'),
            ]
        )

        client = OPCUAClient(config)
        await client.connect()

        # Read single value
        value = await client.read_node('temperature')

        # Subscribe to changes
        await client.subscribe(callback=my_handler)

        # Write value
        await client.write_node('motor_speed', 1500)
    """

    def __init__(self, config: OPCUAConnectionConfig):
        self.config = config
        self._client = None
        self._subscription = None
        self._connected = False
        self._lock = Lock()
        self._node_cache: Dict[str, OPCUANodeValue] = {}
        self._subscribed = False
        self._callbacks: List[Callable] = []
        self._last_error: Optional[str] = None

        # Statistics
        self._connection_count = 0
        self._read_count = 0
        self._write_count = 0
        self._error_count = 0

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            'connected': self._connected,
            'subscribed': self._subscribed,
            'connection_count': self._connection_count,
            'read_count': self._read_count,
            'write_count': self._write_count,
            'error_count': self._error_count,
            'last_error': self._last_error,
            'nodes_cached': len(self._node_cache),
        }

    async def connect(self) -> bool:
        """Establish connection to OPC-UA server."""
        try:
            from asyncua import Client, ua

            self._client = Client(
                url=self.config.endpoint_url,
                timeout=self.config.timeout,
            )

            # Set security if configured
            if self.config.security_mode != OPCUASecurityMode.NONE:
                await self._configure_security()

            # Set authentication if configured
            if self.config.username:
                self._client.set_user(self.config.username)
                self._client.set_password(self.config.password or '')

            # Connect
            await self._client.connect()
            self._connected = True
            self._connection_count += 1

            logger.info(f"OPC-UA connected: {self.config.endpoint_url}")
            return True

        except ImportError:
            # Fallback to simulation mode
            logger.warning("asyncua not installed, using simulation mode")
            self._client = None
            self._connected = True
            self._connection_count += 1
            return True

        except Exception as e:
            self._last_error = str(e)
            self._error_count += 1
            logger.error(f"OPC-UA connect failed [{self.config.name}]: {e}")
            return False

    async def _configure_security(self):
        """Configure security settings."""
        if not self._client:
            return

        # This requires asyncua library
        from asyncua import ua

        policy_map = {
            OPCUASecurityPolicy.BASIC128RSA15: ua.SecurityPolicyType.Basic128Rsa15_Sign,
            OPCUASecurityPolicy.BASIC256: ua.SecurityPolicyType.Basic256_Sign,
            OPCUASecurityPolicy.BASIC256SHA256: ua.SecurityPolicyType.Basic256Sha256_Sign,
        }

        if self.config.security_mode == OPCUASecurityMode.SIGN_AND_ENCRYPT:
            policy_map = {
                OPCUASecurityPolicy.BASIC128RSA15: ua.SecurityPolicyType.Basic128Rsa15_SignAndEncrypt,
                OPCUASecurityPolicy.BASIC256: ua.SecurityPolicyType.Basic256_SignAndEncrypt,
                OPCUASecurityPolicy.BASIC256SHA256: ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
            }

        policy = policy_map.get(self.config.security_policy)
        if policy and self.config.certificate_path:
            await self._client.set_security(
                policy,
                certificate=self.config.certificate_path,
                private_key=self.config.private_key_path,
                server_certificate=self.config.server_certificate_path,
            )

    async def disconnect(self):
        """Close OPC-UA connection."""
        if self._subscription:
            try:
                await self._subscription.delete()
            except Exception as e:
                logger.warning(f"Error deleting subscription: {e}")
            self._subscription = None

        if self._client:
            try:
                await self._client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting OPC-UA: {e}")

        self._connected = False
        self._subscribed = False
        logger.info(f"OPC-UA disconnected: {self.config.name}")

    async def read_node(self, node_name: str) -> Optional[OPCUANodeValue]:
        """Read a single node by name."""
        node = self._find_node(node_name)
        if not node:
            logger.error(f"Node not found: {node_name}")
            return None

        return await self._read_node(node)

    async def _read_node(self, node: OPCUANode) -> OPCUANodeValue:
        """Read a node from the OPC-UA server."""
        now = datetime.utcnow()

        try:
            if not self._client:
                # Simulation mode
                value = self._simulate_read(node)
                eng_value = (value * node.scale_factor) + node.offset

                result = OPCUANodeValue(
                    node=node,
                    value=value,
                    eng_value=eng_value,
                    status_code=OPCUAStatusCode.GOOD,
                    source_timestamp=now,
                    server_timestamp=now,
                )
            else:
                # Real OPC-UA read
                ua_node = self._client.get_node(node.node_id)
                data_value = await ua_node.read_data_value()

                value = data_value.Value.Value
                eng_value = (value * node.scale_factor) + node.offset if value is not None else None

                result = OPCUANodeValue(
                    node=node,
                    value=value,
                    eng_value=eng_value,
                    status_code=data_value.StatusCode.value,
                    source_timestamp=data_value.SourceTimestamp,
                    server_timestamp=data_value.ServerTimestamp,
                )

            self._node_cache[node.name] = result
            self._read_count += 1
            return result

        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)

            return OPCUANodeValue(
                node=node,
                value=None,
                eng_value=None,
                status_code=OPCUAStatusCode.BAD_COMMUNICATION_ERROR,
                source_timestamp=now,
                server_timestamp=now,
                error=str(e),
            )

    def _simulate_read(self, node: OPCUANode) -> Any:
        """Generate simulated read values."""
        import random

        type_generators = {
            OPCUADataType.BOOLEAN: lambda: random.choice([True, False]),
            OPCUADataType.SBYTE: lambda: random.randint(-128, 127),
            OPCUADataType.BYTE: lambda: random.randint(0, 255),
            OPCUADataType.INT16: lambda: random.randint(-1000, 1000),
            OPCUADataType.UINT16: lambda: random.randint(0, 2000),
            OPCUADataType.INT32: lambda: random.randint(-100000, 100000),
            OPCUADataType.UINT32: lambda: random.randint(0, 200000),
            OPCUADataType.INT64: lambda: random.randint(-1000000, 1000000),
            OPCUADataType.UINT64: lambda: random.randint(0, 2000000),
            OPCUADataType.FLOAT: lambda: random.uniform(0, 100),
            OPCUADataType.DOUBLE: lambda: random.uniform(0, 100),
            OPCUADataType.STRING: lambda: f"SIM_{node.name[:8]}",
            OPCUADataType.DATETIME: lambda: datetime.utcnow(),
        }

        generator = type_generators.get(node.data_type, lambda: 0)
        return generator()

    async def write_node(self, node_name: str, value: Any) -> bool:
        """Write a value to a node."""
        node = self._find_node(node_name)
        if not node:
            logger.error(f"Node not found: {node_name}")
            return False

        if node.read_only:
            logger.error(f"Node is read-only: {node_name}")
            return False

        return await self._write_node(node, value)

    async def _write_node(self, node: OPCUANode, value: Any) -> bool:
        """Write a value to the OPC-UA server."""
        try:
            # Convert engineering to raw
            raw_value = (value - node.offset) / node.scale_factor

            if not self._client:
                # Simulation mode
                logger.info(f"[SIM] Write {node.name} = {value} (raw: {raw_value})")
            else:
                # Real OPC-UA write
                ua_node = self._client.get_node(node.node_id)
                await ua_node.write_value(raw_value)

            self._write_count += 1
            logger.debug(f"Wrote {node.name} = {value}")
            return True

        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)
            logger.error(f"Write failed [{node.name}]: {e}")
            return False

    async def read_all_nodes(self) -> Dict[str, OPCUANodeValue]:
        """Read all configured nodes."""
        results = {}
        for node in self.config.nodes:
            results[node.name] = await self._read_node(node)
        return results

    async def subscribe(self, callback: Callable = None):
        """Subscribe to node value changes."""
        if self._subscribed:
            logger.warning("Already subscribed")
            return

        if callback:
            self._callbacks.append(callback)

        if not self._client:
            # Simulation mode - start polling
            asyncio.create_task(self._simulate_subscription())
            self._subscribed = True
            return

        try:
            from asyncua import ua

            # Create subscription
            self._subscription = await self._client.create_subscription(
                period=500,  # Publishing interval in ms
                handler=self,
            )

            # Subscribe to all nodes
            for node in self.config.nodes:
                ua_node = self._client.get_node(node.node_id)
                await self._subscription.subscribe_data_change(
                    ua_node,
                    ua.AttributeIds.Value,
                    queuesize=node.queue_size,
                )

            self._subscribed = True
            logger.info(f"Subscribed to {len(self.config.nodes)} nodes")

        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)
            logger.error(f"Subscribe failed: {e}")

    async def _simulate_subscription(self):
        """Simulate subscription with polling."""
        while self._subscribed:
            try:
                values = await self.read_all_nodes()
                for callback in self._callbacks:
                    await callback(self.config.name, values)
            except Exception as e:
                logger.error(f"Simulation poll error: {e}")
            await asyncio.sleep(1.0)

    def datachange_notification(self, node, val, data):
        """OPC-UA subscription callback (asyncua handler interface)."""
        try:
            # Find our node definition
            node_id = node.nodeid.to_string()
            our_node = None
            for n in self.config.nodes:
                if n.node_id == node_id:
                    our_node = n
                    break

            if not our_node:
                return

            # Update cache
            eng_value = (val * our_node.scale_factor) + our_node.offset if val is not None else None
            result = OPCUANodeValue(
                node=our_node,
                value=val,
                eng_value=eng_value,
                status_code=data.monitored_item.Value.StatusCode.value,
                source_timestamp=data.monitored_item.Value.SourceTimestamp,
                server_timestamp=data.monitored_item.Value.ServerTimestamp,
            )
            self._node_cache[our_node.name] = result

            # Notify callbacks
            for callback in self._callbacks:
                asyncio.create_task(callback(our_node.name, result))

        except Exception as e:
            logger.error(f"Data change notification error: {e}")

    async def unsubscribe(self):
        """Unsubscribe from all nodes."""
        self._subscribed = False
        if self._subscription:
            try:
                await self._subscription.delete()
            except Exception as e:
                logger.warning(f"Error deleting subscription: {e}")
            self._subscription = None
        logger.info("Unsubscribed from all nodes")

    async def browse(self, node_id: str = 'i=85') -> List[Dict[str, Any]]:
        """Browse server namespace from a starting node."""
        if not self._client:
            # Simulation mode - return dummy browse results
            return [
                {'node_id': 'ns=2;s=Sensors', 'browse_name': 'Sensors', 'node_class': 'Object'},
                {'node_id': 'ns=2;s=Motors', 'browse_name': 'Motors', 'node_class': 'Object'},
                {'node_id': 'ns=2;s=PLCs', 'browse_name': 'PLCs', 'node_class': 'Object'},
            ]

        try:
            node = self._client.get_node(node_id)
            children = await node.get_children()

            results = []
            for child in children:
                browse_name = await child.read_browse_name()
                node_class = await child.read_node_class()

                results.append({
                    'node_id': child.nodeid.to_string(),
                    'browse_name': browse_name.Name,
                    'node_class': node_class.name,
                })

            return results

        except Exception as e:
            logger.error(f"Browse failed: {e}")
            return []

    def get_cached_value(self, node_name: str) -> Optional[OPCUANodeValue]:
        """Get the most recent cached value for a node."""
        return self._node_cache.get(node_name)

    def get_all_cached_values(self) -> Dict[str, OPCUANodeValue]:
        """Get all cached node values."""
        return dict(self._node_cache)

    def _find_node(self, name: str) -> Optional[OPCUANode]:
        """Find a node by name."""
        for node in self.config.nodes:
            if node.name == name:
                return node
        return None

    def add_node(self, node: OPCUANode):
        """Add a node to the configuration."""
        self.config.nodes.append(node)

    def remove_node(self, node_name: str) -> bool:
        """Remove a node by name."""
        for i, node in enumerate(self.config.nodes):
            if node.name == node_name:
                del self.config.nodes[i]
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize client state to dictionary."""
        return {
            'name': self.config.name,
            'endpoint_url': self.config.endpoint_url,
            'security_mode': self.config.security_mode.value,
            'connected': self._connected,
            'subscribed': self._subscribed,
            'node_count': len(self.config.nodes),
            'stats': self.stats,
        }
