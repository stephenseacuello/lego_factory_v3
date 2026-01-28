"""
Drawing OCR Service.

Reads text and annotations from engineering drawings:
- Part numbers and revisions
- Dimensions and tolerances
- Notes and specifications
- Title block information
"""

import logging
import base64
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TextCategory(Enum):
    """Categories of text in drawings."""
    PART_NUMBER = "part_number"
    REVISION = "revision"
    DIMENSION = "dimension"
    TOLERANCE = "tolerance"
    MATERIAL = "material"
    SURFACE_FINISH = "surface_finish"
    NOTE = "note"
    TITLE = "title"
    SCALE = "scale"
    DATE = "date"
    AUTHOR = "author"
    APPROVAL = "approval"
    GD_T = "gd&t"  # Geometric Dimensioning & Tolerancing
    GENERAL = "general"


@dataclass
class ExtractedText:
    """Extracted text element from drawing."""
    text: str
    category: TextCategory
    confidence: float = 0.0
    location: str = ""  # Description of where found
    context: str = ""   # Surrounding context
    value: Optional[float] = None  # Numeric value if applicable
    unit: Optional[str] = None


@dataclass
class DrawingElement:
    """A recognized element in the drawing."""
    element_type: str  # e.g., "hole callout", "dimension line"
    description: str
    associated_text: List[ExtractedText] = field(default_factory=list)
    location: str = ""


@dataclass
class OCRResult:
    """Result of drawing OCR."""
    success: bool
    drawing_type: str = ""  # e.g., "mechanical drawing", "schematic"
    title_block: Dict[str, str] = field(default_factory=dict)
    extracted_text: List[ExtractedText] = field(default_factory=list)
    elements: List[DrawingElement] = field(default_factory=list)
    dimensions: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    raw_analysis: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class DrawingOCR:
    """
    Extracts text and annotations from engineering drawings.

    Uses Claude's vision to:
    - Read title block information
    - Extract dimensions and tolerances
    - Identify notes and specifications
    - Parse GD&T symbols
    """

    OCR_PROMPT = """Analyze this engineering drawing and extract all text and annotations.

Focus on:
1. Title Block Information:
   - Part number, revision, drawing number
   - Material specification
   - Author, date, approval signatures
   - Scale, sheet number

2. Dimensions:
   - All numeric dimensions with units
   - Tolerances (bilateral, unilateral, limit)
   - Reference dimensions

3. GD&T Symbols (if present):
   - Feature control frames
   - Datum references
   - Geometric tolerances

4. Notes and Specifications:
   - General notes
   - Specific call-outs
   - Surface finish requirements
   - Special processing instructions

5. Feature Call-outs:
   - Hole sizes and depths
   - Thread specifications
   - Chamfer and radius call-outs

Format your response as JSON:
{{
    "drawing_type": "mechanical drawing",
    "title_block": {{
        "part_number": "12345-001",
        "revision": "A",
        "title": "Mounting Bracket",
        "material": "6061-T6 Aluminum",
        "date": "2024-01-15",
        "scale": "1:1",
        "drawn_by": "JSmith"
    }},
    "extracted_text": [
        {{
            "text": "4X Ø0.250 THRU",
            "category": "dimension",
            "confidence": 0.95,
            "location": "center pattern",
            "value": 0.250,
            "unit": "inches"
        }}
    ],
    "elements": [
        {{
            "element_type": "hole callout",
            "description": "4 holes 0.250 diameter through",
            "location": "center of part"
        }}
    ],
    "dimensions": {{
        "overall_length": 4.000,
        "overall_width": 2.500,
        "overall_height": 0.500
    }},
    "notes": [
        "ALL DIMENSIONS IN INCHES",
        "BREAK ALL SHARP EDGES 0.010 MAX",
        "ANODIZE PER MIL-A-8625 TYPE II CLASS 2"
    ]
}}

Be thorough in extracting all visible text. Include confidence levels for uncertain readings."""

    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize drawing OCR service."""
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

    async def extract_text(
        self,
        image_data: bytes,
        image_type: str = "image/png",
        focus_area: Optional[str] = None,
    ) -> OCRResult:
        """
        Extract text from an engineering drawing.

        Args:
            image_data: Raw image bytes
            image_type: MIME type of the image
            focus_area: Optional area to focus on (e.g., "title block")

        Returns:
            OCR result with extracted text
        """
        if not self.client:
            return OCRResult(
                success=False,
                notes=["Claude API not configured"],
            )

        try:
            # Encode image
            image_b64 = base64.standard_b64encode(image_data).decode("utf-8")

            # Build prompt
            prompt = self.OCR_PROMPT
            if focus_area:
                prompt += f"\n\nFocus specifically on: {focus_area}"

            # Call Claude Vision
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
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
            return self._parse_ocr_response(response_text)

        except Exception as e:
            logger.error(f"OCR error: {e}")
            return OCRResult(
                success=False,
                notes=[f"OCR failed: {str(e)}"],
            )

    def _parse_ocr_response(self, response_text: str) -> OCRResult:
        """Parse Claude's OCR response."""
        try:
            # Extract JSON
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)

                # Parse extracted text
                extracted_text = []
                for text_data in data.get("extracted_text", []):
                    text = self._parse_extracted_text(text_data)
                    if text:
                        extracted_text.append(text)

                # Parse elements
                elements = []
                for elem_data in data.get("elements", []):
                    elements.append(DrawingElement(
                        element_type=elem_data.get("element_type", ""),
                        description=elem_data.get("description", ""),
                        location=elem_data.get("location", ""),
                    ))

                return OCRResult(
                    success=True,
                    drawing_type=data.get("drawing_type", ""),
                    title_block=data.get("title_block", {}),
                    extracted_text=extracted_text,
                    elements=elements,
                    dimensions=data.get("dimensions", {}),
                    notes=data.get("notes", []),
                    raw_analysis=response_text,
                )

            return OCRResult(
                success=True,
                raw_analysis=response_text,
                notes=["Could not parse structured response"],
            )

        except json.JSONDecodeError:
            return OCRResult(
                success=True,
                raw_analysis=response_text,
                notes=["Response was not in expected JSON format"],
            )

    def _parse_extracted_text(
        self,
        data: Dict[str, Any],
    ) -> Optional[ExtractedText]:
        """Parse extracted text data."""
        try:
            category = TextCategory(data.get("category", "general"))
        except ValueError:
            category = TextCategory.GENERAL

        return ExtractedText(
            text=data.get("text", ""),
            category=category,
            confidence=float(data.get("confidence", 0.5)),
            location=data.get("location", ""),
            context=data.get("context", ""),
            value=data.get("value"),
            unit=data.get("unit"),
        )

    async def extract_title_block(
        self,
        image_data: bytes,
        image_type: str = "image/png",
    ) -> Dict[str, str]:
        """
        Extract only title block information.

        Args:
            image_data: Raw image bytes
            image_type: MIME type

        Returns:
            Dictionary of title block fields
        """
        result = await self.extract_text(
            image_data,
            image_type,
            focus_area="title block",
        )
        return result.title_block

    async def extract_dimensions(
        self,
        image_data: bytes,
        image_type: str = "image/png",
    ) -> List[ExtractedText]:
        """
        Extract only dimensions from drawing.

        Args:
            image_data: Raw image bytes
            image_type: MIME type

        Returns:
            List of dimension text elements
        """
        result = await self.extract_text(
            image_data,
            image_type,
            focus_area="dimensions and tolerances",
        )

        return [
            text for text in result.extracted_text
            if text.category in [
                TextCategory.DIMENSION,
                TextCategory.TOLERANCE,
                TextCategory.GD_T,
            ]
        ]

    async def extract_bom(
        self,
        image_data: bytes,
        image_type: str = "image/png",
    ) -> List[Dict[str, Any]]:
        """
        Extract Bill of Materials if present.

        Args:
            image_data: Raw image bytes
            image_type: MIME type

        Returns:
            List of BOM items
        """
        if not self.client:
            return []

        try:
            image_b64 = base64.standard_b64encode(image_data).decode("utf-8")

            prompt = """Extract the Bill of Materials (BOM) from this drawing if present.

Return as JSON array:
[
    {
        "item": 1,
        "part_number": "12345",
        "description": "Mounting Bracket",
        "quantity": 2,
        "material": "Aluminum"
    }
]

If no BOM is visible, return an empty array []."""

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
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
                        {"type": "text", "text": prompt},
                    ],
                }],
            )

            response_text = response.content[0].text

            # Extract JSON array
            json_start = response_text.find("[")
            json_end = response_text.rfind("]") + 1

            if json_start >= 0 and json_end > json_start:
                return json.loads(response_text[json_start:json_end])

            return []

        except Exception as e:
            logger.error(f"BOM extraction error: {e}")
            return []

    def format_extracted_data(self, result: OCRResult) -> str:
        """Format OCR result as readable text."""
        lines = [
            "=" * 50,
            "DRAWING DATA EXTRACTION",
            "=" * 50,
            f"Drawing Type: {result.drawing_type}",
            "",
        ]

        # Title Block
        if result.title_block:
            lines.append("TITLE BLOCK:")
            lines.append("-" * 30)
            for key, value in result.title_block.items():
                lines.append(f"  {key.replace('_', ' ').title()}: {value}")
            lines.append("")

        # Dimensions
        if result.dimensions:
            lines.append("KEY DIMENSIONS:")
            lines.append("-" * 30)
            for key, value in result.dimensions.items():
                lines.append(f"  {key.replace('_', ' ').title()}: {value}")
            lines.append("")

        # Extracted Text by Category
        by_category: Dict[TextCategory, List[ExtractedText]] = {}
        for text in result.extracted_text:
            if text.category not in by_category:
                by_category[text.category] = []
            by_category[text.category].append(text)

        for category, texts in by_category.items():
            lines.append(f"{category.value.upper().replace('_', ' ')}:")
            lines.append("-" * 30)
            for text in texts:
                conf = f"({text.confidence * 100:.0f}%)" if text.confidence < 1 else ""
                lines.append(f"  • {text.text} {conf}")
                if text.location:
                    lines.append(f"    @ {text.location}")
            lines.append("")

        # Notes
        if result.notes:
            lines.append("NOTES:")
            lines.append("-" * 30)
            for i, note in enumerate(result.notes, 1):
                lines.append(f"  {i}. {note}")

        lines.append("=" * 50)

        return "\n".join(lines)
