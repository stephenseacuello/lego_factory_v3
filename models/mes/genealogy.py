"""
LEGO Factory v3 - Product Genealogy Models
============================================
Genealogy and traceability for MESA-11 Product Tracking & Genealogy function.
Tracks product serial numbers, process steps, and material lot consumption.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import uuid

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class GenealogyStatus(str, Enum):
    """Product genealogy status."""
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    SCRAPPED = 'scrapped'
    QUARANTINE = 'quarantine'
    SHIPPED = 'shipped'


class QualityResult(str, Enum):
    """Quality inspection result."""
    PENDING = 'pending'
    PASSED = 'passed'
    FAILED = 'failed'
    REWORK = 'rework'
    WAIVED = 'waived'


class ProductGenealogy(AuditedModel):
    """
    Product genealogy record - tracks a single unit through production.
    Each serial number gets one genealogy record.
    """

    __tablename__ = 'product_genealogy'

    # Serial identification
    serial_number = Column(String(100), unique=True, nullable=False, index=True)
    batch_number = Column(String(50), index=True)

    # Work order reference
    work_order_id = Column(UUID(as_uuid=True), ForeignKey('work_orders.id'), index=True)
    job_id = Column(String(50), index=True)

    # Product info
    product_id = Column(String(50), nullable=False, index=True)
    product_name = Column(String(200))
    product_revision = Column(String(20))

    # Status
    status = Column(SQLEnum(GenealogyStatus), default=GenealogyStatus.IN_PROGRESS, nullable=False)

    # Timing
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True))

    # Parent lot (raw material)
    parent_lot_id = Column(UUID(as_uuid=True), ForeignKey('material_lots.id'))

    # Quality summary
    overall_quality = Column(SQLEnum(QualityResult), default=QualityResult.PENDING)
    quality_score = Column(Float)  # 0-100 composite score

    # Location tracking
    current_location = Column(String(100))
    shipped_to = Column(String(200))
    shipped_at = Column(DateTime(timezone=True))

    # Metadata
    customer_order = Column(String(50))
    notes = Column(Text)
    extra_data = Column(JSON, default=dict)

    # Relationships
    work_order = relationship('WorkOrder', backref='genealogy_records')
    parent_lot = relationship('MaterialLot', backref='produced_items')
    process_steps = relationship('ProcessStep', back_populates='genealogy', cascade='all, delete-orphan')
    lot_traces = relationship('LotTrace', back_populates='output_genealogy', foreign_keys='LotTrace.output_genealogy_id')

    __table_args__ = (
        Index('ix_product_genealogy_product_status', 'product_id', 'status'),
        Index('ix_product_genealogy_wo', 'work_order_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'serial_number': self.serial_number,
            'batch_number': self.batch_number,
            'work_order_id': str(self.work_order_id) if self.work_order_id else None,
            'job_id': self.job_id,
            'product_id': self.product_id,
            'product_name': self.product_name,
            'status': self.status.value if self.status else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'overall_quality': self.overall_quality.value if self.overall_quality else None,
            'quality_score': self.quality_score,
            'current_location': self.current_location,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ProcessStep(BaseModel):
    """
    Individual process step in production.
    Records machine, operator, parameters, and quality for each operation.
    """

    __tablename__ = 'process_steps'

    # Parent genealogy
    genealogy_id = Column(UUID(as_uuid=True), ForeignKey('product_genealogy.id'), nullable=False, index=True)

    # Operation reference
    operation_id = Column(String(50), index=True)
    operation_name = Column(String(200))
    sequence = Column(Integer, nullable=False)

    # Execution details
    machine_id = Column(String(50), index=True)
    worker_id = Column(String(50), index=True)
    workstation = Column(String(100))

    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    planned_duration_mins = Column(Float)
    actual_duration_mins = Column(Float)

    # Process parameters
    parameters = Column(JSON, default=dict)  # Recipe parameters used
    setpoints = Column(JSON, default=dict)   # Target values
    actuals = Column(JSON, default=dict)     # Actual measured values

    # Quality
    quality_result = Column(SQLEnum(QualityResult), default=QualityResult.PENDING)
    inspection_data = Column(JSON, default=dict)
    defects_found = Column(JSON, default=list)

    # Sensor data reference
    sensor_data_ref = Column(String(200))  # Reference to time-series data

    # Notes
    notes = Column(Text)
    operator_comments = Column(Text)

    # Relationships
    genealogy = relationship('ProductGenealogy', back_populates='process_steps')

    __table_args__ = (
        Index('ix_process_steps_genealogy_seq', 'genealogy_id', 'sequence'),
        Index('ix_process_steps_machine', 'machine_id', 'started_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'genealogy_id': str(self.genealogy_id),
            'operation_id': self.operation_id,
            'operation_name': self.operation_name,
            'sequence': self.sequence,
            'machine_id': self.machine_id,
            'worker_id': self.worker_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'actual_duration_mins': self.actual_duration_mins,
            'quality_result': self.quality_result.value if self.quality_result else None,
            'parameters': self.parameters,
            'defects_found': self.defects_found,
        }


class LotTrace(BaseModel):
    """
    Material lot consumption trace.
    Links material lots to the products they were used to produce.
    """

    __tablename__ = 'lot_traces'

    # Source lot
    lot_id = Column(UUID(as_uuid=True), ForeignKey('material_lots.id'), nullable=False, index=True)

    # Consuming job
    consumed_by_job_id = Column(String(50), nullable=False, index=True)
    work_order_id = Column(String(50), index=True)

    # Output product
    output_genealogy_id = Column(UUID(as_uuid=True), ForeignKey('product_genealogy.id'), index=True)

    # Quantities
    quantity_consumed = Column(Float, nullable=False)
    unit_of_measure = Column(String(20))

    # Transformation type
    transformation_type = Column(String(50))  # 'consumed', 'transformed', 'assembled'

    # Timing
    consumed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    lot = relationship('MaterialLot', backref='traces')
    output_genealogy = relationship('ProductGenealogy', back_populates='lot_traces', foreign_keys=[output_genealogy_id])

    __table_args__ = (
        Index('ix_lot_traces_lot', 'lot_id'),
        Index('ix_lot_traces_output', 'output_genealogy_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'lot_id': str(self.lot_id),
            'lot_number': self.lot.lot_number if self.lot else None,
            'consumed_by_job_id': self.consumed_by_job_id,
            'work_order_id': self.work_order_id,
            'output_genealogy_id': str(self.output_genealogy_id) if self.output_genealogy_id else None,
            'output_serial': self.output_genealogy.serial_number if self.output_genealogy else None,
            'quantity_consumed': self.quantity_consumed,
            'unit_of_measure': self.unit_of_measure,
            'transformation_type': self.transformation_type,
            'consumed_at': self.consumed_at.isoformat() if self.consumed_at else None,
        }
