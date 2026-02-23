"""
LEGO Factory v3 - Predictive Alarm Service
==========================================
Advanced alarm capabilities with dynamic thresholds, trend detection,
and alarm correlation for reduced alert fatigue.
"""

import math
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

from sqlalchemy.orm import Session

from config.database import get_db_session
from services.scada.alarm_management.alarm_service import (
    AlarmProcessor, AlarmEvent, AlarmStatus, AlarmPriority,
    alarm_processor, _emit_alarm_event
)

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Trend direction for sensor values"""
    STABLE = 'stable'
    INCREASING = 'increasing'
    DECREASING = 'decreasing'
    RAPIDLY_INCREASING = 'rapidly_increasing'
    RAPIDLY_DECREASING = 'rapidly_decreasing'


class AlertSeverity(Enum):
    """Severity levels for predictive alerts"""
    INFO = 'info'
    WARNING = 'warning'
    CRITICAL = 'critical'


@dataclass
class RollingStatistics:
    """Rolling statistics for a sensor tag"""
    tag_id: str
    window_size: int = 100
    values: deque = field(default_factory=lambda: deque(maxlen=100))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=100))

    # Computed statistics
    mean: float = 0.0
    std_dev: float = 0.0
    min_value: float = float('inf')
    max_value: float = float('-inf')

    # Rate of change tracking
    rate_of_change: float = 0.0
    trend_direction: TrendDirection = TrendDirection.STABLE

    def add_value(self, value: float, timestamp: datetime):
        """Add a new value and update statistics"""
        self.values.append(value)
        self.timestamps.append(timestamp)
        self._recalculate()

    def _recalculate(self):
        """Recalculate all statistics"""
        if len(self.values) < 2:
            return

        values_list = list(self.values)
        n = len(values_list)

        # Mean
        self.mean = sum(values_list) / n

        # Standard deviation
        variance = sum((x - self.mean) ** 2 for x in values_list) / n
        self.std_dev = math.sqrt(variance) if variance > 0 else 0.0

        # Min/Max
        self.min_value = min(values_list)
        self.max_value = max(values_list)

        # Rate of change (using last 10 values or available)
        recent_count = min(10, n)
        if recent_count >= 2:
            recent_values = values_list[-recent_count:]
            recent_times = list(self.timestamps)[-recent_count:]

            # Linear regression slope
            time_deltas = [(recent_times[i] - recent_times[0]).total_seconds() / 60.0
                          for i in range(recent_count)]

            if time_deltas[-1] > 0:
                # Simple slope calculation
                value_change = recent_values[-1] - recent_values[0]
                time_change = time_deltas[-1]
                self.rate_of_change = value_change / time_change  # Units per minute

                # Determine trend direction
                self._determine_trend()

    def _determine_trend(self):
        """Determine trend direction based on rate of change"""
        if self.std_dev == 0:
            self.trend_direction = TrendDirection.STABLE
            return

        # Normalize rate of change by standard deviation
        normalized_rate = abs(self.rate_of_change) / self.std_dev if self.std_dev > 0 else 0

        if normalized_rate < 0.1:
            self.trend_direction = TrendDirection.STABLE
        elif self.rate_of_change > 0:
            self.trend_direction = (TrendDirection.RAPIDLY_INCREASING
                                   if normalized_rate > 0.5
                                   else TrendDirection.INCREASING)
        else:
            self.trend_direction = (TrendDirection.RAPIDLY_DECREASING
                                   if normalized_rate > 0.5
                                   else TrendDirection.DECREASING)


@dataclass
class DynamicThreshold:
    """Dynamic threshold computed from rolling statistics"""
    tag_id: str
    base_value: float  # Original static threshold
    dynamic_value: float  # Computed dynamic threshold
    confidence: float  # 0-1 confidence in the threshold
    last_updated: datetime = field(default_factory=datetime.utcnow)

    # Threshold components
    statistical_limit: float = 0.0  # Mean + k*sigma
    trend_adjusted_limit: float = 0.0  # Adjusted for trending

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tag_id': self.tag_id,
            'base_value': self.base_value,
            'dynamic_value': self.dynamic_value,
            'confidence': self.confidence,
            'last_updated': self.last_updated.isoformat(),
            'statistical_limit': self.statistical_limit,
            'trend_adjusted_limit': self.trend_adjusted_limit
        }


@dataclass
class TrendAlert:
    """Alert generated from trend analysis"""
    alert_id: str
    tag_id: str
    tag_name: str
    severity: AlertSeverity
    message: str
    trend_direction: TrendDirection
    current_value: float
    predicted_value: float  # Predicted value at threshold crossing time
    time_to_threshold: Optional[float]  # Minutes until threshold crossing
    threshold_value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'tag_id': self.tag_id,
            'tag_name': self.tag_name,
            'severity': self.severity.value,
            'message': self.message,
            'trend_direction': self.trend_direction.value,
            'current_value': self.current_value,
            'predicted_value': self.predicted_value,
            'time_to_threshold': self.time_to_threshold,
            'threshold_value': self.threshold_value,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class CorrelatedAlarmGroup:
    """Group of correlated alarms"""
    group_id: str
    name: str
    root_cause_alarm_id: Optional[str]
    related_alarm_ids: List[str]
    correlation_strength: float  # 0-1
    first_alarm_time: datetime
    suppressed_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'group_id': self.group_id,
            'name': self.name,
            'root_cause_alarm_id': self.root_cause_alarm_id,
            'related_alarm_ids': self.related_alarm_ids,
            'correlation_strength': self.correlation_strength,
            'first_alarm_time': self.first_alarm_time.isoformat(),
            'suppressed_count': self.suppressed_count
        }


class PredictiveAlarmService:
    """
    Advanced alarm service with predictive capabilities.

    Features:
    - Dynamic threshold calculation based on rolling statistics
    - Trend-based alerts (degradation detection before threshold crossing)
    - Alarm correlation to reduce alert fatigue
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize service state"""
        # Rolling statistics per tag
        self._tag_stats: Dict[str, RollingStatistics] = {}

        # Dynamic thresholds
        self._dynamic_thresholds: Dict[str, Dict[str, DynamicThreshold]] = {}  # tag_id -> {alarm_type -> threshold}

        # Active trend alerts
        self._trend_alerts: Dict[str, TrendAlert] = {}  # alert_id -> TrendAlert

        # Alarm correlation
        self._correlation_rules: Dict[str, List[str]] = {}  # tag_id -> related_tag_ids
        self._alarm_groups: Dict[str, CorrelatedAlarmGroup] = {}  # group_id -> group
        self._recent_alarms: deque = deque(maxlen=1000)  # Recent alarm events for correlation

        # Configuration
        self._config = {
            'sigma_multiplier': 3.0,  # Number of standard deviations for dynamic threshold
            'trend_prediction_minutes': 30,  # How far ahead to predict
            'correlation_window_seconds': 60,  # Window for correlating alarms
            'min_samples_for_dynamic': 20,  # Minimum samples before using dynamic thresholds
            'trend_alert_lookahead_minutes': 15,  # Alert when threshold crossing predicted within this time
        }

        logger.info("PredictiveAlarmService initialized")

    def configure(self, config: Dict[str, Any]):
        """Update service configuration"""
        self._config.update(config)
        logger.info(f"PredictiveAlarmService configured: {config}")

    # ==================== Dynamic Threshold Management ====================

    def process_sensor_value(
        self,
        tag_id: str,
        tag_name: str,
        value: float,
        timestamp: datetime = None,
        alarm_thresholds: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Process a sensor value for predictive analysis.

        Args:
            tag_id: Sensor tag identifier
            tag_name: Human-readable tag name
            value: Current sensor value
            timestamp: Value timestamp
            alarm_thresholds: Static alarm thresholds {type: value}
                             e.g., {'high': 100, 'high_high': 120, 'low': 20}

        Returns:
            Dict with dynamic thresholds, trend alerts, and recommendations
        """
        timestamp = timestamp or datetime.utcnow()

        # Update rolling statistics
        if tag_id not in self._tag_stats:
            self._tag_stats[tag_id] = RollingStatistics(tag_id=tag_id)

        stats = self._tag_stats[tag_id]
        stats.add_value(value, timestamp)

        result = {
            'tag_id': tag_id,
            'tag_name': tag_name,
            'current_value': value,
            'statistics': {
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'min': stats.min_value,
                'max': stats.max_value,
                'sample_count': len(stats.values),
                'rate_of_change': stats.rate_of_change,
                'trend': stats.trend_direction.value
            },
            'dynamic_thresholds': {},
            'trend_alerts': [],
            'recommendations': []
        }

        # Calculate dynamic thresholds if we have enough samples
        if alarm_thresholds and len(stats.values) >= self._config['min_samples_for_dynamic']:
            result['dynamic_thresholds'] = self._calculate_dynamic_thresholds(
                tag_id, stats, alarm_thresholds
            )

        # Check for trend-based alerts
        if alarm_thresholds:
            trend_alerts = self._check_trend_alerts(
                tag_id, tag_name, value, stats, alarm_thresholds
            )
            result['trend_alerts'] = [a.to_dict() for a in trend_alerts]

        # Generate recommendations
        result['recommendations'] = self._generate_recommendations(stats, result)

        return result

    def _calculate_dynamic_thresholds(
        self,
        tag_id: str,
        stats: RollingStatistics,
        static_thresholds: Dict[str, float]
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate dynamic thresholds based on rolling statistics"""

        if tag_id not in self._dynamic_thresholds:
            self._dynamic_thresholds[tag_id] = {}

        sigma = self._config['sigma_multiplier']
        results = {}

        for alarm_type, static_value in static_thresholds.items():
            # Calculate statistical limit
            if 'high' in alarm_type.lower():
                statistical_limit = stats.mean + (sigma * stats.std_dev)
                # Trend adjustment: if increasing, be more conservative
                if stats.trend_direction in [TrendDirection.INCREASING, TrendDirection.RAPIDLY_INCREASING]:
                    trend_factor = 0.9  # Lower threshold slightly
                else:
                    trend_factor = 1.0
            else:  # low threshold
                statistical_limit = stats.mean - (sigma * stats.std_dev)
                # Trend adjustment: if decreasing, be more conservative
                if stats.trend_direction in [TrendDirection.DECREASING, TrendDirection.RAPIDLY_DECREASING]:
                    trend_factor = 1.1  # Raise threshold slightly
                else:
                    trend_factor = 1.0

            trend_adjusted = statistical_limit * trend_factor

            # Blend static and dynamic (weighted average)
            # More weight to static if fewer samples
            sample_weight = min(len(stats.values) / 100, 1.0)
            dynamic_value = (static_value * (1 - sample_weight * 0.5) +
                           trend_adjusted * sample_weight * 0.5)

            # Calculate confidence based on sample size and variance stability
            confidence = min(len(stats.values) / self._config['min_samples_for_dynamic'], 1.0)

            threshold = DynamicThreshold(
                tag_id=tag_id,
                base_value=static_value,
                dynamic_value=dynamic_value,
                confidence=confidence,
                statistical_limit=statistical_limit,
                trend_adjusted_limit=trend_adjusted
            )

            self._dynamic_thresholds[tag_id][alarm_type] = threshold
            results[alarm_type] = threshold.to_dict()

        return results

    def get_dynamic_threshold(
        self,
        tag_id: str,
        alarm_type: str
    ) -> Optional[DynamicThreshold]:
        """Get current dynamic threshold for a tag/alarm type"""
        if tag_id in self._dynamic_thresholds:
            return self._dynamic_thresholds[tag_id].get(alarm_type)
        return None

    # ==================== Trend-Based Alerts ====================

    def _check_trend_alerts(
        self,
        tag_id: str,
        tag_name: str,
        current_value: float,
        stats: RollingStatistics,
        thresholds: Dict[str, float]
    ) -> List[TrendAlert]:
        """Check if trends predict threshold crossing"""

        alerts = []

        if stats.trend_direction == TrendDirection.STABLE:
            return alerts

        lookahead = self._config['trend_alert_lookahead_minutes']

        for alarm_type, threshold_value in thresholds.items():
            # Calculate time to threshold crossing
            if stats.rate_of_change == 0:
                continue

            distance_to_threshold = threshold_value - current_value

            # Check if trending toward threshold
            trending_toward = (
                (distance_to_threshold > 0 and stats.rate_of_change > 0) or
                (distance_to_threshold < 0 and stats.rate_of_change < 0)
            )

            if not trending_toward:
                continue

            # Calculate time to crossing (in minutes)
            time_to_crossing = abs(distance_to_threshold / stats.rate_of_change)

            # Only alert if crossing predicted within lookahead window
            if time_to_crossing > lookahead:
                continue

            # Predict value at threshold crossing time
            predicted_value = current_value + (stats.rate_of_change * time_to_crossing)

            # Determine severity based on time to crossing
            if time_to_crossing <= 5:
                severity = AlertSeverity.CRITICAL
            elif time_to_crossing <= 10:
                severity = AlertSeverity.WARNING
            else:
                severity = AlertSeverity.INFO

            # Check if we already have an active alert for this
            alert_key = f"{tag_id}_{alarm_type}_trend"
            if alert_key in self._trend_alerts:
                existing = self._trend_alerts[alert_key]
                # Update if severity increased
                if severity.value <= existing.severity.value:
                    continue

            alert = TrendAlert(
                alert_id=alert_key,
                tag_id=tag_id,
                tag_name=tag_name,
                severity=severity,
                message=(f"{tag_name} trending toward {alarm_type} threshold. "
                        f"Predicted crossing in {time_to_crossing:.1f} minutes."),
                trend_direction=stats.trend_direction,
                current_value=current_value,
                predicted_value=predicted_value,
                time_to_threshold=time_to_crossing,
                threshold_value=threshold_value
            )

            self._trend_alerts[alert_key] = alert
            alerts.append(alert)

            # Emit WebSocket event
            _emit_alarm_event('trend_alert', alert.to_dict())

            logger.warning(
                f"Trend alert: {tag_name} approaching {alarm_type} "
                f"(ETA: {time_to_crossing:.1f} min)"
            )

        return alerts

    def get_active_trend_alerts(
        self,
        tag_id: str = None,
        min_severity: AlertSeverity = None
    ) -> List[TrendAlert]:
        """Get active trend alerts with optional filtering"""
        alerts = list(self._trend_alerts.values())

        if tag_id:
            alerts = [a for a in alerts if a.tag_id == tag_id]

        if min_severity:
            severity_order = [AlertSeverity.CRITICAL, AlertSeverity.WARNING, AlertSeverity.INFO]
            min_idx = severity_order.index(min_severity)
            alerts = [a for a in alerts if severity_order.index(a.severity) <= min_idx]

        return sorted(alerts, key=lambda a: (
            [AlertSeverity.CRITICAL, AlertSeverity.WARNING, AlertSeverity.INFO].index(a.severity),
            a.time_to_threshold or float('inf')
        ))

    def clear_trend_alert(self, alert_id: str):
        """Clear a trend alert (usually when condition improves)"""
        if alert_id in self._trend_alerts:
            del self._trend_alerts[alert_id]
            logger.info(f"Trend alert cleared: {alert_id}")

    # ==================== Alarm Correlation ====================

    def register_correlation_rule(
        self,
        primary_tag_id: str,
        related_tag_ids: List[str],
        name: str = None
    ):
        """
        Register a correlation rule between tags.

        When an alarm fires on primary_tag_id, alarms on related_tag_ids
        within the correlation window will be grouped.
        """
        self._correlation_rules[primary_tag_id] = related_tag_ids
        logger.info(f"Registered correlation rule: {primary_tag_id} -> {related_tag_ids}")

    def process_alarm_for_correlation(
        self,
        alarm_event: AlarmEvent
    ) -> Optional[CorrelatedAlarmGroup]:
        """
        Process an alarm event for correlation with recent alarms.

        Returns a CorrelatedAlarmGroup if this alarm is part of a group.
        """
        now = datetime.utcnow()
        window = timedelta(seconds=self._config['correlation_window_seconds'])

        # Add to recent alarms
        self._recent_alarms.append({
            'alarm_id': alarm_event.alarm_id,
            'tag_id': alarm_event.tag_id,
            'timestamp': alarm_event.timestamp,
            'priority': alarm_event.priority
        })

        # Find recent alarms within correlation window
        recent = [
            a for a in self._recent_alarms
            if now - a['timestamp'] <= window and a['alarm_id'] != alarm_event.alarm_id
        ]

        if not recent:
            return None

        # Check if this tag has correlation rules
        related_tags = self._correlation_rules.get(alarm_event.tag_id, [])

        # Also check if this alarm is related to another primary
        for primary_tag, related in self._correlation_rules.items():
            if alarm_event.tag_id in related:
                related_tags.append(primary_tag)

        # Find correlated alarms
        correlated = [
            a for a in recent
            if a['tag_id'] in related_tags or alarm_event.tag_id in self._correlation_rules.get(a['tag_id'], [])
        ]

        if not correlated:
            return None

        # Create or update correlation group
        group_id = f"group_{alarm_event.tag_id}_{int(now.timestamp())}"

        # Determine root cause (highest priority alarm that fired first)
        all_alarms = correlated + [{'alarm_id': alarm_event.alarm_id,
                                     'tag_id': alarm_event.tag_id,
                                     'timestamp': alarm_event.timestamp,
                                     'priority': alarm_event.priority}]

        root_cause = min(all_alarms, key=lambda a: (a['priority'], a['timestamp']))

        group = CorrelatedAlarmGroup(
            group_id=group_id,
            name=f"Correlated alarms from {alarm_event.tag_id}",
            root_cause_alarm_id=root_cause['alarm_id'],
            related_alarm_ids=[a['alarm_id'] for a in all_alarms if a['alarm_id'] != root_cause['alarm_id']],
            correlation_strength=len(correlated) / (len(related_tags) + 1) if related_tags else 1.0,
            first_alarm_time=min(a['timestamp'] for a in all_alarms),
            suppressed_count=len(correlated)
        )

        self._alarm_groups[group_id] = group

        # Emit correlation event
        _emit_alarm_event('alarm_correlation', {
            'group': group.to_dict(),
            'message': f"Grouped {len(all_alarms)} related alarms. Root cause: {root_cause['alarm_id']}"
        })

        logger.info(
            f"Alarm correlation detected: {len(all_alarms)} alarms grouped, "
            f"root cause: {root_cause['alarm_id']}"
        )

        return group

    def get_alarm_groups(self, active_only: bool = True) -> List[CorrelatedAlarmGroup]:
        """Get all alarm correlation groups"""
        groups = list(self._alarm_groups.values())

        if active_only:
            # Filter to groups from last hour
            cutoff = datetime.utcnow() - timedelta(hours=1)
            groups = [g for g in groups if g.first_alarm_time > cutoff]

        return sorted(groups, key=lambda g: g.first_alarm_time, reverse=True)

    # ==================== Recommendations ====================

    def _generate_recommendations(
        self,
        stats: RollingStatistics,
        analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []

        # Trend-based recommendations
        if stats.trend_direction == TrendDirection.RAPIDLY_INCREASING:
            recommendations.append(
                "Rapidly increasing trend detected. Consider investigating cause."
            )
        elif stats.trend_direction == TrendDirection.RAPIDLY_DECREASING:
            recommendations.append(
                "Rapidly decreasing trend detected. Consider investigating cause."
            )

        # Variance recommendations
        if stats.std_dev > stats.mean * 0.2 and len(stats.values) >= 50:
            recommendations.append(
                f"High variability detected (CV={stats.std_dev/stats.mean:.1%}). "
                "Process may be unstable."
            )

        # Trend alert recommendations
        critical_alerts = [
            a for a in analysis.get('trend_alerts', [])
            if a.get('severity') == 'critical'
        ]
        if critical_alerts:
            recommendations.append(
                f"URGENT: {len(critical_alerts)} critical trend alert(s). "
                "Immediate attention required."
            )

        return recommendations

    # ==================== Statistics Access ====================

    def get_tag_statistics(self, tag_id: str) -> Optional[Dict[str, Any]]:
        """Get current rolling statistics for a tag"""
        if tag_id not in self._tag_stats:
            return None

        stats = self._tag_stats[tag_id]
        return {
            'tag_id': tag_id,
            'sample_count': len(stats.values),
            'mean': stats.mean,
            'std_dev': stats.std_dev,
            'min': stats.min_value,
            'max': stats.max_value,
            'rate_of_change': stats.rate_of_change,
            'trend': stats.trend_direction.value,
            'recent_values': list(stats.values)[-10:] if stats.values else []
        }

    def get_all_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tracked tags"""
        return {
            tag_id: self.get_tag_statistics(tag_id)
            for tag_id in self._tag_stats
        }

    def reset_tag_statistics(self, tag_id: str):
        """Reset statistics for a specific tag"""
        if tag_id in self._tag_stats:
            del self._tag_stats[tag_id]
        if tag_id in self._dynamic_thresholds:
            del self._dynamic_thresholds[tag_id]
        logger.info(f"Reset statistics for tag: {tag_id}")


# Global service instance
predictive_alarm_service = PredictiveAlarmService()


def get_predictive_alarm_service() -> PredictiveAlarmService:
    """Get the predictive alarm service singleton"""
    return predictive_alarm_service
