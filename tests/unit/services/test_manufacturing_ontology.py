"""
Unit tests for Manufacturing Ontology module.

Tests the ISO 23247-3 compliant entity models, relationships,
capabilities, and ontology registry functionality.
"""

import pytest
from datetime import datetime

from services.digital_twin.manufacturing_ontology import (
    EntityType,
    EntityStatus,
    CapabilityType,
    RelationshipType,
    ManufacturingEntity,
    EntityIdentifier,
    Capability,
    EntityRelationship,
    ManufacturingOntology,
    create_machine_entity,
    create_robot_entity,
    create_sensor_entity,
    get_manufacturing_ontology,
    get_entity_namespace,
    reset_manufacturing_ontology,
)


# =============================================================================
# EntityIdentifier Tests
# =============================================================================

class TestEntityIdentifier:
    """Tests for EntityIdentifier class."""

    def test_create_identifier(self):
        """Test basic identifier creation."""
        eid = EntityIdentifier(
            entity_id="cnc_001",
            namespace="urn:lego-factory",
            entity_type=EntityType.MACHINE
        )

        assert eid.entity_id == "cnc_001"
        assert eid.namespace == "urn:lego-factory"
        assert eid.entity_type == EntityType.MACHINE

    def test_uri_generation(self):
        """Test full URI generation."""
        eid = EntityIdentifier(
            entity_id="cnc_001",
            namespace="urn:lego-factory",
            entity_type=EntityType.MACHINE
        )

        assert eid.uri == "urn:lego-factory:machine:cnc_001"

    def test_default_namespace(self):
        """Test default namespace is applied."""
        eid = EntityIdentifier(entity_id="sensor_001")

        assert eid.namespace == "urn:lego-factory"

    def test_alternate_ids(self):
        """Test alternate identifiers."""
        eid = EntityIdentifier(
            entity_id="cnc_001",
            alternate_ids={
                "serial_number": "SN12345",
                "asset_tag": "ASSET-001"
            }
        )

        assert eid.alternate_ids["serial_number"] == "SN12345"
        assert eid.alternate_ids["asset_tag"] == "ASSET-001"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        eid = EntityIdentifier(
            entity_id="cnc_001",
            entity_type=EntityType.MACHINE
        )

        data = eid.to_dict()
        assert data["entity_id"] == "cnc_001"
        assert data["entity_type"] == "machine"
        assert "uri" in data


# =============================================================================
# Capability Tests
# =============================================================================

class TestCapability:
    """Tests for Capability class."""

    def test_create_capability(self):
        """Test basic capability creation."""
        cap = Capability(
            capability_type=CapabilityType.MILLING,
            parameters={"max_spindle_speed": 10000},
            constraints={"max_workpiece_size": {"x": 500, "y": 300}}
        )

        assert cap.capability_type == CapabilityType.MILLING
        assert cap.parameters["max_spindle_speed"] == 10000

    def test_to_dict(self):
        """Test capability serialization."""
        cap = Capability(
            capability_type=CapabilityType.DRILLING,
            quality_level="precision"
        )

        data = cap.to_dict()
        assert data["type"] == "drilling"
        assert data["quality_level"] == "precision"


# =============================================================================
# ManufacturingEntity Tests
# =============================================================================

class TestManufacturingEntity:
    """Tests for ManufacturingEntity class."""

    def test_create_entity(self):
        """Test basic entity creation."""
        entity = ManufacturingEntity(
            identifier=EntityIdentifier(
                entity_id="cnc_001",
                entity_type=EntityType.MACHINE
            ),
            name="Haas VF-2",
            description="3-axis vertical milling center"
        )

        assert entity.entity_id == "cnc_001"
        assert entity.name == "Haas VF-2"
        assert entity.entity_type == EntityType.MACHINE

    def test_default_status(self):
        """Test default status is UNKNOWN."""
        entity = ManufacturingEntity(
            identifier=EntityIdentifier(entity_id="test"),
            name="Test Entity"
        )

        assert entity.status == EntityStatus.UNKNOWN

    def test_metadata_initialization(self):
        """Test metadata is auto-initialized."""
        entity = ManufacturingEntity(
            identifier=EntityIdentifier(entity_id="test"),
            name="Test Entity"
        )

        assert "created_at" in entity.metadata
        assert "version" in entity.metadata

    def test_add_capability(self):
        """Test adding capabilities."""
        entity = ManufacturingEntity(
            identifier=EntityIdentifier(entity_id="cnc_001"),
            name="CNC Machine"
        )

        entity.add_capability(Capability(capability_type=CapabilityType.MILLING))
        entity.add_capability(Capability(capability_type=CapabilityType.DRILLING))

        assert len(entity.capabilities) == 2
        assert entity.has_capability(CapabilityType.MILLING)
        assert entity.has_capability(CapabilityType.DRILLING)
        assert not entity.has_capability(CapabilityType.TURNING)

    def test_add_relationship(self):
        """Test adding relationships."""
        entity = ManufacturingEntity(
            identifier=EntityIdentifier(entity_id="cnc_001"),
            name="CNC Machine"
        )

        entity.add_relationship(
            RelationshipType.LOCATED_IN,
            "urn:lego-factory:area:machine_shop"
        )

        assert len(entity.relationships) == 1
        related = entity.get_related(RelationshipType.LOCATED_IN)
        assert "urn:lego-factory:area:machine_shop" in related

    def test_to_dict_and_from_dict(self):
        """Test round-trip serialization."""
        original = ManufacturingEntity(
            identifier=EntityIdentifier(
                entity_id="cnc_001",
                entity_type=EntityType.MACHINE
            ),
            name="Haas VF-2",
            status=EntityStatus.RUNNING,
            properties={"spindle_speed": 5000}
        )
        original.add_capability(Capability(
            capability_type=CapabilityType.MILLING,
            parameters={"max_rpm": 10000}
        ))

        data = original.to_dict()
        restored = ManufacturingEntity.from_dict(data)

        assert restored.entity_id == original.entity_id
        assert restored.name == original.name
        assert restored.status == original.status
        assert len(restored.capabilities) == 1


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunctions:
    """Tests for entity factory functions."""

    def test_create_machine_entity(self):
        """Test machine entity factory."""
        machine = create_machine_entity(
            entity_id="cnc_001",
            name="Haas VF-2",
            capabilities=["milling", "drilling", "tapping"]
        )

        assert machine.entity_id == "cnc_001"
        assert machine.entity_type == EntityType.MACHINE
        assert machine.has_capability(CapabilityType.MILLING)
        assert machine.has_capability(CapabilityType.DRILLING)
        assert machine.has_capability(CapabilityType.TAPPING)

    def test_create_machine_with_properties(self):
        """Test machine factory with custom properties."""
        machine = create_machine_entity(
            entity_id="cnc_001",
            name="Test CNC",
            max_rpm=12000,
            axis_count=5
        )

        assert machine.properties["max_rpm"] == 12000
        assert machine.properties["axis_count"] == 5

    def test_create_robot_entity(self):
        """Test robot entity factory."""
        robot = create_robot_entity(
            entity_id="robot_001",
            name="xArm 6",
            robot_type="6-axis",
            payload_kg=5.0,
            reach_mm=700.0
        )

        assert robot.entity_id == "robot_001"
        assert robot.entity_type == EntityType.ROBOT
        assert robot.properties["payload_kg"] == 5.0
        assert robot.properties["reach_mm"] == 700.0
        assert robot.has_capability(CapabilityType.PICK_PLACE)

    def test_create_sensor_entity(self):
        """Test sensor entity factory."""
        sensor = create_sensor_entity(
            entity_id="temp_001",
            name="Spindle Temperature Sensor",
            sensor_type="temperature",
            unit="°C"
        )

        assert sensor.entity_id == "temp_001"
        assert sensor.entity_type == EntityType.SENSOR
        assert sensor.properties["sensor_type"] == "temperature"
        assert sensor.properties["unit"] == "°C"

    def test_get_entity_namespace(self):
        """Test namespace URI generation."""
        machine = create_machine_entity("cnc_001", "Test CNC")
        ns = get_entity_namespace(machine)

        assert ns == "urn:lego-factory:machine:cnc_001"


# =============================================================================
# ManufacturingOntology Tests
# =============================================================================

class TestManufacturingOntology:
    """Tests for ManufacturingOntology registry."""

    def setup_method(self):
        """Reset global ontology before each test."""
        reset_manufacturing_ontology()

    def test_register_entity(self):
        """Test entity registration."""
        ontology = ManufacturingOntology()
        machine = create_machine_entity("cnc_001", "Test CNC")

        ontology.register(machine)

        assert len(ontology) == 1
        assert ontology.get(machine.uri) == machine

    def test_unregister_entity(self):
        """Test entity removal."""
        ontology = ManufacturingOntology()
        machine = create_machine_entity("cnc_001", "Test CNC")

        ontology.register(machine)
        ontology.unregister(machine.uri)

        assert len(ontology) == 0
        assert ontology.get(machine.uri) is None

    def test_find_by_type(self):
        """Test finding entities by type."""
        ontology = ManufacturingOntology()
        ontology.register(create_machine_entity("cnc_001", "CNC 1"))
        ontology.register(create_machine_entity("cnc_002", "CNC 2"))
        ontology.register(create_robot_entity("robot_001", "Robot 1"))

        machines = ontology.find_by_type(EntityType.MACHINE)
        robots = ontology.find_by_type(EntityType.ROBOT)

        assert len(machines) == 2
        assert len(robots) == 1

    def test_find_by_capability(self):
        """Test finding entities by capability."""
        ontology = ManufacturingOntology()
        ontology.register(create_machine_entity(
            "cnc_001", "CNC 1", capabilities=["milling", "drilling"]
        ))
        ontology.register(create_machine_entity(
            "cnc_002", "CNC 2", capabilities=["turning"]
        ))

        milling_machines = ontology.find_by_capability(CapabilityType.MILLING)
        turning_machines = ontology.find_by_capability(CapabilityType.TURNING)

        assert len(milling_machines) == 1
        assert len(turning_machines) == 1
        assert milling_machines[0].entity_id == "cnc_001"

    def test_find_by_status(self):
        """Test finding entities by status."""
        ontology = ManufacturingOntology()

        machine1 = create_machine_entity("cnc_001", "CNC 1")
        machine1.status = EntityStatus.RUNNING

        machine2 = create_machine_entity("cnc_002", "CNC 2")
        machine2.status = EntityStatus.IDLE

        ontology.register(machine1)
        ontology.register(machine2)

        running = ontology.find_by_status(EntityStatus.RUNNING)
        idle = ontology.find_by_status(EntityStatus.IDLE)

        assert len(running) == 1
        assert len(idle) == 1

    def test_add_relationship(self):
        """Test adding relationships via ontology."""
        ontology = ManufacturingOntology()
        machine = create_machine_entity("cnc_001", "CNC 1")
        sensor = create_sensor_entity("temp_001", "Temp Sensor", "temperature", "°C")

        ontology.register(machine)
        ontology.register(sensor)

        result = ontology.add_relationship(
            sensor.uri,
            RelationshipType.MONITORS,
            machine.uri
        )

        assert result is True
        related = ontology.get_related(sensor.uri, RelationshipType.MONITORS)
        assert len(related) == 1
        assert related[0].entity_id == "cnc_001"

    def test_get_by_id(self):
        """Test getting entity by ID."""
        ontology = ManufacturingOntology()
        machine = create_machine_entity("cnc_001", "Test CNC")
        ontology.register(machine)

        found = ontology.get_by_id("cnc_001")
        assert found is not None
        assert found.name == "Test CNC"

        not_found = ontology.get_by_id("nonexistent")
        assert not_found is None

    def test_iteration(self):
        """Test iterating over ontology."""
        ontology = ManufacturingOntology()
        ontology.register(create_machine_entity("cnc_001", "CNC 1"))
        ontology.register(create_machine_entity("cnc_002", "CNC 2"))

        entities = list(ontology)
        assert len(entities) == 2

    def test_to_dict(self):
        """Test ontology serialization."""
        ontology = ManufacturingOntology()
        ontology.register(create_machine_entity("cnc_001", "CNC 1"))
        ontology.register(create_robot_entity("robot_001", "Robot 1"))

        data = ontology.to_dict()
        assert data["entity_count"] == 2
        assert len(data["entities"]) == 2
        assert data["types"]["machine"] == 1
        assert data["types"]["robot"] == 1


# =============================================================================
# Global Ontology Tests
# =============================================================================

class TestGlobalOntology:
    """Tests for global ontology singleton."""

    def setup_method(self):
        """Reset global ontology before each test."""
        reset_manufacturing_ontology()

    def test_get_singleton(self):
        """Test singleton retrieval."""
        ontology1 = get_manufacturing_ontology()
        ontology2 = get_manufacturing_ontology()

        assert ontology1 is ontology2

    def test_reset_singleton(self):
        """Test singleton reset."""
        ontology1 = get_manufacturing_ontology()
        ontology1.register(create_machine_entity("cnc_001", "Test"))

        reset_manufacturing_ontology()
        ontology2 = get_manufacturing_ontology()

        assert ontology1 is not ontology2
        assert len(ontology2) == 0


# =============================================================================
# ISO 23247-3 Compliance Tests
# =============================================================================

class TestISO23247Part3Compliance:
    """Tests for ISO 23247-3 compliance requirements."""

    def test_entity_has_unique_identifier(self):
        """ISO 23247-3 5.1: Entities must have unique identifiers."""
        entity = create_machine_entity("cnc_001", "Test CNC")

        assert entity.identifier is not None
        assert entity.identifier.entity_id is not None
        assert len(entity.identifier.uri) > 0

    def test_entity_has_type_classification(self):
        """ISO 23247-3 5.2: Entities must have type classification."""
        machine = create_machine_entity("cnc_001", "Test CNC")
        robot = create_robot_entity("robot_001", "Test Robot")

        assert machine.entity_type == EntityType.MACHINE
        assert robot.entity_type == EntityType.ROBOT

    def test_entity_supports_capabilities(self):
        """ISO 23247-3 7.1: Entities can declare capabilities."""
        machine = create_machine_entity(
            "cnc_001", "Test CNC",
            capabilities=["milling", "drilling"]
        )

        assert len(machine.capabilities) >= 2
        assert any(c.capability_type == CapabilityType.MILLING
                   for c in machine.capabilities)

    def test_entity_supports_relationships(self):
        """ISO 23247-3 8.1: Entities can have relationships."""
        machine = create_machine_entity("cnc_001", "Test CNC")
        machine.add_relationship(
            RelationshipType.LOCATED_IN,
            "urn:lego-factory:area:shop_floor"
        )
        machine.add_relationship(
            RelationshipType.OPERATED_BY,
            "urn:lego-factory:operator:john_doe"
        )

        assert len(machine.relationships) == 2

    def test_namespace_uri_format(self):
        """ISO 23247-3 5.3: Namespace URIs follow standard format."""
        entity = create_machine_entity("cnc_001", "Test CNC")

        # Should start with urn: or http(s)://
        assert entity.identifier.uri.startswith("urn:") or \
               entity.identifier.uri.startswith("http")

    def test_status_values_align_with_standard(self):
        """ISO 23247-3 6.2: Status values align with ISA-88/95."""
        # Check that standard status values exist
        standard_statuses = [
            EntityStatus.IDLE,
            EntityStatus.RUNNING,
            EntityStatus.STOPPED,
            EntityStatus.MAINTENANCE,
            EntityStatus.FAULT
        ]

        for status in standard_statuses:
            assert status in EntityStatus

    def test_hierarchy_relationship_types(self):
        """ISO 23247-3 8.2: Hierarchy relationships supported."""
        # Check composition relationships exist
        assert RelationshipType.CONTAINS in RelationshipType
        assert RelationshipType.PART_OF in RelationshipType

    def test_entity_serializable_for_exchange(self):
        """ISO 23247-3 9.1: Entities must be serializable for exchange."""
        machine = create_machine_entity(
            "cnc_001", "Test CNC",
            capabilities=["milling"]
        )
        machine.status = EntityStatus.RUNNING
        machine.properties["spindle_speed"] = 5000

        # Should serialize without error
        data = machine.to_dict()

        # Should deserialize without error
        restored = ManufacturingEntity.from_dict(data)

        assert restored.entity_id == machine.entity_id
        assert restored.status == machine.status
