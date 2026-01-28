"""
AI Guardrails Framework for LEGO MCP Manufacturing System

DoD/ONR-class AI safety controls providing:
- Input validation and sanitization
- Output verification against physics
- Confidence thresholds and rejection
- Human-in-the-loop escalation
- Hallucination detection
- Safety filtering for manufacturing actions

Designed for trustworthy AI in safety-critical manufacturing.

Reference Standards:
- NIST AI Risk Management Framework
- DoD AI Ethical Principles
- IEC 61508 (for AI in safety systems)
"""

from .input_validator import InputValidator, ValidationResult
from .output_verifier import OutputVerifier, VerificationResult
from .confidence_thresholds import ConfidenceThresholds, ThresholdResult
from .human_in_loop import HumanInLoopManager, EscalationLevel
from .hallucination_detector import HallucinationDetector, DetectionResult
from .safety_filter import SafetyFilter, FilterResult

__all__ = [
    "InputValidator",
    "ValidationResult",
    "OutputVerifier",
    "VerificationResult",
    "ConfidenceThresholds",
    "ThresholdResult",
    "HumanInLoopManager",
    "EscalationLevel",
    "HallucinationDetector",
    "DetectionResult",
    "SafetyFilter",
    "FilterResult",
]
