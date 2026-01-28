"""
Counterfactual Engine - What-if scenario analysis.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

Answer questions like:
"What would the defect rate have been if we used 210C instead of 200C?"
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np
import logging

from .scm_builder import CausalGraph, CausalVariable

logger = logging.getLogger(__name__)


@dataclass
class CounterfactualQuery:
    """
    Counterfactual query specification.

    Given observation O, intervention I, compute counterfactual outcome Y.
    """
    observation: Dict[str, Any]      # What we observed
    intervention: Dict[str, Any]     # What we would change
    outcome: str                     # Variable to predict
    description: str = ""


@dataclass
class CounterfactualResult:
    """Result of counterfactual computation."""
    query: CounterfactualQuery
    factual_value: Any              # What actually happened
    counterfactual_value: Any       # What would have happened
    effect_size: float              # Difference
    confidence: float               # Confidence in result
    explanation: str = ""


class CounterfactualEngine:
    """
    Counterfactual reasoning engine.

    Implements the three-step process:
    1. Abduction: Infer noise/exogenous variables from observation
    2. Action: Apply intervention to the model
    3. Prediction: Compute counterfactual outcome
    """

    def __init__(self,
                 graph: CausalGraph,
                 equations: Dict[str, Callable]):
        self.graph = graph
        self.equations = equations
        self._noise_cache: Dict[str, float] = {}

    def query(self, query: CounterfactualQuery) -> CounterfactualResult:
        """
        Answer a counterfactual query.

        Args:
            query: CounterfactualQuery specification

        Returns:
            CounterfactualResult with factual and counterfactual values
        """
        logger.info(f"Counterfactual query: {query.description or query.outcome}")

        # Step 1: Abduction - infer noise terms
        noise = self._abduct(query.observation)

        # Get factual value
        factual = query.observation.get(query.outcome)

        # Step 2: Action - apply intervention
        modified_values = query.observation.copy()
        modified_values.update(query.intervention)

        # Step 3: Prediction - compute counterfactual
        counterfactual = self._predict(
            query.outcome,
            modified_values,
            noise,
            query.intervention
        )

        # Calculate effect
        if isinstance(factual, (int, float)) and isinstance(counterfactual, (int, float)):
            effect_size = counterfactual - factual
        else:
            effect_size = 0 if factual == counterfactual else 1

        return CounterfactualResult(
            query=query,
            factual_value=factual,
            counterfactual_value=counterfactual,
            effect_size=effect_size,
            confidence=0.85,
            explanation=self._generate_explanation(query, factual, counterfactual)
        )

    def _abduct(self, observation: Dict[str, Any]) -> Dict[str, float]:
        """
        Abduction step: infer noise/exogenous variables.

        Given observed values and structural equations, solve for noise terms.
        """
        noise = {}

        # Process in topological order
        order = self.graph.topological_sort()

        for var in order:
            if var not in self.equations:
                continue

            observed = observation.get(var)
            if observed is None:
                noise[var] = 0  # Default noise
                continue

            # Get parent values
            parents = self.graph.get_parents(var)
            parent_values = {p: observation.get(p, 0) for p in parents}

            # Compute what value equation would give with zero noise
            eq = self.equations[var]
            predicted = eq(parent_values, 0)

            # Infer noise as difference
            if isinstance(observed, (int, float)) and isinstance(predicted, (int, float)):
                noise[var] = observed - predicted
            else:
                noise[var] = 0

        return noise

    def _predict(self,
                 outcome: str,
                 values: Dict[str, Any],
                 noise: Dict[str, float],
                 interventions: Dict[str, Any]) -> Any:
        """
        Prediction step: compute counterfactual outcome.

        Propagate intervention effects through the model.
        """
        computed = values.copy()

        # Process in topological order
        order = self.graph.topological_sort()

        for var in order:
            if var in interventions:
                # Intervention sets value directly (do-operator)
                computed[var] = interventions[var]
            elif var in self.equations:
                # Compute from parents + noise
                parents = self.graph.get_parents(var)
                parent_values = {p: computed.get(p, 0) for p in parents}
                var_noise = noise.get(var, 0)
                computed[var] = self.equations[var](parent_values, var_noise)

        return computed.get(outcome)

    def _generate_explanation(self,
                              query: CounterfactualQuery,
                              factual: Any,
                              counterfactual: Any) -> str:
        """Generate natural language explanation."""
        intervention_desc = ', '.join(
            f"{k}={v}" for k, v in query.intervention.items()
        )

        if isinstance(factual, (int, float)) and isinstance(counterfactual, (int, float)):
            change = counterfactual - factual
            direction = "increase" if change > 0 else "decrease"
            return (
                f"If {intervention_desc}, {query.outcome} would {direction} "
                f"from {factual:.3f} to {counterfactual:.3f} (change of {change:+.3f})"
            )
        else:
            return (
                f"If {intervention_desc}, {query.outcome} would change "
                f"from {factual} to {counterfactual}"
            )

    def batch_query(self,
                    observation: Dict[str, Any],
                    intervention_scenarios: List[Dict[str, Any]],
                    outcome: str) -> List[CounterfactualResult]:
        """
        Run multiple counterfactual scenarios.

        Useful for sensitivity analysis.
        """
        results = []
        for i, intervention in enumerate(intervention_scenarios):
            query = CounterfactualQuery(
                observation=observation,
                intervention=intervention,
                outcome=outcome,
                description=f"Scenario {i+1}"
            )
            results.append(self.query(query))
        return results

    def sensitivity_analysis(self,
                            observation: Dict[str, Any],
                            intervention_var: str,
                            value_range: Tuple[float, float],
                            outcome: str,
                            n_points: int = 10) -> List[Tuple[float, float]]:
        """
        Analyze sensitivity of outcome to intervention variable.

        Returns list of (intervention_value, outcome_value) pairs.
        """
        values = np.linspace(value_range[0], value_range[1], n_points)
        results = []

        for val in values:
            query = CounterfactualQuery(
                observation=observation,
                intervention={intervention_var: val},
                outcome=outcome
            )
            result = self.query(query)
            if isinstance(result.counterfactual_value, (int, float)):
                results.append((val, result.counterfactual_value))

        return results

    def find_optimal_intervention(self,
                                  observation: Dict[str, Any],
                                  intervention_var: str,
                                  value_range: Tuple[float, float],
                                  outcome: str,
                                  target: float,
                                  n_iterations: int = 20) -> Dict[str, Any]:
        """
        Find intervention value that achieves target outcome.

        Uses binary search to find optimal intervention.
        """
        low, high = value_range

        for _ in range(n_iterations):
            mid = (low + high) / 2
            query = CounterfactualQuery(
                observation=observation,
                intervention={intervention_var: mid},
                outcome=outcome
            )
            result = self.query(query)

            if not isinstance(result.counterfactual_value, (int, float)):
                break

            if result.counterfactual_value < target:
                low = mid
            else:
                high = mid

        return {
            'optimal_value': mid,
            'predicted_outcome': result.counterfactual_value,
            'target': target,
            'gap': abs(result.counterfactual_value - target)
        }


# Convenience function
def what_if(graph: CausalGraph,
            equations: Dict[str, Callable],
            observation: Dict[str, Any],
            intervention: Dict[str, Any],
            outcome: str) -> CounterfactualResult:
    """
    Quick counterfactual query.

    Example:
        result = what_if(
            graph, equations,
            observation={'print_temp': 200, 'clutch_power': 2.0},
            intervention={'print_temp': 210},
            outcome='clutch_power'
        )
    """
    engine = CounterfactualEngine(graph, equations)
    query = CounterfactualQuery(
        observation=observation,
        intervention=intervention,
        outcome=outcome
    )
    return engine.query(query)
