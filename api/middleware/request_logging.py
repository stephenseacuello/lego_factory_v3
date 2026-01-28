"""
LEGO Factory v3 - Request Logging Middleware
=============================================
Structured logging for HTTP requests and responses with correlation IDs.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Set

from flask import Flask, g, request, Response
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from config.logging_config import (
    clear_request_context,
    generate_request_id,
    get_structured_logger,
    redact_sensitive_data,
    set_request_context,
    SENSITIVE_FIELDS,
)

# Logger for this module
logger = get_structured_logger(__name__)

# Paths to exclude from request logging (health checks, static files, etc.)
EXCLUDED_PATHS: Set[str] = {
    '/health',
    '/healthz',
    '/ready',
    '/readiness',
    '/live',
    '/liveness',
    '/metrics',
    '/favicon.ico',
    '/static',
}

# Paths that should not have their bodies logged (even when redacted)
BODY_EXCLUDED_PATHS: Set[str] = {
    '/api/auth/login',
    '/api/auth/register',
    '/api/auth/password',
    '/api/auth/reset-password',
}

# Maximum body size to log (in bytes)
MAX_BODY_LOG_SIZE = 10000

# Methods that typically have request bodies
BODY_METHODS = {'POST', 'PUT', 'PATCH'}


def _should_log_path(path: str) -> bool:
    """Check if the path should be logged."""
    # Check for exact matches
    if path in EXCLUDED_PATHS:
        return False

    # Check for prefix matches
    for excluded in EXCLUDED_PATHS:
        if path.startswith(excluded):
            return False

    return True


def _should_log_body(path: str) -> bool:
    """Check if the request body should be logged for this path."""
    for excluded in BODY_EXCLUDED_PATHS:
        if path.startswith(excluded):
            return False
    return True


def _get_client_ip() -> str:
    """Get the client IP address, handling proxy headers."""
    # Check for forwarded headers (set by reverse proxies)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs; get the first one
        return forwarded_for.split(',')[0].strip()

    # Check for X-Real-IP (set by nginx)
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip

    # Fall back to remote_addr
    return request.remote_addr or 'unknown'


def _get_request_body() -> Optional[Dict[str, Any]]:
    """Get and redact the request body for logging."""
    if request.method not in BODY_METHODS:
        return None

    if not _should_log_body(request.path):
        return {'_redacted': 'Body logging disabled for this endpoint'}

    # Check content length
    content_length = request.content_length or 0
    if content_length > MAX_BODY_LOG_SIZE:
        return {'_truncated': True, 'size_bytes': content_length}

    try:
        # Try to get JSON body
        if request.is_json:
            body = request.get_json(silent=True)
            if body:
                return redact_sensitive_data(body)

        # Try to get form data
        if request.form:
            return redact_sensitive_data(dict(request.form))

        return None
    except Exception:
        return {'_error': 'Could not parse request body'}


def _get_user_id() -> Optional[str]:
    """Safely get the current user ID from JWT."""
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        return str(identity) if identity else None
    except Exception:
        return None


def _extract_request_info() -> Dict[str, Any]:
    """Extract relevant information from the current request."""
    return {
        'method': request.method,
        'path': request.path,
        'url': request.url,
        'query_string': request.query_string.decode('utf-8', errors='replace') if request.query_string else None,
        'ip': _get_client_ip(),
        'user_agent': request.headers.get('User-Agent'),
        'content_type': request.content_type,
        'content_length': request.content_length,
    }


class RequestLoggingMiddleware:
    """
    WSGI middleware for request/response logging.

    This middleware:
    - Generates and injects request IDs
    - Logs all incoming requests with relevant metadata
    - Logs response status and duration
    - Redacts sensitive data from request bodies
    - Adds correlation ID header to responses
    """

    def __init__(self, app: Flask):
        """
        Initialize the middleware.

        Args:
            app: The Flask application
        """
        self.app = app
        self.logger = get_structured_logger('api.middleware.request_logging')

    def init_app(self, app: Flask) -> None:
        """
        Initialize the middleware with a Flask application.

        Args:
            app: The Flask application
        """
        # Register before_request handler
        @app.before_request
        def before_request():
            """Handle pre-request logging and context setup."""
            # Skip logging for excluded paths
            if not _should_log_path(request.path):
                return

            # Generate or extract request ID
            request_id = (
                request.headers.get('X-Request-ID') or
                request.headers.get('X-Correlation-ID') or
                generate_request_id()
            )

            # Get user ID if authenticated
            user_id = _get_user_id()

            # Set up request context for structured logging
            set_request_context(
                request_id=request_id,
                user_id=user_id,
                path=request.path,
                method=request.method
            )

            # Store timing info
            g.request_start_time = time.perf_counter()
            g.request_id = request_id

            # Extract request info for logging
            request_info = _extract_request_info()

            # Log request body for POST/PUT/PATCH
            request_body = _get_request_body()
            if request_body:
                request_info['body'] = request_body

            # Log the incoming request
            self.logger.info(
                f"Request started: {request.method} {request.path}",
                extra={
                    'event': 'request_start',
                    'request_id': request_id,
                    'user_id': user_id,
                    **request_info,
                }
            )

        # Register after_request handler
        @app.after_request
        def after_request(response: Response) -> Response:
            """Handle post-request logging."""
            # Skip logging for excluded paths
            if not _should_log_path(request.path):
                return response

            # Calculate duration
            start_time = getattr(g, 'request_start_time', None)
            duration_ms = (
                (time.perf_counter() - start_time) * 1000
                if start_time else None
            )

            # Get request ID
            request_id = getattr(g, 'request_id', None)

            # Add request ID to response headers
            if request_id:
                response.headers['X-Request-ID'] = request_id

            # Determine log level based on status code
            status_code = response.status_code
            if status_code >= 500:
                log_level = logging.ERROR
            elif status_code >= 400:
                log_level = logging.WARNING
            else:
                log_level = logging.INFO

            # Build log entry
            log_extra = {
                'event': 'request_end',
                'request_id': request_id,
                'method': request.method,
                'path': request.path,
                'status': status_code,
                'duration_ms': round(duration_ms, 2) if duration_ms else None,
                'ip': _get_client_ip(),
                'response_size': response.content_length,
            }

            # Log the response
            self.logger.log(
                log_level,
                f"Request completed: {request.method} {request.path} -> {status_code} ({duration_ms:.2f}ms)" if duration_ms else f"Request completed: {request.method} {request.path} -> {status_code}",
                extra=log_extra,
            )

            return response

        # Register teardown handler to clean up context
        @app.teardown_request
        def teardown_request(exception=None):
            """Clean up request context."""
            if exception:
                request_id = getattr(g, 'request_id', None)
                self.logger.error(
                    f"Request failed with exception: {exception}",
                    extra={
                        'event': 'request_error',
                        'request_id': request_id,
                        'exception_type': type(exception).__name__,
                        'exception_message': str(exception),
                    }
                )
            clear_request_context()


def log_request(
    operation: Optional[str] = None,
    log_response: bool = False
) -> Callable:
    """
    Decorator for logging specific API endpoint calls with additional context.

    Args:
        operation: Name of the operation (defaults to function name)
        log_response: Whether to log the response data

    Example:
        @app.route('/api/items/<item_id>')
        @log_request(operation='get_item')
        def get_item(item_id):
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            op_name = operation or f.__name__
            start_time = time.perf_counter()

            # Create logger with operation context
            func_logger = get_structured_logger(
                f.__module__,
                operation=op_name,
            )

            # Log operation start
            func_logger.debug(
                f"Starting operation: {op_name}",
                extra={'event': 'operation_start', 'args': redact_sensitive_data(kwargs)}
            )

            try:
                result = f(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Log success
                extra = {
                    'event': 'operation_end',
                    'success': True,
                    'duration_ms': round(duration_ms, 2),
                }
                if log_response and result:
                    extra['response'] = redact_sensitive_data(result) if isinstance(result, dict) else str(result)[:200]

                func_logger.debug(
                    f"Completed operation: {op_name} in {duration_ms:.2f}ms",
                    extra=extra
                )

                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                func_logger.error(
                    f"Operation failed: {op_name} after {duration_ms:.2f}ms - {e}",
                    extra={
                        'event': 'operation_error',
                        'success': False,
                        'duration_ms': round(duration_ms, 2),
                        'exception_type': type(e).__name__,
                        'exception_message': str(e),
                    },
                    exc_info=True
                )
                raise

        return wrapper
    return decorator


def init_request_logging(app: Flask) -> RequestLoggingMiddleware:
    """
    Initialize request logging for a Flask application.

    Args:
        app: The Flask application

    Returns:
        The configured RequestLoggingMiddleware instance
    """
    middleware = RequestLoggingMiddleware(app)
    middleware.init_app(app)

    logger.info(
        "Request logging middleware initialized",
        extra={'event': 'middleware_initialized', 'middleware': 'request_logging'}
    )

    return middleware


# Re-export commonly used items
__all__ = [
    'RequestLoggingMiddleware',
    'init_request_logging',
    'log_request',
    'EXCLUDED_PATHS',
    'BODY_EXCLUDED_PATHS',
]
