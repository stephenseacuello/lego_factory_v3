"""
Downtime Analysis Service
=========================
Comprehensive downtime tracking, root cause analysis, and cost calculation.

Features:
- Downtime event recording with categorization
- Root cause analysis (equipment, material, operator, process)
- Pareto analysis by multiple dimensions
- MTBF/MTTR trending
- Downtime cost calculation
- Automatic work order generation for recurring issues
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


class DowntimeCategory(str, Enum):
    """Primary downtime categories (ISA-95 aligned)."""
    BREAKDOWN = 'breakdown'
    CHANGEOVER = 'changeover'
    SETUP = 'setup'
    MATERIAL_SHORTAGE = 'material_shortage'
    QUALITY_HOLD = 'quality_hold'
    PLANNED_MAINTENANCE = 'planned_maintenance'
    UNPLANNED_MAINTENANCE = 'unplanned_maintenance'
    NO_OPERATOR = 'no_operator'
    NO_DEMAND = 'no_demand'
    TOOL_CHANGE = 'tool_change'
    CLEANING = 'cleaning'
    OTHER = 'other'


class RootCauseType(str, Enum):
    """Root cause categories for analysis."""
    EQUIPMENT = 'equipment'       # Machine/tool failure
    MATERIAL = 'material'         # Material quality/availability
    OPERATOR = 'operator'         # Human error, training
    PROCESS = 'process'           # Process design, recipe
    ENVIRONMENT = 'environment'   # External factors
    SUPPLY_CHAIN = 'supply_chain' # Vendor, logistics
    PLANNING = 'planning'         # Scheduling, sequencing
    UNKNOWN = 'unknown'


@dataclass
class DowntimeEvent:
    """Downtime event record."""
    event_id: str
    machine_id: str
    category: DowntimeCategory
    root_cause: RootCauseType
    start_time: datetime
    end_time: Optional[datetime]
    duration_minutes: Optional[float]
    reason_code: Optional[str]
    reason_description: Optional[str]
    operator_id: Optional[str]
    shift_id: Optional[str]
    product_id: Optional[str]
    cost: Optional[float] = None
    work_order_generated: bool = False


@dataclass
class DowntimeStatistics:
    """Downtime statistics summary."""
    total_events: int
    total_downtime_minutes: float
    total_downtime_hours: float
    average_duration_minutes: float
    mtbf_hours: Optional[float]
    mttr_minutes: Optional[float]
    availability_percent: float
    estimated_cost: float


# Mapping from local DowntimeCategory values to DowntimeReason enum values.
# This bridges the ISA-95 aligned API categories to the DB model's reason enum.
_CATEGORY_TO_REASON = {
    'breakdown': 'maintenance_unplanned',
    'changeover': 'changeover',
    'setup': 'setup',
    'material_shortage': 'material',
    'quality_hold': 'quality_issue',
    'planned_maintenance': 'maintenance_planned',
    'unplanned_maintenance': 'maintenance_unplanned',
    'no_operator': 'operator',
    'no_demand': 'other',
    'tool_change': 'tooling',
    'cleaning': 'other',
    'other': 'other',
}

# DowntimeReason values that represent unplanned failures (for MTBF/MTTR).
_FAILURE_REASONS = {
    'maintenance_unplanned',
    'tooling',
    'nozzle_clog',
    'bed_adhesion',
    'layer_shift',
    'power',
    'software',
}


class DowntimeService:
    """
    Comprehensive downtime analysis service.

    Provides:
    - Downtime event recording with root cause
    - Multi-dimensional Pareto analysis
    - MTBF/MTTR calculation and trending
    - Downtime cost estimation
    - Recurring issue detection
    - Automatic work order generation
    """

    # Default cost rates ($/minute)
    DEFAULT_COST_RATES = {
        'fdm': 0.50,      # FDM printer
        'cnc': 2.00,      # CNC machine
        'laser': 1.00,    # Laser cutter
        'assembly': 0.75, # Assembly station
        'default': 1.00,
    }

    # Root cause mapping for auto-categorization
    ROOT_CAUSE_KEYWORDS = {
        RootCauseType.EQUIPMENT: ['failure', 'broken', 'malfunction', 'worn', 'jam', 'stuck'],
        RootCauseType.MATERIAL: ['material', 'filament', 'stock', 'shortage', 'quality'],
        RootCauseType.OPERATOR: ['error', 'mistake', 'forgot', 'training', 'absent'],
        RootCauseType.PROCESS: ['recipe', 'parameter', 'setting', 'speed', 'temperature'],
        RootCauseType.SUPPLY_CHAIN: ['delivery', 'vendor', 'late', 'shipment'],
        RootCauseType.PLANNING: ['schedule', 'sequence', 'changeover', 'batch'],
    }

    def __init__(self, session: Session):
        self.session = session
        self._cost_rates = self.DEFAULT_COST_RATES.copy()

    # =========================================================================
    # DOWNTIME RECORDING
    # =========================================================================

    def record_downtime(
        self,
        machine_id: str,
        category: str,
        start_time: datetime,
        end_time: datetime = None,
        reason_code: str = None,
        reason_description: str = None,
        root_cause: str = None,
        operator_id: str = None,
        shift_id: str = None,
        product_id: str = None
    ) -> Dict[str, Any]:
        """
        Record a downtime event with optional root cause.

        Args:
            machine_id: Machine ID (string, e.g. "bambu-ps1")
            category: Downtime category (from DowntimeCategory enum values)
            start_time: Downtime start
            end_time: Downtime end (optional, for open events)
            reason_code: Reason code
            reason_description: Description of what happened
            root_cause: Root cause category
            operator_id: Operator on shift
            shift_id: Shift ID
            product_id: Product being made when downtime occurred

        Returns:
            Dict with recorded event info
        """
        from models.scada.machines import Machine
        from models.mes.oee import DowntimeEvent as DBDowntimeEvent, DowntimeReason

        # Validate machine exists
        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()

        if not machine:
            return {'error': f'Machine {machine_id} not found'}

        # Calculate duration
        duration = None
        if end_time:
            duration = round((end_time - start_time).total_seconds() / 60, 1)

        # Auto-detect root cause if not provided
        if not root_cause and reason_description:
            root_cause = self._auto_detect_root_cause(reason_description)
        root_cause = root_cause or RootCauseType.UNKNOWN.value

        # Calculate cost
        cost = self._calculate_downtime_cost(machine_id, duration) if duration else None

        # Map the category string to the closest DowntimeReason enum value
        reason_value = _CATEGORY_TO_REASON.get(category, 'other')
        try:
            reason_enum = DowntimeReason(reason_value)
        except ValueError:
            reason_enum = DowntimeReason.OTHER

        # Determine if this is planned downtime
        planned = category in (
            DowntimeCategory.PLANNED_MAINTENANCE.value,
            DowntimeCategory.SETUP.value,
            DowntimeCategory.CHANGEOVER.value,
            DowntimeCategory.CLEANING.value,
            DowntimeCategory.NO_DEMAND.value,
        )

        # Create DowntimeEvent record
        event = DBDowntimeEvent(
            machine_id=machine_id,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration,
            reason=reason_enum,
            planned=planned,
            description=reason_description,
            root_cause=root_cause,
            reported_by=operator_id,
        )
        self.session.add(event)
        self.session.flush()

        # Check for recurring issues
        if duration and duration > 10:  # Only for significant downtime
            self._check_recurring_issue(machine_id, category, reason_code)

        logger.info(f"Recorded downtime for {machine_id}: {category}, {duration} min")

        return {
            'status': 'recorded',
            'event_id': str(event.id),
            'duration_minutes': duration,
            'estimated_cost': cost,
            'root_cause': root_cause
        }

    def close_downtime(
        self,
        event_id: str,
        end_time: datetime = None,
        resolution_notes: str = None
    ) -> Dict[str, Any]:
        """Close an open downtime event."""
        from models.mes.oee import DowntimeEvent as DBDowntimeEvent

        event = self.session.query(DBDowntimeEvent).filter(
            DBDowntimeEvent.id == event_id
        ).first()

        if not event:
            return {'error': f'Event {event_id} not found'}

        end_time = end_time or datetime.utcnow()
        duration = round((end_time - event.start_time).total_seconds() / 60, 1)
        cost = self._calculate_downtime_cost(event.machine_id, duration)

        event.end_time = end_time
        event.duration_minutes = duration
        if resolution_notes:
            event.corrective_action = resolution_notes

        self.session.flush()

        return {
            'status': 'closed',
            'event_id': str(event.id),
            'duration_minutes': duration,
            'estimated_cost': cost
        }

    def _auto_detect_root_cause(self, description: str) -> str:
        """Auto-detect root cause from description keywords."""
        description_lower = description.lower()

        for cause_type, keywords in self.ROOT_CAUSE_KEYWORDS.items():
            if any(kw in description_lower for kw in keywords):
                return cause_type.value

        return RootCauseType.UNKNOWN.value

    def _calculate_downtime_cost(self, machine_id: str, duration_minutes: float) -> float:
        """Calculate estimated cost of downtime."""
        machine_type = self._get_machine_type(machine_id)
        rate = self._cost_rates.get(machine_type, self._cost_rates['default'])
        return round(rate * duration_minutes, 2)

    def set_cost_rate(self, machine_type: str, rate_per_minute: float):
        """Set custom cost rate for a machine type."""
        self._cost_rates[machine_type] = rate_per_minute

    # =========================================================================
    # PARETO ANALYSIS
    # =========================================================================

    def get_pareto(
        self,
        machine_id: str = None,
        period_days: int = 30,
        group_by: str = 'category'  # 'category', 'root_cause', 'machine', 'shift', 'product'
    ) -> Dict[str, Any]:
        """
        Get Pareto analysis of downtime.

        Args:
            machine_id: Filter by machine (optional)
            period_days: Analysis period
            group_by: Dimension to group by

        Returns:
            Pareto data with cumulative percentages
        """
        from models.mes.oee import DowntimeEvent as DBDowntimeEvent

        cutoff = datetime.utcnow() - timedelta(days=period_days)

        query = self.session.query(DBDowntimeEvent).filter(
            DBDowntimeEvent.start_time >= cutoff
        )

        if machine_id:
            query = query.filter(DBDowntimeEvent.machine_id == machine_id)

        events = query.all()

        # Group by specified dimension
        grouped = defaultdict(lambda: {'minutes': 0, 'count': 0, 'cost': 0})

        for event in events:
            duration = event.duration_minutes or 0
            cost = self._calculate_downtime_cost(event.machine_id, duration) if duration else 0

            if group_by == 'category':
                key = event.reason.value if event.reason else 'other'
            elif group_by == 'root_cause':
                key = event.root_cause or 'unknown'
            elif group_by == 'machine':
                key = event.machine_id
            elif group_by == 'shift':
                key = 'unknown'  # DowntimeEvent doesn't have shift_id
            elif group_by == 'product':
                key = str(event.job_id) if event.job_id else 'unknown'
            else:
                key = event.reason.value if event.reason else 'other'

            grouped[key]['minutes'] += duration
            grouped[key]['count'] += 1
            grouped[key]['cost'] += cost

        # Sort by duration descending
        total_minutes = sum(g['minutes'] for g in grouped.values()) or 1
        total_cost = sum(g['cost'] for g in grouped.values())
        sorted_groups = sorted(grouped.items(), key=lambda x: x[1]['minutes'], reverse=True)

        # Build Pareto data
        pareto_data = []
        cumulative = 0
        for key, data in sorted_groups:
            cumulative += data['minutes']
            pareto_data.append({
                group_by: key,
                'duration_minutes': round(data['minutes'], 1),
                'event_count': data['count'],
                'estimated_cost': round(data['cost'], 2),
                'percentage': round(data['minutes'] / total_minutes * 100, 1),
                'cumulative_pct': round(cumulative / total_minutes * 100, 1),
            })

        return {
            'period_days': period_days,
            'group_by': group_by,
            'total_downtime_minutes': round(total_minutes, 1),
            'total_downtime_hours': round(total_minutes / 60, 1),
            'total_estimated_cost': round(total_cost, 2),
            'data': pareto_data,
            'event_count': len(events),
        }

    def get_root_cause_analysis(
        self,
        machine_id: str = None,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Get root cause analysis with recommendations."""
        pareto = self.get_pareto(machine_id, period_days, group_by='root_cause')

        # Generate recommendations based on top root causes
        recommendations = []
        for item in pareto['data'][:3]:  # Top 3 root causes
            root_cause = item['root_cause']
            pct = item['percentage']

            if root_cause == 'equipment':
                recommendations.append({
                    'root_cause': root_cause,
                    'recommendation': 'Increase preventive maintenance frequency',
                    'impact_pct': pct
                })
            elif root_cause == 'material':
                recommendations.append({
                    'root_cause': root_cause,
                    'recommendation': 'Review supplier quality and buffer stock levels',
                    'impact_pct': pct
                })
            elif root_cause == 'operator':
                recommendations.append({
                    'root_cause': root_cause,
                    'recommendation': 'Enhance operator training and work instructions',
                    'impact_pct': pct
                })
            elif root_cause == 'process':
                recommendations.append({
                    'root_cause': root_cause,
                    'recommendation': 'Review and optimize process parameters',
                    'impact_pct': pct
                })

        pareto['recommendations'] = recommendations
        return pareto

    # =========================================================================
    # MTBF/MTTR ANALYSIS
    # =========================================================================

    def get_mtbf_mttr(
        self,
        machine_id: str,
        period_days: int = 90
    ) -> Dict[str, Any]:
        """
        Calculate MTBF (Mean Time Between Failures) and MTTR (Mean Time To Repair).

        Args:
            machine_id: Machine to analyze (string ID, e.g. "bambu-ps1")
            period_days: Analysis period

        Returns:
            MTBF/MTTR statistics
        """
        from models.scada.machines import Machine
        from models.mes.oee import DowntimeEvent as DBDowntimeEvent, DowntimeReason

        cutoff = datetime.utcnow() - timedelta(days=period_days)

        # Validate machine exists
        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()

        if not machine:
            return {'error': f'Machine {machine_id} not found'}

        # Get failure events (unplanned failures only)
        failure_reasons = [DowntimeReason(r) for r in _FAILURE_REASONS]

        failure_events = self.session.query(DBDowntimeEvent).filter(
            DBDowntimeEvent.machine_id == machine_id,
            DBDowntimeEvent.start_time >= cutoff,
            DBDowntimeEvent.reason.in_(failure_reasons)
        ).order_by(DBDowntimeEvent.start_time).all()

        if not failure_events:
            return {
                'machine_id': machine_id,
                'period_days': period_days,
                'failure_count': 0,
                'mtbf_hours': None,
                'mttr_minutes': None,
                'availability_percent': 100,
                'message': 'No failures recorded in period'
            }

        # Calculate MTTR (Mean Time To Repair)
        repair_times = []
        for event in failure_events:
            if event.duration_minutes:
                repair_times.append(event.duration_minutes)

        mttr = sum(repair_times) / len(repair_times) if repair_times else 0

        # Calculate MTBF (Time between failures)
        if len(failure_events) > 1:
            intervals = []
            for i in range(1, len(failure_events)):
                interval = (failure_events[i].start_time - failure_events[i-1].start_time)
                intervals.append(interval.total_seconds() / 3600)  # Hours
            mtbf = sum(intervals) / len(intervals)
        else:
            # Single failure - estimate from period
            mtbf = period_days * 24 / len(failure_events)

        # Calculate availability
        total_downtime = sum(repair_times)  # Minutes
        total_time = period_days * 24 * 60  # Minutes
        availability = ((total_time - total_downtime) / total_time) * 100

        return {
            'machine_id': machine_id,
            'period_days': period_days,
            'failure_count': len(failure_events),
            'mtbf_hours': round(mtbf, 1),
            'mttr_minutes': round(mttr, 1),
            'total_downtime_minutes': round(total_downtime, 1),
            'availability_percent': round(availability, 2)
        }

    def get_mtbf_trend(
        self,
        machine_id: str,
        period_months: int = 6
    ) -> List[Dict[str, Any]]:
        """Get MTBF trend over time (monthly)."""
        trend = []

        for i in range(period_months - 1, -1, -1):
            end_date = datetime.utcnow() - timedelta(days=i * 30)
            start_date = end_date - timedelta(days=30)

            # Calculate MTBF for this month
            mtbf_data = self.get_mtbf_mttr(machine_id, period_days=30)

            trend.append({
                'month': end_date.strftime('%Y-%m'),
                'mtbf_hours': mtbf_data.get('mtbf_hours'),
                'mttr_minutes': mtbf_data.get('mttr_minutes'),
                'failure_count': mtbf_data.get('failure_count', 0)
            })

        return trend

    # =========================================================================
    # RECURRING ISSUE DETECTION & WORK ORDER GENERATION
    # =========================================================================

    def _check_recurring_issue(
        self,
        machine_id: str,
        category: str,
        reason_code: str
    ) -> bool:
        """
        Check for recurring issues and generate work order if threshold met.

        Returns True if recurring issue detected and work order created.
        """
        from models.mes.oee import DowntimeEvent as DBDowntimeEvent, DowntimeReason

        # Check for same issue in last 7 days
        cutoff = datetime.utcnow() - timedelta(days=7)

        # Map the category to the corresponding DowntimeReason for filtering
        reason_value = _CATEGORY_TO_REASON.get(category, 'other')
        try:
            reason_enum = DowntimeReason(reason_value)
        except ValueError:
            reason_enum = DowntimeReason.OTHER

        similar_count = self.session.query(DBDowntimeEvent).filter(
            DBDowntimeEvent.machine_id == machine_id,
            DBDowntimeEvent.start_time >= cutoff,
            DBDowntimeEvent.reason == reason_enum
        ).count()

        # Threshold: 3 similar issues in 7 days
        RECURRING_THRESHOLD = 3

        if similar_count >= RECURRING_THRESHOLD:
            work_order = self._create_maintenance_work_order(
                machine_id=machine_id,
                reason=f"Recurring {category} issue - {similar_count} occurrences in 7 days",
                priority='high' if similar_count >= 5 else 'medium'
            )
            return work_order is not None

        return False

    def _create_maintenance_work_order(
        self,
        machine_id: str,
        reason: str,
        priority: str = 'medium'
    ) -> Optional[str]:
        """Create a maintenance work order for recurring issues."""
        try:
            from models.cmms.maintenance import MaintenanceWorkOrder, MaintenanceType, MaintenanceStatus

            wo = MaintenanceWorkOrder(
                asset_id=machine_id,
                description=f"Auto-generated: {reason}",
                maintenance_type=MaintenanceType.CORRECTIVE,
                status=MaintenanceStatus.REQUESTED,
                priority=priority,
                created_at=datetime.utcnow(),
                requested_by='system_cbm'
            )
            self.session.add(wo)
            self.session.flush()

            logger.info(f"Auto-generated maintenance work order {wo.work_order_number} for {machine_id}")
            return str(wo.id)

        except ImportError:
            logger.warning("CMMS models not available for work order generation")
            return None

    def get_recurring_issues(
        self,
        period_days: int = 30,
        min_occurrences: int = 3
    ) -> List[Dict[str, Any]]:
        """Get list of recurring issues across all machines."""
        from models.mes.oee import DowntimeEvent as DBDowntimeEvent

        cutoff = datetime.utcnow() - timedelta(days=period_days)

        events = self.session.query(DBDowntimeEvent).filter(
            DBDowntimeEvent.start_time >= cutoff
        ).all()

        # Group by machine + reason
        issue_groups = defaultdict(list)
        for event in events:
            key = (
                event.machine_id,
                event.reason.value if event.reason else 'other',
            )
            issue_groups[key].append(event)

        # Find recurring issues
        recurring = []
        for (mid, reason), group_events in issue_groups.items():
            if len(group_events) >= min_occurrences:
                total_duration = sum(
                    e.duration_minutes or 0
                    for e in group_events
                )
                recurring.append({
                    'machine_id': mid,
                    'category': reason,
                    'reason_code': reason,
                    'occurrence_count': len(group_events),
                    'total_downtime_minutes': round(total_duration, 1),
                    'average_duration_minutes': round(total_duration / len(group_events), 1),
                    'last_occurrence': max(e.start_time for e in group_events).isoformat()
                })

        # Sort by occurrence count
        recurring.sort(key=lambda x: x['occurrence_count'], reverse=True)

        return recurring

    # =========================================================================
    # TOP LOSSES & SUMMARY
    # =========================================================================

    def get_top_losses(
        self,
        limit: int = 10,
        period_days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get top downtime losses across all machines."""
        from models.mes.oee import DowntimeEvent as DBDowntimeEvent

        cutoff = datetime.utcnow() - timedelta(days=period_days)

        events = self.session.query(DBDowntimeEvent).filter(
            DBDowntimeEvent.start_time >= cutoff
        ).all()

        machine_losses = defaultdict(lambda: {
            'total_minutes': 0,
            'events': 0,
            'total_cost': 0,
            'categories': defaultdict(float)
        })

        for event in events:
            mid = event.machine_id
            duration = event.duration_minutes or 0
            cost = self._calculate_downtime_cost(mid, duration) if duration else 0
            category = event.reason.value if event.reason else 'other'

            machine_losses[mid]['total_minutes'] += duration
            machine_losses[mid]['events'] += 1
            machine_losses[mid]['total_cost'] += cost
            machine_losses[mid]['categories'][category] += duration

        # Sort and format
        sorted_losses = sorted(
            machine_losses.items(),
            key=lambda x: x[1]['total_minutes'],
            reverse=True
        )

        results = []
        for mid, data in sorted_losses[:limit]:
            # Find top category
            top_category = max(data['categories'].items(), key=lambda x: x[1]) if data['categories'] else ('other', 0)

            results.append({
                'machine_id': mid,
                'total_downtime_minutes': round(data['total_minutes'], 1),
                'total_downtime_hours': round(data['total_minutes'] / 60, 1),
                'event_count': data['events'],
                'estimated_cost': round(data['total_cost'], 2),
                'top_category': top_category[0],
                'top_category_minutes': round(top_category[1], 1)
            })

        return results

    def get_statistics(
        self,
        machine_id: str = None,
        period_days: int = 30
    ) -> DowntimeStatistics:
        """Get comprehensive downtime statistics."""
        pareto = self.get_pareto(machine_id, period_days)

        total_events = pareto['event_count']
        total_minutes = pareto['total_downtime_minutes']
        total_cost = pareto['total_estimated_cost']

        avg_duration = total_minutes / total_events if total_events > 0 else 0

        # Calculate availability
        total_time_minutes = period_days * 24 * 60
        availability = ((total_time_minutes - total_minutes) / total_time_minutes) * 100

        # Get MTBF/MTTR if specific machine
        mtbf = None
        mttr = None
        if machine_id:
            mtbf_data = self.get_mtbf_mttr(machine_id, period_days)
            mtbf = mtbf_data.get('mtbf_hours')
            mttr = mtbf_data.get('mttr_minutes')

        return DowntimeStatistics(
            total_events=total_events,
            total_downtime_minutes=round(total_minutes, 1),
            total_downtime_hours=round(total_minutes / 60, 1),
            average_duration_minutes=round(avg_duration, 1),
            mtbf_hours=mtbf,
            mttr_minutes=mttr,
            availability_percent=round(availability, 2),
            estimated_cost=round(total_cost, 2)
        )

    def _get_machine_type(self, machine_id: str) -> str:
        """Get machine type from ID."""
        machine_lower = machine_id.lower()
        if 'bambu' in machine_lower or 'creality' in machine_lower or 'fdm' in machine_lower:
            return 'fdm'
        elif 'cnc' in machine_lower or 'bantam' in machine_lower:
            return 'cnc'
        elif 'laser' in machine_lower:
            return 'laser'
        elif 'assembly' in machine_lower:
            return 'assembly'
        return 'default'


# Convenience functions for API and tasks
def get_downtime_pareto(session: Session, **kwargs) -> Dict[str, Any]:
    """Get downtime Pareto analysis."""
    service = DowntimeService(session)
    return service.get_pareto(**kwargs)


def get_machine_mtbf(session: Session, machine_id: str, **kwargs) -> Dict[str, Any]:
    """Get MTBF/MTTR for a machine."""
    service = DowntimeService(session)
    return service.get_mtbf_mttr(machine_id, **kwargs)
