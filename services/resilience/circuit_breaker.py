"""
LEGO Factory v3 - Circuit Breaker Implementation
=================================================
Production-ready circuit breaker pattern for external service calls.

Implements the circuit breaker pattern to prevent cascading failures
when external services (Redis, MQTT, Database, APIs) are unavailable.

Circuit States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, requests are blocked
- HALF-OPEN: Testing if service has recovered

Usage:
    from services.resilience import redis_breaker, with_fallback

    @redis_breaker
    def get_from_cache(key):
        return redis_client.get(key)

    # With fallback
    @with_fallback(default_value=None)
    @redis_breaker
    def get_cached_data(key):
        return redis_client.get(key)
"""

import functools
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from dataclasses import dataclass, field
from enum import Enum

from pybreaker import CircuitBreaker, CircuitBreakerListener as PyBreakerListener, CircuitBreakerError

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half-open'


@dataclass
class CircuitBreakerMetrics:
    """Metrics collected for a circuit breaker."""
    name: str
    state: CircuitState
    failure_count: int
    success_count: int
    total_calls: int
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_state_change: Optional[datetime] = None
    reset_timeout: int = 30
    fail_max: int = 5
    opened_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for API response."""
        result = {
            'name': self.name,
            'state': self.state.value,
            'failures': self.failure_count,
            'successes': self.success_count,
            'total_calls': self.total_calls,
            'fail_max': self.fail_max,
            'reset_timeout_seconds': self.reset_timeout,
        }

        if self.last_failure_time:
            result['last_failure'] = self.last_failure_time.isoformat()

        if self.last_success_time:
            result['last_success'] = self.last_success_time.isoformat()

        if self.last_state_change:
            result['last_state_change'] = self.last_state_change.isoformat()

        if self.state == CircuitState.OPEN and self.opened_at:
            from datetime import timedelta
            reset_at = self.opened_at + timedelta(seconds=self.reset_timeout)
            result['reset_at'] = reset_at.isoformat()

        return result


class CircuitBreakerListener(PyBreakerListener):
    """
    Custom listener for circuit breaker state changes.

    Provides logging, metrics collection, and optional callbacks
    when circuit state changes.
    """

    def __init__(
        self,
        name: str,
        on_open: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        on_half_open: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize the listener.

        Args:
            name: Circuit breaker name for logging
            on_open: Callback when circuit opens
            on_close: Callback when circuit closes
            on_half_open: Callback when circuit enters half-open state
        """
        self.name = name
        self.on_open_callback = on_open
        self.on_close_callback = on_close
        self.on_half_open_callback = on_half_open

        # Metrics tracking
        self._lock = threading.Lock()
        self._failure_count = 0
        self._success_count = 0
        self._total_calls = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        self._last_state_change: Optional[datetime] = None
        self._current_state = CircuitState.CLOSED
        self._opened_at: Optional[datetime] = None

    def state_change(self, cb: CircuitBreaker, old_state: str, new_state: str):
        """Called when circuit breaker state changes."""
        now = datetime.now(timezone.utc)

        with self._lock:
            self._last_state_change = now

            # Map pybreaker states to our enum
            state_map = {
                'closed': CircuitState.CLOSED,
                'open': CircuitState.OPEN,
                'half-open': CircuitState.HALF_OPEN,
            }
            self._current_state = state_map.get(new_state, CircuitState.CLOSED)

            if new_state == 'open':
                self._opened_at = now

        logger.warning(
            f"Circuit breaker '{self.name}' state changed: {old_state} -> {new_state}",
            extra={
                'circuit_name': self.name,
                'old_state': old_state,
                'new_state': new_state,
                'failure_count': cb.fail_counter,
            }
        )

        # Execute callbacks
        if new_state == 'open' and self.on_open_callback:
            try:
                self.on_open_callback()
            except Exception as e:
                logger.error(f"Circuit breaker on_open callback failed: {e}")

        elif new_state == 'closed' and self.on_close_callback:
            try:
                self.on_close_callback()
            except Exception as e:
                logger.error(f"Circuit breaker on_close callback failed: {e}")

        elif new_state == 'half-open' and self.on_half_open_callback:
            try:
                self.on_half_open_callback()
            except Exception as e:
                logger.error(f"Circuit breaker on_half_open callback failed: {e}")

    def before_call(self, cb: CircuitBreaker, func: Callable, *args, **kwargs):
        """Called before a protected function is executed."""
        with self._lock:
            self._total_calls += 1

    def success(self, cb: CircuitBreaker):
        """Called when a protected function succeeds."""
        with self._lock:
            self._success_count += 1
            self._last_success_time = datetime.now(timezone.utc)

    def failure(self, cb: CircuitBreaker, exc: Exception):
        """Called when a protected function fails."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)

        logger.warning(
            f"Circuit breaker '{self.name}' recorded failure: {exc}",
            extra={
                'circuit_name': self.name,
                'exception': str(exc),
                'failure_count': self._failure_count,
            }
        )

    def get_metrics(self, cb: CircuitBreaker) -> CircuitBreakerMetrics:
        """Get current metrics for this circuit breaker."""
        with self._lock:
            return CircuitBreakerMetrics(
                name=self.name,
                state=self._current_state,
                failure_count=self._failure_count,
                success_count=self._success_count,
                total_calls=self._total_calls,
                last_failure_time=self._last_failure_time,
                last_success_time=self._last_success_time,
                last_state_change=self._last_state_change,
                reset_timeout=cb.reset_timeout,
                fail_max=cb.fail_max,
                opened_at=self._opened_at,
            )


class CircuitBreakerFactory:
    """
    Factory for creating and managing circuit breakers.

    Provides centralized configuration and tracking of all
    circuit breakers in the application.
    """

    _instance: Optional['CircuitBreakerFactory'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'CircuitBreakerFactory':
        """Singleton pattern for factory."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the factory."""
        if self._initialized:
            return

        self._breakers: Dict[str, CircuitBreaker] = {}
        self._listeners: Dict[str, CircuitBreakerListener] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._initialized = True

        logger.info("CircuitBreakerFactory initialized")

    def create(
        self,
        name: str,
        fail_max: int = 5,
        reset_timeout: int = 30,
        exclude: Optional[List[type]] = None,
        on_open: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        on_half_open: Optional[Callable[[], None]] = None,
    ) -> CircuitBreaker:
        """
        Create or retrieve a circuit breaker.

        Args:
            name: Unique name for the circuit breaker
            fail_max: Number of failures before opening circuit
            reset_timeout: Seconds before attempting recovery
            exclude: Exception types to not count as failures
            on_open: Callback when circuit opens
            on_close: Callback when circuit closes
            on_half_open: Callback when circuit enters half-open state

        Returns:
            Configured CircuitBreaker instance
        """
        if name in self._breakers:
            return self._breakers[name]

        # Create listener
        listener = CircuitBreakerListener(
            name=name,
            on_open=on_open,
            on_close=on_close,
            on_half_open=on_half_open,
        )

        # Create circuit breaker
        breaker = CircuitBreaker(
            name=name,
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            exclude=exclude or [],
            listeners=[listener],
        )

        # Store references
        self._breakers[name] = breaker
        self._listeners[name] = listener
        self._configs[name] = {
            'fail_max': fail_max,
            'reset_timeout': reset_timeout,
            'exclude': [e.__name__ for e in (exclude or [])],
        }

        logger.info(
            f"Created circuit breaker '{name}' "
            f"(fail_max={fail_max}, reset_timeout={reset_timeout}s)"
        )

        return breaker

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name."""
        return self._breakers.get(name)

    def get_metrics(self, name: str) -> Optional[CircuitBreakerMetrics]:
        """Get metrics for a circuit breaker."""
        if name not in self._breakers or name not in self._listeners:
            return None
        return self._listeners[name].get_metrics(self._breakers[name])

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get state information for all circuit breakers."""
        states = {}
        for name in self._breakers:
            metrics = self.get_metrics(name)
            if metrics:
                states[name] = metrics.to_dict()
        return states

    def reset(self, name: str) -> bool:
        """
        Manually reset a circuit breaker to closed state.

        Args:
            name: Circuit breaker name

        Returns:
            True if reset was successful
        """
        breaker = self._breakers.get(name)
        if breaker:
            breaker.close()
            logger.info(f"Circuit breaker '{name}' manually reset")
            return True
        return False

    def reset_all(self) -> int:
        """Reset all circuit breakers. Returns count of reset breakers."""
        count = 0
        for name in self._breakers:
            if self.reset(name):
                count += 1
        return count


# Global factory instance
_factory = CircuitBreakerFactory()


def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get a circuit breaker by name."""
    return _factory.get(name)


def get_all_circuit_states() -> Dict[str, Dict[str, Any]]:
    """Get state information for all circuit breakers."""
    return _factory.get_all_states()


# ============================================================================
# Pre-configured Circuit Breakers
# ============================================================================

def _on_redis_open():
    """Callback when Redis circuit opens."""
    logger.error("Redis circuit breaker OPENED - falling back to local cache")


def _on_redis_close():
    """Callback when Redis circuit closes."""
    logger.info("Redis circuit breaker CLOSED - Redis connection restored")


def _on_mqtt_open():
    """Callback when MQTT circuit opens."""
    logger.error("MQTT circuit breaker OPENED - messages will be queued")


def _on_mqtt_close():
    """Callback when MQTT circuit closes."""
    logger.info("MQTT circuit breaker CLOSED - MQTT connection restored")


def _on_database_open():
    """Callback when Database circuit opens."""
    logger.error("Database circuit breaker OPENED - using cached data")


def _on_database_close():
    """Callback when Database circuit closes."""
    logger.info("Database circuit breaker CLOSED - database connection restored")


def _on_external_api_open():
    """Callback when External API circuit opens."""
    logger.error("External API circuit breaker OPENED - returning cached/default responses")


def _on_external_api_close():
    """Callback when External API circuit closes."""
    logger.info("External API circuit breaker CLOSED - external services available")


def _on_ros2_open():
    """Callback when ROS2 circuit opens."""
    logger.error("ROS2 circuit breaker OPENED - robot commands will be queued")


def _on_ros2_close():
    """Callback when ROS2 circuit closes."""
    logger.info("ROS2 circuit breaker CLOSED - ROS2 bridge restored")


# Redis Circuit Breaker
# - 5 failures before opening
# - 30 second reset timeout
# - Exclude KeyError (key not found is not a failure)
redis_breaker = _factory.create(
    name='redis',
    fail_max=5,
    reset_timeout=30,
    exclude=[KeyError],
    on_open=_on_redis_open,
    on_close=_on_redis_close,
)

# MQTT Circuit Breaker
# - 3 failures before opening (more sensitive for real-time messaging)
# - 60 second reset timeout (give broker time to recover)
mqtt_breaker = _factory.create(
    name='mqtt',
    fail_max=3,
    reset_timeout=60,
    exclude=[],
    on_open=_on_mqtt_open,
    on_close=_on_mqtt_close,
)

# Database Circuit Breaker
# - 5 failures before opening
# - 30 second reset timeout
# - Exclude integrity errors (data issues, not connection issues)
database_breaker = _factory.create(
    name='database',
    fail_max=5,
    reset_timeout=30,
    exclude=[],  # Will add specific exceptions in service layer
    on_open=_on_database_open,
    on_close=_on_database_close,
)

# External API Circuit Breaker (Fusion 360, Slicer Service)
# - 3 failures before opening
# - 45 second reset timeout
external_api_breaker = _factory.create(
    name='external_api',
    fail_max=3,
    reset_timeout=45,
    exclude=[],
    on_open=_on_external_api_open,
    on_close=_on_external_api_close,
)

# ROS2 Bridge Circuit Breaker
# - 3 failures before opening
# - 30 second reset timeout
ros2_breaker = _factory.create(
    name='ros2',
    fail_max=3,
    reset_timeout=30,
    exclude=[],
    on_open=_on_ros2_open,
    on_close=_on_ros2_close,
)


# ============================================================================
# Fallback Decorator
# ============================================================================

def with_fallback(
    default_value: Any = None,
    fallback_func: Optional[Callable[..., T]] = None,
    log_fallback: bool = True,
) -> Callable:
    """
    Decorator to provide fallback behavior when circuit breaker is open.

    Usage:
        @with_fallback(default_value=[])
        @redis_breaker
        def get_cached_items():
            return redis_client.lrange('items', 0, -1)

        # Or with a fallback function
        @with_fallback(fallback_func=get_items_from_db)
        @redis_breaker
        def get_cached_items():
            return redis_client.lrange('items', 0, -1)

    Args:
        default_value: Value to return when circuit is open
        fallback_func: Function to call when circuit is open
        log_fallback: Whether to log when fallback is used

    Returns:
        Decorated function with fallback behavior
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except CircuitBreakerError as e:
                if log_fallback:
                    logger.warning(
                        f"Circuit breaker open for {func.__name__}, using fallback",
                        extra={'function': func.__name__, 'error': str(e)}
                    )

                if fallback_func is not None:
                    return fallback_func(*args, **kwargs)
                return default_value
        return wrapper
    return decorator


# ============================================================================
# Async Support
# ============================================================================

def async_with_fallback(
    default_value: Any = None,
    fallback_func: Optional[Callable] = None,
    log_fallback: bool = True,
) -> Callable:
    """
    Async version of with_fallback decorator.

    Usage:
        @async_with_fallback(default_value=None)
        @redis_breaker
        async def get_cached_item(key):
            return await redis_client.get(key)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except CircuitBreakerError as e:
                if log_fallback:
                    logger.warning(
                        f"Circuit breaker open for {func.__name__}, using fallback",
                        extra={'function': func.__name__, 'error': str(e)}
                    )

                if fallback_func is not None:
                    if asyncio.iscoroutinefunction(fallback_func):
                        return await fallback_func(*args, **kwargs)
                    return fallback_func(*args, **kwargs)
                return default_value
        return wrapper
    return decorator


# ============================================================================
# Message Queue for Retry
# ============================================================================

@dataclass
class QueuedMessage:
    """Message queued for retry when circuit is open."""
    payload: Any
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attempts: int = 0
    max_attempts: int = 3


class RetryQueue:
    """
    Thread-safe queue for messages that need to be retried.

    Used when circuit breakers are open to store messages
    for later processing when the service recovers.
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize retry queue.

        Args:
            max_size: Maximum number of messages to queue
        """
        self._queue: List[QueuedMessage] = []
        self._lock = threading.Lock()
        self._max_size = max_size

    def enqueue(self, payload: Any, max_attempts: int = 3) -> bool:
        """
        Add a message to the retry queue.

        Args:
            payload: Message payload
            max_attempts: Maximum retry attempts

        Returns:
            True if message was queued, False if queue is full
        """
        with self._lock:
            if len(self._queue) >= self._max_size:
                logger.warning("Retry queue full, dropping oldest message")
                self._queue.pop(0)

            message = QueuedMessage(
                payload=payload,
                max_attempts=max_attempts,
            )
            self._queue.append(message)
            return True

    def dequeue(self) -> Optional[QueuedMessage]:
        """Remove and return the oldest message from the queue."""
        with self._lock:
            if self._queue:
                return self._queue.pop(0)
            return None

    def peek(self) -> Optional[QueuedMessage]:
        """Return the oldest message without removing it."""
        with self._lock:
            if self._queue:
                return self._queue[0]
            return None

    def size(self) -> int:
        """Return current queue size."""
        with self._lock:
            return len(self._queue)

    def clear(self) -> int:
        """Clear the queue and return number of removed messages."""
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count

    def get_all(self) -> List[QueuedMessage]:
        """Get all messages in the queue (for bulk retry)."""
        with self._lock:
            messages = self._queue.copy()
            self._queue.clear()
            return messages


# Global retry queues for different services
mqtt_retry_queue = RetryQueue(max_size=1000)
ros2_retry_queue = RetryQueue(max_size=500)


# ============================================================================
# Local Cache Fallback
# ============================================================================

class LocalCache:
    """
    Simple local cache for fallback when Redis is unavailable.

    Uses LRU eviction and TTL-based expiration.
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize local cache.

        Args:
            max_size: Maximum number of items
            default_ttl: Default time-to-live in seconds
        """
        self._cache: Dict[str, tuple] = {}  # key -> (value, expiry_time)
        self._lock = threading.Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._access_order: List[str] = []  # For LRU tracking

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        with self._lock:
            if key not in self._cache:
                return None

            value, expiry = self._cache[key]

            # Check expiration
            if expiry and datetime.now(timezone.utc) > expiry:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return None

            # Update access order (LRU)
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in cache."""
        with self._lock:
            # Evict if necessary
            while len(self._cache) >= self._max_size and self._access_order:
                oldest = self._access_order.pop(0)
                if oldest in self._cache:
                    del self._cache[oldest]

            ttl = ttl if ttl is not None else self._default_ttl
            expiry = datetime.now(timezone.utc) + timedelta(seconds=ttl) if ttl > 0 else None

            self._cache[key] = (value, expiry)

            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

    def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return True
            return False

    def clear(self) -> int:
        """Clear all cached values."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._access_order.clear()
            return count

    def size(self) -> int:
        """Return current cache size."""
        with self._lock:
            return len(self._cache)


# Global local cache for Redis fallback
from datetime import timedelta
local_cache = LocalCache(max_size=1000, default_ttl=300)


# ============================================================================
# Convenience Functions
# ============================================================================

def reset_circuit(name: str) -> bool:
    """Reset a specific circuit breaker."""
    return _factory.reset(name)


def reset_all_circuits() -> int:
    """Reset all circuit breakers."""
    return _factory.reset_all()


def get_circuit_metrics(name: str) -> Optional[Dict[str, Any]]:
    """Get metrics for a specific circuit breaker."""
    metrics = _factory.get_metrics(name)
    return metrics.to_dict() if metrics else None


def is_circuit_open(name: str) -> bool:
    """Check if a circuit breaker is open."""
    breaker = _factory.get(name)
    if breaker:
        return breaker.current_state == 'open'
    return False


def is_circuit_closed(name: str) -> bool:
    """Check if a circuit breaker is closed."""
    breaker = _factory.get(name)
    if breaker:
        return breaker.current_state == 'closed'
    return True  # Default to closed if breaker doesn't exist
