"""
MTConnect Agent Implementation

Provides MTConnect interface for LEGO MCP Manufacturing System.
Implements the MTConnect standard for manufacturing equipment interoperability.

Standards:
- MTConnect Version 2.2
- ANSI/MTC1.4-2018

Author: LEGO MCP Engineering Team
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Callable
from datetime import datetime, timezone
from enum import Enum, auto
from xml.etree import ElementTree as ET
import threading
import time
import uuid
import re

logger = logging.getLogger(__name__)


# MTConnect Namespaces
MTCONNECT_NS = "urn:mtconnect.org:MTConnectDevices:2.2"
MTCONNECT_STREAMS_NS = "urn:mtconnect.org:MTConnectStreams:2.2"


class MTConnectCategory(Enum):
    """MTConnect data item categories."""
    SAMPLE = "SAMPLE"       # Numeric values that change over time
    EVENT = "EVENT"         # State changes
    CONDITION = "CONDITION" # Alarm/warning conditions


class MTConnectRepresentation(Enum):
    """MTConnect data representations."""
    VALUE = "VALUE"
    TIME_SERIES = "TIME_SERIES"
    DISCRETE = "DISCRETE"
    DATA_SET = "DATA_SET"
    TABLE = "TABLE"


class ConditionLevel(Enum):
    """MTConnect condition levels."""
    UNAVAILABLE = "UNAVAILABLE"
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    FAULT = "FAULT"


@dataclass
class DataItem:
    """MTConnect Data Item definition."""
    id: str
    name: str
    category: MTConnectCategory
    type: str
    sub_type: Optional[str] = None
    units: Optional[str] = None
    native_units: Optional[str] = None
    representation: MTConnectRepresentation = MTConnectRepresentation.VALUE
    coordinate_system: Optional[str] = None
    significant_digits: Optional[int] = None

    def to_xml(self) -> ET.Element:
        """Convert to XML element."""
        elem = ET.Element("DataItem")
        elem.set("id", self.id)
        elem.set("name", self.name)
        elem.set("category", self.category.value)
        elem.set("type", self.type)
        if self.sub_type:
            elem.set("subType", self.sub_type)
        if self.units:
            elem.set("units", self.units)
        if self.native_units:
            elem.set("nativeUnits", self.native_units)
        if self.representation != MTConnectRepresentation.VALUE:
            elem.set("representation", self.representation.value)
        return elem


@dataclass
class Observation:
    """MTConnect Observation (data value)."""
    data_item_id: str
    timestamp: datetime
    sequence: int
    value: Any
    condition_level: Optional[ConditionLevel] = None
    native_code: Optional[str] = None
    native_severity: Optional[str] = None
    qualifier: Optional[str] = None

    def to_xml(self, tag_name: str) -> ET.Element:
        """Convert to XML element."""
        elem = ET.Element(tag_name)
        elem.set("dataItemId", self.data_item_id)
        elem.set("timestamp", self.timestamp.isoformat())
        elem.set("sequence", str(self.sequence))
        if self.condition_level:
            elem.text = str(self.value) if self.value else ""
            if self.native_code:
                elem.set("nativeCode", self.native_code)
        else:
            elem.text = str(self.value) if self.value is not None else "UNAVAILABLE"
        return elem


@dataclass
class Component:
    """MTConnect Component (part of a device)."""
    id: str
    name: str
    component_type: str
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    data_items: List[DataItem] = field(default_factory=list)
    sub_components: List["Component"] = field(default_factory=list)

    def add_data_item(self, data_item: DataItem) -> None:
        """Add a data item to this component."""
        self.data_items.append(data_item)

    def to_xml(self) -> ET.Element:
        """Convert to XML element."""
        elem = ET.Element(self.component_type)
        elem.set("id", self.id)
        elem.set("name", self.name)
        elem.set("uuid", self.uuid)

        if self.description:
            desc = ET.SubElement(elem, "Description")
            desc.text = self.description

        if self.data_items:
            data_items_elem = ET.SubElement(elem, "DataItems")
            for item in self.data_items:
                data_items_elem.append(item.to_xml())

        if self.sub_components:
            components_elem = ET.SubElement(elem, "Components")
            for comp in self.sub_components:
                components_elem.append(comp.to_xml())

        return elem


@dataclass
class Device:
    """MTConnect Device."""
    id: str
    name: str
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    description: str = ""
    components: List[Component] = field(default_factory=list)
    data_items: List[DataItem] = field(default_factory=list)

    def add_component(self, component: Component) -> None:
        """Add a component to this device."""
        self.components.append(component)

    def add_data_item(self, data_item: DataItem) -> None:
        """Add a device-level data item."""
        self.data_items.append(data_item)

    def get_all_data_items(self) -> List[DataItem]:
        """Get all data items from device and components."""
        items = list(self.data_items)

        def collect_from_component(comp: Component):
            items.extend(comp.data_items)
            for sub in comp.sub_components:
                collect_from_component(sub)

        for comp in self.components:
            collect_from_component(comp)

        return items

    def to_xml(self) -> ET.Element:
        """Convert to XML element."""
        elem = ET.Element("Device")
        elem.set("id", self.id)
        elem.set("name", self.name)
        elem.set("uuid", self.uuid)

        if self.manufacturer or self.model or self.serial_number:
            desc = ET.SubElement(elem, "Description")
            if self.manufacturer:
                desc.set("manufacturer", self.manufacturer)
            if self.model:
                desc.set("model", self.model)
            if self.serial_number:
                desc.set("serialNumber", self.serial_number)
            if self.description:
                desc.text = self.description

        if self.data_items:
            data_items_elem = ET.SubElement(elem, "DataItems")
            for item in self.data_items:
                data_items_elem.append(item.to_xml())

        if self.components:
            components_elem = ET.SubElement(elem, "Components")
            for comp in self.components:
                components_elem.append(comp.to_xml())

        return elem


class MTConnectAgent:
    """
    MTConnect Agent for LEGO MCP Manufacturing System.

    Features:
    - Device model management
    - Observation/Sample/Condition streaming
    - SHDR adapter support
    - REST API endpoints (probe, current, sample)

    Usage:
        agent = MTConnectAgent(instance_id=1)

        # Add device
        device = agent.add_device("CNC_001", "CNC Machine 1")

        # Add data items
        agent.add_data_item("CNC_001", "spindle_speed", "SAMPLE", "SPINDLE_SPEED", units="REVOLUTION/MINUTE")

        # Update values
        agent.update_value("spindle_speed", 12000)

        # Start agent
        agent.start()
    """

    def __init__(
        self,
        instance_id: int = 1,
        sender: str = "LEGO_MCP",
        buffer_size: int = 131072,
        port: int = 5000,
    ):
        self.instance_id = instance_id
        self.sender = sender
        self.buffer_size = buffer_size
        self.port = port

        self.devices: Dict[str, Device] = {}
        self.data_items: Dict[str, DataItem] = {}
        self.observations: Dict[str, Observation] = {}

        self._sequence = 0
        self._first_sequence = 1
        self._next_sequence = 1

        self._running = False
        self._server_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._shdr_adapters: Dict[str, Callable] = {}

        logger.info(f"MTConnect Agent initialized (instance={instance_id})")

    def add_device(
        self,
        device_id: str,
        name: str,
        manufacturer: str = "LEGO MCP",
        model: str = "",
        serial_number: str = "",
        description: str = "",
    ) -> Device:
        """Add a device to the agent."""
        device = Device(
            id=device_id,
            name=name,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
            description=description,
        )
        self.devices[device_id] = device
        logger.info(f"Added MTConnect device: {device_id}")
        return device

    def add_component(
        self,
        device_id: str,
        component_id: str,
        name: str,
        component_type: str,
        description: str = "",
    ) -> Component:
        """Add a component to a device."""
        device = self.devices.get(device_id)
        if not device:
            raise ValueError(f"Device not found: {device_id}")

        component = Component(
            id=component_id,
            name=name,
            component_type=component_type,
            description=description,
        )
        device.add_component(component)
        return component

    def add_data_item(
        self,
        device_id: str,
        item_id: str,
        category: str,
        item_type: str,
        name: Optional[str] = None,
        sub_type: Optional[str] = None,
        units: Optional[str] = None,
        component_id: Optional[str] = None,
    ) -> DataItem:
        """Add a data item to a device or component."""
        device = self.devices.get(device_id)
        if not device:
            raise ValueError(f"Device not found: {device_id}")

        data_item = DataItem(
            id=item_id,
            name=name or item_id,
            category=MTConnectCategory[category.upper()],
            type=item_type,
            sub_type=sub_type,
            units=units,
        )

        # Add to device or component
        if component_id:
            for comp in device.components:
                if comp.id == component_id:
                    comp.add_data_item(data_item)
                    break
        else:
            device.add_data_item(data_item)

        # Track data item
        self.data_items[item_id] = data_item

        # Initialize with UNAVAILABLE
        self._add_observation(item_id, "UNAVAILABLE")

        return data_item

    def update_value(
        self,
        item_id: str,
        value: Any,
        condition_level: Optional[str] = None,
        native_code: Optional[str] = None,
    ) -> bool:
        """Update a data item value."""
        if item_id not in self.data_items:
            logger.warning(f"Data item not found: {item_id}")
            return False

        level = ConditionLevel[condition_level.upper()] if condition_level else None
        self._add_observation(item_id, value, level, native_code)
        return True

    def _add_observation(
        self,
        item_id: str,
        value: Any,
        condition_level: Optional[ConditionLevel] = None,
        native_code: Optional[str] = None,
    ) -> None:
        """Add an observation to the buffer."""
        with self._lock:
            self._sequence += 1

            observation = Observation(
                data_item_id=item_id,
                timestamp=datetime.now(timezone.utc),
                sequence=self._sequence,
                value=value,
                condition_level=condition_level,
                native_code=native_code,
            )

            self.observations[item_id] = observation
            self._next_sequence = self._sequence + 1

    def get_probe(self) -> str:
        """Get MTConnectDevices XML (probe response)."""
        root = ET.Element("MTConnectDevices")
        root.set("xmlns", MTCONNECT_NS)

        # Header
        header = ET.SubElement(root, "Header")
        header.set("instanceId", str(self.instance_id))
        header.set("sender", self.sender)
        header.set("bufferSize", str(self.buffer_size))
        header.set("version", "2.2")
        header.set("creationTime", datetime.now(timezone.utc).isoformat())

        # Devices
        devices_elem = ET.SubElement(root, "Devices")
        for device in self.devices.values():
            devices_elem.append(device.to_xml())

        return ET.tostring(root, encoding="unicode")

    def get_current(self, path: Optional[str] = None) -> str:
        """Get MTConnectStreams XML (current response)."""
        root = ET.Element("MTConnectStreams")
        root.set("xmlns", MTCONNECT_STREAMS_NS)

        # Header
        header = ET.SubElement(root, "Header")
        header.set("instanceId", str(self.instance_id))
        header.set("sender", self.sender)
        header.set("bufferSize", str(self.buffer_size))
        header.set("version", "2.2")
        header.set("creationTime", datetime.now(timezone.utc).isoformat())
        header.set("firstSequence", str(self._first_sequence))
        header.set("nextSequence", str(self._next_sequence))
        header.set("lastSequence", str(self._sequence))

        # Streams
        streams = ET.SubElement(root, "Streams")

        for device_id, device in self.devices.items():
            device_stream = ET.SubElement(streams, "DeviceStream")
            device_stream.set("name", device.name)
            device_stream.set("uuid", device.uuid)

            # Group observations by component
            component_stream = ET.SubElement(device_stream, "ComponentStream")
            component_stream.set("component", "Device")
            component_stream.set("componentId", device.id)

            samples = ET.SubElement(component_stream, "Samples")
            events = ET.SubElement(component_stream, "Events")
            conditions = ET.SubElement(component_stream, "Condition")

            for item in device.get_all_data_items():
                if item.id in self.observations:
                    obs = self.observations[item.id]

                    if item.category == MTConnectCategory.SAMPLE:
                        samples.append(obs.to_xml(item.type))
                    elif item.category == MTConnectCategory.EVENT:
                        events.append(obs.to_xml(item.type))
                    elif item.category == MTConnectCategory.CONDITION:
                        conditions.append(obs.to_xml(item.type))

        return ET.tostring(root, encoding="unicode")

    def process_shdr(self, shdr_line: str) -> None:
        """Process a SHDR (Simple Hierarchical Data Representation) line."""
        # SHDR format: timestamp|key=value|key=value...
        # or: timestamp|key|value

        parts = shdr_line.strip().split("|")
        if len(parts) < 2:
            return

        timestamp_str = parts[0]
        try:
            # ISO format timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except ValueError:
            timestamp = datetime.now(timezone.utc)

        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
            else:
                # Key|value format
                continue

            if key in self.data_items:
                self.update_value(key.strip(), value.strip())

    def start(self) -> None:
        """Start the MTConnect agent."""
        if self._running:
            return

        self._running = True
        logger.info(f"MTConnect Agent starting on port {self.port}")

        # Note: In production, integrate with actual HTTP server
        self._server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self._server_thread.start()

    def stop(self) -> None:
        """Stop the MTConnect agent."""
        self._running = False
        if self._server_thread:
            self._server_thread.join(timeout=5.0)
        logger.info("MTConnect Agent stopped")

    def _server_loop(self) -> None:
        """Main server loop."""
        while self._running:
            # Stub: In production, handle HTTP requests
            time.sleep(1.0)

    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            "instance_id": self.instance_id,
            "sender": self.sender,
            "port": self.port,
            "running": self._running,
            "device_count": len(self.devices),
            "data_item_count": len(self.data_items),
            "current_sequence": self._sequence,
        }


# Factory function
def create_mtconnect_agent(port: int = 5000) -> MTConnectAgent:
    """Create and configure an MTConnect agent for LEGO MCP."""
    agent = MTConnectAgent(port=port)

    # Add CNC device
    agent.add_device(
        "cnc_001",
        "CNC Machine 1",
        manufacturer="LEGO MCP",
        model="CNC-3AXIS",
        description="3-axis CNC milling machine"
    )

    # Add CNC data items
    agent.add_data_item("cnc_001", "spindle_speed", "SAMPLE", "SPINDLE_SPEED", units="REVOLUTION/MINUTE")
    agent.add_data_item("cnc_001", "feed_rate", "SAMPLE", "PATH_FEEDRATE", units="MILLIMETER/SECOND")
    agent.add_data_item("cnc_001", "x_position", "SAMPLE", "POSITION", sub_type="ACTUAL", units="MILLIMETER")
    agent.add_data_item("cnc_001", "y_position", "SAMPLE", "POSITION", sub_type="ACTUAL", units="MILLIMETER")
    agent.add_data_item("cnc_001", "z_position", "SAMPLE", "POSITION", sub_type="ACTUAL", units="MILLIMETER")
    agent.add_data_item("cnc_001", "execution", "EVENT", "EXECUTION")
    agent.add_data_item("cnc_001", "program", "EVENT", "PROGRAM")
    agent.add_data_item("cnc_001", "system", "CONDITION", "SYSTEM")

    # Add 3D Printer device
    agent.add_device(
        "printer_001",
        "3D Printer 1",
        manufacturer="LEGO MCP",
        model="FDM-001",
        description="FDM 3D printer"
    )

    # Add printer data items
    agent.add_data_item("printer_001", "extruder_temp", "SAMPLE", "TEMPERATURE", sub_type="ACTUAL", units="CELSIUS")
    agent.add_data_item("printer_001", "bed_temp", "SAMPLE", "TEMPERATURE", sub_type="ACTUAL", units="CELSIUS")
    agent.add_data_item("printer_001", "layer", "EVENT", "BLOCK")
    agent.add_data_item("printer_001", "execution", "EVENT", "EXECUTION")

    return agent


__all__ = [
    "MTConnectAgent",
    "Device",
    "Component",
    "DataItem",
    "Observation",
    "MTConnectCategory",
    "ConditionLevel",
    "create_mtconnect_agent",
]
