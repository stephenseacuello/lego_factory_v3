"""
LEGO Factory v3 - OEE Models
============================
Overall Equipment Effectiveness tracking and metrics.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class DowntimeReason(str, Enum):
    """Standard downtime reason codes."""
    SETUP = 'setup'
    CHANGEOVER = 'changeover'
    MATERIAL = 'material'
    MAINTENANCE_PLANNED = 'maintenance_planned'
    MAINTENANCE_UNPLANNED = 'maintenance_unplanned'
    QUALITY_ISSUE = 'quality_issue'
    OPERATOR = 'operator'
    TOOLING = 'tooling'
    POWER = 'power'
    SOFTWARE = 'software'
    CALIBRATION = 'calibration'
    FILAMENT_CHANGE = 'filament_change'
    BED_ADHESION = 'bed_adhesion'
    NOZZLE_CLOG = 'nozzle_clog'
    LAYER_SHIFT = 'layer_shift'
    OTHER = 'other'


class DowntimeEvent(AuditedModel):
    """Machine downtime event record."""

    __tablename__ = 'downtime_events'

    machine_id = Column(String(50), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id'))

    # Timing
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime)
    duration_minutes = Column(Float)

    # Classification
    reason = Column(SQLEnum(DowntimeReason), nullable=False)
    planned = Column(Boolean, default=False)

    # Details
    description = Column(Text)
    root_cause = Column(Text)
    corrective_action = Column(Text)

    # Reported by
    reported_by = Column(String(50))

    __table_args__ = (
        Index('ix_downtime_machine_time', 'machine_id', 'start_time'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'machine_id': self.machine_id,
            'job_id': str(self.job_id) if self.job_id else None,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_minutes': self.duration_minutes,
            'reason': self.reason.value if self.reason else None,
            'planned': self.planned,
            'description': self.description,
        }


class ProductionCount(AuditedModel):
    """Production count record for OEE calculation."""

    __tablename__ = 'production_counts'

    machine_id = Column(String(50), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id'))
    shift_date = Column(Date, nullable=False, index=True)
    shift = Column(String(20))

    # Counts
    total_count = Column(Integer, default=0)
    good_count = Column(Integer, default=0)
    reject_count = Column(Integer, default=0)
    rework_count = Column(Integer, default=0)

    # Timing
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    run_time_minutes = Column(Float)
    ideal_cycle_time_seconds = Column(Float)

    __table_args__ = (
        Index('ix_production_machine_date', 'machine_id', 'shift_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'machine_id': self.machine_id,
            'job_id': str(self.job_id) if self.job_id else None,
            'shift_date': self.shift_date.isoformat() if self.shift_date else None,
            'shift': self.shift,
            'total_count': self.total_count,
            'good_count': self.good_count,
            'reject_count': self.reject_count,
            'rework_count': self.rework_count,
        }

    @property
    def quality_rate(self) -> float:
        """Calculate quality rate (good / total)."""
        if self.total_count == 0:
            return 0.0
        return self.good_count / self.total_count


class OEERecord(AuditedModel):
    """Calculated OEE record (typically daily or shift-level)."""

    __tablename__ = 'oee_records'

    machine_id = Column(String(50), nullable=False, index=True)
    record_date = Column(Date, nullable=False, index=True)
    shift = Column(String(20))

    # Time components (minutes)
    scheduled_time = Column(Float, default=0)
    operating_time = Column(Float, default=0)
    net_operating_time = Column(Float, default=0)

    # Downtime breakdown
    planned_downtime = Column(Float, default=0)
    unplanned_downtime = Column(Float, default=0)
    changeover_time = Column(Float, default=0)

    # Production
    total_count = Column(Integer, default=0)
    good_count = Column(Integer, default=0)
    ideal_cycle_time = Column(Float)

    # OEE Components (0-1 scale)
    availability = Column(Float, default=0)
    performance = Column(Float, default=0)
    quality = Column(Float, default=0)
    oee = Column(Float, default=0)

    # Additional metrics
    mtbf_minutes = Column(Float)  # Mean Time Between Failures
    mttr_minutes = Column(Float)  # Mean Time To Repair

    __table_args__ = (
        Index('ix_oee_machine_date', 'machine_id', 'record_date'),
    )

    def calculate_oee(self):
        """Calculate OEE components and overall OEE."""
        # Availability = Operating Time / Scheduled Time
        if self.scheduled_time > 0:
            self.availability = self.operating_time / self.scheduled_time
        else:
            self.availability = 0

        # Performance = (Ideal Cycle Time × Total Count) / Operating Time
        if self.operating_time > 0 and self.ideal_cycle_time:
            ideal_time = (self.ideal_cycle_time / 60) * self.total_count  # Convert to minutes
            self.performance = min(1.0, ideal_time / self.operating_time)
        else:
            self.performance = 0

        # Quality = Good Count / Total Count
        if self.total_count > 0:
            self.quality = self.good_count / self.total_count
        else:
            self.quality = 0

        # OEE = Availability × Performance × Quality
        self.oee = self.availability * self.performance * self.quality

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'machine_id': self.machine_id,
            'record_date': self.record_date.isoformat() if self.record_date else None,
            'shift': self.shift,
            'scheduled_time': self.scheduled_time,
            'operating_time': self.operating_time,
            'availability': round(self.availability * 100, 2),
            'performance': round(self.performance * 100, 2),
            'quality': round(self.quality * 100, 2),
            'oee': round(self.oee * 100, 2),
            'total_count': self.total_count,
            'good_count': self.good_count,
        }
