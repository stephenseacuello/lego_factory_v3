"""
ISO 23247 Manufacturing Ontology
================================

Provides semantic definitions for manufacturing entities in digital twin systems.
This module implements the Observable Manufacturing Element (OME) model from
ISO 23247-3, enabling consistent identification, classification, and relationship
modeling across the factory.

ISO 23247-3 Compliance
----------------------
This module implements:
    Section 5: Observable Manufacturing Element (OME) structure
    Section 6: Manufacturing element types and hierarchy
    Section 7: Attribute and property specifications
    Section 8: Relationship and composition models

OPC UA Integration
------------------
Entity types and relationships are designed to map cleanly to OPC UA:
    - Namespace URIs follow OPC UA conventions
    - NodeIds can be derived from entity identifiers
    - Type definitions align with OPC UA companion specifications

Manufacturing Hierarchy
-----------------------
The ISA-95 equipment hierarchy is modeled as:

    Enterprise
        └── Site
            └── Area
                └── WorkCenter (Production Line)
                    └── WorkUnit (Workstation/Cell)
                        └── Equipment (Machine)
                            └── EquipmentModule (Subsystem)
                                └── ControlModule (Sensor/Actuator)

Example:
    from services.digital_twin.manufacturing_ontology import (
        ManufacturingEntity,
        EntityType,
        create_machine_entity,
        get_entity_namespace,
    )

    # Create a machine entity
    machine = create_machine_entity(
        entity_id="cnc_001",
        name="Haas VF-2",
        capabilities=["milling", "drilling", "tapping"]
    )

    # Get the full namespace URI
    ns = get_entity_namespace(machine)
    # Returns: "urn:lego-factory:equipment:cnc_001"
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
from enum import Enum
from datetime import datetime
import json


# =============================================================================
# Entity Types (ISO 23247-3 Section 6)
# =============================================================================

class EntityType(Enum):
    """
    Manufacturing entity types following ISA-95 equipment hierarchy.

    These types represent the Observable Manufacturing Elements (OME)
    defined in ISO 23247-3 for digital twin systems.
    """

    # Level 4 - Enterprise (ISA-95 Level 4)
    ENTERPRISE = "enterprise"

    # Level 3 - Site/Plant
    SITE = "site"
    AREA = "area"

    # Level 2 - Production
    WORK_CENTER = "work_center"      # Production line
    WORK_UNIT = "work_unit"          # Workstation or cell
    STORAGE_ZONE = "storage_zone"    # Warehouse area

    # Level 1 - Equipment
    EQUIPMENT = "equipment"           # General equipment
    MACHINE = "machine"               # Machine tool (CNC, etc.)
    ROBOT = "robot"                   # Industrial robot
    AGV = "agv"                       # Automated guided vehicle
    CONVEYOR = "conveyor"             # Material handling
    PRINTER_3D = "printer_3d"         # Additive manufacturing

    # Level 0 - Components
    EQUIPMENT_MODULE = "equipment_module"  # Subsystem (spindle, axis)
    CONTROL_MODULE = "control_module"      # Sensor or actuator
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    TOOL = "tool"                          # Cutting tool, gripper

    # Material
    MATERIAL = "material"             # Raw material or WIP
    PRODUCT = "product"               # Finished product
    CONTAINER = "container"           # Pallet, bin, fixture

    # Personnel
    OPERATOR = "operator"
    MAINTENANCE_TECH = "maintenance_tech"


class EntityStatus(Enum):
    """
    Standard status values for manufacturing entities.

    Based on ISA-88/ISA-95 state models and PackML states.
    """

    # Basic states
    UNKNOWN = "unknown"
    OFFLINE = "offline"
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"

    # PackML states (ISA-88)
    STARTING = "starting"
    EXECUTING = "executing"
    COMPLETING = "completing"
    COMPLETED = "completed"
    RESETTING = "resetting"
    HOLDING = "holding"
    HELD = "held"
    UNHOLDING = "unholding"
    SUSPENDING = "suspending"
    SUSPENDED = "suspended"
    UNSUSPENDING = "unsuspending"
    ABORTING = "aborting"
    ABORTED = "aborted"
    CLEARING = "clearing"
    STOPPING = "stopping"

    # Maintenance states
    MAINTENANCE = "maintenance"
    SETUP = "setup"
    CHANGEOVER = "changeover"

    # Fault states
    FAULT = "fault"
    ERROR = "error"
    ALARM = "alarm"


class RelationshipType(Enum):
    """
    Relationship types between manufacturing entities.

    ISO 23247-3 Section 8 defines these relationships for digital twin
    composition and association.
    """

    # Composition (parent-child)
    CONTAINS = "contains"              # Parent contains child
    PART_OF = "part_of"                # Child is part of parent

    # Spatial
    LOCATED_IN = "located_in"          # Entity is physically in location
    ADJACENT_TO = "adjacent_to"        # Entities are physically adjacent
    CONNECTED_TO = "connected_to"      # Physical connection (conveyor, etc.)

    # Operational
    PRODUCES = "produces"              # Equipment produces product
    CONSUMES = "consumes"              # Equipment consumes material
    PROCESSES = "processes"            # Equipment processes material
    TRANSPORTS = "transports"          # Equipment moves material

    # Assignment
    ASSIGNED_TO = "assigned_to"        # Resource assigned to work
    OPERATED_BY = "operated_by"        # Equipment operated by personnel
    MAINTAINED_BY = "maintained_by"    # Equipment maintained by personnel

    # Dependency
    DEPENDS_ON = "depends_on"          # Operational dependency
    CONTROLS = "controls"              # Controller controls equipment
    MONITORS = "monitors"              # Sensor monitors equipment


# =============================================================================
# Capability Model (ISO 23247-3 Section 7)
# =============================================================================

class CapabilityType(Enum):
    """
    Manufacturing capability types for equipment.

    Capabilities describe what operations an entity can perform.
    """

    # Machining
    MILLING = "milling"
    TURNING = "turning"
    DRILLING = "drilling"
    GRINDING = "grinding"
    BORING = "boring"
    TAPPING = "tapping"
    EDM = "edm"                        # Electrical discharge machining

    # Forming
    BENDING = "bending"
    STAMPING = "stamping"
    FORGING = "forging"
    CASTING = "casting"

    # Additive
    FDM = "fdm"                        # Fused deposition modeling
    SLA = "sla"                        # Stereolithography
    SLS = "sls"                        # Selective laser sintering

    # Assembly
    PICK_PLACE = "pick_place"
    FASTENING = "fastening"
    WELDING = "welding"
    GLUING = "gluing"
    INSPECTION = "inspection"

    # Material handling
    TRANSPORT = "transport"
    STORAGE = "storage"
    DISPENSING = "dispensing"


@dataclass
class Capability:
    """
    Describes a specific capability of a manufacturing entity.

    Attributes:
        capability_type: The type of capability
        parameters: Capability parameters (e.g., max spindle speed)
        constraints: Operational constraints (e.g., max workpiece size)
        quality_level: Quality grade this capability can achieve
    """
    capability_type: CapabilityType
    parameters: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    quality_level: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": self.capability_type.value,
            "parameters": self.parameters,
            "constraints": self.constraints,
            "quality_level": self.quality_level
        }


# =============================================================================
# Entity Model (ISO 23247-3 Section 5)
# =============================================================================

@dataclass
class EntityIdentifier:
    """
    Unique identifier for a manufacturing entity.

    ISO 23247-3 requires globally unique identification with namespace
    support for multi-site and multi-vendor environments.

    Attributes:
        entity_id: Local identifier within the namespace
        namespace: URI-based namespace for global uniqueness
        entity_type: Type classification of the entity
        alternate_ids: Optional alternate identifiers (serial number, etc.)
    """
    entity_id: str
    namespace: str = "urn:lego-factory"
    entity_type: EntityType = EntityType.EQUIPMENT
    alternate_ids: Dict[str, str] = field(default_factory=dict)

    @property
    def uri(self) -> str:
        """Get full URI for this entity."""
        return f"{self.namespace}:{self.entity_type.value}:{self.entity_id}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "entity_id": self.entity_id,
            "namespace": self.namespace,
            "entity_type": self.entity_type.value,
            "uri": self.uri,
            "alternate_ids": self.alternate_ids
        }


@dataclass
class EntityRelationship:
    """
    Relationship between two manufacturing entities.

    Attributes:
        relationship_type: Type of relationship
        source_id: URI of source entity
        target_id: URI of target entity
        properties: Additional relationship properties
    """
    relationship_type: RelationshipType
    source_id: str
    target_id: str
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": self.relationship_type.value,
            "source": self.source_id,
            "target": self.target_id,
            "properties": self.properties
        }


@dataclass
class ManufacturingEntity:
    """
    Observable Manufacturing Element (OME) per ISO 23247-3.

    This is the core entity model for digital twins in manufacturing.
    Each entity represents a physical or logical manufacturing element
    with identity, properties, capabilities, and relationships.

    Attributes:
        identifier: Unique identifier with namespace
        name: Human-readable name
        description: Optional description
        status: Current operational status
        properties: Static and dynamic properties
        capabilities: What operations this entity can perform
        relationships: Relationships to other entities
        metadata: Additional metadata (created, modified, version)
    """

    identifier: EntityIdentifier
    name: str
    description: str = ""
    status: EntityStatus = EntityStatus.UNKNOWN
    properties: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[Capability] = field(default_factory=list)
    relationships: List[EntityRelationship] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize metadata if not provided."""
        if "created_at" not in self.metadata:
            self.metadata["created_at"] = datetime.utcnow().isoformat()
        if "version" not in self.metadata:
            self.metadata["version"] = "1.0.0"

    @property
    def entity_id(self) -> str:
        """Shortcut to get entity_id."""
        return self.identifier.entity_id

    @property
    def entity_type(self) -> EntityType:
        """Shortcut to get entity_type."""
        return self.identifier.entity_type

    @property
    def uri(self) -> str:
        """Shortcut to get full URI."""
        return self.identifier.uri

    def add_capability(self, capability: Capability) -> None:
        """Add a capability to this entity."""
        self.capabilities.append(capability)

    def add_relationship(
        self,
        rel_type: RelationshipType,
        target_uri: str,
        **properties
    ) -> None:
        """Add a relationship to another entity."""
        self.relationships.append(EntityRelationship(
            relationship_type=rel_type,
            source_id=self.uri,
            target_id=target_uri,
            properties=properties
        ))

    def has_capability(self, cap_type: CapabilityType) -> bool:
        """Check if entity has a specific capability."""
        return any(c.capability_type == cap_type for c in self.capabilities)

    def get_related(self, rel_type: RelationshipType) -> List[str]:
        """Get URIs of entities with the specified relationship."""
        return [
            r.target_id for r in self.relationships
            if r.relationship_type == rel_type
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON/message exchange."""
        return {
            "identifier": self.identifier.to_dict(),
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "properties": self.properties,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "relationships": [r.to_dict() for r in self.relationships],
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ManufacturingEntity':
        """Deserialize from dictionary."""
        identifier = EntityIdentifier(
            entity_id=data["identifier"]["entity_id"],
            namespace=data["identifier"].get("namespace", "urn:lego-factory"),
            entity_type=EntityType(data["identifier"]["entity_type"]),
            alternate_ids=data["identifier"].get("alternate_ids", {})
        )

        capabilities = [
            Capability(
                capability_type=CapabilityType(c["type"]),
                parameters=c.get("parameters", {}),
                constraints=c.get("constraints", {}),
                quality_level=c.get("quality_level")
            )
            for c in data.get("capabilities", [])
        ]

        relationships = [
            EntityRelationship(
                relationship_type=RelationshipType(r["type"]),
                source_id=r["source"],
                target_id=r["target"],
                properties=r.get("properties", {})
            )
            for r in data.get("relationships", [])
        ]

        return cls(
            identifier=identifier,
            name=data["name"],
            description=data.get("description", ""),
            status=EntityStatus(data.get("status", "unknown")),
            properties=data.get("properties", {}),
            capabilities=capabilities,
            relationships=relationships,
            metadata=data.get("metadata", {})
        )


# =============================================================================
# Factory Functions
# =============================================================================

def create_machine_entity(
    entity_id: str,
    name: str,
    capabilities: List[str] = None,
    **properties
) -> ManufacturingEntity:
    """
    Create a machine entity with common defaults.

    Args:
        entity_id: Unique identifier for the machine
        name: Human-readable name
        capabilities: List of capability type names (e.g., ["milling", "drilling"])
        **properties: Additional properties

    Returns:
        Configured ManufacturingEntity
    """
    caps = []
    for cap_name in (capabilities or []):
        try:
            cap_type = CapabilityType(cap_name.lower())
            caps.append(Capability(capability_type=cap_type))
        except ValueError:
            pass  # Unknown capability type, skip

    return ManufacturingEntity(
        identifier=EntityIdentifier(
            entity_id=entity_id,
            entity_type=EntityType.MACHINE
        ),
        name=name,
        capabilities=caps,
        properties=properties
    )


def create_robot_entity(
    entity_id: str,
    name: str,
    robot_type: str = "6-axis",
    payload_kg: float = 5.0,
    reach_mm: float = 700.0,
    **properties
) -> ManufacturingEntity:
    """
    Create a robot entity with standard properties.

    Args:
        entity_id: Unique identifier
        name: Human-readable name
        robot_type: Robot configuration (6-axis, SCARA, delta, etc.)
        payload_kg: Maximum payload in kg
        reach_mm: Maximum reach in mm
        **properties: Additional properties

    Returns:
        Configured ManufacturingEntity
    """
    return ManufacturingEntity(
        identifier=EntityIdentifier(
            entity_id=entity_id,
            entity_type=EntityType.ROBOT
        ),
        name=name,
        capabilities=[
            Capability(
                capability_type=CapabilityType.PICK_PLACE,
                parameters={"payload_kg": payload_kg, "reach_mm": reach_mm}
            )
        ],
        properties={
            "robot_type": robot_type,
            "payload_kg": payload_kg,
            "reach_mm": reach_mm,
            **properties
        }
    )


def create_sensor_entity(
    entity_id: str,
    name: str,
    sensor_type: str,
    unit: str,
    **properties
) -> ManufacturingEntity:
    """
    Create a sensor entity.

    Args:
        entity_id: Unique identifier
        name: Human-readable name
        sensor_type: Type of sensor (temperature, pressure, vibration, etc.)
        unit: Engineering unit for readings
        **properties: Additional properties

    Returns:
        Configured ManufacturingEntity
    """
    return ManufacturingEntity(
        identifier=EntityIdentifier(
            entity_id=entity_id,
            entity_type=EntityType.SENSOR
        ),
        name=name,
        properties={
            "sensor_type": sensor_type,
            "unit": unit,
            **properties
        }
    )


def get_entity_namespace(entity: ManufacturingEntity) -> str:
    """Get the full namespace URI for an entity."""
    return entity.uri


# =============================================================================
# Ontology Registry
# =============================================================================

class ManufacturingOntology:
    """
    Central registry for manufacturing entity definitions and relationships.

    This class maintains the semantic model of the factory, enabling:
    - Entity discovery by type
    - Relationship traversal
    - Capability matching
    - Hierarchy navigation

    Example:
        ontology = ManufacturingOntology()

        # Register entities
        ontology.register(machine_entity)
        ontology.register(robot_entity)

        # Define relationships
        ontology.add_relationship(
            machine_entity.uri,
            RelationshipType.OPERATED_BY,
            operator_entity.uri
        )

        # Query capabilities
        machines = ontology.find_by_capability(CapabilityType.MILLING)
    """

    def __init__(self):
        """Initialize empty ontology."""
        self._entities: Dict[str, ManufacturingEntity] = {}
        self._by_type: Dict[EntityType, Set[str]] = {}

    def register(self, entity: ManufacturingEntity) -> None:
        """
        Register an entity in the ontology.

        Args:
            entity: Entity to register
        """
        uri = entity.uri
        self._entities[uri] = entity

        # Index by type
        if entity.entity_type not in self._by_type:
            self._by_type[entity.entity_type] = set()
        self._by_type[entity.entity_type].add(uri)

    def unregister(self, uri: str) -> None:
        """
        Remove an entity from the ontology.

        Args:
            uri: URI of entity to remove
        """
        if uri in self._entities:
            entity = self._entities[uri]
            self._by_type[entity.entity_type].discard(uri)
            del self._entities[uri]

    def get(self, uri: str) -> Optional[ManufacturingEntity]:
        """
        Get an entity by URI.

        Args:
            uri: Entity URI

        Returns:
            Entity if found, None otherwise
        """
        return self._entities.get(uri)

    def get_by_id(
        self,
        entity_id: str,
        entity_type: Optional[EntityType] = None
    ) -> Optional[ManufacturingEntity]:
        """
        Get an entity by ID (with optional type filter).

        Args:
            entity_id: Entity ID to find
            entity_type: Optional type to narrow search

        Returns:
            Entity if found, None otherwise
        """
        for entity in self._entities.values():
            if entity.entity_id == entity_id:
                if entity_type is None or entity.entity_type == entity_type:
                    return entity
        return None

    def find_by_type(self, entity_type: EntityType) -> List[ManufacturingEntity]:
        """
        Find all entities of a specific type.

        Args:
            entity_type: Type to filter by

        Returns:
            List of matching entities
        """
        uris = self._by_type.get(entity_type, set())
        return [self._entities[uri] for uri in uris]

    def find_by_capability(
        self,
        capability_type: CapabilityType
    ) -> List[ManufacturingEntity]:
        """
        Find entities that have a specific capability.

        Args:
            capability_type: Capability to search for

        Returns:
            List of entities with the capability
        """
        return [
            entity for entity in self._entities.values()
            if entity.has_capability(capability_type)
        ]

    def find_by_status(self, status: EntityStatus) -> List[ManufacturingEntity]:
        """
        Find entities with a specific status.

        Args:
            status: Status to filter by

        Returns:
            List of matching entities
        """
        return [
            entity for entity in self._entities.values()
            if entity.status == status
        ]

    def add_relationship(
        self,
        source_uri: str,
        rel_type: RelationshipType,
        target_uri: str,
        **properties
    ) -> bool:
        """
        Add a relationship between entities.

        Args:
            source_uri: Source entity URI
            rel_type: Relationship type
            target_uri: Target entity URI
            **properties: Additional relationship properties

        Returns:
            True if relationship added, False if source not found
        """
        source = self._entities.get(source_uri)
        if not source:
            return False

        source.add_relationship(rel_type, target_uri, **properties)
        return True

    def get_related(
        self,
        uri: str,
        rel_type: RelationshipType
    ) -> List[ManufacturingEntity]:
        """
        Get entities related to a given entity.

        Args:
            uri: Source entity URI
            rel_type: Relationship type to follow

        Returns:
            List of related entities
        """
        entity = self._entities.get(uri)
        if not entity:
            return []

        target_uris = entity.get_related(rel_type)
        return [
            self._entities[t_uri] for t_uri in target_uris
            if t_uri in self._entities
        ]

    def get_children(self, uri: str) -> List[ManufacturingEntity]:
        """Get entities contained by the given entity."""
        return self.get_related(uri, RelationshipType.CONTAINS)

    def get_parent(self, uri: str) -> Optional[ManufacturingEntity]:
        """Get the entity that contains the given entity."""
        parents = self.get_related(uri, RelationshipType.PART_OF)
        return parents[0] if parents else None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the ontology to a dictionary."""
        return {
            "entities": [e.to_dict() for e in self._entities.values()],
            "entity_count": len(self._entities),
            "types": {t.value: len(uris) for t, uris in self._by_type.items()}
        }

    def __len__(self) -> int:
        """Return number of registered entities."""
        return len(self._entities)

    def __iter__(self):
        """Iterate over all entities."""
        return iter(self._entities.values())


# =============================================================================
# Global Ontology Instance
# =============================================================================

_ontology: Optional[ManufacturingOntology] = None


def get_manufacturing_ontology() -> ManufacturingOntology:
    """
    Get the global manufacturing ontology instance.

    Returns:
        Singleton ManufacturingOntology instance
    """
    global _ontology
    if _ontology is None:
        _ontology = ManufacturingOntology()
    return _ontology


def reset_manufacturing_ontology() -> None:
    """Reset the global ontology (for testing)."""
    global _ontology
    _ontology = None
