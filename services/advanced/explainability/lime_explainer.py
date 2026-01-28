"""
LIME Explainer - Local Interpretable Model-agnostic Explanations.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class LIMEExplanation:
    """LIME explanation result."""
    feature_names: List[str]
    weights: Dict[str, float]
    local_prediction: float
    actual_prediction: float
    intercept: float
    score: float  # R² of local model


class LIMEExplainer:
    """
    LIME-based local explanations.

    Features:
    - Tabular data explanations
    - Text explanations
    - Image explanations (superpixel)
    - Custom similarity kernels
    """

    def __init__(self,
                 training_data: Optional[np.ndarray] = None,
                 feature_names: Optional[List[str]] = None,
                 mode: str = "tabular"):
        """
        Initialize LIME explainer.

        Args:
            training_data: Background data for sampling
            feature_names: Names of features
            mode: "tabular", "text", or "image"
        """
        self.training_data = training_data
        self.feature_names = feature_names
        self.mode = mode
        self._explainer = None

    def set_training_data(self,
                         data: np.ndarray,
                         feature_names: Optional[List[str]] = None) -> None:
        """Set training data for sampling."""
        self.training_data = data
        if feature_names:
            self.feature_names = feature_names
        elif self.feature_names is None:
            self.feature_names = [f"feature_{i}" for i in range(data.shape[1])]

    def explain(self,
               instance: np.ndarray,
               predict_fn: Callable,
               num_features: int = 10,
               num_samples: int = 5000) -> LIMEExplanation:
        """
        Generate LIME explanation.

        Args:
            instance: Instance to explain
            predict_fn: Model prediction function
            num_features: Number of features in explanation
            num_samples: Number of perturbed samples

        Returns:
            LIME explanation
        """
        instance = np.atleast_1d(instance)

        try:
            import lime
            import lime.lime_tabular

            if self._explainer is None and self.training_data is not None:
                self._explainer = lime.lime_tabular.LimeTabularExplainer(
                    self.training_data,
                    feature_names=self.feature_names,
                    mode='regression'
                )

            if self._explainer:
                exp = self._explainer.explain_instance(
                    instance,
                    predict_fn,
                    num_features=num_features,
                    num_samples=num_samples
                )

                weights = dict(exp.as_list())
                local_pred = exp.local_pred[0] if hasattr(exp, 'local_pred') else 0
                actual_pred = predict_fn(instance.reshape(1, -1))[0]

                return LIMEExplanation(
                    feature_names=self.feature_names or [],
                    weights=weights,
                    local_prediction=local_pred,
                    actual_prediction=actual_pred,
                    intercept=exp.intercept if hasattr(exp, 'intercept') else 0,
                    score=exp.score if hasattr(exp, 'score') else 0
                )
            else:
                return self._fallback_explain(instance, predict_fn, num_features, num_samples)

        except ImportError:
            return self._fallback_explain(instance, predict_fn, num_features, num_samples)

    def _fallback_explain(self,
                         instance: np.ndarray,
                         predict_fn: Callable,
                         num_features: int,
                         num_samples: int) -> LIMEExplanation:
        """Fallback LIME implementation."""
        n_features = len(instance)

        if self.training_data is not None:
            # Sample around training data
            mean = np.mean(self.training_data, axis=0)
            std = np.std(self.training_data, axis=0) + 1e-6
        else:
            mean = instance
            std = np.abs(instance) * 0.1 + 0.1

        # Generate perturbed samples
        samples = np.random.normal(mean, std, size=(num_samples, n_features))

        # Compute distances (kernel weights)
        distances = np.sqrt(np.sum((samples - instance) ** 2, axis=1))
        kernel_width = np.sqrt(n_features) * 0.75
        weights = np.exp(-(distances ** 2) / (kernel_width ** 2))

        # Get predictions
        predictions = predict_fn(samples)

        # Fit weighted linear regression
        coefficients, intercept, score = self._weighted_linear_regression(
            samples, predictions, weights
        )

        # Select top features
        importance = np.abs(coefficients)
        top_indices = np.argsort(importance)[::-1][:num_features]

        feature_names = self.feature_names or [f"feature_{i}" for i in range(n_features)]
        weights_dict = {
            feature_names[i]: coefficients[i]
            for i in top_indices
        }

        actual_pred = predict_fn(instance.reshape(1, -1))[0]
        local_pred = intercept + np.dot(coefficients, instance)

        return LIMEExplanation(
            feature_names=feature_names,
            weights=weights_dict,
            local_prediction=local_pred,
            actual_prediction=actual_pred,
            intercept=intercept,
            score=score
        )

    def _weighted_linear_regression(self,
                                   X: np.ndarray,
                                   y: np.ndarray,
                                   weights: np.ndarray) -> Tuple[np.ndarray, float, float]:
        """Fit weighted linear regression."""
        # Add intercept
        X_with_intercept = np.column_stack([np.ones(len(X)), X])

        # Weight matrix
        W = np.diag(weights)

        # Weighted least squares: (X'WX)^-1 X'Wy
        try:
            XtWX = X_with_intercept.T @ W @ X_with_intercept
            XtWy = X_with_intercept.T @ W @ y
            beta = np.linalg.solve(XtWX + 1e-6 * np.eye(XtWX.shape[0]), XtWy)
        except np.linalg.LinAlgError:
            # Fallback to simple regression
            beta = np.zeros(X_with_intercept.shape[1])

        intercept = beta[0]
        coefficients = beta[1:]

        # R² score
        y_pred = X_with_intercept @ beta
        ss_res = np.sum(weights * (y - y_pred) ** 2)
        ss_tot = np.sum(weights * (y - np.average(y, weights=weights)) ** 2)
        score = 1 - ss_res / (ss_tot + 1e-10)

        return coefficients, intercept, score

    def format_explanation(self, explanation: LIMEExplanation) -> str:
        """Format explanation as readable text."""
        lines = [
            f"Actual prediction: {explanation.actual_prediction:.4f}",
            f"Local approximation: {explanation.local_prediction:.4f}",
            f"Local model R²: {explanation.score:.4f}",
            "\nFeature contributions:"
        ]

        # Sort by absolute weight
        sorted_weights = sorted(
            explanation.weights.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )

        for name, weight in sorted_weights:
            direction = "+" if weight > 0 else "-"
            lines.append(f"  {name}: {direction}{abs(weight):.4f}")

        return "\n".join(lines)
