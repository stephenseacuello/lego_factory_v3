"""
Error Recovery Service.

Provides comprehensive error detection, handling, and recovery procedures
for the LEGO Factory manufacturing execution system.
"""

import logging
import asyncio
import time
import functools
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, List, Type
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = 1       # Informational, can continue
    MEDIUM = 2    # Warning, degraded operation
    HIGH = 3      # Error, functionality impaired
    CRITICAL = 4  # System failure, immediate action required


class RecoveryStrategy(Enum):
    """Recovery strategy types."""
    RETRY = "retry"                    # Retry the operation
    FALLBACK = "fallback"              # Use fallback behavior
    CIRCUIT_BREAKER = "circuit_breaker"  # Stop attempts temporarily
    GRACEFUL_DEGRADATION = "graceful_degradation"  # Reduce functionality
    MANUAL_INTERVENTION = "manual_intervention"  # Require human action


@dataclass
class ErrorEvent:
    """Represents an error event."""
    error_id: str
    timestamp: datetime
    source: str
    error_type: str
    message: str
    severity: ErrorSeverity
    exception: Optional[Exception] = None
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_succeeded: bool = False
    recovery_strategy: Optional[RecoveryStrategy] = None


@dataclass
class CircuitBreakerState:
    """State for circuit breaker pattern."""
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "closed"  # closed, open, half-open
    reset_timeout: float = 60.0  # seconds
    failure_threshold: int = 5


class ErrorRecoveryService:
    """
    Centralized error recovery service.

    Provides:
    - Error tracking and logging
    - Automatic retry with exponential backoff
    - Circuit breaker pattern
    - Fallback mechanisms
    - Recovery procedure orchestration
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._error_history: List[ErrorEvent] = []
        self._max_history_size = 10000
        self._circuit_breakers: Dict[str, CircuitBreakerState] = defaultdict(CircuitBreakerState)
        self._recovery_handlers: Dict[str, Callable] = {}
        self._fallback_handlers: Dict[str, Callable] = {}
        self._lock = threading.Lock()

        # Metrics
        self._error_counts = defaultdict(int)
        self._recovery_success_counts = defaultdict(int)
        self._recovery_failure_counts = defaultdict(int)

        logger.info("Error Recovery Service initialized")

    def record_error(
        self,
        source: str,
        error_type: str,
        message: str,
        severity: ErrorSeverity,
        exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorEvent:
        """
        Record an error event.

        Args:
            source: Component that generated the error
            error_type: Type/category of error
            message: Human-readable error message
            severity: Severity level
            exception: Original exception if any
            context: Additional context data

        Returns:
            ErrorEvent record
        """
        error_id = f"{source}_{int(time.time() * 1000)}"

        event = ErrorEvent(
            error_id=error_id,
            timestamp=datetime.utcnow(),
            source=source,
            error_type=error_type,
            message=message,
            severity=severity,
            exception=exception,
            context=context or {}
        )

        with self._lock:
            self._error_history.append(event)
            self._error_counts[f"{source}:{error_type}"] += 1

            # Trim history if needed
            if len(self._error_history) > self._max_history_size:
                self._error_history = self._error_history[-self._max_history_size:]

        # Log based on severity
        log_method = {
            ErrorSeverity.LOW: logger.info,
            ErrorSeverity.MEDIUM: logger.warning,
            ErrorSeverity.HIGH: logger.error,
            ErrorSeverity.CRITICAL: logger.critical
        }.get(severity, logger.error)

        log_method(f"[{source}] {error_type}: {message}", exc_info=exception is not None)

        return event

    def register_recovery_handler(
        self,
        error_type: str,
        handler: Callable[[ErrorEvent], bool]
    ) -> None:
        """
        Register a recovery handler for an error type.

        Args:
            error_type: Error type to handle
            handler: Function that attempts recovery, returns True on success
        """
        self._recovery_handlers[error_type] = handler
        logger.info(f"Registered recovery handler for: {error_type}")

    def register_fallback(
        self,
        operation: str,
        fallback: Callable[..., Any]
    ) -> None:
        """
        Register a fallback function for an operation.

        Args:
            operation: Operation name
            fallback: Fallback function to call
        """
        self._fallback_handlers[operation] = fallback
        logger.info(f"Registered fallback for: {operation}")

    def attempt_recovery(self, event: ErrorEvent) -> bool:
        """
        Attempt to recover from an error.

        Args:
            event: Error event to recover from

        Returns:
            True if recovery succeeded
        """
        handler = self._recovery_handlers.get(event.error_type)

        if not handler:
            logger.warning(f"No recovery handler for: {event.error_type}")
            return False

        try:
            event.recovery_attempted = True
            result = handler(event)
            event.recovery_succeeded = result

            if result:
                self._recovery_success_counts[event.error_type] += 1
                logger.info(f"Recovery succeeded for: {event.error_type}")
            else:
                self._recovery_failure_counts[event.error_type] += 1
                logger.warning(f"Recovery failed for: {event.error_type}")

            return result

        except Exception as e:
            logger.error(f"Recovery handler raised exception: {e}")
            self._recovery_failure_counts[event.error_type] += 1
            return False

    def check_circuit_breaker(self, service_name: str) -> bool:
        """
        Check if circuit breaker allows operation.

        Args:
            service_name: Name of the service to check

        Returns:
            True if operation is allowed
        """
        state = self._circuit_breakers[service_name]

        if state.state == "closed":
            return True

        elif state.state == "open":
            # Check if timeout has elapsed
            if state.last_failure_time:
                elapsed = (datetime.utcnow() - state.last_failure_time).total_seconds()
                if elapsed >= state.reset_timeout:
                    state.state = "half-open"
                    logger.info(f"Circuit breaker half-open for: {service_name}")
                    return True
            return False

        elif state.state == "half-open":
            # Allow one request through
            return True

        return False

    def record_circuit_breaker_failure(self, service_name: str) -> None:
        """Record a failure for circuit breaker."""
        state = self._circuit_breakers[service_name]
        state.failure_count += 1
        state.last_failure_time = datetime.utcnow()

        if state.state == "half-open":
            # Back to open on failure during half-open
            state.state = "open"
            logger.warning(f"Circuit breaker reopened for: {service_name}")

        elif state.failure_count >= state.failure_threshold:
            state.state = "open"
            logger.warning(f"Circuit breaker opened for: {service_name}")

    def record_circuit_breaker_success(self, service_name: str) -> None:
        """Record a success for circuit breaker."""
        state = self._circuit_breakers[service_name]

        if state.state == "half-open":
            # Reset on success during half-open
            state.state = "closed"
            state.failure_count = 0
            logger.info(f"Circuit breaker closed for: {service_name}")

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        with self._lock:
            recent_errors = [
                e for e in self._error_history
                if e.timestamp > datetime.utcnow() - timedelta(hours=1)
            ]

            return {
                "total_errors": len(self._error_history),
                "errors_last_hour": len(recent_errors),
                "by_severity": {
                    sev.name: len([e for e in recent_errors if e.severity == sev])
                    for sev in ErrorSeverity
                },
                "error_counts": dict(self._error_counts),
                "recovery_success": dict(self._recovery_success_counts),
                "recovery_failure": dict(self._recovery_failure_counts),
                "circuit_breakers": {
                    name: {"state": state.state, "failures": state.failure_count}
                    for name, state in self._circuit_breakers.items()
                }
            }

    def get_recent_errors(
        self,
        source: Optional[str] = None,
        severity: Optional[ErrorSeverity] = None,
        limit: int = 100
    ) -> List[ErrorEvent]:
        """Get recent error events."""
        with self._lock:
            errors = self._error_history[-limit:]

            if source:
                errors = [e for e in errors if e.source == source]

            if severity:
                errors = [e for e in errors if e.severity == severity]

            return errors


# Singleton instance
error_recovery_service = ErrorRecoveryService()


def with_retry(
    max_retries: int = 3,
    backoff_base: float = 1.0,
    backoff_max: float = 60.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None
) -> Callable:
    """
    Decorator for automatic retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_base: Base delay between retries (seconds)
        backoff_max: Maximum delay between retries
        exceptions: Exception types to catch and retry
        on_retry: Callback function on each retry

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        delay = min(backoff_base * (2 ** attempt), backoff_max)
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after {delay:.1f}s: {e}"
                        )

                        if on_retry:
                            on_retry(attempt, e)

                        time.sleep(delay)
                    else:
                        error_recovery_service.record_error(
                            source=func.__module__,
                            error_type="retry_exhausted",
                            message=f"All {max_retries} retries failed for {func.__name__}",
                            severity=ErrorSeverity.HIGH,
                            exception=e
                        )

            raise last_exception

        return wrapper

    return decorator


def with_circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    reset_timeout: float = 60.0,
    fallback: Optional[Callable] = None
) -> Callable:
    """
    Decorator for circuit breaker pattern.

    Args:
        service_name: Name of the service for circuit breaker state
        failure_threshold: Number of failures before opening circuit
        reset_timeout: Seconds before attempting reset
        fallback: Optional fallback function

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        # Initialize circuit breaker state
        state = error_recovery_service._circuit_breakers[service_name]
        state.failure_threshold = failure_threshold
        state.reset_timeout = reset_timeout

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not error_recovery_service.check_circuit_breaker(service_name):
                logger.warning(f"Circuit breaker open for: {service_name}")

                if fallback:
                    return fallback(*args, **kwargs)
                raise CircuitBreakerOpenError(f"Circuit breaker open for: {service_name}")

            try:
                result = func(*args, **kwargs)
                error_recovery_service.record_circuit_breaker_success(service_name)
                return result

            except Exception as e:
                error_recovery_service.record_circuit_breaker_failure(service_name)
                raise

        return wrapper

    return decorator


def with_fallback(fallback_func: Callable) -> Callable:
    """
    Decorator to provide fallback on error.

    Args:
        fallback_func: Function to call on error

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Using fallback for {func.__name__}: {e}")
                return fallback_func(*args, **kwargs)

        return wrapper

    return decorator


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# Pre-defined recovery handlers
def _database_connection_recovery(event: ErrorEvent) -> bool:
    """Recovery handler for database connection errors."""
    logger.info("Attempting database connection recovery...")

    try:
        # Import here to avoid circular imports
        from database.engine import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")

        logger.info("Database connection recovered")
        return True

    except Exception as e:
        logger.error(f"Database recovery failed: {e}")
        return False


def _redis_connection_recovery(event: ErrorEvent) -> bool:
    """Recovery handler for Redis connection errors."""
    logger.info("Attempting Redis connection recovery...")

    try:
        import redis
        import os

        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD"),
            socket_timeout=5
        )
        client.ping()

        logger.info("Redis connection recovered")
        return True

    except Exception as e:
        logger.error(f"Redis recovery failed: {e}")
        return False


def _ros2_bridge_recovery(event: ErrorEvent) -> bool:
    """Recovery handler for ROS2 bridge errors."""
    logger.info("Attempting ROS2 bridge recovery...")

    try:
        from services.robotics.ros2_bridge import get_ros2_bridge

        bridge = get_ros2_bridge()
        bridge.disconnect()
        time.sleep(1)
        result = bridge.connect()

        if result:
            logger.info("ROS2 bridge recovered")
        return result

    except Exception as e:
        logger.error(f"ROS2 bridge recovery failed: {e}")
        return False


# Register default recovery handlers
error_recovery_service.register_recovery_handler(
    "database_connection_error",
    _database_connection_recovery
)
error_recovery_service.register_recovery_handler(
    "redis_connection_error",
    _redis_connection_recovery
)
error_recovery_service.register_recovery_handler(
    "ros2_bridge_error",
    _ros2_bridge_recovery
)
