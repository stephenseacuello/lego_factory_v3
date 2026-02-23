"""
OpenTelemetry Distributed Tracing

Implements W3C Trace Context propagation for end-to-end
manufacturing operation visibility.

Reference: OpenTelemetry Specification, W3C Trace Context
"""

import logging
import time
import uuid
import functools
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from datetime import datetime
from enum import Enum
import threading
import json

logger = logging.getLogger(__name__)

# Type variable for generic decorator
F = TypeVar('F', bound=Callable[..., Any])


class SpanKind(Enum):
    """OpenTelemetry Span kinds."""
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(Enum):
    """Span status codes."""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanContext:
    """
    W3C Trace Context compatible span context.

    Format: {version}-{trace_id}-{span_id}-{trace_flags}
    Example: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
    """
    trace_id: str
    span_id: str
    trace_flags: int = 1  # Sampled
    trace_state: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def generate(cls) -> "SpanContext":
        """Generate new span context with random IDs."""
        return cls(
            trace_id=uuid.uuid4().hex,
            span_id=uuid.uuid4().hex[:16],
            trace_flags=1
        )

    @classmethod
    def from_traceparent(cls, traceparent: str) -> Optional["SpanContext"]:
        """Parse W3C traceparent header."""
        try:
            parts = traceparent.split("-")
            if len(parts) != 4:
                return None
            version, trace_id, span_id, trace_flags = parts
            if version != "00":
                return None
            return cls(
                trace_id=trace_id,
                span_id=span_id,
                trace_flags=int(trace_flags, 16)
            )
        except Exception:
            return None

    def to_traceparent(self) -> str:
        """Generate W3C traceparent header."""
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags:02x}"

    def child_context(self) -> "SpanContext":
        """Create child span context (new span_id, same trace_id)."""
        return SpanContext(
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex[:16],
            trace_flags=self.trace_flags,
            trace_state=self.trace_state.copy()
        )

    @property
    def is_sampled(self) -> bool:
        """Check if trace is sampled."""
        return bool(self.trace_flags & 0x01)


@dataclass
class SpanEvent:
    """Event recorded during a span."""
    name: str
    timestamp: float
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpanLink:
    """Link to another span."""
    context: SpanContext
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """
    OpenTelemetry-compatible Span.

    Represents a single operation within a trace.
    """
    name: str
    context: SpanContext
    parent_context: Optional[SpanContext] = None
    kind: SpanKind = SpanKind.INTERNAL
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: SpanStatus = SpanStatus.UNSET
    status_message: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    links: List[SpanLink] = field(default_factory=list)

    # Manufacturing-specific attributes
    equipment_id: Optional[str] = None
    operation_type: Optional[str] = None
    job_id: Optional[str] = None

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def set_attributes(self, attributes: Dict[str, Any]) -> None:
        """Set multiple attributes."""
        self.attributes.update(attributes)

    def add_event(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None
    ) -> None:
        """Add an event to the span."""
        self.events.append(SpanEvent(
            name=name,
            timestamp=timestamp or time.time(),
            attributes=attributes or {}
        ))

    def add_link(
        self,
        context: SpanContext,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a link to another span."""
        self.links.append(SpanLink(
            context=context,
            attributes=attributes or {}
        ))

    def set_status(self, status: SpanStatus, message: Optional[str] = None) -> None:
        """Set span status."""
        self.status = status
        self.status_message = message

    def record_exception(self, exception: Exception) -> None:
        """Record an exception as an event."""
        self.add_event("exception", {
            "exception.type": type(exception).__name__,
            "exception.message": str(exception),
            "exception.stacktrace": repr(exception)
        })
        self.set_status(SpanStatus.ERROR, str(exception))

    def end(self, end_time: Optional[float] = None) -> None:
        """End the span."""
        self.end_time = end_time or time.time()

    @property
    def duration_ms(self) -> Optional[float]:
        """Get span duration in milliseconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary for export."""
        return {
            "traceId": self.context.trace_id,
            "spanId": self.context.span_id,
            "parentSpanId": self.parent_context.span_id if self.parent_context else None,
            "name": self.name,
            "kind": self.kind.value,
            "startTimeUnixNano": int(self.start_time * 1e9),
            "endTimeUnixNano": int(self.end_time * 1e9) if self.end_time else None,
            "status": {
                "code": self.status.value,
                "message": self.status_message
            },
            "attributes": self.attributes,
            "events": [
                {
                    "name": e.name,
                    "timeUnixNano": int(e.timestamp * 1e9),
                    "attributes": e.attributes
                }
                for e in self.events
            ],
            "links": [
                {
                    "traceId": l.context.trace_id,
                    "spanId": l.context.span_id,
                    "attributes": l.attributes
                }
                for l in self.links
            ],
            # Manufacturing extensions
            "manufacturing": {
                "equipmentId": self.equipment_id,
                "operationType": self.operation_type,
                "jobId": self.job_id
            }
        }


class SpanExporter:
    """Base class for span exporters."""

    def export(self, spans: List[Span]) -> bool:
        """Export spans. Returns True on success."""
        raise NotImplementedError


class ConsoleSpanExporter(SpanExporter):
    """Export spans to console for debugging."""

    def export(self, spans: List[Span]) -> bool:
        for span in spans:
            logger.info(
                f"SPAN: {span.name} | trace={span.context.trace_id[:8]} | "
                f"span={span.context.span_id[:8]} | "
                f"duration={span.duration_ms:.2f}ms | "
                f"status={span.status.value}"
            )
        return True


class OTLPSpanExporter(SpanExporter):
    """
    Export spans to OTLP endpoint (Jaeger, Zipkin, etc.).

    Implements OTLP/HTTP protocol.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:4318/v1/traces",
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0
    ):
        self.endpoint = endpoint
        self.headers = headers or {}
        self.timeout = timeout

    def export(self, spans: List[Span]) -> bool:
        """Export spans via OTLP/HTTP."""
        try:
            import urllib.request
            import urllib.error

            # Build OTLP payload
            payload = {
                "resourceSpans": [
                    {
                        "resource": {
                            "attributes": [
                                {"key": "service.name", "value": {"stringValue": "lego-mcp"}},
                                {"key": "service.version", "value": {"stringValue": "2.0.0"}}
                            ]
                        },
                        "scopeSpans": [
                            {
                                "scope": {"name": "lego.mcp.manufacturing"},
                                "spans": [self._convert_span(s) for s in spans]
                            }
                        ]
                    }
                ]
            }

            data = json.dumps(payload).encode('utf-8')
            headers = {
                "Content-Type": "application/json",
                **self.headers
            }

            req = urllib.request.Request(
                self.endpoint,
                data=data,
                headers=headers,
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.status == 200

        except Exception as e:
            logger.warning(f"Failed to export spans: {e}")
            return False

    def _convert_span(self, span: Span) -> Dict[str, Any]:
        """Convert span to OTLP format."""
        return {
            "traceId": span.context.trace_id,
            "spanId": span.context.span_id,
            "parentSpanId": span.parent_context.span_id if span.parent_context else "",
            "name": span.name,
            "kind": self._span_kind_to_int(span.kind),
            "startTimeUnixNano": str(int(span.start_time * 1e9)),
            "endTimeUnixNano": str(int(span.end_time * 1e9)) if span.end_time else "",
            "attributes": [
                {"key": k, "value": self._convert_value(v)}
                for k, v in span.attributes.items()
            ],
            "status": {
                "code": 1 if span.status == SpanStatus.OK else
                       2 if span.status == SpanStatus.ERROR else 0
            }
        }

    def _span_kind_to_int(self, kind: SpanKind) -> int:
        """Convert span kind to OTLP integer."""
        mapping = {
            SpanKind.INTERNAL: 1,
            SpanKind.SERVER: 2,
            SpanKind.CLIENT: 3,
            SpanKind.PRODUCER: 4,
            SpanKind.CONSUMER: 5
        }
        return mapping.get(kind, 1)

    def _convert_value(self, value: Any) -> Dict[str, Any]:
        """Convert Python value to OTLP attribute value."""
        if isinstance(value, bool):
            return {"boolValue": value}
        elif isinstance(value, int):
            return {"intValue": str(value)}
        elif isinstance(value, float):
            return {"doubleValue": value}
        else:
            return {"stringValue": str(value)}


class TracingManager:
    """
    Central tracing manager for distributed tracing.

    Features:
    - Automatic trace context propagation
    - Sampling strategies
    - Multiple exporter support
    - Manufacturing-specific semantic conventions

    Usage:
        >>> tracer = TracingManager()
        >>> with tracer.start_span("print_job") as span:
        ...     span.set_attribute("job_id", "JOB-001")
        ...     # Do work
    """

    # Thread-local storage for current span
    _local = threading.local()

    def __init__(
        self,
        service_name: str = "lego-mcp",
        exporters: Optional[List[SpanExporter]] = None,
        sample_rate: float = 1.0,
        max_spans_per_trace: int = 1000,
        export_batch_size: int = 100,
        export_interval: float = 5.0
    ):
        """
        Initialize tracing manager.

        Args:
            service_name: Name of the service
            exporters: List of span exporters
            sample_rate: Trace sampling rate (0.0-1.0)
            max_spans_per_trace: Maximum spans per trace
            export_batch_size: Batch size for export
            export_interval: Export interval in seconds
        """
        self.service_name = service_name
        self.exporters = exporters or [ConsoleSpanExporter()]
        self.sample_rate = sample_rate
        self.max_spans_per_trace = max_spans_per_trace
        self.export_batch_size = export_batch_size
        self.export_interval = export_interval

        # Span buffer for batching
        self._span_buffer: List[Span] = []
        self._buffer_lock = threading.Lock()

        # Trace statistics
        self._trace_counts: Dict[str, int] = {}

        # Background export thread
        self._running = False
        self._export_thread: Optional[threading.Thread] = None

        logger.info(f"TracingManager initialized: service={service_name}, sample_rate={sample_rate}")

    def start(self) -> None:
        """Start the background export thread."""
        self._running = True
        self._export_thread = threading.Thread(target=self._export_loop, daemon=True)
        self._export_thread.start()
        logger.info("Tracing export thread started")

    def stop(self) -> None:
        """Stop the tracing manager and flush remaining spans."""
        self._running = False
        if self._export_thread:
            self._export_thread.join(timeout=5.0)
        self._flush()
        logger.info("TracingManager stopped")

    def _export_loop(self) -> None:
        """Background thread for periodic span export."""
        while self._running:
            time.sleep(self.export_interval)
            self._flush()

    def _flush(self) -> None:
        """Export buffered spans."""
        with self._buffer_lock:
            if not self._span_buffer:
                return
            spans_to_export = self._span_buffer[:self.export_batch_size]
            self._span_buffer = self._span_buffer[self.export_batch_size:]

        for exporter in self.exporters:
            try:
                exporter.export(spans_to_export)
            except Exception as e:
                logger.error(f"Span export failed: {e}")

    def _should_sample(self, context: SpanContext) -> bool:
        """Determine if trace should be sampled."""
        if self.sample_rate >= 1.0:
            return True
        if self.sample_rate <= 0.0:
            return False
        # Use trace_id hash for consistent sampling
        hash_value = int(context.trace_id[:8], 16)
        return (hash_value / 0xFFFFFFFF) < self.sample_rate

    @property
    def current_span(self) -> Optional[Span]:
        """Get the current active span."""
        return getattr(self._local, 'current_span', None)

    @current_span.setter
    def current_span(self, span: Optional[Span]) -> None:
        """Set the current active span."""
        self._local.current_span = span

    def get_current_context(self) -> Optional[SpanContext]:
        """Get the current span context."""
        span = self.current_span
        return span.context if span else None

    @contextmanager
    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: Optional[Union[Span, SpanContext]] = None,
        attributes: Optional[Dict[str, Any]] = None,
        links: Optional[List[SpanLink]] = None,
        # Manufacturing extensions
        equipment_id: Optional[str] = None,
        operation_type: Optional[str] = None,
        job_id: Optional[str] = None
    ):
        """
        Start a new span as a context manager.

        Usage:
            >>> with tracer.start_span("operation") as span:
            ...     span.set_attribute("key", "value")
        """
        # Determine parent context
        if parent is None:
            parent_context = self.get_current_context()
        elif isinstance(parent, Span):
            parent_context = parent.context
        else:
            parent_context = parent

        # Create span context
        if parent_context:
            context = parent_context.child_context()
        else:
            context = SpanContext.generate()

        # Check sampling
        if not self._should_sample(context):
            # Return a no-op span
            yield None
            return

        # Create span
        span = Span(
            name=name,
            context=context,
            parent_context=parent_context,
            kind=kind,
            attributes=attributes or {},
            links=links or [],
            equipment_id=equipment_id,
            operation_type=operation_type,
            job_id=job_id
        )

        # Track span count per trace
        trace_id = context.trace_id
        self._trace_counts[trace_id] = self._trace_counts.get(trace_id, 0) + 1

        if self._trace_counts[trace_id] > self.max_spans_per_trace:
            logger.warning(f"Trace {trace_id[:8]} exceeded max spans")
            yield span
            return

        # Set as current span
        previous_span = self.current_span
        self.current_span = span

        try:
            yield span
            if span.status == SpanStatus.UNSET:
                span.set_status(SpanStatus.OK)
        except Exception as e:
            span.record_exception(e)
            raise
        finally:
            span.end()
            self.current_span = previous_span

            # Add to export buffer
            with self._buffer_lock:
                self._span_buffer.append(span)

    def start_span_from_headers(
        self,
        name: str,
        headers: Dict[str, str],
        kind: SpanKind = SpanKind.SERVER
    ):
        """
        Start a span from incoming request headers.

        Extracts W3C trace context from headers.
        """
        traceparent = headers.get("traceparent") or headers.get("Traceparent")
        parent_context = None

        if traceparent:
            parent_context = SpanContext.from_traceparent(traceparent)

        return self.start_span(name, kind=kind, parent=parent_context)

    def inject_headers(self, headers: Dict[str, str]) -> None:
        """
        Inject trace context into outgoing request headers.

        Adds W3C traceparent header.
        """
        context = self.get_current_context()
        if context:
            headers["traceparent"] = context.to_traceparent()

    def create_manufacturing_span(
        self,
        operation: str,
        equipment_id: str,
        job_id: Optional[str] = None,
        **attributes
    ):
        """
        Create a span with manufacturing semantic conventions.

        Args:
            operation: Operation name (e.g., "print", "mill", "inspect")
            equipment_id: Equipment identifier
            job_id: Optional job identifier
            **attributes: Additional attributes
        """
        attrs = {
            "manufacturing.equipment.id": equipment_id,
            "manufacturing.operation": operation,
            **attributes
        }
        if job_id:
            attrs["manufacturing.job.id"] = job_id

        return self.start_span(
            f"manufacturing.{operation}",
            kind=SpanKind.INTERNAL,
            attributes=attrs,
            equipment_id=equipment_id,
            operation_type=operation,
            job_id=job_id
        )


def trace_operation(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None
) -> Callable[[F], F]:
    """
    Decorator for tracing function calls.

    Usage:
        >>> @trace_operation("process_job")
        ... def process_job(job_id: str):
        ...     # Do work
        ...     pass
    """
    def decorator(func: F) -> F:
        span_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get tracer from context or create default
            tracer = getattr(wrapper, '_tracer', None)
            if tracer is None:
                tracer = TracingManager()
                wrapper._tracer = tracer

            attrs = {
                "code.function": func.__name__,
                "code.namespace": func.__module__,
                **(attributes or {})
            }

            with tracer.start_span(span_name, kind=kind, attributes=attrs) as span:
                if span:
                    # Add function arguments as attributes
                    for i, arg in enumerate(args):
                        span.set_attribute(f"arg.{i}", str(arg)[:100])
                    for key, value in kwargs.items():
                        span.set_attribute(f"kwarg.{key}", str(value)[:100])

                return func(*args, **kwargs)

        return wrapper
    return decorator


# Global tracer instance
_global_tracer: Optional[TracingManager] = None


def get_tracer() -> TracingManager:
    """Get the global tracer instance."""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = TracingManager()
    return _global_tracer


def set_tracer(tracer: TracingManager) -> None:
    """Set the global tracer instance."""
    global _global_tracer
    _global_tracer = tracer
