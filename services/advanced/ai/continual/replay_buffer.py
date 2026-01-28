"""
Experience Replay Buffer
LegoMCP PhD-Level Manufacturing Platform

Implements experience replay for continual learning:
- Reservoir sampling
- Priority-based replay
- Gradient-based sample selection
- Memory-efficient storage
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Tuple, Iterator
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import random

logger = logging.getLogger(__name__)


class ReplayStrategy(Enum):
    RANDOM = "random"  # Uniform random sampling
    RESERVOIR = "reservoir"  # Reservoir sampling (stream data)
    PRIORITY = "priority"  # Priority-based (loss-weighted)
    GRADIENT = "gradient"  # Gradient-based (influence-weighted)
    HERDING = "herding"  # Herding (centroid-preserving)


@dataclass
class Experience:
    """Single experience sample."""
    data: np.ndarray  # Input features
    label: Any  # Target label/value
    task_id: str = "default"
    timestamp: float = 0.0
    priority: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayBatch:
    """Batch of experiences for training."""
    data: np.ndarray
    labels: np.ndarray
    task_ids: List[str]
    weights: np.ndarray  # Importance weights
    indices: List[int]  # Buffer indices


class ExperienceReplayBuffer:
    """
    Experience replay buffer for continual learning.

    Stores and samples past experiences to prevent
    catastrophic forgetting during sequential learning.

    Features:
    - Multiple sampling strategies
    - Task-balanced sampling
    - Memory-efficient storage
    - Priority updates
    """

    def __init__(
        self,
        capacity: int = 10000,
        strategy: ReplayStrategy = ReplayStrategy.RESERVOIR,
        per_task_limit: int = None,
    ):
        self.capacity = capacity
        self.strategy = strategy
        self.per_task_limit = per_task_limit

        self._buffer: List[Experience] = []
        self._task_counts: Dict[str, int] = {}
        self._priorities: np.ndarray = np.array([])
        self._seen_count: int = 0

    def add(
        self,
        data: np.ndarray,
        label: Any,
        task_id: str = "default",
        priority: float = 1.0,
        metadata: Dict[str, Any] = None,
    ):
        """
        Add experience to buffer.

        Args:
            data: Input features
            label: Target label/value
            task_id: Task identifier
            priority: Priority score
            metadata: Additional metadata
        """
        exp = Experience(
            data=data,
            label=label,
            task_id=task_id,
            timestamp=float(self._seen_count),
            priority=priority,
            metadata=metadata or {},
        )

        self._seen_count += 1

        if self.strategy == ReplayStrategy.RESERVOIR:
            self._reservoir_add(exp)
        elif self.strategy == ReplayStrategy.PRIORITY:
            self._priority_add(exp)
        else:
            self._simple_add(exp)

    def _simple_add(self, exp: Experience):
        """Simple FIFO addition."""
        if len(self._buffer) < self.capacity:
            self._buffer.append(exp)
            self._task_counts[exp.task_id] = self._task_counts.get(exp.task_id, 0) + 1
        else:
            # Replace oldest
            old_exp = self._buffer[0]
            self._task_counts[old_exp.task_id] -= 1
            self._buffer.pop(0)
            self._buffer.append(exp)
            self._task_counts[exp.task_id] = self._task_counts.get(exp.task_id, 0) + 1

    def _reservoir_add(self, exp: Experience):
        """
        Reservoir sampling addition.

        Maintains uniform random sample of stream.
        """
        if len(self._buffer) < self.capacity:
            self._buffer.append(exp)
            self._task_counts[exp.task_id] = self._task_counts.get(exp.task_id, 0) + 1
        else:
            # Reservoir sampling
            j = random.randint(0, self._seen_count - 1)
            if j < self.capacity:
                old_exp = self._buffer[j]
                self._task_counts[old_exp.task_id] -= 1
                self._buffer[j] = exp
                self._task_counts[exp.task_id] = self._task_counts.get(exp.task_id, 0) + 1

    def _priority_add(self, exp: Experience):
        """Priority-based addition."""
        if len(self._buffer) < self.capacity:
            self._buffer.append(exp)
            self._priorities = np.append(self._priorities, exp.priority)
            self._task_counts[exp.task_id] = self._task_counts.get(exp.task_id, 0) + 1
        else:
            # Replace lowest priority
            min_idx = np.argmin(self._priorities)
            if exp.priority > self._priorities[min_idx]:
                old_exp = self._buffer[min_idx]
                self._task_counts[old_exp.task_id] -= 1
                self._buffer[min_idx] = exp
                self._priorities[min_idx] = exp.priority
                self._task_counts[exp.task_id] = self._task_counts.get(exp.task_id, 0) + 1

    def add_batch(
        self,
        data: np.ndarray,
        labels: np.ndarray,
        task_id: str = "default",
    ):
        """
        Add batch of experiences.

        Args:
            data: Input features (n_samples, n_features)
            labels: Target labels (n_samples,)
            task_id: Task identifier
        """
        for i in range(len(data)):
            self.add(data[i], labels[i], task_id)

    def sample(
        self,
        batch_size: int = 32,
        task_balanced: bool = False,
    ) -> ReplayBatch:
        """
        Sample batch of experiences.

        Args:
            batch_size: Number of samples
            task_balanced: Balance across tasks

        Returns:
            ReplayBatch with sampled experiences
        """
        if len(self._buffer) == 0:
            raise ValueError("Buffer is empty")

        batch_size = min(batch_size, len(self._buffer))

        if task_balanced:
            indices = self._task_balanced_sample(batch_size)
        elif self.strategy == ReplayStrategy.PRIORITY:
            indices = self._priority_sample(batch_size)
        else:
            indices = random.sample(range(len(self._buffer)), batch_size)

        # Extract experiences
        experiences = [self._buffer[i] for i in indices]

        data = np.stack([exp.data for exp in experiences])
        labels = np.array([exp.label for exp in experiences])
        task_ids = [exp.task_id for exp in experiences]
        weights = np.array([exp.priority for exp in experiences])

        # Normalize weights
        weights = weights / weights.sum()

        return ReplayBatch(
            data=data,
            labels=labels,
            task_ids=task_ids,
            weights=weights,
            indices=indices,
        )

    def _task_balanced_sample(self, batch_size: int) -> List[int]:
        """Sample balanced across tasks."""
        tasks = list(self._task_counts.keys())
        if not tasks:
            return []

        samples_per_task = batch_size // len(tasks)
        extra = batch_size % len(tasks)

        indices = []
        for i, task in enumerate(tasks):
            task_indices = [
                j for j, exp in enumerate(self._buffer)
                if exp.task_id == task
            ]

            n_samples = samples_per_task + (1 if i < extra else 0)
            n_samples = min(n_samples, len(task_indices))

            if task_indices:
                indices.extend(random.sample(task_indices, n_samples))

        return indices

    def _priority_sample(self, batch_size: int) -> List[int]:
        """Sample based on priorities."""
        if len(self._priorities) == 0:
            return random.sample(range(len(self._buffer)), batch_size)

        probs = self._priorities / self._priorities.sum()
        indices = np.random.choice(
            len(self._buffer),
            size=batch_size,
            replace=False,
            p=probs,
        )
        return indices.tolist()

    def update_priorities(
        self,
        indices: List[int],
        priorities: np.ndarray,
    ):
        """
        Update priorities for sampled experiences.

        Used for priority replay with loss-based weighting.

        Args:
            indices: Buffer indices to update
            priorities: New priority values
        """
        for idx, priority in zip(indices, priorities):
            if 0 <= idx < len(self._buffer):
                self._buffer[idx].priority = float(priority)
                if idx < len(self._priorities):
                    self._priorities[idx] = float(priority)

    def get_task_samples(
        self,
        task_id: str,
        n_samples: int = None,
    ) -> List[Experience]:
        """Get samples for specific task."""
        task_samples = [exp for exp in self._buffer if exp.task_id == task_id]

        if n_samples is not None and n_samples < len(task_samples):
            task_samples = random.sample(task_samples, n_samples)

        return task_samples

    def clear(self):
        """Clear all experiences."""
        self._buffer = []
        self._task_counts = {}
        self._priorities = np.array([])

    def clear_task(self, task_id: str):
        """Clear experiences for specific task."""
        self._buffer = [exp for exp in self._buffer if exp.task_id != task_id]
        self._task_counts.pop(task_id, None)
        self._priorities = np.array([exp.priority for exp in self._buffer])

    def __len__(self) -> int:
        return len(self._buffer)

    def __iter__(self) -> Iterator[Experience]:
        return iter(self._buffer)

    @property
    def task_distribution(self) -> Dict[str, float]:
        """Get distribution of samples across tasks."""
        total = len(self._buffer)
        if total == 0:
            return {}
        return {
            task: count / total
            for task, count in self._task_counts.items()
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        return {
            "size": len(self._buffer),
            "capacity": self.capacity,
            "utilization": len(self._buffer) / self.capacity,
            "num_tasks": len(self._task_counts),
            "task_distribution": self.task_distribution,
            "seen_count": self._seen_count,
            "strategy": self.strategy.value,
        }


class GradientReplayBuffer(ExperienceReplayBuffer):
    """
    Gradient-based experience replay buffer.

    Selects samples based on gradient magnitude or
    influence on model parameters.
    """

    def __init__(self, capacity: int = 10000, model: Any = None):
        super().__init__(capacity, ReplayStrategy.GRADIENT)
        self.model = model
        self._gradients: Dict[int, np.ndarray] = {}

    def compute_sample_gradients(self, data: np.ndarray, labels: np.ndarray):
        """Compute per-sample gradients for importance."""
        try:
            import torch

            if self.model is None:
                return

            self.model.train()
            gradients = []

            for i in range(len(data)):
                x = torch.tensor(data[i:i+1], dtype=torch.float32)
                y = torch.tensor([labels[i]])

                self.model.zero_grad()
                output = self.model(x)
                loss = torch.nn.functional.cross_entropy(output, y)
                loss.backward()

                # Compute gradient norm
                grad_norm = 0
                for param in self.model.parameters():
                    if param.grad is not None:
                        grad_norm += param.grad.norm().item() ** 2
                gradients.append(np.sqrt(grad_norm))

            # Update priorities based on gradient magnitude
            for i, grad in enumerate(gradients):
                if i < len(self._buffer):
                    self._buffer[i].priority = float(grad)

            self._priorities = np.array([exp.priority for exp in self._buffer])

        except ImportError:
            logger.warning("PyTorch not available for gradient computation")


class HerdingReplayBuffer(ExperienceReplayBuffer):
    """
    Herding-based experience replay buffer.

    Maintains samples that preserve class centroids.
    """

    def __init__(self, capacity: int = 10000):
        super().__init__(capacity, ReplayStrategy.HERDING)
        self._class_means: Dict[Any, np.ndarray] = {}
        self._class_counts: Dict[Any, int] = {}

    def add(
        self,
        data: np.ndarray,
        label: Any,
        task_id: str = "default",
        priority: float = 1.0,
        metadata: Dict[str, Any] = None,
    ):
        """Add with herding-based selection."""
        # Update class mean
        if label not in self._class_means:
            self._class_means[label] = data.copy()
            self._class_counts[label] = 1
        else:
            self._class_counts[label] += 1
            alpha = 1.0 / self._class_counts[label]
            self._class_means[label] = (
                (1 - alpha) * self._class_means[label] + alpha * data
            )

        # Compute distance to class mean for priority
        class_mean = self._class_means[label]
        distance = np.linalg.norm(data - class_mean)
        priority = 1.0 / (1.0 + distance)

        super().add(data, label, task_id, priority, metadata)


# Global instance
replay_buffer = ExperienceReplayBuffer()
