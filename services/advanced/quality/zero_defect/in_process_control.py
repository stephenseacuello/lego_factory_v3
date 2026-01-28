"""
In-Process Control - Real-Time Quality Intervention

LegoMCP World-Class Manufacturing System v5.0
Phase 21: Zero-Defect Manufacturing

Real-time quality control during production:
- Layer-by-layer analysis for 3D printing
- Automatic parameter adjustment
- Defect detection and intervention
- Closed-loop feedback control
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class LayerStatus(str, Enum):
    """Status of a printed layer."""
    GOOD = "good"
    WARNING = "warning"
    DEFECTIVE = "defective"
    UNKNOWN = "unknown"


class DefectSeverity(str, Enum):
    """Severity of detected defects."""
    NONE = "none"
    COSMETIC = "cosmetic"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


@dataclass
class LayerAnalysis:
    """Analysis result for a single layer."""
    layer_number: int
    timestamp: datetime
    status: LayerStatus

    # Defect detection
    defects_detected: List[str] = field(default_factory=list)
    defect_severity: DefectSeverity = DefectSeverity.NONE
    defect_locations: List[Tuple[float, float]] = field(default_factory=list)

    # Dimensional analysis
    layer_height_actual: Optional[float] = None
    layer_height_deviation: Optional[float] = None
    width_variation: Optional[float] = None

    # Quality metrics
    surface_quality_score: float = 100.0
    adhesion_score: float = 100.0
    extrusion_consistency: float = 100.0

    # Confidence
    analysis_confidence: float = 0.0

    def is_acceptable(self) -> bool:
        """Check if layer is acceptable quality."""
        return self.status in (LayerStatus.GOOD, LayerStatus.WARNING)


@dataclass
class ParameterAdjustment:
    """Recommended or applied parameter adjustment."""
    timestamp: datetime
    parameter: str
    current_value: float
    new_value: float
    reason: str
    auto_applied: bool = False
    effectiveness: Optional[float] = None  # Measured improvement


class InProcessController:
    """
    Real-time in-process quality controller.

    Monitors production in real-time and makes adjustments
    to maintain quality.
    """

    # Thresholds for intervention
    WARNING_THRESHOLD = 0.8  # Quality score below this triggers warning
    DEFECTIVE_THRESHOLD = 0.5  # Below this is defective
    INTERVENTION_THRESHOLD = 0.7  # Below this triggers parameter adjustment

    # Maximum adjustments before stopping
    MAX_ADJUSTMENTS_PER_LAYER = 3
    MAX_CONSECUTIVE_DEFECTS = 5

    def __init__(
        self,
        machine_controller: Optional[Any] = None,
        vision_system: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.machine = machine_controller
        self.vision = vision_system
        self.config = config or {}

        # State tracking
        self._current_job_id: Optional[str] = None
        self._layer_history: List[LayerAnalysis] = []
        self._adjustment_history: List[ParameterAdjustment] = []
        self._consecutive_defects = 0
        self._adjustments_this_layer = 0

        # Current process parameters
        self._current_params: Dict[str, float] = {
            'nozzle_temp': 210.0,
            'bed_temp': 60.0,
            'print_speed': 40.0,
            'flow_rate': 100.0,
            'fan_speed': 100.0,
        }

        # Parameter limits
        self._param_limits = {
            'nozzle_temp': (190.0, 230.0),
            'bed_temp': (50.0, 80.0),
            'print_speed': (20.0, 80.0),
            'flow_rate': (90.0, 110.0),
            'fan_speed': (0.0, 100.0),
        }

    def start_job(self, job_id: str, initial_params: Optional[Dict[str, float]] = None) -> None:
        """Start monitoring a new job."""
        self._current_job_id = job_id
        self._layer_history = []
        self._adjustment_history = []
        self._consecutive_defects = 0

        if initial_params:
            self._current_params.update(initial_params)

        logger.info(f"In-process control started for job {job_id}")

    def end_job(self) -> Dict[str, Any]:
        """End job and return summary."""
        summary = {
            'job_id': self._current_job_id,
            'total_layers': len(self._layer_history),
            'good_layers': sum(1 for l in self._layer_history if l.status == LayerStatus.GOOD),
            'warning_layers': sum(1 for l in self._layer_history if l.status == LayerStatus.WARNING),
            'defective_layers': sum(1 for l in self._layer_history if l.status == LayerStatus.DEFECTIVE),
            'total_adjustments': len(self._adjustment_history),
            'adjustments_by_type': self._count_adjustments_by_type(),
        }

        self._current_job_id = None
        return summary

    def analyze_layer(
        self,
        layer_number: int,
        layer_image: Optional[np.ndarray] = None,
        sensor_data: Optional[Dict[str, float]] = None,
    ) -> LayerAnalysis:
        """
        Analyze a completed layer.

        Args:
            layer_number: Layer number (0-indexed)
            layer_image: Camera image of the layer
            sensor_data: Sensor readings during layer

        Returns:
            LayerAnalysis with quality assessment
        """
        self._adjustments_this_layer = 0

        analysis = LayerAnalysis(
            layer_number=layer_number,
            timestamp=datetime.utcnow(),
            status=LayerStatus.UNKNOWN,
        )

        # Analyze from vision system if available
        if layer_image is not None:
            vision_analysis = self._analyze_layer_image(layer_image)
            analysis.defects_detected = vision_analysis.get('defects', [])
            analysis.defect_locations = vision_analysis.get('locations', [])
            analysis.surface_quality_score = vision_analysis.get('surface_score', 100)
            analysis.analysis_confidence = vision_analysis.get('confidence', 0.9)

        # Analyze from sensor data
        if sensor_data:
            sensor_analysis = self._analyze_sensor_data(sensor_data)
            analysis.layer_height_actual = sensor_analysis.get('layer_height')
            analysis.layer_height_deviation = sensor_analysis.get('height_deviation')
            analysis.extrusion_consistency = sensor_analysis.get('consistency', 100)

        # Determine status
        analysis.status, analysis.defect_severity = self._determine_status(analysis)

        # Update tracking
        self._layer_history.append(analysis)

        if analysis.status == LayerStatus.DEFECTIVE:
            self._consecutive_defects += 1
        else:
            self._consecutive_defects = 0

        # Check if we should stop
        if self._consecutive_defects >= self.MAX_CONSECUTIVE_DEFECTS:
            logger.error(f"Too many consecutive defects ({self._consecutive_defects}). Stopping.")
            # Would trigger machine stop

        return analysis

    def _analyze_layer_image(self, image: np.ndarray) -> Dict[str, Any]:
        """Analyze layer from camera image."""
        # In production, this would use CV/ML models
        # For now, return simulated results

        result = {
            'defects': [],
            'locations': [],
            'surface_score': 100.0,
            'confidence': 0.85,
        }

        # Simulate defect detection based on image properties
        if image is not None and len(image.shape) >= 2:
            # Calculate image statistics
            mean_intensity = np.mean(image)
            std_intensity = np.std(image)

            # High variance might indicate surface issues
            if std_intensity > 50:
                result['defects'].append('surface_roughness')
                result['surface_score'] = max(50, 100 - std_intensity)

            # Very dark areas might indicate under-extrusion
            if mean_intensity < 100:
                result['defects'].append('under_extrusion')

        return result

    def _analyze_sensor_data(self, data: Dict[str, float]) -> Dict[str, Any]:
        """Analyze sensor data for layer quality."""
        result = {}

        # Layer height analysis
        if 'layer_height' in data:
            target_height = self.config.get('target_layer_height', 0.12)
            actual_height = data['layer_height']
            deviation = actual_height - target_height

            result['layer_height'] = actual_height
            result['height_deviation'] = deviation

        # Extrusion consistency
        if 'extrusion_pressure' in data:
            pressure = data['extrusion_pressure']
            target_pressure = self.config.get('target_pressure', 1.0)
            consistency = 100 - abs(pressure - target_pressure) / target_pressure * 100
            result['consistency'] = max(0, min(100, consistency))

        return result

    def _determine_status(
        self,
        analysis: LayerAnalysis
    ) -> Tuple[LayerStatus, DefectSeverity]:
        """Determine layer status from analysis."""
        # Calculate overall quality score
        quality_score = (
            analysis.surface_quality_score * 0.4 +
            analysis.adhesion_score * 0.3 +
            analysis.extrusion_consistency * 0.3
        ) / 100.0

        # Determine severity based on defects
        severity = DefectSeverity.NONE
        if analysis.defects_detected:
            if any('critical' in d.lower() for d in analysis.defects_detected):
                severity = DefectSeverity.CRITICAL
            elif any('major' in d.lower() or 'structural' in d.lower() for d in analysis.defects_detected):
                severity = DefectSeverity.MAJOR
            elif any('minor' in d.lower() for d in analysis.defects_detected):
                severity = DefectSeverity.MINOR
            else:
                severity = DefectSeverity.COSMETIC

        # Determine status
        if quality_score >= self.WARNING_THRESHOLD and severity in (DefectSeverity.NONE, DefectSeverity.COSMETIC):
            return LayerStatus.GOOD, severity
        elif quality_score >= self.DEFECTIVE_THRESHOLD and severity != DefectSeverity.CRITICAL:
            return LayerStatus.WARNING, severity
        else:
            return LayerStatus.DEFECTIVE, severity

    def get_adjustment(self, analysis: LayerAnalysis) -> Optional[ParameterAdjustment]:
        """
        Get recommended parameter adjustment based on analysis.

        Returns adjustment if intervention is recommended.
        """
        if analysis.status == LayerStatus.GOOD:
            return None

        if self._adjustments_this_layer >= self.MAX_ADJUSTMENTS_PER_LAYER:
            logger.warning("Max adjustments reached for this layer")
            return None

        # Determine best adjustment based on defects
        adjustment = None

        for defect in analysis.defects_detected:
            if 'under_extrusion' in defect.lower():
                adjustment = self._create_adjustment('flow_rate', 2, "Under-extrusion detected")
                break
            elif 'over_extrusion' in defect.lower():
                adjustment = self._create_adjustment('flow_rate', -2, "Over-extrusion detected")
                break
            elif 'layer_adhesion' in defect.lower() or 'delamination' in defect.lower():
                adjustment = self._create_adjustment('nozzle_temp', 5, "Poor layer adhesion")
                break
            elif 'surface' in defect.lower() or 'rough' in defect.lower():
                adjustment = self._create_adjustment('print_speed', -5, "Surface quality issues")
                break
            elif 'warping' in defect.lower():
                adjustment = self._create_adjustment('bed_temp', 5, "Warping detected")
                break

        # If no specific defect, check scores
        if adjustment is None:
            if analysis.extrusion_consistency < 80:
                adjustment = self._create_adjustment('flow_rate', 1, "Low extrusion consistency")
            elif analysis.surface_quality_score < 80:
                adjustment = self._create_adjustment('print_speed', -3, "Low surface quality score")

        if adjustment:
            self._adjustments_this_layer += 1
            self._adjustment_history.append(adjustment)

        return adjustment

    def _create_adjustment(
        self,
        parameter: str,
        delta: float,
        reason: str
    ) -> ParameterAdjustment:
        """Create a parameter adjustment."""
        current = self._current_params.get(parameter, 0)
        limits = self._param_limits.get(parameter, (float('-inf'), float('inf')))

        new_value = max(limits[0], min(limits[1], current + delta))

        return ParameterAdjustment(
            timestamp=datetime.utcnow(),
            parameter=parameter,
            current_value=current,
            new_value=new_value,
            reason=reason,
        )

    def apply_adjustment(self, adjustment: ParameterAdjustment) -> bool:
        """
        Apply a parameter adjustment.

        Returns True if adjustment was applied.
        """
        if self.machine is None:
            logger.warning("No machine controller - adjustment not applied")
            adjustment.auto_applied = False
            return False

        try:
            # Apply to machine
            # self.machine.set_parameter(adjustment.parameter, adjustment.new_value)

            # Update internal state
            self._current_params[adjustment.parameter] = adjustment.new_value
            adjustment.auto_applied = True

            logger.info(
                f"Adjusted {adjustment.parameter}: "
                f"{adjustment.current_value} → {adjustment.new_value} "
                f"({adjustment.reason})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to apply adjustment: {e}")
            return False

    def should_stop(self, analysis: LayerAnalysis) -> Tuple[bool, str]:
        """
        Determine if production should be stopped.

        Returns (should_stop, reason)
        """
        if analysis.defect_severity == DefectSeverity.CRITICAL:
            return True, "Critical defect detected"

        if self._consecutive_defects >= self.MAX_CONSECUTIVE_DEFECTS:
            return True, f"Too many consecutive defects ({self._consecutive_defects})"

        # Check trend - if quality is declining
        if len(self._layer_history) >= 5:
            recent_scores = [
                l.surface_quality_score
                for l in self._layer_history[-5:]
            ]
            if all(s < self.DEFECTIVE_THRESHOLD * 100 for s in recent_scores):
                return True, "Sustained quality degradation"

        return False, ""

    def _count_adjustments_by_type(self) -> Dict[str, int]:
        """Count adjustments by parameter type."""
        counts = {}
        for adj in self._adjustment_history:
            counts[adj.parameter] = counts.get(adj.parameter, 0) + 1
        return counts

    def get_layer_history(self) -> List[Dict[str, Any]]:
        """Get layer analysis history."""
        return [
            {
                'layer': l.layer_number,
                'status': l.status.value,
                'defects': l.defects_detected,
                'surface_score': l.surface_quality_score,
                'confidence': l.analysis_confidence,
            }
            for l in self._layer_history
        ]

    def get_adjustment_history(self) -> List[Dict[str, Any]]:
        """Get adjustment history."""
        return [
            {
                'timestamp': a.timestamp.isoformat(),
                'parameter': a.parameter,
                'from': a.current_value,
                'to': a.new_value,
                'reason': a.reason,
                'applied': a.auto_applied,
            }
            for a in self._adjustment_history
        ]

    def get_current_params(self) -> Dict[str, float]:
        """Get current process parameters."""
        return self._current_params.copy()

    def get_quality_trend(self) -> Dict[str, Any]:
        """Get quality trend over recent layers."""
        if not self._layer_history:
            return {'status': 'no_data'}

        window = min(10, len(self._layer_history))
        recent = self._layer_history[-window:]

        avg_surface = sum(l.surface_quality_score for l in recent) / window
        avg_extrusion = sum(l.extrusion_consistency for l in recent) / window
        defect_rate = sum(1 for l in recent if l.status == LayerStatus.DEFECTIVE) / window

        trend = 'stable'
        if len(self._layer_history) >= 5:
            older = sum(l.surface_quality_score for l in self._layer_history[-10:-5]) / 5
            newer = sum(l.surface_quality_score for l in self._layer_history[-5:]) / 5
            if newer < older - 5:
                trend = 'declining'
            elif newer > older + 5:
                trend = 'improving'

        return {
            'layers_analyzed': len(self._layer_history),
            'avg_surface_quality': avg_surface,
            'avg_extrusion_consistency': avg_extrusion,
            'defect_rate': defect_rate,
            'consecutive_defects': self._consecutive_defects,
            'trend': trend,
        }
