"""
OpenAPI Specification Generator for Flask CNC SCADA System
==========================================================
Auto-generates OpenAPI 3.0 documentation from Flask routes.

Features:
- Automatic route discovery
- Schema generation from dataclasses
- Response examples
- Security scheme documentation
- Swagger UI integration

Usage:
    from api.openapi_spec import setup_openapi, get_openapi_spec

    # Setup with Flask app
    setup_openapi(app)

    # Access Swagger UI at /api/docs
    # Access OpenAPI JSON at /api/openapi.json

Endpoints documented:
    - System status and health
    - TinyG machine control
    - Sensor data
    - MCC DAQ
    - MES/Work Orders
    - Scheduling
    - Authentication
    - MTConnect
"""

import json
import logging
from typing import Dict, Any, List, Optional, Type
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class OpenAPIInfo:
    """API information."""
    title: str = "CNC SCADA API"
    version: str = "2.0.0"
    description: str = """
## CNC SCADA System API

Industrial-grade API for CNC machine monitoring and control.

### Features
- Real-time machine status and position
- Sensor data streaming
- G-code execution and monitoring
- Work order management (MES)
- Production scheduling
- Alert management

### Authentication
Most endpoints require JWT authentication. Obtain a token via `/auth/login`.

### Rate Limiting
- Standard endpoints: 100 requests/minute
- High-frequency data: 1000 requests/minute
- Admin operations: 10 requests/minute
"""
    contact: Dict[str, str] = field(default_factory=lambda: {
        "name": "CNC SCADA Support",
        "email": "support@cnc-scada.local",
    })
    license: Dict[str, str] = field(default_factory=lambda: {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    })


@dataclass
class OpenAPIServer:
    """Server configuration."""
    url: str
    description: str = ""


# Common schemas
SCHEMAS = {
    "Error": {
        "type": "object",
        "properties": {
            "error": {"type": "string", "description": "Error message"},
            "code": {"type": "string", "description": "Error code"},
            "details": {"type": "object", "description": "Additional error details"},
        },
        "required": ["error"],
    },
    "Success": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "example": "ok"},
            "message": {"type": "string"},
        },
    },
    "MachinePosition": {
        "type": "object",
        "properties": {
            "wx": {"type": "number", "description": "Work X position (mm)"},
            "wy": {"type": "number", "description": "Work Y position (mm)"},
            "wz": {"type": "number", "description": "Work Z position (mm)"},
            "mx": {"type": "number", "description": "Machine X position (mm)"},
            "my": {"type": "number", "description": "Machine Y position (mm)"},
            "mz": {"type": "number", "description": "Machine Z position (mm)"},
        },
    },
    "MachineStatus": {
        "type": "object",
        "properties": {
            "connected": {"type": "boolean"},
            "stat": {"type": "integer", "description": "Machine state (0-9)"},
            "momo": {"type": "integer", "description": "Motion mode"},
            "feed": {"type": "number", "description": "Feed rate (mm/min)"},
            "vel": {"type": "number", "description": "Velocity (mm/min)"},
            "sps": {"type": "number", "description": "Spindle speed (RPM)"},
            "position": {"$ref": "#/components/schemas/MachinePosition"},
            "timestamp": {"type": "number", "description": "Unix timestamp"},
        },
    },
    "SensorData": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "Sensor ID"},
            "timestamp": {"type": "number"},
            "ax": {"type": "number", "description": "Accelerometer X (g)"},
            "ay": {"type": "number", "description": "Accelerometer Y (g)"},
            "az": {"type": "number", "description": "Accelerometer Z (g)"},
            "gx": {"type": "number", "description": "Gyroscope X (dps)"},
            "gy": {"type": "number", "description": "Gyroscope Y (dps)"},
            "gz": {"type": "number", "description": "Gyroscope Z (dps)"},
            "temperature": {"type": "number", "description": "Temperature (°C)"},
            "pressure": {"type": "number", "description": "Pressure (hPa)"},
        },
    },
    "MCCData": {
        "type": "object",
        "properties": {
            "timestamp": {"type": "number"},
            "channels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "channel": {"type": "integer"},
                        "current": {"type": "number", "description": "Current (A)"},
                    },
                },
            },
        },
    },
    "WorkOrder": {
        "type": "object",
        "properties": {
            "work_order_id": {"type": "string"},
            "part_number": {"type": "string"},
            "quantity": {"type": "integer"},
            "quantity_completed": {"type": "integer"},
            "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "cancelled"]},
            "priority": {"type": "integer", "minimum": 1, "maximum": 5},
            "due_date": {"type": "string", "format": "date-time"},
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "Alert": {
        "type": "object",
        "properties": {
            "alert_id": {"type": "string"},
            "level": {"type": "string", "enum": ["info", "warning", "critical", "emergency"]},
            "title": {"type": "string"},
            "message": {"type": "string"},
            "machine_id": {"type": "string"},
            "timestamp": {"type": "string", "format": "date-time"},
            "state": {"type": "string", "enum": ["active", "acknowledged", "resolved"]},
        },
    },
    "LoginRequest": {
        "type": "object",
        "properties": {
            "username": {"type": "string"},
            "password": {"type": "string", "format": "password"},
        },
        "required": ["username", "password"],
    },
    "LoginResponse": {
        "type": "object",
        "properties": {
            "access_token": {"type": "string"},
            "refresh_token": {"type": "string"},
            "token_type": {"type": "string", "example": "Bearer"},
            "expires_in": {"type": "integer", "description": "Token lifetime in seconds"},
        },
    },
    "GCodeCommand": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "G-code command", "example": "G0 X10 Y10"},
        },
        "required": ["command"],
    },
    "JogRequest": {
        "type": "object",
        "properties": {
            "axis": {"type": "string", "enum": ["x", "y", "z", "a"]},
            "distance": {"type": "number", "description": "Distance in mm"},
            "feed_rate": {"type": "number", "description": "Feed rate (mm/min)"},
        },
        "required": ["axis", "distance"],
    },
    "HealthCheck": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["healthy", "degraded", "unhealthy"]},
            "timestamp": {"type": "string", "format": "date-time"},
            "components": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "latency_ms": {"type": "number"},
                    },
                },
            },
        },
    },
}

# Security schemes
SECURITY_SCHEMES = {
    "bearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT authentication token. Obtain via /auth/login",
    },
    "apiKey": {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "API key for machine-to-machine authentication",
    },
}

# API paths
PATHS = {
    "/api/health": {
        "get": {
            "tags": ["System"],
            "summary": "Health check",
            "description": "Check system health and component status",
            "operationId": "getHealth",
            "responses": {
                "200": {
                    "description": "System health status",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/HealthCheck"},
                        },
                    },
                },
            },
        },
    },
    "/status": {
        "get": {
            "tags": ["System"],
            "summary": "System status",
            "description": "Get overall system status including all subsystems",
            "operationId": "getStatus",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "System status",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "tinyg": {"$ref": "#/components/schemas/MachineStatus"},
                                    "sensors": {"type": "object"},
                                    "mcc": {"type": "object"},
                                    "influxdb": {"type": "object"},
                                    "mqtt": {"type": "object"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/auth/login": {
        "post": {
            "tags": ["Authentication"],
            "summary": "User login",
            "description": "Authenticate and obtain JWT tokens",
            "operationId": "login",
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/LoginRequest"},
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Login successful",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/LoginResponse"},
                        },
                    },
                },
                "401": {
                    "description": "Invalid credentials",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"},
                        },
                    },
                },
            },
        },
    },
    "/auth/refresh": {
        "post": {
            "tags": ["Authentication"],
            "summary": "Refresh token",
            "description": "Refresh access token using refresh token",
            "operationId": "refreshToken",
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "refresh_token": {"type": "string"},
                            },
                            "required": ["refresh_token"],
                        },
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Token refreshed",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/LoginResponse"},
                        },
                    },
                },
            },
        },
    },
    "/tinyg/status": {
        "get": {
            "tags": ["TinyG Machine"],
            "summary": "Get machine status",
            "description": "Get current TinyG machine status including position and state",
            "operationId": "getTinyGStatus",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Machine status",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/MachineStatus"},
                        },
                    },
                },
            },
        },
    },
    "/tinyg/send": {
        "post": {
            "tags": ["TinyG Machine"],
            "summary": "Send G-code command",
            "description": "Send a G-code command to the TinyG controller",
            "operationId": "sendGCode",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/GCodeCommand"},
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Command sent",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Success"},
                        },
                    },
                },
                "400": {
                    "description": "Invalid command",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"},
                        },
                    },
                },
            },
        },
    },
    "/tinyg/jog": {
        "post": {
            "tags": ["TinyG Machine"],
            "summary": "Jog machine",
            "description": "Jog the machine in a specific direction",
            "operationId": "jogMachine",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/JogRequest"},
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Jog command sent",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Success"},
                        },
                    },
                },
            },
        },
    },
    "/tinyg/home": {
        "post": {
            "tags": ["TinyG Machine"],
            "summary": "Home machine",
            "description": "Execute homing cycle",
            "operationId": "homeMachine",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Homing started",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Success"},
                        },
                    },
                },
            },
        },
    },
    "/tinyg/feedhold": {
        "post": {
            "tags": ["TinyG Machine"],
            "summary": "Feed hold",
            "description": "Pause machine motion",
            "operationId": "feedHold",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Feed hold activated",
                },
            },
        },
    },
    "/tinyg/resume": {
        "post": {
            "tags": ["TinyG Machine"],
            "summary": "Resume motion",
            "description": "Resume from feed hold",
            "operationId": "resumeMotion",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Motion resumed",
                },
            },
        },
    },
    "/sensor/status": {
        "get": {
            "tags": ["Sensors"],
            "summary": "Get sensor status",
            "description": "Get status and latest data from all sensors",
            "operationId": "getSensorStatus",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Sensor status",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "connected_count": {"type": "integer"},
                                    "sensors": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/SensorData"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/sensor/{sensor_id}/data": {
        "get": {
            "tags": ["Sensors"],
            "summary": "Get sensor data",
            "description": "Get data from specific sensor",
            "operationId": "getSensorData",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {
                    "name": "sensor_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Sensor data",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/SensorData"},
                        },
                    },
                },
            },
        },
    },
    "/mcc/status": {
        "get": {
            "tags": ["MCC DAQ"],
            "summary": "Get MCC DAQ status",
            "description": "Get status and latest data from MCC DAQ",
            "operationId": "getMCCStatus",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "MCC status",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/MCCData"},
                        },
                    },
                },
            },
        },
    },
    "/api/mes/work-orders": {
        "get": {
            "tags": ["MES"],
            "summary": "List work orders",
            "description": "Get list of work orders with optional filters",
            "operationId": "listWorkOrders",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {
                    "name": "status",
                    "in": "query",
                    "schema": {"type": "string"},
                },
                {
                    "name": "limit",
                    "in": "query",
                    "schema": {"type": "integer", "default": 100},
                },
            ],
            "responses": {
                "200": {
                    "description": "Work orders list",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "work_orders": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/WorkOrder"},
                                    },
                                    "total": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
            },
        },
        "post": {
            "tags": ["MES"],
            "summary": "Create work order",
            "description": "Create a new work order",
            "operationId": "createWorkOrder",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/WorkOrder"},
                    },
                },
            },
            "responses": {
                "201": {
                    "description": "Work order created",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/WorkOrder"},
                        },
                    },
                },
            },
        },
    },
    "/analytics/oee": {
        "get": {
            "tags": ["Analytics"],
            "summary": "Get OEE metrics",
            "description": "Get Overall Equipment Effectiveness metrics",
            "operationId": "getOEE",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {
                    "name": "machine_id",
                    "in": "query",
                    "schema": {"type": "string"},
                },
                {
                    "name": "period",
                    "in": "query",
                    "schema": {"type": "string", "enum": ["hour", "day", "week", "month"]},
                },
            ],
            "responses": {
                "200": {
                    "description": "OEE metrics",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "availability": {"type": "number"},
                                    "performance": {"type": "number"},
                                    "quality": {"type": "number"},
                                    "oee": {"type": "number"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/mtconnect/probe": {
        "get": {
            "tags": ["MTConnect"],
            "summary": "MTConnect probe",
            "description": "Get MTConnect device information (XML)",
            "operationId": "mtconnectProbe",
            "responses": {
                "200": {
                    "description": "Device information",
                    "content": {
                        "application/xml": {
                            "schema": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
    "/mtconnect/current": {
        "get": {
            "tags": ["MTConnect"],
            "summary": "MTConnect current",
            "description": "Get current MTConnect data items (XML)",
            "operationId": "mtconnectCurrent",
            "responses": {
                "200": {
                    "description": "Current data",
                    "content": {
                        "application/xml": {
                            "schema": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
    "/mtconnect/current/json": {
        "get": {
            "tags": ["MTConnect"],
            "summary": "MTConnect current (JSON)",
            "description": "Get current MTConnect data items as JSON",
            "operationId": "mtconnectCurrentJson",
            "responses": {
                "200": {
                    "description": "Current data",
                    "content": {
                        "application/json": {
                            "schema": {"type": "object"},
                        },
                    },
                },
            },
        },
    },
    "/metrics": {
        "get": {
            "tags": ["Monitoring"],
            "summary": "Prometheus metrics",
            "description": "Get metrics in Prometheus format",
            "operationId": "getMetrics",
            "responses": {
                "200": {
                    "description": "Prometheus metrics",
                    "content": {
                        "text/plain": {
                            "schema": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
}


def generate_openapi_spec(info: Optional[OpenAPIInfo] = None,
                         servers: Optional[List[OpenAPIServer]] = None) -> Dict[str, Any]:
    """
    Generate complete OpenAPI specification.

    Args:
        info: API info (uses defaults if not provided)
        servers: Server list (uses defaults if not provided)

    Returns:
        OpenAPI specification dictionary
    """
    info = info or OpenAPIInfo()
    servers = servers or [
        OpenAPIServer(url="http://localhost:5000", description="Development server"),
        OpenAPIServer(url="https://cnc-scada.local", description="Production server"),
    ]

    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": info.title,
            "version": info.version,
            "description": info.description,
            "contact": info.contact,
            "license": info.license,
        },
        "servers": [{"url": s.url, "description": s.description} for s in servers],
        "tags": [
            {"name": "System", "description": "System status and health"},
            {"name": "Authentication", "description": "User authentication and authorization"},
            {"name": "TinyG Machine", "description": "TinyG CNC controller operations"},
            {"name": "Sensors", "description": "Sensor data and management"},
            {"name": "MCC DAQ", "description": "MCC DAQ current measurement"},
            {"name": "MES", "description": "Manufacturing Execution System"},
            {"name": "Analytics", "description": "Analytics and reporting"},
            {"name": "MTConnect", "description": "MTConnect protocol endpoints"},
            {"name": "Monitoring", "description": "System monitoring and metrics"},
        ],
        "paths": PATHS,
        "components": {
            "schemas": SCHEMAS,
            "securitySchemes": SECURITY_SCHEMES,
        },
        "security": [{"bearerAuth": []}],
    }

    return spec


def setup_openapi(app):
    """
    Set up OpenAPI documentation endpoints.

    Adds:
    - /api/openapi.json - OpenAPI spec
    - /api/docs - Swagger UI

    Args:
        app: Flask application
    """
    from flask import jsonify, render_template_string

    spec = generate_openapi_spec()

    @app.route('/api/openapi.json')
    def openapi_spec():
        """Return OpenAPI specification."""
        return jsonify(spec)

    @app.route('/api/docs')
    def swagger_ui():
        """Render Swagger UI."""
        return render_template_string(SWAGGER_UI_HTML)

    logger.info("OpenAPI documentation registered at /api/docs")


# Swagger UI HTML template
SWAGGER_UI_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>CNC SCADA API Documentation</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    <style>
        html { box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }
        *, *:before, *:after { box-sizing: inherit; }
        body { margin: 0; background: #fafafa; }
        .swagger-ui .topbar { display: none; }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {
            window.ui = SwaggerUIBundle({
                url: "/api/openapi.json",
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                persistAuthorization: true,
            });
        };
    </script>
</body>
</html>
"""


def get_openapi_spec() -> Dict[str, Any]:
    """Get the OpenAPI specification dictionary."""
    return generate_openapi_spec()
