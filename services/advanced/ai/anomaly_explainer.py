"""
Anomaly Explainer - AI-Powered Anomaly Analysis

LegoMCP World-Class Manufacturing System v5.0
Phase 17: AI Manufacturing Copilot

Provides plain-language explanations for production anomalies:
- SPC chart signals
- Quality defects
- Equipment issues
- Schedule deviations

Uses Claude to translate technical data into actionable insights.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    """Types of production anomalies."""
    SPC_SIGNAL = "spc_signal"
    QUALITY_DEFECT = "quality_defect"
    EQUIPMENT_ALARM = "equipment_alarm"
    SCHEDULE_DEVIATION = "schedule_deviation"
    PROCESS_DRIFT = "process_drift"
    MATERIAL_ISSUE = "material_issue"
    OPERATOR_ERROR = "operator_error"


class SeverityLevel(str, Enum):
    """Severity levels for anomalies."""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFORMATIONAL = "informational"


@dataclass
class AnomalyData:
    """Raw data about an anomaly."""
    anomaly_type: AnomalyType
    timestamp: datetime
    source: str  # machine, process, quality, etc.
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    related_events: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RootCause:
    """A potential root cause for an anomaly."""
    description: str
    probability: float  # 0-1
    evidence: List[str] = field(default_factory=list)
    category: str = "unknown"


@dataclass
class CorrectiveAction:
    """A recommended corrective action."""
    description: str
    priority: str  # immediate, short-term, long-term
    action_type: str  # investigate, adjust, replace, retrain
    estimated_impact: str = ""
    requires_approval: bool = False


@dataclass
class AnomalyExplanation:
    """
    Complete explanation of an anomaly.

    Provides human-readable analysis and recommendations.
    """
    anomaly_id: str
    anomaly_type: AnomalyType
    severity: SeverityLevel
    timestamp: datetime

    # Plain language explanation
    summary: str
    detailed_explanation: str

    # Analysis
    root_causes: List[RootCause] = field(default_factory=list)
    contributing_factors: List[str] = field(default_factory=list)

    # Recommendations
    corrective_actions: List[CorrectiveAction] = field(default_factory=list)
    preventive_measures: List[str] = field(default_factory=list)

    # Impact assessment
    production_impact: str = ""
    quality_impact: str = ""
    cost_impact: str = ""

    # Historical context
    similar_incidents: List[Dict[str, Any]] = field(default_factory=list)
    pattern_detected: Optional[str] = None

    # Confidence
    confidence_score: float = 0.0
    needs_human_review: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'anomaly_id': self.anomaly_id,
            'anomaly_type': self.anomaly_type.value,
            'severity': self.severity.value,
            'timestamp': self.timestamp.isoformat(),
            'summary': self.summary,
            'detailed_explanation': self.detailed_explanation,
            'root_causes': [
                {'description': rc.description, 'probability': rc.probability}
                for rc in self.root_causes
            ],
            'corrective_actions': [
                {'description': ca.description, 'priority': ca.priority}
                for ca in self.corrective_actions
            ],
            'confidence_score': self.confidence_score,
            'needs_human_review': self.needs_human_review,
        }


class AnomalyExplainer:
    """
    AI-powered anomaly explainer.

    Uses domain knowledge and AI to provide plain-language
    explanations of production anomalies.
    """

    # SPC rule descriptions
    SPC_RULES = {
        "rule_1": "One point beyond 3σ (control limit violation)",
        "rule_2": "Nine consecutive points on one side of the centerline",
        "rule_3": "Six consecutive points steadily increasing or decreasing",
        "rule_4": "Fourteen consecutive points alternating up and down",
        "zone_a": "2 of 3 consecutive points beyond 2σ",
        "zone_b": "4 of 5 consecutive points beyond 1σ",
        "zone_c": "8 consecutive points on one side of centerline",
    }

    # LEGO-specific failure modes
    LEGO_FAILURE_MODES = {
        "clutch_power_low": {
            "description": "Insufficient grip between bricks",
            "common_causes": ["stud diameter too small", "material shrinkage", "under-extrusion"],
            "actions": ["check flow rate", "verify temperature", "measure stud diameter"],
        },
        "clutch_power_high": {
            "description": "Bricks too tight to separate",
            "common_causes": ["stud diameter too large", "over-extrusion", "material expansion"],
            "actions": ["reduce flow rate", "check cooling", "verify calibration"],
        },
        "warping": {
            "description": "Part deformation after printing",
            "common_causes": ["bed adhesion issues", "cooling too fast", "internal stress"],
            "actions": ["increase bed temp", "use enclosure", "adjust cooling fan"],
        },
        "layer_adhesion": {
            "description": "Weak bonding between layers",
            "common_causes": ["temperature too low", "layer height too high", "print speed too fast"],
            "actions": ["increase nozzle temp", "reduce layer height", "slow down print"],
        },
    }

    def __init__(self, llm_client: Optional[Any] = None):
        """
        Initialize the anomaly explainer.

        Args:
            llm_client: Optional LLM client for AI-powered explanations
        """
        self.llm = llm_client

    async def explain_anomaly(
        self,
        anomaly: AnomalyData,
        include_history: bool = True,
        verbose: bool = False
    ) -> AnomalyExplanation:
        """
        Generate explanation for an anomaly.

        Args:
            anomaly: The anomaly data to explain
            include_history: Whether to include historical context
            verbose: Whether to include detailed technical information

        Returns:
            Complete anomaly explanation
        """
        # Route to appropriate handler based on type
        if anomaly.anomaly_type == AnomalyType.SPC_SIGNAL:
            return await self._explain_spc_signal(anomaly, verbose)
        elif anomaly.anomaly_type == AnomalyType.QUALITY_DEFECT:
            return await self._explain_quality_defect(anomaly, verbose)
        elif anomaly.anomaly_type == AnomalyType.EQUIPMENT_ALARM:
            return await self._explain_equipment_alarm(anomaly, verbose)
        elif anomaly.anomaly_type == AnomalyType.SCHEDULE_DEVIATION:
            return await self._explain_schedule_deviation(anomaly, verbose)
        elif anomaly.anomaly_type == AnomalyType.PROCESS_DRIFT:
            return await self._explain_process_drift(anomaly, verbose)
        else:
            return await self._explain_generic(anomaly, verbose)

    async def _explain_spc_signal(
        self,
        anomaly: AnomalyData,
        verbose: bool
    ) -> AnomalyExplanation:
        """Explain an SPC chart signal."""
        from uuid import uuid4

        signal_type = anomaly.context.get('signal_type', 'unknown')
        metric = anomaly.metric_name or 'unknown metric'
        value = anomaly.metric_value
        ucl = anomaly.context.get('ucl')
        lcl = anomaly.context.get('lcl')
        centerline = anomaly.context.get('centerline')

        # Determine severity
        if signal_type == 'rule_1':
            severity = SeverityLevel.CRITICAL
        elif signal_type in ('zone_a', 'zone_b'):
            severity = SeverityLevel.MAJOR
        else:
            severity = SeverityLevel.MINOR

        # Build explanation
        rule_desc = self.SPC_RULES.get(signal_type, "Unknown pattern detected")

        summary = f"SPC signal on {metric}: {rule_desc}"

        detailed = f"""
The {metric} measurement triggered an SPC alarm. This signal indicates that
the process may be going out of control.

**Signal Type:** {signal_type}
**Pattern:** {rule_desc}
**Current Value:** {value:.4f if value else 'N/A'}
**Control Limits:** UCL={ucl:.4f if ucl else 'N/A'}, LCL={lcl:.4f if lcl else 'N/A'}
**Centerline:** {centerline:.4f if centerline else 'N/A'}

This pattern suggests a non-random cause is affecting the process. Investigation
is required to identify and address the root cause before defects occur.
"""

        # Determine root causes based on metric
        root_causes = []
        if 'stud' in metric.lower():
            root_causes = [
                RootCause(
                    description="Nozzle wear affecting extrusion width",
                    probability=0.4,
                    evidence=["gradual drift pattern", "affects stud dimensions"],
                    category="equipment"
                ),
                RootCause(
                    description="Filament diameter variation",
                    probability=0.3,
                    evidence=["material batch change"],
                    category="material"
                ),
                RootCause(
                    description="Temperature controller drift",
                    probability=0.2,
                    evidence=["ambient temperature changes"],
                    category="environment"
                ),
            ]
        elif 'temperature' in metric.lower():
            root_causes = [
                RootCause(
                    description="Heater cartridge degradation",
                    probability=0.5,
                    evidence=["temperature instability"],
                    category="equipment"
                ),
                RootCause(
                    description="Thermistor contact issue",
                    probability=0.3,
                    evidence=["sudden temperature spikes"],
                    category="sensor"
                ),
            ]

        # Corrective actions
        actions = [
            CorrectiveAction(
                description="Inspect process parameters and equipment",
                priority="immediate",
                action_type="investigate",
                estimated_impact="Prevent potential defects",
            ),
            CorrectiveAction(
                description="Take additional measurements to confirm trend",
                priority="immediate",
                action_type="investigate",
                estimated_impact="Validate signal authenticity",
            ),
        ]

        if severity == SeverityLevel.CRITICAL:
            actions.insert(0, CorrectiveAction(
                description="Consider pausing production pending investigation",
                priority="immediate",
                action_type="adjust",
                estimated_impact="Prevent defective output",
                requires_approval=True,
            ))

        return AnomalyExplanation(
            anomaly_id=str(uuid4()),
            anomaly_type=AnomalyType.SPC_SIGNAL,
            severity=severity,
            timestamp=anomaly.timestamp,
            summary=summary,
            detailed_explanation=detailed.strip(),
            root_causes=root_causes,
            corrective_actions=actions,
            contributing_factors=[
                "Process variation",
                "Equipment condition",
                "Material consistency",
            ],
            preventive_measures=[
                "Implement tighter incoming material inspection",
                "Schedule preventive maintenance for equipment",
                "Review process capability study",
            ],
            production_impact="May produce out-of-spec parts if not addressed",
            quality_impact="Risk of dimensional non-conformance",
            confidence_score=0.85,
            needs_human_review=severity == SeverityLevel.CRITICAL,
        )

    async def _explain_quality_defect(
        self,
        anomaly: AnomalyData,
        verbose: bool
    ) -> AnomalyExplanation:
        """Explain a quality defect."""
        from uuid import uuid4

        defect_type = anomaly.context.get('defect_type', 'unknown')
        defect_info = self.LEGO_FAILURE_MODES.get(
            defect_type,
            {
                "description": "Unknown defect type",
                "common_causes": ["Investigation required"],
                "actions": ["Inspect part and process"],
            }
        )

        severity = SeverityLevel.MAJOR if 'critical' in str(anomaly.context.get('severity', '')).lower() else SeverityLevel.MINOR

        summary = f"Quality defect detected: {defect_info['description']}"

        detailed = f"""
A {defect_type} defect was detected on the produced part.

**Defect Type:** {defect_type}
**Description:** {defect_info['description']}
**Part ID:** {anomaly.context.get('part_id', 'N/A')}
**Work Order:** {anomaly.context.get('work_order_id', 'N/A')}

**Common Causes:**
{chr(10).join(f'- {cause}' for cause in defect_info['common_causes'])}

**Recommended Actions:**
{chr(10).join(f'- {action}' for action in defect_info['actions'])}

This defect may indicate a systematic process issue that should be investigated
before continuing production.
"""

        root_causes = [
            RootCause(
                description=cause,
                probability=0.5 / len(defect_info['common_causes']),
                category="process"
            )
            for cause in defect_info['common_causes']
        ]

        actions = [
            CorrectiveAction(
                description=action,
                priority="short-term",
                action_type="adjust",
            )
            for action in defect_info['actions']
        ]

        return AnomalyExplanation(
            anomaly_id=str(uuid4()),
            anomaly_type=AnomalyType.QUALITY_DEFECT,
            severity=severity,
            timestamp=anomaly.timestamp,
            summary=summary,
            detailed_explanation=detailed.strip(),
            root_causes=root_causes,
            corrective_actions=actions,
            quality_impact=f"Part may not meet LEGO compatibility standards",
            confidence_score=0.75,
            needs_human_review=severity == SeverityLevel.MAJOR,
        )

    async def _explain_equipment_alarm(
        self,
        anomaly: AnomalyData,
        verbose: bool
    ) -> AnomalyExplanation:
        """Explain an equipment alarm."""
        from uuid import uuid4

        alarm_code = anomaly.context.get('alarm_code', 'UNKNOWN')
        machine = anomaly.source

        severity = SeverityLevel.CRITICAL if 'critical' in str(anomaly.context.get('severity', '')).lower() else SeverityLevel.MAJOR

        summary = f"Equipment alarm on {machine}: {alarm_code}"

        detailed = f"""
An alarm was triggered on {machine}.

**Alarm Code:** {alarm_code}
**Machine:** {machine}
**Status:** {anomaly.context.get('machine_status', 'N/A')}

This alarm requires immediate attention to prevent equipment damage
or production quality issues.
"""

        return AnomalyExplanation(
            anomaly_id=str(uuid4()),
            anomaly_type=AnomalyType.EQUIPMENT_ALARM,
            severity=severity,
            timestamp=anomaly.timestamp,
            summary=summary,
            detailed_explanation=detailed.strip(),
            corrective_actions=[
                CorrectiveAction(
                    description="Stop production and investigate alarm",
                    priority="immediate",
                    action_type="investigate",
                    requires_approval=True,
                ),
            ],
            production_impact="Machine may be unavailable",
            confidence_score=0.9,
            needs_human_review=True,
        )

    async def _explain_schedule_deviation(
        self,
        anomaly: AnomalyData,
        verbose: bool
    ) -> AnomalyExplanation:
        """Explain a schedule deviation."""
        from uuid import uuid4

        deviation_type = anomaly.context.get('deviation_type', 'delay')
        order_id = anomaly.context.get('order_id', 'N/A')
        hours_late = anomaly.context.get('hours_late', 0)

        severity = SeverityLevel.MAJOR if hours_late > 24 else SeverityLevel.MINOR

        summary = f"Schedule deviation: Order {order_id} is {hours_late:.1f} hours behind"

        detailed = f"""
A schedule deviation has been detected for order {order_id}.

**Deviation Type:** {deviation_type}
**Hours Behind Schedule:** {hours_late:.1f}
**Original Due Date:** {anomaly.context.get('due_date', 'N/A')}
**Current Status:** {anomaly.context.get('status', 'N/A')}

This may impact customer delivery commitments and downstream operations.
"""

        return AnomalyExplanation(
            anomaly_id=str(uuid4()),
            anomaly_type=AnomalyType.SCHEDULE_DEVIATION,
            severity=severity,
            timestamp=anomaly.timestamp,
            summary=summary,
            detailed_explanation=detailed.strip(),
            corrective_actions=[
                CorrectiveAction(
                    description="Evaluate expediting options",
                    priority="short-term",
                    action_type="adjust",
                ),
                CorrectiveAction(
                    description="Consider schedule reoptimization",
                    priority="short-term",
                    action_type="adjust",
                ),
            ],
            production_impact=f"Order {order_id} may miss customer delivery",
            confidence_score=0.95,
            needs_human_review=hours_late > 24,
        )

    async def _explain_process_drift(
        self,
        anomaly: AnomalyData,
        verbose: bool
    ) -> AnomalyExplanation:
        """Explain process drift."""
        from uuid import uuid4

        metric = anomaly.metric_name or 'process parameter'
        drift_direction = "increasing" if anomaly.context.get('trend', 0) > 0 else "decreasing"

        summary = f"Process drift detected: {metric} is {drift_direction}"

        detailed = f"""
A gradual drift has been detected in {metric}.

**Metric:** {metric}
**Trend Direction:** {drift_direction}
**Current Value:** {anomaly.metric_value}
**Rate of Change:** {anomaly.context.get('rate_of_change', 'N/A')}

Process drift often indicates equipment wear, material changes, or
environmental factors affecting production.
"""

        return AnomalyExplanation(
            anomaly_id=str(uuid4()),
            anomaly_type=AnomalyType.PROCESS_DRIFT,
            severity=SeverityLevel.MINOR,
            timestamp=anomaly.timestamp,
            summary=summary,
            detailed_explanation=detailed.strip(),
            corrective_actions=[
                CorrectiveAction(
                    description="Monitor trend closely",
                    priority="short-term",
                    action_type="investigate",
                ),
                CorrectiveAction(
                    description="Plan corrective adjustment",
                    priority="short-term",
                    action_type="adjust",
                ),
            ],
            preventive_measures=[
                "Implement automatic drift compensation",
                "Schedule process recalibration",
            ],
            confidence_score=0.8,
            needs_human_review=False,
        )

    async def _explain_generic(
        self,
        anomaly: AnomalyData,
        verbose: bool
    ) -> AnomalyExplanation:
        """Generic anomaly explanation."""
        from uuid import uuid4

        return AnomalyExplanation(
            anomaly_id=str(uuid4()),
            anomaly_type=anomaly.anomaly_type,
            severity=SeverityLevel.INFORMATIONAL,
            timestamp=anomaly.timestamp,
            summary=f"Anomaly detected: {anomaly.anomaly_type.value}",
            detailed_explanation=f"An anomaly of type {anomaly.anomaly_type.value} was detected from {anomaly.source}. Investigation is recommended.",
            corrective_actions=[
                CorrectiveAction(
                    description="Investigate anomaly cause",
                    priority="short-term",
                    action_type="investigate",
                ),
            ],
            confidence_score=0.5,
            needs_human_review=True,
        )

    async def batch_explain(
        self,
        anomalies: List[AnomalyData]
    ) -> List[AnomalyExplanation]:
        """Explain multiple anomalies."""
        explanations = []
        for anomaly in anomalies:
            explanation = await self.explain_anomaly(anomaly)
            explanations.append(explanation)
        return explanations

    def correlate_anomalies(
        self,
        explanations: List[AnomalyExplanation]
    ) -> Dict[str, Any]:
        """
        Find correlations between multiple anomalies.

        Identifies patterns and common causes across anomalies.
        """
        if len(explanations) < 2:
            return {"correlation_found": False}

        # Group by type
        by_type = {}
        for exp in explanations:
            by_type.setdefault(exp.anomaly_type.value, []).append(exp)

        # Find common root causes
        all_causes = []
        for exp in explanations:
            all_causes.extend([rc.description for rc in exp.root_causes])

        from collections import Counter
        cause_counts = Counter(all_causes)
        common_causes = [cause for cause, count in cause_counts.items() if count > 1]

        return {
            "correlation_found": len(common_causes) > 0,
            "anomaly_count": len(explanations),
            "types": list(by_type.keys()),
            "common_root_causes": common_causes,
            "recommendation": "Consider system-wide investigation" if common_causes else "Anomalies appear independent",
        }
