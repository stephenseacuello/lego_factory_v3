"""
LEGO Factory v3 - API Utilities
================================
Utility functions and decorators for API routes.
"""

from api.utils.validation import (
    validate_request,
    validate_json,
    validate_query_params,
    validation_error_response,
    ValidationError as PydanticValidationError,
    validate_path_param,
)

from api.utils.errors import (
    APIError,
    NotFoundError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ServiceUnavailableError,
    DatabaseError,
    error_response,
    handle_api_error,
    register_error_handlers,
    not_found,
    bad_request,
    unauthorized,
    forbidden,
    server_error,
    service_unavailable,
)

__all__ = [
    # Validation
    'validate_request',
    'validate_json',
    'validate_query_params',
    'validation_error_response',
    'PydanticValidationError',
    'validate_path_param',
    # Errors
    'APIError',
    'NotFoundError',
    'ValidationError',
    'AuthenticationError',
    'AuthorizationError',
    'ConflictError',
    'ServiceUnavailableError',
    'DatabaseError',
    'error_response',
    'handle_api_error',
    'register_error_handlers',
    'not_found',
    'bad_request',
    'unauthorized',
    'forbidden',
    'server_error',
    'service_unavailable',
]
