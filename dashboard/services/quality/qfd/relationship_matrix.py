"""
Relationship Matrix - Customer-to-Technical requirement relationships.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI, Explainability, FMEA & HOQ
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import IntEnum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class RelationshipStrength(IntEnum):
    """Relationship strength levels."""
    NONE = 0
    WEAK = 1
    MODERATE = 3
    STRONG = 9


@dataclass
class Relationship:
    """Single relationship between customer and technical requirement."""
    customer_req_id: str
    technical_req_id: str
    strength: RelationshipStrength
    confidence: float = 0.8
    notes: str = ""
    auto_detected: bool = False


@dataclass
class MatrixCell:
    """Cell in the relationship matrix."""
    row_id: str  # Customer requirement
    col_id: str  # Technical requirement
    value: int
    confidence: float
    notes: str = ""


class RelationshipMatrix:
    """
    QFD Relationship Matrix (WHATs vs HOWs).

    Features:
    - Manual and AI-assisted relationship scoring
    - Importance weight calculation
    - Relationship analysis
    - Matrix visualization data
    """

    def __init__(self):
        self._customer_reqs: Dict[str, Dict] = {}  # id -> {name, importance, ...}
        self._technical_reqs: Dict[str, Dict] = {}  # id -> {name, unit, ...}
        self._relationships: Dict[Tuple[str, str], Relationship] = {}
        self._ml_model = None

    def set_customer_requirements(self,
                                  requirements: List[Dict[str, Any]]) -> None:
        """
        Set customer requirements (WHATs).

        Args:
            requirements: List of {id, name, importance, ...}
        """
        self._customer_reqs = {r['id']: r for r in requirements}
        logger.info(f"Set {len(requirements)} customer requirements")

    def set_technical_requirements(self,
                                   requirements: List[Dict[str, Any]]) -> None:
        """
        Set technical requirements (HOWs).

        Args:
            requirements: List of {id, name, unit, target, ...}
        """
        self._technical_reqs = {r['id']: r for r in requirements}
        logger.info(f"Set {len(requirements)} technical requirements")

    def set_relationship(self,
                        customer_id: str,
                        technical_id: str,
                        strength: RelationshipStrength,
                        notes: str = "") -> None:
        """Set relationship between customer and technical requirement."""
        key = (customer_id, technical_id)
        self._relationships[key] = Relationship(
            customer_req_id=customer_id,
            technical_req_id=technical_id,
            strength=strength,
            notes=notes,
            auto_detected=False
        )

    def get_relationship(self,
                        customer_id: str,
                        technical_id: str) -> Optional[Relationship]:
        """Get relationship between requirements."""
        return self._relationships.get((customer_id, technical_id))

    def auto_detect_relationships(self) -> List[Relationship]:
        """
        Automatically detect relationships using AI/rules.

        Returns:
            List of detected relationships
        """
        detected = []

        # Keyword-based relationship detection
        relationship_keywords = {
            # Customer keywords -> Technical requirement IDs
            'connect': [('TR-006', 9), ('TR-001', 3)],
            'grip': [('TR-006', 9)],
            'clutch': [('TR-006', 9), ('TR-001', 3), ('TR-004', 3)],
            'separate': [('TR-006', 9)],
            'apart': [('TR-006', 9)],
            'compatible': [('TR-001', 9), ('TR-004', 9), ('TR-005', 9)],
            'lego': [('TR-001', 9), ('TR-002', 9), ('TR-004', 9), ('TR-005', 9)],
            'fit': [('TR-001', 3), ('TR-005', 3)],
            'smooth': [('TR-009', 9)],
            'surface': [('TR-009', 9)],
            'color': [('TR-010', 9)],
            'accurate': [('TR-010', 3), ('TR-001', 3)],
            'strong': [('TR-007', 9), ('TR-008', 9)],
            'durable': [('TR-007', 3), ('TR-008', 3)],
            'break': [('TR-008', 9)],
            'safe': [('TR-012', 9)],
            'child': [('TR-012', 9)],
            'dimension': [('TR-001', 3), ('TR-002', 3), ('TR-003', 3), ('TR-005', 3)]
        }

        for cust_id, cust_data in self._customer_reqs.items():
            cust_name = cust_data.get('name', '').lower()

            for keyword, tech_mappings in relationship_keywords.items():
                if keyword in cust_name:
                    for tech_id, strength in tech_mappings:
                        if tech_id in self._technical_reqs:
                            key = (cust_id, tech_id)
                            if key not in self._relationships:
                                strength_enum = self._strength_to_enum(strength)
                                rel = Relationship(
                                    customer_req_id=cust_id,
                                    technical_req_id=tech_id,
                                    strength=strength_enum,
                                    confidence=0.7,
                                    notes=f"Auto-detected via keyword '{keyword}'",
                                    auto_detected=True
                                )
                                self._relationships[key] = rel
                                detected.append(rel)

        logger.info(f"Auto-detected {len(detected)} relationships")
        return detected

    def _strength_to_enum(self, value: int) -> RelationshipStrength:
        """Convert numeric strength to enum."""
        if value >= 9:
            return RelationshipStrength.STRONG
        elif value >= 3:
            return RelationshipStrength.MODERATE
        elif value >= 1:
            return RelationshipStrength.WEAK
        else:
            return RelationshipStrength.NONE

    def calculate_technical_importance(self) -> Dict[str, float]:
        """
        Calculate importance weight for each technical requirement.

        Returns:
            {tech_id: importance_weight}
        """
        importance = {tech_id: 0.0 for tech_id in self._technical_reqs}

        for (cust_id, tech_id), rel in self._relationships.items():
            cust_data = self._customer_reqs.get(cust_id, {})
            cust_importance = cust_data.get('importance', 1)
            importance[tech_id] += cust_importance * rel.strength.value

        # Normalize
        max_importance = max(importance.values()) if importance else 1
        if max_importance > 0:
            importance = {k: v / max_importance for k, v in importance.items()}

        return importance

    def get_matrix_data(self) -> Dict[str, Any]:
        """
        Get matrix data for visualization.

        Returns:
            Matrix data structure for UI
        """
        # Build matrix
        rows = []
        for cust_id, cust_data in self._customer_reqs.items():
            row = {
                'id': cust_id,
                'name': cust_data.get('name', cust_id),
                'importance': cust_data.get('importance', 1),
                'cells': []
            }
            for tech_id in self._technical_reqs:
                rel = self._relationships.get((cust_id, tech_id))
                row['cells'].append({
                    'tech_id': tech_id,
                    'value': rel.strength.value if rel else 0,
                    'confidence': rel.confidence if rel else 0,
                    'auto_detected': rel.auto_detected if rel else False
                })
            rows.append(row)

        # Column headers
        columns = [
            {
                'id': tech_id,
                'name': tech_data.get('name', tech_id),
                'unit': tech_data.get('unit', ''),
                'target': tech_data.get('target', None)
            }
            for tech_id, tech_data in self._technical_reqs.items()
        ]

        # Calculate importance
        importance = self.calculate_technical_importance()

        return {
            'rows': rows,
            'columns': columns,
            'importance': importance,
            'relationship_count': len(self._relationships)
        }

    def get_matrix_as_array(self) -> np.ndarray:
        """Get matrix as numpy array."""
        n_cust = len(self._customer_reqs)
        n_tech = len(self._technical_reqs)

        matrix = np.zeros((n_cust, n_tech))

        cust_ids = list(self._customer_reqs.keys())
        tech_ids = list(self._technical_reqs.keys())

        for i, cust_id in enumerate(cust_ids):
            for j, tech_id in enumerate(tech_ids):
                rel = self._relationships.get((cust_id, tech_id))
                if rel:
                    matrix[i, j] = rel.strength.value

        return matrix

    def analyze_coverage(self) -> Dict[str, Any]:
        """Analyze matrix coverage and quality."""
        total_cells = len(self._customer_reqs) * len(self._technical_reqs)
        filled_cells = len([r for r in self._relationships.values()
                          if r.strength != RelationshipStrength.NONE])

        # Customer requirements without strong relationships
        orphan_customers = []
        for cust_id in self._customer_reqs:
            max_strength = 0
            for tech_id in self._technical_reqs:
                rel = self._relationships.get((cust_id, tech_id))
                if rel:
                    max_strength = max(max_strength, rel.strength.value)
            if max_strength < 3:  # No moderate or strong relationships
                orphan_customers.append(cust_id)

        # Technical requirements not linked to any customer need
        orphan_technical = []
        for tech_id in self._technical_reqs:
            has_relationship = False
            for cust_id in self._customer_reqs:
                rel = self._relationships.get((cust_id, tech_id))
                if rel and rel.strength.value > 0:
                    has_relationship = True
                    break
            if not has_relationship:
                orphan_technical.append(tech_id)

        return {
            'total_cells': total_cells,
            'filled_cells': filled_cells,
            'coverage_percent': (filled_cells / total_cells * 100) if total_cells > 0 else 0,
            'auto_detected_count': sum(1 for r in self._relationships.values() if r.auto_detected),
            'orphan_customer_reqs': orphan_customers,
            'orphan_technical_reqs': orphan_technical,
            'average_confidence': np.mean([r.confidence for r in self._relationships.values()])
            if self._relationships else 0
        }

    def suggest_missing_relationships(self) -> List[Dict[str, Any]]:
        """Suggest potentially missing relationships."""
        suggestions = []

        # Find customer requirements without adequate technical coverage
        for cust_id, cust_data in self._customer_reqs.items():
            total_strength = sum(
                self._relationships.get((cust_id, tech_id), Relationship(
                    cust_id, tech_id, RelationshipStrength.NONE
                )).strength.value
                for tech_id in self._technical_reqs
            )

            if total_strength < 9:  # Low coverage
                suggestions.append({
                    'type': 'low_coverage',
                    'customer_req_id': cust_id,
                    'customer_req_name': cust_data.get('name'),
                    'current_strength_sum': total_strength,
                    'suggestion': 'Consider adding technical requirements to address this need'
                })

        return suggestions

    def export_to_csv(self) -> str:
        """Export matrix to CSV format."""
        tech_ids = list(self._technical_reqs.keys())

        # Header
        header = "Customer Requirement,Importance," + ",".join(tech_ids)
        rows = [header]

        for cust_id, cust_data in self._customer_reqs.items():
            values = [cust_data.get('name', cust_id), str(cust_data.get('importance', 1))]
            for tech_id in tech_ids:
                rel = self._relationships.get((cust_id, tech_id))
                values.append(str(rel.strength.value if rel else 0))
            rows.append(",".join(values))

        # Add importance row
        importance = self.calculate_technical_importance()
        imp_row = ["Technical Importance", ""] + [f"{importance.get(tid, 0):.2f}" for tid in tech_ids]
        rows.append(",".join(imp_row))

        return "\n".join(rows)
