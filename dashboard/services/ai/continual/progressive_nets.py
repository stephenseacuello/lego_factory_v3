"""
Progressive Neural Networks
LegoMCP PhD-Level Manufacturing Platform

Implements progressive networks for continual learning:
- Lateral connections from previous tasks
- Column-based architecture
- Knowledge transfer without forgetting
- Manufacturing model evolution
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ProgressiveVariant(Enum):
    STANDARD = "standard"  # Original progressive nets
    PACKNET = "packnet"  # PackNet pruning-based
    HAT = "hat"  # Hard Attention to Task


@dataclass
class ProgressiveConfig:
    """Progressive network configuration."""
    hidden_dims: List[int] = field(default_factory=lambda: [256, 128, 64])
    lateral_dims: List[int] = field(default_factory=lambda: [32, 16, 8])
    activation: str = "relu"
    dropout: float = 0.1
    variant: ProgressiveVariant = ProgressiveVariant.STANDARD


@dataclass
class ColumnInfo:
    """Information about a network column."""
    column_id: int
    task_id: str
    input_dim: int
    output_dim: int
    n_parameters: int
    frozen: bool = True


class ProgressiveColumn:
    """
    Single column in progressive network.

    Each column handles one task, with lateral connections
    to all previous columns.
    """

    def __init__(
        self,
        column_id: int,
        input_dim: int,
        output_dim: int,
        hidden_dims: List[int],
        lateral_dims: List[int],
        n_previous_columns: int = 0,
    ):
        self.column_id = column_id
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.hidden_dims = hidden_dims
        self.lateral_dims = lateral_dims
        self.n_previous = n_previous_columns

        self._model = None
        self._lateral_adapters = []
        self._frozen = False

        self._build()

    def _build(self):
        """Build column architecture."""
        try:
            import torch
            import torch.nn as nn

            layers = []
            prev_dim = self.input_dim

            # Add lateral connection dimensions for non-first columns
            if self.n_previous > 0:
                lateral_input = sum(self.lateral_dims) * self.n_previous
                prev_dim += lateral_input

            for i, hidden_dim in enumerate(self.hidden_dims):
                layers.append(nn.Linear(prev_dim, hidden_dim))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(0.1))
                prev_dim = hidden_dim

            layers.append(nn.Linear(prev_dim, self.output_dim))

            self._model = nn.Sequential(*layers)

            # Build lateral adapters for each previous column
            if self.n_previous > 0:
                for _ in range(self.n_previous):
                    adapter = nn.Sequential(
                        nn.Linear(sum(self.hidden_dims), sum(self.lateral_dims)),
                        nn.ReLU(),
                    )
                    self._lateral_adapters.append(adapter)

        except ImportError:
            logger.warning("PyTorch not available, using mock column")
            self._model = MockColumn(self.input_dim, self.output_dim)

    def forward(
        self,
        x: np.ndarray,
        previous_activations: List[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Forward pass through column.

        Args:
            x: Input features
            previous_activations: Activations from previous columns

        Returns:
            Column output
        """
        try:
            import torch

            if isinstance(x, np.ndarray):
                x = torch.tensor(x, dtype=torch.float32)

            # Concatenate lateral connections
            if previous_activations and self._lateral_adapters:
                lateral_features = []
                for i, (act, adapter) in enumerate(zip(previous_activations, self._lateral_adapters)):
                    if isinstance(act, np.ndarray):
                        act = torch.tensor(act, dtype=torch.float32)
                    adapted = adapter(act)
                    lateral_features.append(adapted)

                if lateral_features:
                    lateral = torch.cat(lateral_features, dim=-1)
                    x = torch.cat([x, lateral], dim=-1)

            output = self._model(x)
            return output.detach().numpy()

        except ImportError:
            return self._model(x)

    def freeze(self):
        """Freeze column parameters."""
        self._frozen = True
        try:
            import torch
            for param in self._model.parameters():
                param.requires_grad = False
            for adapter in self._lateral_adapters:
                for param in adapter.parameters():
                    param.requires_grad = False
        except ImportError:
            pass

    def unfreeze(self):
        """Unfreeze column parameters."""
        self._frozen = False
        try:
            import torch
            for param in self._model.parameters():
                param.requires_grad = True
            for adapter in self._lateral_adapters:
                for param in adapter.parameters():
                    param.requires_grad = True
        except ImportError:
            pass

    @property
    def n_parameters(self) -> int:
        """Count trainable parameters."""
        try:
            import torch
            total = sum(p.numel() for p in self._model.parameters())
            for adapter in self._lateral_adapters:
                total += sum(p.numel() for p in adapter.parameters())
            return total
        except ImportError:
            return 0


class MockColumn:
    """Mock column for testing."""

    def __init__(self, input_dim: int, output_dim: int):
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.weights = np.random.randn(input_dim, output_dim) * 0.1

    def __call__(self, x: np.ndarray) -> np.ndarray:
        if x.ndim == 1:
            x = x.reshape(1, -1)
        return x @ self.weights[:x.shape[1], :]

    def parameters(self):
        return []


class ProgressiveNetwork:
    """
    Progressive Neural Network for continual learning.

    Grows by adding new columns for each task while
    preserving knowledge through frozen previous columns.

    Features:
    - Zero forgetting (previous columns frozen)
    - Forward transfer via lateral connections
    - Scalable to many tasks
    - Task-specific outputs
    """

    def __init__(self, config: ProgressiveConfig = None):
        self.config = config or ProgressiveConfig()
        self._columns: List[ProgressiveColumn] = []
        self._task_to_column: Dict[str, int] = {}
        self._column_infos: List[ColumnInfo] = []

    def add_task(
        self,
        task_id: str,
        input_dim: int,
        output_dim: int,
    ) -> int:
        """
        Add new task column to network.

        Args:
            task_id: Unique task identifier
            input_dim: Input dimension
            output_dim: Output dimension

        Returns:
            Column index for the new task
        """
        column_id = len(self._columns)

        # Freeze all previous columns
        for col in self._columns:
            col.freeze()

        # Create new column
        column = ProgressiveColumn(
            column_id=column_id,
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_dims=self.config.hidden_dims,
            lateral_dims=self.config.lateral_dims,
            n_previous_columns=len(self._columns),
        )

        self._columns.append(column)
        self._task_to_column[task_id] = column_id

        # Store column info
        info = ColumnInfo(
            column_id=column_id,
            task_id=task_id,
            input_dim=input_dim,
            output_dim=output_dim,
            n_parameters=column.n_parameters,
            frozen=False,
        )
        self._column_infos.append(info)

        logger.info(f"Added column {column_id} for task {task_id}")
        return column_id

    def forward(
        self,
        x: np.ndarray,
        task_id: str,
    ) -> np.ndarray:
        """
        Forward pass for specific task.

        Args:
            x: Input features
            task_id: Task to use

        Returns:
            Model output for task
        """
        if task_id not in self._task_to_column:
            raise ValueError(f"Unknown task: {task_id}")

        column_idx = self._task_to_column[task_id]

        # Get activations from previous columns
        previous_activations = []
        for i in range(column_idx):
            act = self._get_column_activations(self._columns[i], x)
            previous_activations.append(act)

        # Forward through target column
        return self._columns[column_idx].forward(x, previous_activations)

    def _get_column_activations(
        self,
        column: ProgressiveColumn,
        x: np.ndarray,
    ) -> np.ndarray:
        """Get intermediate activations from column."""
        try:
            import torch

            if isinstance(x, np.ndarray):
                x = torch.tensor(x, dtype=torch.float32)

            activations = []
            current = x

            for layer in column._model:
                current = layer(current)
                if isinstance(layer, torch.nn.Linear):
                    activations.append(current)

            # Concatenate all linear layer outputs
            if activations:
                return torch.cat(activations, dim=-1).detach().numpy()
            return current.detach().numpy()

        except ImportError:
            return column.forward(x)

    def train_task(
        self,
        task_id: str,
        train_data: Any,
        epochs: int = 10,
        lr: float = 0.001,
        loss_fn: Callable = None,
    ) -> Dict[str, float]:
        """
        Train network on specific task.

        Args:
            task_id: Task to train
            train_data: Training data
            epochs: Number of epochs
            lr: Learning rate
            loss_fn: Loss function

        Returns:
            Training metrics
        """
        if task_id not in self._task_to_column:
            raise ValueError(f"Unknown task: {task_id}")

        column_idx = self._task_to_column[task_id]
        column = self._columns[column_idx]

        try:
            import torch
            from torch.utils.data import DataLoader

            if loss_fn is None:
                loss_fn = torch.nn.CrossEntropyLoss()

            # Collect trainable parameters (only current column)
            params = list(column._model.parameters())
            for adapter in column._lateral_adapters:
                params.extend(adapter.parameters())

            optimizer = torch.optim.Adam(params, lr=lr)

            total_loss = 0
            for epoch in range(epochs):
                epoch_loss = 0

                if hasattr(train_data, '__len__'):
                    loader = DataLoader(train_data, batch_size=32, shuffle=True)
                else:
                    loader = [train_data]

                for batch in loader:
                    if isinstance(batch, (tuple, list)):
                        x, y = batch
                    else:
                        x, y = batch, batch

                    if isinstance(x, np.ndarray):
                        x = torch.tensor(x, dtype=torch.float32)
                    if isinstance(y, (np.ndarray, list)):
                        y = torch.tensor(y)

                    optimizer.zero_grad()

                    # Get previous activations
                    previous_activations = []
                    with torch.no_grad():
                        for i in range(column_idx):
                            act = self._get_column_activations(self._columns[i], x.numpy())
                            previous_activations.append(torch.tensor(act, dtype=torch.float32))

                    # Forward through current column
                    if previous_activations:
                        lateral_features = []
                        for act, adapter in zip(previous_activations, column._lateral_adapters):
                            lateral_features.append(adapter(act))
                        lateral = torch.cat(lateral_features, dim=-1)
                        x_combined = torch.cat([x, lateral], dim=-1)
                    else:
                        x_combined = x

                    output = column._model(x_combined)
                    loss = loss_fn(output, y)

                    loss.backward()
                    optimizer.step()

                    epoch_loss += loss.item()

                total_loss = epoch_loss

                if (epoch + 1) % 5 == 0:
                    logger.info(f"Task {task_id} Epoch {epoch + 1}/{epochs}, Loss: {epoch_loss:.4f}")

            # Freeze column after training
            column.freeze()
            self._column_infos[column_idx].frozen = True

            return {
                "final_loss": total_loss,
                "epochs": epochs,
                "task_id": task_id,
            }

        except ImportError:
            logger.warning("PyTorch not available, returning mock metrics")
            return {
                "final_loss": 0.1,
                "epochs": epochs,
                "task_id": task_id,
            }

    def get_task_columns(self) -> List[ColumnInfo]:
        """Get information about all task columns."""
        return self._column_infos

    @property
    def n_tasks(self) -> int:
        """Number of tasks/columns."""
        return len(self._columns)

    @property
    def total_parameters(self) -> int:
        """Total parameters across all columns."""
        return sum(col.n_parameters for col in self._columns)

    def get_statistics(self) -> Dict[str, Any]:
        """Get network statistics."""
        return {
            "n_tasks": self.n_tasks,
            "total_parameters": self.total_parameters,
            "columns": [
                {
                    "column_id": info.column_id,
                    "task_id": info.task_id,
                    "n_parameters": info.n_parameters,
                    "frozen": info.frozen,
                }
                for info in self._column_infos
            ],
        }


class ManufacturingProgressiveNetwork(ProgressiveNetwork):
    """
    Progressive network specialized for manufacturing.

    Handles:
    - Product variant models
    - Process adaptation
    - Equipment-specific learning
    """

    def __init__(self, config: ProgressiveConfig = None):
        super().__init__(config)
        self._product_columns: Dict[str, int] = {}
        self._equipment_columns: Dict[str, int] = {}

    def add_product_variant(
        self,
        product_id: str,
        input_dim: int,
        output_dim: int,
    ) -> int:
        """Add column for new product variant."""
        column_idx = self.add_task(f"product_{product_id}", input_dim, output_dim)
        self._product_columns[product_id] = column_idx
        return column_idx

    def add_equipment_model(
        self,
        equipment_id: str,
        input_dim: int,
        output_dim: int,
    ) -> int:
        """Add column for equipment-specific model."""
        column_idx = self.add_task(f"equipment_{equipment_id}", input_dim, output_dim)
        self._equipment_columns[equipment_id] = column_idx
        return column_idx

    def predict_for_product(
        self,
        x: np.ndarray,
        product_id: str,
    ) -> np.ndarray:
        """Predict using product-specific column."""
        task_id = f"product_{product_id}"
        return self.forward(x, task_id)

    def predict_for_equipment(
        self,
        x: np.ndarray,
        equipment_id: str,
    ) -> np.ndarray:
        """Predict using equipment-specific column."""
        task_id = f"equipment_{equipment_id}"
        return self.forward(x, task_id)


# Global instances
progressive_network = ProgressiveNetwork()
manufacturing_progressive = ManufacturingProgressiveNetwork()
