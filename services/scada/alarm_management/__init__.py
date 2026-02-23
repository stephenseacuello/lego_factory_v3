"""
LEGO Factory v3 - Alarm Management Package
==========================================
ISA-18.2 compliant alarm management with predictive capabilities.
"""

from services.scada.alarm_management.alarm_service import (
    AlarmProcessor,
    AlarmService,
    AlarmEvent,
    AlarmSummary,
    AlarmPriority,
    AlarmStatus,
    AlarmEventType,
    AlarmType,
    alarm_processor,
    get_alarm_service,
    initialize_alarm_processor,
    process_tag_value,
    start_alarm_processor,
    stop_alarm_processor,
)

from services.scada.alarm_management.predictive_alarm_service import (
    PredictiveAlarmService,
    TrendDirection,
    AlertSeverity,
    RollingStatistics,
    DynamicThreshold,
    TrendAlert,
    CorrelatedAlarmGroup,
    predictive_alarm_service,
    get_predictive_alarm_service,
)

from services.scada.alarm_management.anomaly_detection_service import (
    AnomalyDetectionService,
    AnomalyType,
    AnomalyDetection,
    SensorProfile,
    anomaly_detection_service,
    get_anomaly_detection_service,
)

__all__ = [
    # Core alarm service
    'AlarmProcessor',
    'AlarmService',
    'AlarmEvent',
    'AlarmSummary',
    'AlarmPriority',
    'AlarmStatus',
    'AlarmEventType',
    'AlarmType',
    'alarm_processor',
    'get_alarm_service',
    'initialize_alarm_processor',
    'process_tag_value',
    'start_alarm_processor',
    'stop_alarm_processor',
    # Predictive alarm service
    'PredictiveAlarmService',
    'TrendDirection',
    'AlertSeverity',
    'RollingStatistics',
    'DynamicThreshold',
    'TrendAlert',
    'CorrelatedAlarmGroup',
    'predictive_alarm_service',
    'get_predictive_alarm_service',
    # Anomaly detection service
    'AnomalyDetectionService',
    'AnomalyType',
    'AnomalyDetection',
    'SensorProfile',
    'anomaly_detection_service',
    'get_anomaly_detection_service',
]
