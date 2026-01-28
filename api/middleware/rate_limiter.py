"""
LEGO Factory v3 - Rate Limiter Middleware
==========================================
HTTP rate limiting using Flask-Limiter with Redis backend for distributed limiting.

Rate Limits:
- Standard endpoints: 100 requests/minute
- Auth endpoints: 10 requests/minute (prevent brute force)
- Heavy computation (ML, reports): 10 requests/minute
- Admin endpoints: 50 requests/minute

Exemptions:
- Health check endpoints (/health, /ready, /live)
- Internal service-to-service calls (X-Internal-Service header)
"""

import logging
import os
from functools import wraps
from typing import Callable, Optional

from flask import Flask, request, g, jsonify

logger = logging.getLogger(__name__)

# Rate limit constants
RATE_LIMIT_STANDARD = "100 per minute"
RATE_LIMIT_AUTH = "10 per minute"
RATE_LIMIT_HEAVY = "10 per minute"
RATE_LIMIT_ADMIN = "50 per minute"

# Internal service header for service-to-service exemption
INTERNAL_SERVICE_HEADER = "X-Internal-Service"
INTERNAL_SERVICE_SECRET = os.getenv("INTERNAL_SERVICE_SECRET", "")

# Global limiter instance (initialized lazily)
_limiter = None


def get_remote_address() -> str:
    """
    Get the remote address for rate limiting.

    Handles X-Forwarded-For header for clients behind proxies/load balancers.
    Falls back to direct client IP if header is not present.
    """
    # Check for X-Forwarded-For header (common with reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()

    # Check for X-Real-IP header (nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct remote address
    return request.remote_addr or "127.0.0.1"


def is_internal_request() -> bool:
    """
    Check if the request is from an internal service.

    Internal requests are exempt from rate limiting to allow
    service-to-service communication without restrictions.

    Returns:
        True if request has valid internal service header, False otherwise.
    """
    if not INTERNAL_SERVICE_SECRET:
        # If no secret is configured, don't allow any exemptions
        return False

    header_value = request.headers.get(INTERNAL_SERVICE_HEADER, "")
    return header_value == INTERNAL_SERVICE_SECRET


def is_health_check_endpoint() -> bool:
    """
    Check if the current request is to a health check endpoint.

    Health check endpoints are exempt from rate limiting to ensure
    monitoring systems can always reach them.
    """
    health_endpoints = {"/health", "/ready", "/live", "/api/health", "/api/ready", "/api/live"}
    return request.path in health_endpoints


def get_key_func() -> str:
    """
    Custom key function for rate limiting.

    Returns different keys based on request type:
    - 'exempt' for internal/health check requests (bypasses limiting)
    - Client IP address for regular requests
    """
    if is_internal_request():
        return "exempt:internal"

    if is_health_check_endpoint():
        return "exempt:health"

    return get_remote_address()


def get_limiter():
    """Get the global limiter instance."""
    global _limiter
    return _limiter


def get_storage_uri() -> str:
    """
    Get the storage URI for rate limiting.

    Attempts to use Redis first for distributed rate limiting.
    Falls back to in-memory storage if Redis is not configured/available.
    """
    # Try Redis URL from environment
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return redis_url

    # Try to construct Redis URL from individual settings
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    redis_db = os.getenv("REDIS_RATE_LIMIT_DB", "1")  # Use separate DB for rate limiting
    redis_password = os.getenv("REDIS_PASSWORD")

    if redis_password:
        return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"

    return f"redis://{redis_host}:{redis_port}/{redis_db}"


def init_limiter(app: Flask) -> None:
    """
    Initialize the rate limiter with the Flask app.

    This function should be called during app initialization.
    It sets up Flask-Limiter with Redis backend (or memory fallback).

    Args:
        app: Flask application instance
    """
    global _limiter

    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address as default_get_remote_address
    except ImportError:
        logger.warning(
            "Flask-Limiter not installed. Rate limiting disabled. "
            "Install with: pip install Flask-Limiter"
        )
        return

    storage_uri = get_storage_uri()

    # Check if Redis is available
    redis_available = False
    if storage_uri.startswith("redis://"):
        try:
            import redis
            # Parse the URL and test connection
            redis_client = redis.from_url(storage_uri)
            redis_client.ping()
            redis_available = True
            logger.info(f"Rate limiter using Redis backend: {storage_uri.split('@')[-1] if '@' in storage_uri else storage_uri}")
        except Exception as e:
            logger.warning(f"Redis not available for rate limiting: {e}. Falling back to memory storage.")
            storage_uri = "memory://"

    # Configure limiter with appropriate backend
    try:
        _limiter = Limiter(
            key_func=get_key_func,
            app=app,
            storage_uri=storage_uri,
            default_limits=[RATE_LIMIT_STANDARD],
            default_limits_exempt_when=lambda: is_internal_request() or is_health_check_endpoint(),
            headers_enabled=True,  # Add rate limit headers to responses
            header_name_mapping={
                "LIMIT": "X-RateLimit-Limit",
                "REMAINING": "X-RateLimit-Remaining",
                "RESET": "X-RateLimit-Reset",
            },
            strategy="fixed-window",  # or "moving-window" for stricter limiting
            swallow_errors=True,  # Don't break the app if limiter has issues
        )

        # Store reference in app config for access in blueprints
        app.config['LIMITER'] = _limiter

        logger.info(
            f"Rate limiter initialized with {storage_uri.split(':')[0]} storage. "
            f"Default limit: {RATE_LIMIT_STANDARD}"
        )

    except Exception as e:
        logger.error(f"Failed to initialize rate limiter: {e}")
        _limiter = None


def rate_limit_exceeded_handler(e):
    """
    Handle rate limit exceeded errors (429).

    Returns a JSON response with rate limit information.
    """
    return jsonify({
        "error": "Rate Limit Exceeded",
        "message": f"Too many requests. Please wait before making another request.",
        "retry_after": getattr(e, "retry_after", None),
    }), 429


def exempt_from_rate_limit(f: Callable) -> Callable:
    """
    Decorator to exempt a view function from rate limiting.

    Use this for endpoints that should never be rate limited,
    such as health checks or special internal endpoints.

    Example:
        @app.route('/health')
        @exempt_from_rate_limit
        def health():
            return {'status': 'ok'}
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        g._rate_limit_exempt = True
        return f(*args, **kwargs)

    if _limiter is not None:
        return _limiter.exempt(decorated_function)
    return decorated_function


def standard_limit(f: Callable = None, *, limit: str = None) -> Callable:
    """
    Apply standard rate limit to an endpoint.

    Default: 100 requests per minute.

    Example:
        @app.route('/api/resource')
        @standard_limit
        def get_resource():
            ...

        # With custom limit
        @app.route('/api/custom')
        @standard_limit(limit="50 per minute")
        def get_custom():
            ...
    """
    limit_value = limit or RATE_LIMIT_STANDARD

    def decorator(func: Callable) -> Callable:
        if _limiter is not None:
            return _limiter.limit(limit_value)(func)
        return func

    if f is not None:
        return decorator(f)
    return decorator


def auth_limit(f: Callable = None, *, limit: str = None) -> Callable:
    """
    Apply strict rate limit to authentication endpoints.

    Default: 10 requests per minute.

    This prevents brute force attacks on login/register endpoints.

    Example:
        @app.route('/api/auth/login', methods=['POST'])
        @auth_limit
        def login():
            ...
    """
    limit_value = limit or RATE_LIMIT_AUTH

    def decorator(func: Callable) -> Callable:
        if _limiter is not None:
            return _limiter.limit(
                limit_value,
                error_message="Too many authentication attempts. Please wait before trying again."
            )(func)
        return func

    if f is not None:
        return decorator(f)
    return decorator


def heavy_computation_limit(f: Callable = None, *, limit: str = None) -> Callable:
    """
    Apply rate limit to computationally expensive endpoints.

    Default: 10 requests per minute.

    Use this for ML inference, report generation, or other CPU/GPU intensive operations.

    Example:
        @app.route('/api/ml/predict', methods=['POST'])
        @heavy_computation_limit
        def predict():
            ...
    """
    limit_value = limit or RATE_LIMIT_HEAVY

    def decorator(func: Callable) -> Callable:
        if _limiter is not None:
            return _limiter.limit(
                limit_value,
                error_message="This endpoint is rate limited due to computational cost. Please wait before trying again."
            )(func)
        return func

    if f is not None:
        return decorator(f)
    return decorator


def admin_limit(f: Callable = None, *, limit: str = None) -> Callable:
    """
    Apply rate limit to admin endpoints.

    Default: 50 requests per minute.

    Example:
        @app.route('/api/admin/users')
        @admin_limit
        def list_users():
            ...
    """
    limit_value = limit or RATE_LIMIT_ADMIN

    def decorator(func: Callable) -> Callable:
        if _limiter is not None:
            return _limiter.limit(limit_value)(func)
        return func

    if f is not None:
        return decorator(f)
    return decorator


def shared_limit(limit_string: str, scope: str):
    """
    Create a shared rate limit across multiple endpoints.

    This is useful when you want to limit the total requests across
    a group of related endpoints.

    Args:
        limit_string: Rate limit specification (e.g., "100 per minute")
        scope: A unique identifier for this shared limit

    Example:
        # Shared limit across all data export endpoints
        export_limit = shared_limit("5 per minute", "data_export")

        @app.route('/api/export/csv')
        @export_limit
        def export_csv():
            ...

        @app.route('/api/export/json')
        @export_limit
        def export_json():
            ...
    """
    def decorator(f: Callable) -> Callable:
        if _limiter is not None:
            return _limiter.shared_limit(
                limit_string,
                scope=scope
            )(f)
        return f
    return decorator


# Convenience instance for direct use
limiter = None  # Will be set after init_limiter is called


def _update_limiter_reference():
    """Update the module-level limiter reference after initialization."""
    global limiter
    limiter = _limiter
