"""
Self-Supervised Learning for Manufacturing Defect Detection.

Implements state-of-the-art SSL methods for learning defect
representations without labeled data.

Research Value:
- Novel SSL approaches for manufacturing quality inspection
- Contrastive learning for defect feature extraction
- Anomaly detection via self-supervised pretraining

References:
- Chen, T., et al. (2020). A Simple Framework for Contrastive Learning (SimCLR)
- He, K., et al. (2022). Masked Autoencoders Are Scalable Vision Learners (MAE)
- Grill, J.B., et al. (2020). Bootstrap Your Own Latent (BYOL)
"""

from .contrastive_learning import (
    ContrastiveLearner,
    SimCLRConfig,
    ContrastiveAugmentation,
    NTXentLoss,
    DefectContrastive,
)
from .masked_autoencoder import (
    MaskedAutoencoder,
    MAEConfig,
    PatchEmbed,
    MAEEncoder,
    MAEDecoder,
    ManufacturingMAE,
)
from .anomaly_ssl import (
    SSLAnomalyDetector,
    AnomalyConfig,
    FeatureMemoryBank,
    AnomalyScore,
    ManufacturingAnomalySSL,
)

__all__ = [
    # Contrastive Learning
    'ContrastiveLearner',
    'SimCLRConfig',
    'ContrastiveAugmentation',
    'NTXentLoss',
    'DefectContrastive',
    # Masked Autoencoder
    'MaskedAutoencoder',
    'MAEConfig',
    'PatchEmbed',
    'MAEEncoder',
    'MAEDecoder',
    'ManufacturingMAE',
    # Anomaly Detection
    'SSLAnomalyDetector',
    'AnomalyConfig',
    'FeatureMemoryBank',
    'AnomalyScore',
    'ManufacturingAnomalySSL',
]
