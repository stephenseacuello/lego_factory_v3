"""
LEGO Factory v3 - Maintenance Service
=====================================
Maintenance work order management and PM scheduling.
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from config.database import get_db_session

logger = logging.getLogger(__name__)


class MaintenanceService:
    """Service for managing maintenance work orders."""

    def __init__(self, session: Session):
        self.session = session

    def create_work_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a maintenance work order."""
        from models.cmms.maintenance import (
            MaintenanceWorkOrder, WorkOrderType, WorkOrderStatus, WorkOrderPriority
        )
        from models.cmms.assets import Asset

        # Get asset
        asset = self.session.query(Asset).filter(
            Asset.asset_id == data['asset_id']
        ).first()
        if not asset:
            raise ValueError(f"Asset {data['asset_id']} not found")

        wo = MaintenanceWorkOrder(
            wo_number=data.get('wo_number', f"MWO-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"),
            description=data['description'],
            wo_type=WorkOrderType(data.get('wo_type', 'corrective')),
            status=WorkOrderStatus(data.get('status', 'draft')),
            priority=WorkOrderPriority(data.get('priority', 'medium')),
            asset_id=asset.id,
            pm_schedule_id=data.get('pm_schedule_id'),
            problem_code=data.get('problem_code'),
            problem_description=data.get('problem_description'),
            target_start=data.get('target_start'),
            target_completion=data.get('target_completion'),
            assigned_to=data.get('assigned_to'),
            work_center_id=data.get('work_center_id'),
            estimated_hours=data.get('estimated_hours'),
            estimated_cost=data.get('estimated_cost'),
            instructions=data.get('instructions'),
            requires_approval=data.get('requires_approval', False),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(wo)
        self.session.flush()

        logger.info(f"Created maintenance work order: {wo.wo_number}")
        return wo.to_dict()

    def get_work_order(self, wo_number: str) -> Optional[Dict[str, Any]]:
        """Get a work order by number."""
        from models.cmms.maintenance import MaintenanceWorkOrder

        wo = self.session.query(MaintenanceWorkOrder).filter(
            MaintenanceWorkOrder.wo_number == wo_number
        ).first()
        return wo.to_dict() if wo else None

    def get_work_orders(
        self,
        status: str = None,
        wo_type: str = None,
        priority: str = None,
        asset_id: str = None,
        assigned_to: str = None,
        due_before: datetime = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get work orders with filtering."""
        from models.cmms.maintenance import (
            MaintenanceWorkOrder, WorkOrderType, WorkOrderStatus, WorkOrderPriority
        )
        from models.cmms.assets import Asset

        query = self.session.query(MaintenanceWorkOrder).filter(
            MaintenanceWorkOrder.is_deleted == False
        )

        if status:
            query = query.filter(MaintenanceWorkOrder.status == WorkOrderStatus(status))
        if wo_type:
            query = query.filter(MaintenanceWorkOrder.wo_type == WorkOrderType(wo_type))
        if priority:
            query = query.filter(MaintenanceWorkOrder.priority == WorkOrderPriority(priority))
        if asset_id:
            asset = self.session.query(Asset).filter(Asset.asset_id == asset_id).first()
            if asset:
                query = query.filter(MaintenanceWorkOrder.asset_id == asset.id)
        if assigned_to:
            query = query.filter(MaintenanceWorkOrder.assigned_to == assigned_to)
        if due_before:
            query = query.filter(MaintenanceWorkOrder.target_completion <= due_before)

        work_orders = query.order_by(
            MaintenanceWorkOrder.priority,
            MaintenanceWorkOrder.target_completion
        ).offset(offset).limit(limit).all()

        return [wo.to_dict() for wo in work_orders]

    def update_work_order(self, wo_number: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a work order."""
        from models.cmms.maintenance import (
            MaintenanceWorkOrder, WorkOrderType, WorkOrderStatus, WorkOrderPriority
        )

        wo = self.session.query(MaintenanceWorkOrder).filter(
            MaintenanceWorkOrder.wo_number == wo_number
        ).first()

        if not wo:
            return None

        for key, value in data.items():
            if hasattr(wo, key) and key not in ('id', 'wo_number', 'created_at'):
                if key == 'status' and isinstance(value, str):
                    value = WorkOrderStatus(value)
                elif key == 'wo_type' and isinstance(value, str):
                    value = WorkOrderType(value)
                elif key == 'priority' and isinstance(value, str):
                    value = WorkOrderPriority(value)
                setattr(wo, key, value)

        wo.updated_at = datetime.utcnow()
        wo.updated_by = data.get('updated_by', 'system')
        self.session.flush()

        logger.info(f"Updated work order: {wo_number}")
        return wo.to_dict()

    def start_work_order(self, wo_number: str, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """Start a work order."""
        from models.cmms.maintenance import WorkOrderStatus

        return self.update_work_order(wo_number, {
            'status': WorkOrderStatus.IN_PROGRESS,
            'actual_start': datetime.utcnow(),
            'updated_by': user_id
        })

    def complete_work_order(
        self,
        wo_number: str,
        completion_notes: str = None,
        actual_hours: float = None,
        user_id: str = 'system'
    ) -> Optional[Dict[str, Any]]:
        """Complete a work order."""
        from models.cmms.maintenance import MaintenanceWorkOrder, WorkOrderStatus

        wo = self.session.query(MaintenanceWorkOrder).filter(
            MaintenanceWorkOrder.wo_number == wo_number
        ).first()

        if not wo:
            return None

        wo.status = WorkOrderStatus.COMPLETED
        wo.actual_completion = datetime.utcnow()
        wo.updated_by = user_id
        wo.updated_at = datetime.utcnow()

        if completion_notes:
            wo.completion_notes = completion_notes
        if actual_hours is not None:
            wo.actual_hours = actual_hours

        # Calculate labor and material costs
        wo.actual_labor_cost = sum(l.total_cost or 0 for l in wo.labor)
        wo.actual_material_cost = sum(m.total_cost or 0 for m in wo.materials)

        # Calculate downtime if tracked
        if wo.downtime_start and wo.downtime_end:
            wo.downtime_hours = (wo.downtime_end - wo.downtime_start).total_seconds() / 3600

        # Update PM schedule if this was a PM work order
        if wo.pm_schedule_id:
            wo.pm_schedule.last_completed = datetime.utcnow()
            wo.pm_schedule.next_due_date = wo.pm_schedule.calculate_next_due()

        self.session.flush()

        logger.info(f"Completed work order: {wo_number}")
        return wo.to_dict()

    def add_task(self, wo_number: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a task to a work order."""
        from models.cmms.maintenance import MaintenanceWorkOrder, WorkOrderTask

        wo = self.session.query(MaintenanceWorkOrder).filter(
            MaintenanceWorkOrder.wo_number == wo_number
        ).first()

        if not wo:
            return None

        task = WorkOrderTask(
            work_order_id=wo.id,
            sequence=data.get('sequence', 10),
            name=data['name'],
            description=data.get('description'),
            instructions=data.get('instructions'),
            estimated_minutes=data.get('estimated_minutes'),
            lockout_required=data.get('lockout_required', False),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(task)
        self.session.flush()

        return task.to_dict()

    def complete_task(self, task_id: str, user_id: str = 'system', actual_minutes: int = None) -> Optional[Dict[str, Any]]:
        """Complete a work order task."""
        from models.cmms.maintenance import WorkOrderTask

        task = self.session.query(WorkOrderTask).filter(WorkOrderTask.id == task_id).first()
        if not task:
            return None

        task.is_completed = True
        task.completed_by = user_id
        task.completed_date = datetime.utcnow()
        if actual_minutes is not None:
            task.actual_minutes = actual_minutes

        self.session.flush()
        return task.to_dict()

    def record_labor(self, wo_number: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Record labor on a work order."""
        from models.cmms.maintenance import MaintenanceWorkOrder, WorkOrderLabor

        wo = self.session.query(MaintenanceWorkOrder).filter(
            MaintenanceWorkOrder.wo_number == wo_number
        ).first()

        if not wo:
            return None

        labor = WorkOrderLabor(
            work_order_id=wo.id,
            worker_id=data['worker_id'],
            craft=data.get('craft'),
            start_time=data.get('start_time'),
            end_time=data.get('end_time'),
            regular_hours=data.get('regular_hours', 0),
            overtime_hours=data.get('overtime_hours', 0),
            hourly_rate=data.get('hourly_rate'),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        labor.calculate_cost()

        self.session.add(labor)
        self.session.flush()

        # Update work order actual hours
        wo.actual_hours = (wo.actual_hours or 0) + labor.regular_hours + labor.overtime_hours
        self.session.flush()

        return labor.to_dict()

    def record_material(self, wo_number: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Record material usage on a work order."""
        from models.cmms.maintenance import MaintenanceWorkOrder, WorkOrderMaterial

        wo = self.session.query(MaintenanceWorkOrder).filter(
            MaintenanceWorkOrder.wo_number == wo_number
        ).first()

        if not wo:
            return None

        material = WorkOrderMaterial(
            work_order_id=wo.id,
            spare_id=data.get('spare_id'),
            item_id=data.get('item_id'),
            description=data['description'],
            quantity_required=data.get('quantity_required', 1),
            quantity_used=data.get('quantity_used', 0),
            unit_cost=data.get('unit_cost'),
            created_by=data.get('created_by', 'system'),
        )

        material.calculate_cost()

        self.session.add(material)
        self.session.flush()

        return material.to_dict()

    def get_backlog_summary(self) -> Dict[str, Any]:
        """Get maintenance backlog summary."""
        from models.cmms.maintenance import MaintenanceWorkOrder, WorkOrderStatus, WorkOrderPriority

        active_statuses = [
            WorkOrderStatus.DRAFT,
            WorkOrderStatus.APPROVED,
            WorkOrderStatus.WAITING_PARTS,
            WorkOrderStatus.WAITING_SCHEDULE,
            WorkOrderStatus.SCHEDULED,
            WorkOrderStatus.IN_PROGRESS,
            WorkOrderStatus.ON_HOLD,
        ]

        # Count by status
        status_counts = self.session.query(
            MaintenanceWorkOrder.status, func.count(MaintenanceWorkOrder.id)
        ).filter(
            MaintenanceWorkOrder.status.in_(active_statuses),
            MaintenanceWorkOrder.is_deleted == False
        ).group_by(MaintenanceWorkOrder.status).all()

        # Count by priority
        priority_counts = self.session.query(
            MaintenanceWorkOrder.priority, func.count(MaintenanceWorkOrder.id)
        ).filter(
            MaintenanceWorkOrder.status.in_(active_statuses),
            MaintenanceWorkOrder.is_deleted == False
        ).group_by(MaintenanceWorkOrder.priority).all()

        # Overdue count
        overdue_count = self.session.query(func.count(MaintenanceWorkOrder.id)).filter(
            MaintenanceWorkOrder.status.in_(active_statuses),
            MaintenanceWorkOrder.target_completion < datetime.utcnow(),
            MaintenanceWorkOrder.is_deleted == False
        ).scalar()

        # Total estimated hours
        total_hours = self.session.query(func.sum(MaintenanceWorkOrder.estimated_hours)).filter(
            MaintenanceWorkOrder.status.in_(active_statuses),
            MaintenanceWorkOrder.is_deleted == False
        ).scalar() or 0

        return {
            'by_status': {s[0].value: s[1] for s in status_counts},
            'by_priority': {p[0].value: p[1] for p in priority_counts},
            'overdue_count': overdue_count,
            'total_estimated_hours': float(total_hours),
            'total_work_orders': sum(s[1] for s in status_counts),
        }


class PMService:
    """Service for managing PM schedules."""

    def __init__(self, session: Session):
        self.session = session

    def create_pm_schedule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a PM schedule."""
        from models.cmms.maintenance import PMSchedule, PMTriggerType, WorkOrderPriority
        from models.cmms.assets import Asset, Meter

        # Get asset
        asset = self.session.query(Asset).filter(
            Asset.asset_id == data['asset_id']
        ).first()
        if not asset:
            raise ValueError(f"Asset {data['asset_id']} not found")

        # Get meter if meter-based
        meter = None
        if data.get('meter_id'):
            meter = self.session.query(Meter).filter(
                Meter.meter_id == data['meter_id']
            ).first()

        pm = PMSchedule(
            pm_id=data.get('pm_id', f"PM-{uuid.uuid4().hex[:8].upper()}"),
            name=data['name'],
            description=data.get('description'),
            asset_id=asset.id,
            is_active=data.get('is_active', True),
            trigger_type=PMTriggerType(data.get('trigger_type', 'calendar')),
            frequency_days=data.get('frequency_days'),
            day_of_week=data.get('day_of_week'),
            day_of_month=data.get('day_of_month'),
            meter_id=meter.id if meter else None,
            meter_interval=data.get('meter_interval'),
            lead_time_days=data.get('lead_time_days', 7),
            work_window_days=data.get('work_window_days', 7),
            next_due_date=data.get('next_due_date'),
            priority=WorkOrderPriority(data.get('priority', 'medium')),
            estimated_hours=data.get('estimated_hours'),
            estimated_cost=data.get('estimated_cost'),
            work_center_id=data.get('work_center_id'),
            instructions=data.get('instructions'),
            checklist=data.get('checklist', []),
            spares_required=data.get('spares_required', []),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(pm)
        self.session.flush()

        logger.info(f"Created PM schedule: {pm.pm_id}")
        return pm.to_dict()

    def get_pm_schedule(self, pm_id: str) -> Optional[Dict[str, Any]]:
        """Get a PM schedule by ID."""
        from models.cmms.maintenance import PMSchedule

        pm = self.session.query(PMSchedule).filter(
            PMSchedule.pm_id == pm_id
        ).first()
        return pm.to_dict() if pm else None

    def get_pm_schedules(
        self,
        asset_id: str = None,
        is_active: bool = None,
        due_within_days: int = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get PM schedules with filtering."""
        from models.cmms.maintenance import PMSchedule
        from models.cmms.assets import Asset

        query = self.session.query(PMSchedule).filter(PMSchedule.is_deleted == False)

        if asset_id:
            asset = self.session.query(Asset).filter(Asset.asset_id == asset_id).first()
            if asset:
                query = query.filter(PMSchedule.asset_id == asset.id)
        if is_active is not None:
            query = query.filter(PMSchedule.is_active == is_active)
        if due_within_days:
            due_date = date.today() + timedelta(days=due_within_days)
            query = query.filter(PMSchedule.next_due_date <= due_date)

        schedules = query.order_by(PMSchedule.next_due_date).limit(limit).all()
        return [pm.to_dict() for pm in schedules]

    def update_pm_schedule(self, pm_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a PM schedule."""
        from models.cmms.maintenance import PMSchedule, PMTriggerType, WorkOrderPriority

        pm = self.session.query(PMSchedule).filter(
            PMSchedule.pm_id == pm_id
        ).first()

        if not pm:
            return None

        for key, value in data.items():
            if hasattr(pm, key) and key not in ('id', 'pm_id', 'created_at'):
                if key == 'trigger_type' and isinstance(value, str):
                    value = PMTriggerType(value)
                elif key == 'priority' and isinstance(value, str):
                    value = WorkOrderPriority(value)
                setattr(pm, key, value)

        pm.updated_at = datetime.utcnow()
        pm.updated_by = data.get('updated_by', 'system')
        self.session.flush()

        return pm.to_dict()

    def generate_pm_work_orders(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Generate work orders for PMs coming due."""
        from models.cmms.maintenance import PMSchedule, PMTriggerType

        maintenance_service = MaintenanceService(self.session)
        generated = []

        # Get calendar-based PMs due within the window
        due_date = date.today() + timedelta(days=days_ahead)
        pm_schedules = self.session.query(PMSchedule).filter(
            PMSchedule.is_active == True,
            PMSchedule.trigger_type == PMTriggerType.CALENDAR,
            PMSchedule.next_due_date <= due_date,
            PMSchedule.is_deleted == False
        ).all()

        for pm in pm_schedules:
            # Check if work order already exists for this PM
            existing = self.session.query(
                func.count()
            ).select_from(pm.work_orders).filter(
                pm.work_orders.property.mapper.class_.status.in_(['draft', 'approved', 'scheduled', 'in_progress'])
            ).scalar()

            if existing > 0:
                continue

            # Create work order
            wo_data = {
                'asset_id': pm.asset.asset_id,
                'description': f"PM: {pm.name}",
                'wo_type': 'preventive',
                'priority': pm.priority.value if pm.priority else 'medium',
                'pm_schedule_id': pm.id,
                'target_start': pm.next_due_date,
                'target_completion': pm.next_due_date + timedelta(days=pm.work_window_days or 7),
                'estimated_hours': pm.estimated_hours,
                'estimated_cost': pm.estimated_cost,
                'work_center_id': pm.work_center_id,
                'instructions': pm.instructions,
            }

            wo = maintenance_service.create_work_order(wo_data)
            generated.append(wo)

            logger.info(f"Generated PM work order {wo['wo_number']} for {pm.pm_id}")

        return generated

    def get_pm_compliance(self, days: int = 30) -> Dict[str, Any]:
        """Get PM compliance metrics."""
        from models.cmms.maintenance import PMSchedule, MaintenanceWorkOrder, WorkOrderStatus

        # Calculate compliance (completed on time / total due)
        start_date = date.today() - timedelta(days=days)

        total_due = self.session.query(func.count(PMSchedule.id)).filter(
            PMSchedule.is_active == True,
            PMSchedule.next_due_date >= start_date,
            PMSchedule.next_due_date <= date.today(),
            PMSchedule.is_deleted == False
        ).scalar()

        # Count completed PMs
        completed_on_time = self.session.query(func.count(MaintenanceWorkOrder.id)).filter(
            MaintenanceWorkOrder.wo_type == 'preventive',
            MaintenanceWorkOrder.status == WorkOrderStatus.COMPLETED,
            MaintenanceWorkOrder.actual_completion >= start_date,
            MaintenanceWorkOrder.actual_completion <= MaintenanceWorkOrder.target_completion,
            MaintenanceWorkOrder.is_deleted == False
        ).scalar()

        compliance_rate = (completed_on_time / total_due * 100) if total_due > 0 else 0

        return {
            'period_days': days,
            'total_due': total_due,
            'completed_on_time': completed_on_time,
            'compliance_rate': round(compliance_rate, 2),
        }


def get_maintenance_service(session: Session = None) -> MaintenanceService:
    """Get maintenance service instance."""
    if session:
        return MaintenanceService(session)
    with get_db_session() as session:
        return MaintenanceService(session)


def get_pm_service(session: Session = None) -> PMService:
    """Get PM service instance."""
    if session:
        return PMService(session)
    with get_db_session() as session:
        return PMService(session)
