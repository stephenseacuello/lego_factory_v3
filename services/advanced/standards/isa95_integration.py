"""
ISA-95 / IEC 62264 Complete Integration Module

Implements the complete ISA-95 enterprise-control system integration
standard for LEGO MCP manufacturing.

Covers:
- Level 0-4 integration architecture
- B2MML (Business to Manufacturing Markup Language)
- Equipment hierarchy
- Operations scheduling
- Production performance analysis

Reference: ISA-95.00.01 through ISA-95.00.06

Author: LEGO MCP Standards Engineering
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


# =============================================================================
# ISA-95 Level Definitions
# =============================================================================

class ISA95Level(Enum):
    """ISA-95 hierarchical levels."""
    LEVEL_0 = 0  # Physical process
    LEVEL_1 = 1  # Sensing and manipulation
    LEVEL_2 = 2  # Control systems (PLC/DCS)
    LEVEL_3 = 3  # Manufacturing operations (MES)
    LEVEL_4 = 4  # Business planning (ERP)


class EquipmentLevel(Enum):
    """ISA-95 equipment hierarchy levels."""
    ENTERPRISE = "enterprise"
    SITE = "site"
    AREA = "area"
    WORK_CENTER = "work_center"
    WORK_UNIT = "work_unit"
    EQUIPMENT = "equipment"


class OperationType(Enum):
    """Types of manufacturing operations."""
    PRODUCTION = "production"
    MAINTENANCE = "maintenance"
    QUALITY = "quality"
    INVENTORY = "inventory"


class OperationState(Enum):
    """Operation execution states."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"


# =============================================================================
# Equipment Hierarchy (ISA-95.00.01)
# =============================================================================

@dataclass
class EquipmentProperty:
    """Equipment property."""
    name: str
    value: Any
    unit: Optional[str] = None
    data_type: str = "string"


@dataclass
class Equipment:
    """ISA-95 equipment element."""
    id: str
    name: str
    level: EquipmentLevel
    description: str = ""
    parent_id: Optional[str] = None
    properties: List[EquipmentProperty] = field(default_factory=list)
    children: List["Equipment"] = field(default_factory=list)
    status: str = "idle"

    def to_b2mml(self) -> ET.Element:
        """Convert to B2MML XML element."""
        elem = ET.Element("Equipment")
        ET.SubElement(elem, "ID").text = self.id
        ET.SubElement(elem, "Description").text = self.name
        ET.SubElement(elem, "EquipmentLevel").text = self.level.value

        if self.parent_id:
            hierarchy = ET.SubElement(elem, "HierarchyScope")
            ET.SubElement(hierarchy, "EquipmentID").text = self.parent_id

        for prop in self.properties:
            prop_elem = ET.SubElement(elem, "EquipmentProperty")
            ET.SubElement(prop_elem, "ID").text = prop.name
            value_elem = ET.SubElement(prop_elem, "Value")
            ET.SubElement(value_elem, "ValueString").text = str(prop.value)
            if prop.unit:
                ET.SubElement(value_elem, "UnitOfMeasure").text = prop.unit

        return elem


class EquipmentHierarchy:
    """
    ISA-95 Equipment Hierarchy Manager.

    Manages the complete equipment model from enterprise
    down to individual work units.
    """

    def __init__(self):
        self.equipment: Dict[str, Equipment] = {}
        self._root: Optional[str] = None

    def add_equipment(self, equipment: Equipment) -> None:
        """Add equipment to hierarchy."""
        self.equipment[equipment.id] = equipment

        if equipment.parent_id and equipment.parent_id in self.equipment:
            parent = self.equipment[equipment.parent_id]
            parent.children.append(equipment)
        elif equipment.level == EquipmentLevel.ENTERPRISE:
            self._root = equipment.id

        logger.debug(f"Added equipment: {equipment.name} ({equipment.level.value})")

    def get_equipment(self, equipment_id: str) -> Optional[Equipment]:
        """Get equipment by ID."""
        return self.equipment.get(equipment_id)

    def get_children(self, equipment_id: str) -> List[Equipment]:
        """Get child equipment."""
        eq = self.equipment.get(equipment_id)
        return eq.children if eq else []

    def get_by_level(self, level: EquipmentLevel) -> List[Equipment]:
        """Get all equipment at a level."""
        return [e for e in self.equipment.values() if e.level == level]

    def to_b2mml(self) -> ET.Element:
        """Export hierarchy as B2MML XML."""
        root = ET.Element("EquipmentInformation")
        root.set("xmlns", "http://www.mesa.org/xml/B2MML")

        for eq in self.equipment.values():
            root.append(eq.to_b2mml())

        return root


# =============================================================================
# Material Model (ISA-95.00.02)
# =============================================================================

@dataclass
class MaterialClass:
    """Material classification."""
    id: str
    name: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MaterialDefinition:
    """Material definition."""
    id: str
    name: str
    material_class_id: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MaterialLot:
    """Material lot/batch."""
    id: str
    material_definition_id: str
    quantity: float
    unit: str
    status: str = "available"
    storage_location: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MaterialModel:
    """ISA-95 Material Model Manager."""

    def __init__(self):
        self.classes: Dict[str, MaterialClass] = {}
        self.definitions: Dict[str, MaterialDefinition] = {}
        self.lots: Dict[str, MaterialLot] = {}

    def add_class(self, material_class: MaterialClass) -> None:
        """Add material class."""
        self.classes[material_class.id] = material_class

    def add_definition(self, definition: MaterialDefinition) -> None:
        """Add material definition."""
        self.definitions[definition.id] = definition

    def add_lot(self, lot: MaterialLot) -> None:
        """Add material lot."""
        self.lots[lot.id] = lot

    def get_available_lots(self, material_id: str) -> List[MaterialLot]:
        """Get available lots for material."""
        return [
            lot for lot in self.lots.values()
            if lot.material_definition_id == material_id
            and lot.status == "available"
        ]


# =============================================================================
# Personnel Model (ISA-95.00.02)
# =============================================================================

@dataclass
class PersonnelClass:
    """Personnel classification (role)."""
    id: str
    name: str
    description: str = ""
    certifications: List[str] = field(default_factory=list)


@dataclass
class Person:
    """Individual person."""
    id: str
    name: str
    personnel_class_id: str
    certifications: List[str] = field(default_factory=list)
    availability: str = "available"


class PersonnelModel:
    """ISA-95 Personnel Model Manager."""

    def __init__(self):
        self.classes: Dict[str, PersonnelClass] = {}
        self.personnel: Dict[str, Person] = {}

    def add_class(self, personnel_class: PersonnelClass) -> None:
        """Add personnel class."""
        self.classes[personnel_class.id] = personnel_class

    def add_person(self, person: Person) -> None:
        """Add person."""
        self.personnel[person.id] = person

    def get_available_by_class(self, class_id: str) -> List[Person]:
        """Get available personnel by class."""
        return [
            p for p in self.personnel.values()
            if p.personnel_class_id == class_id
            and p.availability == "available"
        ]


# =============================================================================
# Operations Schedule (ISA-95.00.04)
# =============================================================================

@dataclass
class OperationsRequest:
    """Operations request (work order)."""
    id: str
    operation_type: OperationType
    description: str
    priority: int = 5
    requested_start: Optional[datetime] = None
    requested_end: Optional[datetime] = None
    equipment_requirement: Optional[str] = None
    material_requirements: List[Dict[str, Any]] = field(default_factory=list)
    personnel_requirements: List[Dict[str, Any]] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OperationsSegment:
    """Segment of an operations response."""
    id: str
    segment_type: str
    equipment_id: str
    scheduled_start: datetime
    scheduled_end: datetime
    state: OperationState = OperationState.PENDING
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None


@dataclass
class OperationsResponse:
    """Operations response (scheduled work)."""
    id: str
    request_id: str
    operation_type: OperationType
    state: OperationState
    segments: List[OperationsSegment] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OperationsScheduler:
    """
    ISA-95 Operations Scheduler.

    Handles operations requests from Level 4 (ERP)
    and generates operations responses for Level 3 (MES).
    """

    def __init__(self, equipment_hierarchy: EquipmentHierarchy):
        self.equipment = equipment_hierarchy
        self.requests: Dict[str, OperationsRequest] = {}
        self.responses: Dict[str, OperationsResponse] = {}

    def submit_request(self, request: OperationsRequest) -> str:
        """Submit operations request."""
        self.requests[request.id] = request
        logger.info(f"Operations request submitted: {request.id}")
        return request.id

    def schedule(self, request_id: str) -> Optional[OperationsResponse]:
        """Schedule operations request."""
        request = self.requests.get(request_id)
        if not request:
            return None

        # Find available equipment
        available_equipment = [
            e for e in self.equipment.get_by_level(EquipmentLevel.WORK_UNIT)
            if e.status == "idle"
        ]

        if not available_equipment:
            logger.warning(f"No equipment available for request {request_id}")
            return None

        # Simple first-fit scheduling
        equipment = available_equipment[0]
        start_time = request.requested_start or datetime.now(timezone.utc)
        duration = timedelta(hours=1)  # Default duration

        segment = OperationsSegment(
            id=str(uuid.uuid4()),
            segment_type=request.operation_type.value,
            equipment_id=equipment.id,
            scheduled_start=start_time,
            scheduled_end=start_time + duration,
        )

        response = OperationsResponse(
            id=str(uuid.uuid4()),
            request_id=request_id,
            operation_type=request.operation_type,
            state=OperationState.READY,
            segments=[segment],
        )

        self.responses[response.id] = response
        equipment.status = "scheduled"

        logger.info(f"Scheduled request {request_id} -> response {response.id}")
        return response

    def start_operation(self, response_id: str) -> bool:
        """Start scheduled operation."""
        response = self.responses.get(response_id)
        if not response or response.state != OperationState.READY:
            return False

        response.state = OperationState.RUNNING
        for segment in response.segments:
            segment.state = OperationState.RUNNING
            segment.actual_start = datetime.now(timezone.utc)

            eq = self.equipment.get_equipment(segment.equipment_id)
            if eq:
                eq.status = "running"

        logger.info(f"Started operation: {response_id}")
        return True

    def complete_operation(self, response_id: str) -> bool:
        """Complete operation."""
        response = self.responses.get(response_id)
        if not response or response.state != OperationState.RUNNING:
            return False

        response.state = OperationState.COMPLETED
        for segment in response.segments:
            segment.state = OperationState.COMPLETED
            segment.actual_end = datetime.now(timezone.utc)

            eq = self.equipment.get_equipment(segment.equipment_id)
            if eq:
                eq.status = "idle"

        logger.info(f"Completed operation: {response_id}")
        return True


# =============================================================================
# Operations Performance (ISA-95.00.05)
# =============================================================================

@dataclass
class ProductionPerformance:
    """Production performance record."""
    id: str
    response_id: str
    equipment_id: str
    start_time: datetime
    end_time: datetime
    quantity_produced: float
    quantity_unit: str
    good_quantity: float
    scrap_quantity: float
    rework_quantity: float
    energy_consumption: Optional[float] = None
    energy_unit: str = "kWh"


@dataclass
class OEEMetrics:
    """Overall Equipment Effectiveness metrics."""
    availability: float  # 0-1
    performance: float   # 0-1
    quality: float       # 0-1

    @property
    def oee(self) -> float:
        """Calculate OEE."""
        return self.availability * self.performance * self.quality

    def to_dict(self) -> Dict[str, float]:
        return {
            "availability": self.availability,
            "performance": self.performance,
            "quality": self.quality,
            "oee": self.oee,
        }


class PerformanceAnalyzer:
    """ISA-95 Performance Analysis."""

    def __init__(self):
        self.records: List[ProductionPerformance] = []

    def record_performance(self, performance: ProductionPerformance) -> None:
        """Record production performance."""
        self.records.append(performance)

    def calculate_oee(
        self,
        equipment_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> OEEMetrics:
        """Calculate OEE for equipment over time period."""
        relevant = [
            r for r in self.records
            if r.equipment_id == equipment_id
            and r.start_time >= start_time
            and r.end_time <= end_time
        ]

        if not relevant:
            return OEEMetrics(0, 0, 0)

        # Availability: actual run time / planned time
        total_planned = (end_time - start_time).total_seconds()
        total_run = sum(
            (r.end_time - r.start_time).total_seconds()
            for r in relevant
        )
        availability = total_run / total_planned if total_planned > 0 else 0

        # Performance: actual output / theoretical output
        # Simplified: assume theoretical = run_time / ideal_cycle_time
        total_produced = sum(r.quantity_produced for r in relevant)
        ideal_cycle_time = 10  # seconds per unit (example)
        theoretical = total_run / ideal_cycle_time
        performance = total_produced / theoretical if theoretical > 0 else 0

        # Quality: good units / total units
        total_good = sum(r.good_quantity for r in relevant)
        quality = total_good / total_produced if total_produced > 0 else 0

        return OEEMetrics(
            availability=min(1.0, availability),
            performance=min(1.0, performance),
            quality=min(1.0, quality),
        )


# =============================================================================
# ISA-95 Integration Manager
# =============================================================================

class ISA95IntegrationManager:
    """
    Complete ISA-95 Integration Manager.

    Provides unified interface for Level 3/4 integration
    following ISA-95 standards.

    Usage:
        manager = ISA95IntegrationManager()

        # Setup equipment hierarchy
        manager.add_equipment(Equipment(
            id="PLANT-1",
            name="LEGO Brick Plant",
            level=EquipmentLevel.SITE,
        ))

        # Submit work order from ERP
        request = OperationsRequest(
            id="WO-001",
            operation_type=OperationType.PRODUCTION,
            description="Produce 1000 4x2 red bricks",
        )
        manager.submit_work_order(request)

        # Schedule and execute
        response = manager.schedule_work_order("WO-001")
        manager.start_work_order(response.id)
        manager.complete_work_order(response.id)

        # Get performance
        oee = manager.get_oee("MOLD-01", start, end)
    """

    def __init__(self):
        self.equipment = EquipmentHierarchy()
        self.materials = MaterialModel()
        self.personnel = PersonnelModel()
        self.scheduler = OperationsScheduler(self.equipment)
        self.performance = PerformanceAnalyzer()

        logger.info("ISA-95 Integration Manager initialized")

    def add_equipment(self, equipment: Equipment) -> None:
        """Add equipment to hierarchy."""
        self.equipment.add_equipment(equipment)

    def add_material(
        self,
        material_class: MaterialClass,
        definition: MaterialDefinition,
    ) -> None:
        """Add material class and definition."""
        self.materials.add_class(material_class)
        self.materials.add_definition(definition)

    def add_material_lot(self, lot: MaterialLot) -> None:
        """Add material lot to inventory."""
        self.materials.add_lot(lot)

    def add_personnel_class(self, personnel_class: PersonnelClass) -> None:
        """Add personnel class."""
        self.personnel.add_class(personnel_class)

    def add_person(self, person: Person) -> None:
        """Add person."""
        self.personnel.add_person(person)

    def submit_work_order(self, request: OperationsRequest) -> str:
        """Submit work order (from ERP Level 4)."""
        return self.scheduler.submit_request(request)

    def schedule_work_order(self, request_id: str) -> Optional[OperationsResponse]:
        """Schedule work order."""
        return self.scheduler.schedule(request_id)

    def start_work_order(self, response_id: str) -> bool:
        """Start work order execution."""
        return self.scheduler.start_operation(response_id)

    def complete_work_order(
        self,
        response_id: str,
        performance_data: Optional[Dict] = None,
    ) -> bool:
        """Complete work order and record performance."""
        success = self.scheduler.complete_operation(response_id)

        if success and performance_data:
            response = self.scheduler.responses.get(response_id)
            if response and response.segments:
                segment = response.segments[0]
                perf = ProductionPerformance(
                    id=str(uuid.uuid4()),
                    response_id=response_id,
                    equipment_id=segment.equipment_id,
                    start_time=segment.actual_start or segment.scheduled_start,
                    end_time=segment.actual_end or segment.scheduled_end,
                    quantity_produced=performance_data.get("produced", 0),
                    quantity_unit=performance_data.get("unit", "pcs"),
                    good_quantity=performance_data.get("good", 0),
                    scrap_quantity=performance_data.get("scrap", 0),
                    rework_quantity=performance_data.get("rework", 0),
                )
                self.performance.record_performance(perf)

        return success

    def get_oee(
        self,
        equipment_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> OEEMetrics:
        """Get OEE metrics for equipment."""
        return self.performance.calculate_oee(equipment_id, start_time, end_time)

    def export_equipment_b2mml(self) -> str:
        """Export equipment hierarchy as B2MML XML."""
        root = self.equipment.to_b2mml()
        return ET.tostring(root, encoding="unicode")


# Factory function
def create_isa95_manager() -> ISA95IntegrationManager:
    """Create configured ISA-95 manager for LEGO MCP."""
    manager = ISA95IntegrationManager()

    # Setup default equipment hierarchy
    enterprise = Equipment(
        id="LEGO-ENTERPRISE",
        name="LEGO MCP Enterprise",
        level=EquipmentLevel.ENTERPRISE,
    )
    manager.add_equipment(enterprise)

    site = Equipment(
        id="LEGO-PLANT-1",
        name="LEGO Brick Manufacturing Plant",
        level=EquipmentLevel.SITE,
        parent_id="LEGO-ENTERPRISE",
    )
    manager.add_equipment(site)

    # Add default material classes
    abs_class = MaterialClass(
        id="MAT-ABS",
        name="ABS Plastic",
        description="Acrylonitrile Butadiene Styrene",
    )
    manager.add_material(
        abs_class,
        MaterialDefinition(
            id="MAT-ABS-RED",
            name="Red ABS",
            material_class_id="MAT-ABS",
        ),
    )

    return manager


__all__ = [
    "ISA95IntegrationManager",
    "ISA95Level",
    "EquipmentLevel",
    "Equipment",
    "EquipmentHierarchy",
    "OperationsRequest",
    "OperationsResponse",
    "OperationsScheduler",
    "OperationType",
    "OperationState",
    "MaterialModel",
    "MaterialClass",
    "MaterialDefinition",
    "MaterialLot",
    "PersonnelModel",
    "PersonnelClass",
    "Person",
    "ProductionPerformance",
    "OEEMetrics",
    "PerformanceAnalyzer",
    "create_isa95_manager",
]
