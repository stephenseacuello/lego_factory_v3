"""
OEE Service

Overall Equipment Effectiveness tracking and calculation:
- Availability = Run Time / Planned Production Time
- Performance = (Ideal Cycle Time × Total Count) / Run Time
- Quality = Good Count / Total Count
- OEE = Availability × Performance × Quality

World-class OEE target: 85%
"""

from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import WorkCenter, WorkOrder, WorkOrderOperation
from models.analytics import (
    OEEEvent, OEEEventType, DowntimeReasonCode
)


class OEEService:
    """
    OEE Service - Overall Equipment Effectiveness tracking.

    Provides real-time OEE calculation and historical analysis
    for manufacturing equipment following ISA-95 patterns.
    """

    def __init__(self, session: Session):
        self.session = session

    # Event Recording

    def start_production(
        self,
        work_center_id: str,
        work_order_id: str = None,
        operation_id: str = None,
        ideal_cycle_time_sec: float = None,
        operator_id: str = None
    ) -> OEEEvent:
        """
        Start a production run event.

        Args:
            work_center_id: Work center starting production
            work_order_id: Associated work order
            operation_id: Associated operation
            ideal_cycle_time_sec: Standard cycle time per part
            operator_id: Operator running the machine

        Returns:
            Created OEEEvent instance
        """
        # End any existing production event
        self._end_active_events(work_center_id)

        event = OEEEvent(
            work_center_id=work_center_id,
            work_order_id=work_order_id,
            operation_id=operation_id,
            event_type=OEEEventType.PRODUCTION.value,
            start_time=datetime.utcnow(),
            ideal_cycle_time_sec=ideal_cycle_time_sec,
            operator_id=operator_id,
            shift_date=date.today(),
            shift_number=self._get_shift_number()
        )

        self.session.add(event)
        self.session.commit()
        return event

    def end_production(
        self,
        work_center_id: str,
        parts_produced: int = 0,
        parts_defective: int = 0
    ) -> Optional[OEEEvent]:
        """
        End a production run and record results.

        Args:
            work_center_id: Work center ending production
            parts_produced: Total parts produced
            parts_defective: Defective parts (scrap + rework)

        Returns:
            Updated OEEEvent instance
        """
        event = self._get_active_production(work_center_id)
        if not event:
            return None

        event.end_event(parts_produced, parts_defective)
        self.session.commit()
        return event

    def record_downtime(
        self,
        work_center_id: str,
        reason_code: str,
        is_planned: bool = False,
        description: str = None,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> OEEEvent:
        """
        Record a downtime event.

        Args:
            work_center_id: Work center experiencing downtime
            reason_code: Downtime reason code
            is_planned: Whether downtime was planned
            description: Additional description
            start_time: When downtime started (default: now)
            end_time: When downtime ended (None if ongoing)

        Returns:
            Created OEEEvent instance
        """
        # End any active production
        self._end_active_events(work_center_id)

        event_type = (OEEEventType.DOWNTIME_PLANNED.value if is_planned
                     else OEEEventType.DOWNTIME_UNPLANNED.value)

        event = OEEEvent(
            work_center_id=work_center_id,
            event_type=event_type,
            start_time=start_time or datetime.utcnow(),
            reason_code=reason_code,
            reason_description=description,
            shift_date=date.today(),
            shift_number=self._get_shift_number()
        )

        if end_time:
            event.end_time = end_time
            delta = end_time - event.start_time
            event.duration_minutes = delta.total_seconds() / 60

        self.session.add(event)
        self.session.commit()
        return event

    def end_downtime(self, work_center_id: str) -> Optional[OEEEvent]:
        """End an active downtime event."""
        event = self.session.query(OEEEvent).filter(
            OEEEvent.work_center_id == work_center_id,
            OEEEvent.end_time.is_(None),
            OEEEvent.event_type.in_([
                OEEEventType.DOWNTIME_PLANNED.value,
                OEEEventType.DOWNTIME_UNPLANNED.value
            ])
        ).first()

        if event:
            event.end_time = datetime.utcnow()
            delta = event.end_time - event.start_time
            event.duration_minutes = delta.total_seconds() / 60
            self.session.commit()

        return event

    def record_setup(
        self,
        work_center_id: str,
        work_order_id: str = None,
        duration_minutes: float = None
    ) -> OEEEvent:
        """
        Record a setup/changeover event.

        Args:
            work_center_id: Work center being set up
            work_order_id: Work order being set up for
            duration_minutes: Setup duration (if completed)

        Returns:
            Created OEEEvent instance
        """
        self._end_active_events(work_center_id)

        event = OEEEvent(
            work_center_id=work_center_id,
            work_order_id=work_order_id,
            event_type=OEEEventType.SETUP.value,
            start_time=datetime.utcnow(),
            shift_date=date.today(),
            shift_number=self._get_shift_number()
        )

        if duration_minutes:
            event.end_time = event.start_time + timedelta(minutes=duration_minutes)
            event.duration_minutes = duration_minutes

        self.session.add(event)
        self.session.commit()
        return event

    # OEE Calculation

    def calculate_oee(
        self,
        work_center_id: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict[str, Any]:
        """
        Calculate OEE metrics for a work center.

        Args:
            work_center_id: Work center ID
            start_date: Start of period (default: today)
            end_date: End of period (default: now)

        Returns:
            Dictionary with availability, performance, quality, oee
        """
        if not start_date:
            start_date = datetime.combine(date.today(), datetime.min.time())
        if not end_date:
            end_date = datetime.utcnow()

        return OEEEvent.calculate_oee(
            self.session,
            work_center_id,
            start_date,
            end_date
        )

    def get_oee_dashboard(
        self,
        work_center_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        Get OEE dashboard data for all or selected work centers.

        Returns current shift OEE for each work center.
        """
        if not work_center_ids:
            work_centers = self.session.query(WorkCenter).all()
            work_center_ids = [str(wc.id) for wc in work_centers]

        today = datetime.combine(date.today(), datetime.min.time())
        now = datetime.utcnow()

        dashboard = {
            'timestamp': now.isoformat(),
            'period': {
                'start': today.isoformat(),
                'end': now.isoformat()
            },
            'work_centers': [],
            'summary': {
                'average_oee': 0,
                'total_parts': 0,
                'total_good_parts': 0,
                'total_downtime_minutes': 0
            }
        }

        total_oee = 0
        for wc_id in work_center_ids:
            wc = self.session.query(WorkCenter).filter(
                WorkCenter.id == wc_id
            ).first()

            if not wc:
                continue

            oee = self.calculate_oee(wc_id, today, now)

            wc_data = {
                'id': str(wc.id),
                'name': wc.name,
                'code': wc.code,
                'type': wc.type,
                'status': wc.status,
                **oee
            }

            dashboard['work_centers'].append(wc_data)
            total_oee += oee['oee']
            dashboard['summary']['total_parts'] += oee.get('total_parts', 0)
            dashboard['summary']['total_good_parts'] += oee.get('good_parts', 0)
            dashboard['summary']['total_downtime_minutes'] += oee.get('downtime_minutes', 0)

        if work_center_ids:
            dashboard['summary']['average_oee'] = round(
                total_oee / len(work_center_ids), 2
            )

        return dashboard

    def get_oee_trend(
        self,
        work_center_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get daily OEE trend for a work center.

        Args:
            work_center_id: Work center ID
            days: Number of days of history

        Returns:
            List of daily OEE data points
        """
        trend = []
        for i in range(days):
            day = date.today() - timedelta(days=i)
            start = datetime.combine(day, datetime.min.time())
            end = datetime.combine(day, datetime.max.time())

            oee = self.calculate_oee(work_center_id, start, end)
            trend.append({
                'date': day.isoformat(),
                **oee
            })

        return list(reversed(trend))

    def get_downtime_pareto(
        self,
        work_center_id: str = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get Pareto analysis of downtime reasons.

        Args:
            work_center_id: Optional work center filter
            days: Number of days of history

        Returns:
            List of downtime reasons sorted by total time
        """
        return OEEEvent.get_downtime_pareto(
            self.session,
            work_center_id,
            days
        )

    # Real-time Status

    def get_work_center_status(self, work_center_id: str) -> Dict[str, Any]:
        """
        Get real-time status of a work center.

        Returns:
            Dictionary with current status, active event, etc.
        """
        wc = self.session.query(WorkCenter).filter(
            WorkCenter.id == work_center_id
        ).first()

        if not wc:
            raise ValueError(f"Work center {work_center_id} not found")

        # Get active event
        active_event = self.session.query(OEEEvent).filter(
            OEEEvent.work_center_id == work_center_id,
            OEEEvent.end_time.is_(None)
        ).first()

        status = {
            'work_center': {
                'id': str(wc.id),
                'name': wc.name,
                'code': wc.code,
                'type': wc.type,
                'status': wc.status
            },
            'active_event': None,
            'current_shift_oee': self.calculate_oee(work_center_id)
        }

        if active_event:
            status['active_event'] = {
                'id': str(active_event.id),
                'type': active_event.event_type,
                'start_time': active_event.start_time.isoformat(),
                'duration_minutes': (
                    (datetime.utcnow() - active_event.start_time).total_seconds() / 60
                ),
                'work_order_id': str(active_event.work_order_id) if active_event.work_order_id else None,
                'parts_produced': active_event.parts_produced
            }

        return status

    # Helper Methods

    def _get_active_production(self, work_center_id: str) -> Optional[OEEEvent]:
        """Get active production event for work center."""
        return self.session.query(OEEEvent).filter(
            OEEEvent.work_center_id == work_center_id,
            OEEEvent.event_type == OEEEventType.PRODUCTION.value,
            OEEEvent.end_time.is_(None)
        ).first()

    def _end_active_events(self, work_center_id: str):
        """End any active events for a work center."""
        active_events = self.session.query(OEEEvent).filter(
            OEEEvent.work_center_id == work_center_id,
            OEEEvent.end_time.is_(None)
        ).all()

        for event in active_events:
            event.end_time = datetime.utcnow()
            delta = event.end_time - event.start_time
            event.duration_minutes = delta.total_seconds() / 60

    def _get_shift_number(self) -> int:
        """
        Determine current shift number based on time.

        Default: 3 shifts of 8 hours each
        - Shift 1: 06:00 - 14:00
        - Shift 2: 14:00 - 22:00
        - Shift 3: 22:00 - 06:00
        """
        hour = datetime.now().hour

        if 6 <= hour < 14:
            return 1
        elif 14 <= hour < 22:
            return 2
        else:
            return 3


# Standard OEE benchmarks
OEE_BENCHMARKS = {
    'world_class': {
        'availability': 90,
        'performance': 95,
        'quality': 99.9,
        'oee': 85
    },
    'good': {
        'availability': 85,
        'performance': 90,
        'quality': 99,
        'oee': 75
    },
    'average': {
        'availability': 80,
        'performance': 85,
        'quality': 98,
        'oee': 60
    },
    'typical_3d_printer': {
        'availability': 75,  # Longer setup, bed leveling
        'performance': 80,  # Variable print times
        'quality': 95,      # Some failed prints
        'oee': 57
    },
    'typical_cnc': {
        'availability': 85,
        'performance': 90,
        'quality': 99,
        'oee': 76
    }
}
