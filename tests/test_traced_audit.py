"""
Tests for Traced Audit - OpenTelemetry Integration with Audit Trail

Tests verify:
- Trace context injection into audit events
- Query by trace ID
- Query by span ID
- Trace summary generation
- Integration with TracingManager
"""

import os
import tempfile
from datetime import datetime, timedelta
from typing import Optional

import pytest

# Import audit components
from dashboard.services.traceability.audit_chain import DigitalThread
from dashboard.services.traceability.audit_event import (
    AuditEvent,
    AuditEventType,
    EntityType,
)
from dashboard.services.traceability.traced_audit import (
    TracedDigitalThread,
    TRACE_ID_KEY,
    SPAN_ID_KEY,
    TRACEPARENT_KEY,
    reset_traced_digital_thread,
)

# Import tracing components
from dashboard.services.observability.tracing import (
    TracingManager,
    SpanContext,
    SpanKind,
    ConsoleSpanExporter,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def digital_thread(temp_db):
    """Create a DigitalThread with temporary database."""
    return DigitalThread(
        db_path=temp_db,
        auto_verify=False,
        verify_on_startup=False,
    )


@pytest.fixture
def tracer():
    """Create a TracingManager for testing."""
    return TracingManager(
        service_name="test-service",
        exporters=[],  # No export during tests
        sample_rate=1.0,
    )


@pytest.fixture
def traced_thread(digital_thread, tracer):
    """Create a TracedDigitalThread for testing."""
    reset_traced_digital_thread()
    return TracedDigitalThread(
        digital_thread=digital_thread,
        tracer=tracer,
        auto_inject=True,
    )


class TestTracedDigitalThreadBasics:
    """Basic functionality tests."""

    def test_initialization(self, traced_thread):
        """Test TracedDigitalThread initializes correctly."""
        assert traced_thread is not None
        assert traced_thread.digital_thread is not None
        assert traced_thread.tracer is not None

    def test_initialization_without_tracer(self, digital_thread):
        """Test initialization without tracer."""
        thread = TracedDigitalThread(
            digital_thread=digital_thread,
            tracer=None,
            auto_inject=True,
        )
        assert thread is not None
        # Should still work, just without trace injection

    def test_initialization_with_auto_inject_disabled(self, digital_thread, tracer):
        """Test initialization with auto_inject disabled."""
        thread = TracedDigitalThread(
            digital_thread=digital_thread,
            tracer=tracer,
            auto_inject=False,
        )
        assert thread is not None
        assert thread._auto_inject is False


class TestTraceContextInjection:
    """Tests for trace context injection into audit events."""

    def test_event_without_active_span_has_no_trace_context(self, traced_thread):
        """Events logged without an active span should have no trace context."""
        event = traced_thread.log_work_order_event(
            entity_id="WO-001",
            action="created",
            description="Test work order",
        )

        # No active span, so no trace context
        assert TRACE_ID_KEY not in event.metadata or event.metadata[TRACE_ID_KEY] is None

    def test_event_with_active_span_has_trace_context(self, traced_thread, tracer):
        """Events logged within a span should have trace context."""
        with tracer.start_span("test_operation") as span:
            event = traced_thread.log_work_order_event(
                entity_id="WO-002",
                action="created",
                description="Test work order with trace",
            )

            # Should have trace context from the span
            assert event.metadata.get(TRACE_ID_KEY) == span.context.trace_id
            assert event.metadata.get(SPAN_ID_KEY) == span.context.span_id
            assert TRACEPARENT_KEY in event.metadata

    def test_traceparent_format(self, traced_thread, tracer):
        """Verify traceparent follows W3C format."""
        with tracer.start_span("test_operation") as span:
            event = traced_thread.log_equipment_event(
                entity_id="EQ-001",
                action="started",
                description="Equipment started",
            )

            traceparent = event.metadata.get(TRACEPARENT_KEY)
            assert traceparent is not None

            # W3C format: 00-{trace_id}-{span_id}-{flags}
            parts = traceparent.split("-")
            assert len(parts) == 4
            assert parts[0] == "00"  # Version
            assert len(parts[1]) == 32  # Trace ID (32 hex chars)
            assert len(parts[2]) == 16  # Span ID (16 hex chars)

    def test_nested_spans_different_span_ids(self, traced_thread, tracer):
        """Nested spans should produce different span IDs but same trace ID."""
        with tracer.start_span("parent_operation") as parent:
            event1 = traced_thread.log_work_order_event(
                entity_id="WO-003",
                action="created",
                description="Created in parent span",
            )

            with tracer.start_span("child_operation") as child:
                event2 = traced_thread.log_part_event(
                    entity_id="PART-001",
                    action="created",
                    description="Created in child span",
                )

        # Same trace ID
        assert event1.metadata[TRACE_ID_KEY] == event2.metadata[TRACE_ID_KEY]

        # Different span IDs
        assert event1.metadata[SPAN_ID_KEY] != event2.metadata[SPAN_ID_KEY]

    def test_existing_metadata_preserved(self, traced_thread, tracer):
        """Existing metadata should be preserved when trace context is added."""
        with tracer.start_span("test_operation"):
            event = traced_thread.log_work_order_event(
                entity_id="WO-004",
                action="created",
                description="With existing metadata",
                metadata={"custom_key": "custom_value", "priority": "high"},
            )

            # Trace context added
            assert TRACE_ID_KEY in event.metadata

            # Original metadata preserved
            assert event.metadata["custom_key"] == "custom_value"
            assert event.metadata["priority"] == "high"


class TestQueryByTrace:
    """Tests for querying events by trace ID."""

    def test_get_events_by_trace_returns_matching_events(self, traced_thread, tracer):
        """get_events_by_trace should return all events with matching trace ID."""
        with tracer.start_span("batch_operation") as span:
            # Log multiple events in the same trace
            traced_thread.log_work_order_event(
                entity_id="WO-010",
                action="created",
                description="First event",
            )
            traced_thread.log_part_event(
                entity_id="PART-010",
                action="created",
                description="Second event",
            )
            traced_thread.log_equipment_event(
                entity_id="EQ-010",
                action="started",
                description="Third event",
            )

            trace_id = span.context.trace_id

        # Query by trace
        events = traced_thread.get_events_by_trace(trace_id)

        assert len(events) == 3
        for event in events:
            assert event.metadata[TRACE_ID_KEY] == trace_id

    def test_get_events_by_trace_returns_empty_for_unknown_trace(self, traced_thread):
        """get_events_by_trace should return empty list for unknown trace."""
        events = traced_thread.get_events_by_trace("00000000000000000000000000000000")
        assert events == []

    def test_get_events_by_trace_respects_limit(self, traced_thread, tracer):
        """get_events_by_trace should respect the limit parameter."""
        with tracer.start_span("many_events") as span:
            for i in range(10):
                traced_thread.log_part_event(
                    entity_id=f"PART-{i:03d}",
                    action="created",
                    description=f"Part {i}",
                )
            trace_id = span.context.trace_id

        events = traced_thread.get_events_by_trace(trace_id, limit=5)
        assert len(events) == 5


class TestQueryBySpan:
    """Tests for querying events by span ID."""

    def test_get_events_by_span_returns_exact_span_events(self, traced_thread, tracer):
        """get_events_by_span should return only events from specific span."""
        with tracer.start_span("parent") as parent:
            traced_thread.log_work_order_event(
                entity_id="WO-020",
                action="created",
                description="In parent",
            )
            parent_span_id = parent.context.span_id

            with tracer.start_span("child") as child:
                traced_thread.log_part_event(
                    entity_id="PART-020",
                    action="created",
                    description="In child",
                )
                child_span_id = child.context.span_id

            trace_id = parent.context.trace_id

        # Query parent span only
        parent_events = traced_thread.get_events_by_span(trace_id, parent_span_id)
        assert len(parent_events) == 1
        assert parent_events[0].entity_id == "WO-020"

        # Query child span only
        child_events = traced_thread.get_events_by_span(trace_id, child_span_id)
        assert len(child_events) == 1
        assert child_events[0].entity_id == "PART-020"


class TestTraceSummary:
    """Tests for trace summary generation."""

    def test_trace_summary_returns_statistics(self, traced_thread, tracer):
        """get_trace_summary should return comprehensive statistics."""
        with tracer.start_span("complex_operation") as span:
            traced_thread.log_work_order_event(
                entity_id="WO-030",
                action="created",
                user_id="user-001",
            )
            traced_thread.log_part_event(
                entity_id="PART-030",
                action="created",
                user_id="user-002",
            )
            traced_thread.log_equipment_event(
                entity_id="EQ-030",
                action="started",
                user_id="user-001",
            )
            trace_id = span.context.trace_id

        summary = traced_thread.get_trace_summary(trace_id)

        assert summary["trace_id"] == trace_id
        assert summary["event_count"] == 3
        assert len(summary["entities_affected"]) == 3
        assert len(summary["event_types"]) == 3
        assert len(summary["users"]) == 2  # user-001 and user-002
        assert summary["first_event"] is not None
        assert summary["last_event"] is not None
        assert summary["duration_ms"] is not None

    def test_trace_summary_for_unknown_trace(self, traced_thread):
        """get_trace_summary should return empty summary for unknown trace."""
        summary = traced_thread.get_trace_summary("unknown-trace-id")

        assert summary["event_count"] == 0
        assert summary["entities_affected"] == []
        assert summary["first_event"] is None


class TestAllEventTypes:
    """Test trace injection for all event types."""

    def test_work_order_event(self, traced_thread, tracer):
        """Work order events should have trace context."""
        with tracer.start_span("test") as span:
            event = traced_thread.log_work_order_event(
                entity_id="WO-100",
                action="created",
            )
        assert event.metadata.get(TRACE_ID_KEY) == span.context.trace_id

    def test_part_event(self, traced_thread, tracer):
        """Part events should have trace context."""
        with tracer.start_span("test") as span:
            event = traced_thread.log_part_event(
                entity_id="PART-100",
                action="created",
            )
        assert event.metadata.get(TRACE_ID_KEY) == span.context.trace_id

    def test_equipment_event(self, traced_thread, tracer):
        """Equipment events should have trace context."""
        with tracer.start_span("test") as span:
            event = traced_thread.log_equipment_event(
                entity_id="EQ-100",
                action="started",
            )
        assert event.metadata.get(TRACE_ID_KEY) == span.context.trace_id

    def test_quality_event(self, traced_thread, tracer):
        """Quality events should have trace context."""
        with tracer.start_span("test") as span:
            event = traced_thread.log_quality_event(
                entity_id="QC-100",
                action="inspection",
            )
        assert event.metadata.get(TRACE_ID_KEY) == span.context.trace_id

    def test_material_event(self, traced_thread, tracer):
        """Material events should have trace context."""
        with tracer.start_span("test") as span:
            event = traced_thread.log_material_event(
                entity_id="MAT-100",
                action="received",
            )
        assert event.metadata.get(TRACE_ID_KEY) == span.context.trace_id

    def test_generic_log_event(self, traced_thread, tracer):
        """Generic log_event should have trace context."""
        with tracer.start_span("test") as span:
            event = traced_thread.log_event(
                event_type=AuditEventType.CUSTOM,
                entity_type=EntityType.CUSTOM,
                entity_id="CUSTOM-100",
                action="custom_action",
            )
        assert event.metadata.get(TRACE_ID_KEY) == span.context.trace_id


class TestPassThroughMethods:
    """Test that pass-through methods work correctly."""

    def test_verify_chain(self, traced_thread, tracer):
        """verify_chain should work through TracedDigitalThread."""
        with tracer.start_span("test"):
            traced_thread.log_work_order_event(
                entity_id="WO-200",
                action="created",
            )

        status = traced_thread.verify_chain()
        assert status.is_valid is True

    def test_get_entity_history(self, traced_thread, tracer):
        """get_entity_history should work through TracedDigitalThread."""
        with tracer.start_span("test"):
            traced_thread.log_work_order_event(
                entity_id="WO-201",
                action="created",
            )
            traced_thread.log_work_order_event(
                entity_id="WO-201",
                action="started",
            )

        history = traced_thread.get_entity_history(
            EntityType.WORK_ORDER,
            "WO-201",
        )
        assert history.total_events == 2

    def test_get_chain_statistics(self, traced_thread, tracer):
        """get_chain_statistics should work through TracedDigitalThread."""
        with tracer.start_span("test"):
            traced_thread.log_work_order_event(
                entity_id="WO-202",
                action="created",
            )

        stats = traced_thread.get_chain_statistics()
        assert stats["total_events"] >= 1

    def test_query_events(self, traced_thread, tracer):
        """query_events should work through TracedDigitalThread."""
        with tracer.start_span("test"):
            traced_thread.log_work_order_event(
                entity_id="WO-203",
                action="created",
                user_id="test-user",
            )

        events = traced_thread.query_events(user_id="test-user")
        assert len(events) >= 1


class TestAutoInjectDisabled:
    """Tests with auto_inject disabled."""

    def test_no_trace_context_when_disabled(self, digital_thread, tracer):
        """Events should not have trace context when auto_inject is disabled."""
        thread = TracedDigitalThread(
            digital_thread=digital_thread,
            tracer=tracer,
            auto_inject=False,
        )

        with tracer.start_span("test_operation") as span:
            event = thread.log_work_order_event(
                entity_id="WO-300",
                action="created",
            )

            # Should NOT have trace context
            assert TRACE_ID_KEY not in event.metadata or not event.metadata[TRACE_ID_KEY]


class TestEdgeCases:
    """Edge case tests."""

    def test_rapid_event_logging(self, traced_thread, tracer):
        """Test rapid logging of many events in a single span."""
        with tracer.start_span("rapid_logging") as span:
            events = []
            for i in range(100):
                event = traced_thread.log_part_event(
                    entity_id=f"RAPID-{i:04d}",
                    action="created",
                )
                events.append(event)

            trace_id = span.context.trace_id

        # All events should have the same trace ID
        for event in events:
            assert event.metadata[TRACE_ID_KEY] == trace_id

        # Query should return all events
        queried = traced_thread.get_events_by_trace(trace_id)
        assert len(queried) == 100

    def test_concurrent_traces(self, digital_thread):
        """Test that concurrent traces maintain isolation."""
        tracer1 = TracingManager(service_name="service1", exporters=[])
        tracer2 = TracingManager(service_name="service2", exporters=[])

        thread = TracedDigitalThread(
            digital_thread=digital_thread,
            tracer=tracer1,
        )

        # Note: This test is limited because we can only use one tracer at a time
        # Real concurrent testing would require threads
        with tracer1.start_span("trace1") as span1:
            event1 = thread.log_work_order_event(
                entity_id="CONCURRENT-001",
                action="created",
            )
            trace_id_1 = span1.context.trace_id

        # Change tracer
        thread._tracer = tracer2

        with tracer2.start_span("trace2") as span2:
            event2 = thread.log_work_order_event(
                entity_id="CONCURRENT-002",
                action="created",
            )
            trace_id_2 = span2.context.trace_id

        # Different traces
        assert trace_id_1 != trace_id_2
        assert event1.metadata[TRACE_ID_KEY] == trace_id_1
        assert event2.metadata[TRACE_ID_KEY] == trace_id_2
