"""
Quality Models

ISA-95 Quality Operations Management models:
- QualityInspection: Inspection records and results
- QualityMetric: Individual measurement data points
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, Index, Numeric
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from .base import Base, IS_SQLITE

# Use JSON for SQLite, JSONB for PostgreSQL
JSON_TYPE = Text if IS_SQLITE else JSONB


class InspectionType(str, Enum):
    """Types of quality inspections."""
    INCOMING = 'INCOMING'           # Raw material inspection
    IN_PROCESS = 'IN_PROCESS'       # During manufacturing
    FINAL = 'FINAL'                 # Finished goods
    FIRST_ARTICLE = 'FIRST_ARTICLE' # First piece approval
    PERIODIC = 'PERIODIC'           # Scheduled inspection
    RANDOM = 'RANDOM'               # Random sampling


class InspectionResult(str, Enum):
    """Inspection result codes."""
    PASS = 'PASS'
    FAIL = 'FAIL'
    CONDITIONAL = 'CONDITIONAL'
    PENDING = 'PENDING'


class DispositionCode(str, Enum):
    """Disposition codes for failed inspections."""
    ACCEPT = 'ACCEPT'           # Accept as-is
    REWORK = 'REWORK'           # Rework to specification
    SCRAP = 'SCRAP'             # Scrap the part
    RETURN = 'RETURN'           # Return to supplier
    USE_AS_IS = 'USE_AS_IS'     # Use with deviation
    HOLD = 'HOLD'               # Hold for further review


class QualityInspection(Base):
    """
    Quality Inspection - Record of inspection activities.

    Tracks inspections at various stages of manufacturing:
    - Incoming material inspection
    - In-process inspection (during operations)
    - Final inspection (finished goods)
    - First article inspection (new parts/processes)
    """
    __tablename__ = 'quality_inspections'

    work_order_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                           ForeignKey('work_orders.id'), index=True)
    operation_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                          ForeignKey('work_order_operations.id'))
    part_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                     ForeignKey('parts.id'), index=True)

    inspection_type = Column(String(50), nullable=False, index=True)
    inspection_number = Column(String(50), unique=True, index=True)

    # Sample information
    sample_size = Column(Integer, default=1)
    lot_number = Column(String(100))
    serial_numbers = Column(JSON_TYPE)  # List of serial numbers inspected

    # Results
    result = Column(String(50), default=InspectionResult.PENDING.value, index=True)
    disposition = Column(String(50))

    # Timing
    inspection_date = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)

    # Personnel
    inspector_id = Column(String(100))
    approved_by = Column(String(100))

    # Documentation
    notes = Column(Text)
    attachments = Column(JSON_TYPE)  # File references

    # NCR reference if failed
    ncr_number = Column(String(50))

    # Relationships
    work_order = relationship('WorkOrder')
    operation = relationship('WorkOrderOperation')
    part = relationship('Part')
    metrics = relationship('QualityMetric', back_populates='inspection',
                           cascade='all, delete-orphan')

    def __repr__(self):
        return f"<QualityInspection({self.inspection_number}, result={self.result})>"

    @classmethod
    def get_by_number(cls, session, number: str) -> Optional['QualityInspection']:
        """Find inspection by number."""
        return session.query(cls).filter(cls.inspection_number == number).first()

    @classmethod
    def get_by_work_order(cls, session, work_order_id: str) -> List['QualityInspection']:
        """Get all inspections for a work order."""
        return session.query(cls).filter(cls.work_order_id == work_order_id).all()

    @classmethod
    def get_failures(cls, session, days: int = 30) -> List['QualityInspection']:
        """Get recent failed inspections."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        return session.query(cls).filter(
            cls.result == InspectionResult.FAIL.value,
            cls.inspection_date >= cutoff
        ).all()

    def add_metric(self, session, metric_name: str, target: float,
                   actual: float, tolerance: float = None,
                   uom: str = 'mm') -> 'QualityMetric':
        """Add a measurement metric to this inspection."""
        metric = QualityMetric(
            inspection_id=self.id,
            metric_name=metric_name,
            target_value=target,
            actual_value=actual,
            tolerance=tolerance,
            uom=uom
        )
        session.add(metric)
        return metric

    def calculate_result(self) -> str:
        """Calculate overall result from metrics."""
        if not self.metrics:
            return InspectionResult.PENDING.value

        all_pass = all(m.is_within_tolerance for m in self.metrics)
        return InspectionResult.PASS.value if all_pass else InspectionResult.FAIL.value

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate for this inspection's metrics."""
        if not self.metrics:
            return 0.0
        passed = sum(1 for m in self.metrics if m.is_within_tolerance)
        return passed / len(self.metrics) * 100


class QualityMetric(Base):
    """
    Quality Metric - Individual measurement data point.

    Records specific measurements taken during inspection:
    - Dimensional measurements (length, width, height)
    - LEGO-specific measurements (clutch power, stud fit)
    - Surface quality, color matching
    - Functional tests (connectivity, strength)
    """
    __tablename__ = 'quality_metrics'

    inspection_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                           ForeignKey('quality_inspections.id', ondelete='CASCADE'),
                           nullable=False, index=True)

    metric_name = Column(String(100), nullable=False)
    metric_category = Column(String(50))  # DIMENSIONAL, FUNCTIONAL, VISUAL

    # Measurement values
    target_value = Column(Float, nullable=False)
    actual_value = Column(Float)
    tolerance = Column(Float)  # +/- tolerance
    upper_limit = Column(Float)
    lower_limit = Column(Float)

    uom = Column(String(20), default='mm')  # Unit of measure

    # For multi-sample measurements
    sample_number = Column(Integer, default=1)
    measurement_location = Column(String(100))  # Where on the part

    # Statistical data (for SPC)
    measurement_values = Column(JSON_TYPE)  # Array of all measurements
    mean_value = Column(Float)
    std_deviation = Column(Float)
    cp = Column(Float)   # Process capability
    cpk = Column(Float)  # Process capability index

    # Equipment used
    measurement_device = Column(String(100))
    device_calibration_date = Column(DateTime)

    measured_at = Column(DateTime, default=datetime.utcnow)
    measured_by = Column(String(100))

    notes = Column(Text)

    # Relationships
    inspection = relationship('QualityInspection', back_populates='metrics')

    __table_args__ = (
        Index('idx_metric_inspection_name', 'inspection_id', 'metric_name'),
    )

    def __repr__(self):
        return f"<QualityMetric({self.metric_name}, target={self.target_value}, actual={self.actual_value})>"

    @property
    def is_within_tolerance(self) -> bool:
        """Check if actual value is within tolerance."""
        if self.actual_value is None:
            return False

        # Use explicit limits if provided
        if self.upper_limit is not None and self.lower_limit is not None:
            return self.lower_limit <= self.actual_value <= self.upper_limit

        # Otherwise use target +/- tolerance
        if self.tolerance is not None:
            lower = self.target_value - self.tolerance
            upper = self.target_value + self.tolerance
            return lower <= self.actual_value <= upper

        # No tolerance specified, exact match required
        return self.actual_value == self.target_value

    @property
    def deviation(self) -> Optional[float]:
        """Calculate deviation from target."""
        if self.actual_value is None:
            return None
        return self.actual_value - self.target_value

    @property
    def deviation_percentage(self) -> Optional[float]:
        """Calculate percentage deviation from target."""
        if self.actual_value is None or self.target_value == 0:
            return None
        return (self.actual_value - self.target_value) / self.target_value * 100

    def calculate_cpk(self, values: List[float] = None) -> Optional[float]:
        """
        Calculate Cpk (Process Capability Index).

        Cpk = min((USL - mean) / (3 * sigma), (mean - LSL) / (3 * sigma))

        World-class Cpk target: >= 1.33
        """
        import statistics

        if values is None:
            if self.measurement_values:
                values = self.measurement_values
            else:
                return None

        if len(values) < 2:
            return None

        mean = statistics.mean(values)
        sigma = statistics.stdev(values)

        if sigma == 0:
            return None

        usl = self.upper_limit or (self.target_value + (self.tolerance or 0))
        lsl = self.lower_limit or (self.target_value - (self.tolerance or 0))

        cpu = (usl - mean) / (3 * sigma)
        cpl = (mean - lsl) / (3 * sigma)

        cpk = min(cpu, cpl)

        # Store calculated values
        self.mean_value = mean
        self.std_deviation = sigma
        self.cpk = cpk
        self.cp = (usl - lsl) / (6 * sigma)

        return cpk


# LEGO-specific quality metrics
LEGO_QUALITY_METRICS = {
    'stud_diameter': {
        'target': 4.8,
        'tolerance': 0.02,
        'uom': 'mm',
        'category': 'DIMENSIONAL'
    },
    'stud_height': {
        'target': 1.7,
        'tolerance': 0.02,
        'uom': 'mm',
        'category': 'DIMENSIONAL'
    },
    'tube_inner_diameter': {
        'target': 4.8,
        'tolerance': 0.02,
        'uom': 'mm',
        'category': 'DIMENSIONAL'
    },
    'tube_outer_diameter': {
        'target': 6.51,
        'tolerance': 0.03,
        'uom': 'mm',
        'category': 'DIMENSIONAL'
    },
    'brick_length': {
        'target_per_stud': 8.0,
        'tolerance': 0.02,
        'uom': 'mm',
        'category': 'DIMENSIONAL'
    },
    'brick_width': {
        'target_per_stud': 8.0,
        'tolerance': 0.02,
        'uom': 'mm',
        'category': 'DIMENSIONAL'
    },
    'brick_height': {
        'target_per_plate': 3.2,
        'tolerance': 0.02,
        'uom': 'mm',
        'category': 'DIMENSIONAL'
    },
    'wall_thickness': {
        'target': 1.6,
        'tolerance': 0.05,
        'uom': 'mm',
        'category': 'DIMENSIONAL'
    },
    'clutch_power': {
        'target': 30,  # grams of force
        'tolerance': 10,
        'uom': 'gf',
        'category': 'FUNCTIONAL'
    },
    'fit_test': {
        'target': 1,  # 1 = fits, 0 = doesn't fit
        'tolerance': 0,
        'uom': 'boolean',
        'category': 'FUNCTIONAL'
    },
    'surface_roughness': {
        'target': 0.8,  # Ra in micrometers
        'tolerance': 0.2,
        'uom': 'μm',
        'category': 'VISUAL'
    },
    'color_delta_e': {
        'target': 0,
        'tolerance': 2,  # Delta E color difference
        'uom': 'ΔE',
        'category': 'VISUAL'
    }
}
