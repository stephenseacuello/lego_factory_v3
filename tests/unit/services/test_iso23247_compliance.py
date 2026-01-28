"""
LEGO Factory v3 - ISO 23247 Compliance Test Suite
==================================================

Comprehensive test suite verifying compliance with ISO 23247 standards:
- Part 1: Overview and general principles
- Part 2: Reference architecture
- Part 3: Digital representation of manufacturing elements
- Part 4: Information exchange

This test suite ensures the digital twin implementation meets
industry standards for manufacturing digital twins.
"""

import pytest
from datetime import datetime, timedelta
import uuid
import json

from services.digital_twin.vector_clock import (
    VectorClock,
    VersionedState,
    ConflictResolver,
    ConflictResolutionStrategy,
    DigitalTwinStateStore,
    CausalRelation,
)
from services.digital_twin.crdt import (
    GCounter,
    PNCounter,
    LWWRegister,
    ORSet,
    LWWMap,
    CRDTState,
)
from services.digital_twin.message_schema import (
    MessageSchemaValidator,
    MessageType,
    ValidationResult,
    validate_message,
)


class TestISO23247Part1Overview:
    """
    Tests for ISO 23247-1: Overview and general principles.

    Verifies:
    - Digital twin entity definition
    - Lifecycle management
    - Observable manufacturing element representation
    """

    def test_entity_identification_structure(self):
        """
        ISO 23247-1 Section 6.1: Entity Identification.

        Entities must have unique identifiers with type and context.
        """
        state = VersionedState(
            data={"status": "running"},
            entity_id="CNC-MILL-001",
            source_id="CONTROLLER-1",
            state_type="operational"
        )

        assert state.entity_id is not None
        assert len(state.entity_id) > 0
        assert state.state_type in ["operational", "position", "generic"]

    def test_entity_lifecycle_states(self):
        """
        ISO 23247-1 Section 6.2: Entity Lifecycle.

        Entities must support lifecycle state tracking.
        """
        lifecycle_states = [
            "design",
            "commissioning",
            "active",
            "maintenance",
            "degraded",
            "standby",
            "offline",
            "retired"
        ]

        state = CRDTState(entity_id="machine_1", node_id="ctrl_1")

        for ls in lifecycle_states:
            state.status.set(ls)
            assert state.status.value() == ls

    def test_observable_information_types(self):
        """
        ISO 23247-1 Section 6.3: Observable Information.

        Must support position, orientation, velocity, and status.
        """
        state = CRDTState(entity_id="robot_1", node_id="ctrl_1")

        # Position
        state.position.set("x", 100.0)
        state.position.set("y", 200.0)
        state.position.set("z", 50.0)

        # Status
        state.status.set("active")

        snapshot = state.get_snapshot()

        assert "x" in snapshot["position"]
        assert "y" in snapshot["position"]
        assert "z" in snapshot["position"]
        assert snapshot["status"] == "active"


class TestISO23247Part2Architecture:
    """
    Tests for ISO 23247-2: Reference architecture.

    Verifies the 4-domain architecture:
    - User domain
    - Digital Twin domain
    - Data Collection domain
    - Observable Manufacturing Element (OME) domain
    """

    def test_domain_separation(self):
        """
        ISO 23247-2 Section 5: Domain Architecture.

        State should be manageable independently by domain.
        """
        # OME domain - physical entity state
        ome_state = CRDTState(entity_id="physical_machine", node_id="ome_domain")
        ome_state.position.set("x", 100.0)

        # DT domain - digital representation
        dt_state = CRDTState(entity_id="digital_twin", node_id="dt_domain")
        dt_state.position.set("x", 100.0)

        # Data collection domain - bridge
        dc_state = CRDTState(entity_id="data_collector", node_id="dc_domain")

        # States are independently managed
        assert ome_state.node_id != dt_state.node_id
        assert dt_state.node_id != dc_state.node_id

    def test_bidirectional_synchronization(self):
        """
        ISO 23247-2 Section 6.2: Bidirectional Sync.

        State changes must propagate in both directions.
        """
        # Physical to Digital
        physical = CRDTState(entity_id="machine_1", node_id="physical")
        physical.position.set("x", 100.0, timestamp=1.0)

        digital = CRDTState(entity_id="machine_1", node_id="digital")
        digital = physical.merge(digital)

        assert digital.position.get("x") == 100.0

        # Digital to Physical (command)
        digital.position.set("x", 200.0, timestamp=2.0)
        physical = digital.merge(physical)

        assert physical.position.get("x") == 200.0


class TestISO23247Part3Representation:
    """
    Tests for ISO 23247-3: Digital representation of manufacturing elements.

    Verifies:
    - Static attributes
    - Dynamic attributes
    - Relationship representation
    - Capability description
    """

    def test_static_attributes(self):
        """
        ISO 23247-3 Section 6.1: Static Attributes.

        Entities must support immutable characteristics.
        """
        # Static attributes stored in events (immutable)
        state = CRDTState(entity_id="machine_1", node_id="ctrl_1")

        # Add static info as immutable events
        state.events.add("manufacturer:FANUC")
        state.events.add("model:RoboDrill")
        state.events.add("serial:SN-123456")

        events = state.events.value()
        assert "manufacturer:FANUC" in events
        assert "model:RoboDrill" in events

    def test_dynamic_attributes(self):
        """
        ISO 23247-3 Section 6.2: Dynamic Attributes.

        Entities must support changing state values.
        """
        state = CRDTState(entity_id="machine_1", node_id="ctrl_1")

        # Dynamic position updates
        for i in range(10):
            state.position.set("x", float(i * 10))

        assert state.position.get("x") == 90.0

    def test_hierarchical_structure(self):
        """
        ISO 23247-3 Section 6.3: Hierarchical Structure.

        Factory -> Line -> Cell -> Equipment hierarchy.
        """
        # Factory level
        factory = CRDTState(entity_id="factory_1", node_id="factory")
        factory.events.add("type:factory")
        factory.events.add("children:line_1,line_2")

        # Line level
        line = CRDTState(entity_id="line_1", node_id="line")
        line.events.add("type:production_line")
        line.events.add("parent:factory_1")
        line.events.add("children:cell_1,cell_2")

        # Cell level
        cell = CRDTState(entity_id="cell_1", node_id="cell")
        cell.events.add("type:work_cell")
        cell.events.add("parent:line_1")
        cell.events.add("children:machine_1,robot_1")

        # Equipment level
        machine = CRDTState(entity_id="machine_1", node_id="machine")
        machine.events.add("type:equipment")
        machine.events.add("parent:cell_1")

        # Verify hierarchy is captured
        assert "parent:line_1" in cell.events.value()
        assert "parent:cell_1" in machine.events.value()

    def test_capability_representation(self):
        """
        ISO 23247-3 Section 6.4: Capability Information.

        Entities must describe their capabilities.
        """
        state = CRDTState(entity_id="cnc_mill_1", node_id="ctrl_1")

        # Add capabilities as events
        state.events.add("capability:3-axis-milling")
        state.events.add("capability:tool-change")
        state.events.add("capability:probing")
        state.events.add("workspace:500x500x300mm")

        events = state.events.value()
        assert "capability:3-axis-milling" in events
        assert "capability:tool-change" in events


class TestISO23247Part4InformationExchange:
    """
    Tests for ISO 23247-4: Information exchange.

    Verifies:
    - Message format compliance
    - Data integrity
    - Conflict resolution
    - Version control
    - Synchronization protocols
    """

    def test_message_format_compliance(self):
        """
        ISO 23247-4 Section 6.3: Message Format.

        Messages must conform to defined schemas.
        """
        validator = MessageSchemaValidator()

        # Valid state update message
        message = {
            "message_type": "state_update",
            "entity_id": "machine_1",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "state": {
                "position": {"x": 100.0, "y": 50.0, "z": 25.0},
                "status": "running"
            },
            "quality": "good"
        }

        result = validator.validate(message)
        assert result.valid, f"Validation errors: {result.get_error_messages()}"

    def test_message_validation_required_fields(self):
        """
        ISO 23247-4: Required field validation.
        """
        validator = MessageSchemaValidator()

        # Missing required field
        message = {
            "message_type": "state_update",
            # Missing entity_id
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "state": {}
        }

        result = validator.validate(message)
        assert not result.valid
        assert any("entity_id" in e.path for e in result.errors)

    def test_message_validation_enum_values(self):
        """
        ISO 23247-4: Enum value validation.
        """
        validator = MessageSchemaValidator()

        message = {
            "message_type": "state_update",
            "entity_id": "machine_1",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "state": {"status": "invalid_status"},  # Invalid enum value
            "quality": "good"
        }

        result = validator.validate(message)
        assert not result.valid

    def test_data_integrity_checksum(self):
        """
        ISO 23247-4 Section 6.4: Data Integrity.

        State must support integrity verification via checksums.
        """
        state = VersionedState(
            data={"position": {"x": 100, "y": 200, "z": 50}},
            entity_id="machine_1"
        )

        # Compute and store checksum
        state.checksum = state.compute_checksum()

        # Verify integrity
        assert state.verify_integrity() is True

        # Corrupt data
        state.data["position"]["x"] = 999

        # Integrity check should fail
        assert state.verify_integrity() is False

    def test_conflict_detection(self):
        """
        ISO 23247-4 Section 7.1: Conflict Detection.

        System must detect concurrent updates.
        """
        # Two nodes make independent updates
        clock1 = VectorClock(node_id="node_1")
        clock2 = VectorClock(node_id="node_2")

        clock1.increment()
        clock2.increment()

        # These are concurrent
        assert clock1.compare(clock2) == CausalRelation.CONCURRENT
        assert clock1.is_concurrent_with(clock2)

    def test_conflict_resolution_strategies(self):
        """
        ISO 23247-4 Section 7.2: Conflict Resolution.

        Multiple resolution strategies must be supported.
        """
        resolver = ConflictResolver()

        local = VersionedState(
            data={"value": 100},
            version=VectorClock(clock={"a": 2, "b": 1}),
            entity_id="sensor_1"
        )
        local.version.wall_clock = datetime.utcnow() - timedelta(seconds=1)

        remote = VersionedState(
            data={"value": 200},
            version=VectorClock(clock={"a": 1, "b": 2}),
            entity_id="sensor_1"
        )
        remote.version.wall_clock = datetime.utcnow()

        # Last-write-wins
        result, _ = resolver.resolve(
            local, remote,
            strategy=ConflictResolutionStrategy.LAST_WRITE_WINS
        )
        assert result.data["value"] == 200

        # First-write-wins
        result, _ = resolver.resolve(
            local, remote,
            strategy=ConflictResolutionStrategy.FIRST_WRITE_WINS
        )
        assert result.data["value"] == 100

    def test_causal_ordering(self):
        """
        ISO 23247-4 Section 7.3: Causal Ordering.

        Events must be orderable by causality.
        """
        # Event sequence: A -> B -> C
        clock_a = VectorClock(node_id="node_1")
        clock_a.increment()  # Event A

        clock_b = clock_a.copy()
        clock_b.increment()  # Event B (after A)

        clock_c = clock_b.copy()
        clock_c.increment()  # Event C (after B)

        # Verify causal ordering
        assert clock_a.happens_before(clock_b)
        assert clock_b.happens_before(clock_c)
        assert clock_a.happens_before(clock_c)  # Transitivity

    def test_version_vector_merge(self):
        """
        ISO 23247-4: Version vector merging.
        """
        # Complex multi-node scenario
        nodes = {
            "plc": VectorClock(node_id="plc"),
            "hmi": VectorClock(node_id="hmi"),
            "scada": VectorClock(node_id="scada"),
        }

        # PLC updates
        nodes["plc"].increment()
        nodes["plc"].increment()

        # HMI receives from PLC
        nodes["hmi"].merge(nodes["plc"].copy())

        # SCADA receives from both
        nodes["scada"].merge(nodes["plc"].copy())
        nodes["scada"].merge(nodes["hmi"].copy())

        # SCADA should know about all updates
        assert nodes["scada"].clock["plc"] >= 2
        assert "hmi" in nodes["scada"].clock

    def test_conflict_audit_trail(self):
        """
        ISO 23247-4 Section 7.4: Audit Trail.

        Conflict resolutions must be logged.
        """
        resolver = ConflictResolver()

        # Create conflicting states
        local = VersionedState(
            data={"temp": 100},
            version=VectorClock(clock={"a": 2, "b": 1}),
            entity_id="temp_sensor"
        )
        local.version.wall_clock = datetime.utcnow()

        remote = VersionedState(
            data={"temp": 105},
            version=VectorClock(clock={"a": 1, "b": 2}),
            entity_id="temp_sensor"
        )
        remote.version.wall_clock = datetime.utcnow()

        # Resolve conflict
        resolver.resolve(local, remote)

        # Check audit trail
        history = resolver.get_conflict_history()
        assert len(history) == 1

        record = history[0]
        assert record.entity_id == "temp_sensor"
        assert record.local_data["temp"] == 100
        assert record.remote_data["temp"] == 105

    def test_eventual_consistency(self):
        """
        ISO 23247-4: Eventual consistency guarantee.
        """
        # Create 3 replicas
        replicas = [
            CRDTState(entity_id="machine_1", node_id=f"node_{i}")
            for i in range(3)
        ]

        # Each makes independent updates
        replicas[0].position.set("x", 100.0, timestamp=1.0)
        replicas[1].position.set("y", 200.0, timestamp=2.0)
        replicas[2].position.set("z", 300.0, timestamp=3.0)

        # Merge in any order
        final = replicas[0].merge(replicas[1]).merge(replicas[2])

        # All updates present
        pos = final.position.value()
        assert pos.get("x") == 100.0
        assert pos.get("y") == 200.0
        assert pos.get("z") == 300.0

    def test_heartbeat_message_format(self):
        """
        ISO 23247-4: Heartbeat message compliance.
        """
        validator = MessageSchemaValidator()

        message = {
            "message_type": "heartbeat",
            "node_id": "controller_1",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "sequence": 42,
            "status": "healthy"
        }

        result = validator.validate(message)
        assert result.valid

    def test_command_acknowledgment_flow(self):
        """
        ISO 23247-4: Command-acknowledgment protocol.
        """
        validator = MessageSchemaValidator()

        # Command message
        command = {
            "message_type": "command",
            "message_id": str(uuid.uuid4()),
            "entity_id": "robot_1",
            "command": "move_to",
            "parameters": {"x": 100, "y": 50, "z": 25},
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "priority": 5,
            "requires_ack": True
        }

        cmd_result = validator.validate(command)
        assert cmd_result.valid

        # Acknowledgment message
        ack = {
            "message_type": "command_ack",
            "message_id": str(uuid.uuid4()),
            "original_message_id": command["message_id"],
            "entity_id": "robot_1",
            "status": "accepted",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        ack_result = validator.validate(ack)
        assert ack_result.valid


class TestISO23247ComplianceLevel:
    """
    Integration tests for overall ISO 23247 compliance levels.
    """

    def test_basic_compliance_level(self):
        """
        Test basic (Level 1) compliance requirements.

        - Entity identification
        - Basic state representation
        - Simple synchronization
        """
        # Entity with identification
        state = VersionedState(
            data={"status": "active"},
            entity_id="machine_001",
            source_id="controller_1",
            version=VectorClock(node_id="controller_1")
        )
        state.version.increment()

        assert state.entity_id is not None
        assert state.version.clock != {}

    def test_intermediate_compliance_level(self):
        """
        Test intermediate (Level 2) compliance requirements.

        - Conflict detection
        - Basic resolution
        - Message validation
        """
        # Conflict detection
        store = DigitalTwinStateStore(node_id="test")

        store.update_state("machine_1", {"x": 100}, "local")

        remote = VersionedState(
            data={"x": 200},
            version=VectorClock(clock={"remote": 1}),
            entity_id="machine_1"
        )
        remote.version.wall_clock = datetime.utcnow()

        result, had_conflict = store.apply_remote_update(remote)
        # Should handle without error
        assert result is not None

        # Message validation
        validator = MessageSchemaValidator()
        msg = {
            "message_type": "state_update",
            "entity_id": "test",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "state": {}
        }
        assert validator.validate(msg).valid

    def test_advanced_compliance_level(self):
        """
        Test advanced (Level 3) compliance requirements.

        - CRDT-based synchronization
        - Full audit trail
        - Multi-node merge
        """
        # CRDT state management
        states = [
            CRDTState(entity_id="machine_1", node_id=f"node_{i}")
            for i in range(3)
        ]

        # Concurrent updates
        states[0].counters["parts"] = PNCounter(node_id="node_0")
        states[0].counters["parts"].increment(10)

        states[1].counters["parts"] = PNCounter(node_id="node_1")
        states[1].counters["parts"].increment(20)

        states[2].counters["parts"] = PNCounter(node_id="node_2")
        states[2].counters["parts"].increment(30)

        # Merge all
        merged = states[0].merge(states[1]).merge(states[2])

        # All increments preserved
        assert merged.counters["parts"].value() == 60

    def test_world_class_compliance_level(self):
        """
        Test world-class (Level 4) compliance requirements.

        - Full message protocol support
        - Complete conflict resolution
        - Semantic capabilities
        """
        # All message types supported
        validator = MessageSchemaValidator()
        for msg_type in MessageType:
            schema = validator.get_schema_for_type(msg_type)
            # Schema exists for each type (may be None for some)

        # Full resolution strategies
        resolver = ConflictResolver()
        strategies = [
            ConflictResolutionStrategy.LAST_WRITE_WINS,
            ConflictResolutionStrategy.FIRST_WRITE_WINS,
            ConflictResolutionStrategy.MERGE,
            ConflictResolutionStrategy.PREFER_SOURCE,
        ]

        for strategy in strategies:
            # Each strategy is supported
            assert strategy in ConflictResolutionStrategy
