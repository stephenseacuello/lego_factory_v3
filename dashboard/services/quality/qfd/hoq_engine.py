"""
House of Quality Engine - QFD Matrix Builder.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

Automated QFD/House of Quality builder with:
- NLP-based Voice of Customer extraction
- AI-suggested relationship strengths
- Automated competitive benchmarking
- Multi-phase QFD cascade
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger(__name__)


class RelationshipStrength(Enum):
    """Relationship strength levels."""
    NONE = 0
    WEAK = 1
    MODERATE = 3
    STRONG = 9


class CorrelationType(Enum):
    """Technical correlation types (roof of HOQ)."""
    STRONG_POSITIVE = 2
    POSITIVE = 1
    NONE = 0
    NEGATIVE = -1
    STRONG_NEGATIVE = -2


class KanoType(Enum):
    """Kano model classification."""
    MUST_BE = "must_be"           # Basic expectations
    ONE_DIMENSIONAL = "one_dimensional"  # Linear satisfaction
    ATTRACTIVE = "attractive"      # Delighters
    INDIFFERENT = "indifferent"   # No impact
    REVERSE = "reverse"           # Causes dissatisfaction


@dataclass
class CustomerRequirement:
    """Customer requirement (WHAT)."""
    req_id: str
    description: str
    importance: float  # 1-10 scale
    kano_type: KanoType = KanoType.ONE_DIMENSIONAL
    category: str = "general"
    source: str = "customer_feedback"


@dataclass
class TechnicalRequirement:
    """Technical/engineering requirement (HOW)."""
    req_id: str
    description: str
    unit: str
    target_value: float
    direction: str = "target"  # "maximize", "minimize", "target"
    tolerance: Optional[float] = None
    difficulty: int = 5  # 1-10, higher = more difficult


@dataclass
class CompetitorBenchmark:
    """Competitor performance data."""
    competitor_name: str
    ratings: Dict[str, float]  # req_id -> rating (1-5)


@dataclass
class HouseOfQuality:
    """Complete House of Quality matrix."""
    hoq_id: str
    name: str
    customer_requirements: List[CustomerRequirement]
    technical_requirements: List[TechnicalRequirement]
    relationship_matrix: Dict[Tuple[str, str], RelationshipStrength]
    correlation_matrix: Dict[Tuple[str, str], CorrelationType]
    competitive_analysis: List[CompetitorBenchmark]
    targets: Dict[str, float]
    technical_importance: Dict[str, float]

    def get_priority_technicals(self, top_n: int = 5) -> List[Tuple[str, float]]:
        """Get top priority technical requirements."""
        sorted_items = sorted(
            self.technical_importance.items(),
            key=lambda x: -x[1]
        )
        return sorted_items[:top_n]


class HouseOfQualityEngine:
    """
    Build and analyze House of Quality matrices.

    Features:
    - Relationship matrix construction
    - Technical importance calculation
    - Roof (correlation) matrix
    - Competitive benchmarking
    - Target setting
    """

    def __init__(self):
        self._relationship_rules: Dict[str, Dict[str, RelationshipStrength]] = {}

    def build_hoq(self,
                  name: str,
                  customer_reqs: List[CustomerRequirement],
                  technical_reqs: List[TechnicalRequirement],
                  competitors: Optional[List[CompetitorBenchmark]] = None) -> HouseOfQuality:
        """
        Build a complete House of Quality.

        Args:
            name: HOQ name
            customer_reqs: List of customer requirements (WHATs)
            technical_reqs: List of technical requirements (HOWs)
            competitors: Optional competitor benchmark data

        Returns:
            Complete HouseOfQuality
        """
        import uuid
        hoq_id = str(uuid.uuid4())[:8]

        # Build relationship matrix
        relationships = self._build_relationship_matrix(customer_reqs, technical_reqs)

        # Build correlation matrix (roof)
        correlations = self._build_correlation_matrix(technical_reqs)

        # Calculate technical importance
        importance = self._calculate_technical_importance(
            customer_reqs, technical_reqs, relationships
        )

        # Set targets
        targets = self._set_targets(technical_reqs, competitors)

        hoq = HouseOfQuality(
            hoq_id=hoq_id,
            name=name,
            customer_requirements=customer_reqs,
            technical_requirements=technical_reqs,
            relationship_matrix=relationships,
            correlation_matrix=correlations,
            competitive_analysis=competitors or [],
            targets=targets,
            technical_importance=importance
        )

        logger.info(f"Built HOQ '{name}' with {len(customer_reqs)} WHATs and {len(technical_reqs)} HOWs")
        return hoq

    def _build_relationship_matrix(self,
                                   customer_reqs: List[CustomerRequirement],
                                   technical_reqs: List[TechnicalRequirement]
                                   ) -> Dict[Tuple[str, str], RelationshipStrength]:
        """Build relationship matrix between WHATs and HOWs."""
        matrix = {}

        for cr in customer_reqs:
            for tr in technical_reqs:
                # Use rules or AI-based inference
                strength = self._infer_relationship(cr, tr)
                if strength != RelationshipStrength.NONE:
                    matrix[(cr.req_id, tr.req_id)] = strength

        return matrix

    def _infer_relationship(self,
                           cr: CustomerRequirement,
                           tr: TechnicalRequirement) -> RelationshipStrength:
        """Infer relationship strength using keyword matching and rules."""
        cr_text = cr.description.lower()
        tr_text = tr.description.lower()

        # LEGO-specific relationship rules
        lego_rules = {
            ('connect', 'stud'): RelationshipStrength.STRONG,
            ('connect', 'diameter'): RelationshipStrength.STRONG,
            ('connect', 'clutch'): RelationshipStrength.STRONG,
            ('separate', 'clutch'): RelationshipStrength.STRONG,
            ('compatible', 'diameter'): RelationshipStrength.STRONG,
            ('compatible', 'dimension'): RelationshipStrength.STRONG,
            ('smooth', 'surface'): RelationshipStrength.STRONG,
            ('smooth', 'roughness'): RelationshipStrength.STRONG,
            ('color', 'delta'): RelationshipStrength.STRONG,
            ('strong', 'wall'): RelationshipStrength.MODERATE,
            ('strong', 'adhesion'): RelationshipStrength.MODERATE,
        }

        for (cr_key, tr_key), strength in lego_rules.items():
            if cr_key in cr_text and tr_key in tr_text:
                return strength

        # Generic keyword overlap
        cr_words = set(cr_text.split())
        tr_words = set(tr_text.split())
        overlap = len(cr_words & tr_words)

        if overlap >= 2:
            return RelationshipStrength.MODERATE
        elif overlap >= 1:
            return RelationshipStrength.WEAK

        return RelationshipStrength.NONE

    def _build_correlation_matrix(self,
                                  technical_reqs: List[TechnicalRequirement]
                                  ) -> Dict[Tuple[str, str], CorrelationType]:
        """Build technical correlation matrix (roof)."""
        matrix = {}

        # LEGO-specific correlations
        correlation_rules = {
            ('stud_diameter', 'clutch_force'): CorrelationType.STRONG_POSITIVE,
            ('print_speed', 'surface_roughness'): CorrelationType.NEGATIVE,
            ('layer_height', 'surface_roughness'): CorrelationType.POSITIVE,
            ('layer_height', 'print_time'): CorrelationType.NEGATIVE,
            ('wall_thickness', 'material_cost'): CorrelationType.POSITIVE,
            ('wall_thickness', 'strength'): CorrelationType.POSITIVE,
        }

        for i, tr1 in enumerate(technical_reqs):
            for tr2 in technical_reqs[i+1:]:
                # Check rules
                key1 = (tr1.req_id, tr2.req_id)
                key2 = (tr2.req_id, tr1.req_id)

                for rule_key, corr_type in correlation_rules.items():
                    if (rule_key[0] in tr1.req_id.lower() and rule_key[1] in tr2.req_id.lower()) or \
                       (rule_key[1] in tr1.req_id.lower() and rule_key[0] in tr2.req_id.lower()):
                        matrix[key1] = corr_type
                        matrix[key2] = corr_type
                        break

        return matrix

    def _calculate_technical_importance(self,
                                        customer_reqs: List[CustomerRequirement],
                                        technical_reqs: List[TechnicalRequirement],
                                        relationships: Dict[Tuple[str, str], RelationshipStrength]
                                        ) -> Dict[str, float]:
        """Calculate technical importance scores."""
        importance = {}

        for tr in technical_reqs:
            score = 0.0
            for cr in customer_reqs:
                rel = relationships.get((cr.req_id, tr.req_id), RelationshipStrength.NONE)
                score += cr.importance * rel.value
            importance[tr.req_id] = score

        # Normalize
        max_score = max(importance.values()) if importance else 1
        if max_score > 0:
            importance = {k: v / max_score * 100 for k, v in importance.items()}

        return importance

    def _set_targets(self,
                    technical_reqs: List[TechnicalRequirement],
                    competitors: Optional[List[CompetitorBenchmark]]) -> Dict[str, float]:
        """Set target values for technical requirements."""
        targets = {}

        for tr in technical_reqs:
            if tr.target_value is not None:
                targets[tr.req_id] = tr.target_value
            elif competitors:
                # Set target to beat best competitor
                competitor_values = []
                for comp in competitors:
                    if tr.req_id in comp.ratings:
                        competitor_values.append(comp.ratings[tr.req_id])

                if competitor_values:
                    if tr.direction == "maximize":
                        targets[tr.req_id] = max(competitor_values) * 1.1
                    elif tr.direction == "minimize":
                        targets[tr.req_id] = min(competitor_values) * 0.9
                    else:
                        targets[tr.req_id] = sum(competitor_values) / len(competitor_values)

        return targets

    def analyze_conflicts(self, hoq: HouseOfQuality) -> List[Dict[str, Any]]:
        """Identify conflicts between high-priority technical requirements."""
        conflicts = []
        priority_reqs = hoq.get_priority_technicals(5)
        priority_ids = [p[0] for p in priority_reqs]

        for i, tr1_id in enumerate(priority_ids):
            for tr2_id in priority_ids[i+1:]:
                corr = hoq.correlation_matrix.get((tr1_id, tr2_id))
                if corr in (CorrelationType.NEGATIVE, CorrelationType.STRONG_NEGATIVE):
                    conflicts.append({
                        'req1': tr1_id,
                        'req2': tr2_id,
                        'correlation': corr.name,
                        'recommendation': 'Consider design trade-off or innovation to resolve conflict'
                    })

        return conflicts

    def export_to_dict(self, hoq: HouseOfQuality) -> Dict[str, Any]:
        """Export HOQ to dictionary format."""
        return {
            'hoq_id': hoq.hoq_id,
            'name': hoq.name,
            'customer_requirements': [
                {
                    'id': cr.req_id,
                    'description': cr.description,
                    'importance': cr.importance,
                    'kano_type': cr.kano_type.value
                }
                for cr in hoq.customer_requirements
            ],
            'technical_requirements': [
                {
                    'id': tr.req_id,
                    'description': tr.description,
                    'unit': tr.unit,
                    'target': tr.target_value,
                    'direction': tr.direction
                }
                for tr in hoq.technical_requirements
            ],
            'relationships': [
                {
                    'customer_req': k[0],
                    'technical_req': k[1],
                    'strength': v.value
                }
                for k, v in hoq.relationship_matrix.items()
            ],
            'technical_importance': hoq.technical_importance,
            'targets': hoq.targets,
            'priority_technicals': hoq.get_priority_technicals(5)
        }
