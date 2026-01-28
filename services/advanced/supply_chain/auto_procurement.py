"""
Auto Procurement - Supply Chain Automation

LegoMCP World-Class Manufacturing System v5.0
Phase 22: Supply Chain Integration

Provides automated procurement capabilities:
- Automatic reorder point monitoring
- Supplier selection optimization
- Purchase order generation
- Lead time tracking
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import uuid


class ProcurementStatus(Enum):
    """Status of procurement actions."""
    PENDING = "pending"
    APPROVED = "approved"
    ORDERED = "ordered"
    SHIPPED = "shipped"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class SupplierTier(Enum):
    """Supplier tier classification."""
    PREFERRED = "preferred"
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    NEW = "new"


@dataclass
class MaterialRequirement:
    """A material requirement for procurement."""
    material_id: str
    material_name: str
    current_stock: float
    reorder_point: float
    reorder_quantity: float
    unit: str
    lead_time_days: int
    safety_stock: float


@dataclass
class SupplierQuote:
    """A quote from a supplier."""
    supplier_id: str
    supplier_name: str
    material_id: str
    unit_price: float
    currency: str
    min_order_qty: float
    lead_time_days: int
    tier: SupplierTier
    quality_score: float  # 0-100
    on_time_delivery_rate: float  # 0-1


@dataclass
class PurchaseOrder:
    """A purchase order."""
    po_id: str
    supplier_id: str
    supplier_name: str
    items: List[Dict]
    total_value: float
    currency: str
    status: ProcurementStatus
    created_at: datetime
    expected_delivery: datetime
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


@dataclass
class ProcurementRecommendation:
    """Recommendation for automated procurement."""
    recommendation_id: str
    material: MaterialRequirement
    recommended_supplier: SupplierQuote
    alternative_suppliers: List[SupplierQuote]
    recommended_quantity: float
    estimated_cost: float
    urgency: str  # critical, high, normal, low
    reason: str
    auto_approve_eligible: bool


class AutoProcurement:
    """
    Automated procurement system for supply chain management.

    Monitors inventory levels, selects optimal suppliers,
    and generates purchase orders automatically.
    """

    def __init__(self):
        self.materials: Dict[str, MaterialRequirement] = {}
        self.suppliers: Dict[str, List[SupplierQuote]] = {}
        self.purchase_orders: Dict[str, PurchaseOrder] = {}
        self.auto_approve_threshold = 1000.0  # Auto-approve under this value
        self._setup_demo_data()

    def _setup_demo_data(self):
        """Set up demonstration data."""
        self.materials = {
            'PLA-BLACK': MaterialRequirement(
                material_id='PLA-BLACK',
                material_name='PLA Filament - Black',
                current_stock=15.0,
                reorder_point=10.0,
                reorder_quantity=20.0,
                unit='kg',
                lead_time_days=5,
                safety_stock=5.0,
            ),
            'PLA-WHITE': MaterialRequirement(
                material_id='PLA-WHITE',
                material_name='PLA Filament - White',
                current_stock=8.0,
                reorder_point=10.0,
                reorder_quantity=20.0,
                unit='kg',
                lead_time_days=5,
                safety_stock=5.0,
            ),
            'PETG-CLEAR': MaterialRequirement(
                material_id='PETG-CLEAR',
                material_name='PETG Filament - Clear',
                current_stock=5.0,
                reorder_point=8.0,
                reorder_quantity=15.0,
                unit='kg',
                lead_time_days=7,
                safety_stock=3.0,
            ),
        }

        self.suppliers = {
            'PLA-BLACK': [
                SupplierQuote(
                    supplier_id='SUP-001',
                    supplier_name='FilamentCo Premium',
                    material_id='PLA-BLACK',
                    unit_price=22.50,
                    currency='USD',
                    min_order_qty=5.0,
                    lead_time_days=3,
                    tier=SupplierTier.PREFERRED,
                    quality_score=95.0,
                    on_time_delivery_rate=0.98,
                ),
                SupplierQuote(
                    supplier_id='SUP-002',
                    supplier_name='Budget Filaments',
                    material_id='PLA-BLACK',
                    unit_price=18.00,
                    currency='USD',
                    min_order_qty=10.0,
                    lead_time_days=7,
                    tier=SupplierTier.APPROVED,
                    quality_score=82.0,
                    on_time_delivery_rate=0.88,
                ),
            ],
            'PLA-WHITE': [
                SupplierQuote(
                    supplier_id='SUP-001',
                    supplier_name='FilamentCo Premium',
                    material_id='PLA-WHITE',
                    unit_price=22.50,
                    currency='USD',
                    min_order_qty=5.0,
                    lead_time_days=3,
                    tier=SupplierTier.PREFERRED,
                    quality_score=95.0,
                    on_time_delivery_rate=0.98,
                ),
            ],
            'PETG-CLEAR': [
                SupplierQuote(
                    supplier_id='SUP-003',
                    supplier_name='Specialty Polymers',
                    material_id='PETG-CLEAR',
                    unit_price=35.00,
                    currency='USD',
                    min_order_qty=5.0,
                    lead_time_days=5,
                    tier=SupplierTier.PREFERRED,
                    quality_score=92.0,
                    on_time_delivery_rate=0.95,
                ),
            ],
        }

    def check_reorder_points(self) -> List[ProcurementRecommendation]:
        """Check all materials against reorder points."""
        recommendations = []

        for material_id, material in self.materials.items():
            if material.current_stock <= material.reorder_point:
                rec = self._create_recommendation(material)
                if rec:
                    recommendations.append(rec)

        # Sort by urgency
        urgency_order = {'critical': 0, 'high': 1, 'normal': 2, 'low': 3}
        recommendations.sort(key=lambda r: urgency_order.get(r.urgency, 4))

        return recommendations

    def _create_recommendation(
        self,
        material: MaterialRequirement
    ) -> Optional[ProcurementRecommendation]:
        """Create a procurement recommendation."""
        quotes = self.suppliers.get(material.material_id, [])
        if not quotes:
            return None

        # Score suppliers
        scored_quotes = []
        for quote in quotes:
            score = self._score_supplier(quote, material)
            scored_quotes.append((score, quote))

        scored_quotes.sort(reverse=True)
        best_quote = scored_quotes[0][1]
        alternatives = [q for _, q in scored_quotes[1:3]]

        # Calculate quantity
        quantity = max(
            material.reorder_quantity,
            best_quote.min_order_qty
        )

        # Determine urgency
        days_of_stock = material.current_stock / max(1.0, material.reorder_quantity / 30)
        if days_of_stock <= 1:
            urgency = 'critical'
        elif days_of_stock <= 3:
            urgency = 'high'
        elif days_of_stock <= 7:
            urgency = 'normal'
        else:
            urgency = 'low'

        estimated_cost = quantity * best_quote.unit_price

        return ProcurementRecommendation(
            recommendation_id=str(uuid.uuid4()),
            material=material,
            recommended_supplier=best_quote,
            alternative_suppliers=alternatives,
            recommended_quantity=quantity,
            estimated_cost=estimated_cost,
            urgency=urgency,
            reason=f"Stock ({material.current_stock} {material.unit}) below "
                   f"reorder point ({material.reorder_point} {material.unit})",
            auto_approve_eligible=estimated_cost <= self.auto_approve_threshold,
        )

    def _score_supplier(
        self,
        quote: SupplierQuote,
        material: MaterialRequirement
    ) -> float:
        """Score a supplier for selection."""
        score = 0.0

        # Quality weight: 40%
        score += quote.quality_score * 0.4

        # Delivery reliability weight: 30%
        score += quote.on_time_delivery_rate * 100 * 0.3

        # Price weight: 20% (inverse - lower is better)
        max_price = max(q.unit_price for q in self.suppliers.get(material.material_id, [quote]))
        price_score = (1 - (quote.unit_price / max_price)) * 100
        score += price_score * 0.2

        # Lead time weight: 10% (inverse - shorter is better)
        max_lead = max(q.lead_time_days for q in self.suppliers.get(material.material_id, [quote]))
        lead_score = (1 - (quote.lead_time_days / max_lead)) * 100
        score += lead_score * 0.1

        # Tier bonus
        tier_bonus = {
            SupplierTier.PREFERRED: 5,
            SupplierTier.APPROVED: 2,
            SupplierTier.CONDITIONAL: 0,
            SupplierTier.NEW: -5,
        }
        score += tier_bonus.get(quote.tier, 0)

        return score

    def create_purchase_order(
        self,
        recommendation: ProcurementRecommendation,
        auto_approve: bool = False
    ) -> PurchaseOrder:
        """Create a purchase order from a recommendation."""
        po_id = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"

        po = PurchaseOrder(
            po_id=po_id,
            supplier_id=recommendation.recommended_supplier.supplier_id,
            supplier_name=recommendation.recommended_supplier.supplier_name,
            items=[{
                'material_id': recommendation.material.material_id,
                'material_name': recommendation.material.material_name,
                'quantity': recommendation.recommended_quantity,
                'unit': recommendation.material.unit,
                'unit_price': recommendation.recommended_supplier.unit_price,
                'line_total': recommendation.estimated_cost,
            }],
            total_value=recommendation.estimated_cost,
            currency=recommendation.recommended_supplier.currency,
            status=ProcurementStatus.PENDING,
            created_at=datetime.utcnow(),
            expected_delivery=(
                datetime.utcnow() +
                timedelta(days=recommendation.recommended_supplier.lead_time_days)
            ),
        )

        if auto_approve and recommendation.auto_approve_eligible:
            po.status = ProcurementStatus.APPROVED
            po.approved_by = 'SYSTEM_AUTO'
            po.approved_at = datetime.utcnow()

        self.purchase_orders[po.po_id] = po
        return po

    def get_pending_approvals(self) -> List[PurchaseOrder]:
        """Get purchase orders pending approval."""
        return [
            po for po in self.purchase_orders.values()
            if po.status == ProcurementStatus.PENDING
        ]

    def approve_purchase_order(
        self,
        po_id: str,
        approver: str
    ) -> Optional[PurchaseOrder]:
        """Approve a purchase order."""
        po = self.purchase_orders.get(po_id)
        if po and po.status == ProcurementStatus.PENDING:
            po.status = ProcurementStatus.APPROVED
            po.approved_by = approver
            po.approved_at = datetime.utcnow()
            return po
        return None

    def get_procurement_dashboard(self) -> Dict:
        """Get data for procurement dashboard."""
        recommendations = self.check_reorder_points()

        return {
            'materials_below_reorder': len(recommendations),
            'recommendations': [
                {
                    'material': r.material.material_name,
                    'urgency': r.urgency,
                    'supplier': r.recommended_supplier.supplier_name,
                    'estimated_cost': r.estimated_cost,
                }
                for r in recommendations
            ],
            'pending_orders': len(self.get_pending_approvals()),
            'total_pending_value': sum(
                po.total_value for po in self.get_pending_approvals()
            ),
            'active_orders': len([
                po for po in self.purchase_orders.values()
                if po.status in [ProcurementStatus.APPROVED, ProcurementStatus.ORDERED, ProcurementStatus.SHIPPED]
            ]),
        }


# Singleton instance
_auto_procurement: Optional[AutoProcurement] = None


def get_auto_procurement() -> AutoProcurement:
    """Get or create the auto procurement instance."""
    global _auto_procurement
    if _auto_procurement is None:
        _auto_procurement = AutoProcurement()
    return _auto_procurement
