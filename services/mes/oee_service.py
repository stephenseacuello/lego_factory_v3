"""
LEGO Factory v3 - OEE Service
=============================
Overall Equipment Effectiveness calculation and tracking.
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from config.database import get_db_session

logger = logging.getLogger(__name__)


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


def calculate_oee(machine_id: str, record_date: date) -> Dict[str, Any]:
    """Calculate OEE for a machine on a given date."""
    with get_db_session() as session:
        service = OEEService(session)
        return service.calculate_oee(machine_id, record_date)


def get_oee_dashboard(machine_ids: List[str] = None, days: int = 7) -> Dict[str, Any]:
    """Get OEE dashboard data."""
    from models.mes.oee import OEERecord

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    with get_db_session() as session:
        query = session.query(OEERecord).filter(
            OEERecord.record_date >= start_date,
            OEERecord.record_date <= end_date
        )

        if machine_ids:
            query = query.filter(OEERecord.machine_id.in_(machine_ids))

        records = query.all()

        if not records:
            return {'average_oee': 0, 'average_availability': 0, 'average_performance': 0, 'average_quality': 0}

        return {
            'average_oee': sum(r.oee for r in records) / len(records) * 100,
            'average_availability': sum(r.availability for r in records) / len(records) * 100,
            'average_performance': sum(r.performance for r in records) / len(records) * 100,
            'average_quality': sum(r.quality for r in records) / len(records) * 100,
            'record_count': len(records),
            'date_range': {'start': start_date.isoformat(), 'end': end_date.isoformat()}
        }
