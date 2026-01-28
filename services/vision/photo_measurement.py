"""
Photo Measurement Service.

Extracts dimensions from photos of parts:
- Requires reference scale (ruler, known object)
- Measures distances, diameters, angles
- Supports metric and imperial units
"""

import logging
import base64
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class MeasurementUnit(Enum):
    """Measurement units."""
    INCHES = "inches"
    MILLIMETERS = "mm"
    CENTIMETERS = "cm"


class DimensionType(Enum):
    """Types of dimensions."""
    LENGTH = "length"
    WIDTH = "width"
    HEIGHT = "height"
    DIAMETER = "diameter"
    RADIUS = "radius"
    THICKNESS = "thickness"
    DEPTH = "depth"
    ANGLE = "angle"
    DISTANCE = "distance"


@dataclass
class ReferenceScale:
    """Reference scale for calibration."""
    known_length: float
    unit: MeasurementUnit = MeasurementUnit.INCHES
    description: str = ""  # e.g., "ruler", "quarter coin"
    pixels_per_unit: Optional[float] = None


@dataclass
class DetectedDimension:
    """A detected dimension in the image."""
    dimension_type: DimensionType
    value: float
    unit: MeasurementUnit
    confidence: float = 0.0
    location_description: str = ""
    notes: str = ""


@dataclass
class MeasurementResult:
    """Result of photo measurement."""
    success: bool
    dimensions: List[DetectedDimension] = field(default_factory=list)
    scale_detected: bool = False
    scale_factor: Optional[float] = None
    notes: List[str] = field(default_factory=list)
    raw_analysis: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class PhotoMeasurement:
    """
    Extracts measurements from photos of parts.

    Uses Claude's vision to:
    - Detect reference scale objects
    - Measure part dimensions
    - Report in specified units
    """

    MEASUREMENT_PROMPT = """Analyze this photo to extract measurements of the part/object shown.

Reference Scale Information:
{scale_info}

Please identify and measure:
1. Overall dimensions (length, width, height/thickness)
2. Any holes or circular features (diameter)
3. Notable features and their dimensions
4. Any visible angles

Use the reference scale to calculate actual dimensions.

Format your response as JSON:
{{
    "scale_detected": true,
    "scale_factor": 0.1,  // units per pixel
    "dimensions": [
        {{
            "type": "length",
            "value": 4.5,
            "unit": "inches",
            "confidence": 0.85,
            "location": "overall length left to right",
            "notes": "measured along bottom edge"
        }},
        {{
            "type": "diameter",
            "value": 0.25,
            "unit": "inches",
            "confidence": 0.9,
            "location": "center hole",
            "notes": "appears to be a through hole"
        }}
    ],
    "notes": ["photo taken from top-down view", "good lighting conditions"]
}}

Be precise with measurements. If uncertain, indicate lower confidence and explain why."""

    KNOWN_REFERENCES = {
        "ruler": "Standard ruler visible in image",
        "quarter": "US quarter coin (diameter 0.955 inches / 24.26mm)",
        "credit_card": "Standard credit card (3.375 x 2.125 inches / 85.6 x 53.98mm)",
        "business_card": "Standard business card (3.5 x 2 inches / 89 x 51mm)",
        "a4_paper": "A4 paper (210 x 297mm)",
        "letter_paper": "US Letter paper (8.5 x 11 inches)",
    }

    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize photo measurement service."""
        self.api_key = anthropic_api_key
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None and self.api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.warning("anthropic package not installed")
        return self._client

    async def measure(
        self,
        image_data: bytes,
        image_type: str = "image/jpeg",
        reference: Optional[ReferenceScale] = None,
        reference_type: Optional[str] = None,
        output_unit: MeasurementUnit = MeasurementUnit.INCHES,
    ) -> MeasurementResult:
        """
        Extract measurements from a photo.

        Args:
            image_data: Raw image bytes
            image_type: MIME type of the image
            reference: Reference scale object if known
            reference_type: Type of reference (e.g., "ruler", "quarter")
            output_unit: Desired output unit

        Returns:
            Measurement result with detected dimensions
        """
        if not self.client:
            return MeasurementResult(
                success=False,
                notes=["Claude API not configured"],
            )

        try:
            # Build scale info
            scale_info = self._build_scale_info(reference, reference_type)

            # Encode image
            image_b64 = base64.standard_b64encode(image_data).decode("utf-8")

            # Build prompt
            prompt = self.MEASUREMENT_PROMPT.format(scale_info=scale_info)

            # Call Claude Vision
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }],
            )

            # Parse response
            response_text = response.content[0].text
            result = self._parse_measurement_response(response_text)

            # Convert units if needed
            if output_unit != MeasurementUnit.INCHES:
                result = self._convert_units(result, output_unit)

            return result

        except Exception as e:
            logger.error(f"Measurement error: {e}")
            return MeasurementResult(
                success=False,
                notes=[f"Measurement failed: {str(e)}"],
            )

    def _build_scale_info(
        self,
        reference: Optional[ReferenceScale],
        reference_type: Optional[str],
    ) -> str:
        """Build scale information for the prompt."""
        if reference:
            return (
                f"Known reference: {reference.description}\n"
                f"Reference length: {reference.known_length} {reference.unit.value}"
            )

        if reference_type and reference_type in self.KNOWN_REFERENCES:
            return (
                f"Reference object in image: {reference_type}\n"
                f"{self.KNOWN_REFERENCES[reference_type]}"
            )

        return (
            "Look for any reference scale objects in the image:\n"
            "- Rulers or measuring tapes\n"
            "- Coins (US quarter = 0.955 inches diameter)\n"
            "- Standard objects (credit card, business card)\n"
            "If no reference is visible, estimate based on typical part sizes "
            "and note the uncertainty."
        )

    def _parse_measurement_response(
        self,
        response_text: str,
    ) -> MeasurementResult:
        """Parse Claude's measurement response."""
        try:
            # Extract JSON
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)

                # Parse dimensions
                dimensions = []
                for dim_data in data.get("dimensions", []):
                    dimension = self._parse_dimension(dim_data)
                    if dimension:
                        dimensions.append(dimension)

                return MeasurementResult(
                    success=True,
                    dimensions=dimensions,
                    scale_detected=data.get("scale_detected", False),
                    scale_factor=data.get("scale_factor"),
                    notes=data.get("notes", []),
                    raw_analysis=response_text,
                )

            return MeasurementResult(
                success=True,
                raw_analysis=response_text,
                notes=["Could not parse structured response"],
            )

        except json.JSONDecodeError:
            return MeasurementResult(
                success=True,
                raw_analysis=response_text,
                notes=["Response was not in expected JSON format"],
            )

    def _parse_dimension(
        self,
        data: Dict[str, Any],
    ) -> Optional[DetectedDimension]:
        """Parse dimension data from response."""
        try:
            dim_type = DimensionType(data.get("type", "distance"))
        except ValueError:
            dim_type = DimensionType.DISTANCE

        try:
            unit = MeasurementUnit(data.get("unit", "inches"))
        except ValueError:
            unit = MeasurementUnit.INCHES

        return DetectedDimension(
            dimension_type=dim_type,
            value=float(data.get("value", 0)),
            unit=unit,
            confidence=float(data.get("confidence", 0.5)),
            location_description=data.get("location", ""),
            notes=data.get("notes", ""),
        )

    def _convert_units(
        self,
        result: MeasurementResult,
        target_unit: MeasurementUnit,
    ) -> MeasurementResult:
        """Convert all dimensions to target unit."""
        conversion_factors = {
            (MeasurementUnit.INCHES, MeasurementUnit.MILLIMETERS): 25.4,
            (MeasurementUnit.INCHES, MeasurementUnit.CENTIMETERS): 2.54,
            (MeasurementUnit.MILLIMETERS, MeasurementUnit.INCHES): 1 / 25.4,
            (MeasurementUnit.MILLIMETERS, MeasurementUnit.CENTIMETERS): 0.1,
            (MeasurementUnit.CENTIMETERS, MeasurementUnit.INCHES): 1 / 2.54,
            (MeasurementUnit.CENTIMETERS, MeasurementUnit.MILLIMETERS): 10,
        }

        converted_dimensions = []
        for dim in result.dimensions:
            if dim.unit == target_unit:
                converted_dimensions.append(dim)
            else:
                factor = conversion_factors.get((dim.unit, target_unit), 1.0)
                converted_dimensions.append(DetectedDimension(
                    dimension_type=dim.dimension_type,
                    value=dim.value * factor,
                    unit=target_unit,
                    confidence=dim.confidence,
                    location_description=dim.location_description,
                    notes=dim.notes,
                ))

        result.dimensions = converted_dimensions
        return result

    def format_report(self, result: MeasurementResult) -> str:
        """Format measurement result as a readable report."""
        lines = [
            "=== Photo Measurement Report ===",
            f"Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        if result.scale_detected:
            lines.append(f"✓ Scale reference detected")
            if result.scale_factor:
                lines.append(f"  Scale factor: {result.scale_factor:.4f}")
        else:
            lines.append("⚠ No scale reference detected - measurements may be approximate")

        lines.append("")
        lines.append("Dimensions:")

        for dim in result.dimensions:
            conf_str = f"({dim.confidence * 100:.0f}% confidence)"
            lines.append(
                f"  • {dim.dimension_type.value.title()}: "
                f"{dim.value:.3f} {dim.unit.value} {conf_str}"
            )
            if dim.location_description:
                lines.append(f"    Location: {dim.location_description}")
            if dim.notes:
                lines.append(f"    Note: {dim.notes}")

        if result.notes:
            lines.append("")
            lines.append("Notes:")
            for note in result.notes:
                lines.append(f"  - {note}")

        return "\n".join(lines)
