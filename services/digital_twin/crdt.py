"""
ISO 23247 CRDT (Conflict-free Replicated Data Types) Implementation
===================================================================

Implements CRDTs for automatic conflict resolution in distributed digital twins.
Part of ISO 23247-4 Information Exchange compliance.

CRDTs provide mathematically guaranteed eventual consistency without coordination.
Unlike vector clocks which detect conflicts, CRDTs are designed so that conflicts
are impossible - any order of merge operations produces the same final result.

Key CRDT Types Implemented:

    Counters:
        GCounter - Grow-only counter (increments only)
        PNCounter - Positive-Negative counter (increments and decrements)

    Registers:
        LWWRegister - Last-Writer-Wins register (single value with timestamp)
        MVRegister - Multi-Value register (keeps all concurrent values)

    Sets:
        GSet - Grow-only set (additions only)
        ORSet - Observed-Remove set (additions and removals)

    Maps:
        LWWMap - Last-Writer-Wins map (key-value pairs with timestamps)

Mathematical Properties:
    All CRDTs satisfy the following properties ensuring eventual consistency:

    1. Commutativity: merge(A, B) = merge(B, A)
       Order of merging doesn't matter.

    2. Associativity: merge(merge(A, B), C) = merge(A, merge(B, C))
       Grouping of merges doesn't matter.

    3. Idempotency: merge(A, A) = A
       Merging with self has no effect.

ISO 23247 Compliance:
    Part 4, Section 6.2: Distributed state synchronization
    Part 4, Section 6.3: Eventual consistency requirements
    Part 4, Section 7.1: Automatic conflict resolution

Example:
    >>> from services.digital_twin.crdt import CRDTState, PNCounter
    >>>
    >>> # Create CRDT state for a machine
    >>> state = CRDTState(entity_id="machine_001", node_id="controller_1")
    >>>
    >>> # Update position (LWW semantics)
    >>> state.position.set("x", 100.0)
    >>> state.position.set("y", 200.0)
    >>>
    >>> # Track part counts (counter semantics)
    >>> state.counters["parts_produced"] = PNCounter(node_id="controller_1")
    >>> state.counters["parts_produced"].increment(5)
    >>>
    >>> # Merge with remote state (always succeeds, no conflicts)
    >>> merged = state.merge(remote_state)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Set, List, Tuple, TypeVar, Generic
from datetime import datetime
import json
import copy


T = TypeVar('T')


class CRDT(ABC, Generic[T]):
    """
    Abstract base class for all CRDT types.

    All CRDTs must implement three core operations:
    - value(): Extract the current value from the CRDT state
    - merge(): Combine two CRDT instances into one (commutative, associative, idempotent)
    - to_dict(): Serialize for network transmission or storage

    Type Parameters:
        T: The type of value this CRDT represents (int, Set, Dict, etc.)
    """

    @abstractmethod
    def value(self) -> T:
        """
        Get the current value represented by this CRDT.

        Returns:
            The current value, type depends on CRDT implementation.
        """
        pass

    @abstractmethod
    def merge(self, other: 'CRDT[T]') -> 'CRDT[T]':
        """
        Merge with another CRDT instance of the same type.

        This operation must be:
        - Commutative: merge(A, B) = merge(B, A)
        - Associative: merge(merge(A, B), C) = merge(A, merge(B, C))
        - Idempotent: merge(A, A) = A

        Args:
            other: Another CRDT instance to merge with.

        Returns:
            A new CRDT representing the merged state.
        """
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the CRDT state to a dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        pass


@dataclass
class GCounter(CRDT[int]):
    """
    Grow-only Counter CRDT.

    Each node maintains its own counter that only increments. The total value
    is the sum of all node counters. This design allows any node to increment
    without coordination, and merges always succeed by taking the maximum
    of each node's counter.

    Use cases in manufacturing:
        - Part counts (total parts produced)
        - Cycle counts (machine cycles completed)
        - Event counters (alarms triggered, jobs started)
        - OEE metrics (total good units, total defects)

    Merge semantics:
        For each node, take max(local_count, remote_count). This ensures
        we never lose increments, even if updates arrive out of order.

    Attributes:
        counts: Dictionary mapping node_id to that node's counter value.
        node_id: The identifier of the node that owns this counter instance.

    Example:
        >>> counter = GCounter(node_id="plc_1")
        >>> counter.increment(5)  # Node plc_1 increments by 5
        >>> counter.value()       # Returns 5
        >>>
        >>> # Remote node has incremented too
        >>> remote = GCounter(counts={"plc_2": 3}, node_id="plc_2")
        >>> merged = counter.merge(remote)
        >>> merged.value()        # Returns 8 (5 + 3)
    """

    counts: Dict[str, int] = field(default_factory=dict)
    node_id: str = ""

    def value(self) -> int:
        """
        Get total count across all nodes.

        Returns:
            Sum of all node counters.
        """
        return sum(self.counts.values())

    def increment(self, amount: int = 1) -> 'GCounter':
        """Increment this node's counter."""
        if self.node_id:
            self.counts[self.node_id] = self.counts.get(self.node_id, 0) + amount
        return self

    def merge(self, other: 'GCounter') -> 'GCounter':
        """Merge by taking max of each node's counter."""
        all_nodes = set(self.counts.keys()) | set(other.counts.keys())
        merged_counts = {}
        for node in all_nodes:
            merged_counts[node] = max(
                self.counts.get(node, 0),
                other.counts.get(node, 0)
            )
        return GCounter(counts=merged_counts, node_id=self.node_id)

    def to_dict(self) -> Dict[str, Any]:
        return {'type': 'GCounter', 'counts': self.counts, 'node_id': self.node_id}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GCounter':
        return cls(counts=data.get('counts', {}), node_id=data.get('node_id', ''))


@dataclass
class PNCounter(CRDT[int]):
    """
    Positive-Negative Counter CRDT.

    Supports both increment and decrement operations by internally using
    two GCounters: one for increments (positive) and one for decrements
    (negative). The value is positive.value() - negative.value().

    Use cases in manufacturing:
        - Inventory levels (parts added vs consumed)
        - Queue lengths (jobs added vs completed)
        - Available capacity (allocated vs released)
        - WIP counts (started vs finished)

    Why two counters?
        A single counter with subtract would violate commutativity. Example:
        Node A: counter = 5, increment(3) -> 8
        Node B: counter = 5, decrement(2) -> 3
        Merge problem: Which is correct? 8 or 3?

        With PNCounter:
        Node A: positive +3 -> {A:3}
        Node B: negative +2 -> {B:2}
        Merge: positive={A:3}, negative={B:2} -> value = 3 - 2 = 1
        Plus original 5 = 6 (5 + 3 - 2)

    Attributes:
        positive: GCounter for increment operations.
        negative: GCounter for decrement operations.
        node_id: The identifier of the node that owns this counter.

    Example:
        >>> inventory = PNCounter(node_id="warehouse_1")
        >>> inventory.increment(100)  # Received 100 parts
        >>> inventory.decrement(25)   # Used 25 parts
        >>> inventory.value()         # Returns 75
    """

    positive: GCounter = field(default_factory=GCounter)
    negative: GCounter = field(default_factory=GCounter)
    node_id: str = ""

    def __post_init__(self):
        """Initialize node_id on internal counters."""
        self.positive.node_id = self.node_id
        self.negative.node_id = self.node_id

    def value(self) -> int:
        """
        Get net count (positive increments minus decrements).

        Returns:
            The difference: positive.value() - negative.value()
        """
        return self.positive.value() - self.negative.value()

    def increment(self, amount: int = 1) -> 'PNCounter':
        """Increment the counter."""
        self.positive.increment(amount)
        return self

    def decrement(self, amount: int = 1) -> 'PNCounter':
        """Decrement the counter."""
        self.negative.increment(amount)
        return self

    def merge(self, other: 'PNCounter') -> 'PNCounter':
        """Merge by merging both internal counters."""
        return PNCounter(
            positive=self.positive.merge(other.positive),
            negative=self.negative.merge(other.negative),
            node_id=self.node_id
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'PNCounter',
            'positive': self.positive.to_dict(),
            'negative': self.negative.to_dict(),
            'node_id': self.node_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PNCounter':
        return cls(
            positive=GCounter.from_dict(data.get('positive', {})),
            negative=GCounter.from_dict(data.get('negative', {})),
            node_id=data.get('node_id', '')
        )


@dataclass
class LWWRegister(CRDT[T], Generic[T]):
    """
    Last-Writer-Wins Register CRDT.

    Stores a single value with a timestamp. When concurrent writes occur,
    the value with the later timestamp wins. This provides a simple and
    predictable conflict resolution for single-value state.

    Use cases in manufacturing:
        - Machine status (running, stopped, error)
        - Current position (X, Y, Z coordinates)
        - Active job ID (currently executing job)
        - Setpoints (temperature, speed, pressure)

    Trade-offs:
        Pros:
        - Simple semantics, easy to reason about
        - Always converges to a single value
        - Low overhead (just value + timestamp)

        Cons:
        - May lose updates if timestamps are close
        - Requires reasonably synchronized clocks
        - Not suitable for counters or sets

    Clock Requirements:
        Timestamps should be from a reasonably synchronized source.
        Small clock drift is acceptable as long as the most recent
        update generally has the highest timestamp.

    Attributes:
        _value: The stored value.
        timestamp: Unix timestamp (seconds with microseconds) of last write.
        node_id: The identifier of the node that owns this register.

    Example:
        >>> status = LWWRegister(node_id="controller_1")
        >>> status.set("running")   # Automatically uses current time
        >>> status.value()          # Returns "running"
        >>>
        >>> # Later update wins
        >>> status.set("stopped")
        >>> status.value()          # Returns "stopped"
    """

    _value: Optional[T] = None
    timestamp: float = 0.0  # Unix timestamp with microseconds
    node_id: str = ""

    def value(self) -> Optional[T]:
        """
        Get the current value.

        Returns:
            The stored value, or None if never set.
        """
        return self._value

    def set(self, value: T, timestamp: Optional[float] = None) -> 'LWWRegister[T]':
        """Set the value with optional timestamp."""
        ts = timestamp if timestamp is not None else datetime.utcnow().timestamp()
        if ts > self.timestamp:
            self._value = value
            self.timestamp = ts
        return self

    def merge(self, other: 'LWWRegister[T]') -> 'LWWRegister[T]':
        """Merge by keeping value with later timestamp."""
        if other.timestamp > self.timestamp:
            return LWWRegister(
                _value=other._value,
                timestamp=other.timestamp,
                node_id=self.node_id
            )
        return LWWRegister(
            _value=self._value,
            timestamp=self.timestamp,
            node_id=self.node_id
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'LWWRegister',
            'value': self._value,
            'timestamp': self.timestamp,
            'node_id': self.node_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LWWRegister':
        return cls(
            _value=data.get('value'),
            timestamp=data.get('timestamp', 0.0),
            node_id=data.get('node_id', '')
        )


@dataclass
class MVRegister(CRDT[Set[T]], Generic[T]):
    """
    Multi-Value Register CRDT.

    Keeps all concurrent values instead of picking one.
    Useful when conflicts need human resolution.

    Use cases:
    - Conflicting status updates
    - Pending approvals
    - Multi-source sensor readings
    """

    values: Dict[str, Tuple[T, float]] = field(default_factory=dict)  # node_id -> (value, timestamp)
    node_id: str = ""

    def value(self) -> Set[T]:
        """Get all current values."""
        return {v for v, _ in self.values.values()}

    def set(self, value: T, timestamp: Optional[float] = None) -> 'MVRegister[T]':
        """Set value for this node."""
        ts = timestamp if timestamp is not None else datetime.utcnow().timestamp()
        if self.node_id:
            self.values[self.node_id] = (value, ts)
        return self

    def merge(self, other: 'MVRegister[T]') -> 'MVRegister[T]':
        """Merge by keeping values from both, taking latest per node."""
        merged = dict(self.values)
        for node, (value, ts) in other.values.items():
            if node not in merged or ts > merged[node][1]:
                merged[node] = (value, ts)
        return MVRegister(values=merged, node_id=self.node_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'MVRegister',
            'values': {k: list(v) for k, v in self.values.items()},
            'node_id': self.node_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MVRegister':
        values = {k: tuple(v) for k, v in data.get('values', {}).items()}
        return cls(values=values, node_id=data.get('node_id', ''))


@dataclass
class GSet(CRDT[Set[T]], Generic[T]):
    """
    Grow-only Set CRDT.

    Elements can only be added, never removed.

    Use cases:
    - Completed jobs
    - Alarm history
    - Event log entries
    """

    elements: Set[T] = field(default_factory=set)

    def value(self) -> Set[T]:
        """Get all elements."""
        return self.elements.copy()

    def add(self, element: T) -> 'GSet[T]':
        """Add an element."""
        self.elements.add(element)
        return self

    def contains(self, element: T) -> bool:
        """Check if element exists."""
        return element in self.elements

    def merge(self, other: 'GSet[T]') -> 'GSet[T]':
        """Merge by union."""
        return GSet(elements=self.elements | other.elements)

    def to_dict(self) -> Dict[str, Any]:
        return {'type': 'GSet', 'elements': list(self.elements)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GSet':
        return cls(elements=set(data.get('elements', [])))


@dataclass
class ORSet(CRDT[Set[T]], Generic[T]):
    """
    Observed-Remove Set CRDT (Add-Remove Set).

    Supports both add and remove operations through a tag-based mechanism.
    Each addition creates a unique tag (node_id, counter). Removal tombstones
    all observed tags for an element, but new adds after remove create new tags.

    Semantics: "Add wins over concurrent remove"
        If node A adds element X while node B removes it, X remains in the set.
        This is because B can only tombstone tags it has observed, not future tags.

    Use cases in manufacturing:
        - Active alarms (raised and acknowledged)
        - Connected devices (online/offline)
        - Current work orders (assigned and completed)
        - Active faults (detected and cleared)

    How it works:
        1. Add: Create new unique tag (node_id, counter) for element
        2. Remove: Tombstone all currently observed tags for element
        3. Value: Element is active if it has any non-tombstoned tags
        4. Merge: Union elements, union tombstones

    Example scenario:
        Node A adds alarm "TEMP_HIGH" -> tags: {("A", 1)}
        Node B observes, then removes -> tombstones: {("A", 1)}
        Node A re-adds alarm -> tags: {("A", 1), ("A", 2)}
        Merged value: "TEMP_HIGH" is active (tag ("A", 2) not tombstoned)

    Attributes:
        elements: Map of element to its set of (node_id, counter) tags.
        tombstones: Map of element to its tombstoned tags.
        node_id: The identifier of the node that owns this set.
        counter: Monotonic counter for generating unique tags.

    Example:
        >>> alarms = ORSet(node_id="scada_1")
        >>> alarms.add("TEMP_HIGH")
        >>> alarms.add("PRESSURE_LOW")
        >>> alarms.contains("TEMP_HIGH")  # Returns True
        >>> alarms.remove("TEMP_HIGH")    # Acknowledge alarm
        >>> alarms.contains("TEMP_HIGH")  # Returns False
        >>> list(alarms.value())          # Returns ["PRESSURE_LOW"]
    """

    # element -> set of (node_id, counter) tags
    elements: Dict[T, Set[Tuple[str, int]]] = field(default_factory=dict)
    tombstones: Dict[T, Set[Tuple[str, int]]] = field(default_factory=dict)
    node_id: str = ""
    counter: int = 0

    def value(self) -> Set[T]:
        """
        Get all active (non-removed) elements.

        An element is active if it has at least one tag that is not
        in the tombstones set.

        Returns:
            Set of currently active elements.
        """
        result = set()
        for elem, tags in self.elements.items():
            # Element is active if it has tags not in tombstones
            dead_tags = self.tombstones.get(elem, set())
            if tags - dead_tags:
                result.add(elem)
        return result

    def add(self, element: T) -> 'ORSet[T]':
        """Add an element with a unique tag."""
        self.counter += 1
        tag = (self.node_id, self.counter)
        if element not in self.elements:
            self.elements[element] = set()
        self.elements[element].add(tag)
        return self

    def remove(self, element: T) -> 'ORSet[T]':
        """Remove an element by tombstoning all its tags."""
        if element in self.elements:
            if element not in self.tombstones:
                self.tombstones[element] = set()
            self.tombstones[element].update(self.elements[element])
        return self

    def contains(self, element: T) -> bool:
        """Check if element is active."""
        return element in self.value()

    def merge(self, other: 'ORSet[T]') -> 'ORSet[T]':
        """Merge by combining elements and tombstones."""
        # Merge elements
        merged_elements: Dict[T, Set[Tuple[str, int]]] = {}
        all_elems = set(self.elements.keys()) | set(other.elements.keys())
        for elem in all_elems:
            merged_elements[elem] = (
                self.elements.get(elem, set()) |
                other.elements.get(elem, set())
            )

        # Merge tombstones
        merged_tombstones: Dict[T, Set[Tuple[str, int]]] = {}
        all_tombstone_elems = set(self.tombstones.keys()) | set(other.tombstones.keys())
        for elem in all_tombstone_elems:
            merged_tombstones[elem] = (
                self.tombstones.get(elem, set()) |
                other.tombstones.get(elem, set())
            )

        return ORSet(
            elements=merged_elements,
            tombstones=merged_tombstones,
            node_id=self.node_id,
            counter=max(self.counter, other.counter)
        )

    def to_dict(self) -> Dict[str, Any]:
        # Convert sets of tuples to lists for JSON serialization
        elements_serializable = {
            str(k): [list(t) for t in v]
            for k, v in self.elements.items()
        }
        tombstones_serializable = {
            str(k): [list(t) for t in v]
            for k, v in self.tombstones.items()
        }
        return {
            'type': 'ORSet',
            'elements': elements_serializable,
            'tombstones': tombstones_serializable,
            'node_id': self.node_id,
            'counter': self.counter
        }


@dataclass
class LWWMap(CRDT[Dict[str, T]], Generic[T]):
    """
    Last-Writer-Wins Map CRDT.

    Each key has its own LWW register.

    Use cases:
    - Machine state with multiple attributes
    - Sensor readings
    - Configuration parameters
    """

    entries: Dict[str, LWWRegister[T]] = field(default_factory=dict)
    node_id: str = ""

    def value(self) -> Dict[str, T]:
        """Get current map state."""
        return {k: v.value() for k, v in self.entries.items() if v.value() is not None}

    def set(self, key: str, value: T, timestamp: Optional[float] = None) -> 'LWWMap[T]':
        """Set a key-value pair."""
        if key not in self.entries:
            self.entries[key] = LWWRegister(node_id=self.node_id)
        self.entries[key].set(value, timestamp)
        return self

    def get(self, key: str) -> Optional[T]:
        """Get value for a key."""
        if key in self.entries:
            return self.entries[key].value()
        return None

    def merge(self, other: 'LWWMap[T]') -> 'LWWMap[T]':
        """Merge by merging each key's register."""
        all_keys = set(self.entries.keys()) | set(other.entries.keys())
        merged_entries: Dict[str, LWWRegister[T]] = {}

        for key in all_keys:
            self_reg = self.entries.get(key, LWWRegister(node_id=self.node_id))
            other_reg = other.entries.get(key, LWWRegister(node_id=other.node_id))
            merged_entries[key] = self_reg.merge(other_reg)

        return LWWMap(entries=merged_entries, node_id=self.node_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'LWWMap',
            'entries': {k: v.to_dict() for k, v in self.entries.items()},
            'node_id': self.node_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LWWMap':
        entries = {
            k: LWWRegister.from_dict(v)
            for k, v in data.get('entries', {}).items()
        }
        return cls(entries=entries, node_id=data.get('node_id', ''))


@dataclass
class CRDTState:
    """
    Complete CRDT-based state for a digital twin entity.

    Combines multiple CRDTs for different aspects of state.

    ISO 23247 Compliance:
    - Automatic conflict resolution
    - Eventually consistent state
    - No coordination required between nodes
    """

    entity_id: str
    node_id: str

    # Position/numeric state (LWW for latest value)
    position: LWWMap[float] = field(default_factory=lambda: LWWMap())

    # Status (LWW for current status)
    status: LWWRegister[str] = field(default_factory=lambda: LWWRegister())

    # Counters (PN for increment/decrement)
    counters: Dict[str, PNCounter] = field(default_factory=dict)

    # Events/history (GSet for immutable log)
    events: GSet[str] = field(default_factory=GSet)

    # Active items (ORSet for add/remove)
    active_alarms: ORSet[str] = field(default_factory=lambda: ORSet())

    def __post_init__(self):
        self.position.node_id = self.node_id
        self.status.node_id = self.node_id
        self.active_alarms.node_id = self.node_id

    def merge(self, other: 'CRDTState') -> 'CRDTState':
        """Merge with another CRDT state."""
        merged = CRDTState(
            entity_id=self.entity_id,
            node_id=self.node_id
        )

        merged.position = self.position.merge(other.position)
        merged.status = self.status.merge(other.status)
        merged.events = self.events.merge(other.events)
        merged.active_alarms = self.active_alarms.merge(other.active_alarms)

        # Merge counters
        all_counter_keys = set(self.counters.keys()) | set(other.counters.keys())
        for key in all_counter_keys:
            self_counter = self.counters.get(key, PNCounter(node_id=self.node_id))
            other_counter = other.counters.get(key, PNCounter(node_id=other.node_id))
            merged.counters[key] = self_counter.merge(other_counter)

        return merged

    def to_dict(self) -> Dict[str, Any]:
        return {
            'entity_id': self.entity_id,
            'node_id': self.node_id,
            'position': self.position.to_dict(),
            'status': self.status.to_dict(),
            'counters': {k: v.to_dict() for k, v in self.counters.items()},
            'events': self.events.to_dict(),
            'active_alarms': self.active_alarms.to_dict()
        }

    def get_snapshot(self) -> Dict[str, Any]:
        """Get a simple snapshot of current state values."""
        return {
            'entity_id': self.entity_id,
            'position': self.position.value(),
            'status': self.status.value(),
            'counters': {k: v.value() for k, v in self.counters.items()},
            'event_count': len(self.events.value()),
            'active_alarms': list(self.active_alarms.value())
        }
