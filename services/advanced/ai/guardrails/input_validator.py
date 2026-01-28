"""
AI Input Validator

Validates and sanitizes all inputs before LLM/AI processing.

Features:
- Prompt injection detection
- PII redaction
- Input length limits
- Content classification
- Manufacturing context validation
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Input validation status."""
    VALID = "valid"
    SANITIZED = "sanitized"
    REJECTED = "rejected"
    WARNING = "warning"


class ThreatType(Enum):
    """Types of input threats."""
    NONE = "none"
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    PII = "pii"
    MALICIOUS_CODE = "malicious_code"
    EXCESSIVE_LENGTH = "excessive_length"
    UNSAFE_CONTENT = "unsafe_content"


@dataclass
class ValidationResult:
    """
    Result of input validation.

    Attributes:
        status: Validation status
        original_input: Original input
        sanitized_input: Cleaned input (if sanitized)
        threats_detected: List of detected threats
        confidence: Validation confidence
        details: Additional details
    """
    status: ValidationStatus
    original_input: str
    sanitized_input: str
    threats_detected: List[ThreatType] = field(default_factory=list)
    confidence: float = 1.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidatorConfig:
    """
    Input validator configuration.

    Attributes:
        max_input_length: Maximum allowed input length
        enable_pii_detection: Enable PII detection
        enable_injection_detection: Enable prompt injection detection
        blocked_patterns: Regex patterns to block
        manufacturing_context_required: Require manufacturing context
    """
    max_input_length: int = 10000
    enable_pii_detection: bool = True
    enable_injection_detection: bool = True
    blocked_patterns: List[str] = field(default_factory=list)
    manufacturing_context_required: bool = False
    strict_mode: bool = False


class InputValidator:
    """
    Validates and sanitizes inputs for AI processing.

    Provides defense against:
    - Prompt injection attacks
    - Jailbreak attempts
    - PII exposure
    - Malicious payloads
    - Off-topic queries

    Usage:
        >>> validator = InputValidator(config)
        >>> result = validator.validate(user_input)
        >>> if result.status == ValidationStatus.VALID:
        ...     process_with_ai(result.sanitized_input)
    """

    # Common prompt injection patterns
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|all|above)\s+(instructions?|prompts?)",
        r"disregard\s+(everything|all)\s+(above|before)",
        r"you\s+are\s+now\s+(a|an)\s+",
        r"pretend\s+(to\s+be|you\s+are)",
        r"act\s+as\s+(if|though)",
        r"forget\s+(everything|all)",
        r"new\s+instructions?:",
        r"system\s+prompt:",
        r"\[INST\]",
        r"<\|system\|>",
        r"<\|user\|>",
        r"<\|assistant\|>",
    ]

    # PII patterns
    PII_PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    }

    # Manufacturing-related keywords
    MANUFACTURING_KEYWORDS = {
        "cnc", "3d print", "lego", "brick", "mold", "injection",
        "assembly", "robot", "arm", "agv", "conveyor", "machine",
        "tool", "spindle", "temperature", "pressure", "quality",
        "inspection", "defect", "tolerance", "dimension", "layer",
        "extrusion", "filament", "nozzle", "bed", "gcode", "cam",
    }

    def __init__(self, config: Optional[ValidatorConfig] = None):
        """
        Initialize input validator.

        Args:
            config: Validator configuration
        """
        self.config = config or ValidatorConfig()

        # Compile patterns
        self._injection_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS
        ]
        self._pii_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.PII_PATTERNS.items()
        }
        self._blocked_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.blocked_patterns
        ]

        logger.info("InputValidator initialized")

    def validate(self, input_text: str) -> ValidationResult:
        """
        Validate and sanitize input.

        Args:
            input_text: Raw input text

        Returns:
            ValidationResult with status and sanitized text
        """
        threats: List[ThreatType] = []
        sanitized = input_text
        details: Dict[str, Any] = {}

        # Length check
        if len(input_text) > self.config.max_input_length:
            threats.append(ThreatType.EXCESSIVE_LENGTH)
            sanitized = input_text[:self.config.max_input_length]
            details["truncated"] = True
            details["original_length"] = len(input_text)

        # Prompt injection detection
        if self.config.enable_injection_detection:
            injection_result = self._detect_injection(input_text)
            if injection_result["detected"]:
                threats.append(ThreatType.PROMPT_INJECTION)
                details["injection_patterns"] = injection_result["patterns"]

        # PII detection and redaction
        if self.config.enable_pii_detection:
            pii_result = self._detect_and_redact_pii(sanitized)
            if pii_result["detected"]:
                threats.append(ThreatType.PII)
                sanitized = pii_result["sanitized"]
                details["pii_types"] = pii_result["types"]

        # Blocked patterns
        for pattern in self._blocked_patterns:
            if pattern.search(input_text):
                threats.append(ThreatType.UNSAFE_CONTENT)
                details["blocked_pattern_matched"] = True
                break

        # Manufacturing context check
        if self.config.manufacturing_context_required:
            if not self._has_manufacturing_context(input_text):
                details["manufacturing_context"] = False
                if self.config.strict_mode:
                    return ValidationResult(
                        status=ValidationStatus.REJECTED,
                        original_input=input_text,
                        sanitized_input=sanitized,
                        threats_detected=threats,
                        confidence=0.9,
                        details=details
                    )

        # Determine final status
        if ThreatType.PROMPT_INJECTION in threats:
            if self.config.strict_mode:
                return ValidationResult(
                    status=ValidationStatus.REJECTED,
                    original_input=input_text,
                    sanitized_input="",
                    threats_detected=threats,
                    confidence=0.95,
                    details=details
                )

        if threats and sanitized != input_text:
            status = ValidationStatus.SANITIZED
        elif threats:
            status = ValidationStatus.WARNING
        else:
            status = ValidationStatus.VALID

        return ValidationResult(
            status=status,
            original_input=input_text,
            sanitized_input=sanitized,
            threats_detected=threats,
            confidence=self._compute_confidence(threats),
            details=details
        )

    def _detect_injection(self, text: str) -> Dict[str, Any]:
        """Detect prompt injection attempts."""
        detected_patterns = []

        for pattern in self._injection_patterns:
            if pattern.search(text):
                detected_patterns.append(pattern.pattern)

        return {
            "detected": len(detected_patterns) > 0,
            "patterns": detected_patterns
        }

    def _detect_and_redact_pii(self, text: str) -> Dict[str, Any]:
        """Detect and redact PII."""
        detected_types = []
        sanitized = text

        for pii_type, pattern in self._pii_patterns.items():
            if pattern.search(sanitized):
                detected_types.append(pii_type)
                sanitized = pattern.sub(f"[REDACTED_{pii_type.upper()}]", sanitized)

        return {
            "detected": len(detected_types) > 0,
            "types": detected_types,
            "sanitized": sanitized
        }

    def _has_manufacturing_context(self, text: str) -> bool:
        """Check if input has manufacturing context."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.MANUFACTURING_KEYWORDS)

    def _compute_confidence(self, threats: List[ThreatType]) -> float:
        """Compute validation confidence based on detected threats."""
        if not threats:
            return 1.0

        # Reduce confidence for each threat
        confidence = 1.0
        for threat in threats:
            if threat == ThreatType.PROMPT_INJECTION:
                confidence *= 0.3
            elif threat == ThreatType.PII:
                confidence *= 0.7
            elif threat == ThreatType.EXCESSIVE_LENGTH:
                confidence *= 0.9
            else:
                confidence *= 0.5

        return max(0.0, min(1.0, confidence))

    def validate_batch(self, inputs: List[str]) -> List[ValidationResult]:
        """Validate multiple inputs."""
        return [self.validate(text) for text in inputs]
