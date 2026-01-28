"""
LEGO Factory v3 - ERP Planning Models
=====================================
Cost centers, budgets, and demand forecasting.
"""

from datetime import datetime, date
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class BudgetStatus(str, Enum):
    """Budget status."""
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    APPROVED = 'approved'
    ACTIVE = 'active'
    CLOSED = 'closed'
    FROZEN = 'frozen'


class ForecastMethod(str, Enum):
    """Demand forecasting methods."""
    MOVING_AVERAGE = 'moving_average'
    EXPONENTIAL_SMOOTHING = 'exponential_smoothing'
    LINEAR_REGRESSION = 'linear_regression'
    SEASONAL = 'seasonal'
    ML_BASED = 'ml_based'
    MANUAL = 'manual'


class CostCenter(BaseModel):
    """
    Cost center for expense allocation.

    Organizational unit for tracking and controlling costs.
    """

    __tablename__ = 'cost_centers'

    cost_center_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Hierarchy
    parent_id = Column(UUID(as_uuid=True), ForeignKey('cost_centers.id'))
    level = Column(Integer, default=1)

    # Categorization
    department = Column(String(100))
    cost_type = Column(String(50))  # 'direct', 'indirect', 'overhead'

    # Responsibility
    manager = Column(String(200))
    manager_email = Column(String(200))

    # GL Account mapping
    default_gl_account_id = Column(UUID(as_uuid=True), ForeignKey('gl_accounts.id'))

    # Status
    is_active = Column(Boolean, default=True)
    effective_date = Column(Date)
    end_date = Column(Date)

    # Relationships
    children = relationship('CostCenter', backref='parent', remote_side='CostCenter.id')
    budgets = relationship('Budget', back_populates='cost_center')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'cost_center_id': self.cost_center_id,
            'name': self.name,
            'department': self.department,
            'cost_type': self.cost_type,
            'manager': self.manager,
            'is_active': self.is_active,
        }


class Budget(AuditedModel):
    """
    Budget allocation.

    Financial budget for a cost center or project.
    """

    __tablename__ = 'budgets'

    budget_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # What it's for
    cost_center_id = Column(UUID(as_uuid=True), ForeignKey('cost_centers.id'), index=True)
    gl_account_id = Column(UUID(as_uuid=True), ForeignKey('gl_accounts.id'))
    project_code = Column(String(100))

    # Period
    fiscal_year = Column(Integer, nullable=False, index=True)
    fiscal_period = Column(Integer)  # Month or quarter
    period_type = Column(String(20))  # 'annual', 'quarterly', 'monthly'
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Amounts
    original_amount = Column(Float, nullable=False)
    revised_amount = Column(Float)
    current_amount = Column(Float)

    # Actuals (calculated from GL postings)
    actual_amount = Column(Float, default=0)
    committed_amount = Column(Float, default=0)  # POs not yet received
    encumbered_amount = Column(Float, default=0)  # Requisitions

    # Variance
    variance_amount = Column(Float)
    variance_percent = Column(Float)

    # Status
    status = Column(SQLEnum(BudgetStatus), default=BudgetStatus.DRAFT, index=True)

    # Approval
    submitted_by = Column(String(100))
    submitted_at = Column(DateTime)
    approved_by = Column(String(100))
    approved_at = Column(DateTime)

    # Notes
    notes = Column(Text)

    # Relationship
    cost_center = relationship('CostCenter', back_populates='budgets')

    __table_args__ = (
        Index('ix_budgets_fiscal_year_center', 'fiscal_year', 'cost_center_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'budget_id': self.budget_id,
            'name': self.name,
            'cost_center_id': str(self.cost_center_id) if self.cost_center_id else None,
            'fiscal_year': self.fiscal_year,
            'original_amount': self.original_amount,
            'actual_amount': self.actual_amount,
            'variance_amount': self.variance_amount,
            'status': self.status.value if self.status else None,
        }

    @property
    def available_amount(self) -> float:
        """Calculate available budget."""
        current = self.current_amount or self.original_amount
        return current - (self.actual_amount or 0) - (self.committed_amount or 0)


class DemandForecast(AuditedModel):
    """
    Demand forecast for planning.

    Predicted demand for items used in MRP and capacity planning.
    """

    __tablename__ = 'demand_forecasts'

    forecast_id = Column(String(50), unique=True, nullable=False, index=True)

    # What's being forecast
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False, index=True)
    item_number = Column(String(100), nullable=False)
    item_description = Column(String(500))

    # Location
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))
    location_code = Column(String(100))

    # Forecast period
    forecast_date = Column(Date, nullable=False, index=True)
    period_type = Column(String(20))  # 'day', 'week', 'month'
    horizon_days = Column(Integer)

    # Forecast values
    forecast_qty = Column(Float, nullable=False)
    forecast_value = Column(Float)

    # Confidence
    confidence_level = Column(Float)  # 0-1
    lower_bound = Column(Float)
    upper_bound = Column(Float)

    # Method used
    forecast_method = Column(SQLEnum(ForecastMethod), default=ForecastMethod.MOVING_AVERAGE)
    model_version = Column(String(100))

    # Historical basis
    historical_periods = Column(Integer)
    historical_avg_qty = Column(Float)
    trend_factor = Column(Float)
    seasonal_factor = Column(Float)

    # Actual (filled in after the period)
    actual_qty = Column(Float)
    actual_value = Column(Float)
    forecast_error = Column(Float)
    forecast_accuracy = Column(Float)

    # Status
    is_locked = Column(Boolean, default=False)
    source = Column(String(50))  # 'system', 'manual', 'import'

    # Adjustments
    manual_adjustment = Column(Float)
    adjustment_reason = Column(Text)

    __table_args__ = (
        Index('ix_demand_forecasts_item_date', 'item_id', 'forecast_date'),
        Index('ix_demand_forecasts_date', 'forecast_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'forecast_id': self.forecast_id,
            'item_id': str(self.item_id),
            'item_number': self.item_number,
            'forecast_date': self.forecast_date.isoformat() if self.forecast_date else None,
            'forecast_qty': self.forecast_qty,
            'confidence_level': self.confidence_level,
            'forecast_method': self.forecast_method.value if self.forecast_method else None,
            'actual_qty': self.actual_qty,
            'forecast_accuracy': self.forecast_accuracy,
        }


class MRPRun(AuditedModel):
    """
    MRP run record.

    Records the execution and results of an MRP planning run.
    """

    __tablename__ = 'mrp_runs'

    run_id = Column(String(50), unique=True, nullable=False, index=True)
    run_name = Column(String(200))

    # Run parameters
    run_datetime = Column(DateTime, nullable=False, index=True)
    horizon_days = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Scope
    include_forecasts = Column(Boolean, default=True)
    include_safety_stock = Column(Boolean, default=True)
    item_filter = Column(JSON)  # Filter criteria used
    location_filter = Column(JSON)

    # Results summary
    items_processed = Column(Integer)
    planned_orders_count = Column(Integer)
    planned_order_qty = Column(Float)
    planned_order_value = Column(Float)
    action_messages_count = Column(Integer)

    # Status
    status = Column(String(50), default='running')  # running, completed, failed
    error_message = Column(Text)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)

    # Detailed results (stored as JSON or reference to separate table)
    results_summary = Column(JSON)

    # Who ran it
    run_by = Column(String(100))

    __table_args__ = (
        Index('ix_mrp_runs_datetime', 'run_datetime'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'run_id': self.run_id,
            'run_datetime': self.run_datetime.isoformat() if self.run_datetime else None,
            'horizon_days': self.horizon_days,
            'items_processed': self.items_processed,
            'planned_orders_count': self.planned_orders_count,
            'action_messages_count': self.action_messages_count,
            'status': self.status,
            'duration_seconds': self.duration_seconds,
        }


class PlannedOrder(AuditedModel):
    """
    MRP planned order.

    Orders suggested by MRP that haven't been firmed yet.
    """

    __tablename__ = 'planned_orders'

    order_id = Column(String(50), unique=True, nullable=False, index=True)
    mrp_run_id = Column(UUID(as_uuid=True), ForeignKey('mrp_runs.id'), index=True)

    # Item
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False, index=True)
    item_number = Column(String(100), nullable=False)

    # Order type
    order_type = Column(String(50), nullable=False)  # 'purchase', 'manufacturing'

    # Quantities
    required_qty = Column(Float, nullable=False)
    order_qty = Column(Float, nullable=False)

    # Dates
    required_date = Column(Date, nullable=False, index=True)
    order_date = Column(Date, nullable=False)  # Start date (considering lead time)
    release_date = Column(Date)

    # Location
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))

    # For purchase orders
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'))
    estimated_cost = Column(Float)

    # For manufacturing orders
    routing_id = Column(UUID(as_uuid=True), ForeignKey('routings.id'))
    work_center_id = Column(UUID(as_uuid=True))

    # Source of demand
    demand_source = Column(String(50))  # 'sales_order', 'forecast', 'safety_stock'
    source_document_id = Column(UUID(as_uuid=True))

    # Status
    status = Column(String(50), default='planned')  # planned, firmed, released, cancelled

    # Firmed order reference
    firmed_to = Column(String(50))  # PO or WO number when firmed

    __table_args__ = (
        Index('ix_planned_orders_item_date', 'item_id', 'required_date'),
        Index('ix_planned_orders_type_date', 'order_type', 'required_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'order_id': self.order_id,
            'item_id': str(self.item_id),
            'item_number': self.item_number,
            'order_type': self.order_type,
            'order_qty': self.order_qty,
            'required_date': self.required_date.isoformat() if self.required_date else None,
            'order_date': self.order_date.isoformat() if self.order_date else None,
            'status': self.status,
        }
