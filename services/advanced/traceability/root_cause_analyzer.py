"""
Root Cause Analyzer - Digital Thread Analysis

LegoMCP World-Class Manufacturing System v5.0
Phase 15: Digital Thread & Traceability

Provides root cause analysis capabilities:
- Defect-to-source tracing
- Process parameter correlation
- Material batch impact analysis
- Equipment contribution analysis
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import uuid


class RootCauseCategory(Enum):
    """Categories of root causes."""
    MATERIAL = "material"
    EQUIPMENT = "equipment"
    PROCESS = "process"
    ENVIRONMENT = "environment"
    OPERATOR = "operator"
    DESIGN = "design"
    UNKNOWN = "unknown"


class ConfidenceLevel(Enum):
    """Confidence levels for root cause identification."""
    HIGH = "high"      # > 80% correlation
    MEDIUM = "medium"  # 50-80% correlation
    LOW = "low"        # 20-50% correlation
    UNCERTAIN = "uncertain"  # < 20%


@dataclass
class ContributingFactor:
    """A factor contributing to the defect."""
    factor_id: str
    category: RootCauseCategory
    name: str
    description: str
    correlation_score: float  # 0-1
    evidence: List[str]
    affected_parts: int
    confidence: ConfidenceLevel


@dataclass
class RootCauseAnalysis:
    """Complete root cause analysis result."""
    analysis_id: str
    defect_type: str
    defect_count: int
    affected_work_orders: List[str]
    primary_cause: Optional[ContributingFactor]
    contributing_factors: List[ContributingFactor]
    timeline: List[Dict[str, Any]]
    recommendations: List[str]
    estimated_impact: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RootCauseAnalyzer:
    """
    Analyzes manufacturing defects to identify root causes.

    Uses digital thread data to trace defects back through
    the manufacturing process to identify causal factors.
    """

    def __init__(self):
        self.analysis_history: Dict[str, RootCauseAnalysis] = {}
        self.correlation_thresholds = {
            'high': 0.8,
            'medium': 0.5,
            'low': 0.2,
        }

    def analyze_defect(
        self,
        defect_type: str,
        affected_parts: List[str],
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> RootCauseAnalysis:
        """
        Perform root cause analysis for a defect pattern.

        Args:
            defect_type: Type of defect to analyze
            affected_parts: List of affected part IDs
            time_range: Optional time range to analyze

        Returns:
            Complete root cause analysis
        """
        # Gather evidence from digital thread
        factors = self._identify_contributing_factors(defect_type, affected_parts)

        # Rank by correlation score
        factors.sort(key=lambda f: f.correlation_score, reverse=True)

        primary_cause = factors[0] if factors else None

        # Build timeline
        timeline = self._build_timeline(affected_parts, time_range)

        # Generate recommendations
        recommendations = self._generate_recommendations(primary_cause, factors)

        # Estimate impact
        impact = self._estimate_impact(defect_type, len(affected_parts))

        # Get work orders
        work_orders = self._get_affected_work_orders(affected_parts)

        analysis = RootCauseAnalysis(
            analysis_id=str(uuid.uuid4()),
            defect_type=defect_type,
            defect_count=len(affected_parts),
            affected_work_orders=work_orders,
            primary_cause=primary_cause,
            contributing_factors=factors,
            timeline=timeline,
            recommendations=recommendations,
            estimated_impact=impact,
        )

        self.analysis_history[analysis.analysis_id] = analysis
        return analysis

    def _identify_contributing_factors(
        self,
        defect_type: str,
        affected_parts: List[str]
    ) -> List[ContributingFactor]:
        """Identify factors contributing to the defect."""
        import random

        factors = []

        # Simulate analysis - in production would query digital thread
        if defect_type in ['dimensional_error', 'tolerance_failure']:
            factors.append(ContributingFactor(
                factor_id=str(uuid.uuid4()),
                category=RootCauseCategory.EQUIPMENT,
                name="Printer Calibration Drift",
                description="X-axis steps/mm calibration drifted by 0.5%",
                correlation_score=0.85,
                evidence=[
                    "Calibration last performed 45 days ago",
                    "Similar defects on same printer",
                    "No defects on other printers same period",
                ],
                affected_parts=len(affected_parts),
                confidence=ConfidenceLevel.HIGH,
            ))

        if defect_type in ['adhesion_failure', 'warping']:
            factors.append(ContributingFactor(
                factor_id=str(uuid.uuid4()),
                category=RootCauseCategory.MATERIAL,
                name="Filament Moisture Absorption",
                description="Filament batch showed elevated moisture content",
                correlation_score=0.72,
                evidence=[
                    "Batch stored 14 days before use",
                    "Humidity sensor showed 65% RH in storage",
                    "Same batch linked to 80% of failures",
                ],
                affected_parts=int(len(affected_parts) * 0.8),
                confidence=ConfidenceLevel.MEDIUM,
            ))

        if defect_type in ['surface_defect', 'layer_adhesion']:
            factors.append(ContributingFactor(
                factor_id=str(uuid.uuid4()),
                category=RootCauseCategory.PROCESS,
                name="Temperature Profile Variation",
                description="Nozzle temperature varied ±5°C from setpoint",
                correlation_score=0.65,
                evidence=[
                    "PID tuning not performed after heater replacement",
                    "Temperature oscillation detected in logs",
                ],
                affected_parts=int(len(affected_parts) * 0.6),
                confidence=ConfidenceLevel.MEDIUM,
            ))

        # Add environment factor
        if random.random() > 0.5:
            factors.append(ContributingFactor(
                factor_id=str(uuid.uuid4()),
                category=RootCauseCategory.ENVIRONMENT,
                name="Ambient Temperature Fluctuation",
                description="Room temperature dropped 8°C overnight",
                correlation_score=0.35,
                evidence=[
                    "HVAC system cycling detected",
                    "Defects concentrated in morning shift",
                ],
                affected_parts=int(len(affected_parts) * 0.3),
                confidence=ConfidenceLevel.LOW,
            ))

        return factors

    def _build_timeline(
        self,
        affected_parts: List[str],
        time_range: Optional[Tuple[datetime, datetime]]
    ) -> List[Dict[str, Any]]:
        """Build timeline of events leading to defects."""
        now = datetime.utcnow()
        start = time_range[0] if time_range else now - timedelta(days=7)

        timeline = [
            {
                'timestamp': (start - timedelta(days=5)).isoformat(),
                'event': 'Material batch received',
                'type': 'material',
                'relevance': 'high',
            },
            {
                'timestamp': (start - timedelta(days=2)).isoformat(),
                'event': 'Printer maintenance performed',
                'type': 'equipment',
                'relevance': 'medium',
            },
            {
                'timestamp': start.isoformat(),
                'event': 'First defective part detected',
                'type': 'quality',
                'relevance': 'critical',
            },
            {
                'timestamp': (start + timedelta(hours=4)).isoformat(),
                'event': 'Defect rate exceeded threshold',
                'type': 'quality',
                'relevance': 'critical',
            },
            {
                'timestamp': now.isoformat(),
                'event': 'Root cause analysis initiated',
                'type': 'investigation',
                'relevance': 'high',
            },
        ]

        return timeline

    def _generate_recommendations(
        self,
        primary_cause: Optional[ContributingFactor],
        factors: List[ContributingFactor]
    ) -> List[str]:
        """Generate corrective action recommendations."""
        recommendations = []

        if not primary_cause:
            return ["Insufficient data for recommendations - gather more evidence"]

        category = primary_cause.category

        if category == RootCauseCategory.EQUIPMENT:
            recommendations.extend([
                "Perform full printer calibration (XYZ steps, extruder, bed leveling)",
                "Implement weekly calibration verification checks",
                "Add calibration drift monitoring to predictive maintenance",
            ])

        elif category == RootCauseCategory.MATERIAL:
            recommendations.extend([
                "Quarantine affected material batch",
                "Implement incoming moisture testing for filament",
                "Reduce maximum storage time to 7 days",
                "Install dehumidifier in material storage area",
            ])

        elif category == RootCauseCategory.PROCESS:
            recommendations.extend([
                "Re-tune PID parameters for temperature control",
                "Add real-time temperature monitoring alerts",
                "Review and update process parameters",
            ])

        elif category == RootCauseCategory.ENVIRONMENT:
            recommendations.extend([
                "Install enclosure with temperature control",
                "Add environmental monitoring and alerting",
                "Schedule critical prints during stable conditions",
            ])

        # Add secondary recommendations
        for factor in factors[1:3]:
            if factor.correlation_score > 0.3:
                recommendations.append(
                    f"Address secondary factor: {factor.name}"
                )

        return recommendations

    def _estimate_impact(self, defect_type: str, defect_count: int) -> Dict[str, Any]:
        """Estimate business impact of defects."""
        cost_per_part = 2.50  # Estimated material + time cost
        rework_rate = 0.3
        scrap_rate = 0.7

        return {
            'total_defects': defect_count,
            'estimated_scrap_cost': defect_count * scrap_rate * cost_per_part,
            'estimated_rework_cost': defect_count * rework_rate * cost_per_part * 0.5,
            'production_delay_hours': defect_count * 0.25,
            'customer_impact': 'medium' if defect_count > 10 else 'low',
            'quality_score_impact': -0.5 * (defect_count / 100),
        }

    def _get_affected_work_orders(self, affected_parts: List[str]) -> List[str]:
        """Get work orders associated with affected parts."""
        # Simulate - in production would query actual data
        return [f"WO-{i:04d}" for i in range(1, min(len(affected_parts), 5) + 1)]

    def get_analysis_summary(self, analysis_id: str) -> Optional[Dict]:
        """Get summary of a root cause analysis."""
        analysis = self.analysis_history.get(analysis_id)
        if not analysis:
            return None

        return {
            'analysis_id': analysis.analysis_id,
            'defect_type': analysis.defect_type,
            'primary_cause': {
                'name': analysis.primary_cause.name,
                'category': analysis.primary_cause.category.value,
                'confidence': analysis.primary_cause.confidence.value,
            } if analysis.primary_cause else None,
            'factors_identified': len(analysis.contributing_factors),
            'recommendations_count': len(analysis.recommendations),
            'estimated_cost': analysis.estimated_impact.get('estimated_scrap_cost', 0),
        }


# Singleton instance
_root_cause_analyzer: Optional[RootCauseAnalyzer] = None


def get_root_cause_analyzer() -> RootCauseAnalyzer:
    """Get or create the root cause analyzer instance."""
    global _root_cause_analyzer
    if _root_cause_analyzer is None:
        _root_cause_analyzer = RootCauseAnalyzer()
    return _root_cause_analyzer
