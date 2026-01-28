"""
Vision Service for CNC SCADA Copilot.

Provides multi-modal CAD interaction using Claude's vision capabilities:
- Hand-drawn sketch interpretation
- Photo-based measurement extraction
- Visual quality inspection
- Drawing OCR
"""

from .sketch_to_cad import (
    SketchToCAD,
    SketchAnalysisResult,
    DetectedGeometry,
    GeometryType,
)

from .photo_measurement import (
    PhotoMeasurement,
    MeasurementResult,
    DetectedDimension,
    ReferenceScale,
)

from .part_inspection import (
    PartInspection,
    InspectionResult,
    DefectType,
    DetectedDefect,
    QualityScore,
)

from .drawing_ocr import (
    DrawingOCR,
    OCRResult,
    ExtractedText,
    DrawingElement,
)

from .camera_service import (
    CameraService,
    CameraConfig,
    CapturedImage,
)

from .vision_service import (
    VisionService,
    VisionConfig,
    get_vision_service,
    configure_vision_service,
)

__all__ = [
    # Sketch to CAD
    "SketchToCAD",
    "SketchAnalysisResult",
    "DetectedGeometry",
    "GeometryType",
    # Photo measurement
    "PhotoMeasurement",
    "MeasurementResult",
    "DetectedDimension",
    "ReferenceScale",
    # Part inspection
    "PartInspection",
    "InspectionResult",
    "DefectType",
    "DetectedDefect",
    "QualityScore",
    # Drawing OCR
    "DrawingOCR",
    "OCRResult",
    "ExtractedText",
    "DrawingElement",
    # Camera
    "CameraService",
    "CameraConfig",
    "CapturedImage",
    # Main service
    "VisionService",
    "VisionConfig",
    "get_vision_service",
    "configure_vision_service",
]
