"""
Common Pydantic schemas used across multiple API endpoints.
"""

from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Detailed error information."""

    message: str = Field(..., description="Human-readable error message")
    code: str = Field(..., description="Machine-readable error code")
    field: Optional[str] = Field(None, description="Field that caused the error")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    success: bool = Field(default=False, description="Always false for errors")
    error: ErrorDetail = Field(..., description="Error details")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "message": "Invalid G-code command",
                    "code": "INVALID_GCODE",
                    "field": "command",
                    "details": {"received": "G999", "allowed": ["G0", "G1", "G2", "G3"]}
                }
            }
        }


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper.

    Generic type T represents the data payload type.
    """

    success: bool = Field(default=True, description="Whether the request succeeded")
    message: Optional[str] = Field(None, description="Optional status message")
    data: Optional[T] = Field(None, description="Response data payload")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": 1, "status": "active"}
            }
        }


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    per_page: int = Field(default=50, ge=1, le=1000, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: Optional[str] = Field(
        default="asc",
        pattern="^(asc|desc)$",
        description="Sort order: 'asc' or 'desc'"
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    success: bool = True
    items: List[T] = Field(default_factory=list)
    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page")
    per_page: int = Field(..., ge=1, description="Items per page")
    pages: int = Field(..., ge=0, description="Total number of pages")


class HealthStatus(BaseModel):
    """Health check response."""

    status: str = Field(..., pattern="^(healthy|degraded|unhealthy)$")
    version: str = Field(..., description="Application version")
    services: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Status of dependent services"
    )
    uptime_seconds: float = Field(..., ge=0, description="Application uptime")
