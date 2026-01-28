"""
LEGO Factory v3 - Digital Twin Services
=======================================

ISO 23247 compliant digital twin implementation for distributed manufacturing
systems. This module provides the core infrastructure for maintaining consistent
state across multiple nodes in a factory network.

Overview
--------
Digital twins in manufacturing require synchronization of state across multiple
systems: PLCs, SCADA, MES, ERP, and edge devices. This module provides three
complementary approaches to state synchronization:

1. **Vector Clocks** (vector_clock.py)
   Detect conflicts between concurrent updates using logical timestamps.
   When conflict is detected, apply resolution strategies (LWW, merge, etc.)

2. **CRDTs** (crdt.py)
   Conflict-free Replicated Data Types automatically merge without conflicts.
   Mathematically guaranteed eventual consistency without coordination.

3. **Message Validation** (message_schema.py)
   JSON Schema-based validation ensures all messages conform to ISO 23247-4.
   Provides comprehensive error reporting for debugging and compliance.

When to Use Each Approach
-------------------------
- **Vector Clocks**: When you need to detect and handle conflicts explicitly,
  especially for complex state where merge semantics are domain-specific.

- **CRDTs**: When automatic merge is acceptable. Use GCounter/PNCounter for
  counts, LWWRegister for status, ORSet for alarm lists.

- **Both**: Use CRDTs for most state, with vector clocks for critical state
  that requires explicit conflict handling.

ISO 23247 Compliance
--------------------
This module implements requirements from all four parts of ISO 23247:

    Part 1 - Overview and general principles:
        - Entity identification (entity_id, entity_type, namespace)
        - Lifecycle states (active, idle, running, stopped, error, maintenance)

    Part 2 - Reference architecture:
        - Observable Manufacturing Element (OME) representation
        - 4-domain architecture support (User, Digital Twin, Data, Physical)

    Part 3 - Digital representation:
        - State representation with position, orientation, velocity
        - Attribute and capability modeling

    Part 4 - Information exchange:
        - Message types (state_update, command, heartbeat, etc.)
        - Conflict detection and resolution
        - Data integrity with checksums

Quick Start
-----------
Basic state synchronization with vector clocks::

    from services.digital_twin import VectorClock, DigitalTwinStateStore

    # Create a state store for this node
    store = DigitalTwinStateStore(node_id="controller_1")

    # Update local state
    state, _ = store.update_state(
        entity_id="machine_001",
        data={"status": "running", "speed": 1500},
        source_id="plc_1"
    )

    # Receive and apply remote update
    resolved, had_conflict = store.apply_remote_update(remote_state)
    if had_conflict:
        print(f"Conflict detected and resolved: {resolved}")

Automatic merge with CRDTs::

    from services.digital_twin import CRDTState, PNCounter

    # Create CRDT-based state
    state = CRDTState(entity_id="machine_001", node_id="controller_1")

    # Update state (always succeeds, no conflicts possible)
    state.position.set("x", 100.5)
    state.status.set("running")
    state.active_alarms.add("TEMP_WARNING")

    # Merge with remote state (always succeeds)
    merged = state.merge(remote_state)

Message validation::

    from services.digital_twin import MessageSchemaValidator, validate_message

    # Quick validation
    result = validate_message({
        "message_type": "state_update",
        "entity_id": "machine_001",
        "timestamp": "2024-01-15T10:30:00Z",
        "state": {"status": "running"}
    })

    if not result.valid:
        for error in result.errors:
            print(f"{error.path}: {error.message}")

Module Contents
---------------
Vector Clock Components:
    VectorClock - Logical timestamp for causality tracking
    CausalRelation - Enum for happens-before relationships
    ConflictResolutionStrategy - Enum for resolution approaches
    VersionedState - State with vector clock version
    ConflictResolver - Applies resolution strategies
    ConflictRecord - Audit record of resolved conflicts
    DigitalTwinStateStore - Versioned state management

CRDT Components:
    CRDT - Abstract base class for all CRDTs
    GCounter - Grow-only counter
    PNCounter - Positive-negative counter
    LWWRegister - Last-writer-wins single value
    MVRegister - Multi-value register (keeps all concurrent values)
    GSet - Grow-only set
    ORSet - Observed-remove set
    LWWMap - Last-writer-wins key-value map
    CRDTState - Complete CRDT-based entity state

Message Schema Components:
    MessageType - Enum of ISO 23247-4 message types
    ValidationSeverity - Error severity levels
    ValidationError - Single validation error
    ValidationResult - Complete validation outcome
    MessageSchemaValidator - Schema validator class
    validate_message - Convenience validation function

Manufacturing Ontology Components:
    EntityType - Manufacturing entity type enum (machine, robot, sensor, etc.)
    EntityStatus - Entity operational status enum
    CapabilityType - Manufacturing capability types
    RelationshipType - Entity relationship types
    ManufacturingEntity - Core entity model (Observable Manufacturing Element)
    EntityIdentifier - Unique entity identification with namespace
    Capability - Entity capability specification
    EntityRelationship - Relationship between entities
    ManufacturingOntology - Central entity registry
    create_machine_entity - Factory for machine entities
    create_robot_entity - Factory for robot entities
    create_sensor_entity - Factory for sensor entities
    get_manufacturing_ontology - Get singleton ontology instance
"""

from services.digital_twin.vector_clock import (
    VectorClock,
    CausalRelation,
    ConflictResolutionStrategy,
    VersionedState,
    ConflictResolver,
    ConflictRecord,
    DigitalTwinStateStore,
)

from services.digital_twin.crdt import (
    CRDT,
    GCounter,
    PNCounter,
    LWWRegister,
    MVRegister,
    GSet,
    ORSet,
    LWWMap,
    CRDTState,
)

from services.digital_twin.message_schema import (
    MessageType,
    ValidationSeverity,
    ValidationError,
    ValidationResult,
    MessageSchemaValidator,
    validate_message,
)

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
)

__all__ = [
    # Vector Clock
    'VectorClock',
    'CausalRelation',
    'ConflictResolutionStrategy',
    'VersionedState',
    'ConflictResolver',
    'ConflictRecord',
    'DigitalTwinStateStore',
    # CRDT
    'CRDT',
    'GCounter',
    'PNCounter',
    'LWWRegister',
    'MVRegister',
    'GSet',
    'ORSet',
    'LWWMap',
    'CRDTState',
    # Message Schema
    'MessageType',
    'ValidationSeverity',
    'ValidationError',
    'ValidationResult',
    'MessageSchemaValidator',
    'validate_message',
    # Manufacturing Ontology
    'EntityType',
    'EntityStatus',
    'CapabilityType',
    'RelationshipType',
    'ManufacturingEntity',
    'EntityIdentifier',
    'Capability',
    'EntityRelationship',
    'ManufacturingOntology',
    'create_machine_entity',
    'create_robot_entity',
    'create_sensor_entity',
    'get_manufacturing_ontology',
    'get_entity_namespace',
]
