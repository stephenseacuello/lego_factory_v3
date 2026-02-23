"""
Traced Audit - OpenTelemetry Trace Context Integration for Audit Trail

LegoMCP World-Class Manufacturing System v5.0
Phase 7: Observability - Audit-to-Trace Correlation

This module connects the OpenTelemetry distributed tracing system to the
audit trail, enabling end-to-end correlation of manufacturing operations
with their audit events for incident investigation and compliance.

Features:
- Automatic trace context injection into audit events
- Query audit events by trace ID
- Trace-to-audit correlation for SIEM integration
- W3C Trace Context (traceparent) support

Usage:
    from dashboard.services.traceability.traced_audit import TracedDigitalThread
    from dashboard.services.observability.tracing import get_tracer

    tracer = get_tracer()
    thread = TracedDigitalThread(tracer=tracer)

    with tracer.start_span("process_work_order") as span:
        # Audit events automatically include trace context
        thread.log_work_order_event(
            entity_id="WO-001",
            action="created",
            description="Work order created"
        )

    # Later, query by trace
    events = thread.get_events_by_trace(span.context.trace_id)

Author: LegoMCP Team
Version: 1.0.0
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .audit_chain import DigitalThread, get_digital_thread
from .audit_event import AuditEvent, AuditEventType, EntityType

# Import tracing - handle case where it might not be available
try:
    from ..observability.tracing import (
        TracingManager,
        SpanContext,
        get_tracer,
    )
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    TracingManager = None
    SpanContext = None

logger = logging.getLogger(__name__)


# Trace context metadata keys
TRACE_ID_KEY = "trace_id"
SPAN_ID_KEY = "span_id"
TRACEPARENT_KEY = "traceparent"
TRACE_FLAGS_KEY = "trace_flags"


class TracedDigitalThread:
    """
    Digital Thread wrapper with automatic trace context injection.

    This class wraps the DigitalThread to automatically capture and inject
    OpenTelemetry trace context into audit events, enabling:

    1. End-to-end correlation: Link audit events to distributed traces
    2. Incident investigation: Query all audit events in a trace
    3. SIEM integration: Correlate security events with operations
    4. Compliance: Full observability chain for auditors

    The trace context is stored in the event's metadata field:
    - trace_id: W3C trace ID (32-character hex)
    - span_id: Current span ID (16-character hex)
    - traceparent: Full W3C traceparent header
    - trace_flags: Sampling flags

    Usage:
        >>> tracer = get_tracer()
        >>> thread = TracedDigitalThread(tracer=tracer)
        >>>
        >>> with tracer.start_span("manufacturing_operation") as span:
        ...     thread.log_equipment_event(
        ...         entity_id="CNC-001",
        ...         action="started",
        ...         description="CNC mill started"
        ...     )
        >>>
        >>> # Query events by trace
        >>> events = thread.get_events_by_trace(span.context.trace_id)
    """

    def __init__(
        self,
        digital_thread: Optional[DigitalThread] = None,
        tracer: Optional["TracingManager"] = None,
        auto_inject: bool = True,
    ):
        """
        Initialize TracedDigitalThread.

        Args:
            digital_thread: Underlying DigitalThread instance. If None, uses singleton.
            tracer: TracingManager instance. If None, uses global tracer.
            auto_inject: Automatically inject trace context into events.
        """
        self._thread = digital_thread or get_digital_thread()
        self._tracer = tracer
        self._auto_inject = auto_inject

        if TRACING_AVAILABLE and self._tracer is None:
            try:
                self._tracer = get_tracer()
            except Exception as e:
                logger.warning(f"Could not get global tracer: {e}")

        logger.info(
            f"TracedDigitalThread initialized: auto_inject={auto_inject}, "
            f"tracing_available={TRACING_AVAILABLE and self._tracer is not None}"
        )

    def _get_trace_context(self) -> Dict[str, Any]:
        """
        Get current trace context from the tracer.

        Returns:
            Dictionary with trace context fields, or empty dict if no active span.
        """
        if not TRACING_AVAILABLE or self._tracer is None:
            return {}

        try:
            context = self._tracer.get_current_context()
            if context is None:
                return {}

            return {
                TRACE_ID_KEY: context.trace_id,
                SPAN_ID_KEY: context.span_id,
                TRACEPARENT_KEY: context.to_traceparent(),
                TRACE_FLAGS_KEY: context.trace_flags,
            }
        except Exception as e:
            logger.debug(f"Could not get trace context: {e}")
            return {}

    def _inject_trace_context(
        self,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Inject trace context into metadata dictionary.

        Args:
            metadata: Existing metadata dict (or None)

        Returns:
            Metadata dict with trace context added
        """
        result = dict(metadata) if metadata else {}

        if self._auto_inject:
            trace_context = self._get_trace_context()
            if trace_context:
                result.update(trace_context)

        return result

    # ===========================
    # Wrapped logging methods
    # ===========================

    def log_event(
        self,
        event_type: AuditEventType,
        entity_type: EntityType,
        entity_id: str,
        action: str,
        description: str = "",
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        user_name: str = "",
        session_id: str = "",
        source_ip: str = "",
        entity_name: str = "",
        event_subtype: str = "",
    ) -> AuditEvent:
        """
        Log a new audit event with automatic trace context injection.

        See DigitalThread.log_event for full documentation.
        """
        # Inject trace context into metadata
        enriched_metadata = self._inject_trace_context(metadata)

        return self._thread.log_event(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            description=description,
            data=data,
            metadata=enriched_metadata,
            previous_value=previous_value,
            new_value=new_value,
            user_id=user_id,
            user_name=user_name,
            session_id=session_id,
            source_ip=source_ip,
            entity_name=entity_name,
            event_subtype=event_subtype,
        )

    def log_work_order_event(
        self,
        entity_id: str,
        action: str,
        description: str = "",
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        user_name: str = "",
        entity_name: str = "",
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log a work order event with trace context."""
        enriched_metadata = self._inject_trace_context(metadata)

        # Use underlying method but intercept to add metadata
        event_type_map = {
            "created": AuditEventType.WORK_ORDER_CREATED,
            "started": AuditEventType.WORK_ORDER_STARTED,
            "completed": AuditEventType.WORK_ORDER_COMPLETED,
            "cancelled": AuditEventType.WORK_ORDER_CANCELLED,
            "modified": AuditEventType.WORK_ORDER_MODIFIED,
        }
        event_type = event_type_map.get(action, AuditEventType.WORK_ORDER_MODIFIED)

        return self._thread.log_event(
            event_type=event_type,
            entity_type=EntityType.WORK_ORDER,
            entity_id=entity_id,
            action=action,
            description=description,
            data=data,
            metadata=enriched_metadata,
            user_id=user_id,
            user_name=user_name,
            entity_name=entity_name,
            previous_value=previous_value,
            new_value=new_value,
        )

    def log_part_event(
        self,
        entity_id: str,
        action: str,
        description: str = "",
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        user_name: str = "",
        entity_name: str = "",
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log a part event with trace context."""
        enriched_metadata = self._inject_trace_context(metadata)

        event_type_map = {
            "created": AuditEventType.PART_CREATED,
            "modified": AuditEventType.PART_MODIFIED,
            "inspected": AuditEventType.PART_INSPECTED,
            "shipped": AuditEventType.PART_SHIPPED,
            "received": AuditEventType.PART_RECEIVED,
            "scrapped": AuditEventType.PART_SCRAPPED,
            "reworked": AuditEventType.PART_REWORKED,
        }
        event_type = event_type_map.get(action, AuditEventType.PART_MODIFIED)

        return self._thread.log_event(
            event_type=event_type,
            entity_type=EntityType.PART,
            entity_id=entity_id,
            action=action,
            description=description,
            data=data,
            metadata=enriched_metadata,
            user_id=user_id,
            user_name=user_name,
            entity_name=entity_name,
            previous_value=previous_value,
            new_value=new_value,
        )

    def log_equipment_event(
        self,
        entity_id: str,
        action: str,
        description: str = "",
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        user_name: str = "",
        entity_name: str = "",
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log an equipment event with trace context."""
        enriched_metadata = self._inject_trace_context(metadata)

        event_type_map = {
            "started": AuditEventType.EQUIPMENT_STARTED,
            "stopped": AuditEventType.EQUIPMENT_STOPPED,
            "maintenance": AuditEventType.EQUIPMENT_MAINTENANCE,
            "calibrated": AuditEventType.EQUIPMENT_CALIBRATED,
            "fault": AuditEventType.EQUIPMENT_FAULT,
            "parameter_change": AuditEventType.EQUIPMENT_PARAMETER_CHANGE,
        }
        event_type = event_type_map.get(action, AuditEventType.EQUIPMENT_PARAMETER_CHANGE)

        return self._thread.log_event(
            event_type=event_type,
            entity_type=EntityType.EQUIPMENT,
            entity_id=entity_id,
            action=action,
            description=description,
            data=data,
            metadata=enriched_metadata,
            user_id=user_id,
            user_name=user_name,
            entity_name=entity_name,
            previous_value=previous_value,
            new_value=new_value,
        )

    def log_quality_event(
        self,
        entity_id: str,
        action: str,
        description: str = "",
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        user_name: str = "",
        entity_name: str = "",
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log a quality event with trace context."""
        enriched_metadata = self._inject_trace_context(metadata)

        event_type_map = {
            "inspection": AuditEventType.QUALITY_INSPECTION,
            "defect_detected": AuditEventType.QUALITY_DEFECT_DETECTED,
            "hold_placed": AuditEventType.QUALITY_HOLD_PLACED,
            "hold_released": AuditEventType.QUALITY_HOLD_RELEASED,
            "ncr_created": AuditEventType.QUALITY_NCR_CREATED,
            "capa_initiated": AuditEventType.QUALITY_CAPA_INITIATED,
        }
        event_type = event_type_map.get(action, AuditEventType.QUALITY_INSPECTION)

        return self._thread.log_event(
            event_type=event_type,
            entity_type=EntityType.QUALITY_RECORD,
            entity_id=entity_id,
            action=action,
            description=description,
            data=data,
            metadata=enriched_metadata,
            user_id=user_id,
            user_name=user_name,
            entity_name=entity_name,
            previous_value=previous_value,
            new_value=new_value,
        )

    def log_material_event(
        self,
        entity_id: str,
        action: str,
        description: str = "",
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        user_name: str = "",
        entity_name: str = "",
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log a material event with trace context."""
        enriched_metadata = self._inject_trace_context(metadata)

        event_type_map = {
            "received": AuditEventType.MATERIAL_RECEIVED,
            "consumed": AuditEventType.MATERIAL_CONSUMED,
            "lot_created": AuditEventType.MATERIAL_LOT_CREATED,
            "quarantined": AuditEventType.MATERIAL_QUARANTINED,
        }
        event_type = event_type_map.get(action, AuditEventType.MATERIAL_RECEIVED)

        return self._thread.log_event(
            event_type=event_type,
            entity_type=EntityType.MATERIAL,
            entity_id=entity_id,
            action=action,
            description=description,
            data=data,
            metadata=enriched_metadata,
            user_id=user_id,
            user_name=user_name,
            entity_name=entity_name,
            previous_value=previous_value,
            new_value=new_value,
        )

    # ===========================
    # Trace-based query methods
    # ===========================

    def get_events_by_trace(
        self,
        trace_id: str,
        limit: int = 1000,
    ) -> List[AuditEvent]:
        """
        Get all audit events associated with a trace ID.

        This enables end-to-end correlation of distributed operations
        with their audit trail entries.

        Args:
            trace_id: The W3C trace ID to query
            limit: Maximum number of events to return

        Returns:
            List of AuditEvent objects with matching trace_id in metadata
        """
        # Query all events and filter by trace_id in metadata
        # Note: For production, this should use a database index
        all_events = self._thread.query_events(limit=limit * 10)

        traced_events = []
        for event in all_events:
            event_trace_id = event.metadata.get(TRACE_ID_KEY)
            if event_trace_id == trace_id:
                traced_events.append(event)
                if len(traced_events) >= limit:
                    break

        logger.debug(f"Found {len(traced_events)} events for trace {trace_id[:8]}...")
        return traced_events

    def get_events_by_span(
        self,
        trace_id: str,
        span_id: str,
    ) -> List[AuditEvent]:
        """
        Get audit events associated with a specific span.

        Args:
            trace_id: The W3C trace ID
            span_id: The specific span ID to query

        Returns:
            List of AuditEvent objects from this exact span
        """
        trace_events = self.get_events_by_trace(trace_id)

        return [
            event for event in trace_events
            if event.metadata.get(SPAN_ID_KEY) == span_id
        ]

    def get_trace_summary(
        self,
        trace_id: str,
    ) -> Dict[str, Any]:
        """
        Get a summary of audit events for a trace.

        Useful for dashboards and SIEM integration.

        Args:
            trace_id: The W3C trace ID

        Returns:
            Dictionary with trace summary statistics
        """
        events = self.get_events_by_trace(trace_id)

        if not events:
            return {
                "trace_id": trace_id,
                "event_count": 0,
                "entities_affected": [],
                "event_types": [],
                "users": [],
                "first_event": None,
                "last_event": None,
                "duration_ms": None,
            }

        # Collect unique values
        entities = set()
        event_types = set()
        users = set()

        for event in events:
            entities.add(f"{event.entity_type.value}:{event.entity_id}")
            event_types.add(event.event_type.value)
            if event.user_id:
                users.add(event.user_id)

        # Calculate duration
        timestamps = [event.timestamp for event in events]
        first_event = min(timestamps)
        last_event = max(timestamps)
        duration_ms = (last_event - first_event).total_seconds() * 1000

        return {
            "trace_id": trace_id,
            "event_count": len(events),
            "entities_affected": sorted(entities),
            "event_types": sorted(event_types),
            "users": sorted(users),
            "first_event": first_event.isoformat(),
            "last_event": last_event.isoformat(),
            "duration_ms": duration_ms,
        }

    # ===========================
    # Pass-through methods
    # ===========================

    def verify_chain(self, *args, **kwargs):
        """Verify audit chain integrity."""
        return self._thread.verify_chain(*args, **kwargs)

    def get_entity_history(self, *args, **kwargs):
        """Get entity history."""
        return self._thread.get_entity_history(*args, **kwargs)

    def query_events(self, *args, **kwargs):
        """Query events with filters."""
        return self._thread.query_events(*args, **kwargs)

    def get_recent_events(self, *args, **kwargs):
        """Get recent events."""
        return self._thread.get_recent_events(*args, **kwargs)

    def get_chain_statistics(self, *args, **kwargs):
        """Get chain statistics."""
        return self._thread.get_chain_statistics(*args, **kwargs)

    def export_chain(self, *args, **kwargs):
        """Export chain to file."""
        return self._thread.export_chain(*args, **kwargs)

    @property
    def digital_thread(self) -> DigitalThread:
        """Access the underlying DigitalThread."""
        return self._thread

    @property
    def tracer(self) -> Optional["TracingManager"]:
        """Access the tracer instance."""
        return self._tracer


# ===========================
# Singleton instance
# ===========================

_traced_thread_instance: Optional[TracedDigitalThread] = None


def get_traced_digital_thread(
    tracer: Optional["TracingManager"] = None,
    auto_inject: bool = True,
) -> TracedDigitalThread:
    """
    Get or create the singleton TracedDigitalThread instance.

    Args:
        tracer: TracingManager instance (only used on first call)
        auto_inject: Enable auto trace injection (only used on first call)

    Returns:
        The TracedDigitalThread singleton instance
    """
    global _traced_thread_instance

    if _traced_thread_instance is None:
        _traced_thread_instance = TracedDigitalThread(
            tracer=tracer,
            auto_inject=auto_inject,
        )

    return _traced_thread_instance


def reset_traced_digital_thread() -> None:
    """Reset the singleton instance (for testing)."""
    global _traced_thread_instance
    _traced_thread_instance = None
