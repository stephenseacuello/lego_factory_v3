"""
Sync Protocol - Bi-directional Digital Twin Synchronization

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- Bi-directional sync between physical and digital
- Conflict resolution strategies
- Change tracking and versioning
- Offline support with merge
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from enum import Enum
import threading
import uuid
import json
import hashlib
from collections import defaultdict


class SyncDirection(Enum):
    """Synchronization direction."""
    PHYSICAL_TO_DIGITAL = "physical_to_digital"
    DIGITAL_TO_PHYSICAL = "digital_to_physical"
    BIDIRECTIONAL = "bidirectional"


class ConflictStrategy(Enum):
    """Conflict resolution strategies."""
    LAST_WRITE_WINS = "last_write_wins"
    PHYSICAL_WINS = "physical_wins"
    DIGITAL_WINS = "digital_wins"
    MERGE = "merge"
    MANUAL = "manual"


class SyncStatus(Enum):
    """Synchronization status."""
    SYNCED = "synced"
    PENDING = "pending"
    SYNCING = "syncing"
    CONFLICT = "conflict"
    ERROR = "error"
    OFFLINE = "offline"


class ChangeType(Enum):
    """Type of change."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class Change:
    """Represents a change to be synchronized."""
    change_id: str
    entity_id: str
    entity_type: str
    change_type: ChangeType
    property_path: str
    old_value: Any
    new_value: Any
    timestamp: datetime
    source: str  # "physical" or "digital"
    version: int
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Conflict:
    """Represents a synchronization conflict."""
    conflict_id: str
    entity_id: str
    property_path: str
    physical_change: Change
    digital_change: Change
    detected_at: datetime
    resolved: bool = False
    resolution: Optional[str] = None
    resolved_value: Any = None
    resolved_at: Optional[datetime] = None


@dataclass
class SyncState:
    """Synchronization state for an entity."""
    entity_id: str
    physical_version: int
    digital_version: int
    last_sync: datetime
    status: SyncStatus
    pending_changes: List[Change] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)
    checksum: str = ""


@dataclass
class SyncResult:
    """Result of a synchronization operation."""
    success: bool
    synced_count: int
    conflict_count: int
    error_count: int
    duration_ms: float
    changes_applied: List[Change] = field(default_factory=list)
    conflicts_detected: List[Conflict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class SyncConfig:
    """Synchronization configuration."""
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS
    sync_interval_seconds: float = 1.0
    batch_size: int = 100
    retry_attempts: int = 3
    offline_queue_size: int = 1000
    enable_compression: bool = True
    enable_checksums: bool = True


class VectorClock:
    """Vector clock for tracking causality."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.clock: Dict[str, int] = defaultdict(int)

    def increment(self):
        """Increment local clock."""
        self.clock[self.node_id] += 1

    def update(self, other: 'VectorClock'):
        """Update clock with another clock."""
        for node, time in other.clock.items():
            self.clock[node] = max(self.clock[node], time)
        self.increment()

    def happens_before(self, other: 'VectorClock') -> bool:
        """Check if this clock happens before other."""
        less_or_equal = all(
            self.clock.get(k, 0) <= other.clock.get(k, 0)
            for k in set(self.clock.keys()) | set(other.clock.keys())
        )
        strictly_less = any(
            self.clock.get(k, 0) < other.clock.get(k, 0)
            for k in other.clock.keys()
        )
        return less_or_equal and strictly_less

    def concurrent(self, other: 'VectorClock') -> bool:
        """Check if clocks are concurrent (potential conflict)."""
        return not self.happens_before(other) and not other.happens_before(self)

    def to_dict(self) -> Dict[str, int]:
        return dict(self.clock)

    @classmethod
    def from_dict(cls, node_id: str, data: Dict[str, int]) -> 'VectorClock':
        vc = cls(node_id)
        vc.clock = defaultdict(int, data)
        return vc


class SyncProtocol:
    """
    Bi-directional synchronization protocol for Digital Twin.

    Handles:
    - Change detection and tracking
    - Conflict detection and resolution
    - Version management
    - Offline queue management
    """

    def __init__(
        self,
        node_id: str = "digital",
        config: Optional[SyncConfig] = None
    ):
        """
        Initialize sync protocol.

        Args:
            node_id: Identifier for this node
            config: Sync configuration
        """
        self.node_id = node_id
        self.config = config or SyncConfig()

        # State tracking
        self._sync_states: Dict[str, SyncState] = {}
        self._pending_changes: List[Change] = []
        self._offline_queue: List[Change] = []
        self._conflicts: Dict[str, Conflict] = {}

        # Vector clocks for causality
        self._vector_clocks: Dict[str, VectorClock] = {}

        # Change handlers
        self._change_handlers: Dict[str, List[Callable[[Change], bool]]] = defaultdict(list)

        # Thread safety
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "changes_applied": 0,
        }

        # Online status
        self._is_online = True

    def track_change(
        self,
        entity_id: str,
        entity_type: str,
        property_path: str,
        old_value: Any,
        new_value: Any,
        source: str = "digital"
    ) -> Change:
        """
        Track a change for synchronization.

        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            property_path: Path to changed property
            old_value: Previous value
            new_value: New value
            source: Change source ("physical" or "digital")

        Returns:
            Created change
        """
        with self._lock:
            # Get or create sync state
            state = self._get_or_create_state(entity_id)

            # Update vector clock
            vc = self._get_vector_clock(entity_id)
            vc.increment()

            # Determine change type
            if old_value is None and new_value is not None:
                change_type = ChangeType.CREATE
            elif new_value is None:
                change_type = ChangeType.DELETE
            else:
                change_type = ChangeType.UPDATE

            # Calculate checksum
            checksum = self._calculate_checksum(new_value)

            # Create change
            version = state.digital_version + 1 if source == "digital" else state.physical_version + 1

            change = Change(
                change_id=str(uuid.uuid4()),
                entity_id=entity_id,
                entity_type=entity_type,
                change_type=change_type,
                property_path=property_path,
                old_value=old_value,
                new_value=new_value,
                timestamp=datetime.utcnow(),
                source=source,
                version=version,
                checksum=checksum,
                metadata={"vector_clock": vc.to_dict()},
            )

            # Update version
            if source == "digital":
                state.digital_version = version
            else:
                state.physical_version = version

            # Add to pending changes
            state.pending_changes.append(change)
            state.status = SyncStatus.PENDING

            if self._is_online:
                self._pending_changes.append(change)
            else:
                self._offline_queue.append(change)
                if len(self._offline_queue) > self.config.offline_queue_size:
                    self._offline_queue.pop(0)  # Remove oldest

            return change

    def sync(
        self,
        entity_id: Optional[str] = None,
        force: bool = False
    ) -> SyncResult:
        """
        Synchronize changes.

        Args:
            entity_id: Specific entity to sync (all if None)
            force: Force sync even if no changes

        Returns:
            Sync result
        """
        import time
        start_time = time.time()

        with self._lock:
            self._stats["total_syncs"] += 1

            changes_to_sync = []
            conflicts_detected = []
            errors = []
            changes_applied = []

            # Get changes to sync
            if entity_id:
                state = self._sync_states.get(entity_id)
                if state:
                    changes_to_sync = list(state.pending_changes)
            else:
                changes_to_sync = list(self._pending_changes)

            # Process each change
            for change in changes_to_sync:
                try:
                    # Check for conflicts
                    conflict = self._detect_conflict(change)

                    if conflict:
                        conflicts_detected.append(conflict)
                        self._conflicts[conflict.conflict_id] = conflict
                        self._stats["conflicts_detected"] += 1

                        # Try to resolve based on strategy
                        resolved = self._resolve_conflict(conflict)
                        if resolved:
                            change = self._create_resolved_change(conflict)
                            changes_applied.append(change)
                        else:
                            # Mark state as conflict
                            state = self._sync_states.get(change.entity_id)
                            if state:
                                state.status = SyncStatus.CONFLICT
                                state.conflicts.append(conflict)
                    else:
                        # Apply change
                        success = self._apply_change(change)
                        if success:
                            changes_applied.append(change)
                            self._stats["changes_applied"] += 1
                        else:
                            errors.append(f"Failed to apply change {change.change_id}")

                except Exception as e:
                    errors.append(f"Error processing change {change.change_id}: {str(e)}")

            # Clear pending changes that were processed
            self._pending_changes = [
                c for c in self._pending_changes
                if c not in changes_to_sync
            ]

            # Update sync states
            for change in changes_applied:
                state = self._sync_states.get(change.entity_id)
                if state:
                    state.pending_changes = [
                        c for c in state.pending_changes
                        if c.change_id != change.change_id
                    ]
                    if not state.pending_changes and not state.conflicts:
                        state.status = SyncStatus.SYNCED
                    state.last_sync = datetime.utcnow()
                    state.checksum = change.checksum

            duration_ms = (time.time() - start_time) * 1000

            if not errors:
                self._stats["successful_syncs"] += 1

            return SyncResult(
                success=len(errors) == 0,
                synced_count=len(changes_applied),
                conflict_count=len(conflicts_detected),
                error_count=len(errors),
                duration_ms=duration_ms,
                changes_applied=changes_applied,
                conflicts_detected=conflicts_detected,
                errors=errors,
            )

    def receive_changes(
        self,
        changes: List[Dict[str, Any]],
        source: str = "physical"
    ) -> SyncResult:
        """
        Receive and process changes from external source.

        Args:
            changes: List of change dictionaries
            source: Source of changes

        Returns:
            Sync result
        """
        import time
        start_time = time.time()

        with self._lock:
            conflicts_detected = []
            changes_applied = []
            errors = []

            for change_data in changes:
                try:
                    # Parse change
                    change = self._parse_change(change_data, source)

                    # Check for conflicts with local changes
                    conflict = self._detect_conflict(change)

                    if conflict:
                        conflicts_detected.append(conflict)
                        self._conflicts[conflict.conflict_id] = conflict

                        resolved = self._resolve_conflict(conflict)
                        if resolved:
                            change = self._create_resolved_change(conflict)
                    else:
                        # Apply change
                        success = self._apply_change(change)
                        if success:
                            changes_applied.append(change)

                            # Update sync state
                            state = self._get_or_create_state(change.entity_id)
                            state.physical_version = change.version
                            state.last_sync = datetime.utcnow()

                except Exception as e:
                    errors.append(f"Error receiving change: {str(e)}")

            duration_ms = (time.time() - start_time) * 1000

            return SyncResult(
                success=len(errors) == 0,
                synced_count=len(changes_applied),
                conflict_count=len(conflicts_detected),
                error_count=len(errors),
                duration_ms=duration_ms,
                changes_applied=changes_applied,
                conflicts_detected=conflicts_detected,
                errors=errors,
            )

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
        resolved_value: Any = None
    ) -> bool:
        """
        Manually resolve a conflict.

        Args:
            conflict_id: Conflict to resolve
            resolution: Resolution type ("physical", "digital", "merged", "custom")
            resolved_value: Custom resolved value

        Returns:
            Success status
        """
        with self._lock:
            conflict = self._conflicts.get(conflict_id)
            if conflict is None:
                return False

            if resolution == "physical":
                conflict.resolved_value = conflict.physical_change.new_value
            elif resolution == "digital":
                conflict.resolved_value = conflict.digital_change.new_value
            elif resolution == "custom" and resolved_value is not None:
                conflict.resolved_value = resolved_value
            else:
                return False

            conflict.resolved = True
            conflict.resolution = resolution
            conflict.resolved_at = datetime.utcnow()

            # Apply resolution
            resolved_change = self._create_resolved_change(conflict)
            self._apply_change(resolved_change)

            # Update sync state
            state = self._sync_states.get(conflict.entity_id)
            if state:
                state.conflicts = [c for c in state.conflicts if c.conflict_id != conflict_id]
                if not state.conflicts and not state.pending_changes:
                    state.status = SyncStatus.SYNCED

            self._stats["conflicts_resolved"] += 1
            return True

    def get_pending_changes(
        self,
        entity_id: Optional[str] = None
    ) -> List[Change]:
        """Get pending changes."""
        with self._lock:
            if entity_id:
                state = self._sync_states.get(entity_id)
                return list(state.pending_changes) if state else []
            return list(self._pending_changes)

    def get_conflicts(
        self,
        entity_id: Optional[str] = None,
        unresolved_only: bool = True
    ) -> List[Conflict]:
        """Get conflicts."""
        with self._lock:
            conflicts = list(self._conflicts.values())

            if entity_id:
                conflicts = [c for c in conflicts if c.entity_id == entity_id]

            if unresolved_only:
                conflicts = [c for c in conflicts if not c.resolved]

            return conflicts

    def get_sync_state(self, entity_id: str) -> Optional[SyncState]:
        """Get sync state for an entity."""
        with self._lock:
            return self._sync_states.get(entity_id)

    def set_online(self, online: bool):
        """Set online status."""
        with self._lock:
            was_offline = not self._is_online
            self._is_online = online

            if online and was_offline:
                # Flush offline queue
                self._pending_changes.extend(self._offline_queue)
                self._offline_queue.clear()

    def is_online(self) -> bool:
        """Check if online."""
        return self._is_online

    def register_change_handler(
        self,
        entity_type: str,
        handler: Callable[[Change], bool]
    ):
        """Register a handler for changes."""
        self._change_handlers[entity_type].append(handler)

    def get_statistics(self) -> Dict[str, Any]:
        """Get sync statistics."""
        with self._lock:
            return {
                **self._stats,
                "pending_changes": len(self._pending_changes),
                "offline_queue": len(self._offline_queue),
                "active_conflicts": len([c for c in self._conflicts.values() if not c.resolved]),
                "tracked_entities": len(self._sync_states),
                "is_online": self._is_online,
            }

    def _get_or_create_state(self, entity_id: str) -> SyncState:
        """Get or create sync state."""
        if entity_id not in self._sync_states:
            self._sync_states[entity_id] = SyncState(
                entity_id=entity_id,
                physical_version=0,
                digital_version=0,
                last_sync=datetime.utcnow(),
                status=SyncStatus.SYNCED,
            )
        return self._sync_states[entity_id]

    def _get_vector_clock(self, entity_id: str) -> VectorClock:
        """Get vector clock for entity."""
        if entity_id not in self._vector_clocks:
            self._vector_clocks[entity_id] = VectorClock(self.node_id)
        return self._vector_clocks[entity_id]

    def _calculate_checksum(self, value: Any) -> str:
        """Calculate checksum for value."""
        if not self.config.enable_checksums:
            return ""

        try:
            data = json.dumps(value, sort_keys=True, default=str)
            return hashlib.md5(data.encode()).hexdigest()
        except Exception:
            return ""

    def _detect_conflict(self, change: Change) -> Optional[Conflict]:
        """Detect if change conflicts with pending changes."""
        state = self._sync_states.get(change.entity_id)
        if state is None:
            return None

        # Check for conflicting changes
        for pending in state.pending_changes:
            if (pending.property_path == change.property_path and
                pending.source != change.source and
                pending.change_id != change.change_id):

                # Check vector clocks for concurrency
                vc1 = VectorClock.from_dict(
                    self.node_id,
                    pending.metadata.get("vector_clock", {})
                )
                vc2 = VectorClock.from_dict(
                    self.node_id,
                    change.metadata.get("vector_clock", {})
                )

                if vc1.concurrent(vc2):
                    # Concurrent changes = conflict
                    physical = change if change.source == "physical" else pending
                    digital = pending if change.source == "physical" else change

                    return Conflict(
                        conflict_id=str(uuid.uuid4()),
                        entity_id=change.entity_id,
                        property_path=change.property_path,
                        physical_change=physical,
                        digital_change=digital,
                        detected_at=datetime.utcnow(),
                    )

        return None

    def _resolve_conflict(self, conflict: Conflict) -> bool:
        """Resolve conflict using configured strategy."""
        strategy = self.config.conflict_strategy

        if strategy == ConflictStrategy.MANUAL:
            return False

        if strategy == ConflictStrategy.LAST_WRITE_WINS:
            if conflict.physical_change.timestamp > conflict.digital_change.timestamp:
                conflict.resolved_value = conflict.physical_change.new_value
                conflict.resolution = "physical_wins_lww"
            else:
                conflict.resolved_value = conflict.digital_change.new_value
                conflict.resolution = "digital_wins_lww"

        elif strategy == ConflictStrategy.PHYSICAL_WINS:
            conflict.resolved_value = conflict.physical_change.new_value
            conflict.resolution = "physical_wins"

        elif strategy == ConflictStrategy.DIGITAL_WINS:
            conflict.resolved_value = conflict.digital_change.new_value
            conflict.resolution = "digital_wins"

        elif strategy == ConflictStrategy.MERGE:
            # Attempt to merge (for compatible types)
            merged = self._merge_values(
                conflict.physical_change.new_value,
                conflict.digital_change.new_value,
            )
            if merged is not None:
                conflict.resolved_value = merged
                conflict.resolution = "merged"
            else:
                # Fall back to LWW
                if conflict.physical_change.timestamp > conflict.digital_change.timestamp:
                    conflict.resolved_value = conflict.physical_change.new_value
                else:
                    conflict.resolved_value = conflict.digital_change.new_value
                conflict.resolution = "merge_fallback_lww"

        conflict.resolved = True
        conflict.resolved_at = datetime.utcnow()
        self._stats["conflicts_resolved"] += 1

        return True

    def _merge_values(self, value1: Any, value2: Any) -> Optional[Any]:
        """Attempt to merge two values."""
        # Dict merge
        if isinstance(value1, dict) and isinstance(value2, dict):
            merged = {**value1, **value2}
            return merged

        # List merge (union)
        if isinstance(value1, list) and isinstance(value2, list):
            merged = list(set(value1) | set(value2))
            return merged

        # Numeric average
        if isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
            return (value1 + value2) / 2

        return None

    def _create_resolved_change(self, conflict: Conflict) -> Change:
        """Create a change from resolved conflict."""
        return Change(
            change_id=str(uuid.uuid4()),
            entity_id=conflict.entity_id,
            entity_type=conflict.physical_change.entity_type,
            change_type=ChangeType.UPDATE,
            property_path=conflict.property_path,
            old_value=None,  # Unknown after conflict
            new_value=conflict.resolved_value,
            timestamp=datetime.utcnow(),
            source="resolution",
            version=max(
                conflict.physical_change.version,
                conflict.digital_change.version
            ) + 1,
            checksum=self._calculate_checksum(conflict.resolved_value),
            metadata={"conflict_id": conflict.conflict_id},
        )

    def _apply_change(self, change: Change) -> bool:
        """Apply a change via handlers."""
        handlers = self._change_handlers.get(change.entity_type, [])

        if not handlers:
            # No handlers, consider it applied
            return True

        for handler in handlers:
            try:
                if not handler(change):
                    return False
            except Exception:
                return False

        return True

    def _parse_change(self, data: Dict[str, Any], source: str) -> Change:
        """Parse change from dictionary."""
        return Change(
            change_id=data.get("change_id", str(uuid.uuid4())),
            entity_id=data["entity_id"],
            entity_type=data["entity_type"],
            change_type=ChangeType(data["change_type"]),
            property_path=data["property_path"],
            old_value=data.get("old_value"),
            new_value=data["new_value"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else datetime.utcnow(),
            source=source,
            version=data.get("version", 1),
            checksum=data.get("checksum", ""),
            metadata=data.get("metadata", {}),
        )


# Singleton instance
_sync_protocol: Optional[SyncProtocol] = None


def get_sync_protocol() -> SyncProtocol:
    """Get or create the sync protocol instance."""
    global _sync_protocol
    if _sync_protocol is None:
        _sync_protocol = SyncProtocol()
    return _sync_protocol
