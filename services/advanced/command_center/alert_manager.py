"""
Unified Alert Management Service
================================

Centralized alert handling with:
- Multi-source alert ingestion
- Severity classification
- Escalation workflows
- Acknowledgment tracking
- Alert correlation

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import threading
import uuid

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    CRITICAL = "critical"    # Immediate action required
    HIGH = "high"            # Action required soon
    MEDIUM = "medium"        # Needs attention
    LOW = "low"              # Informational
    INFO = "info"            # FYI only


class AlertStatus(Enum):
    """Alert lifecycle status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    EXPIRED = "expired"


class AlertSource(Enum):
    """Sources of alerts"""
    EQUIPMENT = "equipment"
    QUALITY = "quality"
    SAFETY = "safety"
    SCHEDULING = "scheduling"
    INVENTORY = "inventory"
    AI = "ai"
    SECURITY = "security"
    SYSTEM = "system"
    MAINTENANCE = "maintenance"


@dataclass
class Alert:
    """Alert record"""
    id: str
    title: str
    message: str
    severity: AlertSeverity
    source: AlertSource
    status: AlertStatus
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_by: Optional[str] = None
    expires_at: Optional[datetime] = None
    correlation_id: Optional[str] = None
    entity_type: str = ""
    entity_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    escalation_level: int = 0
    notification_sent: bool = False
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "source": self.source.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged_by": self.acknowledged_by,
            "resolved_by": self.resolved_by,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "correlation_id": self.correlation_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "details": self.details,
            "actions": self.actions,
            "escalation_level": self.escalation_level,
            "notification_sent": self.notification_sent,
            "tags": self.tags,
            "duration_seconds": self.duration_seconds
        }

    @property
    def duration_seconds(self) -> float:
        """Calculate alert duration"""
        end_time = self.resolved_at or datetime.now()
        return (end_time - self.created_at).total_seconds()


@dataclass
class AlertSummary:
    """Summary of alert statistics"""
    total_active: int
    by_severity: Dict[str, int]
    by_source: Dict[str, int]
    by_status: Dict[str, int]
    avg_resolution_time: float  # seconds
    oldest_unresolved: Optional[datetime]
    recent_alerts: List[Alert]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_active": self.total_active,
            "by_severity": self.by_severity,
            "by_source": self.by_source,
            "by_status": self.by_status,
            "avg_resolution_time": self.avg_resolution_time,
            "oldest_unresolved": self.oldest_unresolved.isoformat() if self.oldest_unresolved else None,
            "recent_alerts": [a.to_dict() for a in self.recent_alerts]
        }


class AlertManager:
    """
    Unified alert management system.

    Handles alert lifecycle from creation to resolution,
    including escalation and correlation.
    """

    # Escalation time thresholds (seconds)
    ESCALATION_THRESHOLDS = {
        AlertSeverity.CRITICAL: [300, 600, 900],     # 5, 10, 15 min
        AlertSeverity.HIGH: [900, 1800, 3600],       # 15, 30, 60 min
        AlertSeverity.MEDIUM: [3600, 7200, 14400],   # 1, 2, 4 hours
        AlertSeverity.LOW: [86400, 172800, 259200],  # 1, 2, 3 days
        AlertSeverity.INFO: []                        # No escalation
    }

    def __init__(self, escalation_check_interval: float = 60.0):
        """
        Initialize alert manager.

        Args:
            escalation_check_interval: Seconds between escalation checks
        """
        self._alerts: Dict[str, Alert] = {}
        self._resolved_alerts: List[Alert] = []
        self._escalation_interval = escalation_check_interval
        self._running = False
        self._lock = threading.RLock()
        self._callbacks: Dict[str, List[Callable[[Alert], None]]] = {
            "created": [],
            "updated": [],
            "resolved": [],
            "escalated": []
        }
        self._suppression_rules: List[Dict[str, Any]] = []
        self._correlation_window = 300  # 5 minute correlation window
        self._max_resolved_history = 1000

    def create_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        source: AlertSource,
        entity_type: str = "",
        entity_id: str = "",
        details: Dict[str, Any] = None,
        actions: List[Dict[str, Any]] = None,
        tags: List[str] = None,
        expires_in_seconds: int = None
    ) -> Alert:
        """
        Create a new alert.

        Args:
            title: Alert title
            message: Alert message
            severity: Severity level
            source: Alert source
            entity_type: Type of entity (machine, order, etc)
            entity_id: ID of the entity
            details: Additional context
            actions: Suggested actions
            tags: Alert tags
            expires_in_seconds: Auto-expire after this many seconds

        Returns:
            Created Alert object
        """
        # Check suppression rules
        if self._is_suppressed(source, entity_type, entity_id, tags):
            logger.debug(f"Alert suppressed: {title}")
            return None

        # Check for correlation with existing alerts
        correlation_id = self._find_correlation(source, entity_type, entity_id)

        now = datetime.now()
        alert = Alert(
            id=str(uuid.uuid4()),
            title=title,
            message=message,
            severity=severity,
            source=source,
            status=AlertStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            actions=actions or [],
            tags=tags or [],
            correlation_id=correlation_id,
            expires_at=now + timedelta(seconds=expires_in_seconds) if expires_in_seconds else None
        )

        with self._lock:
            self._alerts[alert.id] = alert

        # Notify callbacks
        self._notify("created", alert)

        logger.info(f"Alert created: {alert.id} - {title} [{severity.value}]")
        return alert

    def acknowledge_alert(
        self,
        alert_id: str,
        user: str,
        note: str = ""
    ) -> Optional[Alert]:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert ID
            user: User acknowledging
            note: Optional note

        Returns:
            Updated Alert or None
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if not alert:
                return None

            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now()
            alert.acknowledged_by = user
            alert.updated_at = datetime.now()

            if note:
                alert.details["acknowledgment_note"] = note

        self._notify("updated", alert)
        logger.info(f"Alert acknowledged: {alert_id} by {user}")
        return alert

    def update_alert_status(
        self,
        alert_id: str,
        status: AlertStatus,
        user: str = None,
        note: str = ""
    ) -> Optional[Alert]:
        """
        Update alert status.

        Args:
            alert_id: Alert ID
            status: New status
            user: User making the change
            note: Optional note

        Returns:
            Updated Alert or None
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if not alert:
                return None

            old_status = alert.status
            alert.status = status
            alert.updated_at = datetime.now()

            if note:
                alert.details["status_note"] = note

            if status == AlertStatus.RESOLVED:
                alert.resolved_at = datetime.now()
                alert.resolved_by = user

                # Move to resolved history
                self._resolved_alerts.append(alert)
                del self._alerts[alert_id]

                # Trim history
                if len(self._resolved_alerts) > self._max_resolved_history:
                    self._resolved_alerts = self._resolved_alerts[-self._max_resolved_history:]

                self._notify("resolved", alert)
            else:
                self._notify("updated", alert)

        logger.info(f"Alert {alert_id} status changed: {old_status.value} -> {status.value}")
        return alert

    def resolve_alert(
        self,
        alert_id: str,
        user: str,
        resolution: str = ""
    ) -> Optional[Alert]:
        """
        Resolve an alert.

        Args:
            alert_id: Alert ID
            user: User resolving
            resolution: Resolution description

        Returns:
            Resolved Alert or None
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert and resolution:
                alert.details["resolution"] = resolution

        return self.update_alert_status(
            alert_id,
            AlertStatus.RESOLVED,
            user=user,
            note=resolution
        )

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID"""
        with self._lock:
            return self._alerts.get(alert_id)

    def get_active_alerts(
        self,
        severity: AlertSeverity = None,
        source: AlertSource = None,
        status: AlertStatus = None,
        entity_type: str = None,
        limit: int = 100
    ) -> List[Alert]:
        """
        Get active alerts with optional filtering.

        Args:
            severity: Filter by severity
            source: Filter by source
            status: Filter by status
            entity_type: Filter by entity type
            limit: Maximum alerts to return

        Returns:
            List of matching alerts
        """
        with self._lock:
            alerts = list(self._alerts.values())

            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            if source:
                alerts = [a for a in alerts if a.source == source]
            if status:
                alerts = [a for a in alerts if a.status == status]
            if entity_type:
                alerts = [a for a in alerts if a.entity_type == entity_type]

            # Sort by severity and creation time
            severity_order = {
                AlertSeverity.CRITICAL: 0,
                AlertSeverity.HIGH: 1,
                AlertSeverity.MEDIUM: 2,
                AlertSeverity.LOW: 3,
                AlertSeverity.INFO: 4
            }
            alerts.sort(key=lambda a: (severity_order[a.severity], a.created_at))

            return alerts[:limit]

    def get_summary(self) -> AlertSummary:
        """Get alert summary statistics"""
        with self._lock:
            active_alerts = list(self._alerts.values())
            active_non_resolved = [
                a for a in active_alerts
                if a.status != AlertStatus.RESOLVED
            ]

            # By severity
            by_severity = {}
            for sev in AlertSeverity:
                count = sum(1 for a in active_non_resolved if a.severity == sev)
                if count > 0:
                    by_severity[sev.value] = count

            # By source
            by_source = {}
            for src in AlertSource:
                count = sum(1 for a in active_non_resolved if a.source == src)
                if count > 0:
                    by_source[src.value] = count

            # By status
            by_status = {}
            for stat in AlertStatus:
                count = sum(1 for a in active_non_resolved if a.status == stat)
                if count > 0:
                    by_status[stat.value] = count

            # Average resolution time
            resolution_times = [
                a.duration_seconds for a in self._resolved_alerts
                if a.resolved_at
            ]
            avg_resolution = (
                sum(resolution_times) / len(resolution_times)
                if resolution_times else 0.0
            )

            # Oldest unresolved
            oldest = min(
                (a.created_at for a in active_non_resolved),
                default=None
            )

            # Recent alerts
            recent = sorted(
                active_non_resolved,
                key=lambda a: a.created_at,
                reverse=True
            )[:10]

            return AlertSummary(
                total_active=len(active_non_resolved),
                by_severity=by_severity,
                by_source=by_source,
                by_status=by_status,
                avg_resolution_time=avg_resolution,
                oldest_unresolved=oldest,
                recent_alerts=recent
            )

    def add_suppression_rule(
        self,
        source: AlertSource = None,
        entity_type: str = None,
        entity_id: str = None,
        tags: List[str] = None,
        expires_at: datetime = None
    ):
        """Add an alert suppression rule"""
        rule = {
            "source": source,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "tags": tags or [],
            "expires_at": expires_at
        }
        self._suppression_rules.append(rule)

    def _is_suppressed(
        self,
        source: AlertSource,
        entity_type: str,
        entity_id: str,
        tags: List[str]
    ) -> bool:
        """Check if alert matches suppression rules"""
        now = datetime.now()
        tags = tags or []

        for rule in self._suppression_rules:
            # Check expiration
            if rule["expires_at"] and rule["expires_at"] < now:
                continue

            # Check matches
            if rule["source"] and rule["source"] != source:
                continue
            if rule["entity_type"] and rule["entity_type"] != entity_type:
                continue
            if rule["entity_id"] and rule["entity_id"] != entity_id:
                continue
            if rule["tags"] and not any(t in tags for t in rule["tags"]):
                continue

            return True

        return False

    def _find_correlation(
        self,
        source: AlertSource,
        entity_type: str,
        entity_id: str
    ) -> Optional[str]:
        """Find correlation with existing alerts"""
        cutoff = datetime.now() - timedelta(seconds=self._correlation_window)

        with self._lock:
            for alert in self._alerts.values():
                if (
                    alert.source == source and
                    alert.entity_type == entity_type and
                    alert.entity_id == entity_id and
                    alert.created_at >= cutoff and
                    alert.status != AlertStatus.RESOLVED
                ):
                    return alert.correlation_id or alert.id

        return None

    def add_callback(self, event: str, callback: Callable[[Alert], None]):
        """Add callback for alert events (created, updated, resolved, escalated)"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _notify(self, event: str, alert: Alert):
        """Notify callbacks for an event"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    async def _check_escalations(self):
        """Check for alerts needing escalation"""
        now = datetime.now()

        with self._lock:
            for alert in self._alerts.values():
                if alert.status in [AlertStatus.RESOLVED, AlertStatus.SUPPRESSED]:
                    continue

                thresholds = self.ESCALATION_THRESHOLDS.get(alert.severity, [])
                if alert.escalation_level >= len(thresholds):
                    continue

                threshold = thresholds[alert.escalation_level]
                alert_age = (now - alert.created_at).total_seconds()

                if alert_age >= threshold:
                    alert.escalation_level += 1
                    alert.updated_at = now
                    self._notify("escalated", alert)
                    logger.warning(
                        f"Alert escalated: {alert.id} to level {alert.escalation_level}"
                    )

    async def _check_expirations(self):
        """Check for expired alerts"""
        now = datetime.now()

        with self._lock:
            expired_ids = [
                aid for aid, alert in self._alerts.items()
                if alert.expires_at and alert.expires_at <= now
            ]

            for alert_id in expired_ids:
                self.update_alert_status(alert_id, AlertStatus.EXPIRED)

    async def start_monitoring(self):
        """Start background alert monitoring"""
        self._running = True
        while self._running:
            try:
                await self._check_escalations()
                await self._check_expirations()
            except Exception as e:
                logger.error(f"Alert monitoring error: {e}")
            await asyncio.sleep(self._escalation_interval)

    def stop_monitoring(self):
        """Stop background monitoring"""
        self._running = False


# Singleton instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create the singleton alert manager instance"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
