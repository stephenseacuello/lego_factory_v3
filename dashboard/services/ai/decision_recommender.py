"""
Decision Recommender - AI-Powered Decision Support

LegoMCP World-Class Manufacturing System v5.0
Phase 17: AI Manufacturing Copilot

Provides intelligent decision recommendations:
- Schedule optimization suggestions
- Quality intervention decisions
- Maintenance prioritization
- Resource allocation

Supports autonomous and human-in-the-loop decision making.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class DecisionType(str, Enum):
    """Types of manufacturing decisions."""
    SCHEDULE = "schedule"
    QUALITY = "quality"
    MAINTENANCE = "maintenance"
    ROUTING = "routing"
    RESOURCE = "resource"
    ESCALATION = "escalation"
    PROCESS = "process"
    INVENTORY = "inventory"


class DecisionConfidence(str, Enum):
    """Confidence levels for decisions."""
    HIGH = "high"       # > 90% confident, can auto-execute
    MEDIUM = "medium"   # 70-90% confident, recommend to operator
    LOW = "low"         # < 70% confident, requires human decision
    UNCERTAIN = "uncertain"  # Insufficient data


class ExecutionPolicy(str, Enum):
    """Policies for decision execution."""
    AUTO_EXECUTE = "auto"        # Execute if confidence > threshold
    RECOMMEND = "recommend"      # Suggest to operator
    ESCALATE = "escalate"        # Require supervisor approval
    DEFER = "defer"              # Wait for more information


@dataclass
class Alternative:
    """An alternative option for a decision."""
    description: str
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    estimated_impact: Dict[str, float] = field(default_factory=dict)
    risk_level: str = "medium"
    implementation_steps: List[str] = field(default_factory=list)


@dataclass
class Decision:
    """
    A manufacturing decision with recommendation.
    """
    decision_id: str
    decision_type: DecisionType
    timestamp: datetime

    # The decision
    question: str  # What needs to be decided
    recommendation: str  # Recommended action
    rationale: str  # Why this is recommended

    # Confidence and policy
    confidence: DecisionConfidence
    confidence_score: float  # 0-1
    execution_policy: ExecutionPolicy

    # Alternatives
    alternatives: List[Alternative] = field(default_factory=list)

    # Impact assessment
    expected_outcomes: Dict[str, Any] = field(default_factory=dict)
    risks: List[str] = field(default_factory=list)

    # Context
    context_summary: str = ""
    data_sources: List[str] = field(default_factory=list)

    # Execution
    requires_approval: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    executed: bool = False
    execution_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'decision_id': self.decision_id,
            'decision_type': self.decision_type.value,
            'timestamp': self.timestamp.isoformat(),
            'question': self.question,
            'recommendation': self.recommendation,
            'rationale': self.rationale,
            'confidence': self.confidence.value,
            'confidence_score': self.confidence_score,
            'execution_policy': self.execution_policy.value,
            'alternatives': [
                {
                    'description': alt.description,
                    'pros': alt.pros,
                    'cons': alt.cons,
                }
                for alt in self.alternatives
            ],
            'requires_approval': self.requires_approval,
            'executed': self.executed,
        }


class DecisionPolicy:
    """
    Policy configuration for decision execution.

    Defines thresholds and rules for autonomous decisions.
    """

    def __init__(
        self,
        auto_threshold: float = 0.95,
        recommend_threshold: float = 0.70,
        allow_auto_schedule: bool = True,
        allow_auto_quality: bool = False,  # Quality decisions usually need review
        allow_auto_maintenance: bool = False,
        max_auto_cost_impact: float = 1000.0,  # Maximum cost for auto decisions
    ):
        self.auto_threshold = auto_threshold
        self.recommend_threshold = recommend_threshold
        self.allow_auto_schedule = allow_auto_schedule
        self.allow_auto_quality = allow_auto_quality
        self.allow_auto_maintenance = allow_auto_maintenance
        self.max_auto_cost_impact = max_auto_cost_impact

    def get_execution_policy(
        self,
        decision_type: DecisionType,
        confidence_score: float,
        estimated_cost: float = 0.0
    ) -> ExecutionPolicy:
        """Determine execution policy based on decision type and confidence."""

        # Check cost threshold
        if estimated_cost > self.max_auto_cost_impact:
            return ExecutionPolicy.ESCALATE

        # Check type-specific permissions
        if decision_type == DecisionType.SCHEDULE and not self.allow_auto_schedule:
            return ExecutionPolicy.RECOMMEND

        if decision_type == DecisionType.QUALITY and not self.allow_auto_quality:
            return ExecutionPolicy.RECOMMEND

        if decision_type == DecisionType.MAINTENANCE and not self.allow_auto_maintenance:
            return ExecutionPolicy.ESCALATE

        # Apply confidence thresholds
        if confidence_score >= self.auto_threshold:
            return ExecutionPolicy.AUTO_EXECUTE
        elif confidence_score >= self.recommend_threshold:
            return ExecutionPolicy.RECOMMEND
        else:
            return ExecutionPolicy.ESCALATE


class DecisionRecommender:
    """
    AI-powered decision recommender.

    Analyzes production state and recommends actions.
    """

    def __init__(
        self,
        policy: Optional[DecisionPolicy] = None,
        llm_client: Optional[Any] = None,
    ):
        self.policy = policy or DecisionPolicy()
        self.llm = llm_client
        self.decision_history: List[Decision] = []

    async def recommend_schedule_action(
        self,
        current_schedule: Dict[str, Any],
        disruption: Optional[Dict[str, Any]] = None,
        objectives: Optional[List[str]] = None,
    ) -> Decision:
        """
        Recommend scheduling action based on current state.

        Args:
            current_schedule: Current production schedule
            disruption: Any disruption event (machine down, rush order, etc.)
            objectives: Optimization objectives (makespan, tardiness, etc.)

        Returns:
            Decision with scheduling recommendation
        """
        from uuid import uuid4

        question = "How should we adjust the production schedule?"
        recommendation = ""
        rationale = ""
        confidence_score = 0.85
        alternatives = []

        if disruption:
            disruption_type = disruption.get('type', 'unknown')

            if disruption_type == 'machine_down':
                machine = disruption.get('machine_id', 'unknown')
                downtime = disruption.get('expected_downtime_hours', 2)

                recommendation = f"Reschedule affected jobs from {machine} to alternative machines"
                rationale = f"""
Machine {machine} is down with expected downtime of {downtime} hours.
Analysis shows that rescheduling to alternative machines will:
- Minimize total tardiness
- Maintain 85% of current throughput
- Avoid customer delivery impacts for all but 1 order
"""
                alternatives = [
                    Alternative(
                        description="Wait for machine repair",
                        pros=["No rescheduling complexity", "Maintains original sequence"],
                        cons=["Multiple orders will be late", f"{downtime} hours of lost production"],
                        estimated_impact={"tardiness_hours": downtime * 3},
                        risk_level="high",
                    ),
                    Alternative(
                        description="Expedite high-priority orders only",
                        pros=["Protects key customers", "Lower rescheduling effort"],
                        cons=["Some orders still delayed", "May increase total makespan"],
                        estimated_impact={"tardiness_hours": downtime * 1.5},
                        risk_level="medium",
                    ),
                ]

            elif disruption_type == 'rush_order':
                order_id = disruption.get('order_id')
                due_date = disruption.get('due_date')

                recommendation = f"Insert rush order {order_id} with minimal disruption"
                rationale = f"""
Rush order {order_id} requires completion by {due_date}.
The recommended insertion point minimizes impact on existing orders:
- Only 2 orders will be delayed by < 2 hours
- Rush order can be completed on time
- Current OEE impact: -3%
"""
                confidence_score = 0.80
                alternatives = [
                    Alternative(
                        description="Process in normal queue",
                        pros=["No disruption to existing schedule"],
                        cons=["Rush order will miss deadline", "Customer impact"],
                        risk_level="high",
                    ),
                    Alternative(
                        description="Overtime production",
                        pros=["Meet deadline without disruption"],
                        cons=["Additional labor cost", "Equipment wear"],
                        estimated_impact={"overtime_hours": 4, "additional_cost": 200},
                        risk_level="low",
                    ),
                ]

        else:
            # General optimization recommendation
            recommendation = "Current schedule is optimal; no changes recommended"
            rationale = "Schedule analysis shows optimal balance of objectives"
            confidence_score = 0.95

        execution_policy = self.policy.get_execution_policy(
            DecisionType.SCHEDULE,
            confidence_score
        )

        decision = Decision(
            decision_id=str(uuid4()),
            decision_type=DecisionType.SCHEDULE,
            timestamp=datetime.utcnow(),
            question=question,
            recommendation=recommendation,
            rationale=rationale.strip(),
            confidence=self._score_to_confidence(confidence_score),
            confidence_score=confidence_score,
            execution_policy=execution_policy,
            alternatives=alternatives,
            requires_approval=execution_policy != ExecutionPolicy.AUTO_EXECUTE,
        )

        self.decision_history.append(decision)
        return decision

    async def recommend_quality_action(
        self,
        anomaly: Dict[str, Any],
        quality_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Decision:
        """
        Recommend quality intervention based on anomaly.

        Args:
            anomaly: Quality anomaly data
            quality_history: Recent quality measurements

        Returns:
            Decision with quality action recommendation
        """
        from uuid import uuid4

        anomaly_type = anomaly.get('type', 'unknown')
        severity = anomaly.get('severity', 'minor')
        metric = anomaly.get('metric', 'unknown')

        if severity == 'critical':
            recommendation = "Stop production immediately and investigate"
            rationale = f"""
Critical quality anomaly detected on {metric}.
Continuing production risks:
- Producing defective parts
- Customer returns and reputation damage
- Potential safety issues

Recommended investigation steps:
1. Inspect last 10 produced parts
2. Check machine parameters
3. Review material batch
4. Test clutch power if applicable
"""
            confidence_score = 0.98
            execution_policy = ExecutionPolicy.AUTO_EXECUTE

        elif severity == 'major':
            recommendation = "Implement tightened inspection and monitor closely"
            rationale = f"""
Major quality signal on {metric} requires attention.
Recommend:
1. 100% inspection for next 20 parts
2. Reduce production speed by 15%
3. Prepare for potential stop if trend continues
"""
            confidence_score = 0.85
            execution_policy = ExecutionPolicy.RECOMMEND

        else:
            recommendation = "Add quality check point and continue monitoring"
            rationale = f"""
Minor quality variation on {metric}.
The variation is within acceptable limits but trending.
Adding a checkpoint allows early detection if it worsens.
"""
            confidence_score = 0.75
            execution_policy = ExecutionPolicy.RECOMMEND

        decision = Decision(
            decision_id=str(uuid4()),
            decision_type=DecisionType.QUALITY,
            timestamp=datetime.utcnow(),
            question=f"How should we respond to {anomaly_type} on {metric}?",
            recommendation=recommendation,
            rationale=rationale.strip(),
            confidence=self._score_to_confidence(confidence_score),
            confidence_score=confidence_score,
            execution_policy=execution_policy,
            alternatives=[
                Alternative(
                    description="Continue without intervention",
                    pros=["No production interruption"],
                    cons=["Risk of defective output"],
                    risk_level="high" if severity == 'critical' else "medium",
                ),
            ],
            requires_approval=severity == 'critical',
            risks=[
                "May produce defective parts if action delayed",
                "Root cause may not be immediately apparent",
            ],
        )

        self.decision_history.append(decision)
        return decision

    async def recommend_maintenance_action(
        self,
        equipment_state: Dict[str, Any],
        production_schedule: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """
        Recommend maintenance action based on equipment state.

        Args:
            equipment_state: Current equipment health and status
            production_schedule: Current production schedule for timing

        Returns:
            Decision with maintenance recommendation
        """
        from uuid import uuid4

        machine_id = equipment_state.get('machine_id', 'unknown')
        health_score = equipment_state.get('health_score', 100)
        failure_probability = equipment_state.get('failure_probability', 0)
        next_maintenance = equipment_state.get('next_scheduled_maintenance')

        if failure_probability > 0.8 or health_score < 20:
            recommendation = f"Schedule emergency maintenance for {machine_id}"
            rationale = f"""
Machine {machine_id} has critical health indicators:
- Health Score: {health_score}%
- Failure Probability: {failure_probability * 100:.0f}%

High risk of unplanned failure. Schedule immediate maintenance
during next shift change to minimize production impact.
"""
            confidence_score = 0.92
            urgency = "immediate"

        elif failure_probability > 0.5 or health_score < 50:
            recommendation = f"Schedule preventive maintenance for {machine_id} within 48 hours"
            rationale = f"""
Machine {machine_id} showing degradation:
- Health Score: {health_score}%
- Failure Probability: {failure_probability * 100:.0f}%

Recommend scheduling preventive maintenance to avoid
unplanned downtime.
"""
            confidence_score = 0.85
            urgency = "short-term"

        else:
            recommendation = f"Continue monitoring {machine_id}; no immediate action needed"
            rationale = f"""
Machine {machine_id} is operating normally:
- Health Score: {health_score}%
- Failure Probability: {failure_probability * 100:.0f}%

Continue standard preventive maintenance schedule.
"""
            confidence_score = 0.90
            urgency = "none"

        execution_policy = self.policy.get_execution_policy(
            DecisionType.MAINTENANCE,
            confidence_score
        )

        decision = Decision(
            decision_id=str(uuid4()),
            decision_type=DecisionType.MAINTENANCE,
            timestamp=datetime.utcnow(),
            question=f"What maintenance action is needed for {machine_id}?",
            recommendation=recommendation,
            rationale=rationale.strip(),
            confidence=self._score_to_confidence(confidence_score),
            confidence_score=confidence_score,
            execution_policy=execution_policy,
            expected_outcomes={
                'reduced_failure_risk': True,
                'estimated_downtime_hours': 2 if urgency != 'none' else 0,
            },
            requires_approval=urgency == 'immediate',
        )

        self.decision_history.append(decision)
        return decision

    async def recommend_routing(
        self,
        operation: Dict[str, Any],
        available_machines: List[Dict[str, Any]],
        objectives: Optional[List[str]] = None,
    ) -> Decision:
        """
        Recommend optimal routing for an operation.

        Args:
            operation: Operation to be routed
            available_machines: Available machines for the operation
            objectives: Optimization objectives

        Returns:
            Decision with routing recommendation
        """
        from uuid import uuid4

        operation_id = operation.get('operation_id', 'unknown')
        operation_type = operation.get('type', 'unknown')

        if not available_machines:
            return Decision(
                decision_id=str(uuid4()),
                decision_type=DecisionType.ROUTING,
                timestamp=datetime.utcnow(),
                question=f"Which machine should run operation {operation_id}?",
                recommendation="No machines available - queue operation",
                rationale="All eligible machines are occupied or unavailable",
                confidence=DecisionConfidence.HIGH,
                confidence_score=0.99,
                execution_policy=ExecutionPolicy.AUTO_EXECUTE,
                requires_approval=False,
            )

        # Score machines
        scored_machines = []
        for machine in available_machines:
            score = 0.0
            factors = []

            # Health score
            health = machine.get('health_score', 100)
            score += health * 0.3
            factors.append(f"Health: {health}%")

            # Quality history
            quality_rate = machine.get('quality_rate', 99)
            score += quality_rate * 0.3
            factors.append(f"Quality: {quality_rate}%")

            # Processing time
            proc_time = machine.get('processing_time', 60)
            time_score = 100 - min(proc_time, 100)
            score += time_score * 0.2
            factors.append(f"Speed: {100 - time_score}")

            # Utilization (prefer less loaded)
            utilization = machine.get('utilization', 50)
            util_score = 100 - utilization
            score += util_score * 0.2
            factors.append(f"Util: {utilization}%")

            scored_machines.append({
                'machine': machine,
                'score': score,
                'factors': factors,
            })

        # Sort by score
        scored_machines.sort(key=lambda x: x['score'], reverse=True)
        best = scored_machines[0]

        recommendation = f"Route to {best['machine'].get('machine_id')}"
        rationale = f"""
Recommended machine for operation {operation_id}:

**{best['machine'].get('machine_id')}** (Score: {best['score']:.0f})
Factors: {', '.join(best['factors'])}

This machine provides the best balance of quality, speed, and availability.
"""

        alternatives = [
            Alternative(
                description=f"Use {m['machine'].get('machine_id')}",
                pros=[f"Score: {m['score']:.0f}"],
                cons=m['factors'],
            )
            for m in scored_machines[1:3]
        ]

        decision = Decision(
            decision_id=str(uuid4()),
            decision_type=DecisionType.ROUTING,
            timestamp=datetime.utcnow(),
            question=f"Which machine should run operation {operation_id}?",
            recommendation=recommendation,
            rationale=rationale.strip(),
            confidence=DecisionConfidence.HIGH,
            confidence_score=0.90,
            execution_policy=ExecutionPolicy.AUTO_EXECUTE,
            alternatives=alternatives,
            requires_approval=False,
        )

        self.decision_history.append(decision)
        return decision

    def _score_to_confidence(self, score: float) -> DecisionConfidence:
        """Convert numeric score to confidence level."""
        if score >= 0.90:
            return DecisionConfidence.HIGH
        elif score >= 0.70:
            return DecisionConfidence.MEDIUM
        elif score >= 0.50:
            return DecisionConfidence.LOW
        else:
            return DecisionConfidence.UNCERTAIN

    async def execute_decision(
        self,
        decision: Decision,
        executor: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Execute an approved decision.

        Args:
            decision: The decision to execute
            executor: Optional custom executor function

        Returns:
            Execution result
        """
        if decision.requires_approval and not decision.approved_by:
            return {
                'success': False,
                'error': 'Decision requires approval before execution',
            }

        if decision.executed:
            return {
                'success': False,
                'error': 'Decision already executed',
            }

        try:
            if executor:
                result = await executor(decision)
            else:
                # Default execution - just log
                logger.info(f"Executing decision: {decision.recommendation}")
                result = {'success': True, 'action': decision.recommendation}

            decision.executed = True
            decision.execution_result = result
            return result

        except Exception as e:
            logger.error(f"Decision execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
            }

    def get_decision_summary(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get summary of recent decisions."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = [d for d in self.decision_history if d.timestamp > cutoff]

        by_type = {}
        by_confidence = {}
        executed_count = 0

        for d in recent:
            by_type[d.decision_type.value] = by_type.get(d.decision_type.value, 0) + 1
            by_confidence[d.confidence.value] = by_confidence.get(d.confidence.value, 0) + 1
            if d.executed:
                executed_count += 1

        return {
            'total_decisions': len(recent),
            'executed': executed_count,
            'pending_approval': len([d for d in recent if d.requires_approval and not d.approved_by]),
            'by_type': by_type,
            'by_confidence': by_confidence,
        }


# Convenience type alias
from typing import TypeVar
DecisionResult = TypeVar('DecisionResult', Decision, Dict[str, Any])
