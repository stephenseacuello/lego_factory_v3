"""
Multimodal Quality Prediction for Manufacturing.

Combines multiple data modalities (vision, sensors, process data)
for comprehensive quality prediction and defect detection.

Research Value:
- Novel multimodal fusion for manufacturing quality
- Cross-modal attention mechanisms
- Temporal-spatial feature fusion

References:
- Baltrusaitis, T., et al. (2019). Multimodal Machine Learning: A Survey
- Ngiam, J., et al. (2011). Multimodal Deep Learning
- Ramachandram, D. (2017). Deep Multimodal Learning
"""

from .sensor_fusion import (
    SensorFusion,
    SensorConfig,
    SensorReading,
    FusedFeatures,
    ManufacturingSensorFusion,
)
from .attention_fusion import (
    CrossModalAttention,
    AttentionConfig,
    ModalityEncoder,
    FusionTransformer,
    ManufacturingAttentionFusion,
)
from .temporal_fusion import (
    TemporalFusion,
    TemporalConfig,
    TimeSeriesEncoder,
    ImageSequenceEncoder,
    SpatioTemporalFusion,
)

__all__ = [
    # Sensor Fusion
    'SensorFusion',
    'SensorConfig',
    'SensorReading',
    'FusedFeatures',
    'ManufacturingSensorFusion',
    # Attention Fusion
    'CrossModalAttention',
    'AttentionConfig',
    'ModalityEncoder',
    'FusionTransformer',
    'ManufacturingAttentionFusion',
    # Temporal Fusion
    'TemporalFusion',
    'TemporalConfig',
    'TimeSeriesEncoder',
    'ImageSequenceEncoder',
    'SpatioTemporalFusion',
]
