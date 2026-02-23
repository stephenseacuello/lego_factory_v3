"""
Confidence Thresholds for AI Decision Making

Implements multi-tier confidence thresholds for manufacturing AI:
- Automatic execution (high confidence)
- Human confirmation (medium confidence)
- Rejection (low confidence)

Based on decision theory and manufacturing risk levels.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence level categories."""
    VERY_HIGH = "very_high"  # > 0.95
    HIGH = "high"            # 0.85 - 0.95
    MEDIUM = "medium"        # 0.70 - 0.85
    LOW = "low"              # 0.50 - 0.70
    VERY_LOW = "very_low"    # < 0.50


class ActionTier(Enum):
    """Action tiers based on confidence."""
    AUTO_EXECUTE = "auto_execute"      # Proceed without human
    HUMAN_CONFIRM = "human_confirm"    # Require human confirmation
    HUMAN_REVIEW = "human_review"      # Require human review and edit
    REJECT = "reject"                  # Do not proceed


class RiskLevel(Enum):
    """Manufacturing operation risk levels."""
    CRITICAL = "critical"    # E-stop, safety systems
    HIGH = "high"            # Robot motion, heating
    MEDIUM = "medium"        # Process parameters
    LOW = "low"              # Status queries, logging
    INFORMATIONAL = "informational"  # Pure information


@dataclass
class ThresholdResult:
    """
    Result of threshold evaluation.

    Attributes:
        action_tier: Recommended action tier
        confidence: Original confidence value
        confidence_level: Categorized confidence level
        risk_level: Operation risk level
        adjusted_threshold: Risk-adjusted threshold used
        reason: Explanation for the decision
        metadata: Additional decision metadata
    """
    action_tier: ActionTier
    confidence: float
    confidence_level: ConfidenceLevel
    risk_level: RiskLevel
    adjusted_threshold: float
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThresholdConfig:
    """
    Threshold configuration.

    Thresholds are adjusted based on risk level.
    Higher risk operations require higher confidence.
    """
    # Base thresholds (for LOW risk operations)
    auto_execute_threshold: float = 0.90
    human_confirm_threshold: float = 0.70
    human_review_threshold: float = 0.50
    # Below human_review_threshold -> reject

    # Risk multipliers (applied to thresholds)
    risk_multipliers: Dict[RiskLevel, float] = field(default_factory=lambda: {
        RiskLevel.CRITICAL: 1.10,     # 10% stricter
        RiskLevel.HIGH: 1.05,         # 5% stricter
        RiskLevel.MEDIUM: 1.00,       # No adjustment
        RiskLevel.LOW: 0.95,          # 5% more lenient
        RiskLevel.INFORMATIONAL: 0.90 # 10% more lenient
    })

    # Minimum confidence for any action
    absolute_minimum: float = 0.30

    # Enable adaptive thresholds
    adaptive_enabled: bool = True
    adaptation_rate: float = 0.01


class ConfidenceThresholds:
    """
    Manages confidence thresholds for AI decision making.

    Features:
    - Risk-adjusted thresholds
    - Adaptive threshold learning
    - Multi-model ensemble support
    - Calibration tracking
    - Audit logging

    Usage:
        >>> thresholds = ConfidenceThresholds(config)
        >>> result = thresholds.evaluate(confidence=0.85, risk_level=RiskLevel.HIGH)
        >>> if result.action_tier == ActionTier.AUTO_EXECUTE:
        ...     execute_action()
    """

    def __init__(
        self,
        config: Optional[ThresholdConfig] = None,
        operation_classifier: Optional[Callable] = None
    ):
        """
        Initialize confidence thresholds.

        Args:
            config: Threshold configuration
            operation_classifier: Optional function to classify operation risk
        """
        self.config = config or ThresholdConfig()
        self.operation_classifier = operation_classifier

        # Tracking for adaptive thresholds
        self._decision_history: List[Dict] = []
        self._calibration_errors: List[float] = []

        # Current adaptive adjustments
        self._adaptive_adjustments: Dict[RiskLevel, float] = {
            level: 0.0 for level in RiskLevel
        }

        logger.info("ConfidenceThresholds initialized")

    def evaluate(
        self,
        confidence: float,
        risk_level: Optional[RiskLevel] = None,
        operation_type: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> ThresholdResult:
        """
        Evaluate confidence against thresholds.

        Args:
            confidence: Confidence value (0-1)
            risk_level: Risk level of operation
            operation_type: Type of operation for classification
            context: Additional context

        Returns:
            ThresholdResult with action tier and details
        """
        context = context or {}

        # Classify risk if not provided
        if risk_level is None:
            if self.operation_classifier and operation_type:
                risk_level = self.operation_classifier(operation_type)
            else:
                risk_level = self._default_risk_classification(operation_type)

        # Categorize confidence level
        confidence_level = self._categorize_confidence(confidence)

        # Get risk-adjusted thresholds
        adjusted_thresholds = self._get_adjusted_thresholds(risk_level)

        # Determine action tier
        action_tier, reason = self._determine_action_tier(
            confidence,
            adjusted_thresholds,
            risk_level
        )

        result = ThresholdResult(
            action_tier=action_tier,
            confidence=confidence,
            confidence_level=confidence_level,
            risk_level=risk_level,
            adjusted_threshold=adjusted_thresholds['auto_execute'],
            reason=reason,
            metadata={
                "thresholds": adjusted_thresholds,
                "operation_type": operation_type,
                "context": context
            }
        )

        # Track decision
        self._track_decision(result)

        return result

    def _categorize_confidence(self, confidence: float) -> ConfidenceLevel:
        """Categorize confidence into levels."""
        if confidence > 0.95:
            return ConfidenceLevel.VERY_HIGH
        elif confidence > 0.85:
            return ConfidenceLevel.HIGH
        elif confidence > 0.70:
            return ConfidenceLevel.MEDIUM
        elif confidence > 0.50:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def _get_adjusted_thresholds(self, risk_level: RiskLevel) -> Dict[str, float]:
        """Get risk-adjusted thresholds."""
        multiplier = self.config.risk_multipliers.get(risk_level, 1.0)

        # Apply adaptive adjustment if enabled
        adaptive_adj = 0.0
        if self.config.adaptive_enabled:
            adaptive_adj = self._adaptive_adjustments.get(risk_level, 0.0)

        # Calculate adjusted thresholds
        auto_threshold = min(1.0, (self.config.auto_execute_threshold + adaptive_adj) * multiplier)
        confirm_threshold = min(auto_threshold, (self.config.human_confirm_threshold + adaptive_adj) * multiplier)
        review_threshold = min(confirm_threshold, (self.config.human_review_threshold + adaptive_adj) * multiplier)

        return {
            "auto_execute": auto_threshold,
            "human_confirm": confirm_threshold,
            "human_review": review_threshold,
            "absolute_minimum": self.config.absolute_minimum
        }

    def _determine_action_tier(
        self,
        confidence: float,
        thresholds: Dict[str, float],
        risk_level: RiskLevel
    ) -> tuple:
        """Determine action tier based on confidence and thresholds."""

        # Critical operations always require human for non-perfect confidence
        if risk_level == RiskLevel.CRITICAL and confidence < 0.99:
            return ActionTier.HUMAN_CONFIRM, "Critical operation requires human confirmation"

        # Check against thresholds
        if confidence >= thresholds['auto_execute']:
            return ActionTier.AUTO_EXECUTE, f"Confidence {confidence:.2f} >= auto-execute threshold"

        if confidence >= thresholds['human_confirm']:
            return ActionTier.HUMAN_CONFIRM, f"Confidence {confidence:.2f} requires confirmation"

        if confidence >= thresholds['human_review']:
            return ActionTier.HUMAN_REVIEW, f"Confidence {confidence:.2f} requires review"

        if confidence >= thresholds['absolute_minimum']:
            return ActionTier.REJECT, f"Confidence {confidence:.2f} below review threshold"

        return ActionTier.REJECT, f"Confidence {confidence:.2f} below absolute minimum"

    def _default_risk_classification(self, operation_type: Optional[str]) -> RiskLevel:
        """Default operation risk classification."""
        if not operation_type:
            return RiskLevel.MEDIUM

        op_lower = operation_type.lower()

        # Critical operations
        if any(k in op_lower for k in ['estop', 'emergency', 'safety', 'shutdown']):
            return RiskLevel.CRITICAL

        # High risk
        if any(k in op_lower for k in ['move', 'motion', 'heat', 'temperature', 'pressure']):
            return RiskLevel.HIGH

        # Medium risk
        if any(k in op_lower for k in ['process', 'parameter', 'config', 'setting']):
            return RiskLevel.MEDIUM

        # Low risk
        if any(k in op_lower for k in ['query', 'status', 'info', 'get']):
            return RiskLevel.LOW

        # Informational
        if any(k in op_lower for k in ['log', 'debug', 'trace']):
            return RiskLevel.INFORMATIONAL

        return RiskLevel.MEDIUM

    def _track_decision(self, result: ThresholdResult) -> None:
        """Track decision for adaptive learning."""
        self._decision_history.append({
            "timestamp": time.time(),
            "confidence": result.confidence,
            "action_tier": result.action_tier.value,
            "risk_level": result.risk_level.value
        })

        # Keep only recent history
        max_history = 1000
        if len(self._decision_history) > max_history:
            self._decision_history = self._decision_history[-max_history:]

    def record_outcome(
        self,
        decision_index: int,
        was_correct: bool,
        actual_outcome: Optional[str] = None
    ) -> None:
        """
        Record actual outcome for a decision (for adaptive learning).

        Args:
            decision_index: Index into decision history
            was_correct: Whether the decision was correct
            actual_outcome: Description of actual outcome
        """
        if not self.config.adaptive_enabled:
            return

        if 0 <= decision_index < len(self._decision_history):
            decision = self._decision_history[decision_index]
            decision["outcome_correct"] = was_correct
            decision["actual_outcome"] = actual_outcome

            # Compute calibration error
            expected_prob = decision["confidence"]
            actual_prob = 1.0 if was_correct else 0.0
            calibration_error = expected_prob - actual_prob
            self._calibration_errors.append(calibration_error)

            # Adjust thresholds adaptively
            risk_level = RiskLevel(decision["risk_level"])
            if was_correct and decision["action_tier"] == ActionTier.REJECT.value:
                # False rejection - lower threshold
                self._adaptive_adjustments[risk_level] -= self.config.adaptation_rate
            elif not was_correct and decision["action_tier"] == ActionTier.AUTO_EXECUTE.value:
                # False acceptance - raise threshold
                self._adaptive_adjustments[risk_level] += self.config.adaptation_rate

            # Bound adjustments
            self._adaptive_adjustments[risk_level] = max(
                -0.1, min(0.1, self._adaptive_adjustments[risk_level])
            )

    def get_calibration_metrics(self) -> Dict[str, float]:
        """Get calibration metrics for the threshold system."""
        if not self._calibration_errors:
            return {"calibration_error": 0.0, "sample_count": 0}

        import statistics
        return {
            "mean_calibration_error": statistics.mean(self._calibration_errors),
            "calibration_std": statistics.stdev(self._calibration_errors) if len(self._calibration_errors) > 1 else 0.0,
            "sample_count": len(self._calibration_errors),
            "adaptive_adjustments": dict(self._adaptive_adjustments)
        }

    def get_decision_summary(self) -> Dict[str, Any]:
        """Get summary of recent decisions."""
        if not self._decision_history:
            return {"total_decisions": 0}

        tier_counts = {}
        risk_counts = {}
        avg_confidence = 0.0

        for decision in self._decision_history:
            tier = decision["action_tier"]
            risk = decision["risk_level"]
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
            avg_confidence += decision["confidence"]

        avg_confidence /= len(self._decision_history)

        return {
            "total_decisions": len(self._decision_history),
            "action_tier_distribution": tier_counts,
            "risk_level_distribution": risk_counts,
            "average_confidence": avg_confidence
        }

    def evaluate_batch(
        self,
        confidences: List[float],
        risk_level: RiskLevel = RiskLevel.MEDIUM
    ) -> List[ThresholdResult]:
        """Evaluate multiple confidences."""
        return [
            self.evaluate(conf, risk_level=risk_level)
            for conf in confidences
        ]

    def get_threshold_for_risk(self, risk_level: RiskLevel) -> Dict[str, float]:
        """Get current thresholds for a risk level."""
        return self._get_adjusted_thresholds(risk_level)
