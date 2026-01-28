"""
Technical Requirements - Engineering characteristics management.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI, Explainability, FMEA & HOQ
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RequirementType(Enum):
    """Types of technical requirements."""
    DIMENSIONAL = "dimensional"
    MECHANICAL = "mechanical"
    THERMAL = "thermal"
    MATERIAL = "material"
    PROCESS = "process"
    AESTHETIC = "aesthetic"
    FUNCTIONAL = "functional"
    DURABILITY = "durability"
    SAFETY = "safety"


class OptimizationDirection(Enum):
    """Direction of optimization."""
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"
    TARGET = "target"
    NOMINAL = "nominal"


class DifficultyLevel(Enum):
    """Technical difficulty to achieve."""
    EASY = 1
    MODERATE = 2
    DIFFICULT = 3
    VERY_DIFFICULT = 4
    BREAKTHROUGH = 5


@dataclass
class TechnicalRequirement:
    """Technical/engineering requirement definition."""
    req_id: str
    name: str
    description: str
    requirement_type: RequirementType
    unit: str
    target_value: float
    tolerance: Optional[Tuple[float, float]] = None  # (min, max)
    optimization: OptimizationDirection = OptimizationDirection.TARGET
    difficulty: DifficultyLevel = DifficultyLevel.MODERATE
    weight: float = 1.0  # Relative importance
    measurable: bool = True
    measurement_method: str = ""
    related_standards: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RequirementDerivation:
    """How technical requirement was derived."""
    tech_req_id: str
    source_customer_reqs: List[str]
    derivation_rationale: str
    confidence: float


class TechnicalRequirementsManager:
    """
    Manager for technical/engineering requirements.

    Features:
    - LEGO-specific requirements library
    - Derivation from customer requirements
    - Tolerance analysis
    - Conflict detection
    """

    def __init__(self):
        self._requirements: Dict[str, TechnicalRequirement] = {}
        self._derivations: Dict[str, RequirementDerivation] = {}
        self._load_lego_requirements()

    def _load_lego_requirements(self) -> None:
        """Load LEGO brick standard requirements."""
        # Dimensional requirements
        self.add_requirement(TechnicalRequirement(
            req_id="TR-001",
            name="Stud Diameter",
            description="Outer diameter of brick studs",
            requirement_type=RequirementType.DIMENSIONAL,
            unit="mm",
            target_value=4.8,
            tolerance=(4.78, 4.82),
            optimization=OptimizationDirection.TARGET,
            difficulty=DifficultyLevel.DIFFICULT,
            weight=1.5,
            measurement_method="Caliper or CMM measurement",
            related_standards=["LEGO tolerance spec", "ISO 286"]
        ))

        self.add_requirement(TechnicalRequirement(
            req_id="TR-002",
            name="Stud Height",
            description="Height of brick studs above top surface",
            requirement_type=RequirementType.DIMENSIONAL,
            unit="mm",
            target_value=1.7,
            tolerance=(1.68, 1.72),
            optimization=OptimizationDirection.TARGET,
            difficulty=DifficultyLevel.MODERATE,
            weight=1.2,
            measurement_method="Height gauge measurement"
        ))

        self.add_requirement(TechnicalRequirement(
            req_id="TR-003",
            name="Brick Height (1 unit)",
            description="Total height of 1-unit brick including studs",
            requirement_type=RequirementType.DIMENSIONAL,
            unit="mm",
            target_value=9.6,
            tolerance=(9.58, 9.62),
            optimization=OptimizationDirection.TARGET,
            difficulty=DifficultyLevel.MODERATE,
            weight=1.3,
            measurement_method="Height gauge measurement"
        ))

        self.add_requirement(TechnicalRequirement(
            req_id="TR-004",
            name="Anti-Stud Inner Diameter",
            description="Inner diameter of anti-stud tubes",
            requirement_type=RequirementType.DIMENSIONAL,
            unit="mm",
            target_value=4.8,
            tolerance=(4.78, 4.82),
            optimization=OptimizationDirection.TARGET,
            difficulty=DifficultyLevel.DIFFICULT,
            weight=1.4,
            measurement_method="Bore gauge or CMM"
        ))

        self.add_requirement(TechnicalRequirement(
            req_id="TR-005",
            name="Pitch (stud spacing)",
            description="Center-to-center distance between studs",
            requirement_type=RequirementType.DIMENSIONAL,
            unit="mm",
            target_value=8.0,
            tolerance=(7.99, 8.01),
            optimization=OptimizationDirection.TARGET,
            difficulty=DifficultyLevel.MODERATE,
            weight=1.5,
            measurement_method="Coordinate measurement"
        ))

        # Mechanical requirements
        self.add_requirement(TechnicalRequirement(
            req_id="TR-006",
            name="Clutch Force",
            description="Force required to separate connected bricks",
            requirement_type=RequirementType.MECHANICAL,
            unit="N",
            target_value=2.0,
            tolerance=(1.0, 3.0),
            optimization=OptimizationDirection.TARGET,
            difficulty=DifficultyLevel.DIFFICULT,
            weight=1.8,
            measurement_method="Force gauge pull test"
        ))

        self.add_requirement(TechnicalRequirement(
            req_id="TR-007",
            name="Layer Adhesion Strength",
            description="Interlayer bond strength for FDM prints",
            requirement_type=RequirementType.MECHANICAL,
            unit="MPa",
            target_value=25.0,
            tolerance=(20.0, None),
            optimization=OptimizationDirection.MAXIMIZE,
            difficulty=DifficultyLevel.DIFFICULT,
            weight=1.5,
            measurement_method="Tensile test perpendicular to layers"
        ))

        self.add_requirement(TechnicalRequirement(
            req_id="TR-008",
            name="Stud Break Force",
            description="Force required to break a stud",
            requirement_type=RequirementType.MECHANICAL,
            unit="N",
            target_value=50.0,
            tolerance=(40.0, None),
            optimization=OptimizationDirection.MAXIMIZE,
            difficulty=DifficultyLevel.MODERATE,
            weight=1.6,
            measurement_method="Shear test on individual stud"
        ))

        # Surface requirements
        self.add_requirement(TechnicalRequirement(
            req_id="TR-009",
            name="Surface Roughness Ra",
            description="Average surface roughness",
            requirement_type=RequirementType.AESTHETIC,
            unit="μm",
            target_value=0.8,
            tolerance=(None, 1.6),
            optimization=OptimizationDirection.MINIMIZE,
            difficulty=DifficultyLevel.MODERATE,
            weight=1.0,
            measurement_method="Surface profilometer"
        ))

        self.add_requirement(TechnicalRequirement(
            req_id="TR-010",
            name="Color Accuracy (Delta E)",
            description="Color difference from target",
            requirement_type=RequirementType.AESTHETIC,
            unit="ΔE",
            target_value=1.0,
            tolerance=(None, 2.0),
            optimization=OptimizationDirection.MINIMIZE,
            difficulty=DifficultyLevel.MODERATE,
            weight=0.8,
            measurement_method="Colorimeter measurement"
        ))

        # Material requirements
        self.add_requirement(TechnicalRequirement(
            req_id="TR-011",
            name="Material Modulus",
            description="Young's modulus of material",
            requirement_type=RequirementType.MATERIAL,
            unit="GPa",
            target_value=2.5,
            tolerance=(2.0, 3.0),
            optimization=OptimizationDirection.TARGET,
            difficulty=DifficultyLevel.EASY,
            weight=1.0,
            measurement_method="Tensile test",
            related_standards=["ASTM D638"]
        ))

        # Safety requirements
        self.add_requirement(TechnicalRequirement(
            req_id="TR-012",
            name="Small Parts Safety",
            description="No parts that can detach below minimum size",
            requirement_type=RequirementType.SAFETY,
            unit="mm",
            target_value=31.7,  # Small parts cylinder diameter
            tolerance=(31.7, None),
            optimization=OptimizationDirection.MAXIMIZE,
            difficulty=DifficultyLevel.MODERATE,
            weight=2.0,  # High importance
            measurement_method="Small parts cylinder test",
            related_standards=["ASTM F963", "EN 71-1"]
        ))

        logger.info(f"Loaded {len(self._requirements)} LEGO technical requirements")

    def add_requirement(self, req: TechnicalRequirement) -> None:
        """Add technical requirement."""
        self._requirements[req.req_id] = req

    def get_requirement(self, req_id: str) -> Optional[TechnicalRequirement]:
        """Get requirement by ID."""
        return self._requirements.get(req_id)

    def get_by_type(self, req_type: RequirementType) -> List[TechnicalRequirement]:
        """Get requirements by type."""
        return [r for r in self._requirements.values() if r.requirement_type == req_type]

    def derive_from_customer(self,
                            customer_req: str,
                            customer_req_id: str) -> List[TechnicalRequirement]:
        """
        Derive technical requirements from customer requirement.

        Args:
            customer_req: Customer requirement text
            customer_req_id: Customer requirement ID

        Returns:
            Related technical requirements
        """
        derived = []
        customer_lower = customer_req.lower()

        # Mapping rules
        mapping_rules = {
            ('connect', 'grip', 'clutch', 'hold', 'firm'): ['TR-006', 'TR-001', 'TR-004'],
            ('separate', 'apart', 'disconnect'): ['TR-006'],
            ('compatible', 'lego', 'fit', 'official'): ['TR-001', 'TR-002', 'TR-004', 'TR-005'],
            ('smooth', 'surface', 'feel'): ['TR-009'],
            ('color', 'accurate', 'match'): ['TR-010'],
            ('strong', 'break', 'durable'): ['TR-007', 'TR-008'],
            ('safe', 'child', 'children'): ['TR-012'],
            ('dimension', 'size', 'accurate'): ['TR-001', 'TR-002', 'TR-003', 'TR-005']
        }

        for keywords, req_ids in mapping_rules.items():
            if any(kw in customer_lower for kw in keywords):
                for req_id in req_ids:
                    req = self._requirements.get(req_id)
                    if req and req not in derived:
                        derived.append(req)

                        # Record derivation
                        if req_id not in self._derivations:
                            self._derivations[req_id] = RequirementDerivation(
                                tech_req_id=req_id,
                                source_customer_reqs=[customer_req_id],
                                derivation_rationale=f"Derived from: {customer_req}",
                                confidence=0.8
                            )
                        else:
                            if customer_req_id not in self._derivations[req_id].source_customer_reqs:
                                self._derivations[req_id].source_customer_reqs.append(customer_req_id)

        return derived

    def check_conflicts(self) -> List[Dict[str, Any]]:
        """Check for conflicts between requirements."""
        conflicts = []

        # Check for potentially conflicting requirements
        reqs = list(self._requirements.values())
        for i, req1 in enumerate(reqs):
            for req2 in reqs[i+1:]:
                conflict = self._check_pair_conflict(req1, req2)
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    def _check_pair_conflict(self,
                            req1: TechnicalRequirement,
                            req2: TechnicalRequirement) -> Optional[Dict[str, Any]]:
        """Check if two requirements conflict."""
        # Known conflict pairs
        conflict_rules = [
            # Clutch force vs ease of separation
            (['TR-006'], ['TR-006'], 'self_conflict',
             "Clutch force must be balanced - too high makes separation difficult"),
            # Surface roughness affects clutch
            (['TR-009'], ['TR-006'], 'influence',
             "Surface roughness affects clutch force"),
            # Speed vs quality trade-offs in process
            (['TR-007'], ['TR-009'], 'tradeoff',
             "Layer adhesion and surface finish may require opposite temperature settings")
        ]

        for req1_ids, req2_ids, conflict_type, description in conflict_rules:
            if (req1.req_id in req1_ids and req2.req_id in req2_ids) or \
               (req2.req_id in req1_ids and req1.req_id in req2_ids):
                return {
                    'type': conflict_type,
                    'requirements': [req1.req_id, req2.req_id],
                    'description': description
                }

        return None

    def validate_target(self,
                       req_id: str,
                       actual_value: float) -> Dict[str, Any]:
        """Validate actual value against requirement."""
        req = self._requirements.get(req_id)
        if not req:
            return {'valid': False, 'error': 'Requirement not found'}

        result = {
            'req_id': req_id,
            'target': req.target_value,
            'actual': actual_value,
            'unit': req.unit,
            'valid': True,
            'margin': None
        }

        if req.tolerance:
            min_val, max_val = req.tolerance
            if min_val is not None and actual_value < min_val:
                result['valid'] = False
                result['deviation'] = actual_value - min_val
            elif max_val is not None and actual_value > max_val:
                result['valid'] = False
                result['deviation'] = actual_value - max_val
            else:
                # Calculate margin from limits
                if min_val is not None:
                    margin_low = actual_value - min_val
                else:
                    margin_low = float('inf')
                if max_val is not None:
                    margin_high = max_val - actual_value
                else:
                    margin_high = float('inf')
                result['margin'] = min(margin_low, margin_high)

        return result

    def get_all_requirements(self) -> List[TechnicalRequirement]:
        """Get all requirements."""
        return list(self._requirements.values())

    def get_derivation(self, req_id: str) -> Optional[RequirementDerivation]:
        """Get derivation info for requirement."""
        return self._derivations.get(req_id)

    def export_to_dict(self) -> Dict[str, Any]:
        """Export requirements to dictionary."""
        return {
            'requirements': [
                {
                    'req_id': r.req_id,
                    'name': r.name,
                    'description': r.description,
                    'type': r.requirement_type.value,
                    'unit': r.unit,
                    'target': r.target_value,
                    'tolerance': r.tolerance,
                    'optimization': r.optimization.value,
                    'difficulty': r.difficulty.value,
                    'weight': r.weight
                }
                for r in self._requirements.values()
            ],
            'derivations': [
                {
                    'tech_req_id': d.tech_req_id,
                    'source_customer_reqs': d.source_customer_reqs,
                    'rationale': d.derivation_rationale,
                    'confidence': d.confidence
                }
                for d in self._derivations.values()
            ]
        }
