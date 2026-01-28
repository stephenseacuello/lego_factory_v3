"""
LEGO Factory v3 - Anomaly to Alarm Integration
===============================================
Integration layer connecting ML anomaly detection to the ISA-18.2
alarm management system.
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid

from services.ml.anomaly.anomaly_types import (
    AnomalySeverity,
    AnomalyCategory,
    AnomalyResult,
)

logger = logging.getLogger(__name__)


# Mapping from anomaly categories to alarm types
CATEGORY_TO_ALARM_TYPE = {
    AnomalyCategory.SPIKE: 'rate_of_change',
    AnomalyCategory.DRIFT: 'deviation',
    AnomalyCategory.FLATLINE: 'bad_quality',
    AnomalyCategory.OUT_OF_RANGE: 'high',  # Will be refined based on direction
    AnomalyCategory.OSCILLATION: 'rate_of_change',
    AnomalyCategory.NOISE: 'bad_quality',
    AnomalyCategory.RATE_OF_CHANGE: 'rate_of_change',
    AnomalyCategory.PATTERN: 'ml_anomaly',
    AnomalyCategory.CORRELATION: 'deviation',
    AnomalyCategory.MISSING_DATA: 'bad_quality',
}

# Mapping from anomaly severity to ISA-18.2 alarm priority
SEVERITY_TO_PRIORITY = {
    AnomalySeverity.INFO: 4,       # LOW
    AnomalySeverity.LOW: 4,        # LOW
    AnomalySeverity.MEDIUM: 3,     # MEDIUM
    AnomalySeverity.HIGH: 2,       # HIGH
    AnomalySeverity.CRITICAL: 1,   # EMERGENCY
}


def generate_alarm_from_anomaly(
    anomaly: AnomalyResult,
    auto_acknowledge: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Generate an ISA-18.2 compliant alarm from an anomaly detection result.

    Args:
        anomaly: The detected anomaly
        auto_acknowledge: Whether to auto-acknowledge the alarm

    Returns:
        Alarm event dictionary or None if generation failed
    """
    try:
        from services.scada.alarm_management.alarm_service import (
            alarm_processor,
            AlarmEvent,
            AlarmStatus,
            AlarmPriority,
        )

        # Determine alarm type based on anomaly category and direction
        alarm_type = _determine_alarm_type(anomaly)

        # Get priority from severity
        priority = SEVERITY_TO_PRIORITY.get(anomaly.severity, 3)

        # Generate alarm message
        message = _generate_alarm_message(anomaly)

        # Create alarm event
        alarm_event = AlarmEvent(
            instance_id=anomaly.anomaly_id,
            alarm_id=f"ML_ANOMALY_{anomaly.tag_id}_{anomaly.category.value}",
            tag_id=anomaly.tag_id,
            tag_name=anomaly.tag_name,
            alarm_type=alarm_type,
            priority=priority,
            status=AlarmStatus.ACTIVE_UNACKED.value,
            message=message,
            value=anomaly.value,
            limit_value=anomaly.threshold_violated or 0,
            timestamp=anomaly.timestamp,
            consequence=_get_consequence(anomaly),
            corrective_action=anomaly.category.recommended_action,
        )

        # Submit alarm through the alarm processor
        alarm_processor.submit_ml_alarm(alarm_event)

        logger.info(
            f"Generated alarm for anomaly: {anomaly.tag_name} - "
            f"{anomaly.category.value} (Priority {priority})"
        )

        return {
            'alarm_id': alarm_event.alarm_id,
            'instance_id': alarm_event.instance_id,
            'tag_id': anomaly.tag_id,
            'tag_name': anomaly.tag_name,
            'alarm_type': alarm_type,
            'priority': priority,
            'message': message,
            'value': anomaly.value,
            'timestamp': anomaly.timestamp.isoformat(),
            'anomaly_score': anomaly.anomaly_score,
            'anomaly_category': anomaly.category.value,
            'severity': anomaly.severity.name,
        }

    except ImportError:
        logger.warning("Alarm service not available, logging anomaly only")
        _log_anomaly_as_event(anomaly)
        return None

    except Exception as e:
        logger.error(f"Failed to generate alarm from anomaly: {e}")
        return None


def _determine_alarm_type(anomaly: AnomalyResult) -> str:
    """Determine the ISA-18.2 alarm type from anomaly characteristics."""
    base_type = CATEGORY_TO_ALARM_TYPE.get(anomaly.category, 'ml_anomaly')

    # Refine OUT_OF_RANGE based on direction
    if anomaly.category == AnomalyCategory.OUT_OF_RANGE:
        if anomaly.expected_value is not None:
            if anomaly.value > anomaly.expected_value:
                # Check severity for high vs high_high
                if anomaly.severity >= AnomalySeverity.CRITICAL:
                    return 'high_high'
                return 'high'
            else:
                if anomaly.severity >= AnomalySeverity.CRITICAL:
                    return 'low_low'
                return 'low'

    return base_type


def _generate_alarm_message(anomaly: AnomalyResult) -> str:
    """Generate human-readable alarm message from anomaly."""
    if anomaly.message:
        return anomaly.message

    base_msg = f"{anomaly.tag_name} {anomaly.category.value.replace('_', ' ')} anomaly"

    if anomaly.value is not None:
        base_msg += f": value={anomaly.value:.4f}"

    if anomaly.threshold_violated is not None:
        base_msg += f" (threshold={anomaly.threshold_violated:.4f})"

    if anomaly.deviation is not None:
        base_msg += f", deviation={anomaly.deviation:.4f}"

    base_msg += f" [score={anomaly.anomaly_score:.3f}]"

    return base_msg


def _get_consequence(anomaly: AnomalyResult) -> str:
    """Get consequence description based on anomaly type and severity."""
    consequences = {
        AnomalySeverity.CRITICAL: "Immediate production impact possible. Process may be compromised.",
        AnomalySeverity.HIGH: "Production quality at risk. Intervention required.",
        AnomalySeverity.MEDIUM: "Process deviation detected. Monitor closely.",
        AnomalySeverity.LOW: "Minor deviation from normal operation.",
        AnomalySeverity.INFO: "Informational: Pattern differs from baseline.",
    }

    base = consequences.get(anomaly.severity, "Unknown consequence")

    # Add category-specific consequences
    category_consequences = {
        AnomalyCategory.SPIKE: " Sudden value change may indicate sensor or process issue.",
        AnomalyCategory.DRIFT: " Gradual drift suggests calibration or degradation issue.",
        AnomalyCategory.FLATLINE: " Constant value may indicate sensor failure.",
        AnomalyCategory.OUT_OF_RANGE: " Value outside acceptable limits.",
        AnomalyCategory.RATE_OF_CHANGE: " Rapid change may stress equipment.",
        AnomalyCategory.PATTERN: " ML model detected unusual operational pattern.",
    }

    return base + category_consequences.get(anomaly.category, "")


def _log_anomaly_as_event(anomaly: AnomalyResult):
    """Log anomaly as an event when alarm system is unavailable."""
    logger.warning(
        f"ANOMALY_EVENT: {anomaly.tag_name} | "
        f"Category: {anomaly.category.value} | "
        f"Severity: {anomaly.severity.name} | "
        f"Score: {anomaly.anomaly_score:.3f} | "
        f"Value: {anomaly.value} | "
        f"Message: {anomaly.message}"
    )


def batch_generate_alarms(
    anomalies: List[AnomalyResult],
    min_severity: AnomalySeverity = AnomalySeverity.LOW,
    deduplicate: bool = True,
    dedup_window_seconds: float = 60.0
) -> List[Dict[str, Any]]:
    """
    Generate alarms for multiple anomalies with optional deduplication.

    Args:
        anomalies: List of detected anomalies
        min_severity: Minimum severity to generate alarm
        deduplicate: Whether to deduplicate similar alarms
        dedup_window_seconds: Window for deduplication

    Returns:
        List of generated alarm dictionaries
    """
    alarms = []
    seen_keys = {}  # key -> timestamp

    for anomaly in anomalies:
        # Filter by severity
        if anomaly.severity < min_severity:
            continue

        # Deduplication
        if deduplicate:
            key = f"{anomaly.tag_id}:{anomaly.category.value}"
            last_time = seen_keys.get(key)

            if last_time:
                delta = (anomaly.timestamp - last_time).total_seconds()
                if delta < dedup_window_seconds:
                    continue

            seen_keys[key] = anomaly.timestamp

        # Generate alarm
        alarm = generate_alarm_from_anomaly(anomaly)
        if alarm:
            alarms.append(alarm)

    logger.info(f"Generated {len(alarms)} alarms from {len(anomalies)} anomalies")
    return alarms


class AnomalyAlarmMapper:
    """
    Maps anomaly detection results to ISA-18.2 alarm definitions.

    This class maintains mappings between ML anomaly types and
    pre-configured alarm definitions in the system.
    """

    def __init__(self):
        self._mappings: Dict[str, Dict[str, Any]] = {}
        self._default_config = {
            'enabled': True,
            'priority_offset': 0,  # Adjust priority (+/- from anomaly severity)
            'min_score_for_alarm': 0.5,
            'cooldown_seconds': 60.0,
        }

    def register_mapping(
        self,
        tag_id: str,
        category: AnomalyCategory,
        alarm_definition_id: str,
        config: Dict[str, Any] = None
    ):
        """
        Register a mapping from tag+category to alarm definition.

        Args:
            tag_id: The tag identifier
            category: The anomaly category
            alarm_definition_id: The target alarm definition ID
            config: Optional configuration overrides
        """
        key = f"{tag_id}:{category.value}"
        self._mappings[key] = {
            'alarm_definition_id': alarm_definition_id,
            'config': {**self._default_config, **(config or {})},
        }
        logger.debug(f"Registered alarm mapping: {key} -> {alarm_definition_id}")

    def get_alarm_definition(
        self,
        tag_id: str,
        category: AnomalyCategory
    ) -> Optional[str]:
        """Get alarm definition ID for a tag+category combination."""
        key = f"{tag_id}:{category.value}"
        mapping = self._mappings.get(key)
        return mapping['alarm_definition_id'] if mapping else None

    def should_generate_alarm(
        self,
        anomaly: AnomalyResult
    ) -> bool:
        """Determine if an alarm should be generated for an anomaly."""
        key = f"{anomaly.tag_id}:{anomaly.category.value}"
        mapping = self._mappings.get(key)

        if not mapping:
            # No specific mapping, use defaults
            return anomaly.anomaly_score >= 0.5

        config = mapping['config']

        if not config.get('enabled', True):
            return False

        if anomaly.anomaly_score < config.get('min_score_for_alarm', 0.5):
            return False

        return True

    def get_adjusted_priority(
        self,
        anomaly: AnomalyResult
    ) -> int:
        """Get adjusted alarm priority based on mapping config."""
        base_priority = SEVERITY_TO_PRIORITY.get(anomaly.severity, 3)

        key = f"{anomaly.tag_id}:{anomaly.category.value}"
        mapping = self._mappings.get(key)

        if mapping:
            offset = mapping['config'].get('priority_offset', 0)
            base_priority = max(1, min(4, base_priority + offset))

        return base_priority


# Global mapper instance
anomaly_alarm_mapper = AnomalyAlarmMapper()


def configure_alarm_mapping(
    tag_id: str,
    category: AnomalyCategory,
    alarm_definition_id: str,
    **config
):
    """Configure alarm mapping for a tag+category combination."""
    anomaly_alarm_mapper.register_mapping(tag_id, category, alarm_definition_id, config)


def get_alarm_mapping(tag_id: str, category: AnomalyCategory) -> Optional[str]:
    """Get alarm definition ID for a tag+category."""
    return anomaly_alarm_mapper.get_alarm_definition(tag_id, category)
