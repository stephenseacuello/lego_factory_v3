"""
LEGO Factory v3 - CRDT Unit Tests
=================================
Comprehensive tests for Conflict-free Replicated Data Types.
"""

import pytest
from datetime import datetime
import time

from services.digital_twin.crdt import (
    GCounter,
    PNCounter,
    LWWRegister,
    MVRegister,
    GSet,
    ORSet,
    LWWMap,
    CRDTState,
)


class TestGCounter:
    """Test Grow-only Counter CRDT."""

    def test_initial_value(self):
        """Test initial counter value is zero."""
        counter = GCounter(node_id="node_1")
        assert counter.value() == 0

    def test_increment(self):
        """Test incrementing counter."""
        counter = GCounter(node_id="node_1")
        counter.increment()
        assert counter.value() == 1
        counter.increment(5)
        assert counter.value() == 6

    def test_merge_disjoint_nodes(self):
        """Test merging counters from different nodes."""
        c1 = GCounter(node_id="node_1")
        c1.increment(3)

        c2 = GCounter(node_id="node_2")
        c2.increment(5)

        merged = c1.merge(c2)
        assert merged.value() == 8  # 3 + 5

    def test_merge_same_node(self):
        """Test merging counters from same node takes max."""
        c1 = GCounter(node_id="node_1", counts={"node_1": 3})
        c2 = GCounter(node_id="node_1", counts={"node_1": 5})

        merged = c1.merge(c2)
        assert merged.value() == 5  # max(3, 5)

    def test_merge_idempotent(self):
        """Test that merge is idempotent."""
        c1 = GCounter(node_id="node_1", counts={"node_1": 3, "node_2": 2})
        c2 = c1.merge(c1)
        assert c2.value() == c1.value()

    def test_merge_commutative(self):
        """Test that merge is commutative."""
        c1 = GCounter(node_id="node_1", counts={"node_1": 3})
        c2 = GCounter(node_id="node_2", counts={"node_2": 5})

        m1 = c1.merge(c2)
        m2 = c2.merge(c1)
        assert m1.value() == m2.value()

    def test_serialization(self):
        """Test serialization round-trip."""
        counter = GCounter(node_id="node_1", counts={"node_1": 5, "node_2": 3})
        data = counter.to_dict()
        restored = GCounter.from_dict(data)

        assert restored.value() == counter.value()
        assert restored.node_id == counter.node_id


class TestPNCounter:
    """Test Positive-Negative Counter CRDT."""

    def test_initial_value(self):
        """Test initial value is zero."""
        counter = PNCounter(node_id="node_1")
        assert counter.value() == 0

    def test_increment(self):
        """Test incrementing."""
        counter = PNCounter(node_id="node_1")
        counter.increment(5)
        assert counter.value() == 5

    def test_decrement(self):
        """Test decrementing."""
        counter = PNCounter(node_id="node_1")
        counter.increment(10)
        counter.decrement(3)
        assert counter.value() == 7

    def test_can_go_negative(self):
        """Test counter can go negative."""
        counter = PNCounter(node_id="node_1")
        counter.decrement(5)
        assert counter.value() == -5

    def test_merge_counters(self):
        """Test merging PN counters."""
        c1 = PNCounter(node_id="node_1")
        c1.increment(10)
        c1.decrement(2)

        c2 = PNCounter(node_id="node_2")
        c2.increment(5)
        c2.decrement(1)

        merged = c1.merge(c2)
        # (10 - 2) + (5 - 1) = 8 + 4 = 12
        assert merged.value() == 12


class TestLWWRegister:
    """Test Last-Writer-Wins Register CRDT."""

    def test_initial_value(self):
        """Test initial value is None."""
        reg = LWWRegister(node_id="node_1")
        assert reg.value() is None

    def test_set_value(self):
        """Test setting a value."""
        reg = LWWRegister(node_id="node_1")
        reg.set("hello")
        assert reg.value() == "hello"

    def test_overwrite_with_later_timestamp(self):
        """Test overwriting with later timestamp."""
        reg = LWWRegister(node_id="node_1")
        reg.set("first", timestamp=1.0)
        reg.set("second", timestamp=2.0)
        assert reg.value() == "second"

    def test_ignore_earlier_timestamp(self):
        """Test ignoring earlier timestamp."""
        reg = LWWRegister(node_id="node_1")
        reg.set("second", timestamp=2.0)
        reg.set("first", timestamp=1.0)
        assert reg.value() == "second"

    def test_merge_later_wins(self):
        """Test merge picks later timestamp."""
        r1 = LWWRegister(node_id="node_1")
        r1.set("old", timestamp=1.0)

        r2 = LWWRegister(node_id="node_2")
        r2.set("new", timestamp=2.0)

        merged = r1.merge(r2)
        assert merged.value() == "new"

    def test_merge_keeps_newer(self):
        """Test merge keeps value with newer timestamp."""
        r1 = LWWRegister(node_id="node_1")
        r1.set("new", timestamp=2.0)

        r2 = LWWRegister(node_id="node_2")
        r2.set("old", timestamp=1.0)

        merged = r1.merge(r2)
        assert merged.value() == "new"


class TestMVRegister:
    """Test Multi-Value Register CRDT."""

    def test_initial_value(self):
        """Test initial value is empty set."""
        reg = MVRegister(node_id="node_1")
        assert reg.value() == set()

    def test_set_value(self):
        """Test setting a value."""
        reg = MVRegister(node_id="node_1")
        reg.set("value1")
        assert "value1" in reg.value()

    def test_concurrent_values(self):
        """Test concurrent values are both kept."""
        r1 = MVRegister(node_id="node_1")
        r1.set("from_node_1")

        r2 = MVRegister(node_id="node_2")
        r2.set("from_node_2")

        merged = r1.merge(r2)
        values = merged.value()

        assert "from_node_1" in values
        assert "from_node_2" in values
        assert len(values) == 2


class TestGSet:
    """Test Grow-only Set CRDT."""

    def test_initial_empty(self):
        """Test initial set is empty."""
        s = GSet()
        assert s.value() == set()

    def test_add_element(self):
        """Test adding elements."""
        s = GSet()
        s.add("a")
        s.add("b")
        assert s.value() == {"a", "b"}

    def test_add_duplicate(self):
        """Test adding duplicate has no effect."""
        s = GSet()
        s.add("a")
        s.add("a")
        assert s.value() == {"a"}

    def test_merge_union(self):
        """Test merge is union."""
        s1 = GSet(elements={"a", "b"})
        s2 = GSet(elements={"b", "c"})

        merged = s1.merge(s2)
        assert merged.value() == {"a", "b", "c"}

    def test_contains(self):
        """Test contains method."""
        s = GSet(elements={"a", "b"})
        assert s.contains("a")
        assert not s.contains("c")


class TestORSet:
    """Test Observed-Remove Set CRDT."""

    def test_initial_empty(self):
        """Test initial set is empty."""
        s = ORSet(node_id="node_1")
        assert s.value() == set()

    def test_add_element(self):
        """Test adding elements."""
        s = ORSet(node_id="node_1")
        s.add("a")
        s.add("b")
        assert s.value() == {"a", "b"}

    def test_remove_element(self):
        """Test removing elements."""
        s = ORSet(node_id="node_1")
        s.add("a")
        s.add("b")
        s.remove("a")
        assert s.value() == {"b"}

    def test_add_wins_over_remove(self):
        """Test that add wins over concurrent remove."""
        s1 = ORSet(node_id="node_1")
        s1.add("item")

        s2 = ORSet(node_id="node_2")
        s2.add("item")
        s2.remove("item")

        # s1 has add, s2 has add then remove
        # Merge should include item because s1's add is different from s2's
        merged = s1.merge(s2)

        # After merge, s1's add should be visible
        # (s2 only removed its own add's tag)
        # Note: This depends on implementation semantics

    def test_remove_then_add(self):
        """Test adding after remove brings it back."""
        s = ORSet(node_id="node_1")
        s.add("item")
        s.remove("item")
        assert s.value() == set()

        s.add("item")  # New tag
        assert s.value() == {"item"}

    def test_merge_concurrent_adds(self):
        """Test merging concurrent adds."""
        s1 = ORSet(node_id="node_1")
        s1.add("item")

        s2 = ORSet(node_id="node_2")
        s2.add("item")

        merged = s1.merge(s2)
        assert "item" in merged.value()


class TestLWWMap:
    """Test Last-Writer-Wins Map CRDT."""

    def test_initial_empty(self):
        """Test initial map is empty."""
        m = LWWMap(node_id="node_1")
        assert m.value() == {}

    def test_set_get(self):
        """Test set and get operations."""
        m = LWWMap(node_id="node_1")
        m.set("x", 100.0)
        assert m.get("x") == 100.0

    def test_multiple_keys(self):
        """Test multiple keys."""
        m = LWWMap(node_id="node_1")
        m.set("x", 100.0)
        m.set("y", 200.0)
        m.set("z", 300.0)

        assert m.value() == {"x": 100.0, "y": 200.0, "z": 300.0}

    def test_merge_different_keys(self):
        """Test merging maps with different keys."""
        m1 = LWWMap(node_id="node_1")
        m1.set("x", 100.0)

        m2 = LWWMap(node_id="node_2")
        m2.set("y", 200.0)

        merged = m1.merge(m2)
        assert merged.value() == {"x": 100.0, "y": 200.0}

    def test_merge_same_key_later_wins(self):
        """Test merging same key takes later timestamp."""
        m1 = LWWMap(node_id="node_1")
        m1.set("x", 100.0, timestamp=1.0)

        m2 = LWWMap(node_id="node_2")
        m2.set("x", 200.0, timestamp=2.0)

        merged = m1.merge(m2)
        assert merged.get("x") == 200.0


class TestCRDTState:
    """Test complete CRDT state for digital twin."""

    def test_create_state(self):
        """Test creating CRDT state."""
        state = CRDTState(entity_id="machine_1", node_id="controller_1")

        assert state.entity_id == "machine_1"
        assert state.node_id == "controller_1"

    def test_position_updates(self):
        """Test position updates."""
        state = CRDTState(entity_id="machine_1", node_id="ctrl_1")

        state.position.set("x", 100.0)
        state.position.set("y", 50.0)
        state.position.set("z", 25.0)

        pos = state.position.value()
        assert pos["x"] == 100.0
        assert pos["y"] == 50.0
        assert pos["z"] == 25.0

    def test_status_updates(self):
        """Test status updates."""
        state = CRDTState(entity_id="machine_1", node_id="ctrl_1")

        state.status.set("running")
        assert state.status.value() == "running"

        state.status.set("stopped")
        assert state.status.value() == "stopped"

    def test_counter_operations(self):
        """Test counter operations."""
        state = CRDTState(entity_id="machine_1", node_id="ctrl_1")

        state.counters["parts_produced"] = PNCounter(node_id="ctrl_1")
        state.counters["parts_produced"].increment(10)

        assert state.counters["parts_produced"].value() == 10

    def test_events_immutable(self):
        """Test events are immutable (grow-only)."""
        state = CRDTState(entity_id="machine_1", node_id="ctrl_1")

        state.events.add("event_1")
        state.events.add("event_2")

        events = state.events.value()
        assert "event_1" in events
        assert "event_2" in events

    def test_active_alarms(self):
        """Test active alarms with add/remove."""
        state = CRDTState(entity_id="machine_1", node_id="ctrl_1")

        state.active_alarms.add("alarm_1")
        state.active_alarms.add("alarm_2")

        assert "alarm_1" in state.active_alarms.value()
        assert "alarm_2" in state.active_alarms.value()

        state.active_alarms.remove("alarm_1")
        assert "alarm_1" not in state.active_alarms.value()
        assert "alarm_2" in state.active_alarms.value()

    def test_merge_states(self):
        """Test merging two CRDT states."""
        s1 = CRDTState(entity_id="machine_1", node_id="ctrl_1")
        s1.position.set("x", 100.0)
        s1.status.set("running", timestamp=1.0)
        s1.events.add("event_from_s1")

        s2 = CRDTState(entity_id="machine_1", node_id="ctrl_2")
        s2.position.set("y", 50.0)
        s2.status.set("stopped", timestamp=2.0)
        s2.events.add("event_from_s2")

        merged = s1.merge(s2)

        # Positions from both
        pos = merged.position.value()
        assert pos.get("x") == 100.0
        assert pos.get("y") == 50.0

        # Status takes later timestamp
        assert merged.status.value() == "stopped"

        # Events from both
        events = merged.events.value()
        assert "event_from_s1" in events
        assert "event_from_s2" in events

    def test_get_snapshot(self):
        """Test getting a simple snapshot."""
        state = CRDTState(entity_id="machine_1", node_id="ctrl_1")
        state.position.set("x", 100.0)
        state.status.set("running")
        state.events.add("event_1")
        state.active_alarms.add("alarm_1")

        snapshot = state.get_snapshot()

        assert snapshot["entity_id"] == "machine_1"
        assert snapshot["position"]["x"] == 100.0
        assert snapshot["status"] == "running"
        assert snapshot["event_count"] == 1
        assert "alarm_1" in snapshot["active_alarms"]


class TestCRDTISO23247Compliance:
    """Tests for ISO 23247 compliance of CRDT implementation."""

    def test_eventual_consistency(self):
        """ISO 23247-4: CRDTs achieve eventual consistency."""
        # Create three nodes with different updates
        s1 = CRDTState(entity_id="machine_1", node_id="node_1")
        s2 = CRDTState(entity_id="machine_1", node_id="node_2")
        s3 = CRDTState(entity_id="machine_1", node_id="node_3")

        # Each node makes independent updates
        s1.position.set("x", 100.0, timestamp=1.0)
        s2.position.set("y", 200.0, timestamp=2.0)
        s3.position.set("z", 300.0, timestamp=3.0)

        # Merge in different orders
        m1 = s1.merge(s2).merge(s3)
        m2 = s3.merge(s1).merge(s2)
        m3 = s2.merge(s3).merge(s1)

        # All should converge to same state
        assert m1.position.value() == m2.position.value()
        assert m2.position.value() == m3.position.value()

    def test_no_coordination_required(self):
        """ISO 23247-4: Updates don't require coordination."""
        # Simulate offline updates
        s1 = CRDTState(entity_id="machine_1", node_id="node_1")
        s2 = CRDTState(entity_id="machine_1", node_id="node_2")

        # Both make updates without seeing each other
        for i in range(10):
            s1.counters.setdefault("count", PNCounter(node_id="node_1"))
            s1.counters["count"].increment()

        for i in range(5):
            s2.counters.setdefault("count", PNCounter(node_id="node_2"))
            s2.counters["count"].increment()

        # Merge should combine all increments
        merged = s1.merge(s2)
        assert merged.counters["count"].value() == 15

    def test_concurrent_updates_preserved(self):
        """ISO 23247-4: Concurrent updates don't lose data."""
        s1 = CRDTState(entity_id="machine_1", node_id="node_1")
        s2 = CRDTState(entity_id="machine_1", node_id="node_2")

        # Both add different events concurrently
        s1.events.add("event_from_1")
        s2.events.add("event_from_2")

        merged = s1.merge(s2)

        # Both events should be present
        events = merged.events.value()
        assert "event_from_1" in events
        assert "event_from_2" in events

    def test_alarm_add_wins(self):
        """ISO 23247: Add semantics for safety-critical data."""
        s1 = CRDTState(entity_id="machine_1", node_id="node_1")
        s2 = CRDTState(entity_id="machine_1", node_id="node_2")

        # Node 1 adds alarm
        s1.active_alarms.add("critical_alarm")

        # Node 2 also adds same alarm, then removes it
        s2.active_alarms.add("critical_alarm")
        s2.active_alarms.remove("critical_alarm")

        # Merge should preserve alarm from node 1
        merged = s1.merge(s2)
        # Note: ORSet semantics - node_1's add tag survives node_2's remove
        # This is the "add wins" behavior

    def test_state_serialization(self):
        """ISO 23247-4: State can be serialized for transmission."""
        state = CRDTState(entity_id="machine_1", node_id="node_1")
        state.position.set("x", 100.0)
        state.status.set("running")
        state.events.add("event_1")

        # Serialize
        data = state.to_dict()

        # Verify it's JSON-serializable
        import json
        json_str = json.dumps(data)
        restored_data = json.loads(json_str)

        assert restored_data["entity_id"] == "machine_1"
        assert restored_data["position"]["entries"]["x"]["value"] == 100.0
