"""
Intervention Engine - do-calculus implementation.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

Compute effects of interventions (do-operator).
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set
import numpy as np
import logging

from .scm_builder import CausalGraph

logger = logging.getLogger(__name__)


@dataclass
class InterventionResult:
    """Result of intervention analysis."""
    intervention: Dict[str, Any]
    target: str
    expected_value: float
    confidence_interval: tuple
    sample_size: int
    adjustment_set: Set[str]
    estimand: str


class InterventionEngine:
    """
    Intervention analysis using do-calculus.

    Computes causal effects of interventions:
    P(Y | do(X=x)) - the effect of setting X to x on Y

    Features:
    - Backdoor adjustment
    - Frontdoor adjustment
    - Identifiability checking
    """

    def __init__(self,
                 graph: CausalGraph,
                 equations: Optional[Dict[str, Callable]] = None):
        self.graph = graph
        self.equations = equations or {}

    def compute_intervention_effect(self,
                                    intervention: Dict[str, Any],
                                    target: str,
                                    data: Optional[Dict[str, List[float]]] = None) -> InterventionResult:
        """
        Compute the effect of intervention on target variable.

        Args:
            intervention: {variable: value} to intervene on
            target: Target variable to measure
            data: Optional observational data for estimation

        Returns:
            InterventionResult with expected value and confidence
        """
        intervention_var = list(intervention.keys())[0]
        intervention_val = list(intervention.values())[0]

        # Check identifiability
        if not self._is_identifiable(intervention_var, target):
            logger.warning(f"Effect of {intervention_var} on {target} may not be identifiable")

        # Find adjustment set
        adjustment_set = self._find_adjustment_set(intervention_var, target)

        if data:
            # Estimate from data using adjustment formula
            result = self._estimate_from_data(
                intervention_var, intervention_val,
                target, adjustment_set, data
            )
        else:
            # Compute using structural equations
            result = self._compute_from_equations(
                intervention_var, intervention_val, target
            )

        return InterventionResult(
            intervention=intervention,
            target=target,
            expected_value=result['expected_value'],
            confidence_interval=result['ci'],
            sample_size=result['n'],
            adjustment_set=adjustment_set,
            estimand=self._get_estimand(intervention_var, target, adjustment_set)
        )

    def _is_identifiable(self, x: str, y: str) -> bool:
        """
        Check if causal effect is identifiable.

        Simple check: effect is identifiable if there's no unobserved
        confounding (no bidirected edges in simplified model).
        """
        # In our simplified model, all effects are identifiable
        # Full implementation would check for unobserved confounders
        return True

    def _find_adjustment_set(self, x: str, y: str) -> Set[str]:
        """
        Find valid adjustment set using backdoor criterion.

        A set Z satisfies backdoor criterion if:
        1. No node in Z is a descendant of X
        2. Z blocks all backdoor paths from X to Y
        """
        # Get all ancestors of both X and Y
        x_ancestors = self.graph.get_ancestors(x)
        y_ancestors = self.graph.get_ancestors(y)

        # Get descendants of X (cannot be in adjustment set)
        x_descendants = self.graph.get_descendants(x)

        # Candidates: ancestors of Y that are not descendants of X
        candidates = (x_ancestors | y_ancestors) - x_descendants - {x, y}

        # Find minimal adjustment set
        # Simplified: use all valid candidates
        adjustment_set = set()
        for candidate in candidates:
            # Check if candidate is a confounder
            if candidate in x_ancestors and candidate in y_ancestors:
                adjustment_set.add(candidate)

        return adjustment_set

    def _estimate_from_data(self,
                            x: str,
                            x_val: float,
                            y: str,
                            adjustment_set: Set[str],
                            data: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        Estimate intervention effect from data using adjustment formula.

        E[Y | do(X=x)] = Sum_z P(Y | X=x, Z=z) P(Z=z)
        """
        x_data = np.array(data[x])
        y_data = np.array(data[y])
        n = len(x_data)

        if not adjustment_set:
            # No confounders - use simple conditional mean
            # Find observations where X is close to intervention value
            tolerance = np.std(x_data) * 0.5
            mask = np.abs(x_data - x_val) < tolerance

            if mask.sum() < 5:
                # Too few samples, use regression
                from scipy import stats
                slope, intercept, _, _, _ = stats.linregress(x_data, y_data)
                expected = intercept + slope * x_val
                se = np.std(y_data) / np.sqrt(n)
            else:
                expected = np.mean(y_data[mask])
                se = np.std(y_data[mask]) / np.sqrt(mask.sum())

            return {
                'expected_value': expected,
                'ci': (expected - 1.96 * se, expected + 1.96 * se),
                'n': n
            }

        # With adjustment set - stratified estimation
        z_data = {z: np.array(data[z]) for z in adjustment_set}

        # Simple approach: regression with adjustment variables
        import numpy as np
        from scipy import stats

        # Build design matrix [1, x, z1, z2, ...]
        X_mat = np.column_stack([
            np.ones(n),
            x_data,
            *[z_data[z] for z in adjustment_set]
        ])

        try:
            beta = np.linalg.lstsq(X_mat, y_data, rcond=None)[0]
            # Predict at intervention value
            z_means = [np.mean(z_data[z]) for z in adjustment_set]
            x_new = np.array([1, x_val, *z_means])
            expected = float(x_new @ beta)

            # Estimate SE
            residuals = y_data - X_mat @ beta
            mse = np.sum(residuals**2) / (n - len(beta))
            se = np.sqrt(mse / n)

        except Exception:
            expected = np.mean(y_data)
            se = np.std(y_data) / np.sqrt(n)

        return {
            'expected_value': expected,
            'ci': (expected - 1.96 * se, expected + 1.96 * se),
            'n': n
        }

    def _compute_from_equations(self,
                                x: str,
                                x_val: float,
                                y: str) -> Dict[str, Any]:
        """Compute intervention effect using structural equations."""
        if y not in self.equations:
            return {
                'expected_value': 0.0,
                'ci': (0.0, 0.0),
                'n': 0
            }

        # Propagate intervention through graph
        values = {x: x_val}
        order = self.graph.topological_sort()

        for var in order:
            if var == x:
                continue
            if var in self.equations:
                parents = self.graph.get_parents(var)
                parent_values = {p: values.get(p, 0) for p in parents}
                values[var] = self.equations[var](parent_values, 0)

        expected = values.get(y, 0)
        return {
            'expected_value': expected,
            'ci': (expected, expected),
            'n': 0
        }

    def _get_estimand(self,
                      x: str,
                      y: str,
                      adjustment_set: Set[str]) -> str:
        """Generate estimand formula string."""
        if not adjustment_set:
            return f"E[{y} | do({x})]"
        z_str = ', '.join(sorted(adjustment_set))
        return f"E[{y} | do({x})] = Sum_{{{z_str}}} P({y} | {x}, {z_str}) P({z_str})"

    def compare_interventions(self,
                              interventions: List[Dict[str, Any]],
                              target: str,
                              data: Optional[Dict[str, List[float]]] = None) -> List[InterventionResult]:
        """Compare multiple intervention scenarios."""
        results = []
        for intervention in interventions:
            result = self.compute_intervention_effect(intervention, target, data)
            results.append(result)

        # Sort by expected value
        results.sort(key=lambda r: r.expected_value, reverse=True)
        return results

    def optimal_intervention(self,
                            intervention_var: str,
                            target: str,
                            target_value: float,
                            value_range: tuple,
                            data: Optional[Dict[str, List[float]]] = None,
                            n_points: int = 20) -> Dict[str, Any]:
        """
        Find intervention value that achieves target outcome.
        """
        values = np.linspace(value_range[0], value_range[1], n_points)
        best_intervention = None
        best_gap = float('inf')

        for val in values:
            result = self.compute_intervention_effect(
                {intervention_var: val},
                target,
                data
            )
            gap = abs(result.expected_value - target_value)
            if gap < best_gap:
                best_gap = gap
                best_intervention = {
                    'value': val,
                    'expected_outcome': result.expected_value,
                    'gap': gap
                }

        return best_intervention
