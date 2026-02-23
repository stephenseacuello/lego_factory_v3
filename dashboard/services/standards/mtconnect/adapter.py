"""
MTConnect Adapter Implementation

Connects to CNC machines and provides data to MTConnect Agent.
Supports SHDR protocol for data transmission.

Reference: MTConnect Standard v2.0, SHDR Protocol
"""

import asyncio
import logging
import time
import socket
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class DataItemCategory(Enum):
    """MTConnect Data Item Categories."""
    SAMPLE = "SAMPLE"      # Continuous numeric values
    EVENT = "EVENT"        # Discrete state changes
    CONDITION = "CONDITION"  # Alarm/warning states


class DataItemType(Enum):
    """Common MTConnect Data Item Types."""
    # Samples
    POSITION = "POSITION"
    VELOCITY = "VELOCITY"
    ACCELERATION = "ACCELERATION"
    TEMPERATURE = "TEMPERATURE"
    LOAD = "LOAD"
    SPINDLE_SPEED = "SPINDLE_SPEED"
    PATH_FEEDRATE = "PATH_FEEDRATE"
    ROTARY_VELOCITY = "ROTARY_VELOCITY"

    # Events
    EXECUTION = "EXECUTION"
    CONTROLLER_MODE = "CONTROLLER_MODE"
    PROGRAM = "PROGRAM"
    BLOCK = "BLOCK"
    LINE = "LINE"
    PART_COUNT = "PART_COUNT"
    AVAILABILITY = "AVAILABILITY"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    TOOL_ID = "TOOL_ID"

    # Conditions
    SYSTEM = "SYSTEM"
    LOGIC_PROGRAM = "LOGIC_PROGRAM"
    MOTION_PROGRAM = "MOTION_PROGRAM"
    HARDWARE = "HARDWARE"
    COMMUNICATIONS = "COMMUNICATIONS"


class ConditionState(Enum):
    """MTConnect Condition States."""
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    FAULT = "FAULT"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class DataItem:
    """MTConnect Data Item."""
    id: str
    name: str
    category: DataItemCategory
    type: DataItemType
    sub_type: Optional[str] = None
    units: Optional[str] = None
    native_units: Optional[str] = None
    native_scale: float = 1.0
    coordinate_system: Optional[str] = None

    # Current value
    value: Any = None
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0


@dataclass
class AdapterConfig:
    """MTConnect Adapter Configuration."""
    device_uuid: str = "lego-mcp-cnc-001"
    device_name: str = "LEGO MCP CNC"

    # Network
    agent_host: str = "localhost"
    agent_port: int = 7878

    # Timing
    heartbeat_interval: float = 10.0  # seconds
    sample_interval: float = 0.1  # seconds

    # Reconnection
    reconnect_delay: float = 5.0
    max_reconnect_attempts: int = 10


class MTConnectAdapter:
    """
    MTConnect Adapter for CNC Machine Integration.

    Provides data from CNC machines to MTConnect Agent using
    the SHDR (Simple Hierarchical Data Representation) protocol.

    Features:
    - Automatic connection management
    - Data item management
    - Condition handling
    - Asset updates

    Usage:
        >>> adapter = MTConnectAdapter(config)
        >>> adapter.add_data_item("Xpos", DataItemCategory.SAMPLE, DataItemType.POSITION)
        >>> await adapter.start()
        >>> adapter.update_value("Xpos", 125.5)
    """

    # SHDR Protocol constants
    SHDR_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
    SHDR_UNAVAILABLE = "UNAVAILABLE"

    def __init__(self, config: Optional[AdapterConfig] = None):
        """
        Initialize MTConnect Adapter.

        Args:
            config: Adapter configuration
        """
        self.config = config or AdapterConfig()

        # Data items
        self._data_items: Dict[str, DataItem] = {}
        self._sequence = 0

        # Connection state
        self._connected = False
        self._socket: Optional[socket.socket] = None
        self._running = False

        # Callbacks
        self._value_callbacks: Dict[str, List[Callable]] = {}

        # Tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reconnect_attempts = 0

        logger.info(f"MTConnectAdapter initialized for {self.config.device_name}")

    def add_data_item(
        self,
        id: str,
        category: DataItemCategory,
        type: DataItemType,
        name: Optional[str] = None,
        sub_type: Optional[str] = None,
        units: Optional[str] = None,
        native_units: Optional[str] = None,
        native_scale: float = 1.0,
        coordinate_system: Optional[str] = None
    ) -> DataItem:
        """
        Add a data item to the adapter.

        Args:
            id: Unique data item ID
            category: Data item category
            type: Data item type
            name: Human-readable name
            sub_type: Sub-type specification
            units: Engineering units
            native_units: Native machine units
            native_scale: Scale factor
            coordinate_system: Coordinate system (for positions)

        Returns:
            Created DataItem
        """
        item = DataItem(
            id=id,
            name=name or id,
            category=category,
            type=type,
            sub_type=sub_type,
            units=units,
            native_units=native_units,
            native_scale=native_scale,
            coordinate_system=coordinate_system,
            value=self.SHDR_UNAVAILABLE
        )

        self._data_items[id] = item
        logger.debug(f"Added data item: {id} ({category.value}/{type.value})")
        return item

    def add_standard_cnc_items(self) -> None:
        """Add standard CNC machine data items."""
        # Axis positions
        for axis in ['X', 'Y', 'Z', 'A', 'B', 'C']:
            self.add_data_item(
                f"{axis}pos",
                DataItemCategory.SAMPLE,
                DataItemType.POSITION,
                name=f"{axis} Position",
                units="MILLIMETER",
                sub_type="ACTUAL"
            )
            self.add_data_item(
                f"{axis}load",
                DataItemCategory.SAMPLE,
                DataItemType.LOAD,
                name=f"{axis} Axis Load",
                units="PERCENT"
            )

        # Spindle
        self.add_data_item(
            "Sspeed",
            DataItemCategory.SAMPLE,
            DataItemType.SPINDLE_SPEED,
            name="Spindle Speed",
            units="REVOLUTION/MINUTE",
            sub_type="ACTUAL"
        )
        self.add_data_item(
            "Sload",
            DataItemCategory.SAMPLE,
            DataItemType.LOAD,
            name="Spindle Load",
            units="PERCENT"
        )

        # Feedrate
        self.add_data_item(
            "path_feedrate",
            DataItemCategory.SAMPLE,
            DataItemType.PATH_FEEDRATE,
            name="Path Feedrate",
            units="MILLIMETER/SECOND",
            sub_type="ACTUAL"
        )

        # Controller events
        self.add_data_item(
            "execution",
            DataItemCategory.EVENT,
            DataItemType.EXECUTION,
            name="Execution State"
        )
        self.add_data_item(
            "mode",
            DataItemCategory.EVENT,
            DataItemType.CONTROLLER_MODE,
            name="Controller Mode"
        )
        self.add_data_item(
            "program",
            DataItemCategory.EVENT,
            DataItemType.PROGRAM,
            name="Active Program"
        )
        self.add_data_item(
            "line",
            DataItemCategory.EVENT,
            DataItemType.LINE,
            name="Program Line"
        )
        self.add_data_item(
            "tool_id",
            DataItemCategory.EVENT,
            DataItemType.TOOL_ID,
            name="Current Tool"
        )
        self.add_data_item(
            "part_count",
            DataItemCategory.EVENT,
            DataItemType.PART_COUNT,
            name="Part Count"
        )
        self.add_data_item(
            "avail",
            DataItemCategory.EVENT,
            DataItemType.AVAILABILITY,
            name="Availability"
        )
        self.add_data_item(
            "estop",
            DataItemCategory.EVENT,
            DataItemType.EMERGENCY_STOP,
            name="Emergency Stop"
        )

        # Conditions
        self.add_data_item(
            "system",
            DataItemCategory.CONDITION,
            DataItemType.SYSTEM,
            name="System Condition"
        )
        self.add_data_item(
            "logic",
            DataItemCategory.CONDITION,
            DataItemType.LOGIC_PROGRAM,
            name="Logic Program Condition"
        )
        self.add_data_item(
            "motion",
            DataItemCategory.CONDITION,
            DataItemType.MOTION_PROGRAM,
            name="Motion Program Condition"
        )

        logger.info("Added standard CNC data items")

    async def start(self) -> bool:
        """
        Start the adapter and connect to agent.

        Returns:
            True if started successfully
        """
        if self._running:
            return True

        self._running = True

        # Connect to agent
        if not await self._connect():
            # Schedule reconnection
            asyncio.create_task(self._reconnect_loop())
            return False

        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info("MTConnect Adapter started")
        return True

    async def stop(self) -> None:
        """Stop the adapter."""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        await self._disconnect()
        logger.info("MTConnect Adapter stopped")

    def update_value(
        self,
        item_id: str,
        value: Any,
        timestamp: Optional[float] = None
    ) -> bool:
        """
        Update a data item value.

        Args:
            item_id: Data item ID
            value: New value
            timestamp: Optional timestamp (defaults to now)

        Returns:
            True if updated and sent
        """
        item = self._data_items.get(item_id)
        if not item:
            logger.warning(f"Unknown data item: {item_id}")
            return False

        # Update local state
        item.value = value
        item.timestamp = timestamp or time.time()
        self._sequence += 1
        item.sequence = self._sequence

        # Send to agent
        if self._connected:
            shdr_line = self._format_shdr(item)
            self._send(shdr_line)

        # Trigger callbacks
        for callback in self._value_callbacks.get(item_id, []):
            try:
                callback(item_id, value, item.timestamp)
            except Exception as e:
                logger.error(f"Value callback error: {e}")

        return True

    def update_condition(
        self,
        item_id: str,
        state: ConditionState,
        native_code: Optional[str] = None,
        native_severity: Optional[str] = None,
        qualifier: Optional[str] = None,
        message: Optional[str] = None
    ) -> bool:
        """
        Update a condition data item.

        Args:
            item_id: Condition data item ID
            state: Condition state
            native_code: Native alarm/error code
            native_severity: Native severity level
            qualifier: LOW or HIGH qualifier
            message: Human-readable message

        Returns:
            True if updated
        """
        item = self._data_items.get(item_id)
        if not item or item.category != DataItemCategory.CONDITION:
            logger.warning(f"Invalid condition item: {item_id}")
            return False

        # Format condition value
        value = {
            "state": state.value,
            "native_code": native_code,
            "native_severity": native_severity,
            "qualifier": qualifier,
            "message": message
        }

        return self.update_value(item_id, value)

    def set_unavailable(self, item_id: Optional[str] = None) -> None:
        """
        Set data item(s) to unavailable.

        Args:
            item_id: Specific item ID, or None for all items
        """
        if item_id:
            self.update_value(item_id, self.SHDR_UNAVAILABLE)
        else:
            for id in self._data_items:
                self.update_value(id, self.SHDR_UNAVAILABLE)

    def on_value_change(self, item_id: str, callback: Callable) -> None:
        """
        Register a value change callback.

        Args:
            item_id: Data item ID to monitor
            callback: Function(item_id, value, timestamp)
        """
        if item_id not in self._value_callbacks:
            self._value_callbacks[item_id] = []
        self._value_callbacks[item_id].append(callback)

    async def _connect(self) -> bool:
        """Connect to MTConnect Agent."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(5.0)
            self._socket.connect((self.config.agent_host, self.config.agent_port))
            self._socket.setblocking(False)

            self._connected = True
            self._reconnect_attempts = 0

            logger.info(f"Connected to agent at {self.config.agent_host}:{self.config.agent_port}")

            # Send initial data
            self._send_initial_data()

            return True

        except Exception as e:
            logger.error(f"Failed to connect to agent: {e}")
            self._connected = False
            return False

    async def _disconnect(self) -> None:
        """Disconnect from agent."""
        self._connected = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    async def _reconnect_loop(self) -> None:
        """Reconnection loop."""
        while self._running and not self._connected:
            if self._reconnect_attempts >= self.config.max_reconnect_attempts:
                logger.error("Maximum reconnection attempts exceeded")
                break

            self._reconnect_attempts += 1
            logger.info(f"Reconnection attempt {self._reconnect_attempts}...")

            await asyncio.sleep(self.config.reconnect_delay)

            if await self._connect():
                # Restart heartbeat
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                break

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while self._running and self._connected:
            try:
                self._send("* PONG " + str(int(self.config.heartbeat_interval * 1000)))
                await asyncio.sleep(self.config.heartbeat_interval)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await self._disconnect()
                asyncio.create_task(self._reconnect_loop())
                break

    def _send_initial_data(self) -> None:
        """Send initial data item values."""
        for item in self._data_items.values():
            shdr_line = self._format_shdr(item)
            self._send(shdr_line)

    def _send(self, data: str) -> bool:
        """Send data to agent."""
        if not self._connected or not self._socket:
            return False

        try:
            self._socket.sendall((data + "\n").encode('utf-8'))
            return True
        except Exception as e:
            logger.error(f"Send error: {e}")
            return False

    def _format_shdr(self, item: DataItem) -> str:
        """Format data item as SHDR line."""
        # Timestamp
        ts = datetime.fromtimestamp(item.timestamp)
        timestamp_str = ts.strftime(self.SHDR_TIMESTAMP_FORMAT)

        if item.category == DataItemCategory.CONDITION:
            # Condition format: timestamp|item_id|state|native_code|native_severity|qualifier|message
            if isinstance(item.value, dict):
                parts = [
                    timestamp_str,
                    item.id,
                    item.value.get("state", "NORMAL"),
                    item.value.get("native_code", ""),
                    item.value.get("native_severity", ""),
                    item.value.get("qualifier", ""),
                    item.value.get("message", "")
                ]
                return "|".join(parts)
            return f"{timestamp_str}|{item.id}|NORMAL"
        else:
            # Sample/Event format: timestamp|item_id|value
            return f"{timestamp_str}|{item.id}|{item.value}"

    def get_data_item(self, item_id: str) -> Optional[DataItem]:
        """Get a data item by ID."""
        return self._data_items.get(item_id)

    def get_all_data_items(self) -> Dict[str, DataItem]:
        """Get all data items."""
        return dict(self._data_items)

    @property
    def is_connected(self) -> bool:
        """Check if connected to agent."""
        return self._connected

    def get_adapter_info(self) -> Dict[str, Any]:
        """Get adapter information."""
        return {
            "device_uuid": self.config.device_uuid,
            "device_name": self.config.device_name,
            "connected": self._connected,
            "agent_host": self.config.agent_host,
            "agent_port": self.config.agent_port,
            "data_item_count": len(self._data_items),
            "sequence": self._sequence
        }
