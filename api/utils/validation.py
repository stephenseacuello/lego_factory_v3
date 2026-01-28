"""
LEGO Factory v3 - Request Validation Utilities
===============================================
Validation decorators and helper functions for Flask routes
using Pydantic schemas.

This module provides:
- Decorator for validating JSON request bodies
- Decorator for validating query parameters
- Helper functions for generating validation error responses
- Exception handling for Pydantic validation errors

Usage:
    from api.utils.validation import validate_request, validate_query_params
    from api.schemas.scada_schemas import MachineCreate, MachineListParams

    @app.route('/machines', methods=['POST'])
    @validate_request(MachineCreate)
    def create_machine(validated_data: MachineCreate):
        # validated_data is a validated Pydantic model instance
        return jsonify(validated_data.model_dump())

    @app.route('/machines', methods=['GET'])
    @validate_query_params(MachineListParams)
    def list_machines(query_params: MachineListParams):
        # query_params is a validated Pydantic model instance
        return jsonify({'limit': query_params.limit})
"""

import functools
import logging
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from flask import request, jsonify, g
from pydantic import BaseModel, ValidationError as PydanticValidationError

from api.schemas.common_schemas import ErrorResponse, FieldError, ValidationErrorResponse

logger = logging.getLogger(__name__)

# Type variable for generic schema types
T = TypeVar('T', bound=BaseModel)


class ValidationError(Exception):
    """
    Custom validation error exception.

    Raised when request validation fails, carrying structured
    error information for API response generation.

    Attributes:
        message: Human-readable error message
        errors: List of field-level errors
        status_code: HTTP status code (default: 400)
    """

    def __init__(
        self,
        message: str,
        errors: Optional[List[Dict[str, str]]] = None,
        status_code: int = 400
    ):
        super().__init__(message)
        self.message = message
        self.errors = errors or []
        self.status_code = status_code


def format_pydantic_errors(exc: PydanticValidationError) -> List[FieldError]:
    """
    Format Pydantic validation errors into FieldError objects.

    Converts Pydantic's internal error format into a consistent
    API response format with field names, messages, and error types.

    Args:
        exc: Pydantic ValidationError exception

    Returns:
        List of FieldError objects for API response
    """
    field_errors = []

    for error in exc.errors():
        # Build field path (e.g., "lines.0.quantity" for nested fields)
        field_path = '.'.join(str(loc) for loc in error['loc'])

        # Get user-friendly message
        message = error['msg']

        # Get error type
        error_type = error['type']

        field_errors.append(FieldError(
            field=field_path,
            message=message,
            type=error_type
        ))

    return field_errors


def validation_error_response(
    message: str,
    errors: Optional[List[FieldError]] = None,
    status_code: int = 400,
    request_id: Optional[str] = None
) -> tuple:
    """
    Generate a standardized validation error response.

    Creates a JSON response with consistent error formatting
    for validation failures.

    Args:
        message: Human-readable error message
        errors: List of field-level errors
        status_code: HTTP status code
        request_id: Optional request ID for tracing

    Returns:
        Tuple of (response_dict, status_code) for Flask jsonify
    """
    response = ValidationErrorResponse(
        error="validation_error",
        message=message,
        details=errors or [],
        request_id=request_id
    )

    return jsonify(response.model_dump()), status_code


def validate_json(
    data: Optional[Dict[str, Any]],
    schema: Type[T],
    allow_none: bool = False
) -> T:
    """
    Validate JSON data against a Pydantic schema.

    Standalone validation function that can be called directly
    without using the decorator pattern.

    Args:
        data: JSON data dictionary to validate
        schema: Pydantic model class to validate against
        allow_none: If True, return None for missing data instead of raising

    Returns:
        Validated Pydantic model instance

    Raises:
        ValidationError: If validation fails or data is missing
    """
    if data is None:
        if allow_none:
            return None
        raise ValidationError(
            message="No JSON data provided",
            errors=[FieldError(
                field="body",
                message="Request body is required",
                type="missing"
            ).model_dump()],
            status_code=400
        )

    try:
        return schema.model_validate(data)
    except PydanticValidationError as e:
        field_errors = format_pydantic_errors(e)
        raise ValidationError(
            message="Validation failed",
            errors=[err.model_dump() for err in field_errors],
            status_code=400
        )


def validate_request(schema: Type[T], *, partial: bool = False):
    """
    Decorator to validate JSON request body against a Pydantic schema.

    Automatically parses the request JSON, validates it against
    the provided schema, and passes the validated model to the
    route function. Returns a 400 error response if validation fails.

    Args:
        schema: Pydantic model class to validate against
        partial: If True, allow partial data (useful for PATCH requests)

    Returns:
        Decorated function that receives validated_data as first argument

    Usage:
        @app.route('/machines', methods=['POST'])
        @validate_request(MachineCreate)
        def create_machine(validated_data: MachineCreate):
            machine = service.create(validated_data.model_dump())
            return jsonify(machine), 201

    Example with partial validation (PATCH):
        @app.route('/machines/<id>', methods=['PATCH'])
        @validate_request(MachineUpdate, partial=True)
        def update_machine(validated_data: MachineUpdate, id: str):
            # Only non-None fields will be present
            update_dict = validated_data.model_dump(exclude_unset=True)
            return jsonify(service.update(id, update_dict))
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get JSON data from request
            try:
                data = request.get_json(force=False, silent=True)
            except Exception as e:
                logger.warning(f"Failed to parse JSON: {e}")
                return validation_error_response(
                    message="Invalid JSON in request body",
                    errors=[FieldError(
                        field="body",
                        message=str(e),
                        type="json_parse_error"
                    )],
                    status_code=400
                )

            # Check for missing body
            if data is None:
                return validation_error_response(
                    message="No JSON data provided",
                    errors=[FieldError(
                        field="body",
                        message="Request body is required",
                        type="missing"
                    )],
                    status_code=400
                )

            # Validate against schema
            try:
                validated = schema.model_validate(data)
            except PydanticValidationError as e:
                field_errors = format_pydantic_errors(e)
                logger.debug(f"Validation failed: {field_errors}")
                return validation_error_response(
                    message="Validation failed",
                    errors=field_errors,
                    status_code=400
                )

            # Store validated data in g for access elsewhere if needed
            g.validated_data = validated

            # Call the route function with validated data as first argument
            return func(validated, *args, **kwargs)

        return wrapper
    return decorator


def validate_query_params(schema: Type[T]):
    """
    Decorator to validate query parameters against a Pydantic schema.

    Parses query parameters from the request, validates them against
    the provided schema, and passes the validated model to the route
    function. Returns a 400 error response if validation fails.

    Args:
        schema: Pydantic model class to validate against

    Returns:
        Decorated function that receives query_params as first argument

    Usage:
        @app.route('/machines', methods=['GET'])
        @validate_query_params(MachineListParams)
        def list_machines(query_params: MachineListParams):
            machines = service.list(
                limit=query_params.limit,
                offset=query_params.offset
            )
            return jsonify({'machines': machines})

    Notes:
        - Multi-value parameters (lists) should use getlist
        - Type conversion is handled by Pydantic
        - Default values from schema are applied for missing params
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Convert query params to dict
            # Handle both single values and lists
            params = {}
            for key in request.args.keys():
                values = request.args.getlist(key)
                if len(values) == 1:
                    params[key] = values[0]
                else:
                    params[key] = values

            # Validate against schema
            try:
                validated = schema.model_validate(params)
            except PydanticValidationError as e:
                field_errors = format_pydantic_errors(e)
                logger.debug(f"Query param validation failed: {field_errors}")
                return validation_error_response(
                    message="Invalid query parameters",
                    errors=field_errors,
                    status_code=400
                )

            # Store validated params in g
            g.query_params = validated

            # Call the route function with validated params as first argument
            return func(validated, *args, **kwargs)

        return wrapper
    return decorator


def validate_path_param(
    param_name: str,
    pattern: Optional[str] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None
) -> Callable:
    """
    Decorator to validate a URL path parameter.

    Provides simple validation for path parameters without
    requiring a full Pydantic schema.

    Args:
        param_name: Name of the path parameter to validate
        pattern: Regex pattern to match against
        min_length: Minimum length requirement
        max_length: Maximum length requirement

    Returns:
        Decorated function

    Usage:
        @app.route('/machines/<machine_id>', methods=['GET'])
        @validate_path_param('machine_id', pattern=r'^[a-zA-Z0-9_-]+$', max_length=50)
        def get_machine(machine_id: str):
            return jsonify(service.get(machine_id))
    """
    import re

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            value = kwargs.get(param_name)

            if value is None:
                return validation_error_response(
                    message=f"Missing path parameter: {param_name}",
                    errors=[FieldError(
                        field=param_name,
                        message="Path parameter is required",
                        type="missing"
                    )],
                    status_code=400
                )

            # Validate length
            if min_length is not None and len(value) < min_length:
                return validation_error_response(
                    message=f"Invalid {param_name}",
                    errors=[FieldError(
                        field=param_name,
                        message=f"Must be at least {min_length} characters",
                        type="string_too_short"
                    )],
                    status_code=400
                )

            if max_length is not None and len(value) > max_length:
                return validation_error_response(
                    message=f"Invalid {param_name}",
                    errors=[FieldError(
                        field=param_name,
                        message=f"Must be at most {max_length} characters",
                        type="string_too_long"
                    )],
                    status_code=400
                )

            # Validate pattern
            if pattern is not None and not re.match(pattern, value):
                return validation_error_response(
                    message=f"Invalid {param_name} format",
                    errors=[FieldError(
                        field=param_name,
                        message=f"Does not match required pattern",
                        type="string_pattern_mismatch"
                    )],
                    status_code=400
                )

            return func(*args, **kwargs)

        return wrapper
    return decorator


def require_json_content_type(func: Callable) -> Callable:
    """
    Decorator to require JSON content type for requests.

    Returns a 415 Unsupported Media Type error if the request
    content type is not application/json.

    Usage:
        @app.route('/machines', methods=['POST'])
        @require_json_content_type
        @validate_request(MachineCreate)
        def create_machine(validated_data):
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        content_type = request.content_type or ''
        if not content_type.startswith('application/json'):
            return jsonify({
                'error': 'unsupported_media_type',
                'message': 'Content-Type must be application/json'
            }), 415
        return func(*args, **kwargs)
    return wrapper


def handle_validation_errors(app):
    """
    Register global validation error handlers with a Flask app.

    Call this function during app initialization to ensure
    all validation errors are properly formatted.

    Args:
        app: Flask application instance

    Usage:
        from api.utils.validation import handle_validation_errors

        app = Flask(__name__)
        handle_validation_errors(app)
    """
    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):
        """Handle ValidationError exceptions globally."""
        return validation_error_response(
            message=error.message,
            errors=[FieldError(**e) for e in error.errors] if error.errors else None,
            status_code=error.status_code
        )

    @app.errorhandler(PydanticValidationError)
    def handle_pydantic_error(error: PydanticValidationError):
        """Handle Pydantic ValidationError exceptions globally."""
        field_errors = format_pydantic_errors(error)
        return validation_error_response(
            message="Validation failed",
            errors=field_errors,
            status_code=400
        )


def get_validated_data() -> Optional[BaseModel]:
    """
    Get the validated request data from the current request context.

    Returns the validated Pydantic model stored by @validate_request.

    Returns:
        Validated Pydantic model or None if not available
    """
    return getattr(g, 'validated_data', None)


def get_query_params() -> Optional[BaseModel]:
    """
    Get the validated query parameters from the current request context.

    Returns the validated Pydantic model stored by @validate_query_params.

    Returns:
        Validated Pydantic model or None if not available
    """
    return getattr(g, 'query_params', None)
