"""
WIP Limits & Kanban Controls Service
=====================================
Work-in-process constraints and pull system controls.
Enhanced with aging analysis, kanban signals, cost valuation, and constraint identification.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json
import os


class KanbanSignal(str, Enum):
    """Kanban signal types for pull system control."""
    NONE = 'none'
    REPLENISH = 'replenish'
    EXPEDITE = 'expedite'
    STOP = 'stop'


class AgingCategory(str, Enum):
    """WIP aging categories."""
    FRESH = 'fresh'  # < 1 day
    NORMAL = 'normal'  # 1-3 days
    AGING = 'aging'  # 3-7 days
    STALE = 'stale'  # > 7 days


class ConstraintType(str, Enum):
    """Type of production constraint."""
    BOTTLENECK = 'bottleneck'
    STARVED = 'starved'
    BLOCKED = 'blocked'
    BALANCED = 'balanced'


@dataclass
class WIPItem:
    """Individual WIP item with tracking information."""
    job_id: str
    work_order_id: str
    product_id: str
    machine_id: str
    work_center_id: str
    quantity: int
    entered_queue_at: datetime
    age_hours: float = 0
    age_category: AgingCategory = AgingCategory.FRESH
    unit_cost: float = 0
    total_value: float = 0


@dataclass
class WorkCenterWIP:
    """WIP summary for a work center."""
    work_center_id: str
    machine_ids: List[str]
    total_jobs: int
    total_quantity: int
    wip_limit: int
    utilization_pct: float
    kanban_signal: KanbanSignal
    oldest_job_hours: float
    avg_age_hours: float
    total_value: float
    constraint_type: ConstraintType


@dataclass
class KanbanCard:
    """Kanban card for visual management."""
    card_id: str
    product_id: str
    work_center_id: str
    quantity: int
    status: str  # 'full', 'in_transit', 'empty'
    signal: KanbanSignal
    last_replenish_at: Optional[datetime]
    target_qty: int
    reorder_point: int


@dataclass
class WIPAgingReport:
    """WIP aging analysis report."""
    total_jobs: int
    total_value: float
    by_category: Dict[str, Dict[str, Any]]
    oldest_jobs: List[Dict[str, Any]]
    avg_age_hours: float
    stale_value_pct: float


@dataclass
class ConstraintAnalysis:
    """Production constraint analysis."""
    constraint_work_center: str
    constraint_type: ConstraintType
    wip_accumulation: Dict[str, int]
    throughput_rate: float
    bottleneck_utilization_pct: float
    upstream_starved: List[str]
    downstream_blocked: List[str]
    recommended_actions: List[str]


class WIPService:
    def __init__(self, session):
        self.session = session
        self._wip_limits = self._load_limits()
        self._work_center_map: Dict[str, str] = {}  # machine_id -> work_center_id

    def _load_limits(self) -> Dict[str, int]:
        config_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'config', 'wip_limits.json'
        )
        try:
            with open(config_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'default': 5}

    def _get_unit_cost(self, product_id: Optional[str]) -> float:
        """Look up the standard cost for a product from the Item master."""
        if not product_id:
            return 0
        from models.erp.items import Item
        item = self.session.query(Item.standard_cost).filter(
            Item.item_id == product_id
        ).first()
        return item.standard_cost if item and item.standard_cost else 0

    def set_work_center_mapping(self, machine_id: str, work_center_id: str):
        """Map a machine to its work center."""
        self._work_center_map[machine_id] = work_center_id

    def get_wip_levels(self) -> List[Dict[str, Any]]:
        """Get current WIP levels across all machines."""
        from models.mes.work_orders import Job, JobStatus
        from sqlalchemy import func

        wip_counts = self.session.query(
            Job.machine_id, func.count(Job.id)
        ).filter(
            Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED]),
            Job.is_deleted == False
        ).group_by(Job.machine_id).all()

        results = []
        for machine_id, count in wip_counts:
            limit = self._wip_limits.get(
                machine_id, self._wip_limits.get('default', 5)
            )
            utilization = (count / limit * 100) if limit > 0 else 0

            signal = KanbanSignal.NONE
            if count >= limit:
                signal = KanbanSignal.STOP
            elif count <= limit * 0.3:
                signal = KanbanSignal.REPLENISH
            elif count <= limit * 0.5:
                signal = KanbanSignal.EXPEDITE

            results.append({
                'machine_id': machine_id,
                'work_center_id': self._work_center_map.get(machine_id, machine_id),
                'wip_count': count,
                'wip_limit': limit,
                'utilization_pct': round(utilization, 1),
                'at_limit': count >= limit,
                'over_limit': count > limit,
                'kanban_signal': signal.value,
            })

        return results

    def check_wip_limit(self, machine_id: str) -> Dict[str, Any]:
        """Check if machine can accept more WIP."""
        from models.mes.work_orders import Job, JobStatus

        count = self.session.query(Job).filter(
            Job.machine_id == machine_id,
            Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED]),
            Job.is_deleted == False
        ).count()

        limit = self._wip_limits.get(
            machine_id, self._wip_limits.get('default', 5)
        )

        signal = KanbanSignal.NONE
        if count >= limit:
            signal = KanbanSignal.STOP
        elif count < limit * 0.3:
            signal = KanbanSignal.REPLENISH

        return {
            'machine_id': machine_id,
            'current_wip': count,
            'wip_limit': limit,
            'can_accept': count < limit,
            'available_slots': max(0, limit - count),
            'kanban_signal': signal.value,
        }

    def get_kanban_board(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get visual kanban board representation."""
        from models.mes.work_orders import Job, JobStatus
        from sqlalchemy.orm import joinedload

        jobs = self.session.query(Job).options(
            joinedload(Job.work_order)
        ).filter(
            Job.is_deleted == False
        ).order_by(Job.scheduled_start).limit(200).all()

        board = {'queued': [], 'running': [], 'completed': [], 'other': []}

        for j in jobs:
            age_hours = 0
            if j.scheduled_start:
                age_hours = (datetime.utcnow() - j.scheduled_start).total_seconds() / 3600

            age_category = self._categorize_age(age_hours)
            product_id = j.work_order.product_id if j.work_order else None
            unit_cost = self._get_unit_cost(product_id)

            card = {
                'job_id': str(j.id),
                'machine_id': j.machine_id,
                'work_center_id': self._work_center_map.get(j.machine_id, j.machine_id),
                'status': j.status.value if j.status else 'unknown',
                'work_order': j.work_order.work_order_id if j.work_order else None,
                'product': product_id,
                'quantity': j.work_order.quantity_ordered if j.work_order else 0,
                'age_hours': round(age_hours, 1),
                'age_category': age_category.value,
                'value': round(unit_cost * (j.work_order.quantity_ordered if j.work_order else 0), 2),
            }

            if j.status == JobStatus.QUEUED or j.status == JobStatus.PENDING:
                board['queued'].append(card)
            elif j.status == JobStatus.RUNNING:
                board['running'].append(card)
            elif j.status == JobStatus.COMPLETED:
                board['completed'].append(card)
            else:
                board['other'].append(card)

        return board

    def _categorize_age(self, hours: float) -> AgingCategory:
        """Categorize WIP age."""
        if hours < 24:
            return AgingCategory.FRESH
        elif hours < 72:
            return AgingCategory.NORMAL
        elif hours < 168:
            return AgingCategory.AGING
        else:
            return AgingCategory.STALE

    def get_wip_aging_analysis(self) -> WIPAgingReport:
        """Analyze WIP by age for identifying stale inventory."""
        from models.mes.work_orders import Job, JobStatus
        from sqlalchemy.orm import joinedload

        jobs = self.session.query(Job).options(
            joinedload(Job.work_order)
        ).filter(
            Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED, JobStatus.PENDING]),
            Job.is_deleted == False
        ).all()

        by_category = {
            AgingCategory.FRESH.value: {'count': 0, 'value': 0, 'jobs': []},
            AgingCategory.NORMAL.value: {'count': 0, 'value': 0, 'jobs': []},
            AgingCategory.AGING.value: {'count': 0, 'value': 0, 'jobs': []},
            AgingCategory.STALE.value: {'count': 0, 'value': 0, 'jobs': []},
        }

        total_value = 0
        ages = []
        oldest_jobs = []

        for j in jobs:
            age_hours = 0
            if j.scheduled_start:
                age_hours = (datetime.utcnow() - j.scheduled_start).total_seconds() / 3600
            ages.append(age_hours)

            category = self._categorize_age(age_hours)
            product_id = j.work_order.product_id if j.work_order else None
            qty = j.work_order.quantity_ordered if j.work_order else 0
            unit_cost = self._get_unit_cost(product_id)
            value = unit_cost * qty

            by_category[category.value]['count'] += 1
            by_category[category.value]['value'] += value
            total_value += value

            job_info = {
                'job_id': str(j.id),
                'product_id': product_id,
                'machine_id': j.machine_id,
                'age_hours': round(age_hours, 1),
                'value': round(value, 2),
            }
            by_category[category.value]['jobs'].append(job_info)

            if age_hours > 72:
                oldest_jobs.append(job_info)

        oldest_jobs.sort(key=lambda x: x['age_hours'], reverse=True)
        stale_value = by_category[AgingCategory.STALE.value]['value']
        stale_pct = (stale_value / total_value * 100) if total_value > 0 else 0

        return WIPAgingReport(
            total_jobs=len(jobs),
            total_value=round(total_value, 2),
            by_category=by_category,
            oldest_jobs=oldest_jobs[:10],
            avg_age_hours=round(sum(ages) / len(ages), 1) if ages else 0,
            stale_value_pct=round(stale_pct, 1),
        )

    def get_wip_by_work_center(self) -> List[WorkCenterWIP]:
        """Get WIP summary by work center."""
        from models.mes.work_orders import Job, JobStatus
        from sqlalchemy.orm import joinedload

        jobs = self.session.query(Job).options(
            joinedload(Job.work_order)
        ).filter(
            Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED, JobStatus.PENDING]),
            Job.is_deleted == False
        ).all()

        by_wc: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'machines': set(),
            'jobs': [],
            'quantity': 0,
            'value': 0,
            'ages': [],
        })

        for j in jobs:
            wc_id = self._work_center_map.get(j.machine_id, j.machine_id)
            by_wc[wc_id]['machines'].add(j.machine_id)

            age_hours = 0
            if j.scheduled_start:
                age_hours = (datetime.utcnow() - j.scheduled_start).total_seconds() / 3600

            qty = j.work_order.quantity_ordered if j.work_order else 0
            product_id = j.work_order.product_id if j.work_order else None
            unit_cost = self._get_unit_cost(product_id)

            by_wc[wc_id]['jobs'].append(str(j.id))
            by_wc[wc_id]['quantity'] += qty
            by_wc[wc_id]['value'] += unit_cost * qty
            by_wc[wc_id]['ages'].append(age_hours)

        results = []
        for wc_id, data in by_wc.items():
            total_jobs = len(data['jobs'])
            limit = sum(
                self._wip_limits.get(m, self._wip_limits.get('default', 5))
                for m in data['machines']
            )
            utilization = (total_jobs / limit * 100) if limit > 0 else 0

            signal = KanbanSignal.NONE
            if total_jobs >= limit:
                signal = KanbanSignal.STOP
            elif total_jobs <= limit * 0.3:
                signal = KanbanSignal.REPLENISH

            constraint = ConstraintType.BALANCED
            if utilization > 90:
                constraint = ConstraintType.BOTTLENECK
            elif utilization < 30:
                constraint = ConstraintType.STARVED

            ages = data['ages']
            results.append(WorkCenterWIP(
                work_center_id=wc_id,
                machine_ids=list(data['machines']),
                total_jobs=total_jobs,
                total_quantity=data['quantity'],
                wip_limit=limit,
                utilization_pct=round(utilization, 1),
                kanban_signal=signal,
                oldest_job_hours=round(max(ages), 1) if ages else 0,
                avg_age_hours=round(sum(ages) / len(ages), 1) if ages else 0,
                total_value=round(data['value'], 2),
                constraint_type=constraint,
            ))

        return sorted(results, key=lambda x: x.utilization_pct, reverse=True)

    def generate_kanban_signals(self) -> List[Dict[str, Any]]:
        """Generate kanban signals for all work centers."""
        wc_wip = self.get_wip_by_work_center()
        signals = []

        for wc in wc_wip:
            if wc.kanban_signal != KanbanSignal.NONE:
                action = ''
                urgency = 'normal'

                if wc.kanban_signal == KanbanSignal.STOP:
                    action = 'Stop sending work to this work center'
                    urgency = 'high'
                elif wc.kanban_signal == KanbanSignal.EXPEDITE:
                    action = 'Prioritize completion of jobs at this work center'
                    urgency = 'medium'
                elif wc.kanban_signal == KanbanSignal.REPLENISH:
                    action = 'Release more work to this work center'
                    urgency = 'normal'

                signals.append({
                    'work_center_id': wc.work_center_id,
                    'signal': wc.kanban_signal.value,
                    'current_wip': wc.total_jobs,
                    'wip_limit': wc.wip_limit,
                    'utilization_pct': wc.utilization_pct,
                    'action': action,
                    'urgency': urgency,
                    'timestamp': datetime.utcnow().isoformat(),
                })

        return sorted(signals, key=lambda x: (
            0 if x['urgency'] == 'high' else (1 if x['urgency'] == 'medium' else 2)
        ))

    def get_wip_valuation(self) -> Dict[str, Any]:
        """Get total WIP inventory valuation."""
        from models.mes.work_orders import Job, JobStatus
        from sqlalchemy.orm import joinedload

        jobs = self.session.query(Job).options(
            joinedload(Job.work_order)
        ).filter(
            Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED, JobStatus.PENDING]),
            Job.is_deleted == False
        ).all()

        by_product = defaultdict(lambda: {'qty': 0, 'value': 0})
        by_status = defaultdict(lambda: {'qty': 0, 'value': 0})
        total_value = 0
        total_qty = 0

        for j in jobs:
            product_id = j.work_order.product_id if j.work_order else 'unknown'
            qty = j.work_order.quantity_ordered if j.work_order else 0
            unit_cost = self._get_unit_cost(product_id)
            value = unit_cost * qty
            status = j.status.value if j.status else 'unknown'

            by_product[product_id]['qty'] += qty
            by_product[product_id]['value'] += value
            by_status[status]['qty'] += qty
            by_status[status]['value'] += value
            total_value += value
            total_qty += qty

        return {
            'total_value': round(total_value, 2),
            'total_quantity': total_qty,
            'job_count': len(jobs),
            'by_product': {
                k: {'qty': v['qty'], 'value': round(v['value'], 2)}
                for k, v in sorted(by_product.items(), key=lambda x: x[1]['value'], reverse=True)
            },
            'by_status': {
                k: {'qty': v['qty'], 'value': round(v['value'], 2)}
                for k, v in by_status.items()
            },
            'valuation_timestamp': datetime.utcnow().isoformat(),
        }

    def analyze_constraints(self, throughput_data: Dict[str, float] = None) -> ConstraintAnalysis:
        """Identify production constraints based on WIP accumulation."""
        wc_wip = self.get_wip_by_work_center()

        if not wc_wip:
            return ConstraintAnalysis(
                constraint_work_center='Unknown',
                constraint_type=ConstraintType.BALANCED,
                wip_accumulation={},
                throughput_rate=0,
                bottleneck_utilization_pct=0,
                upstream_starved=[],
                downstream_blocked=[],
                recommended_actions=['Insufficient data for analysis'],
            )

        bottleneck = max(wc_wip, key=lambda x: x.utilization_pct)
        wip_accumulation = {wc.work_center_id: wc.total_jobs for wc in wc_wip}

        upstream_starved = []
        downstream_blocked = []
        bottleneck_found = False

        for wc in sorted(wc_wip, key=lambda x: x.work_center_id):
            if wc.work_center_id == bottleneck.work_center_id:
                bottleneck_found = True
            elif bottleneck_found:
                if wc.utilization_pct < 50:
                    downstream_blocked.append(wc.work_center_id)
            else:
                if wc.utilization_pct < 50:
                    upstream_starved.append(wc.work_center_id)

        recommended_actions = []
        if bottleneck.utilization_pct > 90:
            recommended_actions.append(
                f'Add capacity to {bottleneck.work_center_id} (current bottleneck)'
            )
            recommended_actions.append(
                'Consider overtime or additional shifts at bottleneck'
            )
        if downstream_blocked:
            recommended_actions.append(
                f'Investigate blockage downstream of bottleneck: {", ".join(downstream_blocked)}'
            )
        if bottleneck.avg_age_hours > 48:
            recommended_actions.append(
                f'Reduce WIP aging at {bottleneck.work_center_id} (avg {bottleneck.avg_age_hours:.1f}h)'
            )

        throughput = throughput_data.get(bottleneck.work_center_id, 0) if throughput_data else 0

        return ConstraintAnalysis(
            constraint_work_center=bottleneck.work_center_id,
            constraint_type=bottleneck.constraint_type,
            wip_accumulation=wip_accumulation,
            throughput_rate=throughput,
            bottleneck_utilization_pct=bottleneck.utilization_pct,
            upstream_starved=upstream_starved,
            downstream_blocked=downstream_blocked,
            recommended_actions=recommended_actions,
        )

    def create_kanban_card(self, product_id: str, work_center_id: str,
                            target_qty: int, reorder_point: int) -> KanbanCard:
        """Create a kanban card for a product at a work center."""
        import uuid
        from models.mes.operations import KanbanCardModel

        card_id = f"KB-{uuid.uuid4().hex[:8].upper()}"

        db_card = KanbanCardModel(
            card_id=card_id,
            product_id=product_id,
            work_center_id=work_center_id,
            quantity=0,
            target_qty=target_qty,
            reorder_point=reorder_point,
            status='empty',
            signal=KanbanSignal.REPLENISH.value,
            last_replenish_at=None,
        )
        self.session.add(db_card)
        self.session.flush()

        return KanbanCard(
            card_id=card_id,
            product_id=product_id,
            work_center_id=work_center_id,
            quantity=0,
            status='empty',
            signal=KanbanSignal.REPLENISH,
            last_replenish_at=None,
            target_qty=target_qty,
            reorder_point=reorder_point,
        )

    def update_kanban_card(self, card_id: str, quantity: int) -> Dict[str, Any]:
        """Update kanban card quantity and signal."""
        from models.mes.operations import KanbanCardModel

        db_card = self.session.query(KanbanCardModel).filter(
            KanbanCardModel.card_id == card_id
        ).first()

        if not db_card:
            return {'error': 'Kanban card not found'}

        db_card.quantity = quantity

        if quantity >= db_card.target_qty:
            db_card.status = 'full'
            db_card.signal = KanbanSignal.NONE.value
        elif quantity <= db_card.reorder_point:
            db_card.status = 'empty'
            db_card.signal = KanbanSignal.REPLENISH.value
        else:
            db_card.status = 'in_transit'
            db_card.signal = KanbanSignal.NONE.value

        self.session.flush()

        return {
            'card_id': card_id,
            'quantity': quantity,
            'status': db_card.status,
            'signal': db_card.signal,
        }

    def get_kanban_cards(self, work_center_id: str = None,
                          product_id: str = None) -> List[Dict[str, Any]]:
        """Get kanban cards filtered by work center or product."""
        from models.mes.operations import KanbanCardModel

        query = self.session.query(KanbanCardModel)
        if work_center_id:
            query = query.filter(KanbanCardModel.work_center_id == work_center_id)
        if product_id:
            query = query.filter(KanbanCardModel.product_id == product_id)

        return [card.to_dict() for card in query.all()]

    def get_wip_flow_rate(self, hours: int = 24) -> Dict[str, Any]:
        """Calculate WIP flow rate (Little's Law analysis)."""
        from models.mes.work_orders import Job, JobStatus

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        completed = self.session.query(Job).filter(
            Job.status == JobStatus.COMPLETED,
            Job.actual_end >= cutoff,
            Job.is_deleted == False
        ).count()

        current_wip = self.session.query(Job).filter(
            Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED]),
            Job.is_deleted == False
        ).count()

        throughput_rate = completed / hours if hours > 0 else 0
        avg_lead_time = current_wip / throughput_rate if throughput_rate > 0 else 0

        return {
            'period_hours': hours,
            'completed_jobs': completed,
            'current_wip': current_wip,
            'throughput_rate_per_hour': round(throughput_rate, 2),
            'avg_lead_time_hours': round(avg_lead_time, 1),
            'analysis': "Little's Law: Lead Time = WIP / Throughput Rate",
            'timestamp': datetime.utcnow().isoformat(),
        }

    def set_wip_limit(self, machine_id: str, limit: int) -> Dict[str, Any]:
        """Set WIP limit for a machine."""
        self._wip_limits[machine_id] = limit
        return {
            'machine_id': machine_id,
            'new_limit': limit,
            'status': 'updated',
        }

    def get_wip_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get WIP level trends over time."""
        from models.mes.operations import WIPSnapshot

        cutoff = datetime.utcnow() - timedelta(days=days)

        snapshots = self.session.query(WIPSnapshot).filter(
            WIPSnapshot.created_at >= cutoff
        ).order_by(WIPSnapshot.created_at).all()

        if not snapshots:
            return {
                'days': days,
                'message': 'No historical WIP data available',
                'trend': [],
            }

        daily = defaultdict(list)
        for snap in snapshots:
            day = snap.created_at.strftime('%Y-%m-%d')
            daily[day].append(snap.total_wip)

        trend = [
            {
                'date': day,
                'avg_wip': round(sum(values) / len(values), 1),
                'max_wip': max(values),
                'min_wip': min(values),
            }
            for day, values in sorted(daily.items())
        ]

        return {
            'days': days,
            'trend': trend,
            'overall_avg': round(
                sum(t['avg_wip'] for t in trend) / len(trend), 1
            ) if trend else 0,
        }

    def record_wip_snapshot(self) -> Dict[str, Any]:
        """Record current WIP state for historical tracking."""
        from models.mes.operations import WIPSnapshot

        levels = self.get_wip_levels()
        total_wip = sum(l['wip_count'] for l in levels)
        by_machine = {l['machine_id']: l['wip_count'] for l in levels}

        snapshot = WIPSnapshot(
            total_wip=total_wip,
            by_machine=by_machine,
        )
        self.session.add(snapshot)
        self.session.flush()

        return {
            'timestamp': snapshot.created_at.isoformat() if snapshot.created_at else datetime.utcnow().isoformat(),
            'total_wip': total_wip,
            'by_machine': by_machine,
        }
