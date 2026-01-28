"""
Error Recovery and Retry Logic

Provides robust error handling with automatic retries, circuit breakers,
and graceful degradation for the LEGO MCP system.
"""

import asyncio
import functools
import logging
import time
import traceback
from typing import Dict, Any, Optional, Callable, List, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# ENUMS
# ============================================================================


class RetryStrategy(Enum):
    """Retry strategies for failed operations."""

    IMMEDIATE = "immediate"  # Retry immediately
    LINEAR = "linear"  # Fixed delay between retries
    EXPONENTIAL = "exponential"  # Exponential backoff
    FIBONACCI = "fibonacci"  # Fibonacci backoff


class CircuitState(Enum):
    """States for circuit breaker pattern."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


# ============================================================================
# ERROR TYPES
# ============================================================================


class LegoMCPError(Exception):
    """Base error for LEGO MCP operations."""

    def __init__(self, message: str, code: str = "UNKNOWN", recoverable: bool = True):
        self.message = message
        self.code = code
        self.recoverable = recoverable
        super().__init__(message)


class FusionConnectionError(LegoMCPError):
    """Error connecting to Fusion 360."""

    def __init__(self, message: str = "Cannot connect to Fusion 360"):
        super().__init__(message, "FUSION_CONNECTION", True)


class FusionTimeoutError(LegoMCPError):
    """Fusion 360 operation timed out."""

    def __init__(self, message: str = "Fusion 360 operation timed out"):
        super().__init__(message, "FUSION_TIMEOUT", True)


class SlicerConnectionError(LegoMCPError):
    """Error connecting to slicer service."""

    def __init__(self, message: str = "Cannot connect to slicer service"):
        super().__init__(message, "SLICER_CONNECTION", True)


class ValidationError(LegoMCPError):
    """Invalid parameters provided."""

    def __init__(self, message: str, field: str = None):
        super().__init__(message, "VALIDATION", False)
        self.field = field


class ResourceNotFoundError(LegoMCPError):
    """Requested resource not found."""

    def __init__(self, resource_type: str, resource_id: str):
        message = f"{resource_type} not found: {resource_id}"
        super().__init__(message, "NOT_FOUND", False)
        self.resource_type = resource_type
        self.resource_id = resource_id


class OperationFailedError(LegoMCPError):
    """An operation failed after all retries."""

    def __init__(self, operation: str, attempts: int, last_error: str):
        message = f"Operation '{operation}' failed after {attempts} attempts: {last_error}"
        super().__init__(message, "OPERATION_FAILED", False)
        self.operation = operation
        self.attempts = attempts
        self.last_error = last_error


# ============================================================================
# RETRY DECORATOR
# ============================================================================


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay: float = 1.0  # seconds
    max_delay: float = 30.0  # seconds
    jitter: float = 0.1  # random jitter factor

    # Exceptions to retry
    retry_exceptions: tuple = (
        FusionConnectionError,
        FusionTimeoutError,
        SlicerConnectionError,
        asyncio.TimeoutError,
        ConnectionError,
    )

    # Exceptions to NOT retry
    no_retry_exceptions: tuple = (
        ValidationError,
        ResourceNotFoundError,
    )


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay before next retry attempt."""
    import random

    if config.strategy == RetryStrategy.IMMEDIATE:
        base = 0
    elif config.strategy == RetryStrategy.LINEAR:
        base = config.base_delay
    elif config.strategy == RetryStrategy.EXPONENTIAL:
        base = config.base_delay * (2 ** (attempt - 1))
    elif config.strategy == RetryStrategy.FIBONACCI:
        fib = [1, 1]
        for i in range(attempt - 1):
            fib = [fib[1], fib[0] + fib[1]]
        base = config.base_delay * fib[0]
    else:
        base = config.base_delay

    # Apply max delay cap
    delay = min(base, config.max_delay)

    # Add jitter
    jitter = delay * config.jitter * random.random()

    return delay + jitter


def retry(config: RetryConfig = None):
    """
    Decorator for automatic retry with configurable strategy.

    Usage:
        @retry(RetryConfig(max_attempts=5, strategy=RetryStrategy.EXPONENTIAL))
        async def my_function():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except config.no_retry_exceptions as e:
                    # Don't retry these
                    raise

                except config.retry_exceptions as e:
                    last_exception = e

                    if attempt < config.max_attempts:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"Attempt {attempt}/{config.max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for {func.__name__}: {e}"
                        )

                except Exception as e:
                    # Unexpected exception - log and re-raise
                    logger.error(f"Unexpected error in {func.__name__}: {e}")
                    raise

            # All retries exhausted
            raise OperationFailedError(func.__name__, config.max_attempts, str(last_exception))

        return wrapper

    return decorator


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes before closing
    timeout: float = 30.0  # Seconds in open state before testing
    half_open_max_calls: int = 3  # Max calls in half-open state


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by stopping calls to a failing service
    and allowing it time to recover.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0

        # History for monitoring
        self._call_history: deque = deque(maxlen=100)

    def can_execute(self) -> bool:
        """Check if we can execute a call."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if time.time() - self.last_failure_time >= self.config.timeout:
                self._transition_to_half_open()
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.config.half_open_max_calls

        return False

    def record_success(self):
        """Record a successful call."""
        self._call_history.append(("success", time.time()))

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        else:
            self.failure_count = 0

    def record_failure(self, error: Exception = None):
        """Record a failed call."""
        self._call_history.append(("failure", time.time(), str(error)))
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        else:
            self.failure_count += 1
            if self.failure_count >= self.config.failure_threshold:
                self._transition_to_open()

    def _transition_to_open(self):
        """Transition to open state."""
        logger.warning(f"Circuit breaker '{self.name}' OPENED after {self.failure_count} failures")
        self.state = CircuitState.OPEN
        self.success_count = 0
        self.half_open_calls = 0

    def _transition_to_half_open(self):
        """Transition to half-open state."""
        logger.info(f"Circuit breaker '{self.name}' testing (half-open)")
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.success_count = 0

    def _transition_to_closed(self):
        """Transition to closed state."""
        logger.info(f"Circuit breaker '{self.name}' CLOSED - service recovered")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time,
        }

    def reset(self):
        """Manually reset the circuit breaker."""
        self._transition_to_closed()


def circuit_breaker(breaker: CircuitBreaker):
    """
    Decorator to apply circuit breaker to a function.

    Usage:
        fusion_breaker = CircuitBreaker("fusion360")

        @circuit_breaker(fusion_breaker)
        async def call_fusion():
            ...
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not breaker.can_execute():
                raise LegoMCPError(
                    f"Circuit breaker '{breaker.name}' is open", "CIRCUIT_OPEN", recoverable=True
                )

            if breaker.state == CircuitState.HALF_OPEN:
                breaker.half_open_calls += 1

            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure(e)
                raise

        return wrapper

    return decorator


# ============================================================================
# ERROR HANDLER
# ============================================================================


class ErrorHandler:
    """
    Central error handler for the LEGO MCP system.

    Provides consistent error handling, logging, and recovery suggestions.
    """

    def __init__(self):
        self.error_log: deque = deque(maxlen=1000)
        self._recovery_suggestions: Dict[str, List[str]] = {
            "FUSION_CONNECTION": [
                "Check if Fusion 360 is running",
                "Verify the LEGO MCP add-in is installed and enabled",
                "Check the API URL configuration",
                "Restart Fusion 360",
            ],
            "FUSION_TIMEOUT": [
                "The operation is taking too long",
                "Try with simpler geometry",
                "Check Fusion 360 for pending dialogs",
                "Increase the timeout setting",
            ],
            "SLICER_CONNECTION": [
                "Check if the slicer service is running",
                "Run: docker-compose up slicer-service",
                "Verify the slicer API URL",
            ],
            "VALIDATION": [
                "Check the input parameters",
                "Refer to the documentation for valid ranges",
            ],
            "NOT_FOUND": [
                "Verify the resource name/ID",
                "Check if the resource was created successfully",
            ],
        }

    def handle(self, error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle an error and return a structured response.

        Args:
            error: The exception that occurred
            context: Additional context about the operation

        Returns:
            Structured error response
        """
        error_info = {
            "timestamp": time.time(),
            "error_type": type(error).__name__,
            "message": str(error),
            "context": context or {},
            "recoverable": True,
            "suggestions": [],
            "traceback": None,
        }

        # Extract code and suggestions for LegoMCPError
        if isinstance(error, LegoMCPError):
            error_info["code"] = error.code
            error_info["recoverable"] = error.recoverable
            error_info["suggestions"] = self._recovery_suggestions.get(error.code, [])
        else:
            error_info["code"] = "UNKNOWN"
            error_info["traceback"] = traceback.format_exc()

        # Log the error
        self.error_log.append(error_info)
        logger.error(f"Error handled: {error_info['code']} - {error_info['message']}")

        return {
            "success": False,
            "error": {
                "code": error_info["code"],
                "message": error_info["message"],
                "recoverable": error_info["recoverable"],
                "suggestions": error_info["suggestions"],
            },
        }

    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent errors."""
        return list(self.error_log)[-limit:]

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        if not self.error_log:
            return {"total": 0}

        by_code = {}
        by_type = {}

        for err in self.error_log:
            code = err.get("code", "UNKNOWN")
            by_code[code] = by_code.get(code, 0) + 1

            err_type = err.get("error_type", "Unknown")
            by_type[err_type] = by_type.get(err_type, 0) + 1

        return {
            "total": len(self.error_log),
            "by_code": by_code,
            "by_type": by_type,
            "recoverable_rate": sum(1 for e in self.error_log if e.get("recoverable", False))
            / len(self.error_log),
        }


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

# Circuit breakers for external services
fusion_circuit = CircuitBreaker(
    "fusion360", CircuitBreakerConfig(failure_threshold=3, success_threshold=2, timeout=60.0)
)

slicer_circuit = CircuitBreaker(
    "slicer", CircuitBreakerConfig(failure_threshold=3, success_threshold=2, timeout=30.0)
)

# Global error handler
error_handler = ErrorHandler()


# ============================================================================
# RECOVERY FUNCTIONS
# ============================================================================


async def attempt_fusion_recovery() -> bool:
    """Attempt to recover Fusion 360 connection."""
    logger.info("Attempting Fusion 360 recovery...")

    # Reset circuit breaker
    fusion_circuit.reset()

    # Try to reconnect
    # (In real implementation, this would ping the Fusion API)
    await asyncio.sleep(1)

    return True


async def attempt_slicer_recovery() -> bool:
    """Attempt to recover slicer connection."""
    logger.info("Attempting slicer service recovery...")

    slicer_circuit.reset()
    await asyncio.sleep(1)

    return True


# ============================================================================
# UTILITY DECORATORS
# ============================================================================


def with_error_handling(func: Callable):
    """
    Decorator to add standardized error handling.

    Catches exceptions and returns structured error responses.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            return error_handler.handle(
                e, {"function": func.__name__, "args": str(args)[:100], "kwargs": str(kwargs)[:100]}
            )

    return wrapper


def with_timeout(timeout_seconds: float):
    """
    Decorator to add timeout to async functions.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                raise FusionTimeoutError(
                    f"Operation '{func.__name__}' timed out after {timeout_seconds}s"
                )

        return wrapper

    return decorator


# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================

RECOVERY_TOOLS = {
    "get_system_status": {
        "description": "Get status of all system components including circuit breakers.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "reset_circuit_breaker": {
        "description": "Reset a circuit breaker to allow retrying a failed service.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "enum": ["fusion360", "slicer"],
                    "description": "Service to reset",
                }
            },
            "required": ["service"],
        },
    },
    "get_error_stats": {
        "description": "Get statistics about recent errors.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "attempt_recovery": {
        "description": "Attempt to recover a failed service.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "enum": ["fusion360", "slicer"],
                    "description": "Service to recover",
                }
            },
            "required": ["service"],
        },
    },
}


def get_system_status() -> Dict[str, Any]:
    """Get comprehensive system status."""
    return {
        "circuits": {
            "fusion360": fusion_circuit.get_status(),
            "slicer": slicer_circuit.get_status(),
        },
        "errors": error_handler.get_error_stats(),
    }


async def reset_circuit(service: str) -> Dict[str, Any]:
    """Reset a circuit breaker."""
    if service == "fusion360":
        fusion_circuit.reset()
        return {"success": True, "service": "fusion360", "state": "closed"}
    elif service == "slicer":
        slicer_circuit.reset()
        return {"success": True, "service": "slicer", "state": "closed"}
    else:
        return {"success": False, "error": f"Unknown service: {service}"}
