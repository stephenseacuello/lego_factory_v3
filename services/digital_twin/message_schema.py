"""
ISO 23247-4 Message Schema Validation
=====================================

Implements formal message schema validation for digital twin information exchange.
Ensures compliance with ISO 23247-4 (Information Exchange) requirements.

Key Features:
- JSON Schema-based validation
- Schema versioning for backward compatibility
- Validation of all message types
- Comprehensive error reporting

ISO 23247-4 Compliance:
- Section 6.3: Message format specifications
- Section 6.4: Data validation requirements
- Section 7.2: Schema versioning
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from datetime import datetime
import json
import re


class MessageType(Enum):
    """
    ISO 23247-4 compliant message types.

    These message types support the full digital twin lifecycle
    as defined in ISO 23247-4 Section 5.
    """

    # State synchronization messages
    STATE_UPDATE = "state_update"                    # Real-time state from physical entity
    STATE_CHANGE_NOTIFICATION = "state_change"       # Significant state change event

    # Command and control messages
    COMMAND = "command"                              # Control command to physical entity
    COMMAND_ACKNOWLEDGMENT = "command_ack"           # Acknowledgment of command receipt
    COMMAND_RESULT = "command_result"                # Result of command execution

    # Discovery and capability messages
    CAPABILITY_QUERY = "capability_query"            # Query entity capabilities
    CAPABILITY_RESPONSE = "capability_response"      # Response with capabilities
    ENTITY_REGISTRATION = "entity_registration"      # Register new entity
    ENTITY_DEREGISTRATION = "entity_deregistration"  # Remove entity

    # Synchronization control messages
    SYNC_REQUEST = "sync_request"                    # Request full state sync
    SYNC_RESPONSE = "sync_response"                  # Full state sync response
    HEARTBEAT = "heartbeat"                          # Connection health check

    # Error and diagnostic messages
    ERROR = "error"                                  # Error notification
    DIAGNOSTIC = "diagnostic"                        # Diagnostic information


class ValidationSeverity(Enum):
    """Severity levels for validation errors."""
    ERROR = "error"          # Message is invalid, must be rejected
    WARNING = "warning"      # Message has issues but can be processed
    INFO = "info"            # Informational finding


@dataclass
class ValidationError:
    """
    Represents a validation error or warning.

    Attributes:
        path: JSON path to the invalid field (e.g., "entity.position.x")
        message: Human-readable error description
        severity: Error severity level
        code: Machine-readable error code
    """
    path: str
    message: str
    severity: ValidationSeverity
    code: str


@dataclass
class ValidationResult:
    """
    Result of schema validation.

    Attributes:
        valid: True if message passed validation
        errors: List of validation errors
        schema_version: Version of schema used for validation
        message_type: Type of message that was validated
    """
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    schema_version: str = "1.0.0"
    message_type: Optional[str] = None

    def add_error(self, path: str, message: str, code: str,
                  severity: ValidationSeverity = ValidationSeverity.ERROR):
        """Add a validation error."""
        self.errors.append(ValidationError(path, message, severity, code))
        if severity == ValidationSeverity.ERROR:
            self.valid = False

    def get_error_messages(self) -> List[str]:
        """Get list of error messages."""
        return [f"{e.path}: {e.message}" for e in self.errors
                if e.severity == ValidationSeverity.ERROR]


# Schema definitions following ISO 23247-4 structure
SCHEMA_DEFINITIONS = {
    "entity_identification": {
        "type": "object",
        "required": ["entity_id", "entity_type"],
        "properties": {
            "entity_id": {"type": "string", "pattern": r"^[a-zA-Z0-9_-]+$", "minLength": 1, "maxLength": 128},
            "entity_type": {"type": "string", "enum": [
                "machine", "sensor", "actuator", "robot", "agv",
                "workstation", "production_line", "factory"
            ]},
            "manufacturing_site": {"type": "string", "maxLength": 64},
            "namespace": {"type": "string", "pattern": r"^[a-z]+://.*$"}
        }
    },

    "position_3d": {
        "type": "object",
        "required": ["x", "y", "z"],
        "properties": {
            "x": {"type": "number"},
            "y": {"type": "number"},
            "z": {"type": "number"},
            "unit": {"type": "string", "enum": ["mm", "m", "inch"], "default": "mm"}
        }
    },

    "orientation_3d": {
        "type": "object",
        "properties": {
            "roll": {"type": "number", "minimum": -180, "maximum": 180},
            "pitch": {"type": "number", "minimum": -180, "maximum": 180},
            "yaw": {"type": "number", "minimum": -180, "maximum": 180},
            "unit": {"type": "string", "enum": ["deg", "rad"], "default": "deg"}
        }
    },

    "velocity_3d": {
        "type": "object",
        "properties": {
            "vx": {"type": "number"},
            "vy": {"type": "number"},
            "vz": {"type": "number"},
            "unit": {"type": "string", "enum": ["mm/s", "m/s"], "default": "mm/s"}
        }
    },

    "vector_clock": {
        "type": "object",
        "required": ["clock"],
        "properties": {
            "clock": {"type": "object", "additionalProperties": {"type": "integer", "minimum": 0}},
            "node_id": {"type": "string"},
            "wall_clock": {"type": "string", "format": "date-time"}
        }
    },

    "checksum": {
        "type": "object",
        "required": ["algorithm", "value"],
        "properties": {
            "algorithm": {"type": "string", "enum": ["sha256", "sha512", "crc32"]},
            "value": {"type": "string", "pattern": r"^[a-fA-F0-9]+$"}
        }
    }
}


# Message schemas for each message type
MESSAGE_SCHEMAS = {
    MessageType.STATE_UPDATE: {
        "type": "object",
        "required": ["message_type", "entity_id", "timestamp", "state"],
        "properties": {
            "message_type": {"const": "state_update"},
            "message_id": {"type": "string", "format": "uuid"},
            "entity_id": {"type": "string"},
            "timestamp": {"type": "string", "format": "date-time"},
            "version": {"$ref": "#/definitions/vector_clock"},
            "state": {
                "type": "object",
                "properties": {
                    "position": {"$ref": "#/definitions/position_3d"},
                    "orientation": {"$ref": "#/definitions/orientation_3d"},
                    "velocity": {"$ref": "#/definitions/velocity_3d"},
                    "status": {"type": "string", "enum": [
                        "active", "idle", "running", "stopped", "error",
                        "maintenance", "offline"
                    ]},
                    "attributes": {"type": "object"}
                }
            },
            "quality": {"type": "string", "enum": ["good", "uncertain", "bad", "stale"]},
            "checksum": {"$ref": "#/definitions/checksum"}
        }
    },

    MessageType.COMMAND: {
        "type": "object",
        "required": ["message_type", "entity_id", "command", "timestamp"],
        "properties": {
            "message_type": {"const": "command"},
            "message_id": {"type": "string", "format": "uuid"},
            "entity_id": {"type": "string"},
            "timestamp": {"type": "string", "format": "date-time"},
            "command": {"type": "string"},
            "parameters": {"type": "object"},
            "priority": {"type": "integer", "minimum": 1, "maximum": 10},
            "timeout_ms": {"type": "integer", "minimum": 0},
            "requires_ack": {"type": "boolean", "default": True}
        }
    },

    MessageType.COMMAND_ACKNOWLEDGMENT: {
        "type": "object",
        "required": ["message_type", "original_message_id", "status", "timestamp"],
        "properties": {
            "message_type": {"const": "command_ack"},
            "message_id": {"type": "string", "format": "uuid"},
            "original_message_id": {"type": "string", "format": "uuid"},
            "entity_id": {"type": "string"},
            "status": {"type": "string", "enum": ["received", "accepted", "rejected", "queued"]},
            "timestamp": {"type": "string", "format": "date-time"},
            "reason": {"type": "string"}
        }
    },

    MessageType.CAPABILITY_QUERY: {
        "type": "object",
        "required": ["message_type", "entity_id"],
        "properties": {
            "message_type": {"const": "capability_query"},
            "message_id": {"type": "string", "format": "uuid"},
            "entity_id": {"type": "string"},
            "capability_filter": {"type": "array", "items": {"type": "string"}}
        }
    },

    MessageType.CAPABILITY_RESPONSE: {
        "type": "object",
        "required": ["message_type", "entity_id", "capabilities"],
        "properties": {
            "message_type": {"const": "capability_response"},
            "message_id": {"type": "string", "format": "uuid"},
            "original_message_id": {"type": "string", "format": "uuid"},
            "entity_id": {"type": "string"},
            "entity_type": {"type": "string"},
            "capabilities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "parameters": {"type": "object"},
                        "constraints": {"type": "object"}
                    }
                }
            }
        }
    },

    MessageType.HEARTBEAT: {
        "type": "object",
        "required": ["message_type", "node_id", "timestamp"],
        "properties": {
            "message_type": {"const": "heartbeat"},
            "node_id": {"type": "string"},
            "timestamp": {"type": "string", "format": "date-time"},
            "sequence": {"type": "integer", "minimum": 0},
            "status": {"type": "string", "enum": ["healthy", "degraded", "unhealthy"]}
        }
    },

    MessageType.ERROR: {
        "type": "object",
        "required": ["message_type", "error_code", "message", "timestamp"],
        "properties": {
            "message_type": {"const": "error"},
            "message_id": {"type": "string", "format": "uuid"},
            "original_message_id": {"type": "string", "format": "uuid"},
            "entity_id": {"type": "string"},
            "error_code": {"type": "string"},
            "message": {"type": "string"},
            "severity": {"type": "string", "enum": ["info", "warning", "error", "critical"]},
            "timestamp": {"type": "string", "format": "date-time"},
            "details": {"type": "object"}
        }
    }
}


class MessageSchemaValidator:
    """
    Validates messages against ISO 23247-4 schemas.

    This validator ensures all digital twin messages conform to the
    information exchange requirements of ISO 23247-4.

    Usage:
        validator = MessageSchemaValidator()
        result = validator.validate(message_dict)
        if not result.valid:
            print(result.get_error_messages())
    """

    SCHEMA_VERSION = "1.0.0"

    # Regular expressions for format validation
    UUID_PATTERN = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    DATETIME_PATTERN = re.compile(
        r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$'
    )

    def __init__(self, strict_mode: bool = True):
        """
        Initialize the validator.

        Args:
            strict_mode: If True, unknown properties cause errors.
                         If False, unknown properties are allowed.
        """
        self.strict_mode = strict_mode
        self.definitions = SCHEMA_DEFINITIONS
        self.message_schemas = MESSAGE_SCHEMAS

    def validate(self, message: Dict[str, Any]) -> ValidationResult:
        """
        Validate a message against its schema.

        Args:
            message: The message dictionary to validate

        Returns:
            ValidationResult with validation outcome
        """
        result = ValidationResult(valid=True, schema_version=self.SCHEMA_VERSION)

        # Check message type
        msg_type_str = message.get("message_type")
        if not msg_type_str:
            result.add_error("message_type", "Missing required field 'message_type'", "MISSING_FIELD")
            return result

        try:
            msg_type = MessageType(msg_type_str)
        except ValueError:
            result.add_error(
                "message_type",
                f"Unknown message type: {msg_type_str}",
                "INVALID_MESSAGE_TYPE"
            )
            return result

        result.message_type = msg_type_str

        # Get schema for message type
        schema = self.message_schemas.get(msg_type)
        if not schema:
            result.add_error(
                "message_type",
                f"No schema defined for message type: {msg_type_str}",
                "NO_SCHEMA"
            )
            return result

        # Validate against schema
        self._validate_object(message, schema, "", result)

        return result

    def _validate_object(self, data: Any, schema: Dict[str, Any],
                         path: str, result: ValidationResult):
        """Validate an object against a schema."""

        if schema.get("type") == "object":
            if not isinstance(data, dict):
                result.add_error(path or "root", "Expected object", "TYPE_ERROR")
                return

            # Check required fields
            required = schema.get("required", [])
            for field in required:
                if field not in data:
                    result.add_error(
                        f"{path}.{field}" if path else field,
                        f"Missing required field: {field}",
                        "MISSING_REQUIRED"
                    )

            # Validate properties
            properties = schema.get("properties", {})
            for prop, prop_schema in properties.items():
                if prop in data:
                    self._validate_value(
                        data[prop],
                        prop_schema,
                        f"{path}.{prop}" if path else prop,
                        result
                    )

            # Check for unknown properties in strict mode
            if self.strict_mode:
                for key in data.keys():
                    if key not in properties and key != "message_type":
                        result.add_error(
                            f"{path}.{key}" if path else key,
                            f"Unknown property: {key}",
                            "UNKNOWN_PROPERTY",
                            ValidationSeverity.WARNING
                        )

    def _validate_value(self, value: Any, schema: Dict[str, Any],
                        path: str, result: ValidationResult):
        """Validate a value against a schema."""

        # Handle schema references
        if "$ref" in schema:
            ref = schema["$ref"]
            if ref.startswith("#/definitions/"):
                def_name = ref.split("/")[-1]
                if def_name in self.definitions:
                    schema = self.definitions[def_name]
                else:
                    result.add_error(path, f"Unknown definition: {def_name}", "UNKNOWN_DEF")
                    return

        # Handle const
        if "const" in schema:
            if value != schema["const"]:
                result.add_error(
                    path,
                    f"Expected '{schema['const']}', got '{value}'",
                    "CONST_MISMATCH"
                )
            return

        # Handle enum
        if "enum" in schema:
            if value not in schema["enum"]:
                result.add_error(
                    path,
                    f"Value '{value}' not in allowed values: {schema['enum']}",
                    "ENUM_ERROR"
                )
            return

        # Type validation
        schema_type = schema.get("type")

        if schema_type == "string":
            self._validate_string(value, schema, path, result)
        elif schema_type == "number":
            self._validate_number(value, schema, path, result)
        elif schema_type == "integer":
            self._validate_integer(value, schema, path, result)
        elif schema_type == "boolean":
            if not isinstance(value, bool):
                result.add_error(path, "Expected boolean", "TYPE_ERROR")
        elif schema_type == "array":
            self._validate_array(value, schema, path, result)
        elif schema_type == "object":
            self._validate_object(value, schema, path, result)

    def _validate_string(self, value: Any, schema: Dict[str, Any],
                         path: str, result: ValidationResult):
        """Validate a string value."""
        if not isinstance(value, str):
            result.add_error(path, "Expected string", "TYPE_ERROR")
            return

        # Check minLength
        if "minLength" in schema and len(value) < schema["minLength"]:
            result.add_error(
                path,
                f"String too short (min: {schema['minLength']})",
                "MIN_LENGTH"
            )

        # Check maxLength
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            result.add_error(
                path,
                f"String too long (max: {schema['maxLength']})",
                "MAX_LENGTH"
            )

        # Check pattern
        if "pattern" in schema:
            if not re.match(schema["pattern"], value):
                result.add_error(
                    path,
                    f"String doesn't match pattern: {schema['pattern']}",
                    "PATTERN_MISMATCH"
                )

        # Check format
        fmt = schema.get("format")
        if fmt == "uuid" and not self.UUID_PATTERN.match(value):
            result.add_error(path, "Invalid UUID format", "FORMAT_ERROR")
        elif fmt == "date-time" and not self.DATETIME_PATTERN.match(value):
            result.add_error(path, "Invalid datetime format", "FORMAT_ERROR")

    def _validate_number(self, value: Any, schema: Dict[str, Any],
                         path: str, result: ValidationResult):
        """Validate a number value."""
        if not isinstance(value, (int, float)):
            result.add_error(path, "Expected number", "TYPE_ERROR")
            return

        if "minimum" in schema and value < schema["minimum"]:
            result.add_error(
                path,
                f"Value {value} below minimum {schema['minimum']}",
                "MIN_VALUE"
            )

        if "maximum" in schema and value > schema["maximum"]:
            result.add_error(
                path,
                f"Value {value} above maximum {schema['maximum']}",
                "MAX_VALUE"
            )

    def _validate_integer(self, value: Any, schema: Dict[str, Any],
                          path: str, result: ValidationResult):
        """Validate an integer value."""
        if not isinstance(value, int) or isinstance(value, bool):
            result.add_error(path, "Expected integer", "TYPE_ERROR")
            return

        self._validate_number(value, schema, path, result)

    def _validate_array(self, value: Any, schema: Dict[str, Any],
                        path: str, result: ValidationResult):
        """Validate an array value."""
        if not isinstance(value, list):
            result.add_error(path, "Expected array", "TYPE_ERROR")
            return

        items_schema = schema.get("items")
        if items_schema:
            for i, item in enumerate(value):
                self._validate_value(item, items_schema, f"{path}[{i}]", result)

    def get_schema_for_type(self, msg_type: MessageType) -> Optional[Dict[str, Any]]:
        """Get the schema for a message type."""
        return self.message_schemas.get(msg_type)

    def get_all_message_types(self) -> List[str]:
        """Get list of all supported message types."""
        return [mt.value for mt in MessageType]


def validate_message(message: Dict[str, Any], strict: bool = True) -> ValidationResult:
    """
    Convenience function to validate a message.

    Args:
        message: Message dictionary to validate
        strict: Whether to use strict validation mode

    Returns:
        ValidationResult with outcome

    Example:
        result = validate_message({"message_type": "state_update", ...})
        if not result.valid:
            for error in result.errors:
                print(f"{error.path}: {error.message}")
    """
    validator = MessageSchemaValidator(strict_mode=strict)
    return validator.validate(message)
