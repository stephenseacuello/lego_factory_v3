"""
Part Inspection Service.

Visual quality inspection of machined parts:
- Surface defect detection
- Feature verification
- Dimensional conformance
- Quality scoring
"""

import logging
import base64
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class DefectType(Enum):
    """Types of defects."""
    BURR = "burr"
    SCRATCH = "scratch"
    GOUGE = "gouge"
    CHIP = "chip"
    CRACK = "crack"
    PIT = "pit"
    DISCOLORATION = "discoloration"
    TOOL_MARK = "tool_mark"
    MISSING_FEATURE = "missing_feature"
    INCORRECT_DIMENSION = "incorrect_dimension"
    SURFACE_ROUGHNESS = "surface_roughness"
    CONTAMINATION = "contamination"
    UNKNOWN = "unknown"


class SeverityLevel(Enum):
    """Defect severity levels."""
    CRITICAL = "critical"   # Part reject
    MAJOR = "major"         # Requires rework
    MINOR = "minor"         # Cosmetic, may be acceptable
    INFORMATIONAL = "info"  # Note for process improvement


@dataclass
class DetectedDefect:
    """A detected defect on the part."""
    defect_type: DefectType
    severity: SeverityLevel
    location: str
    description: str
    confidence: float = 0.0
    dimensions: Optional[Dict[str, float]] = None  # Size of defect
    suggested_action: str = ""


@dataclass
class QualityScore:
    """Overall quality assessment."""
    score: float  # 0-100
    grade: str    # A, B, C, D, F
    pass_fail: bool
    summary: str


@dataclass
class InspectionResult:
    """Result of part inspection."""
    success: bool
    part_identified: bool = False
    part_description: str = ""
    defects: List[DetectedDefect] = field(default_factory=list)
    quality_score: Optional[QualityScore] = None
    features_verified: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    raw_analysis: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class PartInspection:
    """
    Visual inspection of machined parts.

    Uses Claude's vision to:
    - Detect surface defects
    - Verify features are present
    - Assess overall quality
    """

    INSPECTION_PROMPT = """Inspect this machined part for quality defects.

{context}

Analyze the image and identify:
1. Any surface defects (burrs, scratches, tool marks, chips)
2. Visible features and their condition
3. Surface finish quality
4. Any contamination or foreign material

For each defect found, assess severity:
- CRITICAL: Part must be rejected (functional or safety issue)
- MAJOR: Requires rework (out of spec but fixable)
- MINOR: Cosmetic issue (may be acceptable)
- INFO: Process improvement note

Format your response as JSON:
{{
    "part_identified": true,
    "part_description": "Aluminum bracket with 4 mounting holes",
    "defects": [
        {{
            "type": "burr",
            "severity": "minor",
            "location": "left edge near hole 1",
            "description": "Small machining burr approximately 0.5mm",
            "confidence": 0.9,
            "dimensions": {{"length": 2.0, "height": 0.5}},
            "suggested_action": "Deburr with file or tumble"
        }}
    ],
    "features_verified": [
        "4 mounting holes present",
        "Edge radii completed",
        "Surface finish acceptable"
    ],
    "quality_score": {{
        "score": 85,
        "grade": "B",
        "pass_fail": true,
        "summary": "Part acceptable with minor deburring required"
    }},
    "notes": ["Good overall machining quality", "Consider adjusting feed rate to reduce burrs"]
}}

Be thorough but fair in assessment. Note both defects AND positive quality indicators."""

    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize part inspection service."""
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

    async def inspect(
        self,
        image_data: bytes,
        image_type: str = "image/jpeg",
        part_number: Optional[str] = None,
        expected_features: Optional[List[str]] = None,
        material: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> InspectionResult:
        """
        Inspect a part for quality defects.

        Args:
            image_data: Raw image bytes
            image_type: MIME type of the image
            part_number: Part number for reference
            expected_features: List of features that should be present
            material: Material type (helps with defect identification)
            operation: Machining operation performed

        Returns:
            Inspection result with defects and quality score
        """
        if not self.client:
            return InspectionResult(
                success=False,
                notes=["Claude API not configured"],
            )

        try:
            # Build context
            context = self._build_context(
                part_number, expected_features, material, operation
            )

            # Encode image
            image_b64 = base64.standard_b64encode(image_data).decode("utf-8")

            # Build prompt
            prompt = self.INSPECTION_PROMPT.format(context=context)

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
            return self._parse_inspection_response(response_text)

        except Exception as e:
            logger.error(f"Inspection error: {e}")
            return InspectionResult(
                success=False,
                notes=[f"Inspection failed: {str(e)}"],
            )

    def _build_context(
        self,
        part_number: Optional[str],
        expected_features: Optional[List[str]],
        material: Optional[str],
        operation: Optional[str],
    ) -> str:
        """Build context information for the prompt."""
        lines = []

        if part_number:
            lines.append(f"Part Number: {part_number}")

        if material:
            lines.append(f"Material: {material}")

        if operation:
            lines.append(f"Operation: {operation}")

        if expected_features:
            lines.append("Expected Features:")
            for feature in expected_features:
                lines.append(f"  - {feature}")

        return "\n".join(lines) if lines else "No additional context provided."

    def _parse_inspection_response(
        self,
        response_text: str,
    ) -> InspectionResult:
        """Parse Claude's inspection response."""
        try:
            # Extract JSON
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)

                # Parse defects
                defects = []
                for defect_data in data.get("defects", []):
                    defect = self._parse_defect(defect_data)
                    if defect:
                        defects.append(defect)

                # Parse quality score
                quality_score = None
                if "quality_score" in data:
                    qs_data = data["quality_score"]
                    quality_score = QualityScore(
                        score=float(qs_data.get("score", 0)),
                        grade=qs_data.get("grade", "F"),
                        pass_fail=qs_data.get("pass_fail", False),
                        summary=qs_data.get("summary", ""),
                    )

                return InspectionResult(
                    success=True,
                    part_identified=data.get("part_identified", False),
                    part_description=data.get("part_description", ""),
                    defects=defects,
                    quality_score=quality_score,
                    features_verified=data.get("features_verified", []),
                    notes=data.get("notes", []),
                    raw_analysis=response_text,
                )

            return InspectionResult(
                success=True,
                raw_analysis=response_text,
                notes=["Could not parse structured response"],
            )

        except json.JSONDecodeError:
            return InspectionResult(
                success=True,
                raw_analysis=response_text,
                notes=["Response was not in expected JSON format"],
            )

    def _parse_defect(
        self,
        data: Dict[str, Any],
    ) -> Optional[DetectedDefect]:
        """Parse defect data from response."""
        try:
            defect_type = DefectType(data.get("type", "unknown"))
        except ValueError:
            defect_type = DefectType.UNKNOWN

        try:
            severity = SeverityLevel(data.get("severity", "info"))
        except ValueError:
            severity = SeverityLevel.INFORMATIONAL

        return DetectedDefect(
            defect_type=defect_type,
            severity=severity,
            location=data.get("location", ""),
            description=data.get("description", ""),
            confidence=float(data.get("confidence", 0.5)),
            dimensions=data.get("dimensions"),
            suggested_action=data.get("suggested_action", ""),
        )

    async def compare_to_reference(
        self,
        part_image: bytes,
        reference_image: bytes,
        image_type: str = "image/jpeg",
    ) -> InspectionResult:
        """
        Compare a part to a reference/golden sample.

        Args:
            part_image: Image of part to inspect
            reference_image: Image of known good part
            image_type: MIME type of images

        Returns:
            Inspection result with comparison notes
        """
        if not self.client:
            return InspectionResult(
                success=False,
                notes=["Claude API not configured"],
            )

        try:
            part_b64 = base64.standard_b64encode(part_image).decode("utf-8")
            ref_b64 = base64.standard_b64encode(reference_image).decode("utf-8")

            prompt = """Compare these two images:

Image 1: Part to inspect
Image 2: Reference/golden sample

Identify any differences between the inspected part and the reference:
1. Missing features
2. Extra features or defects
3. Dimensional differences
4. Surface finish differences
5. Color/appearance differences

Provide a pass/fail assessment based on the comparison.

Format as JSON with the same structure as standard inspection."""

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Image 1 - Part to Inspect:",
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_type,
                                "data": part_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Image 2 - Reference Sample:",
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_type,
                                "data": ref_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }],
            )

            return self._parse_inspection_response(response.content[0].text)

        except Exception as e:
            logger.error(f"Comparison error: {e}")
            return InspectionResult(
                success=False,
                notes=[f"Comparison failed: {str(e)}"],
            )

    def generate_report(self, result: InspectionResult) -> str:
        """Generate a formatted inspection report."""
        lines = [
            "=" * 50,
            "PART INSPECTION REPORT",
            "=" * 50,
            f"Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        if result.part_identified:
            lines.append(f"Part: {result.part_description}")
        lines.append("")

        # Quality Score
        if result.quality_score:
            qs = result.quality_score
            status = "✓ PASS" if qs.pass_fail else "✗ FAIL"
            lines.extend([
                f"Quality Score: {qs.score:.0f}/100 (Grade: {qs.grade})",
                f"Status: {status}",
                f"Summary: {qs.summary}",
                "",
            ])

        # Defects
        if result.defects:
            lines.append("DEFECTS FOUND:")
            lines.append("-" * 40)

            for i, defect in enumerate(result.defects, 1):
                severity_icon = {
                    SeverityLevel.CRITICAL: "🔴",
                    SeverityLevel.MAJOR: "🟠",
                    SeverityLevel.MINOR: "🟡",
                    SeverityLevel.INFORMATIONAL: "🔵",
                }.get(defect.severity, "⚪")

                lines.extend([
                    f"{i}. {severity_icon} {defect.defect_type.value.upper()}",
                    f"   Severity: {defect.severity.value}",
                    f"   Location: {defect.location}",
                    f"   Description: {defect.description}",
                    f"   Confidence: {defect.confidence * 100:.0f}%",
                ])

                if defect.suggested_action:
                    lines.append(f"   Action: {defect.suggested_action}")
                lines.append("")
        else:
            lines.extend([
                "DEFECTS FOUND: None",
                "",
            ])

        # Features Verified
        if result.features_verified:
            lines.append("FEATURES VERIFIED:")
            for feature in result.features_verified:
                lines.append(f"  ✓ {feature}")
            lines.append("")

        # Notes
        if result.notes:
            lines.append("NOTES:")
            for note in result.notes:
                lines.append(f"  • {note}")

        lines.append("=" * 50)

        return "\n".join(lines)
