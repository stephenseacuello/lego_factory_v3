"""
Security Anomaly Detection Service

Provides behavioral anomaly detection for Zero-Trust architecture.
Detects unusual access patterns, geographic anomalies, time-based
anomalies, and behavioral deviations.

Features:
- Statistical baseline modeling
- Time-series anomaly detection
- Geographic anomaly detection
- Session behavior analysis
- Risk scoring

Reference: NIST SP 800-207 Zero Trust, MITRE ATT&CK

Author: LEGO MCP Security Engineering
"""

import logging
import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta, timezone
from enum import Enum
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of security anomalies."""
    GEOGRAPHIC = "geographic"
    TEMPORAL = "temporal"
    BEHAVIORAL = "behavioral"
    VOLUMETRIC = "volumetric"
    CREDENTIAL = "credential"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"


class RiskLevel(Enum):
    """Risk levels for anomalies."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AccessEvent:
    """Access event for analysis."""
    user_id: str
    resource: str
    action: str
    timestamp: datetime
    source_ip: str
    user_agent: str = ""
    geo_location: Optional[str] = None
    session_id: str = ""
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyAlert:
    """Security anomaly alert."""
    alert_id: str
    anomaly_type: AnomalyType
    risk_level: RiskLevel
    user_id: str
    description: str
    evidence: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "anomaly_type": self.anomaly_type.value,
            "risk_level": self.risk_level.name,
            "user_id": self.user_id,
            "description": self.description,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat(),
            "recommendations": self.recommendations,
        }


@dataclass
class UserBaseline:
    """Behavioral baseline for a user."""
    user_id: str
    typical_hours: Set[int] = field(default_factory=set)  # 0-23
    typical_days: Set[int] = field(default_factory=set)   # 0-6 (Mon-Sun)
    typical_locations: Set[str] = field(default_factory=set)
    typical_resources: Set[str] = field(default_factory=set)
    typical_actions: Set[str] = field(default_factory=set)
    avg_requests_per_hour: float = 0.0
    std_requests_per_hour: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_count: int = 0


class StatisticalAnalyzer:
    """Statistical analysis for anomaly detection."""

    @staticmethod
    def z_score(value: float, mean: float, std: float) -> float:
        """Calculate z-score."""
        if std == 0:
            return 0.0
        return (value - mean) / std

    @staticmethod
    def is_outlier(value: float, mean: float, std: float, threshold: float = 3.0) -> bool:
        """Check if value is statistical outlier."""
        z = StatisticalAnalyzer.z_score(value, mean, std)
        return abs(z) > threshold

    @staticmethod
    def entropy(values: List[Any]) -> float:
        """Calculate Shannon entropy of values."""
        if not values:
            return 0.0

        freq = defaultdict(int)
        for v in values:
            freq[v] += 1

        total = len(values)
        entropy = 0.0
        for count in freq.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy


class GeographicAnalyzer:
    """Geographic anomaly detection."""

    # Approximate travel speeds (km/h)
    MAX_TRAVEL_SPEED = 900  # Airplane speed

    # Known geographic coordinates (simplified)
    LOCATION_COORDS = {
        "US-NY": (40.7128, -74.0060),
        "US-CA": (34.0522, -118.2437),
        "US-TX": (29.7604, -95.3698),
        "EU-DE": (52.5200, 13.4050),
        "EU-UK": (51.5074, -0.1278),
        "APAC-JP": (35.6762, 139.6503),
        "APAC-SG": (1.3521, 103.8198),
    }

    @staticmethod
    def haversine_distance(loc1: Tuple[float, float], loc2: Tuple[float, float]) -> float:
        """Calculate distance between two coordinates in km."""
        lat1, lon1 = math.radians(loc1[0]), math.radians(loc1[1])
        lat2, lon2 = math.radians(loc2[0]), math.radians(loc2[1])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        return 6371 * c  # Earth radius in km

    @classmethod
    def is_impossible_travel(
        cls,
        loc1: str,
        time1: datetime,
        loc2: str,
        time2: datetime,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Detect impossible travel scenarios."""
        coords1 = cls.LOCATION_COORDS.get(loc1)
        coords2 = cls.LOCATION_COORDS.get(loc2)

        if not coords1 or not coords2:
            return False, {}

        distance = cls.haversine_distance(coords1, coords2)
        time_diff = abs((time2 - time1).total_seconds()) / 3600  # hours

        if time_diff == 0:
            return True, {
                "distance_km": distance,
                "time_hours": time_diff,
                "required_speed": float('inf'),
            }

        required_speed = distance / time_diff

        is_impossible = required_speed > cls.MAX_TRAVEL_SPEED

        return is_impossible, {
            "distance_km": distance,
            "time_hours": time_diff,
            "required_speed": required_speed,
            "max_speed": cls.MAX_TRAVEL_SPEED,
        }


class TemporalAnalyzer:
    """Time-based anomaly detection."""

    @staticmethod
    def is_unusual_hour(hour: int, typical_hours: Set[int]) -> bool:
        """Check if hour is unusual for user."""
        if not typical_hours:
            return False
        return hour not in typical_hours

    @staticmethod
    def is_unusual_day(day: int, typical_days: Set[int]) -> bool:
        """Check if day is unusual for user."""
        if not typical_days:
            return False
        return day not in typical_days

    @staticmethod
    def is_burst_activity(
        timestamps: List[datetime],
        window_minutes: int = 5,
        threshold: int = 50,
    ) -> Tuple[bool, int]:
        """Detect burst of activity in time window."""
        if len(timestamps) < threshold:
            return False, len(timestamps)

        # Sort and check sliding window
        sorted_ts = sorted(timestamps)
        window = timedelta(minutes=window_minutes)

        max_count = 0
        for i, ts in enumerate(sorted_ts):
            count = sum(1 for t in sorted_ts[i:] if t - ts <= window)
            max_count = max(max_count, count)

        return max_count >= threshold, max_count


class BehaviorAnalyzer:
    """Behavioral anomaly detection."""

    @staticmethod
    def unusual_resource_access(
        resource: str,
        typical_resources: Set[str],
        sensitive_resources: Optional[Set[str]] = None,
    ) -> Tuple[bool, str]:
        """Check for unusual resource access."""
        sensitive = sensitive_resources or {
            "admin", "config", "secrets", "keys", "credentials",
            "database", "backup", "audit", "security",
        }

        # Check if accessing new sensitive resource
        if resource not in typical_resources:
            for s in sensitive:
                if s in resource.lower():
                    return True, f"First access to sensitive resource containing '{s}'"

        return False, ""

    @staticmethod
    def privilege_escalation_pattern(
        actions: List[str],
        window_size: int = 10,
    ) -> Tuple[bool, List[str]]:
        """Detect privilege escalation patterns."""
        escalation_sequence = [
            "read", "write", "execute", "admin", "root", "sudo",
        ]

        recent_actions = actions[-window_size:]
        escalation_detected = []

        for i, action in enumerate(recent_actions[:-1]):
            current_level = -1
            next_level = -1

            for j, esc in enumerate(escalation_sequence):
                if esc in action.lower():
                    current_level = j
                if esc in recent_actions[i+1].lower():
                    next_level = j

            if current_level >= 0 and next_level > current_level:
                escalation_detected.append(
                    f"{action} -> {recent_actions[i+1]}"
                )

        return len(escalation_detected) >= 2, escalation_detected


class SecurityAnomalyDetector:
    """
    Security Anomaly Detection Service.

    Provides comprehensive anomaly detection for Zero-Trust
    security architecture.

    Usage:
        detector = SecurityAnomalyDetector()

        # Record access event
        event = AccessEvent(
            user_id="user123",
            resource="/api/config",
            action="read",
            timestamp=datetime.now(timezone.utc),
            source_ip="192.168.1.100",
            geo_location="US-NY",
        )

        # Check for anomalies
        alerts = detector.analyze_event(event)

        # Get user risk score
        risk = detector.get_user_risk_score("user123")
    """

    def __init__(
        self,
        baseline_period_days: int = 30,
        anomaly_threshold: float = 0.7,
    ):
        self.baseline_period = timedelta(days=baseline_period_days)
        self.anomaly_threshold = anomaly_threshold

        self.user_baselines: Dict[str, UserBaseline] = {}
        self.user_events: Dict[str, List[AccessEvent]] = defaultdict(list)
        self.alerts: List[AnomalyAlert] = []

        self.geo_analyzer = GeographicAnalyzer()
        self.temporal_analyzer = TemporalAnalyzer()
        self.behavior_analyzer = BehaviorAnalyzer()
        self.stats_analyzer = StatisticalAnalyzer()

        logger.info("SecurityAnomalyDetector initialized")

    def record_event(self, event: AccessEvent) -> None:
        """Record access event and update baseline."""
        self.user_events[event.user_id].append(event)
        self._update_baseline(event.user_id, event)

    def analyze_event(self, event: AccessEvent) -> List[AnomalyAlert]:
        """
        Analyze event for anomalies.

        Returns list of anomaly alerts.
        """
        alerts = []

        # Get or create baseline
        baseline = self.user_baselines.get(event.user_id)
        if not baseline:
            baseline = UserBaseline(user_id=event.user_id)
            self.user_baselines[event.user_id] = baseline

        # Record event
        self.record_event(event)

        # Skip analysis if insufficient baseline data
        if baseline.event_count < 10:
            return alerts

        # Geographic anomaly detection
        geo_alert = self._check_geographic_anomaly(event, baseline)
        if geo_alert:
            alerts.append(geo_alert)

        # Temporal anomaly detection
        temporal_alert = self._check_temporal_anomaly(event, baseline)
        if temporal_alert:
            alerts.append(temporal_alert)

        # Behavioral anomaly detection
        behavior_alerts = self._check_behavioral_anomaly(event, baseline)
        alerts.extend(behavior_alerts)

        # Volumetric anomaly detection
        volume_alert = self._check_volumetric_anomaly(event, baseline)
        if volume_alert:
            alerts.append(volume_alert)

        # Store alerts
        self.alerts.extend(alerts)

        return alerts

    def _check_geographic_anomaly(
        self,
        event: AccessEvent,
        baseline: UserBaseline,
    ) -> Optional[AnomalyAlert]:
        """Check for geographic anomalies."""
        if not event.geo_location:
            return None

        # Check impossible travel
        recent_events = self.user_events[event.user_id][-10:]
        for prev_event in reversed(recent_events[:-1]):
            if prev_event.geo_location and prev_event.geo_location != event.geo_location:
                is_impossible, details = GeographicAnalyzer.is_impossible_travel(
                    prev_event.geo_location,
                    prev_event.timestamp,
                    event.geo_location,
                    event.timestamp,
                )

                if is_impossible:
                    return AnomalyAlert(
                        alert_id=hashlib.md5(
                            f"{event.user_id}-geo-{event.timestamp}".encode()
                        ).hexdigest()[:16],
                        anomaly_type=AnomalyType.GEOGRAPHIC,
                        risk_level=RiskLevel.HIGH,
                        user_id=event.user_id,
                        description="Impossible travel detected",
                        evidence={
                            "from_location": prev_event.geo_location,
                            "to_location": event.geo_location,
                            **details,
                        },
                        recommendations=[
                            "Verify user identity with MFA",
                            "Check for credential compromise",
                            "Review recent account activity",
                        ],
                    )
                break

        # Check new location
        if event.geo_location not in baseline.typical_locations:
            return AnomalyAlert(
                alert_id=hashlib.md5(
                    f"{event.user_id}-newloc-{event.timestamp}".encode()
                ).hexdigest()[:16],
                anomaly_type=AnomalyType.GEOGRAPHIC,
                risk_level=RiskLevel.MEDIUM,
                user_id=event.user_id,
                description="Access from new geographic location",
                evidence={
                    "new_location": event.geo_location,
                    "typical_locations": list(baseline.typical_locations),
                },
                recommendations=[
                    "Confirm user is traveling",
                    "Enable location-based MFA",
                ],
            )

        return None

    def _check_temporal_anomaly(
        self,
        event: AccessEvent,
        baseline: UserBaseline,
    ) -> Optional[AnomalyAlert]:
        """Check for temporal anomalies."""
        hour = event.timestamp.hour
        day = event.timestamp.weekday()

        unusual_hour = TemporalAnalyzer.is_unusual_hour(hour, baseline.typical_hours)
        unusual_day = TemporalAnalyzer.is_unusual_day(day, baseline.typical_days)

        if unusual_hour and unusual_day:
            return AnomalyAlert(
                alert_id=hashlib.md5(
                    f"{event.user_id}-time-{event.timestamp}".encode()
                ).hexdigest()[:16],
                anomaly_type=AnomalyType.TEMPORAL,
                risk_level=RiskLevel.MEDIUM,
                user_id=event.user_id,
                description="Access at unusual time",
                evidence={
                    "access_hour": hour,
                    "access_day": day,
                    "typical_hours": list(baseline.typical_hours),
                    "typical_days": list(baseline.typical_days),
                },
                recommendations=[
                    "Verify user activity is legitimate",
                    "Consider time-based access restrictions",
                ],
            )

        return None

    def _check_behavioral_anomaly(
        self,
        event: AccessEvent,
        baseline: UserBaseline,
    ) -> List[AnomalyAlert]:
        """Check for behavioral anomalies."""
        alerts = []

        # Unusual resource access
        is_unusual, reason = BehaviorAnalyzer.unusual_resource_access(
            event.resource,
            baseline.typical_resources,
        )

        if is_unusual:
            alerts.append(AnomalyAlert(
                alert_id=hashlib.md5(
                    f"{event.user_id}-resource-{event.timestamp}".encode()
                ).hexdigest()[:16],
                anomaly_type=AnomalyType.BEHAVIORAL,
                risk_level=RiskLevel.HIGH,
                user_id=event.user_id,
                description=reason,
                evidence={
                    "resource": event.resource,
                    "typical_resources": list(baseline.typical_resources)[:10],
                },
                recommendations=[
                    "Review access need for this resource",
                    "Apply principle of least privilege",
                ],
            ))

        # Privilege escalation pattern
        recent_actions = [e.action for e in self.user_events[event.user_id][-20:]]
        is_escalation, patterns = BehaviorAnalyzer.privilege_escalation_pattern(
            recent_actions
        )

        if is_escalation:
            alerts.append(AnomalyAlert(
                alert_id=hashlib.md5(
                    f"{event.user_id}-priv-{event.timestamp}".encode()
                ).hexdigest()[:16],
                anomaly_type=AnomalyType.PRIVILEGE_ESCALATION,
                risk_level=RiskLevel.CRITICAL,
                user_id=event.user_id,
                description="Potential privilege escalation detected",
                evidence={
                    "escalation_patterns": patterns,
                    "recent_actions": recent_actions[-10:],
                },
                recommendations=[
                    "Immediately review user permissions",
                    "Check for compromised credentials",
                    "Enable enhanced monitoring",
                ],
            ))

        return alerts

    def _check_volumetric_anomaly(
        self,
        event: AccessEvent,
        baseline: UserBaseline,
    ) -> Optional[AnomalyAlert]:
        """Check for volumetric anomalies."""
        # Get events in last hour
        one_hour_ago = event.timestamp - timedelta(hours=1)
        recent_events = [
            e for e in self.user_events[event.user_id]
            if e.timestamp >= one_hour_ago
        ]

        current_rate = len(recent_events)

        # Check for statistical outlier
        if baseline.std_requests_per_hour > 0:
            is_outlier = StatisticalAnalyzer.is_outlier(
                current_rate,
                baseline.avg_requests_per_hour,
                baseline.std_requests_per_hour,
                threshold=3.0,
            )

            if is_outlier and current_rate > baseline.avg_requests_per_hour:
                return AnomalyAlert(
                    alert_id=hashlib.md5(
                        f"{event.user_id}-volume-{event.timestamp}".encode()
                    ).hexdigest()[:16],
                    anomaly_type=AnomalyType.VOLUMETRIC,
                    risk_level=RiskLevel.MEDIUM,
                    user_id=event.user_id,
                    description="Unusual request volume detected",
                    evidence={
                        "current_rate": current_rate,
                        "avg_rate": baseline.avg_requests_per_hour,
                        "std_rate": baseline.std_requests_per_hour,
                        "z_score": StatisticalAnalyzer.z_score(
                            current_rate,
                            baseline.avg_requests_per_hour,
                            baseline.std_requests_per_hour,
                        ),
                    },
                    recommendations=[
                        "Monitor for potential data exfiltration",
                        "Check for automated/scripted access",
                    ],
                )

        # Check for burst
        timestamps = [e.timestamp for e in recent_events]
        is_burst, burst_count = TemporalAnalyzer.is_burst_activity(
            timestamps, window_minutes=5, threshold=50
        )

        if is_burst:
            return AnomalyAlert(
                alert_id=hashlib.md5(
                    f"{event.user_id}-burst-{event.timestamp}".encode()
                ).hexdigest()[:16],
                anomaly_type=AnomalyType.VOLUMETRIC,
                risk_level=RiskLevel.HIGH,
                user_id=event.user_id,
                description="Burst activity detected",
                evidence={
                    "burst_count": burst_count,
                    "window_minutes": 5,
                },
                recommendations=[
                    "Check for automated attacks",
                    "Consider rate limiting",
                    "Review API usage patterns",
                ],
            )

        return None

    def _update_baseline(self, user_id: str, event: AccessEvent) -> None:
        """Update user baseline with new event."""
        if user_id not in self.user_baselines:
            self.user_baselines[user_id] = UserBaseline(user_id=user_id)

        baseline = self.user_baselines[user_id]

        # Update typical patterns
        baseline.typical_hours.add(event.timestamp.hour)
        baseline.typical_days.add(event.timestamp.weekday())

        if event.geo_location:
            baseline.typical_locations.add(event.geo_location)

        baseline.typical_resources.add(event.resource)
        baseline.typical_actions.add(event.action)

        # Update request rate statistics
        baseline.event_count += 1

        # Recalculate hourly rate
        events = self.user_events[user_id]
        if len(events) >= 2:
            time_span = (events[-1].timestamp - events[0].timestamp).total_seconds() / 3600
            if time_span > 0:
                hourly_rate = len(events) / time_span
                # Running average
                baseline.avg_requests_per_hour = (
                    baseline.avg_requests_per_hour * 0.9 + hourly_rate * 0.1
                )
                # Running std
                if baseline.event_count > 10:
                    baseline.std_requests_per_hour = abs(
                        hourly_rate - baseline.avg_requests_per_hour
                    ) * 0.1 + baseline.std_requests_per_hour * 0.9

        baseline.last_updated = datetime.now(timezone.utc)

    def get_user_risk_score(self, user_id: str) -> Dict[str, Any]:
        """Calculate overall risk score for user."""
        recent_alerts = [
            a for a in self.alerts
            if a.user_id == user_id
            and a.timestamp > datetime.now(timezone.utc) - timedelta(hours=24)
        ]

        if not recent_alerts:
            return {
                "user_id": user_id,
                "risk_score": 0.0,
                "risk_level": "LOW",
                "alert_count": 0,
            }

        # Calculate weighted score
        weights = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 3,
            RiskLevel.HIGH: 7,
            RiskLevel.CRITICAL: 10,
        }

        total_score = sum(weights[a.risk_level] for a in recent_alerts)
        max_score = len(recent_alerts) * 10

        risk_score = total_score / max_score if max_score > 0 else 0

        if risk_score >= 0.7:
            risk_level = "CRITICAL"
        elif risk_score >= 0.5:
            risk_level = "HIGH"
        elif risk_score >= 0.3:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "user_id": user_id,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "alert_count": len(recent_alerts),
            "alerts": [a.to_dict() for a in recent_alerts[:5]],
        }

    def get_recent_alerts(
        self,
        hours: int = 24,
        min_risk_level: RiskLevel = RiskLevel.LOW,
    ) -> List[AnomalyAlert]:
        """Get recent alerts above minimum risk level."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        return [
            a for a in self.alerts
            if a.timestamp >= cutoff
            and a.risk_level.value >= min_risk_level.value
        ]


# Factory function
def create_anomaly_detector(
    baseline_days: int = 30,
) -> SecurityAnomalyDetector:
    """Create configured anomaly detector."""
    return SecurityAnomalyDetector(baseline_period_days=baseline_days)


__all__ = [
    "SecurityAnomalyDetector",
    "AccessEvent",
    "AnomalyAlert",
    "AnomalyType",
    "RiskLevel",
    "UserBaseline",
    "GeographicAnalyzer",
    "TemporalAnalyzer",
    "BehaviorAnalyzer",
    "StatisticalAnalyzer",
    "create_anomaly_detector",
]
