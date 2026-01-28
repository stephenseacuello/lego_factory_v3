"""
Layer Inspector - Computer Vision Quality Control

LegoMCP World-Class Manufacturing System v5.0
Phase 13: CV-Based Quality Control

Provides layer-by-layer analysis of 3D printed parts:
- Real-time layer height monitoring
- Extrusion width verification
- Layer adhesion assessment
- Z-offset calibration feedback
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum
import uuid


class LayerDefectType(Enum):
    """Types of layer defects detectable by CV."""
    UNDER_EXTRUSION = "under_extrusion"
    OVER_EXTRUSION = "over_extrusion"
    LAYER_SHIFT = "layer_shift"
    WARPING = "warping"
    STRINGING = "stringing"
    POOR_ADHESION = "poor_adhesion"
    Z_WOBBLE = "z_wobble"
    INCONSISTENT_WIDTH = "inconsistent_width"


@dataclass
class LayerMeasurement:
    """Measurement data for a single layer."""
    layer_number: int
    height_mm: float
    expected_height_mm: float
    width_mm: float
    expected_width_mm: float
    adhesion_score: float  # 0-100
    uniformity_score: float  # 0-100
    defects: List[LayerDefectType] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LayerAnalysisResult:
    """Complete analysis result for layer inspection."""
    analysis_id: str
    work_order_id: str
    total_layers: int
    layers_analyzed: int
    pass_rate: float
    average_height_deviation: float
    average_width_deviation: float
    defect_counts: Dict[str, int]
    recommendations: List[str]
    overall_grade: str  # A, B, C, D, F
    timestamp: datetime = field(default_factory=datetime.utcnow)


class LayerInspector:
    """
    Real-time layer-by-layer inspection using computer vision.

    Monitors each layer as it's printed and provides immediate
    feedback for quality control and process adjustment.
    """

    def __init__(self, camera_id: str = "default"):
        self.camera_id = camera_id
        self.layer_history: Dict[str, List[LayerMeasurement]] = {}
        self.calibration = {
            'height_tolerance_mm': 0.05,
            'width_tolerance_mm': 0.1,
            'min_adhesion_score': 70,
            'min_uniformity_score': 75,
        }

    def analyze_layer(
        self,
        work_order_id: str,
        layer_number: int,
        image_data: Optional[bytes] = None,
        expected_height: float = 0.2,
        expected_width: float = 0.4
    ) -> LayerMeasurement:
        """
        Analyze a single layer from camera image.

        In production, this would use CV models to extract measurements.
        Currently provides simulated analysis for demonstration.
        """
        import random

        # Simulate CV analysis (in production, use actual image processing)
        height_deviation = random.gauss(0, 0.02)
        width_deviation = random.gauss(0, 0.05)

        measured_height = expected_height + height_deviation
        measured_width = expected_width + width_deviation

        # Calculate scores
        adhesion_score = max(0, min(100, 85 + random.gauss(0, 10)))
        uniformity_score = max(0, min(100, 88 + random.gauss(0, 8)))

        # Detect defects based on measurements
        defects = []
        if height_deviation < -self.calibration['height_tolerance_mm']:
            defects.append(LayerDefectType.UNDER_EXTRUSION)
        if height_deviation > self.calibration['height_tolerance_mm']:
            defects.append(LayerDefectType.OVER_EXTRUSION)
        if abs(width_deviation) > self.calibration['width_tolerance_mm']:
            defects.append(LayerDefectType.INCONSISTENT_WIDTH)
        if adhesion_score < self.calibration['min_adhesion_score']:
            defects.append(LayerDefectType.POOR_ADHESION)

        measurement = LayerMeasurement(
            layer_number=layer_number,
            height_mm=measured_height,
            expected_height_mm=expected_height,
            width_mm=measured_width,
            expected_width_mm=expected_width,
            adhesion_score=adhesion_score,
            uniformity_score=uniformity_score,
            defects=defects,
        )

        # Store in history
        if work_order_id not in self.layer_history:
            self.layer_history[work_order_id] = []
        self.layer_history[work_order_id].append(measurement)

        return measurement

    def get_analysis_summary(self, work_order_id: str) -> LayerAnalysisResult:
        """Generate summary analysis for all inspected layers."""
        layers = self.layer_history.get(work_order_id, [])

        if not layers:
            return LayerAnalysisResult(
                analysis_id=str(uuid.uuid4()),
                work_order_id=work_order_id,
                total_layers=0,
                layers_analyzed=0,
                pass_rate=0.0,
                average_height_deviation=0.0,
                average_width_deviation=0.0,
                defect_counts={},
                recommendations=["No layers analyzed yet"],
                overall_grade="N/A",
            )

        # Calculate statistics
        passed_layers = sum(1 for l in layers if not l.defects)
        pass_rate = (passed_layers / len(layers)) * 100

        avg_height_dev = sum(
            abs(l.height_mm - l.expected_height_mm) for l in layers
        ) / len(layers)

        avg_width_dev = sum(
            abs(l.width_mm - l.expected_width_mm) for l in layers
        ) / len(layers)

        # Count defects by type
        defect_counts = {}
        for layer in layers:
            for defect in layer.defects:
                defect_counts[defect.value] = defect_counts.get(defect.value, 0) + 1

        # Generate recommendations
        recommendations = self._generate_recommendations(layers, defect_counts)

        # Calculate overall grade
        if pass_rate >= 95:
            grade = "A"
        elif pass_rate >= 85:
            grade = "B"
        elif pass_rate >= 75:
            grade = "C"
        elif pass_rate >= 60:
            grade = "D"
        else:
            grade = "F"

        return LayerAnalysisResult(
            analysis_id=str(uuid.uuid4()),
            work_order_id=work_order_id,
            total_layers=len(layers),
            layers_analyzed=len(layers),
            pass_rate=pass_rate,
            average_height_deviation=avg_height_dev,
            average_width_deviation=avg_width_dev,
            defect_counts=defect_counts,
            recommendations=recommendations,
            overall_grade=grade,
        )

    def _generate_recommendations(
        self,
        layers: List[LayerMeasurement],
        defect_counts: Dict[str, int]
    ) -> List[str]:
        """Generate actionable recommendations based on defects."""
        recommendations = []

        if defect_counts.get('under_extrusion', 0) > 2:
            recommendations.append(
                "Increase flow rate by 2-5% or check for partial nozzle clog"
            )

        if defect_counts.get('over_extrusion', 0) > 2:
            recommendations.append(
                "Decrease flow rate by 2-5% or verify filament diameter"
            )

        if defect_counts.get('layer_shift', 0) > 0:
            recommendations.append(
                "Check belt tension and stepper motor currents"
            )

        if defect_counts.get('poor_adhesion', 0) > 3:
            recommendations.append(
                "Increase bed temperature by 5°C or apply fresh adhesive"
            )

        if defect_counts.get('stringing', 0) > 5:
            recommendations.append(
                "Increase retraction distance or decrease nozzle temperature"
            )

        if not recommendations:
            recommendations.append("Print quality is within acceptable parameters")

        return recommendations

    def get_real_time_metrics(self, work_order_id: str) -> Dict:
        """Get real-time metrics for dashboard display."""
        layers = self.layer_history.get(work_order_id, [])

        if not layers:
            return {
                'current_layer': 0,
                'pass_rate': 0,
                'last_defect': None,
                'trend': 'unknown',
            }

        recent = layers[-10:] if len(layers) >= 10 else layers
        recent_pass_rate = sum(1 for l in recent if not l.defects) / len(recent) * 100

        earlier = layers[-20:-10] if len(layers) >= 20 else layers[:len(layers)//2]
        earlier_pass_rate = (
            sum(1 for l in earlier if not l.defects) / len(earlier) * 100
            if earlier else recent_pass_rate
        )

        if recent_pass_rate > earlier_pass_rate + 5:
            trend = 'improving'
        elif recent_pass_rate < earlier_pass_rate - 5:
            trend = 'declining'
        else:
            trend = 'stable'

        last_defect = None
        for layer in reversed(layers):
            if layer.defects:
                last_defect = {
                    'layer': layer.layer_number,
                    'type': layer.defects[0].value,
                }
                break

        return {
            'current_layer': layers[-1].layer_number,
            'pass_rate': recent_pass_rate,
            'last_defect': last_defect,
            'trend': trend,
            'adhesion_avg': sum(l.adhesion_score for l in recent) / len(recent),
            'uniformity_avg': sum(l.uniformity_score for l in recent) / len(recent),
        }


# Singleton instance
_layer_inspector: Optional[LayerInspector] = None


def get_layer_inspector() -> LayerInspector:
    """Get or create the layer inspector instance."""
    global _layer_inspector
    if _layer_inspector is None:
        _layer_inspector = LayerInspector()
    return _layer_inspector
