"""
Decision Engine Service
=======================

AI-powered decision engine that:
- Analyzes recommendations from AI/ML services
- Performs risk assessment
- Evaluates impact analysis
- Routes to appropriate approval workflows

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


class DecisionOutcome(Enum):
    """Possible decision outcomes"""
    APPROVE_AUTO = "approve_auto"           # Automatic approval
    APPROVE_RECOMMEND = "approve_recommend"  # Recommend approval
    ESCALATE = "escalate"                   # Escalate to higher authority
    REJECT = "reject"                       # Reject recommendation
    DEFER = "defer"                         # Defer decision
    NEED_INFO = "need_more_info"            # Need more information


class RiskLevel(Enum):
    """Risk level classifications"""
    NEGLIGIBLE = "negligible"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactArea(Enum):
    """Areas that may be impacted"""
    PRODUCTION = "production"
    QUALITY = "quality"
    SAFETY = "safety"
    COST = "cost"
    DELIVERY = "delivery"
    EQUIPMENT = "equipment"
    INVENTORY = "inventory"
    ENVIRONMENT = "environment"


@dataclass
class RiskAssessment:
    """Risk assessment result"""
    level: RiskLevel
    score: float  # 0-100
    factors: List[Dict[str, Any]]
    mitigations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "score": self.score,
            "factors": self.factors,
            "mitigations": self.mitigations
        }


@dataclass
class ImpactAnalysis:
    """Impact analysis result"""
    areas: Dict[ImpactArea, float]  # Impact score per area (0-100)
    total_score: float
    affected_entities: List[Dict[str, Any]]
    timeline: str  # immediate, short-term, long-term
    reversible: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "areas": {k.value: v for k, v in self.areas.items()},
            "total_score": self.total_score,
            "affected_entities": self.affected_entities,
            "timeline": self.timeline,
            "reversible": self.reversible
        }


@dataclass
class Decision:
    """Decision record"""
    id: str
    recommendation_id: str
    source: str
    outcome: DecisionOutcome
    risk_assessment: RiskAssessment
    impact_analysis: ImpactAnalysis
    confidence: float  # 0-1
    reasoning: str
    created_at: datetime
    constraints_violated: List[str] = field(default_factory=list)
    alternative_actions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "recommendation_id": self.recommendation_id,
            "source": self.source,
            "outcome": self.outcome.value,
            "risk_assessment": self.risk_assessment.to_dict(),
            "impact_analysis": self.impact_analysis.to_dict(),
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat(),
            "constraints_violated": self.constraints_violated,
            "alternative_actions": self.alternative_actions
        }


class DecisionEngine:
    """
    AI-powered decision engine for algorithm-to-action pipeline.

    Evaluates recommendations and determines appropriate actions
    based on risk, impact, and policy constraints.
    """

    # Decision thresholds
    AUTO_APPROVE_RISK_THRESHOLD = 25.0
    AUTO_APPROVE_IMPACT_THRESHOLD = 20.0
    ESCALATION_RISK_THRESHOLD = 75.0
    ESCALATION_IMPACT_THRESHOLD = 80.0
    MIN_CONFIDENCE_THRESHOLD = 0.7

    # Constraint definitions
    CONSTRAINTS = {
        "safety": {
            "description": "No actions that could cause safety incidents",
            "check": lambda rec: rec.get("safety_risk", 0) < 10
        },
        "budget": {
            "description": "Actions must be within budget limits",
            "check": lambda rec: rec.get("cost", 0) <= rec.get("budget_limit", float("inf"))
        },
        "capacity": {
            "description": "Actions must respect capacity constraints",
            "check": lambda rec: rec.get("capacity_required", 0) <= rec.get("capacity_available", float("inf"))
        },
        "regulatory": {
            "description": "Actions must comply with regulations",
            "check": lambda rec: rec.get("regulatory_compliant", True)
        },
        "quality": {
            "description": "Actions must not compromise quality standards",
            "check": lambda rec: rec.get("quality_impact", 0) >= -10
        }
    }

    def __init__(self):
        """Initialize decision engine"""
        self._decisions: Dict[str, Decision] = {}
        self._custom_rules: List[Dict[str, Any]] = []

    def evaluate(
        self,
        recommendation: Dict[str, Any],
        source: str = "ai"
    ) -> Decision:
        """
        Evaluate a recommendation and produce a decision.

        Args:
            recommendation: AI/ML recommendation to evaluate
            source: Source of the recommendation

        Returns:
            Decision object with outcome and analysis
        """
        recommendation_id = recommendation.get("id", str(uuid.uuid4()))

        # Assess risk
        risk = self._assess_risk(recommendation)

        # Analyze impact
        impact = self._analyze_impact(recommendation)

        # Check constraints
        violations = self._check_constraints(recommendation)

        # Determine outcome
        outcome, reasoning, confidence = self._determine_outcome(
            recommendation, risk, impact, violations
        )

        # Generate alternatives if not approving
        alternatives = []
        if outcome not in [DecisionOutcome.APPROVE_AUTO, DecisionOutcome.APPROVE_RECOMMEND]:
            alternatives = self._generate_alternatives(recommendation, violations)

        decision = Decision(
            id=str(uuid.uuid4()),
            recommendation_id=recommendation_id,
            source=source,
            outcome=outcome,
            risk_assessment=risk,
            impact_analysis=impact,
            confidence=confidence,
            reasoning=reasoning,
            created_at=datetime.now(),
            constraints_violated=violations,
            alternative_actions=alternatives
        )

        self._decisions[decision.id] = decision
        logger.info(f"Decision made: {decision.id} -> {outcome.value}")

        return decision

    def _assess_risk(self, recommendation: Dict[str, Any]) -> RiskAssessment:
        """Assess risk of implementing recommendation"""
        factors = []
        score = 0.0

        # Safety risk factor
        safety_risk = recommendation.get("safety_risk", 0)
        if safety_risk > 0:
            factors.append({
                "name": "safety",
                "value": safety_risk,
                "weight": 3.0,
                "description": "Potential safety implications"
            })
            score += safety_risk * 3.0

        # Equipment risk factor
        equipment_risk = recommendation.get("equipment_risk", 0)
        if equipment_risk > 0:
            factors.append({
                "name": "equipment",
                "value": equipment_risk,
                "weight": 2.0,
                "description": "Risk to equipment"
            })
            score += equipment_risk * 2.0

        # Financial risk factor
        financial_risk = recommendation.get("financial_risk", 0)
        if financial_risk > 0:
            factors.append({
                "name": "financial",
                "value": financial_risk,
                "weight": 1.5,
                "description": "Financial exposure"
            })
            score += financial_risk * 1.5

        # Operational risk factor
        operational_risk = recommendation.get("operational_risk", 0)
        if operational_risk > 0:
            factors.append({
                "name": "operational",
                "value": operational_risk,
                "weight": 1.0,
                "description": "Operational disruption potential"
            })
            score += operational_risk * 1.0

        # Normalize score
        total_weight = sum(f["weight"] for f in factors) if factors else 1
        score = min(100, score / total_weight if total_weight > 0 else 0)

        # Determine level
        if score < 10:
            level = RiskLevel.NEGLIGIBLE
        elif score < 25:
            level = RiskLevel.LOW
        elif score < 50:
            level = RiskLevel.MEDIUM
        elif score < 75:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL

        # Generate mitigations
        mitigations = self._generate_mitigations(factors)

        return RiskAssessment(
            level=level,
            score=score,
            factors=factors,
            mitigations=mitigations
        )

    def _analyze_impact(self, recommendation: Dict[str, Any]) -> ImpactAnalysis:
        """Analyze impact of implementing recommendation"""
        areas = {}

        # Production impact
        if "production_impact" in recommendation:
            areas[ImpactArea.PRODUCTION] = abs(recommendation["production_impact"])

        # Quality impact
        if "quality_impact" in recommendation:
            areas[ImpactArea.QUALITY] = abs(recommendation["quality_impact"])

        # Cost impact
        if "cost" in recommendation or "cost_impact" in recommendation:
            cost = recommendation.get("cost", 0) + recommendation.get("cost_impact", 0)
            areas[ImpactArea.COST] = min(100, cost / 100)  # Normalize

        # Delivery impact
        if "delivery_impact" in recommendation:
            areas[ImpactArea.DELIVERY] = abs(recommendation["delivery_impact"])

        # Equipment impact
        if "equipment_impact" in recommendation:
            areas[ImpactArea.EQUIPMENT] = abs(recommendation["equipment_impact"])

        # Calculate total
        total_score = sum(areas.values()) / len(areas) if areas else 0

        # Identify affected entities
        affected = recommendation.get("affected_entities", [])

        # Determine timeline
        duration = recommendation.get("duration_hours", 0)
        if duration < 1:
            timeline = "immediate"
        elif duration < 24:
            timeline = "short-term"
        else:
            timeline = "long-term"

        return ImpactAnalysis(
            areas=areas,
            total_score=total_score,
            affected_entities=affected,
            timeline=timeline,
            reversible=recommendation.get("reversible", True)
        )

    def _check_constraints(self, recommendation: Dict[str, Any]) -> List[str]:
        """Check which constraints are violated"""
        violations = []

        for name, constraint in self.CONSTRAINTS.items():
            try:
                if not constraint["check"](recommendation):
                    violations.append(name)
            except Exception as e:
                logger.warning(f"Constraint check failed for {name}: {e}")

        # Check custom rules
        for rule in self._custom_rules:
            try:
                if not rule["check"](recommendation):
                    violations.append(rule["name"])
            except Exception as e:
                logger.warning(f"Custom rule check failed: {e}")

        return violations

    def _determine_outcome(
        self,
        recommendation: Dict[str, Any],
        risk: RiskAssessment,
        impact: ImpactAnalysis,
        violations: List[str]
    ) -> tuple:
        """Determine decision outcome based on analysis"""
        # Check for hard violations
        if "safety" in violations:
            return (
                DecisionOutcome.REJECT,
                "Safety constraint violated - action rejected",
                0.95
            )

        if "regulatory" in violations:
            return (
                DecisionOutcome.REJECT,
                "Regulatory compliance violated - action rejected",
                0.95
            )

        # Check for critical risk
        if risk.level == RiskLevel.CRITICAL:
            return (
                DecisionOutcome.ESCALATE,
                f"Critical risk level ({risk.score:.1f}) requires executive approval",
                0.85
            )

        # Check for high impact requiring escalation
        if impact.total_score > self.ESCALATION_IMPACT_THRESHOLD:
            return (
                DecisionOutcome.ESCALATE,
                f"High impact score ({impact.total_score:.1f}) requires management approval",
                0.80
            )

        # Check for other violations requiring human review
        if violations:
            return (
                DecisionOutcome.APPROVE_RECOMMEND,
                f"Constraints violated ({', '.join(violations)}) - human review recommended",
                0.70
            )

        # Check for auto-approval eligibility
        if (
            risk.score <= self.AUTO_APPROVE_RISK_THRESHOLD and
            impact.total_score <= self.AUTO_APPROVE_IMPACT_THRESHOLD and
            not violations
        ):
            confidence = recommendation.get("confidence", 0.8)
            if confidence >= self.MIN_CONFIDENCE_THRESHOLD:
                return (
                    DecisionOutcome.APPROVE_AUTO,
                    f"Low risk ({risk.score:.1f}) and low impact ({impact.total_score:.1f}) - auto-approved",
                    confidence
                )

        # Default to recommend approval with human review
        return (
            DecisionOutcome.APPROVE_RECOMMEND,
            f"Risk: {risk.level.value}, Impact: {impact.total_score:.1f} - approval recommended",
            recommendation.get("confidence", 0.75)
        )

    def _generate_mitigations(self, risk_factors: List[Dict[str, Any]]) -> List[str]:
        """Generate risk mitigation suggestions"""
        mitigations = []

        for factor in risk_factors:
            name = factor["name"]
            value = factor["value"]

            if name == "safety" and value > 5:
                mitigations.append("Implement additional safety monitoring during execution")
                mitigations.append("Ensure safety personnel are present")

            if name == "equipment" and value > 10:
                mitigations.append("Perform equipment health check before action")
                mitigations.append("Have backup equipment on standby")

            if name == "financial" and value > 20:
                mitigations.append("Set cost limits and monitoring thresholds")
                mitigations.append("Prepare rollback procedure")

            if name == "operational" and value > 15:
                mitigations.append("Schedule during low-production periods")
                mitigations.append("Notify affected stakeholders in advance")

        return mitigations

    def _generate_alternatives(
        self,
        recommendation: Dict[str, Any],
        violations: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate alternative actions when original is not approved"""
        alternatives = []

        # Scaled-down version
        if "magnitude" in recommendation or "quantity" in recommendation:
            scaled = recommendation.copy()
            for key in ["magnitude", "quantity", "scope"]:
                if key in scaled:
                    scaled[key] = scaled[key] * 0.5
            alternatives.append({
                "type": "scaled_down",
                "description": "Execute at 50% scale",
                "parameters": scaled
            })

        # Phased approach
        if recommendation.get("duration_hours", 0) > 4:
            alternatives.append({
                "type": "phased",
                "description": "Implement in multiple phases",
                "parameters": {
                    "phases": 3,
                    "phase_duration": recommendation.get("duration_hours", 12) / 3
                }
            })

        # Delayed execution
        alternatives.append({
            "type": "delayed",
            "description": "Schedule for off-peak hours",
            "parameters": {
                "delay_hours": 12,
                "preferred_window": "00:00-06:00"
            }
        })

        # Manual override with supervision
        if "safety" not in violations:
            alternatives.append({
                "type": "supervised",
                "description": "Execute with enhanced monitoring",
                "parameters": {
                    "supervision_level": "high",
                    "checkpoints": 3
                }
            })

        return alternatives

    def add_custom_rule(
        self,
        name: str,
        description: str,
        check: callable
    ):
        """Add a custom decision rule"""
        self._custom_rules.append({
            "name": name,
            "description": description,
            "check": check
        })

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        """Get a decision by ID"""
        return self._decisions.get(decision_id)

    def get_decisions_for_recommendation(self, recommendation_id: str) -> List[Decision]:
        """Get all decisions for a recommendation"""
        return [
            d for d in self._decisions.values()
            if d.recommendation_id == recommendation_id
        ]


# Singleton instance
_decision_engine: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    """Get or create the singleton decision engine instance"""
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = DecisionEngine()
    return _decision_engine
