"""
CAM Feedback Loop Service - Defect-to-CAM Optimization

LEGO MCP World-Class Manufacturing System v6.0
Phase 18: AI CAM Copilot Feedback Loop

Connects quality inspection defects back to CAM parameter optimization.
Implements closed-loop learning from manufacturing outcomes.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class DefectCategory(Enum):
    """Categories of manufacturing defects."""
    DIMENSIONAL = "dimensional"
    SURFACE = "surface"
    STRUCTURAL = "structural"
    THERMAL = "thermal"
    MATERIAL = "material"


class DefectSeverity(Enum):
    """Severity levels for defects."""
    MINOR = "minor"      # Cosmetic, within tolerance
    MAJOR = "major"      # Functional impact, out of tolerance
    CRITICAL = "critical"  # Safety/structural failure


@dataclass
class DefectRecord:
    """Record of a detected defect."""
    defect_id: str
    timestamp: datetime
    work_center_id: str
    part_number: str
    defect_type: str
    category: DefectCategory
    severity: DefectSeverity
    measured_value: Optional[float] = None
    target_value: Optional[float] = None
    deviation: Optional[float] = None
    cam_recommendation_id: Optional[str] = None
    notes: str = ""
    image_path: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'defect_id': self.defect_id,
            'timestamp': self.timestamp.isoformat(),
            'work_center_id': self.work_center_id,
            'part_number': self.part_number,
            'defect_type': self.defect_type,
            'category': self.category.value,
            'severity': self.severity.value,
            'measured_value': self.measured_value,
            'target_value': self.target_value,
            'deviation': self.deviation,
            'cam_recommendation_id': self.cam_recommendation_id,
            'notes': self.notes,
            'image_path': self.image_path,
        }


@dataclass
class CAMCorrection:
    """Recommended correction to CAM parameters."""
    parameter: str
    current_value: float
    recommended_value: float
    change_percent: float
    confidence: float
    rationale: str

    def to_dict(self) -> Dict:
        return {
            'parameter': self.parameter,
            'current_value': self.current_value,
            'recommended_value': self.recommended_value,
            'change_percent': self.change_percent,
            'confidence': self.confidence,
            'rationale': self.rationale,
        }


@dataclass
class FeedbackAnalysis:
    """Result of analyzing defects for CAM corrections."""
    analysis_id: str
    timestamp: datetime
    defects_analyzed: int
    period_hours: int
    work_center_id: Optional[str]
    corrections: List[CAMCorrection]
    summary: str
    overall_confidence: float

    def to_dict(self) -> Dict:
        return {
            'analysis_id': self.analysis_id,
            'timestamp': self.timestamp.isoformat(),
            'defects_analyzed': self.defects_analyzed,
            'period_hours': self.period_hours,
            'work_center_id': self.work_center_id,
            'corrections': [c.to_dict() for c in self.corrections],
            'summary': self.summary,
            'overall_confidence': self.overall_confidence,
        }


class DefectCAMMapping:
    """
    Mapping between defect types and CAM parameter adjustments.
    Based on manufacturing engineering best practices.
    """

    MAPPINGS = {
        # Dimensional defects
        'undersized_stud': {
            'description': 'Stud diameter below specification',
            'category': DefectCategory.DIMENSIONAL,
            'root_cause': 'Excessive tool deflection or stepover',
            'adjustments': {
                'stepover_percent': {'change': -10, 'max': -20},
                'depth_of_cut_mm': {'change': -0.2, 'max': -0.5},
                'feed_rate_mm_min': {'change': -50, 'max': -100},
            },
        },
        'oversized_stud': {
            'description': 'Stud diameter above specification',
            'category': DefectCategory.DIMENSIONAL,
            'root_cause': 'Tool wear or insufficient material removal',
            'adjustments': {
                'stepover_percent': {'change': +5, 'max': +15},
                'feed_rate_mm_min': {'change': +25, 'max': +50},
            },
        },
        'undersized_tube': {
            'description': 'Anti-stud tube ID below specification',
            'category': DefectCategory.DIMENSIONAL,
            'root_cause': 'Tool runout or programming error',
            'adjustments': {
                'tool_diameter_compensation': {'change': +0.02, 'max': +0.05},
                'finish_passes': {'change': +1, 'max': +2},
            },
        },
        'wall_thickness_variation': {
            'description': 'Inconsistent wall thickness',
            'category': DefectCategory.DIMENSIONAL,
            'root_cause': 'Vibration or fixture instability',
            'adjustments': {
                'feed_rate_mm_min': {'change': -75, 'max': -150},
                'spindle_rpm': {'change': -1000, 'max': -3000},
            },
        },

        # Surface defects
        'rough_surface': {
            'description': 'Surface roughness exceeds specification',
            'category': DefectCategory.SURFACE,
            'root_cause': 'High feed rate or worn tool',
            'adjustments': {
                'stepover_percent': {'change': -15, 'max': -25},
                'feed_rate_mm_min': {'change': -100, 'max': -200},
                'spindle_rpm': {'change': +1000, 'max': +3000},
            },
        },
        'chatter_marks': {
            'description': 'Visible chatter marks on surface',
            'category': DefectCategory.SURFACE,
            'root_cause': 'Vibration from excessive depth of cut or speed',
            'adjustments': {
                'depth_of_cut_mm': {'change': -0.3, 'max': -0.8},
                'spindle_rpm': {'change': -500, 'max': -2000},
                'feed_rate_mm_min': {'change': -50, 'max': -100},
            },
        },
        'tool_marks': {
            'description': 'Visible tool path marks on surface',
            'category': DefectCategory.SURFACE,
            'root_cause': 'Large stepover or insufficient finish passes',
            'adjustments': {
                'stepover_percent': {'change': -10, 'max': -20},
                'finish_passes': {'change': +1, 'max': +2},
            },
        },
        'burrs': {
            'description': 'Material burrs on edges',
            'category': DefectCategory.SURFACE,
            'root_cause': 'Dull tool or incorrect cutting direction',
            'adjustments': {
                'spindle_rpm': {'change': +500, 'max': +1500},
                'feed_rate_mm_min': {'change': -25, 'max': -75},
            },
        },

        # Structural defects
        'cracking': {
            'description': 'Visible cracks in material',
            'category': DefectCategory.STRUCTURAL,
            'root_cause': 'Thermal stress or excessive cutting forces',
            'adjustments': {
                'depth_of_cut_mm': {'change': -0.5, 'max': -1.0},
                'feed_rate_mm_min': {'change': -100, 'max': -200},
                'coolant_flow': {'change': +20, 'max': +50},
            },
        },
        'delamination': {
            'description': 'Layer separation in material',
            'category': DefectCategory.STRUCTURAL,
            'root_cause': 'Thermal stress during machining',
            'adjustments': {
                'spindle_rpm': {'change': -1000, 'max': -3000},
                'coolant_flow': {'change': +30, 'max': +50},
            },
        },

        # Thermal defects
        'burn_marks': {
            'description': 'Discoloration from heat damage',
            'category': DefectCategory.THERMAL,
            'root_cause': 'Insufficient cooling or excessive speed',
            'adjustments': {
                'spindle_rpm': {'change': -2000, 'max': -5000},
                'feed_rate_mm_min': {'change': +50, 'max': +100},
                'coolant_flow': {'change': +25, 'max': +50},
            },
        },
        'melting': {
            'description': 'Material melting or deformation',
            'category': DefectCategory.THERMAL,
            'root_cause': 'Excessive heat generation',
            'adjustments': {
                'spindle_rpm': {'change': -3000, 'max': -6000},
                'feed_rate_mm_min': {'change': +100, 'max': +200},
                'depth_of_cut_mm': {'change': -0.5, 'max': -1.0},
            },
        },
    }

    @classmethod
    def get_mapping(cls, defect_type: str) -> Optional[Dict]:
        """Get the mapping for a specific defect type."""
        return cls.MAPPINGS.get(defect_type)

    @classmethod
    def get_all_defect_types(cls) -> List[str]:
        """Get all known defect types."""
        return list(cls.MAPPINGS.keys())

    @classmethod
    def get_defect_categories(cls) -> Dict[str, List[str]]:
        """Get defect types grouped by category."""
        categories = defaultdict(list)
        for defect_type, mapping in cls.MAPPINGS.items():
            cat = mapping['category'].value
            categories[cat].append(defect_type)
        return dict(categories)


class CAMFeedbackLoop:
    """
    Main service for CAM feedback loop.
    Analyzes defects and recommends CAM parameter adjustments.
    """

    def __init__(self, min_defects_for_analysis: int = 3):
        self.min_defects = min_defects_for_analysis
        self.defect_history: List[DefectRecord] = []
        self.correction_history: List[FeedbackAnalysis] = []
        self._analysis_counter = 0

    def record_defect(
        self,
        work_center_id: str,
        part_number: str,
        defect_type: str,
        severity: str = "minor",
        measured_value: Optional[float] = None,
        target_value: Optional[float] = None,
        cam_recommendation_id: Optional[str] = None,
        notes: str = "",
    ) -> DefectRecord:
        """
        Record a new defect from quality inspection.

        Args:
            work_center_id: ID of the work center that produced the defect
            part_number: Part number affected
            defect_type: Type of defect (from DefectCAMMapping)
            severity: 'minor', 'major', or 'critical'
            measured_value: Actual measured value
            target_value: Target specification value
            cam_recommendation_id: ID of CAM recommendation used (for tracking)
            notes: Additional notes

        Returns:
            The recorded defect
        """
        mapping = DefectCAMMapping.get_mapping(defect_type)
        category = mapping['category'] if mapping else DefectCategory.DIMENSIONAL

        deviation = None
        if measured_value is not None and target_value is not None:
            deviation = measured_value - target_value

        defect = DefectRecord(
            defect_id=f"DEF-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{len(self.defect_history):04d}",
            timestamp=datetime.utcnow(),
            work_center_id=work_center_id,
            part_number=part_number,
            defect_type=defect_type,
            category=category,
            severity=DefectSeverity(severity),
            measured_value=measured_value,
            target_value=target_value,
            deviation=deviation,
            cam_recommendation_id=cam_recommendation_id,
            notes=notes,
        )

        self.defect_history.append(defect)
        logger.info(f"Recorded defect: {defect.defect_id} - {defect_type} on {work_center_id}")

        return defect

    def analyze_defects_for_cam(
        self,
        work_center_id: Optional[str] = None,
        period_hours: int = 24,
        current_params: Optional[Dict[str, float]] = None,
    ) -> FeedbackAnalysis:
        """
        Analyze recent defects and recommend CAM parameter adjustments.

        Args:
            work_center_id: Filter by work center (None = all)
            period_hours: Look back period in hours
            current_params: Current CAM parameters for calculating adjustments

        Returns:
            FeedbackAnalysis with recommended corrections
        """
        cutoff = datetime.utcnow() - timedelta(hours=period_hours)

        # Filter defects
        defects = [
            d for d in self.defect_history
            if d.timestamp >= cutoff
            and (work_center_id is None or d.work_center_id == work_center_id)
        ]

        if not defects:
            return FeedbackAnalysis(
                analysis_id=self._next_analysis_id(),
                timestamp=datetime.utcnow(),
                defects_analyzed=0,
                period_hours=period_hours,
                work_center_id=work_center_id,
                corrections=[],
                summary="No defects found in the analysis period.",
                overall_confidence=1.0,
            )

        # Count defects by type
        defect_counts = defaultdict(int)
        severity_weights = defaultdict(float)

        for defect in defects:
            defect_counts[defect.defect_type] += 1
            weight = {'minor': 1.0, 'major': 2.0, 'critical': 5.0}[defect.severity.value]
            severity_weights[defect.defect_type] += weight

        # Generate corrections for significant defect patterns
        corrections = []
        current_params = current_params or self._get_default_params()

        for defect_type, count in defect_counts.items():
            if count >= self.min_defects:
                mapping = DefectCAMMapping.get_mapping(defect_type)
                if mapping:
                    severity_weight = severity_weights[defect_type] / count
                    corrections.extend(
                        self._generate_corrections(
                            defect_type=defect_type,
                            mapping=mapping,
                            count=count,
                            severity_weight=severity_weight,
                            current_params=current_params,
                        )
                    )

        # Consolidate overlapping corrections
        corrections = self._consolidate_corrections(corrections)

        # Calculate overall confidence
        total_defects = sum(defect_counts.values())
        overall_confidence = min(0.95, 0.5 + (total_defects / 20) * 0.45)

        # Generate summary
        top_defects = sorted(defect_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        summary_parts = [f"{count}x {dtype}" for dtype, count in top_defects]
        summary = f"Analyzed {len(defects)} defects. Top issues: {', '.join(summary_parts)}. " \
                  f"Recommended {len(corrections)} parameter adjustments."

        analysis = FeedbackAnalysis(
            analysis_id=self._next_analysis_id(),
            timestamp=datetime.utcnow(),
            defects_analyzed=len(defects),
            period_hours=period_hours,
            work_center_id=work_center_id,
            corrections=corrections,
            summary=summary,
            overall_confidence=overall_confidence,
        )

        self.correction_history.append(analysis)
        logger.info(f"Generated feedback analysis: {analysis.analysis_id} with {len(corrections)} corrections")

        return analysis

    def _generate_corrections(
        self,
        defect_type: str,
        mapping: Dict,
        count: int,
        severity_weight: float,
        current_params: Dict[str, float],
    ) -> List[CAMCorrection]:
        """Generate CAM corrections from defect mapping."""
        corrections = []

        for param, adjustment in mapping.get('adjustments', {}).items():
            if param not in current_params:
                continue

            current_value = current_params[param]
            base_change = adjustment['change']
            max_change = adjustment['max']

            # Scale change based on count and severity
            scale_factor = min(3.0, 1.0 + (count - self.min_defects) * 0.25 + (severity_weight - 1.0) * 0.5)
            scaled_change = base_change * scale_factor

            # Clamp to max
            if base_change > 0:
                scaled_change = min(scaled_change, max_change)
            else:
                scaled_change = max(scaled_change, max_change)

            recommended_value = current_value + scaled_change
            change_percent = (scaled_change / current_value) * 100 if current_value != 0 else 0

            # Confidence based on sample size and consistency
            confidence = min(0.95, 0.6 + (count / 10) * 0.2 + (severity_weight / 3) * 0.15)

            corrections.append(CAMCorrection(
                parameter=param,
                current_value=current_value,
                recommended_value=round(recommended_value, 3),
                change_percent=round(change_percent, 1),
                confidence=round(confidence, 2),
                rationale=f"Based on {count} occurrences of '{defect_type}'. {mapping['root_cause']}",
            ))

        return corrections

    def _consolidate_corrections(self, corrections: List[CAMCorrection]) -> List[CAMCorrection]:
        """Consolidate multiple corrections for the same parameter."""
        param_corrections = defaultdict(list)

        for corr in corrections:
            param_corrections[corr.parameter].append(corr)

        consolidated = []
        for param, corr_list in param_corrections.items():
            if len(corr_list) == 1:
                consolidated.append(corr_list[0])
            else:
                # Average weighted by confidence
                total_weight = sum(c.confidence for c in corr_list)
                weighted_change = sum(
                    (c.recommended_value - c.current_value) * c.confidence
                    for c in corr_list
                ) / total_weight if total_weight > 0 else 0

                current = corr_list[0].current_value
                recommended = current + weighted_change
                change_pct = (weighted_change / current * 100) if current != 0 else 0
                avg_confidence = total_weight / len(corr_list)

                rationales = [c.rationale for c in corr_list]
                combined_rationale = f"Multiple defect types affecting this parameter: {'; '.join(set(rationales))}"

                consolidated.append(CAMCorrection(
                    parameter=param,
                    current_value=current,
                    recommended_value=round(recommended, 3),
                    change_percent=round(change_pct, 1),
                    confidence=round(avg_confidence, 2),
                    rationale=combined_rationale,
                ))

        return sorted(consolidated, key=lambda c: c.confidence, reverse=True)

    def _get_default_params(self) -> Dict[str, float]:
        """Get default CAM parameters for reference."""
        return {
            'spindle_rpm': 15000,
            'feed_rate_mm_min': 500,
            'plunge_rate_mm_min': 150,
            'depth_of_cut_mm': 1.0,
            'stepover_percent': 40,
            'finish_passes': 1,
            'coolant_flow': 100,
            'tool_diameter_compensation': 0.0,
        }

    def _next_analysis_id(self) -> str:
        """Generate next analysis ID."""
        self._analysis_counter += 1
        return f"FA-{datetime.utcnow().strftime('%Y%m%d')}-{self._analysis_counter:04d}"

    def get_defect_statistics(
        self,
        work_center_id: Optional[str] = None,
        period_hours: int = 168,  # 1 week
    ) -> Dict[str, Any]:
        """Get defect statistics for reporting."""
        cutoff = datetime.utcnow() - timedelta(hours=period_hours)

        defects = [
            d for d in self.defect_history
            if d.timestamp >= cutoff
            and (work_center_id is None or d.work_center_id == work_center_id)
        ]

        by_type = defaultdict(int)
        by_category = defaultdict(int)
        by_severity = defaultdict(int)
        by_work_center = defaultdict(int)

        for defect in defects:
            by_type[defect.defect_type] += 1
            by_category[defect.category.value] += 1
            by_severity[defect.severity.value] += 1
            by_work_center[defect.work_center_id] += 1

        return {
            'period_hours': period_hours,
            'total_defects': len(defects),
            'by_type': dict(by_type),
            'by_category': dict(by_category),
            'by_severity': dict(by_severity),
            'by_work_center': dict(by_work_center),
            'defect_rate_per_hour': len(defects) / period_hours if period_hours > 0 else 0,
        }

    def clear_history(self, older_than_days: int = 30):
        """Clear old defect history."""
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        self.defect_history = [d for d in self.defect_history if d.timestamp >= cutoff]
        self.correction_history = [c for c in self.correction_history if c.timestamp >= cutoff]
        logger.info(f"Cleared history older than {older_than_days} days")


# Global instance
_feedback_loop: Optional[CAMFeedbackLoop] = None


def get_feedback_loop() -> CAMFeedbackLoop:
    """Get the global CAMFeedbackLoop instance."""
    global _feedback_loop
    if _feedback_loop is None:
        _feedback_loop = CAMFeedbackLoop()
    return _feedback_loop
