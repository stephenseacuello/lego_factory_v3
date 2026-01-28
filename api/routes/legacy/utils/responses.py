"""
Standardized API Response Helpers for Flask CNC SCADA.

Provides consistent response formatting across all API endpoints.
"""

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from flask import Response, jsonify, request
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


# Error codes for machine-readable error handling
class ErrorCodes:
    """Standard error codes for API responses."""

    # Validation errors (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_GCODE = "INVALID_GCODE"
    INVALID_PORT = "INVALID_PORT"
    INVALID_PARAMETER = "INVALID_PARAMETER"

    # Authentication errors (401)
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"

    # Authorization errors (403)
    FORBIDDEN = "FORBIDDEN"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"

    # Not found errors (404)
    NOT_FOUND = "NOT_FOUND"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    ENDPOINT_NOT_FOUND = "ENDPOINT_NOT_FOUND"

    # Conflict errors (409)
    CONFLICT = "CONFLICT"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    STATE_CONFLICT = "STATE_CONFLICT"

    # Hardware errors (502/503)
    HARDWARE_ERROR = "HARDWARE_ERROR"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    DEVICE_NOT_CONNECTED = "DEVICE_NOT_CONNECTED"
    SERIAL_ERROR = "SERIAL_ERROR"

    # Service errors (503)
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"

    # Internal errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


def success_response(
    data: Any = None,
    message: Optional[str] = None,
    status_code: int = 200,
) -> tuple[Response, int]:
    """
    Create a standardized success response.

    Args:
        data: Response payload data
        message: Optional success message
        status_code: HTTP status code (default 200)

    Returns:
        Tuple of (Response, status_code)
    """
    response = {"success": True}

    if message:
        response["message"] = message

    if data is not None:
        response["data"] = data

    return jsonify(response), status_code


def error_response(
    message: str,
    code: str = ErrorCodes.INTERNAL_ERROR,
    status_code: int = 400,
    field: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> tuple[Response, int]:
    """
    Create a standardized error response.

    Args:
        message: Human-readable error message
        code: Machine-readable error code
        status_code: HTTP status code
        field: Optional field that caused the error
        details: Optional additional error details

    Returns:
        Tuple of (Response, status_code)
    """
    error_obj: Dict[str, Any] = {
        "message": message,
        "code": code,
    }

    if field:
        error_obj["field"] = field

    if details:
        error_obj["details"] = details

    return jsonify({"success": False, "error": error_obj}), status_code


def validation_error_response(
    errors: Union[List[Dict[str, Any]], ValidationError],
    message: str = "Validation failed",
) -> tuple[Response, int]:
    """
    Create a standardized validation error response.

    Args:
        errors: List of validation errors or Pydantic ValidationError
        message: Overall error message

    Returns:
        Tuple of (Response, status_code)
    """
    if isinstance(errors, ValidationError):
        # Convert Pydantic ValidationError to list of dicts
        error_list = []
        for err in errors.errors():
            error_list.append({
                "field": ".".join(str(loc) for loc in err["loc"]),
                "message": err["msg"],
                "type": err["type"],
            })
        errors = error_list

    return error_response(
        message=message,
        code=ErrorCodes.VALIDATION_ERROR,
        status_code=400,
        details={"errors": errors},
    )


def not_found_response(
    resource: str = "Resource",
    identifier: Optional[str] = None,
) -> tuple[Response, int]:
    """
    Create a standardized 404 not found response.

    Args:
        resource: Name of the resource not found
        identifier: Optional identifier of the resource

    Returns:
        Tuple of (Response, status_code)
    """
    message = f"{resource} not found"
    if identifier:
        message = f"{resource} '{identifier}' not found"

    return error_response(
        message=message,
        code=ErrorCodes.NOT_FOUND,
        status_code=404,
    )


def unauthorized_response(
    message: str = "Authentication required",
    code: str = ErrorCodes.UNAUTHORIZED,
) -> tuple[Response, int]:
    """
    Create a standardized 401 unauthorized response.

    Args:
        message: Error message
        code: Specific error code

    Returns:
        Tuple of (Response, status_code)
    """
    return error_response(
        message=message,
        code=code,
        status_code=401,
    )


def forbidden_response(
    message: str = "Access denied",
    code: str = ErrorCodes.FORBIDDEN,
) -> tuple[Response, int]:
    """
    Create a standardized 403 forbidden response.

    Args:
        message: Error message
        code: Specific error code

    Returns:
        Tuple of (Response, status_code)
    """
    return error_response(
        message=message,
        code=code,
        status_code=403,
    )


def conflict_response(
    message: str,
    code: str = ErrorCodes.CONFLICT,
    details: Optional[Dict[str, Any]] = None,
) -> tuple[Response, int]:
    """
    Create a standardized 409 conflict response.

    Args:
        message: Error message
        code: Specific error code
        details: Optional additional details

    Returns:
        Tuple of (Response, status_code)
    """
    return error_response(
        message=message,
        code=code,
        status_code=409,
        details=details,
    )


def service_unavailable_response(
    service: str,
    message: Optional[str] = None,
    code: str = ErrorCodes.SERVICE_UNAVAILABLE,
) -> tuple[Response, int]:
    """
    Create a standardized 503 service unavailable response.

    Args:
        service: Name of the unavailable service
        message: Optional custom message
        code: Specific error code

    Returns:
        Tuple of (Response, status_code)
    """
    if not message:
        message = f"{service} is currently unavailable"

    return error_response(
        message=message,
        code=code,
        status_code=503,
        details={"service": service},
    )


def hardware_error_response(
    device: str,
    message: Optional[str] = None,
    code: str = ErrorCodes.HARDWARE_ERROR,
    details: Optional[Dict[str, Any]] = None,
) -> tuple[Response, int]:
    """
    Create a standardized hardware error response.

    Args:
        device: Name of the hardware device
        message: Optional custom message
        code: Specific error code
        details: Optional additional details

    Returns:
        Tuple of (Response, status_code)
    """
    if not message:
        message = f"Hardware error with {device}"

    error_details = {"device": device}
    if details:
        error_details.update(details)

    return error_response(
        message=message,
        code=code,
        status_code=502,
        details=error_details,
    )


def validate_request(schema: Type[T]) -> Callable:
    """
    Decorator to validate request JSON against a Pydantic schema.

    Usage:
        @bp.route("/connect", methods=["POST"])
        @validate_request(ConnectRequest)
        def connect(validated_data: ConnectRequest):
            port = validated_data.port
            ...

    Args:
        schema: Pydantic BaseModel class to validate against

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get JSON data from request
            json_data = request.get_json(silent=True)

            if json_data is None:
                return error_response(
                    message="Request body must be valid JSON",
                    code=ErrorCodes.INVALID_REQUEST,
                    status_code=400,
                )

            # Validate against schema
            try:
                validated = schema.model_validate(json_data)
            except ValidationError as e:
                return validation_error_response(e)

            # Pass validated data to the route function
            return func(validated, *args, **kwargs)

        return wrapper
    return decorator


def validate_query_params(schema: Type[T]) -> Callable:
    """
    Decorator to validate query parameters against a Pydantic schema.

    Usage:
        @bp.route("/list", methods=["GET"])
        @validate_query_params(PaginationParams)
        def list_items(params: PaginationParams):
            page = params.page
            ...

    Args:
        schema: Pydantic BaseModel class to validate against

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Convert query params to dict
            query_data = request.args.to_dict()

            # Validate against schema
            try:
                validated = schema.model_validate(query_data)
            except ValidationError as e:
                return validation_error_response(e)

            # Pass validated data to the route function
            return func(validated, *args, **kwargs)

        return wrapper
    return decorator
