"""
Correlation Matrix - Technical requirement correlations (HOQ Roof).

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI, Explainability, FMEA & HOQ
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set
from enum import IntEnum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class CorrelationType(IntEnum):
    """Correlation types for technical requirements."""
    STRONG_NEGATIVE = -2
    NEGATIVE = -1
    NONE = 0
    POSITIVE = 1
    STRONG_POSITIVE = 2


@dataclass
class Correlation:
    """Correlation between two technical requirements."""
    req1_id: str
    req2_id: str
    correlation_type: CorrelationType
    confidence: float = 0.8
    explanation: str = ""
    auto_detected: bool = False


@dataclass
class TradeOff:
    """Trade-off between conflicting requirements."""
    requirements: List[str]
    correlation_type: CorrelationType
    impact: str
    suggested_resolution: str


class CorrelationMatrix:
    """
    QFD Correlation Matrix (HOWs vs HOWs) - The "Roof".

    Features:
    - Technical requirement inter-relationships
    - Trade-off identification
    - Synergy detection
    - Design guidance generation
    """

    def __init__(self):
        self._technical_reqs: Dict[str, Dict] = {}
        self._correlations: Dict[Tuple[str, str], Correlation] = {}
        self._known_correlations: Dict[Tuple[str, str], Tuple[CorrelationType, str]] = {}
        self._load_known_correlations()

    def _load_known_correlations(self) -> None:
        """Load known correlations for LEGO manufacturing."""
        # Format: (req1_prefix, req2_prefix) -> (correlation_type, explanation)
        self._known_correlations = {
            # Dimensional correlations
            ('TR-001', 'TR-004'): (CorrelationType.STRONG_POSITIVE,
                "Stud and anti-stud diameters must be precisely matched for clutch"),
            ('TR-001', 'TR-006'): (CorrelationType.STRONG_POSITIVE,
                "Stud diameter directly affects clutch force"),
            ('TR-004', 'TR-006'): (CorrelationType.STRONG_POSITIVE,
                "Anti-stud diameter directly affects clutch force"),
            ('TR-005', 'TR-001'): (CorrelationType.POSITIVE,
                "Pitch accuracy affects overall stud positioning"),

            # Surface vs function
            ('TR-009', 'TR-006'): (CorrelationType.POSITIVE,
                "Surface roughness affects friction and thus clutch force"),

            # Layer adhesion relationships
            ('TR-007', 'TR-008'): (CorrelationType.STRONG_POSITIVE,
                "Layer adhesion strength contributes to overall stud strength"),
            ('TR-007', 'TR-009'): (CorrelationType.NEGATIVE,
                "Higher temperature for adhesion may increase surface roughness"),

            # Trade-offs
            ('TR-006', 'TR-006'): (CorrelationType.NONE,
                "Clutch force is self-balancing - too high or low is problematic"),

            # Safety
            ('TR-012', 'TR-008'): (CorrelationType.POSITIVE,
                "Stronger studs reduce risk of small parts breaking off")
        }

    def set_technical_requirements(self,
                                   requirements: List[Dict[str, Any]]) -> None:
        """Set technical requirements."""
        self._technical_reqs = {r['id']: r for r in requirements}

    def set_correlation(self,
                       req1_id: str,
                       req2_id: str,
                       correlation_type: CorrelationType,
                       explanation: str = "") -> None:
        """Set correlation between two technical requirements."""
        # Normalize key order (always smaller ID first)
        key = tuple(sorted([req1_id, req2_id]))
        self._correlations[key] = Correlation(
            req1_id=key[0],
            req2_id=key[1],
            correlation_type=correlation_type,
            explanation=explanation,
            auto_detected=False
        )

    def get_correlation(self,
                       req1_id: str,
                       req2_id: str) -> Optional[Correlation]:
        """Get correlation between requirements."""
        key = tuple(sorted([req1_id, req2_id]))
        return self._correlations.get(key)

    def auto_detect_correlations(self) -> List[Correlation]:
        """Auto-detect correlations using known rules."""
        detected = []

        req_ids = list(self._technical_reqs.keys())

        for i, req1_id in enumerate(req_ids):
            for req2_id in req_ids[i+1:]:
                # Check known correlations
                for (known1, known2), (corr_type, explanation) in self._known_correlations.items():
                    if (req1_id.startswith(known1) and req2_id.startswith(known2)) or \
                       (req1_id.startswith(known2) and req2_id.startswith(known1)):
                        key = tuple(sorted([req1_id, req2_id]))
                        if key not in self._correlations:
                            corr = Correlation(
                                req1_id=key[0],
                                req2_id=key[1],
                                correlation_type=corr_type,
                                explanation=explanation,
                                confidence=0.85,
                                auto_detected=True
                            )
                            self._correlations[key] = corr
                            detected.append(corr)

        # Also detect based on requirement type similarity
        for i, req1_id in enumerate(req_ids):
            req1_data = self._technical_reqs[req1_id]
            for req2_id in req_ids[i+1:]:
                req2_data = self._technical_reqs[req2_id]
                key = tuple(sorted([req1_id, req2_id]))

                if key not in self._correlations:
                    # Same type requirements often correlate
                    if req1_data.get('type') == req2_data.get('type'):
                        corr = Correlation(
                            req1_id=key[0],
                            req2_id=key[1],
                            correlation_type=CorrelationType.POSITIVE,
                            explanation=f"Same requirement type: {req1_data.get('type')}",
                            confidence=0.5,
                            auto_detected=True
                        )
                        self._correlations[key] = corr
                        detected.append(corr)

        logger.info(f"Auto-detected {len(detected)} correlations")
        return detected

    def get_matrix_data(self) -> Dict[str, Any]:
        """Get matrix data for visualization."""
        req_ids = list(self._technical_reqs.keys())
        n = len(req_ids)

        # Build triangular matrix (roof shape)
        matrix = []
        for i, req1_id in enumerate(req_ids):
            row = []
            for j, req2_id in enumerate(req_ids):
                if j <= i:
                    # Below or on diagonal - empty
                    row.append(None)
                else:
                    corr = self.get_correlation(req1_id, req2_id)
                    row.append({
                        'value': corr.correlation_type.value if corr else 0,
                        'type': corr.correlation_type.name if corr else 'NONE',
                        'explanation': corr.explanation if corr else '',
                        'auto_detected': corr.auto_detected if corr else False
                    })
            matrix.append(row)

        headers = [
            {
                'id': req_id,
                'name': self._technical_reqs[req_id].get('name', req_id)
            }
            for req_id in req_ids
        ]

        return {
            'headers': headers,
            'matrix': matrix,
            'correlation_count': len(self._correlations)
        }

    def identify_trade_offs(self) -> List[TradeOff]:
        """Identify trade-offs (negative correlations)."""
        trade_offs = []

        for key, corr in self._correlations.items():
            if corr.correlation_type in [CorrelationType.NEGATIVE, CorrelationType.STRONG_NEGATIVE]:
                req1_name = self._technical_reqs.get(corr.req1_id, {}).get('name', corr.req1_id)
                req2_name = self._technical_reqs.get(corr.req2_id, {}).get('name', corr.req2_id)

                trade_offs.append(TradeOff(
                    requirements=[corr.req1_id, corr.req2_id],
                    correlation_type=corr.correlation_type,
                    impact=f"Improving {req1_name} may negatively impact {req2_name}",
                    suggested_resolution=self._suggest_resolution(corr)
                ))

        return trade_offs

    def _suggest_resolution(self, corr: Correlation) -> str:
        """Suggest resolution for trade-off."""
        suggestions = {
            ('TR-007', 'TR-009'): (
                "Use optimized print temperature profile: higher initial layers "
                "for adhesion, lower outer layers for surface quality"
            ),
            ('TR-006', 'TR-006'): (
                "Target clutch force within 1.5-2.5N range to balance "
                "connection strength and ease of separation"
            )
        }

        key = tuple(sorted([corr.req1_id, corr.req2_id]))
        if key in suggestions:
            return suggestions[key]

        return "Consider multi-objective optimization to balance requirements"

    def identify_synergies(self) -> List[Dict[str, Any]]:
        """Identify synergies (positive correlations)."""
        synergies = []

        for key, corr in self._correlations.items():
            if corr.correlation_type in [CorrelationType.POSITIVE, CorrelationType.STRONG_POSITIVE]:
                req1_name = self._technical_reqs.get(corr.req1_id, {}).get('name', corr.req1_id)
                req2_name = self._technical_reqs.get(corr.req2_id, {}).get('name', corr.req2_id)

                synergies.append({
                    'requirements': [corr.req1_id, corr.req2_id],
                    'requirement_names': [req1_name, req2_name],
                    'correlation_type': corr.correlation_type.name,
                    'benefit': f"Improving {req1_name} will also benefit {req2_name}",
                    'confidence': corr.confidence
                })

        return synergies

    def get_requirement_network(self) -> Dict[str, Any]:
        """Get correlation network for graph visualization."""
        nodes = [
            {
                'id': req_id,
                'name': req_data.get('name', req_id),
                'type': req_data.get('type', 'unknown')
            }
            for req_id, req_data in self._technical_reqs.items()
        ]

        edges = []
        for key, corr in self._correlations.items():
            if corr.correlation_type != CorrelationType.NONE:
                edges.append({
                    'source': corr.req1_id,
                    'target': corr.req2_id,
                    'value': corr.correlation_type.value,
                    'type': 'positive' if corr.correlation_type.value > 0 else 'negative',
                    'strength': abs(corr.correlation_type.value)
                })

        return {'nodes': nodes, 'edges': edges}

    def get_conflict_clusters(self) -> List[Set[str]]:
        """Find clusters of conflicting requirements."""
        # Build adjacency for negative correlations
        adjacency: Dict[str, Set[str]] = {req_id: set() for req_id in self._technical_reqs}

        for key, corr in self._correlations.items():
            if corr.correlation_type in [CorrelationType.NEGATIVE, CorrelationType.STRONG_NEGATIVE]:
                adjacency[corr.req1_id].add(corr.req2_id)
                adjacency[corr.req2_id].add(corr.req1_id)

        # Find connected components
        visited: Set[str] = set()
        clusters = []

        for req_id in self._technical_reqs:
            if req_id not in visited and adjacency[req_id]:
                # BFS to find cluster
                cluster: Set[str] = set()
                queue = [req_id]
                while queue:
                    current = queue.pop(0)
                    if current not in visited:
                        visited.add(current)
                        cluster.add(current)
                        queue.extend(adjacency[current] - visited)
                if len(cluster) > 1:
                    clusters.append(cluster)

        return clusters

    def analyze_design_freedom(self) -> Dict[str, Any]:
        """Analyze design freedom based on correlations."""
        results = {}

        for req_id in self._technical_reqs:
            positive_count = 0
            negative_count = 0
            total_strength = 0

            for key, corr in self._correlations.items():
                if req_id in key:
                    if corr.correlation_type.value > 0:
                        positive_count += 1
                    elif corr.correlation_type.value < 0:
                        negative_count += 1
                    total_strength += abs(corr.correlation_type.value)

            # Higher coupling = lower design freedom
            coupling = total_strength / (len(self._technical_reqs) - 1) if len(self._technical_reqs) > 1 else 0
            design_freedom = 1 - coupling / 2  # Normalize to 0-1

            results[req_id] = {
                'name': self._technical_reqs[req_id].get('name', req_id),
                'positive_correlations': positive_count,
                'negative_correlations': negative_count,
                'coupling': coupling,
                'design_freedom': max(0, design_freedom)
            }

        return results

    def export_summary(self) -> str:
        """Export correlation summary."""
        trade_offs = self.identify_trade_offs()
        synergies = self.identify_synergies()

        lines = ["# Correlation Matrix Summary\n"]

        lines.append(f"Total correlations: {len(self._correlations)}")
        lines.append(f"Trade-offs identified: {len(trade_offs)}")
        lines.append(f"Synergies identified: {len(synergies)}\n")

        if trade_offs:
            lines.append("## Trade-offs (Conflicts)\n")
            for to in trade_offs:
                lines.append(f"- {to.impact}")
                lines.append(f"  Resolution: {to.suggested_resolution}\n")

        if synergies:
            lines.append("## Synergies\n")
            for syn in synergies[:5]:  # Top 5
                lines.append(f"- {syn['benefit']}")

        return "\n".join(lines)
