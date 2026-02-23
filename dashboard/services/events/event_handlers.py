"""
Event Handlers - Domain Event Processing

LegoMCP World-Class Manufacturing System v5.0
Phase 7: Event-Driven Architecture

Provides a registry and decorator-based system for handling
manufacturing events with support for:
- Async and sync handlers
- Priority-based processing
- Error handling and retries
- Handler chaining and composition
"""

import asyncio
import functools
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

from .event_types import (
    ManufacturingEvent,
    EventCategory,
    EventPriority,
    MachineEvent,
    QualityEvent,
    SchedulingEvent,
    InventoryEvent,
    MaintenanceEvent,
)

logger = logging.getLogger(__name__)


@dataclass
class HandlerConfig:
    """Configuration for an event handler."""
    event_types: Set[str] = field(default_factory=set)
    categories: Set[EventCategory] = field(default_factory=set)
    priority: EventPriority = EventPriority.NORMAL
    max_retries: int = 3
    timeout_seconds: float = 30.0
    async_handler: bool = True


class EventHandler:
    """
    Base class for event handlers.

    Provides structure for handling events with proper
    error handling, logging, and lifecycle management.
    """

    def __init__(self):
        self.name = self.__class__.__name__
        self._handlers: Dict[str, Callable] = {}
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register handler methods based on naming convention."""
        for attr_name in dir(self):
            if attr_name.startswith('handle_'):
                event_type = attr_name[7:]  # Remove 'handle_' prefix
                self._handlers[event_type] = getattr(self, attr_name)

    async def handle(self, event: ManufacturingEvent) -> Optional[Any]:
        """
        Handle an event by dispatching to the appropriate method.

        Returns the result of the handler, if any.
        """
        # Try specific event type handler
        event_type_key = event.event_type.replace('.', '_')
        if event_type_key in self._handlers:
            handler = self._handlers[event_type_key]
            return await self._invoke_handler(handler, event)

        # Try category handler
        category_key = event.category.value
        if category_key in self._handlers:
            handler = self._handlers[category_key]
            return await self._invoke_handler(handler, event)

        # Try default handler
        if 'default' in self._handlers:
            handler = self._handlers['default']
            return await self._invoke_handler(handler, event)

        logger.debug(f"No handler found for event {event.event_type}")
        return None

    async def _invoke_handler(
        self,
        handler: Callable,
        event: ManufacturingEvent
    ) -> Optional[Any]:
        """Invoke a handler with proper async handling."""
        try:
            if asyncio.iscoroutinefunction(handler):
                return await handler(event)
            else:
                return handler(event)
        except Exception as e:
            logger.error(f"Handler {handler.__name__} failed for {event.event_id}: {e}")
            raise


class EventHandlerRegistry:
    """
    Central registry for event handlers.

    Manages handler registration, dispatch, and lifecycle.
    Supports:
    - Multiple handlers per event type
    - Priority-based ordering
    - Automatic handler discovery
    """

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._category_handlers: Dict[EventCategory, List[Callable]] = {}
        self._global_handlers: List[Callable] = []

    def register(
        self,
        handler: Callable,
        event_types: Optional[List[str]] = None,
        categories: Optional[List[EventCategory]] = None,
        global_handler: bool = False
    ) -> None:
        """
        Register a handler for specific event types or categories.

        Args:
            handler: Callable that takes a ManufacturingEvent
            event_types: List of specific event types to handle
            categories: List of event categories to handle
            global_handler: If True, handler receives all events
        """
        if global_handler:
            self._global_handlers.append(handler)
            return

        if event_types:
            for event_type in event_types:
                if event_type not in self._handlers:
                    self._handlers[event_type] = []
                self._handlers[event_type].append(handler)

        if categories:
            for category in categories:
                if category not in self._category_handlers:
                    self._category_handlers[category] = []
                self._category_handlers[category].append(handler)

    def unregister(self, handler: Callable) -> None:
        """Remove a handler from the registry."""
        # Remove from event type handlers
        for event_type in list(self._handlers.keys()):
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
                if not self._handlers[event_type]:
                    del self._handlers[event_type]

        # Remove from category handlers
        for category in list(self._category_handlers.keys()):
            if handler in self._category_handlers[category]:
                self._category_handlers[category].remove(handler)
                if not self._category_handlers[category]:
                    del self._category_handlers[category]

        # Remove from global handlers
        if handler in self._global_handlers:
            self._global_handlers.remove(handler)

    def get_handlers(self, event: ManufacturingEvent) -> List[Callable]:
        """Get all handlers for an event."""
        handlers = []

        # Add global handlers first
        handlers.extend(self._global_handlers)

        # Add category handlers
        if event.category in self._category_handlers:
            handlers.extend(self._category_handlers[event.category])

        # Add specific event type handlers
        if event.event_type in self._handlers:
            handlers.extend(self._handlers[event.event_type])

        return handlers

    async def dispatch(self, event: ManufacturingEvent) -> List[Any]:
        """
        Dispatch an event to all registered handlers.

        Returns a list of results from each handler.
        """
        handlers = self.get_handlers(event)
        results = []

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(event)
                else:
                    result = handler(event)
                results.append(result)
            except Exception as e:
                logger.error(f"Handler failed for event {event.event_id}: {e}")
                results.append(None)

        return results

    async def dispatch_with_timeout(
        self,
        event: ManufacturingEvent,
        timeout: float = 30.0
    ) -> List[Any]:
        """Dispatch with a timeout for all handlers."""
        try:
            return await asyncio.wait_for(
                self.dispatch(event),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Handler timeout for event {event.event_id}")
            return []


# Global registry instance
_registry = EventHandlerRegistry()


def handler(
    event_types: Optional[List[str]] = None,
    categories: Optional[List[EventCategory]] = None,
    global_handler: bool = False
):
    """
    Decorator to register a function as an event handler.

    Usage:
        @handler(event_types=['machine.state_change'])
        async def on_state_change(event: MachineEvent):
            print(f"State changed: {event.payload}")

        @handler(categories=[EventCategory.QUALITY])
        async def on_quality_event(event: QualityEvent):
            print(f"Quality event: {event.event_type}")
    """
    def decorator(func: Callable) -> Callable:
        _registry.register(
            func,
            event_types=event_types,
            categories=categories,
            global_handler=global_handler
        )

        @functools.wraps(func)
        async def wrapper(event: ManufacturingEvent) -> Any:
            if asyncio.iscoroutinefunction(func):
                return await func(event)
            return func(event)

        return wrapper

    return decorator


def get_registry() -> EventHandlerRegistry:
    """Get the global handler registry."""
    return _registry


# ============================================================================
# Built-in Event Handlers
# ============================================================================

class LoggingHandler(EventHandler):
    """Handler that logs all events for debugging."""

    async def handle_default(self, event: ManufacturingEvent) -> None:
        """Log all events."""
        logger.info(
            f"Event: {event.event_type} | "
            f"Category: {event.category.value} | "
            f"Priority: {event.priority.value} | "
            f"ID: {event.event_id}"
        )


class MetricsHandler(EventHandler):
    """Handler that collects event metrics."""

    def __init__(self):
        super().__init__()
        self.event_counts: Dict[str, int] = {}
        self.category_counts: Dict[EventCategory, int] = {}
        self.last_event_time: Dict[str, datetime] = {}

    async def handle_default(self, event: ManufacturingEvent) -> None:
        """Collect metrics for all events."""
        # Count by event type
        if event.event_type not in self.event_counts:
            self.event_counts[event.event_type] = 0
        self.event_counts[event.event_type] += 1

        # Count by category
        if event.category not in self.category_counts:
            self.category_counts[event.category] = 0
        self.category_counts[event.category] += 1

        # Track last event time
        self.last_event_time[event.event_type] = event.timestamp

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return {
            'event_counts': self.event_counts.copy(),
            'category_counts': {k.value: v for k, v in self.category_counts.items()},
            'last_event_times': {k: v.isoformat() for k, v in self.last_event_time.items()},
            'total_events': sum(self.event_counts.values())
        }


class AlertHandler(EventHandler):
    """Handler that generates alerts for critical events."""

    def __init__(self):
        super().__init__()
        self.alerts: List[Dict[str, Any]] = []
        self.max_alerts = 1000

    async def handle_default(self, event: ManufacturingEvent) -> None:
        """Check for alert conditions."""
        if event.priority in [EventPriority.CRITICAL, EventPriority.HIGH]:
            alert = {
                'event_id': event.event_id,
                'event_type': event.event_type,
                'priority': event.priority.value,
                'timestamp': event.timestamp.isoformat(),
                'work_center_id': event.work_center_id,
                'payload': event.payload
            }
            self.alerts.append(alert)

            # Trim old alerts
            if len(self.alerts) > self.max_alerts:
                self.alerts = self.alerts[-self.max_alerts:]

            logger.warning(f"ALERT: {event.event_type} - {event.payload}")

    def get_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        return self.alerts[-limit:]

    def clear_alerts(self) -> None:
        """Clear all alerts."""
        self.alerts.clear()
