"""
LEGO Factory v3 - ML Anomaly Detection Module
==============================================
Comprehensive anomaly detection for manufacturing sensor data.

This module provides:
- Statistical anomaly detection (z-score, IQR, modified z-score)
- Threshold-based detection for sensor values
- ML pattern detection using trained models
- ISA-18.2 alarm integration
- Real-time detection hooks for data streams
"""

from services.ml.anomaly.anomaly_types import (
    AnomalySeverity,
    AnomalyCategory,
    AnomalyType,
    AnomalyResult,
    AnomalyConfig,
    ThresholdConfig,
)

from services.ml.anomaly.anomaly_detection_service import (
    AnomalyDetectionService,
    anomaly_detection_service,
    detect_anomalies,
    detect_realtime,
    get_detection_config,
    update_detection_config,
    SlidingWindow,
    StatisticalDetector,
    ThresholdDetector,
    PatternDetector,
)

from services.ml.anomaly.alarm_integration import (
    generate_alarm_from_anomaly,
    batch_generate_alarms,
    AnomalyAlarmMapper,
    anomaly_alarm_mapper,
    configure_alarm_mapping,
    get_alarm_mapping,
)

from services.ml.anomaly.realtime_hook import (
    RealtimeAnomalyHook,
    realtime_hook,
    process_tag_value,
    process_tag_value_async,
    on_anomaly,
    on_anomaly_async,
    create_historian_callback,
    create_opc_callback,
    HistorianAnomalyBridge,
    historian_anomaly_bridge,
    TagValueEvent,
    HookConfig,
)

__all__ = [
    # Types
    'AnomalySeverity',
    'AnomalyCategory',
    'AnomalyType',
    'AnomalyResult',
    'AnomalyConfig',
    'ThresholdConfig',

    # Detection Service
    'AnomalyDetectionService',
    'anomaly_detection_service',
    'detect_anomalies',
    'detect_realtime',
    'get_detection_config',
    'update_detection_config',

    # Detectors
    'SlidingWindow',
    'StatisticalDetector',
    'ThresholdDetector',
    'PatternDetector',

    # Alarm Integration
    'generate_alarm_from_anomaly',
    'batch_generate_alarms',
    'AnomalyAlarmMapper',
    'anomaly_alarm_mapper',
    'configure_alarm_mapping',
    'get_alarm_mapping',

    # Real-time Hook
    'RealtimeAnomalyHook',
    'realtime_hook',
    'process_tag_value',
    'process_tag_value_async',
    'on_anomaly',
    'on_anomaly_async',
    'create_historian_callback',
    'create_opc_callback',
    'HistorianAnomalyBridge',
    'historian_anomaly_bridge',
    'TagValueEvent',
    'HookConfig',
]
