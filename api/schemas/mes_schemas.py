"""
LEGO Factory v3 - MES Pydantic Schemas
=======================================
Validation schemas for Manufacturing Execution System (MES)
operations including work orders, jobs, operations, OEE,
scheduling, and labor tracking.

These schemas ensure proper validation of manufacturing
data with support for ISA-95 manufacturing operations
management concepts.
"""

import re
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.schemas.common_schemas import BaseSchema, AuditMixin, PaginationParams


# ============================================================================
# Enums
# ============================================================================

class WorkOrderStatus(str, Enum):
    """Work order status lifecycle."""
    DRAFT = 'draft'
    PLANNED = 'planned'
    RELEASED = 'released'
    IN_PROGRESS = 'in_progress'
    ON_HOLD = 'on_hold'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = 'pending'
    QUEUED = 'queued'
    RUNNING = 'running'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class OperationType(str, Enum):
    """Types of manufacturing operations."""
    DESIGN = 'design'
    PRINTING_FDM = 'printing_fdm'
    PRINTING_SLA = 'printing_sla'
    CNC_MILLING = 'cnc_milling'
    ASSEMBLY = 'assembly'
    INSPECTION = 'inspection'
    PACKAGING = 'packaging'
    CUSTOM = 'custom'


class DowntimeCategory(str, Enum):
    """Downtime categories for OEE calculation."""
    PLANNED = 'planned'
    UNPLANNED = 'unplanned'
    CHANGEOVER = 'changeover'
    BREAKDOWN = 'breakdown'
    SETUP = 'setup'
    MAINTENANCE = 'maintenance'
    MATERIAL_SHORTAGE = 'material_shortage'
    OPERATOR_SHORTAGE = 'operator_shortage'
    QUALITY_ISSUE = 'quality_issue'
    OTHER = 'other'


class ShiftType(str, Enum):
    """Shift types."""
    DAY = 'day'
    EVENING = 'evening'
    NIGHT = 'night'
    WEEKEND = 'weekend'
    OVERTIME = 'overtime'


# ============================================================================
# Work Order Schemas
# ============================================================================

class WorkOrderCreate(BaseSchema):
    """
    Schema for creating a new work order.

    Work orders represent manufacturing orders that specify
    what to produce, how many, and when.

    Attributes:
        work_order_id: Optional custom work order ID (auto-generated if not provided)
        description: Work order description
        product_id: Product/part number to manufacture
        recipe_id: Recipe/routing to use
        quantity_ordered: Number of units to produce
        priority: Priority (1=highest, 10=lowest)
        planned_start: Planned start datetime
        planned_end: Planned end datetime
        due_date: Customer due date
        customer_id: Customer identifier
        sales_order_id: Related sales order
        notes: Additional notes
    """
    work_order_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Work order ID (auto-generated if not provided)"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Work order description"
    )
    product_id: str = Field(
        min_length=1,
        max_length=50,
        description="Product/part number"
    )
    recipe_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Recipe/routing ID"
    )
    routing_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Manufacturing routing ID (auto-generates operations from template)"
    )
    auto_generate_operations: bool = Field(
        default=True,
        description="Auto-generate operations from routing template"
    )
    quantity_ordered: int = Field(
        default=1,
        ge=1,
        le=1000000,
        description="Quantity to produce"
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Priority (1=highest, 10=lowest)"
    )
    planned_start: Optional[datetime] = Field(
        default=None,
        description="Planned start datetime"
    )
    planned_end: Optional[datetime] = Field(
        default=None,
        description="Planned end datetime"
    )
    due_date: Optional[datetime] = Field(
        default=None,
        description="Due date"
    )
    customer_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Customer ID"
    )
    sales_order_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Related sales order ID"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Additional notes"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )

    @field_validator('work_order_id')
    @classmethod
    def validate_work_order_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate work order ID format if provided."""
        if v is not None:
            if not re.match(r'^[a-zA-Z0-9_-]+$', v):
                raise ValueError(
                    'Work order ID must contain only letters, numbers, '
                    'underscores, and hyphens'
                )
        return v

    @model_validator(mode='after')
    def validate_dates(self) -> 'WorkOrderCreate':
        """Validate date consistency."""
        if self.planned_start and self.planned_end:
            if self.planned_end <= self.planned_start:
                raise ValueError('planned_end must be after planned_start')
        if self.planned_end and self.due_date:
            if self.planned_end > self.due_date:
                # Warning, not error - planned end after due date
                pass
        return self


class WorkOrderUpdate(BaseSchema):
    """Schema for updating a work order."""
    description: Optional[str] = Field(default=None, max_length=1000)
    recipe_id: Optional[str] = Field(default=None, max_length=50)
    quantity_ordered: Optional[int] = Field(default=None, ge=1, le=1000000)
    priority: Optional[int] = Field(default=None, ge=1, le=10)
    planned_start: Optional[datetime] = Field(default=None)
    planned_end: Optional[datetime] = Field(default=None)
    due_date: Optional[datetime] = Field(default=None)
    status: Optional[WorkOrderStatus] = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=2000)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class WorkOrderStatusChange(BaseSchema):
    """
    Schema for changing work order status.

    Some status transitions require additional data.

    Attributes:
        status: New status
        user_id: User making the change
        reason: Reason for status change (required for ON_HOLD and CANCELLED)
    """
    status: WorkOrderStatus = Field(description="New status")
    user_id: str = Field(
        default="system",
        min_length=1,
        max_length=100,
        description="User making the change"
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for status change"
    )

    @model_validator(mode='after')
    def validate_reason_required(self) -> 'WorkOrderStatusChange':
        """Validate reason is provided for certain status changes."""
        if self.status in (WorkOrderStatus.ON_HOLD, WorkOrderStatus.CANCELLED):
            if not self.reason:
                raise ValueError(
                    f'Reason is required when changing status to {self.status.value}'
                )
        return self


class WorkOrderResponse(BaseSchema):
    """Work order response schema."""
    id: str
    work_order_id: str
    description: Optional[str] = None
    product_id: Optional[str] = None
    recipe_id: Optional[str] = None
    quantity_ordered: int
    quantity_completed: int = 0
    status: str
    priority: int
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    due_date: Optional[datetime] = None
    customer_id: Optional[str] = None
    created_at: Optional[datetime] = None


class WorkOrderListParams(PaginationParams):
    """Query parameters for listing work orders."""
    status: Optional[WorkOrderStatus] = Field(default=None)
    product_id: Optional[str] = Field(default=None, max_length=50)
    customer_id: Optional[str] = Field(default=None, max_length=50)
    due_before: Optional[datetime] = Field(default=None)
    priority_max: Optional[int] = Field(default=None, ge=1, le=10)


# ============================================================================
# Operation Schemas
# ============================================================================

class OperationCreate(BaseSchema):
    """
    Schema for creating an operation within a work order.

    Operations represent individual manufacturing steps
    in the production routing.

    Attributes:
        operation_id: Optional operation ID (auto-generated if not provided)
        sequence: Operation sequence number (10, 20, 30...)
        operation_type: Type of operation
        name: Operation name
        description: Operation description
        work_center_id: Work center assignment
        machine_id: Machine assignment
        setup_time: Setup time in minutes
        run_time: Run time in minutes
        teardown_time: Teardown time in minutes
        parameters: Operation-specific parameters
    """
    operation_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Operation ID"
    )
    sequence: int = Field(
        default=10,
        ge=1,
        le=9999,
        description="Sequence number"
    )
    operation_type: OperationType = Field(
        description="Operation type"
    )
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Operation name"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Operation description"
    )
    work_center_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Work center ID"
    )
    machine_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Machine ID"
    )
    setup_time: float = Field(
        default=0,
        ge=0,
        le=10000,
        description="Setup time in minutes"
    )
    run_time: float = Field(
        default=0,
        ge=0,
        le=100000,
        description="Run time in minutes"
    )
    teardown_time: float = Field(
        default=0,
        ge=0,
        le=10000,
        description="Teardown time in minutes"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Operation parameters"
    )


class OperationUpdate(BaseSchema):
    """Schema for updating an operation."""
    sequence: Optional[int] = Field(default=None, ge=1, le=9999)
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    work_center_id: Optional[str] = Field(default=None, max_length=50)
    machine_id: Optional[str] = Field(default=None, max_length=50)
    setup_time: Optional[float] = Field(default=None, ge=0, le=10000)
    run_time: Optional[float] = Field(default=None, ge=0, le=100000)
    teardown_time: Optional[float] = Field(default=None, ge=0, le=10000)
    parameters: Optional[Dict[str, Any]] = Field(default=None)


# ============================================================================
# Job Schemas
# ============================================================================

class JobCreate(BaseSchema):
    """
    Schema for creating a job.

    Jobs are the actual execution units scheduled on machines.

    Attributes:
        job_id: Optional job ID (auto-generated if not provided)
        machine_id: Machine to run the job on
        scheduled_start: Scheduled start time
        scheduled_end: Scheduled end time
        quantity_planned: Quantity to produce in this job
        priority_score: Scheduling priority score
        assigned_worker_id: Assigned operator
        gcode_file: Path to G-code file
        gcode_hash: Hash of G-code for verification
    """
    job_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Job ID"
    )
    machine_id: str = Field(
        min_length=1,
        max_length=50,
        description="Machine ID"
    )
    scheduled_start: Optional[datetime] = Field(
        default=None,
        description="Scheduled start time"
    )
    scheduled_end: Optional[datetime] = Field(
        default=None,
        description="Scheduled end time"
    )
    quantity_planned: int = Field(
        default=1,
        ge=1,
        le=1000000,
        description="Quantity to produce"
    )
    priority_score: float = Field(
        default=0,
        ge=-1000,
        le=1000,
        description="Scheduling priority score"
    )
    assigned_worker_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Assigned worker ID"
    )
    gcode_file: Optional[str] = Field(
        default=None,
        max_length=500,
        description="G-code file path"
    )
    gcode_hash: Optional[str] = Field(
        default=None,
        max_length=64,
        description="G-code file hash"
    )

    @model_validator(mode='after')
    def validate_schedule(self) -> 'JobCreate':
        """Validate schedule dates."""
        if self.scheduled_start and self.scheduled_end:
            if self.scheduled_end <= self.scheduled_start:
                raise ValueError('scheduled_end must be after scheduled_start')
        return self


class JobUpdate(BaseSchema):
    """Schema for updating a job."""
    machine_id: Optional[str] = Field(default=None, min_length=1, max_length=50)
    scheduled_start: Optional[datetime] = Field(default=None)
    scheduled_end: Optional[datetime] = Field(default=None)
    quantity_planned: Optional[int] = Field(default=None, ge=1, le=1000000)
    priority_score: Optional[float] = Field(default=None, ge=-1000, le=1000)
    assigned_worker_id: Optional[str] = Field(default=None, max_length=50)
    gcode_file: Optional[str] = Field(default=None, max_length=500)


class JobStatusUpdate(BaseSchema):
    """
    Schema for updating job status.

    Attributes:
        status: New job status
        user_id: User making the change
        quantity_completed: Quantity completed (for partial completions)
        quantity_rejected: Quantity rejected
        failure_reason: Reason for failure (required for FAILED status)
    """
    status: JobStatus = Field(description="New status")
    user_id: str = Field(
        default="system",
        min_length=1,
        max_length=100,
        description="User making the change"
    )
    quantity_completed: Optional[int] = Field(
        default=None,
        ge=0,
        description="Quantity completed"
    )
    quantity_rejected: Optional[int] = Field(
        default=None,
        ge=0,
        description="Quantity rejected"
    )
    failure_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Failure reason"
    )

    @model_validator(mode='after')
    def validate_failure_reason(self) -> 'JobStatusUpdate':
        """Validate failure reason is provided for failed status."""
        if self.status == JobStatus.FAILED and not self.failure_reason:
            raise ValueError('failure_reason is required when status is FAILED')
        return self


class JobResponse(BaseSchema):
    """Job response schema."""
    id: str
    job_id: str
    work_order_id: str
    machine_id: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    status: str
    priority_score: float = 0
    quantity_planned: int = 1
    quantity_completed: int = 0
    quantity_rejected: int = 0
    assigned_worker_id: Optional[str] = None


class JobListParams(PaginationParams):
    """Query parameters for listing jobs."""
    machine_id: Optional[str] = Field(default=None, max_length=50)
    status: Optional[JobStatus] = Field(default=None)
    work_order_id: Optional[str] = Field(default=None, max_length=50)
    scheduled_after: Optional[datetime] = Field(default=None)
    scheduled_before: Optional[datetime] = Field(default=None)


# ============================================================================
# OEE Schemas
# ============================================================================

class OEECalculationRequest(BaseSchema):
    """
    Schema for requesting OEE calculation.

    OEE (Overall Equipment Effectiveness) = Availability x Performance x Quality

    Attributes:
        machine_id: Machine to calculate OEE for
        start: Start of calculation period
        end: End of calculation period
    """
    machine_id: str = Field(
        min_length=1,
        max_length=50,
        description="Machine ID"
    )
    start: datetime = Field(description="Period start")
    end: datetime = Field(description="Period end")

    @model_validator(mode='after')
    def validate_period(self) -> 'OEECalculationRequest':
        """Validate calculation period."""
        if self.end <= self.start:
            raise ValueError('end must be after start')
        return self


class OEEResponse(BaseSchema):
    """OEE calculation response."""
    machine_id: str
    period_start: datetime
    period_end: datetime
    oee: float = Field(ge=0, le=100, description="Overall OEE percentage")
    availability: float = Field(ge=0, le=100, description="Availability percentage")
    performance: float = Field(ge=0, le=100, description="Performance percentage")
    quality: float = Field(ge=0, le=100, description="Quality percentage")
    planned_production_time: float = Field(ge=0, description="Planned time in minutes")
    actual_run_time: float = Field(ge=0, description="Actual run time in minutes")
    total_count: int = Field(ge=0, description="Total units produced")
    good_count: int = Field(ge=0, description="Good units produced")
    rejected_count: int = Field(ge=0, description="Rejected units")


class DowntimeRecord(BaseSchema):
    """
    Schema for recording downtime events.

    Attributes:
        machine_id: Machine that was down
        start_time: Downtime start
        end_time: Downtime end (optional if still down)
        category: Downtime category
        reason: Detailed reason
        operator_id: Operator on duty
    """
    machine_id: str = Field(
        min_length=1,
        max_length=50,
        description="Machine ID"
    )
    start_time: datetime = Field(description="Downtime start")
    end_time: Optional[datetime] = Field(
        default=None,
        description="Downtime end"
    )
    category: DowntimeCategory = Field(
        description="Downtime category"
    )
    reason: str = Field(
        min_length=1,
        max_length=500,
        description="Downtime reason"
    )
    operator_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Operator on duty"
    )
    work_order_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Related work order"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Additional notes"
    )

    @model_validator(mode='after')
    def validate_times(self) -> 'DowntimeRecord':
        """Validate time values."""
        if self.end_time and self.end_time <= self.start_time:
            raise ValueError('end_time must be after start_time')
        return self


class DowntimeUpdate(BaseSchema):
    """Schema for updating a downtime record."""
    end_time: Optional[datetime] = Field(default=None)
    category: Optional[DowntimeCategory] = Field(default=None)
    reason: Optional[str] = Field(default=None, min_length=1, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=1000)


# ============================================================================
# Scheduling Schemas
# ============================================================================

class ScheduleJobRequest(BaseSchema):
    """
    Schema for scheduling a job on a machine.

    Attributes:
        work_order_id: Work order to schedule
        machine_id: Target machine
        start_time: Requested start time
        duration_minutes: Estimated duration
        priority: Scheduling priority
    """
    work_order_id: str = Field(
        min_length=1,
        max_length=50,
        description="Work order ID"
    )
    machine_id: str = Field(
        min_length=1,
        max_length=50,
        description="Machine ID"
    )
    start_time: datetime = Field(description="Requested start time")
    duration_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        le=100000,
        description="Estimated duration in minutes"
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Scheduling priority"
    )


class ScheduleOptimizeRequest(BaseSchema):
    """
    Schema for requesting schedule optimization.

    Attributes:
        machine_ids: Machines to optimize (all if empty)
        start_date: Optimization window start
        end_date: Optimization window end
        optimization_goal: Optimization objective
    """
    machine_ids: Optional[List[str]] = Field(
        default=None,
        max_length=100,
        description="Machine IDs to optimize"
    )
    start_date: datetime = Field(description="Window start")
    end_date: datetime = Field(description="Window end")
    optimization_goal: str = Field(
        default="minimize_makespan",
        pattern="^(minimize_makespan|minimize_lateness|maximize_utilization|balance_load)$",
        description="Optimization goal"
    )

    @model_validator(mode='after')
    def validate_window(self) -> 'ScheduleOptimizeRequest':
        """Validate optimization window."""
        if self.end_date <= self.start_date:
            raise ValueError('end_date must be after start_date')
        return self


class ScheduleConflict(BaseSchema):
    """Schema representing a scheduling conflict."""
    job_id: str
    machine_id: str
    conflicting_job_id: str
    overlap_start: datetime
    overlap_end: datetime
    conflict_type: str


# ============================================================================
# Labor Schemas
# ============================================================================

class LaborEntry(BaseSchema):
    """
    Schema for recording labor time.

    Attributes:
        worker_id: Worker identifier
        work_order_id: Work order worked on
        operation_id: Specific operation
        start_time: Labor start time
        end_time: Labor end time
        labor_type: Type of labor (direct, indirect, setup)
        notes: Additional notes
    """
    worker_id: str = Field(
        min_length=1,
        max_length=50,
        description="Worker ID"
    )
    work_order_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Work order ID"
    )
    operation_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Operation ID"
    )
    machine_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Machine ID"
    )
    start_time: datetime = Field(description="Labor start time")
    end_time: Optional[datetime] = Field(
        default=None,
        description="Labor end time"
    )
    labor_type: str = Field(
        default="direct",
        pattern="^(direct|indirect|setup|rework|training|other)$",
        description="Type of labor"
    )
    shift: Optional[ShiftType] = Field(
        default=None,
        description="Shift"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Notes"
    )

    @model_validator(mode='after')
    def validate_times(self) -> 'LaborEntry':
        """Validate time values."""
        if self.end_time and self.end_time <= self.start_time:
            raise ValueError('end_time must be after start_time')
        return self


class LaborEntryUpdate(BaseSchema):
    """Schema for updating a labor entry."""
    end_time: Optional[datetime] = Field(default=None)
    labor_type: Optional[str] = Field(
        default=None,
        pattern="^(direct|indirect|setup|rework|training|other)$"
    )
    notes: Optional[str] = Field(default=None, max_length=500)


# ============================================================================
# Production Reporting Schemas
# ============================================================================

class ProductionCountReport(BaseSchema):
    """
    Schema for reporting production counts.

    Attributes:
        job_id: Job being reported
        good_count: Number of good units
        rejected_count: Number of rejected units
        scrap_count: Number of scrapped units
        rework_count: Number of units requiring rework
        timestamp: Report timestamp
        operator_id: Reporting operator
        notes: Additional notes
    """
    job_id: str = Field(
        min_length=1,
        max_length=50,
        description="Job ID"
    )
    good_count: int = Field(
        ge=0,
        description="Good units produced"
    )
    rejected_count: int = Field(
        default=0,
        ge=0,
        description="Rejected units"
    )
    scrap_count: int = Field(
        default=0,
        ge=0,
        description="Scrapped units"
    )
    rework_count: int = Field(
        default=0,
        ge=0,
        description="Units requiring rework"
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Report timestamp"
    )
    operator_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Reporting operator"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Notes"
    )


class QualityDefect(BaseSchema):
    """
    Schema for reporting quality defects.

    Attributes:
        job_id: Related job
        defect_code: Defect classification code
        quantity: Number of defective units
        description: Defect description
        severity: Defect severity
        disposition: How defects were handled
    """
    job_id: str = Field(
        min_length=1,
        max_length=50,
        description="Job ID"
    )
    defect_code: str = Field(
        min_length=1,
        max_length=50,
        description="Defect code"
    )
    quantity: int = Field(
        ge=1,
        description="Defective quantity"
    )
    description: str = Field(
        min_length=1,
        max_length=500,
        description="Defect description"
    )
    severity: str = Field(
        default="minor",
        pattern="^(critical|major|minor|cosmetic)$",
        description="Defect severity"
    )
    disposition: str = Field(
        default="scrap",
        pattern="^(scrap|rework|use_as_is|return_to_vendor)$",
        description="Defect disposition"
    )
    inspector_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Inspector ID"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Additional notes"
    )
