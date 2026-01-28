"""
LEGO Factory v3 - PLC Manager
=============================
Unified manager for Level 1 PLC connections across multiple protocols.

Manages connections to:
- Modbus TCP/RTU devices (sensors, VFDs, meters, legacy PLCs)
- OPC-UA servers (modern PLCs, SCADA systems)
- Future: EtherNet/IP, Profinet, CANopen

Provides:
- Connection lifecycle management
- Unified tag/node interface
- Background polling and subscriptions
- Data caching with quality codes
- Historian integration
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from services.plc.modbus_client import (
    ModbusClient, ModbusConnectionConfig, ModbusProtocol,
    ModbusTag, ModbusTagValue, ModbusDataType, ModbusFunctionCode
)
from services.plc.opcua_client import (
    OPCUAClient, OPCUAConnectionConfig, OPCUANode, OPCUANodeValue,
    OPCUADataType, OPCUASecurityMode, OPCUASecurityPolicy
)

logger = logging.getLogger(__name__)


class PLCProtocol(str, Enum):
    """Supported PLC communication protocols."""
    MODBUS_TCP = 'modbus_tcp'
    MODBUS_RTU = 'modbus_rtu'
    OPCUA = 'opcua'
    ETHERNETIP = 'ethernet_ip'      # Future
    PROFINET = 'profinet'           # Future
    CANOPEN = 'canopen'             # Future


@dataclass
class PLCConnection:
    """Unified PLC connection representation."""
    name: str
    protocol: PLCProtocol
    enabled: bool = True
    description: str = ''

    # Connection details (varies by protocol)
    host: str = ''
    port: int = 0
    serial_port: str = ''
    endpoint_url: str = ''

    # Authentication
    username: str = ''
    password: str = ''

    # Client reference (set at runtime)
    client: Any = None

    @property
    def connected(self) -> bool:
        if self.client:
            return self.client.connected
        return False


class PLCManager:
    """
    Unified PLC connection manager.

    Usage:
        manager = PLCManager()

        # Load configuration from file
        manager.load_config('/path/to/plc_config.json')

        # Or add connections programmatically
        manager.add_modbus_connection(
            name='vfd_drive_1',
            host='192.168.1.50',
            port=502,
            tags=[
                {'name': 'speed', 'address': 0, 'data_type': 'float32'},
                {'name': 'current', 'address': 2, 'data_type': 'float32'},
            ]
        )

        manager.add_opcua_connection(
            name='siemens_s7_1500',
            endpoint_url='opc.tcp://192.168.1.100:4840',
            nodes=[
                {'name': 'temperature', 'node_id': 'ns=2;s=Temp1'},
            ]
        )

        # Connect all
        await manager.connect_all()

        # Start polling
        await manager.start_polling(callback=my_handler)

        # Read/write
        value = await manager.read('vfd_drive_1', 'speed')
        await manager.write('vfd_drive_1', 'speed', 1500)
    """

    def __init__(self):
        self._connections: Dict[str, PLCConnection] = {}
        self._polling = False
        self._poll_tasks: List[asyncio.Task] = []
        self._callbacks: List[Callable] = []
        self._config_path: Optional[Path] = None

    @property
    def connections(self) -> Dict[str, PLCConnection]:
        return self._connections

    def add_modbus_connection(
        self,
        name: str,
        host: str = '127.0.0.1',
        port: int = 502,
        serial_port: str = '',
        protocol: ModbusProtocol = ModbusProtocol.TCP,
        tags: List[Dict] = None,
        poll_interval: float = 1.0,
        **kwargs
    ) -> PLCConnection:
        """Add a Modbus TCP/RTU connection."""

        # Convert tag dicts to ModbusTag objects
        modbus_tags = []
        for tag_dict in (tags or []):
            data_type = ModbusDataType(tag_dict.get('data_type', 'uint16'))
            func_code = ModbusFunctionCode(
                tag_dict.get('function_code', ModbusFunctionCode.READ_HOLDING_REGISTERS)
            )

            modbus_tags.append(ModbusTag(
                name=tag_dict['name'],
                address=tag_dict['address'],
                data_type=data_type,
                function_code=func_code,
                unit_id=tag_dict.get('unit_id', 1),
                description=tag_dict.get('description', ''),
                engineering_unit=tag_dict.get('engineering_unit', ''),
                scale_factor=tag_dict.get('scale_factor', 1.0),
                offset=tag_dict.get('offset', 0.0),
                byte_order=tag_dict.get('byte_order', 'big'),
                word_order=tag_dict.get('word_order', 'big'),
                string_length=tag_dict.get('string_length', 0),
                read_only=tag_dict.get('read_only', False),
            ))

        # Create config
        config = ModbusConnectionConfig(
            name=name,
            protocol=protocol,
            host=host,
            port=port,
            serial_port=serial_port,
            poll_interval=poll_interval,
            tags=modbus_tags,
            **kwargs
        )

        # Create client
        client = ModbusClient(config)

        # Create connection record
        plc_protocol = PLCProtocol.MODBUS_TCP if protocol == ModbusProtocol.TCP else PLCProtocol.MODBUS_RTU
        connection = PLCConnection(
            name=name,
            protocol=plc_protocol,
            host=host,
            port=port,
            serial_port=serial_port,
            client=client,
        )

        self._connections[name] = connection
        logger.info(f"Added Modbus connection: {name} ({host}:{port})")
        return connection

    def add_opcua_connection(
        self,
        name: str,
        endpoint_url: str,
        nodes: List[Dict] = None,
        security_mode: str = 'None',
        security_policy: str = 'None',
        username: str = '',
        password: str = '',
        **kwargs
    ) -> PLCConnection:
        """Add an OPC-UA connection."""

        # Convert node dicts to OPCUANode objects
        opcua_nodes = []
        for node_dict in (nodes or []):
            data_type = OPCUADataType(node_dict.get('data_type', 'Double'))

            opcua_nodes.append(OPCUANode(
                name=node_dict['name'],
                node_id=node_dict['node_id'],
                data_type=data_type,
                description=node_dict.get('description', ''),
                engineering_unit=node_dict.get('engineering_unit', ''),
                scale_factor=node_dict.get('scale_factor', 1.0),
                offset=node_dict.get('offset', 0.0),
                read_only=node_dict.get('read_only', False),
                sampling_interval=node_dict.get('sampling_interval', 1000.0),
            ))

        # Create config
        config = OPCUAConnectionConfig(
            name=name,
            endpoint_url=endpoint_url,
            security_mode=OPCUASecurityMode(security_mode),
            security_policy=OPCUASecurityPolicy(security_policy),
            username=username if username else None,
            password=password if password else None,
            nodes=opcua_nodes,
            **kwargs
        )

        # Create client
        client = OPCUAClient(config)

        # Create connection record
        connection = PLCConnection(
            name=name,
            protocol=PLCProtocol.OPCUA,
            endpoint_url=endpoint_url,
            username=username,
            client=client,
        )

        self._connections[name] = connection
        logger.info(f"Added OPC-UA connection: {name} ({endpoint_url})")
        return connection

    def remove_connection(self, name: str) -> bool:
        """Remove a connection."""
        if name in self._connections:
            conn = self._connections[name]
            if conn.connected:
                asyncio.create_task(self._disconnect_one(conn))
            del self._connections[name]
            logger.info(f"Removed connection: {name}")
            return True
        return False

    async def connect(self, name: str) -> bool:
        """Connect to a specific PLC."""
        conn = self._connections.get(name)
        if not conn:
            logger.error(f"Connection not found: {name}")
            return False

        if not conn.enabled:
            logger.warning(f"Connection disabled: {name}")
            return False

        return await conn.client.connect()

    async def disconnect(self, name: str):
        """Disconnect from a specific PLC."""
        conn = self._connections.get(name)
        if conn and conn.client:
            await conn.client.disconnect()

    async def connect_all(self) -> Dict[str, bool]:
        """Connect to all enabled PLCs."""
        results = {}
        tasks = []

        for name, conn in self._connections.items():
            if conn.enabled:
                tasks.append((name, self.connect(name)))

        for name, task in tasks:
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Failed to connect {name}: {e}")
                results[name] = False

        connected = sum(1 for v in results.values() if v)
        logger.info(f"Connected to {connected}/{len(results)} PLCs")
        return results

    async def disconnect_all(self):
        """Disconnect from all PLCs."""
        for name in self._connections:
            await self.disconnect(name)

    async def _disconnect_one(self, conn: PLCConnection):
        """Helper to disconnect a single connection."""
        if conn.client:
            await conn.client.disconnect()

    async def read(self, connection_name: str, tag_name: str) -> Optional[Any]:
        """Read a tag/node value from a PLC."""
        conn = self._connections.get(connection_name)
        if not conn:
            logger.error(f"Connection not found: {connection_name}")
            return None

        if not conn.connected:
            logger.warning(f"Not connected: {connection_name}")
            return None

        if conn.protocol in (PLCProtocol.MODBUS_TCP, PLCProtocol.MODBUS_RTU):
            result = await conn.client.read_tag(tag_name)
            return result.eng_value if result else None

        elif conn.protocol == PLCProtocol.OPCUA:
            result = await conn.client.read_node(tag_name)
            return result.eng_value if result else None

        return None

    async def read_raw(self, connection_name: str, tag_name: str) -> Optional[Any]:
        """Read raw tag/node value (without scaling)."""
        conn = self._connections.get(connection_name)
        if not conn or not conn.connected:
            return None

        if conn.protocol in (PLCProtocol.MODBUS_TCP, PLCProtocol.MODBUS_RTU):
            result = await conn.client.read_tag(tag_name)
            return result

        elif conn.protocol == PLCProtocol.OPCUA:
            result = await conn.client.read_node(tag_name)
            return result

        return None

    async def write(self, connection_name: str, tag_name: str, value: Any) -> bool:
        """Write a value to a tag/node."""
        conn = self._connections.get(connection_name)
        if not conn:
            logger.error(f"Connection not found: {connection_name}")
            return False

        if not conn.connected:
            logger.warning(f"Not connected: {connection_name}")
            return False

        if conn.protocol in (PLCProtocol.MODBUS_TCP, PLCProtocol.MODBUS_RTU):
            return await conn.client.write_tag(tag_name, value)

        elif conn.protocol == PLCProtocol.OPCUA:
            return await conn.client.write_node(tag_name, value)

        return False

    async def read_all(self, connection_name: str) -> Dict[str, Any]:
        """Read all tags/nodes from a connection."""
        conn = self._connections.get(connection_name)
        if not conn or not conn.connected:
            return {}

        if conn.protocol in (PLCProtocol.MODBUS_TCP, PLCProtocol.MODBUS_RTU):
            results = await conn.client.read_all_tags()
            return {name: val.eng_value for name, val in results.items()}

        elif conn.protocol == PLCProtocol.OPCUA:
            results = await conn.client.read_all_nodes()
            return {name: val.eng_value for name, val in results.items()}

        return {}

    def get_cached(self, connection_name: str, tag_name: str) -> Optional[Any]:
        """Get cached value for a tag (no I/O)."""
        conn = self._connections.get(connection_name)
        if not conn:
            return None

        if conn.protocol in (PLCProtocol.MODBUS_TCP, PLCProtocol.MODBUS_RTU):
            result = conn.client.get_cached_value(tag_name)
            return result.eng_value if result else None

        elif conn.protocol == PLCProtocol.OPCUA:
            result = conn.client.get_cached_value(tag_name)
            return result.eng_value if result else None

        return None

    async def start_polling(self, callback: Callable = None):
        """Start background polling on all connections."""
        if self._polling:
            return

        if callback:
            self._callbacks.append(callback)

        self._polling = True

        for name, conn in self._connections.items():
            if not conn.connected or not conn.enabled:
                continue

            if conn.protocol in (PLCProtocol.MODBUS_TCP, PLCProtocol.MODBUS_RTU):
                await conn.client.start_polling(callback=self._on_poll_data)

            elif conn.protocol == PLCProtocol.OPCUA:
                await conn.client.subscribe(callback=self._on_poll_data)

        logger.info("Started polling on all connections")

    async def stop_polling(self):
        """Stop background polling."""
        self._polling = False

        for conn in self._connections.values():
            if conn.protocol in (PLCProtocol.MODBUS_TCP, PLCProtocol.MODBUS_RTU):
                await conn.client.stop_polling()
            elif conn.protocol == PLCProtocol.OPCUA:
                await conn.client.unsubscribe()

        logger.info("Stopped polling on all connections")

    async def _on_poll_data(self, connection_name: str, values: Dict):
        """Internal callback for polled data."""
        for callback in self._callbacks:
            try:
                await callback(connection_name, values)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def load_config(self, config_path: Union[str, Path]):
        """Load PLC configuration from JSON file."""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Config file not found: {path}")
            return

        self._config_path = path

        with open(path, 'r') as f:
            config = json.load(f)

        for conn_cfg in config.get('connections', []):
            protocol = conn_cfg.get('protocol', 'modbus_tcp')

            if protocol in ('modbus_tcp', 'modbus_rtu'):
                self.add_modbus_connection(
                    name=conn_cfg['name'],
                    host=conn_cfg.get('host', '127.0.0.1'),
                    port=conn_cfg.get('port', 502),
                    serial_port=conn_cfg.get('serial_port', ''),
                    protocol=ModbusProtocol.TCP if protocol == 'modbus_tcp' else ModbusProtocol.RTU,
                    tags=conn_cfg.get('tags', []),
                    poll_interval=conn_cfg.get('poll_interval', 1.0),
                )

            elif protocol == 'opcua':
                self.add_opcua_connection(
                    name=conn_cfg['name'],
                    endpoint_url=conn_cfg['endpoint_url'],
                    nodes=conn_cfg.get('nodes', []),
                    security_mode=conn_cfg.get('security_mode', 'None'),
                    security_policy=conn_cfg.get('security_policy', 'None'),
                    username=conn_cfg.get('username', ''),
                    password=conn_cfg.get('password', ''),
                )

        logger.info(f"Loaded {len(self._connections)} connections from {path}")

    def save_config(self, config_path: Union[str, Path] = None):
        """Save current configuration to JSON file."""
        path = Path(config_path) if config_path else self._config_path
        if not path:
            raise ValueError("No config path specified")

        config = {'connections': []}

        for conn in self._connections.values():
            if conn.protocol in (PLCProtocol.MODBUS_TCP, PLCProtocol.MODBUS_RTU):
                conn_cfg = {
                    'name': conn.name,
                    'protocol': conn.protocol.value,
                    'host': conn.host,
                    'port': conn.port,
                    'serial_port': conn.serial_port,
                    'poll_interval': conn.client.config.poll_interval,
                    'tags': [
                        {
                            'name': tag.name,
                            'address': tag.address,
                            'data_type': tag.data_type.value,
                            'function_code': tag.function_code.value,
                            'unit_id': tag.unit_id,
                            'description': tag.description,
                            'engineering_unit': tag.engineering_unit,
                            'scale_factor': tag.scale_factor,
                            'offset': tag.offset,
                            'read_only': tag.read_only,
                        }
                        for tag in conn.client.config.tags
                    ]
                }

            elif conn.protocol == PLCProtocol.OPCUA:
                conn_cfg = {
                    'name': conn.name,
                    'protocol': 'opcua',
                    'endpoint_url': conn.endpoint_url,
                    'security_mode': conn.client.config.security_mode.value,
                    'security_policy': conn.client.config.security_policy.value,
                    'username': conn.username,
                    'nodes': [
                        {
                            'name': node.name,
                            'node_id': node.node_id,
                            'data_type': node.data_type.value,
                            'description': node.description,
                            'engineering_unit': node.engineering_unit,
                            'scale_factor': node.scale_factor,
                            'offset': node.offset,
                            'read_only': node.read_only,
                        }
                        for node in conn.client.config.nodes
                    ]
                }
            else:
                continue

            config['connections'].append(conn_cfg)

        with open(path, 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f"Saved {len(config['connections'])} connections to {path}")

    def get_status(self) -> Dict[str, Any]:
        """Get status of all connections."""
        status = {
            'total_connections': len(self._connections),
            'connected': 0,
            'polling': self._polling,
            'connections': {}
        }

        for name, conn in self._connections.items():
            status['connections'][name] = {
                'protocol': conn.protocol.value,
                'enabled': conn.enabled,
                'connected': conn.connected,
                'host': conn.host or conn.endpoint_url,
                'stats': conn.client.stats if conn.client else {},
            }
            if conn.connected:
                status['connected'] += 1

        return status

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager state."""
        return self.get_status()


# Singleton instance
_plc_manager: Optional[PLCManager] = None


def get_plc_manager() -> PLCManager:
    """Get the global PLC manager instance."""
    global _plc_manager
    if _plc_manager is None:
        _plc_manager = PLCManager()
    return _plc_manager
