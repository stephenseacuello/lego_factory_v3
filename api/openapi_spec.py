"""
OpenAPI/Swagger Specification Generator.

Generates OpenAPI 3.0 specification for the LEGO Factory API.
"""

from flask import Blueprint, jsonify
from flask_swagger_ui import get_swaggerui_blueprint

# OpenAPI Specification
OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "LEGO Factory v3 API",
        "description": """
# LEGO Factory Manufacturing Execution System API

This API provides comprehensive access to the LEGO Factory manufacturing execution system,
supporting ISA-95 Level 3 Manufacturing Operations Management.

## Key Features

- **SCADA Tag Management**: Real-time tag read/write operations
- **Historian**: Time-series data storage and retrieval with SDT compression
- **Alarm Management**: ISA-18.2 compliant alarm handling
- **ML Inference**: Anomaly detection and sensor fingerprinting
- **QMS**: NCR/CAPA management for quality control
- **Robotics**: ROS2 robot control interface
- **Production**: Work order and scheduling management

## Authentication

Most endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your-token>
```

## Rate Limiting

API requests are rate-limited based on endpoint category:
- Standard endpoints: 100 requests/minute
- Authentication: 10 requests/minute
- Heavy computation: 20 requests/minute
- Admin operations: 50 requests/minute
        """,
        "version": "3.0.0",
        "contact": {
            "name": "LEGO Factory Support",
            "email": "support@lego-factory.local"
        },
        "license": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        }
    },
    "servers": [
        {
            "url": "http://localhost:5000",
            "description": "Development server"
        },
        {
            "url": "https://lego-factory.example.com",
            "description": "Production server"
        }
    ],
    "tags": [
        {"name": "Health", "description": "Health check endpoints"},
        {"name": "SCADA Tags", "description": "SCADA tag management operations"},
        {"name": "Historian", "description": "Time-series data operations"},
        {"name": "Alarms", "description": "Alarm management operations"},
        {"name": "ML Inference", "description": "Machine learning inference operations"},
        {"name": "QMS NCR", "description": "Non-Conformance Report management"},
        {"name": "QMS CAPA", "description": "Corrective/Preventive Action management"},
        {"name": "Robotics", "description": "Robot control operations"},
        {"name": "Production", "description": "Production and work order management"}
    ],
    "paths": {
        "/health": {
            "get": {
                "tags": ["Health"],
                "summary": "Health check",
                "description": "Returns the health status of the application and its dependencies.",
                "operationId": "healthCheck",
                "responses": {
                    "200": {
                        "description": "Application is healthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"}
                            }
                        }
                    },
                    "503": {
                        "description": "Application is unhealthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/api/scada/tags": {
            "get": {
                "tags": ["SCADA Tags"],
                "summary": "List all tags",
                "description": "Retrieves a paginated list of SCADA tags.",
                "operationId": "listTags",
                "parameters": [
                    {"$ref": "#/components/parameters/PageParam"},
                    {"$ref": "#/components/parameters/PerPageParam"},
                    {
                        "name": "category",
                        "in": "query",
                        "schema": {"type": "string"},
                        "description": "Filter by tag category"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of tags",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "tags": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/Tag"}
                                        },
                                        "total": {"type": "integer"},
                                        "page": {"type": "integer"},
                                        "per_page": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                },
                "security": [{"bearerAuth": []}]
            }
        },
        "/api/scada/tags/{tag_id}": {
            "get": {
                "tags": ["SCADA Tags"],
                "summary": "Get tag value",
                "description": "Retrieves the current value of a specific tag.",
                "operationId": "getTag",
                "parameters": [
                    {
                        "name": "tag_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Tag identifier"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Tag value",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TagValue"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"}
                },
                "security": [{"bearerAuth": []}]
            }
        },
        "/api/scada/tags/write": {
            "post": {
                "tags": ["SCADA Tags"],
                "summary": "Write tag value",
                "description": "Writes a value to a SCADA tag.",
                "operationId": "writeTag",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/TagWriteRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Write successful",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TagValue"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "404": {"$ref": "#/components/responses/NotFound"}
                },
                "security": [{"bearerAuth": []}]
            }
        },
        "/api/scada/alarms/active": {
            "get": {
                "tags": ["Alarms"],
                "summary": "Get active alarms",
                "description": "Retrieves all currently active alarms.",
                "operationId": "getActiveAlarms",
                "parameters": [
                    {
                        "name": "priority",
                        "in": "query",
                        "schema": {"type": "integer", "minimum": 1, "maximum": 5},
                        "description": "Filter by priority (1=Emergency, 5=Diagnostic)"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of active alarms",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/AlarmEvent"}
                                }
                            }
                        }
                    }
                },
                "security": [{"bearerAuth": []}]
            }
        },
        "/api/scada/alarms/{alarm_id}/acknowledge": {
            "post": {
                "tags": ["Alarms"],
                "summary": "Acknowledge alarm",
                "description": "Acknowledges an active alarm.",
                "operationId": "acknowledgeAlarm",
                "parameters": [
                    {
                        "name": "alarm_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/AcknowledgeRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Alarm acknowledged"},
                    "404": {"$ref": "#/components/responses/NotFound"}
                },
                "security": [{"bearerAuth": []}]
            }
        },
        "/api/historian/trend": {
            "get": {
                "tags": ["Historian"],
                "summary": "Get trend data",
                "description": "Retrieves aggregated trend data for specified tags.",
                "operationId": "getTrendData",
                "parameters": [
                    {
                        "name": "tags",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Comma-separated list of tag IDs"
                    },
                    {
                        "name": "start",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string", "format": "date-time"}
                    },
                    {
                        "name": "end",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string", "format": "date-time"}
                    },
                    {
                        "name": "aggregation",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["avg", "min", "max", "sum", "count"]
                        },
                        "description": "Aggregation function"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Trend data",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TrendResponse"}
                            }
                        }
                    }
                },
                "security": [{"bearerAuth": []}]
            }
        },
        "/api/ml/inference/predict": {
            "post": {
                "tags": ["ML Inference"],
                "summary": "Run prediction",
                "description": "Runs ML inference on sensor data for anomaly detection.",
                "operationId": "runPrediction",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/PredictionRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Prediction results",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PredictionResponse"}
                            }
                        }
                    },
                    "503": {
                        "description": "Model not loaded"
                    }
                },
                "security": [{"bearerAuth": []}]
            }
        },
        "/api/qms/ncrs": {
            "get": {
                "tags": ["QMS NCR"],
                "summary": "List NCRs",
                "description": "Retrieves a paginated list of Non-Conformance Reports.",
                "operationId": "listNCRs",
                "parameters": [
                    {"$ref": "#/components/parameters/PageParam"},
                    {"$ref": "#/components/parameters/PerPageParam"},
                    {
                        "name": "status",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["draft", "open", "disposition_approved", "closed"]
                        }
                    },
                    {
                        "name": "severity",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["critical", "major", "minor"]
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of NCRs",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ncrs": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/NCR"}
                                        },
                                        "total": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                },
                "security": [{"bearerAuth": []}]
            },
            "post": {
                "tags": ["QMS NCR"],
                "summary": "Create NCR",
                "description": "Creates a new Non-Conformance Report.",
                "operationId": "createNCR",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/NCRCreateRequest"}
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "NCR created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/NCR"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"}
                },
                "security": [{"bearerAuth": []}]
            }
        },
        "/api/robotics/robots/{robot_id}/state": {
            "get": {
                "tags": ["Robotics"],
                "summary": "Get robot state",
                "description": "Retrieves the current state of a robot.",
                "operationId": "getRobotState",
                "parameters": [
                    {
                        "name": "robot_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Robot state",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RobotState"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"}
                },
                "security": [{"bearerAuth": []}]
            }
        },
        "/api/robotics/robots/{robot_id}/move": {
            "post": {
                "tags": ["Robotics"],
                "summary": "Send move command",
                "description": "Sends a move command to a robot.",
                "operationId": "sendMoveCommand",
                "parameters": [
                    {
                        "name": "robot_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/MoveCommand"}
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Command sent"},
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "503": {"description": "Robot not connected"}
                },
                "security": [{"bearerAuth": []}]
            }
        }
    },
    "components": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT"
            }
        },
        "parameters": {
            "PageParam": {
                "name": "page",
                "in": "query",
                "schema": {"type": "integer", "minimum": 1, "default": 1},
                "description": "Page number"
            },
            "PerPageParam": {
                "name": "per_page",
                "in": "query",
                "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                "description": "Items per page"
            }
        },
        "responses": {
            "NotFound": {
                "description": "Resource not found",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "BadRequest": {
                "description": "Invalid request",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "Unauthorized": {
                "description": "Authentication required",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                }
            }
        },
        "schemas": {
            "Error": {
                "type": "object",
                "properties": {
                    "error": {"type": "string"},
                    "message": {"type": "string"},
                    "details": {"type": "object"}
                },
                "required": ["error", "message"]
            },
            "HealthResponse": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["healthy", "unhealthy"]},
                    "timestamp": {"type": "string", "format": "date-time"},
                    "version": {"type": "string"},
                    "components": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "latency_ms": {"type": "number"}
                            }
                        }
                    }
                }
            },
            "Tag": {
                "type": "object",
                "properties": {
                    "tag_id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "data_type": {"type": "string"},
                    "engineering_units": {"type": "string"},
                    "category": {"type": "string"}
                }
            },
            "TagValue": {
                "type": "object",
                "properties": {
                    "tag_id": {"type": "string"},
                    "value": {"oneOf": [{"type": "number"}, {"type": "string"}, {"type": "boolean"}]},
                    "quality": {"type": "integer"},
                    "timestamp": {"type": "string", "format": "date-time"}
                }
            },
            "TagWriteRequest": {
                "type": "object",
                "required": ["tag_id", "value"],
                "properties": {
                    "tag_id": {"type": "string"},
                    "value": {"oneOf": [{"type": "number"}, {"type": "string"}, {"type": "boolean"}]},
                    "quality": {"type": "integer", "default": 192}
                }
            },
            "AlarmEvent": {
                "type": "object",
                "properties": {
                    "instance_id": {"type": "string"},
                    "alarm_id": {"type": "string"},
                    "tag_id": {"type": "string"},
                    "tag_name": {"type": "string"},
                    "alarm_type": {"type": "string"},
                    "priority": {"type": "integer"},
                    "status": {"type": "string"},
                    "message": {"type": "string"},
                    "value": {"type": "number"},
                    "limit_value": {"type": "number"},
                    "timestamp": {"type": "string", "format": "date-time"},
                    "is_acknowledged": {"type": "boolean"},
                    "acknowledged_by": {"type": "string"},
                    "acknowledged_at": {"type": "string", "format": "date-time"}
                }
            },
            "AcknowledgeRequest": {
                "type": "object",
                "required": ["acknowledged_by"],
                "properties": {
                    "acknowledged_by": {"type": "string"},
                    "notes": {"type": "string"}
                }
            },
            "TrendResponse": {
                "type": "object",
                "properties": {
                    "tags": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "time": {"type": "string", "format": "date-time"},
                                    "value": {"type": "number"}
                                }
                            }
                        }
                    },
                    "start": {"type": "string", "format": "date-time"},
                    "end": {"type": "string", "format": "date-time"},
                    "aggregation": {"type": "string"}
                }
            },
            "PredictionRequest": {
                "type": "object",
                "required": ["sensor_data"],
                "properties": {
                    "sensor_data": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "number"}
                        },
                        "description": "2D array of sensor values [sequence_length x features]"
                    },
                    "tag_id": {"type": "string"}
                }
            },
            "PredictionResponse": {
                "type": "object",
                "properties": {
                    "inference_id": {"type": "string"},
                    "fingerprint": {
                        "type": "array",
                        "items": {"type": "number"}
                    },
                    "classification": {
                        "type": "array",
                        "items": {"type": "number"}
                    },
                    "anomaly_score": {"type": "number"},
                    "anomaly_detected": {"type": "boolean"},
                    "timestamp": {"type": "string", "format": "date-time"}
                }
            },
            "NCR": {
                "type": "object",
                "properties": {
                    "ncr_number": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string"},
                    "severity": {"type": "string"},
                    "disposition": {"type": "string"},
                    "detected_by": {"type": "string"},
                    "created_at": {"type": "string", "format": "date-time"},
                    "closed_at": {"type": "string", "format": "date-time"}
                }
            },
            "NCRCreateRequest": {
                "type": "object",
                "required": ["title", "description", "detected_by"],
                "properties": {
                    "title": {"type": "string", "maxLength": 200},
                    "description": {"type": "string"},
                    "detected_by": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                    "category": {"type": "string"},
                    "product_id": {"type": "string"},
                    "lot_number": {"type": "string"}
                }
            },
            "RobotState": {
                "type": "object",
                "properties": {
                    "robot_id": {"type": "string"},
                    "connected": {"type": "boolean"},
                    "mode": {"type": "string"},
                    "position": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"},
                            "roll": {"type": "number"},
                            "pitch": {"type": "number"},
                            "yaw": {"type": "number"}
                        }
                    },
                    "joints": {
                        "type": "array",
                        "items": {"type": "number"}
                    },
                    "error_code": {"type": "integer"},
                    "last_update": {"type": "string", "format": "date-time"}
                }
            },
            "MoveCommand": {
                "type": "object",
                "required": ["x", "y", "z"],
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "z": {"type": "number"},
                    "roll": {"type": "number", "default": 0},
                    "pitch": {"type": "number", "default": 0},
                    "yaw": {"type": "number", "default": 0},
                    "speed": {"type": "number", "default": 0.1},
                    "simulation": {"type": "boolean", "default": False}
                }
            }
        }
    }
}


# Blueprint for serving OpenAPI spec
openapi_bp = Blueprint('openapi', __name__)


@openapi_bp.route('/openapi.json')
def get_openapi_spec():
    """Serve the OpenAPI specification as JSON."""
    return jsonify(OPENAPI_SPEC)


def init_swagger_ui(app):
    """Initialize Swagger UI for the application."""
    SWAGGER_URL = '/api/docs'
    API_URL = '/openapi.json'

    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={
            'app_name': "LEGO Factory v3 API",
            'validatorUrl': None,
            'displayRequestDuration': True,
            'docExpansion': 'list',
            'defaultModelsExpandDepth': 2,
            'persistAuthorization': True
        }
    )

    app.register_blueprint(openapi_bp)
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
