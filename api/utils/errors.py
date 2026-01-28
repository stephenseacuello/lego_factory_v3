"""
LEGO Factory v3 - Standardized Error Handling
==============================================

Provides consistent error responses across all API endpoints.

Usage:
    from api.utils.errors import APIError, handle_api_error, register_error_handlers

    # Raise an API error
    raise APIError("Resource not found", status_code=404, error_code="RESOURCE_NOT_FOUND")

    # Register error handlers on Flask app
    register_error_handlers(app)
"""

from flask import jsonify, current_app
from functools import wraps
import logging
import traceback
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class APIError(Exception):
    """
    Standard API error with structured response.

    Attributes:
        message: Human-readable error message
        status_code: HTTP status code (default: 400)
        error_code: Machine-readable error code (default: UNKNOWN_ERROR)
        details: Additional error details (optional)
    """

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "UNKNOWN_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON response."""
        response = {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.details:
            response["details"] = self.details
        return response


# Common error types
class NotFoundError(APIError):
    """Resource not found error (404)."""
    def __init__(self, message: str = "Resource not found", details: Optional[Dict] = None):
        super().__init__(message, status_code=404, error_code="NOT_FOUND", details=details)


class ValidationError(APIError):
    """Request validation error (400)."""
    def __init__(self, message: str = "Validation failed", details: Optional[Dict] = None):
        super().__init__(message, status_code=400, error_code="VALIDATION_ERROR", details=details)


class AuthenticationError(APIError):
    """Authentication required or failed (401)."""
    def __init__(self, message: str = "Authentication required", details: Optional[Dict] = None):
        super().__init__(message, status_code=401, error_code="AUTHENTICATION_ERROR", details=details)


class AuthorizationError(APIError):
    """User not authorized for this action (403)."""
    def __init__(self, message: str = "Not authorized", details: Optional[Dict] = None):
        super().__init__(message, status_code=403, error_code="AUTHORIZATION_ERROR", details=details)


class ConflictError(APIError):
    """Resource conflict (409)."""
    def __init__(self, message: str = "Resource conflict", details: Optional[Dict] = None):
        super().__init__(message, status_code=409, error_code="CONFLICT", details=details)


class ServiceUnavailableError(APIError):
    """External service unavailable (503)."""
    def __init__(self, message: str = "Service unavailable", details: Optional[Dict] = None):
        super().__init__(message, status_code=503, error_code="SERVICE_UNAVAILABLE", details=details)


class DatabaseError(APIError):
    """Database operation failed (500)."""
    def __init__(self, message: str = "Database error", details: Optional[Dict] = None):
        super().__init__(message, status_code=500, error_code="DATABASE_ERROR", details=details)


def error_response(
    message: str,
    status_code: int = 400,
    error_code: str = "ERROR",
    details: Optional[Dict] = None
) -> tuple:
    """
    Create a standardized error response.

    Args:
        message: Human-readable error message
        status_code: HTTP status code
        error_code: Machine-readable error code
        details: Additional error details

    Returns:
        Tuple of (response_dict, status_code) for Flask jsonify
    """
    response = {
        "error": True,
        "error_code": error_code,
        "message": message,
    }
    if details:
        response["details"] = details
    return jsonify(response), status_code


def handle_api_error(func):
    """
    Decorator to handle exceptions and return consistent error responses.

    Usage:
        @app.route('/api/resource')
        @handle_api_error
        def get_resource():
            # Code that might raise exceptions
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            logger.warning(f"API error in {func.__name__}: {e.error_code} - {e.message}")
            return jsonify(e.to_dict()), e.status_code
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            logger.debug(traceback.format_exc())

            # In production, don't expose internal error details
            if current_app.config.get('DEBUG'):
                details = {"exception": str(e), "traceback": traceback.format_exc()}
            else:
                details = None

            return error_response(
                message="An internal error occurred",
                status_code=500,
                error_code="INTERNAL_ERROR",
                details=details
            )
    return wrapper


def register_error_handlers(app):
    """
    Register global error handlers on Flask app.

    Usage:
        from api.utils.errors import register_error_handlers

        app = Flask(__name__)
        register_error_handlers(app)
    """

    @app.errorhandler(APIError)
    def handle_api_error_global(error):
        logger.warning(f"API error: {error.error_code} - {error.message}")
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(400)
    def handle_bad_request(error):
        return error_response(
            message="Bad request",
            status_code=400,
            error_code="BAD_REQUEST"
        )

    @app.errorhandler(401)
    def handle_unauthorized(error):
        return error_response(
            message="Authentication required",
            status_code=401,
            error_code="UNAUTHORIZED"
        )

    @app.errorhandler(403)
    def handle_forbidden(error):
        return error_response(
            message="Access forbidden",
            status_code=403,
            error_code="FORBIDDEN"
        )

    @app.errorhandler(404)
    def handle_not_found(error):
        return error_response(
            message="Resource not found",
            status_code=404,
            error_code="NOT_FOUND"
        )

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        return error_response(
            message="Method not allowed",
            status_code=405,
            error_code="METHOD_NOT_ALLOWED"
        )

    @app.errorhandler(500)
    def handle_internal_error(error):
        logger.error(f"Internal server error: {error}")
        return error_response(
            message="Internal server error",
            status_code=500,
            error_code="INTERNAL_ERROR"
        )

    @app.errorhandler(503)
    def handle_service_unavailable(error):
        return error_response(
            message="Service temporarily unavailable",
            status_code=503,
            error_code="SERVICE_UNAVAILABLE"
        )

    logger.info("Registered global error handlers")


# Export common error responses for quick use
def not_found(resource: str = "Resource") -> tuple:
    """Quick 404 response."""
    return error_response(f"{resource} not found", 404, "NOT_FOUND")


def bad_request(message: str = "Invalid request") -> tuple:
    """Quick 400 response."""
    return error_response(message, 400, "BAD_REQUEST")


def unauthorized(message: str = "Authentication required") -> tuple:
    """Quick 401 response."""
    return error_response(message, 401, "UNAUTHORIZED")


def forbidden(message: str = "Access denied") -> tuple:
    """Quick 403 response."""
    return error_response(message, 403, "FORBIDDEN")


def server_error(message: str = "Internal error") -> tuple:
    """Quick 500 response."""
    return error_response(message, 500, "INTERNAL_ERROR")


def service_unavailable(service: str = "Service") -> tuple:
    """Quick 503 response."""
    return error_response(f"{service} is temporarily unavailable", 503, "SERVICE_UNAVAILABLE")
