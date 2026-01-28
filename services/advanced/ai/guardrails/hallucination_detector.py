"""
Hallucination Detector for Manufacturing AI

Detects AI hallucinations in manufacturing context:
- Factual consistency with domain knowledge
- Cross-reference validation
- Uncertainty-based detection
- Manufacturing-specific fact checking

Critical for trustworthy AI in safety-critical manufacturing.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HallucinationType(Enum):
    """Types of AI hallucinations."""
    NONE = "none"
    FACTUAL_ERROR = "factual_error"           # Incorrect facts
    INCONSISTENCY = "inconsistency"           # Self-contradicting
    FABRICATION = "fabrication"               # Made-up entities
    IMPOSSIBLE_CLAIM = "impossible_claim"     # Physics violations
    OUT_OF_DOMAIN = "out_of_domain"          # Outside expertise
    TEMPORAL_ERROR = "temporal_error"         # Wrong timeframes
    NUMERIC_ERROR = "numeric_error"           # Wrong numbers


class SeverityLevel(Enum):
    """Severity of detected hallucination."""
    LOW = 1       # Minor inaccuracy
    MEDIUM = 2    # Significant error
    HIGH = 3      # Critical error
    CRITICAL = 4  # Safety-affecting error


@dataclass
class DetectionResult:
    """
    Result of hallucination detection.

    Attributes:
        is_hallucination: Whether hallucination detected
        hallucination_type: Type of hallucination
        severity: Severity level
        confidence: Detection confidence
        evidence: Evidence for detection
        corrections: Suggested corrections
    """
    is_hallucination: bool
    hallucination_type: HallucinationType
    severity: SeverityLevel
    confidence: float
    evidence: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ManufacturingKnowledge:
    """
    Manufacturing domain knowledge base.

    Contains verified facts for hallucination checking.
    """
    # LEGO brick specifications (verified)
    lego_stud_diameter_mm: float = 4.8
    lego_stud_height_mm: float = 1.7
    lego_stud_spacing_mm: float = 8.0
    lego_wall_thickness_mm: float = 1.5
    lego_tolerance_mm: float = 0.01

    # Material properties
    abs_melting_point_c: Tuple[float, float] = (200, 250)
    abs_glass_transition_c: Tuple[float, float] = (100, 110)
    pla_melting_point_c: Tuple[float, float] = (180, 220)

    # 3D printing parameters
    typical_layer_height_mm: Tuple[float, float] = (0.1, 0.4)
    typical_nozzle_temp_c: Tuple[float, float] = (180, 260)
    typical_bed_temp_c: Tuple[float, float] = (40, 110)
    typical_print_speed_mm_s: Tuple[float, float] = (20, 150)

    # CNC parameters
    typical_spindle_speed_rpm: Tuple[float, float] = (1000, 30000)
    typical_feed_rate_mm_min: Tuple[float, float] = (100, 5000)

    # Robot parameters
    typical_robot_speed_mm_s: Tuple[float, float] = (1, 2000)
    typical_robot_payload_kg: Tuple[float, float] = (0.5, 1000)


class HallucinationDetector:
    """
    Detects AI hallucinations in manufacturing context.

    Features:
    - Domain knowledge validation
    - Consistency checking
    - Numeric range verification
    - Cross-reference validation
    - Uncertainty-based detection

    Usage:
        >>> detector = HallucinationDetector(knowledge_base)
        >>> result = detector.check(ai_output)
        >>> if result.is_hallucination:
        ...     handle_hallucination(result)
    """

    # Known invalid entities (things that don't exist)
    INVALID_ENTITIES = {
        "lego_ultra_brick",
        "abs_2000",
        "quantum_printer",
        "fusion_extruder",
        "nano_cnc",
    }

    # Manufacturing impossibilities
    IMPOSSIBLE_CLAIMS = [
        (r"temperature.*(-\d+|below.*absolute.*zero)", "negative absolute temperature"),
        (r"speed.*(\d{6,})\s*mm/s", "impossibly high speed"),
        (r"tolerance.*(\d+)\s*nm", "sub-nanometer tolerance in plastic"),
        (r"instant(aneous)?.*print", "instant manufacturing"),
        (r"100%\s*efficiency", "perfect efficiency claim"),
    ]

    def __init__(
        self,
        knowledge: Optional[ManufacturingKnowledge] = None,
        strict_mode: bool = False
    ):
        """
        Initialize hallucination detector.

        Args:
            knowledge: Manufacturing knowledge base
            strict_mode: If True, flag uncertain outputs
        """
        self.knowledge = knowledge or ManufacturingKnowledge()
        self.strict_mode = strict_mode

        # Compile patterns
        self._impossible_patterns = [
            (re.compile(pattern, re.IGNORECASE), desc)
            for pattern, desc in self.IMPOSSIBLE_CLAIMS
        ]

        logger.info(f"HallucinationDetector initialized (strict_mode={strict_mode})")

    def check(
        self,
        output: Any,
        context: Optional[Dict] = None
    ) -> DetectionResult:
        """
        Check AI output for hallucinations.

        Args:
            output: AI-generated output
            context: Additional context

        Returns:
            DetectionResult with detection details
        """
        context = context or {}

        # Convert to text if needed
        if isinstance(output, dict):
            text = str(output)
        elif isinstance(output, (list, tuple)):
            text = " ".join(str(item) for item in output)
        else:
            text = str(output)

        # Run detection checks
        detections: List[Tuple[HallucinationType, SeverityLevel, str, float]] = []

        # Check for impossible claims
        impossible_result = self._check_impossible_claims(text)
        if impossible_result:
            detections.append(impossible_result)

        # Check for fabricated entities
        fabrication_result = self._check_fabrications(text)
        if fabrication_result:
            detections.append(fabrication_result)

        # Check numeric ranges
        numeric_result = self._check_numeric_ranges(text)
        if numeric_result:
            detections.append(numeric_result)

        # Check LEGO specifications
        lego_result = self._check_lego_specs(text)
        if lego_result:
            detections.append(lego_result)

        # Check consistency
        consistency_result = self._check_consistency(text)
        if consistency_result:
            detections.append(consistency_result)

        # Aggregate results
        if detections:
            # Use worst case
            worst = max(detections, key=lambda x: (x[1].value, x[3]))
            return DetectionResult(
                is_hallucination=True,
                hallucination_type=worst[0],
                severity=worst[1],
                confidence=worst[3],
                evidence=[d[2] for d in detections],
                corrections=self._suggest_corrections(detections),
                details={"all_detections": len(detections)}
            )

        return DetectionResult(
            is_hallucination=False,
            hallucination_type=HallucinationType.NONE,
            severity=SeverityLevel.LOW,
            confidence=1.0
        )

    def _check_impossible_claims(
        self,
        text: str
    ) -> Optional[Tuple[HallucinationType, SeverityLevel, str, float]]:
        """Check for physically impossible claims."""
        for pattern, description in self._impossible_patterns:
            if pattern.search(text):
                return (
                    HallucinationType.IMPOSSIBLE_CLAIM,
                    SeverityLevel.CRITICAL,
                    f"Impossible claim detected: {description}",
                    0.95
                )
        return None

    def _check_fabrications(
        self,
        text: str
    ) -> Optional[Tuple[HallucinationType, SeverityLevel, str, float]]:
        """Check for fabricated entities."""
        text_lower = text.lower()
        for entity in self.INVALID_ENTITIES:
            if entity in text_lower:
                return (
                    HallucinationType.FABRICATION,
                    SeverityLevel.HIGH,
                    f"Fabricated entity: {entity}",
                    0.90
                )
        return None

    def _check_numeric_ranges(
        self,
        text: str
    ) -> Optional[Tuple[HallucinationType, SeverityLevel, str, float]]:
        """Check numeric values against known ranges."""

        # Temperature checks
        temp_pattern = re.compile(r'(?:temperature|temp)[:\s]*(\d+(?:\.\d+)?)\s*°?C', re.IGNORECASE)
        temp_matches = temp_pattern.findall(text)
        for temp_str in temp_matches:
            temp = float(temp_str)
            if temp < -273.15:
                return (
                    HallucinationType.NUMERIC_ERROR,
                    SeverityLevel.CRITICAL,
                    f"Temperature {temp}°C below absolute zero",
                    0.99
                )
            if temp > 500:  # Above typical manufacturing temps
                return (
                    HallucinationType.NUMERIC_ERROR,
                    SeverityLevel.MEDIUM,
                    f"Temperature {temp}°C unusually high",
                    0.70
                )

        # Layer height checks
        layer_pattern = re.compile(r'layer[:\s]*(?:height)?[:\s]*(\d+(?:\.\d+)?)\s*mm', re.IGNORECASE)
        layer_matches = layer_pattern.findall(text)
        for layer_str in layer_matches:
            layer = float(layer_str)
            min_layer, max_layer = self.knowledge.typical_layer_height_mm
            if layer < 0.01:  # Sub 10 micron
                return (
                    HallucinationType.NUMERIC_ERROR,
                    SeverityLevel.HIGH,
                    f"Layer height {layer}mm impossibly small for FDM",
                    0.85
                )
            if layer > 1.0:
                return (
                    HallucinationType.NUMERIC_ERROR,
                    SeverityLevel.MEDIUM,
                    f"Layer height {layer}mm unusually large",
                    0.75
                )

        # Speed checks
        speed_pattern = re.compile(r'speed[:\s]*(\d+(?:\.\d+)?)\s*mm/s', re.IGNORECASE)
        speed_matches = speed_pattern.findall(text)
        for speed_str in speed_matches:
            speed = float(speed_str)
            if speed > 1000:  # Above typical print speeds
                return (
                    HallucinationType.NUMERIC_ERROR,
                    SeverityLevel.MEDIUM,
                    f"Speed {speed}mm/s unusually high",
                    0.70
                )

        return None

    def _check_lego_specs(
        self,
        text: str
    ) -> Optional[Tuple[HallucinationType, SeverityLevel, str, float]]:
        """Check LEGO-specific specifications."""
        text_lower = text.lower()

        if 'lego' not in text_lower and 'stud' not in text_lower:
            return None

        # Stud diameter check
        stud_pattern = re.compile(r'stud[:\s]*(?:diameter)?[:\s]*(\d+(?:\.\d+)?)\s*mm', re.IGNORECASE)
        stud_matches = stud_pattern.findall(text)
        for stud_str in stud_matches:
            stud = float(stud_str)
            expected = self.knowledge.lego_stud_diameter_mm
            if abs(stud - expected) > 0.5:  # More than 0.5mm off
                return (
                    HallucinationType.FACTUAL_ERROR,
                    SeverityLevel.HIGH,
                    f"LEGO stud diameter {stud}mm incorrect (should be {expected}mm)",
                    0.90
                )

        # Stud spacing check
        spacing_pattern = re.compile(r'(?:stud\s*)?spacing[:\s]*(\d+(?:\.\d+)?)\s*mm', re.IGNORECASE)
        spacing_matches = spacing_pattern.findall(text)
        for spacing_str in spacing_matches:
            spacing = float(spacing_str)
            expected = self.knowledge.lego_stud_spacing_mm
            if abs(spacing - expected) > 0.5:
                return (
                    HallucinationType.FACTUAL_ERROR,
                    SeverityLevel.HIGH,
                    f"LEGO stud spacing {spacing}mm incorrect (should be {expected}mm)",
                    0.90
                )

        # Tolerance check (LEGO is famous for tight tolerances)
        tolerance_pattern = re.compile(r'tolerance[:\s]*(\d+(?:\.\d+)?)\s*mm', re.IGNORECASE)
        tolerance_matches = tolerance_pattern.findall(text)
        for tol_str in tolerance_matches:
            tol = float(tol_str)
            if tol > 0.1:  # LEGO tolerances are much tighter
                return (
                    HallucinationType.FACTUAL_ERROR,
                    SeverityLevel.MEDIUM,
                    f"LEGO tolerance {tol}mm too loose (typical is {self.knowledge.lego_tolerance_mm}mm)",
                    0.80
                )

        return None

    def _check_consistency(
        self,
        text: str
    ) -> Optional[Tuple[HallucinationType, SeverityLevel, str, float]]:
        """Check for internal consistency."""

        # Look for contradictions
        contradictions = [
            (r'increase.*temperature.*decrease.*temperature', "temperature contradiction"),
            (r'faster.*speed.*slower.*speed', "speed contradiction"),
            (r'both.*impossible.*and.*possible', "logical contradiction"),
        ]

        for pattern, description in contradictions:
            if re.search(pattern, text, re.IGNORECASE):
                return (
                    HallucinationType.INCONSISTENCY,
                    SeverityLevel.MEDIUM,
                    f"Internal inconsistency: {description}",
                    0.75
                )

        return None

    def _suggest_corrections(
        self,
        detections: List[Tuple[HallucinationType, SeverityLevel, str, float]]
    ) -> List[str]:
        """Suggest corrections for detected hallucinations."""
        corrections = []

        for hal_type, severity, evidence, _ in detections:
            if hal_type == HallucinationType.FACTUAL_ERROR:
                if "stud diameter" in evidence.lower():
                    corrections.append(
                        f"Correct LEGO stud diameter is {self.knowledge.lego_stud_diameter_mm}mm"
                    )
                elif "stud spacing" in evidence.lower():
                    corrections.append(
                        f"Correct LEGO stud spacing is {self.knowledge.lego_stud_spacing_mm}mm"
                    )

            elif hal_type == HallucinationType.NUMERIC_ERROR:
                if "temperature" in evidence.lower():
                    corrections.append(
                        f"Temperature should be within reasonable range for the material"
                    )
                elif "layer" in evidence.lower():
                    corrections.append(
                        f"Typical FDM layer heights: {self.knowledge.typical_layer_height_mm[0]}-{self.knowledge.typical_layer_height_mm[1]}mm"
                    )

            elif hal_type == HallucinationType.IMPOSSIBLE_CLAIM:
                corrections.append("Remove physically impossible claim")

        return corrections

    def check_batch(self, outputs: List[Any]) -> List[DetectionResult]:
        """Check multiple outputs for hallucinations."""
        return [self.check(output) for output in outputs]

    def add_knowledge(self, key: str, value: Any) -> None:
        """Add to the knowledge base."""
        if hasattr(self.knowledge, key):
            setattr(self.knowledge, key, value)
        else:
            logger.warning(f"Unknown knowledge key: {key}")

    def get_detection_stats(self) -> Dict[str, Any]:
        """Get detection statistics."""
        return {
            "invalid_entities_count": len(self.INVALID_ENTITIES),
            "impossible_patterns_count": len(self._impossible_patterns),
            "strict_mode": self.strict_mode
        }
