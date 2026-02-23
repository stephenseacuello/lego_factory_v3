"""
Advanced Digital Twin State Synchronization V8.

LEGO MCP V8 - Autonomous Factory Platform
Advanced State Sync with Shadow States, CRDT Merging, and Federation.

Features:
- Shadow state management (physical vs digital divergence tracking)
- CRDT-based conflict-free state merging
- State diffing and incremental patching
- Temporal state queries (time travel debugging)
- Multi-twin federation for factory-wide synchronization
- Bi-directional sync with physical systems

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from dataclasses import dataclass, field
from typing import (
    Dict, Any, List, Optional, Set, Callable, Tuple,
    TypeVar, Generic, Union, AsyncIterator
)
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import asyncio
import hashlib
import json
import logging
import time
import uuid

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# Enums and Types
# =============================================================================

class ShadowStateMode(Enum):
    """Shadow state synchronization mode."""
    PHYSICAL_PRIMARY = "physical_primary"  # Physical state is source of truth
    DIGITAL_PRIMARY = "digital_primary"    # Digital state is source of truth
    BIDIRECTIONAL = "bidirectional"        # Both can update
    SIMULATION = "simulation"              # No physical sync


class MergeStrategy(Enum):
    """State merge strategy for conflicts."""
    LAST_WRITE_WINS = "last_write_wins"
    PHYSICAL_WINS = "physical_wins"
    DIGITAL_WINS = "digital_wins"
    CRDT_MERGE = "crdt_merge"
    MANUAL_RESOLUTION = "manual_resolution"


class DiffType(Enum):
    """Type of state difference."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


class FederationRole(Enum):
    """Role in twin federation."""
    LEADER = "leader"
    FOLLOWER = "follower"
    PEER = "peer"


class SyncDirection(Enum):
    """Direction of state synchronization."""
    PHYSICAL_TO_DIGITAL = "physical_to_digital"
    DIGITAL_TO_PHYSICAL = "digital_to_physical"
    BIDIRECTIONAL = "bidirectional"


# =============================================================================
# CRDT Data Structures
# =============================================================================

@dataclass
class VectorClock:
    """Vector clock for causality tracking."""
    clocks: Dict[str, int] = field(default_factory=dict)

    def increment(self, node_id: str) -> None:
        """Increment clock for a node."""
        self.clocks[node_id] = self.clocks.get(node_id, 0) + 1

    def merge(self, other: 'VectorClock') -> 'VectorClock':
        """Merge with another vector clock."""
        result = VectorClock()
        all_nodes = set(self.clocks.keys()) | set(other.clocks.keys())
        for node in all_nodes:
            result.clocks[node] = max(
                self.clocks.get(node, 0),
                other.clocks.get(node, 0)
            )
        return result

    def happens_before(self, other: 'VectorClock') -> bool:
        """Check if this clock happens before another."""
        all_less_or_equal = all(
            self.clocks.get(node, 0) <= other.clocks.get(node, 0)
            for node in set(self.clocks.keys()) | set(other.clocks.keys())
        )
        at_least_one_less = any(
            self.clocks.get(node, 0) < other.clocks.get(node, 0)
            for node in set(self.clocks.keys()) | set(other.clocks.keys())
        )
        return all_less_or_equal and at_least_one_less

    def concurrent_with(self, other: 'VectorClock') -> bool:
        """Check if this clock is concurrent with another."""
        return not self.happens_before(other) and not other.happens_before(self)

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return dict(self.clocks)

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> 'VectorClock':
        """Create from dictionary."""
        vc = cls()
        vc.clocks = dict(data)
        return vc


@dataclass
class LWWRegister(Generic[T]):
    """Last-Write-Wins Register CRDT."""
    value: T
    timestamp: float
    node_id: str

    def update(self, new_value: T, timestamp: float, node_id: str) -> 'LWWRegister[T]':
        """Update if timestamp is newer."""
        if timestamp > self.timestamp or (
            timestamp == self.timestamp and node_id > self.node_id
        ):
            return LWWRegister(new_value, timestamp, node_id)
        return self

    def merge(self, other: 'LWWRegister[T]') -> 'LWWRegister[T]':
        """Merge with another register."""
        if other.timestamp > self.timestamp or (
            other.timestamp == self.timestamp and other.node_id > self.node_id
        ):
            return other
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "value": self.value,
            "timestamp": self.timestamp,
            "node_id": self.node_id,
        }


@dataclass
class GCounter:
    """Grow-only Counter CRDT."""
    counts: Dict[str, int] = field(default_factory=dict)

    def increment(self, node_id: str, amount: int = 1) -> None:
        """Increment counter for a node."""
        self.counts[node_id] = self.counts.get(node_id, 0) + amount

    def value(self) -> int:
        """Get total counter value."""
        return sum(self.counts.values())

    def merge(self, other: 'GCounter') -> 'GCounter':
        """Merge with another G-Counter."""
        result = GCounter()
        all_nodes = set(self.counts.keys()) | set(other.counts.keys())
        for node in all_nodes:
            result.counts[node] = max(
                self.counts.get(node, 0),
                other.counts.get(node, 0)
            )
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {"counts": dict(self.counts), "value": self.value()}


@dataclass
class ORSet(Generic[T]):
    """Observed-Remove Set CRDT."""
    elements: Dict[T, Set[str]] = field(default_factory=lambda: defaultdict(set))
    tombstones: Dict[T, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def add(self, element: T, tag: Optional[str] = None) -> None:
        """Add element with unique tag."""
        if tag is None:
            tag = str(uuid.uuid4())
        self.elements[element].add(tag)

    def remove(self, element: T) -> None:
        """Remove element by moving all tags to tombstones."""
        if element in self.elements:
            self.tombstones[element].update(self.elements[element])
            self.elements[element].clear()

    def contains(self, element: T) -> bool:
        """Check if element is in set."""
        return bool(self.elements.get(element, set()) - self.tombstones.get(element, set()))

    def values(self) -> Set[T]:
        """Get all elements in set."""
        return {
            elem for elem, tags in self.elements.items()
            if tags - self.tombstones.get(elem, set())
        }

    def merge(self, other: 'ORSet[T]') -> 'ORSet[T]':
        """Merge with another OR-Set."""
        result = ORSet()
        all_elements = set(self.elements.keys()) | set(other.elements.keys())

        for elem in all_elements:
            result.elements[elem] = (
                self.elements.get(elem, set()) | other.elements.get(elem, set())
            )
            result.tombstones[elem] = (
                self.tombstones.get(elem, set()) | other.tombstones.get(elem, set())
            )

        return result


# =============================================================================
# State Difference Tracking
# =============================================================================

@dataclass
class StateDiff:
    """Represents a difference between two states."""
    path: str
    diff_type: DiffType
    old_value: Any
    new_value: Any
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "diff_type": self.diff_type.value,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class StatePatch:
    """A patch to apply to a state."""
    patch_id: str
    source_hash: str
    target_hash: str
    diffs: List[StateDiff]
    created_at: datetime
    vector_clock: VectorClock

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "patch_id": self.patch_id,
            "source_hash": self.source_hash,
            "target_hash": self.target_hash,
            "diffs": [d.to_dict() for d in self.diffs],
            "created_at": self.created_at.isoformat(),
            "vector_clock": self.vector_clock.to_dict(),
        }


# =============================================================================
# Shadow State Management
# =============================================================================

@dataclass
class ShadowState:
    """
    Shadow state tracking physical vs digital divergence.

    Tracks both the physical (actual) and digital (simulated) states
    to detect and reconcile divergence.
    """
    shadow_id: str
    twin_id: str
    physical_state: Dict[str, Any]
    digital_state: Dict[str, Any]
    physical_timestamp: datetime
    digital_timestamp: datetime
    vector_clock: VectorClock
    divergence_score: float = 0.0
    is_synchronized: bool = True
    pending_patches: List[StatePatch] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_divergence(self) -> float:
        """Calculate divergence score between physical and digital states."""
        diffs = self._compute_diffs(self.physical_state, self.digital_state, "")
        if not diffs:
            return 0.0

        # Weight diffs by importance
        total_weight = 0.0
        weighted_divergence = 0.0

        for diff in diffs:
            weight = self._get_path_weight(diff.path)
            total_weight += weight

            if diff.diff_type in (DiffType.ADDED, DiffType.REMOVED):
                weighted_divergence += weight * 1.0
            elif diff.diff_type == DiffType.MODIFIED:
                # Calculate relative change for numeric values
                if isinstance(diff.old_value, (int, float)) and isinstance(diff.new_value, (int, float)):
                    if diff.old_value != 0:
                        rel_change = abs(diff.new_value - diff.old_value) / abs(diff.old_value)
                        weighted_divergence += weight * min(rel_change, 1.0)
                    else:
                        weighted_divergence += weight * (1.0 if diff.new_value != 0 else 0.0)
                else:
                    weighted_divergence += weight * 1.0

        self.divergence_score = weighted_divergence / total_weight if total_weight > 0 else 0.0
        self.is_synchronized = self.divergence_score < 0.01  # 1% threshold
        return self.divergence_score

    def _get_path_weight(self, path: str) -> float:
        """Get importance weight for a state path."""
        # Critical paths have higher weights
        critical_paths = {
            "position": 2.0,
            "temperature": 1.5,
            "speed": 1.5,
            "status": 2.0,
            "error": 3.0,
            "safety": 3.0,
        }
        for critical, weight in critical_paths.items():
            if critical in path.lower():
                return weight
        return 1.0

    def _compute_diffs(
        self,
        old_state: Dict[str, Any],
        new_state: Dict[str, Any],
        prefix: str
    ) -> List[StateDiff]:
        """Compute differences between two states."""
        diffs = []
        all_keys = set(old_state.keys()) | set(new_state.keys())

        for key in all_keys:
            path = f"{prefix}.{key}" if prefix else key
            old_val = old_state.get(key)
            new_val = new_state.get(key)

            if key not in old_state:
                diffs.append(StateDiff(
                    path=path,
                    diff_type=DiffType.ADDED,
                    old_value=None,
                    new_value=new_val,
                    timestamp=datetime.utcnow()
                ))
            elif key not in new_state:
                diffs.append(StateDiff(
                    path=path,
                    diff_type=DiffType.REMOVED,
                    old_value=old_val,
                    new_value=None,
                    timestamp=datetime.utcnow()
                ))
            elif isinstance(old_val, dict) and isinstance(new_val, dict):
                diffs.extend(self._compute_diffs(old_val, new_val, path))
            elif old_val != new_val:
                diffs.append(StateDiff(
                    path=path,
                    diff_type=DiffType.MODIFIED,
                    old_value=old_val,
                    new_value=new_val,
                    timestamp=datetime.utcnow()
                ))

        return diffs

    def get_physical_digital_diffs(self) -> List[StateDiff]:
        """Get all differences between physical and digital states."""
        return self._compute_diffs(self.physical_state, self.digital_state, "")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "shadow_id": self.shadow_id,
            "twin_id": self.twin_id,
            "physical_state": self.physical_state,
            "digital_state": self.digital_state,
            "physical_timestamp": self.physical_timestamp.isoformat(),
            "digital_timestamp": self.digital_timestamp.isoformat(),
            "vector_clock": self.vector_clock.to_dict(),
            "divergence_score": self.divergence_score,
            "is_synchronized": self.is_synchronized,
            "pending_patches": [p.to_dict() for p in self.pending_patches],
            "metadata": self.metadata,
        }


# =============================================================================
# Federation Support
# =============================================================================

@dataclass
class FederatedTwin:
    """A twin participating in federation."""
    twin_id: str
    role: FederationRole
    endpoint: str
    last_sync: datetime
    vector_clock: VectorClock
    is_online: bool = True
    sync_lag_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "twin_id": self.twin_id,
            "role": self.role.value,
            "endpoint": self.endpoint,
            "last_sync": self.last_sync.isoformat(),
            "vector_clock": self.vector_clock.to_dict(),
            "is_online": self.is_online,
            "sync_lag_ms": self.sync_lag_ms,
        }


@dataclass
class SyncTransaction:
    """A state synchronization transaction."""
    transaction_id: str
    source_twin: str
    target_twins: List[str]
    patches: List[StatePatch]
    direction: SyncDirection
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "pending"
    acknowledgments: Dict[str, bool] = field(default_factory=dict)

    def is_complete(self) -> bool:
        """Check if all targets have acknowledged."""
        return all(
            self.acknowledgments.get(twin_id, False)
            for twin_id in self.target_twins
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "transaction_id": self.transaction_id,
            "source_twin": self.source_twin,
            "target_twins": self.target_twins,
            "patches": [p.to_dict() for p in self.patches],
            "direction": self.direction.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "acknowledgments": self.acknowledgments,
        }


# =============================================================================
# Advanced State Synchronizer
# =============================================================================

class AdvancedStateSynchronizer:
    """
    Advanced state synchronization engine for digital twins.

    Features:
    - Shadow state management with divergence tracking
    - CRDT-based conflict-free state merging
    - State diffing and incremental patching
    - Temporal state queries (time travel)
    - Multi-twin federation for factory-wide sync
    - Bi-directional sync with physical systems
    """

    def __init__(
        self,
        node_id: str,
        mode: ShadowStateMode = ShadowStateMode.BIDIRECTIONAL,
        merge_strategy: MergeStrategy = MergeStrategy.CRDT_MERGE,
        max_history_size: int = 1000,
        divergence_threshold: float = 0.1
    ):
        """
        Initialize the advanced state synchronizer.

        Args:
            node_id: Unique identifier for this sync node
            mode: Shadow state synchronization mode
            merge_strategy: Strategy for resolving conflicts
            max_history_size: Maximum state history entries to keep
            divergence_threshold: Threshold for divergence alerts
        """
        self.node_id = node_id
        self.mode = mode
        self.merge_strategy = merge_strategy
        self.max_history_size = max_history_size
        self.divergence_threshold = divergence_threshold

        # State storage
        self.shadow_states: Dict[str, ShadowState] = {}
        self.state_history: Dict[str, List[Tuple[datetime, Dict[str, Any]]]] = defaultdict(list)
        self.vector_clock = VectorClock()

        # CRDT registers for state fields
        self.state_registers: Dict[str, Dict[str, LWWRegister]] = defaultdict(dict)

        # Federation
        self.federated_twins: Dict[str, FederatedTwin] = {}
        self.federation_role = FederationRole.PEER
        self.pending_transactions: Dict[str, SyncTransaction] = {}

        # Callbacks
        self.on_divergence: Optional[Callable[[str, float], None]] = None
        self.on_sync_complete: Optional[Callable[[str, SyncTransaction], None]] = None
        self.on_conflict: Optional[Callable[[str, List[StateDiff]], None]] = None

        # Metrics
        self.sync_count = GCounter()
        self.conflict_count = GCounter()
        self.total_patches_applied = 0
        self._running = False
        self._sync_task: Optional[asyncio.Task] = None

        logger.info(
            f"AdvancedStateSynchronizer initialized: node={node_id}, "
            f"mode={mode.value}, strategy={merge_strategy.value}"
        )

    # -------------------------------------------------------------------------
    # Shadow State Management
    # -------------------------------------------------------------------------

    def create_shadow_state(
        self,
        twin_id: str,
        initial_physical_state: Dict[str, Any],
        initial_digital_state: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ShadowState:
        """
        Create a new shadow state for a digital twin.

        Args:
            twin_id: Unique identifier for the twin
            initial_physical_state: Initial physical state
            initial_digital_state: Initial digital state (defaults to physical)
            metadata: Optional metadata

        Returns:
            Created ShadowState
        """
        now = datetime.utcnow()

        if initial_digital_state is None:
            initial_digital_state = dict(initial_physical_state)

        shadow = ShadowState(
            shadow_id=str(uuid.uuid4()),
            twin_id=twin_id,
            physical_state=initial_physical_state,
            digital_state=initial_digital_state,
            physical_timestamp=now,
            digital_timestamp=now,
            vector_clock=VectorClock(),
            metadata=metadata or {}
        )

        shadow.vector_clock.increment(self.node_id)
        shadow.calculate_divergence()

        self.shadow_states[twin_id] = shadow
        self._record_state_history(twin_id, initial_physical_state)
        self._initialize_state_registers(twin_id, initial_physical_state)

        logger.info(f"Created shadow state for twin: {twin_id}")
        return shadow

    def update_physical_state(
        self,
        twin_id: str,
        state_update: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ) -> ShadowState:
        """
        Update the physical state of a twin.

        Args:
            twin_id: Twin identifier
            state_update: State update (partial or full)
            timestamp: Optional timestamp for the update

        Returns:
            Updated ShadowState
        """
        if twin_id not in self.shadow_states:
            raise ValueError(f"No shadow state for twin: {twin_id}")

        shadow = self.shadow_states[twin_id]
        now = timestamp or datetime.utcnow()

        # Apply update
        self._deep_merge(shadow.physical_state, state_update)
        shadow.physical_timestamp = now
        shadow.vector_clock.increment(self.node_id)

        # Update CRDT registers
        self._update_state_registers(twin_id, state_update, now.timestamp())

        # Record history
        self._record_state_history(twin_id, shadow.physical_state)

        # Calculate divergence
        divergence = shadow.calculate_divergence()

        # Check for divergence alert
        if divergence > self.divergence_threshold and self.on_divergence:
            self.on_divergence(twin_id, divergence)

        # Auto-sync to digital if in physical-primary mode
        if self.mode == ShadowStateMode.PHYSICAL_PRIMARY:
            self._sync_physical_to_digital(twin_id)

        self.vector_clock.increment(self.node_id)
        logger.debug(f"Updated physical state for twin {twin_id}, divergence: {divergence:.4f}")

        return shadow

    def update_digital_state(
        self,
        twin_id: str,
        state_update: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ) -> ShadowState:
        """
        Update the digital state of a twin.

        Args:
            twin_id: Twin identifier
            state_update: State update (partial or full)
            timestamp: Optional timestamp for the update

        Returns:
            Updated ShadowState
        """
        if twin_id not in self.shadow_states:
            raise ValueError(f"No shadow state for twin: {twin_id}")

        shadow = self.shadow_states[twin_id]
        now = timestamp or datetime.utcnow()

        # Apply update
        self._deep_merge(shadow.digital_state, state_update)
        shadow.digital_timestamp = now
        shadow.vector_clock.increment(self.node_id)

        # Calculate divergence
        divergence = shadow.calculate_divergence()

        # Auto-sync to physical if in digital-primary mode
        if self.mode == ShadowStateMode.DIGITAL_PRIMARY:
            self._sync_digital_to_physical(twin_id)

        logger.debug(f"Updated digital state for twin {twin_id}, divergence: {divergence:.4f}")

        return shadow

    def synchronize_states(
        self,
        twin_id: str,
        direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    ) -> StatePatch:
        """
        Synchronize physical and digital states.

        Args:
            twin_id: Twin identifier
            direction: Sync direction

        Returns:
            Applied StatePatch
        """
        if twin_id not in self.shadow_states:
            raise ValueError(f"No shadow state for twin: {twin_id}")

        shadow = self.shadow_states[twin_id]
        diffs = shadow.get_physical_digital_diffs()

        if not diffs:
            logger.debug(f"States already synchronized for twin: {twin_id}")
            return StatePatch(
                patch_id=str(uuid.uuid4()),
                source_hash=self._compute_state_hash(shadow.physical_state),
                target_hash=self._compute_state_hash(shadow.physical_state),
                diffs=[],
                created_at=datetime.utcnow(),
                vector_clock=shadow.vector_clock
            )

        # Handle conflicts based on merge strategy
        if self.merge_strategy == MergeStrategy.CRDT_MERGE:
            merged_state = self._crdt_merge_states(twin_id)
        elif self.merge_strategy == MergeStrategy.PHYSICAL_WINS:
            merged_state = dict(shadow.physical_state)
        elif self.merge_strategy == MergeStrategy.DIGITAL_WINS:
            merged_state = dict(shadow.digital_state)
        else:  # LAST_WRITE_WINS
            if shadow.physical_timestamp > shadow.digital_timestamp:
                merged_state = dict(shadow.physical_state)
            else:
                merged_state = dict(shadow.digital_state)

        # Create patch
        source_hash = self._compute_state_hash(shadow.physical_state)
        target_hash = self._compute_state_hash(merged_state)

        patch = StatePatch(
            patch_id=str(uuid.uuid4()),
            source_hash=source_hash,
            target_hash=target_hash,
            diffs=diffs,
            created_at=datetime.utcnow(),
            vector_clock=VectorClock.from_dict(shadow.vector_clock.to_dict())
        )

        # Apply based on direction
        if direction in (SyncDirection.PHYSICAL_TO_DIGITAL, SyncDirection.BIDIRECTIONAL):
            shadow.digital_state = dict(merged_state)
            shadow.digital_timestamp = datetime.utcnow()

        if direction in (SyncDirection.DIGITAL_TO_PHYSICAL, SyncDirection.BIDIRECTIONAL):
            shadow.physical_state = dict(merged_state)
            shadow.physical_timestamp = datetime.utcnow()

        shadow.calculate_divergence()
        shadow.vector_clock.increment(self.node_id)
        self.sync_count.increment(self.node_id)
        self.total_patches_applied += 1

        logger.info(f"Synchronized states for twin {twin_id}, {len(diffs)} diffs resolved")

        return patch

    # -------------------------------------------------------------------------
    # CRDT Operations
    # -------------------------------------------------------------------------

    def _crdt_merge_states(self, twin_id: str) -> Dict[str, Any]:
        """Merge states using CRDT registers."""
        result = {}

        for path, register in self.state_registers.get(twin_id, {}).items():
            self._set_nested_value(result, path, register.value)

        return result

    def _initialize_state_registers(
        self,
        twin_id: str,
        state: Dict[str, Any],
        prefix: str = ""
    ) -> None:
        """Initialize CRDT registers for state fields."""
        timestamp = time.time()

        for key, value in state.items():
            path = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                self._initialize_state_registers(twin_id, value, path)
            else:
                self.state_registers[twin_id][path] = LWWRegister(
                    value=value,
                    timestamp=timestamp,
                    node_id=self.node_id
                )

    def _update_state_registers(
        self,
        twin_id: str,
        state_update: Dict[str, Any],
        timestamp: float,
        prefix: str = ""
    ) -> None:
        """Update CRDT registers with new state values."""
        for key, value in state_update.items():
            path = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                self._update_state_registers(twin_id, value, timestamp, path)
            else:
                if path in self.state_registers[twin_id]:
                    self.state_registers[twin_id][path] = \
                        self.state_registers[twin_id][path].update(
                            value, timestamp, self.node_id
                        )
                else:
                    self.state_registers[twin_id][path] = LWWRegister(
                        value=value,
                        timestamp=timestamp,
                        node_id=self.node_id
                    )

    # -------------------------------------------------------------------------
    # Temporal Queries (Time Travel)
    # -------------------------------------------------------------------------

    def get_state_at_time(
        self,
        twin_id: str,
        target_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Get the state of a twin at a specific point in time.

        Args:
            twin_id: Twin identifier
            target_time: Target timestamp

        Returns:
            State at that time, or None if not available
        """
        if twin_id not in self.state_history:
            return None

        history = self.state_history[twin_id]

        # Binary search for closest state
        left, right = 0, len(history) - 1
        result = None

        while left <= right:
            mid = (left + right) // 2
            ts, state = history[mid]

            if ts <= target_time:
                result = state
                left = mid + 1
            else:
                right = mid - 1

        return dict(result) if result else None

    def get_state_changes_in_range(
        self,
        twin_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Tuple[datetime, List[StateDiff]]]:
        """
        Get all state changes within a time range.

        Args:
            twin_id: Twin identifier
            start_time: Start of range
            end_time: End of range

        Returns:
            List of (timestamp, diffs) tuples
        """
        if twin_id not in self.state_history:
            return []

        history = self.state_history[twin_id]
        changes = []
        prev_state = None

        for ts, state in history:
            if start_time <= ts <= end_time:
                if prev_state is not None:
                    shadow = self.shadow_states.get(twin_id)
                    if shadow:
                        diffs = shadow._compute_diffs(prev_state, state, "")
                        if diffs:
                            changes.append((ts, diffs))
                prev_state = state
            elif ts > end_time:
                break

        return changes

    # -------------------------------------------------------------------------
    # Federation
    # -------------------------------------------------------------------------

    def join_federation(
        self,
        twin_id: str,
        role: FederationRole,
        endpoint: str
    ) -> FederatedTwin:
        """
        Join a federation of twins.

        Args:
            twin_id: Twin identifier
            role: Role in federation
            endpoint: Network endpoint

        Returns:
            FederatedTwin entry
        """
        federated = FederatedTwin(
            twin_id=twin_id,
            role=role,
            endpoint=endpoint,
            last_sync=datetime.utcnow(),
            vector_clock=VectorClock()
        )

        self.federated_twins[twin_id] = federated

        if role == FederationRole.LEADER:
            self.federation_role = FederationRole.LEADER

        logger.info(f"Twin {twin_id} joined federation as {role.value}")
        return federated

    async def propagate_to_federation(
        self,
        twin_id: str,
        patch: StatePatch
    ) -> SyncTransaction:
        """
        Propagate state changes to federated twins.

        Args:
            twin_id: Source twin identifier
            patch: Patch to propagate

        Returns:
            SyncTransaction
        """
        target_twins = [
            tid for tid, twin in self.federated_twins.items()
            if tid != twin_id and twin.is_online
        ]

        transaction = SyncTransaction(
            transaction_id=str(uuid.uuid4()),
            source_twin=twin_id,
            target_twins=target_twins,
            patches=[patch],
            direction=SyncDirection.BIDIRECTIONAL,
            started_at=datetime.utcnow()
        )

        self.pending_transactions[transaction.transaction_id] = transaction

        # Simulate async propagation
        for target_id in target_twins:
            try:
                # In real implementation, this would be network call
                await asyncio.sleep(0.01)  # Simulated network latency
                transaction.acknowledgments[target_id] = True

                # Update sync timestamp
                if target_id in self.federated_twins:
                    self.federated_twins[target_id].last_sync = datetime.utcnow()

            except Exception as e:
                logger.error(f"Failed to propagate to {target_id}: {e}")
                transaction.acknowledgments[target_id] = False

        if transaction.is_complete():
            transaction.status = "completed"
            transaction.completed_at = datetime.utcnow()

            if self.on_sync_complete:
                self.on_sync_complete(twin_id, transaction)
        else:
            transaction.status = "partial"

        return transaction

    # -------------------------------------------------------------------------
    # Background Sync Loop
    # -------------------------------------------------------------------------

    async def start_sync_loop(self, interval_seconds: float = 1.0) -> None:
        """Start the background synchronization loop."""
        self._running = True

        async def sync_loop():
            while self._running:
                try:
                    await self._perform_sync_cycle()
                except Exception as e:
                    logger.error(f"Sync cycle error: {e}")

                await asyncio.sleep(interval_seconds)

        self._sync_task = asyncio.create_task(sync_loop())
        logger.info(f"Started sync loop with {interval_seconds}s interval")

    async def stop_sync_loop(self) -> None:
        """Stop the background synchronization loop."""
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped sync loop")

    async def _perform_sync_cycle(self) -> None:
        """Perform one sync cycle for all twins."""
        for twin_id, shadow in self.shadow_states.items():
            # Check divergence
            divergence = shadow.calculate_divergence()

            if divergence > self.divergence_threshold:
                # Auto-sync if needed
                if self.mode == ShadowStateMode.BIDIRECTIONAL:
                    patch = self.synchronize_states(twin_id)

                    # Propagate to federation
                    if self.federated_twins:
                        await self.propagate_to_federation(twin_id, patch)

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def _deep_merge(
        self,
        base: Dict[str, Any],
        update: Dict[str, Any]
    ) -> None:
        """Deep merge update into base dictionary."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _compute_state_hash(self, state: Dict[str, Any]) -> str:
        """Compute hash of state for comparison."""
        state_str = json.dumps(state, sort_keys=True, default=str)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]

    def _set_nested_value(
        self,
        obj: Dict[str, Any],
        path: str,
        value: Any
    ) -> None:
        """Set a nested value in a dictionary."""
        parts = path.split('.')
        current = obj

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    def _record_state_history(
        self,
        twin_id: str,
        state: Dict[str, Any]
    ) -> None:
        """Record state in history."""
        history = self.state_history[twin_id]
        history.append((datetime.utcnow(), dict(state)))

        # Trim history if needed
        if len(history) > self.max_history_size:
            self.state_history[twin_id] = history[-self.max_history_size:]

    def _sync_physical_to_digital(self, twin_id: str) -> None:
        """Sync physical state to digital."""
        shadow = self.shadow_states[twin_id]
        shadow.digital_state = dict(shadow.physical_state)
        shadow.digital_timestamp = datetime.utcnow()
        shadow.calculate_divergence()

    def _sync_digital_to_physical(self, twin_id: str) -> None:
        """Sync digital state to physical."""
        shadow = self.shadow_states[twin_id]
        shadow.physical_state = dict(shadow.digital_state)
        shadow.physical_timestamp = datetime.utcnow()
        shadow.calculate_divergence()

    # -------------------------------------------------------------------------
    # Status and Metrics
    # -------------------------------------------------------------------------

    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status."""
        twins_status = {}

        for twin_id, shadow in self.shadow_states.items():
            twins_status[twin_id] = {
                "divergence_score": shadow.divergence_score,
                "is_synchronized": shadow.is_synchronized,
                "physical_timestamp": shadow.physical_timestamp.isoformat(),
                "digital_timestamp": shadow.digital_timestamp.isoformat(),
                "pending_patches": len(shadow.pending_patches),
            }

        federation_status = {
            twin_id: {
                "role": twin.role.value,
                "is_online": twin.is_online,
                "last_sync": twin.last_sync.isoformat(),
                "sync_lag_ms": twin.sync_lag_ms,
            }
            for twin_id, twin in self.federated_twins.items()
        }

        return {
            "node_id": self.node_id,
            "mode": self.mode.value,
            "merge_strategy": self.merge_strategy.value,
            "federation_role": self.federation_role.value,
            "total_twins": len(self.shadow_states),
            "federated_twins": len(self.federated_twins),
            "sync_count": self.sync_count.value(),
            "conflict_count": self.conflict_count.value(),
            "total_patches_applied": self.total_patches_applied,
            "running": self._running,
            "twins": twins_status,
            "federation": federation_status,
        }


# =============================================================================
# Factory Function and Singleton
# =============================================================================

_synchronizer_instance: Optional[AdvancedStateSynchronizer] = None


def get_advanced_synchronizer(
    node_id: Optional[str] = None,
    mode: ShadowStateMode = ShadowStateMode.BIDIRECTIONAL,
    merge_strategy: MergeStrategy = MergeStrategy.CRDT_MERGE
) -> AdvancedStateSynchronizer:
    """
    Get or create the advanced state synchronizer singleton.

    Args:
        node_id: Node identifier (required for first call)
        mode: Shadow state mode
        merge_strategy: Merge strategy

    Returns:
        AdvancedStateSynchronizer instance
    """
    global _synchronizer_instance

    if _synchronizer_instance is None:
        if node_id is None:
            node_id = f"sync-{uuid.uuid4().hex[:8]}"
        _synchronizer_instance = AdvancedStateSynchronizer(
            node_id=node_id,
            mode=mode,
            merge_strategy=merge_strategy
        )

    return _synchronizer_instance


__all__ = [
    # Enums
    'ShadowStateMode',
    'MergeStrategy',
    'DiffType',
    'FederationRole',
    'SyncDirection',
    # CRDTs
    'VectorClock',
    'LWWRegister',
    'GCounter',
    'ORSet',
    # State Types
    'StateDiff',
    'StatePatch',
    'ShadowState',
    'FederatedTwin',
    'SyncTransaction',
    # Main Class
    'AdvancedStateSynchronizer',
    'get_advanced_synchronizer',
]
