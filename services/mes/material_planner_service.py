"""
MES Material Planner Service
=============================
Handles material shortage resolution, alternative suggestions,
schedule impact analysis, and rush order recommendations.

ISA-95 Level 3 - Material Management Integration
"""

import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from models.mes.operations import MaterialShortage

logger = logging.getLogger(__name__)


class ShortageStatus(str, Enum):
    """Material shortage status."""
    DETECTED = 'detected'
    RESOLVED = 'resolved'
    ALTERNATIVE_FOUND = 'alternative_found'
    RUSH_ORDER_PLACED = 'rush_order_placed'
    SCHEDULE_ADJUSTED = 'schedule_adjusted'
    ESCALATED = 'escalated'


class ResolutionType(str, Enum):
    """How shortage was resolved."""
    ALTERNATIVE_MATERIAL = 'alternative_material'
    ALTERNATIVE_LOT = 'alternative_lot'
    RUSH_ORDER = 'rush_order'
    SCHEDULE_DELAY = 'schedule_delay'
    PARTIAL_FULFILLMENT = 'partial_fulfillment'
    CANCELLED = 'cancelled'


@dataclass
class AlternativeMaterial:
    """Alternative material suggestion."""
    material_id: str
    material_name: str
    available_quantity: Decimal
    compatibility_score: float  # 0-1, how suitable is this alternative
    cost_difference: Decimal  # Positive = more expensive
    lead_time_days: int
    location_id: str
    lot_number: str = None
    expiry_date: date = None
    notes: str = None


@dataclass
class ScheduleImpact:
    """Impact of shortage on schedule."""
    job_id: str
    work_order_id: str
    original_start: datetime
    original_end: datetime
    delayed_start: datetime
    delayed_end: datetime
    delay_hours: float
    downstream_jobs_affected: List[str] = field(default_factory=list)
    customer_impact: str = None


class MaterialPlannerService:
    """
    Material shortage resolution and planning service.

    Provides:
    - Shortage detection and tracking
    - Alternative material/lot suggestions
    - Schedule impact analysis
    - Rush order recommendations
    - Dashboard alerts
    """

    def __init__(self, session: Session = None):
        self.session = session
        self._material_alternatives: Dict[str, List[str]] = {}

        # Default material compatibility map
        # Format: material_id -> list of compatible alternatives with scores
        self._compatibility_map = {
            # FDM materials
            'PLA': [('PLA-PRO', 0.95), ('PLA-PLUS', 0.90), ('PETG', 0.70)],
            'PLA-PRO': [('PLA', 0.90), ('PLA-PLUS', 0.95), ('PETG', 0.70)],
            'ABS': [('ABS-PLUS', 0.95), ('ASA', 0.85), ('PETG', 0.60)],
            'PETG': [('PETG-CF', 0.90), ('PLA', 0.60), ('ABS', 0.50)],
            # CNC materials
            'ALU-6061': [('ALU-6063', 0.95), ('ALU-7075', 0.85)],
            'ALU-7075': [('ALU-6061', 0.80), ('ALU-2024', 0.85)],
            'BRS-360': [('BRS-353', 0.90)],
        }

    def check_material_availability(
        self,
        material_id: str,
        quantity_required: float,
        required_date: date = None,
        job_id: str = None,
        work_order_id: str = None
    ) -> Dict[str, Any]:
        """
        Check if material is available and create shortage if not.

        Args:
            material_id: Material to check
            quantity_required: Quantity needed
            required_date: When material is needed
            job_id: Associated job
            work_order_id: Associated work order

        Returns:
            Availability status and any shortage details
        """
        required_date = required_date or date.today()
        qty_required = Decimal(str(quantity_required))

        # Get available inventory
        available = self._get_available_inventory(material_id)

        if available >= qty_required:
            return {
                'available': True,
                'material_id': material_id,
                'quantity_required': float(qty_required),
                'quantity_available': float(available),
                'shortage': None
            }

        # Create shortage record
        shortage = self._create_shortage(
            material_id=material_id,
            required_quantity=qty_required,
            available_quantity=available,
            required_date=required_date,
            job_id=job_id,
            work_order_id=work_order_id
        )

        shortage_quantity = float(qty_required - available)

        # Get alternatives
        alternatives = self.suggest_alternatives(
            material_id=material_id,
            quantity_needed=shortage_quantity
        )

        # Calculate schedule impact
        impact = None
        if job_id:
            impact = self.calculate_schedule_impact(
                job_id=job_id,
                shortage_quantity=shortage_quantity,
                material_id=material_id
            )

        # Emit alert
        self._emit_shortage_alert(shortage, alternatives)

        return {
            'available': False,
            'material_id': material_id,
            'quantity_required': float(qty_required),
            'quantity_available': float(available),
            'shortage': {
                'shortage_id': shortage.shortage_id,
                'shortage_quantity': shortage.quantity_short,
                'status': shortage.status
            },
            'alternatives': alternatives,
            'schedule_impact': impact,
            'recommendations': self._generate_recommendations(shortage, alternatives, impact)
        }

    def _get_available_inventory(self, material_id: str) -> Decimal:
        """Get available inventory for a material."""
        if self.session:
            try:
                from models.erp.inventory import InventoryBalance

                result = self.session.query(
                    func.sum(InventoryBalance.quantity_on_hand)
                ).filter(
                    InventoryBalance.material_id == material_id,
                    InventoryBalance.is_active == True
                ).scalar()

                return Decimal(str(result or 0))
            except ImportError:
                pass

        # Demo data
        demo_inventory = {
            'PLA': Decimal('50'),
            'ABS': Decimal('30'),
            'PETG': Decimal('20'),
            'ALU-6061': Decimal('100'),
        }
        return demo_inventory.get(material_id, Decimal('0'))

    def _create_shortage(
        self,
        material_id: str,
        required_quantity: Decimal,
        available_quantity: Decimal,
        required_date: date,
        job_id: str = None,
        work_order_id: str = None
    ) -> MaterialShortage:
        """Create and store shortage record in the database."""
        shortage_quantity = float(required_quantity - available_quantity)

        shortage = MaterialShortage(
            shortage_id=f"SHORT-{uuid.uuid4().hex[:8].upper()}",
            material_id=material_id,
            quantity_short=shortage_quantity,
            job_id=job_id or '',
            work_order_id=work_order_id or '',
            required_date=required_date,
            status=ShortageStatus.DETECTED.value,
        )

        self.session.add(shortage)
        self.session.flush()

        logger.warning(
            f"Material shortage detected: {material_id}, "
            f"short {shortage_quantity} units"
        )

        return shortage

    def _get_material_name(self, material_id: str) -> str:
        """Get material name from ID."""
        names = {
            'PLA': 'PLA Filament',
            'ABS': 'ABS Filament',
            'PETG': 'PETG Filament',
            'ALU-6061': 'Aluminum 6061-T6',
            'ALU-7075': 'Aluminum 7075-T6',
            'BRS-360': 'Brass 360',
        }
        return names.get(material_id, material_id)

    def suggest_alternatives(
        self,
        material_id: str,
        quantity_needed: float,
        max_alternatives: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Suggest alternative materials or lots.

        Args:
            material_id: Material that's short
            quantity_needed: Quantity shortfall
            max_alternatives: Max suggestions to return

        Returns:
            List of alternative suggestions
        """
        qty_needed = Decimal(str(quantity_needed))
        alternatives = []

        # Check for alternative lots of same material
        lots = self._get_alternative_lots(material_id, qty_needed)
        for lot in lots:
            alternatives.append({
                'type': 'alternative_lot',
                'material_id': material_id,
                'material_name': self._get_material_name(material_id),
                'lot_number': lot.get('lot_number'),
                'available_quantity': lot.get('quantity'),
                'location_id': lot.get('location_id'),
                'compatibility_score': 1.0,
                'cost_difference': 0,
                'lead_time_days': 0,
                'notes': f"Same material, different lot at {lot.get('location_id')}"
            })

        # Check compatible materials
        compatible = self._compatibility_map.get(material_id, [])
        for alt_material, score in compatible:
            available = self._get_available_inventory(alt_material)
            if available > 0:
                alternatives.append({
                    'type': 'alternative_material',
                    'material_id': alt_material,
                    'material_name': self._get_material_name(alt_material),
                    'available_quantity': float(available),
                    'compatibility_score': score,
                    'cost_difference': self._get_cost_difference(material_id, alt_material),
                    'lead_time_days': 0,
                    'notes': f"Compatible substitute (score: {score:.0%})"
                })

        # Check for rush order options
        rush_options = self._get_rush_order_options(material_id, qty_needed)
        for option in rush_options:
            alternatives.append({
                'type': 'rush_order',
                'material_id': material_id,
                'material_name': self._get_material_name(material_id),
                'supplier': option.get('supplier'),
                'available_quantity': float(qty_needed),
                'compatibility_score': 1.0,
                'cost_difference': option.get('cost_premium', 0),
                'lead_time_days': option.get('lead_time_days', 3),
                'notes': f"Rush order from {option.get('supplier')}"
            })

        # Sort by compatibility score then cost
        alternatives.sort(key=lambda x: (-x['compatibility_score'], x['cost_difference']))

        return alternatives[:max_alternatives]

    def _get_alternative_lots(
        self,
        material_id: str,
        quantity_needed: Decimal
    ) -> List[Dict[str, Any]]:
        """Get alternative lots for the same material."""
        if self.session:
            try:
                from models.erp.inventory import InventoryLot

                lots = self.session.query(InventoryLot).filter(
                    InventoryLot.material_id == material_id,
                    InventoryLot.quantity_available > 0,
                    InventoryLot.is_active == True
                ).order_by(InventoryLot.expiry_date.asc().nullsfirst()).all()

                return [{
                    'lot_number': lot.lot_number,
                    'quantity': float(lot.quantity_available),
                    'location_id': lot.location_id,
                    'expiry_date': lot.expiry_date.isoformat() if lot.expiry_date else None
                } for lot in lots]
            except ImportError:
                pass

        return []

    def _get_cost_difference(self, original: str, alternative: str) -> float:
        """Get cost difference between materials."""
        # Demo pricing
        prices = {
            'PLA': 25.0,
            'PLA-PRO': 35.0,
            'PLA-PLUS': 30.0,
            'ABS': 28.0,
            'ABS-PLUS': 38.0,
            'PETG': 30.0,
            'ASA': 45.0,
            'ALU-6061': 5.0,
            'ALU-7075': 8.0,
        }
        orig_price = prices.get(original, 0)
        alt_price = prices.get(alternative, 0)
        return alt_price - orig_price

    def _get_rush_order_options(
        self,
        material_id: str,
        quantity_needed: Decimal
    ) -> List[Dict[str, Any]]:
        """Get rush order options from suppliers."""
        # Demo suppliers
        suppliers = {
            'PLA': [
                {'supplier': 'FastFilament Inc', 'lead_time_days': 2, 'cost_premium': 15.0},
                {'supplier': 'QuickPrint Supply', 'lead_time_days': 3, 'cost_premium': 10.0},
            ],
            'ABS': [
                {'supplier': 'FastFilament Inc', 'lead_time_days': 2, 'cost_premium': 12.0},
            ],
            'ALU-6061': [
                {'supplier': 'MetalExpress', 'lead_time_days': 1, 'cost_premium': 25.0},
                {'supplier': 'QuickMetals', 'lead_time_days': 3, 'cost_premium': 15.0},
            ],
        }
        return suppliers.get(material_id, [])

    def calculate_schedule_impact(
        self,
        job_id: str,
        shortage_quantity: float,
        material_id: str
    ) -> Dict[str, Any]:
        """
        Calculate impact of material shortage on schedule.

        Args:
            job_id: Affected job
            shortage_quantity: Amount short
            material_id: Material that's short

        Returns:
            Schedule impact analysis
        """
        # Estimate delay based on lead time for replenishment
        estimated_lead_time_hours = 48  # Default 2 days

        rush_options = self._get_rush_order_options(material_id, Decimal(str(shortage_quantity)))
        if rush_options:
            # Use fastest rush option
            min_days = min(opt['lead_time_days'] for opt in rush_options)
            estimated_lead_time_hours = min_days * 24

        # Get job details
        job_details = self._get_job_details(job_id)

        if not job_details:
            return {
                'job_id': job_id,
                'delay_hours': estimated_lead_time_hours,
                'downstream_jobs_affected': 0,
                'customer_impact': 'Unknown - job not found'
            }

        original_start = job_details.get('scheduled_start')
        original_end = job_details.get('scheduled_end')

        delayed_start = original_start + timedelta(hours=estimated_lead_time_hours) if original_start else None
        delayed_end = original_end + timedelta(hours=estimated_lead_time_hours) if original_end else None

        # Find downstream jobs
        downstream = self._get_downstream_jobs(job_id)

        return {
            'job_id': job_id,
            'work_order_id': job_details.get('work_order_id'),
            'original_start': original_start.isoformat() if original_start else None,
            'original_end': original_end.isoformat() if original_end else None,
            'delayed_start': delayed_start.isoformat() if delayed_start else None,
            'delayed_end': delayed_end.isoformat() if delayed_end else None,
            'delay_hours': estimated_lead_time_hours,
            'downstream_jobs_affected': len(downstream),
            'downstream_jobs': downstream,
            'customer_due_date': job_details.get('due_date'),
            'will_miss_due_date': self._will_miss_due_date(delayed_end, job_details.get('due_date')),
            'customer_impact': self._assess_customer_impact(job_details, estimated_lead_time_hours)
        }

    def _get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details from database."""
        if self.session:
            try:
                from models.mes.work_orders import Job

                job = self.session.query(Job).filter(Job.job_id == job_id).first()
                if job:
                    return {
                        'job_id': job.job_id,
                        'work_order_id': str(job.work_order_id),
                        'scheduled_start': job.scheduled_start,
                        'scheduled_end': job.scheduled_end,
                        'due_date': job.due_date,
                        'priority': job.priority_score
                    }
            except ImportError:
                pass

        return None

    def _get_downstream_jobs(self, job_id: str) -> List[str]:
        """Get jobs that depend on this job."""
        # In a full implementation, would query job dependencies
        return []

    def _will_miss_due_date(self, delayed_end: datetime, due_date: date) -> bool:
        """Check if delay will cause due date miss."""
        if not delayed_end or not due_date:
            return False
        return delayed_end.date() > due_date

    def _assess_customer_impact(
        self,
        job_details: Dict[str, Any],
        delay_hours: float
    ) -> str:
        """Assess customer impact of delay."""
        if not job_details:
            return 'Unknown'

        priority = job_details.get('priority', 5)
        due_date = job_details.get('due_date')

        if priority >= 8:
            return 'HIGH - Critical priority order affected'
        elif due_date and self._will_miss_due_date(
            datetime.now() + timedelta(hours=delay_hours),
            due_date
        ):
            return 'MEDIUM - Will miss committed due date'
        elif delay_hours > 72:
            return 'MEDIUM - Significant delay'
        else:
            return 'LOW - Minor delay, within buffer'

    def _generate_recommendations(
        self,
        shortage: MaterialShortage,
        alternatives: List[Dict[str, Any]],
        impact: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations."""
        recommendations = []

        # Check for same-material lot alternatives
        lot_alts = [a for a in alternatives if a['type'] == 'alternative_lot']
        if lot_alts:
            recommendations.append({
                'priority': 1,
                'action': 'use_alternative_lot',
                'description': f"Use lot {lot_alts[0]['lot_number']} from {lot_alts[0]['location_id']}",
                'cost_impact': 0,
                'time_impact': 0
            })

        # Check for compatible material alternatives
        mat_alts = [a for a in alternatives if a['type'] == 'alternative_material' and a['compatibility_score'] >= 0.9]
        if mat_alts:
            best = mat_alts[0]
            recommendations.append({
                'priority': 2,
                'action': 'substitute_material',
                'description': f"Substitute with {best['material_name']} ({best['compatibility_score']:.0%} compatible)",
                'cost_impact': best['cost_difference'],
                'time_impact': 0
            })

        # Rush order option
        rush_alts = [a for a in alternatives if a['type'] == 'rush_order']
        if rush_alts:
            fastest = min(rush_alts, key=lambda x: x['lead_time_days'])
            recommendations.append({
                'priority': 3,
                'action': 'rush_order',
                'description': f"Rush order from {fastest['supplier']} ({fastest['lead_time_days']} day delivery)",
                'cost_impact': fastest['cost_difference'],
                'time_impact': fastest['lead_time_days'] * 24
            })

        # Schedule adjustment
        if impact and impact.get('delay_hours', 0) < 48:
            recommendations.append({
                'priority': 4,
                'action': 'reschedule',
                'description': f"Delay job by {impact.get('delay_hours', 0):.0f} hours",
                'cost_impact': 0,
                'time_impact': impact.get('delay_hours', 0)
            })

        return sorted(recommendations, key=lambda x: x['priority'])

    def _emit_shortage_alert(
        self,
        shortage: MaterialShortage,
        alternatives: List[Dict[str, Any]]
    ):
        """Emit shortage alert to dashboard."""
        try:
            from app import socketio
            socketio.emit('material_shortage', {
                'shortage_id': shortage.shortage_id,
                'material_id': shortage.material_id,
                'material_name': self._get_material_name(shortage.material_id),
                'shortage_quantity': shortage.quantity_short,
                'job_id': shortage.job_id,
                'work_order_id': shortage.work_order_id,
                'required_date': shortage.required_date.isoformat() if shortage.required_date else None,
                'alternatives_available': len(alternatives),
                'timestamp': datetime.utcnow().isoformat()
            }, namespace='/dashboard')
        except Exception as e:
            logger.debug(f"WebSocket emit failed: {e}")

    def resolve_shortage(
        self,
        shortage_id: str,
        resolution_type: str,
        resolution_details: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Mark shortage as resolved.

        Args:
            shortage_id: Shortage ID
            resolution_type: How it was resolved
            resolution_details: Details of resolution

        Returns:
            Updated shortage record
        """
        shortage = self.session.query(MaterialShortage).filter(
            MaterialShortage.shortage_id == shortage_id
        ).first()

        if not shortage:
            return {'error': 'Shortage not found', 'shortage_id': shortage_id}

        shortage.status = ShortageStatus.RESOLVED.value
        shortage.resolution_type = resolution_type
        shortage.resolved_at = datetime.utcnow()

        self.session.flush()

        logger.info(f"Shortage {shortage_id} resolved via {resolution_type}")

        return {
            'shortage_id': shortage_id,
            'status': shortage.status,
            'resolution_type': shortage.resolution_type,
            'resolved_at': shortage.resolved_at.isoformat()
        }

    def get_active_shortages(self) -> List[Dict[str, Any]]:
        """Get all active (unresolved) shortages."""
        shortages = self.session.query(MaterialShortage).filter(
            MaterialShortage.status == ShortageStatus.DETECTED.value
        ).all()

        active = []
        for shortage in shortages:
            active.append({
                'shortage_id': shortage.shortage_id,
                'material_id': shortage.material_id,
                'material_name': self._get_material_name(shortage.material_id),
                'shortage_quantity': shortage.quantity_short,
                'job_id': shortage.job_id,
                'work_order_id': shortage.work_order_id,
                'required_date': shortage.required_date.isoformat() if shortage.required_date else None,
                'detected_at': shortage.created_at.isoformat() if shortage.created_at else None
            })
        return active

    def get_shortage_summary(self) -> Dict[str, Any]:
        """Get summary of material shortages."""
        total = self.session.query(func.count(MaterialShortage.id)).scalar() or 0
        active = self.session.query(func.count(MaterialShortage.id)).filter(
            MaterialShortage.status == ShortageStatus.DETECTED.value
        ).scalar() or 0
        resolved = total - active

        return {
            'total_shortages': total,
            'active_shortages': active,
            'resolved_shortages': resolved,
            'shortages_by_material': self._group_shortages_by_material(),
            'resolution_breakdown': self._get_resolution_breakdown()
        }

    def _group_shortages_by_material(self) -> Dict[str, int]:
        """Group shortages by material."""
        rows = self.session.query(
            MaterialShortage.material_id,
            func.count(MaterialShortage.id)
        ).group_by(MaterialShortage.material_id).all()

        return {row[0]: row[1] for row in rows}

    def _get_resolution_breakdown(self) -> Dict[str, int]:
        """Get breakdown of resolutions by type."""
        rows = self.session.query(
            MaterialShortage.resolution_type,
            func.count(MaterialShortage.id)
        ).filter(
            MaterialShortage.resolution_type.isnot(None)
        ).group_by(MaterialShortage.resolution_type).all()

        return {row[0]: row[1] for row in rows}


# Convenience functions
def check_material(
    session: Session,
    material_id: str,
    quantity: float,
    **kwargs
) -> Dict[str, Any]:
    """Check material availability."""
    service = MaterialPlannerService(session)
    return service.check_material_availability(material_id, quantity, **kwargs)


def get_alternatives(
    session: Session,
    material_id: str,
    quantity: float
) -> List[Dict[str, Any]]:
    """Get material alternatives."""
    service = MaterialPlannerService(session)
    return service.suggest_alternatives(material_id, quantity)
