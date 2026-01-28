"""
CRDT Conflict Resolver - Conflict-free Replicated Data Types for Digital Twins.

This module implements CRDTs for distributed digital twin synchronization:
- Automatic conflict resolution without coordination
- Eventual consistency guarantees
- Support for offline operation and edge computing

CRDT Types Implemented:
- G-Counter: Grow-only counter (production counts)
- PN-Counter: Increment/decrement counter (inventory)
- LWW-Register: Last-writer-wins register (sensor values)
- OR-Set: Observed-Remove set (active equipment)
- MV-Register: Multi-value register (concurrent updates)

Research Value:
- Novel CRDT types for manufacturing state
- Hybrid logical clocks for ordering
- Conflict-free merge for edge-cloud sync
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set, Tuple, Generic, TypeVar, Union
from enum import Enum
from datetime import datetime
import json
import hashlib
import uuid
import logging
from abc import ABC, abstractmethod
from collections import defaultdict

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# Hybrid Logical Clock (HLC)
# =============================================================================

@dataclass
class HybridLogicalClock:
    """
    Hybrid Logical Clock for distributed event ordering.

    Combines physical time with logical counters:
    - Preserves causality ordering
    - Bounded clock drift
    - Works with NTP-synchronized clocks
    """
    physical_time: int  # Milliseconds since epoch
    logical_counter: int
    node_id: str

    @classmethod
    def now(cls, node_id: str) -> 'HybridLogicalClock':
        """Create current HLC timestamp."""
        return cls(
            physical_time=int(datetime.utcnow().timestamp() * 1000),
            logical_counter=0,
            node_id=node_id
        )

    def update(self, other: 'HybridLogicalClock' = None) -> 'HybridLogicalClock':
        """Update clock based on local event or received message."""
        now_ms = int(datetime.utcnow().timestamp() * 1000)

        if other is None:
            # Local event
            if now_ms > self.physical_time:
                return HybridLogicalClock(now_ms, 0, self.node_id)
            else:
                return HybridLogicalClock(self.physical_time, self.logical_counter + 1, self.node_id)
        else:
            # Received message
            max_pt = max(self.physical_time, other.physical_time, now_ms)

            if max_pt == self.physical_time == other.physical_time:
                new_lc = max(self.logical_counter, other.logical_counter) + 1
            elif max_pt == self.physical_time:
                new_lc = self.logical_counter + 1
            elif max_pt == other.physical_time:
                new_lc = other.logical_counter + 1
            else:
                new_lc = 0

            return HybridLogicalClock(max_pt, new_lc, self.node_id)

    def __lt__(self, other: 'HybridLogicalClock') -> bool:
        if self.physical_time != other.physical_time:
            return self.physical_time < other.physical_time
        if self.logical_counter != other.logical_counter:
            return self.logical_counter < other.logical_counter
        return self.node_id < other.node_id

    def __eq__(self, other: 'HybridLogicalClock') -> bool:
        return (self.physical_time == other.physical_time and
                self.logical_counter == other.logical_counter and
                self.node_id == other.node_id)

    def __hash__(self):
        return hash((self.physical_time, self.logical_counter, self.node_id))

    def to_tuple(self) -> Tuple[int, int, str]:
        return (self.physical_time, self.logical_counter, self.node_id)

    def to_string(self) -> str:
        return f"{self.physical_time}.{self.logical_counter}.{self.node_id}"


# =============================================================================
# CRDT Base Class
# =============================================================================

class CRDT(ABC, Generic[T]):
    """
    Base class for Conflict-free Replicated Data Types.

    Properties:
    - Associative: merge(merge(a, b), c) = merge(a, merge(b, c))
    - Commutative: merge(a, b) = merge(b, a)
    - Idempotent: merge(a, a) = a

    These properties ensure eventual consistency without coordination.
    """

    @abstractmethod
    def value(self) -> T:
        """Get the current value."""
        pass

    @abstractmethod
    def merge(self, other: 'CRDT[T]') -> 'CRDT[T]':
        """Merge with another CRDT instance."""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CRDT[T]':
        """Deserialize from dictionary."""
        pass


# =============================================================================
# G-Counter (Grow-only Counter)
# =============================================================================

@dataclass
class GCounter(CRDT[int]):
    """
    Grow-only Counter CRDT.

    Use cases:
    - Production counts
    - Part completion counts
    - Event counters

    Each node has its own counter that can only increment.
    Total value is sum of all node counters.
    """
    counters: Dict[str, int] = field(default_factory=dict)
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def value(self) -> int:
        """Get total count across all nodes."""
        return sum(self.counters.values())

    def increment(self, amount: int = 1) -> 'GCounter':
        """Increment counter for this node."""
        if amount < 0:
            raise ValueError("G-Counter can only increment")
        new_counters = self.counters.copy()
        new_counters[self.node_id] = new_counters.get(self.node_id, 0) + amount
        return GCounter(counters=new_counters, node_id=self.node_id)

    def merge(self, other: 'GCounter') -> 'GCounter':
        """Merge by taking max of each node's counter."""
        merged = {}
        all_nodes = set(self.counters.keys()) | set(other.counters.keys())
        for node in all_nodes:
            merged[node] = max(
                self.counters.get(node, 0),
                other.counters.get(node, 0)
            )
        return GCounter(counters=merged, node_id=self.node_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'GCounter',
            'counters': self.counters,
            'node_id': self.node_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GCounter':
        return cls(
            counters=data.get('counters', {}),
            node_id=data.get('node_id', str(uuid.uuid4())[:8])
        )


# =============================================================================
# PN-Counter (Positive-Negative Counter)
# =============================================================================

@dataclass
class PNCounter(CRDT[int]):
    """
    Positive-Negative Counter CRDT.

    Use cases:
    - Inventory levels (can increase/decrease)
    - Work-in-progress counts
    - Resource availability

    Implemented as two G-Counters: one for increments, one for decrements.
    """
    positive: GCounter = field(default_factory=GCounter)
    negative: GCounter = field(default_factory=GCounter)

    def value(self) -> int:
        """Get net count (positive - negative)."""
        return self.positive.value() - self.negative.value()

    def increment(self, amount: int = 1) -> 'PNCounter':
        """Increment the counter."""
        return PNCounter(
            positive=self.positive.increment(amount),
            negative=self.negative
        )

    def decrement(self, amount: int = 1) -> 'PNCounter':
        """Decrement the counter."""
        return PNCounter(
            positive=self.positive,
            negative=self.negative.increment(amount)
        )

    def merge(self, other: 'PNCounter') -> 'PNCounter':
        """Merge both positive and negative counters."""
        return PNCounter(
            positive=self.positive.merge(other.positive),
            negative=self.negative.merge(other.negative)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'PNCounter',
            'positive': self.positive.to_dict(),
            'negative': self.negative.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PNCounter':
        return cls(
            positive=GCounter.from_dict(data.get('positive', {})),
            negative=GCounter.from_dict(data.get('negative', {}))
        )


# =============================================================================
# LWW-Register (Last-Writer-Wins Register)
# =============================================================================

@dataclass
class LWWRegister(CRDT[T], Generic[T]):
    """
    Last-Writer-Wins Register CRDT.

    Use cases:
    - Sensor values (temperature, position)
    - Machine status
    - Configuration settings

    Concurrent writes resolved by timestamp; latest write wins.
    Uses Hybrid Logical Clock for consistent ordering.
    """
    _value: T = None
    timestamp: HybridLogicalClock = None
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = HybridLogicalClock.now(self.node_id)

    def value(self) -> T:
        """Get current value."""
        return self._value

    def set(self, new_value: T) -> 'LWWRegister[T]':
        """Set a new value with updated timestamp."""
        return LWWRegister(
            _value=new_value,
            timestamp=self.timestamp.update(),
            node_id=self.node_id
        )

    def merge(self, other: 'LWWRegister[T]') -> 'LWWRegister[T]':
        """Merge by keeping value with later timestamp."""
        if other.timestamp > self.timestamp:
            return LWWRegister(
                _value=other._value,
                timestamp=other.timestamp,
                node_id=self.node_id
            )
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'LWWRegister',
            'value': self._value,
            'timestamp': self.timestamp.to_tuple(),
            'node_id': self.node_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LWWRegister':
        ts_tuple = data.get('timestamp', (0, 0, ''))
        return cls(
            _value=data.get('value'),
            timestamp=HybridLogicalClock(*ts_tuple),
            node_id=data.get('node_id', str(uuid.uuid4())[:8])
        )


# =============================================================================
# OR-Set (Observed-Remove Set)
# =============================================================================

@dataclass
class ORSet(CRDT[Set[T]], Generic[T]):
    """
    Observed-Remove Set CRDT.

    Use cases:
    - Active equipment set
    - Current defects list
    - Pending operations

    Allows both add and remove. Add wins over concurrent remove
    of the same element.
    """
    elements: Dict[T, Set[Tuple[str, int]]] = field(default_factory=dict)  # value -> set of (node_id, counter)
    tombstones: Dict[T, Set[Tuple[str, int]]] = field(default_factory=dict)  # removed elements
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    _counter: int = field(default=0)

    def value(self) -> Set[T]:
        """Get current set of elements."""
        result = set()
        for elem, tags in self.elements.items():
            # Element is present if it has tags not in tombstones
            removed_tags = self.tombstones.get(elem, set())
            if tags - removed_tags:
                result.add(elem)
        return result

    def add(self, element: T) -> 'ORSet[T]':
        """Add an element to the set."""
        new_elements = {k: v.copy() for k, v in self.elements.items()}
        new_counter = self._counter + 1
        tag = (self.node_id, new_counter)

        if element not in new_elements:
            new_elements[element] = set()
        new_elements[element].add(tag)

        return ORSet(
            elements=new_elements,
            tombstones={k: v.copy() for k, v in self.tombstones.items()},
            node_id=self.node_id,
            _counter=new_counter
        )

    def remove(self, element: T) -> 'ORSet[T]':
        """Remove an element from the set."""
        if element not in self.elements:
            return self

        new_tombstones = {k: v.copy() for k, v in self.tombstones.items()}
        if element not in new_tombstones:
            new_tombstones[element] = set()

        # Add all current tags to tombstones
        new_tombstones[element].update(self.elements.get(element, set()))

        return ORSet(
            elements={k: v.copy() for k, v in self.elements.items()},
            tombstones=new_tombstones,
            node_id=self.node_id,
            _counter=self._counter
        )

    def merge(self, other: 'ORSet[T]') -> 'ORSet[T]':
        """Merge by combining elements and tombstones."""
        # Merge elements
        merged_elements = {}
        all_keys = set(self.elements.keys()) | set(other.elements.keys())
        for key in all_keys:
            merged_elements[key] = (
                self.elements.get(key, set()) |
                other.elements.get(key, set())
            )

        # Merge tombstones
        merged_tombstones = {}
        all_tomb_keys = set(self.tombstones.keys()) | set(other.tombstones.keys())
        for key in all_tomb_keys:
            merged_tombstones[key] = (
                self.tombstones.get(key, set()) |
                other.tombstones.get(key, set())
            )

        return ORSet(
            elements=merged_elements,
            tombstones=merged_tombstones,
            node_id=self.node_id,
            _counter=max(self._counter, other._counter)
        )

    def contains(self, element: T) -> bool:
        """Check if element is in the set."""
        return element in self.value()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'ORSet',
            'elements': {str(k): list(v) for k, v in self.elements.items()},
            'tombstones': {str(k): list(v) for k, v in self.tombstones.items()},
            'node_id': self.node_id,
            'counter': self._counter
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ORSet':
        elements = {k: set(tuple(t) for t in v) for k, v in data.get('elements', {}).items()}
        tombstones = {k: set(tuple(t) for t in v) for k, v in data.get('tombstones', {}).items()}
        return cls(
            elements=elements,
            tombstones=tombstones,
            node_id=data.get('node_id', str(uuid.uuid4())[:8]),
            _counter=data.get('counter', 0)
        )


# =============================================================================
# MV-Register (Multi-Value Register)
# =============================================================================

@dataclass
class MVRegister(CRDT[List[T]], Generic[T]):
    """
    Multi-Value Register CRDT.

    Use cases:
    - Concurrent sensor readings
    - Multiple conflicting updates
    - Tracking all divergent values

    Preserves all concurrent values; application decides how to resolve.
    """
    values: Dict[Tuple[str, int], T] = field(default_factory=dict)  # (node_id, counter) -> value
    vector_clock: Dict[str, int] = field(default_factory=dict)
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def value(self) -> List[T]:
        """Get all concurrent values."""
        return list(self.values.values())

    def set(self, new_value: T) -> 'MVRegister[T]':
        """Set a new value, replacing all concurrent values from this node."""
        new_vc = self.vector_clock.copy()
        new_vc[self.node_id] = new_vc.get(self.node_id, 0) + 1

        # Remove values dominated by new vector clock
        new_values = {}
        for (node, counter), val in self.values.items():
            if counter > new_vc.get(node, 0):
                new_values[(node, counter)] = val

        # Add new value
        new_values[(self.node_id, new_vc[self.node_id])] = new_value

        return MVRegister(
            values=new_values,
            vector_clock=new_vc,
            node_id=self.node_id
        )

    def merge(self, other: 'MVRegister[T]') -> 'MVRegister[T]':
        """Merge by keeping all concurrent values."""
        # Merge vector clocks
        merged_vc = self.vector_clock.copy()
        for node, counter in other.vector_clock.items():
            merged_vc[node] = max(merged_vc.get(node, 0), counter)

        # Merge values, keeping those not dominated
        merged_values = {}

        for (node, counter), val in self.values.items():
            if counter >= other.vector_clock.get(node, 0):
                merged_values[(node, counter)] = val

        for (node, counter), val in other.values.items():
            if counter >= self.vector_clock.get(node, 0):
                merged_values[(node, counter)] = val

        return MVRegister(
            values=merged_values,
            vector_clock=merged_vc,
            node_id=self.node_id
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'MVRegister',
            'values': {f"{k[0]}:{k[1]}": v for k, v in self.values.items()},
            'vector_clock': self.vector_clock,
            'node_id': self.node_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MVRegister':
        values = {}
        for k, v in data.get('values', {}).items():
            node, counter = k.rsplit(':', 1)
            values[(node, int(counter))] = v
        return cls(
            values=values,
            vector_clock=data.get('vector_clock', {}),
            node_id=data.get('node_id', str(uuid.uuid4())[:8])
        )


# =============================================================================
# CRDT State Container
# =============================================================================

@dataclass
class CRDTState:
    """
    Container for multiple CRDT fields representing digital twin state.

    Designed for manufacturing digital twin:
    - Equipment status (LWW-Register)
    - Production counts (G-Counter)
    - Inventory levels (PN-Counter)
    - Active equipment set (OR-Set)
    - Sensor readings (MV-Register for conflicts)
    """
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    fields: Dict[str, CRDT] = field(default_factory=dict)
    _field_timestamps: Dict[str, 'HybridLogicalClock'] = field(default_factory=dict)

    def set_counter(self, name: str, value: int = 0) -> 'CRDTState':
        """Initialize or get a G-Counter field."""
        if name not in self.fields:
            counter = GCounter(node_id=self.node_id)
            if value > 0:
                counter = counter.increment(value)
            self.fields[name] = counter
        return self

    def set_pn_counter(self, name: str, value: int = 0) -> 'CRDTState':
        """Initialize or get a PN-Counter field."""
        if name not in self.fields:
            counter = PNCounter(
                positive=GCounter(node_id=self.node_id),
                negative=GCounter(node_id=self.node_id)
            )
            if value > 0:
                counter = counter.increment(value)
            elif value < 0:
                counter = counter.decrement(-value)
            self.fields[name] = counter
        return self

    def set_register(self, name: str, value: Any = None) -> 'CRDTState':
        """Initialize or get a LWW-Register field."""
        if name not in self.fields:
            self.fields[name] = LWWRegister(_value=value, node_id=self.node_id)
        return self

    def set_set(self, name: str, elements: Set = None) -> 'CRDTState':
        """Initialize or get an OR-Set field."""
        if name not in self.fields:
            orset = ORSet(node_id=self.node_id)
            for elem in (elements or set()):
                orset = orset.add(elem)
            self.fields[name] = orset
        return self

    def get(self, name: str) -> Any:
        """Get the value of a CRDT field."""
        if name in self.fields:
            return self.fields[name].value()
        return None

    def update_counter(self, name: str, amount: int = 1, clock: 'HybridLogicalClock' = None) -> 'CRDTState':
        """Increment a G-Counter field."""
        if name in self.fields and isinstance(self.fields[name], GCounter):
            self.fields[name] = self.fields[name].increment(amount)
            if clock:
                self._field_timestamps[name] = clock
        return self

    def update_pn_counter(self, name: str, amount: int, clock: 'HybridLogicalClock' = None) -> 'CRDTState':
        """Update a PN-Counter field (positive = increment, negative = decrement)."""
        if name in self.fields and isinstance(self.fields[name], PNCounter):
            if amount > 0:
                self.fields[name] = self.fields[name].increment(amount)
            elif amount < 0:
                self.fields[name] = self.fields[name].decrement(-amount)
            if clock:
                self._field_timestamps[name] = clock
        return self

    def update_register(self, name: str, value: Any, clock: 'HybridLogicalClock' = None) -> 'CRDTState':
        """Update a LWW-Register field."""
        if name in self.fields and isinstance(self.fields[name], LWWRegister):
            self.fields[name] = self.fields[name].set(value)
            if clock:
                self._field_timestamps[name] = clock
        return self

    def add_to_set(self, name: str, element: Any, clock: 'HybridLogicalClock' = None) -> 'CRDTState':
        """Add an element to an OR-Set field."""
        if name in self.fields and isinstance(self.fields[name], ORSet):
            self.fields[name] = self.fields[name].add(element)
            if clock:
                self._field_timestamps[name] = clock
        return self

    def remove_from_set(self, name: str, element: Any, clock: 'HybridLogicalClock' = None) -> 'CRDTState':
        """Remove an element from an OR-Set field."""
        if name in self.fields and isinstance(self.fields[name], ORSet):
            self.fields[name] = self.fields[name].remove(element)
            if clock:
                self._field_timestamps[name] = clock
        return self

    def merge(self, other: 'CRDTState') -> 'CRDTState':
        """Merge all CRDT fields with another state."""
        merged = CRDTState(node_id=self.node_id)

        all_fields = set(self.fields.keys()) | set(other.fields.keys())
        for name in all_fields:
            if name in self.fields and name in other.fields:
                merged.fields[name] = self.fields[name].merge(other.fields[name])
            elif name in self.fields:
                merged.fields[name] = self.fields[name]
            else:
                merged.fields[name] = other.fields[name]

        return merged

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'node_id': self.node_id,
            'fields': {name: crdt.to_dict() for name, crdt in self.fields.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CRDTState':
        """Deserialize from dictionary."""
        state = cls(node_id=data.get('node_id', str(uuid.uuid4())[:8]))

        type_map = {
            'GCounter': GCounter,
            'PNCounter': PNCounter,
            'LWWRegister': LWWRegister,
            'ORSet': ORSet,
            'MVRegister': MVRegister
        }

        for name, crdt_data in data.get('fields', {}).items():
            crdt_type = crdt_data.get('type')
            if crdt_type in type_map:
                state.fields[name] = type_map[crdt_type].from_dict(crdt_data)

        return state


# =============================================================================
# CRDT Conflict Resolver
# =============================================================================

class CRDTConflictResolver:
    """
    Conflict-free Replicated Data Type Conflict Resolver.

    Provides:
    - CRDT state management for digital twins
    - Automatic conflict resolution
    - Sync protocol for edge-cloud communication
    - Merge operations for concurrent updates

    Research Features:
    - Manufacturing-specific CRDT types
    - Hybrid logical clocks for ordering
    - Delta-based synchronization
    """

    def __init__(self, node_id: str = None):
        """
        Initialize conflict resolver.

        Args:
            node_id: Unique identifier for this node (edge device, cloud, etc.)
        """
        self.node_id = node_id or str(uuid.uuid4())[:8]
        self.clock = HybridLogicalClock.now(self.node_id)
        self._states: Dict[str, CRDTState] = {}
        self._pending_syncs: List[Tuple[str, Dict[str, Any]]] = []

    # -------------------------------------------------------------------------
    # State Management
    # -------------------------------------------------------------------------

    def create_twin_state(self, twin_id: str) -> CRDTState:
        """
        Create a new CRDT state for a digital twin.

        Args:
            twin_id: Unique identifier for the digital twin

        Returns:
            New CRDTState instance
        """
        state = CRDTState(node_id=self.node_id)

        # Initialize common manufacturing fields
        state.set_counter('production_count')
        state.set_pn_counter('inventory_level')
        state.set_register('status', 'unknown')
        state.set_register('last_update', datetime.utcnow().isoformat())
        state.set_set('active_alarms')
        state.set_set('active_operations')

        self._states[twin_id] = state
        logger.info(f"Created CRDT state for twin: {twin_id}")
        return state

    def get_state(self, twin_id: str) -> Optional[CRDTState]:
        """Get state for a digital twin."""
        return self._states.get(twin_id)

    def update_state(
        self,
        twin_id: str,
        updates: Dict[str, Any]
    ) -> Optional[CRDTState]:
        """
        Apply updates to a digital twin state.

        Args:
            twin_id: Digital twin identifier
            updates: Dictionary of field updates:
                - counters: {name: increment_amount}
                - registers: {name: new_value}
                - sets: {name: {'add': [...], 'remove': [...]}}

        Returns:
            Updated CRDTState
        """
        state = self._states.get(twin_id)
        if not state:
            logger.warning(f"State not found for twin: {twin_id}")
            return None

        # Update clock
        self.clock = self.clock.update()

        # Apply counter updates
        for name, amount in updates.get('counters', {}).items():
            if isinstance(state.fields.get(name), GCounter):
                state.update_counter(name, amount, clock=self.clock)
            elif isinstance(state.fields.get(name), PNCounter):
                state.update_pn_counter(name, amount, clock=self.clock)

        # Apply register updates
        for name, value in updates.get('registers', {}).items():
            state.update_register(name, value, clock=self.clock)

        # Apply set updates
        for name, ops in updates.get('sets', {}).items():
            for elem in ops.get('add', []):
                state.add_to_set(name, elem, clock=self.clock)
            for elem in ops.get('remove', []):
                state.remove_from_set(name, elem, clock=self.clock)

        # Update timestamp
        state.update_register('last_update', datetime.utcnow().isoformat(), clock=self.clock)

        return state

    # -------------------------------------------------------------------------
    # Synchronization
    # -------------------------------------------------------------------------

    def prepare_sync(self, twin_id: str) -> Optional[Dict[str, Any]]:
        """
        Prepare state for synchronization.

        Returns:
            Serialized state for transmission
        """
        state = self._states.get(twin_id)
        if not state:
            return None

        return {
            'twin_id': twin_id,
            'node_id': self.node_id,
            'clock': self.clock.to_tuple(),
            'state': state.to_dict()
        }

    def receive_sync(self, sync_data: Dict[str, Any]) -> Optional[CRDTState]:
        """
        Receive and merge synchronized state.

        Args:
            sync_data: Serialized state from another node

        Returns:
            Merged CRDTState
        """
        twin_id = sync_data.get('twin_id')
        remote_clock = HybridLogicalClock(*sync_data.get('clock', (0, 0, '')))
        remote_state = CRDTState.from_dict(sync_data.get('state', {}))

        # Update local clock
        self.clock = self.clock.update(remote_clock)

        # Get or create local state
        local_state = self._states.get(twin_id)
        if not local_state:
            self._states[twin_id] = remote_state
            return remote_state

        # Merge states
        merged_state = local_state.merge(remote_state)
        self._states[twin_id] = merged_state

        logger.info(f"Merged state from node {sync_data.get('node_id')} for twin {twin_id}")
        return merged_state

    def get_delta(
        self,
        twin_id: str,
        since_clock: HybridLogicalClock
    ) -> Optional[Dict[str, Any]]:
        """
        Get state delta since a given clock time.

        For bandwidth-efficient synchronization.

        Args:
            twin_id: Digital twin identifier
            since_clock: Last known clock from remote

        Returns:
            Delta state for transmission with only changed fields
        """
        state = self._states.get(twin_id)
        if not state:
            return None

        # Get field timestamps for delta tracking
        field_timestamps = getattr(state, '_field_timestamps', {})

        # Build delta with only fields updated since the given clock
        delta_fields = {}
        for name, crdt in state.fields.items():
            field_clock = field_timestamps.get(name)
            # Include field if no timestamp (new field) or if updated after since_clock
            if field_clock is None or field_clock > since_clock:
                delta_fields[name] = crdt.to_dict()

        # If no changes, return None to indicate no delta needed
        if not delta_fields:
            return None

        return {
            'twin_id': twin_id,
            'node_id': self.node_id,
            'clock': {
                'physical_time': self.clock.physical_time,
                'logical_counter': self.clock.logical_counter,
                'node_id': self.clock.node_id
            },
            'is_delta': True,
            'state': {
                'node_id': state.node_id,
                'fields': delta_fields
            }
        }

    # -------------------------------------------------------------------------
    # Conflict Detection (for monitoring)
    # -------------------------------------------------------------------------

    def detect_conflicts(self, twin_id: str) -> List[Dict[str, Any]]:
        """
        Detect fields with concurrent values (for MV-Register).

        Returns:
            List of fields with multiple concurrent values
        """
        state = self._states.get(twin_id)
        if not state:
            return []

        conflicts = []
        for name, crdt in state.fields.items():
            if isinstance(crdt, MVRegister):
                values = crdt.value()
                if len(values) > 1:
                    conflicts.append({
                        'field': name,
                        'values': values,
                        'count': len(values)
                    })

        return conflicts

    def resolve_mv_register(
        self,
        twin_id: str,
        field_name: str,
        resolution_value: Any
    ) -> bool:
        """
        Manually resolve a multi-value register conflict.

        Args:
            twin_id: Digital twin identifier
            field_name: Field name
            resolution_value: Value to set as resolved

        Returns:
            True if resolved
        """
        state = self._states.get(twin_id)
        if not state or field_name not in state.fields:
            return False

        field = state.fields[field_name]
        if isinstance(field, MVRegister):
            state.fields[field_name] = field.set(resolution_value)
            return True

        return False

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        """Get resolver statistics."""
        return {
            'node_id': self.node_id,
            'clock': self.clock.to_string(),
            'twin_count': len(self._states),
            'pending_syncs': len(self._pending_syncs),
            'twins': list(self._states.keys())
        }
