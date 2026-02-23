"""
Event-Driven Architecture - Real-Time Event Streaming

LegoMCP World-Class Manufacturing System v5.0
Phase 7: Event-Driven Architecture

This module provides a real-time event streaming system using Redis Streams
for sub-10ms latency event processing across the manufacturing platform.

Features:
- CQRS/Event Sourcing pattern support
- Redis Streams for reliable event delivery
- Consumer groups for parallel processing
- Dead letter queue for failed events
- Event correlation and tracing
- Typed event definitions with validation

Event Categories:
- MACHINE: State changes, alarms, sensor data
- QUALITY: SPC signals, inspections, defects
- SCHEDULING: Deviations, reschedule triggers
- INVENTORY: Stock movements, transactions
- MAINTENANCE: Predictive alerts, work orders
"""

from .event_types import (
    EventCategory,
    EventPriority,
    ManufacturingEvent,
    MachineEvent,
    QualityEvent,
    SchedulingEvent,
    InventoryEvent,
    MaintenanceEvent,
    EventMetadata,
)

from .event_bus import (
    EventBus,
    EventPublisher,
    EventSubscriber,
    get_event_bus,
)

from .event_handlers import (
    EventHandler,
    EventHandlerRegistry,
    handler,
)

from .stream_consumer import (
    StreamConsumer,
    ConsumerGroup,
    ConsumerConfig,
)

from .dead_letter_queue import (
    DeadLetterQueue,
    FailedEvent,
    RetryPolicy,
)

__all__ = [
    # Event Types
    'EventCategory',
    'EventPriority',
    'ManufacturingEvent',
    'MachineEvent',
    'QualityEvent',
    'SchedulingEvent',
    'InventoryEvent',
    'MaintenanceEvent',
    'EventMetadata',

    # Event Bus
    'EventBus',
    'EventPublisher',
    'EventSubscriber',
    'get_event_bus',

    # Handlers
    'EventHandler',
    'EventHandlerRegistry',
    'handler',

    # Stream Consumer
    'StreamConsumer',
    'ConsumerGroup',
    'ConsumerConfig',

    # Dead Letter Queue
    'DeadLetterQueue',
    'FailedEvent',
    'RetryPolicy',
]
