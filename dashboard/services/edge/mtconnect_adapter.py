"""
MTConnect SHDR Adapter - CNC Equipment Data Streaming
LEGO MCP Manufacturing System v7.0

MTConnect adapter implementing SHDR (Simple Hierarchical Data Representation)
protocol for streaming CNC equipment data to MTConnect Agents.

Features:
- SHDR protocol implementation (MTConnect Standard Part 4)
- TCP socket server for Agent connections
- Data item streaming with timestamps
- Condition/alarm handling
- Asset change notifications
- ROS2 bridge integration for equipment data

Requirements:
    No external dependencies (uses standard library)

Standards Compliance:
    - MTConnect Standard Part 4: SHDR Protocol
    - MTConnect Standard Part 3: Streams
    - MTConnect Standard Part 2: Device Information Model
"""

import asyncio
import logging
import re
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import deque

logger = logging.getLogger(__name__)

# =============================================================================
# MTCONNECT DATA TYPES
# =============================================================================

class MTConnectCategory(Enum):
    """MTConnect data item categories."""
    SAMPLE = "SAMPLE"      # Continuous numeric values
    EVENT = "EVENT"        # Discrete state changes
    CONDITION = "CONDITION"  # Alarm/warning states


class MTConnectConditionState(Enum):
    """MTConnect condition states."""
    UNAVAILABLE = "UNAVAILABLE"
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    FAULT = "FAULT"


class MTConnectExecution(Enum):
    """Controller execution states per MTConnect."""
    UNAVAILABLE = "UNAVAILABLE"
    ACTIVE = "ACTIVE"
    READY = "READY"
    INTERRUPTED = "INTERRUPTED"
    FEED_HOLD = "FEED_HOLD"
    STOPPED = "STOPPED"
    OPTIONAL_STOP = "OPTIONAL_STOP"
    PROGRAM_STOPPED = "PROGRAM_STOPPED"
    PROGRAM_COMPLETED = "PROGRAM_COMPLETED"


class MTConnectControllerMode(Enum):
    """Controller mode per MTConnect."""
    UNAVAILABLE = "UNAVAILABLE"
    AUTOMATIC = "AUTOMATIC"
    SEMI_AUTOMATIC = "SEMI_AUTOMATIC"
    MANUAL = "MANUAL"
    MANUAL_DATA_INPUT = "MANUAL_DATA_INPUT"
    EDIT = "EDIT"


class MTConnectEmergencyStop(Enum):
    """Emergency stop states."""
    UNAVAILABLE = "UNAVAILABLE"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"


class MTConnectAvailability(Enum):
    """Device availability."""
    UNAVAILABLE = "UNAVAILABLE"
    AVAILABLE = "AVAILABLE"


# =============================================================================
# SHDR DATA ITEMS
# =============================================================================

@dataclass
class SHDRDataItem:
    """
    MTConnect SHDR Data Item.

    Represents a single data point in SHDR format.
    SHDR format: timestamp|key|value or timestamp|key1|value1|key2|value2...
    """
    data_item_id: str
    name: str
    category: MTConnectCategory
    value: Any
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # For conditions
    condition_state: MTConnectConditionState = MTConnectConditionState.NORMAL
    condition_native_code: str = ""
    condition_native_severity: str = ""
    condition_qualifier: str = ""
    condition_text: str = ""

    # Metadata
    units: str = ""
    native_units: str = ""
    sub_type: str = ""
    coordinate_system: str = ""

    # For tracking changes
    previous_value: Any = None
    sequence_number: int = 0

    def to_shdr(self) -> str:
        """
        Convert to SHDR format string.

        SHDR Format:
        - Samples/Events: timestamp|data_item_id|value
        - Conditions: timestamp|data_item_id|state|native_code|native_severity|qualifier|text
        """
        ts = self.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        if self.category == MTConnectCategory.CONDITION:
            # Condition format
            parts = [
                ts,
                self.data_item_id,
                self.condition_state.value,
                self.condition_native_code,
                self.condition_native_severity,
                self.condition_qualifier,
                self.condition_text,
            ]
            return "|".join(str(p) for p in parts)
        else:
            # Sample/Event format
            return f"{ts}|{self.data_item_id}|{self.value}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'data_item_id': self.data_item_id,
            'name': self.name,
            'category': self.category.value,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'units': self.units,
            'condition_state': self.condition_state.value if self.category == MTConnectCategory.CONDITION else None,
        }


@dataclass
class MTConnectAsset:
    """MTConnect Asset for asset change notifications."""
    asset_id: str
    asset_type: str
    device_uuid: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    removed: bool = False
    content: str = ""

    def to_shdr(self) -> str:
        """Convert to SHDR asset format."""
        ts = self.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        if self.removed:
            return f"{ts}|@ASSET@|{self.asset_id}|{self.asset_type}|--REMOVED--"
        return f"{ts}|@ASSET@|{self.asset_id}|{self.asset_type}|{self.content}"


# =============================================================================
# MTCONNECT DEVICE MODEL
# =============================================================================

@dataclass
class MTConnectDevice:
    """
    MTConnect Device Model.

    Represents a CNC machine or equipment device per MTConnect Device Information Model.
    """
    device_uuid: str
    device_name: str
    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    description: str = ""

    # Status
    availability: MTConnectAvailability = MTConnectAvailability.UNAVAILABLE

    # Data items
    data_items: Dict[str, SHDRDataItem] = field(default_factory=dict)

    # Components (axes, controllers, etc.)
    components: Dict[str, Dict[str, SHDRDataItem]] = field(default_factory=dict)

    # Assets
    assets: Dict[str, MTConnectAsset] = field(default_factory=dict)

    # ROS2 topic mappings
    ros2_topics: Dict[str, str] = field(default_factory=dict)

    def add_data_item(
        self,
        data_item_id: str,
        name: str,
        category: MTConnectCategory,
        initial_value: Any = "UNAVAILABLE",
        units: str = "",
        component: Optional[str] = None,
    ) -> SHDRDataItem:
        """Add a data item to the device."""
        item = SHDRDataItem(
            data_item_id=data_item_id,
            name=name,
            category=category,
            value=initial_value,
            units=units,
        )

        if component:
            if component not in self.components:
                self.components[component] = {}
            self.components[component][data_item_id] = item
        else:
            self.data_items[data_item_id] = item

        return item

    def get_data_item(self, data_item_id: str) -> Optional[SHDRDataItem]:
        """Get data item by ID."""
        if data_item_id in self.data_items:
            return self.data_items[data_item_id]
        for component_items in self.components.values():
            if data_item_id in component_items:
                return component_items[data_item_id]
        return None

    def update_data_item(
        self,
        data_item_id: str,
        value: Any,
        timestamp: Optional[datetime] = None
    ) -> Optional[SHDRDataItem]:
        """Update data item value."""
        item = self.get_data_item(data_item_id)
        if item:
            item.previous_value = item.value
            item.value = value
            item.timestamp = timestamp or datetime.now(timezone.utc)
            item.sequence_number += 1
            return item
        return None

    def get_all_data_items(self) -> List[SHDRDataItem]:
        """Get all data items including components."""
        items = list(self.data_items.values())
        for component_items in self.components.values():
            items.extend(component_items.values())
        return items

    def get_changed_items(self) -> List[SHDRDataItem]:
        """Get items that have changed since last check."""
        return [
            item for item in self.get_all_data_items()
            if item.value != item.previous_value
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'device_uuid': self.device_uuid,
            'device_name': self.device_name,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'serial_number': self.serial_number,
            'availability': self.availability.value,
            'data_items': {k: v.to_dict() for k, v in self.data_items.items()},
            'components': {
                comp: {k: v.to_dict() for k, v in items.items()}
                for comp, items in self.components.items()
            },
            'asset_count': len(self.assets),
        }


# =============================================================================
# SHDR ADAPTER
# =============================================================================

class MTConnectSHDRAdapter:
    """
    MTConnect SHDR Protocol Adapter.

    Implements the SHDR (Simple Hierarchical Data Representation) protocol
    for streaming data from CNC equipment to MTConnect Agents.

    Features:
        - TCP socket server for Agent connections
        - Multiple concurrent Agent connections
        - SHDR data streaming with timestamps
        - Condition handling (alarms/warnings)
        - Asset change notifications
        - Heartbeat/ping support
        - ROS2 bridge integration

    SHDR Protocol:
        - Line-based text protocol over TCP
        - Format: timestamp|key|value[|key|value...]
        - Special commands: * PING, * PONG, @ASSET@
    """

    SHDR_VERSION = "1.7"
    HEARTBEAT_INTERVAL = 10.0

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 7878,
        adapter_uuid: str = "",
        ros2_bridge: Optional[Any] = None,
    ):
        """
        Initialize MTConnect SHDR Adapter.

        Args:
            host: TCP server host
            port: TCP server port (default 7878)
            adapter_uuid: Unique adapter identifier
            ros2_bridge: ROS2 bridge for equipment data
        """
        self.host = host
        self.port = port
        self.adapter_uuid = adapter_uuid or f"adapter-{int(time.time())}"
        self.ros2_bridge = ros2_bridge

        # Server state
        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._clients: Set[socket.socket] = set()
        self._client_lock = threading.Lock()

        # Devices
        self._devices: Dict[str, MTConnectDevice] = {}

        # Data buffer for streaming
        self._data_buffer: deque = deque(maxlen=10000)
        self._sequence_number = 0

        # Callbacks
        self._on_data_callbacks: List[Callable[[SHDRDataItem], None]] = []

        # Async components
        self._server_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._update_task: Optional[asyncio.Task] = None

        # Configuration
        self._update_interval: float = 0.1  # 100ms default

        logger.info(f"MTConnect SHDR Adapter initialized: {host}:{port}")

    # =========================================================================
    # DEVICE MANAGEMENT
    # =========================================================================

    def register_device(
        self,
        device_uuid: str,
        device_name: str,
        manufacturer: str = "",
        model: str = "",
        serial_number: str = "",
        equipment_type: str = "CNC",
        ros2_topics: Optional[Dict[str, str]] = None,
    ) -> MTConnectDevice:
        """
        Register a CNC device with the adapter.

        Creates standard MTConnect data items based on equipment type.

        Args:
            device_uuid: Unique device identifier
            device_name: Device name
            manufacturer: Device manufacturer
            model: Device model
            serial_number: Serial number
            equipment_type: Type (CNC, 3DPrinter, Robot)
            ros2_topics: ROS2 topic mappings

        Returns:
            MTConnectDevice instance
        """
        device = MTConnectDevice(
            device_uuid=device_uuid,
            device_name=device_name,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
            ros2_topics=ros2_topics or {},
        )

        # Add standard device-level data items
        device.add_data_item(
            f"{device_uuid}_avail",
            "Availability",
            MTConnectCategory.EVENT,
            MTConnectAvailability.UNAVAILABLE.value
        )
        device.add_data_item(
            f"{device_uuid}_estop",
            "EmergencyStop",
            MTConnectCategory.EVENT,
            MTConnectEmergencyStop.UNAVAILABLE.value
        )

        # Add equipment-specific data items
        if equipment_type == "CNC":
            self._add_cnc_data_items(device)
        elif equipment_type == "3DPrinter":
            self._add_3dprinter_data_items(device)
        elif equipment_type == "Robot":
            self._add_robot_data_items(device)

        self._devices[device_uuid] = device
        logger.info(f"Registered MTConnect device: {device_name} ({equipment_type})")

        return device

    def _add_cnc_data_items(self, device: MTConnectDevice) -> None:
        """Add standard CNC data items per MTConnect spec."""
        uuid = device.device_uuid

        # Controller data items
        device.add_data_item(
            f"{uuid}_mode", "ControllerMode", MTConnectCategory.EVENT,
            MTConnectControllerMode.UNAVAILABLE.value, component="Controller"
        )
        device.add_data_item(
            f"{uuid}_exec", "Execution", MTConnectCategory.EVENT,
            MTConnectExecution.UNAVAILABLE.value, component="Controller"
        )
        device.add_data_item(
            f"{uuid}_program", "Program", MTConnectCategory.EVENT,
            "UNAVAILABLE", component="Controller"
        )
        device.add_data_item(
            f"{uuid}_line", "Line", MTConnectCategory.EVENT,
            0, component="Controller"
        )
        device.add_data_item(
            f"{uuid}_block", "Block", MTConnectCategory.EVENT,
            "", component="Controller"
        )

        # Path data items
        device.add_data_item(
            f"{uuid}_feed", "PathFeedrate", MTConnectCategory.SAMPLE,
            0.0, units="MILLIMETER/SECOND", component="Path"
        )
        device.add_data_item(
            f"{uuid}_feed_ovr", "PathFeedrateOverride", MTConnectCategory.SAMPLE,
            100.0, units="PERCENT", component="Path"
        )
        device.add_data_item(
            f"{uuid}_rapid_ovr", "RapidOverride", MTConnectCategory.SAMPLE,
            100.0, units="PERCENT", component="Path"
        )

        # Spindle data items
        device.add_data_item(
            f"{uuid}_Sspeed", "SpindleSpeed", MTConnectCategory.SAMPLE,
            0.0, units="REVOLUTION/MINUTE", component="Spindle"
        )
        device.add_data_item(
            f"{uuid}_Sspeed_ovr", "SpindleSpeedOverride", MTConnectCategory.SAMPLE,
            100.0, units="PERCENT", component="Spindle"
        )
        device.add_data_item(
            f"{uuid}_Sload", "Load", MTConnectCategory.SAMPLE,
            0.0, units="PERCENT", component="Spindle"
        )

        # Axis position data items (X, Y, Z linear)
        for axis in ['X', 'Y', 'Z']:
            device.add_data_item(
                f"{uuid}_{axis}pos", f"{axis}Position", MTConnectCategory.SAMPLE,
                0.0, units="MILLIMETER", component=f"{axis}Axis"
            )
            device.add_data_item(
                f"{uuid}_{axis}load", f"{axis}Load", MTConnectCategory.SAMPLE,
                0.0, units="PERCENT", component=f"{axis}Axis"
            )

        # Rotary axes (A, B, C)
        for axis in ['A', 'B', 'C']:
            device.add_data_item(
                f"{uuid}_{axis}pos", f"{axis}Position", MTConnectCategory.SAMPLE,
                0.0, units="DEGREE", component=f"{axis}Axis"
            )

        # System conditions
        device.add_data_item(
            f"{uuid}_system", "System", MTConnectCategory.CONDITION,
            "", component="Controller"
        )
        device.add_data_item(
            f"{uuid}_logic", "Logic", MTConnectCategory.CONDITION,
            "", component="Controller"
        )
        device.add_data_item(
            f"{uuid}_motion", "Motion", MTConnectCategory.CONDITION,
            "", component="Controller"
        )

    def _add_3dprinter_data_items(self, device: MTConnectDevice) -> None:
        """Add 3D printer data items (extended MTConnect)."""
        uuid = device.device_uuid

        # Controller
        device.add_data_item(
            f"{uuid}_mode", "ControllerMode", MTConnectCategory.EVENT,
            MTConnectControllerMode.UNAVAILABLE.value, component="Controller"
        )
        device.add_data_item(
            f"{uuid}_exec", "Execution", MTConnectCategory.EVENT,
            MTConnectExecution.UNAVAILABLE.value, component="Controller"
        )
        device.add_data_item(
            f"{uuid}_program", "Program", MTConnectCategory.EVENT,
            "UNAVAILABLE", component="Controller"
        )

        # Print progress
        device.add_data_item(
            f"{uuid}_progress", "ProcessProgress", MTConnectCategory.SAMPLE,
            0.0, units="PERCENT", component="Process"
        )
        device.add_data_item(
            f"{uuid}_layer", "LayerCurrent", MTConnectCategory.EVENT,
            0, component="Process"
        )
        device.add_data_item(
            f"{uuid}_layer_total", "LayerTotal", MTConnectCategory.EVENT,
            0, component="Process"
        )

        # Temperatures
        device.add_data_item(
            f"{uuid}_nozzle_temp", "NozzleTemperature", MTConnectCategory.SAMPLE,
            0.0, units="CELSIUS", component="Extruder"
        )
        device.add_data_item(
            f"{uuid}_nozzle_target", "NozzleTargetTemperature", MTConnectCategory.SAMPLE,
            0.0, units="CELSIUS", component="Extruder"
        )
        device.add_data_item(
            f"{uuid}_bed_temp", "BedTemperature", MTConnectCategory.SAMPLE,
            0.0, units="CELSIUS", component="Bed"
        )
        device.add_data_item(
            f"{uuid}_bed_target", "BedTargetTemperature", MTConnectCategory.SAMPLE,
            0.0, units="CELSIUS", component="Bed"
        )

        # Position
        for axis in ['X', 'Y', 'Z']:
            device.add_data_item(
                f"{uuid}_{axis}pos", f"{axis}Position", MTConnectCategory.SAMPLE,
                0.0, units="MILLIMETER", component=f"{axis}Axis"
            )

        # Extruder
        device.add_data_item(
            f"{uuid}_Epos", "ExtruderPosition", MTConnectCategory.SAMPLE,
            0.0, units="MILLIMETER", component="Extruder"
        )
        device.add_data_item(
            f"{uuid}_fan", "FanSpeed", MTConnectCategory.SAMPLE,
            0.0, units="PERCENT", component="Cooling"
        )

    def _add_robot_data_items(self, device: MTConnectDevice) -> None:
        """Add robot data items (extended MTConnect)."""
        uuid = device.device_uuid

        # Controller
        device.add_data_item(
            f"{uuid}_mode", "ControllerMode", MTConnectCategory.EVENT,
            MTConnectControllerMode.UNAVAILABLE.value, component="Controller"
        )
        device.add_data_item(
            f"{uuid}_exec", "Execution", MTConnectCategory.EVENT,
            MTConnectExecution.UNAVAILABLE.value, component="Controller"
        )
        device.add_data_item(
            f"{uuid}_program", "Program", MTConnectCategory.EVENT,
            "UNAVAILABLE", component="Controller"
        )

        # Joint positions (6 DOF)
        for i in range(1, 7):
            device.add_data_item(
                f"{uuid}_J{i}pos", f"Joint{i}Position", MTConnectCategory.SAMPLE,
                0.0, units="DEGREE", component=f"Joint{i}"
            )
            device.add_data_item(
                f"{uuid}_J{i}load", f"Joint{i}Load", MTConnectCategory.SAMPLE,
                0.0, units="PERCENT", component=f"Joint{i}"
            )

        # End effector position (Cartesian)
        for axis in ['X', 'Y', 'Z']:
            device.add_data_item(
                f"{uuid}_TCP{axis}", f"TCP{axis}Position", MTConnectCategory.SAMPLE,
                0.0, units="MILLIMETER", component="EndEffector"
            )
        for axis in ['A', 'B', 'C']:
            device.add_data_item(
                f"{uuid}_TCP{axis}", f"TCP{axis}Position", MTConnectCategory.SAMPLE,
                0.0, units="DEGREE", component="EndEffector"
            )

        # Gripper
        device.add_data_item(
            f"{uuid}_gripper", "GripperState", MTConnectCategory.EVENT,
            "UNAVAILABLE", component="EndEffector"
        )

    def unregister_device(self, device_uuid: str) -> bool:
        """Unregister a device."""
        if device_uuid in self._devices:
            del self._devices[device_uuid]
            logger.info(f"Unregistered device: {device_uuid}")
            return True
        return False

    def get_device(self, device_uuid: str) -> Optional[MTConnectDevice]:
        """Get device by UUID."""
        return self._devices.get(device_uuid)

    def get_all_devices(self) -> List[MTConnectDevice]:
        """Get all registered devices."""
        return list(self._devices.values())

    # =========================================================================
    # DATA STREAMING
    # =========================================================================

    def update_data_item(
        self,
        device_uuid: str,
        data_item_id: str,
        value: Any,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Update a data item value and stream to connected Agents.

        Args:
            device_uuid: Device UUID
            data_item_id: Data item ID
            value: New value
            timestamp: Optional timestamp (defaults to now)

        Returns:
            True if update successful
        """
        device = self._devices.get(device_uuid)
        if not device:
            return False

        item = device.update_data_item(data_item_id, value, timestamp)
        if item:
            self._stream_data_item(item)
            return True
        return False

    def update_condition(
        self,
        device_uuid: str,
        data_item_id: str,
        state: MTConnectConditionState,
        native_code: str = "",
        native_severity: str = "",
        qualifier: str = "",
        text: str = "",
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Update a condition data item.

        Args:
            device_uuid: Device UUID
            data_item_id: Condition data item ID
            state: Condition state (NORMAL, WARNING, FAULT)
            native_code: Native alarm code
            native_severity: Native severity level
            qualifier: Condition qualifier
            text: Human-readable message
            timestamp: Optional timestamp

        Returns:
            True if update successful
        """
        device = self._devices.get(device_uuid)
        if not device:
            return False

        item = device.get_data_item(data_item_id)
        if item and item.category == MTConnectCategory.CONDITION:
            item.condition_state = state
            item.condition_native_code = native_code
            item.condition_native_severity = native_severity
            item.condition_qualifier = qualifier
            item.condition_text = text
            item.timestamp = timestamp or datetime.now(timezone.utc)
            item.sequence_number += 1

            self._stream_data_item(item)
            return True
        return False

    def _stream_data_item(self, item: SHDRDataItem) -> None:
        """Stream data item to all connected Agents."""
        shdr_line = item.to_shdr() + "\n"
        self._sequence_number += 1

        # Add to buffer
        self._data_buffer.append((self._sequence_number, item))

        # Send to all clients
        self._broadcast(shdr_line)

        # Notify callbacks
        for callback in self._on_data_callbacks:
            try:
                callback(item)
            except Exception as e:
                logger.error(f"Data callback error: {e}")

    def _broadcast(self, message: str) -> None:
        """Broadcast message to all connected clients."""
        data = message.encode('utf-8')

        with self._client_lock:
            disconnected = []
            for client in self._clients:
                try:
                    client.sendall(data)
                except Exception as e:
                    logger.warning(f"Client send error: {e}")
                    disconnected.append(client)

            # Remove disconnected clients
            for client in disconnected:
                self._clients.discard(client)
                try:
                    client.close()
                except:
                    pass

    def stream_asset(self, asset: MTConnectAsset) -> None:
        """Stream asset change notification."""
        shdr_line = asset.to_shdr() + "\n"
        self._broadcast(shdr_line)

    # =========================================================================
    # TCP SERVER
    # =========================================================================

    async def start(self) -> bool:
        """
        Start the SHDR adapter.

        Starts TCP server and begins streaming data.
        """
        if self._running:
            return True

        try:
            # Create server socket
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self.host, self.port))
            self._server_socket.listen(5)
            self._server_socket.setblocking(False)

            self._running = True

            # Start server task
            self._server_task = asyncio.create_task(self._server_loop())

            # Start heartbeat task
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Start update task for ROS2 bridge
            if self.ros2_bridge:
                self._update_task = asyncio.create_task(self._update_loop())

            # Set all devices to available
            for device in self._devices.values():
                device.availability = MTConnectAvailability.AVAILABLE
                self.update_data_item(
                    device.device_uuid,
                    f"{device.device_uuid}_avail",
                    MTConnectAvailability.AVAILABLE.value
                )

            logger.info(f"MTConnect SHDR Adapter started on {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to start SHDR adapter: {e}")
            return False

    async def stop(self) -> None:
        """Stop the SHDR adapter."""
        self._running = False

        # Set devices to unavailable
        for device in self._devices.values():
            device.availability = MTConnectAvailability.UNAVAILABLE
            self.update_data_item(
                device.device_uuid,
                f"{device.device_uuid}_avail",
                MTConnectAvailability.UNAVAILABLE.value
            )

        # Cancel tasks
        for task in [self._server_task, self._heartbeat_task, self._update_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close all client connections
        with self._client_lock:
            for client in self._clients:
                try:
                    client.close()
                except:
                    pass
            self._clients.clear()

        # Close server socket
        if self._server_socket:
            self._server_socket.close()
            self._server_socket = None

        logger.info("MTConnect SHDR Adapter stopped")

    async def _server_loop(self) -> None:
        """Accept client connections."""
        loop = asyncio.get_event_loop()

        while self._running:
            try:
                # Accept connection asynchronously
                client, address = await loop.sock_accept(self._server_socket)
                logger.info(f"MTConnect Agent connected from {address}")

                with self._client_lock:
                    self._clients.add(client)

                # Send initial data (current state of all data items)
                asyncio.create_task(self._send_initial_data(client))

                # Start client handler
                asyncio.create_task(self._handle_client(client, address))

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    logger.error(f"Server loop error: {e}")
                await asyncio.sleep(0.1)

    async def _send_initial_data(self, client: socket.socket) -> None:
        """Send current state of all data items to new client."""
        try:
            for device in self._devices.values():
                for item in device.get_all_data_items():
                    shdr_line = item.to_shdr() + "\n"
                    client.sendall(shdr_line.encode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to send initial data: {e}")

    async def _handle_client(
        self,
        client: socket.socket,
        address: Tuple[str, int]
    ) -> None:
        """Handle client communication."""
        loop = asyncio.get_event_loop()
        client.setblocking(False)

        buffer = ""

        while self._running and client in self._clients:
            try:
                # Receive data
                data = await loop.sock_recv(client, 1024)
                if not data:
                    # Client disconnected
                    break

                buffer += data.decode('utf-8')

                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    await self._process_client_command(client, line.strip())

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    logger.debug(f"Client handler error: {e}")
                break

        # Clean up
        with self._client_lock:
            self._clients.discard(client)

        try:
            client.close()
        except:
            pass

        logger.info(f"MTConnect Agent disconnected from {address}")

    async def _process_client_command(
        self,
        client: socket.socket,
        command: str
    ) -> None:
        """Process command from client."""
        if not command:
            return

        if command == "* PING":
            # Respond to ping
            try:
                client.sendall(b"* PONG " + str(self.HEARTBEAT_INTERVAL).encode() + b"\n")
            except:
                pass

        elif command.startswith("* "):
            # Other SHDR commands
            logger.debug(f"Received SHDR command: {command}")

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat to clients."""
        while self._running:
            try:
                # Send heartbeat timestamp
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                heartbeat = f"* PONG {self.HEARTBEAT_INTERVAL}\n"
                self._broadcast(heartbeat)

            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            await asyncio.sleep(self.HEARTBEAT_INTERVAL)

    # =========================================================================
    # ROS2 BRIDGE
    # =========================================================================

    async def _update_loop(self) -> None:
        """Update loop for ROS2 bridge integration."""
        while self._running:
            try:
                await self._update_from_ros2()
            except Exception as e:
                logger.error(f"Update loop error: {e}")

            await asyncio.sleep(self._update_interval)

    async def _update_from_ros2(self) -> None:
        """Update data items from ROS2 topics."""
        if not self.ros2_bridge:
            return

        # This would be connected to actual ROS2 subscriptions
        # For now, simulate updates for demonstration
        pass

    def setup_ros2_subscriptions(self) -> None:
        """Set up ROS2 topic subscriptions for all devices."""
        if not self.ros2_bridge:
            return

        for device in self._devices.values():
            for data_item_id, ros2_topic in device.ros2_topics.items():
                try:
                    self.ros2_bridge.subscribe(
                        ros2_topic,
                        'std_msgs/msg/String',
                        lambda msg, d=device.device_uuid, di=data_item_id: (
                            self.update_data_item(d, di, msg.get('data', msg))
                        )
                    )
                    logger.info(f"Subscribed {ros2_topic} -> {data_item_id}")
                except Exception as e:
                    logger.error(f"Failed to subscribe {ros2_topic}: {e}")

    # =========================================================================
    # CALLBACKS
    # =========================================================================

    def on_data(self, callback: Callable[[SHDRDataItem], None]) -> None:
        """Register callback for data updates."""
        self._on_data_callbacks.append(callback)

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get adapter status summary."""
        return {
            'host': self.host,
            'port': self.port,
            'adapter_uuid': self.adapter_uuid,
            'running': self._running,
            'client_count': len(self._clients),
            'device_count': len(self._devices),
            'sequence_number': self._sequence_number,
            'buffer_size': len(self._data_buffer),
            'devices': [d.to_dict() for d in self._devices.values()],
            'heartbeat_interval': self.HEARTBEAT_INTERVAL,
        }

    def get_current_data(self, device_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Get current data for all or specific device."""
        result = {}

        devices = [self._devices[device_uuid]] if device_uuid and device_uuid in self._devices else self._devices.values()

        for device in devices:
            result[device.device_uuid] = {
                'device_name': device.device_name,
                'availability': device.availability.value,
                'data_items': {
                    item.data_item_id: {
                        'name': item.name,
                        'value': item.value,
                        'timestamp': item.timestamp.isoformat(),
                        'units': item.units,
                    }
                    for item in device.get_all_data_items()
                }
            }

        return result


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_mtconnect_adapter: Optional[MTConnectSHDRAdapter] = None


def get_mtconnect_adapter() -> MTConnectSHDRAdapter:
    """Get or create the MTConnect adapter instance."""
    global _mtconnect_adapter
    if _mtconnect_adapter is None:
        _mtconnect_adapter = MTConnectSHDRAdapter()
    return _mtconnect_adapter


async def init_mtconnect_adapter(
    host: str = "0.0.0.0",
    port: int = 7878,
    ros2_bridge: Optional[Any] = None,
    auto_register_devices: bool = True,
) -> MTConnectSHDRAdapter:
    """
    Initialize and start the MTConnect SHDR adapter.

    Args:
        host: TCP server host
        port: TCP server port
        ros2_bridge: ROS2 bridge for equipment data
        auto_register_devices: Auto-register default devices

    Returns:
        Started MTConnectSHDRAdapter instance
    """
    global _mtconnect_adapter
    _mtconnect_adapter = MTConnectSHDRAdapter(
        host=host,
        port=port,
        ros2_bridge=ros2_bridge,
    )

    # Auto-register devices
    if auto_register_devices:
        # GRBL CNC Router
        grbl = _mtconnect_adapter.register_device(
            device_uuid='grbl_cnc_1',
            device_name='GRBL_CNC_Router',
            manufacturer='LegoMCP',
            model='GRBL-3018',
            serial_number='GRBL-001',
            equipment_type='CNC',
            ros2_topics={
                'grbl_cnc_1_Xpos': '/grbl/grbl_cnc_1/position_x',
                'grbl_cnc_1_Ypos': '/grbl/grbl_cnc_1/position_y',
                'grbl_cnc_1_Zpos': '/grbl/grbl_cnc_1/position_z',
                'grbl_cnc_1_feed': '/grbl/grbl_cnc_1/feed_rate',
                'grbl_cnc_1_Sspeed': '/grbl/grbl_cnc_1/spindle_speed',
                'grbl_cnc_1_exec': '/grbl/grbl_cnc_1/execution_state',
            }
        )

        # Bambu Lab X1C
        bambu = _mtconnect_adapter.register_device(
            device_uuid='bambu_x1c_1',
            device_name='Bambu_Lab_X1C',
            manufacturer='Bambu Lab',
            model='X1-Carbon',
            serial_number='BBL-X1C-001',
            equipment_type='3DPrinter',
            ros2_topics={
                'bambu_x1c_1_nozzle_temp': '/bambu/bambu_x1c_1/nozzle_temp',
                'bambu_x1c_1_bed_temp': '/bambu/bambu_x1c_1/bed_temp',
                'bambu_x1c_1_progress': '/bambu/bambu_x1c_1/progress',
                'bambu_x1c_1_layer': '/bambu/bambu_x1c_1/current_layer',
                'bambu_x1c_1_exec': '/bambu/bambu_x1c_1/execution_state',
            }
        )

        # Niryo Ned2 Robot
        ned2 = _mtconnect_adapter.register_device(
            device_uuid='ned2_1',
            device_name='Niryo_Ned2',
            manufacturer='Niryo',
            model='Ned2',
            serial_number='NED2-001',
            equipment_type='Robot',
            ros2_topics={
                'ned2_1_J1pos': '/ned2/joint_states/j1',
                'ned2_1_J2pos': '/ned2/joint_states/j2',
                'ned2_1_J3pos': '/ned2/joint_states/j3',
                'ned2_1_J4pos': '/ned2/joint_states/j4',
                'ned2_1_J5pos': '/ned2/joint_states/j5',
                'ned2_1_J6pos': '/ned2/joint_states/j6',
                'ned2_1_gripper': '/ned2/gripper_state',
                'ned2_1_exec': '/ned2/execution_state',
            }
        )

    await _mtconnect_adapter.start()

    # Set up ROS2 subscriptions
    if ros2_bridge:
        _mtconnect_adapter.setup_ros2_subscriptions()

    return _mtconnect_adapter
