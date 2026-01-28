"""
LEGO Factory v3 - API Middleware
================================
Middleware components for the Flask API.
"""

from api.middleware.rate_limiter import (
    limiter,
    get_limiter,
    init_limiter,
    standard_limit,
    auth_limit,
    heavy_computation_limit,
    admin_limit,
    exempt_from_rate_limit,
    is_internal_request,
    RATE_LIMIT_STANDARD,
    RATE_LIMIT_AUTH,
    RATE_LIMIT_HEAVY,
    RATE_LIMIT_ADMIN,
)

from api.middleware.request_logging import (
    RequestLoggingMiddleware,
    init_request_logging,
    log_request,
    EXCLUDED_PATHS,
    BODY_EXCLUDED_PATHS,
)

from api.middleware.validation import (
    ValidationError,
    RequestValidator,
    validate_json,
    validate_query_params,
    validate_path_params,
    require_content_type,
    limit_request_size,
    SCHEMAS,
)

from api.middleware.prometheus_metrics import (
    init_metrics,
    track_latency,
    record_scada_tag,
    record_historian_stats,
    record_alarm_event,
    update_active_alarms,
    record_ml_inference,
    record_anomaly_detection,
    record_ncr_event,
    update_open_ncrs,
    update_open_capas,
    record_robot_command,
    record_robot_error,
    update_robot_connections,
    record_part_produced,
    update_active_work_orders,
    record_work_order_completion,
)

__all__ = [
    # Rate limiter exports
    'limiter',
    'get_limiter',
    'init_limiter',
    'standard_limit',
    'auth_limit',
    'heavy_computation_limit',
    'admin_limit',
    'exempt_from_rate_limit',
    'is_internal_request',
    'RATE_LIMIT_STANDARD',
    'RATE_LIMIT_AUTH',
    'RATE_LIMIT_HEAVY',
    'RATE_LIMIT_ADMIN',
    # Request logging exports
    'RequestLoggingMiddleware',
    'init_request_logging',
    'log_request',
    'EXCLUDED_PATHS',
    'BODY_EXCLUDED_PATHS',
    # Validation exports
    'ValidationError',
    'RequestValidator',
    'validate_json',
    'validate_query_params',
    'validate_path_params',
    'require_content_type',
    'limit_request_size',
    'SCHEMAS',
    # Prometheus metrics exports
    'init_metrics',
    'track_latency',
    'record_scada_tag',
    'record_historian_stats',
    'record_alarm_event',
    'update_active_alarms',
    'record_ml_inference',
    'record_anomaly_detection',
    'record_ncr_event',
    'update_open_ncrs',
    'update_open_capas',
    'record_robot_command',
    'record_robot_error',
    'update_robot_connections',
    'record_part_produced',
    'update_active_work_orders',
    'record_work_order_completion',
]
