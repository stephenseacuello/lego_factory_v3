"""
LEGO Factory v3 - ML Training Services
=======================================
Training infrastructure for the MM-DTAE-LSTM fingerprinting model.
"""

from .trainer import (
    Trainer,
    TrainingConfig,
    TrainingMetrics,
    get_trainer,
)
from .losses import (
    FingerprintLoss,
    MultiTaskLoss,
    ContrastiveLoss,
)
from .data_loader import (
    SensorDataset,
    create_data_loaders,
)

__all__ = [
    'Trainer',
    'TrainingConfig',
    'TrainingMetrics',
    'get_trainer',
    'FingerprintLoss',
    'MultiTaskLoss',
    'ContrastiveLoss',
    'SensorDataset',
    'create_data_loaders',
]
