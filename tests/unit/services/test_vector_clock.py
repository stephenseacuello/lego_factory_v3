"""
LEGO Factory v3 - Vector Clock Unit Tests
==========================================
Comprehensive tests for ISO 23247 vector clock conflict resolution.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from services.digital_twin.vector_clock import (
    VectorClock,
    CausalRelation,
    ConflictResolutionStrategy,
    VersionedState,
    ConflictResolver,
    ConflictRecord,
    DigitalTwinStateStore,
)


class TestVectorClock:
    """Test VectorClock basic operations."""

    def test_create_empty_clock(self):
        """Test creating an empty vector clock."""
        clock = VectorClock(node_id="node_1")
        assert clock.clock == {}
        assert clock.node_id == "node_1"

    def test_increment(self):
        """Test incrementing a clock."""
        clock = VectorClock(node_id="node_1")
        clock.increment()
        assert clock.clock["node_1"] == 1
        clock.increment()
        assert clock.clock["node_1"] == 2

    def test_increment_sets_wall_clock(self):
        """Test that increment sets wall clock timestamp."""
        clock = VectorClock(node_id="node_1")
        assert clock.wall_clock is None
        clock.increment()
        assert clock.wall_clock is not None
        assert isinstance(clock.wall_clock, datetime)

    def test_merge_clocks(self):
        """Test merging two vector clocks."""
        clock1 = VectorClock(node_id="node_1", clock={"node_1": 3, "node_2": 1})
        clock2 = VectorClock(node_id="node_2", clock={"node_1": 2, "node_2": 4})

        clock1.merge(clock2)

        # Should take max of each component and increment own
        assert clock1.clock["node_1"] >= 3  # Incremented after merge
        assert clock1.clock["node_2"] == 4

    def test_merge_with_new_nodes(self):
        """Test merging clocks with different nodes."""
        clock1 = VectorClock(node_id="node_1", clock={"node_1": 2})
        clock2 = VectorClock(node_id="node_2", clock={"node_2": 3, "node_3": 1})

        clock1.merge(clock2)

        assert "node_1" in clock1.clock
        assert "node_2" in clock1.clock
        assert "node_3" in clock1.clock


class TestCausalRelation:
    """Test causal relationship comparison."""

    def test_equal_clocks(self):
        """Test comparison of equal clocks."""
        clock1 = VectorClock(clock={"node_1": 2, "node_2": 3})
        clock2 = VectorClock(clock={"node_1": 2, "node_2": 3})

        assert clock1.compare(clock2) == CausalRelation.EQUAL

    def test_happens_before(self):
        """Test happens-before relationship."""
        clock1 = VectorClock(clock={"node_1": 1, "node_2": 2})
        clock2 = VectorClock(clock={"node_1": 2, "node_2": 3})

        assert clock1.compare(clock2) == CausalRelation.BEFORE
        assert clock1.happens_before(clock2)

    def test_happens_after(self):
        """Test happens-after relationship."""
        clock1 = VectorClock(clock={"node_1": 3, "node_2": 4})
        clock2 = VectorClock(clock={"node_1": 2, "node_2": 3})

        assert clock1.compare(clock2) == CausalRelation.AFTER

    def test_concurrent(self):
        """Test concurrent (conflict) detection."""
        clock1 = VectorClock(clock={"node_1": 2, "node_2": 1})
        clock2 = VectorClock(clock={"node_1": 1, "node_2": 2})

        assert clock1.compare(clock2) == CausalRelation.CONCURRENT
        assert clock1.is_concurrent_with(clock2)

    def test_concurrent_with_missing_nodes(self):
        """Test concurrent detection with different node sets."""
        clock1 = VectorClock(clock={"node_1": 2})
        clock2 = VectorClock(clock={"node_2": 2})

        # Both have unique updates, so concurrent
        assert clock1.compare(clock2) == CausalRelation.CONCURRENT


class TestVectorClockSerialization:
    """Test vector clock serialization."""

    def test_to_dict(self):
        """Test serialization to dictionary."""
        clock = VectorClock(
            node_id="node_1",
            clock={"node_1": 3, "node_2": 2}
        )
        clock.increment()

        data = clock.to_dict()

        assert data["node_id"] == "node_1"
        assert data["clock"]["node_1"] >= 3
        assert data["clock"]["node_2"] == 2
        assert data["wall_clock"] is not None

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "node_id": "node_1",
            "clock": {"node_1": 5, "node_2": 3},
            "wall_clock": "2024-01-15T10:30:00"
        }

        clock = VectorClock.from_dict(data)

        assert clock.node_id == "node_1"
        assert clock.clock["node_1"] == 5
        assert clock.wall_clock.year == 2024

    def test_round_trip_serialization(self):
        """Test that serialization round-trips correctly."""
        original = VectorClock(
            node_id="test",
            clock={"a": 1, "b": 2, "c": 3}
        )
        original.increment()

        serialized = original.to_dict()
        restored = VectorClock.from_dict(serialized)

        assert original.node_id == restored.node_id
        assert original.clock == restored.clock

    def test_copy(self):
        """Test deep copying a vector clock."""
        original = VectorClock(node_id="node_1", clock={"node_1": 3})
        copy = original.copy()

        # Modify copy
        copy.increment()

        # Original should be unchanged
        assert original.clock["node_1"] == 3


class TestVersionedState:
    """Test VersionedState operations."""

    def test_create_versioned_state(self):
        """Test creating a versioned state."""
        state = VersionedState(
            data={"position": {"x": 100, "y": 50}},
            entity_id="machine_1",
            source_id="controller_1",
            state_type="position"
        )

        assert state.data["position"]["x"] == 100
        assert state.entity_id == "machine_1"

    def test_compute_checksum(self):
        """Test checksum computation."""
        state = VersionedState(
            data={"value": 42}
        )

        checksum = state.compute_checksum()

        assert checksum is not None
        assert len(checksum) == 64  # SHA-256 hex

    def test_checksum_deterministic(self):
        """Test that checksum is deterministic."""
        state1 = VersionedState(data={"a": 1, "b": 2})
        state2 = VersionedState(data={"b": 2, "a": 1})  # Different order

        # Should produce same checksum (sorted keys)
        assert state1.compute_checksum() == state2.compute_checksum()

    def test_verify_integrity_valid(self):
        """Test integrity verification with valid checksum."""
        state = VersionedState(data={"value": 42})
        state.checksum = state.compute_checksum()

        assert state.verify_integrity() is True

    def test_verify_integrity_invalid(self):
        """Test integrity verification with corrupted data."""
        state = VersionedState(data={"value": 42})
        state.checksum = state.compute_checksum()

        # Corrupt the data
        state.data["value"] = 43

        assert state.verify_integrity() is False

    def test_verify_integrity_no_checksum(self):
        """Test integrity verification with no checksum."""
        state = VersionedState(data={"value": 42})
        # No checksum set

        # Should return True (nothing to verify)
        assert state.verify_integrity() is True


class TestConflictResolver:
    """Test conflict resolution strategies."""

    @pytest.fixture
    def resolver(self):
        """Create a conflict resolver."""
        return ConflictResolver()

    @pytest.fixture
    def local_state(self):
        """Create a local state."""
        state = VersionedState(
            data={"position": {"x": 100}},
            version=VectorClock(node_id="local", clock={"local": 2, "remote": 1}),
            entity_id="machine_1",
            source_id="local_controller"
        )
        state.version.wall_clock = datetime.utcnow() - timedelta(seconds=10)
        return state

    @pytest.fixture
    def remote_state(self):
        """Create a remote state (concurrent with local)."""
        state = VersionedState(
            data={"position": {"x": 200}},
            version=VectorClock(node_id="remote", clock={"local": 1, "remote": 2}),
            entity_id="machine_1",
            source_id="remote_controller"
        )
        state.version.wall_clock = datetime.utcnow()
        return state

    def test_no_conflict_local_newer(self, resolver):
        """Test resolution when local is strictly newer."""
        local = VersionedState(
            data={"value": 1},
            version=VectorClock(clock={"a": 2, "b": 1}),
            entity_id="test"
        )
        remote = VersionedState(
            data={"value": 2},
            version=VectorClock(clock={"a": 1, "b": 1}),
            entity_id="test"
        )

        resolved, had_conflict = resolver.resolve(local, remote)

        assert had_conflict is False
        assert resolved.data["value"] == 1  # Local kept

    def test_no_conflict_remote_newer(self, resolver):
        """Test resolution when remote is strictly newer."""
        local = VersionedState(
            data={"value": 1},
            version=VectorClock(clock={"a": 1, "b": 1}),
            entity_id="test"
        )
        remote = VersionedState(
            data={"value": 2},
            version=VectorClock(clock={"a": 2, "b": 2}),
            entity_id="test"
        )

        resolved, had_conflict = resolver.resolve(local, remote)

        assert had_conflict is False
        assert resolved.data["value"] == 2  # Remote accepted

    def test_conflict_last_write_wins(self, resolver, local_state, remote_state):
        """Test last-write-wins resolution."""
        resolved, had_conflict = resolver.resolve(
            local_state, remote_state,
            strategy=ConflictResolutionStrategy.LAST_WRITE_WINS
        )

        assert had_conflict is True
        # Remote has later wall_clock, so it wins
        assert resolved.data["position"]["x"] == 200

    def test_conflict_first_write_wins(self, resolver, local_state, remote_state):
        """Test first-write-wins resolution."""
        resolved, had_conflict = resolver.resolve(
            local_state, remote_state,
            strategy=ConflictResolutionStrategy.FIRST_WRITE_WINS
        )

        assert had_conflict is True
        # Local has earlier wall_clock, so it wins
        assert resolved.data["position"]["x"] == 100

    def test_conflict_prefer_source(self, local_state, remote_state):
        """Test prefer-source resolution."""
        resolver = ConflictResolver(
            preferred_sources=["remote_controller"]
        )

        resolved, had_conflict = resolver.resolve(
            local_state, remote_state,
            strategy=ConflictResolutionStrategy.PREFER_SOURCE
        )

        assert had_conflict is True
        assert resolved.data["position"]["x"] == 200  # Remote preferred

    def test_conflict_merge_numeric(self, resolver):
        """Test merge resolution with numeric values."""
        local = VersionedState(
            data={"x": 100, "y": 50},
            version=VectorClock(clock={"a": 2, "b": 1}),
            entity_id="test"
        )
        remote = VersionedState(
            data={"x": 200, "y": 50, "z": 30},
            version=VectorClock(clock={"a": 1, "b": 2}),
            entity_id="test"
        )

        resolved, had_conflict = resolver.resolve(
            local, remote,
            strategy=ConflictResolutionStrategy.MERGE
        )

        assert had_conflict is True
        assert resolved.data["x"] == 150  # Average
        assert resolved.data["y"] == 50   # Same value
        assert resolved.data["z"] == 30   # From remote only

    def test_conflict_merge_counters(self, resolver):
        """Test merge resolution takes max for counters."""
        local = VersionedState(
            data={"error_count": 10, "total_count": 100},
            version=VectorClock(clock={"a": 2, "b": 1}),
            entity_id="test"
        )
        remote = VersionedState(
            data={"error_count": 15, "total_count": 95},
            version=VectorClock(clock={"a": 1, "b": 2}),
            entity_id="test"
        )

        resolved, _ = resolver.resolve(
            local, remote,
            strategy=ConflictResolutionStrategy.MERGE
        )

        assert resolved.data["error_count"] == 15  # Max
        assert resolved.data["total_count"] == 100  # Max

    def test_conflict_logged(self, resolver, local_state, remote_state):
        """Test that conflicts are logged."""
        assert len(resolver.conflict_log) == 0

        resolver.resolve(local_state, remote_state)

        assert len(resolver.conflict_log) == 1
        record = resolver.conflict_log[0]
        assert record.entity_id == "machine_1"
        assert record.resolved_by == "auto"

    def test_get_conflict_history(self, resolver, local_state, remote_state):
        """Test retrieving conflict history."""
        # Create multiple conflicts
        for i in range(5):
            local_state.entity_id = f"machine_{i}"
            remote_state.entity_id = f"machine_{i}"
            resolver.resolve(local_state, remote_state)

        history = resolver.get_conflict_history()
        assert len(history) == 5

        # Filter by entity
        history = resolver.get_conflict_history(entity_id="machine_2")
        assert len(history) == 1


class TestDigitalTwinStateStore:
    """Test the complete state store."""

    @pytest.fixture
    def store(self):
        """Create a state store."""
        return DigitalTwinStateStore(node_id="test_node")

    def test_update_state(self, store):
        """Test updating state for an entity."""
        state, had_conflict = store.update_state(
            entity_id="machine_1",
            data={"status": "running"},
            source_id="controller_1"
        )

        assert had_conflict is False
        assert state.entity_id == "machine_1"
        assert state.version.clock["test_node"] == 1

    def test_get_state(self, store):
        """Test retrieving state."""
        store.update_state(
            entity_id="machine_1",
            data={"status": "running"},
            source_id="controller_1"
        )

        state = store.get_state("machine_1")

        assert state is not None
        assert state.data["status"] == "running"

    def test_get_state_not_found(self, store):
        """Test retrieving non-existent state."""
        state = store.get_state("nonexistent")
        assert state is None

    def test_apply_remote_update_no_conflict(self, store):
        """Test applying remote update with no conflict."""
        remote_state = VersionedState(
            data={"status": "stopped"},
            version=VectorClock(node_id="remote", clock={"remote": 1}),
            entity_id="machine_1",
            source_id="remote_controller"
        )
        remote_state.version.increment()

        result, had_conflict = store.apply_remote_update(remote_state)

        assert had_conflict is False
        assert store.get_state("machine_1").data["status"] == "stopped"

    def test_apply_remote_update_with_conflict(self, store):
        """Test applying remote update that causes conflict."""
        # First, create local state
        store.update_state(
            entity_id="machine_1",
            data={"x": 100},
            source_id="local"
        )

        # Create conflicting remote state
        remote_state = VersionedState(
            data={"x": 200},
            version=VectorClock(node_id="remote", clock={"remote": 1}),
            entity_id="machine_1",
            source_id="remote"
        )
        remote_state.version.increment()
        remote_state.version.wall_clock = datetime.utcnow()

        result, had_conflict = store.apply_remote_update(remote_state)

        assert had_conflict is True

    def test_state_history(self, store):
        """Test state history tracking."""
        # Make several updates
        for i in range(5):
            store.update_state(
                entity_id="machine_1",
                data={"value": i},
                source_id="controller"
            )

        history = store.get_history("machine_1")

        assert len(history) == 5
        assert history[-1].data["value"] == 4

    def test_get_all_entities(self, store):
        """Test getting all entity IDs."""
        store.update_state("machine_1", {"a": 1}, "src")
        store.update_state("machine_2", {"b": 2}, "src")
        store.update_state("machine_3", {"c": 3}, "src")

        entities = store.get_all_entities()

        assert len(entities) == 3
        assert "machine_1" in entities
        assert "machine_2" in entities
        assert "machine_3" in entities

    def test_statistics(self, store):
        """Test getting store statistics."""
        store.update_state("machine_1", {"a": 1}, "src")
        store.update_state("machine_1", {"a": 2}, "src")
        store.update_state("machine_2", {"b": 1}, "src")

        stats = store.get_statistics()

        assert stats["node_id"] == "test_node"
        assert stats["entity_count"] == 2
        assert stats["total_history_entries"] == 3


class TestISO23247Compliance:
    """Tests specific to ISO 23247 compliance requirements."""

    def test_data_integrity_checksum(self):
        """ISO 23247-4: Data integrity through checksums."""
        state = VersionedState(
            data={"position": {"x": 100, "y": 200, "z": 50}},
            entity_id="cnc_mill_1"
        )
        state.checksum = state.compute_checksum()

        # Verify integrity
        assert state.verify_integrity() is True

        # Simulate data corruption
        state.data["position"]["x"] = 999
        assert state.verify_integrity() is False

    def test_causal_ordering(self):
        """ISO 23247-4: Causal ordering of events."""
        # Simulate sequence of events across nodes
        node1_clock = VectorClock(node_id="plc")
        node2_clock = VectorClock(node_id="hmi")

        # PLC sends update
        node1_clock.increment()
        plc_v1 = node1_clock.copy()

        # HMI receives and responds
        node2_clock.merge(plc_v1)
        hmi_v1 = node2_clock.copy()

        # PLC receives HMI response
        node1_clock.merge(hmi_v1)
        plc_v2 = node1_clock.copy()

        # Verify causal chain
        assert plc_v1.happens_before(hmi_v1)
        assert hmi_v1.happens_before(plc_v2)

    def test_concurrent_update_detection(self):
        """ISO 23247-4: Detection of concurrent updates."""
        # Two nodes make independent updates
        node1_clock = VectorClock(node_id="controller_1")
        node2_clock = VectorClock(node_id="controller_2")

        node1_clock.increment()
        node2_clock.increment()

        # These are concurrent - potential conflict
        assert node1_clock.is_concurrent_with(node2_clock)

    def test_conflict_resolution_audit_trail(self):
        """ISO 23247-4: Audit trail for conflict resolution."""
        resolver = ConflictResolver()

        local = VersionedState(
            data={"temp": 100},
            version=VectorClock(clock={"a": 2, "b": 1}),
            entity_id="sensor_1",
            source_id="controller_a"
        )
        local.version.wall_clock = datetime.utcnow()

        remote = VersionedState(
            data={"temp": 105},
            version=VectorClock(clock={"a": 1, "b": 2}),
            entity_id="sensor_1",
            source_id="controller_b"
        )
        remote.version.wall_clock = datetime.utcnow() + timedelta(seconds=1)

        resolver.resolve(local, remote)

        # Verify audit record
        history = resolver.get_conflict_history()
        assert len(history) == 1
        record = history[0]

        assert record.entity_id == "sensor_1"
        assert record.local_data["temp"] == 100
        assert record.remote_data["temp"] == 105
        assert record.resolution_strategy == ConflictResolutionStrategy.LAST_WRITE_WINS

    def test_version_vector_merge(self):
        """ISO 23247-4: Proper version vector merging."""
        # Complex multi-node scenario
        clocks = {
            "node_a": VectorClock(node_id="node_a"),
            "node_b": VectorClock(node_id="node_b"),
            "node_c": VectorClock(node_id="node_c"),
        }

        # Node A updates
        clocks["node_a"].increment()
        clocks["node_a"].increment()

        # Node B receives from A and updates
        clocks["node_b"].merge(clocks["node_a"].copy())

        # Node C receives from both
        clocks["node_c"].merge(clocks["node_a"].copy())
        clocks["node_c"].merge(clocks["node_b"].copy())

        # Node C should have complete knowledge
        assert clocks["node_c"].clock["node_a"] >= 2
        assert clocks["node_c"].clock["node_b"] >= 1
        assert clocks["node_c"].clock["node_c"] >= 1  # Its own updates
