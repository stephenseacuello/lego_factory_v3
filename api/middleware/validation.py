"""
API Request Validation Middleware.

Provides comprehensive request validation including:
- Schema validation using JSON Schema
- Input sanitization
- Content-Type verification
- Request size limits
- Parameter type coercion
"""

import re
import json
import logging
from functools import wraps
from typing import Dict, Any, Optional, List, Callable, Type
from flask import request, g, jsonify, current_app
from jsonschema import validate, ValidationError as JsonSchemaError
from werkzeug.exceptions import BadRequest, UnsupportedMediaType, RequestEntityTooLarge

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom validation error with details."""

    def __init__(self, message: str, field: Optional[str] = None, errors: Optional[List[Dict]] = None):
        self.message = message
        self.field = field
        self.errors = errors or []
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {'error': 'validation_error', 'message': self.message}
        if self.field:
            result['field'] = self.field
        if self.errors:
            result['details'] = self.errors
        return result


class RequestValidator:
    """Request validation utilities."""

    # Patterns for input sanitization
    SQL_INJECTION_PATTERN = re.compile(
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)",
        re.IGNORECASE
    )
    XSS_PATTERN = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
    PATH_TRAVERSAL_PATTERN = re.compile(r"\.\./|\.\.\\")

    # Default limits
    DEFAULT_MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    DEFAULT_MAX_STRING_LENGTH = 10000
    DEFAULT_MAX_ARRAY_LENGTH = 1000

    @classmethod
    def sanitize_string(cls, value: str, max_length: int = None) -> str:
        """Sanitize a string input."""
        if not isinstance(value, str):
            return value

        max_length = max_length or cls.DEFAULT_MAX_STRING_LENGTH

        # Truncate if too long
        if len(value) > max_length:
            value = value[:max_length]

        # Remove null bytes
        value = value.replace('\x00', '')

        # Strip leading/trailing whitespace
        value = value.strip()

        return value

    @classmethod
    def check_sql_injection(cls, value: str) -> bool:
        """Check for potential SQL injection patterns."""
        if not isinstance(value, str):
            return False
        return bool(cls.SQL_INJECTION_PATTERN.search(value))

    @classmethod
    def check_xss(cls, value: str) -> bool:
        """Check for potential XSS patterns."""
        if not isinstance(value, str):
            return False
        return bool(cls.XSS_PATTERN.search(value))

    @classmethod
    def check_path_traversal(cls, value: str) -> bool:
        """Check for path traversal attempts."""
        if not isinstance(value, str):
            return False
        return bool(cls.PATH_TRAVERSAL_PATTERN.search(value))

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any], deep: bool = True) -> Dict[str, Any]:
        """Recursively sanitize dictionary values."""
        result = {}
        for key, value in data.items():
            # Sanitize key
            clean_key = cls.sanitize_string(str(key), max_length=100)

            if isinstance(value, str):
                result[clean_key] = cls.sanitize_string(value)
            elif isinstance(value, dict) and deep:
                result[clean_key] = cls.sanitize_dict(value, deep=True)
            elif isinstance(value, list) and deep:
                result[clean_key] = cls.sanitize_list(value)
            else:
                result[clean_key] = value

        return result

    @classmethod
    def sanitize_list(cls, data: List[Any], max_length: int = None) -> List[Any]:
        """Sanitize list values."""
        max_length = max_length or cls.DEFAULT_MAX_ARRAY_LENGTH

        if len(data) > max_length:
            data = data[:max_length]

        result = []
        for item in data:
            if isinstance(item, str):
                result.append(cls.sanitize_string(item))
            elif isinstance(item, dict):
                result.append(cls.sanitize_dict(item))
            elif isinstance(item, list):
                result.append(cls.sanitize_list(item))
            else:
                result.append(item)

        return result


def validate_json(schema: Dict[str, Any] = None,
                  sanitize: bool = True,
                  check_injection: bool = True) -> Callable:
    """
    Decorator to validate JSON request body.

    Args:
        schema: JSON Schema for validation
        sanitize: Whether to sanitize input strings
        check_injection: Whether to check for injection attacks

    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Check content type
            if not request.is_json:
                return jsonify({
                    'error': 'invalid_content_type',
                    'message': 'Content-Type must be application/json'
                }), 415

            # Get JSON body
            try:
                data = request.get_json(force=False, silent=False)
            except BadRequest as e:
                return jsonify({
                    'error': 'invalid_json',
                    'message': 'Request body must be valid JSON'
                }), 400

            if data is None:
                return jsonify({
                    'error': 'missing_body',
                    'message': 'Request body is required'
                }), 400

            # Check for injection attacks
            if check_injection and isinstance(data, dict):
                for key, value in _flatten_dict(data):
                    if isinstance(value, str):
                        if RequestValidator.check_sql_injection(value):
                            logger.warning(f"Potential SQL injection detected in field: {key}")
                            return jsonify({
                                'error': 'security_violation',
                                'message': 'Invalid characters detected in input'
                            }), 400

                        if RequestValidator.check_path_traversal(value):
                            logger.warning(f"Potential path traversal detected in field: {key}")
                            return jsonify({
                                'error': 'security_violation',
                                'message': 'Invalid characters detected in input'
                            }), 400

            # Sanitize input
            if sanitize and isinstance(data, dict):
                data = RequestValidator.sanitize_dict(data)

            # Validate against schema
            if schema:
                try:
                    validate(instance=data, schema=schema)
                except JsonSchemaError as e:
                    return jsonify({
                        'error': 'validation_error',
                        'message': e.message,
                        'path': list(e.absolute_path) if e.absolute_path else None
                    }), 400

            # Store validated data in g for handler access
            g.validated_data = data

            return f(*args, **kwargs)

        return wrapper
    return decorator


def validate_query_params(schema: Dict[str, Any] = None,
                          required: List[str] = None,
                          types: Dict[str, Type] = None) -> Callable:
    """
    Decorator to validate query parameters.

    Args:
        schema: JSON Schema for validation
        required: List of required parameter names
        types: Dict mapping parameter names to expected types

    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            params = dict(request.args)
            errors = []

            # Check required parameters
            if required:
                for param in required:
                    if param not in params:
                        errors.append({
                            'field': param,
                            'message': f'Required parameter "{param}" is missing'
                        })

            if errors:
                return jsonify({
                    'error': 'validation_error',
                    'message': 'Missing required parameters',
                    'details': errors
                }), 400

            # Type coercion and validation
            if types:
                for param, expected_type in types.items():
                    if param in params:
                        try:
                            if expected_type == bool:
                                params[param] = params[param].lower() in ('true', '1', 'yes')
                            elif expected_type == int:
                                params[param] = int(params[param])
                            elif expected_type == float:
                                params[param] = float(params[param])
                            elif expected_type == list:
                                params[param] = params[param].split(',')
                        except (ValueError, AttributeError):
                            errors.append({
                                'field': param,
                                'message': f'Parameter "{param}" must be {expected_type.__name__}'
                            })

            if errors:
                return jsonify({
                    'error': 'validation_error',
                    'message': 'Invalid parameter types',
                    'details': errors
                }), 400

            # Sanitize string parameters
            for key, value in params.items():
                if isinstance(value, str):
                    params[key] = RequestValidator.sanitize_string(value)

            # Validate against schema
            if schema:
                try:
                    validate(instance=params, schema=schema)
                except JsonSchemaError as e:
                    return jsonify({
                        'error': 'validation_error',
                        'message': e.message,
                        'path': list(e.absolute_path) if e.absolute_path else None
                    }), 400

            # Store validated params
            g.validated_params = params

            return f(*args, **kwargs)

        return wrapper
    return decorator


def validate_path_params(**validators: Dict[str, Callable]) -> Callable:
    """
    Decorator to validate path parameters.

    Args:
        **validators: Dict of parameter name to validator function
                     Each validator should raise ValueError on invalid input

    Returns:
        Decorator function

    Example:
        @validate_path_params(
            id=lambda x: int(x) if x.isdigit() else raise ValueError("Invalid ID")
        )
        def get_item(id):
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            errors = []

            for param, validator in validators.items():
                if param in kwargs:
                    try:
                        kwargs[param] = validator(kwargs[param])
                    except (ValueError, TypeError) as e:
                        errors.append({
                            'field': param,
                            'message': str(e) or f'Invalid value for "{param}"'
                        })

            if errors:
                return jsonify({
                    'error': 'validation_error',
                    'message': 'Invalid path parameters',
                    'details': errors
                }), 400

            return f(*args, **kwargs)

        return wrapper
    return decorator


def require_content_type(*content_types: str) -> Callable:
    """
    Decorator to require specific content types.

    Args:
        *content_types: Allowed content types

    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            if request.content_type:
                # Extract main content type (ignore charset, etc.)
                main_type = request.content_type.split(';')[0].strip()
                if main_type not in content_types:
                    return jsonify({
                        'error': 'invalid_content_type',
                        'message': f'Content-Type must be one of: {", ".join(content_types)}'
                    }), 415

            return f(*args, **kwargs)

        return wrapper
    return decorator


def limit_request_size(max_bytes: int) -> Callable:
    """
    Decorator to limit request body size.

    Args:
        max_bytes: Maximum allowed request body size

    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            content_length = request.content_length
            if content_length and content_length > max_bytes:
                return jsonify({
                    'error': 'request_too_large',
                    'message': f'Request body exceeds maximum size of {max_bytes} bytes'
                }), 413

            return f(*args, **kwargs)

        return wrapper
    return decorator


def _flatten_dict(d: Dict[str, Any], parent_key: str = '') -> List[tuple]:
    """Flatten a nested dictionary into key-value pairs."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.extend(_flatten_dict(item, f"{new_key}[{i}]"))
                else:
                    items.append((f"{new_key}[{i}]", item))
        else:
            items.append((new_key, v))
    return items


# Common JSON Schemas for reuse
SCHEMAS = {
    'pagination': {
        'type': 'object',
        'properties': {
            'page': {'type': 'integer', 'minimum': 1},
            'per_page': {'type': 'integer', 'minimum': 1, 'maximum': 100},
            'sort_by': {'type': 'string'},
            'sort_order': {'type': 'string', 'enum': ['asc', 'desc']}
        }
    },
    'id': {
        'type': 'string',
        'pattern': '^[a-zA-Z0-9_-]+$',
        'minLength': 1,
        'maxLength': 64
    },
    'uuid': {
        'type': 'string',
        'pattern': '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    },
    'email': {
        'type': 'string',
        'format': 'email',
        'maxLength': 254
    },
    'datetime': {
        'type': 'string',
        'format': 'date-time'
    },
    'tag_value': {
        'type': 'object',
        'required': ['tag_id', 'value'],
        'properties': {
            'tag_id': {'type': 'string', 'minLength': 1, 'maxLength': 100},
            'value': {'type': ['number', 'string', 'boolean']},
            'quality': {'type': 'integer', 'minimum': 0, 'maximum': 255},
            'timestamp': {'type': 'string', 'format': 'date-time'}
        }
    },
    'ncr_create': {
        'type': 'object',
        'required': ['title', 'description', 'detected_by'],
        'properties': {
            'title': {'type': 'string', 'minLength': 1, 'maxLength': 200},
            'description': {'type': 'string', 'minLength': 1, 'maxLength': 5000},
            'detected_by': {'type': 'string', 'minLength': 1, 'maxLength': 100},
            'severity': {'type': 'string', 'enum': ['critical', 'major', 'minor']},
            'category': {'type': 'string', 'maxLength': 100},
            'product_id': {'type': 'string', 'maxLength': 100},
            'lot_number': {'type': 'string', 'maxLength': 50}
        }
    },
    'work_order': {
        'type': 'object',
        'required': ['product_id', 'quantity'],
        'properties': {
            'product_id': {'type': 'string', 'minLength': 1, 'maxLength': 100},
            'quantity': {'type': 'integer', 'minimum': 1},
            'priority': {'type': 'integer', 'minimum': 1, 'maximum': 5},
            'scheduled_start': {'type': 'string', 'format': 'date-time'},
            'notes': {'type': 'string', 'maxLength': 2000}
        }
    }
}
