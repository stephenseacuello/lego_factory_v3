"""
LEGO MCP OPC UA NodeSet

Custom OPC UA information model for LEGO brick manufacturing.
Defines object types, data types, and methods specific to
the LEGO MCP manufacturing system.

Reference: OPC UA Part 5 (Information Model)
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .namespace import OPCUANamespace

logger = logging.getLogger(__name__)


@dataclass
class LegoMCPTypes:
    """Node IDs for LEGO MCP types."""
    # Object Types
    manufacturing_system: str = ""
    brick_printer: str = ""
    cnc_machine: str = ""
    robot_arm: str = ""
    quality_station: str = ""
    conveyor: str = ""

    # Data Types
    brick_specification: str = ""
    print_job: str = ""
    quality_result: str = ""
    machine_state: str = ""

    # Variable Types
    temperature_variable: str = ""
    position_variable: str = ""
    speed_variable: str = ""


class LegoMCPNodeSet:
    """
    LEGO MCP Manufacturing Information Model.

    Provides a complete OPC UA information model for:
    - 3D printing equipment
    - CNC machines
    - Robotic arms
    - Quality inspection stations
    - Material handling

    Based on OPC UA companion specifications:
    - OPC 40001 (Machinery)
    - OPC 40501 (Robotics)

    Usage:
        >>> nodeset = LegoMCPNodeSet()
        >>> server.load_nodeset(nodeset)
        >>> # Types are now available
        >>> printer = server.instantiate("BrickPrinterType")
    """

    NAMESPACE_URI = "urn:lego-mcp:manufacturing"

    def __init__(self):
        """Initialize LEGO MCP NodeSet."""
        self.namespace = OPCUANamespace(self.NAMESPACE_URI, index=2)
        self.types = LegoMCPTypes()

        # Build the information model
        self._define_data_types()
        self._define_variable_types()
        self._define_object_types()

        logger.info("LegoMCPNodeSet initialized")

    def _define_data_types(self) -> None:
        """Define custom data types."""

        # Brick Specification
        self.types.brick_specification = self.namespace.add_data_type(
            name="BrickSpecificationType",
            base_type="Structure",
            fields=[
                {"name": "StudsX", "data_type": "UInt32"},
                {"name": "StudsY", "data_type": "UInt32"},
                {"name": "HeightPlates", "data_type": "UInt32"},
                {"name": "Color", "data_type": "String"},
                {"name": "Material", "data_type": "String"},
                {"name": "ToleranceMm", "data_type": "Double"},
            ],
            description="LEGO brick specification with dimensions and material"
        )

        # Print Job
        self.types.print_job = self.namespace.add_data_type(
            name="PrintJobType",
            base_type="Structure",
            fields=[
                {"name": "JobId", "data_type": "String"},
                {"name": "BrickSpec", "data_type": "BrickSpecificationType"},
                {"name": "Quantity", "data_type": "UInt32"},
                {"name": "Priority", "data_type": "Int32"},
                {"name": "Status", "data_type": "String"},
                {"name": "Progress", "data_type": "Double"},
                {"name": "StartTime", "data_type": "DateTime"},
                {"name": "EstimatedEndTime", "data_type": "DateTime"},
            ],
            description="3D print job specification"
        )

        # Quality Result
        self.types.quality_result = self.namespace.add_data_type(
            name="QualityResultType",
            base_type="Structure",
            fields=[
                {"name": "InspectionId", "data_type": "String"},
                {"name": "PartId", "data_type": "String"},
                {"name": "PassFail", "data_type": "Boolean"},
                {"name": "DimensionalDeviation", "data_type": "Double"},
                {"name": "SurfaceScore", "data_type": "Double"},
                {"name": "ColorMatch", "data_type": "Double"},
                {"name": "DefectCount", "data_type": "UInt32"},
                {"name": "InspectionTime", "data_type": "DateTime"},
            ],
            description="Quality inspection result"
        )

        # Machine State
        self.types.machine_state = self.namespace.add_data_type(
            name="MachineStateType",
            base_type="Enumeration",
            fields=[
                {"name": "Unknown", "value": 0},
                {"name": "Initializing", "value": 1},
                {"name": "Ready", "value": 2},
                {"name": "Running", "value": 3},
                {"name": "Paused", "value": 4},
                {"name": "Stopped", "value": 5},
                {"name": "Error", "value": 6},
                {"name": "Maintenance", "value": 7},
            ],
            description="Machine operational state"
        )

    def _define_variable_types(self) -> None:
        """Define custom variable types."""

        # Temperature Variable
        self.types.temperature_variable = self.namespace.add_variable_type(
            name="TemperatureVariableType",
            data_type="Double",
            description="Temperature measurement in degrees Celsius"
        )

        # Position Variable
        self.types.position_variable = self.namespace.add_variable_type(
            name="PositionVariableType",
            data_type="Double",
            value_rank=1,  # Array
            description="Position in mm (X, Y, Z)"
        )

        # Speed Variable
        self.types.speed_variable = self.namespace.add_variable_type(
            name="SpeedVariableType",
            data_type="Double",
            description="Speed in mm/s"
        )

    def _define_object_types(self) -> None:
        """Define object types for manufacturing equipment."""

        # Manufacturing System (root type)
        self.types.manufacturing_system = self.namespace.add_object_type(
            name="ManufacturingSystemType",
            description="LEGO MCP Manufacturing System root object",
            variables=[
                {"name": "SystemId", "data_type": "String"},
                {"name": "State", "data_type": "MachineStateType"},
                {"name": "ActiveJobs", "data_type": "UInt32"},
                {"name": "TotalPartsMade", "data_type": "UInt64"},
                {"name": "Uptime", "data_type": "Double"},
                {"name": "OEE", "data_type": "Double"},
            ],
            methods=[
                {
                    "name": "StartProduction",
                    "input_args": [{"name": "JobId", "data_type": "String"}],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "StopProduction",
                    "input_args": [],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "GetStatus",
                    "input_args": [],
                    "output_args": [{"name": "Status", "data_type": "String"}]
                },
            ]
        )

        # Brick Printer
        self.types.brick_printer = self.namespace.add_object_type(
            name="BrickPrinterType",
            base_type="ManufacturingSystemType",
            description="3D printer for LEGO brick manufacturing",
            variables=[
                {"name": "NozzleTemperature", "data_type": "Double"},
                {"name": "BedTemperature", "data_type": "Double"},
                {"name": "ChamberTemperature", "data_type": "Double"},
                {"name": "CurrentLayer", "data_type": "UInt32"},
                {"name": "TotalLayers", "data_type": "UInt32"},
                {"name": "PrintSpeed", "data_type": "Double"},
                {"name": "FilamentUsed", "data_type": "Double"},
                {"name": "CurrentJob", "data_type": "PrintJobType"},
                {"name": "PrintHeadPosition", "data_type": "PositionVariableType"},
            ],
            methods=[
                {
                    "name": "StartPrint",
                    "input_args": [
                        {"name": "JobSpec", "data_type": "PrintJobType"}
                    ],
                    "output_args": [
                        {"name": "JobId", "data_type": "String"},
                        {"name": "EstimatedTime", "data_type": "Double"}
                    ]
                },
                {
                    "name": "PausePrint",
                    "input_args": [],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "ResumePrint",
                    "input_args": [],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "CancelPrint",
                    "input_args": [],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "SetTemperature",
                    "input_args": [
                        {"name": "Zone", "data_type": "String"},
                        {"name": "Temperature", "data_type": "Double"}
                    ],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
            ]
        )

        # CNC Machine
        self.types.cnc_machine = self.namespace.add_object_type(
            name="CNCMachineType",
            base_type="ManufacturingSystemType",
            description="CNC machine for precision mold making",
            variables=[
                {"name": "SpindleSpeed", "data_type": "Double"},
                {"name": "FeedRate", "data_type": "Double"},
                {"name": "ToolNumber", "data_type": "UInt32"},
                {"name": "ToolLife", "data_type": "Double"},
                {"name": "AxisPosition", "data_type": "PositionVariableType"},
                {"name": "CoolantLevel", "data_type": "Double"},
                {"name": "CurrentProgram", "data_type": "String"},
                {"name": "ProgramLine", "data_type": "UInt32"},
            ],
            methods=[
                {
                    "name": "LoadProgram",
                    "input_args": [{"name": "ProgramName", "data_type": "String"}],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "StartProgram",
                    "input_args": [],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "HomeAxes",
                    "input_args": [],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "ToolChange",
                    "input_args": [{"name": "ToolNumber", "data_type": "UInt32"}],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
            ]
        )

        # Robot Arm
        self.types.robot_arm = self.namespace.add_object_type(
            name="RobotArmType",
            base_type="ManufacturingSystemType",
            description="Robotic arm for material handling",
            variables=[
                {"name": "JointPositions", "data_type": "Double", "value_rank": 1},
                {"name": "EndEffectorPosition", "data_type": "PositionVariableType"},
                {"name": "EndEffectorOrientation", "data_type": "Double", "value_rank": 1},
                {"name": "GripperState", "data_type": "Boolean"},
                {"name": "Payload", "data_type": "Double"},
                {"name": "Speed", "data_type": "Double"},
                {"name": "Acceleration", "data_type": "Double"},
            ],
            methods=[
                {
                    "name": "MoveTo",
                    "input_args": [
                        {"name": "Position", "data_type": "Double", "value_rank": 1},
                        {"name": "Speed", "data_type": "Double"}
                    ],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "MoveJoint",
                    "input_args": [
                        {"name": "JointAngles", "data_type": "Double", "value_rank": 1},
                        {"name": "Speed", "data_type": "Double"}
                    ],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "OpenGripper",
                    "input_args": [],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "CloseGripper",
                    "input_args": [{"name": "Force", "data_type": "Double"}],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "Stop",
                    "input_args": [],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
            ]
        )

        # Quality Station
        self.types.quality_station = self.namespace.add_object_type(
            name="QualityStationType",
            base_type="ManufacturingSystemType",
            description="Vision-based quality inspection station",
            variables=[
                {"name": "InspectionCount", "data_type": "UInt64"},
                {"name": "PassCount", "data_type": "UInt64"},
                {"name": "FailCount", "data_type": "UInt64"},
                {"name": "PassRate", "data_type": "Double"},
                {"name": "LastResult", "data_type": "QualityResultType"},
                {"name": "CameraStatus", "data_type": "String"},
                {"name": "LightingIntensity", "data_type": "Double"},
            ],
            methods=[
                {
                    "name": "InspectPart",
                    "input_args": [{"name": "PartId", "data_type": "String"}],
                    "output_args": [{"name": "Result", "data_type": "QualityResultType"}]
                },
                {
                    "name": "Calibrate",
                    "input_args": [],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "SetLighting",
                    "input_args": [{"name": "Intensity", "data_type": "Double"}],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
            ]
        )

        # Conveyor
        self.types.conveyor = self.namespace.add_object_type(
            name="ConveyorType",
            base_type="ManufacturingSystemType",
            description="Conveyor belt for material transport",
            variables=[
                {"name": "Speed", "data_type": "Double"},
                {"name": "Direction", "data_type": "Int32"},
                {"name": "Length", "data_type": "Double"},
                {"name": "ItemCount", "data_type": "UInt32"},
                {"name": "LoadSensorValue", "data_type": "Double"},
            ],
            methods=[
                {
                    "name": "Start",
                    "input_args": [{"name": "Speed", "data_type": "Double"}],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "Stop",
                    "input_args": [],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "SetSpeed",
                    "input_args": [{"name": "Speed", "data_type": "Double"}],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
                {
                    "name": "ReverseDirection",
                    "input_args": [],
                    "output_args": [{"name": "Success", "data_type": "Boolean"}]
                },
            ]
        )

    def generate_nodeset2_xml(self) -> str:
        """Generate NodeSet2 XML for the information model."""
        return self.namespace.generate_nodeset2_xml()

    def get_type_info(self) -> Dict[str, Any]:
        """Get information about defined types."""
        return {
            "namespace_uri": self.NAMESPACE_URI,
            "types": {
                "data_types": list(self.namespace._data_types.keys()),
                "object_types": list(self.namespace._object_types.keys()),
                "variable_types": list(self.namespace._variable_types.keys()),
            },
            "type_ids": {
                "manufacturing_system": self.types.manufacturing_system,
                "brick_printer": self.types.brick_printer,
                "cnc_machine": self.types.cnc_machine,
                "robot_arm": self.types.robot_arm,
                "quality_station": self.types.quality_station,
                "conveyor": self.types.conveyor,
            }
        }
