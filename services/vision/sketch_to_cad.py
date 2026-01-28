"""
Sketch-to-CAD Service.

Converts hand-drawn sketches to machinable geometry:
- Line and arc detection
- Dimension interpretation
- G-code generation suggestions
"""

import logging
import base64
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class GeometryType(Enum):
    """Types of detected geometry."""
    LINE = "line"
    ARC = "arc"
    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    HOLE = "hole"
    SLOT = "slot"
    POCKET = "pocket"
    PROFILE = "profile"
    UNKNOWN = "unknown"


@dataclass
class Point:
    """A 2D point."""
    x: float
    y: float


@dataclass
class DetectedGeometry:
    """Detected geometry from a sketch."""
    geometry_type: GeometryType
    points: List[Point] = field(default_factory=list)
    center: Optional[Point] = None
    radius: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    depth: Optional[float] = None
    confidence: float = 0.0
    notes: str = ""


@dataclass
class SketchAnalysisResult:
    """Result of sketch analysis."""
    success: bool
    geometries: List[DetectedGeometry] = field(default_factory=list)
    dimensions: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    suggested_operations: List[str] = field(default_factory=list)
    raw_description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class SketchToCAD:
    """
    Converts hand-drawn sketches to CAD geometry.

    Uses Claude's vision to:
    - Identify geometric shapes
    - Extract dimensions and annotations
    - Suggest machining operations
    """

    ANALYSIS_PROMPT = """Analyze this hand-drawn sketch for CNC machining.

Identify all geometric features and provide:
1. Type of each feature (line, arc, circle, rectangle, hole, pocket, slot, profile)
2. Approximate dimensions visible or annotated
3. Relationships between features
4. Suggested machining operations

Format your response as JSON:
{
    "geometries": [
        {
            "type": "circle",
            "description": "center hole",
            "center": {"x": 2.0, "y": 1.5},
            "radius": 0.25,
            "depth": 0.5,
            "confidence": 0.9,
            "notes": "appears to be a through hole"
        }
    ],
    "dimensions": {
        "overall_width": 4.0,
        "overall_height": 3.0,
        "material_thickness": 0.5
    },
    "notes": ["sketch shows top-down view", "dimensions appear to be in inches"],
    "suggested_operations": ["profile cutout", "center drill", "pocket"]
}

Be specific about coordinates and dimensions. If a dimension is unclear, estimate based on proportions and note the uncertainty."""

    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize sketch-to-CAD service."""
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

    async def analyze_sketch(
        self,
        image_data: bytes,
        image_type: str = "image/png",
        additional_context: str = "",
    ) -> SketchAnalysisResult:
        """
        Analyze a hand-drawn sketch.

        Args:
            image_data: Raw image bytes
            image_type: MIME type of the image
            additional_context: Additional context about the sketch

        Returns:
            Analysis result with detected geometry
        """
        if not self.client:
            return SketchAnalysisResult(
                success=False,
                notes=["Claude API not configured"],
            )

        try:
            # Encode image
            image_b64 = base64.standard_b64encode(image_data).decode("utf-8")

            # Build prompt
            prompt = self.ANALYSIS_PROMPT
            if additional_context:
                prompt += f"\n\nAdditional context: {additional_context}"

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
            return self._parse_analysis_response(response_text)

        except Exception as e:
            logger.error(f"Sketch analysis error: {e}")
            return SketchAnalysisResult(
                success=False,
                notes=[f"Analysis failed: {str(e)}"],
            )

    def _parse_analysis_response(
        self,
        response_text: str,
    ) -> SketchAnalysisResult:
        """Parse Claude's analysis response."""
        try:
            # Extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)

                # Parse geometries
                geometries = []
                for geo_data in data.get("geometries", []):
                    geometry = self._parse_geometry(geo_data)
                    if geometry:
                        geometries.append(geometry)

                return SketchAnalysisResult(
                    success=True,
                    geometries=geometries,
                    dimensions=data.get("dimensions", {}),
                    notes=data.get("notes", []),
                    suggested_operations=data.get("suggested_operations", []),
                    raw_description=response_text,
                )

            # Fallback: return raw description
            return SketchAnalysisResult(
                success=True,
                raw_description=response_text,
                notes=["Could not parse structured response"],
            )

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return SketchAnalysisResult(
                success=True,
                raw_description=response_text,
                notes=["Response was not in expected JSON format"],
            )

    def _parse_geometry(self, data: Dict[str, Any]) -> Optional[DetectedGeometry]:
        """Parse geometry data from response."""
        try:
            geo_type = GeometryType(data.get("type", "unknown"))
        except ValueError:
            geo_type = GeometryType.UNKNOWN

        # Parse center point
        center = None
        if "center" in data:
            center = Point(
                x=data["center"].get("x", 0),
                y=data["center"].get("y", 0),
            )

        # Parse other points
        points = []
        if "points" in data:
            for p in data["points"]:
                points.append(Point(x=p.get("x", 0), y=p.get("y", 0)))

        return DetectedGeometry(
            geometry_type=geo_type,
            points=points,
            center=center,
            radius=data.get("radius"),
            width=data.get("width"),
            height=data.get("height"),
            depth=data.get("depth"),
            confidence=data.get("confidence", 0.5),
            notes=data.get("notes", data.get("description", "")),
        )

    def generate_gcode_suggestions(
        self,
        result: SketchAnalysisResult,
        material: str = "aluminum",
        tool_diameter: float = 0.25,
    ) -> List[str]:
        """
        Generate G-code suggestions from analysis result.

        Args:
            result: Sketch analysis result
            material: Material type
            tool_diameter: Tool diameter in inches

        Returns:
            List of G-code operation suggestions
        """
        suggestions = []

        for geometry in result.geometries:
            if geometry.geometry_type == GeometryType.HOLE:
                if geometry.radius and geometry.center and geometry.depth:
                    suggestions.append(
                        f"( Drill hole at X{geometry.center.x:.3f} Y{geometry.center.y:.3f} )\n"
                        f"G0 X{geometry.center.x:.3f} Y{geometry.center.y:.3f}\n"
                        f"G1 Z{-geometry.depth:.3f} F10.0\n"
                        f"G0 Z0.1"
                    )

            elif geometry.geometry_type == GeometryType.CIRCLE:
                if geometry.radius and geometry.center:
                    suggestions.append(
                        f"( Circular profile at X{geometry.center.x:.3f} Y{geometry.center.y:.3f} R{geometry.radius:.3f} )\n"
                        f"( Use circular interpolation G2/G3 )"
                    )

            elif geometry.geometry_type == GeometryType.RECTANGLE:
                if geometry.width and geometry.height and geometry.center:
                    suggestions.append(
                        f"( Rectangular profile {geometry.width:.3f} x {geometry.height:.3f} )\n"
                        f"( Center: X{geometry.center.x:.3f} Y{geometry.center.y:.3f} )"
                    )

            elif geometry.geometry_type == GeometryType.POCKET:
                if geometry.width and geometry.height and geometry.depth:
                    suggestions.append(
                        f"( Pocket {geometry.width:.3f} x {geometry.height:.3f} x {geometry.depth:.3f} deep )\n"
                        f"( Use adaptive clearing strategy )"
                    )

        return suggestions

    def to_dxf_points(
        self,
        result: SketchAnalysisResult,
    ) -> str:
        """
        Convert analysis result to simple DXF-like format.

        Args:
            result: Sketch analysis result

        Returns:
            Simple point/line format for CAD import
        """
        lines = ["( Sketch to CAD Export )", "( Points and Lines )"]

        for i, geometry in enumerate(result.geometries):
            lines.append(f"\n( Geometry {i + 1}: {geometry.geometry_type.value} )")

            if geometry.points:
                for j, point in enumerate(geometry.points):
                    lines.append(f"POINT {point.x:.4f} {point.y:.4f}")

                if len(geometry.points) >= 2:
                    for j in range(len(geometry.points) - 1):
                        p1, p2 = geometry.points[j], geometry.points[j + 1]
                        lines.append(
                            f"LINE {p1.x:.4f} {p1.y:.4f} {p2.x:.4f} {p2.y:.4f}"
                        )

            elif geometry.center:
                if geometry.geometry_type == GeometryType.CIRCLE and geometry.radius:
                    lines.append(
                        f"CIRCLE {geometry.center.x:.4f} {geometry.center.y:.4f} "
                        f"{geometry.radius:.4f}"
                    )
                else:
                    lines.append(
                        f"POINT {geometry.center.x:.4f} {geometry.center.y:.4f}"
                    )

        return "\n".join(lines)
