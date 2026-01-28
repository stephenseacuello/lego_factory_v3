"""
MTConnect Device Model

Defines MTConnect device structure for manufacturing equipment.

Reference: MTConnect Standard v2.0 (Device Information Model)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """MTConnect Component Types."""
    CONTROLLER = "Controller"
    PATH = "Path"
    AXES = "Axes"
    LINEAR = "Linear"
    ROTARY = "Rotary"
    SPINDLE = "Spindle"
    SYSTEMS = "Systems"
    COOLANT = "Coolant"
    HYDRAULIC = "Hydraulic"
    PNEUMATIC = "Pneumatic"
    ELECTRIC = "Electric"
    DOOR = "Door"
    CHUCK = "Chuck"
    WORKHOLDING = "Workholding"
    TOOL_MAGAZINE = "ToolMagazine"


class DataItemCategory(Enum):
    """Data item category."""
    SAMPLE = "SAMPLE"
    EVENT = "EVENT"
    CONDITION = "CONDITION"


class DataItemType(Enum):
    """Data item type."""
    POSITION = "POSITION"
    VELOCITY = "VELOCITY"
    LOAD = "LOAD"
    TEMPERATURE = "TEMPERATURE"
    SPINDLE_SPEED = "SPINDLE_SPEED"
    PATH_FEEDRATE = "PATH_FEEDRATE"
    EXECUTION = "EXECUTION"
    CONTROLLER_MODE = "CONTROLLER_MODE"
    PROGRAM = "PROGRAM"
    LINE = "LINE"
    TOOL_ID = "TOOL_ID"
    PART_COUNT = "PART_COUNT"
    AVAILABILITY = "AVAILABILITY"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    SYSTEM = "SYSTEM"


@dataclass
class MTConnectDataItem:
    """MTConnect Data Item definition."""
    id: str
    name: str
    category: DataItemCategory
    type: DataItemType
    sub_type: Optional[str] = None
    units: Optional[str] = None
    native_units: Optional[str] = None
    native_scale: float = 1.0
    coordinate_system: Optional[str] = None
    representation: Optional[str] = None  # VALUE, TIME_SERIES, DISCRETE, etc.
    sample_rate: Optional[float] = None


@dataclass
class MTConnectComponent:
    """MTConnect Component (axis, controller, etc.)."""
    id: str
    name: str
    type: ComponentType
    native_name: Optional[str] = None
    description: Optional[str] = None
    uuid: Optional[str] = None

    # Child components
    components: List["MTConnectComponent"] = field(default_factory=list)

    # Data items for this component
    data_items: List[MTConnectDataItem] = field(default_factory=list)

    def add_component(
        self,
        id: str,
        name: str,
        type: ComponentType,
        **kwargs
    ) -> "MTConnectComponent":
        """Add a child component."""
        component = MTConnectComponent(
            id=id,
            name=name,
            type=type,
            **kwargs
        )
        self.components.append(component)
        return component

    def add_data_item(
        self,
        id: str,
        name: str,
        category: DataItemCategory,
        type: DataItemType,
        **kwargs
    ) -> MTConnectDataItem:
        """Add a data item to this component."""
        item = MTConnectDataItem(
            id=id,
            name=name,
            category=category,
            type=type,
            **kwargs
        )
        self.data_items.append(item)
        return item


@dataclass
class MTConnectDevice:
    """
    MTConnect Device definition.

    Represents a complete manufacturing device with its
    component hierarchy and data items.

    Usage:
        >>> device = MTConnectDevice("cnc-001", "Haas VF-2")
        >>> device.add_standard_cnc_components()
        >>> agent.add_device(device)
    """
    uuid: str
    name: str
    id: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    station_id: Optional[str] = None
    iso841_class: Optional[str] = None
    description: Optional[str] = None

    # Root component
    components: List[MTConnectComponent] = field(default_factory=list)

    # Device-level data items
    data_items: List[MTConnectDataItem] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = self.uuid

    def add_component(
        self,
        id: str,
        name: str,
        type: ComponentType,
        **kwargs
    ) -> MTConnectComponent:
        """Add a top-level component."""
        component = MTConnectComponent(
            id=id,
            name=name,
            type=type,
            **kwargs
        )
        self.components.append(component)
        return component

    def add_data_item(
        self,
        id: str,
        name: str,
        category: DataItemCategory,
        type: DataItemType,
        **kwargs
    ) -> MTConnectDataItem:
        """Add a device-level data item."""
        item = MTConnectDataItem(
            id=id,
            name=name,
            category=category,
            type=type,
            **kwargs
        )
        self.data_items.append(item)
        return item

    def add_standard_cnc_components(self) -> None:
        """Add standard CNC machine components."""
        # Controller
        controller = self.add_component(
            f"{self.id}_controller",
            "Controller",
            ComponentType.CONTROLLER
        )

        # Controller data items
        controller.add_data_item(
            f"{self.id}_avail", "Availability",
            DataItemCategory.EVENT, DataItemType.AVAILABILITY
        )
        controller.add_data_item(
            f"{self.id}_estop", "Emergency Stop",
            DataItemCategory.EVENT, DataItemType.EMERGENCY_STOP
        )

        # Path (program execution)
        path = controller.add_component(
            f"{self.id}_path", "Path",
            ComponentType.PATH
        )
        path.add_data_item(
            f"{self.id}_exec", "Execution",
            DataItemCategory.EVENT, DataItemType.EXECUTION
        )
        path.add_data_item(
            f"{self.id}_mode", "Controller Mode",
            DataItemCategory.EVENT, DataItemType.CONTROLLER_MODE
        )
        path.add_data_item(
            f"{self.id}_program", "Program",
            DataItemCategory.EVENT, DataItemType.PROGRAM
        )
        path.add_data_item(
            f"{self.id}_line", "Line",
            DataItemCategory.EVENT, DataItemType.LINE
        )
        path.add_data_item(
            f"{self.id}_feedrate", "Path Feedrate",
            DataItemCategory.SAMPLE, DataItemType.PATH_FEEDRATE,
            units="MILLIMETER/SECOND"
        )
        path.add_data_item(
            f"{self.id}_tool", "Tool ID",
            DataItemCategory.EVENT, DataItemType.TOOL_ID
        )

        # Axes
        axes = controller.add_component(
            f"{self.id}_axes", "Axes",
            ComponentType.AXES
        )

        # Linear axes
        for axis_name in ['X', 'Y', 'Z']:
            axis = axes.add_component(
                f"{self.id}_{axis_name.lower()}",
                f"{axis_name} Axis",
                ComponentType.LINEAR,
                native_name=axis_name
            )
            axis.add_data_item(
                f"{self.id}_{axis_name.lower()}pos",
                f"{axis_name} Position",
                DataItemCategory.SAMPLE, DataItemType.POSITION,
                units="MILLIMETER", sub_type="ACTUAL"
            )
            axis.add_data_item(
                f"{self.id}_{axis_name.lower()}load",
                f"{axis_name} Load",
                DataItemCategory.SAMPLE, DataItemType.LOAD,
                units="PERCENT"
            )

        # Spindle
        spindle = controller.add_component(
            f"{self.id}_spindle", "Spindle",
            ComponentType.SPINDLE
        )
        spindle.add_data_item(
            f"{self.id}_Sspeed", "Spindle Speed",
            DataItemCategory.SAMPLE, DataItemType.SPINDLE_SPEED,
            units="REVOLUTION/MINUTE", sub_type="ACTUAL"
        )
        spindle.add_data_item(
            f"{self.id}_Sload", "Spindle Load",
            DataItemCategory.SAMPLE, DataItemType.LOAD,
            units="PERCENT"
        )

        # Systems
        systems = controller.add_component(
            f"{self.id}_systems", "Systems",
            ComponentType.SYSTEMS
        )

        # Coolant
        coolant = systems.add_component(
            f"{self.id}_coolant", "Coolant",
            ComponentType.COOLANT
        )
        coolant.add_data_item(
            f"{self.id}_coolant_temp", "Coolant Temperature",
            DataItemCategory.SAMPLE, DataItemType.TEMPERATURE,
            units="CELSIUS"
        )

        # Part count
        self.add_data_item(
            f"{self.id}_part_count", "Part Count",
            DataItemCategory.EVENT, DataItemType.PART_COUNT
        )

        logger.info(f"Added standard CNC components to {self.name}")

    def add_standard_printer_components(self) -> None:
        """Add standard 3D printer components."""
        # Controller
        controller = self.add_component(
            f"{self.id}_controller",
            "Controller",
            ComponentType.CONTROLLER
        )

        controller.add_data_item(
            f"{self.id}_avail", "Availability",
            DataItemCategory.EVENT, DataItemType.AVAILABILITY
        )
        controller.add_data_item(
            f"{self.id}_exec", "Execution",
            DataItemCategory.EVENT, DataItemType.EXECUTION
        )

        # Path (print job)
        path = controller.add_component(
            f"{self.id}_path", "Path",
            ComponentType.PATH
        )
        path.add_data_item(
            f"{self.id}_program", "G-Code File",
            DataItemCategory.EVENT, DataItemType.PROGRAM
        )
        path.add_data_item(
            f"{self.id}_line", "Line",
            DataItemCategory.EVENT, DataItemType.LINE
        )
        path.add_data_item(
            f"{self.id}_feedrate", "Print Speed",
            DataItemCategory.SAMPLE, DataItemType.PATH_FEEDRATE,
            units="MILLIMETER/SECOND"
        )

        # Axes
        axes = controller.add_component(
            f"{self.id}_axes", "Axes",
            ComponentType.AXES
        )

        for axis_name in ['X', 'Y', 'Z']:
            axis = axes.add_component(
                f"{self.id}_{axis_name.lower()}",
                f"{axis_name} Axis",
                ComponentType.LINEAR,
                native_name=axis_name
            )
            axis.add_data_item(
                f"{self.id}_{axis_name.lower()}pos",
                f"{axis_name} Position",
                DataItemCategory.SAMPLE, DataItemType.POSITION,
                units="MILLIMETER"
            )

        # Extruder temperature
        self.add_data_item(
            f"{self.id}_nozzle_temp", "Nozzle Temperature",
            DataItemCategory.SAMPLE, DataItemType.TEMPERATURE,
            units="CELSIUS"
        )
        self.add_data_item(
            f"{self.id}_bed_temp", "Bed Temperature",
            DataItemCategory.SAMPLE, DataItemType.TEMPERATURE,
            units="CELSIUS"
        )

        # Part count
        self.add_data_item(
            f"{self.id}_part_count", "Part Count",
            DataItemCategory.EVENT, DataItemType.PART_COUNT
        )

        logger.info(f"Added standard printer components to {self.name}")

    def get_all_data_items(self) -> List[MTConnectDataItem]:
        """Get all data items from device and components."""
        items = list(self.data_items)

        def collect_items(component: MTConnectComponent):
            items.extend(component.data_items)
            for child in component.components:
                collect_items(child)

        for component in self.components:
            collect_items(component)

        return items

    def get_device_info(self) -> Dict[str, Any]:
        """Get device information."""
        return {
            "uuid": self.uuid,
            "name": self.name,
            "id": self.id,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "serial_number": self.serial_number,
            "component_count": len(self.components),
            "data_item_count": len(self.get_all_data_items())
        }
