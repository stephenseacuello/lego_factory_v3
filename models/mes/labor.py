"""
LEGO Factory v3 - Labor Management Models
=========================================
Workers, skills, and time tracking.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index, Table
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from models.base import BaseModel, AuditedModel, SoftDeleteMixin


class WorkerStatus(str, Enum):
    """Worker availability status."""
    ACTIVE = 'active'
    ON_BREAK = 'on_break'
    UNAVAILABLE = 'unavailable'
    ON_LEAVE = 'on_leave'
    TERMINATED = 'terminated'


class SkillLevel(str, Enum):
    """Skill proficiency levels."""
    TRAINEE = 'trainee'
    BASIC = 'basic'
    INTERMEDIATE = 'intermediate'
    ADVANCED = 'advanced'
    EXPERT = 'expert'


# Association table for worker skills
worker_skills = Table(
    'worker_skills',
    BaseModel.metadata,
    Column('worker_id', UUID(as_uuid=True), ForeignKey('workers.id'), primary_key=True),
    Column('skill_id', UUID(as_uuid=True), ForeignKey('skills.id'), primary_key=True),
    Column('level', SQLEnum(SkillLevel), default=SkillLevel.BASIC),
    Column('certified_date', Date),
    Column('expiry_date', Date),
)


class Worker(AuditedModel, SoftDeleteMixin):
    """Factory worker/operator."""

    __tablename__ = 'workers'

    employee_id = Column(String(50), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(200))
    phone = Column(String(50))

    # Department and role
    department = Column(String(100))
    role = Column(String(100))
    supervisor_id = Column(String(50))

    # Status
    status = Column(SQLEnum(WorkerStatus), default=WorkerStatus.ACTIVE, index=True)
    hire_date = Column(Date)

    # Shift information
    default_shift = Column(String(50))
    hourly_rate = Column(Float)

    # Certifications and qualifications
    certifications = Column(JSON, default=list)

    # Skills relationship
    skills = relationship('Skill', secondary=worker_skills, back_populates='workers')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'employee_id': self.employee_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': f"{self.first_name} {self.last_name}",
            'email': self.email,
            'department': self.department,
            'role': self.role,
            'status': self.status.value if self.status else None,
            'hire_date': self.hire_date.isoformat() if self.hire_date else None,
        }


class Skill(BaseModel, SoftDeleteMixin):
    """Manufacturing skill/competency."""

    __tablename__ = 'skills'

    skill_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(100))

    # Certification requirements
    requires_certification = Column(Boolean, default=False)
    certification_validity_days = Column(Integer)
    training_hours = Column(Float)

    # Equipment association
    equipment_types = Column(JSON, default=list)

    # Workers relationship
    workers = relationship('Worker', secondary=worker_skills, back_populates='skills')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'skill_code': self.skill_code,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'requires_certification': self.requires_certification,
        }


class TimeEntry(AuditedModel):
    """Labor time tracking entry."""

    __tablename__ = 'time_entries'

    worker_id = Column(UUID(as_uuid=True), ForeignKey('workers.id'), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id'))
    work_order_id = Column(UUID(as_uuid=True), ForeignKey('work_orders.id'))

    # Time tracking
    clock_in = Column(DateTime, nullable=False)
    clock_out = Column(DateTime)
    break_minutes = Column(Integer, default=0)

    # Calculated hours
    regular_hours = Column(Float, default=0)
    overtime_hours = Column(Float, default=0)

    # Type
    entry_type = Column(String(50), default='direct')  # direct, indirect, setup, rework

    # Notes
    notes = Column(Text)
    approved = Column(Boolean, default=False)
    approved_by = Column(String(50))
    approved_at = Column(DateTime)

    __table_args__ = (
        Index('ix_time_entries_worker_date', 'worker_id', 'clock_in'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'worker_id': str(self.worker_id),
            'job_id': str(self.job_id) if self.job_id else None,
            'clock_in': self.clock_in.isoformat() if self.clock_in else None,
            'clock_out': self.clock_out.isoformat() if self.clock_out else None,
            'break_minutes': self.break_minutes,
            'regular_hours': self.regular_hours,
            'overtime_hours': self.overtime_hours,
            'entry_type': self.entry_type,
            'approved': self.approved,
        }

    # Relationship for eager-loading
    worker = relationship('Worker', backref='time_entries', lazy='select')

    @property
    def total_hours(self) -> float:
        """Calculate total worked hours."""
        if not self.clock_out:
            return 0
        delta = self.clock_out - self.clock_in
        hours = delta.total_seconds() / 3600
        return max(0, hours - (self.break_minutes / 60))


class ActiveClockSession(BaseModel):
    """Active clock-in session — persisted to survive service restarts."""

    __tablename__ = 'active_clock_sessions'

    worker_id = Column(UUID(as_uuid=True), ForeignKey('workers.id'), nullable=False, index=True)
    employee_id = Column(String(50), nullable=False, index=True)
    job_id = Column(String(100))
    machine_id = Column(String(100))
    skill_id = Column(String(100))
    clock_in = Column(DateTime, nullable=False)
    breaks = Column(JSON, default=list)

    worker = relationship('Worker', backref='active_sessions')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'worker_id': str(self.worker_id),
            'employee_id': self.employee_id,
            'job_id': self.job_id,
            'machine_id': self.machine_id,
            'skill_id': self.skill_id,
            'clock_in': self.clock_in.isoformat() if self.clock_in else None,
            'breaks': self.breaks or [],
        }
