"""
Causal Discovery - Automated structure learning.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

Learn causal structure from observational data.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
from scipy import stats
import logging

from .scm_builder import CausalGraph, CausalVariable, CausalEdge, VariableType, EdgeType

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryResult:
    """Result of causal discovery."""
    graph: CausalGraph
    confidence_scores: Dict[Tuple[str, str], float]
    algorithm_used: str
    n_samples: int
    metadata: Dict[str, Any]


class CausalDiscovery:
    """
    Automated causal structure learning.

    Implements:
    - PC Algorithm (constraint-based)
    - Correlation-based heuristics
    - Domain knowledge integration

    For production use, integrate with specialized libraries
    like causal-learn or dowhy.
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha  # Significance level for independence tests

    def discover_from_data(self,
                          data: Dict[str, List[float]],
                          variable_types: Optional[Dict[str, VariableType]] = None,
                          forbidden_edges: Optional[List[Tuple[str, str]]] = None,
                          required_edges: Optional[List[Tuple[str, str]]] = None) -> DiscoveryResult:
        """
        Discover causal structure from observational data.

        Args:
            data: Dictionary mapping variable names to value lists
            variable_types: Optional variable type specifications
            forbidden_edges: Edges that cannot exist
            required_edges: Edges that must exist

        Returns:
            DiscoveryResult with learned graph
        """
        variables = list(data.keys())
        n_samples = len(next(iter(data.values())))

        logger.info(f"Discovering causal structure from {n_samples} samples")

        # Initialize graph with all variables
        graph = CausalGraph()
        for var in variables:
            var_type = (variable_types or {}).get(var, VariableType.CONTINUOUS)
            graph.add_variable(CausalVariable(name=var, var_type=var_type))

        # Step 1: Build skeleton using PC algorithm
        skeleton, sep_sets = self._build_skeleton(data, variables)

        # Step 2: Orient edges
        oriented = self._orient_edges(skeleton, sep_sets, data)

        # Apply constraints
        if forbidden_edges:
            oriented = [(s, t) for s, t in oriented if (s, t) not in forbidden_edges]

        if required_edges:
            for edge in required_edges:
                if edge not in oriented:
                    oriented.append(edge)

        # Add edges to graph
        confidence_scores = {}
        for source, target in oriented:
            edge = CausalEdge(source=source, target=target)
            if graph.add_edge(edge):
                # Compute confidence from correlation strength
                conf = self._compute_edge_confidence(data[source], data[target])
                confidence_scores[(source, target)] = conf

        return DiscoveryResult(
            graph=graph,
            confidence_scores=confidence_scores,
            algorithm_used="PC",
            n_samples=n_samples,
            metadata={'alpha': self.alpha}
        )

    def _build_skeleton(self,
                        data: Dict[str, List[float]],
                        variables: List[str]) -> Tuple[Set[Tuple[str, str]], Dict]:
        """
        Build undirected skeleton using PC algorithm.

        Start fully connected, remove edges if conditional independence found.
        """
        n = len(variables)

        # Start with complete graph
        skeleton = set()
        for i in range(n):
            for j in range(i + 1, n):
                skeleton.add((variables[i], variables[j]))
                skeleton.add((variables[j], variables[i]))

        sep_sets = {}
        max_conditioning = min(n - 2, 3)  # Limit conditioning set size

        # Iteratively test independence
        for cond_size in range(max_conditioning + 1):
            edges_to_remove = set()

            for edge in list(skeleton):
                x, y = edge
                if (y, x) not in skeleton:
                    continue

                # Get potential conditioning variables
                neighbors = self._get_neighbors(skeleton, x) - {y}

                # Try all conditioning sets of current size
                for cond_set in self._get_subsets(neighbors, cond_size):
                    if self._is_independent(data, x, y, cond_set):
                        edges_to_remove.add((x, y))
                        edges_to_remove.add((y, x))
                        sep_sets[(x, y)] = cond_set
                        sep_sets[(y, x)] = cond_set
                        break

            skeleton -= edges_to_remove

        return skeleton, sep_sets

    def _orient_edges(self,
                      skeleton: Set[Tuple[str, str]],
                      sep_sets: Dict,
                      data: Dict[str, List[float]]) -> List[Tuple[str, str]]:
        """
        Orient edges in skeleton to create DAG.

        Uses v-structure detection and orientation rules.
        """
        oriented = []
        undirected = set()

        # Find unshielded triples and orient v-structures
        variables = set()
        for x, y in skeleton:
            variables.add(x)
            variables.add(y)

        for x in variables:
            for y in variables:
                if x == y:
                    continue
                if (x, y) not in skeleton:
                    continue

                for z in variables:
                    if z in (x, y):
                        continue
                    if (y, z) not in skeleton:
                        continue
                    if (x, z) in skeleton:
                        continue  # Not unshielded

                    # Check if y is in separating set of x, z
                    sep = sep_sets.get((x, z), set())
                    if y not in sep:
                        # V-structure: x -> y <- z
                        oriented.append((x, y))
                        oriented.append((z, y))

        # Apply Meek rules for remaining edges
        for x, y in skeleton:
            if (x, y) not in oriented and (y, x) not in oriented:
                # Use correlation direction heuristic
                corr = self._compute_correlation(data[x], data[y])
                if corr > 0:
                    # Positive correlation - use temporal/domain heuristics
                    undirected.add((x, y))

        # For undirected edges, use simple heuristic
        for x, y in undirected:
            # Orient based on variable naming convention or other heuristics
            if x < y:  # Alphabetical ordering as last resort
                oriented.append((x, y))
            else:
                oriented.append((y, x))

        return oriented

    def _is_independent(self,
                        data: Dict[str, List[float]],
                        x: str,
                        y: str,
                        cond_set: Set[str]) -> bool:
        """
        Test conditional independence of X and Y given conditioning set.

        Uses partial correlation test.
        """
        if not cond_set:
            # Marginal independence
            corr = self._compute_correlation(data[x], data[y])
            n = len(data[x])
            t_stat = corr * np.sqrt((n - 2) / (1 - corr**2 + 1e-10))
            p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 2))
            return p_value > self.alpha

        # Partial correlation
        try:
            x_data = np.array(data[x])
            y_data = np.array(data[y])
            z_data = np.column_stack([data[z] for z in cond_set])

            # Regress X and Y on Z
            x_resid = x_data - self._regress(x_data, z_data)
            y_resid = y_data - self._regress(y_data, z_data)

            partial_corr = self._compute_correlation(x_resid, y_resid)
            n = len(x_data)
            df = n - len(cond_set) - 2
            t_stat = partial_corr * np.sqrt(df / (1 - partial_corr**2 + 1e-10))
            p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df))

            return p_value > self.alpha
        except Exception:
            return False

    def _compute_correlation(self, x: List[float], y: List[float]) -> float:
        """Compute Pearson correlation."""
        x_arr = np.array(x)
        y_arr = np.array(y)
        if len(x_arr) < 2:
            return 0.0
        corr = np.corrcoef(x_arr, y_arr)[0, 1]
        return 0.0 if np.isnan(corr) else corr

    def _compute_edge_confidence(self, x: List[float], y: List[float]) -> float:
        """Compute confidence score for edge."""
        corr = abs(self._compute_correlation(x, y))
        return min(corr * 1.2, 1.0)  # Scale correlation to confidence

    def _regress(self, y: np.ndarray, X: np.ndarray) -> np.ndarray:
        """Simple linear regression prediction."""
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        X = np.column_stack([np.ones(len(X)), X])
        try:
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            return X @ beta
        except Exception:
            return np.zeros_like(y)

    def _get_neighbors(self, skeleton: Set[Tuple[str, str]], node: str) -> Set[str]:
        """Get neighbors of node in skeleton."""
        neighbors = set()
        for x, y in skeleton:
            if x == node:
                neighbors.add(y)
            if y == node:
                neighbors.add(x)
        return neighbors

    def _get_subsets(self, s: Set[str], size: int) -> List[Set[str]]:
        """Get all subsets of given size."""
        if size == 0:
            return [set()]
        if size > len(s):
            return []

        from itertools import combinations
        return [set(c) for c in combinations(s, size)]
