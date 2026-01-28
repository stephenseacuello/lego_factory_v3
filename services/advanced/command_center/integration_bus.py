"""
Integration Message Bus

Event-driven message bus for inter-service communication.
Implements publish-subscribe pattern with topic routing.

Reference: Enterprise Integration Patterns, ISA-95
"""

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import threading
import json
import queue

logger = logging.getLogger(__name__)


class EventType(Enum):
    """System event types."""
    # Lifecycle events
    SERVICE_STARTED = "service.started"
    SERVICE_STOPPED = "service.stopped"
    SERVICE_HEALTH_CHANGED = "service.health_changed"

    # Production events
    JOB_CREATED = "production.job_created"
    JOB_STARTED = "production.job_started"
    JOB_COMPLETED = "production.job_completed"
    JOB_FAILED = "production.job_failed"

    # Quality events
    QUALITY_CHECK_PASSED = "quality.check_passed"
    QUALITY_CHECK_FAILED = "quality.check_failed"
    DEFECT_DETECTED = "quality.defect_detected"

    # Equipment events
    MACHINE_STARTED = "equipment.machine_started"
    MACHINE_STOPPED = "equipment.machine_stopped"
    MACHINE_FAULT = "equipment.machine_fault"
    MAINTENANCE_DUE = "equipment.maintenance_due"

    # Inventory events
    MATERIAL_LOW = "inventory.material_low"
    MATERIAL_RESERVED = "inventory.material_reserved"
    MATERIAL_CONSUMED = "inventory.material_consumed"

    # Safety events
    SAFETY_ALERT = "safety.alert"
    EMERGENCY_STOP = "safety.emergency_stop"
    SAFETY_ZONE_BREACH = "safety.zone_breach"

    # Compliance events
    AUDIT_STARTED = "compliance.audit_started"
    AUDIT_COMPLETED = "compliance.audit_completed"
    VIOLATION_DETECTED = "compliance.violation_detected"

    # Custom events
    CUSTOM = "custom"


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class SystemEvent:
    """System event message."""
    event_id: str
    event_type: EventType
    source: str
    timestamp: datetime
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemEvent':
        """Create from dictionary."""
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            source=data["source"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            payload=data.get("payload", {}),
            priority=EventPriority(data.get("priority", 1)),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Subscription:
    """Event subscription."""
    subscription_id: str
    event_types: Set[EventType]
    handler: Callable[[SystemEvent], None]
    filter_func: Optional[Callable[[SystemEvent], bool]] = None
    async_handler: bool = False


class MessageBus:
    """
    Central Message Bus for event-driven communication.

    Supports:
    - Publish/subscribe pattern
    - Topic-based routing
    - Event filtering
    - Async and sync handlers
    - Event replay
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._subscriptions: Dict[str, Subscription] = {}
        self._handlers_by_type: Dict[EventType, List[str]] = defaultdict(list)
        self._event_history: List[SystemEvent] = []
        self._max_history = 1000
        self._event_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self) -> None:
        """Start message bus worker."""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._process_events, daemon=True)
        self._worker_thread.start()
        logger.info("Message bus started")

    def stop(self) -> None:
        """Stop message bus worker."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("Message bus stopped")

    def subscribe(
        self,
        event_types: List[EventType],
        handler: Callable[[SystemEvent], None],
        filter_func: Optional[Callable[[SystemEvent], bool]] = None,
        async_handler: bool = False
    ) -> str:
        """
        Subscribe to events.

        Args:
            event_types: List of event types to subscribe to
            handler: Callback function for events
            filter_func: Optional filter function
            async_handler: Whether handler is async

        Returns:
            Subscription ID
        """
        sub_id = str(uuid.uuid4())

        subscription = Subscription(
            subscription_id=sub_id,
            event_types=set(event_types),
            handler=handler,
            filter_func=filter_func,
            async_handler=async_handler
        )

        self._subscriptions[sub_id] = subscription

        for event_type in event_types:
            self._handlers_by_type[event_type].append(sub_id)

        logger.debug(f"New subscription: {sub_id} for {[e.value for e in event_types]}")
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        if subscription_id not in self._subscriptions:
            return False

        subscription = self._subscriptions[subscription_id]

        for event_type in subscription.event_types:
            if subscription_id in self._handlers_by_type[event_type]:
                self._handlers_by_type[event_type].remove(subscription_id)

        del self._subscriptions[subscription_id]
        return True

    def publish(
        self,
        event_type: EventType,
        source: str,
        payload: Optional[Dict[str, Any]] = None,
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Publish an event.

        Args:
            event_type: Type of event
            source: Source service/component
            payload: Event data
            priority: Event priority
            correlation_id: Optional correlation ID for tracing

        Returns:
            Event ID
        """
        event = SystemEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source=source,
            timestamp=datetime.now(),
            payload=payload or {},
            priority=priority,
            correlation_id=correlation_id
        )

        # Add to queue with priority (lower number = higher priority)
        queue_priority = 3 - priority.value  # Invert for queue
        self._event_queue.put((queue_priority, event))

        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        logger.debug(f"Published event: {event_type.value} from {source}")
        return event.event_id

    def publish_sync(
        self,
        event_type: EventType,
        source: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        """Publish event and process synchronously."""
        event = SystemEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source=source,
            timestamp=datetime.now(),
            payload=payload or {},
            priority=EventPriority.NORMAL
        )

        self._dispatch_event(event)

    def _process_events(self) -> None:
        """Worker thread to process events."""
        while self._running:
            try:
                # Get event with timeout
                priority, event = self._event_queue.get(timeout=0.1)
                self._dispatch_event(event)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")

    def _dispatch_event(self, event: SystemEvent) -> None:
        """Dispatch event to subscribers."""
        subscriber_ids = self._handlers_by_type.get(event.event_type, [])

        for sub_id in subscriber_ids:
            subscription = self._subscriptions.get(sub_id)
            if not subscription:
                continue

            # Apply filter
            if subscription.filter_func:
                try:
                    if not subscription.filter_func(event):
                        continue
                except Exception as e:
                    logger.error(f"Filter error for {sub_id}: {e}")
                    continue

            # Call handler
            try:
                if subscription.async_handler:
                    # Run in async context
                    if self._async_loop and self._async_loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            subscription.handler(event),
                            self._async_loop
                        )
                    else:
                        asyncio.run(subscription.handler(event))
                else:
                    subscription.handler(event)
            except Exception as e:
                logger.error(f"Handler error for {sub_id}: {e}")

    def get_history(
        self,
        event_type: Optional[EventType] = None,
        source: Optional[str] = None,
        limit: int = 100
    ) -> List[SystemEvent]:
        """Get event history with optional filtering."""
        events = self._event_history

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if source:
            events = [e for e in events if e.source == source]

        return events[-limit:]

    def replay_events(
        self,
        subscription_id: str,
        since: Optional[datetime] = None,
        event_types: Optional[List[EventType]] = None
    ) -> int:
        """
        Replay historical events to a subscription.

        Returns number of events replayed.
        """
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return 0

        count = 0
        for event in self._event_history:
            # Filter by time
            if since and event.timestamp < since:
                continue

            # Filter by type
            if event_types and event.event_type not in event_types:
                continue

            # Must match subscription types
            if event.event_type not in subscription.event_types:
                continue

            # Call handler
            try:
                subscription.handler(event)
                count += 1
            except Exception as e:
                logger.error(f"Replay error: {e}")

        return count

    def get_statistics(self) -> Dict[str, Any]:
        """Get message bus statistics."""
        events_by_type = defaultdict(int)
        for event in self._event_history:
            events_by_type[event.event_type.value] += 1

        return {
            "total_events": len(self._event_history),
            "subscriptions": len(self._subscriptions),
            "queue_size": self._event_queue.qsize(),
            "events_by_type": dict(events_by_type),
            "running": self._running,
        }


def get_message_bus() -> MessageBus:
    """Get global message bus instance."""
    return MessageBus()


# Convenience decorators

def on_event(*event_types: EventType):
    """Decorator to subscribe a function to events."""
    def decorator(func: Callable[[SystemEvent], None]):
        bus = get_message_bus()
        bus.subscribe(list(event_types), func)
        return func
    return decorator


# Event builders for common scenarios

def emit_job_created(source: str, job_id: str, product_id: str, quantity: int) -> str:
    """Emit job created event."""
    return get_message_bus().publish(
        EventType.JOB_CREATED,
        source,
        {"job_id": job_id, "product_id": product_id, "quantity": quantity}
    )


def emit_quality_result(source: str, job_id: str, passed: bool, score: float) -> str:
    """Emit quality check result."""
    event_type = EventType.QUALITY_CHECK_PASSED if passed else EventType.QUALITY_CHECK_FAILED
    return get_message_bus().publish(
        event_type,
        source,
        {"job_id": job_id, "passed": passed, "score": score}
    )


def emit_safety_alert(source: str, alert_type: str, severity: str, message: str) -> str:
    """Emit safety alert."""
    priority = EventPriority.CRITICAL if severity == "critical" else EventPriority.HIGH
    return get_message_bus().publish(
        EventType.SAFETY_ALERT,
        source,
        {"alert_type": alert_type, "severity": severity, "message": message},
        priority=priority
    )


def emit_machine_fault(source: str, machine_id: str, fault_code: str, description: str) -> str:
    """Emit machine fault event."""
    return get_message_bus().publish(
        EventType.MACHINE_FAULT,
        source,
        {"machine_id": machine_id, "fault_code": fault_code, "description": description},
        priority=EventPriority.HIGH
    )
