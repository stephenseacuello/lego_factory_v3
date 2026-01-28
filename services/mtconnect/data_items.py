"""
MTConnect Data Items Definition
===============================
Standard data items per MTConnect specification v2.0.

Reference: https://model.mtconnect.org/

Data Item Categories:
- SAMPLE: Continuously variable numeric values (position, velocity, etc.)
- EVENT: Discrete state changes (execution state, program name, etc.)
- CONDITION: Alarm/fault conditions (normal, warning, fault, unavailable)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime


class DataItemCategory(Enum):
    """MTConnect data item categories."""
    SAMPLE = "SAMPLE"
    EVENT = "EVENT"
    CONDITION = "CONDITION"


class DataItemType(Enum):
    """Common MTConnect data item types."""
    # Samples - Numeric values
    POSITION = "POSITION"
    VELOCITY = "VELOCITY"
    ACCELERATION = "ACCELERATION"
    ANGULAR_VELOCITY = "ANGULAR_VELOCITY"
    LOAD = "LOAD"
    TORQUE = "TORQUE"
    TEMPERATURE = "TEMPERATURE"
    PRESSURE = "PRESSURE"
    AMPERAGE = "AMPERAGE"
    VOLTAGE = "VOLTAGE"
    POWER_FACTOR = "POWER_FACTOR"
    WATTAGE = "WATTAGE"
    FREQUENCY = "FREQUENCY"
    SPINDLE_SPEED = "SPINDLE_SPEED"
    PATH_FEEDRATE = "PATH_FEEDRATE"
    PATH_POSITION = "PATH_POSITION"
    AXIS_FEEDRATE = "AXIS_FEEDRATE"
    ROTARY_VELOCITY = "ROTARY_VELOCITY"
    SOUND_LEVEL = "SOUND_LEVEL"
    VIBRATION = "VIBRATION"

    # Events - Discrete states
    EXECUTION = "EXECUTION"
    CONTROLLER_MODE = "CONTROLLER_MODE"
    AVAILABILITY = "AVAILABILITY"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    PROGRAM = "PROGRAM"
    PROGRAM_COMMENT = "PROGRAM_COMMENT"
    LINE = "LINE"
    BLOCK = "BLOCK"
    PART_COUNT = "PART_COUNT"
    MESSAGE = "MESSAGE"
    ALARM = "ALARM"
    TOOL_ID = "TOOL_ID"
    TOOL_NUMBER = "TOOL_NUMBER"
    SPINDLE_INTERLOCK = "SPINDLE_INTERLOCK"
    DOOR_STATE = "DOOR_STATE"
    ROTARY_MODE = "ROTARY_MODE"
    AXIS_STATE = "AXIS_STATE"
    PATH_MODE = "PATH_MODE"
    COUPLED_AXES = "COUPLED_AXES"
    FUNCTIONAL_MODE = "FUNCTIONAL_MODE"

    # Conditions
    SYSTEM = "SYSTEM"
    LOGIC_PROGRAM = "LOGIC_PROGRAM"
    MOTION_PROGRAM = "MOTION_PROGRAM"
    HARDWARE = "HARDWARE"
    COMMUNICATIONS = "COMMUNICATIONS"
    ACTUATOR = "ACTUATOR"


class ExecutionState(Enum):
    """MTConnect execution states."""
    READY = "READY"
    ACTIVE = "ACTIVE"
    INTERRUPTED = "INTERRUPTED"
    FEED_HOLD = "FEED_HOLD"
    STOPPED = "STOPPED"
    OPTIONAL_STOP = "OPTIONAL_STOP"
    PROGRAM_STOPPED = "PROGRAM_STOPPED"
    PROGRAM_COMPLETED = "PROGRAM_COMPLETED"


class ControllerMode(Enum):
    """MTConnect controller modes."""
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    MANUAL_DATA_INPUT = "MANUAL_DATA_INPUT"
    SEMI_AUTOMATIC = "SEMI_AUTOMATIC"
    EDIT = "EDIT"


class AvailabilityState(Enum):
    """MTConnect availability states."""
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class ConditionState(Enum):
    """MTConnect condition states."""
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    FAULT = "FAULT"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class MTConnectDataItem:
    """
    MTConnect Data Item definition.

    Represents a single piece of data from a device component.
    """
    id: str
    name: str
    type: DataItemType
    category: DataItemCategory
    sub_type: Optional[str] = None
    units: Optional[str] = None
    native_units: Optional[str] = None
    native_scale: float = 1.0
    coordinate_system: Optional[str] = None  # MACHINE, WORK
    representation: str = "VALUE"  # VALUE, TIME_SERIES, DISCRETE, DATA_SET
    significant_digits: Optional[int] = None

    # Current value tracking
    value: Any = None
    timestamp: Optional[datetime] = None
    sequence: int = 0

    def to_xml_element(self) -> str:
        """Generate MTConnect XML element for this data item definition."""
        attrs = [
            f'id="{self.id}"',
            f'name="{self.name}"',
            f'type="{self.type.value}"',
            f'category="{self.category.value}"',
        ]
        if self.sub_type:
            attrs.append(f'subType="{self.sub_type}"')
        if self.units:
            attrs.append(f'units="{self.units}"')
        if self.native_units:
            attrs.append(f'nativeUnits="{self.native_units}"')
        if self.native_scale != 1.0:
            attrs.append(f'nativeScale="{self.native_scale}"')
        if self.coordinate_system:
            attrs.append(f'coordinateSystem="{self.coordinate_system}"')
        if self.representation != "VALUE":
            attrs.append(f'representation="{self.representation}"')

        return f'<DataItem {" ".join(attrs)}/>'

    def to_stream_element(self) -> str:
        """Generate MTConnect XML element for current value in streams."""
        if self.value is None:
            return f'<{self.type.value} dataItemId="{self.id}" timestamp="{self._format_timestamp()}" sequence="{self.sequence}">UNAVAILABLE</{self.type.value}>'

        return f'<{self.type.value} dataItemId="{self.id}" timestamp="{self._format_timestamp()}" sequence="{self.sequence}">{self.value}</{self.type.value}>'

    def _format_timestamp(self) -> str:
        """Format timestamp in ISO 8601 format."""
        ts = self.timestamp or datetime.utcnow()
        return ts.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    def update(self, value: Any, timestamp: datetime = None, sequence: int = None):
        """Update the data item value."""
        self.value = value
        self.timestamp = timestamp or datetime.utcnow()
        if sequence is not None:
            self.sequence = sequence


@dataclass
class MTConnectComponent:
    """
    MTConnect Component (Axes, Controller, Systems, etc.)
    """
    id: str
    name: str
    component_type: str  # Axes, Controller, Systems, Resources
    native_name: Optional[str] = None
    uuid: Optional[str] = None
    data_items: List[MTConnectDataItem] = field(default_factory=list)
    components: List['MTConnectComponent'] = field(default_factory=list)

    def add_data_item(self, item: MTConnectDataItem):
        self.data_items.append(item)

    def add_component(self, component: 'MTConnectComponent'):
        self.components.append(component)


@dataclass
class MTConnectDevice:
    """
    MTConnect Device definition.

    Represents a physical CNC machine or device.
    """
    id: str
    name: str
    uuid: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    station: Optional[str] = None
    iso841_class: Optional[str] = None
    native_name: Optional[str] = None
    components: List[MTConnectComponent] = field(default_factory=list)
    data_items: List[MTConnectDataItem] = field(default_factory=list)

    def add_component(self, component: MTConnectComponent):
        self.components.append(component)

    def add_data_item(self, item: MTConnectDataItem):
        self.data_items.append(item)

    def get_all_data_items(self) -> List[MTConnectDataItem]:
        """Get all data items from device and all components recursively."""
        items = list(self.data_items)

        def collect_from_component(comp: MTConnectComponent):
            items.extend(comp.data_items)
            for child in comp.components:
                collect_from_component(child)

        for comp in self.components:
            collect_from_component(comp)

        return items


# =============================================================================
# Standard Data Items for TinyG CNC Controller
# =============================================================================

def create_tinyg_device(
    device_id: str = "tinyg-1",
    device_name: str = "Nomad3",
    uuid: str = "tinyg-nomad3-001",
) -> MTConnectDevice:
    """
    Create MTConnect device model for TinyG controller.

    Maps TinyG status report fields to MTConnect data items.
    """
    device = MTConnectDevice(
        id=device_id,
        name=device_name,
        uuid=uuid,
        manufacturer="Carbide 3D",
        model="Nomad 3",
        iso841_class="1",  # Machining center
    )

    # Device-level availability
    device.add_data_item(MTConnectDataItem(
        id=f"{device_id}_avail",
        name="avail",
        type=DataItemType.AVAILABILITY,
        category=DataItemCategory.EVENT,
    ))

    # Controller Component
    controller = MTConnectComponent(
        id=f"{device_id}_ctrl",
        name="controller",
        component_type="Controller",
    )

    # Controller Path
    path = MTConnectComponent(
        id=f"{device_id}_path",
        name="path",
        component_type="Path",
    )

    # Execution state (maps to TinyG stat field)
    path.add_data_item(MTConnectDataItem(
        id=f"{device_id}_exec",
        name="execution",
        type=DataItemType.EXECUTION,
        category=DataItemCategory.EVENT,
    ))

    # Controller mode
    path.add_data_item(MTConnectDataItem(
        id=f"{device_id}_mode",
        name="mode",
        type=DataItemType.CONTROLLER_MODE,
        category=DataItemCategory.EVENT,
    ))

    # Program name
    path.add_data_item(MTConnectDataItem(
        id=f"{device_id}_pgm",
        name="program",
        type=DataItemType.PROGRAM,
        category=DataItemCategory.EVENT,
    ))

    # Current line number (maps to TinyG line field)
    path.add_data_item(MTConnectDataItem(
        id=f"{device_id}_line",
        name="line",
        type=DataItemType.LINE,
        category=DataItemCategory.EVENT,
    ))

    # Path feedrate (maps to TinyG vel field)
    path.add_data_item(MTConnectDataItem(
        id=f"{device_id}_Frt",
        name="Frt",
        type=DataItemType.PATH_FEEDRATE,
        category=DataItemCategory.SAMPLE,
        units="MILLIMETER/SECOND",
        native_units="MILLIMETER/MINUTE",
        native_scale=1/60,  # Convert mm/min to mm/s
    ))

    controller.add_component(path)
    device.add_component(controller)

    # Axes Component
    axes = MTConnectComponent(
        id=f"{device_id}_axes",
        name="axes",
        component_type="Axes",
    )

    # Linear Axes (X, Y, Z)
    for axis_name in ['X', 'Y', 'Z']:
        axis = MTConnectComponent(
            id=f"{device_id}_{axis_name.lower()}",
            name=axis_name,
            component_type="Linear",
        )

        # Work position (maps to TinyG wx, wy, wz)
        axis.add_data_item(MTConnectDataItem(
            id=f"{device_id}_{axis_name.lower()}pos",
            name=f"{axis_name}pos",
            type=DataItemType.POSITION,
            category=DataItemCategory.SAMPLE,
            sub_type="ACTUAL",
            units="MILLIMETER",
            coordinate_system="WORK",
        ))

        # Machine position (maps to TinyG mx, my, mz)
        axis.add_data_item(MTConnectDataItem(
            id=f"{device_id}_{axis_name.lower()}mpos",
            name=f"{axis_name}mpos",
            type=DataItemType.POSITION,
            category=DataItemCategory.SAMPLE,
            sub_type="ACTUAL",
            units="MILLIMETER",
            coordinate_system="MACHINE",
        ))

        # Axis load (placeholder for future sensor data)
        axis.add_data_item(MTConnectDataItem(
            id=f"{device_id}_{axis_name.lower()}load",
            name=f"{axis_name}load",
            type=DataItemType.LOAD,
            category=DataItemCategory.SAMPLE,
            units="PERCENT",
        ))

        axes.add_component(axis)

    # Rotary axis (C/Spindle)
    spindle = MTConnectComponent(
        id=f"{device_id}_c",
        name="C",
        component_type="Rotary",
    )

    # Spindle speed (maps to TinyG sps)
    spindle.add_data_item(MTConnectDataItem(
        id=f"{device_id}_Srpm",
        name="Srpm",
        type=DataItemType.SPINDLE_SPEED,
        category=DataItemCategory.SAMPLE,
        sub_type="ACTUAL",
        units="REVOLUTION/MINUTE",
    ))

    # Spindle load
    spindle.add_data_item(MTConnectDataItem(
        id=f"{device_id}_Sload",
        name="Sload",
        type=DataItemType.LOAD,
        category=DataItemCategory.SAMPLE,
        units="PERCENT",
    ))

    axes.add_component(spindle)
    device.add_component(axes)

    # Systems Component (for sensors and auxiliary systems)
    systems = MTConnectComponent(
        id=f"{device_id}_sys",
        name="systems",
        component_type="Systems",
    )

    # Coolant system
    coolant = MTConnectComponent(
        id=f"{device_id}_cool",
        name="coolant",
        component_type="Coolant",
    )
    coolant.add_data_item(MTConnectDataItem(
        id=f"{device_id}_cool_cond",
        name="coolant_condition",
        type=DataItemType.SYSTEM,
        category=DataItemCategory.CONDITION,
    ))
    systems.add_component(coolant)

    # Electric system (for motor currents from MCC DAQ)
    electric = MTConnectComponent(
        id=f"{device_id}_elec",
        name="electric",
        component_type="Electric",
    )

    # Motor currents
    for motor in ['spindle', 'x_motor', 'y_motor', 'z_motor']:
        electric.add_data_item(MTConnectDataItem(
            id=f"{device_id}_{motor}_amp",
            name=f"{motor}_amperage",
            type=DataItemType.AMPERAGE,
            category=DataItemCategory.SAMPLE,
            units="AMPERE",
        ))

    systems.add_component(electric)

    # Environmental sensors (from Arduino sensors)
    environmental = MTConnectComponent(
        id=f"{device_id}_env",
        name="environmental",
        component_type="Environmental",
    )

    environmental.add_data_item(MTConnectDataItem(
        id=f"{device_id}_temp",
        name="temperature",
        type=DataItemType.TEMPERATURE,
        category=DataItemCategory.SAMPLE,
        units="CELSIUS",
    ))

    environmental.add_data_item(MTConnectDataItem(
        id=f"{device_id}_vib",
        name="vibration",
        type=DataItemType.VIBRATION,
        category=DataItemCategory.SAMPLE,
        units="MILLIMETER/SECOND**2",
    ))

    environmental.add_data_item(MTConnectDataItem(
        id=f"{device_id}_pressure",
        name="pressure",
        type=DataItemType.PRESSURE,
        category=DataItemCategory.SAMPLE,
        units="PASCAL",
        native_units="HECTOPASCAL",
        native_scale=100,  # hPa to Pa
    ))

    systems.add_component(environmental)
    device.add_component(systems)

    return device


# Pre-configured device template
DEVICE_DATA_ITEMS = create_tinyg_device()
