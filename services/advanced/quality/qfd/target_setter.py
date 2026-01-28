"""
Target Setter - Optimal target derivation for technical requirements.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI, Explainability, FMEA & HOQ
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Callable
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class TargetStrategy(Enum):
    """Target setting strategies."""
    MATCH_BEST = "match_best"  # Match best competitor
    EXCEED_BEST = "exceed_best"  # Exceed best competitor
    CUSTOMER_DRIVEN = "customer_driven"  # Based on customer importance
    CAPABILITY_BASED = "capability_based"  # Based on our capability
    BALANCED = "balanced"  # Balance all factors


class TargetConfidence(Enum):
    """Confidence level in target."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class TargetRecommendation:
    """Target recommendation for a technical requirement."""
    requirement_id: str
    requirement_name: str
    current_value: Optional[float]
    recommended_target: float
    unit: str
    confidence: TargetConfidence
    strategy_used: TargetStrategy
    rationale: str
    stretch_target: Optional[float] = None
    minimum_acceptable: Optional[float] = None
    improvement_required: float = 0.0
    priority_rank: int = 0


@dataclass
class TargetSet:
    """Complete set of targets."""
    targets: List[TargetRecommendation]
    strategy: TargetStrategy
    overall_feasibility: float
    total_improvement_effort: float
    created_at: datetime = field(default_factory=datetime.utcnow)


class TargetSetter:
    """
    Optimal target derivation for QFD.

    Features:
    - Multi-strategy target setting
    - Feasibility assessment
    - Improvement prioritization
    - Trade-off handling
    """

    def __init__(self):
        self._technical_reqs: Dict[str, Dict] = {}
        self._customer_reqs: Dict[str, Dict] = {}
        self._relationship_matrix: Dict[Tuple[str, str], int] = {}
        self._competitive_data: Dict[str, Dict] = {}
        self._capability_data: Dict[str, Dict] = {}
        self._correlation_matrix: Dict[Tuple[str, str], int] = {}

    def set_technical_requirements(self,
                                   requirements: List[Dict[str, Any]]) -> None:
        """Set technical requirements."""
        self._technical_reqs = {r['id']: r for r in requirements}

    def set_customer_requirements(self,
                                  requirements: List[Dict[str, Any]]) -> None:
        """Set customer requirements with importance ratings."""
        self._customer_reqs = {r['id']: r for r in requirements}

    def set_relationship_matrix(self,
                               relationships: Dict[Tuple[str, str], int]) -> None:
        """Set relationship matrix (customer x technical)."""
        self._relationship_matrix = relationships

    def set_competitive_data(self,
                            data: Dict[str, Dict[str, float]]) -> None:
        """
        Set competitive benchmark data.

        Args:
            data: {tech_req_id: {competitor_id: value, ...}, ...}
        """
        self._competitive_data = data

    def set_capability_data(self,
                           data: Dict[str, Dict[str, float]]) -> None:
        """
        Set our current capability data.

        Args:
            data: {tech_req_id: {current: value, best_achievable: value, cost_factor: value}, ...}
        """
        self._capability_data = data

    def set_correlation_matrix(self,
                              correlations: Dict[Tuple[str, str], int]) -> None:
        """Set correlation matrix for trade-off handling."""
        self._correlation_matrix = correlations

    def derive_targets(self,
                      strategy: TargetStrategy = TargetStrategy.BALANCED) -> TargetSet:
        """
        Derive optimal targets for all technical requirements.

        Args:
            strategy: Target setting strategy to use

        Returns:
            Complete target set
        """
        targets = []
        improvement_efforts = []

        # Calculate importance weight for each technical requirement
        tech_importance = self._calculate_technical_importance()

        for req_id, req_data in self._technical_reqs.items():
            target = self._derive_single_target(req_id, req_data, strategy, tech_importance)
            targets.append(target)
            improvement_efforts.append(target.improvement_required)

        # Rank by priority
        targets.sort(key=lambda t: t.improvement_required * tech_importance.get(t.requirement_id, 1),
                    reverse=True)
        for i, target in enumerate(targets):
            target.priority_rank = i + 1

        # Calculate overall feasibility
        feasibility = self._calculate_overall_feasibility(targets)

        return TargetSet(
            targets=targets,
            strategy=strategy,
            overall_feasibility=feasibility,
            total_improvement_effort=sum(improvement_efforts)
        )

    def _calculate_technical_importance(self) -> Dict[str, float]:
        """Calculate importance weight for each technical requirement."""
        importance = {tech_id: 0.0 for tech_id in self._technical_reqs}

        for (cust_id, tech_id), strength in self._relationship_matrix.items():
            cust_data = self._customer_reqs.get(cust_id, {})
            cust_importance = cust_data.get('importance', 1)
            importance[tech_id] += cust_importance * strength

        # Normalize
        max_imp = max(importance.values()) if importance else 1
        if max_imp > 0:
            importance = {k: v / max_imp for k, v in importance.items()}

        return importance

    def _derive_single_target(self,
                             req_id: str,
                             req_data: Dict,
                             strategy: TargetStrategy,
                             importance: Dict[str, float]) -> TargetRecommendation:
        """Derive target for single technical requirement."""
        current_target = req_data.get('target', 0)
        unit = req_data.get('unit', '')
        name = req_data.get('name', req_id)
        optimization = req_data.get('optimization', 'target')

        # Get competitive data
        comp_data = self._competitive_data.get(req_id, {})
        best_competitor = max(comp_data.values()) if comp_data else current_target

        # Get capability data
        cap_data = self._capability_data.get(req_id, {})
        current_value = cap_data.get('current', current_target)
        best_achievable = cap_data.get('best_achievable', current_target * 1.2)

        # Determine target based on strategy
        if strategy == TargetStrategy.MATCH_BEST:
            recommended = best_competitor
            rationale = f"Match best competitor value of {best_competitor}"
        elif strategy == TargetStrategy.EXCEED_BEST:
            recommended = best_competitor * 1.1  # 10% better
            rationale = f"Exceed best competitor by 10%"
        elif strategy == TargetStrategy.CUSTOMER_DRIVEN:
            # Weight by customer importance
            imp = importance.get(req_id, 0.5)
            recommended = current_target + (best_competitor - current_target) * imp
            rationale = f"Customer-weighted target (importance: {imp:.2f})"
        elif strategy == TargetStrategy.CAPABILITY_BASED:
            recommended = best_achievable
            rationale = f"Based on achievable capability"
        else:  # BALANCED
            # Weighted average of all factors
            weights = [0.3, 0.3, 0.2, 0.2]
            values = [
                best_competitor,
                best_achievable,
                current_target * 1.1,
                current_target + (best_competitor - current_target) * importance.get(req_id, 0.5)
            ]
            recommended = sum(w * v for w, v in zip(weights, values))
            rationale = "Balanced optimization across competitive, capability, and customer factors"

        # Handle optimization direction
        if optimization == 'minimize':
            # For minimize objectives, lower is better
            if best_competitor < current_target:
                recommended = best_competitor * 0.9  # 10% better (lower)
        elif optimization == 'maximize':
            # For maximize objectives, higher is better
            pass  # Default logic works

        # Calculate improvement required
        if optimization == 'minimize':
            improvement = max(0, current_value - recommended) / (current_value + 0.0001)
        else:
            improvement = max(0, recommended - current_value) / (recommended + 0.0001)

        # Calculate stretch and minimum targets
        stretch_target = recommended * 1.15 if optimization != 'minimize' else recommended * 0.85
        min_acceptable = current_target  # At least match current spec

        # Determine confidence
        confidence = self._determine_confidence(req_id, recommended, cap_data, comp_data)

        return TargetRecommendation(
            requirement_id=req_id,
            requirement_name=name,
            current_value=current_value,
            recommended_target=round(recommended, 4),
            unit=unit,
            confidence=confidence,
            strategy_used=strategy,
            rationale=rationale,
            stretch_target=round(stretch_target, 4),
            minimum_acceptable=round(min_acceptable, 4),
            improvement_required=improvement
        )

    def _determine_confidence(self,
                             req_id: str,
                             target: float,
                             capability: Dict,
                             competitive: Dict) -> TargetConfidence:
        """Determine confidence level in target."""
        confidence_score = 0.5  # Base

        # More competitive data = higher confidence
        if len(competitive) >= 3:
            confidence_score += 0.2
        elif len(competitive) >= 1:
            confidence_score += 0.1

        # Capability data available
        if capability:
            confidence_score += 0.15
            # Target within achievable range
            best_achievable = capability.get('best_achievable', float('inf'))
            if target <= best_achievable:
                confidence_score += 0.15

        if confidence_score >= 0.8:
            return TargetConfidence.HIGH
        elif confidence_score >= 0.5:
            return TargetConfidence.MEDIUM
        else:
            return TargetConfidence.LOW

    def _calculate_overall_feasibility(self,
                                       targets: List[TargetRecommendation]) -> float:
        """Calculate overall feasibility of target set."""
        if not targets:
            return 1.0

        # Check for conflicting targets
        conflict_penalty = 0
        for (req1, req2), correlation in self._correlation_matrix.items():
            if correlation < 0:  # Negative correlation = potential conflict
                # Check if both have significant improvement
                t1 = next((t for t in targets if t.requirement_id == req1), None)
                t2 = next((t for t in targets if t.requirement_id == req2), None)
                if t1 and t2:
                    if t1.improvement_required > 0.1 and t2.improvement_required > 0.1:
                        conflict_penalty += abs(correlation) * 0.1

        # Average confidence
        avg_confidence = np.mean([t.confidence.value for t in targets]) / 3

        # Average improvement feasibility (less improvement = more feasible)
        avg_improvement = np.mean([t.improvement_required for t in targets])
        improvement_feasibility = 1 - min(1, avg_improvement)

        feasibility = (avg_confidence * 0.4 + improvement_feasibility * 0.4 - conflict_penalty * 0.2)
        return max(0, min(1, feasibility))

    def optimize_with_constraints(self,
                                 constraints: List[Dict[str, Any]],
                                 objective: str = 'maximize_customer_satisfaction') -> TargetSet:
        """
        Optimize targets with constraints.

        Args:
            constraints: List of {type, requirement_id, value, ...}
            objective: Optimization objective

        Returns:
            Constrained target set
        """
        # Start with balanced targets
        base_targets = self.derive_targets(TargetStrategy.BALANCED)

        # Apply constraints
        constrained_targets = []
        for target in base_targets.targets:
            new_target = self._apply_constraints(target, constraints)
            constrained_targets.append(new_target)

        return TargetSet(
            targets=constrained_targets,
            strategy=TargetStrategy.BALANCED,
            overall_feasibility=self._calculate_overall_feasibility(constrained_targets),
            total_improvement_effort=sum(t.improvement_required for t in constrained_targets)
        )

    def _apply_constraints(self,
                          target: TargetRecommendation,
                          constraints: List[Dict]) -> TargetRecommendation:
        """Apply constraints to target."""
        for constraint in constraints:
            if constraint.get('requirement_id') == target.requirement_id:
                constraint_type = constraint.get('type')
                value = constraint.get('value')

                if constraint_type == 'max':
                    target.recommended_target = min(target.recommended_target, value)
                elif constraint_type == 'min':
                    target.recommended_target = max(target.recommended_target, value)
                elif constraint_type == 'fixed':
                    target.recommended_target = value

        return target

    def generate_target_report(self, target_set: TargetSet) -> str:
        """Generate target setting report."""
        lines = ["# Target Setting Report\n"]
        lines.append(f"Generated: {target_set.created_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Strategy: {target_set.strategy.value}")
        lines.append(f"Overall Feasibility: {target_set.overall_feasibility:.1%}\n")

        lines.append("## Target Summary\n")
        lines.append("| Requirement | Current | Target | Unit | Improvement | Priority |")
        lines.append("|-------------|---------|--------|------|-------------|----------|")

        for target in sorted(target_set.targets, key=lambda t: t.priority_rank):
            current = f"{target.current_value:.2f}" if target.current_value else "N/A"
            lines.append(
                f"| {target.requirement_name} | {current} | "
                f"{target.recommended_target:.2f} | {target.unit} | "
                f"{target.improvement_required:.1%} | {target.priority_rank} |"
            )

        lines.append("\n## Top Priorities\n")
        for target in target_set.targets[:5]:
            lines.append(f"**{target.priority_rank}. {target.requirement_name}**")
            lines.append(f"- Current: {target.current_value} → Target: {target.recommended_target} {target.unit}")
            lines.append(f"- Confidence: {target.confidence.name}")
            lines.append(f"- Rationale: {target.rationale}\n")

        return "\n".join(lines)

    def export_targets(self, target_set: TargetSet) -> Dict[str, Any]:
        """Export targets to dictionary."""
        return {
            'strategy': target_set.strategy.value,
            'feasibility': target_set.overall_feasibility,
            'total_effort': target_set.total_improvement_effort,
            'targets': [
                {
                    'id': t.requirement_id,
                    'name': t.requirement_name,
                    'current': t.current_value,
                    'target': t.recommended_target,
                    'stretch': t.stretch_target,
                    'minimum': t.minimum_acceptable,
                    'unit': t.unit,
                    'confidence': t.confidence.name,
                    'improvement': t.improvement_required,
                    'priority': t.priority_rank,
                    'rationale': t.rationale
                }
                for t in target_set.targets
            ]
        }
