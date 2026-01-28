"""
Curriculum Learning Manager
LegoMCP PhD-Level Manufacturing Platform

Implements curriculum learning for training:
- Difficulty-based ordering
- Self-paced learning
- Competence-based progression
- Manufacturing-specific curricula
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Tuple, Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class CurriculumStrategy(Enum):
    FIXED = "fixed"  # Pre-defined order
    SELF_PACED = "self_paced"  # Model performance-driven
    COMPETENCE = "competence"  # Competence threshold-based
    ANTI_CURRICULUM = "anti_curriculum"  # Hard first
    MIXED = "mixed"  # Interleaved difficulty


class DifficultyMetric(Enum):
    LOSS = "loss"  # Training loss
    PREDICTION_VARIANCE = "prediction_variance"
    DATA_DENSITY = "data_density"
    LABEL_NOISE = "label_noise"
    CUSTOM = "custom"


@dataclass
class CurriculumStage:
    """Single stage in curriculum."""
    stage_id: int
    name: str
    difficulty: float  # 0 (easy) to 1 (hard)
    data_indices: List[int]
    criteria: Dict[str, float]  # Advancement criteria
    completed: bool = False
    performance: float = 0.0


@dataclass
class CurriculumConfig:
    """Curriculum configuration."""
    strategy: CurriculumStrategy = CurriculumStrategy.SELF_PACED
    n_stages: int = 5
    difficulty_metric: DifficultyMetric = DifficultyMetric.LOSS
    competence_threshold: float = 0.8
    pace_factor: float = 1.0  # Speed of curriculum progression
    min_samples_per_stage: int = 100
    warmup_epochs: int = 2


class CurriculumManager:
    """
    Curriculum learning manager.

    Orders training data and manages progression
    based on sample difficulty and model competence.

    Features:
    - Automatic difficulty estimation
    - Multiple curriculum strategies
    - Self-paced learning
    - Progress tracking
    """

    def __init__(self, config: CurriculumConfig = None):
        self.config = config or CurriculumConfig()
        self._stages: List[CurriculumStage] = []
        self._current_stage: int = 0
        self._sample_difficulties: Dict[int, float] = {}
        self._competence_history: List[float] = []
        self._training_data = None
        self._initialized = False

    def initialize(
        self,
        data: np.ndarray,
        labels: np.ndarray,
        model: Any = None,
    ):
        """
        Initialize curriculum with data.

        Args:
            data: Training data
            labels: Training labels
            model: Model for difficulty estimation
        """
        self._training_data = (data, labels)
        n_samples = len(data)

        # Estimate sample difficulties
        self._estimate_difficulties(data, labels, model)

        # Create stages
        self._create_stages(n_samples)

        self._initialized = True
        logger.info(f"Curriculum initialized with {len(self._stages)} stages")

    def _estimate_difficulties(
        self,
        data: np.ndarray,
        labels: np.ndarray,
        model: Any,
    ):
        """Estimate difficulty for each sample."""
        n_samples = len(data)

        if self.config.difficulty_metric == DifficultyMetric.LOSS:
            difficulties = self._loss_based_difficulty(data, labels, model)
        elif self.config.difficulty_metric == DifficultyMetric.PREDICTION_VARIANCE:
            difficulties = self._variance_based_difficulty(data, labels, model)
        elif self.config.difficulty_metric == DifficultyMetric.DATA_DENSITY:
            difficulties = self._density_based_difficulty(data)
        else:
            # Default: random assignment
            difficulties = np.random.rand(n_samples)

        for i, diff in enumerate(difficulties):
            self._sample_difficulties[i] = float(diff)

    def _loss_based_difficulty(
        self,
        data: np.ndarray,
        labels: np.ndarray,
        model: Any,
    ) -> np.ndarray:
        """Estimate difficulty based on training loss."""
        if model is None:
            return np.random.rand(len(data))

        try:
            import torch

            model.eval()
            losses = []

            with torch.no_grad():
                for i in range(len(data)):
                    x = torch.tensor(data[i:i+1], dtype=torch.float32)
                    y = torch.tensor([labels[i]])

                    output = model(x)

                    if output.dim() > 1 and output.shape[-1] > 1:
                        loss = torch.nn.functional.cross_entropy(output, y)
                    else:
                        loss = torch.nn.functional.mse_loss(output.squeeze(), y.float())

                    losses.append(loss.item())

            losses = np.array(losses)
            # Normalize to [0, 1]
            if losses.max() > losses.min():
                losses = (losses - losses.min()) / (losses.max() - losses.min())
            return losses

        except ImportError:
            return np.random.rand(len(data))

    def _variance_based_difficulty(
        self,
        data: np.ndarray,
        labels: np.ndarray,
        model: Any,
    ) -> np.ndarray:
        """Estimate difficulty based on prediction variance."""
        if model is None:
            return np.random.rand(len(data))

        try:
            import torch

            model.train()  # Enable dropout
            predictions = []

            # Multiple forward passes
            n_passes = 10
            with torch.no_grad():
                for _ in range(n_passes):
                    x = torch.tensor(data, dtype=torch.float32)
                    pred = model(x).numpy()
                    predictions.append(pred)

            predictions = np.array(predictions)
            variance = predictions.var(axis=0).mean(axis=-1)

            # Normalize
            if variance.max() > variance.min():
                variance = (variance - variance.min()) / (variance.max() - variance.min())

            return variance

        except ImportError:
            return np.random.rand(len(data))

    def _density_based_difficulty(self, data: np.ndarray) -> np.ndarray:
        """Estimate difficulty based on data density (isolated = harder)."""
        try:
            from sklearn.neighbors import NearestNeighbors

            k = min(10, len(data) - 1)
            nn = NearestNeighbors(n_neighbors=k + 1)
            nn.fit(data)

            distances, _ = nn.kneighbors(data)
            avg_distance = distances[:, 1:].mean(axis=1)

            # Higher distance = lower density = harder
            difficulties = avg_distance
            if difficulties.max() > difficulties.min():
                difficulties = (difficulties - difficulties.min()) / (difficulties.max() - difficulties.min())

            return difficulties

        except ImportError:
            return np.random.rand(len(data))

    def _create_stages(self, n_samples: int):
        """Create curriculum stages based on difficulty."""
        difficulties = np.array([self._sample_difficulties[i] for i in range(n_samples)])
        sorted_indices = np.argsort(difficulties)

        if self.config.strategy == CurriculumStrategy.ANTI_CURRICULUM:
            sorted_indices = sorted_indices[::-1]  # Hard first

        samples_per_stage = max(
            self.config.min_samples_per_stage,
            n_samples // self.config.n_stages
        )

        self._stages = []
        for stage_id in range(self.config.n_stages):
            start_idx = stage_id * samples_per_stage
            end_idx = min(start_idx + samples_per_stage, n_samples)

            if self.config.strategy == CurriculumStrategy.MIXED:
                # Interleaved: mix easy and hard samples
                stage_indices = []
                for i in range(start_idx, end_idx):
                    stage_indices.append(sorted_indices[i])
                    if n_samples - 1 - i >= 0:
                        stage_indices.append(sorted_indices[n_samples - 1 - i])
                stage_indices = list(set(stage_indices))[:samples_per_stage]
            else:
                stage_indices = sorted_indices[start_idx:end_idx].tolist()

            difficulty = (stage_id + 1) / self.config.n_stages

            stage = CurriculumStage(
                stage_id=stage_id,
                name=f"stage_{stage_id}",
                difficulty=difficulty,
                data_indices=stage_indices,
                criteria={"accuracy": 0.7 + 0.05 * stage_id},
            )
            self._stages.append(stage)

    def get_current_stage(self) -> CurriculumStage:
        """Get current curriculum stage."""
        if not self._stages:
            raise ValueError("Curriculum not initialized")
        return self._stages[self._current_stage]

    def get_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get training data for current stage."""
        if not self._initialized:
            raise ValueError("Curriculum not initialized")

        stage = self.get_current_stage()
        data, labels = self._training_data

        stage_data = data[stage.data_indices]
        stage_labels = labels[stage.data_indices]

        return stage_data, stage_labels

    def get_cumulative_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get all data up to and including current stage."""
        if not self._initialized:
            raise ValueError("Curriculum not initialized")

        data, labels = self._training_data
        indices = []

        for stage in self._stages[:self._current_stage + 1]:
            indices.extend(stage.data_indices)

        indices = list(set(indices))
        return data[indices], labels[indices]

    def update_competence(self, performance: float):
        """
        Update competence and potentially advance stage.

        Args:
            performance: Current performance metric (0-1)
        """
        self._competence_history.append(performance)
        self._stages[self._current_stage].performance = performance

        if self.config.strategy == CurriculumStrategy.SELF_PACED:
            self._self_paced_update(performance)
        elif self.config.strategy == CurriculumStrategy.COMPETENCE:
            self._competence_update(performance)

    def _self_paced_update(self, performance: float):
        """Self-paced curriculum update."""
        # Progress based on performance and pace factor
        threshold = self.config.competence_threshold * self.config.pace_factor

        if performance >= threshold:
            self._advance_stage()

    def _competence_update(self, performance: float):
        """Competence-based curriculum update."""
        stage = self.get_current_stage()
        criteria = stage.criteria

        # Check all criteria
        if "accuracy" in criteria and performance >= criteria["accuracy"]:
            self._advance_stage()

    def _advance_stage(self):
        """Advance to next curriculum stage."""
        if self._current_stage < len(self._stages) - 1:
            self._stages[self._current_stage].completed = True
            self._current_stage += 1
            logger.info(f"Advanced to curriculum stage {self._current_stage}")

    def force_advance(self):
        """Manually advance to next stage."""
        self._advance_stage()

    def reset(self):
        """Reset curriculum to beginning."""
        self._current_stage = 0
        self._competence_history = []
        for stage in self._stages:
            stage.completed = False
            stage.performance = 0.0

    @property
    def is_complete(self) -> bool:
        """Check if curriculum is complete."""
        return all(stage.completed for stage in self._stages)

    @property
    def progress(self) -> float:
        """Get curriculum progress (0-1)."""
        if not self._stages:
            return 0.0
        return self._current_stage / len(self._stages)

    def get_statistics(self) -> Dict[str, Any]:
        """Get curriculum statistics."""
        return {
            "strategy": self.config.strategy.value,
            "n_stages": len(self._stages),
            "current_stage": self._current_stage,
            "progress": self.progress,
            "is_complete": self.is_complete,
            "competence_history": self._competence_history[-10:],
            "stages": [
                {
                    "stage_id": s.stage_id,
                    "name": s.name,
                    "difficulty": s.difficulty,
                    "n_samples": len(s.data_indices),
                    "completed": s.completed,
                    "performance": s.performance,
                }
                for s in self._stages
            ],
        }


class ManufacturingCurriculum(CurriculumManager):
    """
    Manufacturing-specific curriculum learning.

    Handles:
    - Process complexity progression
    - Product variant introduction
    - Defect type ordering
    - Equipment-specific learning
    """

    def __init__(self, config: CurriculumConfig = None):
        super().__init__(config)
        self._process_stages: Dict[str, int] = {}
        self._defect_stages: Dict[str, int] = {}

    def create_process_curriculum(
        self,
        processes: List[Dict[str, Any]],
        complexity_key: str = "complexity",
    ):
        """
        Create curriculum based on process complexity.

        Args:
            processes: List of process definitions
            complexity_key: Key for complexity in process dict
        """
        # Sort by complexity
        sorted_processes = sorted(
            processes,
            key=lambda x: x.get(complexity_key, 0)
        )

        for i, process in enumerate(sorted_processes):
            stage = CurriculumStage(
                stage_id=i,
                name=process.get("name", f"process_{i}"),
                difficulty=process.get(complexity_key, i / len(processes)),
                data_indices=[],  # Will be populated later
                criteria={"accuracy": 0.8},
            )
            self._stages.append(stage)
            self._process_stages[process.get("name", f"process_{i}")] = i

    def create_defect_curriculum(
        self,
        defect_types: List[str],
        defect_difficulties: Dict[str, float],
    ):
        """
        Create curriculum for defect detection.

        Args:
            defect_types: List of defect types
            defect_difficulties: Difficulty score per defect type
        """
        # Sort by difficulty
        sorted_defects = sorted(
            defect_types,
            key=lambda x: defect_difficulties.get(x, 0.5)
        )

        for i, defect in enumerate(sorted_defects):
            stage = CurriculumStage(
                stage_id=i,
                name=f"defect_{defect}",
                difficulty=defect_difficulties.get(defect, i / len(defect_types)),
                data_indices=[],
                criteria={"precision": 0.85, "recall": 0.8},
            )
            self._stages.append(stage)
            self._defect_stages[defect] = i

    def get_defect_training_order(self) -> List[str]:
        """Get ordered list of defect types for training."""
        return [
            stage.name.replace("defect_", "")
            for stage in self._stages
            if stage.name.startswith("defect_")
        ]


# Global instances
curriculum_manager = CurriculumManager()
manufacturing_curriculum = ManufacturingCurriculum()
