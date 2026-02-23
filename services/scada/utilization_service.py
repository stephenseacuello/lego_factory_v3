"""
Machine Utilization Tracking & Health Scoring Service
=====================================================
Calculates machine utilization percentages and composite health scores.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from decimal import Decimal

from services.cache.cache_service import cached


class UtilizationService:
    """Tracks machine utilization and calculates health scores."""

    def __init__(self, session):
        self.session = session

    def calculate_utilization(self, machine_id: str, period_days: int = 7) -> Dict[str, Any]:
        """Calculate machine utilization breakdown over a time period."""
        from models.scada.machines import Machine, MachineEvent, MachineState

        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()

        if not machine:
            return {'error': 'Machine not found'}

        cutoff = datetime.utcnow() - timedelta(days=period_days)

        events = self.session.query(MachineEvent).filter(
            MachineEvent.machine_id == machine.id,
            MachineEvent.created_at >= cutoff
        ).order_by(MachineEvent.created_at).all()

        total_seconds = period_days * 24 * 3600
        state_seconds = {
            'running': 0, 'idle': 0, 'setup': 0,
            'alarm': 0, 'maintenance': 0, 'disconnected': 0, 'other': 0
        }

        if events:
            prev_time = cutoff
            prev_state = 'idle'
            for event in events:
                duration = (event.created_at - prev_time).total_seconds()
                bucket = prev_state if prev_state in state_seconds else 'other'
                state_seconds[bucket] += max(0, duration)
                prev_time = event.created_at
                prev_state = event.new_state

            remaining = (datetime.utcnow() - prev_time).total_seconds()
            bucket = prev_state if prev_state in state_seconds else 'other'
            state_seconds[bucket] += max(0, remaining)
        else:
            current = machine.current_state.value if machine.current_state else 'idle'
            bucket = current if current in state_seconds else 'other'
            state_seconds[bucket] = total_seconds

        utilization_pct = round((state_seconds['running'] / max(total_seconds, 1)) * 100, 1)

        return {
            'machine_id': machine_id,
            'period_days': period_days,
            'utilization_pct': utilization_pct,
            'breakdown': {k: round(v / max(total_seconds, 1) * 100, 1) for k, v in state_seconds.items()},
            'total_running_hours': round(state_seconds['running'] / 3600, 1),
            'total_idle_hours': round(state_seconds['idle'] / 3600, 1),
            'total_down_hours': round((state_seconds['alarm'] + state_seconds['maintenance']) / 3600, 1),
        }

    def calculate_health_score(self, machine_id: str) -> Dict[str, Any]:
        """Calculate composite health score 0-100 for a machine."""
        from models.scada.machines import Machine, MachineEvent

        machine = self.session.query(Machine).filter(
            Machine.machine_id == machine_id
        ).first()

        if not machine:
            return {'error': 'Machine not found'}

        scores = {}

        # Uptime score (40% weight) - based on 7-day utilization
        util = self.calculate_utilization(machine_id, 7)
        uptime_pct = 100 - util['breakdown'].get('alarm', 0) - util['breakdown'].get('disconnected', 0)
        scores['uptime'] = min(100, max(0, uptime_pct))

        # Alarm frequency score (30% weight) - fewer alarms = higher score
        cutoff_30d = datetime.utcnow() - timedelta(days=30)
        alarm_count = self.session.query(MachineEvent).filter(
            MachineEvent.machine_id == machine.id,
            MachineEvent.event_type == 'alarm',
            MachineEvent.created_at >= cutoff_30d
        ).count()
        scores['alarm_frequency'] = max(0, 100 - alarm_count * 5)

        # Maintenance compliance score (30% weight)
        if machine.next_maintenance:
            days_until = (machine.next_maintenance - datetime.utcnow()).days
            if days_until < 0:
                scores['maintenance'] = max(0, 50 + days_until * 5)
            elif days_until < 7:
                scores['maintenance'] = 70
            else:
                scores['maintenance'] = 100
        else:
            scores['maintenance'] = 80

        composite = round(
            scores['uptime'] * 0.4 +
            scores['alarm_frequency'] * 0.3 +
            scores['maintenance'] * 0.3, 1
        )

        return {
            'machine_id': machine_id,
            'health_score': composite,
            'components': scores,
            'status': 'good' if composite >= 80 else 'warning' if composite >= 60 else 'critical',
        }

    @cached(ttl=60, prefix='utilization')
    def get_all_utilization(self, period_days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
        """Get utilization for all active machines with pagination."""
        from models.scada.machines import Machine
        machines = self.session.query(Machine).filter(
            Machine.enabled == True
        ).order_by(Machine.machine_id).limit(limit).all()
        results = []
        for m in machines:
            util = self.calculate_utilization(m.machine_id, period_days)
            util['name'] = m.name
            results.append(util)
        return sorted(results, key=lambda x: x.get('utilization_pct', 0), reverse=True)
