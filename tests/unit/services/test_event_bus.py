"""
LEGO Factory v3 - Event Bus Unit Tests
======================================
Tests for event-driven architecture components.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

from services.advanced.events.event_types import (
    ManufacturingEvent,
    EventCategory,
    EventPriority,
    SourceLayer,
    EventMetadata,
)
from services.advanced.events.event_bus import (
    EventBus,
    EventPublisher,
    EventSubscriber,
)


class TestEventCategory:
    """Test EventCategory enum."""

    def test_event_categories_exist(self):
        """Test all expected event categories exist."""
        assert EventCategory.MACHINE.value == "machine"
        assert EventCategory.QUALITY.value == "quality"
        assert EventCategory.SCHEDULING.value == "scheduling"
        assert EventCategory.INVENTORY.value == "inventory"
        assert EventCategory.MAINTENANCE.value == "maintenance"
        assert EventCategory.PRODUCTION.value == "production"
        assert EventCategory.ERP.value == "erp"
        assert EventCategory.SYSTEM.value == "system"


class TestEventPriority:
    """Test EventPriority enum."""

    def test_event_priorities_exist(self):
        """Test all expected priorities exist."""
        assert EventPriority.CRITICAL.value == "critical"
        assert EventPriority.HIGH.value == "high"
        assert EventPriority.NORMAL.value == "normal"
        assert EventPriority.LOW.value == "low"


class TestSourceLayer:
    """Test SourceLayer enum."""

    def test_source_layers_exist(self):
        """Test all ISA-95 layers exist."""
        assert SourceLayer.L0.value == "L0"
        assert SourceLayer.L1.value == "L1"
        assert SourceLayer.L2.value == "L2"
        assert SourceLayer.L3.value == "L3"
        assert SourceLayer.L4.value == "L4"


class TestEventMetadata:
    """Test EventMetadata dataclass."""

    def test_default_metadata(self):
        """Test default metadata values."""
        metadata = EventMetadata()
        assert metadata.correlation_id is None
        assert metadata.user_id is None
        assert metadata.version == 1

    def test_custom_metadata(self):
        """Test custom metadata values."""
        metadata = EventMetadata(
            correlation_id="corr-123",
            user_id="user-456",
            trace_id="trace-789",
        )
        assert metadata.correlation_id == "corr-123"
        assert metadata.user_id == "user-456"
        assert metadata.trace_id == "trace-789"

    def test_to_dict_excludes_none(self):
        """Test to_dict excludes None values."""
        metadata = EventMetadata(
            correlation_id="corr-123",
            user_id=None,
        )
        result = metadata.to_dict()
        assert "correlation_id" in result
        assert "user_id" not in result
        assert result["version"] == 1


class TestManufacturingEvent:
    """Test ManufacturingEvent dataclass."""

    def test_event_creation(self):
        """Test creating a manufacturing event."""
        event = ManufacturingEvent(
            event_type="machine_started",
            category=EventCategory.MACHINE,
        )
        assert event.event_type == "machine_started"
        assert event.category == EventCategory.MACHINE
        assert event.priority == EventPriority.NORMAL
        assert event.source_layer == SourceLayer.L3
        assert isinstance(event.event_id, str)
        assert len(event.event_id) > 0

    def test_event_with_payload(self):
        """Test event with custom payload."""
        event = ManufacturingEvent(
            event_type="temperature_reading",
            category=EventCategory.MACHINE,
            payload={"temperature": 25.5, "sensor_id": "temp-001"},
        )
        assert event.payload["temperature"] == 25.5
        assert event.payload["sensor_id"] == "temp-001"

    def test_event_with_work_ids(self):
        """Test event with work center and work order IDs."""
        event = ManufacturingEvent(
            event_type="job_started",
            category=EventCategory.PRODUCTION,
            work_center_id="wc-001",
            work_order_id="wo-123",
        )
        assert event.work_center_id == "wc-001"
        assert event.work_order_id == "wo-123"

    def test_to_dict(self):
        """Test converting event to dictionary."""
        event = ManufacturingEvent(
            event_type="quality_check",
            category=EventCategory.QUALITY,
            priority=EventPriority.HIGH,
            payload={"result": "pass"},
        )
        result = event.to_dict()

        assert result["event_type"] == "quality_check"
        assert result["category"] == "quality"
        assert result["priority"] == "high"
        assert result["payload"]["result"] == "pass"
        assert "timestamp" in result
        assert "event_id" in result

    def test_to_json(self):
        """Test serializing event to JSON."""
        event = ManufacturingEvent(
            event_type="alarm",
            category=EventCategory.MACHINE,
        )
        json_str = event.to_json()

        assert isinstance(json_str, str)
        assert "alarm" in json_str
        assert "machine" in json_str


class TestEventBus:
    """Test EventBus class."""

    @pytest.fixture
    def event_bus(self):
        """Create an event bus instance."""
        return EventBus(redis_url="redis://localhost:6379", prefix="test:events")

    def test_event_bus_creation(self, event_bus):
        """Test event bus initialization."""
        assert event_bus is not None
        assert event_bus.prefix == "test:events"
        assert event_bus._running is False

    def test_get_stream_key(self, event_bus):
        """Test getting stream key for a category."""
        key = event_bus._get_stream_key(EventCategory.MACHINE)
        assert key == "test:events:machine"

    @pytest.mark.asyncio
    async def test_connect_without_redis(self, event_bus):
        """Test connecting when Redis is not available."""
        with patch('services.advanced.events.event_bus.REDIS_AVAILABLE', False):
            await event_bus.connect()
            # Should not raise, just log warning

    @pytest.mark.asyncio
    async def test_disconnect(self, event_bus):
        """Test disconnecting from event bus."""
        event_bus._redis = MagicMock()
        event_bus._redis.close = AsyncMock()

        await event_bus.disconnect()
        assert event_bus._redis is None

    def test_publish_fallback(self, event_bus):
        """Test fallback publish when Redis unavailable."""
        callback = MagicMock()
        event_bus._subscribers["test:events:machine"] = [callback]

        event = ManufacturingEvent(
            event_type="test",
            category=EventCategory.MACHINE,
        )

        result = event_bus._publish_fallback(event)
        assert result is not None
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_batch_empty(self, event_bus):
        """Test publishing empty batch returns empty list."""
        result = await event_bus.publish_batch([])
        assert result == []

    def test_stop(self, event_bus):
        """Test stopping event bus."""
        event_bus._running = True
        event_bus.stop()
        assert event_bus._running is False


class TestEventPublisher:
    """Test EventPublisher class."""

    @pytest.fixture
    def event_bus(self):
        """Create a mock event bus."""
        bus = MagicMock()
        bus.publish = AsyncMock(return_value="msg-123")
        bus.publish_batch = AsyncMock(return_value=["msg-1", "msg-2"])
        return bus

    @pytest.fixture
    def publisher(self, event_bus):
        """Create an event publisher."""
        return EventPublisher(event_bus)

    @pytest.mark.asyncio
    async def test_publish(self, publisher, event_bus):
        """Test publishing a single event."""
        event = ManufacturingEvent(
            event_type="test",
            category=EventCategory.MACHINE,
        )

        result = await publisher.publish(event)
        assert result == "msg-123"
        event_bus.publish.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_publish_batch(self, publisher, event_bus):
        """Test publishing multiple events."""
        events = [
            ManufacturingEvent(event_type="event1", category=EventCategory.MACHINE),
            ManufacturingEvent(event_type="event2", category=EventCategory.QUALITY),
        ]

        result = await publisher.publish_batch(events)
        assert len(result) == 2
        event_bus.publish_batch.assert_called_once_with(events)


class TestEventSubscriber:
    """Test EventSubscriber class."""

    @pytest.fixture
    def event_bus(self):
        """Create a mock event bus."""
        bus = MagicMock()
        bus.subscribe = AsyncMock()
        return bus

    @pytest.fixture
    def subscriber(self, event_bus):
        """Create an event subscriber."""
        return EventSubscriber(event_bus)

    def test_on_decorator(self, subscriber):
        """Test registering handler with decorator."""

        @subscriber.on(EventCategory.MACHINE, EventCategory.QUALITY)
        def handle_event(event):
            pass

        assert EventCategory.MACHINE in subscriber._handlers
        assert EventCategory.QUALITY in subscriber._handlers
        assert len(subscriber._handlers[EventCategory.MACHINE]) == 1
        assert len(subscriber._handlers[EventCategory.QUALITY]) == 1

    def test_multiple_handlers_same_category(self, subscriber):
        """Test multiple handlers for same category."""

        @subscriber.on(EventCategory.MACHINE)
        def handler1(event):
            pass

        @subscriber.on(EventCategory.MACHINE)
        def handler2(event):
            pass

        assert len(subscriber._handlers[EventCategory.MACHINE]) == 2


class TestEventIntegration:
    """Integration tests for event system."""

    def test_event_round_trip(self):
        """Test creating, serializing, and deserializing an event."""
        original = ManufacturingEvent(
            event_type="quality_inspection",
            category=EventCategory.QUALITY,
            priority=EventPriority.HIGH,
            work_order_id="wo-123",
            payload={
                "inspection_type": "visual",
                "result": "pass",
                "defects_found": 0,
            },
            metadata=EventMetadata(
                correlation_id="corr-456",
                user_id="inspector-001",
            ),
        )

        # Serialize
        event_dict = original.to_dict()

        # Verify structure
        assert event_dict["event_type"] == "quality_inspection"
        assert event_dict["category"] == "quality"
        assert event_dict["priority"] == "high"
        assert event_dict["work_order_id"] == "wo-123"
        assert event_dict["payload"]["inspection_type"] == "visual"
        assert event_dict["metadata"]["correlation_id"] == "corr-456"

        # Can be reconstructed
        reconstructed = ManufacturingEvent(
            event_type=event_dict["event_type"],
            category=EventCategory(event_dict["category"]),
            priority=EventPriority(event_dict["priority"]),
            work_order_id=event_dict["work_order_id"],
            payload=event_dict["payload"],
        )
        assert reconstructed.event_type == original.event_type
        assert reconstructed.category == original.category
