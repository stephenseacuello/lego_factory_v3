"""
LEGO Factory v3 - API Documentation
====================================
Flask-RESTX based API documentation with Swagger UI.

This module provides comprehensive API documentation for all LEGO Factory
endpoints using Flask-RESTX with automatic Swagger/OpenAPI generation.
"""

from flask import Blueprint
from flask_restx import Api

# Create the API blueprint
api_docs_bp = Blueprint('api_docs', __name__, url_prefix='/api/docs')

# Create the Flask-RESTX Api object with comprehensive metadata
api = Api(
    api_docs_bp,
    version='3.0.0',
    title='LEGO Factory v3 API',
    description='''
# LEGO Factory v3 - Smart Manufacturing Platform API

A comprehensive API for the LEGO Factory smart manufacturing system integrating:

- **SCADA** - Supervisory Control and Data Acquisition (Level 2)
- **MES** - Manufacturing Execution System (Level 3)
- **ERP** - Enterprise Resource Planning (Level 4)
- **ROS2** - Robot Operating System integration
- **ML/AI** - Machine Learning for predictive maintenance and quality control

## Authentication

All API endpoints (except `/api/docs` and `/auth`) require JWT Bearer token authentication.

Include the token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

## Rate Limiting

- Standard endpoints: 100 requests/minute
- Heavy computation (ML, reports): 10 requests/minute

## Response Format

All responses follow a consistent JSON format:

### Success Response
```json
{
    "data": { ... },
    "meta": {
        "timestamp": "2024-01-15T10:30:00Z",
        "request_id": "uuid"
    }
}
```

### Error Response
```json
{
    "error": {
        "code": "ERROR_CODE",
        "message": "Human readable message",
        "details": { ... }
    },
    "meta": {
        "timestamp": "2024-01-15T10:30:00Z",
        "request_id": "uuid"
    }
}
```

## WebSocket Support

Real-time updates are available via Socket.IO at `/socket.io`:
- Machine status updates
- Alarm notifications
- Job progress
- Robot state changes

## API Versioning

Current version: v3
Base URL: `/api/v3`
''',
    doc='/swagger',
    license='MIT',
    license_url='https://opensource.org/licenses/MIT',
    contact='LEGO Factory Development Team',
    contact_email='dev@legofactory.local',
    authorizations={
        'Bearer': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'JWT Bearer token. Format: "Bearer {token}"'
        }
    },
    security='Bearer',
    default_mediatype='application/json',
    serve_challenge_on_401=True,
)

# Configure Swagger UI settings
api.swagger_url = '/swagger.json'

# Error handlers
@api.errorhandler(400)
def bad_request_error(error):
    """Bad Request - The request was malformed or invalid."""
    return {
        'error': {
            'code': 'BAD_REQUEST',
            'message': str(error),
        }
    }, 400


@api.errorhandler(401)
def unauthorized_error(error):
    """Unauthorized - Authentication required."""
    return {
        'error': {
            'code': 'UNAUTHORIZED',
            'message': 'Authentication required. Please provide a valid JWT token.',
        }
    }, 401


@api.errorhandler(403)
def forbidden_error(error):
    """Forbidden - Insufficient permissions."""
    return {
        'error': {
            'code': 'FORBIDDEN',
            'message': 'You do not have permission to access this resource.',
        }
    }, 403


@api.errorhandler(404)
def not_found_error(error):
    """Not Found - The requested resource was not found."""
    return {
        'error': {
            'code': 'NOT_FOUND',
            'message': str(error) or 'The requested resource was not found.',
        }
    }, 404


@api.errorhandler(500)
def internal_error(error):
    """Internal Server Error."""
    return {
        'error': {
            'code': 'INTERNAL_ERROR',
            'message': 'An internal server error occurred.',
        }
    }, 500


@api.errorhandler(503)
def service_unavailable_error(error):
    """Service Unavailable - A required service is not available."""
    return {
        'error': {
            'code': 'SERVICE_UNAVAILABLE',
            'message': str(error) or 'Service temporarily unavailable.',
        }
    }, 503


# Import and register all namespaces
def init_namespaces():
    """Initialize and register all API namespaces."""
    from .auth_ns import auth_ns
    from .scada_ns import scada_ns
    from .mes_ns import mes_ns
    from .erp_ns import erp_ns
    from .ros2_ns import ros2_ns
    from .ml_ns import ml_ns

    api.add_namespace(auth_ns, path='/auth')
    api.add_namespace(scada_ns, path='/scada')
    api.add_namespace(mes_ns, path='/mes')
    api.add_namespace(erp_ns, path='/erp')
    api.add_namespace(ros2_ns, path='/ros2')
    api.add_namespace(ml_ns, path='/ml')


# Common API models that can be reused across namespaces
from flask_restx import fields

# Standard response wrapper models
pagination_model = api.model('Pagination', {
    'page': fields.Integer(description='Current page number', example=1),
    'per_page': fields.Integer(description='Items per page', example=20),
    'total': fields.Integer(description='Total number of items', example=100),
    'pages': fields.Integer(description='Total number of pages', example=5),
})

error_model = api.model('Error', {
    'code': fields.String(description='Error code', example='NOT_FOUND'),
    'message': fields.String(description='Human readable error message', example='Resource not found'),
    'details': fields.Raw(description='Additional error details'),
})

success_response = api.model('SuccessResponse', {
    'success': fields.Boolean(description='Operation success status', example=True),
    'message': fields.String(description='Success message', example='Operation completed successfully'),
})

timestamp_fields = {
    'created_at': fields.DateTime(description='Creation timestamp'),
    'updated_at': fields.DateTime(description='Last update timestamp'),
}

# Health check model
health_model = api.model('Health', {
    'status': fields.String(description='Service status', enum=['healthy', 'degraded', 'unhealthy'], example='healthy'),
    'timestamp': fields.DateTime(description='Current server time'),
    'version': fields.String(description='API version', example='3.0.0'),
    'service': fields.String(description='Service name', example='lego-factory'),
    'components': fields.Raw(description='Component health status'),
})


__all__ = [
    'api',
    'api_docs_bp',
    'init_namespaces',
    'pagination_model',
    'error_model',
    'success_response',
    'health_model',
]
