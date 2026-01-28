"""
Supplier Portal - Supply Chain Integration

LegoMCP World-Class Manufacturing System v5.0
Phase 22: Supply Chain Integration

Supplier integration and management:
- Supplier scorecard
- Automated procurement
- Lead time prediction
- Supply risk assessment
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class Supplier:
    """Supplier master data."""
    supplier_id: str
    name: str
    code: str

    # Contact
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

    # Performance
    quality_score: float = 100.0  # Incoming quality %
    delivery_score: float = 100.0  # On-time delivery %
    responsiveness_score: float = 100.0  # Response time score
    cost_competitiveness: float = 100.0  # Price vs market %

    # Status
    is_approved: bool = True
    is_preferred: bool = False
    certification_date: Optional[date] = None

    @property
    def overall_score(self) -> float:
        """Calculate overall supplier score."""
        return (
            self.quality_score * 0.4 +
            self.delivery_score * 0.3 +
            self.responsiveness_score * 0.15 +
            self.cost_competitiveness * 0.15
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'supplier_id': self.supplier_id,
            'name': self.name,
            'code': self.code,
            'email': self.email,
            'quality_score': self.quality_score,
            'delivery_score': self.delivery_score,
            'overall_score': self.overall_score,
            'is_approved': self.is_approved,
            'is_preferred': self.is_preferred,
        }


@dataclass
class SupplyRisk:
    """Supply chain risk assessment."""
    risk_id: str
    supplier_id: str
    risk_type: str  # financial, geographic, capacity, quality, single_source
    severity: str  # low, medium, high, critical
    probability: float  # 0-1
    impact_description: str = ""
    mitigation_plan: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'risk_id': self.risk_id,
            'supplier_id': self.supplier_id,
            'risk_type': self.risk_type,
            'severity': self.severity,
            'probability': self.probability,
            'impact_description': self.impact_description,
            'mitigation_plan': self.mitigation_plan,
        }


class SupplierPortalService:
    """
    Supplier Portal Service.

    Manages supplier relationships and procurement.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._suppliers: Dict[str, Supplier] = {}
        self._risks: Dict[str, List[SupplyRisk]] = {}

    def add_supplier(
        self,
        name: str,
        code: str,
        email: Optional[str] = None,
    ) -> Supplier:
        """Add a new supplier."""
        supplier = Supplier(
            supplier_id=str(uuid4()),
            name=name,
            code=code,
            email=email,
        )
        self._suppliers[supplier.supplier_id] = supplier
        logger.info(f"Added supplier: {name}")
        return supplier

    def update_scorecard(
        self,
        supplier_id: str,
        quality: Optional[float] = None,
        delivery: Optional[float] = None,
        responsiveness: Optional[float] = None,
        cost: Optional[float] = None,
    ) -> Optional[Supplier]:
        """Update supplier scorecard."""
        supplier = self._suppliers.get(supplier_id)
        if not supplier:
            return None

        if quality is not None:
            supplier.quality_score = quality
        if delivery is not None:
            supplier.delivery_score = delivery
        if responsiveness is not None:
            supplier.responsiveness_score = responsiveness
        if cost is not None:
            supplier.cost_competitiveness = cost

        return supplier

    def add_risk(
        self,
        supplier_id: str,
        risk_type: str,
        severity: str,
        probability: float,
        impact: str = "",
        mitigation: str = "",
    ) -> SupplyRisk:
        """Add a supply risk."""
        risk = SupplyRisk(
            risk_id=str(uuid4()),
            supplier_id=supplier_id,
            risk_type=risk_type,
            severity=severity,
            probability=probability,
            impact_description=impact,
            mitigation_plan=mitigation,
        )

        if supplier_id not in self._risks:
            self._risks[supplier_id] = []
        self._risks[supplier_id].append(risk)

        return risk

    def get_supplier(self, supplier_id: str) -> Optional[Supplier]:
        """Get supplier by ID."""
        return self._suppliers.get(supplier_id)

    def get_preferred_suppliers(self) -> List[Supplier]:
        """Get all preferred suppliers."""
        return [s for s in self._suppliers.values() if s.is_preferred]

    def get_supplier_risks(self, supplier_id: str) -> List[SupplyRisk]:
        """Get risks for a supplier."""
        return self._risks.get(supplier_id, [])

    def assess_supply_risk(self) -> Dict[str, Any]:
        """Assess overall supply chain risk."""
        high_risk = []
        for supplier_id, risks in self._risks.items():
            for risk in risks:
                if risk.severity in ['high', 'critical']:
                    high_risk.append({
                        'supplier': self._suppliers.get(supplier_id, {}).name if supplier_id in self._suppliers else 'Unknown',
                        'risk': risk.to_dict(),
                    })

        return {
            'total_suppliers': len(self._suppliers),
            'suppliers_with_risks': len(self._risks),
            'high_risk_count': len(high_risk),
            'high_risks': high_risk,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get supplier portal summary."""
        suppliers = list(self._suppliers.values())
        avg_score = sum(s.overall_score for s in suppliers) / len(suppliers) if suppliers else 0

        return {
            'total_suppliers': len(suppliers),
            'approved_suppliers': sum(1 for s in suppliers if s.is_approved),
            'preferred_suppliers': sum(1 for s in suppliers if s.is_preferred),
            'average_score': avg_score,
        }
