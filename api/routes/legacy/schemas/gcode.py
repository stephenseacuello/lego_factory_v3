"""
Pydantic schemas for G-code related API endpoints.
"""

import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# Valid G-code pattern - allows G/M codes, coordinates, feed rates, etc.
GCODE_PATTERN = re.compile(
    r'^[GMNOXYZIJKFSPRTQHLD][-+]?\d*\.?\d*'
    r'(\s*[GMNOXYZIJKFSPRTQHLD][-+]?\d*\.?\d*)*'
    r'(\s*\(.*\))?$',  # Allow comments in parentheses
    re.IGNORECASE
)


class GCodeCommand(BaseModel):
    """Single G-code command for execution."""

    command: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="G-code command to execute (e.g., 'G0 X10 Y20')"
    )
    priority: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Command priority (1=lowest, 10=highest)"
    )

    @field_validator("command")
    @classmethod
    def validate_gcode_format(cls, v: str) -> str:
        """Validate G-code command format."""
        v = v.strip()
        # Allow empty lines and pure comments
        if not v or v.startswith("(") or v.startswith(";"):
            return v
        # Basic validation - must start with valid letter
        if not v[0].upper() in "GMNOXYZIJKFSPRTQHLD%!":
            raise ValueError(f"Invalid G-code command: must start with G, M, N, X, Y, Z, etc.")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "command": "G0 X10 Y20 Z5",
                "priority": 1
            }
        }


class GCodeFileRequest(BaseModel):
    """Request to load/run a G-code file."""

    filepath: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="Path to G-code file"
    )
    validate_only: bool = Field(
        default=False,
        description="Only validate, don't execute"
    )
    dry_run: bool = Field(
        default=False,
        description="Simulate execution without sending to machine"
    )

    @field_validator("filepath")
    @classmethod
    def validate_filepath(cls, v: str) -> str:
        """Validate filepath for security."""
        # Prevent path traversal attacks
        if ".." in v:
            raise ValueError("Path traversal not allowed")
        # Must have valid G-code extension
        valid_extensions = (".nc", ".gcode", ".ngc", ".tap", ".txt")
        if not v.lower().endswith(valid_extensions):
            raise ValueError(f"Invalid file extension. Allowed: {valid_extensions}")
        return v


class JogRequest(BaseModel):
    """Request to jog the machine."""

    axis: str = Field(
        ...,
        pattern="^[XYZxyz]$",
        description="Axis to jog (X, Y, or Z)"
    )
    distance: float = Field(
        ...,
        ge=-1000,
        le=1000,
        description="Distance to jog in mm (positive or negative)"
    )
    speed: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Feed rate in mm/min"
    )

    @field_validator("axis")
    @classmethod
    def normalize_axis(cls, v: str) -> str:
        """Normalize axis to uppercase."""
        return v.upper()

    class Config:
        json_schema_extra = {
            "example": {
                "axis": "X",
                "distance": 10.0,
                "speed": 1000
            }
        }


class ZeroAxisRequest(BaseModel):
    """Request to zero work coordinates."""

    axis: str = Field(
        ...,
        pattern="^(X|Y|Z|ALL|x|y|z|all)$",
        description="Axis to zero (X, Y, Z, or ALL)"
    )

    @field_validator("axis")
    @classmethod
    def normalize_axis(cls, v: str) -> str:
        """Normalize axis to uppercase."""
        return v.upper()

    class Config:
        json_schema_extra = {
            "example": {
                "axis": "ALL"
            }
        }


class FeedHoldResumeRequest(BaseModel):
    """Request to resume from feed hold."""

    force: bool = Field(
        default=False,
        description="Force resume even if position verification fails"
    )
    verify_position: bool = Field(
        default=True,
        description="Verify machine position before resuming"
    )


class GCodeLineInfo(BaseModel):
    """Information about a single G-code line."""

    line_number: int = Field(..., ge=0)
    command: str
    motion_mode: Optional[str] = None
    target_position: Optional[dict] = None
    feed_rate: Optional[float] = None
    is_rapid: bool = False
    is_arc: bool = False
    estimated_time_seconds: Optional[float] = None


class GCodeFileAnalysis(BaseModel):
    """Analysis of a loaded G-code file."""

    filename: str
    total_lines: int = Field(..., ge=0)
    motion_lines: int = Field(..., ge=0)
    rapid_lines: int = Field(..., ge=0)
    arc_lines: int = Field(..., ge=0)
    tool_changes: int = Field(..., ge=0)
    spindle_commands: int = Field(..., ge=0)
    estimated_time_minutes: Optional[float] = None
    bounding_box: Optional[dict] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
