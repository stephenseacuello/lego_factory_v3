"""
LEGO Factory v3 - ML Services
=============================
Machine learning services for G-code fingerprinting and anomaly detection.

Modules:
- model: Neural network architectures (MM-DTAE-LSTM, EnhancedEncoder)
- inference: Real-time inference service
- anomaly: Comprehensive anomaly detection
- training: Training utilities and data loaders
"""

from services.ml.model.mm_dtae_lstm import (
    ModelConfig,
    MM_DTAE_LSTM,
    EnhancedEncoder,
    make_pad_mask,
)

# Anomaly detection exports
from services.ml.anomaly import (
    AnomalySeverity,
    AnomalyCategory,
    AnomalyType,
    AnomalyResult,
    AnomalyConfig,
    ThresholdConfig,
    anomaly_detection_service,
    detect_anomalies,
    detect_realtime,
    process_tag_value,
    on_anomaly,
    realtime_hook,
)
