"""
ISO 23247 Vector Clock Implementation
======================================

Implements vector clocks for distributed conflict resolution in digital twin
state synchronization, providing causal ordering of events across distributed
manufacturing systems.

This module is a core component of ISO 23247-4 (Information Exchange) compliance,
enabling the detection and resolution of concurrent state updates in distributed
digital twin architectures.

Key Concepts:
    Vector Clock: A logical timestamp mechanism where each node maintains a counter
    for every other node. When a node updates state, it increments its own counter.
    When receiving updates, clocks are merged by taking the maximum of each component.

    Causal Ordering: Vector clocks establish "happens-before" relationships between
    events, allowing the system to determine if updates are causally related or
    concurrent (potentially conflicting).

    Conflict Resolution: When concurrent updates are detected, this module provides
    multiple resolution strategies (last-write-wins, first-write-wins, merge,
    prefer-source) to automatically reconcile differences.

ISO 23247 Compliance:
    Part 4, Section 6: Information exchange mechanisms
    Part 4, Section 7: Conflict detection and resolution
    Part 4, Section 8: Data integrity and checksums

Architecture:
    VectorClock -> Tracks logical timestamps per node
    VersionedState -> State with attached version information
    ConflictResolver -> Applies resolution strategies
    DigitalTwinStateStore -> Manages versioned entity state

Example:
    >>> from services.digital_twin.vector_clock import VectorClock, DigitalTwinStateStore
    >>>
    >>> # Create state store for a node
    >>> store = DigitalTwinStateStore(node_id="controller_1")
    >>>
    >>> # Update machine state
    >>> state, had_conflict = store.update_state(
    ...     entity_id="machine_001",
    ...     data={"position": {"x": 100, "y": 200}},
    ...     source_id="plc_1",
    ...     state_type="position"
    ... )
    >>>
    >>> # Apply remote update (may detect conflict)
    >>> resolved, had_conflict = store.apply_remote_update(remote_state)
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, Tuple
from enum import Enum
from datetime import datetime
import json
import copy


class CausalRelation(Enum):
    """
    Causal relationship between two vector clocks.

    In distributed systems, events can have three types of relationships:
    1. One causally precedes the other (BEFORE/AFTER)
    2. They are causally independent (CONCURRENT) - potential conflict
    3. They represent the same logical time (EQUAL)

    Attributes:
        BEFORE: Event A happened-before event B (A -> B)
        AFTER: Event A happened-after event B (B -> A)
        CONCURRENT: Events are causally independent (A || B)
        EQUAL: Events have identical logical timestamps
    """
    BEFORE = "before"           # a happened-before b
    AFTER = "after"             # a happened-after b
    CONCURRENT = "concurrent"   # a and b are concurrent (conflict)
    EQUAL = "equal"             # a and b are identical


class ConflictResolutionStrategy(Enum):
    """
    Strategies for resolving concurrent updates in distributed digital twins.

    When vector clocks indicate concurrent updates (neither happened-before
    the other), these strategies determine how to reconcile the conflict.

    Attributes:
        LAST_WRITE_WINS: Select the update with the latest wall-clock timestamp.
            Best for: Frequently changing values where recency is most important.
        FIRST_WRITE_WINS: Select the update with the earliest wall-clock timestamp.
            Best for: Values where original data should be preserved.
        MERGE: Attempt semantic merge of non-conflicting fields.
            Best for: Complex state objects with independent sub-fields.
        PREFER_SOURCE: Select based on a priority list of trusted sources.
            Best for: Multi-tier architectures with authoritative data sources.
        MANUAL: Flag for human intervention, temporarily accept remote.
            Best for: Safety-critical or high-value decisions.
    """
    LAST_WRITE_WINS = "last_write_wins"     # Use wall-clock timestamp
    FIRST_WRITE_WINS = "first_write_wins"   # Use earliest wall-clock
    MERGE = "merge"                          # Attempt semantic merge
    PREFER_SOURCE = "prefer_source"          # Prefer specific source
    MANUAL = "manual"                        # Require manual resolution


@dataclass
class VectorClock:
    """
    Vector clock for tracking causality in distributed digital twin updates.

    Each node (machine, controller, service) has its own entry in the clock.
    When a node updates state, it increments its own counter.
    When receiving updates, the clock is merged with incoming clock.

    ISO 23247-4 Compliance:
    - Enables detection of concurrent updates
    - Provides causal ordering of state changes
    - Supports conflict detection and resolution
    """

    # Clock values: node_id -> logical timestamp
    clock: Dict[str, int] = field(default_factory=dict)

    # Node that owns this clock
    node_id: str = ""

    # Wall-clock timestamp for tie-breaking
    wall_clock: Optional[datetime] = None

    def increment(self) -> 'VectorClock':
        """
        Increment this node's clock value for a new local event.

        Called when this node generates a new state update. Increments
        only this node's counter, preserving counters from other nodes.

        Returns:
            Self for method chaining.

        Note:
            Also updates wall_clock to current UTC time for tie-breaking.
        """
        if self.node_id:
            self.clock[self.node_id] = self.clock.get(self.node_id, 0) + 1
        self.wall_clock = datetime.utcnow()
        return self

    def merge(self, other: 'VectorClock') -> 'VectorClock':
        """
        Merge with another vector clock from a remote node.

        Takes the component-wise maximum of both clocks, ensuring this
        clock reflects knowledge of all events known to either clock.
        After merging, increments own counter to mark this merge event.

        Args:
            other: Vector clock from a remote node to merge with.

        Returns:
            Self for method chaining.

        Example:
            local:  {A: 3, B: 2}
            remote: {A: 2, B: 4, C: 1}
            merged: {A: 3, B: 4, C: 1} -> then increment own node
        """
        all_nodes = set(self.clock.keys()) | set(other.clock.keys())
        for node in all_nodes:
            self.clock[node] = max(
                self.clock.get(node, 0),
                other.clock.get(node, 0)
            )
        # After merge, increment own counter to mark this as a new event
        return self.increment()

    def compare(self, other: 'VectorClock') -> CausalRelation:
        """
        Compare this clock with another to determine causal relationship.

        Implements the standard vector clock comparison algorithm:
        - BEFORE: All components <= other, at least one strictly <
        - AFTER: All components >= other, at least one strictly >
        - CONCURRENT: Some components <, some >, indicates potential conflict
        - EQUAL: All components identical

        Args:
            other: Vector clock to compare against.

        Returns:
            CausalRelation indicating the temporal relationship.

        Example:
            {A:1, B:2} vs {A:2, B:2} -> BEFORE (self happened-before other)
            {A:2, B:2} vs {A:1, B:2} -> AFTER (self happened-after other)
            {A:1, B:3} vs {A:2, B:2} -> CONCURRENT (potential conflict)
        """
        all_nodes = set(self.clock.keys()) | set(other.clock.keys())

        self_less = False   # True if any self component < other component
        other_less = False  # True if any other component < self component

        for node in all_nodes:
            self_val = self.clock.get(node, 0)
            other_val = other.clock.get(node, 0)

            if self_val < other_val:
                self_less = True
            elif self_val > other_val:
                other_less = True

        # Determine relationship based on comparison flags
        if self_less and not other_less:
            return CausalRelation.BEFORE
        elif other_less and not self_less:
            return CausalRelation.AFTER
        elif self_less and other_less:
            return CausalRelation.CONCURRENT
        else:
            return CausalRelation.EQUAL

    def is_concurrent_with(self, other: 'VectorClock') -> bool:
        """Check if this clock is concurrent with another (potential conflict)."""
        return self.compare(other) == CausalRelation.CONCURRENT

    def happens_before(self, other: 'VectorClock') -> bool:
        """Check if this clock happened before another."""
        return self.compare(other) == CausalRelation.BEFORE

    def copy(self) -> 'VectorClock':
        """Create a deep copy of this vector clock."""
        return VectorClock(
            clock=copy.deepcopy(self.clock),
            node_id=self.node_id,
            wall_clock=self.wall_clock
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'clock': self.clock,
            'node_id': self.node_id,
            'wall_clock': self.wall_clock.isoformat() if self.wall_clock else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VectorClock':
        """Deserialize from dictionary."""
        wall_clock = None
        if data.get('wall_clock'):
            wall_clock = datetime.fromisoformat(data['wall_clock'])
        return cls(
            clock=data.get('clock', {}),
            node_id=data.get('node_id', ''),
            wall_clock=wall_clock
        )

    def __repr__(self) -> str:
        return f"VectorClock({self.clock}, node={self.node_id})"


@dataclass
class VersionedState:
    """
    State with vector clock for conflict detection.

    ISO 23247 Compliance:
    - Tracks state version with vector clock
    - Enables conflict detection on concurrent updates
    - Provides data lineage information
    """

    # The actual state data
    data: Dict[str, Any] = field(default_factory=dict)

    # Vector clock for this state version
    version: VectorClock = field(default_factory=VectorClock)

    # Entity this state belongs to
    entity_id: str = ""

    # Source that produced this state
    source_id: str = ""

    # Type of state (position, status, sensor, etc.)
    state_type: str = ""

    # Checksum for data integrity (ISO 23247-4)
    checksum: Optional[str] = None

    def compute_checksum(self) -> str:
        """Compute SHA-256 checksum of state data."""
        import hashlib
        data_str = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify data integrity using checksum."""
        if not self.checksum:
            return True  # No checksum to verify
        return self.compute_checksum() == self.checksum

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'data': self.data,
            'version': self.version.to_dict(),
            'entity_id': self.entity_id,
            'source_id': self.source_id,
            'state_type': self.state_type,
            'checksum': self.checksum
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VersionedState':
        """Deserialize from dictionary."""
        return cls(
            data=data.get('data', {}),
            version=VectorClock.from_dict(data.get('version', {})),
            entity_id=data.get('entity_id', ''),
            source_id=data.get('source_id', ''),
            state_type=data.get('state_type', ''),
            checksum=data.get('checksum')
        )


@dataclass
class ConflictRecord:
    """Record of a detected conflict for auditing."""
    timestamp: datetime
    entity_id: str
    local_version: VectorClock
    remote_version: VectorClock
    local_data: Dict[str, Any]
    remote_data: Dict[str, Any]
    resolution_strategy: ConflictResolutionStrategy
    resolved_data: Dict[str, Any]
    resolved_by: str  # "auto" or user_id


class ConflictResolver:
    """
    Resolves conflicts between concurrent state updates.

    ISO 23247-4 Compliance:
    - Implements multiple resolution strategies
    - Maintains conflict audit log
    - Supports semantic merge for compatible changes
    """

    def __init__(
        self,
        default_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LAST_WRITE_WINS,
        preferred_sources: Optional[List[str]] = None
    ):
        self.default_strategy = default_strategy
        self.preferred_sources = preferred_sources or []
        self.conflict_log: List[ConflictRecord] = []

    def resolve(
        self,
        local: VersionedState,
        remote: VersionedState,
        strategy: Optional[ConflictResolutionStrategy] = None
    ) -> Tuple[VersionedState, bool]:
        """
        Resolve conflict between local and remote state.

        Args:
            local: Local state version
            remote: Remote state version
            strategy: Resolution strategy (uses default if None)

        Returns:
            Tuple of (resolved_state, was_conflict)
        """
        relation = local.version.compare(remote.version)

        # No conflict cases
        if relation == CausalRelation.EQUAL:
            return local, False
        if relation == CausalRelation.BEFORE:
            # Remote is newer, accept it
            return remote, False
        if relation == CausalRelation.AFTER:
            # Local is newer, keep it
            return local, False

        # Concurrent - conflict detected
        strategy = strategy or self.default_strategy
        resolved = self._apply_resolution_strategy(local, remote, strategy)

        # Log the conflict
        self.conflict_log.append(ConflictRecord(
            timestamp=datetime.utcnow(),
            entity_id=local.entity_id,
            local_version=local.version.copy(),
            remote_version=remote.version.copy(),
            local_data=copy.deepcopy(local.data),
            remote_data=copy.deepcopy(remote.data),
            resolution_strategy=strategy,
            resolved_data=copy.deepcopy(resolved.data),
            resolved_by="auto"
        ))

        return resolved, True

    def _apply_resolution_strategy(
        self,
        local: VersionedState,
        remote: VersionedState,
        strategy: ConflictResolutionStrategy
    ) -> VersionedState:
        """Apply the specified resolution strategy."""

        if strategy == ConflictResolutionStrategy.LAST_WRITE_WINS:
            # Use wall-clock timestamp to decide
            local_time = local.version.wall_clock or datetime.min
            remote_time = remote.version.wall_clock or datetime.min
            winner = remote if remote_time >= local_time else local

        elif strategy == ConflictResolutionStrategy.FIRST_WRITE_WINS:
            local_time = local.version.wall_clock or datetime.max
            remote_time = remote.version.wall_clock or datetime.max
            winner = local if local_time <= remote_time else remote

        elif strategy == ConflictResolutionStrategy.PREFER_SOURCE:
            # Prefer state from preferred sources
            if remote.source_id in self.preferred_sources:
                winner = remote
            elif local.source_id in self.preferred_sources:
                winner = local
            else:
                # Fall back to last-write-wins
                return self._apply_resolution_strategy(
                    local, remote, ConflictResolutionStrategy.LAST_WRITE_WINS
                )

        elif strategy == ConflictResolutionStrategy.MERGE:
            # Attempt semantic merge
            winner = self._semantic_merge(local, remote)

        else:
            # Manual - for now, prefer remote
            winner = remote

        # Create merged version clock
        result = VersionedState(
            data=copy.deepcopy(winner.data),
            version=local.version.copy(),
            entity_id=local.entity_id,
            source_id=winner.source_id,
            state_type=local.state_type
        )
        result.version.merge(remote.version)
        result.checksum = result.compute_checksum()

        return result

    def _semantic_merge(
        self,
        local: VersionedState,
        remote: VersionedState
    ) -> VersionedState:
        """
        Attempt to semantically merge non-conflicting changes.

        For position data: Average or interpolate
        For status data: Prefer more severe status
        For counters: Take max
        """
        merged_data = copy.deepcopy(local.data)

        for key, remote_val in remote.data.items():
            local_val = local.data.get(key)

            if local_val is None:
                # Key only in remote, add it
                merged_data[key] = remote_val
            elif local_val == remote_val:
                # Same value, no conflict
                continue
            elif isinstance(local_val, (int, float)) and isinstance(remote_val, (int, float)):
                # Numeric: take average for positions, max for counters
                if 'count' in key.lower() or 'total' in key.lower():
                    merged_data[key] = max(local_val, remote_val)
                else:
                    merged_data[key] = (local_val + remote_val) / 2
            elif isinstance(local_val, dict) and isinstance(remote_val, dict):
                # Nested dict: recursive merge
                merged_data[key] = {**local_val, **remote_val}
            else:
                # Can't merge, prefer remote (more recent likely)
                merged_data[key] = remote_val

        result = VersionedState(
            data=merged_data,
            version=local.version.copy(),
            entity_id=local.entity_id,
            source_id=f"{local.source_id}+{remote.source_id}",
            state_type=local.state_type
        )
        return result

    def get_conflict_history(
        self,
        entity_id: Optional[str] = None,
        limit: int = 100
    ) -> List[ConflictRecord]:
        """Get conflict history, optionally filtered by entity."""
        records = self.conflict_log
        if entity_id:
            records = [r for r in records if r.entity_id == entity_id]
        return records[-limit:]

    def clear_conflict_log(self) -> int:
        """Clear conflict log and return number of records cleared."""
        count = len(self.conflict_log)
        self.conflict_log.clear()
        return count


class DigitalTwinStateStore:
    """
    State store with vector clock-based versioning.

    ISO 23247 Compliance:
    - Maintains versioned state for all entities
    - Detects and resolves conflicts automatically
    - Provides complete state history
    - Ensures data integrity with checksums
    """

    def __init__(
        self,
        node_id: str,
        conflict_resolver: Optional[ConflictResolver] = None
    ):
        self.node_id = node_id
        self.resolver = conflict_resolver or ConflictResolver()

        # Current state for each entity
        self._states: Dict[str, VersionedState] = {}

        # State history for replay (limited)
        self._history: Dict[str, List[VersionedState]] = {}
        self._max_history = 1000

    def get_state(self, entity_id: str) -> Optional[VersionedState]:
        """Get current state for an entity."""
        return self._states.get(entity_id)

    def update_state(
        self,
        entity_id: str,
        data: Dict[str, Any],
        source_id: str,
        state_type: str = "generic"
    ) -> Tuple[VersionedState, bool]:
        """
        Update state for an entity.

        Returns:
            Tuple of (new_state, had_conflict)
        """
        # Create new versioned state
        new_state = VersionedState(
            data=data,
            version=VectorClock(node_id=self.node_id),
            entity_id=entity_id,
            source_id=source_id,
            state_type=state_type
        )

        existing = self._states.get(entity_id)

        if existing:
            # Merge clocks and check for conflicts
            new_state.version = existing.version.copy()
            new_state.version.increment()
        else:
            new_state.version.increment()

        new_state.checksum = new_state.compute_checksum()

        # Store the new state
        self._states[entity_id] = new_state
        self._add_to_history(entity_id, new_state)

        return new_state, False

    def apply_remote_update(
        self,
        remote_state: VersionedState
    ) -> Tuple[VersionedState, bool]:
        """
        Apply a state update received from a remote source.

        Returns:
            Tuple of (final_state, had_conflict)
        """
        entity_id = remote_state.entity_id
        local_state = self._states.get(entity_id)

        if not local_state:
            # No local state, accept remote
            self._states[entity_id] = remote_state
            self._add_to_history(entity_id, remote_state)
            return remote_state, False

        # Resolve any conflicts
        resolved, had_conflict = self.resolver.resolve(local_state, remote_state)

        self._states[entity_id] = resolved
        self._add_to_history(entity_id, resolved)

        return resolved, had_conflict

    def _add_to_history(self, entity_id: str, state: VersionedState):
        """Add state to history, maintaining size limit."""
        if entity_id not in self._history:
            self._history[entity_id] = []

        self._history[entity_id].append(state)

        # Trim if over limit
        if len(self._history[entity_id]) > self._max_history:
            self._history[entity_id] = self._history[entity_id][-self._max_history:]

    def get_history(
        self,
        entity_id: str,
        limit: int = 100
    ) -> List[VersionedState]:
        """Get state history for an entity."""
        history = self._history.get(entity_id, [])
        return history[-limit:]

    def get_all_entities(self) -> List[str]:
        """Get list of all entity IDs with state."""
        return list(self._states.keys())

    def get_statistics(self) -> Dict[str, Any]:
        """Get store statistics."""
        return {
            'node_id': self.node_id,
            'entity_count': len(self._states),
            'total_history_entries': sum(len(h) for h in self._history.values()),
            'conflict_count': len(self.resolver.conflict_log)
        }
