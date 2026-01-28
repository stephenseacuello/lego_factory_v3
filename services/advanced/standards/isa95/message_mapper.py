"""
ISA-95 Message Mapper

Maps between internal data models and ISA-95/B2MML structures.

Reference: IEC 62264-2 (Object Model), B2MML v7.0
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ISA95Level(Enum):
    """ISA-95 Hierarchy Levels."""
    ENTERPRISE = 4
    SITE = 3
    AREA = 2
    WORK_CENTER = 1
    WORK_UNIT = 0


class ObjectType(Enum):
    """ISA-95 Object Types."""
    # Equipment
    EQUIPMENT = "Equipment"
    EQUIPMENT_CLASS = "EquipmentClass"
    EQUIPMENT_CAPABILITY = "EquipmentCapability"

    # Material
    MATERIAL = "Material"
    MATERIAL_CLASS = "MaterialClass"
    MATERIAL_LOT = "MaterialLot"
    MATERIAL_SUBLOT = "MaterialSublot"

    # Personnel
    PERSON = "Person"
    PERSONNEL_CLASS = "PersonnelClass"

    # Physical Asset
    PHYSICAL_ASSET = "PhysicalAsset"
    PHYSICAL_ASSET_CLASS = "PhysicalAssetClass"

    # Operations
    OPERATIONS_DEFINITION = "OperationsDefinition"
    OPERATIONS_SCHEDULE = "OperationsSchedule"
    OPERATIONS_REQUEST = "OperationsRequest"
    OPERATIONS_RESPONSE = "OperationsResponse"
    OPERATIONS_PERFORMANCE = "OperationsPerformance"

    # Production
    WORK_DIRECTIVE = "WorkDirective"
    WORK_PERFORMANCE = "WorkPerformance"


class DataType(Enum):
    """ISA-95 Data Types."""
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATETIME = "dateTime"
    DURATION = "duration"
    IDENTIFIER = "identifier"
    QUANTITY = "quantity"


@dataclass
class Property:
    """ISA-95 Property (name-value pair)."""
    id: str
    value: Any
    data_type: DataType = DataType.STRING
    description: Optional[str] = None
    unit_of_measure: Optional[str] = None


@dataclass
class HierarchyScope:
    """ISA-95 Hierarchy Scope."""
    equipment_id: str
    equipment_level: ISA95Level
    equipment_class: Optional[str] = None


@dataclass
class MaterialDefinition:
    """ISA-95 Material Definition."""
    id: str
    description: Optional[str] = None
    material_class_id: Optional[str] = None
    properties: List[Property] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "MaterialDefinitionID": self.id,
            "Description": self.description,
            "MaterialClassID": self.material_class_id,
            "MaterialDefinitionProperty": [
                {
                    "ID": p.id,
                    "Value": {"Value": p.value, "DataType": p.data_type.value},
                    "Description": p.description,
                    "UnitOfMeasure": p.unit_of_measure
                }
                for p in self.properties
            ]
        }


@dataclass
class EquipmentDefinition:
    """ISA-95 Equipment Definition."""
    id: str
    description: Optional[str] = None
    equipment_level: ISA95Level = ISA95Level.WORK_UNIT
    equipment_class_id: Optional[str] = None
    properties: List[Property] = field(default_factory=list)
    capabilities: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "EquipmentID": self.id,
            "Description": self.description,
            "EquipmentLevel": self.equipment_level.name,
            "EquipmentClassID": self.equipment_class_id,
            "EquipmentProperty": [
                {
                    "ID": p.id,
                    "Value": {"Value": p.value, "DataType": p.data_type.value},
                    "Description": p.description
                }
                for p in self.properties
            ],
            "EquipmentCapability": self.capabilities
        }


@dataclass
class PersonnelDefinition:
    """ISA-95 Personnel Definition."""
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    personnel_class_id: Optional[str] = None
    properties: List[Property] = field(default_factory=list)
    qualifications: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "PersonID": self.id,
            "Name": self.name,
            "Description": self.description,
            "PersonnelClassID": self.personnel_class_id,
            "PersonnelProperty": [
                {
                    "ID": p.id,
                    "Value": {"Value": p.value}
                }
                for p in self.properties
            ],
            "PersonnelQualification": self.qualifications
        }


class ISA95MessageMapper:
    """
    ISA-95/IEC 62264 Message Mapper.

    Converts between internal LEGO MCP data models and
    ISA-95 compliant message structures.

    Usage:
        >>> mapper = ISA95MessageMapper()
        >>> b2mml = mapper.map_to_operations_request(job)
        >>> job = mapper.map_from_operations_request(b2mml)
    """

    def __init__(self, enterprise_id: str = "LEGO_MCP"):
        """
        Initialize mapper.

        Args:
            enterprise_id: Enterprise identifier
        """
        self.enterprise_id = enterprise_id

        # Material mappings
        self._material_classes: Dict[str, MaterialDefinition] = {}
        self._equipment_classes: Dict[str, EquipmentDefinition] = {}

        # Initialize standard LEGO MCP mappings
        self._init_lego_mappings()

        logger.info("ISA95MessageMapper initialized")

    def _init_lego_mappings(self) -> None:
        """Initialize LEGO MCP specific mappings."""
        # Material classes
        self.register_material_class(MaterialDefinition(
            id="ABS_FILAMENT",
            description="ABS plastic filament for 3D printing",
            material_class_id="THERMOPLASTIC",
            properties=[
                Property("MeltingPoint", 230.0, DataType.DECIMAL, unit_of_measure="CELSIUS"),
                Property("Diameter", 1.75, DataType.DECIMAL, unit_of_measure="MILLIMETER"),
                Property("Color", "Various", DataType.STRING),
            ]
        ))

        self.register_material_class(MaterialDefinition(
            id="ALUMINUM_BLOCK",
            description="Aluminum stock for CNC machining",
            material_class_id="METAL",
            properties=[
                Property("Alloy", "6061-T6", DataType.STRING),
                Property("HardnessBrinell", 95.0, DataType.DECIMAL),
            ]
        ))

        # Equipment classes
        self.register_equipment_class(EquipmentDefinition(
            id="3D_PRINTER",
            description="FDM 3D printer for LEGO brick manufacturing",
            equipment_level=ISA95Level.WORK_UNIT,
            equipment_class_id="ADDITIVE_MANUFACTURING",
            properties=[
                Property("BuildVolumeX", 200.0, DataType.DECIMAL, unit_of_measure="MILLIMETER"),
                Property("BuildVolumeY", 200.0, DataType.DECIMAL, unit_of_measure="MILLIMETER"),
                Property("BuildVolumeZ", 200.0, DataType.DECIMAL, unit_of_measure="MILLIMETER"),
                Property("LayerResolution", 0.1, DataType.DECIMAL, unit_of_measure="MILLIMETER"),
            ]
        ))

        self.register_equipment_class(EquipmentDefinition(
            id="CNC_MACHINE",
            description="CNC milling machine",
            equipment_level=ISA95Level.WORK_UNIT,
            equipment_class_id="SUBTRACTIVE_MANUFACTURING",
            properties=[
                Property("AxisCount", 5, DataType.INTEGER),
                Property("SpindleSpeedMax", 24000, DataType.INTEGER, unit_of_measure="RPM"),
            ]
        ))

    def register_material_class(self, material: MaterialDefinition) -> None:
        """Register a material class."""
        self._material_classes[material.id] = material

    def register_equipment_class(self, equipment: EquipmentDefinition) -> None:
        """Register an equipment class."""
        self._equipment_classes[equipment.id] = equipment

    def map_print_job_to_operations_request(
        self,
        job_id: str,
        brick_spec: Dict[str, Any],
        quantity: int,
        priority: int = 3,
        requested_start: Optional[datetime] = None,
        requested_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Map a print job to ISA-95 Operations Request.

        Args:
            job_id: Unique job identifier
            brick_spec: Brick specification
            quantity: Number of bricks to produce
            priority: Job priority (1-5)
            requested_start: Requested start time
            requested_end: Requested end time

        Returns:
            ISA-95 Operations Request dict
        """
        return {
            "OperationsRequest": {
                "ID": job_id,
                "Version": "1.0",
                "PublishedDate": datetime.utcnow().isoformat() + "Z",
                "OperationsType": "Production",
                "HierarchyScope": {
                    "EquipmentID": self.enterprise_id,
                    "EquipmentElementLevel": "Enterprise"
                },
                "RequestedStartTime": requested_start.isoformat() + "Z" if requested_start else None,
                "RequestedEndTime": requested_end.isoformat() + "Z" if requested_end else None,
                "Priority": str(priority),
                "RequestState": "Waiting",
                "SegmentRequirement": [
                    {
                        "ID": f"{job_id}_seg_001",
                        "ProcessSegmentID": "LEGO_BRICK_PRINT",
                        "Description": f"Print LEGO brick {brick_spec.get('studs_x', 2)}x{brick_spec.get('studs_y', 4)}",
                        "MaterialRequirement": [
                            {
                                "MaterialDefinitionID": "ABS_FILAMENT",
                                "MaterialUse": "Consumed",
                                "Quantity": {
                                    "QuantityString": str(quantity * 5),  # Estimated grams per brick
                                    "DataType": "decimal",
                                    "UnitOfMeasure": "GRAM"
                                }
                            }
                        ],
                        "EquipmentRequirement": [
                            {
                                "EquipmentID": "3D_PRINTER",
                                "EquipmentUse": "Primary"
                            }
                        ],
                        "SegmentParameter": [
                            {"ID": "StudsX", "Value": {"Value": brick_spec.get('studs_x', 2)}},
                            {"ID": "StudsY", "Value": {"Value": brick_spec.get('studs_y', 4)}},
                            {"ID": "HeightPlates", "Value": {"Value": brick_spec.get('height_plates', 3)}},
                            {"ID": "Color", "Value": {"Value": brick_spec.get('color', 'RED')}},
                            {"ID": "Quantity", "Value": {"Value": quantity}}
                        ]
                    }
                ]
            }
        }

    def map_operations_request_to_print_job(
        self,
        ops_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Map ISA-95 Operations Request to internal print job.

        Args:
            ops_request: ISA-95 Operations Request dict

        Returns:
            Internal print job dict
        """
        request = ops_request.get("OperationsRequest", ops_request)

        # Extract segment requirements
        segments = request.get("SegmentRequirement", [])
        segment = segments[0] if segments else {}

        # Extract parameters
        params = {}
        for param in segment.get("SegmentParameter", []):
            params[param["ID"]] = param["Value"]["Value"]

        return {
            "job_id": request.get("ID"),
            "brick_spec": {
                "studs_x": params.get("StudsX", 2),
                "studs_y": params.get("StudsY", 4),
                "height_plates": params.get("HeightPlates", 3),
                "color": params.get("Color", "RED")
            },
            "quantity": params.get("Quantity", 1),
            "priority": int(request.get("Priority", 3)),
            "requested_start": request.get("RequestedStartTime"),
            "requested_end": request.get("RequestedEndTime"),
            "status": request.get("RequestState", "Waiting")
        }

    def map_production_data_to_performance(
        self,
        job_id: str,
        job_state: str,
        start_time: datetime,
        end_time: Optional[datetime],
        good_count: int,
        reject_count: int,
        equipment_id: str,
        material_consumed: float
    ) -> Dict[str, Any]:
        """
        Map production data to ISA-95 Operations Performance.

        Args:
            job_id: Job identifier
            job_state: Current job state
            start_time: Actual start time
            end_time: Actual end time
            good_count: Good parts produced
            reject_count: Rejected parts
            equipment_id: Equipment used
            material_consumed: Material consumed (grams)

        Returns:
            ISA-95 Operations Performance dict
        """
        performance_id = f"PERF_{job_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        return {
            "OperationsPerformance": {
                "ID": performance_id,
                "Version": "1.0",
                "PublishedDate": datetime.utcnow().isoformat() + "Z",
                "OperationsType": "Production",
                "HierarchyScope": {
                    "EquipmentID": self.enterprise_id,
                    "EquipmentElementLevel": "Enterprise"
                },
                "OperationsRequestID": job_id,
                "OperationsResponse": [
                    {
                        "ID": f"{job_id}_resp",
                        "ResponseState": job_state,
                        "ActualStartTime": start_time.isoformat() + "Z",
                        "ActualEndTime": end_time.isoformat() + "Z" if end_time else None,
                        "SegmentResponse": [
                            {
                                "ID": f"{job_id}_seg_resp",
                                "ProcessSegmentID": "LEGO_BRICK_PRINT",
                                "MaterialActual": [
                                    {
                                        "MaterialDefinitionID": "ABS_FILAMENT",
                                        "MaterialUse": "Consumed",
                                        "Quantity": {
                                            "QuantityString": str(material_consumed),
                                            "UnitOfMeasure": "GRAM"
                                        }
                                    }
                                ],
                                "EquipmentActual": [
                                    {
                                        "EquipmentID": equipment_id,
                                        "EquipmentUse": "Primary"
                                    }
                                ],
                                "SegmentData": [
                                    {"ID": "GoodCount", "Value": {"Value": good_count}},
                                    {"ID": "RejectCount", "Value": {"Value": reject_count}},
                                    {"ID": "TotalCount", "Value": {"Value": good_count + reject_count}},
                                    {"ID": "YieldPercent", "Value": {
                                        "Value": round(good_count / max(good_count + reject_count, 1) * 100, 2)
                                    }}
                                ]
                            }
                        ]
                    }
                ]
            }
        }

    def map_equipment_state_to_capability(
        self,
        equipment_id: str,
        state: str,
        reason: Optional[str] = None,
        capacity_available: float = 100.0
    ) -> Dict[str, Any]:
        """
        Map equipment state to ISA-95 Equipment Capability.

        Args:
            equipment_id: Equipment identifier
            state: Current state (Available, Unavailable, etc.)
            reason: Reason for state
            capacity_available: Available capacity percentage

        Returns:
            ISA-95 Equipment Capability dict
        """
        return {
            "EquipmentCapability": {
                "ID": f"CAP_{equipment_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "PublishedDate": datetime.utcnow().isoformat() + "Z",
                "EquipmentElementLevel": "WorkUnit",
                "EquipmentCapabilityType": "Actual",
                "Reason": reason or "",
                "EquipmentCapabilityProperty": [
                    {
                        "ID": "State",
                        "Value": {"Value": state}
                    },
                    {
                        "ID": "CapacityAvailable",
                        "Value": {
                            "Value": capacity_available,
                            "UnitOfMeasure": "PERCENT"
                        }
                    }
                ],
                "Equipment": [
                    {"EquipmentID": equipment_id}
                ]
            }
        }

    def get_material_definition(self, material_id: str) -> Optional[Dict]:
        """Get material definition as dict."""
        material = self._material_classes.get(material_id)
        return material.to_dict() if material else None

    def get_equipment_definition(self, equipment_id: str) -> Optional[Dict]:
        """Get equipment definition as dict."""
        equipment = self._equipment_classes.get(equipment_id)
        return equipment.to_dict() if equipment else None

    def get_all_material_definitions(self) -> List[Dict]:
        """Get all material definitions."""
        return [m.to_dict() for m in self._material_classes.values()]

    def get_all_equipment_definitions(self) -> List[Dict]:
        """Get all equipment definitions."""
        return [e.to_dict() for e in self._equipment_classes.values()]
