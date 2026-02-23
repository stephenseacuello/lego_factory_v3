"""
QFD Model - Quality Function Deployment (House of Quality)

LegoMCP World-Class Manufacturing System v5.0
Phase 11: QFD / House of Quality

Translates customer requirements to engineering characteristics:
- Voice of Customer capture
- Engineering characteristics definition
- Relationship matrix
- Competitive analysis
- Technical targets
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class RelationshipStrength(int, Enum):
    """Strength of relationship between requirement and characteristic."""
    NONE = 0
    WEAK = 1
    MODERATE = 3
    STRONG = 9


class Direction(str, Enum):
    """Optimization direction for characteristics."""
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"
    TARGET = "target"


class KanoCategory(str, Enum):
    """Kano model categorization."""
    MUST_BE = "must_be"  # Basic expectations
    ONE_DIMENSIONAL = "one_dimensional"  # Linear satisfaction
    ATTRACTIVE = "attractive"  # Delight features
    INDIFFERENT = "indifferent"  # No impact
    REVERSE = "reverse"  # Causes dissatisfaction


@dataclass
class CustomerRequirement:
    """A customer requirement (What)."""
    requirement_id: str
    requirement_text: str
    importance: int = 5  # 1-10
    kano_category: KanoCategory = KanoCategory.ONE_DIMENSIONAL

    # Competitive ratings (1-5)
    our_rating: float = 3.0
    competitor_a_rating: float = 3.0
    competitor_b_rating: float = 3.0

    # Improvement ratio
    target_rating: float = 4.0
    improvement_ratio: float = 1.0
    sales_point: float = 1.0  # 1.0, 1.2, 1.5

    # Calculated weight
    raw_weight: float = 0.0
    relative_weight_percent: float = 0.0

    def __post_init__(self):
        if not self.requirement_id:
            self.requirement_id = str(uuid4())
        self._calculate_weights()

    def _calculate_weights(self) -> None:
        """Calculate requirement weights."""
        if self.our_rating > 0:
            self.improvement_ratio = self.target_rating / self.our_rating
        self.raw_weight = self.importance * self.improvement_ratio * self.sales_point

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'requirement_id': self.requirement_id,
            'requirement_text': self.requirement_text,
            'importance': self.importance,
            'kano_category': self.kano_category.value,
            'our_rating': self.our_rating,
            'competitor_a_rating': self.competitor_a_rating,
            'competitor_b_rating': self.competitor_b_rating,
            'target_rating': self.target_rating,
            'improvement_ratio': self.improvement_ratio,
            'sales_point': self.sales_point,
            'raw_weight': self.raw_weight,
            'relative_weight_percent': self.relative_weight_percent,
        }


@dataclass
class EngineeringCharacteristic:
    """An engineering characteristic (How)."""
    characteristic_id: str
    characteristic_name: str
    unit_of_measure: str = ""
    direction: Direction = Direction.TARGET

    # Current and target values
    current_value: Optional[float] = None
    target_value: Optional[float] = None
    tolerance: Optional[float] = None

    # Competitive values
    competitor_a_value: Optional[float] = None
    competitor_b_value: Optional[float] = None

    # Technical difficulty (1-5)
    technical_difficulty: int = 3

    # Calculated importance
    absolute_importance: float = 0.0
    relative_importance_percent: float = 0.0

    # Roof correlations
    correlations: Dict[str, int] = field(default_factory=dict)  # char_id -> strength

    def __post_init__(self):
        if not self.characteristic_id:
            self.characteristic_id = str(uuid4())

    def is_meeting_target(self) -> bool:
        """Check if current value meets target."""
        if self.current_value is None or self.target_value is None:
            return False

        if self.direction == Direction.MAXIMIZE:
            return self.current_value >= self.target_value
        elif self.direction == Direction.MINIMIZE:
            return self.current_value <= self.target_value
        else:  # TARGET
            if self.tolerance:
                return abs(self.current_value - self.target_value) <= self.tolerance
            return self.current_value == self.target_value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'characteristic_id': self.characteristic_id,
            'characteristic_name': self.characteristic_name,
            'unit_of_measure': self.unit_of_measure,
            'direction': self.direction.value,
            'current_value': self.current_value,
            'target_value': self.target_value,
            'tolerance': self.tolerance,
            'technical_difficulty': self.technical_difficulty,
            'absolute_importance': self.absolute_importance,
            'relative_importance_percent': self.relative_importance_percent,
        }


@dataclass
class QFDRelationship:
    """Relationship between requirement and characteristic."""
    requirement_id: str
    characteristic_id: str
    strength: RelationshipStrength = RelationshipStrength.NONE

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'requirement_id': self.requirement_id,
            'characteristic_id': self.characteristic_id,
            'strength': self.strength.value,
        }


@dataclass
class HouseOfQuality:
    """Complete House of Quality (QFD Matrix)."""
    hoq_id: str
    name: str
    part_id: Optional[str] = None
    description: str = ""

    # What (Customer Requirements)
    customer_requirements: List[CustomerRequirement] = field(default_factory=list)

    # How (Engineering Characteristics)
    engineering_characteristics: List[EngineeringCharacteristic] = field(default_factory=list)

    # Relationships
    relationships: List[QFDRelationship] = field(default_factory=list)

    # Status
    status: str = "draft"  # draft, review, approved, active

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.hoq_id:
            self.hoq_id = str(uuid4())

    def add_requirement(self, req: CustomerRequirement) -> None:
        """Add a customer requirement."""
        self.customer_requirements.append(req)
        self._recalculate()

    def add_characteristic(self, char: EngineeringCharacteristic) -> None:
        """Add an engineering characteristic."""
        self.engineering_characteristics.append(char)
        self._recalculate()

    def set_relationship(
        self,
        requirement_id: str,
        characteristic_id: str,
        strength: RelationshipStrength,
    ) -> None:
        """Set relationship strength."""
        # Remove existing if any
        self.relationships = [
            r for r in self.relationships
            if not (r.requirement_id == requirement_id and
                    r.characteristic_id == characteristic_id)
        ]

        if strength != RelationshipStrength.NONE:
            self.relationships.append(QFDRelationship(
                requirement_id=requirement_id,
                characteristic_id=characteristic_id,
                strength=strength,
            ))

        self._recalculate()

    def _recalculate(self) -> None:
        """Recalculate all derived values."""
        # Calculate relative weights for requirements
        total_raw = sum(r.raw_weight for r in self.customer_requirements)
        if total_raw > 0:
            for req in self.customer_requirements:
                req.relative_weight_percent = (req.raw_weight / total_raw) * 100

        # Calculate importance for characteristics
        for char in self.engineering_characteristics:
            importance = 0.0
            for rel in self.relationships:
                if rel.characteristic_id == char.characteristic_id:
                    # Find corresponding requirement
                    for req in self.customer_requirements:
                        if req.requirement_id == rel.requirement_id:
                            importance += req.relative_weight_percent * rel.strength.value
                            break
            char.absolute_importance = importance

        # Calculate relative importance for characteristics
        total_importance = sum(c.absolute_importance for c in self.engineering_characteristics)
        if total_importance > 0:
            for char in self.engineering_characteristics:
                char.relative_importance_percent = (
                    char.absolute_importance / total_importance
                ) * 100

        self.updated_at = datetime.utcnow()

    def get_relationship_matrix(self) -> List[List[int]]:
        """Get the relationship matrix as 2D array."""
        matrix = []
        for req in self.customer_requirements:
            row = []
            for char in self.engineering_characteristics:
                strength = RelationshipStrength.NONE
                for rel in self.relationships:
                    if (rel.requirement_id == req.requirement_id and
                            rel.characteristic_id == char.characteristic_id):
                        strength = rel.strength
                        break
                row.append(strength.value)
            matrix.append(row)
        return matrix

    def get_priority_characteristics(self, top_n: int = 5) -> List[EngineeringCharacteristic]:
        """Get top priority characteristics by importance."""
        sorted_chars = sorted(
            self.engineering_characteristics,
            key=lambda c: c.relative_importance_percent,
            reverse=True,
        )
        return sorted_chars[:top_n]

    def get_unmet_requirements(self) -> List[CustomerRequirement]:
        """Get requirements not meeting target."""
        return [
            req for req in self.customer_requirements
            if req.our_rating < req.target_rating
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'hoq_id': self.hoq_id,
            'name': self.name,
            'part_id': self.part_id,
            'description': self.description,
            'customer_requirements': [r.to_dict() for r in self.customer_requirements],
            'engineering_characteristics': [c.to_dict() for c in self.engineering_characteristics],
            'relationships': [r.to_dict() for r in self.relationships],
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


# LEGO-specific QFD templates
LEGO_REQUIREMENTS = [
    {"text": "Brick should click firmly", "importance": 9, "kano": "must_be"},
    {"text": "Brick should release without damage", "importance": 8, "kano": "must_be"},
    {"text": "Consistent color across pieces", "importance": 7, "kano": "one_dimensional"},
    {"text": "Smooth surface finish", "importance": 6, "kano": "one_dimensional"},
    {"text": "Accurate stud alignment", "importance": 9, "kano": "must_be"},
    {"text": "Durable under repeated use", "importance": 8, "kano": "must_be"},
    {"text": "Compatible with official LEGO", "importance": 10, "kano": "must_be"},
]

LEGO_CHARACTERISTICS = [
    {"name": "Stud diameter", "unit": "mm", "target": 4.8, "direction": "target", "tolerance": 0.02},
    {"name": "Stud height", "unit": "mm", "target": 1.8, "direction": "target", "tolerance": 0.02},
    {"name": "Clutch power", "unit": "N", "target": 2.0, "direction": "target", "tolerance": 1.0},
    {"name": "Surface roughness", "unit": "Ra", "target": 1.6, "direction": "minimize"},
    {"name": "Color delta E", "unit": "dE", "target": 2.0, "direction": "minimize"},
    {"name": "Wall thickness", "unit": "mm", "target": 1.6, "direction": "target", "tolerance": 0.02},
]
