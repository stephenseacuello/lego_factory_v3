"""
Extended BOM Model - Enhanced Bill of Materials

LegoMCP World-Class Manufacturing System v5.0
Phase 9: Alternative Routings & Enhanced BOM

Enhanced BOM with quality and traceability attributes:
- Functional role classification
- Quality criticality levels
- Lot and serial tracking requirements
- Risk sensitivity
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class FunctionalRole(str, Enum):
    """Functional role of a component in the assembly."""
    STRUCTURAL = "structural"  # Load-bearing, strength-critical
    COSMETIC = "cosmetic"  # Appearance-only
    FUNCTIONAL = "functional"  # Required for function
    CONNECTOR = "connector"  # Joins other components
    FILLER = "filler"  # Space-filling, non-critical
    SAFETY = "safety"  # Safety-critical


class QualityCriticality(str, Enum):
    """Quality criticality classification."""
    CTQ = "ctq"  # Critical to Quality - must meet spec
    MAJOR = "major"  # Important, deviation needs review
    MINOR = "minor"  # Minor impact, wider tolerance OK
    COSMETIC = "cosmetic"  # Visual only


class RiskSensitivity(str, Enum):
    """Risk sensitivity level."""
    HIGH = "high"  # Failure causes major impact
    MEDIUM = "medium"  # Failure causes moderate impact
    LOW = "low"  # Failure causes minor impact


class TrackingLevel(str, Enum):
    """Inventory tracking granularity."""
    NONE = "none"  # No tracking
    LOT = "lot"  # Lot/batch tracking
    SERIAL = "serial"  # Individual serial numbers


@dataclass
class BOMComponentTag:
    """Quality and traceability tags for BOM components."""
    component_id: str
    part_id: str

    # Functional classification
    functional_role: FunctionalRole = FunctionalRole.FUNCTIONAL
    quality_criticality: QualityCriticality = QualityCriticality.MINOR
    risk_sensitivity: RiskSensitivity = RiskSensitivity.LOW

    # Tracking requirements
    tracking_level: TrackingLevel = TrackingLevel.NONE
    requires_lot_tracking: bool = False
    requires_serial_tracking: bool = False

    # Quality requirements
    requires_incoming_inspection: bool = False
    inspection_sampling_percent: float = 0.0
    requires_certificate: bool = False

    # Supplier requirements
    approved_suppliers: List[str] = field(default_factory=list)
    single_source: bool = False
    supplier_quality_required: bool = False

    # Regulatory
    requires_compliance_doc: bool = False
    compliance_standards: List[str] = field(default_factory=list)

    # LEGO-specific
    stud_compatibility_critical: bool = False
    color_match_critical: bool = False
    clutch_power_critical: bool = False

    def __post_init__(self):
        if not self.component_id:
            self.component_id = str(uuid4())
        # Auto-set tracking based on criticality
        if self.quality_criticality == QualityCriticality.CTQ:
            self.requires_lot_tracking = True
        if self.risk_sensitivity == RiskSensitivity.HIGH:
            self.requires_incoming_inspection = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'component_id': self.component_id,
            'part_id': self.part_id,
            'functional_role': self.functional_role.value,
            'quality_criticality': self.quality_criticality.value,
            'risk_sensitivity': self.risk_sensitivity.value,
            'tracking_level': self.tracking_level.value,
            'requires_lot_tracking': self.requires_lot_tracking,
            'requires_serial_tracking': self.requires_serial_tracking,
            'requires_incoming_inspection': self.requires_incoming_inspection,
            'inspection_sampling_percent': self.inspection_sampling_percent,
            'approved_suppliers': self.approved_suppliers,
            'stud_compatibility_critical': self.stud_compatibility_critical,
            'color_match_critical': self.color_match_critical,
            'clutch_power_critical': self.clutch_power_critical,
        }


@dataclass
class EnhancedBOMComponent:
    """Enhanced BOM component with full attributes."""
    component_id: str
    parent_part_id: str
    child_part_id: str
    child_part_name: str = ""
    quantity: float = 1.0
    unit_of_measure: str = "EA"

    # Position in assembly
    sequence: int = 0
    find_number: str = ""  # Assembly drawing find number

    # Effectivity
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None

    # Alternates
    is_phantom: bool = False  # Pass-through in explosion
    substitute_part_ids: List[str] = field(default_factory=list)

    # Quality tags
    tags: Optional[BOMComponentTag] = None

    # Scrap and yield
    scrap_percent: float = 0.0
    expected_yield: float = 100.0

    # Cost
    standard_cost: float = 0.0

    # Notes
    notes: str = ""
    engineering_notes: str = ""

    def __post_init__(self):
        if not self.component_id:
            self.component_id = str(uuid4())

    def gross_quantity(self, parent_qty: float = 1.0) -> float:
        """Calculate gross quantity including scrap allowance."""
        net = self.quantity * parent_qty
        scrap_allowance = net * (self.scrap_percent / 100)
        return net + scrap_allowance

    def is_effective(self, check_date: Optional[datetime] = None) -> bool:
        """Check if component is effective at date."""
        if check_date is None:
            check_date = datetime.utcnow()
        if self.effective_from and check_date < self.effective_from:
            return False
        if self.effective_to and check_date > self.effective_to:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'component_id': self.component_id,
            'parent_part_id': self.parent_part_id,
            'child_part_id': self.child_part_id,
            'child_part_name': self.child_part_name,
            'quantity': self.quantity,
            'unit_of_measure': self.unit_of_measure,
            'sequence': self.sequence,
            'find_number': self.find_number,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'is_phantom': self.is_phantom,
            'substitute_part_ids': self.substitute_part_ids,
            'tags': self.tags.to_dict() if self.tags else None,
            'scrap_percent': self.scrap_percent,
            'standard_cost': self.standard_cost,
            'notes': self.notes,
        }


@dataclass
class EnhancedBOM:
    """Enhanced Bill of Materials with full features."""
    bom_id: str
    part_id: str
    part_name: str = ""
    bom_type: str = "manufacturing"  # engineering, manufacturing, planning
    revision: str = "A"

    # Components
    components: List[EnhancedBOMComponent] = field(default_factory=list)

    # Status
    status: str = "draft"  # draft, pending, approved, released, obsolete
    is_active: bool = True

    # Effectivity
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None

    # Approval
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    # Totals
    total_components: int = 0
    total_standard_cost: float = 0.0
    ctq_component_count: int = 0

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.bom_id:
            self.bom_id = str(uuid4())
        self._recalculate()

    def _recalculate(self) -> None:
        """Recalculate totals."""
        self.total_components = len(self.components)
        self.total_standard_cost = sum(c.standard_cost * c.quantity for c in self.components)
        self.ctq_component_count = sum(
            1 for c in self.components
            if c.tags and c.tags.quality_criticality == QualityCriticality.CTQ
        )

    def add_component(self, component: EnhancedBOMComponent) -> None:
        """Add a component to the BOM."""
        self.components.append(component)
        self.components.sort(key=lambda x: x.sequence)
        self._recalculate()
        self.updated_at = datetime.utcnow()

    def remove_component(self, component_id: str) -> bool:
        """Remove a component from the BOM."""
        for i, comp in enumerate(self.components):
            if comp.component_id == component_id:
                self.components.pop(i)
                self._recalculate()
                self.updated_at = datetime.utcnow()
                return True
        return False

    def get_component(self, child_part_id: str) -> Optional[EnhancedBOMComponent]:
        """Get component by child part ID."""
        for comp in self.components:
            if comp.child_part_id == child_part_id:
                return comp
        return None

    def get_ctq_components(self) -> List[EnhancedBOMComponent]:
        """Get all CTQ components."""
        return [
            c for c in self.components
            if c.tags and c.tags.quality_criticality == QualityCriticality.CTQ
        ]

    def get_tracked_components(self) -> List[EnhancedBOMComponent]:
        """Get all components requiring lot/serial tracking."""
        return [
            c for c in self.components
            if c.tags and (c.tags.requires_lot_tracking or c.tags.requires_serial_tracking)
        ]

    def explode(self, quantity: float = 1.0, effective_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Single-level BOM explosion.

        Returns list of components with calculated quantities.
        """
        result = []
        for comp in self.components:
            if not comp.is_effective(effective_date):
                continue

            result.append({
                'part_id': comp.child_part_id,
                'part_name': comp.child_part_name,
                'quantity': comp.gross_quantity(quantity),
                'tags': comp.tags.to_dict() if comp.tags else None,
            })

        return result

    def approve(self, approved_by: str) -> None:
        """Approve the BOM."""
        self.status = 'approved'
        self.approved_by = approved_by
        self.approved_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def release(self) -> None:
        """Release the BOM for production."""
        if self.status == 'approved':
            self.status = 'released'
            self.is_active = True
            self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'bom_id': self.bom_id,
            'part_id': self.part_id,
            'part_name': self.part_name,
            'bom_type': self.bom_type,
            'revision': self.revision,
            'components': [c.to_dict() for c in self.components],
            'status': self.status,
            'is_active': self.is_active,
            'total_components': self.total_components,
            'total_standard_cost': self.total_standard_cost,
            'ctq_component_count': self.ctq_component_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class EnhancedBOMRepository:
    """Repository for enhanced BOM persistence."""

    def __init__(self):
        self._boms: Dict[str, EnhancedBOM] = {}
        self._by_part: Dict[str, List[str]] = {}

    def save(self, bom: EnhancedBOM) -> None:
        """Save or update a BOM."""
        self._boms[bom.bom_id] = bom

        if bom.part_id not in self._by_part:
            self._by_part[bom.part_id] = []
        if bom.bom_id not in self._by_part[bom.part_id]:
            self._by_part[bom.part_id].append(bom.bom_id)

    def get(self, bom_id: str) -> Optional[EnhancedBOM]:
        """Get BOM by ID."""
        return self._boms.get(bom_id)

    def get_by_part(self, part_id: str) -> List[EnhancedBOM]:
        """Get all BOMs for a part."""
        bom_ids = self._by_part.get(part_id, [])
        return [self._boms[bid] for bid in bom_ids if bid in self._boms]

    def get_active(self, part_id: str) -> Optional[EnhancedBOM]:
        """Get active BOM for a part."""
        for bom in self.get_by_part(part_id):
            if bom.is_active and bom.status == 'released':
                return bom
        return None

    def delete(self, bom_id: str) -> bool:
        """Delete a BOM."""
        if bom_id in self._boms:
            bom = self._boms.pop(bom_id)
            if bom.part_id in self._by_part:
                if bom_id in self._by_part[bom.part_id]:
                    self._by_part[bom.part_id].remove(bom_id)
            return True
        return False

    def count(self) -> int:
        """Get total BOM count."""
        return len(self._boms)
