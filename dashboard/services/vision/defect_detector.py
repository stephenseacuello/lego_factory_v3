"""
Defect Detector - Computer Vision Quality Inspection

LegoMCP World-Class Manufacturing System v5.0
Phase 13: Computer Vision Quality Inspection

Multi-class defect detection for 3D printed parts:
- Layer analysis
- Surface quality assessment
- Dimensional verification
- Defect classification
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class DefectClass(str, Enum):
    """Defect classification."""
    LAYER_SHIFT = "layer_shift"
    STRINGING = "stringing"
    WARPING = "warping"
    UNDER_EXTRUSION = "under_extrusion"
    OVER_EXTRUSION = "over_extrusion"
    SURFACE_ROUGHNESS = "surface_roughness"
    COLOR_DEVIATION = "color_deviation"
    MISSING_FEATURE = "missing_feature"
    DIMENSIONAL_ERROR = "dimensional_error"
    CONTAMINATION = "contamination"
    DELAMINATION = "delamination"
    BLOB = "blob"
    GAP = "gap"
    SCRATCH = "scratch"


class DefectSeverity(str, Enum):
    """Defect severity level."""
    CRITICAL = "critical"  # Reject immediately
    MAJOR = "major"  # Review required
    MINOR = "minor"  # Accept with deviation
    COSMETIC = "cosmetic"  # Visual only


@dataclass
class DefectDetection:
    """A detected defect."""
    defect_id: str
    defect_class: DefectClass
    severity: DefectSeverity
    confidence: float  # 0-1

    # Location
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    layer: Optional[int] = None

    # Measurements
    size_mm2: float = 0.0
    depth_mm: Optional[float] = None

    # Context
    description: str = ""
    likely_cause: str = ""
    recommended_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'defect_id': self.defect_id,
            'defect_class': self.defect_class.value,
            'severity': self.severity.value,
            'confidence': self.confidence,
            'location': {'x': self.x, 'y': self.y, 'width': self.width, 'height': self.height},
            'layer': self.layer,
            'size_mm2': self.size_mm2,
            'description': self.description,
            'likely_cause': self.likely_cause,
            'recommended_action': self.recommended_action,
        }


@dataclass
class InspectionResult:
    """Result of a CV inspection."""
    inspection_id: str
    part_id: str
    timestamp: datetime

    # Overall result
    passed: bool = True
    quality_score: float = 100.0

    # Defects found
    defects: List[DefectDetection] = field(default_factory=list)

    # Counts by severity
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    cosmetic_count: int = 0

    # Processing info
    processing_time_ms: float = 0.0
    images_analyzed: int = 1

    # Disposition
    disposition: str = "accept"  # accept, review, reject

    def __post_init__(self):
        self._update_counts()

    def _update_counts(self) -> None:
        """Update defect counts."""
        self.critical_count = sum(1 for d in self.defects if d.severity == DefectSeverity.CRITICAL)
        self.major_count = sum(1 for d in self.defects if d.severity == DefectSeverity.MAJOR)
        self.minor_count = sum(1 for d in self.defects if d.severity == DefectSeverity.MINOR)
        self.cosmetic_count = sum(1 for d in self.defects if d.severity == DefectSeverity.COSMETIC)

        # Determine pass/fail
        if self.critical_count > 0:
            self.passed = False
            self.disposition = "reject"
        elif self.major_count > 0:
            self.passed = False
            self.disposition = "review"
        else:
            self.passed = True
            self.disposition = "accept"

        # Calculate quality score
        penalty = (
            self.critical_count * 25 +
            self.major_count * 10 +
            self.minor_count * 3 +
            self.cosmetic_count * 1
        )
        self.quality_score = max(0, 100 - penalty)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'inspection_id': self.inspection_id,
            'part_id': self.part_id,
            'timestamp': self.timestamp.isoformat(),
            'passed': self.passed,
            'quality_score': self.quality_score,
            'defects': [d.to_dict() for d in self.defects],
            'critical_count': self.critical_count,
            'major_count': self.major_count,
            'minor_count': self.minor_count,
            'cosmetic_count': self.cosmetic_count,
            'disposition': self.disposition,
            'processing_time_ms': self.processing_time_ms,
        }


class DefectDetector:
    """
    Computer Vision Defect Detection System.

    Analyzes images of 3D printed LEGO parts for defects.
    """

    # Defect detection thresholds
    THRESHOLDS = {
        DefectClass.LAYER_SHIFT: {'min_offset_mm': 0.2, 'severity_critical': 0.5},
        DefectClass.STRINGING: {'min_length_mm': 1.0, 'severity_major': 3.0},
        DefectClass.WARPING: {'min_deflection_mm': 0.3, 'severity_critical': 0.8},
        DefectClass.UNDER_EXTRUSION: {'min_gap_percent': 10, 'severity_critical': 30},
        DefectClass.OVER_EXTRUSION: {'min_excess_percent': 10, 'severity_critical': 25},
    }

    # Likely causes and actions
    DEFECT_INFO = {
        DefectClass.LAYER_SHIFT: {
            'causes': ['Belt slip', 'Loose pulleys', 'Motor skip', 'Print speed too high'],
            'actions': ['Check belts', 'Reduce print speed', 'Check motor current'],
        },
        DefectClass.STRINGING: {
            'causes': ['Temperature too high', 'Retraction insufficient', 'Travel speed low'],
            'actions': ['Lower temperature', 'Increase retraction', 'Enable wipe'],
        },
        DefectClass.WARPING: {
            'causes': ['Bed adhesion poor', 'Cooling too fast', 'No enclosure'],
            'actions': ['Clean bed', 'Reduce fan speed', 'Add brim', 'Use enclosure'],
        },
        DefectClass.UNDER_EXTRUSION: {
            'causes': ['Clogged nozzle', 'Temperature low', 'Filament grinding'],
            'actions': ['Clean nozzle', 'Increase temperature', 'Check extruder tension'],
        },
        DefectClass.OVER_EXTRUSION: {
            'causes': ['Flow rate too high', 'Filament diameter wrong', 'Steps miscalibrated'],
            'actions': ['Reduce flow rate', 'Measure filament', 'Calibrate e-steps'],
        },
        DefectClass.DELAMINATION: {
            'causes': ['Layer adhesion poor', 'Temperature too low', 'Fan too high'],
            'actions': ['Increase temperature', 'Reduce fan', 'Slow down'],
        },
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._model_loaded = False

    def analyze_image(
        self,
        image: np.ndarray,
        part_id: str,
        expected_dimensions: Optional[Dict[str, float]] = None,
    ) -> InspectionResult:
        """
        Analyze an image for defects.

        Args:
            image: Image as numpy array (H, W, C)
            part_id: Part identifier
            expected_dimensions: Expected measurements

        Returns:
            InspectionResult with detected defects
        """
        from uuid import uuid4
        import time

        start_time = time.time()

        inspection = InspectionResult(
            inspection_id=str(uuid4()),
            part_id=part_id,
            timestamp=datetime.utcnow(),
        )

        # Simulate defect detection
        # In production, would use trained CV model (YOLO, etc.)
        defects = self._detect_defects_simulated(image)

        for defect in defects:
            self._enrich_defect(defect)
            inspection.defects.append(defect)

        inspection._update_counts()
        inspection.processing_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Inspection {inspection.inspection_id}: "
            f"Score={inspection.quality_score:.1f}, "
            f"Defects={len(defects)}"
        )

        return inspection

    def _detect_defects_simulated(self, image: np.ndarray) -> List[DefectDetection]:
        """Simulate defect detection (would be ML model in production)."""
        from uuid import uuid4

        defects = []

        # Simulate based on image characteristics
        h, w = image.shape[:2] if len(image.shape) >= 2 else (100, 100)

        # Check for obvious issues in image
        if len(image.shape) == 3:
            # Color analysis
            mean_color = np.mean(image, axis=(0, 1))
            color_std = np.std(image)

            # High variance might indicate surface issues
            if color_std > 50:
                defects.append(DefectDetection(
                    defect_id=str(uuid4()),
                    defect_class=DefectClass.SURFACE_ROUGHNESS,
                    severity=DefectSeverity.MINOR,
                    confidence=0.75,
                    description="Surface texture variation detected",
                ))

        return defects

    def _enrich_defect(self, defect: DefectDetection) -> None:
        """Add cause and action information to defect."""
        info = self.DEFECT_INFO.get(defect.defect_class, {})

        if info.get('causes'):
            defect.likely_cause = info['causes'][0]

        if info.get('actions'):
            defect.recommended_action = info['actions'][0]

    def analyze_layer(
        self,
        layer_image: np.ndarray,
        layer_number: int,
        previous_layer: Optional[np.ndarray] = None,
    ) -> List[DefectDetection]:
        """
        Analyze a single layer during printing.

        Compares to previous layer for shift detection.
        """
        from uuid import uuid4

        defects = []

        if previous_layer is not None and layer_image.shape == previous_layer.shape:
            # Calculate difference
            diff = np.abs(layer_image.astype(float) - previous_layer.astype(float))
            mean_diff = np.mean(diff)

            # High difference might indicate layer shift
            if mean_diff > 30:
                defects.append(DefectDetection(
                    defect_id=str(uuid4()),
                    defect_class=DefectClass.LAYER_SHIFT,
                    severity=DefectSeverity.MAJOR if mean_diff > 50 else DefectSeverity.MINOR,
                    confidence=min(0.95, mean_diff / 100),
                    layer=layer_number,
                    description=f"Layer shift detected at layer {layer_number}",
                ))

        return defects

    def get_defect_classes(self) -> List[str]:
        """Get all defect class names."""
        return [d.value for d in DefectClass]

    def get_severity_levels(self) -> List[str]:
        """Get all severity levels."""
        return [s.value for s in DefectSeverity]
