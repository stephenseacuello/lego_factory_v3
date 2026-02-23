"""
Explanation Generator - Natural language explanations.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ExplanationLevel(Enum):
    """Level of explanation detail."""
    BRIEF = "brief"
    STANDARD = "standard"
    DETAILED = "detailed"
    TECHNICAL = "technical"


@dataclass
class NaturalLanguageExplanation:
    """Natural language explanation."""
    summary: str
    details: List[str]
    recommendations: List[str]
    confidence: float
    level: ExplanationLevel


class ExplanationGenerator:
    """
    Generate natural language explanations for AI decisions.

    Features:
    - Multi-level explanations (brief to technical)
    - Domain-specific terminology
    - Actionable recommendations
    - Confidence scoring
    """

    def __init__(self, domain: str = "manufacturing"):
        """
        Initialize explanation generator.

        Args:
            domain: Domain for terminology ("manufacturing", "quality", etc.)
        """
        self.domain = domain
        self._templates = self._load_templates()

    def _load_templates(self) -> Dict[str, Dict]:
        """Load explanation templates."""
        return {
            "manufacturing": {
                "prediction_high": "The model predicts a {outcome} of {value:.2f}, which is above the typical threshold of {threshold:.2f}.",
                "prediction_low": "The model predicts a {outcome} of {value:.2f}, which is below the typical threshold of {threshold:.2f}.",
                "feature_positive": "{feature} (value: {value:.3f}) contributes positively, increasing the prediction by {impact:.4f}.",
                "feature_negative": "{feature} (value: {value:.3f}) contributes negatively, decreasing the prediction by {impact:.4f}.",
                "recommendation_adjust": "Consider adjusting {feature} to optimize the outcome.",
                "recommendation_monitor": "Monitor {feature} closely as it has significant impact on the result.",
                "confidence_high": "This prediction has high confidence ({confidence:.1%}).",
                "confidence_medium": "This prediction has moderate confidence ({confidence:.1%}).",
                "confidence_low": "This prediction has low confidence ({confidence:.1%}). Consider collecting more data.",
            },
            "quality": {
                "defect_likely": "The model indicates a {probability:.1%} probability of defect in this part.",
                "defect_unlikely": "The model indicates the part is likely acceptable with {probability:.1%} confidence.",
                "root_cause": "The primary contributing factor is {factor}, accounting for {contribution:.1%} of the prediction.",
                "action_required": "Immediate action recommended: {action}",
            }
        }

    def generate(self,
                prediction: float,
                feature_contributions: Dict[str, float],
                feature_values: Dict[str, float],
                level: ExplanationLevel = ExplanationLevel.STANDARD,
                context: Optional[Dict[str, Any]] = None) -> NaturalLanguageExplanation:
        """
        Generate natural language explanation.

        Args:
            prediction: Model prediction
            feature_contributions: SHAP/LIME feature contributions
            feature_values: Actual feature values
            level: Explanation detail level
            context: Additional context (thresholds, etc.)

        Returns:
            Natural language explanation
        """
        context = context or {}
        threshold = context.get('threshold', 0.5)
        outcome_name = context.get('outcome_name', 'outcome')

        templates = self._templates.get(self.domain, self._templates["manufacturing"])

        # Generate summary
        if prediction > threshold:
            summary = templates["prediction_high"].format(
                outcome=outcome_name,
                value=prediction,
                threshold=threshold
            )
        else:
            summary = templates["prediction_low"].format(
                outcome=outcome_name,
                value=prediction,
                threshold=threshold
            )

        # Generate feature details
        details = []
        sorted_features = sorted(
            feature_contributions.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )

        n_features = {
            ExplanationLevel.BRIEF: 3,
            ExplanationLevel.STANDARD: 5,
            ExplanationLevel.DETAILED: 10,
            ExplanationLevel.TECHNICAL: len(sorted_features)
        }[level]

        for feature, impact in sorted_features[:n_features]:
            value = feature_values.get(feature, 0)

            if impact > 0:
                detail = templates["feature_positive"].format(
                    feature=self._format_feature_name(feature),
                    value=value,
                    impact=abs(impact)
                )
            else:
                detail = templates["feature_negative"].format(
                    feature=self._format_feature_name(feature),
                    value=value,
                    impact=abs(impact)
                )
            details.append(detail)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            prediction, sorted_features, context
        )

        # Calculate confidence
        confidence = self._estimate_confidence(feature_contributions, context)

        return NaturalLanguageExplanation(
            summary=summary,
            details=details,
            recommendations=recommendations,
            confidence=confidence,
            level=level
        )

    def _format_feature_name(self, feature: str) -> str:
        """Format feature name for display."""
        # Convert snake_case to Title Case
        return feature.replace('_', ' ').title()

    def _generate_recommendations(self,
                                 prediction: float,
                                 sorted_features: List[tuple],
                                 context: Dict) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        threshold = context.get('threshold', 0.5)
        templates = self._templates.get(self.domain, self._templates["manufacturing"])

        # If prediction is concerning, recommend adjustments
        if prediction > threshold:
            # Recommend adjusting top negative contributors
            for feature, impact in sorted_features[:3]:
                if impact > 0:
                    recommendations.append(
                        templates["recommendation_adjust"].format(
                            feature=self._format_feature_name(feature)
                        )
                    )

        # Always recommend monitoring top features
        if sorted_features:
            top_feature = sorted_features[0][0]
            recommendations.append(
                templates["recommendation_monitor"].format(
                    feature=self._format_feature_name(top_feature)
                )
            )

        return recommendations

    def _estimate_confidence(self,
                            contributions: Dict[str, float],
                            context: Dict) -> float:
        """Estimate explanation confidence."""
        # Higher variance in contributions = lower confidence
        if not contributions:
            return 0.5

        values = list(contributions.values())
        total = sum(abs(v) for v in values)

        if total == 0:
            return 0.5

        # Concentration ratio - if few features dominate, higher confidence
        top_contribution = max(abs(v) for v in values)
        concentration = top_contribution / total

        # Model confidence from context
        model_confidence = context.get('model_confidence', 0.8)

        return (concentration * 0.5 + model_confidence * 0.5)

    def generate_quality_explanation(self,
                                    defect_probability: float,
                                    root_causes: List[Dict],
                                    level: ExplanationLevel = ExplanationLevel.STANDARD) -> NaturalLanguageExplanation:
        """
        Generate quality-specific explanation.

        Args:
            defect_probability: Probability of defect
            root_causes: List of root cause factors
            level: Explanation detail level

        Returns:
            Quality-focused explanation
        """
        templates = self._templates.get("quality", self._templates["manufacturing"])

        # Summary
        if defect_probability > 0.5:
            summary = templates["defect_likely"].format(probability=defect_probability)
        else:
            summary = templates["defect_unlikely"].format(probability=1 - defect_probability)

        # Details from root causes
        details = []
        for rc in root_causes[:5]:
            details.append(templates["root_cause"].format(
                factor=rc.get('name', 'Unknown'),
                contribution=rc.get('contribution', 0)
            ))

        # Recommendations
        recommendations = []
        if defect_probability > 0.7:
            recommendations.append(templates["action_required"].format(
                action="Inspect part immediately"
            ))
        elif defect_probability > 0.5:
            recommendations.append("Consider additional quality checks")

        return NaturalLanguageExplanation(
            summary=summary,
            details=details,
            recommendations=recommendations,
            confidence=0.8,
            level=level
        )

    def format_explanation(self, explanation: NaturalLanguageExplanation) -> str:
        """Format explanation as readable text."""
        lines = [explanation.summary, ""]

        if explanation.details:
            lines.append("Key factors:")
            for detail in explanation.details:
                lines.append(f"  • {detail}")
            lines.append("")

        if explanation.recommendations:
            lines.append("Recommendations:")
            for rec in explanation.recommendations:
                lines.append(f"  → {rec}")
            lines.append("")

        lines.append(f"Confidence: {explanation.confidence:.1%}")

        return "\n".join(lines)
