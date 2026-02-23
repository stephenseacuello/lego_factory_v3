"""
Detection Analyzer - Detection capability analysis.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI, Explainability, FMEA & HOQ
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DetectionMethod(Enum):
    """Types of detection methods."""
    VISUAL_INSPECTION = "visual_inspection"
    DIMENSIONAL_MEASUREMENT = "dimensional_measurement"
    AUTOMATED_VISION = "automated_vision"
    FORCE_TESTING = "force_testing"
    MATERIAL_TESTING = "material_testing"
    FUNCTIONAL_TEST = "functional_test"
    IN_PROCESS_MONITORING = "in_process_monitoring"
    STATISTICAL_CONTROL = "statistical_control"
    SENSOR_BASED = "sensor_based"
    NONE = "none"


class InspectionStage(Enum):
    """Stage where detection occurs."""
    DESIGN_REVIEW = "design_review"
    INCOMING_MATERIAL = "incoming_material"
    IN_PROCESS = "in_process"
    END_OF_LINE = "end_of_line"
    FINAL_INSPECTION = "final_inspection"
    CUSTOMER = "customer"


@dataclass
class DetectionControl:
    """Detection control definition."""
    control_id: str
    name: str
    method: DetectionMethod
    stage: InspectionStage
    detection_probability: float  # 0-1
    cost: float  # Relative cost
    cycle_time: float  # Time in seconds
    automation_level: float  # 0=manual, 1=fully automated
    failure_modes_detected: List[str]


@dataclass
class DetectionAnalysis:
    """Detection capability analysis result."""
    failure_mode: str
    detection_rating: int  # 1-10 FMEA scale
    detection_probability: float
    current_controls: List[DetectionControl]
    gaps: List[str]
    recommended_controls: List[DetectionControl]
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DetectionAnalyzer:
    """
    Detection capability analysis for FMEA.

    Features:
    - Control effectiveness evaluation
    - Detection gap analysis
    - Recommendation generation
    - LEGO-specific detection methods
    """

    def __init__(self):
        self._controls_library: Dict[str, DetectionControl] = {}
        self._failure_control_map: Dict[str, List[str]] = {}
        self._load_standard_controls()

    def _load_standard_controls(self) -> None:
        """Load standard detection controls for LEGO manufacturing."""
        # Visual inspection controls
        self._add_control(DetectionControl(
            control_id="DET-001",
            name="Visual surface inspection",
            method=DetectionMethod.VISUAL_INSPECTION,
            stage=InspectionStage.END_OF_LINE,
            detection_probability=0.7,
            cost=1.0,
            cycle_time=10.0,
            automation_level=0.0,
            failure_modes_detected=[
                "SRF-001", "SRF-002", "SRF-003",
                "color_defect", "surface_scratch"
            ]
        ))

        self._add_control(DetectionControl(
            control_id="DET-002",
            name="AI vision inspection",
            method=DetectionMethod.AUTOMATED_VISION,
            stage=InspectionStage.END_OF_LINE,
            detection_probability=0.95,
            cost=5.0,
            cycle_time=2.0,
            automation_level=1.0,
            failure_modes_detected=[
                "SRF-001", "SRF-002", "SRF-003",
                "DIM-001", "DIM-002", "DIM-003",
                "color_defect", "surface_defect"
            ]
        ))

        # Dimensional controls
        self._add_control(DetectionControl(
            control_id="DET-003",
            name="Caliper measurement",
            method=DetectionMethod.DIMENSIONAL_MEASUREMENT,
            stage=InspectionStage.END_OF_LINE,
            detection_probability=0.85,
            cost=2.0,
            cycle_time=30.0,
            automation_level=0.0,
            failure_modes_detected=[
                "DIM-001", "DIM-002", "DIM-003",
                "stud_diameter", "height_variation"
            ]
        ))

        self._add_control(DetectionControl(
            control_id="DET-004",
            name="CMM measurement",
            method=DetectionMethod.DIMENSIONAL_MEASUREMENT,
            stage=InspectionStage.FINAL_INSPECTION,
            detection_probability=0.99,
            cost=10.0,
            cycle_time=120.0,
            automation_level=0.5,
            failure_modes_detected=[
                "DIM-001", "DIM-002", "DIM-003",
                "all_dimensional"
            ]
        ))

        # Functional testing
        self._add_control(DetectionControl(
            control_id="DET-005",
            name="Clutch force test",
            method=DetectionMethod.FORCE_TESTING,
            stage=InspectionStage.END_OF_LINE,
            detection_probability=0.98,
            cost=3.0,
            cycle_time=15.0,
            automation_level=0.8,
            failure_modes_detected=[
                "FUN-001", "FUN-002",
                "clutch_power", "connection_strength"
            ]
        ))

        self._add_control(DetectionControl(
            control_id="DET-006",
            name="LEGO compatibility test",
            method=DetectionMethod.FUNCTIONAL_TEST,
            stage=InspectionStage.FINAL_INSPECTION,
            detection_probability=0.99,
            cost=4.0,
            cycle_time=60.0,
            automation_level=0.3,
            failure_modes_detected=[
                "FUN-001", "FUN-002",
                "DIM-001", "DIM-002",
                "lego_compatibility"
            ]
        ))

        # In-process monitoring
        self._add_control(DetectionControl(
            control_id="DET-007",
            name="Print temperature monitoring",
            method=DetectionMethod.IN_PROCESS_MONITORING,
            stage=InspectionStage.IN_PROCESS,
            detection_probability=0.9,
            cost=2.0,
            cycle_time=0.0,  # Continuous
            automation_level=1.0,
            failure_modes_detected=[
                "THM-001", "STR-001", "STR-002",
                "temperature_deviation"
            ]
        ))

        self._add_control(DetectionControl(
            control_id="DET-008",
            name="Layer camera monitoring",
            method=DetectionMethod.IN_PROCESS_MONITORING,
            stage=InspectionStage.IN_PROCESS,
            detection_probability=0.85,
            cost=6.0,
            cycle_time=0.0,
            automation_level=1.0,
            failure_modes_detected=[
                "STR-001", "SRF-001",
                "layer_defect", "stringing"
            ]
        ))

        # Statistical process control
        self._add_control(DetectionControl(
            control_id="DET-009",
            name="SPC monitoring",
            method=DetectionMethod.STATISTICAL_CONTROL,
            stage=InspectionStage.IN_PROCESS,
            detection_probability=0.8,
            cost=3.0,
            cycle_time=0.0,
            automation_level=0.9,
            failure_modes_detected=[
                "process_drift", "trend_detection"
            ]
        ))

        # Material testing
        self._add_control(DetectionControl(
            control_id="DET-010",
            name="Incoming material inspection",
            method=DetectionMethod.MATERIAL_TESTING,
            stage=InspectionStage.INCOMING_MATERIAL,
            detection_probability=0.9,
            cost=4.0,
            cycle_time=300.0,
            automation_level=0.5,
            failure_modes_detected=[
                "MAT-001", "MAT-002",
                "material_defect", "contamination"
            ]
        ))

        logger.info(f"Loaded {len(self._controls_library)} detection controls")

    def _add_control(self, control: DetectionControl) -> None:
        """Add control to library."""
        self._controls_library[control.control_id] = control

        # Map failure modes to controls
        for fm in control.failure_modes_detected:
            if fm not in self._failure_control_map:
                self._failure_control_map[fm] = []
            self._failure_control_map[fm].append(control.control_id)

    def analyze(self,
                failure_mode: str,
                current_control_ids: Optional[List[str]] = None) -> DetectionAnalysis:
        """
        Analyze detection capability for failure mode.

        Args:
            failure_mode: Failure mode identifier
            current_control_ids: IDs of currently implemented controls

        Returns:
            Detection capability analysis
        """
        current_control_ids = current_control_ids or []

        # Get current controls
        current_controls = [
            self._controls_library[cid]
            for cid in current_control_ids
            if cid in self._controls_library
        ]

        # Calculate combined detection probability
        detection_probability = self._calculate_combined_detection(
            current_controls, failure_mode
        )

        # Convert to FMEA rating
        detection_rating = self._probability_to_rating(detection_probability)

        # Find gaps
        gaps = self._identify_gaps(failure_mode, current_controls)

        # Get recommended additional controls
        recommended = self._recommend_controls(failure_mode, current_controls)

        return DetectionAnalysis(
            failure_mode=failure_mode,
            detection_rating=detection_rating,
            detection_probability=detection_probability,
            current_controls=current_controls,
            gaps=gaps,
            recommended_controls=recommended,
            confidence=self._calculate_confidence(current_controls)
        )

    def _calculate_combined_detection(self,
                                      controls: List[DetectionControl],
                                      failure_mode: str) -> float:
        """
        Calculate combined detection probability.

        Uses formula: P(detect) = 1 - product(1 - P_i) for independent controls
        """
        if not controls:
            return 0.0

        # Filter controls that can detect this failure mode
        relevant_controls = [
            c for c in controls
            if failure_mode in c.failure_modes_detected or
               any(failure_mode.startswith(fm.split('-')[0]) for fm in c.failure_modes_detected)
        ]

        if not relevant_controls:
            return 0.1  # Some chance of detection even without specific control

        # Calculate combined probability
        non_detection = 1.0
        for control in relevant_controls:
            non_detection *= (1 - control.detection_probability)

        return 1.0 - non_detection

    def _probability_to_rating(self, probability: float) -> int:
        """
        Convert detection probability to FMEA rating.

        AIAG FMEA Detection ratings:
        1: Almost certain detection (>99%)
        2: Very high detection (95-99%)
        3: High detection (90-95%)
        4: Moderately high (85-90%)
        5: Moderate (80-85%)
        6: Low (70-80%)
        7: Very low (60-70%)
        8: Remote (40-60%)
        9: Very remote (20-40%)
        10: No detection (<20%)
        """
        if probability >= 0.99:
            return 1
        elif probability >= 0.95:
            return 2
        elif probability >= 0.90:
            return 3
        elif probability >= 0.85:
            return 4
        elif probability >= 0.80:
            return 5
        elif probability >= 0.70:
            return 6
        elif probability >= 0.60:
            return 7
        elif probability >= 0.40:
            return 8
        elif probability >= 0.20:
            return 9
        else:
            return 10

    def _identify_gaps(self,
                      failure_mode: str,
                      current_controls: List[DetectionControl]) -> List[str]:
        """Identify detection gaps."""
        gaps = []

        # Check coverage by stage
        stages_covered = {c.stage for c in current_controls}
        critical_stages = {
            InspectionStage.IN_PROCESS,
            InspectionStage.END_OF_LINE
        }
        missing_stages = critical_stages - stages_covered
        for stage in missing_stages:
            gaps.append(f"No detection at {stage.value} stage")

        # Check method diversity
        methods_used = {c.method for c in current_controls}
        if DetectionMethod.AUTOMATED_VISION not in methods_used:
            gaps.append("No automated vision inspection")
        if DetectionMethod.IN_PROCESS_MONITORING not in methods_used:
            gaps.append("No in-process monitoring")

        # Check if failure mode has specific controls
        fm_prefix = failure_mode.split('-')[0] if '-' in failure_mode else failure_mode
        has_specific = any(
            failure_mode in c.failure_modes_detected or
            any(fm.startswith(fm_prefix) for fm in c.failure_modes_detected)
            for c in current_controls
        )
        if not has_specific:
            gaps.append(f"No specific control for {failure_mode}")

        return gaps

    def _recommend_controls(self,
                           failure_mode: str,
                           current_controls: List[DetectionControl]) -> List[DetectionControl]:
        """Recommend additional controls."""
        current_ids = {c.control_id for c in current_controls}
        recommendations = []

        # Find controls that can detect this failure mode
        relevant_control_ids = self._failure_control_map.get(failure_mode, [])

        # Also check by prefix
        fm_prefix = failure_mode.split('-')[0] if '-' in failure_mode else failure_mode
        for fm, control_ids in self._failure_control_map.items():
            if fm.startswith(fm_prefix):
                relevant_control_ids.extend(control_ids)

        relevant_control_ids = list(set(relevant_control_ids))

        # Recommend controls not currently implemented
        for cid in relevant_control_ids:
            if cid not in current_ids:
                control = self._controls_library.get(cid)
                if control:
                    recommendations.append(control)

        # Sort by detection probability (highest first)
        recommendations.sort(key=lambda c: c.detection_probability, reverse=True)

        return recommendations[:3]  # Top 3 recommendations

    def _calculate_confidence(self, controls: List[DetectionControl]) -> float:
        """Calculate confidence in detection analysis."""
        if not controls:
            return 0.4

        # Higher automation = higher confidence
        avg_automation = sum(c.automation_level for c in controls) / len(controls)

        # More controls = higher confidence
        control_bonus = min(0.2, len(controls) * 0.05)

        return min(0.95, 0.5 + avg_automation * 0.3 + control_bonus)

    def get_control(self, control_id: str) -> Optional[DetectionControl]:
        """Get control by ID."""
        return self._controls_library.get(control_id)

    def get_controls_by_stage(self, stage: InspectionStage) -> List[DetectionControl]:
        """Get all controls for a specific stage."""
        return [c for c in self._controls_library.values() if c.stage == stage]

    def get_controls_by_method(self, method: DetectionMethod) -> List[DetectionControl]:
        """Get all controls using specific method."""
        return [c for c in self._controls_library.values() if c.method == method]

    def add_custom_control(self, control: DetectionControl) -> None:
        """Add custom detection control."""
        self._add_control(control)
        logger.info(f"Added custom control: {control.control_id}")

    def calculate_inspection_cost(self,
                                  control_ids: List[str],
                                  units_per_day: int = 100) -> Dict[str, float]:
        """Calculate inspection costs."""
        total_cost = 0.0
        total_time = 0.0

        for cid in control_ids:
            control = self._controls_library.get(cid)
            if control:
                total_cost += control.cost
                total_time += control.cycle_time

        return {
            'relative_cost_per_unit': total_cost,
            'time_per_unit_seconds': total_time,
            'daily_inspection_time_hours': (total_time * units_per_day) / 3600
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        return {
            'total_controls': len(self._controls_library),
            'by_method': {
                method.value: len([c for c in self._controls_library.values()
                                  if c.method == method])
                for method in DetectionMethod
            },
            'by_stage': {
                stage.value: len([c for c in self._controls_library.values()
                                 if c.stage == stage])
                for stage in InspectionStage
            }
        }
