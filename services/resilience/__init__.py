"""
LEGO Factory v3 - Resilience Services
======================================
Circuit breaker patterns and fault tolerance utilities.
"""

from services.resilience.circuit_breaker import (
    CircuitBreakerFactory,
    CircuitBreakerMetrics,
    CircuitBreakerListener,
    get_circuit_breaker,
    get_all_circuit_states,
    redis_breaker,
    mqtt_breaker,
    database_breaker,
    external_api_breaker,
    ros2_breaker,
    with_fallback,
)

__all__ = [
    'CircuitBreakerFactory',
    'CircuitBreakerMetrics',
    'CircuitBreakerListener',
    'get_circuit_breaker',
    'get_all_circuit_states',
    'redis_breaker',
    'mqtt_breaker',
    'database_breaker',
    'external_api_breaker',
    'ros2_breaker',
    'with_fallback',
]
