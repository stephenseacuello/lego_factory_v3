"""
Continual Learning Module
=========================

LegoMCP PhD-Level Manufacturing Platform
Part of the Advanced AI/ML Operations (Phase 8.2)

This module provides continual/lifelong learning capabilities that allow
AI models to learn new tasks without forgetting previously learned ones.
This is critical for manufacturing where:

1. **New Products**: Models must adapt to new product variants
2. **Process Changes**: Equipment upgrades require model updates
3. **Shifting Conditions**: Seasonal/environmental changes affect processes
4. **Continuous Improvement**: Ongoing quality improvements

The Challenge: Catastrophic Forgetting
--------------------------------------
Standard neural networks suffer from "catastrophic forgetting" - when
trained on a new task, they forget how to perform previous tasks.
This module implements state-of-the-art techniques to prevent this.

Components:
-----------

1. **EWCTrainer** (Elastic Weight Consolidation):
   - Identifies important weights for previous tasks
   - Penalizes changes to these weights when learning new tasks
   - Uses Fisher Information Matrix to measure weight importance
   - Best for: Sequential task learning with similar input distributions

2. **ExperienceReplayBuffer**:
   - Stores representative samples from previous tasks
   - Replays old samples during training on new tasks
   - Multiple strategies: Random, Reservoir, Priority, Gradient, Herding
   - Best for: When storage is available for exemplars

3. **ProgressiveNetwork**:
   - Adds new network columns for new tasks
   - Freezes previous columns to prevent forgetting
   - Uses lateral connections to transfer knowledge
   - Best for: Distinct tasks requiring separate processing

4. **CurriculumManager**:
   - Orders training samples from easy to hard
   - Improves learning efficiency and final performance
   - Strategies: Fixed, Self-paced, Competence-based
   - Best for: Complex tasks with varying difficulty

Manufacturing Use Cases:
------------------------
- Adapting defect detection to new product lines
- Updating predictive maintenance for new equipment
- Learning new quality standards without forgetting old ones
- Continuous model improvement with production data

Example Usage:
--------------
    from services.ai.continual import (
        EWCTrainer,
        ExperienceReplayBuffer,
        CurriculumManager,
    )

    # EWC for learning new product without forgetting
    ewc = EWCTrainer(model, lambda_ewc=1000)
    ewc.register_task("product_A", train_data_A)
    ewc.train_task("product_B", train_data_B)

    # Experience replay for continuous learning
    buffer = ExperienceReplayBuffer(capacity=10000)
    buffer.add_batch(historical_data, labels, task_id="baseline")
    replay_batch = buffer.sample(batch_size=64, task_balanced=True)

    # Curriculum learning for complex tasks
    curriculum = CurriculumManager(strategy="competence")
    curriculum.initialize(data, labels, model)
    for epoch in range(num_epochs):
        train_data = curriculum.get_training_data()
        # ... train model ...
        curriculum.update_competence(validation_accuracy)

References:
-----------
- Kirkpatrick, J. et al. (2017). Overcoming catastrophic forgetting in NNs
- Rolnick, D. et al. (2019). Experience Replay for Continual Learning
- Rusu, A. et al. (2016). Progressive Neural Networks
- Bengio, Y. et al. (2009). Curriculum Learning

Author: LegoMCP Team
Version: 2.0.0
"""

# Elastic Weight Consolidation
from .ewc_trainer import (
    EWCTrainer,
    EWCConfig,
    ManufacturingEWCTrainer,
    TaskMetrics,
)

# Experience Replay
from .replay_buffer import (
    ExperienceReplayBuffer,
    ReplayStrategy,
    ReplayBatch,
    ReplayConfig,
)

# Progressive Networks
from .progressive_nets import (
    ProgressiveNetwork,
    ProgressiveConfig,
    ProgressiveColumn,
)

# Curriculum Learning
from .curriculum_manager import (
    CurriculumManager,
    CurriculumStage,
    CurriculumStrategy,
    DifficultyScorer,
)

__all__ = [
    # EWC
    "EWCTrainer",
    "EWCConfig",
    "ManufacturingEWCTrainer",
    "TaskMetrics",

    # Replay
    "ExperienceReplayBuffer",
    "ReplayStrategy",
    "ReplayBatch",
    "ReplayConfig",

    # Progressive Networks
    "ProgressiveNetwork",
    "ProgressiveConfig",
    "ProgressiveColumn",

    # Curriculum
    "CurriculumManager",
    "CurriculumStage",
    "CurriculumStrategy",
    "DifficultyScorer",
]

__version__ = "2.0.0"
__author__ = "LegoMCP Team"
