"""
Explainable AI (XAI) for Manufacturing Decisions

Provides human-interpretable explanations for AI predictions
in manufacturing contexts. Critical for operator trust and
regulatory compliance.

Methods:
- SHAP (SHapley Additive exPlanations)
- LIME (Local Interpretable Model-agnostic Explanations)
- Feature Attribution
- Counterfactual Explanations
- Concept-based Explanations

Reference: ISO/IEC TR 24028 - AI Trustworthiness

Author: LEGO MCP AI Safety Engineering
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone
from enum import Enum, auto
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ExplanationType(Enum):
    """Types of explanations."""
    FEATURE_IMPORTANCE = "feature_importance"
    COUNTERFACTUAL = "counterfactual"
    EXAMPLE_BASED = "example_based"
    RULE_BASED = "rule_based"
    CONCEPT_BASED = "concept_based"


class AudienceLevel(Enum):
    """Target audience for explanations."""
    OPERATOR = "operator"           # Shop floor operator
    ENGINEER = "engineer"           # Process engineer
    MANAGER = "manager"             # Production manager
    AUDITOR = "auditor"             # Quality/compliance auditor
    DEVELOPER = "developer"         # ML developer


@dataclass
class FeatureContribution:
    """Individual feature contribution to prediction."""
    feature_name: str
    feature_value: Any
    contribution: float
    baseline_value: Any = None
    importance_rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature_name,
            "value": self.feature_value,
            "contribution": self.contribution,
            "baseline": self.baseline_value,
            "rank": self.importance_rank,
        }


@dataclass
class Counterfactual:
    """Counterfactual explanation."""
    original_prediction: float
    counterfactual_prediction: float
    changes: Dict[str, Tuple[Any, Any]]  # feature: (original, counterfactual)
    distance: float
    validity: bool

    def to_natural_language(self) -> str:
        """Generate natural language explanation."""
        changes_text = []
        for feature, (orig, cf) in self.changes.items():
            changes_text.append(f"{feature} from {orig} to {cf}")

        return (
            f"If {' and '.join(changes_text)}, "
            f"the prediction would change from {self.original_prediction:.2f} "
            f"to {self.counterfactual_prediction:.2f}"
        )


@dataclass
class Explanation:
    """Complete explanation for a prediction."""
    prediction: float
    explanation_type: ExplanationType
    feature_contributions: List[FeatureContribution] = field(default_factory=list)
    counterfactuals: List[Counterfactual] = field(default_factory=list)
    rules: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def top_features(self) -> List[FeatureContribution]:
        """Get top 5 most important features."""
        sorted_features = sorted(
            self.feature_contributions,
            key=lambda x: abs(x.contribution),
            reverse=True,
        )
        return sorted_features[:5]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction": self.prediction,
            "type": self.explanation_type.value,
            "top_features": [f.to_dict() for f in self.top_features],
            "n_counterfactuals": len(self.counterfactuals),
            "rules": self.rules,
            "concepts": self.concepts,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }

    def summarize(self, audience: AudienceLevel = AudienceLevel.OPERATOR) -> str:
        """Generate audience-appropriate summary."""
        if audience == AudienceLevel.OPERATOR:
            return self._operator_summary()
        elif audience == AudienceLevel.ENGINEER:
            return self._engineer_summary()
        elif audience == AudienceLevel.AUDITOR:
            return self._auditor_summary()
        return self._developer_summary()

    def _operator_summary(self) -> str:
        """Simple summary for operators."""
        top = self.top_features[:3]
        if not top:
            return f"Prediction: {self.prediction:.2f}"

        factors = [f"{f.feature_name}" for f in top]
        return f"Prediction: {self.prediction:.2f}. Main factors: {', '.join(factors)}"

    def _engineer_summary(self) -> str:
        """Technical summary for engineers."""
        lines = [f"Prediction: {self.prediction:.4f}"]
        lines.append("Feature contributions:")
        for f in self.top_features:
            lines.append(f"  {f.feature_name}: {f.contribution:+.4f} (value={f.feature_value})")
        return "\n".join(lines)

    def _auditor_summary(self) -> str:
        """Compliance-focused summary."""
        lines = [
            f"Prediction: {self.prediction:.4f}",
            f"Explanation type: {self.explanation_type.value}",
            f"Confidence: {self.confidence:.2%}",
            f"Features analyzed: {len(self.feature_contributions)}",
        ]
        if self.rules:
            lines.append(f"Decision rules: {len(self.rules)}")
        return "\n".join(lines)

    def _developer_summary(self) -> str:
        """Detailed summary for developers."""
        return str(self.to_dict())


class Explainer(ABC):
    """Abstract base for explanation methods."""

    @abstractmethod
    def explain(
        self,
        predict_fn: Callable,
        x: np.ndarray,
        feature_names: List[str],
    ) -> Explanation:
        """Generate explanation for prediction."""
        pass


class SHAPExplainer(Explainer):
    """
    SHAP-based explainer.

    Computes Shapley values to attribute prediction to features.
    Provides theoretically grounded, consistent explanations.

    Reference: Lundberg & Lee, "A Unified Approach to Interpreting
               Model Predictions" (2017)
    """

    def __init__(self, background_data: Optional[np.ndarray] = None):
        self.background_data = background_data
        self.n_samples = 100

    def _compute_shapley_values(
        self,
        predict_fn: Callable,
        x: np.ndarray,
        feature_idx: int,
    ) -> float:
        """
        Compute approximate Shapley value for feature.

        Uses Monte Carlo sampling for efficiency.
        """
        n_features = x.shape[1] if len(x.shape) > 1 else len(x)
        x_flat = x.flatten()

        # Generate baseline (mean of background or zeros)
        if self.background_data is not None:
            baseline = np.mean(self.background_data, axis=0)
        else:
            baseline = np.zeros(n_features)

        shapley_value = 0.0

        for _ in range(self.n_samples):
            # Random permutation
            perm = np.random.permutation(n_features)
            feature_pos = np.where(perm == feature_idx)[0][0]

            # Create two instances: with and without feature
            x_with = baseline.copy()
            x_without = baseline.copy()

            for i in range(feature_pos + 1):
                x_with[perm[i]] = x_flat[perm[i]]
            for i in range(feature_pos):
                x_without[perm[i]] = x_flat[perm[i]]

            # Marginal contribution
            pred_with = predict_fn(x_with.reshape(1, -1))[0]
            pred_without = predict_fn(x_without.reshape(1, -1))[0]

            shapley_value += (pred_with - pred_without)

        return float(shapley_value / self.n_samples)

    def explain(
        self,
        predict_fn: Callable,
        x: np.ndarray,
        feature_names: List[str],
    ) -> Explanation:
        """Generate SHAP explanation."""
        x = x.reshape(1, -1) if len(x.shape) == 1 else x
        prediction = float(predict_fn(x)[0])

        contributions = []
        for i, name in enumerate(feature_names):
            shap_value = self._compute_shapley_values(predict_fn, x, i)
            contributions.append(FeatureContribution(
                feature_name=name,
                feature_value=float(x[0, i]),
                contribution=shap_value,
            ))

        # Rank by absolute contribution
        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        for rank, c in enumerate(contributions):
            c.importance_rank = rank + 1

        return Explanation(
            prediction=prediction,
            explanation_type=ExplanationType.FEATURE_IMPORTANCE,
            feature_contributions=contributions,
            confidence=0.9,  # SHAP is generally reliable
        )


class LIMEExplainer(Explainer):
    """
    LIME-based explainer.

    Fits local linear model around prediction point
    to generate interpretable explanations.

    Reference: Ribeiro et al., "Why Should I Trust You?" (2016)
    """

    def __init__(self, n_samples: int = 1000, kernel_width: float = 0.25):
        self.n_samples = n_samples
        self.kernel_width = kernel_width

    def _sample_around(self, x: np.ndarray) -> np.ndarray:
        """Sample perturbations around x."""
        n_features = x.shape[1] if len(x.shape) > 1 else len(x)
        x_flat = x.flatten()

        # Generate samples from normal distribution centered at x
        samples = np.random.normal(
            loc=x_flat,
            scale=self.kernel_width * np.abs(x_flat + 1),
            size=(self.n_samples, n_features),
        )

        return samples

    def _compute_weights(self, x: np.ndarray, samples: np.ndarray) -> np.ndarray:
        """Compute kernel weights for samples."""
        x_flat = x.flatten()
        distances = np.sqrt(np.sum((samples - x_flat) ** 2, axis=1))
        weights = np.exp(-(distances ** 2) / (self.kernel_width ** 2))
        return weights

    def explain(
        self,
        predict_fn: Callable,
        x: np.ndarray,
        feature_names: List[str],
    ) -> Explanation:
        """Generate LIME explanation."""
        x = x.reshape(1, -1) if len(x.shape) == 1 else x
        prediction = float(predict_fn(x)[0])

        # Sample and get predictions
        samples = self._sample_around(x)
        sample_preds = predict_fn(samples).flatten()
        weights = self._compute_weights(x, samples)

        # Weighted linear regression
        n_features = samples.shape[1]

        # Add bias term
        X = np.column_stack([np.ones(self.n_samples), samples])
        W = np.diag(weights)

        try:
            # Weighted least squares: (X'WX)^-1 X'Wy
            XtWX = X.T @ W @ X
            XtWy = X.T @ W @ sample_preds
            coefficients = np.linalg.solve(XtWX, XtWy)
        except np.linalg.LinAlgError:
            coefficients = np.zeros(n_features + 1)

        # Extract feature contributions (exclude bias)
        contributions = []
        for i, name in enumerate(feature_names):
            contributions.append(FeatureContribution(
                feature_name=name,
                feature_value=float(x[0, i]),
                contribution=float(coefficients[i + 1] * x[0, i]),
            ))

        # Rank by absolute contribution
        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        for rank, c in enumerate(contributions):
            c.importance_rank = rank + 1

        return Explanation(
            prediction=prediction,
            explanation_type=ExplanationType.FEATURE_IMPORTANCE,
            feature_contributions=contributions,
            confidence=0.85,  # LIME is local approximation
        )


class CounterfactualExplainer(Explainer):
    """
    Counterfactual explanation generator.

    Finds minimal changes to input that change the prediction
    to a desired outcome.

    Reference: Wachter et al., "Counterfactual Explanations without
               Opening the Black Box" (2017)
    """

    def __init__(
        self,
        target_class: Optional[int] = None,
        max_iterations: int = 100,
        step_size: float = 0.1,
    ):
        self.target_class = target_class
        self.max_iterations = max_iterations
        self.step_size = step_size

    def explain(
        self,
        predict_fn: Callable,
        x: np.ndarray,
        feature_names: List[str],
    ) -> Explanation:
        """Generate counterfactual explanation."""
        x = x.reshape(1, -1) if len(x.shape) == 1 else x
        original_pred = float(predict_fn(x)[0])

        # Simple gradient-free search for counterfactual
        x_cf = x.copy()
        best_cf = None
        best_distance = float('inf')

        for _ in range(self.max_iterations):
            # Random perturbation
            direction = np.random.randn(*x.shape)
            x_new = x_cf + self.step_size * direction

            new_pred = float(predict_fn(x_new)[0])

            # Check if prediction changed significantly
            if abs(new_pred - original_pred) > 0.1:
                distance = float(np.sum((x_new - x) ** 2))
                if distance < best_distance:
                    best_distance = distance
                    best_cf = (x_new.copy(), new_pred)

            # Move towards change
            if new_pred != original_pred:
                x_cf = x_new

        counterfactuals = []
        if best_cf is not None:
            x_cf, cf_pred = best_cf
            changes = {}
            for i, name in enumerate(feature_names):
                if abs(x_cf[0, i] - x[0, i]) > 0.01:
                    changes[name] = (float(x[0, i]), float(x_cf[0, i]))

            counterfactuals.append(Counterfactual(
                original_prediction=original_pred,
                counterfactual_prediction=cf_pred,
                changes=changes,
                distance=best_distance,
                validity=True,
            ))

        return Explanation(
            prediction=original_pred,
            explanation_type=ExplanationType.COUNTERFACTUAL,
            counterfactuals=counterfactuals,
            confidence=0.7 if counterfactuals else 0.0,
        )


class RuleExtractor:
    """
    Extract interpretable rules from model behavior.

    Useful for compliance documentation and operator training.
    """

    def __init__(self, threshold_precision: float = 0.9):
        self.threshold_precision = threshold_precision

    def extract_rules(
        self,
        predict_fn: Callable,
        x_train: np.ndarray,
        feature_names: List[str],
        n_rules: int = 5,
    ) -> List[str]:
        """Extract simple decision rules."""
        rules = []

        # Get predictions for training data
        y_pred = predict_fn(x_train)
        threshold = np.median(y_pred)

        high_class = y_pred > threshold

        # Find single-feature rules
        for i, name in enumerate(feature_names):
            feature_values = x_train[:, i]
            feature_median = np.median(feature_values)

            # Check precision of simple rule
            rule_pred = feature_values > feature_median
            precision = np.mean(high_class[rule_pred]) if np.sum(rule_pred) > 0 else 0

            if precision > self.threshold_precision:
                rules.append(
                    f"IF {name} > {feature_median:.2f} THEN prediction is HIGH"
                )

            # Check inverse rule
            precision_inv = np.mean(~high_class[~rule_pred]) if np.sum(~rule_pred) > 0 else 0
            if precision_inv > self.threshold_precision:
                rules.append(
                    f"IF {name} <= {feature_median:.2f} THEN prediction is LOW"
                )

            if len(rules) >= n_rules:
                break

        return rules


class ManufacturingExplainer:
    """
    XAI interface for manufacturing AI systems.

    Provides domain-specific explanations optimized for
    manufacturing contexts and audiences.

    Usage:
        explainer = ManufacturingExplainer()

        # Get explanation
        explanation = explainer.explain(
            model.predict,
            sensor_data,
            feature_names=["temperature", "pressure", "cycle_time"],
        )

        # Get operator-friendly summary
        summary = explanation.summarize(AudienceLevel.OPERATOR)
        print(summary)

        # Get counterfactual
        cf_explanation = explainer.explain_counterfactual(
            model.predict,
            sensor_data,
            feature_names,
        )
    """

    def __init__(self):
        self.shap_explainer = SHAPExplainer()
        self.lime_explainer = LIMEExplainer()
        self.cf_explainer = CounterfactualExplainer()
        self.rule_extractor = RuleExtractor()

        logger.info("ManufacturingExplainer initialized")

    def explain(
        self,
        predict_fn: Callable,
        x: np.ndarray,
        feature_names: List[str],
        method: str = "shap",
    ) -> Explanation:
        """
        Generate explanation for prediction.

        Args:
            predict_fn: Model prediction function
            x: Input data
            feature_names: Feature names
            method: "shap", "lime", or "combined"

        Returns:
            Explanation object
        """
        if method == "shap":
            return self.shap_explainer.explain(predict_fn, x, feature_names)
        elif method == "lime":
            return self.lime_explainer.explain(predict_fn, x, feature_names)
        elif method == "combined":
            shap_exp = self.shap_explainer.explain(predict_fn, x, feature_names)
            lime_exp = self.lime_explainer.explain(predict_fn, x, feature_names)

            # Combine contributions (average)
            combined_contributions = []
            shap_dict = {c.feature_name: c for c in shap_exp.feature_contributions}
            lime_dict = {c.feature_name: c for c in lime_exp.feature_contributions}

            for name in feature_names:
                shap_c = shap_dict.get(name)
                lime_c = lime_dict.get(name)

                if shap_c and lime_c:
                    combined_contributions.append(FeatureContribution(
                        feature_name=name,
                        feature_value=shap_c.feature_value,
                        contribution=(shap_c.contribution + lime_c.contribution) / 2,
                    ))

            combined_contributions.sort(key=lambda c: abs(c.contribution), reverse=True)

            return Explanation(
                prediction=shap_exp.prediction,
                explanation_type=ExplanationType.FEATURE_IMPORTANCE,
                feature_contributions=combined_contributions,
                confidence=(shap_exp.confidence + lime_exp.confidence) / 2,
            )
        else:
            raise ValueError(f"Unknown method: {method}")

    def explain_counterfactual(
        self,
        predict_fn: Callable,
        x: np.ndarray,
        feature_names: List[str],
    ) -> Explanation:
        """Generate counterfactual explanation."""
        return self.cf_explainer.explain(predict_fn, x, feature_names)

    def extract_rules(
        self,
        predict_fn: Callable,
        x_train: np.ndarray,
        feature_names: List[str],
        n_rules: int = 5,
    ) -> List[str]:
        """Extract interpretable rules from model."""
        return self.rule_extractor.extract_rules(
            predict_fn, x_train, feature_names, n_rules
        )

    def generate_report(
        self,
        predict_fn: Callable,
        x: np.ndarray,
        feature_names: List[str],
        audience: AudienceLevel = AudienceLevel.ENGINEER,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive explanation report.

        Returns dict suitable for documentation/audit.
        """
        shap_exp = self.explain(predict_fn, x, feature_names, method="shap")
        lime_exp = self.explain(predict_fn, x, feature_names, method="lime")
        cf_exp = self.explain_counterfactual(predict_fn, x, feature_names)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "audience": audience.value,
            "prediction": shap_exp.prediction,
            "shap_explanation": shap_exp.to_dict(),
            "lime_explanation": lime_exp.to_dict(),
            "counterfactual": cf_exp.to_dict() if cf_exp.counterfactuals else None,
            "summary": {
                "operator": shap_exp.summarize(AudienceLevel.OPERATOR),
                "engineer": shap_exp.summarize(AudienceLevel.ENGINEER),
                "auditor": shap_exp.summarize(AudienceLevel.AUDITOR),
            },
        }


# Manufacturing-specific feature sets

LEGO_MANUFACTURING_FEATURES = [
    "mold_temperature_c",
    "melt_temperature_c",
    "injection_pressure_bar",
    "cooling_time_s",
    "cycle_time_s",
    "material_batch_id",
    "cavity_number",
    "ambient_temperature_c",
    "humidity_percent",
]

QUALITY_INSPECTION_FEATURES = [
    "dimension_tolerance_mm",
    "surface_roughness_um",
    "color_delta_e",
    "weight_deviation_g",
    "stud_height_mm",
    "tube_diameter_mm",
    "clutch_force_n",
]


def create_manufacturing_explainer() -> ManufacturingExplainer:
    """Create XAI explainer for manufacturing."""
    return ManufacturingExplainer()


__all__ = [
    "ManufacturingExplainer",
    "Explanation",
    "ExplanationType",
    "AudienceLevel",
    "FeatureContribution",
    "Counterfactual",
    "SHAPExplainer",
    "LIMEExplainer",
    "CounterfactualExplainer",
    "RuleExtractor",
    "create_manufacturing_explainer",
    "LEGO_MANUFACTURING_FEATURES",
    "QUALITY_INSPECTION_FEATURES",
]
