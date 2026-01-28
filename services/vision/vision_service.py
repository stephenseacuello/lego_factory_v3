"""
Main Vision Service for CNC SCADA Copilot.

Integrates all vision components:
- Sketch-to-CAD conversion
- Photo measurement
- Part inspection
- Drawing OCR
- Camera management
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime

from .sketch_to_cad import SketchToCAD, SketchAnalysisResult
from .photo_measurement import (
    PhotoMeasurement,
    MeasurementResult,
    ReferenceScale,
    MeasurementUnit,
)
from .part_inspection import PartInspection, InspectionResult
from .drawing_ocr import DrawingOCR, OCRResult
from .camera_service import CameraService, CameraConfig, CapturedImage

logger = logging.getLogger(__name__)


@dataclass
class VisionConfig:
    """Vision service configuration."""
    # API keys
    anthropic_api_key: Optional[str] = None

    # Feature toggles
    enabled: bool = True
    enable_sketch_to_cad: bool = True
    enable_photo_measurement: bool = True
    enable_part_inspection: bool = True
    enable_drawing_ocr: bool = True

    # Camera settings
    camera_config: CameraConfig = field(default_factory=CameraConfig)

    # Default settings
    default_unit: MeasurementUnit = MeasurementUnit.INCHES
    save_images: bool = False
    image_save_path: str = "./captured_images"


class VisionService:
    """
    Main vision service providing multi-modal CAD interaction.

    Features:
    - Hand-drawn sketch interpretation
    - Photo-based measurement
    - Visual quality inspection
    - Engineering drawing OCR
    """

    def __init__(self, config: Optional[VisionConfig] = None):
        """Initialize vision service."""
        self.config = config or VisionConfig()

        # Initialize components
        self.sketch_to_cad = SketchToCAD(self.config.anthropic_api_key)
        self.photo_measurement = PhotoMeasurement(self.config.anthropic_api_key)
        self.part_inspection = PartInspection(self.config.anthropic_api_key)
        self.drawing_ocr = DrawingOCR(self.config.anthropic_api_key)
        self.camera = CameraService(self.config.camera_config)

        # History
        self._analysis_history: List[Dict[str, Any]] = []

    # =========================================================================
    # Sketch-to-CAD
    # =========================================================================

    async def analyze_sketch(
        self,
        image_data: bytes,
        image_type: str = "image/png",
        context: str = "",
    ) -> SketchAnalysisResult:
        """
        Analyze a hand-drawn sketch for CAD conversion.

        Args:
            image_data: Raw image bytes
            image_type: MIME type
            context: Additional context

        Returns:
            Sketch analysis result
        """
        if not self.config.enable_sketch_to_cad:
            return SketchAnalysisResult(
                success=False,
                notes=["Sketch-to-CAD is disabled"],
            )

        result = await self.sketch_to_cad.analyze_sketch(
            image_data, image_type, context
        )

        self._record_analysis("sketch_to_cad", result)
        return result

    async def sketch_to_gcode(
        self,
        image_data: bytes,
        material: str = "aluminum",
        tool_diameter: float = 0.25,
    ) -> Dict[str, Any]:
        """
        Convert a sketch directly to G-code suggestions.

        Args:
            image_data: Raw image bytes
            material: Material type
            tool_diameter: Tool diameter

        Returns:
            Dict with analysis and G-code suggestions
        """
        result = await self.analyze_sketch(image_data)

        if not result.success:
            return {"success": False, "error": result.notes}

        gcode_suggestions = self.sketch_to_cad.generate_gcode_suggestions(
            result, material, tool_diameter
        )

        return {
            "success": True,
            "analysis": result,
            "gcode_suggestions": gcode_suggestions,
            "dxf_export": self.sketch_to_cad.to_dxf_points(result),
        }

    # =========================================================================
    # Photo Measurement
    # =========================================================================

    async def measure_from_photo(
        self,
        image_data: bytes,
        image_type: str = "image/jpeg",
        reference_type: Optional[str] = None,
        output_unit: Optional[MeasurementUnit] = None,
    ) -> MeasurementResult:
        """
        Extract measurements from a photo.

        Args:
            image_data: Raw image bytes
            image_type: MIME type
            reference_type: Type of reference scale
            output_unit: Desired output unit

        Returns:
            Measurement result
        """
        if not self.config.enable_photo_measurement:
            return MeasurementResult(
                success=False,
                notes=["Photo measurement is disabled"],
            )

        result = await self.photo_measurement.measure(
            image_data,
            image_type,
            reference_type=reference_type,
            output_unit=output_unit or self.config.default_unit,
        )

        self._record_analysis("photo_measurement", result)
        return result

    async def measure_with_scale(
        self,
        image_data: bytes,
        known_length: float,
        unit: MeasurementUnit = MeasurementUnit.INCHES,
        description: str = "",
    ) -> MeasurementResult:
        """
        Measure with a known reference scale.

        Args:
            image_data: Raw image bytes
            known_length: Known length of reference
            unit: Unit of reference
            description: Description of reference

        Returns:
            Measurement result
        """
        reference = ReferenceScale(
            known_length=known_length,
            unit=unit,
            description=description,
        )

        return await self.photo_measurement.measure(
            image_data,
            reference=reference,
            output_unit=unit,
        )

    # =========================================================================
    # Part Inspection
    # =========================================================================

    async def inspect_part(
        self,
        image_data: bytes,
        image_type: str = "image/jpeg",
        part_number: Optional[str] = None,
        expected_features: Optional[List[str]] = None,
        material: Optional[str] = None,
    ) -> InspectionResult:
        """
        Inspect a part for quality defects.

        Args:
            image_data: Raw image bytes
            image_type: MIME type
            part_number: Part number
            expected_features: Features to verify
            material: Material type

        Returns:
            Inspection result
        """
        if not self.config.enable_part_inspection:
            return InspectionResult(
                success=False,
                notes=["Part inspection is disabled"],
            )

        result = await self.part_inspection.inspect(
            image_data,
            image_type,
            part_number=part_number,
            expected_features=expected_features,
            material=material,
        )

        self._record_analysis("part_inspection", result)
        return result

    async def compare_parts(
        self,
        part_image: bytes,
        reference_image: bytes,
    ) -> InspectionResult:
        """
        Compare a part to a reference sample.

        Args:
            part_image: Image of part to inspect
            reference_image: Image of reference part

        Returns:
            Comparison result
        """
        return await self.part_inspection.compare_to_reference(
            part_image, reference_image
        )

    # =========================================================================
    # Drawing OCR
    # =========================================================================

    async def read_drawing(
        self,
        image_data: bytes,
        image_type: str = "image/png",
    ) -> OCRResult:
        """
        Extract text from an engineering drawing.

        Args:
            image_data: Raw image bytes
            image_type: MIME type

        Returns:
            OCR result
        """
        if not self.config.enable_drawing_ocr:
            return OCRResult(
                success=False,
                notes=["Drawing OCR is disabled"],
            )

        result = await self.drawing_ocr.extract_text(image_data, image_type)

        self._record_analysis("drawing_ocr", result)
        return result

    async def extract_part_info(
        self,
        image_data: bytes,
    ) -> Dict[str, Any]:
        """
        Extract key part information from a drawing.

        Args:
            image_data: Raw image bytes

        Returns:
            Dict with part number, material, dimensions, etc.
        """
        result = await self.read_drawing(image_data)

        return {
            "success": result.success,
            "title_block": result.title_block,
            "dimensions": result.dimensions,
            "notes": result.notes,
        }

    # =========================================================================
    # Camera Operations
    # =========================================================================

    def capture_image(self) -> Optional[CapturedImage]:
        """
        Capture an image from the connected camera.

        Returns:
            Captured image or None
        """
        image = self.camera.capture()

        if image and self.config.save_images:
            self._save_image(image)

        return image

    async def capture_and_analyze(
        self,
        analysis_type: str = "inspection",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Capture an image and analyze it.

        Args:
            analysis_type: Type of analysis (inspection, measurement, ocr, sketch)
            **kwargs: Additional arguments for the analysis

        Returns:
            Analysis result
        """
        image = self.capture_image()

        if not image:
            return {
                "success": False,
                "error": "Failed to capture image",
            }

        if analysis_type == "inspection":
            result = await self.inspect_part(image.data, **kwargs)
            return {
                "success": result.success,
                "result": result,
                "report": self.part_inspection.generate_report(result),
            }

        elif analysis_type == "measurement":
            result = await self.measure_from_photo(image.data, **kwargs)
            return {
                "success": result.success,
                "result": result,
                "report": self.photo_measurement.format_report(result),
            }

        elif analysis_type == "ocr":
            result = await self.read_drawing(image.data, **kwargs)
            return {
                "success": result.success,
                "result": result,
                "report": self.drawing_ocr.format_extracted_data(result),
            }

        elif analysis_type == "sketch":
            result = await self.analyze_sketch(image.data, **kwargs)
            return {
                "success": result.success,
                "result": result,
            }

        else:
            return {
                "success": False,
                "error": f"Unknown analysis type: {analysis_type}",
            }

    def get_camera_list(self) -> List[dict]:
        """Get list of available cameras."""
        return self.camera.get_available_cameras()

    def connect_camera(self, device_id: Optional[int] = None) -> bool:
        """Connect to a camera device."""
        if device_id is not None:
            self.camera.config.device_id = device_id
        return self.camera.connect()

    def disconnect_camera(self):
        """Disconnect from the camera."""
        self.camera.disconnect()

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _record_analysis(self, analysis_type: str, result: Any):
        """Record an analysis to history."""
        self._analysis_history.append({
            "type": analysis_type,
            "timestamp": datetime.now().isoformat(),
            "success": result.success if hasattr(result, "success") else True,
        })

        # Keep history manageable
        if len(self._analysis_history) > 100:
            self._analysis_history = self._analysis_history[-100:]

    def _save_image(self, image: CapturedImage):
        """Save captured image to disk."""
        import os

        os.makedirs(self.config.image_save_path, exist_ok=True)

        filename = f"capture_{image.timestamp.strftime('%Y%m%d_%H%M%S')}.{image.format}"
        filepath = os.path.join(self.config.image_save_path, filename)

        with open(filepath, "wb") as f:
            f.write(image.data)

        logger.info(f"Image saved: {filepath}")

    def get_analysis_history(
        self,
        limit: int = 50,
        analysis_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get analysis history."""
        history = self._analysis_history[-limit:]

        if analysis_type:
            history = [h for h in history if h["type"] == analysis_type]

        return history

    def is_available(self) -> Dict[str, bool]:
        """Check which vision features are available."""
        has_api_key = bool(self.config.anthropic_api_key)

        return {
            "sketch_to_cad": has_api_key and self.config.enable_sketch_to_cad,
            "photo_measurement": has_api_key and self.config.enable_photo_measurement,
            "part_inspection": has_api_key and self.config.enable_part_inspection,
            "drawing_ocr": has_api_key and self.config.enable_drawing_ocr,
            "camera": self.camera.state.value != "error",
        }


# Module-level instance
_vision_service: Optional[VisionService] = None


def get_vision_service() -> VisionService:
    """Get the global vision service instance."""
    global _vision_service
    if _vision_service is None:
        _vision_service = VisionService()
    return _vision_service


def configure_vision_service(config: VisionConfig) -> VisionService:
    """Configure the global vision service instance."""
    global _vision_service
    _vision_service = VisionService(config)
    return _vision_service
