"""
Counterfactual Explanations for Manufacturing Quality.

This module implements counterfactual and "what-if" analysis:
- Counterfactual generation for quality predictions
- What-if analysis for process optimization
- Causal reasoning for root cause analysis
- Contrastive explanations

Research Contributions:
- Manufacturing-constrained counterfactual generation
- Process-aware feasibility constraints
- Actionable counterfactual recommendations

References:
- Wachter, S., et al. (2017). Counterfactual Explanations without Opening the Black Box
- Mothilal, R.K., et al. (2020). Explaining Machine Learning Classifiers through Diverse Counterfactuals
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging
from datetime import datetime
import heapq

logger = logging.getLogger(__name__)


class CounterfactualMethod(Enum):
    """Counterfactual generation methods."""
    GRADIENT = "gradient"  # Gradient-based optimization
    GENETIC = "genetic"  # Genetic algorithm
    DICE = "dice"  # Diverse Counterfactual Explanations
    GROWING_SPHERES = "growing_spheres"
    PROTOTYPE = "prototype"  # Prototype-based
    RANDOM_SEARCH = "random_search"


class ConstraintType(Enum):
    """Types of constraints on counterfactuals."""
    IMMUTABLE = "immutable"  # Cannot be changed
    INCREASING = "increasing"  # Can only increase
    DECREASING = "decreasing"  # Can only decrease
    BOUNDED = "bounded"  # Within specific bounds
    CATEGORICAL = "categorical"  # Discrete values only
    CAUSAL = "causal"  # Respects causal structure


@dataclass
class CounterfactualConfig:
    """Configuration for counterfactual generation."""
    method: CounterfactualMethod = CounterfactualMethod.DICE
    n_counterfactuals: int = 5  # Number of counterfactuals
    diversity_weight: float = 0.5  # Trade-off diversity vs proximity
    sparsity_weight: float = 0.3  # Prefer fewer feature changes
    proximity_weight: float = 0.5  # Prefer smaller changes
    plausibility_weight: float = 0.3  # Prefer likely feature values
    max_iterations: int = 100
    convergence_threshold: float = 1e-4
    feature_constraints: Dict[str, ConstraintType] = field(default_factory=dict)
    feature_ranges: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    categorical_features: List[str] = field(default_factory=list)
    actionable_features: List[str] = field(default_factory=list)


@dataclass
class Counterfactual:
    """A single counterfactual explanation."""
    original_values: Dict[str, float]
    counterfactual_values: Dict[str, float]
    changes: Dict[str, float]  # feature -> change magnitude
    original_prediction: float
    counterfactual_prediction: float
    validity: bool  # Achieves desired outcome
    proximity: float  # Distance from original
    sparsity: int  # Number of features changed
    plausibility: float  # How realistic the CF is
    diversity_contribution: float
    cost: float  # Total cost metric

    @property
    def changed_features(self) -> List[str]:
        """Get list of features that were changed."""
        return [f for f, c in self.changes.items() if abs(c) > 1e-6]

    @property
    def n_changes(self) -> int:
        """Number of feature changes."""
        return len(self.changed_features)

    def to_dict(self) -> Dict:
        return {
            'original_values': {k: float(v) for k, v in self.original_values.items()},
            'counterfactual_values': {k: float(v) for k, v in self.counterfactual_values.items()},
            'changes': {k: float(v) for k, v in self.changes.items()},
            'original_prediction': float(self.original_prediction),
            'counterfactual_prediction': float(self.counterfactual_prediction),
            'validity': self.validity,
            'proximity': float(self.proximity),
            'sparsity': self.sparsity,
            'plausibility': float(self.plausibility),
            'cost': float(self.cost),
            'changed_features': self.changed_features
        }


@dataclass
class WhatIfScenario:
    """A what-if analysis scenario."""
    scenario_id: str
    base_values: Dict[str, float]
    modified_values: Dict[str, float]
    base_prediction: float
    modified_prediction: float
    prediction_change: float
    sensitivity: Dict[str, float]  # Feature -> impact
    confidence_interval: Tuple[float, float]
    feasibility_score: float

    def to_dict(self) -> Dict:
        return {
            'scenario_id': self.scenario_id,
            'base_values': self.base_values,
            'modified_values': self.modified_values,
            'base_prediction': float(self.base_prediction),
            'modified_prediction': float(self.modified_prediction),
            'prediction_change': float(self.prediction_change),
            'sensitivity': {k: float(v) for k, v in self.sensitivity.items()},
            'confidence_interval': [float(self.confidence_interval[0]), float(self.confidence_interval[1])],
            'feasibility_score': float(self.feasibility_score)
        }


class CounterfactualExplainer:
    """
    Counterfactual Explainer for manufacturing quality.

    Generates counterfactual explanations showing minimal
    changes needed to achieve a different outcome.
    """

    def __init__(self, config: Optional[CounterfactualConfig] = None):
        self.config = config or CounterfactualConfig()
        self.model = None
        self.training_data = None
        self.feature_names: List[str] = []
        self._feature_stats: Dict[str, Dict] = {}

    def fit(
        self,
        model: Any,
        training_data: np.ndarray,
        feature_names: List[str],
        feature_constraints: Optional[Dict[str, ConstraintType]] = None
    ) -> 'CounterfactualExplainer':
        """
        Fit the counterfactual explainer.

        Args:
            model: Trained model
            training_data: Training data for statistics
            feature_names: Feature names
            feature_constraints: Optional constraints per feature

        Returns:
            Self for method chaining
        """
        self.model = model
        self.training_data = training_data
        self.feature_names = feature_names

        if feature_constraints:
            self.config.feature_constraints = feature_constraints

        # Compute feature statistics
        self._compute_feature_stats()

        # Set default ranges if not provided
        self._set_default_ranges()

        logger.info(f"Counterfactual explainer fitted with {len(training_data)} samples")
        return self

    def _compute_feature_stats(self):
        """Compute feature statistics."""
        for i, fname in enumerate(self.feature_names):
            values = self.training_data[:, i]
            self._feature_stats[fname] = {
                'mean': float(np.mean(values)),
                'std': float(np.std(values)),
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'median': float(np.median(values)),
                'q25': float(np.percentile(values, 25)),
                'q75': float(np.percentile(values, 75))
            }

    def _set_default_ranges(self):
        """Set default feature ranges from data."""
        for fname, stats in self._feature_stats.items():
            if fname not in self.config.feature_ranges:
                self.config.feature_ranges[fname] = (stats['min'], stats['max'])

    def generate(
        self,
        instance: np.ndarray,
        target_prediction: float,
        direction: str = "increase"  # "increase", "decrease", or "target"
    ) -> List[Counterfactual]:
        """
        Generate counterfactual explanations.

        Args:
            instance: Original instance to explain
            target_prediction: Target prediction value
            direction: "increase", "decrease", or "target" (exact value)

        Returns:
            List of counterfactual explanations
        """
        if self.model is None:
            raise ValueError("Explainer not fitted. Call fit() first.")

        # Get original prediction
        original_pred = float(self.model.predict(instance.reshape(1, -1))[0])

        # Determine target
        if direction == "increase":
            target = target_prediction
        elif direction == "decrease":
            target = -target_prediction
        else:
            target = target_prediction

        # Generate counterfactuals based on method
        if self.config.method == CounterfactualMethod.DICE:
            counterfactuals = self._generate_dice(instance, original_pred, target)
        elif self.config.method == CounterfactualMethod.GENETIC:
            counterfactuals = self._generate_genetic(instance, original_pred, target)
        elif self.config.method == CounterfactualMethod.RANDOM_SEARCH:
            counterfactuals = self._generate_random(instance, original_pred, target)
        else:
            counterfactuals = self._generate_random(instance, original_pred, target)

        # Sort by cost
        counterfactuals.sort(key=lambda x: x.cost)

        return counterfactuals[:self.config.n_counterfactuals]

    def _generate_dice(
        self,
        instance: np.ndarray,
        original_pred: float,
        target: float
    ) -> List[Counterfactual]:
        """Generate diverse counterfactuals (DiCE method)."""
        counterfactuals = []
        n_features = len(instance)

        for _ in range(self.config.n_counterfactuals * 3):
            # Generate candidate by perturbing features
            cf_values = instance.copy()

            # Randomly select features to modify
            n_modify = np.random.randint(1, min(5, n_features) + 1)
            modify_indices = np.random.choice(
                [i for i, f in enumerate(self.feature_names)
                 if self.config.feature_constraints.get(f) != ConstraintType.IMMUTABLE],
                size=min(n_modify, n_features),
                replace=False
            )

            for idx in modify_indices:
                fname = self.feature_names[idx]
                constraint = self.config.feature_constraints.get(fname)
                low, high = self.config.feature_ranges.get(fname, (0, 1))

                if constraint == ConstraintType.INCREASING:
                    cf_values[idx] = np.random.uniform(instance[idx], high)
                elif constraint == ConstraintType.DECREASING:
                    cf_values[idx] = np.random.uniform(low, instance[idx])
                else:
                    cf_values[idx] = np.random.uniform(low, high)

            # Get prediction
            cf_pred = float(self.model.predict(cf_values.reshape(1, -1))[0])

            # Check validity
            valid = (target > original_pred and cf_pred > target) or \
                    (target < original_pred and cf_pred < target) or \
                    abs(cf_pred - target) < abs(original_pred - target)

            # Compute metrics
            cf = self._create_counterfactual(instance, cf_values, original_pred, cf_pred, valid)
            counterfactuals.append(cf)

        # Apply diversity filtering
        diverse_cfs = self._diversity_filter(counterfactuals)

        return diverse_cfs

    def _generate_genetic(
        self,
        instance: np.ndarray,
        original_pred: float,
        target: float
    ) -> List[Counterfactual]:
        """Generate counterfactuals using genetic algorithm."""
        population_size = 50
        generations = self.config.max_iterations
        n_features = len(instance)

        # Initialize population
        population = []
        for _ in range(population_size):
            individual = instance.copy()
            n_mutate = np.random.randint(1, 4)
            for _ in range(n_mutate):
                idx = np.random.randint(n_features)
                fname = self.feature_names[idx]
                low, high = self.config.feature_ranges.get(fname, (0, 1))
                individual[idx] = np.random.uniform(low, high)
            population.append(individual)

        # Evolution
        for gen in range(generations):
            # Evaluate fitness
            fitness_scores = []
            for individual in population:
                pred = float(self.model.predict(individual.reshape(1, -1))[0])
                distance = np.sum((individual - instance) ** 2)
                target_diff = abs(pred - target)

                # Fitness: minimize distance while achieving target
                fitness = -target_diff - 0.1 * distance
                fitness_scores.append((fitness, individual, pred))

            # Select best
            fitness_scores.sort(key=lambda x: x[0], reverse=True)
            survivors = [x[1] for x in fitness_scores[:population_size // 2]]

            # Crossover and mutation
            new_population = survivors.copy()
            while len(new_population) < population_size:
                p1, p2 = np.random.choice(len(survivors), 2, replace=False)
                child = survivors[p1].copy()

                # Crossover
                crossover_point = np.random.randint(n_features)
                child[crossover_point:] = survivors[p2][crossover_point:]

                # Mutation
                if np.random.random() < 0.3:
                    idx = np.random.randint(n_features)
                    fname = self.feature_names[idx]
                    low, high = self.config.feature_ranges.get(fname, (0, 1))
                    child[idx] = np.random.uniform(low, high)

                new_population.append(child)

            population = new_population

        # Create counterfactuals from final population
        counterfactuals = []
        for individual in population[:self.config.n_counterfactuals * 2]:
            pred = float(self.model.predict(individual.reshape(1, -1))[0])
            valid = abs(pred - target) < abs(original_pred - target)
            cf = self._create_counterfactual(instance, individual, original_pred, pred, valid)
            counterfactuals.append(cf)

        return counterfactuals

    def _generate_random(
        self,
        instance: np.ndarray,
        original_pred: float,
        target: float
    ) -> List[Counterfactual]:
        """Generate counterfactuals using random search."""
        counterfactuals = []
        n_features = len(instance)

        for _ in range(self.config.max_iterations):
            cf_values = instance.copy()

            # Random perturbations
            n_modify = np.random.randint(1, min(5, n_features) + 1)
            for _ in range(n_modify):
                idx = np.random.randint(n_features)
                fname = self.feature_names[idx]

                if self.config.feature_constraints.get(fname) == ConstraintType.IMMUTABLE:
                    continue

                low, high = self.config.feature_ranges.get(fname, (0, 1))
                cf_values[idx] = np.random.uniform(low, high)

            pred = float(self.model.predict(cf_values.reshape(1, -1))[0])
            valid = abs(pred - target) < abs(original_pred - target)

            cf = self._create_counterfactual(instance, cf_values, original_pred, pred, valid)
            counterfactuals.append(cf)

        return counterfactuals

    def _create_counterfactual(
        self,
        original: np.ndarray,
        cf_values: np.ndarray,
        original_pred: float,
        cf_pred: float,
        valid: bool
    ) -> Counterfactual:
        """Create a Counterfactual object."""
        original_dict = {self.feature_names[i]: float(original[i]) for i in range(len(original))}
        cf_dict = {self.feature_names[i]: float(cf_values[i]) for i in range(len(cf_values))}
        changes = {self.feature_names[i]: float(cf_values[i] - original[i]) for i in range(len(original))}

        # Compute metrics
        proximity = float(np.sqrt(np.sum((cf_values - original) ** 2)))
        sparsity = sum(1 for c in changes.values() if abs(c) > 1e-6)
        plausibility = self._compute_plausibility(cf_values)

        # Total cost
        cost = (
            self.config.proximity_weight * proximity +
            self.config.sparsity_weight * sparsity +
            (1 - self.config.plausibility_weight) * (1 - plausibility)
        )

        return Counterfactual(
            original_values=original_dict,
            counterfactual_values=cf_dict,
            changes=changes,
            original_prediction=original_pred,
            counterfactual_prediction=cf_pred,
            validity=valid,
            proximity=proximity,
            sparsity=sparsity,
            plausibility=plausibility,
            diversity_contribution=0.0,  # Set later
            cost=cost
        )

    def _compute_plausibility(self, cf_values: np.ndarray) -> float:
        """Compute plausibility score based on training data."""
        # Simple: how close is CF to nearest training sample
        distances = np.sqrt(np.sum((self.training_data - cf_values) ** 2, axis=1))
        min_distance = np.min(distances)

        # Normalize by typical distance in data
        typical_distance = np.mean(np.std(self.training_data, axis=0))
        plausibility = np.exp(-min_distance / (typical_distance + 1e-6))

        return float(plausibility)

    def _diversity_filter(
        self,
        counterfactuals: List[Counterfactual]
    ) -> List[Counterfactual]:
        """Filter counterfactuals for diversity."""
        if not counterfactuals:
            return []

        # Sort by validity and cost
        valid_cfs = [cf for cf in counterfactuals if cf.validity]
        invalid_cfs = [cf for cf in counterfactuals if not cf.validity]

        # Prefer valid counterfactuals
        candidates = valid_cfs if valid_cfs else invalid_cfs
        candidates.sort(key=lambda x: x.cost)

        # Greedily select diverse set
        selected = [candidates[0]]

        for cf in candidates[1:]:
            # Check diversity from selected
            min_diversity = float('inf')
            for sel in selected:
                # Diversity based on which features were changed
                cf_changed = set(cf.changed_features)
                sel_changed = set(sel.changed_features)
                jaccard = len(cf_changed & sel_changed) / (len(cf_changed | sel_changed) + 1e-6)
                diversity = 1 - jaccard
                min_diversity = min(min_diversity, diversity)

            cf.diversity_contribution = min_diversity

            if min_diversity > 0.3 or len(selected) < 2:
                selected.append(cf)

            if len(selected) >= self.config.n_counterfactuals:
                break

        return selected


class WhatIfAnalysis:
    """
    What-If Analysis for process optimization.

    Enables exploration of hypothetical scenarios
    to understand process parameter impacts.
    """

    def __init__(self, model: Any, feature_names: List[str]):
        self.model = model
        self.feature_names = feature_names
        self._feature_idx = {name: i for i, name in enumerate(feature_names)}

    def analyze_scenario(
        self,
        base_instance: np.ndarray,
        modifications: Dict[str, float],
        scenario_id: str = "scenario_1"
    ) -> WhatIfScenario:
        """
        Analyze a what-if scenario.

        Args:
            base_instance: Original feature values
            modifications: Dict of feature -> new value
            scenario_id: Identifier for the scenario

        Returns:
            WhatIfScenario with analysis results
        """
        # Get base prediction
        base_pred = float(self.model.predict(base_instance.reshape(1, -1))[0])

        # Apply modifications
        modified_instance = base_instance.copy()
        for fname, new_value in modifications.items():
            if fname in self._feature_idx:
                modified_instance[self._feature_idx[fname]] = new_value

        # Get modified prediction
        modified_pred = float(self.model.predict(modified_instance.reshape(1, -1))[0])

        # Compute sensitivity for each modified feature
        sensitivity = {}
        for fname, new_value in modifications.items():
            if fname in self._feature_idx:
                idx = self._feature_idx[fname]
                original_value = base_instance[idx]
                change = new_value - original_value

                if abs(change) > 1e-6:
                    # Approximate sensitivity
                    partial_effect = (modified_pred - base_pred) / len(modifications)
                    sensitivity[fname] = partial_effect / change
                else:
                    sensitivity[fname] = 0.0

        # Estimate confidence interval (simplified)
        std_estimate = abs(modified_pred - base_pred) * 0.1 + 0.01
        ci = (modified_pred - 1.96 * std_estimate, modified_pred + 1.96 * std_estimate)

        # Feasibility score (simplified)
        feasibility = 1.0  # Would check constraints in real implementation

        return WhatIfScenario(
            scenario_id=scenario_id,
            base_values={self.feature_names[i]: float(base_instance[i]) for i in range(len(base_instance))},
            modified_values={self.feature_names[i]: float(modified_instance[i]) for i in range(len(modified_instance))},
            base_prediction=base_pred,
            modified_prediction=modified_pred,
            prediction_change=modified_pred - base_pred,
            sensitivity=sensitivity,
            confidence_interval=ci,
            feasibility_score=feasibility
        )

    def sensitivity_analysis(
        self,
        base_instance: np.ndarray,
        feature_name: str,
        value_range: Tuple[float, float],
        n_points: int = 20
    ) -> Dict:
        """
        Perform sensitivity analysis for a single feature.

        Args:
            base_instance: Original values
            feature_name: Feature to analyze
            value_range: Range of values to test
            n_points: Number of points to evaluate

        Returns:
            Dict with sensitivity curve data
        """
        if feature_name not in self._feature_idx:
            raise ValueError(f"Unknown feature: {feature_name}")

        idx = self._feature_idx[feature_name]
        values = np.linspace(value_range[0], value_range[1], n_points)
        predictions = []

        for val in values:
            test_instance = base_instance.copy()
            test_instance[idx] = val
            pred = float(self.model.predict(test_instance.reshape(1, -1))[0])
            predictions.append(pred)

        predictions = np.array(predictions)

        # Compute sensitivity metrics
        gradients = np.gradient(predictions, values)

        return {
            'feature': feature_name,
            'values': values.tolist(),
            'predictions': predictions.tolist(),
            'gradients': gradients.tolist(),
            'mean_gradient': float(np.mean(gradients)),
            'max_gradient': float(np.max(np.abs(gradients))),
            'base_value': float(base_instance[idx]),
            'base_prediction': float(self.model.predict(base_instance.reshape(1, -1))[0])
        }

    def multi_feature_sensitivity(
        self,
        base_instance: np.ndarray,
        features: List[str],
        perturbation: float = 0.1
    ) -> Dict[str, Dict]:
        """
        Compute sensitivity for multiple features.

        Args:
            base_instance: Original values
            features: Features to analyze
            perturbation: Fractional perturbation (e.g., 0.1 = ±10%)

        Returns:
            Dict of feature -> sensitivity metrics
        """
        base_pred = float(self.model.predict(base_instance.reshape(1, -1))[0])
        sensitivities = {}

        for fname in features:
            if fname not in self._feature_idx:
                continue

            idx = self._feature_idx[fname]
            original_value = base_instance[idx]
            delta = abs(original_value * perturbation) + 1e-6

            # Forward perturbation
            forward_instance = base_instance.copy()
            forward_instance[idx] = original_value + delta
            forward_pred = float(self.model.predict(forward_instance.reshape(1, -1))[0])

            # Backward perturbation
            backward_instance = base_instance.copy()
            backward_instance[idx] = original_value - delta
            backward_pred = float(self.model.predict(backward_instance.reshape(1, -1))[0])

            sensitivities[fname] = {
                'forward_change': forward_pred - base_pred,
                'backward_change': backward_pred - base_pred,
                'central_gradient': (forward_pred - backward_pred) / (2 * delta),
                'elasticity': ((forward_pred - backward_pred) / base_pred) / (2 * perturbation)
            }

        return sensitivities


class CausalExplainer:
    """
    Causal explanation for manufacturing processes.

    Provides causal reasoning about feature effects
    respecting the causal structure of the process.
    """

    def __init__(self, causal_graph: Optional[Dict[str, List[str]]] = None):
        """
        Initialize with optional causal graph.

        Args:
            causal_graph: Dict of feature -> list of caused features
        """
        self.causal_graph = causal_graph or {}
        self.model = None
        self.feature_names: List[str] = []

    def set_causal_graph(self, graph: Dict[str, List[str]]):
        """Set the causal graph."""
        self.causal_graph = graph

    def set_model(self, model: Any, feature_names: List[str]):
        """Set the prediction model."""
        self.model = model
        self.feature_names = feature_names

    def get_causal_effects(
        self,
        instance: np.ndarray,
        intervention_feature: str,
        new_value: float
    ) -> Dict:
        """
        Compute causal effects of an intervention.

        Args:
            instance: Current feature values
            intervention_feature: Feature to intervene on
            new_value: New value for the feature

        Returns:
            Dict with direct and indirect causal effects
        """
        if intervention_feature not in self.feature_names:
            raise ValueError(f"Unknown feature: {intervention_feature}")

        # Get base prediction
        base_pred = float(self.model.predict(instance.reshape(1, -1))[0])

        # Direct effect: change only intervention feature
        direct_instance = instance.copy()
        idx = self.feature_names.index(intervention_feature)
        direct_instance[idx] = new_value
        direct_pred = float(self.model.predict(direct_instance.reshape(1, -1))[0])
        direct_effect = direct_pred - base_pred

        # Total effect: propagate through causal graph
        total_instance = self._propagate_intervention(
            instance.copy(),
            intervention_feature,
            new_value
        )
        total_pred = float(self.model.predict(total_instance.reshape(1, -1))[0])
        total_effect = total_pred - base_pred

        # Indirect effect = total - direct
        indirect_effect = total_effect - direct_effect

        # Find downstream features
        downstream = self._get_downstream_features(intervention_feature)

        return {
            'intervention_feature': intervention_feature,
            'original_value': float(instance[idx]),
            'new_value': new_value,
            'direct_effect': direct_effect,
            'indirect_effect': indirect_effect,
            'total_effect': total_effect,
            'downstream_features': downstream,
            'base_prediction': base_pred,
            'post_intervention_prediction': total_pred
        }

    def _propagate_intervention(
        self,
        instance: np.ndarray,
        feature: str,
        new_value: float
    ) -> np.ndarray:
        """Propagate intervention through causal graph."""
        idx = self.feature_names.index(feature)
        instance[idx] = new_value

        # Propagate to downstream features
        if feature in self.causal_graph:
            for downstream in self.causal_graph[feature]:
                if downstream in self.feature_names:
                    down_idx = self.feature_names.index(downstream)
                    # Simplified: small proportional change
                    change_ratio = new_value / (instance[idx] + 1e-6)
                    instance[down_idx] *= (1 + 0.1 * (change_ratio - 1))

                    # Recursively propagate
                    instance = self._propagate_intervention(
                        instance,
                        downstream,
                        instance[down_idx]
                    )

        return instance

    def _get_downstream_features(self, feature: str) -> List[str]:
        """Get all downstream features in causal graph."""
        downstream = []
        visited = set()
        queue = [feature]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            if current in self.causal_graph:
                for child in self.causal_graph[current]:
                    if child not in visited:
                        downstream.append(child)
                        queue.append(child)

        return downstream


class ManufacturingCounterfactual:
    """
    Manufacturing-specific counterfactual explanations.

    Provides actionable counterfactuals for quality
    improvement with process constraints.
    """

    def __init__(self, config: Optional[CounterfactualConfig] = None):
        self.config = config or CounterfactualConfig()
        self.explainer = CounterfactualExplainer(config)
        self.what_if = None

        # Manufacturing context
        self.process_constraints: Dict[str, Dict] = {}
        self.quality_thresholds: Dict[str, float] = {}
        self.cost_model: Dict[str, float] = {}

    def set_manufacturing_context(
        self,
        process_constraints: Dict[str, Dict],
        quality_thresholds: Dict[str, float],
        cost_model: Optional[Dict[str, float]] = None
    ):
        """
        Set manufacturing process context.

        Args:
            process_constraints: Dict of feature -> constraint metadata
            quality_thresholds: Quality metric thresholds
            cost_model: Optional cost per unit change for each feature
        """
        self.process_constraints = process_constraints
        self.quality_thresholds = quality_thresholds
        self.cost_model = cost_model or {}

        # Convert to explainer constraints
        for fname, meta in process_constraints.items():
            if 'constraint_type' in meta:
                self.config.feature_constraints[fname] = ConstraintType(meta['constraint_type'])
            if 'min' in meta and 'max' in meta:
                self.config.feature_ranges[fname] = (meta['min'], meta['max'])

    def generate_improvement_plan(
        self,
        instance: np.ndarray,
        model: Any,
        training_data: np.ndarray,
        feature_names: List[str],
        target_quality: float
    ) -> Dict:
        """
        Generate an improvement plan with actionable counterfactuals.

        Returns prioritized list of process changes to achieve target quality.
        """
        # Fit explainer
        self.explainer.fit(model, training_data, feature_names)
        self.what_if = WhatIfAnalysis(model, feature_names)

        # Get original prediction
        original_pred = float(model.predict(instance.reshape(1, -1))[0])

        # Generate counterfactuals
        counterfactuals = self.explainer.generate(instance, target_quality)

        # Compute costs and rank
        ranked_plans = []
        for cf in counterfactuals:
            if cf.validity:
                plan = self._create_improvement_plan(cf, feature_names)
                ranked_plans.append(plan)

        # Sort by total cost
        ranked_plans.sort(key=lambda x: x['total_cost'])

        # What-if analysis for top plans
        detailed_plans = []
        for plan in ranked_plans[:3]:
            detailed = self._add_what_if_analysis(plan, instance, feature_names)
            detailed_plans.append(detailed)

        return {
            'original_prediction': original_pred,
            'target_prediction': target_quality,
            'n_valid_counterfactuals': len([cf for cf in counterfactuals if cf.validity]),
            'improvement_plans': detailed_plans,
            'summary': self._generate_summary(detailed_plans)
        }

    def _create_improvement_plan(
        self,
        cf: Counterfactual,
        feature_names: List[str]
    ) -> Dict:
        """Create improvement plan from counterfactual."""
        changes = []
        total_cost = 0.0

        for fname in cf.changed_features:
            change = cf.changes[fname]
            original = cf.original_values[fname]
            new_val = cf.counterfactual_values[fname]

            # Get cost
            unit_cost = self.cost_model.get(fname, 1.0)
            change_cost = abs(change) * unit_cost

            # Get process info
            process_info = self.process_constraints.get(fname, {})

            changes.append({
                'parameter': fname,
                'current_value': original,
                'recommended_value': new_val,
                'change': change,
                'change_percent': 100 * change / (original + 1e-6),
                'cost': change_cost,
                'unit': process_info.get('unit', ''),
                'constraint': process_info.get('constraint_type', 'none'),
                'priority': 'high' if abs(change_cost) > np.median(
                    [self.cost_model.get(f, 1.0) for f in cf.changed_features]
                ) else 'medium'
            })

            total_cost += change_cost

        return {
            'predicted_improvement': cf.counterfactual_prediction - cf.original_prediction,
            'new_prediction': cf.counterfactual_prediction,
            'changes': sorted(changes, key=lambda x: x['cost'], reverse=True),
            'total_cost': total_cost,
            'n_changes': len(changes),
            'plausibility': cf.plausibility
        }

    def _add_what_if_analysis(
        self,
        plan: Dict,
        instance: np.ndarray,
        feature_names: List[str]
    ) -> Dict:
        """Add what-if analysis to improvement plan."""
        modifications = {
            c['parameter']: c['recommended_value']
            for c in plan['changes']
        }

        scenario = self.what_if.analyze_scenario(instance, modifications)
        plan['what_if_analysis'] = scenario.to_dict()

        return plan

    def _generate_summary(self, plans: List[Dict]) -> Dict:
        """Generate summary of improvement plans."""
        if not plans:
            return {'status': 'no_valid_plans', 'message': 'No valid improvement plans found'}

        best_plan = plans[0]

        summary = {
            'status': 'plans_available',
            'n_plans': len(plans),
            'best_plan': {
                'expected_improvement': best_plan['predicted_improvement'],
                'total_cost': best_plan['total_cost'],
                'n_changes_required': best_plan['n_changes'],
                'key_changes': [c['parameter'] for c in best_plan['changes'][:3]]
            },
            'recommendations': []
        }

        # Generate textual recommendations
        for change in best_plan['changes'][:3]:
            direction = "increase" if change['change'] > 0 else "decrease"
            summary['recommendations'].append(
                f"{direction.capitalize()} {change['parameter']} from {change['current_value']:.2f} "
                f"to {change['recommended_value']:.2f} {change['unit']}"
            )

        return summary
