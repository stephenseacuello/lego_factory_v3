"""
Federated Learning Client for Manufacturing Edge Devices.

This module implements the edge client for federated learning:
- Local model training on factory data
- Gradient computation and compression
- Secure communication with server
- Resource-aware training scheduling

Research Contributions:
- Edge-optimized training for manufacturing devices
- Adaptive local training strategies
- Quality-aware data sampling

References:
- McMahan, B., et al. (2017). Communication-Efficient Learning of Deep Networks
- Li, T., et al. (2020). Federated Optimization in Heterogeneous Networks
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging
from datetime import datetime
import hashlib
import time

logger = logging.getLogger(__name__)


class ClientState(Enum):
    """State of the federated client."""
    IDLE = "idle"
    TRAINING = "training"
    UPLOADING = "uploading"
    WAITING = "waiting"
    ERROR = "error"


class CompressionMethod(Enum):
    """Gradient compression methods."""
    NONE = "none"
    TOP_K = "top_k"  # Keep top-k gradients
    RANDOM_K = "random_k"  # Random sparsification
    QUANTIZATION = "quantization"  # Gradient quantization
    SIGNSGD = "signsgd"  # Sign of gradients only


@dataclass
class ClientConfig:
    """Configuration for federated client."""
    client_id: str
    factory_id: str
    server_url: str = "localhost:8080"
    device_type: str = "edge"  # edge, gateway, cloud
    # Training
    local_epochs: int = 5
    local_batch_size: int = 32
    learning_rate: float = 0.01
    weight_decay: float = 0.0001
    # FedProx
    proximal_mu: float = 0.0  # 0 = no proximal term
    # Communication
    compression: CompressionMethod = CompressionMethod.NONE
    compression_ratio: float = 0.1  # For top-k, random-k
    max_retries: int = 3
    timeout: float = 60.0
    # Resource constraints
    max_memory_mb: float = 512.0
    max_training_time: float = 300.0  # seconds
    # Data handling
    validation_split: float = 0.1
    shuffle_data: bool = True


@dataclass
class LocalDataset:
    """Local dataset for training."""
    X: np.ndarray
    y: np.ndarray
    sample_weights: Optional[np.ndarray] = None
    metadata: Dict = field(default_factory=dict)

    @property
    def n_samples(self) -> int:
        return len(self.X)

    def get_batches(
        self,
        batch_size: int,
        shuffle: bool = True
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Get data batches."""
        indices = np.arange(self.n_samples)
        if shuffle:
            np.random.shuffle(indices)

        batches = []
        for i in range(0, self.n_samples, batch_size):
            batch_idx = indices[i:i+batch_size]
            batches.append((self.X[batch_idx], self.y[batch_idx]))

        return batches


@dataclass
class ModelUpdate:
    """Model update to send to server."""
    client_id: str
    round_number: int
    parameters: Dict[str, np.ndarray]
    gradients: Optional[Dict[str, np.ndarray]]
    num_samples: int
    training_loss: float
    validation_metrics: Dict[str, float]
    training_time: float
    timestamp: datetime = field(default_factory=datetime.now)
    checksum: Optional[str] = None

    def compute_checksum(self) -> str:
        """Compute checksum for integrity."""
        param_bytes = b''
        for name in sorted(self.parameters.keys()):
            param_bytes += self.parameters[name].tobytes()
        return hashlib.sha256(param_bytes).hexdigest()

    def set_checksum(self):
        """Set checksum on update."""
        self.checksum = self.compute_checksum()


class LocalTrainer:
    """
    Local model trainer for federated learning.

    Handles local training on edge device data.
    """

    def __init__(
        self,
        model: Any,
        config: ClientConfig,
        loss_fn: Optional[Callable] = None,
        metrics: Optional[Dict[str, Callable]] = None
    ):
        self.model = model
        self.config = config
        self.loss_fn = loss_fn or self._mse_loss
        self.metrics = metrics or {'mse': self._mse_loss}

        # Training state
        self.current_epoch = 0
        self.training_history: List[Dict] = []

    def train(
        self,
        dataset: LocalDataset,
        global_model: Dict[str, np.ndarray],
        round_number: int
    ) -> ModelUpdate:
        """
        Train model locally on dataset.

        Args:
            dataset: Local training data
            global_model: Current global model parameters
            round_number: Current federated round number

        Returns:
            ModelUpdate with trained parameters
        """
        start_time = time.time()

        # Initialize model with global parameters
        self._set_model_parameters(global_model)

        # Store global model for FedProx
        global_params = {k: v.copy() for k, v in global_model.items()}

        # Split validation set
        train_data, val_data = self._split_validation(dataset)

        # Training loop
        epoch_losses = []
        for epoch in range(self.config.local_epochs):
            epoch_loss = self._train_epoch(train_data, global_params)
            epoch_losses.append(epoch_loss)

            # Check time limit
            if time.time() - start_time > self.config.max_training_time:
                logger.warning(f"Training time limit reached at epoch {epoch+1}")
                break

        # Get updated parameters
        updated_params = self._get_model_parameters()

        # Compute gradients (for gradient-based compression)
        gradients = {
            name: updated_params[name] - global_params[name]
            for name in updated_params.keys()
        }

        # Apply compression if configured
        if self.config.compression != CompressionMethod.NONE:
            gradients = self._compress_gradients(gradients)

        # Validation metrics
        val_metrics = self._evaluate(val_data) if val_data else {}

        training_time = time.time() - start_time

        update = ModelUpdate(
            client_id=self.config.client_id,
            round_number=round_number,
            parameters=updated_params,
            gradients=gradients,
            num_samples=train_data.n_samples,
            training_loss=float(np.mean(epoch_losses)),
            validation_metrics=val_metrics,
            training_time=training_time
        )
        update.set_checksum()

        # Store history
        self.training_history.append({
            'round': round_number,
            'epochs': len(epoch_losses),
            'final_loss': epoch_losses[-1] if epoch_losses else None,
            'validation_metrics': val_metrics,
            'training_time': training_time
        })

        return update

    def _train_epoch(
        self,
        dataset: LocalDataset,
        global_params: Dict[str, np.ndarray]
    ) -> float:
        """Train for one epoch."""
        batches = dataset.get_batches(
            self.config.local_batch_size,
            shuffle=self.config.shuffle_data
        )

        epoch_losses = []
        for X_batch, y_batch in batches:
            loss = self._train_batch(X_batch, y_batch, global_params)
            epoch_losses.append(loss)

        self.current_epoch += 1
        return float(np.mean(epoch_losses))

    def _train_batch(
        self,
        X: np.ndarray,
        y: np.ndarray,
        global_params: Dict[str, np.ndarray]
    ) -> float:
        """Train on a single batch."""
        # Forward pass
        predictions = self._forward(X)
        loss = self.loss_fn(predictions, y)

        # Add FedProx proximal term if configured
        if self.config.proximal_mu > 0:
            current_params = self._get_model_parameters()
            prox_term = sum(
                np.sum((current_params[name] - global_params[name]) ** 2)
                for name in current_params.keys()
            )
            loss += 0.5 * self.config.proximal_mu * prox_term

        # Backward pass (simplified - real impl would use autograd)
        gradients = self._compute_gradients(X, y, predictions)

        # Update parameters
        self._update_parameters(gradients)

        return float(loss)

    def _forward(self, X: np.ndarray) -> np.ndarray:
        """Forward pass through model."""
        # Simplified - real implementation depends on model type
        if hasattr(self.model, 'predict'):
            return self.model.predict(X)
        elif hasattr(self.model, '__call__'):
            return self.model(X)
        else:
            # Simple linear model
            params = self._get_model_parameters()
            if 'weights' in params:
                return X @ params['weights'] + params.get('bias', 0)
            return X

    def _compute_gradients(
        self,
        X: np.ndarray,
        y: np.ndarray,
        predictions: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """Compute gradients (simplified)."""
        # For a linear model: gradient = X.T @ (predictions - y) / n
        error = predictions - y
        n = len(y)

        return {
            'weights': X.T @ error / n,
            'bias': np.mean(error, axis=0)
        }

    def _update_parameters(self, gradients: Dict[str, np.ndarray]):
        """Update model parameters using gradients."""
        params = self._get_model_parameters()

        for name in gradients.keys():
            if name in params:
                params[name] -= self.config.learning_rate * gradients[name]
                # Weight decay
                if self.config.weight_decay > 0 and name != 'bias':
                    params[name] -= self.config.weight_decay * params[name]

        self._set_model_parameters(params)

    def _get_model_parameters(self) -> Dict[str, np.ndarray]:
        """Get model parameters."""
        if hasattr(self.model, 'get_parameters'):
            return self.model.get_parameters()
        elif hasattr(self.model, 'coef_') and hasattr(self.model, 'intercept_'):
            return {
                'weights': self.model.coef_,
                'bias': self.model.intercept_
            }
        else:
            # Assume model has parameters dict
            return getattr(self.model, 'parameters', {})

    def _set_model_parameters(self, params: Dict[str, np.ndarray]):
        """Set model parameters."""
        if hasattr(self.model, 'set_parameters'):
            self.model.set_parameters(params)
        elif hasattr(self.model, 'coef_') and 'weights' in params:
            self.model.coef_ = params['weights']
            if 'bias' in params:
                self.model.intercept_ = params['bias']
        else:
            for name, value in params.items():
                setattr(self.model, name, value)

    def _split_validation(
        self,
        dataset: LocalDataset
    ) -> Tuple[LocalDataset, Optional[LocalDataset]]:
        """Split dataset into training and validation."""
        if self.config.validation_split <= 0:
            return dataset, None

        n_val = int(dataset.n_samples * self.config.validation_split)
        if n_val < 1:
            return dataset, None

        indices = np.random.permutation(dataset.n_samples)
        val_idx = indices[:n_val]
        train_idx = indices[n_val:]

        train_data = LocalDataset(
            X=dataset.X[train_idx],
            y=dataset.y[train_idx]
        )
        val_data = LocalDataset(
            X=dataset.X[val_idx],
            y=dataset.y[val_idx]
        )

        return train_data, val_data

    def _evaluate(self, dataset: LocalDataset) -> Dict[str, float]:
        """Evaluate model on dataset."""
        predictions = self._forward(dataset.X)

        metrics = {}
        for name, metric_fn in self.metrics.items():
            metrics[name] = float(metric_fn(predictions, dataset.y))

        return metrics

    def _compress_gradients(
        self,
        gradients: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """Compress gradients for communication efficiency."""
        compressed = {}

        for name, grad in gradients.items():
            if self.config.compression == CompressionMethod.TOP_K:
                compressed[name] = self._top_k_sparsify(grad)
            elif self.config.compression == CompressionMethod.RANDOM_K:
                compressed[name] = self._random_sparsify(grad)
            elif self.config.compression == CompressionMethod.QUANTIZATION:
                compressed[name] = self._quantize(grad)
            elif self.config.compression == CompressionMethod.SIGNSGD:
                compressed[name] = np.sign(grad)
            else:
                compressed[name] = grad

        return compressed

    def _top_k_sparsify(self, gradient: np.ndarray) -> np.ndarray:
        """Keep only top-k gradient values."""
        flat = gradient.flatten()
        k = max(1, int(len(flat) * self.config.compression_ratio))

        # Get indices of top-k by magnitude
        top_indices = np.argsort(np.abs(flat))[-k:]

        # Create sparse gradient
        sparse = np.zeros_like(flat)
        sparse[top_indices] = flat[top_indices]

        return sparse.reshape(gradient.shape)

    def _random_sparsify(self, gradient: np.ndarray) -> np.ndarray:
        """Random sparsification."""
        flat = gradient.flatten()
        k = max(1, int(len(flat) * self.config.compression_ratio))

        # Random indices
        indices = np.random.choice(len(flat), size=k, replace=False)

        sparse = np.zeros_like(flat)
        sparse[indices] = flat[indices] / self.config.compression_ratio

        return sparse.reshape(gradient.shape)

    def _quantize(self, gradient: np.ndarray, bits: int = 8) -> np.ndarray:
        """Quantize gradients."""
        min_val, max_val = gradient.min(), gradient.max()
        if max_val - min_val < 1e-8:
            return gradient

        # Quantize
        n_levels = 2 ** bits
        scale = (max_val - min_val) / (n_levels - 1)
        quantized = np.round((gradient - min_val) / scale)

        # Dequantize
        return quantized * scale + min_val

    @staticmethod
    def _mse_loss(predictions: np.ndarray, targets: np.ndarray) -> float:
        """Mean squared error loss."""
        return float(np.mean((predictions - targets) ** 2))


class FederatedClient:
    """
    Federated Learning Client for manufacturing edge devices.

    Coordinates local training and communication with server.
    """

    def __init__(self, config: ClientConfig):
        self.config = config
        self.state = ClientState.IDLE

        # Model and trainer
        self.model = None
        self.trainer: Optional[LocalTrainer] = None

        # Local data
        self.local_data: Optional[LocalDataset] = None
        self.data_quality_score: float = 1.0

        # Server communication
        self.current_global_model: Optional[Dict[str, np.ndarray]] = None
        self.current_round: int = 0

        # History
        self.update_history: List[ModelUpdate] = []

        logger.info(f"Federated client {config.client_id} initialized")

    def set_model(
        self,
        model: Any,
        loss_fn: Optional[Callable] = None,
        metrics: Optional[Dict[str, Callable]] = None
    ):
        """Set the model for training."""
        self.model = model
        self.trainer = LocalTrainer(model, self.config, loss_fn, metrics)

    def set_local_data(
        self,
        X: np.ndarray,
        y: np.ndarray,
        metadata: Optional[Dict] = None
    ):
        """Set local training data."""
        self.local_data = LocalDataset(X=X, y=y, metadata=metadata or {})

        # Compute data quality score
        self.data_quality_score = self._compute_data_quality()

        logger.info(f"Local data set: {self.local_data.n_samples} samples, quality: {self.data_quality_score:.2f}")

    def _compute_data_quality(self) -> float:
        """Compute data quality score."""
        if self.local_data is None:
            return 0.0

        # Simple quality metrics
        # 1. Check for NaN/Inf
        nan_ratio = np.mean(~np.isfinite(self.local_data.X))

        # 2. Check label distribution balance (for classification)
        if len(np.unique(self.local_data.y)) < 10:  # Assume classification
            _, counts = np.unique(self.local_data.y, return_counts=True)
            balance = np.min(counts) / np.max(counts)
        else:
            balance = 1.0

        # 3. Feature variance (low variance = less useful)
        variances = np.var(self.local_data.X, axis=0)
        low_variance_ratio = np.mean(variances < 1e-6)

        # Combined score
        quality = (1 - nan_ratio) * balance * (1 - low_variance_ratio)
        return float(np.clip(quality, 0, 1))

    def receive_global_model(
        self,
        model_parameters: Dict[str, np.ndarray],
        round_number: int,
        training_config: Optional[Dict] = None
    ):
        """Receive global model from server."""
        self.current_global_model = model_parameters
        self.current_round = round_number

        # Update training config if provided
        if training_config:
            if 'local_epochs' in training_config:
                self.config.local_epochs = training_config['local_epochs']
            if 'learning_rate' in training_config:
                self.config.learning_rate = training_config['learning_rate']
            if 'proximal_mu' in training_config:
                self.config.proximal_mu = training_config['proximal_mu']

        logger.info(f"Received global model for round {round_number}")

    def train_local(self) -> Optional[ModelUpdate]:
        """Perform local training."""
        if self.trainer is None:
            logger.error("Trainer not set")
            return None

        if self.local_data is None:
            logger.error("No local data")
            return None

        if self.current_global_model is None:
            logger.error("No global model received")
            return None

        try:
            self.state = ClientState.TRAINING

            update = self.trainer.train(
                self.local_data,
                self.current_global_model,
                self.current_round
            )

            self.update_history.append(update)
            self.state = ClientState.IDLE

            logger.info(f"Local training completed. Loss: {update.training_loss:.4f}")
            return update

        except Exception as e:
            logger.error(f"Training failed: {e}")
            self.state = ClientState.ERROR
            return None

    def get_status(self) -> Dict:
        """Get client status."""
        return {
            'client_id': self.config.client_id,
            'factory_id': self.config.factory_id,
            'state': self.state.value,
            'current_round': self.current_round,
            'n_samples': self.local_data.n_samples if self.local_data else 0,
            'data_quality_score': self.data_quality_score,
            'n_updates_sent': len(self.update_history),
            'last_training_time': self.update_history[-1].training_time if self.update_history else None
        }

    def get_training_history(self) -> List[Dict]:
        """Get local training history."""
        return [
            {
                'round': u.round_number,
                'loss': u.training_loss,
                'validation_metrics': u.validation_metrics,
                'training_time': u.training_time,
                'n_samples': u.num_samples
            }
            for u in self.update_history
        ]


class ManufacturingClient(FederatedClient):
    """
    Manufacturing-specific federated client.

    Adds production-aware training and quality features.
    """

    def __init__(self, config: ClientConfig):
        super().__init__(config)

        # Manufacturing context
        self.production_status: str = "normal"
        self.machine_ids: List[str] = []
        self.quality_metrics: Dict[str, float] = {}

    def set_production_context(
        self,
        production_status: str,
        machine_ids: List[str],
        quality_metrics: Dict[str, float]
    ):
        """Set production context."""
        self.production_status = production_status
        self.machine_ids = machine_ids
        self.quality_metrics = quality_metrics

    def is_available_for_training(self) -> bool:
        """Check if client is available for training."""
        # Not available during peak production
        if self.production_status == "peak":
            return False

        # Not available if any machine is in critical state
        if self.quality_metrics.get('machine_health', 1.0) < 0.5:
            return False

        return True

    def adaptive_training(self) -> Optional[ModelUpdate]:
        """Adaptive training based on production context."""
        if not self.is_available_for_training():
            logger.info("Client not available for training during production")
            return None

        # Adjust training based on context
        original_epochs = self.config.local_epochs

        if self.production_status == "low":
            # More aggressive training during low production
            self.config.local_epochs = min(10, original_epochs * 2)
        elif self.production_status == "maintenance":
            # Full training during maintenance
            self.config.local_epochs = 10

        try:
            update = self.train_local()
        finally:
            # Restore original config
            self.config.local_epochs = original_epochs

        return update

    def quality_weighted_data_selection(
        self,
        n_samples: Optional[int] = None
    ) -> LocalDataset:
        """Select training data weighted by quality."""
        if self.local_data is None:
            raise ValueError("No local data")

        if n_samples is None or n_samples >= self.local_data.n_samples:
            return self.local_data

        # Weight by sample quality (if available)
        if self.local_data.sample_weights is not None:
            weights = self.local_data.sample_weights
            weights = weights / weights.sum()
            indices = np.random.choice(
                self.local_data.n_samples,
                size=n_samples,
                replace=False,
                p=weights
            )
        else:
            indices = np.random.choice(
                self.local_data.n_samples,
                size=n_samples,
                replace=False
            )

        return LocalDataset(
            X=self.local_data.X[indices],
            y=self.local_data.y[indices]
        )
