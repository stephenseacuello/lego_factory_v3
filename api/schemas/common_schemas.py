"""
LEGO Factory v3 - Common Pydantic Schemas
==========================================
Base schemas, pagination, error responses, and common utilities
used across all API endpoints.

This module provides foundational schemas that ensure consistent
API request/response patterns throughout the application.
"""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Generic type for paginated responses
T = TypeVar('T')


class BaseSchema(BaseModel):
    """
    Base schema with common configuration for all Pydantic models.

    Provides consistent JSON serialization settings and field aliasing
    support across all API schemas.
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class TimestampMixin(BaseModel):
    """
    Mixin for models that include timestamp fields.

    Provides created_at and updated_at fields with proper
    datetime serialization.
    """
    created_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the record was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the record was last updated"
    )


class AuditMixin(TimestampMixin):
    """
    Mixin for models that include audit tracking fields.

    Extends TimestampMixin with user tracking for creation
    and modification events.
    """
    created_by: Optional[str] = Field(
        default=None,
        max_length=100,
        description="User who created the record"
    )
    updated_by: Optional[str] = Field(
        default=None,
        max_length=100,
        description="User who last updated the record"
    )


# ============================================================================
# Pagination Schemas
# ============================================================================

class PaginationParams(BaseSchema):
    """
    Query parameters for paginated list endpoints.

    Provides standard pagination with sensible defaults and
    maximum limits to prevent excessive resource consumption.

    Attributes:
        limit: Maximum number of records to return (default: 100, max: 1000)
        offset: Number of records to skip (default: 0)
        sort_by: Field name to sort by (optional)
        sort_order: Sort direction, either 'asc' or 'desc' (default: 'asc')
    """
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of records to return"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of records to skip"
    )
    sort_by: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Field to sort by"
    )
    sort_order: str = Field(
        default="asc",
        pattern="^(asc|desc)$",
        description="Sort direction: 'asc' or 'desc'"
    )


class PaginatedResponse(BaseSchema, Generic[T]):
    """
    Generic paginated response wrapper.

    Wraps list data with pagination metadata for consistent
    API response formatting.

    Attributes:
        items: List of records for the current page
        total: Total number of records matching the query
        limit: Records per page used in this response
        offset: Number of records skipped
        has_more: Whether more records exist beyond this page
    """
    items: List[T]
    total: int = Field(ge=0, description="Total number of records")
    limit: int = Field(ge=1, description="Records per page")
    offset: int = Field(ge=0, description="Records skipped")
    has_more: bool = Field(description="Whether more records exist")


# ============================================================================
# Error Response Schemas
# ============================================================================

class FieldError(BaseSchema):
    """
    Field-level validation error detail.

    Provides specific information about validation failures
    for individual fields in a request.

    Attributes:
        field: Name of the field with the error
        message: Human-readable error description
        type: Error type classification (e.g., 'value_error', 'type_error')
    """
    field: str = Field(description="Field name that has the error")
    message: str = Field(description="Human-readable error message")
    type: str = Field(description="Error type classification")


class ErrorResponse(BaseSchema):
    """
    Standard API error response format.

    Provides consistent error formatting across all API endpoints
    with support for field-level validation errors.

    Attributes:
        error: Short error code (e.g., 'validation_error', 'not_found')
        message: Human-readable error description
        details: List of field-level errors for validation failures
        request_id: Optional request ID for tracing
    """
    error: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: Optional[List[FieldError]] = Field(
        default=None,
        description="Field-level validation errors"
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Request ID for tracing"
    )


class ValidationErrorResponse(ErrorResponse):
    """
    Specialized error response for validation failures.

    Pre-configured with validation-specific error code
    and always includes field-level details.
    """
    error: str = Field(default="validation_error")
    details: List[FieldError] = Field(
        default_factory=list,
        description="Field-level validation errors"
    )


# ============================================================================
# Success Response Schemas
# ============================================================================

class SuccessResponse(BaseSchema, Generic[T]):
    """
    Standard API success response wrapper.

    Wraps successful response data with consistent formatting
    and optional metadata.

    Attributes:
        success: Always True for success responses
        data: The actual response payload
        message: Optional success message
    """
    success: bool = Field(default=True)
    data: T
    message: Optional[str] = Field(default=None, description="Optional success message")


class MessageResponse(BaseSchema):
    """
    Simple message-only response for operations without data return.

    Used for DELETE operations, status changes, and other
    actions that don't return entity data.

    Attributes:
        message: Human-readable success message
        success: Always True
    """
    message: str = Field(description="Success message")
    success: bool = Field(default=True)


class CountResponse(BaseSchema):
    """
    Response containing a count of affected/matched records.

    Attributes:
        count: Number of records affected
        message: Optional descriptive message
    """
    count: int = Field(ge=0, description="Number of records")
    message: Optional[str] = Field(default=None)


# ============================================================================
# ID Schemas
# ============================================================================

class UUIDSchema(BaseSchema):
    """
    Schema for UUID-based identifiers.

    Validates and serializes UUID fields consistently.
    """
    id: UUID = Field(description="Unique identifier")


class StringIdSchema(BaseSchema):
    """
    Schema for string-based identifiers.

    Used for business-readable IDs like work order numbers,
    machine IDs, etc.
    """
    id: str = Field(
        min_length=1,
        max_length=100,
        description="String identifier"
    )


# ============================================================================
# Date/Time Range Schemas
# ============================================================================

class DateTimeRange(BaseSchema):
    """
    Schema for datetime range queries.

    Used for filtering historical data, events, and reports.

    Attributes:
        start: Start of the time range (inclusive)
        end: End of the time range (inclusive)
    """
    start: datetime = Field(description="Start datetime (inclusive)")
    end: datetime = Field(description="End datetime (inclusive)")

    @field_validator('end')
    @classmethod
    def end_after_start(cls, v: datetime, info) -> datetime:
        """Validate that end is after start."""
        if 'start' in info.data and v < info.data['start']:
            raise ValueError('end must be after start')
        return v


class DateRange(BaseSchema):
    """
    Schema for date-only range queries.

    Used for daily reports and date-based filtering.
    """
    start_date: str = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Start date in YYYY-MM-DD format"
    )
    end_date: str = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="End date in YYYY-MM-DD format"
    )


# ============================================================================
# Search and Filter Schemas
# ============================================================================

class SearchParams(BaseSchema):
    """
    Common search parameters for list endpoints.

    Combines text search with pagination for typical
    list/search operations.

    Attributes:
        search: Text search query
        limit: Maximum results to return
        offset: Number of results to skip
    """
    search: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Text search query"
    )
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class BulkOperationRequest(BaseSchema):
    """
    Request schema for bulk operations on multiple records.

    Attributes:
        ids: List of record IDs to operate on
    """
    ids: List[str] = Field(
        min_length=1,
        max_length=100,
        description="List of record IDs"
    )


class BulkOperationResponse(BaseSchema):
    """
    Response schema for bulk operations.

    Attributes:
        succeeded: List of IDs that were successfully processed
        failed: List of IDs that failed with error details
        total_processed: Total number of records processed
    """
    succeeded: List[str] = Field(description="Successfully processed IDs")
    failed: List[Dict[str, str]] = Field(
        description="Failed IDs with error messages"
    )
    total_processed: int = Field(ge=0, description="Total records processed")
