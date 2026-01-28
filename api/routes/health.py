"""
LEGO Factory v3 - Health Check Routes
======================================
Health monitoring endpoints including circuit breaker status.
"""

from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
import logging

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__, url_prefix='/api/health')


@health_bp.route('/')
def health_check():
    """
    Basic health check endpoint.

    Returns:
        JSON with overall system health status
    """
    from services.resilience.circuit_breaker import get_all_circuit_states

    circuit_states = get_all_circuit_states()

    # Determine overall health based on circuit states
    open_circuits = [
        name for name, state in circuit_states.items()
        if state.get('state') == 'open'
    ]

    status = 'healthy'
    if len(open_circuits) > 0:
        status = 'degraded'
    if len(open_circuits) > 2:
        status = 'unhealthy'

    return jsonify({
        'status': status,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '3.0.0',
        'open_circuits': open_circuits,
    })


@health_bp.route('/circuits')
def circuit_breaker_status():
    """
    Get status of all circuit breakers.

    Returns detailed information about each circuit breaker:
    - Current state (closed, open, half-open)
    - Failure count
    - Success count
    - Last failure/success timestamps
    - Reset timeout and when circuit will reset (if open)

    Response Example:
        {
            "circuits": {
                "redis": {
                    "state": "closed",
                    "failures": 0,
                    "successes": 150,
                    "total_calls": 150,
                    "fail_max": 5,
                    "reset_timeout_seconds": 30
                },
                "mqtt": {
                    "state": "open",
                    "failures": 5,
                    "successes": 45,
                    "total_calls": 50,
                    "fail_max": 3,
                    "reset_timeout_seconds": 60,
                    "last_failure": "2024-01-20T12:00:00Z",
                    "reset_at": "2024-01-20T12:05:00Z"
                },
                "database": {
                    "state": "half-open",
                    "failures": 3,
                    "successes": 200,
                    "total_calls": 203,
                    "fail_max": 5,
                    "reset_timeout_seconds": 30,
                    "last_state_change": "2024-01-20T12:04:30Z"
                }
            },
            "summary": {
                "total": 5,
                "closed": 3,
                "open": 1,
                "half_open": 1
            },
            "timestamp": "2024-01-20T12:04:35Z"
        }
    """
    from services.resilience.circuit_breaker import get_all_circuit_states

    circuit_states = get_all_circuit_states()

    # Calculate summary
    summary = {
        'total': len(circuit_states),
        'closed': 0,
        'open': 0,
        'half_open': 0,
    }

    for name, state in circuit_states.items():
        circuit_state = state.get('state', 'closed')
        if circuit_state == 'closed':
            summary['closed'] += 1
        elif circuit_state == 'open':
            summary['open'] += 1
        elif circuit_state == 'half-open':
            summary['half_open'] += 1

    return jsonify({
        'circuits': circuit_states,
        'summary': summary,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })


@health_bp.route('/circuits/<circuit_name>')
def circuit_breaker_detail(circuit_name: str):
    """
    Get detailed status of a specific circuit breaker.

    Args:
        circuit_name: Name of the circuit breaker (redis, mqtt, database, external_api, ros2)

    Returns:
        Detailed circuit breaker information
    """
    from services.resilience.circuit_breaker import get_circuit_metrics

    metrics = get_circuit_metrics(circuit_name)

    if metrics is None:
        return jsonify({
            'error': f"Circuit breaker '{circuit_name}' not found",
            'available_circuits': ['redis', 'mqtt', 'database', 'external_api', 'ros2'],
        }), 404

    return jsonify({
        'circuit': metrics,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })


@health_bp.route('/circuits/<circuit_name>/reset', methods=['POST'])
def reset_circuit_breaker(circuit_name: str):
    """
    Manually reset a circuit breaker to closed state.

    This is an administrative action that should be used with caution.
    The circuit will immediately start accepting requests again.

    Args:
        circuit_name: Name of the circuit breaker to reset

    Returns:
        Success status and new circuit state
    """
    from services.resilience.circuit_breaker import reset_circuit, get_circuit_metrics

    success = reset_circuit(circuit_name)

    if not success:
        return jsonify({
            'error': f"Circuit breaker '{circuit_name}' not found or could not be reset",
            'available_circuits': ['redis', 'mqtt', 'database', 'external_api', 'ros2'],
        }), 404

    logger.info(f"Circuit breaker '{circuit_name}' manually reset by admin")

    metrics = get_circuit_metrics(circuit_name)

    return jsonify({
        'success': True,
        'message': f"Circuit breaker '{circuit_name}' has been reset",
        'circuit': metrics,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })


@health_bp.route('/circuits/reset-all', methods=['POST'])
def reset_all_circuit_breakers():
    """
    Reset all circuit breakers to closed state.

    This is an administrative action that should be used with extreme caution.
    All circuits will immediately start accepting requests again.

    Returns:
        Success status and count of reset circuits
    """
    from services.resilience.circuit_breaker import reset_all_circuits, get_all_circuit_states

    count = reset_all_circuits()

    logger.warning(f"All circuit breakers ({count}) manually reset by admin")

    return jsonify({
        'success': True,
        'message': f"Reset {count} circuit breakers",
        'circuits': get_all_circuit_states(),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })


@health_bp.route('/queues')
def retry_queue_status():
    """
    Get status of retry queues for services with circuit breakers.

    Returns information about queued messages waiting to be processed
    when services recover.
    """
    from services.resilience.circuit_breaker import mqtt_retry_queue, ros2_retry_queue

    return jsonify({
        'queues': {
            'mqtt': {
                'size': mqtt_retry_queue.size(),
                'description': 'Messages queued for MQTT broker',
            },
            'ros2': {
                'size': ros2_retry_queue.size(),
                'description': 'Commands queued for ROS2 bridge',
            },
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })


@health_bp.route('/cache')
def local_cache_status():
    """
    Get status of the local fallback cache.

    Returns information about cached items used when Redis is unavailable.
    """
    from services.resilience.circuit_breaker import local_cache

    return jsonify({
        'cache': {
            'size': local_cache.size(),
            'max_size': local_cache._max_size,
            'default_ttl_seconds': local_cache._default_ttl,
            'description': 'Local cache for Redis fallback',
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })


@health_bp.route('/dependencies')
def dependencies_status():
    """
    Check health of all external dependencies.

    Attempts to connect to each service and reports status.
    """
    from services.resilience.circuit_breaker import (
        is_circuit_open,
        get_circuit_metrics,
    )

    dependencies = {}

    # Redis
    redis_circuit = get_circuit_metrics('redis')
    dependencies['redis'] = {
        'status': 'unavailable' if is_circuit_open('redis') else 'available',
        'circuit_state': redis_circuit.get('state') if redis_circuit else 'unknown',
        'failures': redis_circuit.get('failures', 0) if redis_circuit else 0,
    }

    # MQTT
    mqtt_circuit = get_circuit_metrics('mqtt')
    dependencies['mqtt'] = {
        'status': 'unavailable' if is_circuit_open('mqtt') else 'available',
        'circuit_state': mqtt_circuit.get('state') if mqtt_circuit else 'unknown',
        'failures': mqtt_circuit.get('failures', 0) if mqtt_circuit else 0,
    }

    # Database
    db_circuit = get_circuit_metrics('database')
    dependencies['database'] = {
        'status': 'unavailable' if is_circuit_open('database') else 'available',
        'circuit_state': db_circuit.get('state') if db_circuit else 'unknown',
        'failures': db_circuit.get('failures', 0) if db_circuit else 0,
    }

    # External APIs
    api_circuit = get_circuit_metrics('external_api')
    dependencies['external_api'] = {
        'status': 'unavailable' if is_circuit_open('external_api') else 'available',
        'circuit_state': api_circuit.get('state') if api_circuit else 'unknown',
        'failures': api_circuit.get('failures', 0) if api_circuit else 0,
        'services': ['slicer_service', 'fusion360_api'],
    }

    # ROS2
    ros2_circuit = get_circuit_metrics('ros2')
    dependencies['ros2'] = {
        'status': 'unavailable' if is_circuit_open('ros2') else 'available',
        'circuit_state': ros2_circuit.get('state') if ros2_circuit else 'unknown',
        'failures': ros2_circuit.get('failures', 0) if ros2_circuit else 0,
    }

    # Calculate overall status
    unavailable_count = sum(
        1 for d in dependencies.values()
        if d.get('status') == 'unavailable'
    )

    if unavailable_count == 0:
        overall = 'all_healthy'
    elif unavailable_count <= 2:
        overall = 'partially_degraded'
    else:
        overall = 'severely_degraded'

    return jsonify({
        'overall': overall,
        'dependencies': dependencies,
        'unavailable_count': unavailable_count,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })
