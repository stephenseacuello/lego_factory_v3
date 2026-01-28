"""
Pydantic schemas for TinyG controller API endpoints.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ConnectRequest(BaseModel):
    """Request to connect to TinyG controller."""

    port: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Serial port path (e.g., '/dev/ttyUSB0', 'COM3')"
    )
    baud: int = Field(
        default=115200,
        ge=9600,
        le=921600,
        description="Baud rate for serial communication"
    )
    machine_id: Optional[str] = Field(
        None,
        max_length=64,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Optional machine identifier"
    )

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: str) -> str:
        """Validate serial port path."""
        # Basic validation - must start with expected prefixes
        valid_prefixes = ("/dev/tty", "/dev/cu.", "COM", "/dev/serial")
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(
                f"Invalid serial port. Must start with one of: {valid_prefixes}"
            )
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "port": "/dev/ttyUSB0",
                "baud": 115200,
                "machine_id": "mill-1"
            }
        }


class PollingRequest(BaseModel):
    """Request to start/configure status polling."""

    interval: float = Field(
        default=0.1,
        ge=0.01,
        le=10.0,
        description="Polling interval in seconds"
    )
    experiment_name: str = Field(
        default="",
        max_length=128,
        description="Name of experiment for logging"
    )
    trial_number: Optional[int] = Field(
        None,
        ge=0,
        le=99999,
        description="Trial number for logging"
    )
    log_directory: Optional[str] = Field(
        None,
        max_length=512,
        description="Custom log directory path"
    )

    @field_validator("log_directory")
    @classmethod
    def validate_log_directory(cls, v: Optional[str]) -> Optional[str]:
        """Validate log directory path."""
        if v and ".." in v:
            raise ValueError("Path traversal not allowed in log directory")
        return v


class AutoReconnectConfig(BaseModel):
    """Configuration for auto-reconnect behavior."""

    enabled: bool = Field(
        default=True,
        description="Enable/disable auto-reconnect"
    )
    max_attempts: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum reconnection attempts"
    )
    base_delay: float = Field(
        default=1.0,
        ge=0.5,
        le=60.0,
        description="Initial delay between attempts in seconds"
    )
    max_delay: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Maximum delay between attempts in seconds"
    )

    @field_validator("max_delay")
    @classmethod
    def validate_max_delay(cls, v: float, info) -> float:
        """Ensure max_delay >= base_delay."""
        base_delay = info.data.get("base_delay", 1.0)
        if v < base_delay:
            raise ValueError("max_delay must be >= base_delay")
        return v


class DryRunPositionRequest(BaseModel):
    """Request to set simulated position in dry run mode."""

    x: Optional[float] = Field(
        None,
        ge=-10000,
        le=10000,
        description="X position in mm"
    )
    y: Optional[float] = Field(
        None,
        ge=-10000,
        le=10000,
        description="Y position in mm"
    )
    z: Optional[float] = Field(
        None,
        ge=-10000,
        le=10000,
        description="Z position in mm"
    )


class PositionToleranceRequest(BaseModel):
    """Request to set position tolerance for feed hold verification."""

    tolerance: float = Field(
        ...,
        ge=0.001,
        le=10.0,
        description="Position tolerance in mm"
    )


class TinyGStatus(BaseModel):
    """TinyG controller status response."""

    connected: bool
    port: Optional[str] = None
    machine_id: Optional[str] = None
    polling: bool = False
    recording: bool = False
    poll_count: int = 0
    bytes_written: int = 0
    dry_run: bool = False
    auto_reconnect: bool = True
    reconnecting: bool = False


class MachinePosition(BaseModel):
    """Machine position data."""

    wx: float = Field(..., description="Work X position")
    wy: float = Field(..., description="Work Y position")
    wz: float = Field(..., description="Work Z position")
    mx: Optional[float] = Field(None, description="Machine X position")
    my: Optional[float] = Field(None, description="Machine Y position")
    mz: Optional[float] = Field(None, description="Machine Z position")
    feed: Optional[float] = Field(None, description="Feed rate")
    vel: Optional[float] = Field(None, description="Velocity")
    stat: Optional[int] = Field(None, description="Machine state")
    momo: Optional[int] = Field(None, description="Motion mode")
    sps: Optional[float] = Field(None, description="Spindle speed")
    line: Optional[int] = Field(None, description="G-code line number")
