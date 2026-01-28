"""
SHAP Explainer - SHapley Additive exPlanations.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class SHAPExplanation:
    """SHAP explanation result."""
    feature_names: List[str]
    shap_values: np.ndarray
    base_value: float
    expected_value: float
    data: np.ndarray
    prediction: float


class SHAPExplainer:
    """
    SHAP-based model explanations.

    Features:
    - TreeExplainer for tree-based models
    - KernelExplainer for any model
    - Feature importance ranking
    - Interaction effects
    """

    def __init__(self, model: Any = None, model_type: str = "auto"):
        """
        Initialize SHAP explainer.

        Args:
            model: ML model to explain
            model_type: "tree", "linear", "kernel", or "auto"
        """
        self.model = model
        self.model_type = model_type
        self._explainer = None
        self._background_data = None

    def set_model(self, model: Any, model_type: str = "auto") -> None:
        """Set model to explain."""
        self.model = model
        self.model_type = model_type
        self._explainer = None

    def set_background_data(self, data: np.ndarray) -> None:
        """Set background data for KernelExplainer."""
        self._background_data = data

    def _create_explainer(self) -> Any:
        """Create appropriate SHAP explainer."""
        try:
            import shap

            if self.model_type == "tree":
                return shap.TreeExplainer(self.model)
            elif self.model_type == "linear":
                return shap.LinearExplainer(self.model, self._background_data)
            elif self.model_type == "kernel":
                return shap.KernelExplainer(
                    self.model.predict if hasattr(self.model, 'predict') else self.model,
                    self._background_data
                )
            elif self.model_type == "auto":
                # Auto-detect model type
                model_name = type(self.model).__name__.lower()
                if any(t in model_name for t in ['tree', 'forest', 'xgb', 'lgb', 'catboost']):
                    return shap.TreeExplainer(self.model)
                elif 'linear' in model_name or 'logistic' in model_name:
                    return shap.LinearExplainer(self.model, self._background_data)
                else:
                    return shap.KernelExplainer(
                        self.model.predict if hasattr(self.model, 'predict') else self.model,
                        self._background_data
                    )
        except ImportError:
            logger.warning("SHAP not installed, using fallback")
            return None

    def explain(self,
               X: np.ndarray,
               feature_names: Optional[List[str]] = None) -> SHAPExplanation:
        """
        Generate SHAP explanation for input.

        Args:
            X: Input data (single sample or batch)
            feature_names: Names of features

        Returns:
            SHAP explanation
        """
        if self.model is None:
            raise ValueError("Model not set")

        X = np.atleast_2d(X)

        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(X.shape[1])]

        # Try SHAP library
        try:
            import shap

            if self._explainer is None:
                self._explainer = self._create_explainer()

            shap_values = self._explainer.shap_values(X)

            # Handle multi-output
            if isinstance(shap_values, list):
                shap_values = shap_values[1]  # Binary classification - positive class

            expected_value = self._explainer.expected_value
            if isinstance(expected_value, (list, np.ndarray)):
                expected_value = expected_value[1] if len(expected_value) > 1 else expected_value[0]

            prediction = self.model.predict(X)[0] if hasattr(self.model, 'predict') else 0

            return SHAPExplanation(
                feature_names=feature_names,
                shap_values=shap_values[0] if len(shap_values.shape) > 1 else shap_values,
                base_value=expected_value,
                expected_value=expected_value,
                data=X[0],
                prediction=prediction
            )

        except ImportError:
            # Fallback: compute approximate feature importance
            return self._fallback_explain(X, feature_names)

    def _fallback_explain(self,
                         X: np.ndarray,
                         feature_names: List[str]) -> SHAPExplanation:
        """Fallback explanation when SHAP not available."""
        # Permutation-based importance approximation
        n_features = X.shape[1]
        base_pred = self.model.predict(X)[0] if hasattr(self.model, 'predict') else 0

        importance = np.zeros(n_features)

        for i in range(n_features):
            X_permuted = X.copy()
            # Shuffle this feature
            X_permuted[:, i] = np.random.permutation(X_permuted[:, i])
            new_pred = self.model.predict(X_permuted)[0] if hasattr(self.model, 'predict') else 0
            importance[i] = abs(base_pred - new_pred)

        return SHAPExplanation(
            feature_names=feature_names,
            shap_values=importance,
            base_value=float(base_pred),
            expected_value=float(base_pred),
            data=X[0],
            prediction=float(base_pred)
        )

    def get_feature_importance(self,
                              X: np.ndarray,
                              feature_names: Optional[List[str]] = None) -> Dict[str, float]:
        """
        Get global feature importance.

        Args:
            X: Dataset to compute importance over
            feature_names: Feature names

        Returns:
            Feature importance dictionary
        """
        X = np.atleast_2d(X)

        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(X.shape[1])]

        try:
            import shap

            if self._explainer is None:
                self._explainer = self._create_explainer()

            shap_values = self._explainer.shap_values(X)

            if isinstance(shap_values, list):
                shap_values = shap_values[1]

            # Mean absolute SHAP value per feature
            importance = np.mean(np.abs(shap_values), axis=0)

            return dict(zip(feature_names, importance.tolist()))

        except ImportError:
            # Fallback
            explanation = self._fallback_explain(X, feature_names)
            return dict(zip(feature_names, explanation.shap_values.tolist()))

    def explain_interaction(self,
                           X: np.ndarray,
                           feature_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Compute SHAP interaction values.

        Args:
            X: Input data
            feature_names: Feature names

        Returns:
            Interaction values
        """
        X = np.atleast_2d(X)

        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(X.shape[1])]

        try:
            import shap

            if self._explainer is None:
                self._explainer = self._create_explainer()

            if hasattr(self._explainer, 'shap_interaction_values'):
                interaction_values = self._explainer.shap_interaction_values(X)

                return {
                    'feature_names': feature_names,
                    'interaction_matrix': interaction_values[0] if len(X) == 1 else interaction_values
                }
            else:
                return {'error': 'Interaction values not supported for this model type'}

        except ImportError:
            return {'error': 'SHAP not installed'}

    def format_explanation(self, explanation: SHAPExplanation) -> str:
        """Format explanation as readable text."""
        lines = [f"Prediction: {explanation.prediction:.4f}"]
        lines.append(f"Base value: {explanation.base_value:.4f}")
        lines.append("\nFeature contributions:")

        # Sort by absolute impact
        indices = np.argsort(np.abs(explanation.shap_values))[::-1]

        for idx in indices:
            name = explanation.feature_names[idx]
            value = explanation.data[idx]
            shap = explanation.shap_values[idx]
            direction = "↑" if shap > 0 else "↓"
            lines.append(f"  {name} = {value:.3f} → {direction} {abs(shap):.4f}")

        return "\n".join(lines)
