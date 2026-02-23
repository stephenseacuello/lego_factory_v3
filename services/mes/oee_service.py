"""
LEGO Factory v3 - OEE Service
=============================
Overall Equipment Effectiveness calculation and tracking.

Enhanced Features:
- Real-time OEE calculation
- OEE waterfall breakdown (availability → performance → quality)
- Six Big Losses categorization
- Statistical trending with control limits
- Shift-level and operator-level OEE comparison
"""

import logging
import statistics
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func

from config.database import get_db_session

logger = logging.getLogger(__name__)


class SixBigLosses(str, Enum):
    """The Six Big Losses in OEE framework."""
    # Availability losses
    EQUIPMENT_FAILURE = 'equipment_failure'  # Breakdowns
    SETUP_ADJUSTMENT = 'setup_adjustment'  # Changeovers
    # Performance losses
    IDLING_MINOR_STOPS = 'idling_minor_stops'  # Small stops
    REDUCED_SPEED = 'reduced_speed'  # Speed loss
    # Quality losses
    PROCESS_DEFECTS = 'process_defects'  # Scrap/rework
    STARTUP_REJECTS = 'startup_rejects'  # Reduced yield


@dataclass
class OEEWaterfall:
    """OEE waterfall breakdown showing loss contribution."""
    scheduled_time: float
    planned_downtime: float
    available_time: float
    equipment_failure_loss: float
    setup_loss: float
    operating_time: float
    idling_stops_loss: float
    speed_loss: float
    net_operating_time: float
    defect_loss: float
    startup_loss: float
    value_operating_time: float

    # Calculated OEE components
    availability: float = 0.0
    performance: float = 0.0
    quality: float = 0.0
    oee: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'scheduled_time': self.scheduled_time,
            'planned_downtime': self.planned_downtime,
            'available_time': self.available_time,
            'losses': {
                'equipment_failure': self.equipment_failure_loss,
                'setup_adjustment': self.setup_loss,
                'idling_minor_stops': self.idling_stops_loss,
                'reduced_speed': self.speed_loss,
                'process_defects': self.defect_loss,
                'startup_rejects': self.startup_loss,
            },
            'operating_time': self.operating_time,
            'net_operating_time': self.net_operating_time,
            'value_operating_time': self.value_operating_time,
            'availability': self.availability,
            'performance': self.performance,
            'quality': self.quality,
            'oee': self.oee,
        }


@dataclass
class RealTimeOEE:
    """Real-time OEE snapshot."""
    machine_id: str
    timestamp: datetime
    period_start: datetime
    period_end: datetime

    # Components
    availability: float
    performance: float
    quality: float
    oee: float

    # Counts
    total_count: int
    good_count: int
    reject_count: int

    # Times (minutes)
    scheduled_time: float
    operating_time: float
    downtime: float
    actual_cycle_time: float
    ideal_cycle_time: float

    # Status
    is_running: bool
    current_state: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'machine_id': self.machine_id,
            'timestamp': self.timestamp.isoformat(),
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'availability': self.availability,
            'performance': self.performance,
            'quality': self.quality,
            'oee': self.oee,
            'total_count': self.total_count,
            'good_count': self.good_count,
            'reject_count': self.reject_count,
            'scheduled_time': self.scheduled_time,
            'operating_time': self.operating_time,
            'downtime': self.downtime,
            'actual_cycle_time': self.actual_cycle_time,
            'ideal_cycle_time': self.ideal_cycle_time,
            'is_running': self.is_running,
            'current_state': self.current_state,
        }


class OEEService:
    """Service for OEE calculation and tracking."""

    def __init__(self, session: Session):
        self.session = session

    def record_downtime(
        self,
        machine_id: str,
        reason: str,
        start_time: datetime,
        end_time: datetime = None,
        description: str = None,
        planned: bool = False,
        job_id: str = None,
        reported_by: str = None
    ) -> Dict[str, Any]:
        """Record a downtime event."""
        from models.mes.oee import DowntimeEvent, DowntimeReason

        duration = None
        if end_time:
            duration = (end_time - start_time).total_seconds() / 60

        event = DowntimeEvent(
            machine_id=machine_id,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration,
            reason=DowntimeReason(reason),
            planned=planned,
            description=description,
            reported_by=reported_by,
        )

        self.session.add(event)
        self.session.flush()

        logger.info(f"Recorded downtime for {machine_id}: {reason}")
        return event.to_dict()

    def end_downtime(self, event_id: str, end_time: datetime = None) -> Optional[Dict[str, Any]]:
        """End an active downtime event."""
        from models.mes.oee import DowntimeEvent

        event = self.session.query(DowntimeEvent).filter(
            DowntimeEvent.id == event_id
        ).first()

        if not event:
            return None

        event.end_time = end_time or datetime.utcnow()
        event.duration_minutes = (event.end_time - event.start_time).total_seconds() / 60
        self.session.flush()

        return event.to_dict()

    def record_production(
        self,
        machine_id: str,
        shift_date: date,
        total_count: int,
        good_count: int,
        reject_count: int = 0,
        rework_count: int = 0,
        shift: str = None,
        job_id: str = None,
        run_time_minutes: float = None,
        ideal_cycle_time_seconds: float = None
    ) -> Dict[str, Any]:
        """Record production counts."""
        from models.mes.oee import ProductionCount

        count = ProductionCount(
            machine_id=machine_id,
            shift_date=shift_date,
            shift=shift,
            total_count=total_count,
            good_count=good_count,
            reject_count=reject_count,
            rework_count=rework_count,
            run_time_minutes=run_time_minutes,
            ideal_cycle_time_seconds=ideal_cycle_time_seconds,
        )

        self.session.add(count)
        self.session.flush()

        return count.to_dict()

    def calculate_oee(
        self,
        machine_id: str,
        record_date: date,
        shift: str = None,
        scheduled_time_minutes: float = 480  # Default 8-hour shift
    ) -> Dict[str, Any]:
        """Calculate and record OEE for a machine."""
        from models.mes.oee import OEERecord, DowntimeEvent, ProductionCount, DowntimeReason

        # Get downtime for the period
        start_dt = datetime.combine(record_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)

        downtimes = self.session.query(DowntimeEvent).filter(
            DowntimeEvent.machine_id == machine_id,
            DowntimeEvent.start_time >= start_dt,
            DowntimeEvent.start_time < end_dt
        ).all()

        # Calculate downtime totals
        planned_downtime = sum(d.duration_minutes or 0 for d in downtimes if d.planned)
        unplanned_downtime = sum(d.duration_minutes or 0 for d in downtimes if not d.planned)
        changeover_time = sum(d.duration_minutes or 0 for d in downtimes
                              if d.reason in (DowntimeReason.SETUP, DowntimeReason.CHANGEOVER))

        # Get production counts
        production = self.session.query(ProductionCount).filter(
            ProductionCount.machine_id == machine_id,
            ProductionCount.shift_date == record_date
        ).all()

        total_count = sum(p.total_count for p in production)
        good_count = sum(p.good_count for p in production)
        run_time = sum(p.run_time_minutes or 0 for p in production)
        ideal_cycle = next((p.ideal_cycle_time_seconds for p in production if p.ideal_cycle_time_seconds), 60)

        # Calculate times
        operating_time = scheduled_time_minutes - planned_downtime - unplanned_downtime
        net_operating_time = operating_time - changeover_time

        # Create OEE record
        oee_record = OEERecord(
            machine_id=machine_id,
            record_date=record_date,
            shift=shift,
            scheduled_time=scheduled_time_minutes,
            operating_time=max(0, operating_time),
            net_operating_time=max(0, net_operating_time),
            planned_downtime=planned_downtime,
            unplanned_downtime=unplanned_downtime,
            changeover_time=changeover_time,
            total_count=total_count,
            good_count=good_count,
            ideal_cycle_time=ideal_cycle,
        )

        # Calculate OEE components
        oee_record.calculate_oee()

        self.session.add(oee_record)
        self.session.flush()

        logger.info(f"Calculated OEE for {machine_id} on {record_date}: {oee_record.oee:.2%}")
        return oee_record.to_dict()

    def get_oee_history(
        self,
        machine_id: str,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Get OEE history for a machine."""
        from models.mes.oee import OEERecord

        records = self.session.query(OEERecord).filter(
            OEERecord.machine_id == machine_id,
            OEERecord.record_date >= start_date,
            OEERecord.record_date <= end_date
        ).order_by(OEERecord.record_date).all()

        return [r.to_dict() for r in records]

    def get_downtime_pareto(
        self,
        machine_id: str = None,
        start_date: date = None,
        end_date: date = None
    ) -> List[Dict[str, Any]]:
        """Get downtime Pareto analysis."""
        from models.mes.oee import DowntimeEvent

        query = self.session.query(
            DowntimeEvent.reason,
            func.count(DowntimeEvent.id).label('count'),
            func.sum(DowntimeEvent.duration_minutes).label('total_minutes')
        )

        if machine_id:
            query = query.filter(DowntimeEvent.machine_id == machine_id)
        if start_date:
            query = query.filter(DowntimeEvent.start_time >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(DowntimeEvent.start_time < datetime.combine(end_date + timedelta(days=1), datetime.min.time()))

        results = query.group_by(DowntimeEvent.reason)\
            .order_by(func.sum(DowntimeEvent.duration_minutes).desc()).all()

        return [{
            'reason': r.reason.value if r.reason else 'unknown',
            'count': r.count,
            'total_minutes': float(r.total_minutes or 0)
        } for r in results]

    # ==================== Real-Time OEE ====================

    def calculate_realtime_oee(
        self,
        machine_id: str,
        period_minutes: int = 60
    ) -> RealTimeOEE:
        """
        Calculate real-time OEE for the specified period.

        Args:
            machine_id: Machine identifier
            period_minutes: Rolling period for calculation

        Returns:
            Real-time OEE snapshot
        """
        from models.mes.oee import DowntimeEvent, ProductionCount
        from models.scada.machines import Machine

        now = datetime.utcnow()
        period_start = now - timedelta(minutes=period_minutes)

        # Get machine status
        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()

        is_running = machine.status == 'running' if machine else False
        current_state = machine.status if machine else 'unknown'

        # Get downtime in period
        downtimes = self.session.query(DowntimeEvent).filter(
            DowntimeEvent.machine_id == machine_id,
            DowntimeEvent.start_time >= period_start,
            DowntimeEvent.start_time <= now
        ).all()

        total_downtime = 0
        for d in downtimes:
            if d.end_time:
                dt_end = min(d.end_time, now)
                dt_start = max(d.start_time, period_start)
                total_downtime += max(0, (dt_end - dt_start).total_seconds() / 60)
            elif d.start_time >= period_start:
                total_downtime += (now - d.start_time).total_seconds() / 60

        # Get production counts for current shift
        today = date.today()
        production = self.session.query(ProductionCount).filter(
            ProductionCount.machine_id == machine_id,
            ProductionCount.shift_date == today
        ).all()

        total_count = sum(p.total_count for p in production)
        good_count = sum(p.good_count for p in production)
        reject_count = sum(p.reject_count or 0 for p in production)
        ideal_cycle = next((p.ideal_cycle_time_seconds for p in production if p.ideal_cycle_time_seconds), 60)

        # Calculate OEE components
        scheduled_time = float(period_minutes)
        operating_time = max(0, scheduled_time - total_downtime)

        # Availability
        availability = operating_time / scheduled_time if scheduled_time > 0 else 0

        # Performance (based on actual vs ideal cycle time)
        if total_count > 0 and operating_time > 0:
            actual_cycle = (operating_time * 60) / total_count  # seconds
            performance = min(1.0, ideal_cycle / actual_cycle) if actual_cycle > 0 else 0
        else:
            actual_cycle = 0
            performance = 0

        # Quality
        quality = good_count / total_count if total_count > 0 else 1.0

        # OEE
        oee = availability * performance * quality

        return RealTimeOEE(
            machine_id=machine_id,
            timestamp=now,
            period_start=period_start,
            period_end=now,
            availability=round(availability, 4),
            performance=round(performance, 4),
            quality=round(quality, 4),
            oee=round(oee, 4),
            total_count=total_count,
            good_count=good_count,
            reject_count=reject_count,
            scheduled_time=scheduled_time,
            operating_time=round(operating_time, 2),
            downtime=round(total_downtime, 2),
            actual_cycle_time=round(actual_cycle, 2),
            ideal_cycle_time=ideal_cycle,
            is_running=is_running,
            current_state=current_state
        )

    def get_oee_waterfall(
        self,
        machine_id: str,
        record_date: date,
        scheduled_time_minutes: float = 480
    ) -> OEEWaterfall:
        """
        Calculate OEE waterfall breakdown showing where losses occur.

        The waterfall shows the reduction from scheduled time to value-operating time
        through each of the six big losses.

        Args:
            machine_id: Machine identifier
            record_date: Date to analyze
            scheduled_time_minutes: Scheduled production time

        Returns:
            OEE waterfall breakdown
        """
        from models.mes.oee import DowntimeEvent, ProductionCount, DowntimeReason

        start_dt = datetime.combine(record_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)

        # Get downtime events
        downtimes = self.session.query(DowntimeEvent).filter(
            DowntimeEvent.machine_id == machine_id,
            DowntimeEvent.start_time >= start_dt,
            DowntimeEvent.start_time < end_dt
        ).all()

        # Categorize downtime by six big losses
        planned_downtime = 0
        equipment_failure = 0
        setup_adjustment = 0
        idling_stops = 0

        for d in downtimes:
            duration = d.duration_minutes or 0
            if d.planned:
                planned_downtime += duration
            elif d.reason in (DowntimeReason.BREAKDOWN, DowntimeReason.ELECTRICAL, DowntimeReason.MECHANICAL):
                equipment_failure += duration
            elif d.reason in (DowntimeReason.SETUP, DowntimeReason.CHANGEOVER, DowntimeReason.TOOLING):
                setup_adjustment += duration
            elif d.reason in (DowntimeReason.MATERIAL, DowntimeReason.OPERATOR):
                idling_stops += duration
            else:
                # Default to equipment failure
                equipment_failure += duration

        # Get production data
        production = self.session.query(ProductionCount).filter(
            ProductionCount.machine_id == machine_id,
            ProductionCount.shift_date == record_date
        ).all()

        total_count = sum(p.total_count for p in production)
        good_count = sum(p.good_count for p in production)
        reject_count = sum(p.reject_count or 0 for p in production)
        rework_count = sum(p.rework_count or 0 for p in production)
        run_time = sum(p.run_time_minutes or 0 for p in production)
        ideal_cycle = next((p.ideal_cycle_time_seconds for p in production if p.ideal_cycle_time_seconds), 60)

        # Calculate times
        available_time = scheduled_time_minutes - planned_downtime
        operating_time = available_time - equipment_failure - setup_adjustment
        operating_time = max(0, operating_time - idling_stops)

        # Speed loss calculation
        if total_count > 0 and operating_time > 0:
            ideal_run_time = (total_count * ideal_cycle) / 60  # minutes
            speed_loss = max(0, operating_time - ideal_run_time)
        else:
            speed_loss = 0

        net_operating_time = max(0, operating_time - speed_loss)

        # Quality losses
        if total_count > 0 and net_operating_time > 0:
            defect_time = (reject_count * ideal_cycle) / 60 if reject_count > 0 else 0
            startup_loss = (rework_count * ideal_cycle) / 60 if rework_count > 0 else 0
        else:
            defect_time = 0
            startup_loss = 0

        value_operating_time = max(0, net_operating_time - defect_time - startup_loss)

        # Calculate OEE components
        availability = operating_time / available_time if available_time > 0 else 0
        performance = net_operating_time / operating_time if operating_time > 0 else 0
        quality = good_count / total_count if total_count > 0 else 1.0
        oee = availability * performance * quality

        waterfall = OEEWaterfall(
            scheduled_time=scheduled_time_minutes,
            planned_downtime=planned_downtime,
            available_time=available_time,
            equipment_failure_loss=equipment_failure,
            setup_loss=setup_adjustment,
            operating_time=operating_time,
            idling_stops_loss=idling_stops,
            speed_loss=speed_loss,
            net_operating_time=net_operating_time,
            defect_loss=defect_time,
            startup_loss=startup_loss,
            value_operating_time=value_operating_time,
            availability=round(availability, 4),
            performance=round(performance, 4),
            quality=round(quality, 4),
            oee=round(oee, 4)
        )

        return waterfall

    def get_six_big_losses_analysis(
        self,
        machine_id: str = None,
        start_date: date = None,
        end_date: date = None
    ) -> Dict[str, Any]:
        """
        Analyze the six big losses across machines or time period.

        Args:
            machine_id: Optional machine filter
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            Analysis of six big losses with totals and percentages
        """
        from models.mes.oee import DowntimeEvent, ProductionCount, DowntimeReason, OEERecord

        start_date = start_date or date.today() - timedelta(days=7)
        end_date = end_date or date.today()

        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

        # Query downtime
        query = self.session.query(DowntimeEvent).filter(
            DowntimeEvent.start_time >= start_dt,
            DowntimeEvent.start_time < end_dt
        )
        if machine_id:
            query = query.filter(DowntimeEvent.machine_id == machine_id)

        downtimes = query.all()

        # Categorize losses
        losses = {
            SixBigLosses.EQUIPMENT_FAILURE.value: 0,
            SixBigLosses.SETUP_ADJUSTMENT.value: 0,
            SixBigLosses.IDLING_MINOR_STOPS.value: 0,
            SixBigLosses.REDUCED_SPEED.value: 0,
            SixBigLosses.PROCESS_DEFECTS.value: 0,
            SixBigLosses.STARTUP_REJECTS.value: 0,
        }

        for d in downtimes:
            duration = d.duration_minutes or 0
            if d.planned:
                continue  # Planned downtime not counted in losses

            if d.reason in (DowntimeReason.BREAKDOWN, DowntimeReason.ELECTRICAL, DowntimeReason.MECHANICAL):
                losses[SixBigLosses.EQUIPMENT_FAILURE.value] += duration
            elif d.reason in (DowntimeReason.SETUP, DowntimeReason.CHANGEOVER, DowntimeReason.TOOLING):
                losses[SixBigLosses.SETUP_ADJUSTMENT.value] += duration
            elif d.reason in (DowntimeReason.MATERIAL, DowntimeReason.OPERATOR):
                losses[SixBigLosses.IDLING_MINOR_STOPS.value] += duration

        # Get quality losses from production records
        prod_query = self.session.query(ProductionCount).filter(
            ProductionCount.shift_date >= start_date,
            ProductionCount.shift_date <= end_date
        )
        if machine_id:
            prod_query = prod_query.filter(ProductionCount.machine_id == machine_id)

        production = prod_query.all()

        total_rejects = sum(p.reject_count or 0 for p in production)
        total_rework = sum(p.rework_count or 0 for p in production)
        avg_cycle = 60  # Default 60 seconds

        # Convert to time equivalent
        losses[SixBigLosses.PROCESS_DEFECTS.value] = (total_rejects * avg_cycle) / 60
        losses[SixBigLosses.STARTUP_REJECTS.value] = (total_rework * avg_cycle) / 60

        # Calculate totals and percentages
        total_loss = sum(losses.values())

        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'machine_id': machine_id,
            'losses': losses,
            'total_loss_minutes': total_loss,
            'loss_percentages': {
                k: round(v / total_loss * 100, 1) if total_loss > 0 else 0
                for k, v in losses.items()
            },
            'loss_categories': {
                'availability': losses[SixBigLosses.EQUIPMENT_FAILURE.value] + losses[SixBigLosses.SETUP_ADJUSTMENT.value],
                'performance': losses[SixBigLosses.IDLING_MINOR_STOPS.value] + losses[SixBigLosses.REDUCED_SPEED.value],
                'quality': losses[SixBigLosses.PROCESS_DEFECTS.value] + losses[SixBigLosses.STARTUP_REJECTS.value],
            }
        }

    def get_oee_trend_with_limits(
        self,
        machine_id: str,
        days: int = 30,
        target_oee: float = 0.85
    ) -> Dict[str, Any]:
        """
        Get OEE trending with statistical control limits.

        Args:
            machine_id: Machine identifier
            days: Number of days to analyze
            target_oee: Target OEE for comparison

        Returns:
            OEE trend data with UCL/LCL
        """
        from models.mes.oee import OEERecord

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        records = self.session.query(OEERecord).filter(
            OEERecord.machine_id == machine_id,
            OEERecord.record_date >= start_date,
            OEERecord.record_date <= end_date
        ).order_by(OEERecord.record_date).all()

        if len(records) < 5:
            return {
                'error': f'Insufficient data: {len(records)} records (need at least 5)',
                'machine_id': machine_id
            }

        # Extract OEE values
        oee_values = [r.oee for r in records if r.oee is not None]
        dates = [r.record_date.isoformat() for r in records if r.oee is not None]

        if not oee_values:
            return {'error': 'No OEE values found', 'machine_id': machine_id}

        # Calculate statistics
        mean_oee = statistics.mean(oee_values)
        stdev_oee = statistics.stdev(oee_values) if len(oee_values) > 1 else 0

        # Control limits (3-sigma)
        ucl = min(1.0, mean_oee + 3 * stdev_oee)
        lcl = max(0.0, mean_oee - 3 * stdev_oee)

        # Warning limits (2-sigma)
        uwl = min(1.0, mean_oee + 2 * stdev_oee)
        lwl = max(0.0, mean_oee - 2 * stdev_oee)

        # Detect out-of-control points
        out_of_control = []
        for i, (d, v) in enumerate(zip(dates, oee_values)):
            if v > ucl or v < lcl:
                out_of_control.append({
                    'date': d,
                    'oee': v,
                    'violation': 'beyond_3sigma'
                })

        # Trend direction
        if len(oee_values) >= 7:
            recent_mean = statistics.mean(oee_values[-7:])
            earlier_mean = statistics.mean(oee_values[:7])
            trend = 'improving' if recent_mean > earlier_mean else 'degrading'
        else:
            trend = 'insufficient_data'

        return {
            'machine_id': machine_id,
            'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'data': [{'date': d, 'oee': v} for d, v in zip(dates, oee_values)],
            'statistics': {
                'mean': round(mean_oee, 4),
                'std_dev': round(stdev_oee, 4),
                'min': min(oee_values),
                'max': max(oee_values),
            },
            'control_limits': {
                'ucl': round(ucl, 4),
                'cl': round(mean_oee, 4),
                'lcl': round(lcl, 4),
                'uwl': round(uwl, 4),
                'lwl': round(lwl, 4),
            },
            'target_oee': target_oee,
            'vs_target': 'above' if mean_oee >= target_oee else 'below',
            'trend': trend,
            'out_of_control_points': out_of_control,
            'points_in_control': len(oee_values) - len(out_of_control),
            'control_percentage': round((len(oee_values) - len(out_of_control)) / len(oee_values) * 100, 1)
        }

    def compare_oee_by_shift(
        self,
        machine_id: str = None,
        start_date: date = None,
        end_date: date = None
    ) -> Dict[str, Any]:
        """
        Compare OEE across different shifts.

        Args:
            machine_id: Optional machine filter
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            OEE comparison by shift
        """
        from models.mes.oee import OEERecord

        start_date = start_date or date.today() - timedelta(days=30)
        end_date = end_date or date.today()

        query = self.session.query(OEERecord).filter(
            OEERecord.record_date >= start_date,
            OEERecord.record_date <= end_date
        )
        if machine_id:
            query = query.filter(OEERecord.machine_id == machine_id)

        records = query.all()

        # Group by shift
        shift_data = defaultdict(list)
        for r in records:
            shift = r.shift or 'unspecified'
            if r.oee is not None:
                shift_data[shift].append({
                    'oee': r.oee,
                    'availability': r.availability,
                    'performance': r.performance,
                    'quality': r.quality
                })

        # Calculate averages per shift
        shift_summary = {}
        for shift, data in shift_data.items():
            if not data:
                continue
            shift_summary[shift] = {
                'record_count': len(data),
                'avg_oee': round(statistics.mean([d['oee'] for d in data]), 4),
                'avg_availability': round(statistics.mean([d['availability'] for d in data if d['availability']]), 4),
                'avg_performance': round(statistics.mean([d['performance'] for d in data if d['performance']]), 4),
                'avg_quality': round(statistics.mean([d['quality'] for d in data if d['quality']]), 4),
                'min_oee': min([d['oee'] for d in data]),
                'max_oee': max([d['oee'] for d in data]),
            }

        # Rank shifts by OEE
        ranked = sorted(shift_summary.items(), key=lambda x: x[1]['avg_oee'], reverse=True)

        return {
            'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'machine_id': machine_id,
            'shifts': shift_summary,
            'ranking': [{'shift': s, 'avg_oee': d['avg_oee']} for s, d in ranked],
            'best_shift': ranked[0][0] if ranked else None,
            'worst_shift': ranked[-1][0] if ranked else None,
        }

    def compare_oee_by_machine(
        self,
        machine_ids: List[str] = None,
        start_date: date = None,
        end_date: date = None
    ) -> Dict[str, Any]:
        """
        Compare OEE across different machines.

        Args:
            machine_ids: List of machines to compare
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            OEE comparison by machine
        """
        from models.mes.oee import OEERecord

        start_date = start_date or date.today() - timedelta(days=30)
        end_date = end_date or date.today()

        query = self.session.query(OEERecord).filter(
            OEERecord.record_date >= start_date,
            OEERecord.record_date <= end_date
        )
        if machine_ids:
            query = query.filter(OEERecord.machine_id.in_(machine_ids))

        records = query.all()

        # Group by machine
        machine_data = defaultdict(list)
        for r in records:
            if r.oee is not None:
                machine_data[r.machine_id].append({
                    'oee': r.oee,
                    'availability': r.availability,
                    'performance': r.performance,
                    'quality': r.quality
                })

        # Calculate averages per machine
        machine_summary = {}
        for machine_id, data in machine_data.items():
            if not data:
                continue
            machine_summary[machine_id] = {
                'record_count': len(data),
                'avg_oee': round(statistics.mean([d['oee'] for d in data]), 4),
                'avg_availability': round(statistics.mean([d['availability'] for d in data if d['availability']]), 4),
                'avg_performance': round(statistics.mean([d['performance'] for d in data if d['performance']]), 4),
                'avg_quality': round(statistics.mean([d['quality'] for d in data if d['quality']]), 4),
                'stdev_oee': round(statistics.stdev([d['oee'] for d in data]), 4) if len(data) > 1 else 0,
            }

        # Rank machines by OEE
        ranked = sorted(machine_summary.items(), key=lambda x: x[1]['avg_oee'], reverse=True)

        # Identify bottleneck (lowest OEE)
        bottleneck = ranked[-1][0] if ranked else None

        return {
            'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'machines': machine_summary,
            'ranking': [{'machine_id': m, 'avg_oee': d['avg_oee']} for m, d in ranked],
            'best_machine': ranked[0][0] if ranked else None,
            'bottleneck_machine': bottleneck,
            'total_machines': len(machine_summary),
        }


def calculate_oee(machine_id: str, record_date: date) -> Dict[str, Any]:
    """Calculate OEE for a machine on a given date."""
    with get_db_session() as session:
        service = OEEService(session)
        return service.calculate_oee(machine_id, record_date)


def get_oee_dashboard(machine_ids: List[str] = None, days: int = 7) -> Dict[str, Any]:
    """Get OEE dashboard data using database aggregation for efficiency."""
    from models.mes.oee import OEERecord
    from services.cache.cache_service import cached

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Cache key includes machine_ids and date range
    cache_key = f"oee_dashboard:{hash(tuple(machine_ids) if machine_ids else ())}-{days}"

    with get_db_session() as session:
        # Use database aggregate functions instead of loading all records
        query = session.query(
            func.avg(OEERecord.oee).label('avg_oee'),
            func.avg(OEERecord.availability).label('avg_availability'),
            func.avg(OEERecord.performance).label('avg_performance'),
            func.avg(OEERecord.quality).label('avg_quality'),
            func.count(OEERecord.id).label('record_count')
        ).filter(
            OEERecord.record_date >= start_date,
            OEERecord.record_date <= end_date
        )

        if machine_ids:
            query = query.filter(OEERecord.machine_id.in_(machine_ids))

        result = query.one()

        if result.record_count == 0:
            return {'average_oee': 0, 'average_availability': 0, 'average_performance': 0, 'average_quality': 0}

        return {
            'average_oee': float(result.avg_oee or 0) * 100,
            'average_availability': float(result.avg_availability or 0) * 100,
            'average_performance': float(result.avg_performance or 0) * 100,
            'average_quality': float(result.avg_quality or 0) * 100,
            'record_count': result.record_count,
            'date_range': {'start': start_date.isoformat(), 'end': end_date.isoformat()}
        }
