"""
Shift Handover Checklist Service
==================================
Structured handover between shifts with auto-populated items.
"""
from datetime import datetime, date
from typing import Dict, Any, List

from models.mes.operations import ShiftHandover, HandoverStatus


class HandoverService:
    def __init__(self, session):
        self.session = session

    def create_handover(self, shift_date: str = None, shift_type: str = 'day',
                        outgoing_worker: str = None) -> Dict[str, Any]:
        """Create a new shift handover with auto-populated items."""
        from models.scada.machines import Machine, MachineState

        if shift_date:
            parsed_date = date.fromisoformat(shift_date)
        else:
            parsed_date = date.today()

        items = []

        # Auto-populate: machines in alarm state
        alarm_machines = self.session.query(Machine).filter(
            Machine.current_state == MachineState.ALARM
        ).all()
        for m in alarm_machines:
            items.append({
                'category': 'SAFETY', 'description': f'Machine {m.name} in ALARM state',
                'status': 'CRITICAL', 'notes': m.error_message or '',
            })

        # Auto-populate: machines in maintenance
        maint_machines = self.session.query(Machine).filter(
            Machine.current_state == MachineState.MAINTENANCE
        ).all()
        for m in maint_machines:
            items.append({
                'category': 'MAINTENANCE', 'description': f'Machine {m.name} under maintenance',
                'status': 'ATTENTION', 'notes': m.maintenance_notes or '',
            })

        # Default safety item
        items.append({
            'category': 'SAFETY', 'description': 'Safety walkthrough completed',
            'status': 'OK', 'notes': '',
        })
        items.append({
            'category': 'PRODUCTION', 'description': 'Production targets reviewed',
            'status': 'OK', 'notes': '',
        })
        items.append({
            'category': 'QUALITY', 'description': 'Quality issues reviewed',
            'status': 'OK', 'notes': '',
        })

        count = self.session.query(ShiftHandover).count()
        handover_id = f'HO-{count + 1:04d}'

        handover = ShiftHandover(
            handover_id=handover_id,
            shift_date=parsed_date,
            shift_type=shift_type,
            outgoing_worker=outgoing_worker,
            incoming_worker=None,
            status=HandoverStatus.DRAFT,
            items=items,
        )
        self.session.add(handover)
        self.session.flush()
        return handover.to_dict()

    def complete_handover(self, handover_id: str, incoming_worker: str) -> Dict[str, Any]:
        """Complete handover with incoming worker acknowledgment."""
        handover = self.session.query(ShiftHandover).filter(
            ShiftHandover.handover_id == handover_id
        ).first()
        if not handover:
            return {'error': 'Handover not found'}
        handover.incoming_worker = incoming_worker
        handover.status = HandoverStatus.COMPLETED
        handover.completed_at = datetime.utcnow()
        self.session.flush()
        return handover.to_dict()

    def get_handovers(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent handovers."""
        handovers = self.session.query(ShiftHandover).order_by(
            ShiftHandover.created_at.desc()
        ).limit(limit).all()
        return [h.to_dict() for h in handovers]
