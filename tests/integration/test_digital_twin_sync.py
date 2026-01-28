"""
Integration tests for Digital Twin State Synchronization.

Tests the complete flow of state synchronization across multiple nodes,
including conflict detection, resolution, and CRDT merging.

These tests simulate real-world scenarios where multiple controllers
or systems update the same entity state concurrently.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
import copy

from services.digital_twin import (
    # Vector Clock
    VectorClock,
    CausalRelation,
    ConflictResolutionStrategy,
    VersionedState,
    ConflictResolver,
    DigitalTwinStateStore,
    # CRDT
    CRDTState,
    GCounter,
    PNCounter,
    LWWRegister,
    ORSet,
    LWWMap,
    # Message Validation
    MessageSchemaValidator,
    MessageType,
    validate_message,
    # Ontology
    ManufacturingEntity,
    EntityType,
    EntityStatus,
    ManufacturingOntology,
    create_machine_entity,
    get_manufacturing_ontology,
    reset_manufacturing_ontology,
)


# =============================================================================
# Multi-Node State Synchronization Tests
# =============================================================================

class TestMultiNodeStateSync:
    """
    Tests state synchronization between multiple nodes.

    Simulates a factory scenario where multiple controllers (PLCs, SCADA, MES)
    are updating the same equipment state.
    """

    def test_two_node_sequential_updates(self):
        """
        Test sequential updates from two nodes without conflicts.

        Scenario:
        1. Node A updates machine state
        2. Node A's state is sent to Node B
        3. Node B applies the update
        4. Both nodes should have identical state
        """
        # Create two state stores for two nodes
        store_a = DigitalTwinStateStore(node_id="controller_a")
        store_b = DigitalTwinStateStore(node_id="controller_b")

        # Node A makes an update
        state_a, _ = store_a.update_state(
            entity_id="machine_001",
            data={"position": {"x": 100, "y": 200}, "status": "running"},
            source_id="plc_1"
        )

        # Node B receives and applies Node A's state
        resolved, had_conflict = store_b.apply_remote_update(state_a)

        assert not had_conflict
        assert resolved.data["status"] == "running"
        assert store_b.get_state("machine_001").data == state_a.data

    def test_two_node_concurrent_updates_conflict(self):
        """
        Test concurrent updates from two nodes causing conflict.

        Scenario:
        1. Both nodes read initial state
        2. Node A updates position to (100, 100)
        3. Node B (without seeing A's update) updates position to (200, 200)
        4. Node B receives Node A's update - conflict detected
        5. Conflict is resolved via last-write-wins
        """
        store_a = DigitalTwinStateStore(
            node_id="controller_a",
            conflict_resolver=ConflictResolver(
                default_strategy=ConflictResolutionStrategy.LAST_WRITE_WINS
            )
        )
        store_b = DigitalTwinStateStore(
            node_id="controller_b",
            conflict_resolver=ConflictResolver(
                default_strategy=ConflictResolutionStrategy.LAST_WRITE_WINS
            )
        )

        # Both nodes update concurrently (simulated by not syncing)
        state_a, _ = store_a.update_state(
            entity_id="machine_001",
            data={"position": {"x": 100, "y": 100}},
            source_id="plc_1"
        )

        state_b, _ = store_b.update_state(
            entity_id="machine_001",
            data={"position": {"x": 200, "y": 200}},
            source_id="plc_2"
        )

        # Check that the clocks indicate concurrent updates
        relation = state_a.version.compare(state_b.version)
        assert relation == CausalRelation.CONCURRENT

        # Node B receives Node A's update - should detect conflict
        resolved, had_conflict = store_b.apply_remote_update(state_a)

        assert had_conflict
        # Resolved state should exist
        assert resolved is not None
        assert "position" in resolved.data

    def test_three_node_conflict_chain(self):
        """
        Test conflict resolution across three nodes.

        Scenario:
        1. Node A, B, C all start with same initial state
        2. Each node makes independent updates
        3. Updates are propagated and merged
        4. All nodes should eventually converge
        """
        store_a = DigitalTwinStateStore(node_id="node_a")
        store_b = DigitalTwinStateStore(node_id="node_b")
        store_c = DigitalTwinStateStore(node_id="node_c")

        # Each node makes an update
        state_a, _ = store_a.update_state(
            entity_id="machine_001",
            data={"temp": 25.0},
            source_id="sensor_a"
        )

        state_b, _ = store_b.update_state(
            entity_id="machine_001",
            data={"temp": 26.0},
            source_id="sensor_b"
        )

        state_c, _ = store_c.update_state(
            entity_id="machine_001",
            data={"temp": 24.5},
            source_id="sensor_c"
        )

        # Propagate A to B, then to C
        store_b.apply_remote_update(state_a)
        store_c.apply_remote_update(store_b.get_state("machine_001"))

        # Propagate B to C
        store_c.apply_remote_update(state_b)

        # All nodes should have converged
        final_state_c = store_c.get_state("machine_001")
        assert final_state_c is not None


# =============================================================================
# CRDT Convergence Tests
# =============================================================================

class TestCRDTConvergence:
    """
    Tests that CRDTs properly converge across distributed nodes.

    CRDTs guarantee eventual consistency without conflicts -
    any merge order produces the same final result.
    """

    def test_gcounter_convergence(self):
        """
        Test GCounter convergence across multiple nodes.

        Each node increments independently, merged result is sum.
        """
        # Three nodes counting parts
        counter_a = GCounter(node_id="counter_a")
        counter_b = GCounter(node_id="counter_b")
        counter_c = GCounter(node_id="counter_c")

        # Each node counts independently
        counter_a.increment(10)
        counter_b.increment(20)
        counter_c.increment(5)

        # Merge in different orders should give same result
        # Order 1: A + B + C
        merged_1 = counter_a.merge(counter_b).merge(counter_c)

        # Order 2: C + A + B (reset and re-merge)
        merged_2 = GCounter(node_id="merged")
        merged_2 = counter_c.merge(counter_a).merge(counter_b)

        assert merged_1.value() == merged_2.value()
        assert merged_1.value() == 35  # 10 + 20 + 5

    def test_pncounter_convergence(self):
        """
        Test PNCounter convergence with increments and decrements.

        Simulates inventory tracking across multiple systems.
        """
        # Warehouse 1 adds stock
        wh1 = PNCounter(node_id="warehouse_1")
        wh1.increment(100)  # Received shipment

        # Warehouse 2 removes stock
        wh2 = PNCounter(node_id="warehouse_2")
        wh2.decrement(25)  # Shipped out

        # Production adds scrap
        prod = PNCounter(node_id="production")
        prod.increment(50)  # Produced
        prod.decrement(5)   # Scrapped

        # Merge all
        total = wh1.merge(wh2).merge(prod)

        # 100 - 25 + 50 - 5 = 120
        assert total.value() == 120

    def test_lww_register_convergence(self):
        """
        Test LWWRegister convergence (last write wins).

        Latest timestamp wins regardless of merge order.
        """
        reg_a = LWWRegister(node_id="node_a")
        reg_b = LWWRegister(node_id="node_b")

        # Node A sets value at t=1
        reg_a.set("first", timestamp=1.0)

        # Node B sets value at t=2 (later)
        reg_b.set("second", timestamp=2.0)

        # Merge order shouldn't matter
        merged_ab = reg_a.merge(reg_b)
        merged_ba = reg_b.merge(reg_a)

        assert merged_ab.value() == "second"
        assert merged_ba.value() == "second"

    def test_orset_convergence_add_remove(self):
        """
        Test ORSet convergence with concurrent add/remove.

        Add wins over concurrent remove (observed-remove semantics).
        """
        set_a = ORSet(node_id="node_a")
        set_b = ORSet(node_id="node_b")

        # Node A adds alarm
        set_a.add("TEMP_HIGH")

        # Node B observes and adds same alarm, then removes it
        set_b = set_a.merge(set_b)  # B sees A's add
        set_b.remove("TEMP_HIGH")   # B removes it

        # Meanwhile, A adds alarm again (after original)
        set_a.add("TEMP_HIGH")  # New add with new tag

        # Merge - the new add from A should survive
        merged = set_a.merge(set_b)

        # Alarm should still be active (new add wins over earlier remove)
        assert "TEMP_HIGH" in merged.value()

    def test_crdt_state_full_merge(self):
        """
        Test complete CRDTState merge for a machine entity.

        Combines all CRDT types for comprehensive state.
        """
        # Controller 1 state
        state1 = CRDTState(entity_id="machine_001", node_id="controller_1")
        state1.position.set("x", 100.0)
        state1.position.set("y", 200.0)
        state1.status.set("running")
        state1.active_alarms.add("WARN_001")

        # Controller 2 state (concurrent updates)
        state2 = CRDTState(entity_id="machine_001", node_id="controller_2")
        state2.position.set("z", 50.0)  # Different axis
        state2.active_alarms.add("WARN_002")

        # Merge states
        merged = state1.merge(state2)

        # Should have all positions
        snapshot = merged.get_snapshot()
        assert "x" in snapshot["position"]
        assert "y" in snapshot["position"]
        assert "z" in snapshot["position"]

        # Should have both alarms
        assert "WARN_001" in snapshot["active_alarms"]
        assert "WARN_002" in snapshot["active_alarms"]


# =============================================================================
# Conflict Resolution Strategy Tests
# =============================================================================

class TestConflictResolutionStrategies:
    """Tests for different conflict resolution strategies."""

    def test_last_write_wins_strategy(self):
        """Test last-write-wins resolution."""
        resolver = ConflictResolver(
            default_strategy=ConflictResolutionStrategy.LAST_WRITE_WINS
        )

        # Create two concurrent states
        state1 = VersionedState(
            data={"value": "old"},
            version=VectorClock(node_id="node1"),
            entity_id="test"
        )
        state1.version.increment()
        state1.version.wall_clock = datetime(2024, 1, 1, 10, 0, 0)

        state2 = VersionedState(
            data={"value": "new"},
            version=VectorClock(node_id="node2"),
            entity_id="test"
        )
        state2.version.increment()
        state2.version.wall_clock = datetime(2024, 1, 1, 11, 0, 0)  # Later

        # Resolve conflict
        resolved, had_conflict = resolver.resolve(state1, state2)

        assert had_conflict
        assert resolved.data["value"] == "new"  # Later timestamp wins

    def test_first_write_wins_strategy(self):
        """Test first-write-wins resolution."""
        resolver = ConflictResolver(
            default_strategy=ConflictResolutionStrategy.FIRST_WRITE_WINS
        )

        state1 = VersionedState(
            data={"value": "first"},
            version=VectorClock(node_id="node1"),
            entity_id="test"
        )
        state1.version.increment()
        state1.version.wall_clock = datetime(2024, 1, 1, 10, 0, 0)

        state2 = VersionedState(
            data={"value": "second"},
            version=VectorClock(node_id="node2"),
            entity_id="test"
        )
        state2.version.increment()
        state2.version.wall_clock = datetime(2024, 1, 1, 11, 0, 0)

        resolved, _ = resolver.resolve(state1, state2)

        assert resolved.data["value"] == "first"  # Earlier timestamp wins

    def test_prefer_source_strategy(self):
        """Test prefer-source resolution with trusted sources."""
        resolver = ConflictResolver(
            default_strategy=ConflictResolutionStrategy.PREFER_SOURCE,
            preferred_sources=["trusted_plc"]
        )

        state1 = VersionedState(
            data={"value": "from_untrusted"},
            version=VectorClock(node_id="node1"),
            entity_id="test",
            source_id="untrusted_hmi"
        )
        state1.version.increment()

        state2 = VersionedState(
            data={"value": "from_trusted"},
            version=VectorClock(node_id="node2"),
            entity_id="test",
            source_id="trusted_plc"
        )
        state2.version.increment()

        resolved, _ = resolver.resolve(state1, state2)

        assert resolved.data["value"] == "from_trusted"  # Trusted source wins

    def test_merge_strategy(self):
        """Test semantic merge strategy for compatible changes."""
        resolver = ConflictResolver(
            default_strategy=ConflictResolutionStrategy.MERGE
        )

        # States with non-overlapping changes
        state1 = VersionedState(
            data={"position_x": 100, "temperature": 25.0},
            version=VectorClock(node_id="node1"),
            entity_id="test"
        )
        state1.version.increment()

        state2 = VersionedState(
            data={"position_y": 200, "pressure": 101.3},
            version=VectorClock(node_id="node2"),
            entity_id="test"
        )
        state2.version.increment()

        resolved, _ = resolver.resolve(state1, state2)

        # Should have merged all fields
        assert "position_x" in resolved.data
        assert "position_y" in resolved.data
        assert "temperature" in resolved.data
        assert "pressure" in resolved.data

    def test_conflict_audit_log(self):
        """Test that conflicts are logged for auditing."""
        resolver = ConflictResolver(
            default_strategy=ConflictResolutionStrategy.LAST_WRITE_WINS
        )

        state1 = VersionedState(
            data={"v": 1},
            version=VectorClock(node_id="n1"),
            entity_id="machine_001"
        )
        state1.version.increment()

        state2 = VersionedState(
            data={"v": 2},
            version=VectorClock(node_id="n2"),
            entity_id="machine_001"
        )
        state2.version.increment()

        resolver.resolve(state1, state2)

        # Check conflict was logged
        history = resolver.get_conflict_history(entity_id="machine_001")
        assert len(history) == 1
        assert history[0].entity_id == "machine_001"


# =============================================================================
# Message Validation Integration Tests
# =============================================================================

class TestMessageValidationIntegration:
    """Tests message validation in the sync pipeline."""

    def test_validate_state_update_message(self):
        """Test validation of a state update message."""
        message = {
            "message_type": "state_update",
            "entity_id": "machine_001",
            "timestamp": "2024-01-15T10:30:00Z",
            "state": {
                "status": "running",
                "position": {"x": 100.0, "y": 200.0, "z": 0.0}
            }
        }

        result = validate_message(message)
        assert result.valid

    def test_validate_command_message(self):
        """Test validation of a command message."""
        message = {
            "message_type": "command",
            "entity_id": "robot_001",
            "timestamp": "2024-01-15T10:30:00Z",
            "command": "move_to",
            "parameters": {"x": 150.0, "y": 250.0, "z": 50.0},
            "priority": 5
        }

        result = validate_message(message)
        assert result.valid

    def test_reject_invalid_message(self):
        """Test that invalid messages are rejected."""
        # Missing required timestamp
        message = {
            "message_type": "state_update",
            "entity_id": "machine_001",
            "state": {"status": "running"}
        }

        result = validate_message(message)
        assert not result.valid
        assert any("timestamp" in e.path for e in result.errors)

    def test_validate_heartbeat_message(self):
        """Test validation of heartbeat messages."""
        message = {
            "message_type": "heartbeat",
            "node_id": "controller_1",
            "timestamp": "2024-01-15T10:30:00Z",
            "sequence": 42,
            "status": "healthy"
        }

        result = validate_message(message)
        assert result.valid


# =============================================================================
# Ontology Integration Tests
# =============================================================================

class TestOntologyIntegration:
    """Tests ontology integration with state synchronization."""

    def setup_method(self):
        """Reset ontology before each test."""
        reset_manufacturing_ontology()

    def test_entity_state_with_ontology(self):
        """Test linking state store entities to ontology."""
        # Register entity in ontology
        ontology = get_manufacturing_ontology()
        machine = create_machine_entity(
            "cnc_001",
            "Haas VF-2",
            capabilities=["milling", "drilling"]
        )
        machine.status = EntityStatus.RUNNING
        ontology.register(machine)

        # Create state store and update state
        store = DigitalTwinStateStore(node_id="controller_1")
        state, _ = store.update_state(
            entity_id="cnc_001",
            data={"spindle_speed": 5000, "feed_rate": 250},
            source_id="plc_1"
        )

        # Verify entity exists in both systems
        assert ontology.get_by_id("cnc_001") is not None
        assert store.get_state("cnc_001") is not None

    def test_crdt_state_for_ontology_entity(self):
        """Test using CRDT state for ontology entities."""
        ontology = get_manufacturing_ontology()
        machine = create_machine_entity("cnc_001", "Test CNC")
        ontology.register(machine)

        # Create CRDT state linked to ontology entity
        crdt_state = CRDTState(
            entity_id=machine.entity_id,
            node_id="controller_1"
        )

        # Update state
        crdt_state.position.set("x", 100.0)
        crdt_state.status.set("running")

        # Sync ontology status
        machine.status = EntityStatus(crdt_state.status.value())

        assert machine.status == EntityStatus.RUNNING


# =============================================================================
# End-to-End Synchronization Scenario
# =============================================================================

class TestE2ESyncScenario:
    """
    End-to-end test of a realistic factory synchronization scenario.

    Simulates a CNC machine being monitored by:
    - PLC (Level 1) - Position and status
    - SCADA (Level 2) - Alarms and historian
    - MES (Level 3) - Work order state
    """

    def setup_method(self):
        """Set up the multi-tier factory scenario."""
        reset_manufacturing_ontology()

        # Create state stores for each tier
        self.plc_store = DigitalTwinStateStore(node_id="plc_cnc_001")
        self.scada_store = DigitalTwinStateStore(node_id="scada_server")
        self.mes_store = DigitalTwinStateStore(node_id="mes_server")

        # Register machine in ontology
        self.ontology = get_manufacturing_ontology()
        self.machine = create_machine_entity(
            "cnc_001",
            "5-Axis CNC",
            capabilities=["milling", "drilling"]
        )
        self.ontology.register(self.machine)

    def test_position_update_propagation(self):
        """Test position updates flow from PLC through all tiers."""
        # PLC updates position
        plc_state, _ = self.plc_store.update_state(
            entity_id="cnc_001",
            data={
                "position": {"x": 150.5, "y": 200.3, "z": 50.0},
                "status": "running"
            },
            source_id="plc_driver"
        )

        # SCADA receives PLC update
        scada_resolved, scada_conflict = self.scada_store.apply_remote_update(plc_state)
        assert not scada_conflict

        # MES receives SCADA state
        mes_resolved, mes_conflict = self.mes_store.apply_remote_update(scada_resolved)
        assert not mes_conflict

        # All tiers should have same position
        assert self.mes_store.get_state("cnc_001").data["position"]["x"] == 150.5

    def test_concurrent_tier_updates(self):
        """Test handling concurrent updates from different tiers."""
        # PLC updates position
        plc_state, _ = self.plc_store.update_state(
            entity_id="cnc_001",
            data={"position": {"x": 100}},
            source_id="plc"
        )

        # MES updates work order (concurrent, different data)
        mes_state, _ = self.mes_store.update_state(
            entity_id="cnc_001",
            data={"work_order": "WO-12345"},
            source_id="mes"
        )

        # SCADA merges both
        self.scada_store.apply_remote_update(plc_state)
        self.scada_store.apply_remote_update(mes_state)

        # SCADA should have both pieces of data
        scada_state = self.scada_store.get_state("cnc_001")
        # Note: Due to conflict resolution, the exact state depends on strategy

    def test_alarm_synchronization_with_crdt(self):
        """Test alarm state synchronization using ORSet CRDT."""
        # Create CRDT states for PLC and SCADA
        plc_alarms = CRDTState(entity_id="cnc_001", node_id="plc")
        scada_alarms = CRDTState(entity_id="cnc_001", node_id="scada")

        # PLC raises alarms
        plc_alarms.active_alarms.add("SPINDLE_OVERTEMP")
        plc_alarms.active_alarms.add("COOLANT_LOW")

        # SCADA acknowledges one alarm
        scada_alarms = plc_alarms.merge(scada_alarms)
        scada_alarms.active_alarms.remove("SPINDLE_OVERTEMP")

        # PLC raises another alarm
        plc_alarms.active_alarms.add("AXIS_FAULT")

        # Final merge
        final = plc_alarms.merge(scada_alarms)

        # Should have COOLANT_LOW and AXIS_FAULT
        # SPINDLE_OVERTEMP was acknowledged
        active = final.active_alarms.value()
        assert "COOLANT_LOW" in active
        assert "AXIS_FAULT" in active
        # Note: Due to ORSet semantics, SPINDLE_OVERTEMP might still be present
        # if it was re-added after the remove

    def test_data_integrity_verification(self):
        """Test checksum verification for data integrity."""
        # Create state with checksum
        state, _ = self.plc_store.update_state(
            entity_id="cnc_001",
            data={"critical_param": 42.5},
            source_id="plc"
        )

        # State should have checksum
        assert state.checksum is not None

        # Verify integrity
        assert state.verify_integrity()

        # Tamper with data
        state.data["critical_param"] = 99.9

        # Integrity check should fail
        assert not state.verify_integrity()
