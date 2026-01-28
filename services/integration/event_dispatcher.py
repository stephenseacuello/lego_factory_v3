"""
Event Dispatcher for Flask CNC SCADA
====================================
Pub/sub event system for decoupled service communication.

Features:
- Event types for all workflow stages
- Synchronous and asynchronous event delivery
- Event filtering and routing
- MQTT integration for external subscribers
- Event history for debugging

Usage:
    from services.integration.event_dispatcher import get_event_dispatcher, EventType

    dispatcher = get_event_dispatcher()

    # Subscribe to events
    dispatcher.subscribe(EventType.JOB_STARTED, my_callback)

    # Publish events
    dispatcher.publish(EventType.JOB_STARTED, {"job_id": "123", "machine_id": "tinyg-1"})
"""

import logging
import time
import uuid
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
from queue import Queue, Empty
import json

from config import get_config

logger = logging.getLogger(__name__)
config = get_config()


class EventType(Enum):
    """Event types for the CNC workflow system."""

    # Work Order Events
    WORK_ORDER_CREATED = "work_order.created"
    WORK_ORDER_UPDATED = "work_order.updated"
    WORK_ORDER_RELEASED = "work_order.released"
    WORK_ORDER_STARTED = "work_order.started"
    WORK_ORDER_COMPLETED = "work_order.completed"
    WORK_ORDER_ON_HOLD = "work_order.on_hold"
    WORK_ORDER_CANCELLED = "work_order.cancelled"

    # Operation Events
    OPERATION_STARTED = "operation.started"
    OPERATION_COMPLETED = "operation.completed"
    OPERATION_PAUSED = "operation.paused"
    OPERATION_RESUMED = "operation.resumed"

    # Job Events
    JOB_CREATED = "job.created"
    JOB_QUEUED = "job.queued"
    JOB_SCHEDULED = "job.scheduled"
    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_PAUSED = "job.paused"
    JOB_RESUMED = "job.resumed"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"

    # Scheduling Events
    SCHEDULE_CREATED = "schedule.created"
    SCHEDULE_UPDATED = "schedule.updated"
    SCHEDULE_ACTIVATED = "schedule.activated"

    # Execution Events
    GCODE_LINE_EXECUTED = "execution.gcode_line"
    MACHINE_STATE_CHANGED = "execution.machine_state"
    TOOL_CHANGED = "execution.tool_changed"
    FEED_OVERRIDE_CHANGED = "execution.feed_override"

    # Labor Events
    LABOR_CLOCK_IN = "labor.clock_in"
    LABOR_CLOCK_OUT = "labor.clock_out"

    # Traceability Events
    TRACE_RECORD_CREATED = "traceability.record_created"
    SENSOR_SNAPSHOT_CAPTURED = "traceability.sensor_snapshot"
    QUALITY_CHECK_COMPLETED = "traceability.quality_check"

    # Quality Events
    QUALITY_INSPECTION = "quality.inspection"
    QUALITY_PASSED = "quality.passed"
    QUALITY_FAILED = "quality.failed"

    # Machine Events
    MACHINE_CONNECTED = "machine.connected"
    MACHINE_DISCONNECTED = "machine.disconnected"
    MACHINE_ERROR = "machine.error"
    MACHINE_ALARM = "machine.alarm"

    # System Events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"

    # Feedback Events
    TIME_ACCURACY_RECORDED = "feedback.time_accuracy"


@dataclass
class Event:
    """Event data structure."""
    id: str
    type: EventType
    timestamp: float
    data: Dict[str, Any]
    source: str = "system"
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "data": self.data,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def create(
        cls,
        event_type: EventType,
        data: Dict[str, Any],
        source: str = "system",
        correlation_id: Optional[str] = None,
    ) -> "Event":
        """Factory method to create a new event."""
        return cls(
            id=str(uuid.uuid4()),
            type=event_type,
            timestamp=time.time(),
            data=data,
            source=source,
            correlation_id=correlation_id,
        )


# Type alias for event callbacks
EventCallback = Callable[[Event], None]


class EventDispatcher:
    """
    Central event dispatcher for the CNC system.

    Handles event publishing, subscription, and routing to MQTT.
    """

    def __init__(self, enable_mqtt: bool = True, history_size: int = 1000):
        """
        Initialize event dispatcher.

        Args:
            enable_mqtt: Whether to publish events to MQTT
            history_size: Number of events to keep in history
        """
        self._subscribers: Dict[EventType, List[EventCallback]] = defaultdict(list)
        self._wildcard_subscribers: List[EventCallback] = []
        self._lock = threading.RLock()

        # Event history for debugging
        self._history: List[Event] = []
        self._history_size = history_size

        # Async event queue
        self._event_queue: Queue = Queue()
        self._async_enabled = False
        self._async_thread: Optional[threading.Thread] = None

        # MQTT integration
        self._enable_mqtt = enable_mqtt
        self._mqtt_service = None

        logger.info("EventDispatcher initialized")

    def start_async_processing(self):
        """Start async event processing thread."""
        if not self._async_enabled:
            self._async_enabled = True
            self._async_thread = threading.Thread(
                target=self._async_event_loop,
                daemon=True,
                name="EventDispatcher-Async"
            )
            self._async_thread.start()
            logger.info("Async event processing started")

    def stop_async_processing(self):
        """Stop async event processing."""
        self._async_enabled = False
        if self._async_thread:
            self._async_thread.join(timeout=2.0)
            self._async_thread = None
            logger.info("Async event processing stopped")

    def _async_event_loop(self):
        """Process events asynchronously."""
        while self._async_enabled:
            try:
                event = self._event_queue.get(timeout=0.1)
                self._dispatch_event(event)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error in async event processing: {e}")

    def subscribe(
        self,
        event_type: EventType,
        callback: EventCallback,
    ) -> None:
        """
        Subscribe to a specific event type.

        Args:
            event_type: The event type to subscribe to
            callback: Function to call when event occurs
        """
        with self._lock:
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
                logger.debug(f"Subscribed to {event_type.value}")

    def subscribe_all(self, callback: EventCallback) -> None:
        """
        Subscribe to all events.

        Args:
            callback: Function to call for any event
        """
        with self._lock:
            if callback not in self._wildcard_subscribers:
                self._wildcard_subscribers.append(callback)
                logger.debug("Subscribed to all events")

    def unsubscribe(
        self,
        event_type: EventType,
        callback: EventCallback,
    ) -> bool:
        """
        Unsubscribe from an event type.

        Args:
            event_type: The event type to unsubscribe from
            callback: The callback to remove

        Returns:
            True if callback was removed
        """
        with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                return True
            return False

    def publish(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        source: str = "system",
        correlation_id: Optional[str] = None,
        async_delivery: bool = False,
    ) -> Event:
        """
        Publish an event.

        Args:
            event_type: Type of event
            data: Event data
            source: Source of the event
            correlation_id: Optional correlation ID for tracing
            async_delivery: If True, deliver asynchronously

        Returns:
            The created Event
        """
        event = Event.create(event_type, data, source, correlation_id)

        # Add to history
        self._add_to_history(event)

        if async_delivery and self._async_enabled:
            self._event_queue.put(event)
        else:
            self._dispatch_event(event)

        return event

    def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to all subscribers."""
        with self._lock:
            # Get callbacks for this event type
            callbacks = list(self._subscribers.get(event.type, []))
            wildcard_callbacks = list(self._wildcard_subscribers)

        # Call type-specific subscribers
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback for {event.type.value}: {e}")

        # Call wildcard subscribers
        for callback in wildcard_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in wildcard event callback: {e}")

        # Publish to MQTT if enabled
        if self._enable_mqtt:
            self._publish_to_mqtt(event)

    def _publish_to_mqtt(self, event: Event) -> None:
        """Publish event to MQTT broker."""
        try:
            # Lazy import to avoid circular dependency
            if self._mqtt_service is None:
                from services.mqtt_service import get_mqtt_service
                self._mqtt_service = get_mqtt_service()

            if self._mqtt_service and self._mqtt_service.connected:
                # Convert event type to MQTT topic
                # e.g., "job.started" -> "cnc/events/job/started"
                topic_parts = event.type.value.split(".")
                topic = f"cnc/events/{'/'.join(topic_parts)}"

                self._mqtt_service.publish(topic, event.to_dict())
        except Exception as e:
            logger.error(f"Error publishing event to MQTT: {e}")

    def _add_to_history(self, event: Event) -> None:
        """Add event to history, maintaining max size."""
        with self._lock:
            self._history.append(event)
            while len(self._history) > self._history_size:
                self._history.pop(0)

    def get_history(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 100,
        since_timestamp: Optional[float] = None,
    ) -> List[Event]:
        """
        Get event history.

        Args:
            event_type: Filter by event type
            limit: Maximum number of events
            since_timestamp: Only events after this timestamp

        Returns:
            List of events
        """
        with self._lock:
            events = list(self._history)

        # Filter by type
        if event_type:
            events = [e for e in events if e.type == event_type]

        # Filter by timestamp
        if since_timestamp:
            events = [e for e in events if e.timestamp > since_timestamp]

        # Apply limit and reverse (newest first)
        return list(reversed(events[-limit:]))

    def get_subscribers_count(self, event_type: Optional[EventType] = None) -> int:
        """Get count of subscribers."""
        with self._lock:
            if event_type:
                return len(self._subscribers.get(event_type, []))
            return sum(len(subs) for subs in self._subscribers.values())

    def clear_history(self) -> None:
        """Clear event history."""
        with self._lock:
            self._history.clear()


# Global dispatcher instance
_event_dispatcher: Optional[EventDispatcher] = None


def get_event_dispatcher() -> EventDispatcher:
    """Get global event dispatcher instance."""
    global _event_dispatcher
    if _event_dispatcher is None:
        _event_dispatcher = EventDispatcher()
    return _event_dispatcher


def initialize_event_dispatcher(
    enable_mqtt: bool = True,
    async_processing: bool = True,
) -> EventDispatcher:
    """Initialize and configure global event dispatcher."""
    global _event_dispatcher
    _event_dispatcher = EventDispatcher(enable_mqtt=enable_mqtt)
    if async_processing:
        _event_dispatcher.start_async_processing()
    return _event_dispatcher
