"""
Analytics Models

ISA-95 Level 3 analytics and performance tracking models:
- OEEEvent: Overall Equipment Effectiveness data collection
- CostLedger: Standard/actual cost recording
- DigitalTwinState: Machine state snapshots
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, Date,
    ForeignKey, Index, Numeric
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from .base import Base, IS_SQLITE

# Use JSON for SQLite, JSONB for PostgreSQL
JSON_TYPE = Text if IS_SQLITE else JSONB


class OEEEventType(str, Enum):
    """Types of OEE events for tracking."""
    PRODUCTION = 'PRODUCTION'       # Normal production run
    DOWNTIME_PLANNED = 'DOWNTIME_PLANNED'  # Scheduled maintenance, breaks
    DOWNTIME_UNPLANNED = 'DOWNTIME_UNPLANNED'  # Breakdowns, jams
    SETUP = 'SETUP'                 # Changeover, setup time
    IDLE = 'IDLE'                   # Waiting for work
    QUALITY_LOSS = 'QUALITY_LOSS'   # Rework, scrap time


class DowntimeReasonCode(str, Enum):
    """Standard downtime reason codes."""
    # Planned
    SCHEDULED_MAINTENANCE = 'SCHEDULED_MAINTENANCE'
    SHIFT_CHANGE = 'SHIFT_CHANGE'
    BREAK = 'BREAK'
    NO_ORDERS = 'NO_ORDERS'
    TRAINING = 'TRAINING'

    # Unplanned
    BREAKDOWN = 'BREAKDOWN'
    MATERIAL_SHORTAGE = 'MATERIAL_SHORTAGE'
    OPERATOR_UNAVAILABLE = 'OPERATOR_UNAVAILABLE'
    QUALITY_ISSUE = 'QUALITY_ISSUE'
    TOOLING_ISSUE = 'TOOLING_ISSUE'
    POWER_FAILURE = 'POWER_FAILURE'
    NETWORK_ISSUE = 'NETWORK_ISSUE'

    # 3D Printer Specific
    FILAMENT_RUNOUT = 'FILAMENT_RUNOUT'
    NOZZLE_CLOG = 'NOZZLE_CLOG'
    BED_ADHESION = 'BED_ADHESION'
    LAYER_SHIFT = 'LAYER_SHIFT'
    THERMAL_RUNAWAY = 'THERMAL_RUNAWAY'

    # CNC Specific
    TOOL_BREAKAGE = 'TOOL_BREAKAGE'
    TOOL_WEAR = 'TOOL_WEAR'
    COOLANT_ISSUE = 'COOLANT_ISSUE'
    SPINDLE_ERROR = 'SPINDLE_ERROR'


class CostType(str, Enum):
    """Types of manufacturing costs."""
    MATERIAL = 'MATERIAL'
    LABOR = 'LABOR'
    MACHINE = 'MACHINE'
    OVERHEAD = 'OVERHEAD'
    TOOLING = 'TOOLING'
    QUALITY = 'QUALITY'
    SCRAP = 'SCRAP'
    REWORK = 'REWORK'


class OEEEvent(Base):
    """
    OEE Event - Overall Equipment Effectiveness data collection.

    Captures time-based events for calculating:
    - Availability = Run Time / Planned Production Time
    - Performance = (Ideal Cycle Time × Total Count) / Run Time
    - Quality = Good Count / Total Count
    - OEE = Availability × Performance × Quality

    World-class OEE target: 85%
    """
    __tablename__ = 'oee_events'

    work_center_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                            ForeignKey('work_centers.id'), nullable=False, index=True)
    work_order_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                           ForeignKey('work_orders.id'), index=True)
    operation_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                          ForeignKey('work_order_operations.id'))

    event_type = Column(String(50), nullable=False, index=True)

    # Timing
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime)
    duration_minutes = Column(Float)

    # Production counts
    parts_produced = Column(Integer, default=0)
    parts_good = Column(Integer, default=0)
    parts_defective = Column(Integer, default=0)
    parts_rework = Column(Integer, default=0)

    # Cycle time tracking
    ideal_cycle_time_sec = Column(Float)  # Standard/ideal cycle time
    actual_cycle_time_sec = Column(Float)  # Actual average cycle time

    # Downtime tracking
    reason_code = Column(String(50), index=True)
    reason_description = Column(Text)

    # Shift context
    shift_date = Column(Date, index=True)
    shift_number = Column(Integer)
    operator_id = Column(String(100))

    # Additional data
    parameters = Column(JSON_TYPE)  # Machine parameters during event
    notes = Column(Text)

    # Relationships
    work_center = relationship('WorkCenter', back_populates='oee_events')
    work_order = relationship('WorkOrder')
    operation = relationship('WorkOrderOperation')

    __table_args__ = (
        Index('idx_oee_wc_date', 'work_center_id', 'shift_date'),
        Index('idx_oee_type_reason', 'event_type', 'reason_code'),
    )

    def __repr__(self):
        return f"<OEEEvent({self.work_center_id}, {self.event_type}, {self.start_time})>"

    def end_event(self, parts_produced: int = 0, parts_defective: int = 0):
        """End this event and calculate duration."""
        self.end_time = datetime.utcnow()
        if self.start_time:
            delta = self.end_time - self.start_time
            self.duration_minutes = delta.total_seconds() / 60
        self.parts_produced = parts_produced
        self.parts_defective = parts_defective
        self.parts_good = parts_produced - parts_defective

        # Calculate actual cycle time
        if parts_produced > 0 and self.duration_minutes:
            self.actual_cycle_time_sec = (self.duration_minutes * 60) / parts_produced

    @classmethod
    def calculate_oee(cls, session, work_center_id: str,
                      start_date: datetime, end_date: datetime) -> Dict[str, float]:
        """
        Calculate OEE metrics for a work center over a time period.

        Returns:
            Dictionary with availability, performance, quality, oee percentages
        """
        from sqlalchemy import func

        events = session.query(cls).filter(
            cls.work_center_id == work_center_id,
            cls.start_time >= start_date,
            cls.start_time < end_date,
            cls.duration_minutes.isnot(None)
        ).all()

        if not events:
            return {'availability': 0, 'performance': 0, 'quality': 0, 'oee': 0}

        # Calculate totals
        total_time = sum(e.duration_minutes or 0 for e in events)
        production_time = sum(
            e.duration_minutes or 0 for e in events
            if e.event_type == OEEEventType.PRODUCTION.value
        )
        planned_downtime = sum(
            e.duration_minutes or 0 for e in events
            if e.event_type == OEEEventType.DOWNTIME_PLANNED.value
        )

        total_parts = sum(e.parts_produced or 0 for e in events)
        good_parts = sum(e.parts_good or 0 for e in events)

        # Availability = Run Time / Planned Production Time
        planned_production_time = total_time - planned_downtime
        availability = (production_time / planned_production_time * 100) if planned_production_time > 0 else 0

        # Performance = (Ideal Cycle Time × Total Count) / Run Time
        ideal_time = sum(
            (e.ideal_cycle_time_sec or 60) * (e.parts_produced or 0) / 60
            for e in events if e.event_type == OEEEventType.PRODUCTION.value
        )
        performance = (ideal_time / production_time * 100) if production_time > 0 else 0

        # Quality = Good Count / Total Count
        quality = (good_parts / total_parts * 100) if total_parts > 0 else 0

        # OEE = Availability × Performance × Quality
        oee = (availability / 100) * (performance / 100) * (quality / 100) * 100

        return {
            'availability': round(availability, 2),
            'performance': round(min(performance, 100), 2),  # Cap at 100%
            'quality': round(quality, 2),
            'oee': round(oee, 2),
            'total_parts': total_parts,
            'good_parts': good_parts,
            'production_minutes': round(production_time, 2),
            'downtime_minutes': round(total_time - production_time, 2)
        }

    @classmethod
    def get_downtime_pareto(cls, session, work_center_id: str = None,
                            days: int = 30) -> List[Dict[str, Any]]:
        """
        Get Pareto analysis of downtime reasons.

        Returns list of reason codes sorted by total downtime.
        """
        from sqlalchemy import func

        cutoff = datetime.utcnow() - timedelta(days=days)

        query = session.query(
            cls.reason_code,
            func.sum(cls.duration_minutes).label('total_minutes'),
            func.count(cls.id).label('event_count')
        ).filter(
            cls.start_time >= cutoff,
            cls.event_type.in_([
                OEEEventType.DOWNTIME_UNPLANNED.value,
                OEEEventType.DOWNTIME_PLANNED.value
            ]),
            cls.reason_code.isnot(None)
        )

        if work_center_id:
            query = query.filter(cls.work_center_id == work_center_id)

        results = query.group_by(cls.reason_code).order_by(
            func.sum(cls.duration_minutes).desc()
        ).all()

        total_downtime = sum(r.total_minutes or 0 for r in results)
        cumulative = 0

        pareto = []
        for r in results:
            cumulative += r.total_minutes or 0
            pareto.append({
                'reason_code': r.reason_code,
                'total_minutes': round(r.total_minutes or 0, 2),
                'event_count': r.event_count,
                'percentage': round((r.total_minutes or 0) / total_downtime * 100, 2) if total_downtime > 0 else 0,
                'cumulative_percentage': round(cumulative / total_downtime * 100, 2) if total_downtime > 0 else 0
            })

        return pareto


class CostLedger(Base):
    """
    Cost Ledger - Manufacturing cost tracking and variance analysis.

    Records standard costs (expected) vs actual costs (incurred)
    for variance analysis:
    - Material variance
    - Labor variance
    - Overhead variance
    """
    __tablename__ = 'cost_ledger'

    transaction_date = Column(DateTime, default=datetime.utcnow, index=True)

    work_order_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                           ForeignKey('work_orders.id'), index=True)
    operation_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                          ForeignKey('work_order_operations.id'))
    part_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                     ForeignKey('parts.id'), index=True)

    cost_type = Column(String(50), nullable=False, index=True)
    cost_element = Column(String(100))  # Specific cost element

    # Cost values
    quantity = Column(Float, default=1)
    standard_unit_cost = Column(Numeric(10, 4), default=0)
    actual_unit_cost = Column(Numeric(10, 4), default=0)
    standard_cost = Column(Numeric(12, 4), default=0)
    actual_cost = Column(Numeric(12, 4), default=0)
    variance = Column(Numeric(12, 4), default=0)

    # Context
    resource_id = Column(String(100))  # Material lot, operator, machine
    reference_doc = Column(String(100))
    notes = Column(Text)

    # Relationships
    work_order = relationship('WorkOrder')
    operation = relationship('WorkOrderOperation')
    part = relationship('Part')

    __table_args__ = (
        Index('idx_cost_wo_type', 'work_order_id', 'cost_type'),
        Index('idx_cost_date_type', 'transaction_date', 'cost_type'),
    )

    def __repr__(self):
        return f"<CostLedger({self.cost_type}, std={self.standard_cost}, act={self.actual_cost})>"

    def calculate_variance(self):
        """Calculate variance between standard and actual cost."""
        self.standard_cost = float(self.quantity or 0) * float(self.standard_unit_cost or 0)
        self.actual_cost = float(self.quantity or 0) * float(self.actual_unit_cost or 0)
        self.variance = self.actual_cost - self.standard_cost

    @classmethod
    def get_variance_summary(cls, session, work_order_id: str = None,
                             start_date: datetime = None,
                             end_date: datetime = None) -> Dict[str, Dict[str, float]]:
        """
        Get variance summary by cost type.

        Returns:
            Dictionary with standard, actual, variance for each cost type
        """
        from sqlalchemy import func

        query = session.query(
            cls.cost_type,
            func.sum(cls.standard_cost).label('total_standard'),
            func.sum(cls.actual_cost).label('total_actual'),
            func.sum(cls.variance).label('total_variance')
        )

        if work_order_id:
            query = query.filter(cls.work_order_id == work_order_id)
        if start_date:
            query = query.filter(cls.transaction_date >= start_date)
        if end_date:
            query = query.filter(cls.transaction_date < end_date)

        results = query.group_by(cls.cost_type).all()

        summary = {}
        for r in results:
            summary[r.cost_type] = {
                'standard': float(r.total_standard or 0),
                'actual': float(r.total_actual or 0),
                'variance': float(r.total_variance or 0),
                'variance_pct': round(
                    float(r.total_variance or 0) / float(r.total_standard or 1) * 100, 2
                ) if r.total_standard else 0
            }

        return summary

    @classmethod
    def record_material_cost(cls, session, work_order_id: str, part_id: str,
                             quantity: float, standard_unit: float,
                             actual_unit: float, lot_number: str = None) -> 'CostLedger':
        """Record material cost for a work order."""
        entry = cls(
            work_order_id=work_order_id,
            part_id=part_id,
            cost_type=CostType.MATERIAL.value,
            cost_element='Raw Material',
            quantity=quantity,
            standard_unit_cost=standard_unit,
            actual_unit_cost=actual_unit,
            resource_id=lot_number
        )
        entry.calculate_variance()
        session.add(entry)
        return entry

    @classmethod
    def record_labor_cost(cls, session, work_order_id: str, operation_id: str,
                          hours: float, standard_rate: float,
                          actual_rate: float, operator_id: str = None) -> 'CostLedger':
        """Record labor cost for an operation."""
        entry = cls(
            work_order_id=work_order_id,
            operation_id=operation_id,
            cost_type=CostType.LABOR.value,
            cost_element='Direct Labor',
            quantity=hours,
            standard_unit_cost=standard_rate,
            actual_unit_cost=actual_rate,
            resource_id=operator_id
        )
        entry.calculate_variance()
        session.add(entry)
        return entry

    @classmethod
    def record_machine_cost(cls, session, work_order_id: str, operation_id: str,
                            hours: float, standard_rate: float,
                            actual_rate: float, machine_id: str = None) -> 'CostLedger':
        """Record machine cost for an operation."""
        entry = cls(
            work_order_id=work_order_id,
            operation_id=operation_id,
            cost_type=CostType.MACHINE.value,
            cost_element='Machine Time',
            quantity=hours,
            standard_unit_cost=standard_rate,
            actual_unit_cost=actual_rate,
            resource_id=machine_id
        )
        entry.calculate_variance()
        session.add(entry)
        return entry


class DigitalTwinState(Base):
    """
    Digital Twin State - Real-time machine state snapshots.

    Captures periodic state of manufacturing equipment for:
    - Real-time monitoring dashboards
    - Historical trend analysis
    - Predictive maintenance
    - Simulation replay
    """
    __tablename__ = 'digital_twin_state'

    work_center_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                            ForeignKey('work_centers.id'), nullable=False, index=True)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    state_type = Column(String(50), nullable=False, index=True)
    # TELEMETRY, POSITION, TEMPERATURE, STATUS, ALERT

    # Machine state
    machine_status = Column(String(50))  # RUNNING, IDLE, ERROR, PAUSED
    current_operation = Column(String(100))
    current_program = Column(String(255))
    progress_pct = Column(Float)

    # Position/motion (for CNC, 3D printers)
    position_x = Column(Float)
    position_y = Column(Float)
    position_z = Column(Float)
    feed_rate = Column(Float)

    # Temperature data (for 3D printers)
    hotend_temp = Column(Float)
    hotend_target = Column(Float)
    bed_temp = Column(Float)
    bed_target = Column(Float)
    chamber_temp = Column(Float)

    # Spindle/tool data (for CNC)
    spindle_speed = Column(Float)
    spindle_load = Column(Float)
    tool_number = Column(Integer)

    # Laser data
    laser_power = Column(Float)
    laser_frequency = Column(Float)

    # Job context
    work_order_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                           ForeignKey('work_orders.id'))
    parts_completed = Column(Integer)
    estimated_completion = Column(DateTime)

    # Consumables
    filament_used_mm = Column(Float)
    filament_remaining_pct = Column(Float)

    # Error/alert data
    error_code = Column(String(50))
    error_message = Column(Text)

    # Full state as JSON (for custom/extended data)
    state_data = Column(JSON_TYPE)

    # Relationships
    work_center = relationship('WorkCenter')
    work_order = relationship('WorkOrder')

    __table_args__ = (
        Index('idx_twin_wc_time', 'work_center_id', 'timestamp'),
        Index('idx_twin_type_time', 'state_type', 'timestamp'),
    )

    def __repr__(self):
        return f"<DigitalTwinState({self.work_center_id}, {self.state_type}, {self.timestamp})>"

    @classmethod
    def capture_3d_printer_state(cls, session, work_center_id: str,
                                  status: str, hotend_temp: float, bed_temp: float,
                                  position: Dict[str, float] = None,
                                  progress: float = None,
                                  work_order_id: str = None) -> 'DigitalTwinState':
        """Capture state snapshot for a 3D printer."""
        state = cls(
            work_center_id=work_center_id,
            state_type='TELEMETRY',
            machine_status=status,
            hotend_temp=hotend_temp,
            bed_temp=bed_temp,
            progress_pct=progress,
            work_order_id=work_order_id
        )

        if position:
            state.position_x = position.get('x')
            state.position_y = position.get('y')
            state.position_z = position.get('z')

        session.add(state)
        return state

    @classmethod
    def capture_cnc_state(cls, session, work_center_id: str,
                          status: str, spindle_speed: float,
                          position: Dict[str, float] = None,
                          tool_number: int = None,
                          work_order_id: str = None) -> 'DigitalTwinState':
        """Capture state snapshot for a CNC machine."""
        state = cls(
            work_center_id=work_center_id,
            state_type='TELEMETRY',
            machine_status=status,
            spindle_speed=spindle_speed,
            tool_number=tool_number,
            work_order_id=work_order_id
        )

        if position:
            state.position_x = position.get('x')
            state.position_y = position.get('y')
            state.position_z = position.get('z')
            state.feed_rate = position.get('feed_rate')

        session.add(state)
        return state

    @classmethod
    def get_latest_state(cls, session, work_center_id: str) -> Optional['DigitalTwinState']:
        """Get the most recent state for a work center."""
        return session.query(cls).filter(
            cls.work_center_id == work_center_id
        ).order_by(cls.timestamp.desc()).first()

    @classmethod
    def get_state_history(cls, session, work_center_id: str,
                          start_time: datetime, end_time: datetime = None,
                          state_type: str = None) -> List['DigitalTwinState']:
        """Get state history for a work center."""
        query = session.query(cls).filter(
            cls.work_center_id == work_center_id,
            cls.timestamp >= start_time
        )

        if end_time:
            query = query.filter(cls.timestamp <= end_time)
        if state_type:
            query = query.filter(cls.state_type == state_type)

        return query.order_by(cls.timestamp).all()

    @classmethod
    def get_temperature_trend(cls, session, work_center_id: str,
                               hours: int = 24) -> List[Dict[str, Any]]:
        """Get temperature trend data for graphing."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        states = session.query(cls).filter(
            cls.work_center_id == work_center_id,
            cls.timestamp >= cutoff,
            cls.hotend_temp.isnot(None)
        ).order_by(cls.timestamp).all()

        return [
            {
                'timestamp': s.timestamp.isoformat(),
                'hotend_temp': s.hotend_temp,
                'hotend_target': s.hotend_target,
                'bed_temp': s.bed_temp,
                'bed_target': s.bed_target
            }
            for s in states
        ]
