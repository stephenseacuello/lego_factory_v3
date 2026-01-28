"""
Event Sourcing for Manufacturing Digital Twins.

This module implements complete event sourcing for manufacturing operations:
- Domain events with causal ordering
- Event streams with snapshots
- Aggregate roots for consistency
- Projections for read models

Research Value:
- Novel event types for manufacturing domain
- Temporal queries for process analysis
- Event-driven architecture patterns

References:
- Fowler, M. (2005). Event Sourcing
- Vernon, V. (2013). Implementing Domain-Driven Design
- ISO 23247 Digital Twin Framework
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import (
    Dict, List, Optional, Set, Any, TypeVar, Generic,
    Callable, Iterator, Tuple, Union
)
from uuid import UUID, uuid4
import json
import hashlib
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# Domain Events
# =============================================================================

class EventType(Enum):
    """Manufacturing domain event types."""
    # Brick Events
    BRICK_CREATED = auto()
    BRICK_MODIFIED = auto()
    BRICK_DELETED = auto()
    BRICK_QUALITY_CHECKED = auto()

    # Print Job Events
    PRINT_JOB_CREATED = auto()
    PRINT_JOB_STARTED = auto()
    PRINT_JOB_PAUSED = auto()
    PRINT_JOB_RESUMED = auto()
    PRINT_JOB_COMPLETED = auto()
    PRINT_JOB_FAILED = auto()
    PRINT_JOB_CANCELLED = auto()

    # Layer Events (for print process)
    LAYER_STARTED = auto()
    LAYER_COMPLETED = auto()
    LAYER_DEFECT_DETECTED = auto()

    # Quality Events
    INSPECTION_STARTED = auto()
    INSPECTION_COMPLETED = auto()
    DEFECT_DETECTED = auto()
    DEFECT_RESOLVED = auto()
    QUALITY_APPROVED = auto()
    QUALITY_REJECTED = auto()

    # Machine Events
    MACHINE_STARTED = auto()
    MACHINE_STOPPED = auto()
    MACHINE_MAINTENANCE_STARTED = auto()
    MACHINE_MAINTENANCE_COMPLETED = auto()
    MACHINE_CALIBRATED = auto()
    MACHINE_ERROR = auto()

    # Material Events
    MATERIAL_LOADED = auto()
    MATERIAL_UNLOADED = auto()
    MATERIAL_CONSUMED = auto()
    MATERIAL_LOW_ALERT = auto()

    # Process Events
    TEMPERATURE_CHANGED = auto()
    SPEED_CHANGED = auto()
    PARAMETER_ADJUSTED = auto()

    # Order Events
    ORDER_CREATED = auto()
    ORDER_SCHEDULED = auto()
    ORDER_STARTED = auto()
    ORDER_COMPLETED = auto()
    ORDER_SHIPPED = auto()


@dataclass(frozen=True)
class EventMetadata:
    """Metadata for domain events."""
    correlation_id: UUID  # Groups related events
    causation_id: Optional[UUID]  # Event that caused this event
    user_id: Optional[str]  # User who triggered event
    source_system: str  # System that generated event
    timestamp: datetime
    schema_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'correlation_id': str(self.correlation_id),
            'causation_id': str(self.causation_id) if self.causation_id else None,
            'user_id': self.user_id,
            'source_system': self.source_system,
            'timestamp': self.timestamp.isoformat(),
            'schema_version': self.schema_version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EventMetadata':
        return cls(
            correlation_id=UUID(data['correlation_id']),
            causation_id=UUID(data['causation_id']) if data.get('causation_id') else None,
            user_id=data.get('user_id'),
            source_system=data['source_system'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            schema_version=data.get('schema_version', 1)
        )


@dataclass(frozen=True)
class DomainEvent:
    """
    Immutable domain event representing a state change.

    Events are the source of truth in event sourcing.
    """
    event_id: UUID
    event_type: EventType
    aggregate_id: UUID
    aggregate_type: str
    version: int  # Aggregate version after this event
    payload: Dict[str, Any]
    metadata: EventMetadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': str(self.event_id),
            'event_type': self.event_type.name,
            'aggregate_id': str(self.aggregate_id),
            'aggregate_type': self.aggregate_type,
            'version': self.version,
            'payload': self.payload,
            'metadata': self.metadata.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DomainEvent':
        return cls(
            event_id=UUID(data['event_id']),
            event_type=EventType[data['event_type']],
            aggregate_id=UUID(data['aggregate_id']),
            aggregate_type=data['aggregate_type'],
            version=data['version'],
            payload=data['payload'],
            metadata=EventMetadata.from_dict(data['metadata'])
        )

    def get_hash(self) -> str:
        """Get cryptographic hash of event for integrity verification."""
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


# =============================================================================
# Event Stream
# =============================================================================

@dataclass
class EventStream:
    """
    Stream of events for an aggregate.

    Provides temporal queries and versioning.
    """
    aggregate_id: UUID
    aggregate_type: str
    events: List[DomainEvent] = field(default_factory=list)

    @property
    def version(self) -> int:
        """Current version of the aggregate."""
        return self.events[-1].version if self.events else 0

    @property
    def created_at(self) -> Optional[datetime]:
        """When the aggregate was created."""
        return self.events[0].metadata.timestamp if self.events else None

    @property
    def updated_at(self) -> Optional[datetime]:
        """When the aggregate was last updated."""
        return self.events[-1].metadata.timestamp if self.events else None

    def append(self, event: DomainEvent) -> None:
        """Append event to stream with version validation."""
        expected_version = self.version + 1
        if event.version != expected_version:
            raise ValueError(
                f"Version mismatch: expected {expected_version}, got {event.version}"
            )
        self.events.append(event)

    def get_events_after(self, version: int) -> List[DomainEvent]:
        """Get events after a specific version."""
        return [e for e in self.events if e.version > version]

    def get_events_between(
        self,
        start: datetime,
        end: datetime
    ) -> List[DomainEvent]:
        """Get events within a time range."""
        return [
            e for e in self.events
            if start <= e.metadata.timestamp <= end
        ]

    def get_events_by_type(self, event_type: EventType) -> List[DomainEvent]:
        """Get events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def get_events_by_correlation(self, correlation_id: UUID) -> List[DomainEvent]:
        """Get events with the same correlation ID."""
        return [
            e for e in self.events
            if e.metadata.correlation_id == correlation_id
        ]

    def replay_to_version(self, version: int) -> List[DomainEvent]:
        """Get events up to a specific version for replay."""
        return [e for e in self.events if e.version <= version]


# =============================================================================
# Snapshots
# =============================================================================

@dataclass
class Snapshot:
    """
    Point-in-time snapshot of aggregate state.

    Used for performance optimization in event replay.
    """
    snapshot_id: UUID
    aggregate_id: UUID
    aggregate_type: str
    version: int
    state: Dict[str, Any]
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'snapshot_id': str(self.snapshot_id),
            'aggregate_id': str(self.aggregate_id),
            'aggregate_type': self.aggregate_type,
            'version': self.version,
            'state': self.state,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Snapshot':
        return cls(
            snapshot_id=UUID(data['snapshot_id']),
            aggregate_id=UUID(data['aggregate_id']),
            aggregate_type=data['aggregate_type'],
            version=data['version'],
            state=data['state'],
            created_at=datetime.fromisoformat(data['created_at'])
        )


# =============================================================================
# Aggregate Root
# =============================================================================

T = TypeVar('T', bound='Aggregate')


class Aggregate(ABC):
    """
    Abstract base class for aggregate roots.

    Aggregates are consistency boundaries that:
    - Encapsulate domain logic
    - Emit events for state changes
    - Can be rebuilt from events
    """

    def __init__(self, aggregate_id: UUID):
        self._id = aggregate_id
        self._version = 0
        self._pending_events: List[DomainEvent] = []
        self._correlation_id: Optional[UUID] = None
        self._causation_id: Optional[UUID] = None

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def version(self) -> int:
        return self._version

    @property
    def pending_events(self) -> List[DomainEvent]:
        return self._pending_events.copy()

    def clear_pending_events(self) -> List[DomainEvent]:
        """Clear and return pending events after persistence."""
        events = self._pending_events
        self._pending_events = []
        return events

    def set_correlation_context(
        self,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None
    ) -> None:
        """Set correlation context for tracking related events."""
        self._correlation_id = correlation_id
        self._causation_id = causation_id

    def _apply_event(self, event: DomainEvent) -> None:
        """Apply event to update aggregate state."""
        self._version = event.version
        self._when(event)

    def _raise_event(
        self,
        event_type: EventType,
        payload: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> DomainEvent:
        """Raise a new domain event."""
        self._version += 1

        metadata = EventMetadata(
            correlation_id=self._correlation_id or uuid4(),
            causation_id=self._causation_id,
            user_id=user_id,
            source_system='lego-mcp',
            timestamp=datetime.utcnow()
        )

        event = DomainEvent(
            event_id=uuid4(),
            event_type=event_type,
            aggregate_id=self._id,
            aggregate_type=self._get_aggregate_type(),
            version=self._version,
            payload=payload,
            metadata=metadata
        )

        self._pending_events.append(event)
        self._when(event)

        # Next event will be caused by this one
        self._causation_id = event.event_id

        return event

    @abstractmethod
    def _get_aggregate_type(self) -> str:
        """Return the aggregate type name."""
        pass

    @abstractmethod
    def _when(self, event: DomainEvent) -> None:
        """Apply event to update state. Must handle all event types."""
        pass

    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Get current state for snapshotting."""
        pass

    @abstractmethod
    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore state from snapshot."""
        pass

    @classmethod
    def rebuild(
        cls: type[T],
        aggregate_id: UUID,
        events: List[DomainEvent],
        snapshot: Optional[Snapshot] = None
    ) -> T:
        """Rebuild aggregate from events and optional snapshot."""
        aggregate = cls(aggregate_id)

        if snapshot:
            aggregate.restore_state(snapshot.state)
            aggregate._version = snapshot.version
            # Only replay events after snapshot
            events = [e for e in events if e.version > snapshot.version]

        for event in events:
            aggregate._apply_event(event)

        return aggregate


# =============================================================================
# Manufacturing Aggregates
# =============================================================================

class PrintJobAggregate(Aggregate):
    """
    Aggregate for print job lifecycle.

    Tracks the complete lifecycle of a 3D print job.
    """

    def __init__(self, aggregate_id: UUID):
        super().__init__(aggregate_id)
        self.brick_id: Optional[str] = None
        self.status: str = 'pending'
        self.machine_id: Optional[str] = None
        self.current_layer: int = 0
        self.total_layers: int = 0
        self.parameters: Dict[str, Any] = {}
        self.defects: List[Dict[str, Any]] = []
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.quality_result: Optional[str] = None

    def _get_aggregate_type(self) -> str:
        return 'PrintJob'

    def create(
        self,
        brick_id: str,
        total_layers: int,
        parameters: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> DomainEvent:
        """Create a new print job."""
        if self.status != 'pending':
            raise ValueError("Print job already created")

        return self._raise_event(
            EventType.PRINT_JOB_CREATED,
            {
                'brick_id': brick_id,
                'total_layers': total_layers,
                'parameters': parameters
            },
            user_id
        )

    def start(
        self,
        machine_id: str,
        user_id: Optional[str] = None
    ) -> DomainEvent:
        """Start the print job."""
        if self.status != 'created':
            raise ValueError(f"Cannot start job in status: {self.status}")

        return self._raise_event(
            EventType.PRINT_JOB_STARTED,
            {'machine_id': machine_id},
            user_id
        )

    def complete_layer(
        self,
        layer_number: int,
        metrics: Dict[str, float],
        user_id: Optional[str] = None
    ) -> DomainEvent:
        """Mark a layer as completed."""
        if self.status != 'printing':
            raise ValueError(f"Cannot complete layer in status: {self.status}")

        return self._raise_event(
            EventType.LAYER_COMPLETED,
            {
                'layer_number': layer_number,
                'metrics': metrics
            },
            user_id
        )

    def detect_defect(
        self,
        layer_number: int,
        defect_type: str,
        severity: str,
        location: Dict[str, float],
        user_id: Optional[str] = None
    ) -> DomainEvent:
        """Record a detected defect."""
        return self._raise_event(
            EventType.LAYER_DEFECT_DETECTED,
            {
                'layer_number': layer_number,
                'defect_type': defect_type,
                'severity': severity,
                'location': location
            },
            user_id
        )

    def complete(
        self,
        final_metrics: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> DomainEvent:
        """Complete the print job."""
        if self.status != 'printing':
            raise ValueError(f"Cannot complete job in status: {self.status}")

        return self._raise_event(
            EventType.PRINT_JOB_COMPLETED,
            {'final_metrics': final_metrics},
            user_id
        )

    def fail(
        self,
        reason: str,
        error_code: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> DomainEvent:
        """Mark the print job as failed."""
        return self._raise_event(
            EventType.PRINT_JOB_FAILED,
            {
                'reason': reason,
                'error_code': error_code
            },
            user_id
        )

    def approve_quality(
        self,
        inspector_id: str,
        notes: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> DomainEvent:
        """Approve quality of completed print."""
        if self.status != 'completed':
            raise ValueError("Can only approve completed jobs")

        return self._raise_event(
            EventType.QUALITY_APPROVED,
            {
                'inspector_id': inspector_id,
                'notes': notes
            },
            user_id
        )

    def _when(self, event: DomainEvent) -> None:
        """Apply event to update state."""
        if event.event_type == EventType.PRINT_JOB_CREATED:
            self.brick_id = event.payload['brick_id']
            self.total_layers = event.payload['total_layers']
            self.parameters = event.payload['parameters']
            self.status = 'created'

        elif event.event_type == EventType.PRINT_JOB_STARTED:
            self.machine_id = event.payload['machine_id']
            self.status = 'printing'
            self.started_at = event.metadata.timestamp

        elif event.event_type == EventType.LAYER_COMPLETED:
            self.current_layer = event.payload['layer_number']

        elif event.event_type == EventType.LAYER_DEFECT_DETECTED:
            self.defects.append(event.payload)

        elif event.event_type == EventType.PRINT_JOB_COMPLETED:
            self.status = 'completed'
            self.completed_at = event.metadata.timestamp

        elif event.event_type == EventType.PRINT_JOB_FAILED:
            self.status = 'failed'
            self.completed_at = event.metadata.timestamp

        elif event.event_type == EventType.QUALITY_APPROVED:
            self.quality_result = 'approved'

        elif event.event_type == EventType.QUALITY_REJECTED:
            self.quality_result = 'rejected'

    def get_state(self) -> Dict[str, Any]:
        """Get current state for snapshotting."""
        return {
            'brick_id': self.brick_id,
            'status': self.status,
            'machine_id': self.machine_id,
            'current_layer': self.current_layer,
            'total_layers': self.total_layers,
            'parameters': self.parameters,
            'defects': self.defects,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'quality_result': self.quality_result
        }

    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore state from snapshot."""
        self.brick_id = state['brick_id']
        self.status = state['status']
        self.machine_id = state['machine_id']
        self.current_layer = state['current_layer']
        self.total_layers = state['total_layers']
        self.parameters = state['parameters']
        self.defects = state['defects']
        self.started_at = (
            datetime.fromisoformat(state['started_at'])
            if state['started_at'] else None
        )
        self.completed_at = (
            datetime.fromisoformat(state['completed_at'])
            if state['completed_at'] else None
        )
        self.quality_result = state['quality_result']


class MachineAggregate(Aggregate):
    """
    Aggregate for machine/printer state.

    Tracks machine status, maintenance, and operational metrics.
    """

    def __init__(self, aggregate_id: UUID):
        super().__init__(aggregate_id)
        self.name: str = ''
        self.machine_type: str = ''
        self.status: str = 'offline'
        self.current_job_id: Optional[UUID] = None
        self.maintenance_due: Optional[datetime] = None
        self.total_print_hours: float = 0.0
        self.error_count: int = 0
        self.last_calibration: Optional[datetime] = None

    def _get_aggregate_type(self) -> str:
        return 'Machine'

    def _when(self, event: DomainEvent) -> None:
        """Apply event to update state."""
        if event.event_type == EventType.MACHINE_STARTED:
            self.status = 'running'
            self.current_job_id = UUID(event.payload.get('job_id')) if event.payload.get('job_id') else None

        elif event.event_type == EventType.MACHINE_STOPPED:
            self.status = 'idle'
            self.current_job_id = None
            if 'print_duration_hours' in event.payload:
                self.total_print_hours += event.payload['print_duration_hours']

        elif event.event_type == EventType.MACHINE_MAINTENANCE_STARTED:
            self.status = 'maintenance'

        elif event.event_type == EventType.MACHINE_MAINTENANCE_COMPLETED:
            self.status = 'idle'
            self.maintenance_due = None

        elif event.event_type == EventType.MACHINE_CALIBRATED:
            self.last_calibration = event.metadata.timestamp

        elif event.event_type == EventType.MACHINE_ERROR:
            self.error_count += 1
            self.status = 'error'

    def get_state(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'machine_type': self.machine_type,
            'status': self.status,
            'current_job_id': str(self.current_job_id) if self.current_job_id else None,
            'maintenance_due': self.maintenance_due.isoformat() if self.maintenance_due else None,
            'total_print_hours': self.total_print_hours,
            'error_count': self.error_count,
            'last_calibration': self.last_calibration.isoformat() if self.last_calibration else None
        }

    def restore_state(self, state: Dict[str, Any]) -> None:
        self.name = state['name']
        self.machine_type = state['machine_type']
        self.status = state['status']
        self.current_job_id = UUID(state['current_job_id']) if state['current_job_id'] else None
        self.maintenance_due = (
            datetime.fromisoformat(state['maintenance_due'])
            if state['maintenance_due'] else None
        )
        self.total_print_hours = state['total_print_hours']
        self.error_count = state['error_count']
        self.last_calibration = (
            datetime.fromisoformat(state['last_calibration'])
            if state['last_calibration'] else None
        )


# =============================================================================
# Event Store
# =============================================================================

class EventStore:
    """
    Persistent event store for manufacturing events.

    Provides:
    - Event persistence with ordering guarantees
    - Optimistic concurrency control
    - Snapshot management
    - Temporal queries

    In production, this would use PostgreSQL or EventStoreDB.
    """

    def __init__(self):
        self._streams: Dict[UUID, EventStream] = {}
        self._snapshots: Dict[UUID, List[Snapshot]] = defaultdict(list)
        self._all_events: List[DomainEvent] = []  # Global event log
        self._subscribers: Dict[EventType, List[Callable[[DomainEvent], None]]] = defaultdict(list)
        self._snapshot_threshold = 100  # Snapshot every N events

    def append_events(
        self,
        aggregate_id: UUID,
        aggregate_type: str,
        events: List[DomainEvent],
        expected_version: int
    ) -> None:
        """
        Append events with optimistic concurrency control.

        Raises:
            ValueError: If version mismatch (concurrent modification)
        """
        if aggregate_id not in self._streams:
            self._streams[aggregate_id] = EventStream(
                aggregate_id=aggregate_id,
                aggregate_type=aggregate_type
            )

        stream = self._streams[aggregate_id]

        # Optimistic concurrency check
        if stream.version != expected_version:
            raise ValueError(
                f"Concurrency conflict: expected version {expected_version}, "
                f"but stream is at version {stream.version}"
            )

        # Append events
        for event in events:
            stream.append(event)
            self._all_events.append(event)

            # Notify subscribers
            for subscriber in self._subscribers[event.event_type]:
                try:
                    subscriber(event)
                except Exception as e:
                    logger.error(f"Subscriber error: {e}")

        # Auto-snapshot if threshold reached
        if stream.version % self._snapshot_threshold == 0:
            logger.info(f"Auto-snapshot triggered for {aggregate_id}")

    def get_events(
        self,
        aggregate_id: UUID,
        after_version: int = 0
    ) -> List[DomainEvent]:
        """Get events for an aggregate after a specific version."""
        if aggregate_id not in self._streams:
            return []
        return self._streams[aggregate_id].get_events_after(after_version)

    def get_stream(self, aggregate_id: UUID) -> Optional[EventStream]:
        """Get the complete event stream for an aggregate."""
        return self._streams.get(aggregate_id)

    def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save a snapshot for an aggregate."""
        self._snapshots[snapshot.aggregate_id].append(snapshot)

    def get_latest_snapshot(self, aggregate_id: UUID) -> Optional[Snapshot]:
        """Get the most recent snapshot for an aggregate."""
        snapshots = self._snapshots.get(aggregate_id, [])
        return snapshots[-1] if snapshots else None

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[DomainEvent], None]
    ) -> None:
        """Subscribe to events of a specific type."""
        self._subscribers[event_type].append(handler)

    def get_events_by_correlation(
        self,
        correlation_id: UUID
    ) -> List[DomainEvent]:
        """Get all events with the same correlation ID."""
        return [
            e for e in self._all_events
            if e.metadata.correlation_id == correlation_id
        ]

    def get_events_by_type(
        self,
        event_type: EventType,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[DomainEvent]:
        """Get all events of a type within an optional time range."""
        events = [e for e in self._all_events if e.event_type == event_type]

        if start:
            events = [e for e in events if e.metadata.timestamp >= start]
        if end:
            events = [e for e in events if e.metadata.timestamp <= end]

        return events

    def get_aggregate_ids_by_type(self, aggregate_type: str) -> Set[UUID]:
        """Get all aggregate IDs of a specific type."""
        return {
            stream.aggregate_id
            for stream in self._streams.values()
            if stream.aggregate_type == aggregate_type
        }

    def rebuild_aggregate(
        self,
        aggregate_class: type[T],
        aggregate_id: UUID
    ) -> Optional[T]:
        """Rebuild an aggregate from its event stream."""
        stream = self._streams.get(aggregate_id)
        if not stream:
            return None

        snapshot = self.get_latest_snapshot(aggregate_id)
        return aggregate_class.rebuild(aggregate_id, stream.events, snapshot)

    # Temporal Queries

    def get_state_at(
        self,
        aggregate_class: type[T],
        aggregate_id: UUID,
        point_in_time: datetime
    ) -> Optional[T]:
        """Rebuild aggregate state at a specific point in time."""
        stream = self._streams.get(aggregate_id)
        if not stream:
            return None

        # Get events up to point in time
        events = [
            e for e in stream.events
            if e.metadata.timestamp <= point_in_time
        ]

        if not events:
            return None

        return aggregate_class.rebuild(aggregate_id, events)

    def get_events_timeline(
        self,
        aggregate_ids: Optional[Set[UUID]] = None,
        event_types: Optional[Set[EventType]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[DomainEvent]:
        """
        Get events across multiple aggregates for timeline analysis.

        Useful for process mining and operational analytics.
        """
        events = self._all_events.copy()

        if aggregate_ids:
            events = [e for e in events if e.aggregate_id in aggregate_ids]

        if event_types:
            events = [e for e in events if e.event_type in event_types]

        if start:
            events = [e for e in events if e.metadata.timestamp >= start]

        if end:
            events = [e for e in events if e.metadata.timestamp <= end]

        return sorted(events, key=lambda e: e.metadata.timestamp)

    # Analytics

    def get_event_counts(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> Dict[EventType, int]:
        """Get counts of each event type in a time range."""
        events = self._all_events

        if start:
            events = [e for e in events if e.metadata.timestamp >= start]
        if end:
            events = [e for e in events if e.metadata.timestamp <= end]

        counts: Dict[EventType, int] = defaultdict(int)
        for event in events:
            counts[event.event_type] += 1

        return dict(counts)

    def get_aggregate_lifecycle(
        self,
        aggregate_id: UUID
    ) -> List[Tuple[datetime, str, EventType]]:
        """
        Get lifecycle transitions for process analysis.

        Returns list of (timestamp, status, event_type) tuples.
        """
        stream = self._streams.get(aggregate_id)
        if not stream:
            return []

        lifecycle = []
        for event in stream.events:
            lifecycle.append((
                event.metadata.timestamp,
                event.payload.get('status', 'unknown'),
                event.event_type
            ))

        return lifecycle

    def export_to_json(self) -> str:
        """Export all events to JSON for backup/analysis."""
        return json.dumps(
            [e.to_dict() for e in self._all_events],
            indent=2,
            default=str
        )

    def import_from_json(self, json_data: str) -> int:
        """Import events from JSON backup."""
        events_data = json.loads(json_data)
        count = 0

        for event_dict in events_data:
            event = DomainEvent.from_dict(event_dict)
            aggregate_id = event.aggregate_id

            if aggregate_id not in self._streams:
                self._streams[aggregate_id] = EventStream(
                    aggregate_id=aggregate_id,
                    aggregate_type=event.aggregate_type
                )

            self._streams[aggregate_id].events.append(event)
            self._all_events.append(event)
            count += 1

        return count


# =============================================================================
# Projections (Read Models)
# =============================================================================

class Projection(ABC):
    """
    Abstract base for event projections.

    Projections build read-optimized views from events.
    """

    @abstractmethod
    def handle(self, event: DomainEvent) -> None:
        """Handle an event to update the projection."""
        pass

    @abstractmethod
    def rebuild(self, events: List[DomainEvent]) -> None:
        """Rebuild projection from scratch."""
        pass


class ActiveJobsProjection(Projection):
    """Projection of currently active print jobs."""

    def __init__(self):
        self.active_jobs: Dict[UUID, Dict[str, Any]] = {}

    def handle(self, event: DomainEvent) -> None:
        if event.aggregate_type != 'PrintJob':
            return

        job_id = event.aggregate_id

        if event.event_type == EventType.PRINT_JOB_STARTED:
            self.active_jobs[job_id] = {
                'job_id': str(job_id),
                'machine_id': event.payload['machine_id'],
                'started_at': event.metadata.timestamp.isoformat(),
                'current_layer': 0,
                'defects': 0
            }

        elif event.event_type == EventType.LAYER_COMPLETED:
            if job_id in self.active_jobs:
                self.active_jobs[job_id]['current_layer'] = event.payload['layer_number']

        elif event.event_type == EventType.LAYER_DEFECT_DETECTED:
            if job_id in self.active_jobs:
                self.active_jobs[job_id]['defects'] += 1

        elif event.event_type in (
            EventType.PRINT_JOB_COMPLETED,
            EventType.PRINT_JOB_FAILED,
            EventType.PRINT_JOB_CANCELLED
        ):
            self.active_jobs.pop(job_id, None)

    def rebuild(self, events: List[DomainEvent]) -> None:
        self.active_jobs.clear()
        for event in events:
            self.handle(event)

    def get_active_jobs(self) -> List[Dict[str, Any]]:
        return list(self.active_jobs.values())


class MachineUtilizationProjection(Projection):
    """Projection for machine utilization analytics."""

    def __init__(self):
        self.machine_stats: Dict[UUID, Dict[str, Any]] = defaultdict(
            lambda: {
                'total_jobs': 0,
                'completed_jobs': 0,
                'failed_jobs': 0,
                'total_runtime_seconds': 0,
                'total_defects': 0
            }
        )
        self._job_starts: Dict[UUID, datetime] = {}

    def handle(self, event: DomainEvent) -> None:
        if event.aggregate_type == 'PrintJob':
            job_id = event.aggregate_id

            if event.event_type == EventType.PRINT_JOB_STARTED:
                machine_id = event.payload.get('machine_id')
                if machine_id:
                    self.machine_stats[machine_id]['total_jobs'] += 1
                    self._job_starts[job_id] = event.metadata.timestamp

            elif event.event_type == EventType.PRINT_JOB_COMPLETED:
                if job_id in self._job_starts:
                    # This is simplified; in reality we'd track machine_id
                    pass

            elif event.event_type == EventType.LAYER_DEFECT_DETECTED:
                pass  # Track defects per machine

    def rebuild(self, events: List[DomainEvent]) -> None:
        self.machine_stats.clear()
        self._job_starts.clear()
        for event in events:
            self.handle(event)


class DefectAnalyticsProjection(Projection):
    """Projection for defect analysis and quality metrics."""

    def __init__(self):
        self.defects_by_type: Dict[str, int] = defaultdict(int)
        self.defects_by_layer: Dict[int, int] = defaultdict(int)
        self.defects_by_severity: Dict[str, int] = defaultdict(int)
        self.total_inspections: int = 0
        self.passed_inspections: int = 0

    def handle(self, event: DomainEvent) -> None:
        if event.event_type == EventType.LAYER_DEFECT_DETECTED:
            defect_type = event.payload.get('defect_type', 'unknown')
            layer = event.payload.get('layer_number', 0)
            severity = event.payload.get('severity', 'medium')

            self.defects_by_type[defect_type] += 1
            self.defects_by_layer[layer] += 1
            self.defects_by_severity[severity] += 1

        elif event.event_type == EventType.INSPECTION_COMPLETED:
            self.total_inspections += 1

        elif event.event_type == EventType.QUALITY_APPROVED:
            self.passed_inspections += 1

    def rebuild(self, events: List[DomainEvent]) -> None:
        self.defects_by_type.clear()
        self.defects_by_layer.clear()
        self.defects_by_severity.clear()
        self.total_inspections = 0
        self.passed_inspections = 0
        for event in events:
            self.handle(event)

    def get_quality_rate(self) -> float:
        if self.total_inspections == 0:
            return 1.0
        return self.passed_inspections / self.total_inspections

    def get_pareto_defects(self) -> List[Tuple[str, int]]:
        """Get defects sorted by frequency (Pareto analysis)."""
        return sorted(
            self.defects_by_type.items(),
            key=lambda x: x[1],
            reverse=True
        )


# =============================================================================
# Event Sourcing Manager
# =============================================================================

class EventSourcingManager:
    """
    High-level manager for event sourcing operations.

    Coordinates event store, projections, and aggregates.
    """

    def __init__(self, event_store: Optional[EventStore] = None):
        self.event_store = event_store or EventStore()
        self.projections: Dict[str, Projection] = {}

        # Register built-in projections
        self._register_projection('active_jobs', ActiveJobsProjection())
        self._register_projection('machine_utilization', MachineUtilizationProjection())
        self._register_projection('defect_analytics', DefectAnalyticsProjection())

    def _register_projection(self, name: str, projection: Projection) -> None:
        """Register a projection and subscribe to events."""
        self.projections[name] = projection

        # Subscribe to all event types
        for event_type in EventType:
            self.event_store.subscribe(event_type, projection.handle)

    def save(self, aggregate: Aggregate) -> None:
        """Save aggregate changes to the event store."""
        events = aggregate.clear_pending_events()
        if not events:
            return

        expected_version = aggregate.version - len(events)

        self.event_store.append_events(
            aggregate_id=aggregate.id,
            aggregate_type=aggregate._get_aggregate_type(),
            events=events,
            expected_version=expected_version
        )

    def load(
        self,
        aggregate_class: type[T],
        aggregate_id: UUID
    ) -> Optional[T]:
        """Load an aggregate from the event store."""
        return self.event_store.rebuild_aggregate(aggregate_class, aggregate_id)

    def get_projection(self, name: str) -> Optional[Projection]:
        """Get a registered projection by name."""
        return self.projections.get(name)

    def rebuild_projections(self) -> None:
        """Rebuild all projections from the event store."""
        events = self.event_store._all_events.copy()
        events.sort(key=lambda e: e.metadata.timestamp)

        for projection in self.projections.values():
            projection.rebuild(events)

    def create_snapshot(self, aggregate: Aggregate) -> Snapshot:
        """Create and save a snapshot of an aggregate."""
        snapshot = Snapshot(
            snapshot_id=uuid4(),
            aggregate_id=aggregate.id,
            aggregate_type=aggregate._get_aggregate_type(),
            version=aggregate.version,
            state=aggregate.get_state(),
            created_at=datetime.utcnow()
        )

        self.event_store.save_snapshot(snapshot)
        return snapshot


# Export public API
__all__ = [
    # Events
    'EventType',
    'EventMetadata',
    'DomainEvent',
    'EventStream',
    'Snapshot',
    # Aggregates
    'Aggregate',
    'PrintJobAggregate',
    'MachineAggregate',
    # Store
    'EventStore',
    # Projections
    'Projection',
    'ActiveJobsProjection',
    'MachineUtilizationProjection',
    'DefectAnalyticsProjection',
    # Manager
    'EventSourcingManager',
]
