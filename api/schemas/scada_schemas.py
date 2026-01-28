"""
LEGO Factory v3 - SCADA Pydantic Schemas
=========================================
Validation schemas for SCADA operations including machines,
tags, alarms, recipes, and historian data.

These schemas ensure data integrity for industrial control
system operations with proper validation of process values,
alarm limits, and machine control parameters.
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.schemas.common_schemas import BaseSchema, AuditMixin, PaginationParams


# ============================================================================
# Enums (mirroring database models)
# ============================================================================

class TagDataType(str, Enum):
    """Tag data types supported by the SCADA system."""
    BOOLEAN = "boolean"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    STRING = "string"


class TagCategory(str, Enum):
    """Tag categories for organization."""
    ANALOG_INPUT = "analog_input"
    ANALOG_OUTPUT = "analog_output"
    DIGITAL_INPUT = "digital_input"
    DIGITAL_OUTPUT = "digital_output"
    CALCULATED = "calculated"
    SETPOINT = "setpoint"
    ALARM = "alarm"
    STATUS = "status"


class AlarmPriority(int, Enum):
    """ISA-18.2 Alarm priorities."""
    EMERGENCY = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class AlarmClass(str, Enum):
    """ISA-18.2 Alarm classes."""
    PROCESS = "process"
    EQUIPMENT = "equipment"
    SAFETY = "safety"
    ENVIRONMENTAL = "environmental"
    QUALITY = "quality"
    DIAGNOSTIC = "diagnostic"


class AlarmType(str, Enum):
    """Alarm trigger types."""
    HIGH = "high"
    HIGH_HIGH = "high_high"
    LOW = "low"
    LOW_LOW = "low_low"
    DEVIATION = "deviation"
    RATE_OF_CHANGE = "rate_of_change"
    DIGITAL = "digital"
    BAD_QUALITY = "bad_quality"


class AlarmState(str, Enum):
    """ISA-18.2 Alarm states."""
    NORMAL = "normal"
    UNACKED_ACTIVE = "unacked_active"
    ACKED_ACTIVE = "acked_active"
    UNACKED_CLEARED = "unacked_cleared"
    SHELVED = "shelved"
    SUPPRESSED = "suppressed"
    OUT_OF_SERVICE = "out_of_service"


class MachineType(str, Enum):
    """Types of machines in the factory."""
    FDM_PRINTER = "fdm_printer"
    SLA_PRINTER = "sla_printer"
    CNC_MILL = "cnc_mill"
    CNC_LATHE = "cnc_lathe"
    ROBOT_ARM = "robot_arm"
    CONVEYOR = "conveyor"
    INJECTION_MOLDER = "injection_molder"
    ASSEMBLY_STATION = "assembly_station"


class ControllerType(str, Enum):
    """Machine controller types."""
    GRBL = "grbl"
    MARLIN = "marlin"
    BAMBU = "bambu"
    KLIPPER = "klipper"
    DUET = "duet"
    FANUC = "fanuc"
    SIEMENS = "siemens"
    MODBUS = "modbus"
    OPC_UA = "opc_ua"


class MachineState(str, Enum):
    """Machine operational states."""
    OFFLINE = "offline"
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    HOMING = "homing"


# ============================================================================
# Machine Schemas
# ============================================================================

class MachineCreate(BaseSchema):
    """
    Schema for creating a new machine.

    Validates all required fields for machine registration
    with proper format checks on identifiers and addresses.

    Attributes:
        machine_id: Unique machine identifier (alphanumeric with underscores/hyphens)
        name: Human-readable machine name
        controller_type: Type of controller (GRBL, Marlin, etc.)
        machine_type: Type of machine (FDM printer, CNC mill, etc.)
        ip_address: Optional IP address for network-connected machines
        port: Network port number
        serial_port: Serial port path for directly connected machines
        area: Factory area where machine is located
        description: Optional description
        config: Additional configuration parameters
    """
    machine_id: str = Field(
        min_length=1,
        max_length=50,
        description="Unique machine identifier"
    )
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Human-readable machine name"
    )
    controller_type: ControllerType = Field(
        description="Controller type"
    )
    machine_type: Optional[MachineType] = Field(
        default=None,
        description="Machine type"
    )
    ip_address: Optional[str] = Field(
        default=None,
        max_length=45,
        description="IP address (IPv4 or IPv6)"
    )
    port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="Network port number"
    )
    serial_port: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Serial port path (e.g., /dev/ttyUSB0)"
    )
    area: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Factory area location"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Machine description"
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional configuration parameters"
    )

    @field_validator('machine_id')
    @classmethod
    def validate_machine_id(cls, v: str) -> str:
        """Validate machine ID format."""
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', v):
            raise ValueError(
                'Machine ID must start with a letter and contain only '
                'letters, numbers, underscores, and hyphens'
            )
        return v

    @field_validator('ip_address')
    @classmethod
    def validate_ip_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate IP address format if provided."""
        if v is not None:
            # Basic IPv4/IPv6 validation
            ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
            ipv6_pattern = r'^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$'
            if not (re.match(ipv4_pattern, v) or re.match(ipv6_pattern, v)):
                raise ValueError('Invalid IP address format')
        return v


class MachineUpdate(BaseSchema):
    """
    Schema for updating an existing machine.

    All fields are optional - only provided fields will be updated.
    """
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Human-readable machine name"
    )
    controller_type: Optional[ControllerType] = Field(
        default=None,
        description="Controller type"
    )
    machine_type: Optional[MachineType] = Field(
        default=None,
        description="Machine type"
    )
    ip_address: Optional[str] = Field(
        default=None,
        max_length=45,
        description="IP address"
    )
    port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="Network port"
    )
    serial_port: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Serial port path"
    )
    area: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Factory area"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Description"
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Configuration parameters"
    )


class MachineResponse(BaseSchema):
    """Machine data response schema."""
    id: Optional[str] = Field(default=None, description="Database ID")
    machine_id: str = Field(description="Machine identifier")
    name: str = Field(description="Machine name")
    controller_type: str = Field(description="Controller type")
    machine_type: Optional[str] = Field(default=None, description="Machine type")
    state: Optional[str] = Field(default=None, description="Current state")
    ip_address: Optional[str] = Field(default=None)
    port: Optional[int] = Field(default=None)
    area: Optional[str] = Field(default=None)
    is_connected: Optional[bool] = Field(default=None)
    last_seen: Optional[datetime] = Field(default=None)


class MachineJogRequest(BaseSchema):
    """
    Request to jog machine to a position.

    At least one axis position must be specified.

    Attributes:
        x: X-axis position in mm
        y: Y-axis position in mm
        z: Z-axis position in mm
        feed_rate: Movement speed in mm/min (default: 1000)
    """
    x: Optional[float] = Field(
        default=None,
        ge=-10000,
        le=10000,
        description="X-axis position in mm"
    )
    y: Optional[float] = Field(
        default=None,
        ge=-10000,
        le=10000,
        description="Y-axis position in mm"
    )
    z: Optional[float] = Field(
        default=None,
        ge=-1000,
        le=1000,
        description="Z-axis position in mm"
    )
    feed_rate: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="Feed rate in mm/min"
    )

    @model_validator(mode='after')
    def at_least_one_axis(self) -> 'MachineJogRequest':
        """Validate at least one axis is specified."""
        if self.x is None and self.y is None and self.z is None:
            raise ValueError('At least one axis position must be specified')
        return self


class MachineHomeRequest(BaseSchema):
    """
    Request to home machine axes.

    Attributes:
        axes: Axes to home (e.g., 'XYZ', 'X', 'XY')
    """
    axes: str = Field(
        default="XYZ",
        pattern=r'^[XYZxyz]+$',
        max_length=3,
        description="Axes to home"
    )

    @field_validator('axes')
    @classmethod
    def normalize_axes(cls, v: str) -> str:
        """Normalize axes to uppercase."""
        return v.upper()


class GCodeExecuteRequest(BaseSchema):
    """
    Request to execute G-code on a machine.

    Attributes:
        gcode: G-code commands (single line or multiple lines)
        wait_for_completion: Whether to wait for execution to complete
    """
    gcode: str = Field(
        min_length=1,
        max_length=100000,
        description="G-code commands"
    )
    wait_for_completion: bool = Field(
        default=True,
        description="Wait for execution to complete"
    )


# ============================================================================
# Tag Schemas
# ============================================================================

class TagCreate(BaseSchema):
    """
    Schema for creating a new SCADA tag.

    Tags represent data points in the system that can be read
    from or written to equipment.

    Attributes:
        tag_id: Unique tag identifier following naming convention
        name: Human-readable tag name
        data_type: Data type of the tag value
        category: Tag category for organization
        description: Optional description
        area: Factory area
        equipment: Equipment identifier
        eng_units: Engineering units (e.g., 'degC', 'bar', 'mm')
        eng_low: Low engineering scale value
        eng_high: High engineering scale value
        raw_low: Low raw value
        raw_high: High raw value
        deadband: Change deadband for value change detection
        historize: Whether to store historical values
        scan_rate_ms: Scan rate in milliseconds
    """
    tag_id: str = Field(
        min_length=1,
        max_length=100,
        description="Unique tag identifier"
    )
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Human-readable tag name"
    )
    data_type: TagDataType = Field(
        default=TagDataType.FLOAT32,
        description="Tag data type"
    )
    category: TagCategory = Field(
        default=TagCategory.ANALOG_INPUT,
        description="Tag category"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Tag description"
    )
    area: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Factory area"
    )
    equipment: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Equipment identifier"
    )
    eng_units: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Engineering units"
    )
    eng_low: Optional[float] = Field(
        default=None,
        description="Low engineering scale value"
    )
    eng_high: Optional[float] = Field(
        default=None,
        description="High engineering scale value"
    )
    raw_low: Optional[float] = Field(
        default=None,
        description="Low raw value"
    )
    raw_high: Optional[float] = Field(
        default=None,
        description="High raw value"
    )
    deadband: float = Field(
        default=0.0,
        ge=0,
        description="Change deadband"
    )
    deadband_mode: str = Field(
        default="absolute",
        pattern="^(absolute|percent)$",
        description="Deadband mode: absolute or percent"
    )
    historize: bool = Field(
        default=True,
        description="Store historical values"
    )
    scan_rate_ms: int = Field(
        default=1000,
        ge=10,
        le=3600000,
        description="Scan rate in milliseconds"
    )
    source_type: str = Field(
        default="internal",
        pattern="^(internal|modbus|opc|calculated)$",
        description="Tag source type"
    )
    source_address: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Source address for external tags"
    )

    @field_validator('tag_id')
    @classmethod
    def validate_tag_id(cls, v: str) -> str:
        """
        Validate tag ID follows naming convention.

        Format: AREA.EQUIPMENT.TAG_NAME or similar hierarchical pattern.
        """
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_.-]*$', v):
            raise ValueError(
                'Tag ID must start with a letter and contain only '
                'letters, numbers, underscores, periods, and hyphens'
            )
        return v

    @model_validator(mode='after')
    def validate_scaling(self) -> 'TagCreate':
        """Validate that scaling values are consistent."""
        if self.eng_low is not None and self.eng_high is not None:
            if self.eng_low >= self.eng_high:
                raise ValueError('eng_high must be greater than eng_low')
        if self.raw_low is not None and self.raw_high is not None:
            if self.raw_low >= self.raw_high:
                raise ValueError('raw_high must be greater than raw_low')
        return self


class TagUpdate(BaseSchema):
    """Schema for updating an existing tag."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    area: Optional[str] = Field(default=None, max_length=100)
    equipment: Optional[str] = Field(default=None, max_length=100)
    eng_units: Optional[str] = Field(default=None, max_length=50)
    eng_low: Optional[float] = Field(default=None)
    eng_high: Optional[float] = Field(default=None)
    deadband: Optional[float] = Field(default=None, ge=0)
    historize: Optional[bool] = Field(default=None)
    scan_rate_ms: Optional[int] = Field(default=None, ge=10, le=3600000)


class TagValueWrite(BaseSchema):
    """
    Schema for writing a value to a tag.

    Attributes:
        value: Value to write (type depends on tag data type)
        quality: OPC quality code (default: 192 = GOOD)
        tag_name: Optional tag name for cache update
        eng_units: Optional engineering units
    """
    value: Union[float, int, bool, str] = Field(
        description="Value to write"
    )
    quality: int = Field(
        default=192,
        ge=0,
        le=255,
        description="OPC quality code"
    )
    tag_name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Tag name"
    )
    eng_units: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Engineering units"
    )


class TagValueBulkWrite(BaseSchema):
    """
    Schema for writing multiple tag values.

    Attributes:
        values: List of tag value writes
    """
    values: List["TagValueWriteItem"] = Field(
        min_length=1,
        max_length=1000,
        description="List of tag values to write"
    )


class TagValueWriteItem(BaseSchema):
    """Single item in bulk tag value write."""
    tag_id: str = Field(min_length=1, max_length=100)
    value: Union[float, int, bool, str]
    quality: int = Field(default=192, ge=0, le=255)
    tag_name: Optional[str] = Field(default=None, max_length=200)
    eng_units: Optional[str] = Field(default=None, max_length=50)


class TagGroupCreate(BaseSchema):
    """Schema for creating a tag group."""
    name: str = Field(
        min_length=1,
        max_length=100,
        description="Group name"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Group description"
    )
    parent_id: Optional[str] = Field(
        default=None,
        description="Parent group ID"
    )
    tag_ids: List[str] = Field(
        default_factory=list,
        max_length=1000,
        description="List of tag IDs in the group"
    )


class TagBulkCreate(BaseSchema):
    """Schema for bulk tag creation."""
    tags: List[TagCreate] = Field(
        min_length=1,
        max_length=500,
        description="List of tags to create"
    )


class TagImportRequest(BaseSchema):
    """Schema for importing tags from JSON."""
    tags: List[Dict[str, Any]] = Field(
        min_length=1,
        description="Tag data to import"
    )
    update_existing: bool = Field(
        default=False,
        description="Update existing tags with same ID"
    )


class TagScaleRequest(BaseSchema):
    """Schema for scaling a raw value to engineering units."""
    raw_value: float = Field(description="Raw value to scale")


class TagListParams(PaginationParams):
    """Query parameters for listing tags."""
    area: Optional[str] = Field(default=None, max_length=100)
    equipment: Optional[str] = Field(default=None, max_length=100)
    category: Optional[TagCategory] = Field(default=None)
    search: Optional[str] = Field(default=None, max_length=200)


# ============================================================================
# Alarm Schemas
# ============================================================================

class AlarmDefinitionCreate(BaseSchema):
    """
    Schema for creating an alarm definition.

    Defines conditions under which an alarm should be triggered
    following ISA-18.2 alarm management standards.

    Attributes:
        alarm_id: Unique alarm identifier
        name: Human-readable alarm name
        tag_id: Tag to monitor for alarm conditions
        alarm_type: Type of alarm (high, low, deviation, etc.)
        priority: Alarm priority (1=emergency to 4=low)
        alarm_class: Alarm classification
        setpoint: Reference setpoint for deviation alarms
        high_limit: High alarm limit
        high_high_limit: High-high alarm limit
        low_limit: Low alarm limit
        low_low_limit: Low-low alarm limit
        deviation_limit: Deviation limit from setpoint
        deadband: Hysteresis for alarm clearing
        on_delay_seconds: Delay before alarm activates
        off_delay_seconds: Delay before alarm clears
        consequence: Description of alarm consequence
        corrective_action: Recommended corrective action
    """
    alarm_id: str = Field(
        min_length=1,
        max_length=100,
        description="Unique alarm identifier"
    )
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Alarm name"
    )
    tag_id: str = Field(
        min_length=1,
        description="Tag ID to monitor"
    )
    alarm_type: AlarmType = Field(
        description="Alarm trigger type"
    )
    priority: AlarmPriority = Field(
        default=AlarmPriority.MEDIUM,
        description="Alarm priority"
    )
    alarm_class: AlarmClass = Field(
        default=AlarmClass.PROCESS,
        description="Alarm classification"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Alarm description"
    )
    setpoint: Optional[float] = Field(
        default=None,
        description="Setpoint for deviation alarms"
    )
    high_limit: Optional[float] = Field(
        default=None,
        description="High alarm limit"
    )
    high_high_limit: Optional[float] = Field(
        default=None,
        description="High-high alarm limit"
    )
    low_limit: Optional[float] = Field(
        default=None,
        description="Low alarm limit"
    )
    low_low_limit: Optional[float] = Field(
        default=None,
        description="Low-low alarm limit"
    )
    deviation_limit: Optional[float] = Field(
        default=None,
        ge=0,
        description="Deviation limit"
    )
    rate_limit: Optional[float] = Field(
        default=None,
        ge=0,
        description="Rate of change limit (units per second)"
    )
    deadband: float = Field(
        default=0.0,
        ge=0,
        description="Alarm deadband"
    )
    on_delay_seconds: float = Field(
        default=0.0,
        ge=0,
        le=3600,
        description="On delay in seconds"
    )
    off_delay_seconds: float = Field(
        default=0.0,
        ge=0,
        le=3600,
        description="Off delay in seconds"
    )
    consequence: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Consequence of alarm condition"
    )
    corrective_action: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Recommended corrective action"
    )
    enabled: bool = Field(
        default=True,
        description="Whether alarm is enabled"
    )

    @field_validator('alarm_id')
    @classmethod
    def validate_alarm_id(cls, v: str) -> str:
        """Validate alarm ID format."""
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_.-]*$', v):
            raise ValueError(
                'Alarm ID must start with a letter and contain only '
                'letters, numbers, underscores, periods, and hyphens'
            )
        return v

    @model_validator(mode='after')
    def validate_limits(self) -> 'AlarmDefinitionCreate':
        """Validate alarm limits are consistent."""
        if self.alarm_type == AlarmType.HIGH and self.high_limit is None:
            raise ValueError('high_limit required for HIGH alarm type')
        if self.alarm_type == AlarmType.HIGH_HIGH and self.high_high_limit is None:
            raise ValueError('high_high_limit required for HIGH_HIGH alarm type')
        if self.alarm_type == AlarmType.LOW and self.low_limit is None:
            raise ValueError('low_limit required for LOW alarm type')
        if self.alarm_type == AlarmType.LOW_LOW and self.low_low_limit is None:
            raise ValueError('low_low_limit required for LOW_LOW alarm type')
        if self.alarm_type == AlarmType.DEVIATION:
            if self.setpoint is None or self.deviation_limit is None:
                raise ValueError('setpoint and deviation_limit required for DEVIATION alarm')
        if self.alarm_type == AlarmType.RATE_OF_CHANGE and self.rate_limit is None:
            raise ValueError('rate_limit required for RATE_OF_CHANGE alarm type')

        # Validate limit ordering
        if self.high_limit is not None and self.high_high_limit is not None:
            if self.high_high_limit <= self.high_limit:
                raise ValueError('high_high_limit must be greater than high_limit')
        if self.low_limit is not None and self.low_low_limit is not None:
            if self.low_low_limit >= self.low_limit:
                raise ValueError('low_low_limit must be less than low_limit')
        return self


class AlarmDefinitionUpdate(BaseSchema):
    """Schema for updating an alarm definition."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    priority: Optional[AlarmPriority] = Field(default=None)
    alarm_class: Optional[AlarmClass] = Field(default=None)
    setpoint: Optional[float] = Field(default=None)
    high_limit: Optional[float] = Field(default=None)
    high_high_limit: Optional[float] = Field(default=None)
    low_limit: Optional[float] = Field(default=None)
    low_low_limit: Optional[float] = Field(default=None)
    deadband: Optional[float] = Field(default=None, ge=0)
    on_delay_seconds: Optional[float] = Field(default=None, ge=0, le=3600)
    off_delay_seconds: Optional[float] = Field(default=None, ge=0, le=3600)
    consequence: Optional[str] = Field(default=None, max_length=1000)
    corrective_action: Optional[str] = Field(default=None, max_length=1000)
    enabled: Optional[bool] = Field(default=None)


class AlarmAcknowledge(BaseSchema):
    """
    Schema for acknowledging an alarm.

    Attributes:
        user_id: User acknowledging the alarm
        comment: Optional acknowledgment comment
    """
    user_id: str = Field(
        default="system",
        min_length=1,
        max_length=100,
        description="User ID acknowledging the alarm"
    )
    comment: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Acknowledgment comment"
    )


class AlarmShelveRequest(BaseSchema):
    """
    Schema for shelving an alarm.

    Temporarily suppresses an alarm for a specified duration.

    Attributes:
        user_id: User shelving the alarm
        duration_minutes: Shelve duration in minutes
        reason: Required reason for shelving
    """
    user_id: str = Field(
        default="system",
        min_length=1,
        max_length=100,
        description="User ID shelving the alarm"
    )
    duration_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,  # Max 24 hours
        description="Shelve duration in minutes"
    )
    reason: str = Field(
        min_length=1,
        max_length=500,
        description="Reason for shelving (required)"
    )


class AlarmUnshelveRequest(BaseSchema):
    """Schema for unshelving an alarm."""
    user_id: str = Field(
        default="system",
        min_length=1,
        max_length=100,
        description="User ID unshelving the alarm"
    )


class AlarmGroupCreate(BaseSchema):
    """Schema for creating an alarm group."""
    name: str = Field(
        min_length=1,
        max_length=100,
        description="Group name"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Group description"
    )
    alarm_ids: List[str] = Field(
        default_factory=list,
        max_length=500,
        description="List of alarm IDs in the group"
    )


class AlarmListParams(PaginationParams):
    """Query parameters for listing alarm definitions."""
    area: Optional[str] = Field(default=None, max_length=100)
    priority: Optional[AlarmPriority] = Field(default=None)
    alarm_class: Optional[AlarmClass] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)
    search: Optional[str] = Field(default=None, max_length=200)


class ActiveAlarmParams(BaseSchema):
    """Query parameters for active alarms."""
    priority: Optional[AlarmPriority] = Field(default=None)
    area: Optional[str] = Field(default=None, max_length=100)
    unacknowledged_only: bool = Field(default=False)


class AlarmHistoryParams(BaseSchema):
    """Query parameters for alarm history."""
    alarm_ids: Optional[List[str]] = Field(default=None, max_length=100)
    start: Optional[datetime] = Field(default=None)
    end: Optional[datetime] = Field(default=None)
    priority: Optional[AlarmPriority] = Field(default=None)
    limit: int = Field(default=1000, ge=1, le=10000)


# ============================================================================
# Historian Schemas
# ============================================================================

class HistorianQueryRequest(BaseSchema):
    """
    Schema for querying historian data.

    Supports various aggregation modes for time-series analysis.

    Attributes:
        tag_ids: List of tag IDs to query
        start: Start of query time range
        end: End of query time range
        aggregation: Aggregation mode (raw, average, min, max, etc.)
        interval_seconds: Aggregation interval
        limit: Maximum number of points to return
    """
    tag_ids: List[str] = Field(
        min_length=1,
        max_length=100,
        description="Tag IDs to query"
    )
    start: datetime = Field(description="Query start time")
    end: datetime = Field(description="Query end time")
    aggregation: str = Field(
        default="raw",
        pattern="^(raw|average|min|max|first|last|count|sum|std)$",
        description="Aggregation mode"
    )
    interval_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        le=86400,
        description="Aggregation interval in seconds"
    )
    limit: int = Field(
        default=10000,
        ge=1,
        le=100000,
        description="Maximum points to return"
    )

    @model_validator(mode='after')
    def validate_time_range(self) -> 'HistorianQueryRequest':
        """Validate time range."""
        if self.end <= self.start:
            raise ValueError('end must be after start')
        # Require interval for non-raw aggregation
        if self.aggregation != 'raw' and self.interval_seconds is None:
            raise ValueError('interval_seconds required for aggregated queries')
        return self


class HistorianWriteRequest(BaseSchema):
    """Schema for writing data to historian."""
    tag_id: str = Field(min_length=1, max_length=100)
    values: List["HistorianValue"] = Field(
        min_length=1,
        max_length=10000,
        description="Values to write"
    )


class HistorianValue(BaseSchema):
    """Single historian value for batch writes."""
    timestamp: datetime
    value: Union[float, int, bool, str]
    quality: int = Field(default=192, ge=0, le=255)


# Resolve forward references
TagValueBulkWrite.model_rebuild()
HistorianWriteRequest.model_rebuild()
