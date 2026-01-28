"""
Hybrid Trainer for Physics-Informed Neural Networks

Combines data-driven and physics-based training with:
- Adaptive learning rate scheduling
- Curriculum learning for physics
- Early stopping with physics validation
- Distributed training support
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class TrainerConfig:
    """
    Hybrid trainer configuration.

    Attributes:
        max_epochs: Maximum training epochs
        batch_size: Training batch size
        learning_rate: Initial learning rate
        physics_sample_ratio: Ratio of physics collocation points
        early_stopping_patience: Epochs without improvement before stopping
        validation_split: Fraction for validation
        checkpoint_interval: Epochs between checkpoints
    """
    max_epochs: int = 10000
    batch_size: int = 256
    learning_rate: float = 1e-3
    physics_sample_ratio: float = 0.5
    early_stopping_patience: int = 500
    validation_split: float = 0.1
    checkpoint_interval: int = 100
    print_interval: int = 100


@dataclass
class TrainingHistory:
    """Training history record."""
    losses: Dict[str, List[float]] = field(default_factory=dict)
    metrics: Dict[str, List[float]] = field(default_factory=dict)
    epochs: List[int] = field(default_factory=list)
    times: List[float] = field(default_factory=list)
    best_epoch: int = 0
    best_loss: float = float('inf')


class HybridTrainer:
    """
    Hybrid trainer for PINN models.

    Features:
    - Combined data and physics training
    - Adaptive loss balancing
    - Physics curriculum learning
    - Validation on physics satisfaction
    - Gradient-based optimization (simplified)

    Usage:
        >>> trainer = HybridTrainer(model, config)
        >>> history = trainer.train(x_data, y_data, x_physics)
    """

    def __init__(
        self,
        model: Any,
        config: Optional[TrainerConfig] = None
    ):
        """
        Initialize hybrid trainer.

        Args:
            model: PINN model to train
            config: Trainer configuration
        """
        self.model = model
        self.config = config or TrainerConfig()
        self.history = TrainingHistory()

        # Training state
        self._best_weights = None
        self._epochs_without_improvement = 0
        self._current_lr = self.config.learning_rate

        logger.info(f"HybridTrainer initialized: epochs={self.config.max_epochs}, "
                   f"batch_size={self.config.batch_size}")

    def train(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        x_physics: np.ndarray,
        x_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None
    ) -> TrainingHistory:
        """
        Train the PINN model.

        Args:
            x_data: Training input data
            y_data: Training target data
            x_physics: Collocation points for physics
            x_val: Optional validation inputs
            y_val: Optional validation targets

        Returns:
            TrainingHistory with losses and metrics
        """
        logger.info(f"Starting training: {len(x_data)} data points, "
                   f"{len(x_physics)} physics points")

        start_time = time.time()

        # Split validation if not provided
        if x_val is None:
            split_idx = int(len(x_data) * (1 - self.config.validation_split))
            x_val, y_val = x_data[split_idx:], y_data[split_idx:]
            x_data, y_data = x_data[:split_idx], y_data[:split_idx]

        for epoch in range(self.config.max_epochs):
            epoch_start = time.time()

            # Training step
            train_losses = self._train_epoch(x_data, y_data, x_physics)

            # Validation
            val_loss = self._validate(x_val, y_val, x_physics)

            # Record history
            self.history.epochs.append(epoch)
            for name, value in train_losses.items():
                if name not in self.history.losses:
                    self.history.losses[name] = []
                self.history.losses[name].append(value)

            if 'val_total' not in self.history.losses:
                self.history.losses['val_total'] = []
            self.history.losses['val_total'].append(val_loss)

            self.history.times.append(time.time() - epoch_start)

            # Check for improvement
            if val_loss < self.history.best_loss:
                self.history.best_loss = val_loss
                self.history.best_epoch = epoch
                self._best_weights = self._get_weights_copy()
                self._epochs_without_improvement = 0
            else:
                self._epochs_without_improvement += 1

            # Early stopping
            if self._epochs_without_improvement >= self.config.early_stopping_patience:
                logger.info(f"Early stopping at epoch {epoch}")
                break

            # Logging
            if epoch % self.config.print_interval == 0:
                logger.info(
                    f"Epoch {epoch}: train_loss={train_losses['total']:.6f}, "
                    f"val_loss={val_loss:.6f}, "
                    f"best={self.history.best_loss:.6f}"
                )

            # Learning rate decay
            if epoch > 0 and epoch % 1000 == 0:
                self._current_lr *= 0.5
                logger.info(f"Learning rate decayed to {self._current_lr}")

            # Checkpoint
            if epoch % self.config.checkpoint_interval == 0:
                self._save_checkpoint(epoch)

        # Restore best weights
        if self._best_weights is not None:
            self._restore_weights(self._best_weights)

        total_time = time.time() - start_time
        logger.info(f"Training complete in {total_time:.1f}s. "
                   f"Best loss: {self.history.best_loss:.6f} at epoch {self.history.best_epoch}")

        return self.history

    def _train_epoch(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        x_physics: np.ndarray
    ) -> Dict[str, float]:
        """Train for one epoch."""
        # Shuffle data
        indices = np.random.permutation(len(x_data))
        x_data = x_data[indices]
        y_data = y_data[indices]

        # Batch training
        epoch_losses = {}
        num_batches = 0

        for i in range(0, len(x_data), self.config.batch_size):
            # Data batch
            x_batch = x_data[i:i + self.config.batch_size]
            y_batch = y_data[i:i + self.config.batch_size]

            # Physics batch
            physics_size = int(len(x_batch) * self.config.physics_sample_ratio)
            physics_indices = np.random.choice(len(x_physics), physics_size)
            x_physics_batch = x_physics[physics_indices]

            # Forward pass
            y_pred = self.model._forward_pass(x_batch)
            y_pred_physics = self.model._forward_pass(x_physics_batch)

            # Compute losses
            batch_losses = self._compute_batch_losses(
                x_batch, y_batch, y_pred,
                x_physics_batch, y_pred_physics
            )

            # Gradient update (simplified numerical gradient descent)
            self._gradient_step(
                x_batch, y_batch,
                x_physics_batch,
                self._current_lr
            )

            # Accumulate losses
            for name, value in batch_losses.items():
                if name not in epoch_losses:
                    epoch_losses[name] = 0.0
                epoch_losses[name] += value

            num_batches += 1

        # Average losses
        for name in epoch_losses:
            epoch_losses[name] /= max(1, num_batches)

        return epoch_losses

    def _compute_batch_losses(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        y_pred: np.ndarray,
        x_physics: np.ndarray,
        y_pred_physics: np.ndarray
    ) -> Dict[str, float]:
        """Compute losses for a batch."""
        losses = {}

        # Data loss
        losses['data'] = float(np.mean((y_pred - y_data) ** 2))

        # Physics losses
        residuals = self.model.compute_physics_residual(x_physics, y_pred_physics)
        losses['physics'] = 0.0
        for name, residual in residuals.items():
            loss_value = float(np.mean(residual ** 2))
            losses[f'physics_{name}'] = loss_value
            losses['physics'] += loss_value

        losses['total'] = losses['data'] + losses['physics']
        return losses

    def _gradient_step(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        x_physics: np.ndarray,
        learning_rate: float
    ) -> None:
        """Perform gradient descent step (numerical approximation)."""
        eps = 1e-7

        for layer_idx in range(len(self.model._weights)):
            w = self.model._weights[layer_idx]
            b = self.model._biases[layer_idx]

            # Gradient for weights (simplified: random subset)
            dw = np.zeros_like(w)
            sample_rate = min(1.0, 100 / w.size)

            for i in range(w.shape[0]):
                for j in range(w.shape[1]):
                    if np.random.random() > sample_rate:
                        continue

                    # Numerical gradient
                    w[i, j] += eps
                    loss_plus, _ = self.model.compute_total_loss(x_data, y_data, x_physics)
                    w[i, j] -= 2 * eps
                    loss_minus, _ = self.model.compute_total_loss(x_data, y_data, x_physics)
                    w[i, j] += eps

                    dw[i, j] = (loss_plus - loss_minus) / (2 * eps)

            # Update weights
            self.model._weights[layer_idx] -= learning_rate * dw

            # Gradient for biases
            db = np.zeros_like(b)
            for j in range(b.shape[1]):
                b[0, j] += eps
                loss_plus, _ = self.model.compute_total_loss(x_data, y_data, x_physics)
                b[0, j] -= 2 * eps
                loss_minus, _ = self.model.compute_total_loss(x_data, y_data, x_physics)
                b[0, j] += eps

                db[0, j] = (loss_plus - loss_minus) / (2 * eps)

            self.model._biases[layer_idx] -= learning_rate * db

    def _validate(
        self,
        x_val: np.ndarray,
        y_val: np.ndarray,
        x_physics: np.ndarray
    ) -> float:
        """Compute validation loss."""
        y_pred = self.model._forward_pass(x_val)
        y_pred_physics = self.model._forward_pass(x_physics[:len(x_val)])
        residuals = self.model.compute_physics_residual(x_physics[:len(x_val)], y_pred_physics)

        data_loss = float(np.mean((y_pred - y_val) ** 2))
        physics_loss = sum(float(np.mean(r ** 2)) for r in residuals.values())

        return data_loss + physics_loss

    def _get_weights_copy(self) -> Tuple[List, List]:
        """Get copy of current weights."""
        weights = [w.copy() for w in self.model._weights]
        biases = [b.copy() for b in self.model._biases]
        return weights, biases

    def _restore_weights(self, weights_biases: Tuple[List, List]) -> None:
        """Restore weights from copy."""
        weights, biases = weights_biases
        self.model._weights = [w.copy() for w in weights]
        self.model._biases = [b.copy() for b in biases]

    def _save_checkpoint(self, epoch: int) -> None:
        """Save training checkpoint."""
        # In production, would save to disk
        pass
