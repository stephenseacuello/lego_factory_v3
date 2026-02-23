"""
Severity Calculator - AI-assisted severity scoring.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI, Explainability, FMEA & HOQ
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SafetyImpact(Enum):
    """Safety impact levels."""
    NONE = 0
    MINOR = 1
    MODERATE = 2
    SERIOUS = 3
    HAZARDOUS = 4
    CATASTROPHIC = 5


class FunctionalImpact(Enum):
    """Functional impact levels."""
    NONE = 0
    COSMETIC = 1
    MINOR_DEGRADATION = 2
    SIGNIFICANT_DEGRADATION = 3
    LOSS_OF_PRIMARY_FUNCTION = 4
    COMPLETE_FAILURE = 5


class CustomerImpact(Enum):
    """Customer/user impact levels."""
    NONE = 0
    BARELY_NOTICEABLE = 1
    SLIGHT_DISSATISFACTION = 2
    DISSATISFACTION = 3
    HIGH_DISSATISFACTION = 4
    EXTREME_DISSATISFACTION = 5


@dataclass
class EffectPropagation:
    """Propagated effect through system."""
    effect: str
    affected_components: List[str]
    severity_contribution: float
    propagation_path: List[str]


@dataclass
class SeverityAssessment:
    """Complete severity assessment."""
    failure_mode: str
    overall_severity: int  # 1-10
    safety_impact: SafetyImpact
    functional_impact: FunctionalImpact
    customer_impact: CustomerImpact
    lego_compatibility_impact: float  # 0-1
    propagated_effects: List[EffectPropagation]
    confidence: float
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SeverityCalculator:
    """
    AI-assisted severity scoring for FMEA.

    Features:
    - Multi-factor severity analysis
    - Effect propagation through system
    - LEGO-specific compatibility assessment
    - Safety impact evaluation
    """

    def __init__(self):
        self._component_graph: Dict[str, List[str]] = {}
        self._severity_rules: Dict[str, Dict] = {}
        self._load_default_rules()
        self._load_lego_component_graph()

    def _load_default_rules(self) -> None:
        """Load default severity scoring rules."""
        # Safety-related severity mappings
        self._severity_rules['safety'] = {
            SafetyImpact.NONE: 0,
            SafetyImpact.MINOR: 2,
            SafetyImpact.MODERATE: 4,
            SafetyImpact.SERIOUS: 7,
            SafetyImpact.HAZARDOUS: 9,
            SafetyImpact.CATASTROPHIC: 10
        }

        # Functional impact severity mappings
        self._severity_rules['functional'] = {
            FunctionalImpact.NONE: 0,
            FunctionalImpact.COSMETIC: 1,
            FunctionalImpact.MINOR_DEGRADATION: 3,
            FunctionalImpact.SIGNIFICANT_DEGRADATION: 5,
            FunctionalImpact.LOSS_OF_PRIMARY_FUNCTION: 7,
            FunctionalImpact.COMPLETE_FAILURE: 9
        }

        # Customer impact severity mappings
        self._severity_rules['customer'] = {
            CustomerImpact.NONE: 0,
            CustomerImpact.BARELY_NOTICEABLE: 1,
            CustomerImpact.SLIGHT_DISSATISFACTION: 3,
            CustomerImpact.DISSATISFACTION: 5,
            CustomerImpact.HIGH_DISSATISFACTION: 7,
            CustomerImpact.EXTREME_DISSATISFACTION: 9
        }

    def _load_lego_component_graph(self) -> None:
        """Load LEGO brick component dependency graph."""
        self._component_graph = {
            'stud': ['clutch_power', 'compatibility', 'assembly'],
            'tube': ['clutch_power', 'compatibility', 'structural_integrity'],
            'wall': ['structural_integrity', 'aesthetics'],
            'top_surface': ['stud', 'aesthetics'],
            'bottom_surface': ['tube', 'stability'],
            'clutch_power': ['build_stability', 'user_experience'],
            'compatibility': ['official_lego_interop', 'user_experience'],
            'structural_integrity': ['safety', 'durability'],
            'aesthetics': ['user_experience', 'brand_perception'],
            'build_stability': ['user_experience', 'play_value'],
            'safety': [],  # Terminal node
            'user_experience': [],  # Terminal node
            'durability': ['long_term_value'],
            'long_term_value': []  # Terminal node
        }

    def calculate_severity(self,
                          failure_mode: str,
                          effects: List[str],
                          affected_component: str,
                          context: Optional[Dict[str, Any]] = None) -> SeverityAssessment:
        """
        Calculate severity for a failure mode.

        Args:
            failure_mode: Name/description of failure mode
            effects: List of potential effects
            affected_component: Primary affected component
            context: Additional context (material, process, etc.)

        Returns:
            Complete severity assessment
        """
        context = context or {}

        # Assess individual impact dimensions
        safety_impact = self._assess_safety_impact(failure_mode, effects)
        functional_impact = self._assess_functional_impact(effects, affected_component)
        customer_impact = self._assess_customer_impact(effects)

        # Assess LEGO-specific compatibility
        lego_impact = self._assess_lego_compatibility(affected_component, effects)

        # Propagate effects through component graph
        propagated = self._propagate_effects(affected_component, effects)

        # Calculate overall severity
        severity_scores = [
            self._severity_rules['safety'][safety_impact],
            self._severity_rules['functional'][functional_impact],
            self._severity_rules['customer'][customer_impact]
        ]

        # Add propagated severity
        propagation_bonus = sum(p.severity_contribution for p in propagated) / 10

        # LEGO compatibility is critical
        lego_penalty = lego_impact * 3

        # Weighted combination
        base_severity = max(severity_scores)  # Use maximum as base
        weighted_severity = (
            0.4 * self._severity_rules['safety'][safety_impact] +
            0.3 * self._severity_rules['functional'][functional_impact] +
            0.2 * self._severity_rules['customer'][customer_impact] +
            0.1 * lego_penalty
        )

        # Take maximum of base and weighted
        overall = max(base_severity, weighted_severity)
        overall = min(10, max(1, round(overall + propagation_bonus)))

        # Generate reasoning
        reasoning = self._generate_reasoning(
            failure_mode, safety_impact, functional_impact,
            customer_impact, lego_impact, propagated
        )

        # Estimate confidence
        confidence = self._estimate_confidence(context, propagated)

        return SeverityAssessment(
            failure_mode=failure_mode,
            overall_severity=overall,
            safety_impact=safety_impact,
            functional_impact=functional_impact,
            customer_impact=customer_impact,
            lego_compatibility_impact=lego_impact,
            propagated_effects=propagated,
            confidence=confidence,
            reasoning=reasoning
        )

    def _assess_safety_impact(self,
                             failure_mode: str,
                             effects: List[str]) -> SafetyImpact:
        """Assess safety impact of failure mode."""
        safety_keywords = {
            SafetyImpact.CATASTROPHIC: ['fatal', 'death', 'life-threatening'],
            SafetyImpact.HAZARDOUS: ['injury', 'harm', 'hazard', 'choking'],
            SafetyImpact.SERIOUS: ['risk', 'dangerous', 'sharp'],
            SafetyImpact.MODERATE: ['bruise', 'pinch', 'minor injury'],
            SafetyImpact.MINOR: ['discomfort', 'irritation']
        }

        all_text = (failure_mode + ' ' + ' '.join(effects)).lower()

        for impact, keywords in safety_keywords.items():
            for kw in keywords:
                if kw in all_text:
                    return impact

        return SafetyImpact.NONE

    def _assess_functional_impact(self,
                                  effects: List[str],
                                  component: str) -> FunctionalImpact:
        """Assess functional impact."""
        functional_keywords = {
            FunctionalImpact.COMPLETE_FAILURE: ['unusable', 'cannot', 'fails completely', 'broken'],
            FunctionalImpact.LOSS_OF_PRIMARY_FUNCTION: ['does not connect', 'falls apart', 'no clutch'],
            FunctionalImpact.SIGNIFICANT_DEGRADATION: ['poor connection', 'weak', 'unstable'],
            FunctionalImpact.MINOR_DEGRADATION: ['reduced', 'slightly', 'minor issue'],
            FunctionalImpact.COSMETIC: ['appearance', 'visual', 'aesthetic', 'color']
        }

        effects_text = ' '.join(effects).lower()

        for impact, keywords in functional_keywords.items():
            for kw in keywords:
                if kw in effects_text:
                    return impact

        # Check component criticality
        critical_components = ['stud', 'tube', 'clutch_power']
        if component in critical_components:
            return FunctionalImpact.SIGNIFICANT_DEGRADATION

        return FunctionalImpact.MINOR_DEGRADATION

    def _assess_customer_impact(self, effects: List[str]) -> CustomerImpact:
        """Assess customer/user impact."""
        customer_keywords = {
            CustomerImpact.EXTREME_DISSATISFACTION: ['return', 'refund', 'unacceptable', 'angry'],
            CustomerImpact.HIGH_DISSATISFACTION: ['frustrated', 'disappointed', 'complaint'],
            CustomerImpact.DISSATISFACTION: ['annoyed', 'unhappy', 'dissatisfied'],
            CustomerImpact.SLIGHT_DISSATISFACTION: ['minor annoyance', 'slightly'],
            CustomerImpact.BARELY_NOTICEABLE: ['barely', 'hardly', 'minimal']
        }

        effects_text = ' '.join(effects).lower()

        for impact, keywords in customer_keywords.items():
            for kw in keywords:
                if kw in effects_text:
                    return impact

        # Default based on number of effects
        if len(effects) >= 4:
            return CustomerImpact.DISSATISFACTION
        elif len(effects) >= 2:
            return CustomerImpact.SLIGHT_DISSATISFACTION
        else:
            return CustomerImpact.BARELY_NOTICEABLE

    def _assess_lego_compatibility(self,
                                   component: str,
                                   effects: List[str]) -> float:
        """
        Assess impact on LEGO compatibility.

        Returns:
            Impact score 0-1 (1 = complete incompatibility)
        """
        compatibility_keywords = [
            'incompatible', 'does not fit', 'official lego',
            'clutch', 'connection', 'stud', 'dimension'
        ]

        # Check if component affects compatibility
        compatibility_components = ['stud', 'tube', 'clutch_power', 'compatibility']
        component_score = 0.5 if component in compatibility_components else 0.1

        # Check effects for compatibility keywords
        effects_text = ' '.join(effects).lower()
        keyword_hits = sum(1 for kw in compatibility_keywords if kw in effects_text)
        keyword_score = min(1.0, keyword_hits * 0.2)

        return min(1.0, component_score + keyword_score)

    def _propagate_effects(self,
                          component: str,
                          effects: List[str]) -> List[EffectPropagation]:
        """Propagate effects through component dependency graph."""
        propagated = []
        visited: Set[str] = set()

        def traverse(current: str, path: List[str], depth: int):
            if current in visited or depth > 5:
                return
            visited.add(current)

            dependents = self._component_graph.get(current, [])
            for dep in dependents:
                new_path = path + [dep]
                severity_contribution = 1.0 / (depth + 1)  # Diminishing with depth

                propagated.append(EffectPropagation(
                    effect=f"Impact on {dep} via {current}",
                    affected_components=[dep],
                    severity_contribution=severity_contribution,
                    propagation_path=new_path
                ))

                traverse(dep, new_path, depth + 1)

        traverse(component, [component], 0)
        return propagated

    def _generate_reasoning(self,
                           failure_mode: str,
                           safety: SafetyImpact,
                           functional: FunctionalImpact,
                           customer: CustomerImpact,
                           lego_impact: float,
                           propagated: List[EffectPropagation]) -> str:
        """Generate human-readable severity reasoning."""
        parts = [f"Failure mode '{failure_mode}' assessment:"]

        if safety != SafetyImpact.NONE:
            parts.append(f"- Safety impact: {safety.name} (contributes to severity)")

        parts.append(f"- Functional impact: {functional.name}")
        parts.append(f"- Customer impact: {customer.name}")

        if lego_impact > 0.3:
            parts.append(f"- LEGO compatibility impact: {lego_impact:.0%} (significant)")

        if propagated:
            affected = set()
            for p in propagated:
                affected.update(p.affected_components)
            parts.append(f"- Propagates to: {', '.join(list(affected)[:5])}")

        return '\n'.join(parts)

    def _estimate_confidence(self,
                            context: Dict[str, Any],
                            propagated: List[EffectPropagation]) -> float:
        """Estimate confidence in severity assessment."""
        confidence = 0.7  # Base confidence

        # More context increases confidence
        if context.get('historical_data'):
            confidence += 0.1
        if context.get('expert_input'):
            confidence += 0.1
        if context.get('test_results'):
            confidence += 0.1

        # Many propagation paths may indicate uncertainty
        if len(propagated) > 10:
            confidence -= 0.1

        return max(0.3, min(0.95, confidence))

    def batch_calculate(self,
                       failure_modes: List[Dict[str, Any]]) -> List[SeverityAssessment]:
        """
        Calculate severity for multiple failure modes.

        Args:
            failure_modes: List of {failure_mode, effects, component, context}

        Returns:
            List of severity assessments
        """
        assessments = []
        for fm in failure_modes:
            assessment = self.calculate_severity(
                failure_mode=fm.get('failure_mode', ''),
                effects=fm.get('effects', []),
                affected_component=fm.get('component', ''),
                context=fm.get('context')
            )
            assessments.append(assessment)
        return assessments

    def compare_severities(self,
                          assessments: List[SeverityAssessment]) -> Dict[str, Any]:
        """Compare multiple severity assessments."""
        if not assessments:
            return {}

        return {
            'highest_severity': max(a.overall_severity for a in assessments),
            'average_severity': sum(a.overall_severity for a in assessments) / len(assessments),
            'safety_critical': [a.failure_mode for a in assessments
                              if a.safety_impact.value >= SafetyImpact.SERIOUS.value],
            'lego_compatibility_issues': [a.failure_mode for a in assessments
                                         if a.lego_compatibility_impact > 0.5],
            'severity_distribution': self._get_severity_distribution(assessments)
        }

    def _get_severity_distribution(self,
                                   assessments: List[SeverityAssessment]) -> Dict[str, int]:
        """Get distribution of severity scores."""
        distribution = {'low (1-3)': 0, 'medium (4-6)': 0, 'high (7-10)': 0}
        for a in assessments:
            if a.overall_severity <= 3:
                distribution['low (1-3)'] += 1
            elif a.overall_severity <= 6:
                distribution['medium (4-6)'] += 1
            else:
                distribution['high (7-10)'] += 1
        return distribution
