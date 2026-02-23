"""
Digital Twin Ontology (ISO 23247)

Semantic representation of digital twin entities
following ISO 23247 Digital Twin Framework.

Components:
- Observable Manufacturing Element (OME)
- Digital Twin Entity
- Data Collection & Device Control
- Core User Entity

Reference: ISO 23247-1:2021, ISO 23247-2:2021

Author: LEGO MCP Digital Twin Engineering
"""

import logging
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union
from datetime import datetime, timezone
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# ISO 23247 Core Concepts
# =============================================================================

class EntityType(Enum):
    """ISO 23247 entity types."""
    OBSERVABLE_MANUFACTURING_ELEMENT = "OME"
    DIGITAL_TWIN_ENTITY = "DTE"
    USER_ENTITY = "UE"
    DATA_COLLECTION_ENTITY = "DCE"
    DEVICE_CONTROL_ENTITY = "DevCE"


class ManufacturingElementType(Enum):
    """Types of observable manufacturing elements."""
    EQUIPMENT = "equipment"
    PRODUCT = "product"
    PROCESS = "process"
    MATERIAL = "material"
    PERSONNEL = "personnel"
    FACILITY = "facility"


class RelationType(Enum):
    """Types of relationships between entities."""
    REPRESENTS = "represents"           # DTE represents OME
    MONITORS = "monitors"               # DCE monitors OME
    CONTROLS = "controls"               # DevCE controls OME
    PART_OF = "part_of"                # Hierarchical
    CONNECTED_TO = "connected_to"       # Physical connection
    DEPENDS_ON = "depends_on"           # Dependency
    PRODUCES = "produces"               # Production relationship
    CONSUMES = "consumes"               # Material consumption


class DataQuality(Enum):
    """Data quality levels."""
    RAW = "raw"
    VALIDATED = "validated"
    PROCESSED = "processed"
    CERTIFIED = "certified"


# =============================================================================
# Ontology Classes
# =============================================================================

@dataclass
class Identifier:
    """Unique identifier for ontology entities."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    namespace: str = "lego-mcp"
    uri: str = ""

    def __post_init__(self):
        if not self.uri:
            self.uri = f"urn:{self.namespace}:{self.id}"

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "namespace": self.namespace,
            "uri": self.uri,
        }


@dataclass
class Property:
    """Property of an ontology entity."""
    name: str
    value: Any
    data_type: str = "string"
    unit: Optional[str] = None
    quality: DataQuality = DataQuality.RAW
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "dataType": self.data_type,
            "unit": self.unit,
            "quality": self.quality.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }


@dataclass
class Relationship:
    """Relationship between ontology entities."""
    source_id: str
    target_id: str
    relation_type: RelationType
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sourceId": self.source_id,
            "targetId": self.target_id,
            "relationType": self.relation_type.value,
            "properties": self.properties,
        }


@dataclass
class Capability:
    """Capability of a manufacturing element."""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)


class OntologyEntity(ABC):
    """Base class for ontology entities."""

    def __init__(
        self,
        identifier: Optional[Identifier] = None,
        name: str = "",
        description: str = "",
    ):
        self.identifier = identifier or Identifier()
        self.name = name
        self.description = description
        self.properties: List[Property] = []
        self.relationships: List[Relationship] = []

    @property
    @abstractmethod
    def entity_type(self) -> EntityType:
        """Return entity type."""
        pass

    def add_property(self, prop: Property) -> None:
        """Add property to entity."""
        self.properties.append(prop)

    def get_property(self, name: str) -> Optional[Property]:
        """Get property by name."""
        return next((p for p in self.properties if p.name == name), None)

    def add_relationship(self, rel: Relationship) -> None:
        """Add relationship."""
        self.relationships.append(rel)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "identifier": self.identifier.to_dict(),
            "entityType": self.entity_type.value,
            "name": self.name,
            "description": self.description,
            "properties": [p.to_dict() for p in self.properties],
            "relationships": [r.to_dict() for r in self.relationships],
        }

    def to_rdf_turtle(self) -> str:
        """Convert to RDF Turtle format."""
        lines = [
            f"@prefix lego: <urn:lego-mcp:> .",
            f"@prefix iso23247: <urn:iso:std:iso:23247:> .",
            f"@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "",
            f"<{self.identifier.uri}>",
            f"    a iso23247:{self.entity_type.value} ;",
            f'    lego:name "{self.name}" ;',
            f'    lego:description "{self.description}" ;',
        ]

        for prop in self.properties:
            lines.append(
                f'    lego:{prop.name} "{prop.value}"^^xsd:{prop.data_type} ;'
            )

        lines[-1] = lines[-1].rstrip(" ;") + " ."

        return "\n".join(lines)


# =============================================================================
# ISO 23247 Entities
# =============================================================================

class ObservableManufacturingElement(OntologyEntity):
    """
    Observable Manufacturing Element (OME).

    Physical or logical element in manufacturing that
    can be observed and controlled.
    """

    def __init__(
        self,
        element_type: ManufacturingElementType,
        identifier: Optional[Identifier] = None,
        name: str = "",
        description: str = "",
    ):
        super().__init__(identifier, name, description)
        self.element_type = element_type
        self.capabilities: List[Capability] = []
        self.state: Dict[str, Any] = {}

    @property
    def entity_type(self) -> EntityType:
        return EntityType.OBSERVABLE_MANUFACTURING_ELEMENT

    def add_capability(self, capability: Capability) -> None:
        """Add capability to element."""
        self.capabilities.append(capability)

    def update_state(self, key: str, value: Any) -> None:
        """Update element state."""
        self.state[key] = value

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "elementType": self.element_type.value,
            "capabilities": [
                {"name": c.name, "description": c.description}
                for c in self.capabilities
            ],
            "state": self.state,
        })
        return base


class DigitalTwinEntity(OntologyEntity):
    """
    Digital Twin Entity (DTE).

    Virtual representation of an Observable Manufacturing Element.
    """

    def __init__(
        self,
        ome: ObservableManufacturingElement,
        identifier: Optional[Identifier] = None,
        name: str = "",
        description: str = "",
    ):
        super().__init__(
            identifier,
            name or f"DT_{ome.name}",
            description or f"Digital twin of {ome.name}",
        )
        self.ome = ome
        self.models: List[Dict[str, Any]] = []
        self.simulations: List[Dict[str, Any]] = []
        self.synchronization_interval_ms: int = 1000

        # Add represents relationship
        self.add_relationship(Relationship(
            source_id=self.identifier.id,
            target_id=ome.identifier.id,
            relation_type=RelationType.REPRESENTS,
        ))

    @property
    def entity_type(self) -> EntityType:
        return EntityType.DIGITAL_TWIN_ENTITY

    def add_model(
        self,
        name: str,
        model_type: str,
        parameters: Dict[str, Any],
    ) -> None:
        """Add predictive model to twin."""
        self.models.append({
            "name": name,
            "type": model_type,
            "parameters": parameters,
            "created": datetime.now(timezone.utc).isoformat(),
        })

    def add_simulation(
        self,
        name: str,
        sim_type: str,
        configuration: Dict[str, Any],
    ) -> None:
        """Add simulation capability."""
        self.simulations.append({
            "name": name,
            "type": sim_type,
            "configuration": configuration,
        })

    def synchronize(self) -> Dict[str, Any]:
        """Synchronize twin state with OME."""
        # Copy state from OME
        for prop in self.ome.properties:
            twin_prop = self.get_property(prop.name)
            if twin_prop:
                twin_prop.value = prop.value
                twin_prop.timestamp = datetime.now(timezone.utc)
            else:
                self.add_property(Property(
                    name=prop.name,
                    value=prop.value,
                    data_type=prop.data_type,
                    unit=prop.unit,
                    quality=DataQuality.VALIDATED,
                ))

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "properties_synced": len(self.properties),
        }

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "omeId": self.ome.identifier.id,
            "models": self.models,
            "simulations": self.simulations,
            "syncIntervalMs": self.synchronization_interval_ms,
        })
        return base


class DataCollectionEntity(OntologyEntity):
    """
    Data Collection Entity (DCE).

    Collects data from Observable Manufacturing Elements.
    """

    def __init__(
        self,
        identifier: Optional[Identifier] = None,
        name: str = "",
        description: str = "",
    ):
        super().__init__(identifier, name, description)
        self.monitored_elements: List[str] = []
        self.collection_config: Dict[str, Any] = {}
        self.data_buffer: List[Dict[str, Any]] = []

    @property
    def entity_type(self) -> EntityType:
        return EntityType.DATA_COLLECTION_ENTITY

    def monitor(self, ome: ObservableManufacturingElement) -> None:
        """Add OME to monitoring."""
        self.monitored_elements.append(ome.identifier.id)
        self.add_relationship(Relationship(
            source_id=self.identifier.id,
            target_id=ome.identifier.id,
            relation_type=RelationType.MONITORS,
        ))

    def collect(self, ome: ObservableManufacturingElement) -> Dict[str, Any]:
        """Collect data from OME."""
        data = {
            "elementId": ome.identifier.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "properties": {p.name: p.value for p in ome.properties},
            "state": ome.state,
        }
        self.data_buffer.append(data)
        return data


class DeviceControlEntity(OntologyEntity):
    """
    Device Control Entity (DevCE).

    Controls Observable Manufacturing Elements.
    """

    def __init__(
        self,
        identifier: Optional[Identifier] = None,
        name: str = "",
        description: str = "",
    ):
        super().__init__(identifier, name, description)
        self.controlled_elements: List[str] = []
        self.control_commands: List[Dict[str, Any]] = []

    @property
    def entity_type(self) -> EntityType:
        return EntityType.DEVICE_CONTROL_ENTITY

    def control(self, ome: ObservableManufacturingElement) -> None:
        """Add OME to control."""
        self.controlled_elements.append(ome.identifier.id)
        self.add_relationship(Relationship(
            source_id=self.identifier.id,
            target_id=ome.identifier.id,
            relation_type=RelationType.CONTROLS,
        ))

    def send_command(
        self,
        ome: ObservableManufacturingElement,
        command: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send control command to OME."""
        cmd = {
            "elementId": ome.identifier.id,
            "command": command,
            "parameters": parameters,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "sent",
        }
        self.control_commands.append(cmd)
        return cmd


# =============================================================================
# Ontology Manager
# =============================================================================

class TwinOntologyManager:
    """
    Digital Twin Ontology Manager.

    Manages the complete ontology for LEGO MCP digital twins
    following ISO 23247.

    Usage:
        manager = TwinOntologyManager()

        # Create manufacturing element
        mold = manager.create_ome(
            element_type=ManufacturingElementType.EQUIPMENT,
            name="InjectionMold_001",
        )

        # Create digital twin
        twin = manager.create_twin(mold)

        # Add properties
        manager.add_property(mold, "temperature", 185.0, "float", "celsius")

        # Synchronize
        twin.synchronize()

        # Export to JSON-LD
        jsonld = manager.export_jsonld()
    """

    def __init__(self, namespace: str = "lego-mcp"):
        self.namespace = namespace
        self.entities: Dict[str, OntologyEntity] = {}
        self.relationships: List[Relationship] = []

        logger.info(f"TwinOntologyManager initialized (namespace={namespace})")

    def create_ome(
        self,
        element_type: ManufacturingElementType,
        name: str,
        description: str = "",
    ) -> ObservableManufacturingElement:
        """Create Observable Manufacturing Element."""
        ome = ObservableManufacturingElement(
            element_type=element_type,
            identifier=Identifier(namespace=self.namespace),
            name=name,
            description=description,
        )
        self.entities[ome.identifier.id] = ome
        return ome

    def create_twin(
        self,
        ome: ObservableManufacturingElement,
    ) -> DigitalTwinEntity:
        """Create Digital Twin for OME."""
        twin = DigitalTwinEntity(
            ome=ome,
            identifier=Identifier(namespace=self.namespace),
        )
        self.entities[twin.identifier.id] = twin
        self.relationships.extend(twin.relationships)
        return twin

    def create_data_collector(self, name: str) -> DataCollectionEntity:
        """Create Data Collection Entity."""
        dce = DataCollectionEntity(
            identifier=Identifier(namespace=self.namespace),
            name=name,
        )
        self.entities[dce.identifier.id] = dce
        return dce

    def create_device_controller(self, name: str) -> DeviceControlEntity:
        """Create Device Control Entity."""
        devce = DeviceControlEntity(
            identifier=Identifier(namespace=self.namespace),
            name=name,
        )
        self.entities[devce.identifier.id] = devce
        return devce

    def add_property(
        self,
        entity: OntologyEntity,
        name: str,
        value: Any,
        data_type: str = "string",
        unit: Optional[str] = None,
    ) -> Property:
        """Add property to entity."""
        prop = Property(
            name=name,
            value=value,
            data_type=data_type,
            unit=unit,
        )
        entity.add_property(prop)
        return prop

    def add_relationship(
        self,
        source: OntologyEntity,
        target: OntologyEntity,
        relation_type: RelationType,
    ) -> Relationship:
        """Add relationship between entities."""
        rel = Relationship(
            source_id=source.identifier.id,
            target_id=target.identifier.id,
            relation_type=relation_type,
        )
        source.add_relationship(rel)
        self.relationships.append(rel)
        return rel

    def get_entity(self, entity_id: str) -> Optional[OntologyEntity]:
        """Get entity by ID."""
        return self.entities.get(entity_id)

    def get_twins(self) -> List[DigitalTwinEntity]:
        """Get all digital twins."""
        return [
            e for e in self.entities.values()
            if isinstance(e, DigitalTwinEntity)
        ]

    def export_jsonld(self) -> Dict[str, Any]:
        """Export ontology as JSON-LD."""
        return {
            "@context": {
                "@vocab": f"urn:{self.namespace}:",
                "iso23247": "urn:iso:std:iso:23247:",
                "xsd": "http://www.w3.org/2001/XMLSchema#",
                "entities": "@graph",
            },
            "@graph": [e.to_dict() for e in self.entities.values()],
            "relationships": [r.to_dict() for r in self.relationships],
        }

    def export_rdf_turtle(self) -> str:
        """Export ontology as RDF Turtle."""
        lines = [
            f"@prefix lego: <urn:{self.namespace}:> .",
            "@prefix iso23247: <urn:iso:std:iso:23247:> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "",
        ]

        for entity in self.entities.values():
            lines.append(entity.to_rdf_turtle())
            lines.append("")

        return "\n".join(lines)

    def validate(self) -> Dict[str, Any]:
        """Validate ontology consistency."""
        issues = []

        # Check all twins have OME
        for twin in self.get_twins():
            if twin.ome.identifier.id not in self.entities:
                issues.append({
                    "type": "missing_ome",
                    "twin_id": twin.identifier.id,
                    "ome_id": twin.ome.identifier.id,
                })

        # Check relationship targets exist
        for rel in self.relationships:
            if rel.target_id not in self.entities:
                issues.append({
                    "type": "missing_target",
                    "source_id": rel.source_id,
                    "target_id": rel.target_id,
                })

        return {
            "valid": len(issues) == 0,
            "entity_count": len(self.entities),
            "relationship_count": len(self.relationships),
            "issues": issues,
        }


# Factory function
def create_twin_ontology(namespace: str = "lego-mcp") -> TwinOntologyManager:
    """Create configured ontology manager."""
    manager = TwinOntologyManager(namespace)

    # Pre-populate with common LEGO manufacturing elements
    mold_class = manager.create_ome(
        element_type=ManufacturingElementType.EQUIPMENT,
        name="InjectionMoldClass",
        description="Standard LEGO injection mold",
    )
    mold_class.add_capability(Capability(
        name="injection_molding",
        description="Plastic injection molding capability",
        parameters={"max_pressure_bar": 2500, "max_temp_c": 300},
    ))

    return manager


__all__ = [
    "TwinOntologyManager",
    "ObservableManufacturingElement",
    "DigitalTwinEntity",
    "DataCollectionEntity",
    "DeviceControlEntity",
    "EntityType",
    "ManufacturingElementType",
    "RelationType",
    "Property",
    "Relationship",
    "Capability",
    "Identifier",
    "DataQuality",
    "create_twin_ontology",
]
