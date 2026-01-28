"""
Pydantic Validation Schemas for Flask CNC SCADA API.

These schemas provide request/response validation for API endpoints.
"""

from api.schemas.gcode import (
    GCodeCommand,
    GCodeFileRequest,
    JogRequest,
    ZeroAxisRequest,
)
from api.schemas.tinyg import (
    ConnectRequest,
    PollingRequest,
    AutoReconnectConfig,
    DryRunPositionRequest,
)
from api.schemas.sensor import (
    SensorDataRequest,
    SensorConfigRequest,
)
from api.schemas.common import (
    APIResponse,
    ErrorResponse,
    PaginationParams,
)

__all__ = [
    # G-code schemas
    "GCodeCommand",
    "GCodeFileRequest",
    "JogRequest",
    "ZeroAxisRequest",
    # TinyG schemas
    "ConnectRequest",
    "PollingRequest",
    "AutoReconnectConfig",
    "DryRunPositionRequest",
    # Sensor schemas
    "SensorDataRequest",
    "SensorConfigRequest",
    # Common schemas
    "APIResponse",
    "ErrorResponse",
    "PaginationParams",
]
