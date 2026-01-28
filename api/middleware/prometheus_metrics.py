"""
Prometheus Metrics Middleware.

Provides comprehensive metrics collection for monitoring:
- Request latency histograms
- Request counters by endpoint/method/status
- Active connections gauge
- Error rate tracking
- Custom business metrics
"""

import time
import logging
from functools import wraps
from typing import Callable, Optional
from flask import Flask, request, g, Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    multiprocess,
    REGISTRY
)

logger = logging.getLogger(__name__)

# Create a custom registry for our metrics
try:
    # Try to use multiprocess mode for gunicorn workers
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
except Exception:
    # Fall back to default registry for single process
    registry = REGISTRY


# Request metrics
REQUEST_COUNT = Counter(
    'lego_factory_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code'],
    registry=registry
)

REQUEST_LATENCY = Histogram(
    'lego_factory_http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
    registry=registry
)

REQUESTS_IN_PROGRESS = Gauge(
    'lego_factory_http_requests_in_progress',
    'Number of HTTP requests currently in progress',
    ['method', 'endpoint'],
    registry=registry
)

REQUEST_SIZE = Histogram(
    'lego_factory_http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint'],
    buckets=(100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000),
    registry=registry
)

RESPONSE_SIZE = Histogram(
    'lego_factory_http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint'],
    buckets=(100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000),
    registry=registry
)

# Error metrics
ERROR_COUNT = Counter(
    'lego_factory_errors_total',
    'Total errors by type',
    ['error_type', 'endpoint'],
    registry=registry
)

# Business metrics - SCADA
SCADA_TAG_WRITES = Counter(
    'lego_factory_scada_tag_writes_total',
    'Total SCADA tag writes',
    ['tag_id'],
    registry=registry
)

SCADA_TAG_VALUE = Gauge(
    'lego_factory_scada_tag_value',
    'Current SCADA tag value',
    ['tag_id', 'tag_name'],
    registry=registry
)

HISTORIAN_BUFFER_SIZE = Gauge(
    'lego_factory_historian_buffer_size',
    'Current historian buffer size',
    registry=registry
)

HISTORIAN_COMPRESSION_RATIO = Gauge(
    'lego_factory_historian_compression_ratio',
    'Current historian compression ratio',
    registry=registry
)

# Business metrics - Alarms
ACTIVE_ALARMS = Gauge(
    'lego_factory_active_alarms',
    'Number of active alarms',
    ['priority'],
    registry=registry
)

ALARM_EVENTS = Counter(
    'lego_factory_alarm_events_total',
    'Total alarm events',
    ['event_type', 'priority'],
    registry=registry
)

# Business metrics - ML
ML_INFERENCE_COUNT = Counter(
    'lego_factory_ml_inference_total',
    'Total ML inferences',
    ['model_name'],
    registry=registry
)

ML_INFERENCE_LATENCY = Histogram(
    'lego_factory_ml_inference_duration_seconds',
    'ML inference latency in seconds',
    ['model_name'],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=registry
)

ML_ANOMALY_SCORE = Gauge(
    'lego_factory_ml_anomaly_score',
    'Latest ML anomaly score',
    ['tag_id'],
    registry=registry
)

ANOMALY_DETECTIONS = Counter(
    'lego_factory_anomaly_detections_total',
    'Total anomaly detections',
    ['severity'],
    registry=registry
)

# Business metrics - QMS
OPEN_NCRS = Gauge(
    'lego_factory_open_ncrs',
    'Number of open NCRs',
    ['severity'],
    registry=registry
)

NCR_EVENTS = Counter(
    'lego_factory_ncr_events_total',
    'Total NCR events',
    ['event_type'],
    registry=registry
)

OPEN_CAPAS = Gauge(
    'lego_factory_open_capas',
    'Number of open CAPAs',
    ['capa_type'],
    registry=registry
)

# Business metrics - Production
WORK_ORDERS_ACTIVE = Gauge(
    'lego_factory_work_orders_active',
    'Number of active work orders',
    registry=registry
)

WORK_ORDER_COMPLETION_TIME = Histogram(
    'lego_factory_work_order_completion_seconds',
    'Work order completion time in seconds',
    buckets=(60, 300, 600, 1800, 3600, 7200, 14400, 28800),
    registry=registry
)

PARTS_PRODUCED = Counter(
    'lego_factory_parts_produced_total',
    'Total parts produced',
    ['product_type'],
    registry=registry
)

# Business metrics - ROS2/Robotics
ROBOT_CONNECTIONS = Gauge(
    'lego_factory_robot_connections',
    'Number of connected robots',
    registry=registry
)

ROBOT_COMMANDS = Counter(
    'lego_factory_robot_commands_total',
    'Total robot commands',
    ['robot_id', 'command_type'],
    registry=registry
)

ROBOT_ERRORS = Counter(
    'lego_factory_robot_errors_total',
    'Total robot errors',
    ['robot_id', 'error_type'],
    registry=registry
)

# Application info
APP_INFO = Info(
    'lego_factory_app',
    'Application information',
    registry=registry
)


def init_metrics(app: Flask) -> None:
    """
    Initialize Prometheus metrics for a Flask app.

    Args:
        app: Flask application instance
    """
    # Set application info
    APP_INFO.info({
        'version': app.config.get('VERSION', '3.0.0'),
        'environment': app.config.get('FLASK_ENV', 'production'),
        'python_version': '3.11'
    })

    # Register before/after request handlers
    @app.before_request
    def before_request():
        """Record request start time and increment in-progress counter."""
        g.start_time = time.time()
        endpoint = _get_endpoint()
        REQUESTS_IN_PROGRESS.labels(method=request.method, endpoint=endpoint).inc()

    @app.after_request
    def after_request(response):
        """Record metrics after request completes."""
        endpoint = _get_endpoint()

        # Calculate latency
        latency = time.time() - getattr(g, 'start_time', time.time())

        # Record metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status_code=response.status_code
        ).inc()

        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=endpoint
        ).observe(latency)

        REQUESTS_IN_PROGRESS.labels(
            method=request.method,
            endpoint=endpoint
        ).dec()

        # Record request/response sizes
        request_size = request.content_length or 0
        REQUEST_SIZE.labels(method=request.method, endpoint=endpoint).observe(request_size)

        response_size = response.content_length or len(response.get_data())
        RESPONSE_SIZE.labels(method=request.method, endpoint=endpoint).observe(response_size)

        # Track errors
        if response.status_code >= 400:
            error_type = 'client_error' if response.status_code < 500 else 'server_error'
            ERROR_COUNT.labels(error_type=error_type, endpoint=endpoint).inc()

        return response

    # Add metrics endpoint
    @app.route('/metrics')
    def metrics():
        """Expose Prometheus metrics."""
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

    logger.info("Prometheus metrics initialized")


def _get_endpoint() -> str:
    """Get normalized endpoint name for metrics."""
    if request.endpoint:
        return request.endpoint

    # Fall back to URL rule or path
    if request.url_rule:
        return request.url_rule.rule

    # Normalize path to prevent high cardinality
    path = request.path
    # Replace UUIDs
    path = _normalize_path_segment(path, r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', ':uuid')
    # Replace numeric IDs
    path = _normalize_path_segment(path, r'/\d+', '/:id')

    return path


def _normalize_path_segment(path: str, pattern: str, replacement: str) -> str:
    """Normalize path segments to prevent high cardinality."""
    import re
    return re.sub(pattern, replacement, path)


# Decorator for tracking specific function metrics
def track_latency(metric_name: str, labels: dict = None) -> Callable:
    """
    Decorator to track function execution latency.

    Args:
        metric_name: Name prefix for the metric
        labels: Optional labels for the metric

    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        # Create a histogram for this function if it doesn't exist
        histogram = Histogram(
            f'{metric_name}_duration_seconds',
            f'Duration of {f.__name__} in seconds',
            list((labels or {}).keys()),
            registry=registry
        )

        @wraps(f)
        def wrapper(*args, **kwargs):
            label_values = labels or {}
            with histogram.labels(**label_values).time():
                return f(*args, **kwargs)

        return wrapper
    return decorator


def record_scada_tag(tag_id: str, tag_name: str, value: float) -> None:
    """Record SCADA tag value metric."""
    SCADA_TAG_VALUE.labels(tag_id=tag_id, tag_name=tag_name).set(value)
    SCADA_TAG_WRITES.labels(tag_id=tag_id).inc()


def record_historian_stats(buffer_size: int, compression_ratio: float) -> None:
    """Record historian statistics."""
    HISTORIAN_BUFFER_SIZE.set(buffer_size)
    HISTORIAN_COMPRESSION_RATIO.set(compression_ratio)


def record_alarm_event(event_type: str, priority: int) -> None:
    """Record alarm event."""
    ALARM_EVENTS.labels(event_type=event_type, priority=str(priority)).inc()


def update_active_alarms(priority: int, count: int) -> None:
    """Update active alarms gauge."""
    ACTIVE_ALARMS.labels(priority=str(priority)).set(count)


def record_ml_inference(model_name: str, latency: float, anomaly_score: float = None, tag_id: str = None) -> None:
    """Record ML inference metrics."""
    ML_INFERENCE_COUNT.labels(model_name=model_name).inc()
    ML_INFERENCE_LATENCY.labels(model_name=model_name).observe(latency)

    if anomaly_score is not None and tag_id:
        ML_ANOMALY_SCORE.labels(tag_id=tag_id).set(anomaly_score)


def record_anomaly_detection(severity: str) -> None:
    """Record anomaly detection event."""
    ANOMALY_DETECTIONS.labels(severity=severity).inc()


def record_ncr_event(event_type: str) -> None:
    """Record NCR event."""
    NCR_EVENTS.labels(event_type=event_type).inc()


def update_open_ncrs(severity: str, count: int) -> None:
    """Update open NCRs gauge."""
    OPEN_NCRS.labels(severity=severity).set(count)


def update_open_capas(capa_type: str, count: int) -> None:
    """Update open CAPAs gauge."""
    OPEN_CAPAS.labels(capa_type=capa_type).set(count)


def record_robot_command(robot_id: str, command_type: str) -> None:
    """Record robot command."""
    ROBOT_COMMANDS.labels(robot_id=robot_id, command_type=command_type).inc()


def record_robot_error(robot_id: str, error_type: str) -> None:
    """Record robot error."""
    ROBOT_ERRORS.labels(robot_id=robot_id, error_type=error_type).inc()


def update_robot_connections(count: int) -> None:
    """Update robot connections gauge."""
    ROBOT_CONNECTIONS.set(count)


def record_part_produced(product_type: str, count: int = 1) -> None:
    """Record parts produced."""
    PARTS_PRODUCED.labels(product_type=product_type).inc(count)


def update_active_work_orders(count: int) -> None:
    """Update active work orders gauge."""
    WORK_ORDERS_ACTIVE.set(count)


def record_work_order_completion(duration_seconds: float) -> None:
    """Record work order completion time."""
    WORK_ORDER_COMPLETION_TIME.observe(duration_seconds)
