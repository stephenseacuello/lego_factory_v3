"""
Query Strategy - Sample selection strategies for active learning.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 4: Closed-Loop Learning
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result of query strategy."""
    indices: List[int]
    scores: List[float]
    strategy: str


class QueryStrategy(ABC):
    """Base class for active learning query strategies."""

    @abstractmethod
    def query(self,
             X: np.ndarray,
             model: Any,
             n_samples: int) -> QueryResult:
        """
        Select samples for labeling.

        Args:
            X: Unlabeled data pool
            model: Current model
            n_samples: Number of samples to select

        Returns:
            Query result with selected indices
        """
        pass


class UncertaintySampling(QueryStrategy):
    """
    Uncertainty-based sampling strategies.

    Select samples where the model is most uncertain.
    """

    def __init__(self, method: str = "entropy"):
        """
        Initialize uncertainty sampling.

        Args:
            method: "entropy", "least_confidence", or "margin"
        """
        self.method = method

    def query(self,
             X: np.ndarray,
             model: Any,
             n_samples: int) -> QueryResult:
        """Select most uncertain samples."""
        # Get model predictions
        if hasattr(model, 'predict_proba'):
            probs = model.predict_proba(X)
        else:
            # Use prediction as probability
            preds = model.predict(X)
            probs = np.column_stack([1 - preds, preds])

        # Compute uncertainty scores
        if self.method == "entropy":
            scores = self._entropy(probs)
        elif self.method == "least_confidence":
            scores = self._least_confidence(probs)
        elif self.method == "margin":
            scores = self._margin(probs)
        else:
            scores = self._entropy(probs)

        # Select top-k uncertain samples
        indices = np.argsort(scores)[::-1][:n_samples]

        return QueryResult(
            indices=indices.tolist(),
            scores=scores[indices].tolist(),
            strategy=f"uncertainty_{self.method}"
        )

    def _entropy(self, probs: np.ndarray) -> np.ndarray:
        """Compute entropy of predictions."""
        # Avoid log(0)
        probs = np.clip(probs, 1e-10, 1.0)
        return -np.sum(probs * np.log(probs), axis=1)

    def _least_confidence(self, probs: np.ndarray) -> np.ndarray:
        """Compute 1 - max(probability)."""
        return 1 - np.max(probs, axis=1)

    def _margin(self, probs: np.ndarray) -> np.ndarray:
        """Compute margin between top two predictions."""
        sorted_probs = np.sort(probs, axis=1)
        return 1 - (sorted_probs[:, -1] - sorted_probs[:, -2])


class DiversitySampling(QueryStrategy):
    """
    Diversity-based sampling strategies.

    Select samples that are diverse/representative of the data.
    """

    def __init__(self, method: str = "kmeans"):
        """
        Initialize diversity sampling.

        Args:
            method: "kmeans", "coreset", or "random"
        """
        self.method = method

    def query(self,
             X: np.ndarray,
             model: Any,
             n_samples: int) -> QueryResult:
        """Select diverse samples."""
        if self.method == "kmeans":
            indices, scores = self._kmeans_sampling(X, n_samples)
        elif self.method == "coreset":
            indices, scores = self._coreset_sampling(X, n_samples)
        else:
            indices = np.random.choice(len(X), n_samples, replace=False)
            scores = np.ones(n_samples)

        return QueryResult(
            indices=indices.tolist(),
            scores=scores.tolist(),
            strategy=f"diversity_{self.method}"
        )

    def _kmeans_sampling(self,
                        X: np.ndarray,
                        n_samples: int) -> Tuple[np.ndarray, np.ndarray]:
        """K-means based diversity sampling."""
        n = len(X)
        if n_samples >= n:
            return np.arange(n), np.ones(n)

        # Simple k-means++ initialization
        centers = [np.random.randint(n)]
        distances = np.full(n, np.inf)

        for _ in range(n_samples - 1):
            # Compute distances to nearest center
            last_center = X[centers[-1]]
            new_distances = np.sum((X - last_center) ** 2, axis=1)
            distances = np.minimum(distances, new_distances)

            # Select point with maximum distance
            next_center = np.argmax(distances)
            centers.append(next_center)

        indices = np.array(centers)
        scores = distances[indices]
        scores = scores / (scores.max() + 1e-10)

        return indices, scores

    def _coreset_sampling(self,
                         X: np.ndarray,
                         n_samples: int) -> Tuple[np.ndarray, np.ndarray]:
        """Greedy coreset construction."""
        n = len(X)
        if n_samples >= n:
            return np.arange(n), np.ones(n)

        selected = []
        remaining = set(range(n))

        # Start with random point
        first = np.random.randint(n)
        selected.append(first)
        remaining.remove(first)

        # Greedily add points maximizing minimum distance to selected
        for _ in range(n_samples - 1):
            best_idx = -1
            best_dist = -1

            for idx in remaining:
                min_dist = min(
                    np.sum((X[idx] - X[s]) ** 2)
                    for s in selected
                )
                if min_dist > best_dist:
                    best_dist = min_dist
                    best_idx = idx

            selected.append(best_idx)
            remaining.remove(best_idx)

        indices = np.array(selected)
        scores = np.ones(len(selected))

        return indices, scores


class QBCSampling(QueryStrategy):
    """
    Query by Committee (QBC) sampling.

    Select samples where committee members disagree most.
    """

    def __init__(self, n_committee: int = 5):
        """
        Initialize QBC.

        Args:
            n_committee: Number of committee members
        """
        self.n_committee = n_committee

    def query(self,
             X: np.ndarray,
             model: Any,
             n_samples: int,
             committee: Optional[List[Any]] = None) -> QueryResult:
        """Select samples with highest committee disagreement."""
        if committee is None:
            # Use single model with dropout or bootstrap
            committee = [model] * self.n_committee

        # Get predictions from each committee member
        predictions = []
        for member in committee:
            if hasattr(member, 'predict_proba'):
                pred = member.predict_proba(X)
            else:
                pred = member.predict(X)
            predictions.append(pred)

        predictions = np.array(predictions)

        # Compute disagreement (vote entropy)
        if len(predictions.shape) == 3:
            # Probabilities: average and compute entropy
            avg_pred = np.mean(predictions, axis=0)
            avg_pred = np.clip(avg_pred, 1e-10, 1.0)
            scores = -np.sum(avg_pred * np.log(avg_pred), axis=1)
        else:
            # Class predictions: compute vote entropy
            scores = np.zeros(len(X))
            for i in range(len(X)):
                votes = predictions[:, i]
                unique, counts = np.unique(votes, return_counts=True)
                vote_probs = counts / len(committee)
                scores[i] = -np.sum(vote_probs * np.log(vote_probs + 1e-10))

        indices = np.argsort(scores)[::-1][:n_samples]

        return QueryResult(
            indices=indices.tolist(),
            scores=scores[indices].tolist(),
            strategy="qbc"
        )


class CombinedStrategy(QueryStrategy):
    """
    Combined strategy using uncertainty and diversity.
    """

    def __init__(self,
                uncertainty_weight: float = 0.5,
                diversity_weight: float = 0.5):
        self.uncertainty = UncertaintySampling()
        self.diversity = DiversitySampling()
        self.uncertainty_weight = uncertainty_weight
        self.diversity_weight = diversity_weight

    def query(self,
             X: np.ndarray,
             model: Any,
             n_samples: int) -> QueryResult:
        """Combine uncertainty and diversity scores."""
        # Get uncertainty scores
        unc_result = self.uncertainty.query(X, model, len(X))
        unc_scores = np.zeros(len(X))
        for i, idx in enumerate(unc_result.indices):
            unc_scores[idx] = unc_result.scores[i] if i < len(unc_result.scores) else 0

        # Normalize
        unc_scores = (unc_scores - unc_scores.min()) / (unc_scores.max() - unc_scores.min() + 1e-10)

        # Get diversity scores using distance to labeled set
        div_result = self.diversity.query(X, model, len(X))
        div_scores = np.zeros(len(X))
        for i, idx in enumerate(div_result.indices):
            div_scores[idx] = div_result.scores[i] if i < len(div_result.scores) else 0

        # Normalize
        div_scores = (div_scores - div_scores.min()) / (div_scores.max() - div_scores.min() + 1e-10)

        # Combine
        combined = (self.uncertainty_weight * unc_scores +
                   self.diversity_weight * div_scores)

        indices = np.argsort(combined)[::-1][:n_samples]

        return QueryResult(
            indices=indices.tolist(),
            scores=combined[indices].tolist(),
            strategy="combined"
        )
