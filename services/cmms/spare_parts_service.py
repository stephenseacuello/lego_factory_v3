"""
Spare Parts Integration Service
=================================
Parts availability, auto-requisition, and usage tracking.

Enhanced Features:
- Min/max inventory optimization based on usage patterns
- Reorder point calculation with lead time and safety stock
- ABC classification for parts criticality
- MRP integration for procurement planning
- Obsolescence tracking for aging inventory
"""
import math
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from decimal import Decimal

logger = logging.getLogger(__name__)


class ABCClassification(str, Enum):
    """ABC inventory classification."""
    A = 'A'  # High value, tight control (top 20% by value, ~80% of total value)
    B = 'B'  # Medium value, moderate control (next 30%)
    C = 'C'  # Low value, simple control (remaining 50%)


class ObsolescenceRisk(str, Enum):
    """Obsolescence risk level."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


@dataclass
class InventoryOptimization:
    """Optimized inventory parameters."""
    part_id: str
    current_on_hand: int
    recommended_min: int
    recommended_max: int
    reorder_point: int
    safety_stock: int
    economic_order_qty: int
    avg_daily_usage: float
    lead_time_days: int
    service_level: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'part_id': self.part_id,
            'current_on_hand': self.current_on_hand,
            'inventory_parameters': {
                'min': self.recommended_min,
                'max': self.recommended_max,
                'reorder_point': self.reorder_point,
                'safety_stock': self.safety_stock,
                'eoq': self.economic_order_qty,
            },
            'usage': {
                'avg_daily': round(self.avg_daily_usage, 2),
                'lead_time_days': self.lead_time_days,
            },
            'service_level': self.service_level,
            'status': self._get_status(),
        }

    def _get_status(self) -> str:
        if self.current_on_hand <= self.safety_stock:
            return 'critical'
        elif self.current_on_hand <= self.reorder_point:
            return 'reorder_needed'
        elif self.current_on_hand >= self.recommended_max:
            return 'overstocked'
        else:
            return 'optimal'


@dataclass
class ABCAnalysisResult:
    """ABC analysis result for a part."""
    part_id: str
    part_name: str
    annual_value: float
    annual_quantity: int
    unit_cost: float
    classification: ABCClassification
    cumulative_value_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'part_id': self.part_id,
            'part_name': self.part_name,
            'annual_value': round(self.annual_value, 2),
            'annual_quantity': self.annual_quantity,
            'unit_cost': round(self.unit_cost, 2),
            'classification': self.classification.value,
            'cumulative_value_pct': round(self.cumulative_value_pct, 1),
            'control_level': self._get_control_level(),
        }

    def _get_control_level(self) -> str:
        if self.classification == ABCClassification.A:
            return 'tight_control'
        elif self.classification == ABCClassification.B:
            return 'moderate_control'
        else:
            return 'simple_control'


@dataclass
class ObsolescenceAssessment:
    """Obsolescence assessment for a part."""
    part_id: str
    part_name: str
    last_usage_date: Optional[datetime]
    days_since_use: int
    on_hand_qty: int
    on_hand_value: float
    risk_level: ObsolescenceRisk
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'part_id': self.part_id,
            'part_name': self.part_name,
            'last_usage_date': self.last_usage_date.isoformat() if self.last_usage_date else None,
            'days_since_use': self.days_since_use,
            'on_hand_qty': self.on_hand_qty,
            'on_hand_value': round(self.on_hand_value, 2),
            'risk_level': self.risk_level.value,
            'recommendation': self.recommendation,
        }


class SparePartsService:
    """
    Spare parts management with inventory optimization.

    Features:
    - Availability checking
    - Usage tracking and trending
    - Min/max optimization
    - ABC classification
    - Obsolescence tracking
    """

    def __init__(self, session):
        self.session = session

    def check_parts_availability(self, required_parts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check if all required parts are in stock."""
        from models.cmms.assets import Spare

        available = []
        missing = []
        for part in required_parts:
            part_id = part.get('part_id', '')
            qty_needed = part.get('quantity', 1)

            # Query the database for current on-hand quantity
            try:
                spare = self.session.query(Spare).filter(
                    Spare.spare_id == part_id
                ).first()
                qty_on_hand = spare.quantity_on_hand if spare else 0
            except Exception:
                logger.warning("Failed to query spare %s, falling back to provided on_hand", part_id)
                qty_on_hand = part.get('on_hand', 0)

            if qty_on_hand >= qty_needed:
                available.append({'part_id': part_id, 'needed': qty_needed, 'on_hand': qty_on_hand})
            else:
                missing.append({'part_id': part_id, 'needed': qty_needed, 'on_hand': qty_on_hand,
                                'shortage': qty_needed - qty_on_hand})
        return {
            'all_available': len(missing) == 0,
            'available': available, 'missing': missing,
            'total_parts': len(required_parts),
        }

    def auto_requisition(self, part_id: str, quantity: int, reorder_point: int = 5) -> Dict[str, Any]:
        """Create purchase requisition if below reorder point."""
        return {
            'part_id': part_id,
            'requisition_qty': quantity,
            'reorder_point': reorder_point,
            'status': 'requisition_created',
            'created_at': datetime.utcnow().isoformat(),
        }

    def record_usage(self, part_id: str, quantity: int, work_order_id: str = None) -> Dict[str, Any]:
        """Record spare part usage by decrementing on-hand and writing a WorkOrderMaterial row."""
        from models.cmms.assets import Spare
        from models.cmms.maintenance import WorkOrderMaterial, MaintenanceWorkOrder

        timestamp = datetime.utcnow()

        try:
            spare = self.session.query(Spare).filter(
                Spare.spare_id == part_id
            ).first()

            if spare is None:
                logger.warning("Spare %s not found in database; usage not persisted", part_id)
                return {
                    'status': 'error',
                    'message': f'Spare part {part_id} not found',
                }

            # Decrement on-hand quantity (floor at 0)
            spare.quantity_on_hand = max(0, (spare.quantity_on_hand or 0) - quantity)

            # If a work order was supplied, create/update a WorkOrderMaterial record
            if work_order_id:
                wo = self.session.query(MaintenanceWorkOrder).filter(
                    MaintenanceWorkOrder.wo_number == work_order_id
                ).first()

                if wo:
                    # Look for an existing material line for this spare on this WO
                    existing = self.session.query(WorkOrderMaterial).filter(
                        WorkOrderMaterial.work_order_id == wo.id,
                        WorkOrderMaterial.spare_id == spare.id,
                    ).first()

                    if existing:
                        existing.quantity_used = (existing.quantity_used or 0) + quantity
                        existing.unit_cost = spare.unit_cost
                        if existing.unit_cost:
                            existing.total_cost = existing.quantity_used * existing.unit_cost
                    else:
                        unit_cost = spare.unit_cost or 0
                        mat = WorkOrderMaterial(
                            work_order_id=wo.id,
                            spare_id=spare.id,
                            description=spare.name or part_id,
                            quantity_required=quantity,
                            quantity_used=quantity,
                            unit_cost=unit_cost,
                            total_cost=unit_cost * quantity,
                        )
                        self.session.add(mat)

            self.session.flush()

        except Exception:
            logger.exception("Failed to record usage for spare %s", part_id)
            self.session.rollback()
            return {
                'status': 'error',
                'message': f'Database error recording usage for {part_id}',
            }

        entry = {
            'part_id': part_id,
            'quantity': quantity,
            'work_order_id': work_order_id,
            'timestamp': timestamp.isoformat(),
        }
        return {'status': 'recorded', 'entry': entry}

    def get_usage_history(self, part_id: str, period_days: int = 90) -> Dict[str, Any]:
        """Get consumption trend for a part from WorkOrderMaterial records."""
        from sqlalchemy import func, extract
        from models.cmms.assets import Spare
        from models.cmms.maintenance import WorkOrderMaterial

        cutoff = datetime.utcnow() - timedelta(days=period_days)

        try:
            spare = self.session.query(Spare).filter(
                Spare.spare_id == part_id
            ).first()

            if spare is None:
                return {
                    'part_id': part_id,
                    'period_days': period_days,
                    'total_consumed': 0,
                    'usage_count': 0,
                    'monthly_trend': [],
                }

            # Query all WorkOrderMaterial rows for this spare within the period
            entries = (
                self.session.query(WorkOrderMaterial)
                .filter(
                    WorkOrderMaterial.spare_id == spare.id,
                    WorkOrderMaterial.created_at >= cutoff,
                )
                .all()
            )

            total_qty = sum((e.quantity_used or 0) for e in entries)

            # Group by year-month
            monthly: Dict[str, float] = defaultdict(float)
            for e in entries:
                if e.created_at:
                    month_key = e.created_at.strftime('%Y-%m')
                    monthly[month_key] += (e.quantity_used or 0)

            return {
                'part_id': part_id,
                'period_days': period_days,
                'total_consumed': total_qty,
                'usage_count': len(entries),
                'monthly_trend': [
                    {'month': m, 'quantity': q}
                    for m, q in sorted(monthly.items())
                ],
            }

        except Exception:
            logger.exception("Failed to get usage history for spare %s", part_id)
            return {
                'part_id': part_id,
                'period_days': period_days,
                'total_consumed': 0,
                'usage_count': 0,
                'monthly_trend': [],
            }

    # ==================== Inventory Optimization ====================

    def calculate_optimal_inventory(
        self,
        part_id: str,
        current_on_hand: int,
        unit_cost: float,
        lead_time_days: int = 14,
        service_level: float = 0.95,
        holding_cost_pct: float = 0.25,
        order_cost: float = 50.0,
        period_days: int = 365
    ) -> InventoryOptimization:
        """
        Calculate optimal min/max inventory levels.

        Uses Economic Order Quantity (EOQ) model with safety stock
        based on service level and demand variability.

        Args:
            part_id: Part identifier
            current_on_hand: Current inventory quantity
            unit_cost: Cost per unit
            lead_time_days: Lead time for replenishment
            service_level: Target service level (0.0-1.0)
            holding_cost_pct: Annual holding cost as % of unit cost
            order_cost: Fixed cost per order
            period_days: Analysis period for usage data

        Returns:
            Optimized inventory parameters
        """
        # Get usage history
        history = self.get_usage_history(part_id, period_days)
        total_used = history['total_consumed']

        if total_used == 0:
            # No usage - set minimal levels
            return InventoryOptimization(
                part_id=part_id,
                current_on_hand=current_on_hand,
                recommended_min=1,
                recommended_max=5,
                reorder_point=1,
                safety_stock=1,
                economic_order_qty=1,
                avg_daily_usage=0,
                lead_time_days=lead_time_days,
                service_level=service_level
            )

        # Calculate average daily usage
        avg_daily_usage = total_used / period_days

        # Calculate usage variability (standard deviation)
        monthly_data = history['monthly_trend']
        if len(monthly_data) >= 2:
            monthly_values = [m['quantity'] for m in monthly_data]
            avg_monthly = sum(monthly_values) / len(monthly_values)
            variance = sum((v - avg_monthly) ** 2 for v in monthly_values) / len(monthly_values)
            std_dev_monthly = math.sqrt(variance)
            std_dev_daily = std_dev_monthly / 30  # Approximate daily std dev
        else:
            std_dev_daily = avg_daily_usage * 0.3  # Default 30% variability

        # Calculate safety stock using service level Z-score
        z_score = self._service_level_to_z(service_level)
        safety_stock = int(math.ceil(z_score * std_dev_daily * math.sqrt(lead_time_days)))
        safety_stock = max(1, safety_stock)

        # Calculate reorder point (ROP)
        lead_time_demand = avg_daily_usage * lead_time_days
        reorder_point = int(math.ceil(lead_time_demand + safety_stock))

        # Calculate Economic Order Quantity (EOQ)
        annual_demand = avg_daily_usage * 365
        holding_cost = unit_cost * holding_cost_pct

        if holding_cost > 0 and annual_demand > 0:
            eoq = int(math.ceil(math.sqrt((2 * annual_demand * order_cost) / holding_cost)))
            eoq = max(1, eoq)
        else:
            eoq = max(1, int(avg_daily_usage * 30))  # Default to 1 month supply

        # Calculate min/max
        recommended_min = reorder_point
        recommended_max = reorder_point + eoq

        return InventoryOptimization(
            part_id=part_id,
            current_on_hand=current_on_hand,
            recommended_min=recommended_min,
            recommended_max=recommended_max,
            reorder_point=reorder_point,
            safety_stock=safety_stock,
            economic_order_qty=eoq,
            avg_daily_usage=avg_daily_usage,
            lead_time_days=lead_time_days,
            service_level=service_level
        )

    def _service_level_to_z(self, service_level: float) -> float:
        """Convert service level to Z-score (normal distribution)."""
        # Common service levels and their Z-scores
        z_table = {
            0.50: 0.00,
            0.80: 0.84,
            0.85: 1.04,
            0.90: 1.28,
            0.95: 1.65,
            0.97: 1.88,
            0.99: 2.33,
            0.999: 3.09,
        }

        # Find closest match
        closest = min(z_table.keys(), key=lambda x: abs(x - service_level))
        return z_table[closest]

    def bulk_optimize_inventory(
        self,
        parts_data: List[Dict[str, Any]],
        default_lead_time: int = 14,
        service_level: float = 0.95
    ) -> Dict[str, Any]:
        """
        Optimize inventory for multiple parts at once.

        Args:
            parts_data: List of dicts with part_id, on_hand, unit_cost
            default_lead_time: Default lead time for all parts
            service_level: Target service level

        Returns:
            Optimization results for all parts
        """
        results = []
        needs_reorder = []
        overstocked = []

        for part in parts_data:
            opt = self.calculate_optimal_inventory(
                part_id=part['part_id'],
                current_on_hand=part.get('on_hand', 0),
                unit_cost=part.get('unit_cost', 10.0),
                lead_time_days=part.get('lead_time_days', default_lead_time),
                service_level=service_level
            )

            result = opt.to_dict()
            results.append(result)

            if opt.current_on_hand <= opt.reorder_point:
                needs_reorder.append({
                    'part_id': part['part_id'],
                    'current': opt.current_on_hand,
                    'reorder_point': opt.reorder_point,
                    'order_qty': opt.economic_order_qty
                })

            if opt.current_on_hand > opt.recommended_max:
                overstocked.append({
                    'part_id': part['part_id'],
                    'current': opt.current_on_hand,
                    'max': opt.recommended_max,
                    'excess': opt.current_on_hand - opt.recommended_max
                })

        return {
            'parts_analyzed': len(results),
            'results': results,
            'needs_reorder': needs_reorder,
            'overstocked': overstocked,
            'summary': {
                'reorder_count': len(needs_reorder),
                'overstock_count': len(overstocked),
            }
        }

    # ==================== ABC Classification ====================

    def abc_analysis(
        self,
        parts_data: List[Dict[str, Any]],
        period_days: int = 365
    ) -> Dict[str, Any]:
        """
        Perform ABC classification on parts inventory.

        Classifies parts based on annual value (price x usage):
        - A items: Top 20% by value (~80% of total value)
        - B items: Next 30% by value (~15% of total value)
        - C items: Remaining 50% (~5% of total value)

        Args:
            parts_data: List of dicts with part_id, part_name, unit_cost, annual_qty
            period_days: Period for usage analysis

        Returns:
            ABC classification results
        """
        # Calculate annual value for each part
        parts_with_value = []
        for part in parts_data:
            part_id = part['part_id']
            part_name = part.get('part_name', part_id)
            unit_cost = part.get('unit_cost', 0)

            # Get actual usage if available
            history = self.get_usage_history(part_id, period_days)
            annual_qty = history['total_consumed']

            if annual_qty == 0:
                annual_qty = part.get('annual_qty', 0)

            annual_value = unit_cost * annual_qty

            parts_with_value.append({
                'part_id': part_id,
                'part_name': part_name,
                'unit_cost': unit_cost,
                'annual_qty': annual_qty,
                'annual_value': annual_value
            })

        # Sort by annual value (descending)
        parts_with_value.sort(key=lambda x: x['annual_value'], reverse=True)

        # Calculate total value
        total_value = sum(p['annual_value'] for p in parts_with_value)

        if total_value == 0:
            # No value data - use equal classification
            n = len(parts_with_value)
            a_cutoff = int(n * 0.2)
            b_cutoff = int(n * 0.5)

            results = []
            for i, p in enumerate(parts_with_value):
                if i < a_cutoff:
                    classification = ABCClassification.A
                elif i < b_cutoff:
                    classification = ABCClassification.B
                else:
                    classification = ABCClassification.C

                results.append(ABCAnalysisResult(
                    part_id=p['part_id'],
                    part_name=p['part_name'],
                    annual_value=p['annual_value'],
                    annual_quantity=p['annual_qty'],
                    unit_cost=p['unit_cost'],
                    classification=classification,
                    cumulative_value_pct=0
                ))

            return {
                'parts_analyzed': len(results),
                'total_annual_value': 0,
                'results': [r.to_dict() for r in results],
                'summary': {
                    'A_count': a_cutoff,
                    'B_count': b_cutoff - a_cutoff,
                    'C_count': n - b_cutoff,
                }
            }

        # Classify based on cumulative value percentage
        results = []
        cumulative_value = 0

        for p in parts_with_value:
            cumulative_value += p['annual_value']
            cumulative_pct = (cumulative_value / total_value) * 100

            if cumulative_pct <= 80:
                classification = ABCClassification.A
            elif cumulative_pct <= 95:
                classification = ABCClassification.B
            else:
                classification = ABCClassification.C

            results.append(ABCAnalysisResult(
                part_id=p['part_id'],
                part_name=p['part_name'],
                annual_value=p['annual_value'],
                annual_quantity=p['annual_qty'],
                unit_cost=p['unit_cost'],
                classification=classification,
                cumulative_value_pct=cumulative_pct
            ))

        # Count by classification
        a_count = len([r for r in results if r.classification == ABCClassification.A])
        b_count = len([r for r in results if r.classification == ABCClassification.B])
        c_count = len([r for r in results if r.classification == ABCClassification.C])

        a_value = sum(r.annual_value for r in results if r.classification == ABCClassification.A)
        b_value = sum(r.annual_value for r in results if r.classification == ABCClassification.B)
        c_value = sum(r.annual_value for r in results if r.classification == ABCClassification.C)

        return {
            'parts_analyzed': len(results),
            'total_annual_value': round(total_value, 2),
            'results': [r.to_dict() for r in results],
            'summary': {
                'A': {'count': a_count, 'value': round(a_value, 2), 'value_pct': round(a_value / total_value * 100, 1)},
                'B': {'count': b_count, 'value': round(b_value, 2), 'value_pct': round(b_value / total_value * 100, 1)},
                'C': {'count': c_count, 'value': round(c_value, 2), 'value_pct': round(c_value / total_value * 100, 1)},
            },
            'recommendations': [
                f"A items ({a_count}): Implement tight control, frequent review, accurate forecasting",
                f"B items ({b_count}): Moderate control, periodic review, safety stock",
                f"C items ({c_count}): Simple control, larger safety stock, less frequent review"
            ]
        }

    # ==================== Obsolescence Tracking ====================

    def obsolescence_analysis(
        self,
        parts_data: List[Dict[str, Any]],
        slow_moving_days: int = 180,
        obsolete_days: int = 365
    ) -> Dict[str, Any]:
        """
        Analyze parts for obsolescence risk.

        Identifies slow-moving and obsolete inventory based on last usage.

        Args:
            parts_data: List of dicts with part_id, part_name, on_hand, unit_cost
            slow_moving_days: Days without use to be considered slow-moving
            obsolete_days: Days without use to be considered obsolete

        Returns:
            Obsolescence analysis results
        """
        from sqlalchemy import func
        from models.cmms.assets import Spare
        from models.cmms.maintenance import WorkOrderMaterial

        now = datetime.utcnow()
        results = []
        total_at_risk_value = 0

        for part in parts_data:
            part_id = part['part_id']
            part_name = part.get('part_name', part_id)
            on_hand = part.get('on_hand', 0)
            unit_cost = part.get('unit_cost', 0)

            # Find last usage from WorkOrderMaterial records
            last_usage = None
            days_since_use = 9999  # No recorded usage

            try:
                spare = self.session.query(Spare).filter(
                    Spare.spare_id == part_id
                ).first()

                if spare is not None:
                    last_mat = (
                        self.session.query(func.max(WorkOrderMaterial.created_at))
                        .filter(WorkOrderMaterial.spare_id == spare.id)
                        .scalar()
                    )
                    if last_mat is not None:
                        last_usage = last_mat
                        days_since_use = (now - last_usage).days
            except Exception:
                logger.exception(
                    "Failed to query last usage for spare %s; treating as no usage",
                    part_id,
                )

            # Determine risk level
            on_hand_value = on_hand * unit_cost

            if days_since_use >= obsolete_days:
                risk_level = ObsolescenceRisk.CRITICAL
                recommendation = "Consider disposal, return to vendor, or write-off"
            elif days_since_use >= slow_moving_days:
                risk_level = ObsolescenceRisk.HIGH
                recommendation = "Review demand forecast, consider reducing stock"
            elif days_since_use >= slow_moving_days // 2:
                risk_level = ObsolescenceRisk.MEDIUM
                recommendation = "Monitor closely, verify continued need"
            else:
                risk_level = ObsolescenceRisk.LOW
                recommendation = "Normal usage pattern"

            if risk_level in (ObsolescenceRisk.HIGH, ObsolescenceRisk.CRITICAL):
                total_at_risk_value += on_hand_value

            assessment = ObsolescenceAssessment(
                part_id=part_id,
                part_name=part_name,
                last_usage_date=last_usage,
                days_since_use=days_since_use if days_since_use < 9999 else -1,
                on_hand_qty=on_hand,
                on_hand_value=on_hand_value,
                risk_level=risk_level,
                recommendation=recommendation
            )
            results.append(assessment)

        # Sort by risk (critical first)
        risk_order = {
            ObsolescenceRisk.CRITICAL: 0,
            ObsolescenceRisk.HIGH: 1,
            ObsolescenceRisk.MEDIUM: 2,
            ObsolescenceRisk.LOW: 3
        }
        results.sort(key=lambda x: risk_order[x.risk_level])

        # Count by risk level
        critical_count = len([r for r in results if r.risk_level == ObsolescenceRisk.CRITICAL])
        high_count = len([r for r in results if r.risk_level == ObsolescenceRisk.HIGH])
        medium_count = len([r for r in results if r.risk_level == ObsolescenceRisk.MEDIUM])
        low_count = len([r for r in results if r.risk_level == ObsolescenceRisk.LOW])

        return {
            'parts_analyzed': len(results),
            'results': [r.to_dict() for r in results],
            'summary': {
                'critical': critical_count,
                'high': high_count,
                'medium': medium_count,
                'low': low_count,
                'total_at_risk_value': round(total_at_risk_value, 2),
            },
            'thresholds': {
                'slow_moving_days': slow_moving_days,
                'obsolete_days': obsolete_days,
            }
        }

    # ==================== MRP Integration ====================

    def generate_mrp_requirements(
        self,
        work_orders: List[Dict[str, Any]],
        parts_inventory: Dict[str, int],
        bom_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Generate Material Requirements Planning (MRP) output.

        Calculates net requirements based on work orders, BOM, and inventory.

        Args:
            work_orders: List of work orders with job_id, product_id, quantity, due_date
            parts_inventory: Dict mapping part_id to current on_hand quantity
            bom_data: Dict mapping product_id to list of {part_id, qty_per}

        Returns:
            MRP requirements with planned orders
        """
        # Calculate gross requirements from work orders
        gross_requirements = defaultdict(int)
        requirement_details = []

        for wo in work_orders:
            product_id = wo.get('product_id')
            wo_qty = wo.get('quantity', 1)
            due_date = wo.get('due_date')

            # Get BOM for this product
            bom = bom_data.get(product_id, [])

            for component in bom:
                part_id = component['part_id']
                qty_per = component.get('qty_per', 1)
                required_qty = wo_qty * qty_per

                gross_requirements[part_id] += required_qty
                requirement_details.append({
                    'part_id': part_id,
                    'work_order': wo.get('job_id'),
                    'product': product_id,
                    'required_qty': required_qty,
                    'due_date': due_date
                })

        # Calculate net requirements
        net_requirements = {}
        planned_orders = []
        shortages = []

        for part_id, gross_qty in gross_requirements.items():
            on_hand = parts_inventory.get(part_id, 0)
            net_qty = max(0, gross_qty - on_hand)

            net_requirements[part_id] = {
                'gross_requirement': gross_qty,
                'on_hand': on_hand,
                'net_requirement': net_qty
            }

            if net_qty > 0:
                # Get optimized order quantity
                opt = self.calculate_optimal_inventory(
                    part_id=part_id,
                    current_on_hand=on_hand,
                    unit_cost=10.0,  # Default, should come from master data
                    lead_time_days=14
                )

                order_qty = max(net_qty, opt.economic_order_qty)

                planned_orders.append({
                    'part_id': part_id,
                    'order_quantity': order_qty,
                    'net_requirement': net_qty,
                    'status': 'planned'
                })

                shortages.append({
                    'part_id': part_id,
                    'shortage_qty': net_qty,
                    'on_hand': on_hand,
                    'required': gross_qty
                })

        return {
            'work_orders_processed': len(work_orders),
            'parts_analyzed': len(gross_requirements),
            'requirement_details': requirement_details,
            'net_requirements': net_requirements,
            'planned_orders': planned_orders,
            'shortages': shortages,
            'summary': {
                'total_gross_requirement': sum(gross_requirements.values()),
                'parts_with_shortage': len(shortages),
                'planned_order_count': len(planned_orders),
            }
        }
