"""
Sample Selector - Optimal sample selection for active learning.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 4: Closed-Loop Learning
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import logging

from .query_strategy import QueryStrategy, UncertaintySampling, DiversitySampling, CombinedStrategy

logger = logging.getLogger(__name__)


@dataclass
class SelectionResult:
    """Result of sample selection."""
    selected_indices: List[int]
    selected_scores: List[float]
    strategy_used: str
    budget_used: int
    total_pool_size: int
    expected_improvement: float


class SampleSelector:
    """
    Intelligent sample selection for active learning.

    Features:
    - Multiple strategy support
    - Budget constraints
    - Batch selection with diversity
    - Cost-sensitive selection
    """

    def __init__(self,
                 strategy: str = "combined",
                 batch_size: int = 10,
                 budget: Optional[int] = None):
        """
        Initialize sample selector.

        Args:
            strategy: Selection strategy
            batch_size: Samples to select per batch
            budget: Total labeling budget
        """
        self.batch_size = batch_size
        self.budget = budget
        self._labels_used = 0

        # Set strategy
        if strategy == "uncertainty":
            self._strategy = UncertaintySampling()
        elif strategy == "diversity":
            self._strategy = DiversitySampling()
        elif strategy == "combined":
            self._strategy = CombinedStrategy()
        else:
            self._strategy = CombinedStrategy()

        self._strategy_name = strategy

    def select(self,
              X_pool: np.ndarray,
              model: Any,
              n_samples: Optional[int] = None,
              exclude_indices: Optional[List[int]] = None) -> SelectionResult:
        """
        Select samples for labeling.

        Args:
            X_pool: Unlabeled data pool
            model: Current model
            n_samples: Number to select (default: batch_size)
            exclude_indices: Indices to exclude

        Returns:
            Selection result
        """
        n_samples = n_samples or self.batch_size

        # Check budget
        if self.budget is not None:
            remaining = self.budget - self._labels_used
            n_samples = min(n_samples, remaining)

            if n_samples <= 0:
                return SelectionResult(
                    selected_indices=[],
                    selected_scores=[],
                    strategy_used=self._strategy_name,
                    budget_used=0,
                    total_pool_size=len(X_pool),
                    expected_improvement=0.0
                )

        # Exclude already selected
        if exclude_indices:
            mask = np.ones(len(X_pool), dtype=bool)
            mask[exclude_indices] = False
            X_available = X_pool[mask]
            original_indices = np.where(mask)[0]
        else:
            X_available = X_pool
            original_indices = np.arange(len(X_pool))

        if len(X_available) == 0:
            return SelectionResult(
                selected_indices=[],
                selected_scores=[],
                strategy_used=self._strategy_name,
                budget_used=0,
                total_pool_size=len(X_pool),
                expected_improvement=0.0
            )

        # Apply strategy
        result = self._strategy.query(X_available, model, n_samples)

        # Map back to original indices
        selected = [int(original_indices[i]) for i in result.indices]

        # Estimate improvement
        improvement = self._estimate_improvement(result.scores)

        self._labels_used += len(selected)

        return SelectionResult(
            selected_indices=selected,
            selected_scores=result.scores,
            strategy_used=self._strategy_name,
            budget_used=len(selected),
            total_pool_size=len(X_pool),
            expected_improvement=improvement
        )

    def select_with_costs(self,
                         X_pool: np.ndarray,
                         model: Any,
                         costs: np.ndarray,
                         budget: float) -> SelectionResult:
        """
        Select samples considering labeling costs.

        Args:
            X_pool: Unlabeled data pool
            model: Current model
            costs: Cost per sample
            budget: Total cost budget

        Returns:
            Selection result
        """
        # Get scores from strategy
        result = self._strategy.query(X_pool, model, len(X_pool))

        # Compute value = score / cost (bang for buck)
        scores = np.zeros(len(X_pool))
        for i, idx in enumerate(result.indices):
            if i < len(result.scores):
                scores[idx] = result.scores[i]

        values = scores / (costs + 1e-10)

        # Greedy selection within budget
        selected = []
        selected_scores = []
        total_cost = 0

        order = np.argsort(values)[::-1]

        for idx in order:
            if total_cost + costs[idx] <= budget:
                selected.append(int(idx))
                selected_scores.append(float(scores[idx]))
                total_cost += costs[idx]

        return SelectionResult(
            selected_indices=selected,
            selected_scores=selected_scores,
            strategy_used=f"{self._strategy_name}_cost_aware",
            budget_used=len(selected),
            total_pool_size=len(X_pool),
            expected_improvement=self._estimate_improvement(selected_scores)
        )

    def select_batch_diverse(self,
                            X_pool: np.ndarray,
                            model: Any,
                            n_samples: int,
                            diversity_weight: float = 0.3) -> SelectionResult:
        """
        Select batch with diversity constraint.

        Ensures selected samples are diverse while being informative.
        """
        # Get uncertainty scores
        uncertainty = UncertaintySampling()
        unc_result = uncertainty.query(X_pool, model, len(X_pool))

        scores = np.zeros(len(X_pool))
        for i, idx in enumerate(unc_result.indices):
            if i < len(unc_result.scores):
                scores[idx] = unc_result.scores[i]

        # Greedy selection with diversity
        selected = []
        remaining = set(range(len(X_pool)))

        while len(selected) < n_samples and remaining:
            if not selected:
                # First sample: highest uncertainty
                best = max(remaining, key=lambda i: scores[i])
            else:
                # Balance uncertainty and diversity
                best = None
                best_value = -float('inf')

                for idx in remaining:
                    # Uncertainty component
                    unc_score = scores[idx]

                    # Diversity component (min distance to selected)
                    min_dist = min(
                        np.sum((X_pool[idx] - X_pool[s]) ** 2)
                        for s in selected
                    )
                    div_score = np.sqrt(min_dist)

                    # Normalize
                    div_score = div_score / (np.max(X_pool) - np.min(X_pool) + 1e-10)

                    # Combined value
                    value = (1 - diversity_weight) * unc_score + diversity_weight * div_score

                    if value > best_value:
                        best_value = value
                        best = idx

            selected.append(best)
            remaining.remove(best)

        selected_scores = [float(scores[i]) for i in selected]

        return SelectionResult(
            selected_indices=selected,
            selected_scores=selected_scores,
            strategy_used="batch_diverse",
            budget_used=len(selected),
            total_pool_size=len(X_pool),
            expected_improvement=self._estimate_improvement(selected_scores)
        )

    def _estimate_improvement(self, scores: List[float]) -> float:
        """Estimate expected model improvement from selected samples."""
        if not scores:
            return 0.0

        # Simple heuristic: higher average score = more potential improvement
        avg_score = sum(scores) / len(scores)
        n_samples = len(scores)

        # Diminishing returns with more samples
        improvement = avg_score * np.log1p(n_samples)

        return min(improvement, 1.0)

    def get_remaining_budget(self) -> Optional[int]:
        """Get remaining labeling budget."""
        if self.budget is None:
            return None
        return max(0, self.budget - self._labels_used)

    def reset_budget(self) -> None:
        """Reset budget counter."""
        self._labels_used = 0

    def set_strategy(self, strategy: QueryStrategy) -> None:
        """Set custom query strategy."""
        self._strategy = strategy
        self._strategy_name = "custom"

    def get_statistics(self) -> Dict[str, Any]:
        """Get selection statistics."""
        return {
            'strategy': self._strategy_name,
            'batch_size': self.batch_size,
            'total_budget': self.budget,
            'labels_used': self._labels_used,
            'remaining_budget': self.get_remaining_budget()
        }
