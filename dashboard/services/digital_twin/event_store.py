"""
Event Store - Immutable Event Log for Digital Twin

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- Append-only event storage
- Event replay and projection
- Snapshot management
- Event querying
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Iterator, Tuple
from enum import Enum
import threading
import uuid
import json
from collections import defaultdict

from .event_types import TwinEvent, EventCategory, EventPriority


class StorageBackend(Enum):
    """Storage backend types."""
    MEMORY = "memory"
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    REDIS = "redis"


class SnapshotStrategy(Enum):
    """Snapshot creation strategies."""
    EVERY_N_EVENTS = "every_n_events"
    TIME_INTERVAL = "time_interval"
    ON_DEMAND = "on_demand"


@dataclass
class EventStream:
    """A stream of events for a specific aggregate."""
    stream_id: str
    aggregate_type: str
    events: List[TwinEvent] = field(default_factory=list)
    current_version: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_event_at: Optional[datetime] = None


@dataclass
class Snapshot:
    """State snapshot for fast reconstruction."""
    snapshot_id: str
    stream_id: str
    version: int
    state: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    event_count: int = 0
    size_bytes: int = 0


@dataclass
class EventStoreConfig:
    """Event store configuration."""
    backend: StorageBackend = StorageBackend.MEMORY
    snapshot_strategy: SnapshotStrategy = SnapshotStrategy.EVERY_N_EVENTS
    snapshot_interval: int = 100  # Events between snapshots
    max_events_in_memory: int = 10000
    enable_indexing: bool = True
    enable_compression: bool = False
    retention_days: Optional[int] = None


@dataclass
class EventQuery:
    """Query parameters for event retrieval."""
    stream_id: Optional[str] = None
    category: Optional[EventCategory] = None
    event_type: Optional[str] = None
    from_version: Optional[int] = None
    to_version: Optional[int] = None
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    min_priority: Optional[EventPriority] = None
    limit: int = 1000
    offset: int = 0


@dataclass
class AppendResult:
    """Result of appending events."""
    success: bool
    stream_id: str
    new_version: int
    events_appended: int
    error: Optional[str] = None


class EventStore:
    """
    Immutable event store for Digital Twin event sourcing.

    Features:
    - Append-only storage
    - Optimistic concurrency control
    - Event replay and projection
    - Snapshot management
    - Multiple storage backends
    """

    def __init__(self, config: Optional[EventStoreConfig] = None):
        """
        Initialize event store.

        Args:
            config: Event store configuration
        """
        self.config = config or EventStoreConfig()

        # In-memory storage
        self._streams: Dict[str, EventStream] = {}
        self._snapshots: Dict[str, List[Snapshot]] = defaultdict(list)
        self._global_sequence: int = 0

        # Indexes
        self._category_index: Dict[str, List[str]] = defaultdict(list)
        self._type_index: Dict[str, List[str]] = defaultdict(list)
        self._time_index: List[Tuple[datetime, str, str]] = []

        # Subscriptions
        self._subscribers: Dict[str, List[Callable[[TwinEvent], None]]] = defaultdict(list)
        self._global_subscribers: List[Callable[[TwinEvent], None]] = []

        # Thread safety
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            "total_events": 0,
            "total_streams": 0,
            "total_snapshots": 0,
            "appends": 0,
            "reads": 0,
            "replays": 0,
        }

    def append(
        self,
        stream_id: str,
        events: List[TwinEvent],
        expected_version: Optional[int] = None,
        aggregate_type: str = "twin"
    ) -> AppendResult:
        """
        Append events to a stream.

        Args:
            stream_id: Stream identifier
            events: Events to append
            expected_version: Expected current version (optimistic concurrency)
            aggregate_type: Type of aggregate

        Returns:
            Append result
        """
        if not events:
            return AppendResult(
                success=True,
                stream_id=stream_id,
                new_version=self._get_stream_version(stream_id),
                events_appended=0,
            )

        with self._lock:
            # Get or create stream
            stream = self._streams.get(stream_id)

            if stream is None:
                stream = EventStream(
                    stream_id=stream_id,
                    aggregate_type=aggregate_type,
                )
                self._streams[stream_id] = stream
                self._stats["total_streams"] += 1

            # Optimistic concurrency check
            if expected_version is not None:
                if stream.current_version != expected_version:
                    return AppendResult(
                        success=False,
                        stream_id=stream_id,
                        new_version=stream.current_version,
                        events_appended=0,
                        error=f"Concurrency conflict: expected {expected_version}, got {stream.current_version}",
                    )

            # Assign sequence numbers and append
            for event in events:
                stream.current_version += 1
                self._global_sequence += 1

                # Update event with sequence number
                event.sequence_number = stream.current_version

                # Append to stream
                stream.events.append(event)
                stream.last_event_at = event.timestamp

                # Update indexes
                if self.config.enable_indexing:
                    self._index_event(event, stream_id)

                # Notify subscribers
                self._notify_subscribers(event, stream_id)

                self._stats["total_events"] += 1

            self._stats["appends"] += 1

            # Check if snapshot needed
            if self._should_create_snapshot(stream):
                self._create_snapshot(stream)

            return AppendResult(
                success=True,
                stream_id=stream_id,
                new_version=stream.current_version,
                events_appended=len(events),
            )

    def read_stream(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[TwinEvent]:
        """
        Read events from a stream.

        Args:
            stream_id: Stream identifier
            from_version: Start version (inclusive)
            to_version: End version (inclusive)
            limit: Maximum events to return

        Returns:
            List of events
        """
        with self._lock:
            self._stats["reads"] += 1

            stream = self._streams.get(stream_id)
            if stream is None:
                return []

            events = stream.events

            # Filter by version
            filtered = [
                e for e in events
                if e.sequence_number >= from_version and
                (to_version is None or e.sequence_number <= to_version)
            ]

            # Apply limit
            if limit is not None:
                filtered = filtered[:limit]

            return filtered

    def read_all(
        self,
        from_sequence: int = 0,
        limit: int = 1000
    ) -> List[TwinEvent]:
        """
        Read all events across streams.

        Args:
            from_sequence: Global sequence to start from
            limit: Maximum events to return

        Returns:
            List of events ordered by time
        """
        with self._lock:
            all_events = []

            for stream in self._streams.values():
                all_events.extend(stream.events)

            # Sort by timestamp
            all_events.sort(key=lambda e: e.timestamp)

            # Filter and limit
            filtered = [e for e in all_events if e.sequence_number >= from_sequence]
            return filtered[:limit]

    def query(self, query: EventQuery) -> List[TwinEvent]:
        """
        Query events with filters.

        Args:
            query: Query parameters

        Returns:
            Matching events
        """
        with self._lock:
            self._stats["reads"] += 1

            # Start with all events or stream-specific
            if query.stream_id:
                stream = self._streams.get(query.stream_id)
                if stream is None:
                    return []
                events = list(stream.events)
            else:
                events = []
                for stream in self._streams.values():
                    events.extend(stream.events)

            # Apply filters
            if query.category:
                events = [e for e in events if e.category == query.category]

            if query.event_type:
                events = [e for e in events if e.event_type == query.event_type]

            if query.from_version:
                events = [e for e in events if e.sequence_number >= query.from_version]

            if query.to_version:
                events = [e for e in events if e.sequence_number <= query.to_version]

            if query.from_time:
                events = [e for e in events if e.timestamp >= query.from_time]

            if query.to_time:
                events = [e for e in events if e.timestamp <= query.to_time]

            if query.min_priority:
                events = [e for e in events if e.priority.value >= query.min_priority.value]

            # Sort by timestamp
            events.sort(key=lambda e: e.timestamp)

            # Apply offset and limit
            return events[query.offset:query.offset + query.limit]

    def replay(
        self,
        stream_id: str,
        projector: Callable[[Dict[str, Any], TwinEvent], Dict[str, Any]],
        initial_state: Optional[Dict[str, Any]] = None,
        from_version: int = 0
    ) -> Dict[str, Any]:
        """
        Replay events to rebuild state.

        Args:
            stream_id: Stream to replay
            projector: Function to apply events to state
            initial_state: Starting state
            from_version: Version to start replay from

        Returns:
            Reconstructed state
        """
        with self._lock:
            self._stats["replays"] += 1

            state = initial_state or {}

            # Try to start from snapshot
            snapshot = self._get_latest_snapshot(stream_id, from_version)
            if snapshot:
                state = snapshot.state.copy()
                from_version = snapshot.version + 1

            # Replay events
            events = self.read_stream(stream_id, from_version)

            for event in events:
                state = projector(state, event)

            return state

    def replay_all(
        self,
        projector: Callable[[Dict[str, Dict[str, Any]], TwinEvent], Dict[str, Dict[str, Any]]],
        initial_state: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Replay all events across all streams.

        Args:
            projector: Function to apply events to state
            initial_state: Starting state (dict of stream_id -> state)

        Returns:
            Reconstructed state for all streams
        """
        with self._lock:
            state = initial_state or {}

            all_events = self.read_all(limit=self.config.max_events_in_memory)

            for event in all_events:
                state = projector(state, event)

            return state

    def subscribe(
        self,
        stream_id: Optional[str],
        handler: Callable[[TwinEvent], None]
    ) -> str:
        """
        Subscribe to events.

        Args:
            stream_id: Stream to subscribe to (None for all)
            handler: Event handler function

        Returns:
            Subscription ID
        """
        subscription_id = str(uuid.uuid4())

        with self._lock:
            if stream_id is None:
                self._global_subscribers.append(handler)
            else:
                self._subscribers[stream_id].append(handler)

        return subscription_id

    def unsubscribe(self, stream_id: Optional[str], handler: Callable):
        """Unsubscribe from events."""
        with self._lock:
            if stream_id is None:
                if handler in self._global_subscribers:
                    self._global_subscribers.remove(handler)
            else:
                if handler in self._subscribers[stream_id]:
                    self._subscribers[stream_id].remove(handler)

    def create_snapshot(self, stream_id: str, state: Dict[str, Any]) -> Snapshot:
        """
        Create a manual snapshot.

        Args:
            stream_id: Stream to snapshot
            state: Current state

        Returns:
            Created snapshot
        """
        with self._lock:
            stream = self._streams.get(stream_id)
            version = stream.current_version if stream else 0

            snapshot = Snapshot(
                snapshot_id=str(uuid.uuid4()),
                stream_id=stream_id,
                version=version,
                state=state,
                event_count=len(stream.events) if stream else 0,
                size_bytes=len(json.dumps(state)),
            )

            self._snapshots[stream_id].append(snapshot)
            self._stats["total_snapshots"] += 1

            return snapshot

    def get_snapshot(
        self,
        stream_id: str,
        version: Optional[int] = None
    ) -> Optional[Snapshot]:
        """
        Get a snapshot.

        Args:
            stream_id: Stream ID
            version: Specific version (latest if None)

        Returns:
            Snapshot or None
        """
        with self._lock:
            snapshots = self._snapshots.get(stream_id, [])

            if not snapshots:
                return None

            if version is None:
                return snapshots[-1]

            for snapshot in reversed(snapshots):
                if snapshot.version <= version:
                    return snapshot

            return None

    def get_stream_info(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get stream information."""
        with self._lock:
            stream = self._streams.get(stream_id)
            if stream is None:
                return None

            return {
                "stream_id": stream.stream_id,
                "aggregate_type": stream.aggregate_type,
                "current_version": stream.current_version,
                "event_count": len(stream.events),
                "created_at": stream.created_at.isoformat(),
                "last_event_at": stream.last_event_at.isoformat() if stream.last_event_at else None,
                "snapshot_count": len(self._snapshots.get(stream_id, [])),
            }

    def list_streams(
        self,
        aggregate_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List all streams."""
        with self._lock:
            streams = []

            for stream_id, stream in self._streams.items():
                if aggregate_type and stream.aggregate_type != aggregate_type:
                    continue

                streams.append({
                    "stream_id": stream.stream_id,
                    "aggregate_type": stream.aggregate_type,
                    "current_version": stream.current_version,
                    "event_count": len(stream.events),
                })

                if len(streams) >= limit:
                    break

            return streams

    def delete_stream(self, stream_id: str) -> bool:
        """
        Delete a stream (soft delete - marks as deleted).

        Note: In event sourcing, we typically don't delete.
        This marks the stream as archived.
        """
        with self._lock:
            stream = self._streams.get(stream_id)
            if stream is None:
                return False

            # Create archive event
            archive_event = TwinEvent.create(
                event_type="stream_archived",
                category=EventCategory.SYSTEM,
                twin_id=stream_id,
                data={"reason": "manual_deletion"},
            )

            self.append(stream_id, [archive_event])
            return True

    def compact(
        self,
        stream_id: str,
        keep_last_n: int = 100
    ) -> int:
        """
        Compact a stream by creating snapshot and removing old events.

        Note: Use with caution - breaks immutability guarantee.

        Args:
            stream_id: Stream to compact
            keep_last_n: Number of recent events to keep

        Returns:
            Number of events removed
        """
        with self._lock:
            stream = self._streams.get(stream_id)
            if stream is None or len(stream.events) <= keep_last_n:
                return 0

            events_to_remove = len(stream.events) - keep_last_n

            # Create snapshot of current state first
            # In real implementation, would replay to get state
            state = {"compacted": True, "original_count": len(stream.events)}
            self.create_snapshot(stream_id, state)

            # Remove old events
            stream.events = stream.events[-keep_last_n:]

            return events_to_remove

    def get_statistics(self) -> Dict[str, Any]:
        """Get event store statistics."""
        with self._lock:
            return {
                **self._stats,
                "streams": len(self._streams),
                "memory_events": sum(len(s.events) for s in self._streams.values()),
                "snapshots": sum(len(s) for s in self._snapshots.values()),
                "global_sequence": self._global_sequence,
            }

    def _get_stream_version(self, stream_id: str) -> int:
        """Get current stream version."""
        stream = self._streams.get(stream_id)
        return stream.current_version if stream else 0

    def _index_event(self, event: TwinEvent, stream_id: str):
        """Add event to indexes."""
        event_ref = f"{stream_id}:{event.sequence_number}"

        self._category_index[event.category.value].append(event_ref)
        self._type_index[event.event_type].append(event_ref)
        self._time_index.append((event.timestamp, stream_id, str(event.sequence_number)))

    def _notify_subscribers(self, event: TwinEvent, stream_id: str):
        """Notify event subscribers."""
        # Stream-specific subscribers
        for handler in self._subscribers.get(stream_id, []):
            try:
                handler(event)
            except Exception:
                pass  # Don't let subscriber errors affect storage

        # Global subscribers
        for handler in self._global_subscribers:
            try:
                handler(event)
            except Exception:
                pass

    def _should_create_snapshot(self, stream: EventStream) -> bool:
        """Check if snapshot should be created."""
        if self.config.snapshot_strategy == SnapshotStrategy.ON_DEMAND:
            return False

        if self.config.snapshot_strategy == SnapshotStrategy.EVERY_N_EVENTS:
            snapshots = self._snapshots.get(stream.stream_id, [])
            last_snapshot_version = snapshots[-1].version if snapshots else 0
            return stream.current_version - last_snapshot_version >= self.config.snapshot_interval

        return False

    def _create_snapshot(self, stream: EventStream):
        """Create automatic snapshot."""
        # In real implementation, would replay events to get state
        state = {
            "auto_snapshot": True,
            "version": stream.current_version,
            "event_count": len(stream.events),
        }

        snapshot = Snapshot(
            snapshot_id=str(uuid.uuid4()),
            stream_id=stream.stream_id,
            version=stream.current_version,
            state=state,
            event_count=len(stream.events),
        )

        self._snapshots[stream.stream_id].append(snapshot)
        self._stats["total_snapshots"] += 1

    def _get_latest_snapshot(
        self,
        stream_id: str,
        before_version: int
    ) -> Optional[Snapshot]:
        """Get latest snapshot before version."""
        snapshots = self._snapshots.get(stream_id, [])

        for snapshot in reversed(snapshots):
            if snapshot.version < before_version:
                return snapshot

        return None


class EventStoreProjection:
    """
    Projection for building read models from events.
    """

    def __init__(
        self,
        event_store: EventStore,
        name: str,
        handlers: Dict[str, Callable[[Dict[str, Any], TwinEvent], Dict[str, Any]]]
    ):
        """
        Initialize projection.

        Args:
            event_store: Event store to project from
            name: Projection name
            handlers: Event type -> handler mapping
        """
        self.event_store = event_store
        self.name = name
        self.handlers = handlers
        self.state: Dict[str, Any] = {}
        self.last_position: int = 0

    def rebuild(self):
        """Rebuild projection from scratch."""
        self.state = {}
        self.last_position = 0
        self.catch_up()

    def catch_up(self):
        """Catch up to latest events."""
        events = self.event_store.read_all(
            from_sequence=self.last_position,
            limit=10000,
        )

        for event in events:
            handler = self.handlers.get(event.event_type)
            if handler:
                self.state = handler(self.state, event)
            self.last_position = event.sequence_number

    def get_state(self) -> Dict[str, Any]:
        """Get current projection state."""
        return self.state


# Singleton instance
_event_store: Optional[EventStore] = None


def get_event_store() -> EventStore:
    """Get or create the event store instance."""
    global _event_store
    if _event_store is None:
        _event_store = EventStore()
    return _event_store
