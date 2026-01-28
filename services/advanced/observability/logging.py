"""
Structured Logging with Correlation IDs

Implements structured JSON logging with automatic
trace correlation for distributed systems.

Reference: OpenTelemetry Logging, ECS Logging
"""

import logging
import sys
import json
import time
import threading
import traceback
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Union, TextIO
from datetime import datetime, timezone
from enum import Enum
from contextlib import contextmanager
import uuid
import os


class LogLevel(Enum):
    """Standard log levels."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class LogContext:
    """
    Context information for structured logging.

    Provides correlation IDs and contextual metadata.
    """
    # Correlation identifiers
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None

    # Service context
    service_name: str = "lego-mcp"
    service_version: str = "2.0.0"
    environment: str = "development"

    # Manufacturing context
    equipment_id: Optional[str] = None
    job_id: Optional[str] = None
    operation: Optional[str] = None

    # User context
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    # Additional context
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {}
        for key, value in asdict(self).items():
            if value is not None and key != "extra":
                result[key] = value
        result.update(self.extra)
        return result

    def with_trace(self, trace_id: str, span_id: str) -> "LogContext":
        """Create new context with trace information."""
        return LogContext(
            trace_id=trace_id,
            span_id=span_id,
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            service_name=self.service_name,
            service_version=self.service_version,
            environment=self.environment,
            equipment_id=self.equipment_id,
            job_id=self.job_id,
            operation=self.operation,
            user_id=self.user_id,
            session_id=self.session_id,
            extra=self.extra.copy()
        )

    def with_equipment(self, equipment_id: str, job_id: Optional[str] = None) -> "LogContext":
        """Create new context with equipment information."""
        return LogContext(
            trace_id=self.trace_id,
            span_id=self.span_id,
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            service_name=self.service_name,
            service_version=self.service_version,
            environment=self.environment,
            equipment_id=equipment_id,
            job_id=job_id or self.job_id,
            operation=self.operation,
            user_id=self.user_id,
            session_id=self.session_id,
            extra=self.extra.copy()
        )


@dataclass
class LogRecord:
    """Structured log record following ECS conventions."""
    # Core fields
    timestamp: str
    level: str
    message: str

    # Logger info
    logger_name: str
    module: Optional[str] = None
    function: Optional[str] = None
    line: Optional[int] = None

    # Correlation
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None

    # Service
    service_name: Optional[str] = None
    service_version: Optional[str] = None
    environment: Optional[str] = None

    # Manufacturing
    equipment_id: Optional[str] = None
    job_id: Optional[str] = None
    operation: Optional[str] = None

    # Error info
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_stack: Optional[str] = None

    # Labels and extra data
    labels: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Convert to JSON string."""
        data = {k: v for k, v in asdict(self).items() if v is not None}
        # Flatten empty dicts
        if not data.get("labels"):
            data.pop("labels", None)
        if not data.get("extra"):
            data.pop("extra", None)
        return json.dumps(data, default=str, ensure_ascii=False)

    def to_ecs(self) -> Dict[str, Any]:
        """
        Convert to Elastic Common Schema format.

        Reference: https://www.elastic.co/guide/en/ecs/current/
        """
        ecs = {
            "@timestamp": self.timestamp,
            "log": {
                "level": self.level,
                "logger": self.logger_name
            },
            "message": self.message
        }

        # Service
        if self.service_name:
            ecs["service"] = {
                "name": self.service_name,
                "version": self.service_version,
                "environment": self.environment
            }

        # Trace
        if self.trace_id:
            ecs["trace"] = {"id": self.trace_id}
        if self.span_id:
            ecs.setdefault("span", {})["id"] = self.span_id

        # Error
        if self.error_type:
            ecs["error"] = {
                "type": self.error_type,
                "message": self.error_message,
                "stack_trace": self.error_stack
            }

        # Labels
        if self.labels:
            ecs["labels"] = self.labels

        # Manufacturing (custom)
        if self.equipment_id or self.job_id or self.operation:
            ecs["manufacturing"] = {
                "equipment_id": self.equipment_id,
                "job_id": self.job_id,
                "operation": self.operation
            }

        return ecs


class JsonFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Outputs logs in JSON format compatible with log aggregators.
    """

    def __init__(
        self,
        context: Optional[LogContext] = None,
        include_stack: bool = True,
        ecs_format: bool = False
    ):
        super().__init__()
        self.context = context or LogContext()
        self.include_stack = include_stack
        self.ecs_format = ecs_format

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Get current context from thread-local storage
        ctx = getattr(record, 'log_context', None) or self.context

        # Build structured record
        log_record = LogRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=record.levelname,
            message=record.getMessage(),
            logger_name=record.name,
            module=record.module,
            function=record.funcName,
            line=record.lineno,
            trace_id=ctx.trace_id,
            span_id=ctx.span_id,
            request_id=ctx.request_id,
            correlation_id=ctx.correlation_id,
            service_name=ctx.service_name,
            service_version=ctx.service_version,
            environment=ctx.environment,
            equipment_id=ctx.equipment_id,
            job_id=ctx.job_id,
            operation=ctx.operation
        )

        # Handle exceptions
        if record.exc_info and self.include_stack:
            exc_type, exc_value, exc_tb = record.exc_info
            if exc_type:
                log_record.error_type = exc_type.__name__
                log_record.error_message = str(exc_value)
                log_record.error_stack = "".join(
                    traceback.format_exception(exc_type, exc_value, exc_tb)
                )

        # Add extra fields from record
        extra = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'pathname', 'process', 'processName', 'relativeCreated',
                'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                'message', 'log_context', 'asctime'
            }:
                extra[key] = value
        log_record.extra = extra

        if self.ecs_format:
            return json.dumps(log_record.to_ecs(), default=str)
        return log_record.to_json()


class StructuredLogger:
    """
    Structured logger with context propagation.

    Features:
    - Automatic correlation ID injection
    - Trace context propagation
    - Manufacturing-specific fields
    - JSON output for log aggregation

    Usage:
        >>> logger = StructuredLogger("my_service")
        >>> with logger.context(equipment_id="PRINTER-001"):
        ...     logger.info("Starting print job", job_id="JOB-001")
    """

    # Thread-local context stack
    _local = threading.local()

    def __init__(
        self,
        name: str,
        level: int = logging.INFO,
        handler: Optional[logging.Handler] = None,
        context: Optional[LogContext] = None
    ):
        """
        Initialize structured logger.

        Args:
            name: Logger name
            level: Log level
            handler: Optional custom handler
            context: Base context
        """
        self.name = name
        self.base_context = context or LogContext()

        # Create underlying logger
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)

        # Remove existing handlers
        self._logger.handlers = []

        # Add handler
        if handler is None:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JsonFormatter(self.base_context))
        self._logger.addHandler(handler)

    @property
    def _context_stack(self) -> List[LogContext]:
        """Get thread-local context stack."""
        if not hasattr(self._local, 'context_stack'):
            self._local.context_stack = []
        return self._local.context_stack

    @property
    def current_context(self) -> LogContext:
        """Get current effective context."""
        if self._context_stack:
            return self._context_stack[-1]
        return self.base_context

    @contextmanager
    def context(self, **kwargs):
        """
        Create a context scope with additional fields.

        Usage:
            >>> with logger.context(equipment_id="PRINTER-001"):
            ...     logger.info("Processing")
        """
        # Build new context
        ctx = LogContext(
            trace_id=kwargs.get('trace_id', self.current_context.trace_id),
            span_id=kwargs.get('span_id', self.current_context.span_id),
            request_id=kwargs.get('request_id', self.current_context.request_id),
            correlation_id=kwargs.get('correlation_id', self.current_context.correlation_id),
            service_name=kwargs.get('service_name', self.current_context.service_name),
            service_version=kwargs.get('service_version', self.current_context.service_version),
            environment=kwargs.get('environment', self.current_context.environment),
            equipment_id=kwargs.get('equipment_id', self.current_context.equipment_id),
            job_id=kwargs.get('job_id', self.current_context.job_id),
            operation=kwargs.get('operation', self.current_context.operation),
            user_id=kwargs.get('user_id', self.current_context.user_id),
            session_id=kwargs.get('session_id', self.current_context.session_id),
            extra={**self.current_context.extra, **kwargs.get('extra', {})}
        )

        self._context_stack.append(ctx)
        try:
            yield ctx
        finally:
            self._context_stack.pop()

    def _log(
        self,
        level: int,
        message: str,
        exc_info: Optional[BaseException] = None,
        **kwargs
    ) -> None:
        """Internal log method."""
        # Create log record with context
        ctx = self.current_context

        # Update context with any kwargs
        extra_ctx = {k: v for k, v in kwargs.items()}
        if extra_ctx:
            ctx = LogContext(
                trace_id=extra_ctx.pop('trace_id', ctx.trace_id),
                span_id=extra_ctx.pop('span_id', ctx.span_id),
                request_id=extra_ctx.pop('request_id', ctx.request_id),
                correlation_id=extra_ctx.pop('correlation_id', ctx.correlation_id),
                service_name=ctx.service_name,
                service_version=ctx.service_version,
                environment=ctx.environment,
                equipment_id=extra_ctx.pop('equipment_id', ctx.equipment_id),
                job_id=extra_ctx.pop('job_id', ctx.job_id),
                operation=extra_ctx.pop('operation', ctx.operation),
                user_id=ctx.user_id,
                session_id=ctx.session_id,
                extra={**ctx.extra, **extra_ctx}
            )

        # Log with context
        self._logger.log(
            level,
            message,
            exc_info=exc_info,
            extra={'log_context': ctx, **extra_ctx}
        )

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: Optional[BaseException] = None, **kwargs) -> None:
        """Log error message."""
        self._log(logging.ERROR, message, exc_info=exc_info, **kwargs)

    def critical(self, message: str, exc_info: Optional[BaseException] = None, **kwargs) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, message, exc_info=exc_info, **kwargs)

    def exception(self, message: str, **kwargs) -> None:
        """Log exception with stack trace."""
        self._log(logging.ERROR, message, exc_info=sys.exc_info(), **kwargs)

    # Manufacturing-specific logging methods
    def equipment_event(
        self,
        event: str,
        equipment_id: str,
        state: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log equipment event."""
        self.info(
            f"Equipment event: {event}",
            equipment_id=equipment_id,
            event_type="equipment",
            equipment_state=state,
            **kwargs
        )

    def job_event(
        self,
        event: str,
        job_id: str,
        equipment_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log job event."""
        self.info(
            f"Job event: {event}",
            job_id=job_id,
            equipment_id=equipment_id,
            event_type="job",
            **kwargs
        )

    def quality_event(
        self,
        measurement: str,
        value: float,
        equipment_id: str,
        passed: bool,
        **kwargs
    ) -> None:
        """Log quality measurement event."""
        level = logging.INFO if passed else logging.WARNING
        self._log(
            level,
            f"Quality measurement: {measurement}={value} {'PASS' if passed else 'FAIL'}",
            equipment_id=equipment_id,
            event_type="quality",
            measurement_type=measurement,
            measurement_value=value,
            quality_passed=passed,
            **kwargs
        )

    def production_event(
        self,
        event: str,
        equipment_id: str,
        parts_count: int,
        **kwargs
    ) -> None:
        """Log production event."""
        self.info(
            f"Production event: {event}",
            equipment_id=equipment_id,
            event_type="production",
            parts_count=parts_count,
            **kwargs
        )


class LogAggregator:
    """
    Aggregates logs for bulk shipping to log backends.

    Supports buffering and batch export to various destinations.
    """

    def __init__(
        self,
        buffer_size: int = 1000,
        flush_interval: float = 5.0,
        exporters: Optional[List] = None
    ):
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.exporters = exporters or []

        self._buffer: List[LogRecord] = []
        self._lock = threading.Lock()
        self._running = False
        self._flush_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the aggregator."""
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

    def stop(self) -> None:
        """Stop the aggregator and flush remaining logs."""
        self._running = False
        if self._flush_thread:
            self._flush_thread.join(timeout=5.0)
        self._flush()

    def add(self, record: LogRecord) -> None:
        """Add a log record to the buffer."""
        with self._lock:
            self._buffer.append(record)
            if len(self._buffer) >= self.buffer_size:
                self._flush_internal()

    def _flush_loop(self) -> None:
        """Background flush loop."""
        while self._running:
            time.sleep(self.flush_interval)
            self._flush()

    def _flush(self) -> None:
        """Flush the buffer."""
        with self._lock:
            self._flush_internal()

    def _flush_internal(self) -> None:
        """Internal flush (must hold lock)."""
        if not self._buffer:
            return

        records = self._buffer[:]
        self._buffer = []

        for exporter in self.exporters:
            try:
                exporter.export(records)
            except Exception as e:
                print(f"Log export failed: {e}", file=sys.stderr)


def configure_logging(
    service_name: str = "lego-mcp",
    level: int = logging.INFO,
    json_format: bool = True,
    ecs_format: bool = False,
    output: TextIO = sys.stdout
) -> StructuredLogger:
    """
    Configure structured logging for the application.

    Args:
        service_name: Name of the service
        level: Log level
        json_format: Use JSON format
        ecs_format: Use Elastic Common Schema format
        output: Output stream

    Returns:
        Configured StructuredLogger
    """
    context = LogContext(
        service_name=service_name,
        environment=os.environ.get("ENVIRONMENT", "development")
    )

    handler = logging.StreamHandler(output)

    if json_format:
        handler.setFormatter(JsonFormatter(context, ecs_format=ecs_format))
    else:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

    return StructuredLogger(
        name=service_name,
        level=level,
        handler=handler,
        context=context
    )


# Global logger instance
_global_logger: Optional[StructuredLogger] = None


def get_logger(name: Optional[str] = None) -> StructuredLogger:
    """Get a structured logger instance."""
    global _global_logger
    if name:
        return StructuredLogger(name)
    if _global_logger is None:
        _global_logger = configure_logging()
    return _global_logger
