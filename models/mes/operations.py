"""
LEGO Factory v3 - Operational Models
=====================================
Models for rework tracking, shift handovers, kanban cards,
WIP snapshots, and cycle time records.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


# ---------------------------------------------------------------------------
# Rework / Scrap
# ---------------------------------------------------------------------------

class ReworkStatus(str, Enum):
    OPEN = 'open'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class ReworkOrder(AuditedModel):
    """Rework order tracking."""

    __tablename__ = 'rework_orders'

    rework_id = Column(String(50), unique=True, nullable=False, index=True)
    original_wo_id = Column(String(50), nullable=False, index=True)
    ncr_id = Column(String(50))
    reason = Column(Text)
    rework_operations = Column(JSON, default=list)
    quantity = Column(Integer, default=0)
    cost = Column(Float, default=0)
    status = Column(SQLEnum(ReworkStatus), default=ReworkStatus.OPEN, nullable=False)
    completed_at = Column(DateTime)

    __table_args__ = (
        Index('ix_rework_status', 'status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'rework_id': self.rework_id,
            'original_wo_id': self.original_wo_id,
            'ncr_id': self.ncr_id,
            'reason': self.reason,
            'rework_operations': self.rework_operations,
            'quantity': self.quantity,
            'cost': self.cost,
            'status': self.status.value if self.status else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class ScrapEvent(AuditedModel):
    """Scrap event record for cost tracking."""

    __tablename__ = 'scrap_events'

    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id'), index=True)
    machine_id = Column(String(50), index=True)
    quantity = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=False)
    unit_cost = Column(Float, default=0)
    total_cost = Column(Float, default=0)
    dispositioned_by = Column(String(100))

    __table_args__ = (
        Index('ix_scrap_job_reason', 'job_id', 'reason'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'job_id': str(self.job_id) if self.job_id else None,
            'machine_id': self.machine_id,
            'quantity': self.quantity,
            'reason': self.reason,
            'unit_cost': self.unit_cost,
            'total_cost': self.total_cost,
            'dispositioned_by': self.dispositioned_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Shift Handover
# ---------------------------------------------------------------------------

class HandoverStatus(str, Enum):
    DRAFT = 'draft'
    COMPLETED = 'completed'


class ShiftHandover(AuditedModel):
    """Shift handover record."""

    __tablename__ = 'shift_handovers'

    handover_id = Column(String(50), unique=True, nullable=False, index=True)
    shift_date = Column(Date, nullable=False, index=True)
    shift_type = Column(String(20), nullable=False)  # 'day', 'night', 'swing'
    outgoing_worker = Column(String(100))
    incoming_worker = Column(String(100))
    status = Column(SQLEnum(HandoverStatus), default=HandoverStatus.DRAFT, nullable=False)
    items = Column(JSON, default=list)  # list of checklist items
    notes = Column(Text)
    completed_at = Column(DateTime)

    __table_args__ = (
        Index('ix_handover_date_shift', 'shift_date', 'shift_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'handover_id': self.handover_id,
            'shift_date': self.shift_date.isoformat() if self.shift_date else None,
            'shift_type': self.shift_type,
            'outgoing_worker': self.outgoing_worker,
            'incoming_worker': self.incoming_worker,
            'status': self.status.value if self.status else None,
            'items': self.items,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


# ---------------------------------------------------------------------------
# Kanban / WIP
# ---------------------------------------------------------------------------

class KanbanCardModel(AuditedModel):
    """Kanban card for pull system control."""

    __tablename__ = 'kanban_cards'

    card_id = Column(String(50), unique=True, nullable=False, index=True)
    product_id = Column(String(100), nullable=False, index=True)
    work_center_id = Column(String(50), nullable=False, index=True)
    quantity = Column(Integer, default=0)
    target_qty = Column(Integer, nullable=False)
    reorder_point = Column(Integer, nullable=False)
    status = Column(String(20), default='empty')  # 'full', 'in_transit', 'empty'
    signal = Column(String(20), default='replenish')  # KanbanSignal values
    last_replenish_at = Column(DateTime)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'card_id': self.card_id,
            'product_id': self.product_id,
            'work_center_id': self.work_center_id,
            'quantity': self.quantity,
            'target_qty': self.target_qty,
            'reorder_point': self.reorder_point,
            'status': self.status,
            'signal': self.signal,
            'last_replenish_at': self.last_replenish_at.isoformat() if self.last_replenish_at else None,
        }


class WIPSnapshot(BaseModel):
    """WIP level snapshot for historical trending."""

    __tablename__ = 'wip_snapshots'

    total_wip = Column(Integer, nullable=False)
    by_machine = Column(JSON, default=dict)

    __table_args__ = (
        Index('ix_wip_snapshot_time', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'total_wip': self.total_wip,
            'by_machine': self.by_machine,
            'timestamp': self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Takt / Cycle Time
# ---------------------------------------------------------------------------

class CycleTimeRecord(BaseModel):
    """Cycle time record for takt analysis."""

    __tablename__ = 'cycle_time_records'

    work_center_id = Column(String(50), nullable=False, index=True)
    cycle_seconds = Column(Float, nullable=False)
    takt_target_seconds = Column(Float, nullable=False)
    deviation_seconds = Column(Float)
    on_takt = Column(Boolean, default=True)
    job_id = Column(String(100))
    operator_id = Column(String(100))

    __table_args__ = (
        Index('ix_cycle_time_wc_time', 'work_center_id', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'work_center_id': self.work_center_id,
            'cycle_seconds': self.cycle_seconds,
            'takt_target_seconds': self.takt_target_seconds,
            'deviation_seconds': self.deviation_seconds,
            'on_takt': self.on_takt,
            'job_id': self.job_id,
            'operator_id': self.operator_id,
            'timestamp': self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Material Shortage
# ---------------------------------------------------------------------------

class MaterialShortage(BaseModel):
    """Material shortage record for planner service."""

    __tablename__ = 'material_shortages'

    shortage_id = Column(String(50), unique=True, nullable=False, index=True)
    material_id = Column(String(100), nullable=False, index=True)
    quantity_short = Column(Float, nullable=False)
    required_date = Column(Date)
    job_id = Column(String(100))
    work_order_id = Column(String(100))
    status = Column(String(50), default='open')
    resolution_type = Column(String(50))
    resolved_at = Column(DateTime)

    __table_args__ = (
        Index('ix_material_shortage_status', 'status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'shortage_id': self.shortage_id,
            'material_id': self.material_id,
            'quantity_short': self.quantity_short,
            'required_date': self.required_date.isoformat() if self.required_date else None,
            'job_id': self.job_id,
            'work_order_id': self.work_order_id,
            'status': self.status,
            'resolution_type': self.resolution_type,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
