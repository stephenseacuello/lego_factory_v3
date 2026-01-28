"""
ISO 23247 Digital Twin Framework Schemas.

This module provides Pydantic models compliant with:
- ISO 23247-1: General Principles
- ISO 23247-2: Reference Architecture
- ISO 23247-3: Digital Representation
- ISO 23247-4: Information Exchange

References:
- https://www.iso.org/standard/75066.html
- https://www.nist.gov/publications/analysis-new-iso-23247-series-standards-digital-twin-framework-manufacturing
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# ISO 23247-3: Observable Manufacturing Element Types
# =============================================================================

class OMEType(str, Enum):
    """
    Observable Manufacturing Element types per ISO 23247-3.

    These represent the physical entities that can be digitally twinned
    in a manufacturing environment.
    """
    EQUIPMENT = "equipment"
    MATERIAL = "material"
    PROCESS = "process"
    PERSONNEL = "personnel"
    FACILITY = "facility"


class EquipmentSubtype(str, Enum):
    """Equipment subtypes for CNC machines."""
    CNC_MILL = "cnc_mill"
    CNC_LATHE = "cnc_lathe"
    CNC_ROUTER = "cnc_router"
    LASER_CUTTER = "laser_cutter"
    CONVEYOR = "conveyor"
    ROBOT = "robot"
    CMM = "cmm"  # Coordinate Measuring Machine


# =============================================================================
# Position and Geometry
# =============================================================================

class Position3D(BaseModel):
    """3D position in millimeters."""
    x: float = Field(default=0.0, description="X coordinate (mm)")
    y: float = Field(default=0.0, description="Y coordinate (mm)")
    z: float = Field(default=0.0, description="Z coordinate (mm)")
    timestamp: Optional[float] = Field(None, description="Unix timestamp of position update")

    class Config:
        json_schema_extra = {
            "example": {"x": 100.5, "y": 50.2, "z": -25.0, "timestamp": 1703894400.123}
        }


class MachinePosition(BaseModel):
    """Complete machine position including work and machine coordinates."""
    work: Position3D = Field(..., description="Work coordinate position")
    machine: Position3D = Field(..., description="Machine coordinate position")
    coordinate_system: str = Field(default="G54", description="Active coordinate system")


class BoundingBox(BaseModel):
    """3D bounding box for work envelope or geometry."""
    min: Position3D = Field(..., description="Minimum corner")
    max: Position3D = Field(..., description="Maximum corner")


class WorkEnvelope(BaseModel):
    """Machine work envelope per ISO 23247-3."""
    x_min: float = Field(default=0.0, description="X minimum (mm)")
    x_max: float = Field(default=300.0, description="X maximum (mm)")
    y_min: float = Field(default=0.0, description="Y minimum (mm)")
    y_max: float = Field(default=200.0, description="Y maximum (mm)")
    z_min: float = Field(default=-100.0, description="Z minimum (mm)")
    z_max: float = Field(default=0.0, description="Z maximum (mm)")


# =============================================================================
# ISO 23247-3: Operational State (MTConnect aligned)
# =============================================================================

class ExecutionState(str, Enum):
    """Execution state per MTConnect/ISO 23247."""
    READY = "READY"
    ACTIVE = "ACTIVE"
    INTERRUPTED = "INTERRUPTED"
    FEED_HOLD = "FEED_HOLD"
    STOPPED = "STOPPED"
    OPTIONAL_STOP = "OPTIONAL_STOP"
    PROGRAM_STOPPED = "PROGRAM_STOPPED"
    PROGRAM_COMPLETED = "PROGRAM_COMPLETED"


class ControllerMode(str, Enum):
    """Controller mode per MTConnect."""
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    MANUAL_DATA_INPUT = "MANUAL_DATA_INPUT"
    SEMI_AUTOMATIC = "SEMI_AUTOMATIC"
    EDIT = "EDIT"


class MotionMode(str, Enum):
    """Motion mode (G-code based)."""
    RAPID = "rapid"  # G0
    LINEAR = "linear"  # G1
    ARC_CW = "arc_cw"  # G2
    ARC_CCW = "arc_ccw"  # G3
    DWELL = "dwell"  # G4


class OperationalState(BaseModel):
    """
    Machine operational state per MTConnect/ISO 23247.

    Maps MTConnect data items to ISO 23247-3 state representation.
    """
    execution: ExecutionState = Field(
        default=ExecutionState.READY,
        description="Current execution state"
    )
    mode: ControllerMode = Field(
        default=ControllerMode.AUTOMATIC,
        description="Controller mode"
    )
    motion_mode: MotionMode = Field(
        default=MotionMode.RAPID,
        description="Current motion mode"
    )
    program: Optional[str] = Field(None, description="Active program name")
    line_number: int = Field(default=0, description="Current G-code line number")
    feed_override: float = Field(default=100.0, ge=0, le=200, description="Feed override %")
    spindle_override: float = Field(default=100.0, ge=0, le=200, description="Spindle override %")
    rapid_override: float = Field(default=100.0, ge=0, le=100, description="Rapid override %")

    class Config:
        json_schema_extra = {
            "example": {
                "execution": "ACTIVE",
                "mode": "AUTOMATIC",
                "motion_mode": "linear",
                "program": "part_001.nc",
                "line_number": 150,
                "feed_override": 100.0,
                "spindle_override": 100.0,
                "rapid_override": 100.0
            }
        }


# =============================================================================
# Tool and Spindle State
# =============================================================================

class ToolType(str, Enum):
    """Tool types for CNC operations."""
    ENDMILL = "endmill"
    BALLNOSE = "ballnose"
    DRILL = "drill"
    TAP = "tap"
    REAMER = "reamer"
    BORING_BAR = "boring_bar"
    FACE_MILL = "face_mill"
    CHAMFER = "chamfer"
    ENGRAVER = "engraver"


class ToolState(BaseModel):
    """Current tool state per ISO 23247-3."""
    tool_number: int = Field(default=1, ge=0, description="Tool number in magazine")
    tool_name: str = Field(default="", description="Tool name/identifier")
    tool_type: ToolType = Field(default=ToolType.ENDMILL, description="Tool type")
    diameter: float = Field(default=6.0, gt=0, description="Tool diameter (mm)")
    length: float = Field(default=50.0, gt=0, description="Tool length (mm)")
    flute_count: int = Field(default=4, ge=1, description="Number of flutes")
    max_rpm: float = Field(default=24000.0, gt=0, description="Maximum RPM")
    max_feed: float = Field(default=5000.0, gt=0, description="Maximum feed rate (mm/min)")


class SpindleState(BaseModel):
    """Spindle state per ISO 23247-3."""
    spindle_on: bool = Field(default=False, description="Spindle running")
    spindle_rpm: float = Field(default=0.0, ge=0, description="Spindle RPM")
    spindle_direction: str = Field(default="CW", pattern="^(CW|CCW)$", description="Rotation direction")
    spindle_load: float = Field(default=0.0, ge=0, le=100, description="Spindle load %")


# =============================================================================
# Axis State (Kinematic Chain)
# =============================================================================

class AxisState(BaseModel):
    """Individual axis state per ISO 23247-3."""
    name: str = Field(..., description="Axis name (X, Y, Z, A, B, C)")
    position: float = Field(default=0.0, description="Current position (mm or degrees)")
    velocity: float = Field(default=0.0, description="Current velocity (mm/min or deg/min)")
    load: float = Field(default=0.0, ge=0, le=100, description="Motor load %")
    homed: bool = Field(default=False, description="Axis is homed")
    in_position: bool = Field(default=True, description="Axis has reached target")


class KinematicsState(BaseModel):
    """
    Kinematic chain state for Unity animation.

    Represents all axes of the machine for real-time visualization.
    """
    axes: Dict[str, AxisState] = Field(
        default_factory=dict,
        description="State of each axis (X, Y, Z, A, B, C)"
    )
    tool: ToolState = Field(default_factory=ToolState, description="Current tool state")
    spindle: SpindleState = Field(default_factory=SpindleState, description="Spindle state")


# =============================================================================
# Data Lineage and Quality (ISO 8000 aligned)
# =============================================================================

class DataQuality(str, Enum):
    """Data quality levels per ISO 8000."""
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"
    STALE = "STALE"


class DataLineage(BaseModel):
    """
    Data lineage for traceability per ISO 8000/ISO 23247.

    Tracks the source, transformation, and quality of data.
    """
    source_id: str = Field(..., description="Source device/sensor ID")
    source_type: str = Field(..., description="Source type (controller, sensor, daq)")
    timestamp: float = Field(..., description="Original data timestamp")
    sample_rate_hz: Optional[float] = Field(None, description="Data sample rate")
    calibration_date: Optional[datetime] = Field(None, description="Last calibration date")
    calibration_id: Optional[str] = Field(None, description="Calibration certificate ID")
    quality: DataQuality = Field(default=DataQuality.GOOD, description="Data quality")
    schema_version: str = Field(default="1.0.0", description="Data schema version")


# =============================================================================
# Sensor Data Overlay
# =============================================================================

class SensorOverlay(BaseModel):
    """
    Aggregated sensor data for Unity visualization overlay.

    Provides real-time sensor values for visual representation.
    """
    vibration_rms: float = Field(default=0.0, ge=0, description="Vibration RMS (g)")
    temperature: float = Field(default=25.0, description="Temperature (°C)")
    pressure: float = Field(default=1013.25, description="Pressure (hPa)")
    humidity: Optional[float] = Field(None, ge=0, le=100, description="Humidity %")
    motor_currents: Dict[str, float] = Field(
        default_factory=dict,
        description="Motor currents by axis (A)"
    )
    alerts: List[str] = Field(default_factory=list, description="Active sensor alerts")


# =============================================================================
# AAS Submodel References (IEC 63278 aligned)
# =============================================================================

class IdentificationSubmodel(BaseModel):
    """
    Identification submodel per IDTA 02003.

    Contains asset identification information from AAS.
    """
    manufacturer_name: str = Field(..., description="Manufacturer name")
    manufacturer_product_designation: str = Field(..., description="Product designation")
    serial_number: str = Field(..., description="Serial number")
    year_of_construction: Optional[int] = Field(None, description="Year of construction")
    asset_id: str = Field(..., description="Unique asset identifier")


class TechnicalDataSubmodel(BaseModel):
    """
    Technical data submodel per IDTA 02002.

    Contains technical specifications from AAS.
    """
    controller_type: str = Field(..., description="Controller type (TinyG, GRBL, etc.)")
    axes_count: int = Field(default=3, ge=1, le=9, description="Number of axes")
    work_envelope: WorkEnvelope = Field(
        default_factory=WorkEnvelope,
        description="Machine work envelope"
    )
    max_feed_rate: float = Field(default=5000.0, gt=0, description="Max feed rate (mm/min)")
    max_spindle_speed: float = Field(default=24000.0, gt=0, description="Max spindle RPM")
    positioning_accuracy: Optional[float] = Field(None, gt=0, description="Positioning accuracy (mm)")
    repeatability: Optional[float] = Field(None, gt=0, description="Repeatability (mm)")


# =============================================================================
# ISO 23247-3: Digital Representation (Main Schema)
# =============================================================================

class DigitalRepresentation(BaseModel):
    """
    ISO 23247-3 compliant digital representation.

    This is the main schema for representing an Observable Manufacturing Element
    (OME) as a digital twin for Unity visualization.

    The schema integrates:
    - Real-time state from controllers (MTConnect aligned)
    - Geometry references (STEP AP242 derived)
    - AAS submodels (IEC 63278)
    - Data lineage and quality (ISO 8000)
    """
    # Core identification
    ome_id: str = Field(..., description="Unique OME identifier")
    ome_type: OMEType = Field(default=OMEType.EQUIPMENT, description="OME type")
    equipment_subtype: Optional[EquipmentSubtype] = Field(
        None,
        description="Equipment subtype for machines"
    )
    timestamp: float = Field(..., description="State timestamp (Unix)")
    frame_number: int = Field(default=0, ge=0, description="Frame sequence number")

    # Geometry (STEP-derived)
    geometry_ref: Optional[str] = Field(
        None,
        description="URI to geometry resource (glTF/STEP)"
    )
    geometry_format: str = Field(default="glTF", description="Geometry format")
    pmi_ref: Optional[str] = Field(
        None,
        description="URI to PMI annotations (AP242)"
    )

    # Real-time state
    operational_state: OperationalState = Field(
        default_factory=OperationalState,
        description="Current operational state"
    )
    position: Position3D = Field(
        default_factory=Position3D,
        description="Current work position"
    )
    machine_position: Optional[Position3D] = Field(
        None,
        description="Current machine position"
    )
    kinematics: KinematicsState = Field(
        default_factory=KinematicsState,
        description="Full kinematic chain state"
    )

    # Sensor overlay
    sensors: Optional[SensorOverlay] = Field(
        None,
        description="Aggregated sensor data for visualization"
    )

    # AAS-derived attributes
    identification: Optional[IdentificationSubmodel] = Field(
        None,
        description="Identification from AAS"
    )
    technical_data: Optional[TechnicalDataSubmodel] = Field(
        None,
        description="Technical data from AAS"
    )
    aas_shell_ref: Optional[str] = Field(
        None,
        description="URI to full AAS shell"
    )

    # Data quality and lineage
    lineage: Optional[DataLineage] = Field(
        None,
        description="Data lineage for traceability"
    )
    quality_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Overall data quality score"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "ome_id": "mill-001",
                "ome_type": "equipment",
                "equipment_subtype": "cnc_mill",
                "timestamp": 1703894400.123,
                "frame_number": 12345,
                "geometry_ref": "/api/unity/geometry/mill-001",
                "geometry_format": "glTF",
                "operational_state": {
                    "execution": "ACTIVE",
                    "mode": "AUTOMATIC",
                    "motion_mode": "linear",
                    "program": "part_001.nc",
                    "line_number": 150
                },
                "position": {"x": 100.5, "y": 50.2, "z": -25.0},
                "quality_score": 0.98
            }
        }


# =============================================================================
# STEP Geometry Schemas
# =============================================================================

class STEPModelInfo(BaseModel):
    """STEP AP242 model information."""
    file_path: str = Field(..., description="Path to STEP file")
    format_version: str = Field(default="AP242", description="STEP format version")
    units: str = Field(default="mm", description="Model units")
    assembly_structure: Optional[Dict[str, Any]] = Field(
        None,
        description="Assembly hierarchy"
    )
    has_pmi: bool = Field(default=False, description="Contains PMI data")


class PMIAnnotation(BaseModel):
    """Product Manufacturing Information annotation from STEP AP242."""
    annotation_id: str = Field(..., description="Unique annotation ID")
    annotation_type: str = Field(..., description="Type (dimension, tolerance, datum, etc.)")
    value: str = Field(..., description="Annotation value/text")
    position: Position3D = Field(..., description="3D position for display")
    normal: Optional[Position3D] = Field(None, description="Display normal vector")
    associated_geometry: Optional[str] = Field(None, description="Associated geometry ID")


class UnityGeometry(BaseModel):
    """Geometry prepared for Unity import."""
    format: str = Field(default="glTF", description="Export format")
    data_uri: str = Field(..., description="URI to geometry data")
    scale_factor: float = Field(default=0.001, description="Scale factor (mm to Unity units)")
    hierarchy: Dict[str, Any] = Field(
        default_factory=dict,
        description="GameObject hierarchy for kinematic chain"
    )
    materials: List[str] = Field(
        default_factory=list,
        description="Material names for assignment"
    )


# =============================================================================
# STEP-NC Toolpath Schemas (ISO 14649)
# =============================================================================

class STEPNCWorkingStep(BaseModel):
    """STEP-NC working step (machining operation)."""
    step_id: str = Field(..., description="Working step ID")
    step_name: str = Field(..., description="Operation name")
    feature_type: str = Field(..., description="Machining feature type")
    tool_number: int = Field(..., ge=0, description="Tool number")
    feed_rate: float = Field(..., gt=0, description="Feed rate (mm/min)")
    spindle_speed: float = Field(..., gt=0, description="Spindle speed (RPM)")
    cutting_depth: float = Field(default=0.0, description="Cutting depth (mm)")
    step_over: float = Field(default=0.0, description="Step over (mm)")


class ToolpathSegment(BaseModel):
    """Individual toolpath segment."""
    start: Position3D = Field(..., description="Segment start point")
    end: Position3D = Field(..., description="Segment end point")
    motion_type: MotionMode = Field(..., description="Motion type")
    feed_rate: float = Field(..., gt=0, description="Feed rate (mm/min)")
    line_number: Optional[int] = Field(None, description="Source G-code line")
    arc_center: Optional[Position3D] = Field(None, description="Arc center (for G2/G3)")
    arc_radius: Optional[float] = Field(None, gt=0, description="Arc radius (mm)")


class STEPNCToolpath(BaseModel):
    """STEP-NC derived toolpath for Unity visualization."""
    program_id: str = Field(..., description="Program identifier")
    working_steps: List[STEPNCWorkingStep] = Field(
        default_factory=list,
        description="Machining working steps"
    )
    segments: List[ToolpathSegment] = Field(
        default_factory=list,
        description="Toolpath segments"
    )
    bounds: BoundingBox = Field(..., description="Toolpath bounding box")
    estimated_time_seconds: float = Field(default=0.0, ge=0, description="Estimated cycle time")
    total_distance_mm: float = Field(default=0.0, ge=0, description="Total tool travel distance")


# =============================================================================
# Unity-specific Request/Response Schemas
# =============================================================================

class UnitySubscribeRequest(BaseModel):
    """Request to subscribe to Unity state updates."""
    machine_id: str = Field(..., description="Machine to subscribe to")
    update_rate_hz: int = Field(default=30, ge=1, le=60, description="Desired update rate")
    include_sensors: bool = Field(default=True, description="Include sensor overlay")
    include_kinematics: bool = Field(default=True, description="Include full kinematics")
    include_toolpath: bool = Field(default=False, description="Include toolpath trail")


class UnityStateResponse(BaseModel):
    """Response containing Unity digital twin state."""
    success: bool = Field(default=True, description="Request success")
    representation: DigitalRepresentation = Field(..., description="Digital representation")
    trail_points: Optional[List[Position3D]] = Field(
        None,
        description="Recent toolpath trail points"
    )


class UnityGeometryRequest(BaseModel):
    """Request for Unity-compatible geometry."""
    machine_id: str = Field(..., description="Machine ID")
    format: str = Field(default="glTF", description="Desired format (glTF, FBX)")
    include_pmi: bool = Field(default=True, description="Include PMI annotations")
    lod_level: int = Field(default=0, ge=0, le=3, description="Level of detail (0=highest)")


class UnityToolpathRequest(BaseModel):
    """Request for toolpath visualization data."""
    gcode_content: Optional[str] = Field(None, description="G-code content to parse")
    file_path: Optional[str] = Field(None, description="Path to G-code file")
    step_nc_path: Optional[str] = Field(None, description="Path to STEP-NC file")
    max_segments: int = Field(default=10000, ge=100, le=100000, description="Max segments")
