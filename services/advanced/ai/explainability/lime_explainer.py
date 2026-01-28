"""
LIME (Local Interpretable Model-agnostic Explanations) for Manufacturing.

This module implements LIME-based explainability for:
- Local explanation of individual predictions
- Tabular data explanations for process parameters
- Image explanations for defect detection
- Text explanations for maintenance logs

Research Contributions:
- Manufacturing-domain perturbation strategies
- Process-aware neighborhood sampling
- Integration with zero-defect quality systems

References:
- Ribeiro, M.T., et al. (2016). "Why Should I Trust You?": Explaining Predictions
- Ribeiro, M.T., et al. (2018). Anchors: High-Precision Model-Agnostic Explanations
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class KernelType(Enum):
    """Kernel functions for LIME weighting."""
    EXPONENTIAL = "exponential"
    GAUSSIAN = "gaussian"
    COSINE = "cosine"
    LINEAR = "linear"


class SamplingStrategy(Enum):
    """Perturbation sampling strategies."""
    UNIFORM = "uniform"  # Uniform random sampling
    GAUSSIAN = "gaussian"  # Gaussian perturbation
    PROCESS_AWARE = "process_aware"  # Respect process constraints
    ADAPTIVE = "adaptive"  # Adaptive based on feature importance


class ExplainerMode(Enum):
    """LIME explainer modes."""
    TABULAR = "tabular"  # For structured data
    IMAGE = "image"  # For image data
    TEXT = "text"  # For text data


@dataclass
class LIMEConfig:
    """Configuration for LIME explainer."""
    mode: ExplainerMode = ExplainerMode.TABULAR
    n_samples: int = 500  # Number of perturbation samples
    kernel: KernelType = KernelType.EXPONENTIAL
    kernel_width: float = 0.75  # Kernel width parameter
    sampling_strategy: SamplingStrategy = SamplingStrategy.GAUSSIAN
    feature_selection: str = "auto"  # 'auto', 'none', 'forward', 'lasso'
    n_features: int = 10  # Max features in explanation
    discretize_continuous: bool = True
    discretizer: str = "quartile"  # 'quartile', 'decile', 'entropy'
    random_state: Optional[int] = None
    # Manufacturing-specific
    process_constraints: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    feature_bounds: Dict[str, Tuple[float, float]] = field(default_factory=dict)


@dataclass
class LocalExplanation:
    """Local explanation for a single prediction."""
    sample_id: str
    prediction: float
    prediction_proba: Optional[Dict[str, float]]  # For classifiers
    intercept: float  # Local model intercept
    feature_weights: Dict[str, float]  # Feature -> weight
    feature_values: Dict[str, float]  # Actual feature values
    feature_contributions: Dict[str, float]  # weight * value
    local_model_score: float  # R² of local linear model
    neighborhood_size: int
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def top_positive_features(self) -> List[Tuple[str, float]]:
        """Get features with positive contribution."""
        return sorted(
            [(k, v) for k, v in self.feature_weights.items() if v > 0],
            key=lambda x: x[1],
            reverse=True
        )

    @property
    def top_negative_features(self) -> List[Tuple[str, float]]:
        """Get features with negative contribution."""
        return sorted(
            [(k, v) for k, v in self.feature_weights.items() if v < 0],
            key=lambda x: x[1]
        )

    def to_dict(self) -> Dict:
        return {
            'sample_id': self.sample_id,
            'prediction': float(self.prediction),
            'prediction_proba': self.prediction_proba,
            'intercept': float(self.intercept),
            'feature_weights': {k: float(v) for k, v in self.feature_weights.items()},
            'feature_values': {k: float(v) for k, v in self.feature_values.items()},
            'feature_contributions': {k: float(v) for k, v in self.feature_contributions.items()},
            'local_model_score': float(self.local_model_score),
            'neighborhood_size': self.neighborhood_size,
            'timestamp': self.timestamp.isoformat()
        }


class LIMEVisualization:
    """Visualization utilities for LIME explanations."""

    @staticmethod
    def create_bar_chart_data(explanation: LocalExplanation, top_k: int = 10) -> Dict:
        """Create data for horizontal bar chart."""
        sorted_weights = sorted(
            explanation.feature_weights.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:top_k]

        return {
            'features': [
                {
                    'name': name,
                    'weight': weight,
                    'value': explanation.feature_values.get(name, 0),
                    'contribution': explanation.feature_contributions.get(name, 0),
                    'direction': 'positive' if weight > 0 else 'negative'
                }
                for name, weight in sorted_weights
            ],
            'intercept': explanation.intercept,
            'prediction': explanation.prediction,
            'local_model_score': explanation.local_model_score
        }

    @staticmethod
    def create_decision_boundary_data(
        explanations: List[LocalExplanation],
        feature_pair: Tuple[str, str]
    ) -> Dict:
        """Create data for 2D decision boundary visualization."""
        f1, f2 = feature_pair

        points = []
        for exp in explanations:
            if f1 in exp.feature_values and f2 in exp.feature_values:
                points.append({
                    'x': exp.feature_values[f1],
                    'y': exp.feature_values[f2],
                    'prediction': exp.prediction,
                    'f1_weight': exp.feature_weights.get(f1, 0),
                    'f2_weight': exp.feature_weights.get(f2, 0)
                })

        return {
            'feature_1': f1,
            'feature_2': f2,
            'points': points
        }


class LIMEExplainer:
    """
    LIME Explainer for manufacturing quality models.

    Provides local interpretable explanations by fitting
    interpretable models in the neighborhood of predictions.
    """

    def __init__(self, config: Optional[LIMEConfig] = None):
        self.config = config or LIMEConfig()
        self.model = None
        self.training_data = None
        self.feature_names: List[str] = []
        self.class_names: Optional[List[str]] = None
        self.is_classifier: bool = False
        self._discretizer = None
        self._scaler = None

        # Set random state
        if self.config.random_state is not None:
            np.random.seed(self.config.random_state)

    def fit(
        self,
        model: Any,
        training_data: np.ndarray,
        feature_names: List[str],
        class_names: Optional[List[str]] = None,
        is_classifier: bool = False
    ) -> 'LIMEExplainer':
        """
        Fit the LIME explainer.

        Args:
            model: Trained model with predict method
            training_data: Training data for statistics
            feature_names: Names of features
            class_names: Names of classes (for classification)
            is_classifier: Whether model is a classifier

        Returns:
            Self for method chaining
        """
        self.model = model
        self.training_data = training_data
        self.feature_names = feature_names
        self.class_names = class_names
        self.is_classifier = is_classifier

        # Compute feature statistics
        self._compute_feature_stats()

        # Initialize discretizer if needed
        if self.config.discretize_continuous:
            self._init_discretizer()

        logger.info(f"LIME explainer fitted with {len(training_data)} samples")
        return self

    def _compute_feature_stats(self):
        """Compute feature statistics for perturbation."""
        self._feature_means = np.mean(self.training_data, axis=0)
        self._feature_stds = np.std(self.training_data, axis=0) + 1e-6
        self._feature_mins = np.min(self.training_data, axis=0)
        self._feature_maxs = np.max(self.training_data, axis=0)

    def _init_discretizer(self):
        """Initialize discretizer for continuous features."""
        n_features = len(self.feature_names)

        if self.config.discretizer == "quartile":
            self._discretizer = {
                i: np.percentile(self.training_data[:, i], [25, 50, 75])
                for i in range(n_features)
            }
        elif self.config.discretizer == "decile":
            self._discretizer = {
                i: np.percentile(self.training_data[:, i], list(range(10, 100, 10)))
                for i in range(n_features)
            }

    def explain(
        self,
        X: np.ndarray,
        sample_ids: Optional[List[str]] = None,
        labels: Optional[List[int]] = None
    ) -> List[LocalExplanation]:
        """
        Generate LIME explanations for samples.

        Args:
            X: Samples to explain (n_samples, n_features)
            sample_ids: Optional sample identifiers
            labels: Class labels to explain (for classifiers)

        Returns:
            List of local explanations
        """
        if self.model is None:
            raise ValueError("Explainer not fitted. Call fit() first.")

        if X.ndim == 1:
            X = X.reshape(1, -1)

        n_samples = len(X)
        if sample_ids is None:
            sample_ids = [f"sample_{i}" for i in range(n_samples)]

        explanations = []

        for i in range(n_samples):
            instance = X[i]
            sample_id = sample_ids[i]
            label = labels[i] if labels is not None else None

            explanation = self._explain_instance(instance, sample_id, label)
            explanations.append(explanation)

        return explanations

    def _explain_instance(
        self,
        instance: np.ndarray,
        sample_id: str,
        label: Optional[int] = None
    ) -> LocalExplanation:
        """Generate explanation for a single instance."""
        # Get original prediction
        pred = self.model.predict(instance.reshape(1, -1))
        if pred.ndim > 1:
            pred = pred[0]
        prediction = float(pred[0] if hasattr(pred, '__len__') else pred)

        # Get prediction probabilities for classifiers
        prediction_proba = None
        if self.is_classifier and hasattr(self.model, 'predict_proba'):
            proba = self.model.predict_proba(instance.reshape(1, -1))[0]
            if self.class_names:
                prediction_proba = dict(zip(self.class_names, proba.tolist()))
            else:
                prediction_proba = {f"class_{i}": float(p) for i, p in enumerate(proba)}

        # Generate neighborhood samples
        neighborhood = self._generate_neighborhood(instance)

        # Get predictions for neighborhood
        neighborhood_predictions = self.model.predict(neighborhood)
        if neighborhood_predictions.ndim > 1:
            neighborhood_predictions = neighborhood_predictions[:, 0]

        # Compute distances and weights
        distances = self._compute_distances(instance, neighborhood)
        weights = self._compute_kernel_weights(distances)

        # Fit local linear model
        intercept, coefficients, score = self._fit_local_model(
            neighborhood, neighborhood_predictions, weights
        )

        # Create feature weights and contributions
        feature_weights = {}
        feature_values = {}
        feature_contributions = {}

        for j, fname in enumerate(self.feature_names):
            feature_weights[fname] = float(coefficients[j])
            feature_values[fname] = float(instance[j])
            feature_contributions[fname] = float(coefficients[j] * instance[j])

        return LocalExplanation(
            sample_id=sample_id,
            prediction=prediction,
            prediction_proba=prediction_proba,
            intercept=float(intercept),
            feature_weights=feature_weights,
            feature_values=feature_values,
            feature_contributions=feature_contributions,
            local_model_score=float(score),
            neighborhood_size=len(neighborhood)
        )

    def _generate_neighborhood(self, instance: np.ndarray) -> np.ndarray:
        """Generate perturbed samples around instance."""
        n_features = len(instance)
        neighborhood = np.zeros((self.config.n_samples, n_features))

        for i in range(self.config.n_samples):
            if self.config.sampling_strategy == SamplingStrategy.GAUSSIAN:
                # Gaussian perturbation
                perturbation = np.random.randn(n_features) * self._feature_stds * 0.5
                perturbed = instance + perturbation
            elif self.config.sampling_strategy == SamplingStrategy.UNIFORM:
                # Uniform perturbation
                perturbation = (np.random.rand(n_features) - 0.5) * self._feature_stds
                perturbed = instance + perturbation
            elif self.config.sampling_strategy == SamplingStrategy.PROCESS_AWARE:
                # Respect process constraints
                perturbed = self._process_aware_perturbation(instance)
            else:
                # Default to Gaussian
                perturbation = np.random.randn(n_features) * self._feature_stds * 0.5
                perturbed = instance + perturbation

            # Clip to feature bounds
            perturbed = np.clip(perturbed, self._feature_mins, self._feature_maxs)

            # Apply process constraints if defined
            for j, fname in enumerate(self.feature_names):
                if fname in self.config.process_constraints:
                    low, high = self.config.process_constraints[fname]
                    perturbed[j] = np.clip(perturbed[j], low, high)

            neighborhood[i] = perturbed

        return neighborhood

    def _process_aware_perturbation(self, instance: np.ndarray) -> np.ndarray:
        """Generate perturbation respecting manufacturing constraints."""
        perturbed = instance.copy()
        n_features = len(instance)

        for j in range(n_features):
            fname = self.feature_names[j]

            # Check if we have bounds
            if fname in self.config.feature_bounds:
                low, high = self.config.feature_bounds[fname]
            else:
                low, high = self._feature_mins[j], self._feature_maxs[j]

            # Perturb within bounds
            range_width = high - low
            perturbation = (np.random.rand() - 0.5) * range_width * 0.3
            perturbed[j] = np.clip(instance[j] + perturbation, low, high)

        return perturbed

    def _compute_distances(
        self,
        instance: np.ndarray,
        neighborhood: np.ndarray
    ) -> np.ndarray:
        """Compute distances from instance to neighborhood samples."""
        # Normalize by feature std
        normalized_instance = instance / self._feature_stds
        normalized_neighborhood = neighborhood / self._feature_stds

        # Euclidean distance
        distances = np.sqrt(np.sum((normalized_neighborhood - normalized_instance) ** 2, axis=1))

        return distances

    def _compute_kernel_weights(self, distances: np.ndarray) -> np.ndarray:
        """Compute kernel weights for neighborhood samples."""
        kernel_width = self.config.kernel_width

        if self.config.kernel == KernelType.EXPONENTIAL:
            weights = np.exp(-distances ** 2 / (2 * kernel_width ** 2))
        elif self.config.kernel == KernelType.GAUSSIAN:
            weights = np.exp(-distances ** 2 / (2 * kernel_width ** 2))
        elif self.config.kernel == KernelType.COSINE:
            weights = 1 - distances / (np.max(distances) + 1e-6)
        else:
            weights = np.ones_like(distances)

        return weights

    def _fit_local_model(
        self,
        X: np.ndarray,
        y: np.ndarray,
        weights: np.ndarray
    ) -> Tuple[float, np.ndarray, float]:
        """Fit weighted linear regression as local model."""
        # Add intercept term
        n_samples, n_features = X.shape
        X_with_intercept = np.column_stack([np.ones(n_samples), X])

        # Weighted least squares
        W = np.diag(weights)
        try:
            XtWX = X_with_intercept.T @ W @ X_with_intercept
            XtWy = X_with_intercept.T @ W @ y

            # Add regularization for numerical stability
            reg = np.eye(XtWX.shape[0]) * 1e-6
            coefficients = np.linalg.solve(XtWX + reg, XtWy)

            intercept = coefficients[0]
            feature_coefficients = coefficients[1:]

            # Compute R² score
            predictions = X_with_intercept @ coefficients
            ss_res = np.sum(weights * (y - predictions) ** 2)
            ss_tot = np.sum(weights * (y - np.average(y, weights=weights)) ** 2)
            r2_score = 1 - ss_res / (ss_tot + 1e-6)

        except np.linalg.LinAlgError:
            # Fallback to simple average
            intercept = np.average(y, weights=weights)
            feature_coefficients = np.zeros(n_features)
            r2_score = 0.0

        return intercept, feature_coefficients, max(0.0, r2_score)

    def get_feature_importance_summary(
        self,
        explanations: List[LocalExplanation]
    ) -> Dict[str, Dict]:
        """Aggregate feature importance across explanations."""
        importance = {fname: {'weights': [], 'contributions': []} for fname in self.feature_names}

        for exp in explanations:
            for fname in self.feature_names:
                importance[fname]['weights'].append(exp.feature_weights.get(fname, 0))
                importance[fname]['contributions'].append(exp.feature_contributions.get(fname, 0))

        summary = {}
        for fname, data in importance.items():
            weights = np.array(data['weights'])
            contributions = np.array(data['contributions'])

            summary[fname] = {
                'mean_weight': float(np.mean(weights)),
                'std_weight': float(np.std(weights)),
                'mean_abs_weight': float(np.mean(np.abs(weights))),
                'mean_contribution': float(np.mean(contributions)),
                'std_contribution': float(np.std(contributions)),
                'consistency': float(np.mean(np.sign(weights) == np.sign(np.mean(weights))))
            }

        return summary


class ManufacturingLIME:
    """
    Manufacturing-specific LIME analysis.

    Provides domain-aware local explanations with:
    - Process constraint awareness
    - Quality target interpretation
    - Operator-friendly explanations
    """

    def __init__(self, config: Optional[LIMEConfig] = None):
        self.config = config or LIMEConfig()
        self.config.sampling_strategy = SamplingStrategy.PROCESS_AWARE
        self.explainer = LIMEExplainer(self.config)

        # Manufacturing context
        self.process_parameters: Dict[str, Dict] = {}
        self.quality_thresholds: Dict[str, float] = {}

    def set_process_context(
        self,
        process_parameters: Dict[str, Dict],
        quality_thresholds: Dict[str, float]
    ):
        """
        Set manufacturing process context.

        Args:
            process_parameters: Dict of parameter name to metadata
                e.g., {'temperature': {'min': 180, 'max': 220, 'unit': 'C'}}
            quality_thresholds: Dict of quality metric to threshold
        """
        self.process_parameters = process_parameters
        self.quality_thresholds = quality_thresholds

        # Update config with constraints
        for param, meta in process_parameters.items():
            if 'min' in meta and 'max' in meta:
                self.config.process_constraints[param] = (meta['min'], meta['max'])
                self.config.feature_bounds[param] = (meta['min'], meta['max'])

    def explain_with_context(
        self,
        X: np.ndarray,
        model: Any,
        training_data: np.ndarray,
        feature_names: List[str]
    ) -> Dict:
        """
        Generate contextual manufacturing explanations.

        Returns explanations with process-aware interpretations.
        """
        # Fit explainer
        self.explainer.fit(model, training_data, feature_names)

        # Get explanations
        explanations = self.explainer.explain(X)

        # Add manufacturing context
        contextualized = []
        for exp in explanations:
            context = self._add_manufacturing_context(exp)
            contextualized.append(context)

        # Generate operator summary
        operator_summary = self._generate_operator_summary(explanations)

        return {
            'explanations': contextualized,
            'operator_summary': operator_summary,
            'feature_importance': self.explainer.get_feature_importance_summary(explanations)
        }

    def _add_manufacturing_context(self, explanation: LocalExplanation) -> Dict:
        """Add manufacturing context to explanation."""
        base_dict = explanation.to_dict()

        # Add process interpretation
        process_insights = []
        for fname, weight in explanation.feature_weights.items():
            if fname in self.process_parameters:
                meta = self.process_parameters[fname]
                value = explanation.feature_values[fname]

                insight = {
                    'parameter': fname,
                    'current_value': value,
                    'unit': meta.get('unit', ''),
                    'operating_range': [meta.get('min', 0), meta.get('max', 100)],
                    'impact': 'positive' if weight > 0 else 'negative',
                    'impact_magnitude': abs(weight),
                    'recommendation': self._get_parameter_recommendation(fname, value, weight, meta)
                }
                process_insights.append(insight)

        base_dict['process_insights'] = process_insights
        base_dict['quality_status'] = self._assess_quality_status(explanation)

        return base_dict

    def _get_parameter_recommendation(
        self,
        param: str,
        value: float,
        weight: float,
        meta: Dict
    ) -> str:
        """Generate parameter recommendation."""
        min_val = meta.get('min', 0)
        max_val = meta.get('max', 100)
        range_size = max_val - min_val

        # Position in range
        position = (value - min_val) / range_size if range_size > 0 else 0.5

        if weight > 0:
            # Positive impact - higher is better
            if position < 0.3:
                return f"Consider increasing {param} - currently at lower end of range"
            elif position > 0.9:
                return f"{param} is near optimal at upper range"
            else:
                return f"{param} has positive impact, within acceptable range"
        else:
            # Negative impact - lower might be better
            if position > 0.7:
                return f"Consider reducing {param} - currently at higher end of range"
            elif position < 0.1:
                return f"{param} is near optimal at lower range"
            else:
                return f"{param} may need adjustment - monitor closely"

    def _assess_quality_status(self, explanation: LocalExplanation) -> Dict:
        """Assess quality status based on explanation."""
        prediction = explanation.prediction

        status = {
            'prediction': prediction,
            'overall_status': 'unknown',
            'threshold_checks': []
        }

        for metric, threshold in self.quality_thresholds.items():
            passed = prediction >= threshold if 'min' in metric.lower() else prediction <= threshold
            status['threshold_checks'].append({
                'metric': metric,
                'threshold': threshold,
                'passed': passed
            })

        # Overall status
        if all(check['passed'] for check in status['threshold_checks']):
            status['overall_status'] = 'pass'
        elif any(check['passed'] for check in status['threshold_checks']):
            status['overall_status'] = 'marginal'
        else:
            status['overall_status'] = 'fail'

        return status

    def _generate_operator_summary(self, explanations: List[LocalExplanation]) -> Dict:
        """Generate operator-friendly summary."""
        n_samples = len(explanations)
        avg_score = np.mean([e.local_model_score for e in explanations])

        # Find most important parameters
        importance = self.explainer.get_feature_importance_summary(explanations)
        sorted_params = sorted(
            importance.items(),
            key=lambda x: x[1]['mean_abs_weight'],
            reverse=True
        )

        top_factors = []
        for param, stats in sorted_params[:5]:
            if param in self.process_parameters:
                meta = self.process_parameters[param]
                top_factors.append({
                    'parameter': param,
                    'importance': stats['mean_abs_weight'],
                    'effect_direction': 'increases quality' if stats['mean_weight'] > 0 else 'decreases quality',
                    'unit': meta.get('unit', ''),
                    'consistency': stats['consistency']
                })

        return {
            'samples_analyzed': n_samples,
            'explanation_reliability': float(avg_score),
            'top_quality_factors': top_factors,
            'actionable_insights': self._generate_actionable_insights(sorted_params)
        }

    def _generate_actionable_insights(
        self,
        sorted_params: List[Tuple[str, Dict]]
    ) -> List[str]:
        """Generate actionable insights for operators."""
        insights = []

        for param, stats in sorted_params[:3]:
            if stats['consistency'] > 0.8:
                direction = "increasing" if stats['mean_weight'] > 0 else "decreasing"
                insights.append(
                    f"Consistently, {direction} {param} improves quality outcomes"
                )
            elif stats['consistency'] < 0.5:
                insights.append(
                    f"{param} has variable effects - may depend on other conditions"
                )

        if not insights:
            insights.append("No strong consistent patterns found - review process stability")

        return insights
