"""
MTConnect Adapter for LEGO MCP

Implements MTConnect protocol for CNC data streaming:
- Agent (server) mode for data collection
- Adapter (client) mode for equipment connection
- Standard MTConnect data model (ANSI/MTC1.4-2018)

Industry 4.0/5.0 Architecture - ISA-95 Level 0-3 Integration

MTConnect Data Flow:
    Equipment (CNC/Laser) -> Adapter -> Agent -> Client (Dashboard/SCADA)

Endpoints:
    GET /probe     - Device capability description
    GET /current   - Current state snapshot
    GET /sample    - Historical data with sequence numbers
    GET /asset     - Asset metadata

LEGO MCP Manufacturing System v7.0
"""

import asyncio
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from collections import deque
import hashlib
import threading
import time
import json


class ExecutionState(Enum):
    """MTConnect Execution states."""
    ACTIVE = "ACTIVE"
    INTERRUPTED = "INTERRUPTED"
    STOPPED = "STOPPED"
    READY = "READY"
    PROGRAM_STOPPED = "PROGRAM_STOPPED"
    PROGRAM_COMPLETED = "PROGRAM_COMPLETED"
    PROGRAM_OPTIONAL_STOP = "PROGRAM_OPTIONAL_STOP"
    FEED_HOLD = "FEED_HOLD"
    OPTIONAL_STOP = "OPTIONAL_STOP"


class ControllerMode(Enum):
    """MTConnect Controller modes."""
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    MANUAL_DATA_INPUT = "MANUAL_DATA_INPUT"
    SEMI_AUTOMATIC = "SEMI_AUTOMATIC"


class AvailabilityState(Enum):
    """MTConnect Availability states."""
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class EmergencyStop(Enum):
    """MTConnect Emergency Stop states."""
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"


class ConditionState(Enum):
    """MTConnect Condition states."""
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    FAULT = "FAULT"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class DataItem:
    """MTConnect Data Item definition."""
    id: str
    name: str
    category: str  # SAMPLE, EVENT, CONDITION
    type: str  # POSITION, EXECUTION, etc.
    sub_type: Optional[str] = None
    units: Optional[str] = None
    native_units: Optional[str] = None
    coordinate_system: Optional[str] = None
    component_id: str = ""


@dataclass
class Observation:
    """MTConnect data observation."""
    data_item_id: str
    timestamp: datetime
    sequence: int
    value: Any
    condition_state: Optional[ConditionState] = None


@dataclass
class Component:
    """MTConnect component (device hierarchy)."""
    id: str
    name: str
    component_type: str  # Device, Controller, Axes, Linear, Rotary, etc.
    uuid: Optional[str] = None
    children: List['Component'] = field(default_factory=list)
    data_items: List[DataItem] = field(default_factory=list)


@dataclass
class Device:
    """MTConnect Device definition."""
    id: str
    name: str
    uuid: str
    iso841_class: Optional[str] = None  # e.g., "6" for milling
    components: List[Component] = field(default_factory=list)
    data_items: List[DataItem] = field(default_factory=list)


class MTConnectAdapter:
    """
    MTConnect Adapter for CNC equipment.

    Collects data from equipment and formats it for MTConnect agents.
    Supports SHDR (Simple Hierarchical Data Representation) protocol.

    Usage:
        adapter = MTConnectAdapter(equipment_id="bantam_cnc")
        adapter.add_data_item("execution", "EVENT", "EXECUTION")
        adapter.update_value("execution", ExecutionState.ACTIVE.value)
        shdr_output = adapter.get_shdr_data()
    """

    def __init__(
        self,
        equipment_id: str,
        equipment_name: str,
        agent_host: str = "localhost",
        agent_port: int = 7878,
    ):
        """
        Initialize MTConnect adapter.

        Args:
            equipment_id: Unique equipment identifier
            equipment_name: Human-readable equipment name
            agent_host: MTConnect agent host
            agent_port: MTConnect agent port
        """
        self.equipment_id = equipment_id
        self.equipment_name = equipment_name
        self.agent_host = agent_host
        self.agent_port = agent_port

        self._data_items: Dict[str, DataItem] = {}
        self._current_values: Dict[str, Any] = {}
        self._observations: deque = deque(maxlen=10000)
        self._sequence = 0
        self._lock = threading.RLock()

        # Initialize standard CNC data items
        self._initialize_cnc_data_items()

    def _initialize_cnc_data_items(self):
        """Initialize standard CNC data items per MTConnect specification."""

        # Availability
        self.add_data_item(DataItem(
            id=f"{self.equipment_id}_avail",
            name="availability",
            category="EVENT",
            type="AVAILABILITY",
            component_id=self.equipment_id,
        ))

        # Emergency Stop
        self.add_data_item(DataItem(
            id=f"{self.equipment_id}_estop",
            name="emergency_stop",
            category="EVENT",
            type="EMERGENCY_STOP",
            component_id=self.equipment_id,
        ))

        # Execution
        self.add_data_item(DataItem(
            id=f"{self.equipment_id}_exec",
            name="execution",
            category="EVENT",
            type="EXECUTION",
            component_id=f"{self.equipment_id}_controller",
        ))

        # Controller Mode
        self.add_data_item(DataItem(
            id=f"{self.equipment_id}_mode",
            name="controller_mode",
            category="EVENT",
            type="CONTROLLER_MODE",
            component_id=f"{self.equipment_id}_controller",
        ))

        # Program
        self.add_data_item(DataItem(
            id=f"{self.equipment_id}_prog",
            name="program",
            category="EVENT",
            type="PROGRAM",
            component_id=f"{self.equipment_id}_controller",
        ))

        # Axis Positions (X, Y, Z)
        for axis in ["X", "Y", "Z"]:
            self.add_data_item(DataItem(
                id=f"{self.equipment_id}_{axis.lower()}pos",
                name=f"{axis}_position",
                category="SAMPLE",
                type="POSITION",
                sub_type="ACTUAL",
                units="MILLIMETER",
                component_id=f"{self.equipment_id}_{axis.lower()}axis",
            ))

        # Spindle Speed
        self.add_data_item(DataItem(
            id=f"{self.equipment_id}_sspeed",
            name="spindle_speed",
            category="SAMPLE",
            type="SPINDLE_SPEED",
            sub_type="ACTUAL",
            units="REVOLUTION/MINUTE",
            component_id=f"{self.equipment_id}_spindle",
        ))

        # Feed Rate
        self.add_data_item(DataItem(
            id=f"{self.equipment_id}_feed",
            name="path_feedrate",
            category="SAMPLE",
            type="PATH_FEEDRATE",
            sub_type="ACTUAL",
            units="MILLIMETER/SECOND",
            component_id=f"{self.equipment_id}_path",
        ))

        # System Condition
        self.add_data_item(DataItem(
            id=f"{self.equipment_id}_system",
            name="system_condition",
            category="CONDITION",
            type="SYSTEM",
            component_id=self.equipment_id,
        ))

    def add_data_item(self, data_item: DataItem):
        """Add a data item to the adapter."""
        with self._lock:
            self._data_items[data_item.id] = data_item
            self._current_values[data_item.id] = "UNAVAILABLE"

    def update_value(self, data_item_id: str, value: Any, timestamp: Optional[datetime] = None):
        """
        Update a data item value.

        Args:
            data_item_id: Data item ID
            value: New value
            timestamp: Optional timestamp (defaults to now)
        """
        with self._lock:
            if data_item_id not in self._data_items:
                return

            self._sequence += 1
            ts = timestamp or datetime.now()

            self._current_values[data_item_id] = value

            observation = Observation(
                data_item_id=data_item_id,
                timestamp=ts,
                sequence=self._sequence,
                value=value,
            )
            self._observations.append(observation)

    def update_condition(
        self,
        data_item_id: str,
        state: ConditionState,
        native_code: Optional[str] = None,
        message: Optional[str] = None,
    ):
        """
        Update a condition data item.

        Args:
            data_item_id: Data item ID
            state: Condition state
            native_code: Native alarm/error code
            message: Condition message
        """
        with self._lock:
            if data_item_id not in self._data_items:
                return

            self._sequence += 1

            observation = Observation(
                data_item_id=data_item_id,
                timestamp=datetime.now(),
                sequence=self._sequence,
                value={"state": state.value, "native_code": native_code, "message": message},
                condition_state=state,
            )
            self._observations.append(observation)

    def get_shdr_data(self) -> str:
        """
        Get SHDR formatted data for agent connection.

        Returns:
            SHDR formatted string
        """
        with self._lock:
            lines = []
            ts = datetime.now().isoformat()

            for item_id, value in self._current_values.items():
                if isinstance(value, dict):
                    # Condition
                    state = value.get("state", "UNAVAILABLE")
                    native_code = value.get("native_code", "")
                    message = value.get("message", "")
                    lines.append(f"{ts}|{item_id}|{state}|{native_code}|{message}")
                else:
                    lines.append(f"{ts}|{item_id}|{value}")

            return "\n".join(lines)

    def get_current_state(self) -> Dict:
        """Get current state as dictionary."""
        with self._lock:
            return {
                item_id: {
                    "data_item": self._data_items[item_id].name,
                    "type": self._data_items[item_id].type,
                    "category": self._data_items[item_id].category,
                    "value": value,
                }
                for item_id, value in self._current_values.items()
            }


class MTConnectAgent:
    """
    MTConnect Agent (Server).

    Provides HTTP REST API endpoints for MTConnect clients:
    - /probe - Device capability
    - /current - Current state
    - /sample - Historical samples

    Usage:
        agent = MTConnectAgent(port=5001)
        agent.add_device(device)
        agent.add_adapter(adapter)
        await agent.start()
    """

    def __init__(
        self,
        instance_id: str = "lego_mcp_agent",
        sender: str = "LEGO_MCP",
        version: str = "1.8",
        buffer_size: int = 131072,
        port: int = 5001,
    ):
        """
        Initialize MTConnect agent.

        Args:
            instance_id: Agent instance ID
            sender: Sender identification
            version: MTConnect version
            buffer_size: Circular buffer size
            port: HTTP port
        """
        self.instance_id = instance_id
        self.sender = sender
        self.version = version
        self.buffer_size = buffer_size
        self.port = port

        self._devices: Dict[str, Device] = {}
        self._adapters: Dict[str, MTConnectAdapter] = {}
        self._observations: deque = deque(maxlen=buffer_size)
        self._sequence = 0
        self._lock = threading.RLock()
        self._running = False

    def add_device(self, device: Device):
        """Add a device to the agent."""
        with self._lock:
            self._devices[device.id] = device

    def add_adapter(self, adapter: MTConnectAdapter):
        """Connect an adapter to the agent."""
        with self._lock:
            self._adapters[adapter.equipment_id] = adapter

    def generate_probe_xml(self) -> str:
        """
        Generate MTConnectDevices XML (probe response).

        Returns:
            XML string
        """
        root = ET.Element("MTConnectDevices", {
            "xmlns": "urn:mtconnect.org:MTConnectDevices:1.8",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        })

        header = ET.SubElement(root, "Header", {
            "creationTime": datetime.utcnow().isoformat() + "Z",
            "sender": self.sender,
            "instanceId": str(hash(self.instance_id) % 10000000),
            "version": self.version,
            "bufferSize": str(self.buffer_size),
        })

        devices_elem = ET.SubElement(root, "Devices")

        for device in self._devices.values():
            self._add_device_xml(devices_elem, device)

        return ET.tostring(root, encoding="unicode", method="xml")

    def _add_device_xml(self, parent: ET.Element, device: Device):
        """Add device XML to parent element."""
        device_elem = ET.SubElement(parent, "Device", {
            "id": device.id,
            "name": device.name,
            "uuid": device.uuid,
        })
        if device.iso841_class:
            device_elem.set("iso841Class", device.iso841_class)

        # Add data items
        if device.data_items:
            data_items_elem = ET.SubElement(device_elem, "DataItems")
            for item in device.data_items:
                self._add_data_item_xml(data_items_elem, item)

        # Add components
        if device.components:
            components_elem = ET.SubElement(device_elem, "Components")
            for comp in device.components:
                self._add_component_xml(components_elem, comp)

    def _add_component_xml(self, parent: ET.Element, component: Component):
        """Add component XML to parent element."""
        comp_elem = ET.SubElement(parent, component.component_type, {
            "id": component.id,
            "name": component.name,
        })
        if component.uuid:
            comp_elem.set("uuid", component.uuid)

        if component.data_items:
            data_items_elem = ET.SubElement(comp_elem, "DataItems")
            for item in component.data_items:
                self._add_data_item_xml(data_items_elem, item)

        if component.children:
            components_elem = ET.SubElement(comp_elem, "Components")
            for child in component.children:
                self._add_component_xml(components_elem, child)

    def _add_data_item_xml(self, parent: ET.Element, item: DataItem):
        """Add data item XML to parent element."""
        attrs = {
            "id": item.id,
            "name": item.name,
            "category": item.category,
            "type": item.type,
        }
        if item.sub_type:
            attrs["subType"] = item.sub_type
        if item.units:
            attrs["units"] = item.units
        if item.native_units:
            attrs["nativeUnits"] = item.native_units

        ET.SubElement(parent, "DataItem", attrs)

    def generate_current_xml(self) -> str:
        """
        Generate MTConnectStreams XML (current response).

        Returns:
            XML string
        """
        root = ET.Element("MTConnectStreams", {
            "xmlns": "urn:mtconnect.org:MTConnectStreams:1.8",
        })

        header = ET.SubElement(root, "Header", {
            "creationTime": datetime.utcnow().isoformat() + "Z",
            "sender": self.sender,
            "instanceId": str(hash(self.instance_id) % 10000000),
            "version": self.version,
            "bufferSize": str(self.buffer_size),
            "nextSequence": str(self._sequence + 1),
            "firstSequence": str(max(1, self._sequence - len(self._observations) + 1)),
            "lastSequence": str(self._sequence),
        })

        streams_elem = ET.SubElement(root, "Streams")

        # Collect current values from all adapters
        for device_id, adapter in self._adapters.items():
            device_stream = ET.SubElement(streams_elem, "DeviceStream", {
                "name": adapter.equipment_name,
                "uuid": hashlib.md5(device_id.encode()).hexdigest(),
            })

            comp_stream = ET.SubElement(device_stream, "ComponentStream", {
                "component": "Controller",
                "componentId": f"{device_id}_controller",
            })

            current = adapter.get_current_state()
            events_elem = None
            samples_elem = None
            conditions_elem = None

            for item_id, data in current.items():
                category = data["category"]
                if category == "EVENT":
                    if events_elem is None:
                        events_elem = ET.SubElement(comp_stream, "Events")
                    ET.SubElement(events_elem, data["type"], {
                        "dataItemId": item_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "sequence": str(self._sequence),
                    }).text = str(data["value"])

                elif category == "SAMPLE":
                    if samples_elem is None:
                        samples_elem = ET.SubElement(comp_stream, "Samples")
                    ET.SubElement(samples_elem, data["type"], {
                        "dataItemId": item_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "sequence": str(self._sequence),
                    }).text = str(data["value"])

                elif category == "CONDITION":
                    if conditions_elem is None:
                        conditions_elem = ET.SubElement(comp_stream, "Condition")
                    value = data["value"]
                    if isinstance(value, dict):
                        ET.SubElement(conditions_elem, value.get("state", "Normal"), {
                            "dataItemId": item_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "sequence": str(self._sequence),
                        }).text = value.get("message", "")

        return ET.tostring(root, encoding="unicode", method="xml")

    def handle_request(self, path: str, params: Optional[Dict] = None) -> tuple[str, str]:
        """
        Handle MTConnect HTTP request.

        Args:
            path: Request path (/probe, /current, /sample)
            params: Query parameters

        Returns:
            Tuple of (content, content_type)
        """
        if path == "/probe":
            return self.generate_probe_xml(), "application/xml"
        elif path == "/current":
            return self.generate_current_xml(), "application/xml"
        elif path == "/sample":
            # For simplicity, return current for now
            # Full implementation would support sequence-based retrieval
            return self.generate_current_xml(), "application/xml"
        elif path == "/asset":
            # Asset endpoint placeholder
            return "<MTConnectAssets/>", "application/xml"
        else:
            return "<MTConnectError/>", "application/xml"


def create_cnc_device(
    equipment_id: str,
    equipment_name: str,
    manufacturer: str = "LEGO MCP",
    model: str = "CNC Router",
    serial_number: Optional[str] = None,
) -> Device:
    """
    Create a standard CNC device definition.

    Args:
        equipment_id: Unique equipment ID
        equipment_name: Equipment name
        manufacturer: Manufacturer name
        model: Model name
        serial_number: Optional serial number

    Returns:
        Device definition
    """
    device = Device(
        id=equipment_id,
        name=equipment_name,
        uuid=hashlib.md5(f"{equipment_id}{serial_number or ''}".encode()).hexdigest(),
        iso841_class="6",  # Milling machine
    )

    # Controller component
    controller = Component(
        id=f"{equipment_id}_controller",
        name="Controller",
        component_type="Controller",
        data_items=[
            DataItem(
                id=f"{equipment_id}_exec",
                name="execution",
                category="EVENT",
                type="EXECUTION",
            ),
            DataItem(
                id=f"{equipment_id}_mode",
                name="mode",
                category="EVENT",
                type="CONTROLLER_MODE",
            ),
            DataItem(
                id=f"{equipment_id}_prog",
                name="program",
                category="EVENT",
                type="PROGRAM",
            ),
        ],
    )

    # Axes component
    axes = Component(
        id=f"{equipment_id}_axes",
        name="Axes",
        component_type="Axes",
        children=[
            Component(
                id=f"{equipment_id}_x",
                name="X",
                component_type="Linear",
                data_items=[
                    DataItem(
                        id=f"{equipment_id}_xpos",
                        name="Xact",
                        category="SAMPLE",
                        type="POSITION",
                        sub_type="ACTUAL",
                        units="MILLIMETER",
                    ),
                ],
            ),
            Component(
                id=f"{equipment_id}_y",
                name="Y",
                component_type="Linear",
                data_items=[
                    DataItem(
                        id=f"{equipment_id}_ypos",
                        name="Yact",
                        category="SAMPLE",
                        type="POSITION",
                        sub_type="ACTUAL",
                        units="MILLIMETER",
                    ),
                ],
            ),
            Component(
                id=f"{equipment_id}_z",
                name="Z",
                component_type="Linear",
                data_items=[
                    DataItem(
                        id=f"{equipment_id}_zpos",
                        name="Zact",
                        category="SAMPLE",
                        type="POSITION",
                        sub_type="ACTUAL",
                        units="MILLIMETER",
                    ),
                ],
            ),
        ],
    )

    # Spindle component
    spindle = Component(
        id=f"{equipment_id}_spindle",
        name="Spindle",
        component_type="Rotary",
        data_items=[
            DataItem(
                id=f"{equipment_id}_sspeed",
                name="Sspeed",
                category="SAMPLE",
                type="SPINDLE_SPEED",
                sub_type="ACTUAL",
                units="REVOLUTION/MINUTE",
            ),
        ],
    )

    device.components = [controller, axes, spindle]
    device.data_items = [
        DataItem(
            id=f"{equipment_id}_avail",
            name="avail",
            category="EVENT",
            type="AVAILABILITY",
        ),
        DataItem(
            id=f"{equipment_id}_estop",
            name="estop",
            category="EVENT",
            type="EMERGENCY_STOP",
        ),
    ]

    return device
